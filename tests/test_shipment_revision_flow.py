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
    def _fetch_one(t, f="", s="*"):
        if t == "sales_month_close" and MONTH_CLOSE:
            return dict(MONTH_CLOSE[0])
        if t == "shipments" and "shipment_id=eq." in f:
            sid = int(f.split("shipment_id=eq.")[1].split("&")[0])
            return next((dict(x) for x in SHIPMENTS if x["shipment_id"] == sid), None)
        return None
    monkeypatch.setattr(db, "fetch_one", _fetch_one)
    monkeypatch.setattr(db, "insert", _insert)
    monkeypatch.setattr(db, "update", _update)
    # 조건부 머리글 갱신(status=eq.DRAFT, 2026-10-13 069) — DRAFT 가 아니면 0행
    def _update_count(t, f, v, select="*"):
        if t == "shipments" and "status=eq.DRAFT" in f:
            sid = int(f.split("shipment_id=eq.")[1].split("&")[0])
            row = next((x for x in SHIPMENTS if x["shipment_id"] == sid), None)
            if row is None or row.get("status") != "DRAFT":
                return 0
        return 1 if db.update(t, f, v) else 0
    monkeypatch.setattr(db, "update_count", _update_count)
    monkeypatch.setattr(db, "rpc", lambda *a, **k: None)   # RPC 없음 → 기존 경로
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
    at.selectbox(key="sr_base_month").set_value("2026-09")
    at.run()
    assert [b for b in at.button if b.key == "sr_mc_close"]
    at.button(key="sr_mc_close").click()
    at.run()
    at.button(key="sr_mc_close_cfm_ok").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert [r for t, recs in INSERTED if t == "sales_month_close"
            for r in recs if r["ym"] == "2026-09"]


def test_sales_report_period_query(rev_db):
    """마감 조회 — 기준 월 + 범위로 기간을 정하고 그 기간의 확정 전표만 집계
    (2026-09-30: 거래처별 마감일이 달라 달력 월 고정 → 기간 조회)."""
    _seed()
    at = _open("영업 보고")
    at.selectbox(key="sr_base_month").set_value("2026-09")
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    labels = {getattr(b, "label", "") for b in at.get("download_button")}
    assert any("마감 보고서 인쇄" in l for l in labels)   # 9/1 확정 전표 포함
    assert any("거래내역서 인쇄" in l for l in labels)
    assert any("거래내역서 엑셀" in l for l in labels)
    assert [m for m in at.multiselect if m.key == "sr_cust"]
    # 16일~말일 — 9/1 전표는 범위 밖
    at.selectbox(key="sr_range").set_value("16일 ~ 말일")
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert any("2026-09-16 ~ 2026-09-30 확정 전표가 없습니다" in str(i.value)
               for i in at.info)
    # 전월 26일~25일 — 8/26 ~ 9/25 로 9/1 전표 포함
    at.selectbox(key="sr_range").set_value("전월 26일 ~ 25일")
    at.run()
    assert any(t.value == "2026-08-26" for t in at.text_input)
    labels = {getattr(b, "label", "") for b in at.get("download_button")}
    assert any("마감 보고서 인쇄" in l for l in labels)
    # 잠금은 달력 월 그대로
    assert [b for b in at.button if b.key == "sr_mc_close"]


def test_draft_with_applied_effects_is_guarded(rev_db):
    """확정의 라인 반영(재고 차감·회차 충당)은 끝났는데 전표 머리글만 DRAFT 로
    남은 전표 (2026-10-08 SH-20261008-04 사고): 확정 버튼 잠금, 작성중 취소
    차단, [확정 상태로 저장] 으로 머리글만 맞춘다."""
    _seed()
    TXNS.append({"txn_id": 9, "ref_table": "shipment_items", "ref_id": 2,
                 "txn_type": "ISSUE", "lot_number": None, "qty": -100,
                 "product_id": "P1"})
    ALLOCS.append({"alloc_id": 9, "si_id": 2, "sched_id": 2, "qty": 100})
    at = _open()
    assert any("전표 취소를 누르지 마세요" in str(e.value) for e in at.error)
    assert at.button(key="cf_go").proto.disabled
    # 정정 저장·재고 없이 출고 허용·작성중 취소도 잠긴다 (2026-10-12 리뷰)
    assert at.button(key="cf_save").proto.disabled
    assert at.checkbox(key="cf_over").proto.disabled
    assert at.button(key="cf_cancel").proto.disabled
    # 작성중 취소는 버튼 자체가 잠긴다 (AppTest 도 잠긴 위젯 조작을 거부)
    assert not any(t == "shipments" and f.get("status") == "CANCELLED"
                   for t, _, f in UPDATED)
    # 머리글만 확정으로 저장
    at.button(key="cf_fix_header").click().run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert any(t == "shipments" and f.get("status") == "CONFIRMED"
               and "shipment_id=eq.2" in fq for t, fq, f in UPDATED)
    assert SHIPMENTS[1]["status"] == "CONFIRMED"
    # 성공 안내는 rerun 뒤에도 남는다 (목록에서 전표가 '확정'으로 옮겨가므로)
    assert any("확정으로 저장" in str(x.value) for x in at.success)
    # 라인 재반영은 없어야 한다 (이중 반영 방지)
    assert not any(t == "sales_order_items" for t, _, _ in UPDATED)
    assert not any(t == "inventory_transactions" for t, _ in INSERTED)


