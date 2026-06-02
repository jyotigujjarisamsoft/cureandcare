import frappe
from frappe.utils import flt


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
    


@frappe.whitelist()
def create_delivery_note(rent_name):

    rent_doc = frappe.get_doc("Rent", rent_name)

    # ---------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------

    if not rent_doc.confirm:
        frappe.throw("Please confirm the document first")

    # ---------------------------------------------------
    # RETURN DELIVERY NOTE FLOW
    # ---------------------------------------------------

    if rent_doc.renewal_no:

        # Find Original Delivery Note
        original_dn = frappe.db.get_value(
            "Delivery Note",
            {
                "custom_rent_reference": rent_doc.renewal_no
            },
            "name"
        )

        if not original_dn:
            frappe.throw("Original Delivery Note not found")

        # Prevent Duplicate Return DN
        existing_return_dn = frappe.db.exists(
            "Delivery Note",
            {
                "custom_rent_reference": rent_doc.name,
                "is_return": 1
            }
        )

        if existing_return_dn:
            frappe.msgprint(
                f"Return Delivery Note already exists: {existing_return_dn}"
            )
            return existing_return_dn

        # Create Return Delivery Note
        return_dn = frappe.new_doc("Delivery Note")

        return_dn.customer = rent_doc.customer_name
        return_dn.is_return = 1
        return_dn.return_against = original_dn
        return_dn.custom_rent_reference = rent_doc.name

        returned_item_found = False

        # Add only Returned items
        for row in rent_doc.rent_product_details:

            if row.rent_item_status == "Returned":

                returned_item_found = True

                # Fetch Original Delivery Note Item
                dn_detail = frappe.db.get_value(
                    "Delivery Note Item",
                    {
                        "parent": original_dn,
                        "item_code": row.product_name
                    },
                    "name"
                )

                if not dn_detail:
                    frappe.throw(
                        f"Item {row.product_name} does not exist in Original Delivery Note"
                    )

                return_dn.append("items", {
    "item_code": row.product_name,
    "qty": -abs(row.qty),              # Sales Qty Positive
    #"stock_qty": -abs(row.qty),       # Stock Qty Negative
    "rate": row.rental_rate * row.duration,
    "amount": row.amount,
    "warehouse": row.warehouse,
    "dn_detail": dn_detail
})

        if not returned_item_found:
            frappe.throw("No Returned items found")

        return_dn.insert(ignore_permissions=True)
        return_dn.submit()

        return return_dn.name

    # ---------------------------------------------------
    # NORMAL DELIVERY NOTE FLOW
    # ---------------------------------------------------

    else:

        # Check Existing DN
        existing_dn = frappe.db.exists(
            "Delivery Note",
            {
                "custom_rent_reference": rent_doc.name
            }
        )

        if existing_dn:

            # Fetch existing items
            existing_items = frappe.get_all(
                "Delivery Note Item",
                filters={
                    "parent": existing_dn
                },
                fields=["item_code"]
            )

            delivered_items = [d.item_code for d in existing_items]

            for row in rent_doc.rent_product_details:

                if row.product_name in delivered_items:

                    frappe.msgprint(
                        f"Product <b>{row.product_name}</b> already delivered in Delivery Note <b>{existing_dn}</b>"
                    )

                    return existing_dn

        # Create Delivery Note
        dn = frappe.new_doc("Delivery Note")

        dn.customer = rent_doc.customer_name
        dn.custom_rent_reference = rent_doc.name

        # Add Items
        for row in rent_doc.rent_product_details:

            dn.append("items", {
                "item_code": row.product_name,
                "qty": row.qty,
                "rate": row.rental_rate * row.duration,
                "amount": row.amount,
                "warehouse": row.warehouse
            })

        dn.insert(ignore_permissions=True)
        dn.submit()

        return dn.name
        
        
import frappe
from frappe.model.mapper import get_mapped_doc


