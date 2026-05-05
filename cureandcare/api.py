import frappe

@frappe.whitelist()
def get_qty_with_customer(customer, item_code):
    result = frappe.db.sql("""
        SELECT 
            COALESCE(SUM(CASE 
                WHEN IFNULL(dn.is_return, 0) = 0 THEN dni.qty 
                ELSE 0 
            END), 0) AS delivered,

            COALESCE(SUM(CASE 
                WHEN IFNULL(dn.is_return, 0) = 1 THEN ABS(dni.qty) 
                ELSE 0 
            END), 0) AS returned

        FROM `tabDelivery Note Item` dni
        INNER JOIN `tabDelivery Note` dn ON dn.name = dni.parent
        WHERE 
            dn.customer = %s
            AND dni.item_code = %s
            AND dn.docstatus = 1
    """, (customer, item_code), as_dict=1)

    if result:
        delivered = flt(result[0].delivered)
        returned = flt(result[0].returned)
        return delivered - returned

    return 0
