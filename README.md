# Medical Bill Extraction API 🏥

## Project Overview

This project was developed for the Bajaj Finserv Datathon, where I secured All-India Rank 11 among 2000+ participants from IITs, NITs, and BITS across India. It’s a FastAPI-based service that uses Google’s Gemini AI to automatically extract structured line-item data from medical bills (both hospital and pharmacy) in PDF or image format.

**Key Feature**: Converts unstructured medical bills into clean, structured JSON data with page-wise line items, handling both typed and handwritten documents.

---

## Architecture

```
┌─────────────┐
│   main.py   │  FastAPI application entrypoint
└──────┬──────┘
       │
       ├──> /extract-bill-data  (POST endpoint)
       ├──> /health             (GET endpoint)
       │
┌──────▼──────────────────────────────────────┐
│  services/extractor.py                      │
│  - Gemini API client initialization         │
│  - Calls gemini-2.5-flash with JSON schema  │
│  - Token usage tracking                     │
└──────┬──────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────┐
│  services/prompt.py                         │
│  - MIME type detection (PDF vs Image)       │
│  - File download & multimodal packaging     │
│  - System prompt with business rules        │
│  - Strict JSON schema definition            │
└──────┬──────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────┐
│  utils/postprocess.py                       │
│  - Normalize raw Gemini JSON                │
│  - Drop invalid/zero-amount rows            │
│  - Recompute missing rates                  │
│  - Validate into Pydantic models            │
└──────┬──────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────┐
│  models/models.py                           │
│  - Pydantic schemas for all API contracts   │
│  - Request/Response models                  │
│  - Bill data structures                     │
└─────────────────────────────────────────────┘
```
<img width="927" height="613" alt="Screenshot 2025-12-05 155304" src="https://github.com/user-attachments/assets/5270c0b6-4b9e-4e57-8048-c4446567a6e6" />
---

## File-by-File Breakdown

### 1. `main.py` - FastAPI Application

**Purpose**: Bootstraps the FastAPI app with API endpoints and Swagger documentation.

**Key Features**:
- Permissive CORS configuration for easy testing with Postman or evaluation frontends
- Swagger UI accessible for judges to explore API without extra documentation
- Error handling and response orchestration

**Endpoints**:

#### `POST /extract-bill-data`
- Accepts JSON body with document URL
- Validates input with Pydantic
- Calls Gemini service to extract bill data
- Returns structured JSON with line items and token usage

#### `GET /health`
- Lightweight health check endpoint
- Monitors service without invoking LLM
- Quick availability verification

---

### 2. `models/models.py` - Data Contracts

**Purpose**: Defines all JSON contracts using Pydantic for type safety and validation.

#### Schema Definitions:

**`DocumentRequest`**
```python
- document_url: HttpUrl  # Pydantic validates URL format automatically
```
Invalid URLs are rejected at validation layer before hitting business logic.

**`BillItem`** - Individual line item
```python
- item_name: str        # Verbatim from bill (e.g., "Consultation Charges")
- item_rate: float      # Per-unit rate
- item_quantity: float  # Quantity (units implied by context)
- item_amount: float    # Total for line (rate × quantity)
```

**`PageLineItems`** - Page-level grouping
```python
- page_no: str
- page_type: str        # "Pharmacy" | "Bill Detail" | "Final Bill"
- items: List[BillItem]
```
Distinguishes between detailed pages, summary pages, and pharmacy bills.

**`DataPayload`** - Complete extraction result
```python
- pagewise_line_items: List[PageLineItems]
- total_item_count: int  # Quick sanity check for evaluators
```

**`TokenUsage`** - LLM cost/efficiency tracking
```python
- input_tokens: int
- output_tokens: int
- total_tokens: int
```

**`SuccessResponse` & `ErrorResponse`**
- Standardized response wrappers
- Scoring scripts check `is_success` flag
- Either reads `data` or `message` field

---

### 3. `services/prompt.py` - Multimodal Processing

**Purpose**: Handles MIME type detection, file download, and Gemini content packaging.

#### MIME Type Detection

**Why it matters**: Many public URLs (like Google Drive) send incorrect `Content-Type: application/octet-stream`. Gemini needs correct MIME types to choose the right pipeline:
- `image/*` → Vision OCR system
- `application/pdf` → PDF text extraction engine
- `application/octet-stream` → ❌ Won't OCR correctly

