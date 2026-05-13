"""purchase_orders + purchase_order_items"""
from app.db import supabase_rest as db


def next_po_number() -> str:
    """DB 함수 next_po_number() 호출 — 동시성 안전"""
    result = db.rpc("next_po_number")
    if isinstance(result, str):
        return result
    if isinstance(result, list) and result:
        return str(result[0])
    raise RuntimeError(f"unexpected rpc result: {result!r}")


def create_purchase_order(header: dict, items: list[dict]) -> int:
    """발주 헤더 + 품목 동시 생성. 반환: po_id"""
    db.insert("purchase_orders", [header])
    po_row = db.fetch_one(
        "purchase_orders",
        f"po_number=eq.{header['po_number']}",
        "po_id",
    )
    if not po_row:
        raise RuntimeError("PO created but not found")
    po_id = po_row["po_id"]
    if items:
        for it in items:
            it["po_id"] = po_id
        db.insert("purchase_order_items", items)
    return po_id


def update_po_status(po_id: int, new_status: str) -> bool:
    return db.update("purchase_orders", f"po_id=eq.{po_id}", {"status": new_status})


def get_po_with_items(po_id: int):
    po = db.fetch_one("purchase_orders", f"po_id=eq.{po_id}", "*")
    items = db.fetch("purchase_order_items", "*",
                     f"po_id=eq.{po_id}&order=line_no", limit=200)
    return po, items
