import frappe


# باقات افتراضية بهوية Horizon ERP — عدّل الأسعار من Desk بعد التركيب
# NOTE ON NAMING
# ----------------------------------------------------------------------------
# The product is called "Horizon AI Powered ERP" everywhere a customer can see
# it (signup page, emails, Desk banner, invoices). The strings below are *bench
# app names* — they are arguments to `bench install-app` and must match the app
# folder on disk. They never appear in customer-facing text.
HORIZON_CORE_APPS = "erpnext"   # bench app id of the Horizon ERP core

DEFAULT_PLANS = [
    # (name, price, cur, users, companies, branches, space_mb, trial, apps, features)
    ("Horizon Basic",      99,  "SAR", 5,  1, 1,  5120,  14, HORIZON_CORE_APPS,
     {"advanced_reports": 0, "api_access": 0}),
    ("Horizon Pro",        249, "SAR", 15, 1, 3,  20480, 14, HORIZON_CORE_APPS,
     {"advanced_reports": 1, "api_access": 0}),
    ("Horizon Enterprise", 499, "SAR", 0,  3, 10, 51200, 14, HORIZON_CORE_APPS,
     {"advanced_reports": 1, "api_access": 1}),
]


def after_install():
    for (name, price, currency, users, companies, branches,
         space, trial, apps, feats) in DEFAULT_PLANS:
        if frappe.db.exists("SaaS Plan", name):
            continue
        frappe.get_doc({
            "doctype": "SaaS Plan",
            "plan_name": name,
            "monthly_price": price,
            "currency": currency,
            "max_users": users,          # 0 = unlimited
            "max_companies": companies,
            "max_branches": branches,
            "max_space_mb": space,
            "trial_days": trial,
            "apps_to_install": apps,     # horizon_client is added automatically
            "enabled": 1,
            "features": [
                {"feature_key": k, "feature_value": str(v)} for k, v in feats.items()
            ],
        }).insert(ignore_permissions=True)
    frappe.db.commit()
