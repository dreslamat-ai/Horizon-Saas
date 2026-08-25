import frappe


def get_context(context):
    context.no_cache = 1
    context.root_domain = frappe.conf.get("saas_root_domain") or "horizonerp.cloud"
    return context
