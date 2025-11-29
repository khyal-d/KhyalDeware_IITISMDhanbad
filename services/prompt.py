# # services/prompt.py

# from typing import List
# from google.genai import types
# import requests


# def _guess_mime_type_from_url(url: str) -> str:
#     """Very simple mime type guess based on file extension."""
#     url_lower = url.lower()
#     if url_lower.endswith(".png"):
#         return "image/png"
#     if url_lower.endswith(".jpg") or url_lower.endswith(".jpeg"):
#         return "image/jpeg"
#     if url_lower.endswith(".webp"):
#         return "image/webp"
#     # fallback
#     return "image/png"


# def build_gemini_contents(document_url: str) -> List[types.Content]:
#     """
#     Build Gemini multimodal contents:
#     - Text instructions (system prompt + extraction task)
#     - Image loaded from the given URL
#     """
#     mime_type = _guess_mime_type_from_url(document_url)
#     resp = requests.get(document_url, timeout=20)
#     resp.raise_for_status()
#     image_bytes = resp.content

#     image_part = types.Part.from_bytes(
#         data=image_bytes,
#         mime_type=mime_type,
#     )

#     # Combine system-style instructions + user instruction in one text part
#     text_instruction = SYSTEM_PROMPT.strip()

#     content = types.Content(
#         role="user",
#         parts=[
#             types.Part(text=text_instruction),
#             image_part,
#         ],
#     )
#     return [content]


# SYSTEM_PROMPT = """
# You are an expert medical bill parser.

# Your task:
# - Read hospital bills and pharmacy bills (typed or handwritten).
# - Extract ONLY the true line items that represent chargeable services or medicines.
# - Return a JSON object that STRICTLY matches the provided json_schema.

# Important semantic rules (learned from training samples):

# 1) What counts as a line item
#    - Individual investigations, lab tests, scans.
#    - Individual procedures or services (e.g., "NURSING CHARGES - NICU", "CT SCAN CHEST").
#    - Individual consumables / medicines / injections.
#    - Individual doctor visit / consultation entries.
#    - Per-day/Per-hour charges such as "VENTILATOR PER DAY", "ROOM RENT", etc.

# 2) What must be EXCLUDED (never output as bill_items)
#    - Any TOTAL / SUBTOTAL / GRAND TOTAL rows (e.g., "Sub Total", "Total of Pathology", "Grand Total", "Net Amount").
#    - Summary rows for categories (e.g., "Consultation", "OT Charges", "Laboratory Charges" when they are category names and not single services).
#    - Discount rows (e.g., "CASH DISCOUNT", "GST Discount", "Discount Amount").
#    - Tax rows (CGST, SGST, IGST, TAX, RND, ROUND OFF).
#    - "Amount in words" text.
#    - Deposit / advance / refund rows.
#    - Headers and footers: patient details, page numbers, disclaimers, “Printed on …”, etc.

# 3) Page handling and page_type
#    - Each physical page that contains at least one valid line item becomes one entry in `pagewise_line_items`.
#    - If a page is pure summary (only totals / discounts / category subtotals) with NO individual items, you may skip that page OR return it with an empty `bill_items` array.
#    - Choose `page_type` as:
#         - "Pharmacy"  → Pharmacy bills: HSN + Batch + Expiry + drug name, or clearly a pharmacy cash bill.
#         - "Bill Detail" → Detailed service / lab / procedure / IPD itemized lists.
#         - "Final Bill"  → Discharge / final / interim summary bills for the whole stay.
#    - For mixed IPD bills, detailed item pages are usually "Bill Detail"; high-level category summaries are "Final Bill".

