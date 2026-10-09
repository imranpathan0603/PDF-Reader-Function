import os
import json
import re

import time

import requests

# ============================================================

# ZOHO CONFIG

# ============================================================

ZOHO_ACCOUNTS_URL = os.getenv(

    "ZOHO_ACCOUNTS_URL",

    "https://accounts.zoho.in"

)

CREATOR_API_URL = os.getenv(

    "CREATOR_API_URL",

    "https://www.zohoapis.in"

).rstrip("/")

CREATOR_OWNER = os.getenv(

    "CREATOR_OWNER"

)

CREATOR_APP = os.getenv(

    "CREATOR_APP"

)

CREATOR_ITEM_REPORT = os.getenv(

    "CREATOR_ITEM_REPORT"

)

CREATOR_ENVIRONMENT = os.getenv(

    "CREATOR_ENVIRONMENT",

    "production"

)

# ============================================================

# OPTIONAL ACCESS TOKEN CACHE

# ============================================================

#

# Access tokens expire. We keep the generated token in memory

# while the Catalyst function container is alive.

#

# If the container restarts, a new access token is generated

# automatically from the refresh token.

#

_cached_access_token = None

_cached_access_token_expiry = 0

_cached_api_domain = None

# ============================================================

# GET ACCESS TOKEN

# ============================================================

def get_access_token():

    """

    Generate a fresh Zoho access token using the refresh token.

    Required environment variables:

        ZOHO_CLIENT_ID

        ZOHO_CLIENT_SECRET

        ZOHO_REFRESH_TOKEN

        """

    global _cached_access_token

    global _cached_access_token_expiry

    global _cached_api_domain

    # --------------------------------------------------------

    # Reuse cached token if still valid

    # --------------------------------------------------------

    current_time = time.time()

    if (

        _cached_access_token

        and current_time < (_cached_access_token_expiry - 60)

    ):

        return {

            "access_token": _cached_access_token,

            "api_domain": _cached_api_domain or CREATOR_API_URL

        }

    # --------------------------------------------------------

    # Read credentials

    # --------------------------------------------------------

    client_id = os.getenv(

        "ZOHO_CLIENT_ID"

    )

    client_secret = os.getenv(

        "ZOHO_CLIENT_SECRET"

    )

    refresh_token = os.getenv(

        "ZOHO_REFRESH_TOKEN"

    )

    if not client_id:

        raise RuntimeError(

            "Missing environment variable: ZOHO_CLIENT_ID"

        )

    if not client_secret:

        raise RuntimeError(

            "Missing environment variable: ZOHO_CLIENT_SECRET"

        )

    if not refresh_token:

        raise RuntimeError(

            "Missing environment variable: ZOHO_REFRESH_TOKEN"

        )

    # --------------------------------------------------------

    # Refresh token URL

    # --------------------------------------------------------

    token_url = (

        f"{ZOHO_ACCOUNTS_URL}/oauth/v2/token"

    )

    payload = {

        "refresh_token": refresh_token,

        "client_id": client_id,

        "client_secret": client_secret,

        "grant_type": "refresh_token"

    }

    # --------------------------------------------------------

    # Generate access token

    # --------------------------------------------------------

    try:

        response = requests.post(

            token_url,

            data=payload,

            timeout=30

        )

    except requests.RequestException as e:

        raise RuntimeError(

            f"Zoho OAuth request failed: {str(e)}"

        ) from e

    # --------------------------------------------------------

    # Validate response

    # --------------------------------------------------------

    if response.status_code != 200:

        raise RuntimeError(

            "Zoho OAuth failed. "

            f"HTTP {response.status_code}: "

            f"{response.text[:2000]}"

        )

    try:

        token_data = response.json()

    except ValueError:

        raise RuntimeError(

            "Zoho OAuth returned invalid JSON: "

            f"{response.text[:2000]}"

        )

    if not isinstance(token_data, dict):

        raise RuntimeError(

            "Zoho OAuth returned an invalid response structure."

        )

    # --------------------------------------------------------

    # Check OAuth error

    # --------------------------------------------------------

    if token_data.get("error"):

        raise RuntimeError(

            "Zoho OAuth error: "

            f"{token_data}"

        )

    access_token = token_data.get(

        "access_token"

    )

    if not access_token:

        raise RuntimeError(

            "Zoho OAuth did not return access_token. "

            f"Response: {token_data}"

        )

    # --------------------------------------------------------

    # Store token in memory

    # --------------------------------------------------------

    try:

        expires_in = int(token_data.get("expires_in", 3600))

    except (TypeError, ValueError) as e:

        raise RuntimeError(

            "Zoho OAuth returned an invalid expires_in value."

        ) from e

    if expires_in <= 0:

        raise RuntimeError(

            "Zoho OAuth returned a non-positive expires_in value."

        )

    api_domain = (

        token_data.get("api_domain")

        or CREATOR_API_URL

    )

    _cached_access_token = access_token

    _cached_access_token_expiry = (

        current_time + expires_in

    )

    _cached_api_domain = api_domain

    print(

        "Zoho access token generated successfully."

    )

    return {

        "access_token": access_token,

        "api_domain": api_domain

    }

