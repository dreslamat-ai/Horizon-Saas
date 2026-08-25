import frappe


def get_context(context):
    """Signup page context. Plans and root domain come from the control site,
    so pricing/limits are edited in Desk — never in the template."""
    context.no_cache = 1
    context.root_domain = frappe.conf.get("saas_root_domain") or "horizonerp.cloud"
    # جلسة داخلة (مثلاً أدمن فاتح الدسك) بترفض أي POST بلا توكن CSRF
    # بـ"طلب غير صالح" — الصفحة لازم تحقنه وتبعته مع كل نداء
    context.csrf_token = frappe.sessions.get_csrf_token()
    # البلد من الـIP على الخادم حصرًا — العميل لا يختار (منع تلاعب الأسعار)
    from saas_manager.geo import detect_country
    from saas_manager.pricing import localize_plan
    country_ar = {
        "Saudi Arabia": "السعودية", "United Arab Emirates": "الإمارات",
        "Egypt": "مصر", "Kuwait": "الكويت", "Qatar": "قطر",
        "Bahrain": "البحرين", "Oman": "عُمان", "Jordan": "الأردن", "Iraq": "العراق",
    }
    context.detected_country = detect_country()
    context.detected_country_ar = country_ar.get(context.detected_country, context.detected_country)
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
    # the middle plan is highlighted as the recommended one
    context.recommended = (
        context.plans[len(context.plans) // 2]["name"] if context.plans else None
    )
    context.trial_days = context.plans[0]["trial_days"] if context.plans else 14
    return context
