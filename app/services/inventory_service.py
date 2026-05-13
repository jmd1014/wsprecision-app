"""inventory 비즈니스 로직"""
from app.repositories import inventory_repository as inv_repo


def receive_material(
    material_id: str,
    qty: float,
    *,
    lot_number: str | None = None,
    purchase_order_id: int | None = None,
    txn_date: str | None = None,
    remark: str | None = None,
    created_by: str | None = None,
) -> int:
    """자재 입고 (양수 qty)"""
    if qty <= 0:
        raise ValueError("receive qty must be > 0")
    return inv_repo.record_transaction(
        material_id=material_id,
        txn_type="RECEIPT",
        qty=qty,
        ref_table="purchase_orders" if purchase_order_id else None,
        ref_id=purchase_order_id,
        lot_number=lot_number,
        txn_date=txn_date,
        remark=remark,
        created_by=created_by,
    )


def consume_for_production(
    material_id: str,
    qty: float,
    *,
    product_id: str | None = None,
    work_order_id: int | None = None,
    lot_number: str | None = None,
    txn_date: str | None = None,
    remark: str | None = None,
    created_by: str | None = None,
) -> int:
    """생산 투입 (자재 차감 — 음수 qty 기록)"""
    if qty <= 0:
        raise ValueError("consume qty must be > 0 (자동 음수 부호 처리)")
    return inv_repo.record_transaction(
        material_id=material_id,
        txn_type="PROD_INPUT",
        qty=-qty,
        ref_table="work_orders" if work_order_id else None,
        ref_id=work_order_id,
        lot_number=lot_number,
        product_id=product_id,
        txn_date=txn_date,
        remark=remark,
        created_by=created_by,
    )


def record_defect(
    material_id: str,
    qty: float,
    *,
    lot_number: str | None = None,
    remark: str | None = None,
    created_by: str | None = None,
) -> int:
    """불량 폐기 — 음수 qty"""
    if qty <= 0:
        raise ValueError("defect qty must be > 0")
    return inv_repo.record_transaction(
        material_id=material_id,
        txn_type="DEFECT",
        qty=-qty,
        lot_number=lot_number,
        remark=remark,
        created_by=created_by,
    )


def adjust_stock(
    material_id: str,
    delta: float,
    *,
    reason: str,
    created_by: str | None = None,
) -> int:
    """수동 재고 조정 (delta 양수/음수 모두 가능)"""
    if delta == 0:
        raise ValueError("adjustment delta cannot be 0")
    return inv_repo.record_transaction(
        material_id=material_id,
        txn_type="ADJUSTMENT",
        qty=delta,
        remark=reason,
        created_by=created_by,
    )


def get_current_stock(material_id: str) -> float:
    return inv_repo.current_stock(material_id)


def calc_required_qty(so_qty: float, qty_per_pc: float, shared_factor: float = 1) -> float:
    """BOM 자재 필요량 = (수주수량 * 자재/PC) / shared_factor"""
    if shared_factor <= 0:
        shared_factor = 1
    return (so_qty * (qty_per_pc or 0)) / shared_factor
