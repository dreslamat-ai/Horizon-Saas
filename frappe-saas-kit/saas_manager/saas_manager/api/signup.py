"""
Public signup API (guest-accessible) — the front door of the SaaS.

Flow:
  1. check_subdomain(subdomain)          -> live availability check
  2. request_signup(...)                 -> creates Signup Request + emails OTP
  3. verify_otp(request_id, otp)         -> verifies email, creates Tenant Site,
                                            queues provisioning automatically
Rate limiting uses frappe.rate_limiter via decorators-by-cache (simple manual
counters here to stay version-agnostic).
"""

import hashlib
import json as _json
import secrets
import urllib.request

import frappe

from saas_manager import emails
from frappe.utils import now_datetime, add_to_date, get_datetime, validate_email_address

from saas_manager.provisioning import provisioner

OTP_TTL_MINUTES = 15
MAX_OTP_ATTEMPTS = 5


def notify_owner_telegram(text: str):
    """إشعار تليجرام فوري للمالك — saas_tg_token/saas_tg_chat من site_config.
    الفشل يُسجَّل ولا يكسر مسار العميل أبدًا."""
    token = frappe.conf.get("saas_tg_token")
    chat = frappe.conf.get("saas_tg_chat")
    if not (token and chat):
        return
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=_json.dumps({"chat_id": chat, "text": text}).encode(),
            headers={"Content-Type": "application/json",
                     "User-Agent": "horizon-saas/1.0"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=15)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Signup telegram notify failed")


def _hash_otp(otp: str) -> str:
    return hashlib.sha256(otp.encode()).hexdigest()


def _rate_limit(key: str, limit: int, window_sec: int = 3600):
    cache_key = f"saas_rl:{key}"
    count = frappe.cache().get_value(cache_key) or 0
    if int(count) >= limit:
        frappe.throw("Too many attempts. Try again later.", frappe.TooManyRequestsError)
    frappe.cache().set_value(cache_key, int(count) + 1, expires_in_sec=window_sec)


# ------------------------------------------------------------------ #

@frappe.whitelist(allow_guest=True)
def get_plans():
    return frappe.get_all(
        "SaaS Plan",
        filters={"enabled": 1},
        fields=["name", "plan_name", "monthly_price", "currency",
                "max_users", "max_space_mb", "trial_days"],
        order_by="monthly_price asc",
    )


@frappe.whitelist(allow_guest=True)
def check_subdomain(subdomain: str):
    subdomain = provisioner.validate_subdomain(subdomain)
    taken = frappe.db.exists("Tenant Site", {"subdomain": subdomain,
                                             "status": ["!=", "Dropped"]})
    return {"subdomain": subdomain, "available": not bool(taken)}


@frappe.whitelist(allow_guest=True)
def request_signup(business_name: str, email: str, subdomain: str,
                   plan: str, phone: str = "", country: str = "",
                   contact_name: str = ""):
    _rate_limit(f"signup:{frappe.local.request_ip}", limit=10)

    email = validate_email_address(email, throw=True)
    subdomain = provisioner.validate_subdomain(subdomain)

    if not frappe.db.exists("SaaS Plan", {"name": plan, "enabled": 1}):
        frappe.throw("Invalid plan.")
    if frappe.db.exists("Tenant Site", {"subdomain": subdomain,
                                        "status": ["!=", "Dropped"]}):
        frappe.throw("Subdomain already taken.")

    otp = f"{secrets.randbelow(1000000):06d}"

    req = frappe.get_doc({
        "doctype": "Signup Request",
        "business_name": business_name.strip()[:140],
        "contact_name": (contact_name or "").strip()[:140],
        "email": email,
        "phone": (phone or "").strip()[:30],
        "country": (country or "").strip()[:60],
        "subdomain": subdomain,
        "plan": plan,
        "status": "Pending OTP",
        "otp_hash": _hash_otp(otp),
        "otp_expires_at": add_to_date(now_datetime(), minutes=OTP_TTL_MINUTES),
    }).insert(ignore_permissions=True)
    frappe.db.commit()

    emails.send_otp(email, otp, minutes=OTP_TTL_MINUTES)
    return {"request_id": req.name}


