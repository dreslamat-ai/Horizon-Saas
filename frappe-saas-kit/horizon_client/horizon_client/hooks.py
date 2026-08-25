app_name = "horizon_client"
app_title = "Horizon Client"
app_publisher = "Horizon Smart Systems"
app_description = "Enforces SaaS plan limits (users/companies/branches) and feature gates from site_config. Installed automatically on every tenant site."
app_email = "support@horizonerp.cloud"
app_license = "MIT"

# limits are enforced server-side on validate — cannot be bypassed from UI or API
doc_events = {
    "User": {"validate": ["horizon_client.limits.check_user_limit",
                          "horizon_client.limits.sync_module_blocks"]},
    "Company": {"validate": ["horizon_client.limits.check_company_limit",
                             "horizon_client.limits.enforce_currency"]},
    "Branch": {"validate": "horizon_client.limits.check_branch_limit"},
    # العملة مثبتة من بلد الاشتراك — تغييرها يغيّر التسعير فيُمنع من داخل النظام
    "Global Defaults": {"validate": "horizon_client.limits.enforce_currency"},
}

# subscription banner (days-left warning) on every Desk page
app_include_js = "/assets/horizon_client/js/horizon_banner.js"
