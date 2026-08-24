frappe.ui.form.on("Tenant Site", {
    refresh(frm) {
        const call = (method, args = {}) =>
            frm.call(method, args).then(() => frm.reload_doc());

        if (frm.doc.status === "Pending" || frm.doc.status === "Failed") {
            frm.add_custom_button(__("Provision Now"), () => call("provision"))
               .addClass("btn-primary");
        }
        if (["Active", "Suspended"].includes(frm.doc.status)) {
            frm.add_custom_button(__("Activate / Extend (bank transfer)"), () => {
                frappe.prompt(
                    { fieldname: "months", fieldtype: "Int", label: __("Months"), default: 1, reqd: 1 },
                    (v) => call("activate", { months: v.months }),
                    __("Extend Subscription")
                );
            });
        }
        if (frm.doc.status === "Active") {
            frm.add_custom_button(__("Change Plan"), () => {
                frappe.prompt(
                    { fieldname: "new_plan", fieldtype: "Link", options: "SaaS Plan",
                      label: __("New Plan"), reqd: 1 },
                    (v) => call("change_plan", { new_plan: v.new_plan }),
                    __("Change Plan")
                );
            });
            frm.add_custom_button(__("MyFatoorah Invoice"), () => {
                frappe.prompt(
                    { fieldname: "months", fieldtype: "Int", label: __("Months"),
                      default: 1, reqd: 1 },
                    (v) => call("create_mf_invoice", { months: v.months }),
                    __("Renewal Invoice")
                );
            });
            frm.add_custom_button(__("Suspend"), () => call("suspend"));
            frm.add_custom_button(__("Backup Now"), () => call("backup_now"));
        }
        if (frm.doc.status === "Suspended") {
            frm.add_custom_button(__("Resume"), () => call("resume")).addClass("btn-primary");
        }
    },
});
