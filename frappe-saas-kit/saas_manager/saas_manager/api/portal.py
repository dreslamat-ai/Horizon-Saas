"""بوابة العميل — طلبات التجديد والترقية من صفحة /subscription داخل موقعه.

كل طلب: يتوثق على سجل Tenant Site + إشعار تليجرام فوري للمالك.
لو MyFatoorah مهيأة، التجديد يرجع رابط دفع مباشرًا بدل وضع الطلب.
"""

import frappe
from frappe.utils import cint

from saas_manager.api.signup import _rate_limit, notify_owner_telegram as _notify_telegram


@frappe.whitelist(allow_guest=True)
def request_service(site: str, kind: str, plan: str = "", months: int = 1):
    _rate_limit(f"portal:{frappe.local.request_ip}", limit=20)

    if kind not in ("renew", "upgrade"):
        frappe.throw("Invalid request kind.")

    t = frappe.db.get_value(
        "Tenant Site", {"site_name": site, "status": ["!=", "Dropped"]},
        ["name", "customer_name", "email", "plan", "status"], as_dict=True,
    )
    if not t:
        frappe.throw("Unknown site.")

    months = max(1, min(cint(months) or 1, 12))
    if kind == "upgrade":
        if not frappe.db.exists("SaaS Plan", {"name": plan, "enabled": 1}):
            frappe.throw("Invalid plan.")
        detail = f"طلب ترقية: {t.plan} ← {plan}"
    else:
        detail = f"طلب تجديد: {months} شهر على باقة {t.plan}"

    frappe.get_doc({
        "doctype": "Comment",
        "comment_type": "Info",
        "reference_doctype": "Tenant Site",
        "reference_name": t.name,
        "content": detail,
    }).insert(ignore_permissions=True)
    frappe.db.commit()

    _notify_telegram(
        f"💰 {detail}\n"
        f"العميل: {t.customer_name}\n"
        f"الموقع: {site}\n"
        f"البريد: {t.email}\n"
        f"نفّذها من لوحة التحكم: Tenant Site ← {t.name}"
    )

    # دفع مباشر للتجديد لو MyFatoorah مهيأة — الترقية بتظل طلبًا لأن قيمتها
    # تُحسب على الباقة الجديدة بعد اعتماد المالك
    if kind == "renew":
        try:
            from saas_manager.payments import myfatoorah
            if myfatoorah.is_configured():
                inv = myfatoorah.create_renewal_invoice(t.name, months=months)
                return {"mode": "pay", "url": inv.payment_url}
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"MF link failed: {t.name}")

    return {
        "mode": "request",
        "message": "وصل طلبك ✅ — فريق Horizon هيتواصل معك في نفس اليوم لإتمام السداد والتفعيل.",
    }