# ============================================================

# FETCH ONE ITEM MASTER PAGE

# ============================================================

def fetch_item_master_page(

    access_token,

    api_domain,

    record_cursor=None,

    page_size=1000

):

    """Fetch one page from the Zoho Creator Item Master report."""

    if page_size <= 0:

        raise ValueError("page_size must be greater than 0.")

    if not CREATOR_OWNER or not CREATOR_APP or not CREATOR_ITEM_REPORT:

        raise RuntimeError(

            "CREATOR_OWNER, CREATOR_APP, and CREATOR_ITEM_REPORT must be configured."

        )



    api_base = (api_domain or CREATOR_API_URL).rstrip("/")

    url = (

        f"{api_base}/creator/v2.1/data/{CREATOR_OWNER}/"

        f"{CREATOR_APP}/report/{CREATOR_ITEM_REPORT}"

    )

    headers = {

        "Authorization": f"Zoho-oauthtoken {access_token}",

        "Accept": "application/json",

    }

    if CREATOR_ENVIRONMENT != "production":
        headers["environment"] = CREATOR_ENVIRONMENT
    if record_cursor:
        headers["record_cursor"] = record_cursor

    try:
        response = requests.get(
            url,
            headers=headers,
            params={"max_records": page_size, "field_config": "all"},
            timeout=30,
        )
    except requests.RequestException as e:
        raise RuntimeError(f"Creator API request failed: {e}") from e

    if response.status_code == 204:
        return [], None
    if response.status_code != 200:
        raise RuntimeError(
            f"Creator API returned HTTP {response.status_code}: "
            f"{response.text[:2000]}"
        )

    try:
        body = response.json()
    except ValueError as e:
        raise RuntimeError(
            f"Creator API returned invalid JSON: {response.text[:2000]}"
        ) from e
    if not isinstance(body, dict):
        raise RuntimeError("Creator API returned an invalid response structure.")
    if body.get("code") != 3000:
        raise RuntimeError(f"Creator API returned an error: {body}")

    records = body.get("data", [])
    if not isinstance(records, list) or any(
        not isinstance(record, dict) for record in records
    ):
        raise RuntimeError(
            "Creator API returned invalid 'data' structure; expected a list of records."
        )

    return records, response.headers.get("record_cursor")





        # ============================================================

        # FETCH ALL ITEM MASTER RECORDS

        # ============================================================

def fetch_item_master(

    max_pages=50,

    page_size=1000

):

    """Fetch all Item Master records, following Creator record cursors."""

    if not CREATOR_OWNER:

        raise RuntimeError(

            "Missing environment variable: CREATOR_OWNER"

        )

    if not CREATOR_APP:

        raise RuntimeError(

            "Missing environment variable: CREATOR_APP"

        )

    if not CREATOR_ITEM_REPORT:

        raise RuntimeError(

            "Missing environment variable: "

            "CREATOR_ITEM_REPORT"

        )

    if max_pages <= 0:

        raise ValueError("max_pages must be greater than 0.")

    if page_size <= 0:

        raise ValueError("page_size must be greater than 0.")



    token_data = get_access_token()

    access_token = token_data["access_token"]

    api_domain = token_data.get("api_domain")



    all_records = []

    record_cursor = None

    seen_cursors = set()



    for page_number in range(1, max_pages + 1):

        records, next_cursor = fetch_item_master_page(

            access_token=access_token,

            api_domain=api_domain,

            record_cursor=record_cursor,

            page_size=page_size,

        )

        print(f"Item Master page {page_number}: {len(records)} records")

        all_records.extend(records)



        if next_cursor is None or str(next_cursor).casefold() in ("", "null", "none"):
            break

        next_cursor = str(next_cursor)

        if next_cursor in seen_cursors or next_cursor == record_cursor:

            raise RuntimeError(

                "Creator API repeated a record cursor; pagination cannot continue."

            )

        seen_cursors.add(next_cursor)

        record_cursor = next_cursor

    else:

        raise RuntimeError(

            f"Creator API pagination exceeded the configured limit of {max_pages} pages."

        )



    print(f"TOTAL ITEM MASTER RECORDS: {len(all_records)}")

    return all_records


