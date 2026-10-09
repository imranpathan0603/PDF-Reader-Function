# Zoho Catalyst Asynchronous PDF Processing

> **Project:** Project-Rainfall  
> **Implementation period:** 8–9 October 2026  
> **Purpose:** Process PDF attachments associated with Zoho Creator Sales Inbox records asynchronously using Zoho Catalyst Job Functions.

## Table of Contents

1. [Overview](#1-overview)
2. [Problem and Solution](#2-problem-and-solution)
3. [Architecture](#3-architecture)
4. [Project Configuration](#4-project-configuration)
5. [Functions and Responsibilities](#5-functions-and-responsibilities)
6. [End-to-End Execution Flow](#6-end-to-end-execution-flow)
7. [Job Parameters and Naming](#7-job-parameters-and-naming)
8. [File Store](#8-file-store)
9. [Python Processor Workflow](#9-python-processor-workflow)
10. [Environment Variables and Secrets](#10-environment-variables-and-secrets)
11. [Dependencies](#11-dependencies)
12. [Local Development and Validation](#12-local-development-and-validation)
13. [Deployment](#13-deployment)
14. [Testing the Flow](#14-testing-the-flow)
15. [Monitoring Jobs and Logs](#15-monitoring-jobs-and-logs)
16. [Issues Encountered and Resolutions](#16-issues-encountered-and-resolutions)
17. [Troubleshooting Guide](#17-troubleshooting-guide)
18. [Retries, Concurrency, and Reliability](#18-retries-concurrency-and-reliability)
19. [Security and Operations](#19-security-and-operations)
20. [Production Readiness Checklist](#20-production-readiness-checklist)
21. [Known Follow-up Items](#21-known-follow-up-items)
22. [Quick Reference](#22-quick-reference)

## 1. Overview

This project moves a long-running PDF processing workflow out of a single synchronous HTTP request and into an asynchronous, multi-stage Zoho Catalyst workflow.

The HTTP entry point accepts the PDF and Sales Inbox record ID, stores the file in Catalyst File Store, schedules a Node.js Worker job, and returns an acceptance response. The Worker verifies that the PDF can be downloaded and schedules a Python Processor job. The Python Processor executes the existing business logic.

**Important:** An HTTP `200` response with `"status": "accepted"` means that the request was accepted and the job was queued. It does **not** mean that all PDF processing and Sales Inbox updates have completed. The final Processor job status must be checked separately.

## 2. Problem and Solution

### Original challenge

The original flow performed multiple potentially long-running operations inside one HTTP request:

- Downloading and extracting PDF content.
- Fetching Item Master records from Zoho Creator.
- Extracting structured information with OpenAI.
- Reconciling extracted lines with Item Master records.
- Getting or creating customer information.
- Updating the Sales Inbox record and its lines.

Keeping all operations inside one request creates timeout and reliability risks.

### Solution

Separate request acceptance and background processing into three functions:

1. **Trigger:** accepts the HTTP request, uploads the PDF, and submits a Worker job.
2. **Worker:** downloads/verifies the file and submits the Processor job.
3. **Processor:** runs the Python business logic and records final success or failure through the Catalyst Job Function context.

This design reduces the amount of work performed during the original HTTP request and makes each stage independently observable.

## 3. Architecture

```text
Zoho Creator
    |
    | PDF + Sales Inbox ID
    v
Node.js Advanced I/O
alliance_product_ai_trigger
    |
    | Upload PDF
    v
Catalyst File Store
Folder: 64647000000032024
    |
    | Submit Worker job
    v
Node.js Job Function
alliance_product_ai_worker
    |
    | Download and verify PDF
    | Submit Processor job
    v
Python 3.12 Job Function
alliance_product_ai_processor
    |
    +--> Download PDF from File Store
    +--> Extract PDF (PyMuPDF)
    +--> Load Item Master (Zoho Creator)
    +--> OpenAI structured extraction
    +--> Reconcile items with Item Master
    +--> Get/Create customer
    +--> Update Sales Inbox in Zoho Creator
    +--> Close job with success/failure
```

### Responsibilities by stage

| Stage | Function/service | Responsibility |
|---|---|---|
| 1 | Zoho Creator | Sends PDF and Sales Inbox ID |
| 2 | `alliance_product_ai_trigger` | Parses request, uploads PDF, submits Worker job, responds accepted |
| 3 | Catalyst File Store | Stores PDF and provides a `file_id` |
| 4 | `alliance_product_ai_worker` | Downloads/verifies PDF and submits Processor job |
| 5 | `alliance_product_ai_processor` | Executes the PDF/AI/Creator business workflow |
| 6 | Zoho Creator | Receives Item Master reads and Sales Inbox/customer updates |

## 4. Project Configuration

The following values were used during development.

| Setting | Value |
|---|---|
| Catalyst project | `Project-Rainfall` |
| Project ID | `64647000000013024` |
| Development URL | `https://project-rainfall-60086308503.development.catalystserverless.in` |
| File Store folder ID | `64647000000032024` |
| Job Pool name | `allianceproductaipool` |
| Job Pool ID | `64647000000032018` |
| Python runtime | `python_3_12` |
| Node runtime | Node.js 20 |

Treat project IDs, folder IDs, pool names, and URLs as environment-specific configuration. Confirm them in the target Catalyst environment before deployment.

## 5. Functions and Responsibilities

### 5.1 `alliance_product_ai_trigger`

**Type:** Node.js Advanced I/O function.

Responsibilities:

1. Receive the PDF and Sales Inbox ID.
2. Parse the multipart request.
3. Validate required input.
4. Write the upload to a temporary file when required by the implementation.
5. Upload the PDF to Catalyst File Store.
6. Capture the resulting `file_id`.
7. Submit a job targeting `alliance_product_ai_worker`.
8. Return an accepted response to the caller.

The Trigger should not run the full PDF extraction, OpenAI, reconciliation, customer, and Sales Inbox update flow.

Example response:

```json
{
  "success": true,
  "status": "accepted",
  "message": "Sales Inbox processing job submitted.",
  "sales_inbox_id": "444935000000185047",
  "file_id": "64647000000035017",
  "file_name": "1791178318400_PO132474-WOOTZWORK.pdf",
  "job_name": "APAI_1791525647257"
}
```

IDs above are examples from development runs; a new run should return its own identifiers.

### 5.2 `alliance_product_ai_worker`

**Type:** Node.js Job Function.

Responsibilities:

1. Read `sales_inbox_id` and `file_id` from the job request.
2. Initialize the Catalyst Node.js SDK.
3. Open the configured File Store folder.
4. Download the PDF and confirm it is not empty.
5. Log the downloaded byte count.
6. Submit a new job targeting `alliance_product_ai_processor`.
7. Mark the Worker job successful after the Processor job has been submitted.

The Worker is an orchestration/verification layer. It does not perform the Python business processing.

Representative log:

```text
PDF downloaded successfully. Size: 223671 bytes
```

A successful Worker job confirms that the Worker completed its own work and submitted the Processor job. It does not mean the Processor has succeeded.

### 5.3 `alliance_product_ai_processor`

**Type:** Python 3.12 Job Function.

Directory:

```text
functions/alliance_product_ai_processor/
```

Files:

```text
main.py
item_master.py
customer_service.py
sales_inbox_updater.py
requirements.txt
catalyst-config.json
```

Responsibilities:

1. Read `sales_inbox_id` and `file_id`.
2. Initialize the Catalyst Python SDK.
3. Download the PDF from File Store.
4. Extract PDF content using PyMuPDF.
5. Fetch Item Master data from Zoho Creator.
6. Use OpenAI for structured extraction.
7. Reconcile extracted lines against Item Master records.
8. Get or create customer data as required.
9. Update the Sales Inbox record and its line items.
10. Close the job with success or failure.

The existing Python business logic remains in this function; the architecture change is primarily the asynchronous orchestration around it.

## 6. End-to-End Execution Flow

1. A user or workflow in Zoho Creator initiates processing for a Sales Inbox PDF.
2. Creator sends the PDF and Sales Inbox ID to the Trigger endpoint.
3. The Trigger validates the request and uploads the PDF to Catalyst File Store.
4. The Trigger submits `alliance_product_ai_worker` with the Sales Inbox ID and File Store file ID.
5. The Trigger returns an accepted response without waiting for the complete processing flow.
6. The Worker starts and downloads the PDF to verify file access.
7. The Worker submits `alliance_product_ai_processor` with the same Sales Inbox ID and File Store file ID.
8. The Worker closes successfully.
9. The Python Processor starts independently.
10. The Processor downloads and extracts the PDF.
11. It loads Item Master data and processes the PDF with OpenAI.
12. It reconciles the extracted items, processes customer data, and updates Sales Inbox data.
13. The Processor marks the job successful if all required steps finish, or failed if an unhandled error occurs.

### Job relationship

```text
HTTP request
   |
   v
Trigger returns "accepted"
   |
   v
Worker job (APAI_...)
   |
   v
Processor job (AP_...)
   |
   v
Final processing status
```

The two job names are separate. Always inspect the job whose target is `alliance_product_ai_processor` to determine the result of the business processing.

## 7. Job Parameters and Naming

### Worker parameters

The Trigger sends the Worker parameters, including:

- `sales_inbox_id`
- `file_id`
- `file_name` (the Trigger may send it for traceability)

### Processor parameters

The Worker submits the Processor using the required parameters:

```json
{
  "sales_inbox_id": "444935000000185047",
  "file_id": "64647000000035017"
}
```

The Processor was changed not to require `file_name`, because the Worker submission sends only `sales_inbox_id` and `file_id`. A job handler must not call `get_job_param("file_name")` if that parameter is not sent; depending on the SDK, accessing a missing key can raise an exception.

### Job naming

Observed conventions:

- Trigger-to-Worker jobs: `APAI_<timestamp>`
- Worker-to-Processor jobs: `AP_<timestamp>`

Use unique job names and comply with Catalyst's currently applicable naming restrictions.

### Retry settings used

```text
number_of_retries = 2
retry_interval = 900 seconds (15 minutes)
```

Confirm the supported limits and retry semantics for the deployed Catalyst plan/runtime before relying on them for production recovery.

## 8. File Store

The PDF is stored in Catalyst File Store before background processing starts.

```text
Folder ID: 64647000000032024
```

A typical flow is:

```text
Creator PDF
    |
    v
Trigger uploads PDF
    |
    v
File Store returns file_id
    |
    v
Worker downloads/verifies PDF
    |
    v
Processor downloads PDF for extraction
```

Example development file ID:

```text
64647000000035017
```

File IDs are generated by File Store and must not be hard-coded as constants. Use the ID returned by the current upload.

The Worker and Processor each download the file for different reasons: the Worker verifies availability, while the Processor needs the bytes for actual extraction.

## 9. Python Processor Workflow

The Processor's business stages are:

### 9.1 Download PDF

- Initialize the Python Catalyst SDK.
- Get the File Store service and configured folder.
- Call the SDK's file download method.
- Validate that the returned bytes are not `None` and not empty.
- Log the file size, but do not log the document contents or sensitive data.

### 9.2 Extract PDF

Use the existing PyMuPDF (`fitz`) logic in `main.py` to extract text/content from the downloaded PDF.

### 9.3 Load Item Master

`item_master.py` fetches Item Master records from Zoho Creator. This step requires its configured Creator/OAuth settings.

### 9.4 OpenAI extraction

The Processor uses OpenAI to extract structured data from the PDF. The API key must be configured securely in the Catalyst environment.

### 9.5 Reconcile items

The extracted lines are reconciled with Item Master records using the existing business logic. The exact matching rules are defined in the current Python implementation.

### 9.6 Customer processing

The existing customer service logic gets or creates the customer as required by the extracted order data.

### 9.7 Update Sales Inbox

`sales_inbox_updater.py` performs the Creator update. The existing implementation should validate Creator API responses and report failed updates clearly.

### 9.8 Close the Job Function

Use the supported Job Function context methods in the existing handler to mark final success or failure. Do not treat job submission as equivalent to successful processing.

## 10. Environment Variables and Secrets

The Processor configuration includes these Creator settings:

```text
CREATOR_OWNER=isha.sharma_wootz
CREATOR_APP=wootz-work-erp
CREATOR_ITEM_REPORT=All_Item_Masters
CREATOR_API_URL=https://www.zohoapis.in
```

The Item Master code was later found to require:

```text
ZOHO_CLIENT_ID
ZOHO_CLIENT_SECRET
ZOHO_REFRESH_TOKEN
```

The missing `ZOHO_CLIENT_ID` was the actual error that stopped Item Master loading after PDF download succeeded.

The Processor also requires the OpenAI key if the existing implementation reads it from the environment:

```text
OPENAI_API_KEY
```

### Security requirements

- Set secrets in Catalyst environment configuration.
- Never commit client secrets, refresh tokens, or API keys to Git.
- Never paste secret values into support tickets, logs, README files, or chat.
- Restrict access to environment configuration.
- If a secret is exposed, rotate it.

### Processor `catalyst-config.json`

The configuration used during development was similar to:

```json
{
  "deployment": {
    "name": "alliance_product_ai_processor",
    "stack": "python_3_12",
    "type": "job",
    "env_variables": {
      "CREATOR_OWNER": "isha.sharma_wootz",
      "CREATOR_APP": "wootz-work-erp",
      "CREATOR_ITEM_REPORT": "All_Item_Masters",
      "CREATOR_API_URL": "https://www.zohoapis.in"
    }
  },
  "execution": {
    "main": "main.py"
  }
}
```

This is a representative configuration. Confirm how your current Catalyst CLI/deployment setup supplies environment variables. Do not assume that setting a value in a local config automatically means a secret is securely configured in every target environment.

## 11. Dependencies

### Python `requirements.txt`

The development dependency list was:

```text
openai>=1.0.0
zcatalyst-sdk>=1.4.0
requests
python-dotenv
PyMuPDF>=1.23.0
Pillow>=10.0.0
Flask>=3.0.0
```

Check the actual imports before removing dependencies. Flask was retained from the existing implementation even though the function is now a Job Function.

### Node Worker dependencies

The Worker uses `zcatalyst-sdk-node` and the dependencies required by the deployed implementation. Confirm that `zcatalyst-sdk-node` is explicitly listed in the Worker `package.json`, with the intended version, rather than relying on a transitive dependency.

## 12. Local Development and Validation

Run commands from the Catalyst project root:

```text
C:\Users\ThinkBook\Desktop\Internal Project Widget\zoho catalyst\zoho catalyst
```

### Validate Python syntax

```powershell
python -m py_compile .\functions\alliance_product_ai_processor\main.py
```

No output means syntax compilation succeeded. It does not validate runtime SDK calls, environment variables, API access, or business logic.

### Validate Worker JavaScript syntax

```powershell
node --check .\functions\alliance_product_ai_worker\index.js
```

### Install Worker dependencies

```powershell
npm install --prefix .\functions\alliance_product_ai_worker
```

### Verify Node SDK resolution

```powershell
node -e "console.log(require.resolve('zcatalyst-sdk-node'))"
```

If the command reports `Cannot find module`, check `package.json`, install dependencies in the correct function directory, and deploy the Worker again.

## 13. Deployment

### Deploy only the Processor

```powershell
catalyst deploy --only functions:alliance_product_ai_processor
```

Use this after changing only `main.py`, Processor dependencies, or Processor configuration.

### Deploy the complete configured function set

```powershell
catalyst deploy
```

Use this when multiple functions or project configuration have changed. Review the deployment output carefully.

During development, Catalyst reported a `sales_order_processor` target warning because it was listed in the root `catalyst.json` even though its function directory was absent. That warning was separate from the asynchronous PDF flow.

### Root `catalyst.json` observed during implementation

```json
{
  "functions": {
    "targets": [
      "alliance_product_ai_function",
      "sales_order_processor",
      "alliance_product_ai_trigger",
      "alliance_product_ai_worker",
      "alliance_product_ai_processor"
    ],
    "env_variables": {},
    "ignore": [],
    "source": "functions"
  }
}
```

Do not remove old function targets until the replacement flow is fully validated and the impact on any other use has been checked.

## 14. Testing the Flow

1. Choose a Sales Inbox record with a PDF attachment.
2. Submit the PDF and Sales Inbox ID to the Trigger.
3. Confirm the HTTP status is `200` and the body says `"status": "accepted"`.
4. Record the returned `job_name`, `file_id`, and `sales_inbox_id`.
5. Open Catalyst Console and find the corresponding Worker job.
6. Confirm the Worker status is `Success`.
7. Check the Worker logs for a successful PDF download and a non-zero byte size.
8. Find the Processor job created by that Worker.
9. Confirm its parameters contain `sales_inbox_id` and `file_id`.
10. Inspect Processor logs from start to finish.
11. Confirm Item Master loads, OpenAI processing runs, reconciliation completes, customer processing completes, and the Sales Inbox update succeeds.
12. Confirm the **Processor job** reaches `Success`.

A successful Trigger and Worker are not sufficient to declare the whole workflow successful.

## 15. Monitoring Jobs and Logs

Use Catalyst Console:

```text
Project-Rainfall
    |
    +--> Job Scheduling / Jobs
    |       |
    |       +--> Worker: APAI_...
    |       +--> Processor: AP_...
    |
    +--> DevOps
            |
            +--> Logs
```

### Worker logs

Expected checkpoint:

```text
PDF downloaded successfully. Size: <non-zero byte count> bytes
```

### Processor logs

Useful checkpoints include:

```text
ALLIANCE PRODUCT AI PROCESSOR - START
FILE STORE DOWNLOAD - START
File Store service obtained successfully
STARTING FILE DOWNLOAD
Downloaded object type: bytes
PDF downloaded successfully
Item Master loading ...
OpenAI extraction ...
Reconciliation ...
Customer processing ...
Sales Inbox update ...
```

The exact messages depend on the deployed code. Use logs to identify the last successful stage and the first error.

### Log indexing

The Catalyst Console indicated that recent logs may not be indexed immediately. If a just-completed execution shows no logs, wait briefly and refresh before concluding that the function emitted none.

## 16. Issues Encountered and Resolutions

### Issue 1: Node Worker could not load Catalyst SDK

**Error:**

```text
Error: Cannot find module 'zcatalyst-sdk-node'
```

**Resolution:**

```powershell
npm install --prefix .\functions\alliance_product_ai_worker
```

Then verify SDK resolution:

```powershell
node -e "console.log(require.resolve('zcatalyst-sdk-node'))"
```

Also ensure the SDK is explicitly declared in the Worker `package.json`.

### Issue 2: Processor expected a missing `file_name` parameter

**Error:**

```text
Error: 'file_name'
```

The Worker was submitting only `sales_inbox_id` and `file_id` to the Processor, while the Python code attempted to read `file_name`.

**Resolution:** Change the Processor to retrieve only the parameters actually sent:

```python
sales_inbox_id = job_request.get_job_param("sales_inbox_id")
file_id = job_request.get_job_param("file_id")
```

Do not access `file_name` unless the Worker includes it in the Processor job parameters.

### Issue 3: File Store debugging appeared to stop

Additional logging was added around Python SDK initialization, File Store service creation, folder access, and download. A `get_details()` diagnostic call was also tried, but it failed before providing useful file metadata, so it was removed.

The successful logs eventually showed:

```text
STARTING FILE DOWNLOAD
Downloaded object type: bytes
```

This confirmed that the Python Processor had downloaded the file and had progressed beyond the File Store stage.

### Issue 4: Item Master failed because of missing OAuth configuration

**Error:**

```text
Item Master loading failed
Missing environment variable: ZOHO_CLIENT_ID
```

**Resolution:** Configure the required OAuth variables in the Python Processor's Catalyst environment:

```text
ZOHO_CLIENT_ID
ZOHO_CLIENT_SECRET
ZOHO_REFRESH_TOKEN
```

Do not put the actual values in this README.

After configuring the required variables, the Processor progressed beyond the previous Item Master authentication failure.

## 17. Troubleshooting Guide

| Symptom | What to check |
|---|---|
| Trigger returns an error | Request parsing, required parameters, upload result, Trigger logs |
| Trigger returns accepted but no Worker job appears | Job Pool name/ID, `submitJob` response, Trigger logs |
| Worker fails with module-not-found | Worker `package.json`, installed dependencies, deployment |
| Worker cannot download PDF | File Store folder ID, `file_id`, SDK access, download error |
| Worker succeeds but Processor fails | Open the matching Processor job and inspect its logs |
| Processor fails before downloading | Python SDK initialization, File Store service/folder access |
| Processor reports a missing job parameter | Compare Processor `get_job_param()` calls with Worker `params` |
| Processor fails during Item Master | OAuth variables, Creator settings, token refresh and Creator API response |
| Processor fails during OpenAI | Check `OPENAI_API_KEY`, request errors, rate limits and response handling |
| Processor fails during Creator update | Creator API response, field API names, lookup values, subform structure and permissions |
| Logs appear empty immediately | Wait for indexing and refresh the log page |

## 18. Retries, Concurrency, and Reliability

The implementation used:

```text
number_of_retries = 2
retry_interval = 900 seconds (15 minutes)
```

The observed Job Pool configuration during development was:

```text
Name: allianceproductaipool
ID: 64647000000032018
Capacity: 1
Memory: 1024 MB
```

These are observed development settings, not a guarantee of the maximum supported Catalyst limits.

Before production, confirm with Zoho Catalyst Support:

- Maximum Job Function execution duration for the selected runtimes.
- Job Pool queue limits and maximum pending jobs.
- Maximum supported concurrency and how capacity can be increased.
- Retry count and retry interval limits.
- File Store file-size, storage, and transfer limits.
- Restrictions on submitting a Job Function from another Job Function.
- Any plan/edition-specific quotas.

### Duplicate-processing safety

Retries can cause a stage to run more than once. Review the business logic to ensure that retrying does not create duplicate customers, duplicate Sales Order Lines, or repeated updates. Where possible, use stable identifiers and idempotent update/create logic.

### Job completion semantics

The Worker should mark itself successful after the Processor job has been submitted successfully. The Processor job's status is the authoritative status for the PDF processing operation.

## 19. Security and Operations

- Store OAuth secrets and API keys in Catalyst environment configuration.
- Avoid logging PDF contents, tokens, secrets, or unnecessary customer information.
- Keep logs useful by including job IDs, Sales Inbox IDs where appropriate, and stage names.
- Avoid logging sensitive payloads in full.
- Keep dependencies pinned or reviewed for production deployments.
- Monitor failed jobs and configure alerts where appropriate.
- Decide how and when processed PDFs should be removed from File Store, based on retention and audit requirements.
- Review permissions for Creator API connections and Catalyst functions.
- Keep development and production configuration separate.

## 20. Production Readiness Checklist

### Architecture

- [ ] Trigger responds quickly after successfully queuing the Worker.
- [ ] Worker downloads/verifies the PDF and submits the Processor.
- [ ] Processor executes all business stages.
- [ ] Creator is updated only after extraction/reconciliation rules pass.
- [ ] Failures are logged with enough detail to diagnose them.

### Configuration

- [ ] Correct File Store folder is configured.
- [ ] Correct Job Pool is configured.
- [ ] Creator environment variables are present.
- [ ] OAuth variables are present and valid.
- [ ] OpenAI API key is present and valid.
- [ ] Secrets are not committed to source control.

### Reliability

- [ ] Retry behavior has been tested.
- [ ] Duplicate processing has been considered.
- [ ] Job Pool concurrency is appropriate for expected volume.
- [ ] Large PDFs have been tested.
- [ ] Multiple simultaneous uploads have been tested.
- [ ] Error handling covers Creator and OpenAI failures.

### Operations

- [ ] Operators know how to locate Worker and Processor jobs.
- [ ] Log filtering by execution ID has been documented.
- [ ] Failure alerting and retry/reprocessing procedures are defined.
- [ ] File retention and cleanup policy is defined.
- [ ] Development-to-production deployment steps are documented.

## 21. Known Follow-up Items

1. **Confirm full end-to-end completion.** The logs confirmed PDF download and identified/fixed the missing Item Master OAuth variable. The complete final sequence through OpenAI, reconciliation, customer processing, and Sales Inbox update should be verified with a successful Processor job.
2. **Confirm Catalyst platform limits.** Obtain support confirmation for execution time, concurrency, Job Pool queues, File Store limits, and retries.
3. **Review `sales_order_processor` configuration.** It was listed in the root target configuration while its directory was absent. Remove or correct it only after checking whether it is needed.
4. **Review the legacy synchronous function.** Retain it until the asynchronous replacement has been fully tested and approved.
5. **Review Worker dependencies.** Ensure `zcatalyst-sdk-node` is explicitly declared in the Worker package manifest.
6. **Reduce temporary diagnostics when stable.** Keep useful stage-level logs, but remove overly verbose diagnostic output if it is no longer needed.
7. **Review Job Pool capacity.** Capacity was observed as 1 during development. Confirm expected volume and adjust only after checking the supported Catalyst configuration and cost implications.

## 22. Quick Reference

### Main function names

```text
alliance_product_ai_trigger
alliance_product_ai_worker
alliance_product_ai_processor
```

### Key configuration

```text
Project: Project-Rainfall
Project ID: 64647000000013024
File Store folder ID: 64647000000032024
Job Pool: allianceproductaipool
Job Pool ID: 64647000000032018
Python runtime: python_3_12
```

### Commands

Check Python syntax:

```powershell
python -m py_compile .\functions\alliance_product_ai_processor\main.py
```

Check Worker syntax:

```powershell
node --check .\functions\alliance_product_ai_worker\index.js
```

Install Worker dependencies:

```powershell
npm install --prefix .\functions\alliance_product_ai_worker
```

Verify Node SDK resolution:

```powershell
node -e "console.log(require.resolve('zcatalyst-sdk-node'))"
```

Deploy only the Processor:

```powershell
catalyst deploy --only functions:alliance_product_ai_processor
```

Deploy configured functions:

```powershell
catalyst deploy
```

---

## Summary

The workflow uses an asynchronous architecture to avoid keeping the original Creator HTTP request open during the full PDF processing operation:

```text
Creator
  -> alliance_product_ai_trigger
  -> Catalyst File Store
  -> alliance_product_ai_worker
  -> alliance_product_ai_processor
  -> PDF extraction / Item Master / OpenAI / reconciliation
  -> Customer processing
  -> Sales Inbox update
```

The key debugging findings were:

- The Worker SDK dependency had to be installed/resolved correctly.
- The Processor had to request only job parameters that were actually sent.
- Detailed logs showed that the Python Processor could download the PDF.
- Item Master processing then exposed the missing `ZOHO_CLIENT_ID` environment variable.
- The required OAuth variables were configured in the Processor environment, allowing processing to proceed beyond that failure.

**Final acceptance should be based on a successful Processor job and verified Creator updates, not merely the Trigger's HTTP 200 response or the Worker's success status.**
