import frappe


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {
            "label": "Rent",
            "fieldname": "rent",
            "fieldtype": "Link",
            "options": "Rent",
            "width": 150
        },
        {
            "label": "Rental Receipt Date",
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": 100
        },
        {
            "label": "Customer",
            "fieldname": "customer",
            "fieldtype": "Data",
            "width": 180
        },
        {
            "label": "Duration",
            "fieldname": "duration",
            "fieldtype": "Data",
            "width": 80
        },
        {
            "label": "Status",
            "fieldname": "status",
            "fieldtype": "HTML",
            "width": 120
        },
        {
            "label": "From Date",
            "fieldname": "from_date",
            "fieldtype": "Date",
            "width": 100
        },
        {
            "label": "To Date",
            "fieldname": "to_date",
            "fieldtype": "Date",
            "width": 100
        },
        {
            "label": "Rent Product Details",
            "fieldname": "rent_products",
            "fieldtype": "HTML",
            "width": 600
        }
    ]


def get_status_html(status):
    colors = {
        "Draft": "#6c757d",
        "Active": "#28a745",
        "Cancelled": "#dc3545",
        "Renewed": "#007bff",
        "Closed": "#e74c3c",
        "Partial Active": "#fd7e14",
    }

    color = colors.get(status, "#343a40")

    return f"""
    <span style="
        background:{color};
        color:white;
        padding:4px 10px;
        border-radius:12px;
        font-weight:bold;
        display:inline-block;">
        {status}
    </span>
    """


def get_data(filters):

    conditions = ""
    values = {}

    if filters.get("receipt_from_date"):
        conditions += " AND rental_receipt_date >= %(receipt_from_date)s"
        values["receipt_from_date"] = filters.get("receipt_from_date")

    if filters.get("receipt_to_date"):
        conditions += " AND rental_receipt_date <= %(receipt_to_date)s"
        values["receipt_to_date"] = filters.get("receipt_to_date")

    if filters.get("rent_from_date"):
        conditions += " AND from_date >= %(rent_from_date)s"
        values["rent_from_date"] = filters.get("rent_from_date")

    if filters.get("rent_to_date"):
        conditions += " AND to_date <= %(rent_to_date)s"
        values["rent_to_date"] = filters.get("rent_to_date")

    if filters.get("status"):
        conditions += " AND status = %(status)s"
        values["status"] = filters.get("status")

    rents = frappe.db.sql(f"""
        SELECT
            name,
            rental_receipt_date,
            customer_name,
            duration,
            status,
            from_date,
            to_date
        FROM `tabRent`
        WHERE docstatus < 2
        {conditions}
        ORDER BY rental_receipt_date DESC
    """, values, as_dict=True)

    data = []

    for r in rents:

        doc = frappe.get_doc("Rent", r.name)

        rows = []

        for d in doc.rent_product_details:
            rows.append(
                f"<b>{d.product_name or ''}</b>|"
                f"{d.qty or 0}|"
                f"{d.amount or 0}|"
                f"{d.rent_item_status or ''}|"
                f"{d.duration or 0}"
            )

        product_html = " &nbsp;&nbsp;<span style='color:#999;'>||</span>&nbsp;&nbsp; ".join(rows)

        data.append({
            "rent": r.name,
            "posting_date": r.rental_receipt_date,
            "customer": r.customer_name,
            "duration": r.duration,
            "status": get_status_html(r.status),
            "from_date": r.from_date,
            "to_date": r.to_date,
            "rent_products": product_html
        })

    return data
