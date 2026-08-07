# -*- coding: utf-8 -*-
"""출고 전표 흐름 검증 — 담기(등록) → 확인·정정 → 확정 → 재발행."""
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
    {"sched_id": 1, "soi_id": 11, "so_id": 100, "seq": 1,
     "due_date": TODAY, "qty": 500, "delivered_qty": 0},
    {"sched_id": 2, "soi_id": 12, "so_id": 101, "seq": 1,
     "due_date": TODAY, "qty": 300, "delivered_qty": 100},
    {"sched_id": 3, "soi_id": 11, "so_id": 100, "seq": 0,
     "due_date": YESTERDAY, "qty": 200, "delivered_qty": 0},
]
LINES = {
    11: {"soi_id": 11, "so_id": 100, "canonical_pn": "4PDVN-03",
         "customer_part_no": "4S4PDVN-03", "customer_item_name": None,
         "product_id": "P1", "qty": 2000, "received_qty": 0,
         "pending_qty": 2000, "unit": "EA", "unit_price": 1000,
         "due_date": None},
    12: {"soi_id": 12, "so_id": 101, "canonical_pn": "MRG6-07",
         "customer_part_no": None, "customer_item_name": None,
         "product_id": "P2", "qty": 1000, "received_qty": 100,
         "pending_qty": 900, "unit": "EA", "unit_price": None,
         "due_date": None},
}
SOS = [{"so_id": 100, "so_number": "SO-100", "customer": "㈜엠제이티",
        "status": "CONFIRMED", "so_date": "2026-07-01", "due_date": None},
       {"so_id": 101, "so_number": "SO-101", "customer": "미진정밀",
        "status": "PARTIAL", "so_date": "2026-07-02", "due_date": None}]
STOCK = {"P1": 1000.0, "P2": 150.0}
LOTS = {"P1": [{"product_id": "P1", "lot_number": "20260801-001",
                "remain_qty": 600},
               {"product_id": "P1", "lot_number": "20260803-001",
                "remain_qty": 400}],
        "P2": [{"product_id": "P2", "lot_number": "20260804-001",
                "remain_qty": 150}]}

# 상태 저장 mock — shipments/shipment_items 는 실제로 쌓인다
SHIPMENTS, SHIP_ITEMS = [], []
INSERTED, UPDATED = [], []


def _fetch(table, select="*", filter_query="", limit=1000):
    if table == "shipments":
        rows = [dict(s) for s in SHIPMENTS]
        if "ship_date=eq." in filter_query:
            v = filter_query.split("ship_date=eq.")[1].split("&")[0]
            rows = [r for r in rows if r["ship_date"] == v]
        if "status=eq." in filter_query:
            v = filter_query.split("status=eq.")[1].split("&")[0]
            rows = [r for r in rows if r["status"] == v]
        if "status=neq." in filter_query:
            v = filter_query.split("status=neq.")[1].split("&")[0]
            rows = [r for r in rows if r["status"] != v]
        return sorted(rows, key=lambda r: -r["shipment_id"])
    if table == "shipment_items":
        rows = [dict(x) for x in SHIP_ITEMS]
        if "shipment_id=eq." in filter_query:
            v = int(filter_query.split("shipment_id=eq.")[1].split("&")[0])
            rows = [r for r in rows if r["shipment_id"] == v]
        return rows
    if table == "so_delivery_schedule":
        rows = [dict(r) for r in ROUNDS]
        if "soi_id=eq." in filter_query:
            sid = int(filter_query.split("soi_id=eq.")[1].split("&")[0])
            rows = [r for r in rows if r["soi_id"] == sid]
        if "due_date=lte." in filter_query or "due_date=eq." in filter_query:
            cut = filter_query.split("due_date=")[1].split("&")[0]
            op, _, val = cut.partition(".")
            rows = [r for r in rows
                    if (r["due_date"] == val if op == "eq"
                        else r["due_date"] <= val)]
        return sorted(rows, key=lambda r: (r["due_date"], r["seq"]))
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
                 "last_txn_date": None} for p, v in STOCK.items()]
    if table == "product_lot_stock_v":
        return [dict(x, pn=x["product_id"], customer="-", tokusai_qty=0,
                     produced_qty=x["remain_qty"], issued_qty=0,
                     material_lot=None, first_output_date=None)
                for v in LOTS.values() for x in v]
    if table == "vendors":
        return [{"name": "미진정밀", "business_no": "6060394821",
                 "ceo_name": "이미옥", "phone": None, "address": None,
                 "business_type": "제조", "business_item": "기계부품"}]
    if table == "sales_order_stats":
        return []
    return []


def _insert(table, records):
    if table == "shipments":
        for r in records:
            SHIPMENTS.append(dict(r, shipment_id=len(SHIPMENTS) + 1))
    elif table == "shipment_items":
        for r in records:
            SHIP_ITEMS.append(dict(r, si_id=len(SHIP_ITEMS) + 1))
    INSERTED.append((table, records))
    return len(records)


def _fetch_one(table, filter_query="", select="*"):
    if table == "shipments" and "ship_no=eq." in filter_query:
        no = filter_query.split("ship_no=eq.")[1].split("&")[0]
        for s in SHIPMENTS:
            if s["ship_no"] == no:
                return dict(s)
    return None


