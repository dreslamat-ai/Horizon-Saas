"""
Lifecycle automation: activation, suspension, resume, expiry enforcement,
expiry notices (30/15/7-style ladder -> here 7/3/1 for trials), backups, drop.
All bench calls go through provisioner.run_bench (safe arg lists).
"""

import frappe
from frappe.utils import add_months, add_days, nowdate, now_datetime, date_diff

from saas_manager.provisioning.provisioner import run_bench, _log

GRACE_DAYS = 3          # grace period after subscription end before suspension
DROP_AFTER_DAYS = 60    # suspended sites older than this are archived+dropped (manual by default)


# ------------------------------------------------------------------ #
# activation / suspension
# ------------------------------------------------------------------ #

def activate(tenant: str, months: int = 1):
    """Called by admin after confirming bank transfer, or by a payment webhook."""
    doc = frappe.get_doc("Tenant Site", tenant)
    base = doc.subscription_ends_on if (
        doc.subscription_ends_on and str(doc.subscription_ends_on) >= nowdate()
    ) else nowdate()
    doc.db_set("subscription_ends_on", add_months(base, months))
    run_bench(["--site", doc.site_name, "set-config", "saas_subscription_ends_on",
               str(doc.subscription_ends_on)], tenant)
    if doc.status == "Suspended":
        resume(tenant)
    else:
        frappe.db.commit()
    _log(tenant, f"Activated/extended by {months} month(s) until {doc.subscription_ends_on}.")


def suspend(tenant: str, reason: str = ""):
    doc = frappe.get_doc("Tenant Site", tenant)
    site = doc.site_name
    # maintenance mode blocks all requests; pause_scheduler stops jobs
    run_bench(["--site", site, "set-config", "maintenance_mode", "1", "--parse"], tenant)
    run_bench(["--site", site, "set-config", "pause_scheduler", "1", "--parse"], tenant)
    doc.db_set("status", "Suspended")
    doc.db_set("suspended_on", nowdate())
    frappe.db.commit()
    _log(tenant, f"Suspended. {reason}")
    _notify(doc, "تم إيقاف اشتراكك مؤقتًا",
            "تم إيقاف النظام لانتهاء الاشتراك. للتفعيل قم بتحويل قيمة الباقة وسيتم إعادة التشغيل فورًا.")


def resume(tenant: str):
    doc = frappe.get_doc("Tenant Site", tenant)
    site = doc.site_name
    run_bench(["--site", site, "set-config", "maintenance_mode", "0", "--parse"], tenant)
    run_bench(["--site", site, "set-config", "pause_scheduler", "0", "--parse"], tenant)
    doc.db_set("status", "Active")
    doc.db_set("suspended_on", None)
    frappe.db.commit()
    _log(tenant, "Resumed.")
    _notify(doc, "تم إعادة تفعيل حسابك ✅", "رجعنا شغالين! نظامك متاح الآن بشكل كامل.")


# ------------------------------------------------------------------ #
# scheduler jobs (control plane)
# ------------------------------------------------------------------ #

def enforce_expiries():
    """Daily: suspend Active sites whose subscription ended more than GRACE_DAYS ago."""
    rows = frappe.get_all(
        "Tenant Site",
        filters={"status": "Active", "subscription_ends_on": ["<", add_days(nowdate(), -GRACE_DAYS)]},
        pluck="name",
    )
    for name in rows:
        try:
            suspend(name, reason="Subscription expired (auto).")
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Auto-suspend failed: {name}")


def send_expiry_notices():
    """Daily: notify owners 7 / 3 / 1 days before subscription end."""
    for days in (7, 3, 1):
        target = add_days(nowdate(), days)
        rows = frappe.get_all(
            "Tenant Site",
            filters={"status": "Active", "subscription_ends_on": target},
            fields=["name", "email", "customer_name", "subscription_ends_on", "plan"],
        )
        for r in rows:
            doc = frappe.get_doc("Tenant Site", r.name)
            body = (f"باقتك ({r.plan}) تنتهي يوم {r.subscription_ends_on}. "
                    "جدّد بالتحويل البنكي وسيتم التفعيل فور التأكيد.")
            try:
                from saas_manager.payments import myfatoorah
                if myfatoorah.is_configured():
                    inv = myfatoorah.create_renewal_invoice(r.name, months=1)
                    body = (f"باقتك ({r.plan}) تنتهي يوم {r.subscription_ends_on}.<br>"
                            f'<a href="{inv.payment_url}" style="display:inline-block;'
                            f'background:#1D2D44;color:#fff;padding:10px 22px;'
                            f'border-radius:10px;text-decoration:none;font-weight:bold">'
                            f"جدّد الآن — {inv.amount} {inv.currency}</a><br>"
                            "الدفع آمن عبر MyFatoorah والتفعيل فوري وتلقائي. "
                            "التحويل البنكي متاح أيضًا كخيار بديل.")
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"MF link failed: {r.name}")
            _notify(doc, f"اشتراكك ينتهي خلال {days} يوم", body)


def backup_all_active_sites():
    for name in frappe.get_all("Tenant Site", filters={"status": "Active"}, pluck="name"):
        frappe.enqueue(
            "saas_manager.provisioning.lifecycle.backup_site",
            queue="long", timeout=1800, tenant=name,
        )


def backup_site(tenant: str):
    doc = frappe.get_doc("Tenant Site", tenant)
    run_bench(["--site", doc.site_name, "backup", "--with-files"], tenant, timeout=1800)
    doc.db_set("last_backup_on", now_datetime())
    frappe.db.commit()
    # Optional: sync ./sites/{site}/private/backups to S3 via rclone/awscli here.


def drop_site(tenant: str, db_root_password: str | None = None):
    """
    DESTRUCTIVE — intentionally manual-only (no scheduler wiring).
    Takes a final backup, then drops the site into the archive path.
    """
    doc = frappe.get_doc("Tenant Site", tenant)
    if doc.status != "Suspended":
        frappe.throw("Only suspended sites can be dropped.")
    if date_diff(nowdate(), doc.suspended_on or nowdate()) < DROP_AFTER_DAYS:
        frappe.throw(f"Site must be suspended for at least {DROP_AFTER_DAYS} days.")
    backup_site(tenant)
    db_root = db_root_password or frappe.conf.get("saas_db_root_password")
    run_bench(["drop-site", doc.site_name, "--db-root-password", db_root, "--force"],
              tenant, timeout=1800)
    doc.db_set("status", "Dropped")
    frappe.db.commit()


# ------------------------------------------------------------------ #

def _notify(doc, subject: str, body: str):
    try:
        frappe.sendmail(
            recipients=[doc.email],
            subject=subject,
            message=(
                f'<div dir="rtl" style="font-family:Cairo,Arial;color:#221f1f">{body}'
                f'<p style="color:#5083BC;font-weight:bold">— الاء | Horizon Smart Systems</p></div>'
            ),
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Notify failed: {doc.name}")
