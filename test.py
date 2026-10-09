# import os
# import json
# import re
# from unittest import result
# from wsgiref import headers
# import requests

# from datetime import datetime

# from item_master import (
#     get_access_token,
#     fetch_item_master,
#     reconcile_so_items_with_item_master,
# )


# # ============================================================
# # ZOHO CREATOR CONFIG
# # ============================================================

# CREATOR_API_URL = os.getenv(
#     "CREATOR_API_URL",
#     "https://www.zohoapis.in"
# ).rstrip("/")

# CREATOR_OWNER = os.getenv(
#     "CREATOR_OWNER"
# )

# CREATOR_APP = os.getenv(
#     "CREATOR_APP"
# )

# CREATOR_ENVIRONMENT = os.getenv(
#     "CREATOR_ENVIRONMENT",
#     "production"
# )

# # IMPORTANT:
# # This must be the REPORT LINK NAME of Sales Inbox.
# #
# # Example:
# # CREATOR_SALES_INBOX_REPORT=All_Sales_Inbox

# CREATOR_SALES_INBOX_REPORT = os.getenv(
#     "CREATOR_SALES_INBOX_REPORT"
# )


# # ============================================================
# # SALES INBOX FIELD API NAMES
# # ============================================================

# SALES_INBOX_LINES_FIELD = "Sales_Order_Lines"

# FIELD_BILLING_ADDRESS = "Billing_Address"
# FIELD_BU_GROUP = "BU_Group"
# FIELD_CURRENCY = "Currency"
# FIELD_CUSTOMER_NAME = "Customer_Name"
# FIELD_DELIVERY_DATE = "Delivery_Date"
# FIELD_GST_TREATMENT = "GST_Treatment"
# FIELD_GSTIN = "GSTIN"
# FIELD_NOTES = "Notes"
# FIELD_PAYMENT_TERMS = "Payment_Terms"
# FIELD_PAYMENT_TYPE = "Payment_Type"
# FIELD_PLACE_OF_SUPPLY = "Place_of_Supply"
# FIELD_PROJECT_NAME = "Project_Name"
# FIELD_REFERENCE = "Reference"
# FIELD_REFERENCE_DATE = "Reference_Date"
# FIELD_RESPONSIBLE_PERSON = "Responsible_person"
# FIELD_SALES_ORDER = "Sales_Order"
# FIELD_SALES_ORDER_DATE = "Sales_Order_Date"
# FIELD_SALES_ORDER_NO = "Sales_Order_No"
# FIELD_SHIPPING_ADDRESS = "Shipping_Address"
# FIELD_SHIPPING_GSTIN = "Shipping_GSTIN"


# # ============================================================
# # SALES ORDER LINE FIELD API NAMES
# # ============================================================

# LINE_MATERIAL_TYPE = "Material_Type"
# LINE_BALANCE_QTY = "Balance_Qty"
# LINE_ZB_ID = "ZB_ID"
# LINE_DESCRIPTION = "Description"
# LINE_DISCOUNT = "Discount"
# LINE_HSN_SAC = "HSN_SAC"
# LINE_TOTAL_AMOUNT = "Total_Amount"
# LINE_SALES_INBOX_ID = "Sales_Inbox_ID"
# LINE_SO_PARENT_ID = "SO_Parent_ID"
# LINE_TAX = "Tax"
# LINE_NET_AMOUNT = "Net_Amount"
# LINE_TAX_AMOUNT = "Tax_Amount"
# LINE_DISCOUNT_PERCENT = "Discount_in_percent"
# LINE_TOTAL_INVOICED_QTY = "Total_Invoiced_Qty"
# LINE_INVOICE_STATUS = "Invoice_Status"
# LINE_DELIVERY_DATE = "Delivery_Date"
# LINE_RATE = "Rate"
# LINE_QUANTITY = "Quantity"
# LINE_UOM = "UOM"
# LINE_TOTAL_INVOICED_PERCENT = "Total_Invoiced_Percent"
# LINE_IS_IMPORTED = "Is_imported"
# LINE_ITEM_NAME = "Item_Name"
# LINE_SALES_ORDER_NO = "Sales_Order_No"
# LINE_SALES_ORDER_PDF = "Sales_Order_PDF"
# LINE_SELECT = "Select"
# LINE_SENDER = "Sender_field"
# LINE_SHIPPING_ADDRESS = "Shipping_Address"
# LINE_SHIPPING_GSTIN = "Shipping_GSTIN"
# LINE_SPACE = "space"
# LINE_STATUS = "Status"
# LINE_SUBJECT = "Subject_field1"
# LINE_TAXABLE_VALUE = "Taxable_Value"
# LINE_TCS = "TCS"
# LINE_TCS_AMOUNT = "TCS_Amount"
# LINE_TDS = "TDS"
# LINE_TDS_AMOUNT = "TDS_Amount"
# LINE_TERMS_CONDITIONS = "Terms_Conditions"


