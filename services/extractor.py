# services/extractor.py

import json
import os
from typing import Dict, Tuple

from google import genai
from google.genai import types  # noqa: F401 (used indirectly via prompt)
from models.models import DataPayload
from services.prompt import (
    EXTRACTION_JSON_SCHEMA,
    build_gemini_contents,
)
from utils.postprocess import normalize_payload

# Read API key from environment
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError(
        "GEMINI_API_KEY is not set. Please set it as an environment variable or in your .env file."
    )

# Create client with api_key explicitly
client = genai.Client(api_key=GEMINI_API_KEY)



def extract_bill_from_document_url(document_url: str) -> Tuple[DataPayload, Dict[str, int]]:
    contents = build_gemini_contents(document_url)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        config={
            "response_mime_type": "application/json",
            "response_json_schema": EXTRACTION_JSON_SCHEMA["schema"],
        },
    )

    usage = getattr(response, "usage_metadata", None)
    token_usage = {
        "total_tokens": getattr(usage, "total_token_count", 0) if usage else 0,
        "input_tokens": getattr(usage, "prompt_token_count", 0) if usage else 0,
        "output_tokens": getattr(usage, "candidates_token_count", 0) if usage else 0,
    }

    raw_json = json.loads(response.text)
    data_payload = normalize_payload(raw_json)
    return data_payload, token_usage

