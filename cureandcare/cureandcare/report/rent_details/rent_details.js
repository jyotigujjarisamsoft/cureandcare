frappe.query_reports["Rent Details"] = {
    filters: [
        {
            fieldname: "receipt_from_date",
            label: "Receipt From Date",
            fieldtype: "Date"
        },
        {
            fieldname: "receipt_to_date",
            label: "Receipt To Date",
            fieldtype: "Date"
        },
        {
            fieldname: "rent_from_date",
            label: "Rent From Date",
            fieldtype: "Date"
        },
        {
            fieldname: "rent_to_date",
            label: "Rent To Date",
            fieldtype: "Date"
        },
        {
            fieldname: "status",
            label: "Status",
            fieldtype: "Select",
            options: "\nDraft\nActive\nPartial Active\nClosed\nCancelled\nRenewed"
        }
    ]
};
