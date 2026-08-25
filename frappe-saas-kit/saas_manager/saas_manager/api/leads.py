"""
Lead capture from the public cost-leakage calculator.

Threat model for a guest-writable endpoint:
  - it creates records, so it is rate-limited per IP exactly like signup
  - every field is length-capped before it reaches the database
  - the estimate is recomputed server-side is NOT possible (the visitor owns
    their own inputs), so it is stored as a claim, clearly labelled as
    self-estimated — never treated as a verified figure
  - a repeat submission from the same email updates the existing lead instead
    of piling up duplicates for the sales team
"""

import json

import frappe
from frappe.utils import now_datetime, validate_email_address

from saas_manager import emails
from saas_manager.api.signup import _rate_limit

MODES = {"mfg": "Manufacturing", "con": "Contracting"}


def _clip(value, length: int) -> str:
    return (str(value or "").strip())[:length]


@frappe.whitelist(allow_guest=True)
def calculator_lead(name: str, email: str, company: str = "", phone: str = "",
                    mode: str = "", estimate: float = 0, inputs: str = ""):
    """Record a lead from the calculator and email the visitor their summary."""
    _rate_limit(f"lead:{frappe.local.request_ip}", limit=8)

    email = _clip(email, 140).lower()
    if not email or not validate_email_address(email):
        frappe.throw("Please enter a valid email address.")

    contact = _clip(name, 140)
    if not contact:
        frappe.throw("Please enter your name.")

    try:
        estimate = max(0.0, float(estimate or 0))
    except (TypeError, ValueError):
        estimate = 0.0

    payload = {
        "contact_name": contact,
        "company": _clip(company, 140),
        "phone": _clip(phone, 40),
        "calc_mode": MODES.get(mode, ""),
        "estimate": estimate,
        "inputs_json": _clip(inputs, 500),
    }

    existing = frappe.db.get_value("SaaS Lead", {"email": email, "source": "Cost Calculator"}, "name")
    if existing:
        doc = frappe.get_doc("SaaS Lead", existing)
        doc.update(payload)                      # refresh with the latest run
        doc.save(ignore_permissions=True)
    else:
        doc = frappe.get_doc({
            "doctype": "SaaS Lead",
            "email": email,
            "source": "Cost Calculator",
            "status": "New",
            **payload,
        }).insert(ignore_permissions=True)

    frappe.db.commit()

    try:
        emails.send_calculator_report(doc)
        doc.db_set("report_sent_on", now_datetime())
        frappe.db.commit()
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Calculator report failed: {doc.name}")

    return {"ok": True, "lead": doc.name}
