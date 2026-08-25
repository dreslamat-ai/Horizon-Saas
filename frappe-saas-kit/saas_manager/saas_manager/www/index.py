import frappe


def get_context(context):
    """Marketing homepage. Plan prices come from the database so the site and
    the signup page can never disagree about pricing."""
    context.no_cache = 1
    context.root_domain = frappe.conf.get("saas_root_domain") or "horizonerp.cloud"
    context.plans = frappe.get_all(
        "SaaS Plan",
        filters={"enabled": 1},
        fields=["name", "plan_name", "monthly_price", "currency",
                "max_users", "max_companies", "max_branches", "trial_days"],
        order_by="monthly_price asc",
    )
    # positional taglines: the plan DocType has no marketing copy field, and
    # adding one would put website wording in an operational record.
    context.plan_desc = [
        "للورش والشركات الصغيرة اللي بتبدأ تنظّم شغلها",
        "للمصانع وشركات المقاولات المتوسطة",
        "بلا حدود — لمجموعات الشركات ومتعددة المصانع والمشاريع",
    ]
    return context
