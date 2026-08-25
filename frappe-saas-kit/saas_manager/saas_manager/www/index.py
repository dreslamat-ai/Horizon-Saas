import frappe


def get_context(context):
    """Marketing homepage. Plan prices come from the database so the site and
    the signup page can never disagree about pricing."""
    context.no_cache = 1
    context.root_domain = frappe.conf.get("saas_root_domain") or "horizonerp.cloud"
    from saas_manager.geo import detect_country
    from saas_manager.pricing import localize_plan
    context.detected_country = detect_country()
    context.plans = [
        localize_plan(p, context.detected_country)
        for p in frappe.get_all(
            "SaaS Plan",
            filters={"enabled": 1},
            fields=["name", "plan_name", "monthly_price", "currency",
                    "max_users", "max_companies", "max_branches", "trial_days"],
            order_by="monthly_price asc",
        )
    ]
    # positional taglines: the plan DocType has no marketing copy field, and
    # adding one would put website wording in an operational record.
    # هيكل الباقات بقرار المالك (٢٥ أغسطس): الأولى تشغيل يومي بلا حسابات،
    # الثانية +الحسابات، الثالثة +الموديولات المتقدمة — وإنتربرايز بلا سعر
    context.plan_ar = {
        "Horizon Basic": "أساسية",
        "Horizon Pro": "احترافية",
        "Horizon Enterprise": "أعمال",
    }
    context.plan_desc = [
        "للمحلات والمستودعات — إدارة التشغيل اليومي",
        "للشركات اللي محتاجة حسابات كاملة وفروع متعددة",
        "للمصانع وشركات المشاريع — الموديولات المتقدمة كاملة",
    ]
    return context
