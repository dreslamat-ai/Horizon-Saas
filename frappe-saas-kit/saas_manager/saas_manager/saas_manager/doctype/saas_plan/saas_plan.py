import frappe
from frappe.model.document import Document


class SaaSPlan(Document):
    def validate(self):
        self.apps_list()

    def apps_list(self):
        apps = [a.strip() for a in (self.apps_to_install or "").splitlines() if a.strip()]
        for a in apps:
            if not a.replace("_", "").isalnum():
                frappe.throw(f"Invalid app name: {a}")
        return apps

    def features_dict(self) -> dict:
        return {row.feature_key: row.feature_value for row in (self.features or [])}