**Implementation**:
```python
def _guess_mime_type_from_url(url: str) -> str
    # Header-based detection

def _guess_mime_type_from_bytes(data: bytes) -> str
    # Magic-number-based detection (file signature)
```

Triple-layer detection: HTTP headers → file extension → binary magic numbers

#### `build_gemini_contents(document_url: str)`

**Multimodal packer** that:
1. Downloads the bill document
2. Auto-detects PDF vs Image
3. Wraps it as Gemini file part with correct MIME
4. Pairs with detailed system prompt

Keeps all MIME complexity out of main business logic.

---

### 4. System Prompt - Business Rules Encoding

**Core Philosophy**: Transform Gemini from a chatty assistant into a deterministic parser.

#### Prompt Structure:

**Role Definition**
```
"You are an expert medical bill parser."
- Read hospital + pharmacy bills (typed or handwritten)
- Output must strictly follow JSON schema
```

**Valid Line Items** (Include):
- Individual tests, scans, procedures
- Consumables / medicines
- Per-day / per-hour charges (room rent, ICU)
- Doctor consultation entries

**Invalid Items** (Exclude):
- Totals, subtotals, grand totals
- Category summaries without own amount/qty
- Discounts, taxes, deposit/refund rows
- Headers, footers, "amount in words"

**Prevents double-counting and noisy data.**

#### Page Handling Rules:

**`page_type` Classification**:
- `"Pharmacy"` – Drug bills with HSN, batch, expiry
- `"Bill Detail"` – Detailed item lists
- `"Final Bill"` – Summary/discharge statements

#### Field Extraction Rules:

**Per `BillItem`**:
- `item_name` → Verbatim text (no paraphrasing)
- `item_quantity` → From Qty/No./Units columns, default `1` if missing
- `item_rate` → Use rate column, else compute `amount ÷ quantity`
- `item_amount` → Net amount per line (after line discounts, no tax)

**Special Cases**:
- Pharmacy-specific HSN/batch handling
- Multi-page IPD (inpatient) bills
- No artificial grouping
- Strictly numeric values only
- `page_no` as string type

---

### 5. JSON Schema - Strict Output Format

**`EXTRACTION_JSON_SCHEMA`**

```json
{
  "name": "bill_extraction_schema",
  "schema": {
    "type": "object",
    "properties": {
      "pagewise_line_items": { /* ... */ },
      "total_item_count": {"type": "integer"}
    },
    "required": ["pagewise_line_items", "total_item_count"],
    "additionalProperties": false
  },
  "strict": true
}
```

**Impact**: 
- Passed into Gemini's generative call
- Forces strictly structured JSON output
- Post-processing can `json.loads` directly into Pydantic
- No regex cleaning needed
- **Reduces hallucinations dramatically**

**System Prompt + Strict Schema = Structured Extractor, Not Chat Agent**

---

### 6. `services/extractor.py` - Gemini Integration

**Purpose**: Bridge between API and Gemini AI.

#### Initialization:
```python
- Reads GEMINI_API_KEY from environment
- Creates single Gemini client
- Fails fast with clear error if key missing
```
Misconfiguration caught early, not during request processing.

#### Extraction Flow:

1. **Build multimodal content** (prompt + bill file)
2. **Call `gemini-2.5-flash`** with:
   - `response_mime_type=application/json`
   - Strict JSON schema enforcement
3. **Extract token usage** from `usage_metadata`
4. **Normalize raw JSON** via `normalize_payload`

**Returns**:
```python
{
  "payload": DataPayload,  # Validated Pydantic model
  "usage": TokenUsage      # Cost tracking
}
```

**Key Decision**: Using `gemini-2.5-flash` for speed + cost efficiency while maintaining accuracy.

---

### 7. `utils/postprocess.py` - Data Cleaning

**Purpose**: `normalize_payload` - Turn Gemini's "weird-but-close" JSON into clean, reliable `DataPayload`.

#### Cleaning Steps:

1. **Convert to typed Pydantic models**
2. **Drop invalid rows**:
   - Zero or negative `item_amount`
   - Zero or negative `item_quantity`
