import frappe
from frappe.model.document import Document

from saas_manager.provisioning import provisioner, lifecycle


class TenantSite(Document):
    def validate(self):
        provisioner.validate_subdomain(self.subdomain)
        if not self.site_name:
            self.site_name = provisioner.full_site_name(self.subdomain)

    # ---- Desk buttons (called from client or via frappe.call) ----

    @frappe.whitelist()
    def provision(self):
        """Queue provisioning on the long worker."""
        frappe.only_for("System Manager")
        frappe.enqueue(
            "saas_manager.provisioning.provisioner.provision_site",
            queue="long",
            timeout=3600,
            tenant=self.name,
        )
        frappe.msgprint("Provisioning queued.")

    @frappe.whitelist()
    def activate(self, months: int = 1):
        """Manual activation after bank-transfer confirmation."""
        frappe.only_for("System Manager")
        lifecycle.activate(self.name, months=int(months))

    @frappe.whitelist()
    def suspend(self):
        frappe.only_for("System Manager")
        lifecycle.suspend(self.name, reason="Manual suspension")

    @frappe.whitelist()
    def resume(self):
        frappe.only_for("System Manager")
        lifecycle.resume(self.name)

    @frappe.whitelist()
    def change_plan(self, new_plan: str):
        """Upgrade/downgrade: install missing apps + rewrite limits & features."""
        frappe.only_for("System Manager")
        from saas_manager.provisioning.provisioner import run_bench, apply_plan_config
        plan = frappe.get_doc("SaaS Plan", new_plan)
        installed = run_bench(["--site", self.site_name, "list-apps"], self.name)
        for app in plan.apps_list() + ["horizon_client"]:
            if app not in installed:
                run_bench(["--site", self.site_name, "install-app", app],
                          self.name, timeout=2400)
        apply_plan_config(self.site_name, plan, tenant_name=self.name)
        self.db_set("plan", new_plan)
        frappe.db.commit()
        frappe.msgprint(f"Plan changed to {new_plan}. Limits and features applied.")

    @frappe.whitelist()
    def create_mf_invoice(self, months: int = 1):
        """Generate a MyFatoorah payment link for renewal (also emailed by reminders)."""
        frappe.only_for("System Manager")
        from saas_manager.payments import myfatoorah
        inv = myfatoorah.create_renewal_invoice(self.name, months=int(months))
        frappe.msgprint(
            f'Invoice <b>{inv.name}</b> — <a href="{inv.payment_url}" target="_blank">'
            f"رابط الدفع ({inv.amount} {inv.currency})</a>"
        )
        return inv.payment_url

    @frappe.whitelist()
    def backup_now(self):
        frappe.only_for("System Manager")
        frappe.enqueue(
            "saas_manager.provisioning.lifecycle.backup_site",
            queue="long", timeout=1800, tenant=self.name,
        )
        frappe.msgprint("Backup queued.")
