// Defaults to the trailing 12 months: long enough for a renewal cycle to have
// happened at least once, which is the minimum window where retention means
// anything at all.
frappe.query_reports["SaaS Revenue and Retention"] = {
    filters: [
        {
            fieldname: "from_date",
            label: __("من تاريخ"),
            fieldtype: "Date",
            default: frappe.datetime.add_months(frappe.datetime.get_today(), -12),
        },
        {
            fieldname: "to_date",
            label: __("إلى تاريخ"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
        },
        {
            fieldname: "group_by",
            label: __("تجميع حسب"),
            fieldtype: "Select",
            options: ["Plan", "Status", "Month"].join("\n"),
            default: "Plan",
        },
        {
            fieldname: "plan",
            label: __("الباقة"),
            fieldtype: "Link",
            options: "SaaS Plan",
        },
    ],

    formatter(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (!data) return value;

        // Retention is the judgement column: blue for healthy, amber for
        // watch, red for bleeding. Blue stays reserved for success.
        if (column.fieldname === "retention") {
            const r = data.retention;
            const c = r >= 90 ? "#5083BC" : r >= 75 ? "#B8860B" : "#B04A3F";
            value = `<span style="color:${c};font-weight:700">${value}</span>`;
        }
        if (column.fieldname === "churned" && data.churned > 0) {
            value = `<span style="color:#B04A3F;font-weight:700">${value}</span>`;
        }
        // lapsed trials are amber, never red: they never paid, so they are a
        // marketing problem, not a retention failure.
        if (column.fieldname === "lapsed" && data.lapsed > 0) {
            value = `<span style="color:#B8860B;font-weight:700">${value}</span>`;
        }
        if (column.fieldname === "mrr" && data.mrr > 0) {
            value = `<span style="font-weight:700">${value}</span>`;
        }
        return value;
    },
};
