"""
Lifecycle automation: activation, suspension, resume, expiry enforcement,
expiry notices (30/15/7-style ladder -> here 7/3/1 for trials), backups, drop.
All bench calls go through provisioner.run_bench (safe arg lists).
"""

import frappe

from saas_manager import emails
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
    pay_url = ""
    try:
        from saas_manager.payments import myfatoorah
        if myfatoorah.is_configured():
            pay_url = myfatoorah.create_renewal_invoice(tenant, months=1).payment_url
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"MF link failed on suspend: {tenant}")
    emails.send_suspended(doc, pay_url=pay_url)


def resume(tenant: str):
    doc = frappe.get_doc("Tenant Site", tenant)
    site = doc.site_name
    run_bench(["--site", site, "set-config", "maintenance_mode", "0", "--parse"], tenant)
    run_bench(["--site", site, "set-config", "pause_scheduler", "0", "--parse"], tenant)
    doc.db_set("status", "Active")
    doc.db_set("suspended_on", None)
    frappe.db.commit()
    _log(tenant, "Resumed.")
    emails.send_resumed(doc)


# ------------------------------------------------------------------ #
# scheduler jobs (control plane)
# ------------------------------------------------------------------ #

def enforce_expiries():
    """Daily: suspend Active sites whose subscription ended more than GRACE_DAYS ago.

    🔴 حادثة ٢٤ أغسطس ٢٠٢٦ (منتصف الليل KSA): مواقع الإنتاج العشرة المسجَّلة
    كبيانات وصفية كانت subscription_ends_on فيها NULL — وفرابي يبني شرط
    التاريخ بـ ifnull(..., '') والسلسلة الفاضية "أصغر من" أي تاريخ، فاعتُبرت
    كلها "منتهية من الأزل" وعُلِّقت جميعًا (maintenance_mode) في أول تشغيلة
    ليلية. من هنا: **بلا تاريخ انتهاء = لا إنفاذ إطلاقًا** — الموقع الذي لا
    يُدار اشتراكه من المنصة لا تعلّقه المنصة أبدًا.
    """
    rows = frappe.get_all(
        "Tenant Site",
        filters=[
            ["status", "=", "Active"],
            ["subscription_ends_on", "is", "set"],
            ["subscription_ends_on", "<", add_days(nowdate(), -GRACE_DAYS)],
        ],
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
            pay_url, amount = "", ""
            try:
                from saas_manager.payments import myfatoorah
                if myfatoorah.is_configured():
                    inv = myfatoorah.create_renewal_invoice(r.name, months=1)
                    pay_url = inv.payment_url
                    amount = f"{inv.amount} {inv.currency}"
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"MF link failed: {r.name}")
            emails.send_expiry_notice(doc, days, r.plan, r.subscription_ends_on,
                                      pay_url=pay_url, amount=amount)


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