# 4) Item fields
#    For every extracted line item:
#    - item_name:
#        - Use the exact description as written, including doctor names when present
#          (e.g., "IP CONSULTATION CHARGES - Dr. RANJAN KAMILYA (ORTHOPAEDICS)").
#        - Do NOT paraphrase or simplify.
#    - item_quantity:
#        - Use the quantity column from the bill:
#            * QTY / Qty / No. / Nos / Units / Duration.
#        - If quantity is missing but clearly implied (e.g., a single blood test), treat it as 1.
#    - item_rate:
#        - Use the RATE / Unit Price / Gross-per-unit column if printed.
#        - If rate is not printed but total amount and quantity are printed, compute:
#            item_rate = item_amount / item_quantity (round to 2 decimals).
#    - item_amount:
#        - Use the NET amount charged for that line (after any line-level discount).
#        - When both Gross and Net are present, ALWAYS use the Net column.
#        - Never include tax or discount totals here.

# 5) Pharmacy-specific hints
#    - Bills with columns like: HSN, Batch, Exp Date, Mfg, Qty, Rate, Amount and drug names are "Pharmacy".
#    - Handwritten pharmacy slips often show:
#         * A drug name,
#         * A quantity,
#         * A final amount at the right side.
#      In such cases:
#         - item_amount = the handwritten amount for that drug.
#         - item_quantity = the written quantity (default 1 if not clear).
#         - item_rate = item_amount / item_quantity.
#    - Do NOT treat "Cash Discount" or "GST Discount" or "Total" as bill_items.

# 6) Multi-page IPD bills
#    - Very long bills may contain dozens or hundreds of items across many pages.
#    - NEVER summarise or group items; output every valid row as its own line item.
#    - Ignore repeated category headers such as "IPD CONSUMABLE CHARGES" if they do not have their own amount and quantity columns.

# 7) Avoiding double counting
#    - Do NOT create artificial extra items.
#    - Do NOT turn section subtotals into items.
#    - Only rows with BOTH (a) a concrete service or medicine name, and (b) a numeric amount should become items.

# 8) Types and formatting
#    - Follow the json_schema exactly. No additional keys.
#    - All amounts, rates, and quantities must be valid numbers (no commas or currency symbols).
#    - page_no should be a string such as "1", "2", "3" (use 1-based index if page number is not printed).

# Return ONLY the JSON object as per the json_schema.
# """

# EXTRACTION_JSON_SCHEMA = {
#     "name": "bill_extraction_schema",
#     "schema": {
#         "type": "object",
#         "properties": {
#             "pagewise_line_items": {
#                 "type": "array",
#                 "items": {
#                     "type": "object",
#                     "properties": {
#                         "page_no": {"type": "string"},
#                         "page_type": {
#                             "type": "string",
#                             "enum": ["Bill Detail", "Final Bill", "Pharmacy"],
#                         },
#                         "bill_items": {
#                             "type": "array",
#                             "items": {
#                                 "type": "object",
#                                 "properties": {
#                                     "item_name": {"type": "string"},
#                                     "item_amount": {"type": "number"},
#                                     "item_rate": {"type": "number"},
#                                     "item_quantity": {"type": "number"},
#                                 },
#                                 "required": [
#                                     "item_name",
#                                     "item_amount",
#                                     "item_rate",
#                                     "item_quantity",
#                                 ],
#                                 "additionalProperties": False,
#                             },
#                         },
#                     },
#                     "required": ["page_no", "page_type", "bill_items"],
#                     "additionalProperties": False,
#                 },
#             },
#             "total_item_count": {"type": "integer"},
#         },
#         "required": ["pagewise_line_items", "total_item_count"],
#         "additionalProperties": False,
#     },
#     "strict": True,
# }



# services/prompt.py

from typing import List
from google.genai import types
import requests


def _guess_mime_type_from_url(url: str) -> str:
    """
    Fallback MIME type detector based on URL extension.
    Supports: pdf, png, jpg, jpeg, webp.
    """
    url_lower = url.lower()
    if url_lower.endswith(".png"):
        return "image/png"
    if url_lower.endswith(".jpg") or url_lower.endswith(".jpeg"):
        return "image/jpeg"
    if url_lower.endswith(".webp"):
        return "image/webp"
    if url_lower.endswith(".pdf"):
        return "application/pdf"
    # generic fallback
    return "application/octet-stream"


