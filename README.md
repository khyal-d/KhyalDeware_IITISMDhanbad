# HackRx Bill Extraction 
# 🧾 Medical Bill Line-Item Extraction API (FastAPI + Gemini)

This is a project I made in the **Bajaj Finserv Datathon**.

Here I have explained my project in depth. You can use this documentation if you want to understand the system architecture or build a similar extraction pipeline.

---

# 1️⃣ Associated Explanation (Prompt + MIME Logic)

### MIME Type Handling

> **“A lot of public URLs (like Google Drive) lie about Content-Type and send `application/octet-stream`. I added both header-based, extension-based and magic-number-based detection so Gemini always gets the correct MIME (`image/*` or `application/pdf`) and never octet-stream, which it doesn’t support.”**

> **“MIME type decides which internal pipeline Gemini uses. Images trigger the vision OCR system; PDFs trigger the PDF text extraction engine. If we send `application/octet-stream`, Gemini treats it as unknown binary and won’t OCR it correctly. So after detecting MIME type, we explicitly attach it to the Gemini file part to guarantee correct parsing.”**

---

# 2️⃣ `build_gemini_contents(document_url: str)`

> **“build_gemini_contents is my multimodal packer: it downloads the bill, auto-detects whether it’s a PDF or an image, wraps it as a Gemini file part, and pairs it with a detailed system prompt. This keeps all MIME-type and download complexity out of the main business logic.”**

---

# 3️⃣ SYSTEM_PROMPT (The Brain of Extraction)

`SYSTEM_PROMPT` is a detailed instruction block that tells Gemini **exactly what to extract** and **what to ignore**.

> **“The prompt encodes all our business rules: what counts as a chargeable line, how to distinguish pharmacy vs bill-detail vs final-bill pages, how to compute rate if missing, and what to exclude like totals and taxes. That makes the model behave like a deterministic parser instead of a chatty assistant.”**

## Key ideas encoded in the prompt:

### Role & Task
- **“You are an expert medical bill parser.”**
- Understand **hospital + pharmacy bills**, typed or handwritten.
- Output **must strictly follow the JSON schema**.

### What is a Valid Line Item?
Includes:
- Individual tests, scans, procedures  
- Consumables / medicines  
- Per-day / per-hour charges  
- Doctor consultation entries  

### What to Exclude
- Totals, subtotals, grand totals  
- Category summaries (e.g., `"OT Charges"` without qty/amount)  
- Discounts, taxes, deposit/refund rows  
- Headers, footers, “amount in words”  

> This avoids double counting and noisy rows.

### Page Handling & `page_type`
Each physical page with items → **one entry** in `pagewise_line_items`.

`page_type` can be:

- `"Pharmacy"` – HSN, batch, expiry  
- `"Bill Detail"` – detailed item listing  
- `"Final Bill"` – summary/discharge  

### Field Rules per `BillItem`
- `item_name` → verbatim (no paraphrasing)  
- `item_quantity` → parsed or default **1**  
- `item_rate` → parsed or compute `amount / quantity`  
- `item_amount` → **net** per-line amount (no tax, no discounts)  

Also includes:
- Pharmacy hints  
- Multi-page IPD handling  
- No grouping  
- No artificial items  
- Strict numeric values  
- `page_no` always string  

---

# 4️⃣ EXTRACTION_JSON_SCHEMA

```python
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
Explanation:
“I pass this JSON schema into Gemini’s generative call so it produces strictly structured JSON. That way my post-processing can json.loads directly into Pydantic models with almost no regex cleaning.”

“The combination of a very explicit system prompt plus a strict JSON schema turns the LLM from a chat agent into a structured extractor. We define what rows to keep or drop, how to compute missing fields, and we forbid extra keys via JSON schema. This reduces hallucinations and makes evaluation straightforward.”

5️⃣ services/extractor.py
Big Picture: What Does This Module Do?
Reads GEMINI_API_KEY

Creates a Gemini client

Builds multimodal content (prompt + file)

Calls gemini-2.5-flash with strict JSON schema

Extracts token usage metadata

Normalizes Gemini JSON into DataPayload

Returns structured output to FastAPI

This module is the bridge between your API and Gemini.

Important Explanations:
“The extractor module initializes a single Gemini client using an API key from environment variables. If the key is missing, it fails fast with a clear error, so misconfiguration is caught early instead of during a request.”

“I call gemini-2.5-flash with a strict JSON schema and response_mime_type=application/json. That forces the model to emit valid JSON matching my schema instead of free-form text, which makes downstream parsing deterministic.”

“Once Gemini returns JSON, I parse it and pass it through a normalize_payload helper that maps it into my DataPayload schema. This layer shields the rest of the system from any minor inconsistencies in the raw LLM output.”

In simple words:
“The extractor takes a bill URL, builds a multimodal Gemini request with our custom system prompt and the file, and calls gemini-2.5-flash with a strict JSON schema so the response is pure JSON. Then I parse that JSON, normalize it into our DataPayload model, and also track token usage from usage_metadata. The FastAPI layer just calls this function and wraps the result into a consistent API response.”

6️⃣ utils/postprocess.py
What normalize_payload Does
Think of it as:

“Whatever weird-but-close JSON Gemini gives… turn it into clean, reliable DataPayload or quietly drop junk.”

Specific behaviors:
Converts everything to strong Pydantic models

Drops rows with:

Zero or negative amounts

Zero or negative quantities

Recomputes missing rates (amount / quantity)

Ignores malformed items

Only keeps pages that contain at least one valid item

Explanation:
“After Gemini returns JSON matching our schema, I pass it through a normalize_payload function. It converts everything into typed Pydantic models, drops rows with zero or negative amounts/quantities, recomputes the rate if it’s missing, and ignores malformed entries instead of failing. Only pages with at least one valid line item are kept. This gives us a clean DataPayload that’s safe to expose via the API and easy to score in the datathon.”

✅ Final Summary
“The API exposes a /extract-bill-data endpoint that takes a public bill URL. The backend downloads the file, detects whether it’s a PDF or image, and sends it to Gemini with a strict JSON schema and a detailed system prompt. Gemini returns structured JSON with page-wise line items, which I then clean and validate into Pydantic models, drop invalid rows, recompute missing rates, and finally respond with a consistent SuccessResponse that includes the extracted bill data plus token usage for cost tracking.”