@frappe.whitelist()
def create_rent_renewal(docname):

    import frappe

    print("docname", docname)

    # =====================================================
    # GET SOURCE DOC
    # =====================================================

    source_doc = frappe.get_doc(
        "Rent Renewal Receipt",
        docname
    )

    print("source_doc", source_doc)

    # =====================================================
    # GET OLD RENT
    # =====================================================

    old_rent = frappe.get_doc(
        "Rent",
        source_doc.renewal_no
    )

    print("old_rent", old_rent)

    # =====================================================
    # SEGREGATE ITEMS
    # =====================================================

    renewed_items = []
    returned_items = []
    na_items = []

    for row in source_doc.renewal_product_details:

        if row.rent_item_status == "Renewed":

            renewed_items.append(row)

        elif row.rent_item_status == "Returned":

            returned_items.append(row)

        elif row.rent_item_status == "NA":

            na_items.append(row)

    created_rent = None
    created_return = None

    # =====================================================
    # EXCLUDE FIELDS
    # =====================================================

    exclude_fields = [
        "name",
        "owner",
        "creation",
        "modified",
        "modified_by",
        "docstatus",
        "idx"
    ]

    # =====================================================
    # CREATE NEW RENT
    # =====================================================

    if renewed_items:

        new_rent = frappe.new_doc("Rent")

        # -------------------------------------------------
        # COPY HEADER FIELDS
        # -------------------------------------------------

        for field in old_rent.meta.fields:

            if field.fieldtype == "Table":
                continue

            fieldname = field.fieldname

            if fieldname in exclude_fields:
                continue

            if new_rent.meta.has_field(fieldname):

                new_rent.set(
                    fieldname,
                    old_rent.get(fieldname)
                )

        # -------------------------------------------------
        # EXTRA VALUES
        # -------------------------------------------------

        new_rent.status = "Active"

        # LINK TO RENEWAL RECEIPT
        new_rent.renewal_no = source_doc.name

        # -------------------------------------------------
        # ADD ONLY RENEWED ITEMS
        # -------------------------------------------------

        for row in renewed_items:

            child = new_rent.append(
                "rent_product_details",
                {}
            )

            target_fields = child.as_dict().keys()

            for field in row.meta.fields:

                fieldname = field.fieldname

                if fieldname in exclude_fields:
                    continue

                if fieldname in target_fields:

                    child.set(
                        fieldname,
                        row.get(fieldname)
                    )

        # -------------------------------------------------
        # SAVE RENT
        # -------------------------------------------------

        new_rent.insert(ignore_permissions=True)

        created_rent = new_rent.name

        print("created_rent", created_rent)

    # =====================================================
    # CREATE RENTAL RETURN REQUEST
    # =====================================================

    if returned_items:

        return_doc = frappe.new_doc(
            "Rental Return Request"
        )

        # -------------------------------------------------
        # HEADER VALUES
        # -------------------------------------------------

        return_doc.rental_receipt_no = source_doc.renewal_no
        return_doc.renewal_no = source_doc.name

        # -------------------------------------------------
        # ADD ONLY RETURNED ITEMS
        # -------------------------------------------------

        for row in returned_items:

            child = return_doc.append(
                "return_product_details",
                {}
            )

            target_fields = child.as_dict().keys()

            for field in row.meta.fields:

                fieldname = field.fieldname

                if fieldname in exclude_fields:
                    continue

                if fieldname in target_fields:

                    child.set(
                        fieldname,
                        row.get(fieldname)
                    )

        # -------------------------------------------------
        # SAVE RETURN REQUEST
        # -------------------------------------------------

        return_doc.insert(ignore_permissions=True)

        created_return = return_doc.name

        print("created_return", created_return)

    # =====================================================
    # UPDATE OLD RENT STATUS
    # =====================================================

    total_rows = len(source_doc.renewal_product_details)

    renewed_count = len(renewed_items)
    returned_count = len(returned_items)
    na_count = len(na_items)

    # -------------------------------------------------
    # ALL RENEWED
    # -------------------------------------------------

    if renewed_count == total_rows:

        old_rent.status = "Closed"

    # -------------------------------------------------
    # ALL RETURNED
    # -------------------------------------------------

    elif returned_count == total_rows:

        old_rent.status = "Intransit"

    # -------------------------------------------------
    # ANY NA
    # -------------------------------------------------

    elif na_count > 0:

        old_rent.status = "Partial Active"

    # -------------------------------------------------
    # MIXED RENEWED / RETURNED
    # -------------------------------------------------

    else:

        old_rent.status = "Partial Active"

    # -------------------------------------------------
    # SAVE OLD RENT
    # -------------------------------------------------
    # UPDATE OLD RENT CHILD ROW STATUS
    renewal_status_map = {}
    for row in source_doc.renewal_product_details:
    	if row.rent_item_status == "Returned":
    		renewal_status_map[row.product_name] = "Yet To Pickup"
    	else:
    		renewal_status_map[row.product_name] = row.rent_item_status
    	#renewal_status_map[row.product_name] = row.rent_item_status
    for row in old_rent.rent_product_details:
    	if row.product_name in renewal_status_map:
    		row.rent_item_status = renewal_status_map[row.product_name]
    old_rent.save(ignore_permissions=True)

    # =====================================================
    # COMMIT
    # =====================================================

    frappe.db.commit()

    # =====================================================
    # RETURN MESSAGE
    # =====================================================

    return f"""
        <b>Process Completed Successfully</b>
        <br><br>

        New Rent:
        <b>{created_rent or "Not Created"}</b>

        <br><br>

        Rental Return Request:
        <b>{created_return or "Not Created"}</b>

        <br><br>

        Existing Rent Status:
        <b>{old_rent.status}</b>
    """
 