# # ============================================================
# # BASIC HELPERS
# # ============================================================

# def _clean(value):
#     """
#     Convert None to empty string and remove unnecessary spaces.
#     """

#     if value is None:
#         return ""

#     if isinstance(value, str):
#         return value.strip()

#     return value


# def _to_number(value, default=None):
#     """
#     Convert numeric values safely.
#     """

#     if value in ("", None):
#         return default

#     try:
#         return float(value)

#     except (TypeError, ValueError):
#         return default


# def _to_int(value, default=None):
#     """
#     Convert lookup/number IDs safely.
#     """

#     if value in ("", None):
#         return default

#     try:
#         return int(value)

#     except (TypeError, ValueError):
#         return default


# def _extract_record_id(record):
#     """
#     Extract Creator record ID from different possible structures.
#     """

#     if not isinstance(record, dict):
#         return None

#     possible_keys = [
#         "ID",
#         "id",
#         "Record_ID",
#         "record_id",
#         "Item_ID",
#         "item_id",
#     ]

#     for key in possible_keys:

#         value = record.get(key)

#         if isinstance(value, dict):

#             nested_id = (
#                 value.get("ID")
#                 or value.get("id")
#                 or value.get("value")
#             )

#             if nested_id:
#                 return str(nested_id)

#             elif value not in ("", None):
#                 return str(value)

#             elif value not in ("", None):
#                 return str(value)

#     return None


#         # ============================================================
#         # DATE CONVERSION
#         # ============================================================

# def convert_date(value):
#     """
#     Convert common PDF date formats to Creator-compatible
#     date format.

#     Example:
#         22.07.2026 -> 22-Jul-2026

#         If the value is not a real date, return None.

#         IMPORTANT:
#             'Woche 02.2027' is NOT converted because it is not
#             a real date.
#             """

#     if not value:
#         return None

#     value = str(value).strip()

#     formats = [
#         "%d.%m.%Y",
#         "%d-%m-%Y",
#         "%d/%m/%Y",
#         "%Y-%m-%d",
#     ]

#     for fmt in formats:

#         try:

#             dt = datetime.strptime(
#                 value,
#                 fmt
#             )

#             return dt.strftime(
#                 "%d-%b-%Y"
#             )

#         except ValueError:
#             continue

#         return None


#     # ============================================================
#     # BUILD SALES ORDER LINE
#     # ============================================================

# def build_sales_order_line(
#     line_data,
#     sales_inbox_id,
#     item_master_record=None,
# ):
#     """
#     Convert extracted SO line into Creator
#     Sales_Order_Lines subform structure.
#     """

#     if not isinstance(line_data, dict):

#         raise ValueError(
#             "Sales Order line must be a dictionary."
#         )

#     item_code = _clean(
#         line_data.get("item_code")
#     )

#     item_name = _clean(
#         line_data.get("item_name")
#     )

#     description = _clean(
#         line_data.get("description")
#     )

#     hsn_sac = _clean(
#         line_data.get("hsn_sac")
#     )

#     uom = _clean(
#         line_data.get("uom")
#     )

#     delivery_date = convert_date(
#         line_data.get("delivery_date")
#     )

#     # --------------------------------------------------------
#     # Item Master lookup ID
#     # --------------------------------------------------------

#     item_master_id = _extract_record_id(
#         item_master_record
#     )

#     row = {}

#     # --------------------------------------------------------
#     # Item Name lookup
#     # --------------------------------------------------------

#     if item_master_id:

#         # Item_Name is a NUMBER/LOOKUP field.
#         row[LINE_ITEM_NAME] = _to_int(
#             item_master_id
#         )

#         # --------------------------------------------------------
#         # Material / Item Code
#         # --------------------------------------------------------

#         if item_code:
#             row[LINE_MATERIAL_TYPE] = item_code

#             # --------------------------------------------------------
#             # Description
#             # --------------------------------------------------------

#             if description:
#                 row[LINE_DESCRIPTION] = description

#                 # --------------------------------------------------------
#                 # HSN/SAC
#                 # --------------------------------------------------------

#                 if hsn_sac:
#                     row[LINE_HSN_SAC] = hsn_sac

#                     # --------------------------------------------------------
#                     # Quantity
#                     # --------------------------------------------------------

#                     quantity = _to_number(
#                         line_data.get("quantity")
#                     )

#                     if quantity is not None:
#                         row[LINE_QUANTITY] = quantity

