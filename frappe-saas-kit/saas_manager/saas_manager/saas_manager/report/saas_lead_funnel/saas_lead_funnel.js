// Filters for the lead funnel. Defaults to the last 90 days: short enough to
// reflect current campaigns, long enough for a sales cycle to have closed.
frappe.query_reports["SaaS Lead Funnel"] = {
    filters: [
        {
            fieldname: "from_date",
            label: __("من تاريخ"),
            fieldtype: "Date",
            default: frappe.datetime.add_days(frappe.datetime.get_today(), -90),
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
            options: ["Segment", "Status", "Estimate Band"].join("\n"),
            default: "Segment",
        },
        {
            fieldname: "segment",
            label: __("القطاع"),
            fieldtype: "Select",
            options: ["", "Manufacturing", "Contracting"].join("\n"),
        },
        {
            fieldname: "source",
            label: __("المصدر"),
            fieldtype: "Select",
            options: ["", "Cost Calculator", "Website", "Demo Request", "Other"].join("\n"),
        },
    ],

    formatter(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        // conversion rate carries the judgement, so colour only that column:
        // blue is reserved for success in the Horizon identity.
        if (column.fieldname === "conversion" && data) {
            const c = data.conversion >= 10 ? "#5083BC" : (data.conversion > 0 ? "#B8860B" : "#69727F");
            value = `<span style="color:${c};font-weight:700">${value}</span>`;
        }
        if (column.fieldname === "converted" && data && data.converted > 0) {
            value = `<span style="color:#5083BC;font-weight:700">${value}</span>`;
        }
        return value;
    },
};
