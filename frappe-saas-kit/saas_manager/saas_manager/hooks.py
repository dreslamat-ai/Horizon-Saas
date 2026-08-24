app_name = "saas_manager"
app_title = "SaaS Manager"
app_publisher = "Horizon Smart Systems"
app_description = "Control plane that turns a Frappe bench into a multi-tenant SaaS: signup, OTP, provisioning, plans, trials, suspension, backups."
app_email = "support@horizonerp.cloud"
app_license = "MIT"

# ---- Scheduler (control-plane automation) ----
scheduler_events = {
    "daily": [
        "saas_manager.provisioning.lifecycle.enforce_expiries",
        "saas_manager.provisioning.lifecycle.send_expiry_notices",
        "saas_manager.payments.myfatoorah.reconcile_pending",
    ],
    "cron": {
        # nightly backups for all active tenant sites at 02:30
        "30 2 * * *": [
            "saas_manager.provisioning.lifecycle.backup_all_active_sites"
        ],
    },
}

# create default plans on install (edit in saas_manager/install.py)
after_install = "saas_manager.install.after_install"

# Guest-accessible endpoints are declared with @frappe.whitelist(allow_guest=True)