@frappe.whitelist()
def old_create_delivery_note_return(rent_name):

    import frappe

    # ===================================================
    # GET RETURN REQUEST
    # ===================================================

    return_doc = frappe.get_doc(
        "Rental Return Request",
        rent_name
    )

    # ===================================================
    # GET RENT
    # ===================================================

    rent = return_doc.rental_receipt_no

    rent_doc = frappe.get_doc(
        "Rent",
        rent
    )

    print("rent_doc", rent_doc.name)

    # ===================================================
    # VALIDATION
    # ===================================================

    if not return_doc.confirm:

        frappe.throw(
            "Please confirm the document first"
        )

    # ===================================================
    # FIND ORIGINAL DELIVERY NOTE
    # ===================================================

    original_dn = frappe.db.get_value(
        "Delivery Note",
        {
            "custom_rent_reference": rent_doc.name,
            "customer": rent_doc.customer_name,
            "is_return": 0,
            "docstatus": 1
        },
        "name"
    )

    print("original_dn", original_dn)

    if not original_dn:

        frappe.throw(
            "Original Delivery Note not found"
        )

    # ===================================================
    # FETCH ORIGINAL DELIVERY NOTE ITEMS
    # ===================================================

    original_dn_items = frappe.get_all(
        "Delivery Note Item",
        filters={
            "parent": original_dn
        },
        fields=[
            "name",
            "item_code",
            "qty",
            "warehouse"
        ]
    )

    print("original_dn_items", original_dn_items)

    if not original_dn_items:

        frappe.throw(
            "No items found in Original Delivery Note"
        )

    # ===================================================
    # CREATE ITEM MAP
    # ===================================================

    dn_item_map = {}

    for d in original_dn_items:

        dn_item_map[d.item_code] = d

    print("dn_item_map", dn_item_map)

    # ===================================================
    # CREATE RETURN DELIVERY NOTE
    # ===================================================

    return_dn = frappe.new_doc(
        "Delivery Note"
    )

    return_dn.customer = rent_doc.customer_name

    return_dn.is_return = 1

    return_dn.return_against = original_dn

    return_dn.custom_rent_reference = rent_doc.name

    returned_item_found = False

    # ===================================================
    # ADD RETURN ITEMS
    # ===================================================

    for row in return_doc.return_product_details:

        print("Processing Row", row.product_name)

        # ------------------------------------------------
        # ONLY RETURNED ITEMS
        # ------------------------------------------------

        if row.rent_item_status != "Returned":

            print("Skipped - Not Returned")

            continue

        # ------------------------------------------------
        # ITEM NOT FOUND
        # ------------------------------------------------

        if row.product_name not in dn_item_map:

            print(
                "Item Not Found In DN",
                row.product_name
            )

            continue

        dn_row = dn_item_map[row.product_name]

        print("Matched DN Row", dn_row)

        returned_item_found = True

        # ------------------------------------------------
        # APPEND ITEM
        # ------------------------------------------------

        return_dn.append("items", {

            "item_code": row.product_name,

            "qty": -1 * abs(row.qty),

            "warehouse": row.warehouse or dn_row.warehouse,

            "rate": row.rental_rate * row.duration,

            "amount": row.amount,

            "dn_detail": dn_row.name
        })

    print("return_dn_items", return_dn.items)

    # ===================================================
    # VALIDATION
    # ===================================================

    if not returned_item_found:

        frappe.throw(
            "No matching returned items found"
        )

    if not return_dn.items:

        frappe.throw(
            "No items added in Return Delivery Note"
        )

    # ===================================================
    # SAVE DELIVERY NOTE
    # ===================================================

    return_dn.flags.ignore_permissions = True

    return_dn.insert()

    print("Return DN Inserted", return_dn.name)

    # ===================================================
    # SUBMIT DELIVERY NOTE
    # ===================================================

    return_dn.submit()

    print("Return DN Submitted", return_dn.name)

    # ===================================================
    # CLOSE RENT
    # ===================================================

    rent_doc.status = "Closed"
    # UPDATE RENT CHILD TABLE STATUS
    returned_products = []
    for row in return_doc.return_product_details:
    	if row.rent_item_status == "Returned":
    		 returned_products.append(row.product_name)
    		 
    for row in rent_doc.rent_product_details:
    	if row.product_name in returned_products:
    		row.rent_item_status = "Returned"

    rent_doc.save(ignore_permissions=True)

    print("Rent Closed", rent_doc.name)

    # ===================================================
    # COMMIT
    # ===================================================

    frappe.db.commit()

    # ===================================================
    # RETURN
    # ===================================================

    return {
        "delivery_note": return_dn.name,
        "rent_status": rent_doc.status
    }
    
