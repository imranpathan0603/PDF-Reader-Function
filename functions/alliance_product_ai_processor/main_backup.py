import base64

import binascii

import json

import logging

import os

import re



import fitz

from flask import Request, jsonify, make_response, request

from openai import OpenAI

from pydantic import BaseModel, Field
from sales_inbox_updater import process_sales_inbox_so
from customer_service import get_or_create_customer




from item_master import (
    fetch_item_master,
    reconcile_so_items_with_item_master,
)



logger = logging.getLogger()

logger.setLevel(logging.INFO)



MAX_PDF_BYTES = 10 * 1024 * 1024

MAX_PDF_TEXT_CHARS = 40000



class SOLineItem(BaseModel):

    item_code: str = Field(

        default="",

        description=(

            "Part Number first; Part Number. "

            "Never use description, quantity, or UOM as item_code."

        ),

    )

    item_name: str = Field(default="", description="Item Name")

    description: str = Field(default="", description="Detailed item description")

    hsn_sac: str = Field(default="", description="HSN or SAC Code")

    delivery_date: str = Field(default="", description="Delivery / Ship Date")

    quantity: float = Field(default=0.0, description="Quantity ordered")

    uom: str = Field(default="pcs", description="Unit of Measurement")

    rate: float = Field(default=0.0, description="Unit rate")

    discount_percent: float = Field(default=0.0, description="Discount percentage")

    discount: float = Field(default=0.0, description="Discount amount")

    net_amount: float = Field(default=0.0, description="Net amount")

    tax: str = Field(default="", description="Tax")

    tax_amount: float = Field(default=0.0, description="Tax amount")

    total_amount: float = Field(default=0.0, description="Total line amount")

    total_invoiced_qty: float = Field(default=0.0, description="Invoiced quantity")

    balance_qty: float = Field(default=0.0, description="Balance quantity")

    total_invoiced_percent: float = Field(

        default=0.0, description="Percentage invoiced"

    )

    invoice_status: str = Field(default="", description="Invoice status")

    so_parent_id: str = Field(default="", description="SO Parent ID")

    is_imported: bool = Field(default=False, description="Whether item is imported")

    sales_inbox_id: str = Field(default="", description="Sales Inbox ID")





class SalesOrderData(BaseModel):

    sales_order_no: str = Field(default="", description="Sales Order Number / PO Number")

    sales_order_date: str = Field(default="", description="Sales Order Date")

    customer_name: str = Field(
    default="",
    description="Customer name from the supplier/company header at the top of the PO. Do not use Wootz Work / Order To."
)

    customer_email: str = Field(
    default="",
    description="company email from the supplier/company header."
)

    customer_phone: str = Field(
    default="",
    description="company phone from the supplier/company header."
)


    reference_no: str = Field(default="", description="Reference / Quote / PO number")

    reference_date: str = Field(default="", description="Reference date")

    project_name: str = Field(default="", description="Project Name")

    payment_type: str = Field(default="Other", description="Payment Type")

    delivery_date: str = Field(default="", description="Expected delivery date")

    bu_group: str = Field(default="Component", description="Business Unit / Group")

    notes_content: str = Field(default="", description="Notes / comments / instructions")

    gst_treatment: str = Field(default="", description="GST Treatment")

    gstin: str = Field(default="", description="Customer GSTIN")

    shipping_gstin: str = Field(default="", description="Shipping GSTIN")

    place_of_supply: str = Field(default="", description="Place of Supply")

    currency: str = Field(default="INR - Indian Rupee", description="Currency")

    payment_terms: str = Field(default="Net 30", description="Payment Terms")

    responsible_person: str = Field(

        default="", description="Responsible Person / Sales Representative"

    )

    sales_order: str = Field(default="", description="Additional SO details")

    billing_address: str = Field(default="", description="Billing Address")

    shipping_address: str = Field(default="", description="Shipping Address")

    so_lines: list[SOLineItem] = Field(

        default_factory=list, description="Sales Order line items"

    )





def extract_text_from_pdf(pdf_bytes: bytes) -> str:

    text_chunks = []

    pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")

    try:

        for page in pdf_document:

            page_text = page.get_text()

            if page_text:

                text_chunks.append(page_text)

    finally:

        pdf_document.close()

    return "\n--- PAGE BREAK ---\n".join(text_chunks)





def value_to_text(value) -> str:

    """Convert Creator field values, including lookups and lists, to text."""

    if value is None:

        return ""

    if isinstance(value, (bool, str, int, float)):

        return str(value)

    if isinstance(value, dict):

        return " ".join(

            text for child in value.values()

            if (text := value_to_text(child))

        )

    if isinstance(value, (list, tuple)):

        return " ".join(

            text for child in value

            if (text := value_to_text(child))

        )

    return str(value)





