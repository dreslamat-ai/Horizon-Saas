"""
MyFatoorah integration for automatic subscription renewal.

SECURITY MODEL
--------------
- Activation NEVER happens from webhook payload data alone. On every webhook,
  the server calls GetPaymentStatus itself and only activates on a verified
  "Paid" status. The webhook payload is treated as an untrusted hint.
- Idempotent: an invoice already marked Paid is never processed twice.
- API key lives only in the control site's site_config.json.

REQUIRED CONTROL-SITE CONFIG KEYS
---------------------------------
  "saas_mf_api_key":  "<MyFatoorah API token>",
  "saas_mf_base_url": "https://apitest.myfatoorah.com"   # test
                      # live KSA:   https://api-sa.myfatoorah.com
                      # live other: https://api.myfatoorah.com

VERIFY ON INTEGRATION (per CLAUDE.md rule): confirm current endpoint paths and
response shapes against MyFatoorah docs (v2/SendPayment, v2/GetPaymentStatus)
before going live — payment APIs evolve.
"""

import json

import frappe
import requests
from frappe.utils import now_datetime

from saas_manager.provisioning import lifecycle

TIMEOUT = 30


def _base() -> str:
    return (frappe.conf.get("saas_mf_base_url") or "https://apitest.myfatoorah.com").rstrip("/")


def _headers() -> dict:
    key = frappe.conf.get("saas_mf_api_key")
    if not key:
        frappe.throw("MyFatoorah is not configured (saas_mf_api_key missing).")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def is_configured() -> bool:
    return bool(frappe.conf.get("saas_mf_api_key"))


# ------------------------------------------------------------------ #
# invoice creation
# ------------------------------------------------------------------ #

def create_renewal_invoice(tenant: str, months: int = 1) -> "frappe.Document":
    """
    Create a SaaS Invoice + MyFatoorah payment link (SendPayment, LNK mode).
    Reuses an existing Pending invoice for the same tenant/months to avoid
    spamming the customer with duplicate links from the 7/3/1 reminders.
    """
    existing = frappe.db.get_value(
        "SaaS Invoice",
        {"tenant_site": tenant, "months": months, "status": "Pending"},
        "name",
    )
    if existing:
        return frappe.get_doc("SaaS Invoice", existing)

    site = frappe.get_doc("Tenant Site", tenant)
    plan = frappe.get_doc("SaaS Plan", site.plan)
    amount = (plan.monthly_price or 0) * months
    if amount <= 0:
        frappe.throw(f"Plan {plan.name} has no monthly_price set.")

    inv = frappe.get_doc({
        "doctype": "SaaS Invoice",
        "tenant_site": tenant,
        "plan": plan.name,
        "months": months,
        "amount": amount,
        "currency": plan.currency,
        "status": "Pending",
    }).insert(ignore_permissions=True)

    root = frappe.conf.get("saas_root_domain") or "horizonerp.cloud"
    payload = {
        "NotificationOption": "LNK",          # we deliver the link ourselves (email/الاء)
        "CustomerName": site.customer_name or site.subdomain,
        "CustomerEmail": site.email,
        "InvoiceValue": float(amount),
        "DisplayCurrencyIso": plan.currency,
        "CustomerReference": inv.name,        # ties MF invoice back to us
        "CallBackUrl": f"https://control.{root}/renewed",
        "ErrorUrl": f"https://control.{root}/renewed?err=1",
        "Language": "AR",
    }
    resp = requests.post(f"{_base()}/v2/SendPayment", headers=_headers(),
                         data=json.dumps(payload), timeout=TIMEOUT)
    data = resp.json()
    if not data.get("IsSuccess"):
        inv.db_set("status", "Failed")
        inv.db_set("notes", json.dumps(data)[:500])
        frappe.throw(f"MyFatoorah SendPayment failed: {data.get('Message')}")

    inv.db_set("mf_invoice_id", str(data["Data"]["InvoiceId"]))
    inv.db_set("payment_url", data["Data"]["InvoiceURL"])
    frappe.db.commit()
    return inv


# ------------------------------------------------------------------ #
# verification + webhook
# ------------------------------------------------------------------ #

def verify_paid(mf_invoice_id: str) -> bool:
    """Server-side truth: ask MyFatoorah directly."""
    resp = requests.post(
        f"{_base()}/v2/GetPaymentStatus", headers=_headers(),
        data=json.dumps({"Key": str(mf_invoice_id), "KeyType": "InvoiceId"}),
        timeout=TIMEOUT,
    )
    data = resp.json()
    return bool(data.get("IsSuccess")) and data["Data"].get("InvoiceStatus") == "Paid"


def _settle(inv) -> str:
    """Verify with MyFatoorah and activate if truly paid. Idempotent."""
    if inv.status == "Paid":
        return "already-paid"
    if not verify_paid(inv.mf_invoice_id):
        return "not-paid-yet"
    inv.db_set("status", "Paid")
    inv.db_set("paid_on", now_datetime())
    frappe.db.commit()
    lifecycle.activate(inv.tenant_site, months=inv.months)
    frappe.db.commit()
    try:
        from saas_manager import emails
        t = frappe.get_doc("Tenant Site", inv.tenant_site)
        emails.send_payment_confirmed(t, inv.name, f"{inv.amount} {inv.currency}",
                                      t.subscription_ends_on)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Payment email failed: {inv.name}")
    return "activated"


@frappe.whitelist(allow_guest=True)
def webhook():
    """
    MyFatoorah webhook / callback receiver. Payload shapes vary by event type,
    so we only extract candidate ids and re-verify everything server-side.
    """
    try:
        payload = frappe.request.get_json(silent=True) or {}
    except Exception:
        payload = {}
    data = payload.get("Data") or payload
    mf_id = str(data.get("InvoiceId") or data.get("invoiceId") or "").strip()
    ref = str(data.get("CustomerReference") or data.get("customerReference") or "").strip()

    name = None
    if mf_id:
        name = frappe.db.get_value("SaaS Invoice", {"mf_invoice_id": mf_id}, "name")
    if not name and ref and frappe.db.exists("SaaS Invoice", ref):
        name = ref
    if not name:
        frappe.local.response["http_status_code"] = 200  # ack anyway; nothing to do
        return {"status": "ignored"}

    result = _settle(frappe.get_doc("SaaS Invoice", name))
    return {"status": result}


@frappe.whitelist()
def reconcile_pending():
    """
    Safety net (also scheduled daily): if a webhook was ever missed, verify all
    Pending invoices directly and activate the paid ones.
    """
    for name in frappe.get_all("SaaS Invoice", filters={"status": "Pending"}, pluck="name"):
        try:
            _settle(frappe.get_doc("SaaS Invoice", name))
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"MF reconcile failed: {name}")