#                         # --------------------------------------------------------
#                         # Rate
#                         # --------------------------------------------------------

#                         rate = _to_number(
#                             line_data.get("rate")
#                         )

#                         if rate is not None:
#                             row[LINE_RATE] = rate

#                             # --------------------------------------------------------
#                             # Discount
#                             # --------------------------------------------------------

#                             discount = _to_number(
#                                 line_data.get("discount")
#                             )

#                             if discount is not None:
#                                 row[LINE_DISCOUNT] = discount

#                                 # --------------------------------------------------------
#                                 # Discount Percentage
#                                 # --------------------------------------------------------

#                                 discount_percent = _to_number(
#                                     line_data.get("discount_percent")
#                                 )

#                                 if discount_percent is not None:
#                                     row[LINE_DISCOUNT_PERCENT] = (
#                                         discount_percent
#                                     )

#                                     # --------------------------------------------------------
#                                     # Net Amount
#                                     # --------------------------------------------------------

#                                     net_amount = _to_number(
#                                         line_data.get("net_amount")
#                                     )

#                                     if net_amount is not None:
#                                         row[LINE_NET_AMOUNT] = net_amount

#                                         # --------------------------------------------------------
#                                         # Total Amount
#                                         # --------------------------------------------------------

#                                         total_amount = _to_number(
#                                             line_data.get("total_amount")
#                                         )

#                                         if total_amount is not None:
#                                             row[LINE_TOTAL_AMOUNT] = total_amount

#                                             # --------------------------------------------------------
#                                             # Tax Amount
#                                             # --------------------------------------------------------

#                                             tax_amount = _to_number(
#                                                 line_data.get("tax_amount")
#                                             )

#                                             if tax_amount is not None:
#                                                 row[LINE_TAX_AMOUNT] = tax_amount

#                                                 # --------------------------------------------------------
#                                                 # Balance Quantity
#                                                 # --------------------------------------------------------

#                                                 balance_qty = _to_number(
#                                                     line_data.get("balance_qty")
#                                                 )

#                                                 if balance_qty is not None:
#                                                     row[LINE_BALANCE_QTY] = balance_qty

#                                                     # --------------------------------------------------------
#                                                     # Total Invoiced Quantity
#                                                     # --------------------------------------------------------

#                                                     total_invoiced_qty = _to_number(
#                                                         line_data.get("total_invoiced_qty")
#                                                     )

#                                                     if total_invoiced_qty is not None:
#                                                         row[LINE_TOTAL_INVOICED_QTY] = (
#                                                             total_invoiced_qty
#                                                         )

#                                                         # --------------------------------------------------------
#                                                         # Total Invoiced Percentage
#                                                         # --------------------------------------------------------

#                                                         total_invoiced_percent = _to_number(
#                                                             line_data.get("total_invoiced_percent")
#                                                         )

#                                                         if total_invoiced_percent is not None:
#                                                             row[LINE_TOTAL_INVOICED_PERCENT] = (
#                                                                 total_invoiced_percent
#                                                             )

#                                                             # --------------------------------------------------------
#                                                             # Tax
#                                                             # --------------------------------------------------------

#                                                             tax = line_data.get("tax")

#                                                             if tax not in ("", None):
#                                                                 row[LINE_TAX] = tax

#                                                                 # --------------------------------------------------------
#                                                                 # Invoice Status
#                                                                 # --------------------------------------------------------

#                                                                 invoice_status = _clean(
#                                                                     line_data.get("invoice_status")
#                                                                 )

#                                                                 if invoice_status:
#                                                                     row[LINE_INVOICE_STATUS] = (
#                                                                         invoice_status
#                                                                     )

#                                                                     # --------------------------------------------------------
#                                                                     # Delivery Date
#                                                                     # --------------------------------------------------------

#                                                                     if delivery_date:
#                                                                         row[LINE_DELIVERY_DATE] = (
#                                                                             delivery_date
#                                                                         )

#                                                                         # --------------------------------------------------------
#                                                                         # UOM
#                                                                         # --------------------------------------------------------

#                                                                         # UOM is NUMBER/LOOKUP in Creator.
#                                                                         #
#                                                                         # The PDF value such as "Stück" cannot be directly
#                                                                         # inserted into a NUMBER/LOOKUP field.
#                                                                         #
#                                                                         # If uom_id is available, use it.

#                                                                         uom_id = line_data.get("uom_id")

#                                                                         if uom_id not in ("", None):

#                                                                             converted_uom_id = _to_int(
#                                                                                 uom_id
#                                                                             )

#                                                                             if converted_uom_id is not None:
#                                                                                 row[LINE_UOM] = converted_uom_id

