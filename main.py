from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models.models import (
    DocumentRequest,
    SuccessResponse,
    ErrorResponse,
    TokenUsage,
)
from services.extractor import extract_bill_from_document_url

app = FastAPI(
    title="HackRx Bill Extraction API (Gemini)",
    version="1.0.0",
    description="Datathon bill line item extraction service using Google Gemini API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post(
    "/extract-bill-data",
    response_model=SuccessResponse,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def extract_bill_data(payload: DocumentRequest):
    """
    Required Datathon endpoint:

    POST /extract-bill-data
    Body: { "document": "<public URL of bill image>" }
    """
    document_url = str(payload.document)

    try:
        data_payload, usage = extract_bill_from_document_url(document_url)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process document: {e}",
        )

    token_usage = TokenUsage(
        total_tokens=usage.get("total_tokens", 0),
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
    )

    return SuccessResponse(
        is_success=True,
        token_usage=token_usage,
        data=data_payload,
    )


@app.get("/health")
def health_check():
    return {"status": "ok"}