def test_clean_draft_cancel_still_works(rev_db):
    """반영 흔적이 없는 작성중 전표는 종전대로 원클릭 취소."""
    _seed()
    at = _open()
    assert not any("확정이 이미 반영된 상태" in str(e.value) for e in at.error)
    assert not [b for b in at.button if b.key == "cf_fix_header"]
    at.button(key="cf_cancel").click().run()
    at.button(key="cf_cancel_cfm_ok").click().run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert SHIPMENTS[1]["status"] == "CANCELLED"
    assert SHIPMENTS[1]["cancel_reason"] == "작성중 취소"


def test_applied_check_failure_locks_everything(rev_db, monkeypatch):
    """흔적 조회가 실패하면 '모름' — 확정·정정·취소를 모두 잠그고 안내
    (2026-10-12 리뷰: 예전엔 실패를 '흔적 없음'으로 처리해 보호가 꺼졌다)."""
    _seed()
    import db

    def _boom(table, select="*", filter_query="", limit=1000):
        if table == "inventory_transactions":
            raise RuntimeError("db down")
        return _fetch(table, select, filter_query, limit)
    monkeypatch.setattr(db, "fetch", _boom)
    at = _open()
    assert any("반영 여부를 확인하지 못했습니다" in str(e.value) for e in at.error)
    assert at.button(key="cf_go").proto.disabled
    assert at.button(key="cf_save").proto.disabled
    assert at.button(key="cf_cancel").proto.disabled
    assert not [b for b in at.button if b.key == "cf_fix_header"]
    assert SHIPMENTS[1]["status"] == "DRAFT"


def test_net_zero_issue_is_not_a_trace(rev_db):
    """차감 −100 과 역분개 +100 이 모두 있는 라인(순합 0)은 흔적이 아니다 —
    건수 기준이면 역반영 끝난 전표가 영구히 잠겼다 (2026-10-12 QA M2)."""
    _seed()
    TXNS.append({"txn_id": 9, "ref_table": "shipment_items", "ref_id": 2,
                 "txn_type": "ISSUE", "lot_number": None, "qty": -100,
                 "product_id": "P1"})
    TXNS.append({"txn_id": 10, "ref_table": "shipment_items", "ref_id": 2,
                 "txn_type": "ISSUE", "lot_number": None, "qty": 100,
                 "product_id": "P1"})
    at = _open()
    assert not any("전표 취소를 누르지 마세요" in str(e.value) for e in at.error)
    assert not at.button(key="cf_go").proto.disabled
    assert not at.button(key="cf_cancel").proto.disabled