#                                                                                 # --------------------------------------------------------
#                                                                                 # Sales Inbox Parent ID
#                                                                                 # --------------------------------------------------------

#                                                                                 sales_inbox_record_id = _to_int(
#                                                                                     sales_inbox_id
#                                                                                 )

#                                                                                 if sales_inbox_record_id is not None:
#                                                                                     row[LINE_SALES_INBOX_ID] = (
#                                                                                         sales_inbox_record_id
#                                                                                     )

#                                                                                     # --------------------------------------------------------
#                                                                                     # SO Parent ID
#                                                                                     # --------------------------------------------------------

#                                                                                     so_parent_id = line_data.get(
#                                                                                         "so_parent_id"
#                                                                                     )

#                                                                                     if so_parent_id not in ("", None):

#                                                                                         converted_parent_id = _to_int(
#                                                                                             so_parent_id
#                                                                                         )

#                                                                                         if converted_parent_id is not None:
#                                                                                             row[LINE_SO_PARENT_ID] = (
#                                                                                                 converted_parent_id
#                                                                                             )

#                                                                                             # --------------------------------------------------------
#                                                                                             # Sales Order Number
#                                                                                             # --------------------------------------------------------

#                                                                                             sales_order_no = _clean(
#                                                                                                 line_data.get(
#                                                                                                     "sales_order_no"
#                                                                                                 )
#                                                                                             )

#                                                                                             if sales_order_no:
#                                                                                                 row[LINE_SALES_ORDER_NO] = (
#                                                                                                     sales_order_no
#                                                                                                 )

#                                                                                                 # --------------------------------------------------------
#                                                                                                 # Imported
#                                                                                                 # --------------------------------------------------------

#                                                                                                 is_imported = line_data.get(
#                                                                                                     "is_imported"
#                                                                                                 )

#                                                                                                 if is_imported not in ("", None):

#                                                                                                     if isinstance(
#                                                                                                         is_imported,
#                                                                                                         str
#                                                                                                     ):

#                                                                                                         row[LINE_IS_IMPORTED] = (
#                                                                                                             is_imported.lower()
#                                                                                                             in (
#                                                                                                                 "true",
#                                                                                                                 "1",
#                                                                                                                 "yes",
#                                                                                                             )
#                                                                                                         )

#                                                                                                     else:
#                                                                                                         row[LINE_IS_IMPORTED] = bool(
#                                                                                                             is_imported
#                                                                                                         )

#                                                                                                         # --------------------------------------------------------
#                                                                                                         # Optional fields
#                                                                                                         # --------------------------------------------------------

#                                                                                                         value = _clean(
#                                                                                                             line_data.get("sender")
#                                                                                                         )

#                                                                                                         if value:
#                                                                                                             row[LINE_SENDER] = value

#                                                                                                             value = _clean(
#                                                                                                                 line_data.get(
#                                                                                                                     "shipping_address"
#                                                                                                                 )
#                                                                                                             )

#                                                                                                             if value:
#                                                                                                                 row[LINE_SHIPPING_ADDRESS] = value

#                                                                                                                 value = _clean(
#                                                                                                                     line_data.get(
#                                                                                                                         "shipping_gstin"
#                                                                                                                     )
#                                                                                                                 )

#                                                                                                                 if value:
#                                                                                                                     row[LINE_SHIPPING_GSTIN] = value

#                                                                                                                     value = _clean(
#                                                                                                                         line_data.get("status")
#                                                                                                                     )

#                                                                                                                     if value:
#                                                                                                                         row[LINE_STATUS] = value

#                                                                                                                         value = _clean(
#                                                                                                                             line_data.get("subject")
#                                                                                                                         )

#                                                                                                                         if value:
#                                                                                                                             row[LINE_SUBJECT] = value

#                                                                                                                             value = _to_number(
#                                                                                                                                 line_data.get("taxable_value")
#                                                                                                                             )

#                                                                                                                             if value is not None:
#                                                                                                                                 row[LINE_TAXABLE_VALUE] = value

#                                                                                                                                 value = _to_number(
#                                                                                                                                     line_data.get("tcs")
#                                                                                                                                 )

#                                                                                                                                 if value is not None:
#                                                                                                                                     row[LINE_TCS] = value

#                                                                                                                                     value = _to_number(
#                                                                                                                                         line_data.get("tcs_amount")
#                                                                                                                                     )

#                                                                                                                                     if value is not None:
#                                                                                                                                         row[LINE_TCS_AMOUNT] = value

#                                                                                                                                         value = _to_number(
#                                                                                                                                             line_data.get("tds")
#                                                                                                                                         )

#                                                                                                                                         if value is not None:
#                                                                                                                                             row[LINE_TDS] = value

