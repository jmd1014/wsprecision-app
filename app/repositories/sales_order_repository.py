"""sales_orders + sales_order_items"""
from app.db import supabase_rest as db


def find_existing_so_numbers(customer: str, so_numbers: list[str]) -> set:
    """주어진 (customer, so_numbers)로 이미 등록된 번호 set 반환"""
    if not so_numbers:
        return set()
    fq = (
        f"customer=eq.{customer}&"
        f"so_number=in.({','.join(so_numbers)})"
    )
    rows = db.fetch("sales_orders", "so_number", fq, limit=1000)
    return {r["so_number"] for r in rows}


def create_sales_order(header: dict, items: list[dict]) -> int:
    """SO 헤더 + 품목 생성. 중복 검사는 호출자가 미리."""
    db.insert("sales_orders", [header])
    row = db.fetch_one(
        "sales_orders",
        f"so_number=eq.{header['so_number']}&customer=eq.{header['customer']}",
        "so_id",
    )
    if not row:
        raise RuntimeError("SO created but not found")
    so_id = row["so_id"]
    if items:
        for it in items:
            it["so_id"] = so_id
        db.insert("sales_order_items", items)
    return so_id


def update_so_status(so_id: int, new_status: str) -> bool:
    return db.update("sales_orders", f"so_id=eq.{so_id}", {"status": new_status})


def get_so_items(so_id: int) -> list:
    return db.fetch("sales_order_items", "*",
                    f"so_id=eq.{so_id}&order=line_no", limit=200)


def calc_pending_qty(qty: float, received_qty: float) -> float:
    """미납 수량 계산 — DB pending_qty 컬럼 대신 이 함수 우선 사용"""
    return max((qty or 0) - (received_qty or 0), 0)


def derive_item_status(qty: float, received_qty: float) -> str:
    """received_qty 기반 상태 도출 (DB의 sales_order_items_v.computed_status와 동일)"""
    rq = received_qty or 0
    if rq == 0:
        return "PENDING"
    if rq >= (qty or 0):
        return "DELIVERED"
    return "PARTIAL"