def build_item_master_context(

    records,

    document_text: str,

    max_candidates: int = 25,

    max_context_chars: int = 12000,

) -> str:

    """Select relevant catalog fields without returning unrelated records."""

    if not isinstance(records, (list, tuple)):
        raise ValueError("records must be a list or tuple.")

    normalized_text = " ".join(

        re.findall(r"[a-z0-9]+", document_text.casefold())

    )

    padded_text = f" {normalized_text} "

    document_tokens = set(normalized_text.split())

    field_hints = ("item", "product", "part", "code", "sku", "name", "description", "id")

    identifier_hints = ("part", "code", "sku", "id")

    exact_records = []

    fuzzy_records = []



    for record in records:

        if not isinstance(record, dict):

            continue



        match_fields = {}

        score = 0

        has_exact_match = False



        for field, value in record.items():

            field_name = str(field).casefold()

            if not any(hint in field_name for hint in field_hints):

                continue



            value_text = value_to_text(value).strip()

            if not value_text:

                continue

            match_fields[field] = value

            normalized_value = " ".join(

                re.findall(r"[a-z0-9]+", value_text.casefold())

            )

            if not normalized_value:

                continue

            weight = 3 if any(hint in field_name for hint in identifier_hints) else 1

            if len(normalized_value) >= 3 and f" {normalized_value} " in padded_text:

                score += 100 * weight

                has_exact_match = True

                common_tokens = set(normalized_value.split()) & document_tokens

                score += len(common_tokens) * weight

        if score and match_fields:
            target = exact_records if has_exact_match else fuzzy_records
            target.append((score, match_fields))

    ranked_records = exact_records if exact_records else fuzzy_records
    ranked_records.sort(key=lambda entry: entry[0], reverse=True)

    candidates = []
    for _, candidate in ranked_records[:max_candidates]:
        proposed = json.dumps(
            candidates + [candidate],
            ensure_ascii=True,
            separators=(",", ":"),
            default=str,
        )
        if len(proposed) <= max_context_chars:
            candidates.append(candidate)

    return json.dumps(
        candidates,
        ensure_ascii=True,
        separators=(",", ":"),
        default=str,
    )



def load_item_master():

    logger.info("Fetching Item Master from Zoho Creator")

    logger.info("Creator Owner: %s", os.getenv("CREATOR_OWNER", ""))

    logger.info("Creator App: %s", os.getenv("CREATOR_APP", ""))

    logger.info("Creator Report: %s", os.getenv("CREATOR_ITEM_REPORT", ""))



    try:

        item_master = fetch_item_master(max_pages=50, page_size=1000)

    except Exception as e:

        logger.exception("Item Master fetch failed")

        raise RuntimeError(

            f"Item Master fetch failed: {type(e).__name__}: {e}"

        ) from e



    logger.info("Fetched %d Item Master records", len(item_master))

    for index, item in enumerate(item_master[:5], start=1):

        logger.info(

            "ITEM MASTER %d: %s",

            index,

            json.dumps(item, ensure_ascii=True, default=str),

        )

    return item_master



SYSTEM_PROMPT = """
You are an expert Sales Order document parser for Wootz Work ERP.

Extract all Sales Order fields accurately from the document.
For each line item, prefer Part Number, then Item ID, then a value explicitly
labeled SKU. Never use description, quantity, or UOM as an item code, and never
invent a value. Use the Item Master reference only to validate identifiers;
do not invent a match or return unrelated catalog records.
Extract only information present in the PDF. Use empty strings for missing text
and zero for missing numbers. Return every Sales Order line item.

IMPORTANT CUSTOMER NAME RULE:

    The customer_name must contain the actual company or organization name
    found in the PDF.

    - Do not use labels such as "From", "To", "Order To", "Sent By",
    "Supplier", "Vendor", "Customer", "Company", etc. as the customer name.
    - Do not use an address, phone number, email address, website, PO number,
    reference number, or person's name as customer_name unless the document
    clearly identifies that person/company as the customer.
    - Do not invent or construct a company name.
    - customer_name must be copied from an actual company/organization name
    appearing in the PDF.
    - If Wootz Work or Wootzwork Labs Private Limited appears anywhere in the PDF,
    treat it as OUR COMPANY and exclude it from customer identification.
    - If multiple company names are present, select the external company that
    issued/sent/supplied the Purchase Order.
    - Prefer the company name appearing in the "From", "Sent By", "Supplier",
    "Vendor", "Seller", "Issued By", or company-header section.
    - Never select Wootz Work when another valid external company name is present.
    - If no valid external company name can be found anywhere in the PDF,
    return an empty string rather than guessing.
"""