#                                                                                                                                             value = _to_number(
#                                                                                                                                                 line_data.get("tds_amount")
#                                                                                                                                             )

#                                                                                                                                             if value is not None:
#                                                                                                                                                 row[LINE_TDS_AMOUNT] = value

#                                                                                                                                                 value = _clean(
#                                                                                                                                                     line_data.get(
#                                                                                                                                                         "terms_conditions"
#                                                                                                                                                     )
#                                                                                                                                                 )

#                                                                                                                                                 if value:
#                                                                                                                                                     row[LINE_TERMS_CONDITIONS] = value

#                                                                                                                                                     return row


#                                                                                                                                                 # ============================================================
#                                                                                                                                                 # BUILD SALES INBOX HEADER
#                                                                                                                                                 # ============================================================
# def build_creator_address(
#     address_line_1=None,
#     address_line_2=None,
#     city=None,
#     state=None,
#     postal_code=None,
#     country=None
# ):
#     return {
#         "address_line_1": address_line_1 or "",
#         "address_line_2": address_line_2 or "",
#         "district_city": city or "",
#         "state_province": state or "",
#         "postal_code": postal_code or "",
#         "country": country or ""
#     }
    
# def parse_address_text(address):
#     if not address:
#         return {}

#     lines = [
#         line.strip()
#         for line in str(address).splitlines()
#         if line.strip()
#     ]

#     result = {
#         "address_line_1": "",
#         "address_line_2": "",
#         "district_city": "",
#         "state_province": "",
#         "postal_code": "",
#         "country": ""
#     }

#     if len(lines) >= 1:
#         result["address_line_1"] = lines[0]

#     if len(lines) >= 2:
#         result["address_line_2"] = lines[1]

#     if len(lines) >= 3:
#         import re

#         match = re.search(
#            r"\b(\d{4,6})\b\s*(.*)",
#            lines[2]
# )

#         if match:
#             result["postal_code"] = str(match.group(1) or "")
#             result["district_city"] = str(match.group(2).strip())
#         else:
#            result["district_city"] = lines[2]

#     if len(lines) >= 4:
#         result["country"] = lines[3]

#         return result



# def build_sales_inbox_header(so_data):
#     """
#     Build Sales Inbox header fields.

#     Only values actually available in so_data are sent.

#     Lookup fields require actual Creator record IDs.
#     """

#     if not isinstance(so_data, dict):

#         raise ValueError(
#             "so_data must be a dictionary."
#         )

#     record = {}

#     # --------------------------------------------------------
#     # Billing Address
#     # --------------------------------------------------------

  
    
#     billing_address = parse_address_text(
#     so_data.get("billing_address")
#     )
#     if billing_address:
#         record[FIELD_BILLING_ADDRESS] = build_creator_address(
#             address_line_1=billing_address.get("address_line_1"),
#             address_line_2=billing_address.get("address_line_2"),
#             city=billing_address.get("district_city"),
#             state=billing_address.get("state_province"),
#             postal_code=billing_address.get("postal_code"),
#             country=billing_address.get("country")
#     )
        
        
#         # --------------------------------------------------------
#         # Shipping Address
#         # --------------------------------------------------------

#         shipping_address = parse_address_text(
#             so_data.get(
#                 "shipping_address"
#             )
#         )

#         if shipping_address:
#             record[
#                 FIELD_SHIPPING_ADDRESS
#             ] = build_creator_address(
#                 address_line_1=shipping_address.get("address_line_1"),
#                 address_line_2=shipping_address.get("address_line_2"),
#                 city=shipping_address.get("district_city"),
#                 state=shipping_address.get("state_province"),
#                 postal_code=shipping_address.get("postal_code"),
#                 country=shipping_address.get("country")
#             )

#             # --------------------------------------------------------
#             # GSTIN
#             # --------------------------------------------------------

#             value = _clean(
#                 so_data.get("gstin")
#             )

#             if value:
#                 record[
#                     FIELD_GSTIN
#                 ] = value

#                 # --------------------------------------------------------
#                 # Shipping GSTIN
#                 # --------------------------------------------------------

#                 value = _clean(
#                     so_data.get(
#                         "shipping_gstin"
#                     )
#                 )

#                 if value:
#                     record[
#                         FIELD_SHIPPING_GSTIN
#                     ] = value

#                     # --------------------------------------------------------
#                     # GST Treatment
#                     # --------------------------------------------------------

#                     value = _clean(
#                         so_data.get(
#                             "gst_treatment"
#                         )
#                     )

#                     if value:
#                         record[
#                             FIELD_GST_TREATMENT
#                         ] = value

#                         # --------------------------------------------------------
#                         # Payment Terms
#                         # --------------------------------------------------------