@frappe.whitelist()
def create_delivery_note_return(rent_name):

    import frappe

    # ===================================================
    # GET RETURN REQUEST
    # ===================================================

    return_doc = frappe.get_doc(
        "Rental Return Request",
        rent_name
    )

    # ===================================================
    # GET RENT
    # ===================================================

    rent = return_doc.rental_receipt_no

    rent_doc = frappe.get_doc(
        "Rent",
        rent
    )

    print("rent_doc", rent_doc.name)

    # ===================================================
    # VALIDATION
    # ===================================================

    if not return_doc.confirm:

        frappe.throw(
            "Please confirm the document first"
        )

    # ===================================================
    # FIND ORIGINAL DELIVERY NOTE
    # ===================================================

    original_dn = frappe.db.get_value(
        "Delivery Note",
        {
            "custom_rent_reference": rent_doc.name,
            "customer": rent_doc.customer_name,
            "is_return": 0,
            "docstatus": 1
        },
        "name"
    )

    print("original_dn", original_dn)

    if not original_dn:

        frappe.throw(
            "Original Delivery Note not found"
        )

    # ===================================================
    # FETCH ORIGINAL DELIVERY NOTE ITEMS
    # ===================================================

    original_dn_items = frappe.get_all(
        "Delivery Note Item",
        filters={
            "parent": original_dn
        },
        fields=[
            "name",
            "item_code",
            "qty",
            "warehouse"
        ]
    )

    print("original_dn_items", original_dn_items)

    if not original_dn_items:

        frappe.throw(
            "No items found in Original Delivery Note"
        )

    # ===================================================
    # CREATE ITEM MAP
    # ===================================================

    dn_item_map = {}

    for d in original_dn_items:

        dn_item_map[d.item_code] = d

    print("dn_item_map", dn_item_map)

    # ===================================================
    # CREATE RETURN DELIVERY NOTE
    # ===================================================

    return_dn = frappe.new_doc(
        "Delivery Note"
    )

    return_dn.customer = rent_doc.customer_name

    return_dn.is_return = 1

    return_dn.return_against = original_dn

    return_dn.custom_rent_reference = rent_doc.name

    returned_item_found = False

    # ===================================================
    # ADD RETURN ITEMS
    # ===================================================

    for row in return_doc.return_product_details:

        print("Processing Row", row.product_name)

        # ------------------------------------------------
        # ONLY RETURNED ITEMS
        # ------------------------------------------------

        if row.rent_item_status != "Returned":

            print("Skipped - Not Returned")

            continue

        # ------------------------------------------------
        # ITEM NOT FOUND
        # ------------------------------------------------

        if row.product_name not in dn_item_map:

            print(
                "Item Not Found In DN",
                row.product_name
            )

            continue

        dn_row = dn_item_map[row.product_name]

        print("Matched DN Row", dn_row)

        returned_item_found = True

        # ------------------------------------------------
        # APPEND ITEM
        # ------------------------------------------------

        return_dn.append("items", {

            "item_code": row.product_name,

            "qty": -1 * abs(row.qty),

            "warehouse": row.warehouse or dn_row.warehouse,

            "rate": row.rental_rate * row.duration,

            "amount": row.amount,

            "dn_detail": dn_row.name
        })

    print("return_dn_items", return_dn.items)

    # ===================================================
    # VALIDATION
    # ===================================================

    if not returned_item_found:

        frappe.throw(
            "No matching returned items found"
        )

    if not return_dn.items:

        frappe.throw(
            "No items added in Return Delivery Note"
        )

    # ===================================================
    # SAVE DELIVERY NOTE
    # ===================================================

    return_dn.flags.ignore_permissions = True

    return_dn.insert()

    print("Return DN Inserted", return_dn.name)

    # ===================================================
    # SUBMIT DELIVERY NOTE
    # ===================================================

    return_dn.submit()

    print("Return DN Submitted", return_dn.name)

    # ===================================================
    # UPDATE RENT CHILD TABLE STATUS
    # ===================================================

    returned_products = []

    for row in return_doc.return_product_details:

        if row.rent_item_status == "Returned":

            returned_products.append(
                row.product_name
            )

    # ---------------------------------------------------
    # UPDATE RENT PRODUCT STATUS
    # ---------------------------------------------------

    for row in rent_doc.rent_product_details:

        if row.product_name in returned_products:

            row.rent_item_status = "Returned"

    # ===================================================
    # CHECK WHETHER RENT SHOULD CLOSE
    # ===================================================

    close_rent = True

    for row in rent_doc.rent_product_details:

        # ------------------------------------------------
        # IF ANY ITEM IS NOT RETURNED OR RENEWAL
        # ------------------------------------------------

        if row.rent_item_status not in [
            "Returned",
            "Renewal"
        ]:

            close_rent = False
            break

    # ===================================================
    # UPDATE RENT STATUS
    # ===================================================

    if close_rent:

        rent_doc.status = "Closed"

    else:

        rent_doc.status = "Partial Active"

    # ===================================================
    # SAVE RENT
    # ===================================================

    rent_doc.save(ignore_permissions=True)

    print(
        "Rent Status Updated",
        rent_doc.status
    )

    # ===================================================
    # COMMIT
    # ===================================================

    frappe.db.commit()

    # ===================================================
    # RETURN
    # ===================================================

    return {
        "delivery_note": return_dn.name,
        "rent_status": rent_doc.status
    }
