import os
import re
import requests

# Reuse the cached access token already created for Item Master.
from item_master import get_access_token


# ============================================================
# ZOHO CREATOR CONFIGURATION
# ============================================================

CREATOR_API_URL = os.getenv(
    "CREATOR_API_URL",
    "https://www.zohoapis.in"
).rstrip("/")

CREATOR_OWNER = os.getenv("CREATOR_OWNER")
CREATOR_APP = os.getenv("CREATOR_APP")

CREATOR_ENVIRONMENT = os.getenv(
    "CREATOR_ENVIRONMENT",
    "production"
)


# ============================================================
# CUSTOMER CONFIGURATION
# ============================================================

# Creator Form link name
CUSTOMER_FORM = os.getenv("CUSTOMER_FORM")

# Creator Report link name
CUSTOMER_REPORT = os.getenv("CUSTOMER_REPORT")

# Customer name field API name
CUSTOMER_NAME_FIELD = "Company_Name"

# Customer type field API name
CUSTOMER_TYPE_FIELD = "Contact_Type"

# Default customer type
CUSTOMER_TYPE_VALUE = "Customer"


# ============================================================
# VALIDATE CONFIGURATION
# ============================================================

def validate_config():
    required = {
        "CREATOR_OWNER": CREATOR_OWNER,
        "CREATOR_APP": CREATOR_APP,
        "CUSTOMER_FORM": CUSTOMER_FORM,
        "CUSTOMER_REPORT": CUSTOMER_REPORT,
    }

    missing = [
        key
        for key, value in required.items()
        if not value
    ]

    if missing:
        raise RuntimeError(
            "Missing required environment variables: "
            + ", ".join(missing)
        )


    # ============================================================
    # EXTRACT CREATOR RECORD ID
    # ============================================================

def _extract_record_id(record):
    """
    Extract Creator record ID from different response structures.
    """

    if record is None:
        return None

    # Direct primitive value
    if isinstance(record, (str, int, float)):
        value = str(record).strip()
        return value if value else None

    if isinstance(record, dict):

        # Most common Creator record ID keys
        for key in (
            "ID",
            "id",
            "Record_ID",
            "record_id",
            "recordId",
            "recordID",
        ):
            value = record.get(key)

            if value not in ("", None):
                if isinstance(value, dict):
                    nested = _extract_record_id(value)

                    if nested:
                        return nested

                else:
                    return str(value)

        # Common nested wrapper
        for key in (
            "data",
            "details",
            "response",
            "result",
            "record",
            "record_details",
        ):
            value = record.get(key)

            if value not in ("", None):
                found = _extract_record_id(value)

                if found:
                    return found

        # Last resort: recursively inspect all values
        for value in record.values():

            if isinstance(value, (dict, list)):
                found = _extract_record_id(value)

                if found:
                    return found

        return None

    if isinstance(record, list):

        for item in record:
            found = _extract_record_id(item)

            if found:
                return found

    return None


def normalize_phone(phone):
    """
    Convert PDF phone numbers into a Creator-compatible format.
    Keeps the leading + and digits only.
    """
    phone = str(phone or "").strip()

    if not phone:
        return ""

    # Keep only digits and leading +
    if phone.startswith("+"):
        return "+" + re.sub(r"\D", "", phone[1:])

    return re.sub(r"\D", "", phone)

# ============================================================
# FIND CUSTOMER
# ============================================================

def _is_no_records_response(response):
    """True when Creator reports 'No records found' (code 9280)."""
    try:
        body = response.json()
    except ValueError:
        return False

    return isinstance(body, dict) and body.get("code") == 9280