#                         value = _clean(
#                             so_data.get(
#                                 "payment_terms"
#                             )
#                         )

#                         if value:
#                             record[
#                                 FIELD_PAYMENT_TERMS
#                             ] = value

#                             # --------------------------------------------------------
#                             # Payment Type
#                             # --------------------------------------------------------

#                             value = _clean(
#                                 so_data.get(
#                                     "payment_type"
#                                 )
#                             )

#                             if value:
#                                 record[
#                                     FIELD_PAYMENT_TYPE
#                                 ] = value

#                                 # --------------------------------------------------------
#                                 # Notes
#                                 # --------------------------------------------------------

#                                 value = _clean(
#                                     so_data.get(
#                                         "notes_content"
#                                     )
#                                 )

#                                 if value:
#                                     record[
#                                         FIELD_NOTES
#                                     ] = value

#                                     # --------------------------------------------------------
#                                     # Reference
#                                     # --------------------------------------------------------

#                                     value = _clean(
#                                         so_data.get(
#                                             "reference_no"
#                                         )
#                                     )

#                                     if value:
#                                         record[
#                                             FIELD_REFERENCE
#                                         ] = value

#                                         # --------------------------------------------------------
#                                         # Sales Order Number
#                                         # --------------------------------------------------------

#                                         value = _clean(
#                                             so_data.get(
#                                                 "sales_order_no"
#                                             )
#                                         )

#                                         if value:
#                                             record[
#                                                 FIELD_SALES_ORDER_NO
#                                             ] = value

#                                             # --------------------------------------------------------
#                                             # Sales Order Date
#                                             # --------------------------------------------------------

#                                             value = convert_date(
#                                                 so_data.get(
#                                                     "sales_order_date"
#                                                 )
#                                             )

#                                             if value:
#                                                 record[
#                                                     FIELD_SALES_ORDER_DATE
#                                                 ] = value

#                                                 # --------------------------------------------------------
#                                                 # Reference Date
#                                                 # --------------------------------------------------------

#                                                 value = convert_date(
#                                                     so_data.get(
#                                                         "reference_date"
#                                                     )
#                                                 )

#                                                 if value:
#                                                     record[
#                                                         FIELD_REFERENCE_DATE
#                                                     ] = value

#                                                     # --------------------------------------------------------
#                                                     # Delivery Date
#                                                     # --------------------------------------------------------

#                                                     value = convert_date(
#                                                         so_data.get(
#                                                             "delivery_date"
#                                                         )
#                                                     )

#                                                     if value:
#                                                         record[
#                                                             FIELD_DELIVERY_DATE
#                                                         ] = value

#                                                         # --------------------------------------------------------
#                                                         # BU Group
#                                                         # --------------------------------------------------------

#                                                         bu_group = so_data.get(
#                                                             "bu_group"
#                                                         )

#                                                         if bu_group not in (
#                                                             "",
#                                                             None,
#                                                         ):

#                                                             value = _to_number(
#                                                                 bu_group
#                                                             )

#                                                             if value is not None:
#                                                                 record[
#                                                                     FIELD_BU_GROUP
#                                                                 ] = value

#                                                                 # --------------------------------------------------------
#                                                                 # Customer Lookup
#                                                                 # --------------------------------------------------------

#                                                                 customer_id = so_data.get(
#                                                                     "customer_id"
#                                                                 )

#                                                                 if customer_id not in (
#                                                                     "",
#                                                                     None,
#                                                                 ):

#                                                                     record[
#                                                                         FIELD_CUSTOMER_NAME
#                                                                     ] = str(customer_id)

#                                                                     # --------------------------------------------------------
#                                                                     # Currency Lookup
#                                                                     # --------------------------------------------------------

#                                                                     currency_id = so_data.get(
#                                                                         "currency_id"
#                                                                     )

#                                                                     if currency_id not in (
#                                                                         "",
#                                                                         None,
#                                                                     ):

#                                                                         record[
#                                                                             FIELD_CURRENCY
#                                                                         ] = str(currency_id)

#                                                                         # --------------------------------------------------------
#                                                                         # Place Of Supply Lookup
#                                                                         # --------------------------------------------------------

#                                                                         place_of_supply_id = so_data.get(
#                                                                             "place_of_supply_id"
#                                                                         )

#                                                                         if place_of_supply_id not in (
#                                                                             "",
#                                                                             None,
#                                                                         ):

#                                                                             record[
#                                                                                 FIELD_PLACE_OF_SUPPLY
#                                                                             ] = str(
#                                                                                 place_of_supply_id
#                                                                             )

#                                                                             # --------------------------------------------------------
#                                                                             # Project Lookup
#                                                                             # --------------------------------------------------------