def _guess_mime_type_from_bytes(data: bytes) -> str:
    """
    Detect MIME type from file 'magic numbers' (first few bytes).
    This handles cases where Content-Type is application/octet-stream
    (e.g., some Google Drive downloads).
    """
    if not data or len(data) < 4:
        return "application/octet-stream"

    # PDF: starts with '%PDF'
    if data.startswith(b"%PDF"):
        return "application/pdf"

    # PNG: 89 50 4E 47 0D 0A 1A 0A
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"

    # JPEG: FF D8 FF
    if data[0:3] == b"\xff\xd8\xff":
        return "image/jpeg"

    # WEBP: 'RIFF'....'WEBP'
    if data[0:4] == b"RIFF" and b"WEBP" in data[0:32]:
        return "image/webp"

    # default
    return "application/octet-stream"


def build_gemini_contents(document_url: str) -> List[types.Content]:
    """
    Build Gemini multimodal contents:
    - Download file from URL (PDF or image)
    - Detect MIME type from HTTP Content-Type header first
    - Fallback to extension- and byte-based detection
    - Support: pdf, jpg, jpeg, png, webp
    """
    # 1) Download the file
    resp = requests.get(document_url, timeout=45)
    resp.raise_for_status()
    file_bytes = resp.content

    # 2) Start with HTTP header hint
    content_type = (resp.headers.get("Content-Type") or "").lower()

    if "pdf" in content_type:
        mime_type = "application/pdf"
    elif "png" in content_type:
        mime_type = "image/png"
    elif "jpeg" in content_type or "jpg" in content_type:
        mime_type = "image/jpeg"
    elif "webp" in content_type:
        mime_type = "image/webp"
    else:
        # 3) If header is useless (e.g. application/octet-stream),
        #    try to detect from byte signature (magic number)
        mime_type = _guess_mime_type_from_bytes(file_bytes)
        if mime_type == "application/octet-stream":
            # 4) Last resort: infer from URL
            mime_type = _guess_mime_type_from_url(document_url)

    # IMPORTANT: Gemini does NOT support application/octet-stream,
    # so if everything fails, assume PDF (most bills are PDFs).
    if mime_type == "application/octet-stream":
        mime_type = "application/pdf"

    file_part = types.Part.from_bytes(
        data=file_bytes,
        mime_type=mime_type,
    )

    text_instruction = SYSTEM_PROMPT.strip()

    content = types.Content(
        role="user",
        parts=[
            types.Part(text=text_instruction),
            file_part,
        ],
    )
    return [content]