# ============================================================
# ITEM MASTER CREATE / COMPARE HELPERS
# ============================================================

CREATOR_ITEM_FORM = os.getenv("CREATOR_ITEM_FORM", "")

ITEM_MASTER_CODE_FIELD = os.getenv(
    "ITEM_MASTER_CODE_FIELD",
    "Item_Code",
)
ITEM_MASTER_NAME_FIELD = os.getenv(
    "ITEM_MASTER_NAME_FIELD",
    "Item_Name",
)
ITEM_MASTER_SKU_FIELD = os.getenv(
    "ITEM_MASTER_SKU_FIELD",
    "SKU",
)

ITEM_MASTER_ITEM_TYPE_FIELD = os.getenv(
    "ITEM_MASTER_ITEM_TYPE_FIELD",
    "Item_Type",
)
ITEM_MASTER_DESCRIPTION_FIELD = os.getenv(
    "ITEM_MASTER_DESCRIPTION_FIELD",
    "Description",
)
ITEM_MASTER_HSN_FIELD = os.getenv(
    "ITEM_MASTER_HSN_FIELD",
    "HSN_SAC",
)
ITEM_MASTER_UOM_FIELD = os.getenv(
    "ITEM_MASTER_UOM_FIELD",
    "UOM",
)
ITEM_MASTER_RATE_FIELD = os.getenv(
    "ITEM_MASTER_RATE_FIELD",
    "Rate",
)


def _creator_value_to_text(value) -> str:
    """Convert Creator values, including lookup/list/dict values, to text."""
    if value is None:
        return ""

    if isinstance(value, (str, int, float, bool)):
        return str(value)

    if isinstance(value, dict):
        for key in (
            "display_value",
            "value",
            "zc_display_value",
            "name",
            "id",
            "ID",
        ):
            if key in value:
                text = _creator_value_to_text(value.get(key)).strip()
                if text:
                    return text
        return " ".join(
            text
            for child in value.values()
            if (text := _creator_value_to_text(child).strip())
        )

    if isinstance(value, (list, tuple)):
        return " ".join(
            text
            for child in value
            if (text := _creator_value_to_text(child).strip())
        )

    return str(value)


def normalize_item_value(value):
    """Normalize an item code/name for reliable comparison."""
    text = _creator_value_to_text(value).strip().casefold()
    return re.sub(r"[^a-z0-9]+", "", text)


def _get_record_field_value(record, field_names):
    """Get the first non-empty value from a Creator record."""
    if not isinstance(record, dict):
        return ""

    for field_name in field_names:
        if field_name not in record:
            continue

        value = _creator_value_to_text(record.get(field_name)).strip()

        if value:
            return value

    return ""


def get_item_master_code(record):
    """Extract Item Code / Part Number / SKU / Item ID."""
    return _get_record_field_value(
        record,
        [
            ITEM_MASTER_CODE_FIELD,
            "Item_Code",
            "Item Code",
            "Part_Number",
            "Part Number",
            "Part_No",
            "Part No",
            "SKU",
            "Sku",
            "Item_ID",
            "Item ID",
            "ItemId",
            "item_code",
            "part_number",
            "sku",
            "item_id",
        ],
    )


def get_item_master_name(record):
    """Extract Item Name."""
    return _get_record_field_value(
        record,
        [
            ITEM_MASTER_NAME_FIELD,
            "Item_Name",
            "Item Name",
            "Name",
            "item_name",
            "name",
        ],
    )


def find_item_master_match(
    item_code,
    item_name,
    item_master_records,
    item_type="item",
    sku="00"
):
    """
    Compare an SO line with Item Master.

    Priority:
        1. Item Code / Part Number / SKU
        2. Item Name
        """
    normalized_code = normalize_item_value(item_code)
    normalized_name = normalize_item_value(item_name)

    for record in item_master_records:
        if normalized_code:
            existing_code = get_item_master_code(record)
            if existing_code and normalize_item_value(existing_code) == normalized_code:
                return record

        if normalized_name:
            existing_name = get_item_master_name(record)
            if existing_name and normalize_item_value(existing_name) == normalized_name:
                return record

    return None