def find_customer(customer_name="", customer_phone="", customer_email=""):
    """
    Find an existing Customer in Zoho Creator.

    Search priority:
    1. Company_Name
    2. Phone
    3. Email

    Returns:
        Customer record ID if found.
        None if no matching customer exists.
    """

    validate_config()

    token_data = get_access_token()
    access_token = token_data.get("access_token")

    if not access_token:
        raise RuntimeError("Access token missing.")

    api_domain = token_data.get("api_domain") or CREATOR_API_URL

    url = (
        f"{api_domain.rstrip('/')}"
        f"/creator/v2.1/data/"
        f"{CREATOR_OWNER}/"
        f"{CREATOR_APP}/"
        f"report/"
        f"{CUSTOMER_REPORT}"
    )

    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Accept": "application/json",
    }

    if CREATOR_ENVIRONMENT != "production":
        headers["environment"] = CREATOR_ENVIRONMENT

    # ---------------------------------------------------------
    # Build search values
    # ---------------------------------------------------------

    customer_name = str(customer_name or "").strip()
    customer_phone = normalize_phone(customer_phone)
    customer_email = str(customer_email or "").strip()

    search_list = []

    if customer_name:
        search_list.append(
            (
                "Company_Name",
                customer_name,
                "Customer Name"
            )
        )

    if customer_phone:
        search_list.append(
            (
                "Phone",
                customer_phone,
                "Customer Phone"
            )
        )

    if customer_email:
        search_list.append(
            (
                "Email",
                customer_email,
                "Customer Email"
            )
        )

    if not search_list:
        print("No customer search value available.")
        return None

    # ---------------------------------------------------------
    # Search sequentially
    # ---------------------------------------------------------

    for field_name, field_value, search_label in search_list:

        escaped_value = (
            str(field_value)
            .replace("\\", "\\\\")
            .replace('"', '\\"')
        )

        criteria = f'({field_name} == "{escaped_value}")'

        print("==============================================")
        print("SEARCHING CUSTOMER")
        print("==============================================")
        print("Search Type:", search_label)
        print("Search Value:", field_value)
        print("Customer Search URL:", url)
        print("Customer Criteria:", criteria)

        try:
            response = requests.get(
                url,
                headers=headers,
                params={"criteria": criteria},
                timeout=60,
            )

        except requests.RequestException as e:
            raise RuntimeError(
                f"Customer search request failed using {search_label}: {e}"
            ) from e

        print("Customer Search Status:", response.status_code)
        print("Customer Search Response:", response.text)

        # -----------------------------------------------------
        # No record found
        # -----------------------------------------------------

        if response.status_code != 200:

            if _is_no_records_response(response):

                print(
                    f"No customer found using {search_label}: "
                    f"{field_value}"
                )

                continue

            raise RuntimeError(
                f"Customer search failed using {search_label}: "
                + response.text
            )

        # -----------------------------------------------------
        # Parse response
        # -----------------------------------------------------

        try:
            data = response.json()

        except ValueError as exc:
            raise RuntimeError(
                "Customer search returned invalid JSON: "
                + response.text
            ) from exc

        records = data.get("data", [])

        if not records:
            print(
                f"No customer found using {search_label}: "
                f"{field_value}"
            )
            continue

        # -----------------------------------------------------
        # Existing customer found
        # -----------------------------------------------------

        customer_record = records[0]

        print("==============================================")
        print("EXISTING CUSTOMER FOUND")
        print("==============================================")
        print("Matched Using:", search_label)
        print("Customer Record:", customer_record)

        customer_id = _extract_record_id(customer_record)

        if customer_id:

            print(
                f"Existing Customer ID: {customer_id}"
            )

            return customer_id

        print(
            "Customer record found, "
            "but Customer ID could not be extracted."
        )

    # ---------------------------------------------------------
    # Nothing found
    # ---------------------------------------------------------

    print("No existing customer found by name, phone, or email.")

    return None


    # ============================================================
    # CREATE CUSTOMER
    # ============================================================