def extract_sales_order(extracted_text: str, item_master_context: str):
    openai_key = os.getenv("OPENAI_API_KEY")

    if not openai_key:
        raise RuntimeError("Missing environment variable: OPENAI_API_KEY")

    client = OpenAI(api_key=openai_key, timeout=60.0)

    user_prompt = (
        "SALES ORDER DOCUMENT\n"
        "========================================\n"
        f"{extracted_text}\n\n"
        "ITEM MASTER REFERENCE\n"
        "========================================\n"
        f"{item_master_context}\n"
    )

    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format=SalesOrderData,
            timeout=60.0,
        )
    except Exception as e:
        raise RuntimeError(f"OpenAI extraction failed: {e}") from e

    if not completion.choices:
        raise RuntimeError("OpenAI returned no choices.")

    parsed_data = completion.choices[0].message.parsed
    if parsed_data is None:
        raise RuntimeError("OpenAI did not return parsed Sales Order data.")

    return parsed_data



def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response



def error_response(message: str, status: int, **extra):
    body = {"success": False, "error": message}
    body.update(extra)
    response = jsonify(body)
    response.status_code = status
    return add_cors(response)



def read_input_file(request: Request):
    """Read a PDF upload or JSON/base64 payload."""
    files = request.files or {}
    if "file" in files:
        uploaded_file = files["file"]
        return uploaded_file.read(), uploaded_file.filename or ""

    req_data = request.get_json(silent=True)
    if not isinstance(req_data, dict):
        return None, ""

    file_name = req_data.get("file_name") or ""
    base64_data = req_data.get("file_data") or ""

    if not base64_data:
        return None, file_name

    if not isinstance(base64_data, str):
        raise ValueError("file_data must be a base64 string.")

    base64_data = re.sub(r"\s+", "", base64_data)

    if base64_data.startswith("data:"):
        prefix, separator, base64_data = base64_data.partition(",")
        if not separator or "base64" not in prefix.casefold():
            raise ValueError("PDF data URI must contain base64 data.")

    try:
        pdf_bytes = base64.b64decode(base64_data, validate=True)
    except (ValueError, binascii.Error) as e:
        raise ValueError(f"Invalid base64 PDF data: {e}") from e

    return pdf_bytes, file_name


def build_final_so_output(parsed_data: SalesOrderData) -> dict:
    header_fields = (
        "sales_order_no",
        "sales_order_date",
        "customer_name",
        "customer_email",
        "customer_phone",
        "reference_no",
        "reference_date",
        "project_name",
        "payment_type",
        "delivery_date",
        "bu_group",
        "notes_content",
        "gst_treatment",
        "gstin",
        "shipping_gstin",
        "place_of_supply",
        "currency",
        "payment_terms",
        "responsible_person",
        "sales_order",
        "billing_address",
        "shipping_address",
    )

    output = {name: getattr(parsed_data, name) for name in header_fields}
    output["so_lines"] = [line.model_dump() for line in parsed_data.so_lines]
    return output