def _extract_created_record(body):
    """Normalize common Creator Add Record response structures."""
    if not isinstance(body, dict):
        return {}

    data = body.get("data")
    if isinstance(data, dict):
        return data
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]

    result = body.get("result")

    if isinstance(result, dict):
        return result

    if isinstance(result, list) and result:
        first = result[0]
        if isinstance(first, dict):
            nested = first.get("data")
            if isinstance(nested, dict):
                return nested
            return first
    return {}


def create_item_master_record(item_data):
    """
    Create a missing Item Master record in Zoho Creator.

    Only PDF-extracted SO-line data is used.
    Creator form workflows/schedules are skipped with
    skip_workflow=["all"].
    """
    if not isinstance(item_data, dict):
        raise ValueError("item_data must be a dictionary.")

    if not CREATOR_OWNER:
        raise RuntimeError("Missing environment variable: CREATOR_OWNER")

    if not CREATOR_APP:
        raise RuntimeError("Missing environment variable: CREATOR_APP")

    if not CREATOR_ITEM_FORM:
        raise RuntimeError(
            "Missing environment variable: CREATOR_ITEM_FORM"
        )

    item_code = str(item_data.get("item_code") or "").strip()
    item_name = str(item_data.get("item_name") or "").strip()
    description = str(item_data.get("description") or "").strip()
    hsn_sac = str(item_data.get("hsn_sac") or "").strip()
    uom = str(item_data.get("uom") or "").strip()
    rate = item_data.get("rate", 0)

    if not item_code and not item_name:
        raise ValueError(
            "Cannot create Item Master record because both "
            "item_code and item_name are empty."
        )

    token_data = get_access_token()
    access_token = token_data["access_token"]
    api_domain = token_data.get("api_domain") or CREATOR_API_URL
    api_base = api_domain.rstrip("/")

    url = (
        f"{api_base}/creator/v2.1/data/"
        f"{CREATOR_OWNER}/{CREATOR_APP}/form/"
        f"{CREATOR_ITEM_FORM}"
    )

    record = {}
    if item_code:
        record[ITEM_MASTER_CODE_FIELD] = item_code
    record[ITEM_MASTER_ITEM_TYPE_FIELD] = "Goods"
    if item_code:
        record[ITEM_MASTER_SKU_FIELD] = item_code
    if item_name:
        record[ITEM_MASTER_NAME_FIELD] = item_name
    if description:
        record[ITEM_MASTER_DESCRIPTION_FIELD] = description
    if hsn_sac:
        record[ITEM_MASTER_HSN_FIELD] = hsn_sac
    if uom:
        record[ITEM_MASTER_UOM_FIELD] = uom
    if rate not in ("", None):
        record[ITEM_MASTER_RATE_FIELD] = rate
    record['From_PDF'] = True

    payload = {
        "data": record,
        "skip_workflow": ["all"],
    }
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if CREATOR_ENVIRONMENT != "production":
        headers["environment"] = CREATOR_ENVIRONMENT

    print(
        "Creating missing Item Master:",
        json.dumps(record, ensure_ascii=True, default=str),
    )
    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30,
        )
    except requests.RequestException as e:
        raise RuntimeError(
            f"Creator Item Master create request failed: {e}"
        ) from e

    if response.status_code not in (200, 201):
        raise RuntimeError(
            "Creator Item Master create failed. "
            f"HTTP {response.status_code}: {response.text[:3000]}"
        )

    try:
        body = response.json()
    except ValueError as e:
        raise RuntimeError(
            "Creator Item Master create returned invalid JSON: "
            f"{response.text[:3000]}"
        ) from e

    if not isinstance(body, dict):
        raise RuntimeError(
            "Creator Item Master create returned an invalid response."
        )
    if body.get("code") not in (None, 3000):
        raise RuntimeError(f"Creator Item Master creation failed: {body}")

    created_record = _extract_created_record(body)
    print(
        "Item Master created successfully:",
        json.dumps(body, ensure_ascii=True, default=str),
    )
    return {
        "response": body,
        "record": created_record,
    }

