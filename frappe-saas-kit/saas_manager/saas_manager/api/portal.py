"""بوابة العميل — طلبات التجديد والترقية من صفحة /subscription داخل موقعه.

كل طلب: يتوثق على سجل Tenant Site + إشعار تليجرام فوري للمالك.
لو MyFatoorah مهيأة، التجديد يرجع رابط دفع مباشرًا بدل وضع الطلب.
"""

import frappe
from frappe.utils import cint

from saas_manager.api.signup import _rate_limit, notify_owner_telegram as _notify_telegram


@frappe.whitelist(allow_guest=True)
def request_service(site: str, kind: str, plan: str = "", months: int = 1, points: int = 0):
    _rate_limit(f"portal:{frappe.local.request_ip}", limit=20)

    if kind not in ("renew", "upgrade", "alaa_points", "alaa_plan"):
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
    elif kind == "alaa_points":
        # الشحن الفعلي يدوي من لوحة إعدادات ألاء بعد تأكيد السداد —
        # زي التجديد قبل MyFatoorah بالضبط: طلب + تليجرام، لا تنفيذ آلي.
        points = max(100, min(cint(points) or 0, 50000))
        detail = f"طلب شحن نقاط ألاء: {points} نقطة"
    elif kind == "alaa_plan":
        # اسم باقة ألاء حر (مصدره alaa_plans عند ألاء لا SaaS Plan هنا) —
        # يُقصّ فقط، والتحقق الفعلي بشري: التفعيل يدوي من لوحة ألاء بعد السداد
        plan = (plan or "").strip()[:60]
        if not plan:
            frappe.throw("Invalid plan.")
        detail = f"طلب باقة ألاء: {plan}"
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


@frappe.whitelist(allow_guest=True)
def alaa_status(site: str):
    """رصيد ألاء وباقتها لموقع مستأجر — تعرضه صفحة /subscription داخل موقعه.

    البروكسي هنا (control ← واجهة ألاء الداخلية على 127.0.0.1) عمدًا:
    مفتاح ألاء الداخلي يبقى في site_config بتاع control وحده، لا يوزَّع
    على مواقع المستأجرين ولا يظهر لأي متصفح.
    """
    _rate_limit(f"alaa-status:{frappe.local.request_ip}", limit=30)

    if not frappe.db.exists("Tenant Site", {"site_name": site, "status": ["!=", "Dropped"]}):
        frappe.throw("Unknown site.")

    internal_key = frappe.conf.get("alaa_internal_key")
    alaa_url = frappe.conf.get("alaa_internal_url") or "http://127.0.0.1:4001/alaa"
    if not internal_key:
        return {"enabled": False}

    import json as _json
    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        f"{alaa_url}/api/internal/balance?site={site}",
        headers={"x-internal-key": internal_key},
    )
    try:
        data = _json.loads(urllib.request.urlopen(req, timeout=10).read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"enabled": False}
        raise
    except Exception:
        # ألاء واقفة مؤقتًا ≠ الموقع بلا ألاء — الصفحة تخفي الكارت بس
        return {"enabled": False}

    # باقات ألاء المتاحة للترقية — فشلها لا يُسقط عرض الرصيد
    plans = []
    try:
        preq = urllib.request.Request(
            f"{alaa_url}/api/internal/plans", headers={"x-internal-key": internal_key},
        )
        plans = _json.loads(urllib.request.urlopen(preq, timeout=10).read().decode()).get("plans") or []
    except Exception:
        pass

    return {
        "enabled": True,
        "credits_balance": data.get("creditsBalance"),
        "subscription_status": data.get("subscriptionStatus"),
        "subscription_end_date": (data.get("subscriptionEndDate") or "")[:10],
        "plan": data.get("plan"),
        "plans": plans,
    }
