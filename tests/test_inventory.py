"""inventory transaction 합산 로직 + 자재 필요량"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.services.inventory_service import calc_required_qty


def test_calc_required_qty_basic():
    # 수주 100 EA × 자재 1 EA/PC → 100 EA 필요
    assert calc_required_qty(100, 1) == 100
    # 수주 100 × 2/PC → 200
    assert calc_required_qty(100, 2) == 200
    # shared_factor: 환봉 1개에서 5개 분할 가공 → 100 EA 만들려면 20 EA만 필요
    assert calc_required_qty(100, 1, shared_factor=5) == 20
    # shared_factor=0 또는 None → 1로 처리
    assert calc_required_qty(100, 1, shared_factor=0) == 100
    # 빈 qty/qty_per_pc는 0
    assert calc_required_qty(0, 1) == 0
    assert calc_required_qty(100, None) == 0


def test_inventory_sum_logic():
    """inventory_transactions에서 SUM(qty) = 현재고 검증 로직 시뮬레이션"""
    transactions = [
        {"txn_type": "RECEIPT",    "qty": 100},
        {"txn_type": "PROD_INPUT", "qty": -30},
        {"txn_type": "RECEIPT",    "qty": 50},
        {"txn_type": "DEFECT",     "qty": -5},
        {"txn_type": "ADJUSTMENT", "qty": -2},
    ]
    current = sum(t["qty"] for t in transactions)
    assert current == 113

    # 카테고리별 집계
    total_received = sum(t["qty"] for t in transactions if t["txn_type"] == "RECEIPT")
    total_consumed = -sum(t["qty"] for t in transactions if t["txn_type"] == "PROD_INPUT")
    total_defect   = -sum(t["qty"] for t in transactions if t["txn_type"] == "DEFECT")
    assert total_received == 150
    assert total_consumed == 30
    assert total_defect == 5