def _update(table, filter_query, fields):
    if table == "shipments" and "shipment_id=eq." in filter_query:
        sid = int(filter_query.split("shipment_id=eq.")[1].split("&")[0])
        for s in SHIPMENTS:
            if s["shipment_id"] == sid:
                s.update(fields)
    UPDATED.append((table, filter_query, fields))
    return True


@pytest.fixture()
def ship_db(monkeypatch):
    import db
    SHIPMENTS.clear()
    SHIP_ITEMS.clear()
    INSERTED.clear()
    UPDATED.clear()
    monkeypatch.setattr(db, "fetch", _fetch)
    monkeypatch.setattr(db, "fetch_one", _fetch_one)
    monkeypatch.setattr(db, "insert", _insert)
    monkeypatch.setattr(db, "update", _update)
    monkeypatch.setattr(db, "delete", lambda t, f: 1)
    monkeypatch.setattr(db, "health_check",
                        lambda: {"status": "OK", "counts": {}})
    monkeypatch.setattr(db, "debug_check", lambda: {"status": "mock"})
    if hasattr(db, "count_rows"):
        monkeypatch.setattr(db, "count_rows", lambda t, f="": 0)
    return db


def _open_shipping(ship_db):
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


def _register(at):
    at.button(key="ship_reg").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]


def test_cart_lists_rounds_and_register_creates_draft(ship_db):
    """스케줄 3회차가 담기고 등록하면 DRAFT 전표 + 품목 스냅샷 생성."""
    at = _open_shipping(ship_db)
    ed = next(d.value for d in at.dataframe
              if "잔량" in d.value.columns and "출고" in d.value.columns)
    assert len(ed) == 3
    _register(at)
    assert len(SHIPMENTS) == 1
    s = SHIPMENTS[0]
    assert s["status"] == "DRAFT"
    assert s["ship_no"].startswith("SH-")
    items = [x for x in SHIP_ITEMS if x["shipment_id"] == 1]
    assert len(items) == 3
    # 스냅샷에 거래처 표기·단가 보존
    assert any(x["customer_pn"] == "4S4PDVN-03" for x in items)
    assert any(x["unit_price"] == 1000 for x in items)
    # 등록 시점에는 수주·재고를 건드리지 않는다
    assert not [1 for t, _, _ in UPDATED if t == "sales_order_items"]
    assert not [1 for t, _ in INSERTED
                if t == "inventory_transactions"]


def test_confirm_processes_lines_rounds_fifo_and_status(ship_db):
    """확정 시 수주 반영·회차 날짜 충당·LOT FIFO·전표 CONFIRMED."""
    at = _open_shipping(ship_db)
    _register(at)
    at2 = _open_shipping(ship_db)      # 전표 탭에서 확정
    at2.button(key="cf_go").click()
    at2.run()
    assert not at2.exception, [str(e.value) for e in at2.exception]

    line_upd = [(f, v) for t, f, v in UPDATED
                if t == "sales_order_items"]
    soi11 = [v for f, v in line_upd if "soi_id=eq.11" in f]
    assert soi11[-1]["received_qty"] == 700       # 500(오늘)+200(지연)
    soi12 = [v for f, v in line_upd if "soi_id=eq.12" in f]
    assert soi12[-1]["received_qty"] == 300       # 100+200

    sched_upd = {f: v for t, f, v in UPDATED
                 if t == "so_delivery_schedule"}
    assert sched_upd["sched_id=eq.1"]["delivered_qty"] == 500
    assert sched_upd["sched_id=eq.3"]["delivered_qty"] == 200
    assert sched_upd["sched_id=eq.2"]["delivered_qty"] == 300

    txns = [r for t, recs in INSERTED
            if t == "inventory_transactions" for r in recs]
    p1 = [r for r in txns if r["product_id"] == "P1"]
    assert sum(-r["qty"] for r in p1) == 700
    assert p1[0]["lot_number"] == "20260801-001"   # FIFO
    assert all(r["ref_table"] == "shipment_items" for r in txns)

    assert SHIPMENTS[0]["status"] == "CONFIRMED"


def test_confirmed_shipment_offers_reprints(ship_db):
    """확정 전표에서 출고 리스트·거래명세서 재발행 버튼 제공."""
    at = _open_shipping(ship_db)
    _register(at)
    at2 = _open_shipping(ship_db)
    at2.button(key="cf_go").click()
    at2.run()
    at3 = _open_shipping(ship_db)
    next(r for r in at3.radio
         if r.key == "cf_filter").set_value("확정")
    at3.run()
    assert not at3.exception, [str(e.value) for e in at3.exception]
    # AppTest 는 download_button 의 key 를 노출하지 않음 — 라벨 검증
    labels = {getattr(b, "label", "")
              for b in at3.get("download_button")}
    assert any("출고 리스트 재발행" in l for l in labels)
    assert any("거래명세서 재발행" in l for l in labels)


def test_confirm_stock_guard(ship_db):
    """재고 부족이면 확정 버튼이 잠긴다 (허용 체크 전까지)."""
    STOCK["P2"] = 50.0
    try:
        at = _open_shipping(ship_db)
        _register(at)
        at2 = _open_shipping(ship_db)
        assert any("완성 재고 부족" in e.value for e in at2.error)
        assert at2.button(key="cf_go").disabled
    finally:
        STOCK["P2"] = 150.0
