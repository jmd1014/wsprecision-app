# -*- coding: utf-8 -*-
"""출고 리스트 품명·LOT 헬퍼 검증."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.ship_lots import (  # noqa: E402
    fifo_preview, format_lots, issued_lots, names_and_lots)


def test_format_lots():
    assert format_lots([]) == ""
    assert format_lots([("W0001", 500)]) == "W0001"
    assert format_lots([("W0001", 400), ("W0002", 100)]) == \
        "W0001(400) W0002(100)"
    assert format_lots([(None, 200)]) == "미지정"
    assert format_lots([("W0001", 0)]) == ""       # 0 수량 무시


def test_issued_lots_groups_by_si():
    txns = [
        {"ref_id": 1, "lot_number": "W0001", "qty": -400},
        {"ref_id": 1, "lot_number": "W0002", "qty": -100},
        {"ref_id": 2, "lot_number": None, "qty": -50},
        {"ref_id": None, "lot_number": "W0009", "qty": -9},
    ]
    out = issued_lots(txns)
    assert out[1] == "W0001(400) W0002(100)"
    assert out[2] == "미지정"
    assert None not in out


def test_fifo_preview_splits_and_tracks_usage():
    """같은 제품 두 라인이 잔량을 나눠 쓰고, FIFO 순서를 지킨다."""
    items = [{"si_id": 1, "product_id": "P1", "qty": 500},
             {"si_id": 2, "product_id": "P1", "qty": 400}]
    lots = {"P1": [{"lot_number": "W0001", "remain_qty": 600},
                   {"lot_number": "W0002", "remain_qty": 400}]}
    out = fifo_preview(items, lots)
    assert out[1] == "W0001"                       # 500 ≤ 600 — 단일
    assert out[2] == "W0001(100) W0002(300)"       # 나머지 100 + 다음 LOT


def test_fifo_preview_shortage_marker():
    items = [{"si_id": 1, "product_id": "P1", "qty": 2000}]
    lots = {"P1": [{"lot_number": "W0001", "remain_qty": 600}]}
    out = fifo_preview(items, lots)
    assert out[1] == "W0001 (부족 1,400)"
    # LOT 자체가 없으면 전량 부족
    assert fifo_preview(items, {})[1] == "(부족 2,000)"


def _fake_fetch(table, select="*", filter_query="", limit=1000):
    if table == "products":
        return [{"product_id": "P1", "sub_class": "PDV"}]
    if table == "inventory_transactions":
        return [{"ref_id": 1, "lot_number": "W0001", "qty": -500}]
    if table == "product_lot_stock_v":
        return [{"product_id": "P1", "lot_number": "W0003",
                 "remain_qty": 600}]
    return []


def test_names_and_lots_confirmed():
    """확정 전표 — 원장 실적 LOT + 품명 폴백(sub_class)."""
    items = [{"si_id": 1, "product_id": "P1", "item_name": None,
              "qty": 500}]
    names, lots = names_and_lots(_fake_fetch, items, confirmed=True)
    assert names[1] == "PDV"                       # item_name 없음 → 폴백
    assert lots[1] == "W0001"


def test_names_and_lots_draft_uses_fifo():
    """작성중 전표 — 완성 LOT 잔량 FIFO 예정 배분."""
    items = [{"si_id": 1, "product_id": "P1",
              "item_name": "40A BELLOWS VALVE GLAND NUT", "qty": 500}]
    names, lots = names_and_lots(_fake_fetch, items, confirmed=False)
    assert names[1] == "40A BELLOWS VALVE GLAND NUT"
    assert lots[1] == "W0003"


def test_names_prefer_product_master_item_name():
    """사내명칭 위주 — 마스터 품명이 스냅샷(수주 품명)보다 우선,
    마스터 품명이 없으면 스냅샷 → 제품군 순."""
    def _f(table, select="*", filter_query="", limit=1000):
        if table == "products":
            return [{"product_id": "P1",
                     "item_name": "40A BELLOWS VALVE GLAND NUT",
                     "sub_class": "ABV"},
                    {"product_id": "P2", "item_name": None,
                     "sub_class": "PDV"}]
        return []
    items = [{"si_id": 1, "product_id": "P1",
              "item_name": "수주때 표기", "qty": 10},
             {"si_id": 2, "product_id": "P2",
              "item_name": "수주 품명", "qty": 10},
             {"si_id": 3, "product_id": "P2", "item_name": None,
              "qty": 10}]
    names, _ = names_and_lots(_f, items, confirmed=True)
    assert names[1] == "40A BELLOWS VALVE GLAND NUT"   # 마스터 우선
    assert names[2] == "수주 품명"                      # 마스터 없음 → 스냅샷
    assert names[3] == "PDV"                           # 둘 다 없음 → 제품군