3. **Recompute missing rates**: `rate = amount ÷ quantity`
4. **Ignore malformed entries** (don't fail entire request)
5. **Filter empty pages**: Only keep pages with ≥1 valid line item

**Philosophy**: Quiet error handling - extract what's valid, drop what's not.

**Result**: Clean `DataPayload` that's:
- Safe to expose via API
- Easy to score in datathon
- Free of malformed data

---

## Complete Request Flow

```
User Request
    ↓
[POST /extract-bill-data with document_url]
    ↓
[Validate URL with Pydantic]
    ↓
[Download file + detect MIME type]
    ↓
[Package as Gemini multimodal content]
    ↓
[Send to gemini-2.5-flash with strict schema]
    ↓
[Receive structured JSON response]
    ↓
[Normalize + clean data (drop invalid rows)]
    ↓
[Wrap in SuccessResponse with token usage]
    ↓
Return JSON to client
```

---

## API Usage Example

### Request:
```bash
POST /extract-bill-data
Content-Type: application/json

{
  "document_url": "https://example.com/medical-bill.pdf"
}
```

### Response:
```json
{
  "is_success": true,
  "message": "Bill data extracted successfully",
  "data": {
    "pagewise_line_items": [
      {
        "page_no": "1",
        "page_type": "Bill Detail",
        "items": [
          {
            "item_name": "Consultation Charges",
            "item_rate": 500.0,
            "item_quantity": 1.0,
            "item_amount": 500.0
          },
          {
            "item_name": "Blood Test - CBC",
            "item_rate": 350.0,
            "item_quantity": 1.0,
            "item_amount": 350.0
          }
        ]
      }
    ],
    "total_item_count": 2
  },
  "usage": {
    "input_tokens": 1234,
    "output_tokens": 567,
    "total_tokens": 1801
  }
}
```

---

## Technical Highlights

### 🎯 Why This Approach Works:

1. **Deterministic Parsing**: System prompt + strict JSON schema = consistent output
2. **Multi-format Support**: Auto-detection handles PDFs and images seamlessly
3. **Robust MIME Handling**: Triple-layer detection prevents Gemini pipeline failures
4. **Error Resilience**: Post-processing drops bad data instead of failing requests
5. **Cost Tracking**: Token usage metadata for monitoring LLM efficiency
6. **Type Safety**: Pydantic validation at every layer prevents runtime errors

### 🔧 Technologies Used:

- **FastAPI** - High-performance async API framework
- **Pydantic** - Data validation and serialization
- **Google Gemini 2.5 Flash** - Multimodal LLM with vision + PDF parsing
- **Python Magic Numbers** - Binary file type detection
- **CORS Middleware** - Cross-origin resource sharing for testing

---

## Environment Setup

```bash
# Required environment variable
GEMINI_API_KEY=your_api_key_here
```

---

## Key Design Decisions

### 1. Why `gemini-2.5-flash`?
- Optimal balance of speed, cost, and accuracy
- Native multimodal support (PDF + images)
- Structured output via JSON schema

### 2. Why strict JSON schema?
- Eliminates free-form LLM responses
- Makes parsing deterministic
- Reduces hallucinations
- No regex post-processing needed

### 3. Why normalize after extraction?
- LLMs occasionally produce edge cases
- Defensive programming: extract valid data, drop invalid
- Better UX: partial success > complete failure

### 4. Why separate MIME detection?
- Public URLs often lie about content type
- Wrong MIME = wrong Gemini pipeline = poor extraction
- Triple-layer detection ensures reliability

---

## Project Structure

```
.
├── main.py                  # FastAPI entrypoint
├── models/
│   └── models.py           # Pydantic schemas
├── services/
│   ├── prompt.py           # MIME detection + multimodal packaging
│   └── extractor.py        # Gemini API integration
└── utils/
    └── postprocess.py      # Data normalization & cleaning
```

---

## Summary

**The Complete Pipeline**:

> The API exposes a `/extract-bill-data` endpoint that takes a public bill URL. The backend downloads the file, detects whether it's a PDF or image, and sends it to Gemini with a strict JSON schema and a detailed system prompt. Gemini returns structured JSON with page-wise line items, which I then clean and validate into Pydantic models, drop invalid rows, recompute missing rates, and finally respond with a consistent `SuccessResponse` that includes the extracted bill data plus token usage for cost tracking.

---

## Future Enhancements

- [ ] Batch processing for multiple bills
- [ ] Support for additional document formats (TIFF, JPEG2000)
- [ ] Caching layer for repeated URLs
- [ ] Async processing with job queue
- [ ] Enhanced validation rules for specific hospital formats

---

## Contributing

This project was built for the **Bajaj Finserv Datathon**. Feel free to fork and adapt for your use cases!


---

**Built with ❤️ for Bajaj Finserv Datathon**