def test_confirm_header_failure_is_surfaced_and_recoverable(rev_db, monkeypatch):
    """확정: 라인 반영 뒤 머리글 CONFIRMED 저장이 3회 실패하면 '확정 완료'가
    아니라 오류 배너 + DRAFT 잔류, 다시 열면 [확정 상태로 저장] 이 보인다.
    라인 반영은 정확히 1회 (2026-10-08 사고 경로 자체를 검증)."""
    _seed()
    import db

    def _upd(table, filter_query, fields):
        if table == "shipments" and fields.get("status") == "CONFIRMED":
            UPDATED.append((table, filter_query, fields))
            return False
        return _update(table, filter_query, fields)
    monkeypatch.setattr(db, "update", _upd)
    at = _open()
    at.button(key="cf_go").click().run()
    assert not at.exception, [str(e.value) for e in at.exception]
    hdr_tries = [f for t, _, f in UPDATED
                 if t == "shipments" and f.get("status") == "CONFIRMED"]
    assert len(hdr_tries) == 3
    assert SHIPMENTS[1]["status"] == "DRAFT"
    assert any("전표 취소를 누르지 마세요" in str(e.value) for e in at.error)
    assert not any("출고 확정 —" in str(x.value) for x in at.success)
    line_upd = [f for t, fq, f in UPDATED
                if t == "sales_order_items" and "soi_id=eq.11" in fq]
    assert len(line_upd) == 1 and float(line_upd[0]["received_qty"]) == 600
    assert sum(len(r) for t, r in INSERTED
               if t == "inventory_transactions") == 1
    # 재진입: 흔적을 목에 반영한 뒤 다시 열면 복구 버튼
    TXNS.append({"txn_id": 9, "ref_table": "shipment_items", "ref_id": 2,
                 "txn_type": "ISSUE", "lot_number": None, "qty": -100,
                 "product_id": "P1"})
    ALLOCS.append({"alloc_id": 9, "si_id": 2, "sched_id": 2, "qty": 100})
    at.run()
    assert [b for b in at.button if b.key == "cf_fix_header"]
    assert at.button(key="cf_go").proto.disabled


def test_confirmed_cancel_twice_does_not_double_reverse(rev_db, monkeypatch):
    """확정 전표 취소: 라인 역반영 뒤 머리글 저장이 실패해 CONFIRMED 로 남아도,
    두 번째 취소는 이력(CANCEL)을 보고 라인을 다시 되돌리지 않는다 (QA H3)."""
    _seed()
    import db
    calls = {"n": 0}

    def _upd(table, filter_query, fields):
        if table == "shipments" and fields.get("status") == "CANCELLED":
            calls["n"] += 1
            if calls["n"] <= 3:          # 1차 취소의 재시도 3회 모두 실패
                UPDATED.append((table, filter_query, fields))
                return False
        return _update(table, filter_query, fields)
    monkeypatch.setattr(db, "update", _upd)
    at = _pick_confirmed(_open())
    at.text_input(key="cf_cx_reason_1").set_value("납품일 오류")
    at.run()
    at.button(key="cf_cancel").click()
    at.run()
    at.button(key="cf_cancel_cfm_ok").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert SHIPMENTS[0]["status"] == "CONFIRMED"      # 머리글 실패
    n_line1 = len([1 for t, fq, _ in UPDATED
                   if t == "sales_order_items" and "soi_id=eq.11" in fq])
    assert n_line1 == 1
    assert REVS and REVS[0]["action"] == "CANCEL"
    # 두 번째 취소 — 머리글만
    at.run()
    at.text_input(key="cf_cx_reason_1").set_value("납품일 오류")
    at.run()
    at.button(key="cf_cancel").click()
    at.run()
    at.button(key="cf_cancel_cfm_ok").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    n_line2 = len([1 for t, fq, _ in UPDATED
                   if t == "sales_order_items" and "soi_id=eq.11" in fq])
    assert n_line2 == 1, "두 번째 취소가 수주 라인을 다시 되돌리면 안 됨"
    assert SHIPMENTS[0]["status"] == "CANCELLED"


def test_fix_header_zero_rows_is_reported(rev_db, monkeypatch):
    """[확정 상태로 저장]이 0행(이미 상태가 바뀜)이면 성공으로 표시하지 않는다
    (2026-10-13 069: status=eq.DRAFT 조건부 갱신)."""
    _seed()
    TXNS.append({"txn_id": 9, "ref_table": "shipment_items", "ref_id": 2,
                 "txn_type": "ISSUE", "lot_number": None, "qty": -100,
                 "product_id": "P1"})
    ALLOCS.append({"alloc_id": 9, "si_id": 2, "sched_id": 2, "qty": 100})
    import db
    monkeypatch.setattr(db, "update_count", lambda *a, **k: 0)
    at = _open()
    assert [b for b in at.button if b.key == "cf_fix_header"]
    at.button(key="cf_fix_header").click().run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert SHIPMENTS[1]["status"] == "DRAFT"
    assert any("확정 상태 저장 실패" in str(e.value) for e in at.error)
    assert not any("확정으로 저장했습니다" in str(x.value) for x in at.success)