def handler(job_request, context):
    try:
        if request.method == "OPTIONS":
            return add_cors(make_response("", 204))

        if request.method != "POST":
            return add_cors(
                make_response(
                    jsonify(
                        {
                            "success": True,
                            "status": "OK",
                            "message": "Wootz Work SO Extractor API is running.",
                        }
                    )
                )
            )

        try:
            pdf_bytes, file_name = read_input_file(request)
        except (ValueError, TypeError) as e:
            return error_response(
                "Failed to decode base64 file data.", 400, details=str(e)
            )

        if not pdf_bytes:
            return error_response("Missing file upload or JSON payload.", 400)

        if file_name and not file_name.lower().endswith(".pdf"):
            return error_response("Please provide a PDF file.", 400)

        if len(pdf_bytes) > MAX_PDF_BYTES:
            return error_response("File size exceeds 10MB limit.", 400)

        logger.info("Processing PDF: %s", file_name or "uploaded-pdf")

        try:
            extracted_text = extract_text_from_pdf(pdf_bytes)
        except Exception as e:
            logger.exception("PDF extraction failed")
            return error_response(
                "Unable to extract text from PDF.", 400, details=str(e)
            )

        if not extracted_text.strip():
            return error_response("PDF contains no readable text.", 400)

        if len(extracted_text) > MAX_PDF_TEXT_CHARS:
            logger.info("PDF text truncated to %d characters.", MAX_PDF_TEXT_CHARS)
            extracted_text = extracted_text[:MAX_PDF_TEXT_CHARS]

        try:
            item_master = load_item_master()
            if not isinstance(item_master, list):
                raise RuntimeError("Item Master fetch returned an invalid record list.")
        except Exception as e:
            logger.exception("Item Master loading failed")
            return error_response(
                "Item Master fetch failed.",
                502,
                error_type=type(e).__name__,
                details=str(e),
            )

        try:
            item_master_context = build_item_master_context(
                records=item_master,
                document_text=extracted_text,
                max_candidates=25,
                max_context_chars=12000,
            )
        except Exception as e:
            logger.exception("Item Master context generation failed")
            return error_response(
                "Failed to prepare Item Master data.", 500, details=str(e)
            )

        try:
            parsed_data = extract_sales_order(
                extracted_text=extracted_text,
                item_master_context=item_master_context,
            )
        except Exception as e:
            logger.exception("OpenAI extraction failed")
            return error_response(
                "OpenAI processing failed.",
                500,
                error_type=type(e).__name__,
                details=str(e),
            )

        try:
            reconciliation_result = reconcile_so_items_with_item_master(
                so_lines=parsed_data.so_lines,
                item_master_records=item_master,
            )
        except Exception as e:
            logger.exception("Item Master reconciliation failed")
            return error_response(
                "Item Master reconciliation failed.",
                500,
                error_type=type(e).__name__,
                details=str(e),
            )

        if not isinstance(reconciliation_result, dict):
            raise RuntimeError("Item Master reconciliation returned an invalid response.")

        reconciliation = reconciliation_result.get("reconciliation", [])
        if not isinstance(reconciliation, list):
            raise RuntimeError("Item Master reconciliation returned invalid results.")

        request_data = request.get_json(silent=True) or {}
        if not isinstance(request_data, dict):
            request_data = {}

        sales_inbox_id = request_data.get("sales_inbox_id")
        if not sales_inbox_id:
            sales_inbox_id = request.form.get("sales_inbox_id")

        if not sales_inbox_id:
            return error_response(
                "Missing sales_inbox_id.",
                400,
                content_type=request.content_type,
                form_keys=list(request.form.keys()),
            )

        logger.info("Sales Inbox ID received: %s", sales_inbox_id)

        final_so_data = build_final_so_output(parsed_data)

        # ============================================================
        # CUSTOMER: FIND OR CREATE
        # ============================================================

        customer_name = final_so_data.get("customer_name", "").strip()

        customer_email = final_so_data.get("customer_email", "")
        customer_phone = final_so_data.get("customer_phone", "")

        if customer_name or customer_email or customer_phone:
            try:
                customer_id = get_or_create_customer(customer_name,
                                                     customer_email,
                                                     customer_phone)

                if customer_id:
                    final_so_data["customer_id"] = customer_id

                    logger.info(
                        "Customer found/created successfully. Name=%s, ID=%s",
                        customer_name,
                        customer_id,
                    )
                else:
                    logger.warning(
                        "Customer ID not returned for customer: %s",
                        customer_name,
                    )

            except Exception as e:
                logger.exception(
                    "Customer find/create failed for '%s': %s",
                    customer_name,
                    e,
                )
        else:
            logger.warning(
                "Customer name, phone, and email were not found in PDF."
            )

        # ============================================================
        # UPDATE SALES INBOX
        # ============================================================

        logger.info("Updating Sales Inbox ID: %s", sales_inbox_id)

        sales_inbox_result = process_sales_inbox_so(
            sales_inbox_id=str(sales_inbox_id).strip(),
            so_data=final_so_data,
            item_master_records=item_master,
            reconciliation_result=reconciliation_result,
        )
        if sales_inbox_result is None:
            raise RuntimeError(
                "process_sales_inbox_so() returned None. "
                "Check update_sales_inbox() return flow."
            )

        logger.info(
            "SALES INBOX UPDATE RESULT: %s",
            json.dumps(sales_inbox_result, ensure_ascii=True, default=str),
        )

        created_count = sum(
            1 for row in reconciliation if row.get("status") == "CREATED"
        )
        existing_count = sum(
            1 for row in reconciliation if row.get("status") == "EXISTS"
        )
        skipped_count = sum(
            1 for row in reconciliation if row.get("status") == "SKIPPED"
        )

        response_data = {
            "success": True,
            "pdf_file": file_name,
            "item_master_count": len(item_master),
            "item_master_reconciliation": {
                "total_so_lines": len(parsed_data.so_lines),
                "existing_items": existing_count,
                "created_items": created_count,
                "skipped_items": skipped_count,
                "details": reconciliation,
            },
            "so_data": build_final_so_output(parsed_data),
        }

        if "sales_inbox_result" in locals():
            response_data["sales_inbox_result"] = sales_inbox_result

        # return add_cors(make_response(jsonify(response_data)))

    except Exception as e:
        logger.exception("Processing error")
        # # return error_response(
        #     "Internal Processing Pipeline Failure",
        #     500,
        #     error_type=type(e).__name__,
        #     details=str(e),
        # )
