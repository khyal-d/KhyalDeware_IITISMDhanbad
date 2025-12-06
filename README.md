# HackRx Bill Extraction 

# 🧾 Medical Bill Line-Item Extraction API (FastAPI + Gemini)

This is a project I made for the **Bajaj Finserv Datathon**.

Here I have explained my project in depth — you can read it to understand the architecture, or use parts of it if you want to build something similar.

---

## 🌐 High-Level Summary

> **“The API exposes a `/extract-bill-data` endpoint that takes a public bill URL. The backend downloads the file, detects whether it’s a PDF or image, and sends it to Gemini with a strict JSON schema and a detailed system prompt. Gemini returns structured JSON with page-wise line items, which I then clean and validate into Pydantic models, drop invalid rows, recompute missing rates, and finally respond with a consistent `SuccessResponse` that includes the extracted bill data plus token usage for cost tracking.”**

---

## 🗂 Project Structure (Core Files)

```text
.
├── main.py
├── models/
│   └── models.py
├── services/
│   ├── prompt.py
│   └── extractor.py
└── utils/
    └── postprocess.py

The explanation below walks through the request path top-down.

1️⃣ main.py – FastAPI Entrypoint

We start from the top of the request path: main.py (FastAPI entrypoint).

What main.py does

Bootstraps the FastAPI application with metadata.

Configures CORS.

Exposes the main Datathon endpoint: POST /extract-bill-data.

Adds a simple health check endpoint: GET /health.

Design notes (how I describe it)

App metadata & Swagger:

“main.py bootstraps the FastAPI app with basic metadata so the judges can explore the API via Swagger without extra docs.”

CORS:

“I added permissive CORS so any evaluation frontend or Postman can hit the API without browser CORS errors.”

Main endpoint:

“The /extract-bill-data endpoint accepts a JSON body with a document URL, validates it with Pydantic, then calls a service function that talks to Gemini and returns bill line items plus token usage. The handler just orchestrates: it catches errors, maps the raw result into our SuccessResponse schema, and returns structured JSON to the evaluator.”

Health endpoint:

“I added a lightweight /health endpoint so we can monitor the service without invoking the LLM every time.”

So main.py is a thin orchestration layer: it doesn’t contain business logic, only HTTP wiring.

2️⃣ models/models.py – API Contracts with Pydantic
What models.py does

This file defines all the JSON contracts for the API using Pydantic:

Request body: DocumentRequest

Internal structured bill representation: BillItem, PageLineItems, DataPayload

Metadata: TokenUsage

Top-level responses: SuccessResponse, ErrorResponse

If you look only at this file, you can know exactly what you must send and what you will get back.

Schema-by-schema explanation
1. DocumentRequest

Wraps the incoming JSON body.

Uses HttpUrl to validate the document field.

“I use Pydantic’s HttpUrl so invalid document links are rejected at the validation layer.”

2. Line item representation: BillItem

Each row in a bill table is normalized into this structure:

item_name – description (e.g., "Consultation Charges").

item_rate – per-unit rate.

item_quantity – quantity, units implied by context.

item_amount – total for that line (rate × quantity).

This is what Gemini is effectively forced to output.

3. Page-level grouping: PageLineItems

Groups BillItems per page of the PDF/image.

page_type lets you distinguish between:

detailed pages,

final summary pages,

pharmacy pages, etc.

4. Full data payload: DataPayload

Represents the main result of the extraction.

Contains:

pagewise_line_items: List[PageLineItems]

total_item_count: int

total_item_count is a quick sanity check and a metric for the evaluator.

5. Token usage metadata: TokenUsage

Tracks LLM cost / efficiency:

total tokens

input tokens

output tokens

6. Success + Error wrappers

SuccessResponse – used on all successful paths.

ErrorResponse – used on validation or server errors.

“I standardized responses into SuccessResponse and ErrorResponse so the scoring script doesn’t have to guess; it always checks is_success and then either reads data or message.”

3️⃣ services/prompt.py – Prompt Engineering & Content Builder

This file has three big responsibilities:

Detect MIME type for the bill (PDF/image).

Build the multimodal request (text + file) for Gemini.

Define the SYSTEM_PROMPT and the EXTRACTION_JSON_SCHEMA.

3.1 MIME Type Detection
def _guess_mime_type_from_url(url: str) -> str: ...
def _guess_mime_type_from_bytes(data: bytes) -> str: ...


Why this is needed:

“A lot of public URLs (like Google Drive) lie about Content-Type and send application/octet-stream. I added both header-based, extension-based and magic-number-based detection so Gemini always gets the correct MIME (image/* or application/pdf) and never octet-stream, which it doesn’t support.”

Why MIME matters:

“MIME type decides which internal pipeline Gemini uses. Images trigger the vision OCR system; PDFs trigger the PDF text extraction engine. If we send application/octet-stream, Gemini treats it as unknown binary and won’t OCR it correctly. So after detecting MIME type, we explicitly attach it to the Gemini file part to guarantee correct parsing.”

3.2 build_gemini_contents(document_url: str)

This function:

Downloads the bill file from the URL.

Auto-detects whether it’s a PDF or an image.

Wraps it as a Gemini file part.

Combines it with the SYSTEM_PROMPT into a single multimodal request.

“build_gemini_contents is my multimodal packer: it downloads the bill, auto-detects whether it’s a PDF or an image, wraps it as a Gemini file part, and pairs it with a detailed system prompt. This keeps all MIME-type and download complexity out of the main business logic.”

3.3 SYSTEM_PROMPT – The Extraction Brain

SYSTEM_PROMPT is a big instruction block that tells Gemini exactly what to extract and what to ignore.

“The prompt encodes all our business rules: what counts as a chargeable line, how to distinguish pharmacy vs bill-detail vs final-bill pages, how to compute rate if missing, and what to exclude like totals and taxes. That makes the model behave like a deterministic parser instead of a chatty assistant.”

Key ideas that are mentioned:

Role & task

“You are an expert medical bill parser.”

Read hospital + pharmacy bills, typed or handwritten.

Output must strictly follow the JSON schema.

What is a valid line item?

Includes:

individual tests, scans, procedures

consumables / medicines

per-day / per-hour charges

doctor consultation entries

What to exclude

totals, subtotals, grand totals

category summaries (e.g., "OT Charges" row without its own amount/qty)

discounts, taxes, deposit/refund rows

headers, footers, “amount in words”

This avoids double counting and noisy rows.

Page handling + page_type

Each physical page with items → one pagewise_line_items entry.

page_type can be:

"Pharmacy" – drug-style bills with HSN, batch, expiry

"Bill Detail" – detailed item lists

"Final Bill" – summary/discharge bill

Field rules for each BillItem

item_name → verbatim text from the bill, no paraphrasing

item_quantity → from Qty / No. / Units etc., default 1 if missing

item_rate → use rate column, else compute amount / quantity

item_amount → net amount per line (after line-level discounts), no tax

Also includes: pharmacy-specific hints, multi-page IPD handling, no grouping, no artificial items, strictly numeric values, page_no as a string.

3.4 EXTRACTION_JSON_SCHEMA
EXTRACTION_JSON_SCHEMA = {
    "name": "bill_extraction_schema",
    "schema": {
        "type": "object",
        "properties": {
            "pagewise_line_items": { ... },
            "total_item_count": {"type": "integer"},
        },
        "required": ["pagewise_line_items", "total_item_count"],
        "additionalProperties": False,
    },
    "strict": True,
}


This schema is passed to Gemini to force structured JSON output.

additionalProperties: False and "strict": True forbid extra keys.

“I pass this JSON schema into Gemini’s generative call so it produces strictly structured JSON. That way my post-processing can json.loads directly into Pydantic models with almost no regex cleaning.”

“The combination of a very explicit system prompt plus a strict JSON schema turns the LLM from a chat agent into a structured extractor. We define what rows to keep or drop, how to compute missing fields, and we forbid extra keys via JSON schema. This reduces hallucinations and makes evaluation straightforward.”

4️⃣ services/extractor.py – Bridge Between API and Gemini
Big picture: what does extractor.py do?

Reads GEMINI_API_KEY.

Creates a Gemini client.

Builds the multimodal content (prompt + bill file).

Calls gemini-2.5-flash with a strict JSON schema.

Extracts token usage.

Normalizes the raw JSON into DataPayload using normalize_payload.

Returns both DataPayload and token usage.

This is the bridge between your API and Gemini.

Key explanations

“The extractor module initializes a single Gemini client using an API key from environment variables. If the key is missing, it fails fast with a clear error, so misconfiguration is caught early instead of during a request.”

“I call gemini-2.5-flash with a strict JSON schema and response_mime_type=application/json. That forces the model to emit valid JSON matching my schema instead of free-form text, which makes downstream parsing deterministic.”

“Once Gemini returns JSON, I parse it and pass it through a normalize_payload helper that maps it into my DataPayload schema. This layer shields the rest of the system from any minor inconsistencies in the raw LLM output.”

In other words:

“The extractor takes a bill URL, builds a multimodal Gemini request with our custom system prompt and the file, and calls gemini-2.5-flash with a strict JSON schema so the response is pure JSON. Then I parse that JSON, normalize it into our DataPayload model, and also track token usage from usage_metadata. The FastAPI layer just calls this function and wraps the result into a consistent API response.”

5️⃣ utils/postprocess.py – Normalization & Cleanup
What normalize_payload does

Takes raw JSON from Gemini (which already follows the schema).

Converts it into proper Pydantic models.

Drops obviously invalid rows.

Recomputes missing rates.

Keeps only valid pages.

“Think of normalize_payload as: ‘Whatever weird-but-close JSON Gemini gives… turn it into clean, reliable DataPayload or quietly drop junk.’”

“After Gemini returns JSON matching our schema, I pass it through a normalize_payload function. It converts everything into typed Pydantic models, drops rows with zero or negative amounts/quantities, recomputes the rate if it’s missing, and ignores malformed entries instead of failing. Only pages with at least one valid line item are kept. This gives us a clean DataPayload that’s safe to expose via the API and easy to score in the datathon.”

🧪 Final Summary (One Paragraph)

“The API exposes a /extract-bill-data endpoint that takes a public bill URL. The backend downloads the file, detects whether it’s a PDF or image, and sends it to Gemini with a strict JSON schema and a detailed system prompt. Gemini returns structured JSON with page-wise line items, which I then clean and validate into Pydantic models, drop invalid rows, recompute missing rates, and finally respond with a consistent SuccessResponse that includes the extracted bill data plus token usage for cost tracking.”

▶️ How to Run (Example)
# Install dependencies
pip install -r requirements.txt

# Set your Gemini API key
export GEMINI_API_KEY="your_api_key_here"

# Run FastAPI app
uvicorn main:app --reload --port 3000


Open Swagger UI:

http://localhost:3000/docs

You can then test POST /extract-bill-data by passing a JSON body like:

{
  "document": "https://example.com/sample-bill.pdf"
}