def reconcile_so_items_with_item_master(
    so_lines,
    item_master_records,
):
    """
    Compare every extracted SO line with Item Master.

    Existing item -> no creation.
    Missing item -> create using available PDF data.
    Missing code -> compare by Item Name.
    Missing code + name -> skip.

    Newly created items are added to the local cache to prevent
    duplicate creation within the same PDF.
    """

    if not isinstance(so_lines, list):
        raise ValueError("so_lines must be a list.")

    if not isinstance(item_master_records, list):
        raise ValueError("item_master_records must be a list.")

    reconciliation = []

    for index, line in enumerate(so_lines, start=1):

        # --------------------------------------------------------
        # Convert Pydantic model / dictionary to dictionary
        # --------------------------------------------------------
        if hasattr(line, "model_dump"):
            line_data = line.model_dump()

        elif isinstance(line, dict):
            line_data = dict(line)

        else:
            print(f"Skipping invalid SO line {index}")

            reconciliation.append({
                "line_number": index,
                "status": "SKIPPED",
                "reason": "Invalid SO line structure.",
            })

            continue

        # --------------------------------------------------------
        # Extract Item Code and Item Name
        # --------------------------------------------------------
        item_code = str(
            line_data.get("item_code") or ""
        ).strip()

        item_name = str(
            line_data.get("item_name") or ""
        ).strip()

        # --------------------------------------------------------
        # Compare with existing Item Master
        # --------------------------------------------------------
        existing_record = find_item_master_match(
            item_code=item_code,
            item_name=item_name,
            item_master_records=item_master_records,
            item_type="item",
            sku=item_code
            
        )

        # --------------------------------------------------------
        # ITEM EXISTS
        # --------------------------------------------------------
        if existing_record:

            reconciliation.append({
                "line_number": index,
                "status": "EXISTS",
                "item_code": item_code,
                "item_name": item_name,
                "item_master": existing_record,
            })

            print(
                f"SO line {index}: Item Master exists. "
                f"Code={item_code}, Name={item_name}"
            )

            continue

        # --------------------------------------------------------
        # NO CODE + NO NAME
        # --------------------------------------------------------
        if not item_code and not item_name:

            reconciliation.append({
                "line_number": index,
                "status": "SKIPPED",
                "reason": (
                    "No item_code and no item_name were "
                    "extracted from PDF."
                ),
                "item_code": "",
                "item_name": "",
            })

            print(
                f"SO line {index}: skipped because "
                "item_code and item_name are both empty."
            )

            continue

        # --------------------------------------------------------
        # ITEM DOES NOT EXIST
        # CREATE NEW ITEM MASTER
        # --------------------------------------------------------
        print(
            f"SO line {index}: Item Master not found. "
            f"Creating Code={item_code}, Name={item_name}"
        )

        created_result = create_item_master_record(
            line_data
        )

        if not isinstance(created_result, dict):
            raise RuntimeError(
                "create_item_master_record returned "
                "an invalid response."
            )

        created_record = created_result.get(
            "record",
            {}
        )

        # --------------------------------------------------------
        # Build local Item Master record
        # --------------------------------------------------------
        local_created_record = dict(
            created_record
            if isinstance(created_record, dict)
            else {}
        )

        # Item Code
        if item_code:
            local_created_record[
                ITEM_MASTER_CODE_FIELD
            ] = item_code

        # Item Name 
        if item_name:
            local_created_record[
                ITEM_MASTER_NAME_FIELD
            ] = item_name

        # Description
        description = str(
            line_data.get("description") or ""
        ).strip()

        if description:
            local_created_record[
                ITEM_MASTER_DESCRIPTION_FIELD
            ] = description

        # HSN/SAC
        hsn_sac = str(
            line_data.get("hsn_sac") or ""
        ).strip()

        if hsn_sac:
            local_created_record[
                ITEM_MASTER_HSN_FIELD
            ] = hsn_sac

        # UOM
        uom = str(
            line_data.get("uom") or ""
        ).strip()

        if uom:
            local_created_record[
                ITEM_MASTER_UOM_FIELD
            ] = uom

        # Rate
        rate = line_data.get("rate")

        if rate not in ("", None):
            local_created_record[
                ITEM_MASTER_RATE_FIELD
            ] = rate

        # --------------------------------------------------------
        # Add newly created record to local cache
        # --------------------------------------------------------
        item_master_records.append(
            local_created_record
        )

        # --------------------------------------------------------
        # Add CREATED result
        # --------------------------------------------------------
        reconciliation.append({
            "line_number": index,
            "status": "CREATED",
            "item_code": item_code,
            "item_name": item_name,
            "item_master": local_created_record,
        })

        print(
            f"SO line {index}: Item Master created successfully. "
            f"Code={item_code}, Name={item_name}"
        )

    # ============================================================
    # Return ONLY AFTER ALL SO LINES are processed
    # ============================================================
    return {
        "so_lines": so_lines,
        "reconciliation": reconciliation,
        "item_master_records": item_master_records,
    }