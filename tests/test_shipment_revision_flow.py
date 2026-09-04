# -*- coding: utf-8 -*-
"""확정 출고 전표 정정·취소 흐름 (AppTest) — 차이만 역반영 + 월 마감 잠금.

data_editor 는 AppTest 로 편집할 수 없어 '전체 취소'(전 라인 0) 로
정정 엔진(LOT 복원·회차 되돌림·수주 라인·이력·헤더)을 검증한다.
"""
import os
import sys
import importlib.util

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

streamlit_available = importlib.util.find_spec("streamlit") is not None
pytestmark = pytest.mark.skipif(
    not streamlit_available, reason="streamlit 미설치 — AppTest 불가")

APP_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "streamlit_app.py")

SHIPMENTS, SHIP_ITEMS, TXNS, ALLOCS, ROUNDS, LINES = [], [], [], [], [], {}
MONTH_CLOSE, REVS = [], []
INSERTED, UPDATED, DELETED = [], [], []


def _seed(closed=False):
    SHIPMENTS[:] = [
        {"shipment_id": 1, "ship_no": "SH-20260901-01",
         "ship_date": "2026-09-01", "status": "CONFIRMED",
         "created_by": "테스트", "confirmed_at": "2026-09-01T10:00:00",
         "rev_no": 0, "revised_at": None, "cancelled_at": None,
         "cancel_reason": None},
        {"shipment_id": 2, "ship_no": "SH-20260902-01",
         "ship_date": "2026-09-02", "status": "DRAFT",
         "created_by": "테스트", "confirmed_at": None, "rev_no": 0,
         "revised_at": None, "cancelled_at": None,
         "cancel_reason": None},
    ]
    SHIP_ITEMS[:] = [
        {"si_id": 1, "shipment_id": 1, "soi_id": 11, "so_id": 100,
         "sched_id": 1, "product_id": "P1", "pn": "4PDVN-03",
         "customer_pn": "4S4PDVN-03", "item_name": None,
         "customer": "㈜엠제이티", "so_number": "SO-100", "qty": 500,
         "unit": "EA", "unit_price": 1000},
        {"si_id": 2, "shipment_id": 2, "soi_id": 11, "so_id": 100,
         "sched_id": 2, "product_id": "P1", "pn": "4PDVN-03",
         "customer_pn": "4S4PDVN-03", "item_name": None,
         "customer": "㈜엠제이티", "so_number": "SO-100", "qty": 100,
         "unit": "EA", "unit_price": 1000},
    ]
    TXNS[:] = [
        {"txn_id": 1, "ref_table": "shipment_items", "ref_id": 1,
         "txn_type": "ISSUE", "lot_number": "W01", "qty": -300,
         "product_id": "P1"},
        {"txn_id": 2, "ref_table": "shipment_items", "ref_id": 1,
         "txn_type": "ISSUE", "lot_number": "W02", "qty": -200,
         "product_id": "P1"},
    ]
    ALLOCS[:] = [{"alloc_id": 1, "si_id": 1, "sched_id": 1, "qty": 500}]
    ROUNDS[:] = [
        {"sched_id": 1, "soi_id": 11, "so_id": 100, "seq": 1,
         "due_date": "2026-09-01", "qty": 500, "delivered_qty": 500},
        {"sched_id": 2, "soi_id": 11, "so_id": 100, "seq": 2,
         "due_date": "2026-09-02", "qty": 100, "delivered_qty": 0},
    ]
    LINES.clear()
    LINES[11] = {"soi_id": 11, "so_id": 100, "canonical_pn": "4PDVN-03",
                 "customer_part_no": "4S4PDVN-03",
                 "customer_item_name": None, "product_id": "P1",
                 "qty": 2000, "received_qty": 500, "pending_qty": 1500,
                 "unit": "EA", "unit_price": 1000, "due_date": None}
    MONTH_CLOSE[:] = [{"ym": "2026-09", "closed_at": "2026-09-03",
                       "closed_by": "관리자", "note": None}] if closed else []
    REVS[:] = []
    INSERTED.clear()
    UPDATED.clear()
    DELETED.clear()