SYSTEM_PROMPT = """
You are an expert medical bill parser.

Your task:
- Read hospital bills and pharmacy bills (typed or handwritten).
- Extract ONLY the true line items that represent chargeable services or medicines.
- Return a JSON object that STRICTLY matches the provided json_schema.

Important semantic rules (learned from training samples):

1) What counts as a line item
   - Individual investigations, lab tests, scans.
   - Individual procedures or services (e.g., "NURSING CHARGES - NICU", "CT SCAN CHEST").
   - Individual consumables / medicines / injections.
   - Individual doctor visit / consultation entries.
   - Per-day/Per-hour charges such as "VENTILATOR PER DAY", "ROOM RENT", etc.

2) What must be EXCLUDED (never output as bill_items)
   - Any TOTAL / SUBTOTAL / GRAND TOTAL rows (e.g., "Sub Total", "Total of Pathology", "Grand Total", "Net Amount").
   - Summary rows for categories (e.g., "Consultation", "OT Charges", "Laboratory Charges" when they are category names and not single services).
   - Discount rows (e.g., "CASH DISCOUNT", "GST Discount", "Discount Amount").
   - Tax rows (CGST, SGST, IGST, TAX, RND, ROUND OFF).
   - "Amount in words" text.
   - Deposit / advance / refund rows.
   - Headers and footers: patient details, page numbers, disclaimers, “Printed on …”, etc.

3) Page handling and page_type
   - Each physical page that contains at least one valid line item becomes one entry in `pagewise_line_items`.
   - If a page is pure summary (only totals / discounts / category subtotals) with NO individual items, you may skip that page OR return it with an empty `bill_items` array.
   - Choose `page_type` as:
        - "Pharmacy"  → Pharmacy bills: HSN + Batch + Expiry + drug name, or clearly a pharmacy cash bill.
        - "Bill Detail" → Detailed service / lab / procedure / IPD itemized lists.
        - "Final Bill"  → Discharge / final / interim summary bills for the whole stay.
   - For mixed IPD bills, detailed item pages are usually "Bill Detail"; high-level category summaries are "Final Bill".

4) Item fields
   For every extracted line item:
   - item_name:
       - Use the exact description as written, including doctor names when present
         (e.g., "IP CONSULTATION CHARGES - Dr. RANJAN KAMILYA (ORTHOPAEDICS)").
       - Do NOT paraphrase or simplify.
   - item_quantity:
       - Use the quantity column from the bill:
           * QTY / Qty / No. / Nos / Units / Duration.
       - If quantity is missing but clearly implied (e.g., a single blood test), treat it as 1.
   - item_rate:
       - Use the RATE / Unit Price / Gross-per-unit column if printed.
       - If rate is not printed but total amount and quantity are printed, compute:
           item_rate = item_amount / item_quantity (round to 2 decimals).
   - item_amount:
       - Use the NET amount charged for that line (after any line-level discount).
       - When both Gross and Net are present, ALWAYS use the Net column.
       - Never include tax or discount totals here.

5) Pharmacy-specific hints
   - Bills with columns like: HSN, Batch, Exp Date, Mfg, Qty, Rate, Amount and drug names are "Pharmacy".
   - Handwritten pharmacy slips often show:
        * A drug name,
        * A quantity,
        * A final amount at the right side.
     In such cases:
        - item_amount = the handwritten amount for that drug.
        - item_quantity = the written quantity (default 1 if not clear).
        - item_rate = item_amount / item_quantity.
   - Do NOT treat "Cash Discount" or "GST Discount" or "Total" as bill_items.

6) Multi-page IPD bills
   - Very long bills may contain dozens or hundreds of items across many pages.
   - NEVER summarise or group items; output every valid row as its own line item.
   - Ignore repeated category headers such as "IPD CONSUMABLE CHARGES" if they do not have their own amount and quantity columns.

7) Avoiding double counting
   - Do NOT create artificial extra items.
   - Do NOT turn section subtotals into items.
   - Only rows with BOTH (a) a concrete service or medicine name, and (b) a numeric amount should become items.

8) Types and formatting
   - Follow the json_schema exactly. No additional keys.
   - All amounts, rates, and quantities must be valid numbers (no commas or currency symbols).
   - page_no should be a string such as "1", "2", "3" (use 1-based index if page number is not printed).

Return ONLY the JSON object as per the json_schema.
"""

EXTRACTION_JSON_SCHEMA = {
    "name": "bill_extraction_schema",
    "schema": {
        "type": "object",
        "properties": {
            "pagewise_line_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "page_no": {"type": "string"},
                        "page_type": {
                            "type": "string",
                            "enum": ["Bill Detail", "Final Bill", "Pharmacy"],
                        },
                        "bill_items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "item_name": {"type": "string"},
                                    "item_amount": {"type": "number"},
                                    "item_rate": {"type": "number"},
                                    "item_quantity": {"type": "number"},
                                },
                                "required": [
                                    "item_name",
                                    "item_amount",
                                    "item_rate",
                                    "item_quantity",
                                ],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["page_no", "page_type", "bill_items"],
                    "additionalProperties": False,
                },
            },
            "total_item_count": {"type": "integer"},
        },
        "required": ["pagewise_line_items", "total_item_count"],
        "additionalProperties": False,
    },
    "strict": True,
}
