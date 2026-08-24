import frappe
from frappe.utils import cint, date_diff, nowdate


def get_context(context):
    """صفحة «اشتراكي» — العميل يشوف باقته واستخدامه ويطلب تجديدًا أو ترقية."""
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/subscription"
        raise frappe.Redirect

    context.no_cache = 1
    conf = frappe.conf
    context.plan = conf.get("saas_plan") or "Horizon"
    ends = conf.get("saas_subscription_ends_on")
    context.ends_on = ends or ""
    context.days_left = date_diff(ends, nowdate()) if ends else None
    context.max_users = cint(conf.get("saas_max_users") or 0)
    context.used_users = frappe.db.count(
        "User",
        {
            "user_type": "System User",
            "enabled": 1,
            "name": ["not in", ["Administrator", "Guest"]],
        },
    )
    context.site_name = frappe.local.site
    context.control_url = "https://control.horizonerp.cloud"
    return context
