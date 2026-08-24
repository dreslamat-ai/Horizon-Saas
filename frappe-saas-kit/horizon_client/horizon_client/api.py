import frappe
from frappe.utils import cint, date_diff, nowdate


@frappe.whitelist()
def subscription_info():
    """Read-only info for the Desk banner + الاء integration. Logged-in users only."""
    ends = frappe.conf.get("saas_subscription_ends_on")
    days_left = date_diff(ends, nowdate()) if ends else None
    return {
        "plan": frappe.conf.get("saas_plan"),
        "ends_on": ends,
        "days_left": days_left,
        "limits": {
            "users": cint(frappe.conf.get("saas_max_users") or 0),
            "companies": cint(frappe.conf.get("saas_max_companies") or 0),
            "branches": cint(frappe.conf.get("saas_max_branches") or 0),
        },
        "features": frappe.conf.get("saas_features") or {},
    }
