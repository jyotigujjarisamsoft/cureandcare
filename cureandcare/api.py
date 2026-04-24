import frappe

@frappe.whitelist()
def get_qty_with_customer(customer, item_code):
    result = frappe.db.sql("""
        SELECT 
            SUM(CASE WHEN dn.is_return = 0 THEN dni.qty ELSE 0 END) as delivered,
            SUM(CASE WHEN dn.is_return = 1 THEN dni.qty ELSE 0 END) as returned
        FROM `tabDelivery Note Item` dni
        JOIN `tabDelivery Note` dn ON dn.name = dni.parent
        WHERE 
            dn.customer = %s
            AND dni.item_code = %s
            AND dn.docstatus = 1
    """, (customer, item_code), as_dict=1)

    if result:
        delivered = result[0].delivered or 0
        returned = result[0].returned or 0
        return delivered - returned

    return 0
