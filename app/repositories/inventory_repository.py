"""inventory_transactions + material_stock 조회"""
from app.db import supabase_rest as db


def record_transaction(
    material_id: str,
    txn_type: str,
    qty: float,
    *,
    ref_table: str | None = None,
    ref_id: int | None = None,
    lot_number: str | None = None,
    product_id: str | None = None,
    txn_date: str | None = None,
    remark: str | None = None,
    created_by: str | None = None,
) -> int:
    """inventory_transactions에 1행 추가. 반환: insert 행수 (보통 1)"""
    payload = {
        "material_id": material_id,
        "txn_type": txn_type,
        "qty": qty,
        "ref_table": ref_table,
        "ref_id": ref_id,
        "lot_number": lot_number,
        "product_id": product_id,
        "remark": remark,
        "created_by": created_by,
    }
    if txn_date:
        payload["txn_date"] = txn_date
    payload = {k: v for k, v in payload.items() if v is not None}
    return db.insert("inventory_transactions", [payload])


def list_transactions(material_id: str | None = None,
                      since_date: str | None = None,
                      limit: int = 200) -> list:
    fq_parts = ["order=txn_date.desc,txn_id.desc"]
    if material_id:
        fq_parts.append(f"material_id=eq.{material_id}")
    if since_date:
        fq_parts.append(f"txn_date=gte.{since_date}")
    return db.fetch("inventory_transactions", "*", "&".join(fq_parts), limit=limit)


def current_stock(material_id: str) -> float:
    row = db.fetch_one("material_stock", f"material_id=eq.{material_id}",
                       "current_stock")
    return float(row["current_stock"]) if row and row.get("current_stock") is not None else 0.0


def list_stock(material_filter: str | None = None, limit: int = 500) -> list:
    fq = "order=material_id.asc"
    if material_filter:
        fq = f"or=(material_id.ilike.*{material_filter}*,raw_name.ilike.*{material_filter}*)&" + fq
    return db.fetch("material_stock", "*", fq, limit=limit)
