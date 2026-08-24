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
import secrets

import frappe
from frappe.utils import now_datetime, add_to_date, get_datetime, validate_email_address

from saas_manager.provisioning import provisioner

OTP_TTL_MINUTES = 15
MAX_OTP_ATTEMPTS = 5


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

    frappe.sendmail(
        recipients=[email],
        subject=f"Horizon — رمز التحقق: {otp}",
        message=f"""
        <div dir="rtl" style="font-family:Cairo,Arial;text-align:center">
          <h2 style="color:#1D2D44">Horizon AI Powered ERP</h2>
          <p style="color:#4A5361">رمز التحقق الخاص بك</p>
          <p style="font-size:32px;letter-spacing:8px;font-weight:bold;color:#1D2D44">{otp}</p>
          <p>صالح لمدة {OTP_TTL_MINUTES} دقيقة.</p>
        </div>""",
        delayed=False,
    )
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


@frappe.whitelist(allow_guest=True)
def provisioning_status(request_id: str):
    """Polled by the signup page to show live progress."""
    req = frappe.db.get_value("Signup Request", request_id,
                              ["tenant_site"], as_dict=True)
    if not req or not req.tenant_site:
        return {"status": "pending"}
    t = frappe.db.get_value("Tenant Site", req.tenant_site,
                            ["status", "site_name"], as_dict=True)
    return {"status": (t.status or "").lower(), "url": f"https://{t.site_name}"}


@frappe.whitelist(allow_guest=True)
def signup_status(request_id: str):
    """Alias of provisioning_status — the signup page polls this name."""
    return provisioning_status(request_id)
