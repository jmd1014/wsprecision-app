"""미납 수량 계산 + 상태 도출"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.services.sales_order_service import calc_pending_qty, derive_item_status


def test_calc_pending_qty():
    assert calc_pending_qty(100, 0) == 100
    assert calc_pending_qty(100, 40) == 60
    assert calc_pending_qty(100, 100) == 0
    assert calc_pending_qty(100, 120) == 0          # 초과 납품 시 0
    assert calc_pending_qty(None, None) == 0
    assert calc_pending_qty(50, None) == 50


def test_derive_item_status():
    assert derive_item_status(100, 0) == "PENDING"
    assert derive_item_status(100, 50) == "PARTIAL"
    assert derive_item_status(100, 100) == "DELIVERED"
    assert derive_item_status(100, 150) == "DELIVERED"
    assert derive_item_status(0, 0) == "PENDING"
