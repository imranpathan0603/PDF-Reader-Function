# Zoho Catalyst Deployment Guide

This project is a Zoho Catalyst Advanced I/O function that accepts a quotation PDF, extracts structured quotation data with OpenAI Vision, and returns the parsed JSON response.

## Project Overview

The deployed function is located in:
- [functions/alliance_product_ai_function/main.py](functions/alliance_product_ai_function/main.py)

It performs the following steps:
1. Accepts a PDF upload through a multipart form request.
2. Saves the uploaded file locally in the function's uploads folder.
3. Converts the PDF pages into images.
4. Sends the images to OpenAI GPT-4o Vision for extraction.
5. Returns structured quotation data as JSON and saves a copy to the output folder.

## Repository Structure

- [catalyst.json](catalyst.json) - Root Catalyst project configuration
- [functions/alliance_product_ai_function/main.py](functions/alliance_product_ai_function/main.py) - Main handler logic
- [functions/alliance_product_ai_function/catalyst-config.json](functions/alliance_product_ai_function/catalyst-config.json) - Function deployment configuration
- [functions/alliance_product_ai_function/requirements.txt](functions/alliance_product_ai_function/requirements.txt) - Python dependencies
- [functions/alliance_product_ai_function/pyproject.toml](functions/alliance_product_ai_function/pyproject.toml) - Optional Python project metadata

## Prerequisites

Before deploying, make sure you have:
- A Zoho Catalyst account
- Zoho Catalyst CLI installed and logged in
- Python 3.12+
- An OpenAI API key with access to GPT-4o

## Environment Variables

Set the following values in the Catalyst function configuration:

- OPENAI_API_KEY: Your OpenAI API key
- CREATOR_OWNER, CREATOR_APP, and CREATOR_ITEM_REPORT: the Creator account, app, and report used by the Item Master lookup
- CREATOR_API_URL (optional): the regional Creator API base URL; defaults to `https://www.zohoapis.in`

Do not store API keys in `catalyst.json` or other checked-in files.

The function also requires a Catalyst connection named `zoho_creator_connection`, configured with access to the Creator app/report. The function uses the Catalyst SDK to retrieve that connection's OAuth token; do not place Creator tokens in environment variables or source files.

## Local Setup

From the project root, install dependencies:

```bash
cd functions/alliance_product_ai_function
pip install -r requirements.txt
```

If you want to test locally, make sure the function can access your OpenAI key in the environment before running it through the Catalyst runtime or local test flow.

## Deployment to Zoho Catalyst

1. Open the project root where [catalyst.json](catalyst.json) is located.
2. Log in to Zoho Catalyst CLI:

```bash
catalyst login
```

3. Deploy the project:

```bash
catalyst deploy
```

4. After deployment, open the Catalyst console and note the deployed function URL for the function named `alliance_product_ai_function`.

## API Usage

The deployed function expects a POST request with a file field named `file`.

### Example using curl

```bash
curl -X POST "<YOUR_FUNCTION_URL>" \
  -F "file=@quotation.pdf"
```

### Request format

- Method: POST
- Content-Type: multipart/form-data
- Field name: `file`
- File type: PDF only

### Example response

```json
{
  "success": true,
  "pdf_file": "quotation.pdf",
  "saved_pdf_path": "quotation_20260721_123456.pdf",
  "total_pages": 3,
  "output_json_file": "quotation_20260721_123456.json",
  "quotation_data": {
    "quotation_number": "Q-1001",
    "company_name": "ABC Supplies",
    "items": []
  }
}
```

## Notes

- Only PDF files are accepted.
- The function saves uploaded files into the uploads folder and generated JSON output into the output folder.
- The extraction quality depends on the clarity of the uploaded quotation PDF and the OpenAI API response quality.
- If deployment fails, verify that the OpenAI API key is configured correctly in the Catalyst environment settings.

## Troubleshooting

If the deployment or execution fails, check the following:
- The `OPENAI_API_KEY` environment variable is set correctly.
- The function is deployed with the correct Python stack (`python_3_12`).
- The uploaded file is a valid PDF.
- The function URL is being called with the `file` field in multipart form data.