#                                                                             project_id = so_data.get(
#                                                                                 "project_id"
#                                                                             )

#                                                                             if project_id not in (
#                                                                                 "",
#                                                                                 None,
#                                                                             ):

#                                                                                 record[
#                                                                                     FIELD_PROJECT_NAME
#                                                                                 ] = str(project_id)

#                                                                                 # --------------------------------------------------------
#                                                                                 # Responsible Person Lookup
#                                                                                 # --------------------------------------------------------

#                                                                                 responsible_person_id = so_data.get(
#                                                                                     "responsible_person_id"
#                                                                                 )

#                                                                                 if responsible_person_id not in (
#                                                                                     "",
#                                                                                     None,
#                                                                                 ):

#                                                                                     record[
#                                                                                         FIELD_RESPONSIBLE_PERSON
#                                                                                     ] = str(
#                                                                                         responsible_person_id
#                                                                                     )

#                                                                                     # --------------------------------------------------------
#                                                                                     # Sales Order Lookup
#                                                                                     # --------------------------------------------------------

#                                                                                     sales_order_id = so_data.get(
#                                                                                         "sales_order_id"
#                                                                                     )

#                                                                                     if sales_order_id not in (
#                                                                                         "",
#                                                                                         None,
#                                                                                     ):

#                                                                                         record[
#                                                                                             FIELD_SALES_ORDER
#                                                                                         ] = str(
#                                                                                             sales_order_id
#                                                                                         )

#                                                                                         print("\nSales Inbox Header:")
#                                                                                         print(
#                                                                                             json.dumps(
#                                                                                                 record,
#                                                                                                 ensure_ascii=True,
#                                                                                                 indent=2,
#                                                                                                 default=str,
#                                                                                             )
#                                                                                         )

#                                                                                         return record

#     # ------------------------------------------------------------------
#     # Fallback: always return the built header even if some optional lookup
#     # fields are missing. This prevents a later 'NoneType is not subscriptable'
#     # error when record is used as a dictionary.
#     # ------------------------------------------------------------------
#     print("\nSales Inbox Header (fallback):")
#     print(
#         json.dumps(
#             record,
#             ensure_ascii=True,
#             indent=2,
#             default=str,
#         )
#     )
#     return record


# # ============================================================
# # BUILD SALES ORDER LINES
# # ============================================================

# def build_sales_order_lines(
#     so_data,
#     reconciliation_result,
#     sales_inbox_id,
# ):
#     """
#     Build Sales_Order_Lines from extracted SO lines.

#     Maps each SO line number to its Item Master record.
#     """

#     so_lines = so_data.get(
#         "so_lines",
#         []
#     )

#     reconciliation = (
#         reconciliation_result.get(
#             "reconciliation",
#             []
#         )
#         if isinstance(
#             reconciliation_result,
#             dict
#         )
#         else []
#     )

#     # --------------------------------------------------------
#     # Map:
#     # line number -> Item Master record
#     # --------------------------------------------------------

#     item_master_by_line = {}

#     for result in reconciliation:

#         if not isinstance(
#             result,
#             dict
#         ):
#             continue

#         line_number = result.get(
#             "line_number"
#         )

#         item_master = result.get(
#             "item_master"
#         )

#         if line_number is None:
#             continue

#         try:
#             item_master_by_line[
#                 int(line_number)
#             ] = item_master

#         except (
#             TypeError,
#             ValueError,
#         ):
#             continue


#         # --------------------------------------------------------
#         # Build rows
#         # --------------------------------------------------------

#         subform_rows = []

#         for index, line_data in enumerate(
#             so_lines,
#             start=1
#         ):

#             if hasattr(
#                 line_data,
#                 "model_dump"
#             ):
#                 line_data = (
#                     line_data.model_dump()
#                 )

#             elif not isinstance(
#                 line_data,
#                 dict
#             ):
#                 continue


#             item_master = (
#                 item_master_by_line.get(
#                     index
#                 )
#             )


#             print(
#                 f"\nBuilding Sales Order Line {index}"
#             )

#             print(
#                 "Item Master:"
#             )

#             print(
#                 json.dumps(
#                     item_master,
#                     ensure_ascii=True,
#                     default=str,
#                 )
#             )


#             row = build_sales_order_line(
#                 line_data=line_data,
#                 sales_inbox_id=sales_inbox_id,
#                 item_master_record=item_master,
#             )


#             if row:
#                 subform_rows.append(
#                     row
#                 )


#                 # --------------------------------------------------------
#                 # IMPORTANT:
#                 # Return AFTER processing ALL lines
#                 # --------------------------------------------------------

#                 print(
#                     "\nSales Order Lines Count:",
#                     len(subform_rows),
#                 )

