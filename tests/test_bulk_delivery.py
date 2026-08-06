# -*- coding: utf-8 -*-
"""스케줄 일괄 출고 검증 — 납품 예정 회차 기반 다품목 동시 출고."""
import os
import sys
import importlib.util
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

streamlit_available = importlib.util.find_spec("streamlit") is not None
pytestmark = pytest.mark.skipif(
    not streamlit_available, reason="streamlit 미설치 — AppTest 불가")

APP_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "streamlit_app.py")

TODAY = date.today().isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()

ROUNDS = [
    # 오늘 납기 2품목 + 어제 지연 1건
    {"sched_id": 1, "soi_id": 11, "so_id": 100, "seq": 1,
     "due_date": TODAY, "qty": 500, "delivered_qty": 0},
    {"sched_id": 2, "soi_id": 12, "so_id": 101, "seq": 1,
     "due_date": TODAY, "qty": 300, "delivered_qty": 100},
    {"sched_id": 3, "soi_id": 11, "so_id": 100, "seq": 0,
     "due_date": YESTERDAY, "qty": 200, "delivered_qty": 0},
]
LINES = {
    11: {"soi_id": 11, "so_id": 100, "canonical_pn": "4PDVN-03",
         "customer_part_no": "4S4PDVN-03", "product_id": "P1",
         "qty": 2000, "received_qty": 0, "pending_qty": 2000, "unit": "EA"},
    12: {"soi_id": 12, "so_id": 101, "canonical_pn": "MRG6-07",
         "customer_part_no": None, "product_id": "P2",
         "qty": 1000, "received_qty": 100, "pending_qty": 900, "unit": "EA"},
}
SOS = [{"so_id": 100, "so_number": "SO-100", "customer": "㈜엠제이티",
        "status": "CONFIRMED", "so_date": "2026-07-01",
        "due_date": None},
       {"so_id": 101, "so_number": "SO-101", "customer": "미진정밀",
        "status": "PARTIAL", "so_date": "2026-07-02", "due_date": None}]
STOCK = {"P1": 1000.0, "P2": 150.0}
LOTS = {"P1": [{"product_id": "P1", "lot_number": "20260801-001",
                "remain_qty": 600, "tokusai_qty": 0,
                "first_output_date": "2026-08-01"},
               {"product_id": "P1", "lot_number": "20260803-001",
                "remain_qty": 400, "tokusai_qty": 0,
                "first_output_date": "2026-08-03"}],
        "P2": [{"product_id": "P2", "lot_number": "20260804-001",
                "remain_qty": 150, "tokusai_qty": 0,
                "first_output_date": "2026-08-04"}]}

INSERTED, UPDATED = [], []


def _fetch(table, select="*", filter_query="", limit=1000):
    if table == "so_delivery_schedule":
        if "due_date=lte." in filter_query or "due_date=eq." in filter_query:
            cut = filter_query.split("due_date=")[1].split("&")[0]
            op, _, val = cut.partition(".")
            if op == "eq":
                return [dict(r) for r in ROUNDS if r["due_date"] == val]
            return [dict(r) for r in ROUNDS if r["due_date"] <= val]
        return [dict(r) for r in ROUNDS]
    if table == "sales_orders":
        return [dict(s) for s in SOS]
    if table == "sales_order_items":
        if "so_id=eq." in filter_query:
            sid = int(filter_query.split("so_id=eq.")[1].split("&")[0])
            return [dict(l) for l in LINES.values() if l["so_id"] == sid]
        return [dict(l) for l in LINES.values()]
    if table == "product_stock_v":
        return [{"product_id": p, "pn": p, "customer": "-",
                 "produced_qty": v, "issued_qty": 0, "current_stock": v,
                 "last_txn_date": None}
                for p, v in STOCK.items()]
    if table == "product_lot_stock_v":
        return [dict(x, pn=x["product_id"], customer="-",
                     produced_qty=x["remain_qty"], issued_qty=0,
                     material_lot=None)
                for v in LOTS.values() for x in v]
    if table == "sales_order_stats":
        return []
    return []