@frappe.whitelist(allow_guest=True)
def verify_otp(request_id: str, otp: str):
    _rate_limit(f"otp:{frappe.local.request_ip}", limit=20)

    req = frappe.get_doc("Signup Request", request_id)

    if req.status != "Pending OTP":
        frappe.throw("This request is already processed.")
    if req.attempts >= MAX_OTP_ATTEMPTS:
        req.db_set("status", "Expired")
        frappe.throw("Too many wrong attempts. Start over.")
    if get_datetime(req.otp_expires_at) < now_datetime():
        req.db_set("status", "Expired")
        frappe.throw("OTP expired. Start over.")

    req.db_set("attempts", req.attempts + 1)
    if _hash_otp((otp or "").strip()) != req.otp_hash:
        frappe.db.commit()
        frappe.throw("Wrong code.")

    # verified -> create tenant + queue provisioning (fully automatic)
    req.db_set("verified", 1)
    req.db_set("status", "Verified")

    tenant = frappe.get_doc({
        "doctype": "Tenant Site",
        "subdomain": req.subdomain,
        "site_name": provisioner.full_site_name(req.subdomain),
        "status": "Pending",
        "plan": req.plan,
        "customer_name": req.business_name,
        "contact_name": req.get("contact_name"),
        "email": req.email,
        "phone": req.phone,
        "country": req.get("country"),
    }).insert(ignore_permissions=True)

    req.db_set("tenant_site", tenant.name)
    req.db_set("status", "Provisioned")
    frappe.db.commit()

    # إشعار المالك بكل تسجيل مؤكَّد — طلب صريح: «كل تسجيل يحصل يجيلي
    # إشعار ببيانات العميل الجديد»
    notify_owner_telegram(
        "🎉 عميل جديد سجّل في Horizon SaaS\n"
        f"النشاط: {req.business_name}\n"
        f"المسؤول: {req.get('contact_name') or '—'}\n"
        f"البريد: {req.email}\n"
        f"الجوال: {req.phone or '—'}\n"
        f"الدولة: {req.get('country') or 'Saudi Arabia'}\n"
        f"الموقع: {tenant.site_name}\n"
        f"الباقة: {req.plan} (تجربة)\n"
        "التجهيز شغّال دلوقتي — هيوصله بريد ببيانات دخوله خلال دقائق."
    )

    frappe.enqueue(
        "saas_manager.provisioning.provisioner.provision_site",
        queue="long", timeout=3600, tenant=tenant.name,
    )

    return {
        "site": tenant.site_name,
        "url": f"https://{tenant.site_name}",
        "status": "provisioning",
        "message": "جاري تجهيز نظامك — هيوصلك إيميل ببيانات الدخول خلال دقائق.",
    }


# أسماء ودّية للتطبيقات وهي بتتركب — بتظهر في شريحة الحالة تحت المعاينة
_APP_LABELS = {
    "erpnext": "وحدات ERP الأساسية (مبيعات · مشتريات · مخزون · حسابات)",
    "hrms": "الموارد البشرية والرواتب",
    "horizon_client": "بوابة اشتراكك وحدود باقتك",
    "horizon_desk_theme": "هوية Horizon البصرية",
    "alaa_widget": "مساعدتك الذكية ألاء",
}


def _current_step(log: str) -> tuple[str, str]:
    """آخر أمر RUN في provisioning_log يحدد الخطوة الفعلية.

    بلاغ المالك (٢٥ أغسطس): شريط التقدم كان بيقف على خطوة واحدة طول
    الدقائق لأن الحالة "Provisioning" ثابتة — التصنيف هنا مبني على تسلسل
    أوامر حقيقي من لوج تجهيز heliumai (لا على تخمين ترتيب الكود).
    الخطوات: queue ⟵ site ⟵ apps ⟵ config ⟵ user ⟵ alaa.
    """
    last = ""
    for line in reversed((log or "").splitlines()):
        if "RUN: " in line:
            last = line
            break
    if not last:
        return "queue", ""
    if "saas_subscription_ends_on" in last or "alaa" in last or " backup" in last             or last.rstrip().endswith("clear-cache") or "list-apps" in last:
        # كل ذيل التجهيز (سر SSO، تركيب الودجت، المفاتيح، الباكب الأول)
        return "alaa", ""
    if "install-app" in last:
        app = last.rsplit("install-app", 1)[-1].strip().split()[0] if "install-app " in last else ""
        return "apps", _APP_LABELS.get(app, app)
    if "setup_wizard" in last:
        return "user", "بنجهّز شركتك: عربي · ريال سعودي · دليل حسابات مرقّم"
    if "add-system-manager" in last:
        return "user", "بننشئ حسابك كمدير للنظام"
    if "set-config" in last or "Website Se" in last or "clear-website-cache" in last:
        return "config", ""
    if "new-site" in last:
        return "site", ""
    return "site", ""


def _avg_provision_seconds() -> int:
    """متوسط زمن آخر ٥ تجهيزات ناجحة — تقدير العدّاد يتحدث لوحده مع كل
    تجهيز بدل رقم ثابت يكدب أول ما السيرفر يتقل أو يخف."""
    row = frappe.db.sql(
        """SELECT AVG(s) FROM (
             SELECT TIMESTAMPDIFF(SECOND, creation, provisioned_on) AS s
             FROM `tabTenant Site`
             WHERE provisioned_on IS NOT NULL AND provisioned_on > creation
             ORDER BY provisioned_on DESC LIMIT 5) x""")
    avg = int(row[0][0] or 0) if row else 0
    # حدا أمان: تقدير خارج النطاق المعقول (سجل معطوب/موقع مستورد) يرجع للافتراضي
    return avg if 90 <= avg <= 900 else 240


@frappe.whitelist(allow_guest=True)
def provisioning_status(request_id: str):
    """Polled by the signup page to show live progress."""
    req = frappe.db.get_value("Signup Request", request_id,
                              ["tenant_site"], as_dict=True)
    if not req or not req.tenant_site:
        return {"status": "pending"}
    t = frappe.db.get_value("Tenant Site", req.tenant_site,
                            ["status", "site_name", "provisioning_log", "creation"], as_dict=True)
    out = {"status": (t.status or "").lower(), "url": f"https://{t.site_name}"}
    if out["status"] == "provisioning":
        out["step"], out["detail"] = _current_step(t.provisioning_log)
        from frappe.utils import now_datetime, get_datetime
        out["elapsed"] = max(0, int((now_datetime() - get_datetime(t.creation)).total_seconds()))
        out["estimate"] = _avg_provision_seconds()
    return out


@frappe.whitelist(allow_guest=True)
def signup_status(request_id: str):
    """Alias of provisioning_status — the signup page polls this name."""
    return provisioning_status(request_id)