def _in_ids(fq, key):
    if f"{key}=in.(" not in fq:
        return None
    raw = fq.split(f"{key}=in.(")[1].split(")")[0]
    return {x.strip('"') for x in raw.split(",") if x}


def _fetch(table, select="*", filter_query="", limit=1000):
    fq = filter_query
    if table == "shipments":
        rows = [dict(s) for s in SHIPMENTS]
        if "status=eq." in fq:
            v = fq.split("status=eq.")[1].split("&")[0]
            rows = [r for r in rows if r["status"] == v]
        return sorted(rows, key=lambda r: -r["shipment_id"])
    if table == "shipment_items":
        rows = [dict(x) for x in SHIP_ITEMS]
        if "shipment_id=eq." in fq:
            v = int(fq.split("shipment_id=eq.")[1].split("&")[0])
            rows = [r for r in rows if r["shipment_id"] == v]
        ids = _in_ids(fq, "shipment_id")
        if ids is not None:
            rows = [r for r in rows if str(r["shipment_id"]) in ids]
        return rows
    if table == "inventory_transactions":
        ids = _in_ids(fq, "ref_id")
        return [dict(t) for t in TXNS
                if ids is None or str(t["ref_id"]) in ids]
    if table == "shipment_allocations":
        ids = _in_ids(fq, "si_id")
        return [dict(a) for a in ALLOCS
                if ids is None or str(a["si_id"]) in ids]
    if table == "so_delivery_schedule":
        rows = [dict(r) for r in ROUNDS]
        if "soi_id=eq." in fq:
            sid = int(fq.split("soi_id=eq.")[1].split("&")[0])
            rows = [r for r in rows if r["soi_id"] == sid]
        return sorted(rows, key=lambda r: (r["due_date"], r["seq"]))
    if table == "sales_order_items":
        if "so_id=eq." in fq:
            sid = int(fq.split("so_id=eq.")[1].split("&")[0])
            return [dict(l) for l in LINES.values() if l["so_id"] == sid]
        return [dict(l) for l in LINES.values()]
    if table == "sales_month_close":
        return [dict(m) for m in MONTH_CLOSE]
    if table == "shipment_revisions":
        return [dict(r) for r in REVS]
    if table == "sales_orders":
        return [{"so_id": 100, "so_number": "SO-100",
                 "customer": "㈜엠제이티", "status": "PARTIAL",
                 "so_date": "2026-08-01", "due_date": None}]
    if table == "product_stock_v":
        return [{"product_id": "P1", "pn": "4PDVN-03", "customer": "-",
                 "current_stock": 1000, "produced_qty": 1500,
                 "issued_qty": -500, "last_txn_date": None}]
    return []


def _insert(table, records):
    if table == "shipment_revisions":
        REVS.extend(records)
    INSERTED.append((table, records))
    return len(records)


def _update(table, filter_query, fields):
    if table == "shipments" and "shipment_id=eq." in filter_query:
        sid = int(filter_query.split("shipment_id=eq.")[1].split("&")[0])
        for s in SHIPMENTS:
            if s["shipment_id"] == sid:
                s.update(fields)
    UPDATED.append((table, filter_query, fields))
    return True


def _delete(table, filter_query):
    DELETED.append((table, filter_query))
    return 1


@pytest.fixture()
def rev_db(monkeypatch):
    import db
    monkeypatch.setattr(db, "fetch", _fetch)
    monkeypatch.setattr(db, "fetch_one",
                        lambda t, f="", s="*": (
                            dict(MONTH_CLOSE[0])
                            if t == "sales_month_close" and MONTH_CLOSE
                            else None))
    monkeypatch.setattr(db, "insert", _insert)
    monkeypatch.setattr(db, "update", _update)
    monkeypatch.setattr(db, "delete", _delete)
    monkeypatch.setattr(db, "health_check",
                        lambda: {"status": "OK", "counts": {}})
    monkeypatch.setattr(db, "debug_check", lambda: {"status": "mock"})
    if hasattr(db, "count_rows"):
        monkeypatch.setattr(db, "count_rows", lambda t, f="": 0)
    return db


