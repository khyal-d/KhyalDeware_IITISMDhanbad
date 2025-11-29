# utils/postprocess.py

from typing import Any, Dict, List
from models.models import BillItem, PageLineItems, DataPayload


def normalize_payload(raw: Dict[str, Any]) -> DataPayload:
    """
    Convert raw JSON from the model into DataPayload,
    enforcing numeric types and basic sanity checks.
    """
    pages: List[PageLineItems] = []

    for page in raw.get("pagewise_line_items", []):
        page_no = str(page.get("page_no", "1")).strip()
        page_type = str(page.get("page_type", "Bill Detail")).strip() or "Bill Detail"

        bill_items: List[BillItem] = []

        for item in page.get("bill_items", []):
            try:
                name = str(item.get("item_name", "")).strip()
                if not name:
                    continue

                amt = float(item.get("item_amount", 0))
                qty = float(item.get("item_quantity", 0))
                rate_val = float(item.get("item_rate", 0))

                # Drop obviously invalid rows
                if amt <= 0 or qty <= 0:
                    continue

                # Recompute rate if needed
                if rate_val <= 0:
                    rate_val = round(amt / qty, 2)

                bill_items.append(
                    BillItem(
                        item_name=name,
                        item_amount=round(amt, 2),
                        item_rate=round(rate_val, 2),
                        item_quantity=qty,
                    )
                )
            except Exception:
                # Ignore malformed rows
                continue

        if bill_items:
            pages.append(
                PageLineItems(
                    page_no=page_no,
                    page_type=page_type,
                    bill_items=bill_items,
                )
            )

    total_item_count = sum(len(p.bill_items) for p in pages)

    return DataPayload(
        pagewise_line_items=pages,
        total_item_count=total_item_count,
    )