def create_customer(customer_name,customer_email,customer_phone):
    customer_name = str(customer_name or "").strip()
    customer_email = str(customer_email or "").strip()
    customer_phone = normalize_phone(customer_phone)
    



    if not customer_name:
        return None

    validate_config()

    token_data = get_access_token()
    access_token = token_data.get("access_token")

    if not access_token:
        raise RuntimeError("Access token missing.")

    api_domain = token_data.get("api_domain") or CREATOR_API_URL

    url = (
        f"{api_domain.rstrip('/')}"
        f"/creator/v2.1/data/"
        f"{CREATOR_OWNER}/"
        f"{CREATOR_APP}/"
        f"form/"
        f"{CUSTOMER_FORM}"
    )

    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    if CREATOR_ENVIRONMENT != "production":
        headers["environment"] = CREATOR_ENVIRONMENT

    payload = {
        "data": {
            CUSTOMER_NAME_FIELD: customer_name,
            CUSTOMER_TYPE_FIELD: CUSTOMER_TYPE_VALUE,
            "Email": customer_email,
            "Phone": customer_phone,
            "From_PDF":True
        },
        "skip_workflow": ["all"],
    }

    print("==============================================")
    print("CREATING CUSTOMER")
    print("==============================================")
    print("Customer Name:", customer_name)
    print("Customer Create URL:", url)
    print("Customer Create Payload:", payload)

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=60,
    )

    print("Customer Create Status:", response.status_code)
    print("Customer Create Response:", response.text)

    if response.status_code not in (200, 201):
        raise RuntimeError(
            "Customer creation failed: "
            + response.text
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError(
            "Customer creation returned invalid JSON: "
            + response.text
        ) from exc

    print("Customer Create Parsed JSON:", data)

    # ---------------------------------------------------------
    # GET CREATED CUSTOMER ID
    # ---------------------------------------------------------

    customer_id = _extract_record_id(data)

    if customer_id:
        print(
            "Customer created successfully. "
            "Customer ID:",
            customer_id
        )
        return customer_id

    # Sometimes Creator puts the record inside data
    created_data = data.get("data")

    if isinstance(created_data, dict):
        customer_id = _extract_record_id(created_data)

        if customer_id:
            print(
                "Customer ID extracted from data:",
                customer_id
            )
            return customer_id

    print(
        "ERROR: Customer was created, "
        "but Customer ID was not found in response."
    )

    return None


def get_or_create_customer(customer_name, customer_email, customer_phone):
    """
    Find existing customer before creating a new one.

    Search priority:
    1. Company Name
    2. Phone
    3. Email
    4. Create new customer
    """

    customer_name = str(customer_name or "").strip()
    customer_email = str(customer_email or "").strip()
    customer_phone = normalize_phone(customer_phone)

    if not customer_name and not customer_phone and not customer_email:
        print(
            "No customer name, phone, or email available. "
            "Skipping customer processing."
        )
        return None

    print("==============================================")
    print("CUSTOMER PROCESSING")
    print("==============================================")
    print("Customer Name:", customer_name)
    print("Customer Phone:", customer_phone)
    print("Customer Email:", customer_email)

    # =========================================================
    # STEP 1: SEARCH EXISTING CUSTOMER
    # =========================================================

    print("Searching existing Customer...")

    customer_id = find_customer(
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer_email=customer_email
    )

    if customer_id:

        print(
            "=============================================="
        )
        print(
            "EXISTING CUSTOMER WILL BE USED"
        )
        print(
            f"Customer Name: {customer_name}"
        )
        print(
            f"Customer ID: {customer_id}"
        )
        print(
            "=============================================="
        )

        return customer_id

    # =========================================================
    # STEP 2: CUSTOMER DOES NOT EXIST
    # =========================================================

    print(
        f"Customer not found by name, phone, or email. "
        f"Creating new customer: {customer_name}"
    )

    customer_id = create_customer(
        customer_name,
        customer_email,
        customer_phone
    )

    # =========================================================
    # STEP 3: USE NEW CUSTOMER ID
    # =========================================================

    if customer_id:

        print(
            f"Customer created successfully: "
            f"{customer_name} -> {customer_id}"
        )

        return customer_id

    # =========================================================
    # STEP 4: CREATION FAILED
    # =========================================================

    raise RuntimeError(
        "Customer was not found and creation did not return "
        f"a Customer ID: {customer_name}"
    )