def _open(page="출고 관리"):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP_FILE, default_timeout=60)
    at.secrets["supabase"] = {"url": "https://mock.local",
                              "anon_key": "a", "service_role_key": "s"}
    at.secrets["auth"] = {"disabled": True}
    at.run()
    if page == "영업 보고":              # 관리자 메뉴 (두 번째 radio)
        at.sidebar.radio[1].set_value(page)
    else:
        at.sidebar.radio[0].set_value(page)
        at.sidebar.radio[1].set_value(None)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def _pick_confirmed(at):
    next(r for r in at.radio if r.key == "cf_filter").set_value("확정")
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def test_confirmed_cancel_reverses_delta_and_keeps_number(rev_db):
    """확정 전표 전체 취소: LOT 복원(양수 ISSUE)·회차·수주 되돌림·이력."""
    _seed()
    at = _pick_confirmed(_open())
    # 정정 expander 와 취소 입력이 보인다
    assert any("전표 정정" in (getattr(e, "label", "") or "")
               for e in at.expander)
    at.text_input(key="cf_cx_reason_1").set_value("거래처 착오")
    at.run()
    at.button(key="cf_cancel").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    at.button(key="cf_cancel_cfm_ok").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]

    txns = [r for t, recs in INSERTED
            if t == "inventory_transactions" for r in recs]
    assert sorted((r["lot_number"], r["qty"]) for r in txns) == \
        [("W01", 300), ("W02", 200)]          # 양수 ISSUE = 복원
    assert all(r["ref_id"] == 1 and r["txn_type"] == "ISSUE"
               for r in txns)

    sched = {f: v for t, f, v in UPDATED if t == "so_delivery_schedule"}
    assert sched["sched_id=eq.1"]["delivered_qty"] == 0
    assert ("shipment_allocations", "alloc_id=eq.1") in DELETED

    line = [v for t, f, v in UPDATED
            if t == "sales_order_items" and "soi_id=eq.11" in f][-1]
    assert line == {"received_qty": 0, "pending_qty": 2000,
                    "status": "PENDING"}

    revs = [r for t, recs in INSERTED
            if t == "shipment_revisions" for r in recs]
    assert len(revs) == 1 and revs[0]["action"] == "CANCEL"
    assert (revs[0]["qty_before"], revs[0]["qty_after"]) == (500, 0)
    assert revs[0]["reason"] == "거래처 착오"

    # 전표 라인 수량은 기록으로 보존, 번호 유지, 상태만 CANCELLED
    assert not [1 for t, f, v in UPDATED if t == "shipment_items"]
    s = SHIPMENTS[0]
    assert s["status"] == "CANCELLED" and s["ship_no"] == "SH-20260901-01"
    assert s["cancel_reason"] == "거래처 착오" and s["rev_no"] == 1


def test_month_close_locks_confirm_and_revision(rev_db):
    """마감된 달: 작성중 전표 확정 버튼 잠금, 확정 전표 정정·취소 숨김."""
    _seed(closed=True)
    at = _open()
    assert any("월 마감" in str(e.value) for e in at.error)
    assert at.button(key="cf_go").proto.disabled
    at = _pick_confirmed(at)
    assert not [b for b in at.button if b.key == "cf_cancel"]
    assert any("월 마감" in str(i.value) for i in at.info)


def test_sales_report_month_close_button(rev_db):
    """영업 보고 > 월 마감: 관리자에게 잠금 버튼, 마감 후 해제 버튼."""
    _seed()
    at = _open("영업 보고")
    assert [b for b in at.button if b.key == "sr_mc_close"]
    at.button(key="sr_mc_close").click()
    at.run()
    at.button(key="sr_mc_close_cfm_ok").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert [r for t, recs in INSERTED if t == "sales_month_close"
            for r in recs if r["ym"] == "2026-09"]
