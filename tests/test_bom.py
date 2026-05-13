"""BOM 필요량 + 부족분 계산 시나리오"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.services.inventory_service import calc_required_qty


def test_bom_shortage_scenario():
    """수주 1건의 BOM 자재 필요량과 재고 부족 계산"""
    so_qty = 1000  # 수주 수량
    bom_rows = [
        # (material_id, qty_per_pc, shared_factor, current_stock)
        ("M001", 1.0, 1, 500),     # 1000 필요, 500 재고 → 500 부족
        ("M002", 0.5, 1, 600),     # 500 필요, 600 재고 → 0 부족
        ("M003", 1.0, 5, 200),     # 200 필요 (1000/5), 200 재고 → 0 부족
    ]
    shortages = {}
    for mid, qpc, sf, stock in bom_rows:
        required = calc_required_qty(so_qty, qpc, sf)
        shortage = max(required - stock, 0)
        shortages[mid] = shortage

    assert shortages["M001"] == 500
    assert shortages["M002"] == 0
    assert shortages["M003"] == 0


def test_bom_multi_product_share():
    """같은 자재(공용)가 여러 제품에 쓰이는 케이스"""
    # 자재 M005가 제품A 100EA, 제품B 50EA에 각각 1 EA/PC씩 사용
    requirements_per_product = [
        ("PRODUCT_A", 100, 1.0),
        ("PRODUCT_B", 50, 1.0),
    ]
    total_required = sum(qty * qpc for _, qty, qpc in requirements_per_product)
    assert total_required == 150
