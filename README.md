# HackRx Bill Extraction 
# 🧾 Medical Bill Line-Item Extraction API (FastAPI + Gemini)

This is a project I made in the **Bajaj Finserv Datathon**.

Here I have explained my project in depth. You can use it if you want to understand the architecture or reuse parts of the design.

---

## 🔁 Request Path Overview

Let’s start from the top of the request path: **`main.py` (FastAPI entrypoint)**.

---

## 1️⃣ `main.py`

Key ideas and responsibilities:

- App bootstrap and metadata
- CORS configuration
- Main extraction endpoint: `/extract-bill-data`
- Health check endpoint: `/health`

Important points I highlight:

> “main.py bootstraps the FastAPI app with basic metadata so the judges can explore the API via Swagger without extra docs.”

> “I added permissive CORS so any evaluation frontend or Postman can hit the API without browser CORS errors.”

> “The /extract-bill-data endpoint accepts a JSON body with a document URL, validates it with Pydantic, then calls a service function that talks to Gemini and returns bill line items plus token usage. The handler just orchestrates: it catches errors, maps the raw result into our SuccessResponse schema, and returns structured JSON to the evaluator.”

> “I added a lightweight /health endpoint so we can monitor the service without invoking the LLM every time.”

---

## 2️⃣ `models/models.py`

### What `models.py` does

This file defines all the JSON contracts for your API using **Pydantic**:

- Request body: **`DocumentRequest`**
- Internal structured bill representation:
  - **`BillItem`**
  - **`PageLineItems`**
  - **`DataPayload`**
- Metadata:
  - **`TokenUsage`**
- Top-level responses:
  - **`SuccessResponse`**
  - **`ErrorResponse`**

So if you have a look only at this file, then you could know exactly what you must send and what you will get back.

### Schema-by-schema explanation

#### 1. `DocumentRequest`

> “I use Pydantic’s HttpUrl so invalid document links are rejected at the validation layer.”

#### 2. Line item representation (`BillItem`)

Each row in a bill table is normalized into this structure:

- `item_name` – description (e.g., “Consultation Charges”).
- `item_rate` – per-unit rate.
- `item_quantity` – quantity, units implied by context.
- `item_amount` – total for that line (rate × quantity).

> This is what Gemini is effectively forced to output.

#### 3. Page-level grouping (`PageLineItems`)

Groups `BillItem`s per page of the PDF/image.

`page_type` lets you distinguish between:

- Detailed pages  
- Final summary pages  
- Pharmacy pages, etc.

#### 4. Full data payload (`DataPayload`)

This is the main result of the extraction.

- `total_item_count` is a quick sanity check and a metric for the evaluator.

#### 5. Token usage metadata (`TokenUsage`)

Tracks LLM cost / efficiency.

#### 6. Success + Error wrappers

> “I standardized responses into SuccessResponse and ErrorResponse so the scoring script doesn’t have to guess; it always checks is_success and then either reads data or message.”

---

## 3️⃣ `services/prompt.py`

In this module, I handle:

- MIME type detection
- Building Gemini multimodal contents
- The main system prompt
- The JSON schema used for structured output

### MIME helpers

```python
def _guess_mime_type_from_url(url: str) -> str: ...
def _guess_mime_type_from_bytes(data: bytes) -> str: ...