@pytest.fixture()
def bulk_db(monkeypatch):
    import db
    INSERTED.clear()
    UPDATED.clear()
    monkeypatch.setattr(db, "fetch", _fetch)
    monkeypatch.setattr(db, "fetch_one", lambda t, f="", s="*": None)
    monkeypatch.setattr(db, "insert",
                        lambda t, r: (INSERTED.append((t, r)), len(r))[1])
    monkeypatch.setattr(db, "update",
                        lambda t, f, v: (UPDATED.append((t, f, v)), True)[1])
    monkeypatch.setattr(db, "delete", lambda t, f: 1)
    monkeypatch.setattr(db, "health_check",
                        lambda: {"status": "OK", "counts": {}})
    monkeypatch.setattr(db, "debug_check", lambda: {"status": "mock"})
    if hasattr(db, "count_rows"):
        monkeypatch.setattr(db, "count_rows", lambda t, f="": 0)
    return db


def _open_shipping(bulk_db):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP_FILE, default_timeout=60)
    at.secrets["supabase"] = {"url": "https://mock.local",
                              "anon_key": "a", "service_role_key": "s"}
    at.secrets["auth"] = {"disabled": True}
    at.run()
    at.sidebar.radio[0].set_value("출고 관리")
    at.sidebar.radio[1].set_value(None)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def test_bulk_table_lists_due_and_late_rounds(bulk_db):
    """오늘 2회차 + 지연 1회차가 목록에 오르고 출고 기본값 = 잔량."""
    at = _open_shipping(bulk_db)
    # AppTest 는 data_editor 를 dataframe 요소로 노출한다
    ed = next(d.value for d in at.dataframe
              if "회차잔량" in d.value.columns)
    assert len(ed) == 3
    assert set(ed["품번"]) == {"4PDVN-03", "MRG6-07"}
    row = ed[ed["납기"] == TODAY].iloc[0]
    assert row["출고"] == row["회차잔량"]
    # MRG6-07: 회차 300 중 100 납품됨 → 잔량 200
    assert float(ed[ed["품번"] == "MRG6-07"].iloc[0]["회차잔량"]) == 200


def test_bulk_submit_writes_lines_rounds_and_fifo_issues(bulk_db):
    at = _open_shipping(bulk_db)
    at.button(key="bk_go").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]

    # 수주 라인: 같은 라인(soi 11)의 2회차(500+200)가 누적 반영
    line_upd = [(f, v) for t, f, v in UPDATED
                if t == "sales_order_items"]
    soi11 = [v for f, v in line_upd if "soi_id=eq.11" in f]
    assert soi11[-1]["received_qty"] == 700
    assert soi11[-1]["pending_qty"] == 1300
    soi12 = [v for f, v in line_upd if "soi_id=eq.12" in f]
    assert soi12[-1]["received_qty"] == 300   # 100 + 200

    # 회차: 각 회차에 직접 충당
    sched_upd = {f: v for t, f, v in UPDATED
                 if t == "so_delivery_schedule"}
    assert sched_upd["sched_id=eq.1"]["delivered_qty"] == 500
    assert sched_upd["sched_id=eq.3"]["delivered_qty"] == 200
    assert sched_upd["sched_id=eq.2"]["delivered_qty"] == 300  # 100+200

    # ISSUE 원장: P1 은 LOT 선입선출 (600 LOT 에서 500+100, 400 LOT 에서 100)
    txns = [r for t, recs in INSERTED
            if t == "inventory_transactions" for r in recs]
    p1 = [r for r in txns if r["product_id"] == "P1"]
    assert sum(-r["qty"] for r in p1) == 700
    assert p1[0]["lot_number"] == "20260801-001"
    assert all(r["txn_type"] == "ISSUE" for r in txns)
    p2 = [r for r in txns if r["product_id"] == "P2"]
    assert sum(-r["qty"] for r in p2) == 200

    # 헤더 상태 갱신
    hdr = [(f, v) for t, f, v in UPDATED if t == "sales_orders"]
    assert any("so_id=eq.100" in f for f, _ in hdr)


def test_bulk_stock_guard_blocks_over_issue(bulk_db):
    """완성 재고보다 많은 출고는 허용 체크 없이는 막힌다."""
    STOCK["P2"] = 50.0     # MRG6-07 잔량 200 > 재고 50
    try:
        at = _open_shipping(bulk_db)
        assert any("완성 재고 부족" in e.value for e in at.error)
        assert at.button(key="bk_go").disabled
    finally:
        STOCK["P2"] = 150.0
