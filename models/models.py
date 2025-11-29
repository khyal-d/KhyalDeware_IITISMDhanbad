from pydantic import BaseModel, HttpUrl
from typing import List


class DocumentRequest(BaseModel):
    document: HttpUrl


class BillItem(BaseModel):
    item_name: str
    item_amount: float
    item_rate: float
    item_quantity: float


class PageLineItems(BaseModel):
    page_no: str
    page_type: str  # "Bill Detail" | "Final Bill" | "Pharmacy"
    bill_items: List[BillItem]


class DataPayload(BaseModel):
    pagewise_line_items: List[PageLineItems]
    total_item_count: int


class TokenUsage(BaseModel):
    total_tokens: int
    input_tokens: int
    output_tokens: int


class SuccessResponse(BaseModel):
    is_success: bool = True
    token_usage: TokenUsage
    data: DataPayload


class ErrorResponse(BaseModel):
    is_success: bool = False
    message: str