#                 print(
#                     "\nSales Order Lines Payload:"
#                 )

#                 print(
#                     json.dumps(
#                         subform_rows,
#                         ensure_ascii=True,
#                         indent=2,
#                         default=str,
#                     )
#                 )

#                 return subform_rows
# # ============================================================
# # UPDATE SALES INBOX
# # ============================================================

# def update_sales_inbox(
#     sales_inbox_id,
#     so_data,
#     item_master_records=None,
#     reconciliation_result=None,
# ):
#     """
#     Update existing Sales Inbox record.
#     """
#     if not sales_inbox_id:
#         raise ValueError("sales_inbox_id is required.")

#     if not isinstance(so_data, dict):
#         raise ValueError("so_data must be a dictionary.")

#     if not CREATOR_OWNER:
#         raise RuntimeError("Missing environment variable: CREATOR_OWNER")

#     if not CREATOR_APP:
#         raise RuntimeError("Missing environment variable: CREATOR_APP")

#     if not CREATOR_SALES_INBOX_REPORT:
#         raise RuntimeError("Missing environment variable: CREATOR_SALES_INBOX_REPORT")

#     token_data = get_access_token()
#     access_token = token_data.get("access_token")
#     if not access_token:
#         raise RuntimeError("Access token missing from token response.")

#     api_domain = token_data.get("api_domain") or CREATOR_API_URL
#     api_base = api_domain.rstrip("/")

#     url = (
#         f"{api_base}/creator/v2.1/data/"
#         f"{CREATOR_OWNER}/{CREATOR_APP}/report/"
#         f"{CREATOR_SALES_INBOX_REPORT}/{sales_inbox_id}"
#     )

#     headers = {
#         "Authorization": f"Zoho-oauthtoken {access_token}",
#         "Accept": "application/json",
#         "Content-Type": "application/json",
#     }

#     if CREATOR_ENVIRONMENT != "production":
#         headers["environment"] = CREATOR_ENVIRONMENT

#     record = build_sales_inbox_header(so_data)

#     sales_order_lines = build_sales_order_lines(
#         so_data=so_data,
#         reconciliation_result=reconciliation_result or {},
#         sales_inbox_id=sales_inbox_id,
#     )

#     if sales_order_lines:
#         record[SALES_INBOX_LINES_FIELD] = sales_order_lines

#     payload = {
#         "data": record,
#         "skip_workflow": ["all"],
#     }

#     try:
#         response = requests.patch(url, headers=headers, json=payload, timeout=60)
#     except requests.RequestException as e:
#         raise RuntimeError(f"Sales Inbox update request failed: {e}") from e

#     if response.status_code not in (200, 201):
#         raise RuntimeError(
#             f"Sales Inbox update failed. HTTP {response.status_code}: {response.text[:5000]}"
#         )

#     try:
#         body = response.json()
#     except ValueError as e:
#         raise RuntimeError(
#             f"Sales Inbox API returned invalid JSON: {response.text[:5000]}"
#         ) from e

#     if not isinstance(body, dict):
#         raise RuntimeError("Sales Inbox API returned invalid response.")

#     if body.get("code") not in (None, 3000):
#         raise RuntimeError(f"Sales Inbox update returned an error: {body}")

#     return {
#         "success": True,
#         "sales_inbox_id": str(sales_inbox_id),
#         "sales_order_lines_count": len(sales_order_lines or []),
#         "updated_fields": list(record.keys()),
#         "creator_response": body,
#     }


# def process_sales_inbox_so(
#     sales_inbox_id,
#     so_data,
#     item_master_records=None,
#     reconciliation_result=None,
# ):
#     """
#     Complete Sales Inbox update process.

#     1. Get Item Master records if needed.
#     2. Reuse reconciliation result if supplied.
#     3. Update Sales Inbox.
#     4. Return the actual update result.
#     """
#     if not sales_inbox_id:
#         raise ValueError("Sales Inbox ID is required.")

#     if not isinstance(so_data, dict):
#         raise ValueError("so_data must be a dictionary.")

#     try:
#         if item_master_records is None:
#             item_master_records = fetch_item_master(max_pages=50, page_size=1000)

#         if reconciliation_result is None:
#             reconciliation_result = reconcile_so_items_with_item_master(
#                 so_lines=so_data.get("so_lines", []),
#                 item_master_records=item_master_records,
#             )

#         result = update_sales_inbox(
#             sales_inbox_id=sales_inbox_id,
#             so_data=so_data,
#             item_master_records=item_master_records,
#             reconciliation_result=reconciliation_result,
#         )

#         return result

#     except Exception as e:
#         raise RuntimeError(f"Sales Inbox processing failed: {e}") from e