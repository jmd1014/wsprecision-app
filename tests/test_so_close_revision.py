# -*- coding: utf-8 -*-
"""수주 상태 정리 r3 — 출고 정정·취소가 종결 수주를 만나는 경우 (D15·D16) 와 대체 되돌리기 실제 흐름 (R5 ③).

정정 흐름은 tests/test_shipment_revision_flow.py 의 목(전표·LOT·회차·라인)을 그대로 쓰고,
수주 머리글·라인만 이 파일에서 덮어쓴다. 대체 되돌리기는 SOMock + so_line_replacements 시드로 수주 관리 화면의 [되돌리기] 를 누른다.
"""
import os
import sys
import importlib.util

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import db as _dbmod  # noqa: E402
from tests import test_shipment_revision_flow as RV  # noqa: E402
from tests.test_shipment_revision_flow import rev_db  # noqa: E402,F401  (fixture 재사용)
from tests.so_mock import SOMock  # noqa: E402
from tests.conftest import goto  # noqa: E402

APP_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "streamlit_app.py")
streamlit_available = importlib.util.find_spec("streamlit") is not None
pytestmark = pytest.mark.skipif(not streamlit_available, reason="streamlit 미설치 — AppTest 불가")


def _patch_header(monkeypatch, status, stale_line=None, current_line=None):
    """sales_orders 머리글 상태를 덮고, 선택적으로 정정이 읽는 라인(stale)과 조건부 갱신이 보는 라인(current)을 가른다."""
    real_fetch = _dbmod.fetch
    real_uc = _dbmod.update_count

    def _fetch(table, select="*", filter_query="", limit=1000, **kw):
        if table == "sales_orders":
            return [{"so_id": 100, "so_number": "SO-100", "customer": "㈜엠제이티", "status": status,
                     "so_date": "2026-08-01", "due_date": None}]
        if table == "sales_order_items" and stale_line is not None and "soi_id=in." in (filter_query or ""):
            return [dict(stale_line)]
        return real_fetch(table, select, filter_query, limit)
    monkeypatch.setattr(_dbmod, "fetch", _fetch)
    real_update = _dbmod.update

    def _update(t, f, v):
        # 회차 갱신은 목 ROUNDS 에 반영 — 그 뒤 조회(닫힌 회차 정리)가 바뀐 delivered 를 본다
        if t == "so_delivery_schedule" and "sched_id=eq." in f:
            sid = int(f.split("sched_id=eq.")[1].split("&")[0])
            for r in RV.ROUNDS:
                if r["sched_id"] == sid:
                    r.update(v)
        return real_update(t, f, v)
    monkeypatch.setattr(_dbmod, "update", _update)

    def _update_count(t, f, v, select="*"):
        if t == "sales_order_items" and current_line is not None:
            # 조건부 갱신: 읽은 status·received 가 현재 라인과 다르면 0행 (운영 PostgREST 와 같은 의미)
            st_ok = f"status=eq.{current_line['status']}" in f
            rc_ok = f"received_qty=eq.{float(current_line['received_qty'])}" in f
            if not (st_ok and rc_ok):
                return 0
        return real_uc(t, f, v, select)
    monkeypatch.setattr(_dbmod, "update_count", _update_count)


def _line_updates():
    return [(f, v) for t, f, v in RV.UPDATED if t == "sales_order_items"]


def _cancel_confirmed(at):
    at.text_input(key="cf_cx_reason_1").set_value("정정 테스트")
    at.run()
    at.button(key="cf_cancel").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    at.button(key="cf_cancel_cfm_ok").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def test_revision_on_closed_header_keeps_delivered_line_inactive(rev_db, monkeypatch):
    """R1/D15: 종결 수주(머리글 CLOSED)의 완납 라인(500/500) 출고 500 전체 취소 → 라인 CLOSED·pending 0·closed_qty 500, 머리글 유지."""
    RV._seed()
    RV.LINES[11].update({"qty": 500, "received_qty": 500, "pending_qty": 0, "status": "DELIVERED", "closed_qty": 0})
    _patch_header(monkeypatch, "CLOSED")
    at = RV._pick_confirmed(RV._open())
    _cancel_confirmed(at)
    ups = _line_updates()
    assert ups, "수주 라인 갱신이 없음"
    flt, fields = ups[-1]
    assert "soi_id=eq.11" in flt and "status=eq.DELIVERED" in flt and "received_qty=eq.500.0" in flt   # D16 조건부
    assert fields == {"received_qty": 0, "pending_qty": 0, "status": "CLOSED", "closed_qty": 500.0}
    # LOT 복원(양수 ISSUE)과 회차 되돌림은 그대로 진행됐다(라인 갱신이 먼저, 그 뒤 LOT·회차)
    txns = [r for t, recs in RV.INSERTED if t == "inventory_transactions" for r in recs]
    assert sorted((r["lot_number"], r["qty"]) for r in txns) == [("W01", 300), ("W02", 200)]
    # 머리글: 비활성이라 재계산 없음 (sales_orders 갱신 0)
    assert not [1 for t, f, v in RV.UPDATED if t == "sales_orders"]
    # 닫힌 회차 정리: 회차 1(qty 500, delivered 500→0)은 qty 도 0 으로 (조건부, R4)
    sched = [(f, v) for t, f, v in RV.UPDATED if t == "so_delivery_schedule"]
    assert any("sched_id=eq.1&qty=gt." in f and v == {"qty": 0.0} for f, v in sched), sched


def test_revision_stops_when_line_changed_meanwhile(rev_db, monkeypatch):
    """R2/D16: 정정이 읽은 라인(PARTIAL·received 500)이 그 사이 종결(CLOSED·closed 1500)돼 조건부 갱신이 0행 → 쓰기 전에 중단."""
    RV._seed()
    stale = dict(RV.LINES[11])                                          # 정정이 읽은 옛 라인
    RV.LINES[11].update({"status": "CLOSED", "pending_qty": 0, "closed_qty": 1500})   # 그 사이 종결된 현재 라인
    _patch_header(monkeypatch, "CLOSED", stale_line=stale, current_line=RV.LINES[11])
    at = RV._pick_confirmed(RV._open())
    _cancel_confirmed(at)
    assert _line_updates() == []                                        # 라인 덮어쓰기 없음
    assert not [1 for t, recs in RV.INSERTED if t == "inventory_transactions"]   # LOT 복원도 안 함(라인이 먼저)
    assert not [1 for t, f, v in RV.UPDATED if t == "so_delivery_schedule"]
    texts = " ".join(str(getattr(w, "value", "") or "") for w in at.warning) + " " + \
            " ".join(str(getattr(w, "value", "") or "") for w in at.error)
    assert "중단" in texts and "새로 열고" in texts
    assert RV.LINES[11]["closed_qty"] == 1500 and RV.LINES[11]["pending_qty"] == 0   # 보존 잔량 유지


def test_revision_on_active_header_unchanged_behaviour(rev_db, monkeypatch):
    """회귀: 활성 수주(PARTIAL)는 r1 과 같은 값(received 0·pending 2000·PENDING) — 조건부 갱신만 추가."""
    RV._seed()
    _patch_header(monkeypatch, "PARTIAL")
    at = RV._pick_confirmed(RV._open())
    _cancel_confirmed(at)
    flt, fields = _line_updates()[-1]
    assert fields == {"received_qty": 0, "pending_qty": 2000, "status": "PENDING"}
    assert "status=eq.PARTIAL" in flt or "status=eq." in flt


# ── 대체 되돌리기 실제 흐름 (`_rp_revert`) ──
def _open_so(monkeypatch, mock):
    mock.install(monkeypatch, _dbmod)
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP_FILE, default_timeout=90)
    at.secrets["supabase"] = {"url": "https://mock.local", "anon_key": "a", "service_role_key": "s"}
    at.secrets["auth"] = {"disabled": True}
    at.run()
    goto(at, "so", "list")
    return at


def _repl_seed(m, old_so_status="CANCELLED", old_line=(1, 1000, 0, 0, "REPLACED"), extra=()):
    """옛 수주 101(대체됨) + 새 수주 102 + 대체 이력 1건."""
    m.seed(so_id=101, so_number="PO-OLD", so_status=old_so_status, lines=[old_line, *extra], rounds=[])
    m.seed(so_id=102, so_number="PO-NEW", so_status="DRAFT", lines=[(9, 1000, 0, 1000, "PENDING")], rounds=[])
    m.line(1)["replaced_by_soi"] = 9
    m.tables["so_line_replacements"] = [{
        "repl_id": 1, "old_soi_id": 1, "new_soi_id": 9, "action": "REPLACE", "old_price": 100, "new_price": 110,
        "closed_pending_qty": 1000, "closed_rounds": [], "moved_rounds": [], "master_updated": False,
        "master_old_price": None, "old_so_status": "DRAFT", "old_line_status": "PENDING", "created_by": "테스트",
        "created_at": "2026-10-20T00:00:00+00:00", "reverted_at": None, "tagged_soi_id": None, "tagged_kind": None}]
    return m


def test_rp_revert_real_flow_recomputes_cancelled_header(monkeypatch):
    """QA B-1 실제 흐름: 대체가 만든 CANCELLED 머리글 → [되돌리기] → 라인 PENDING·pending 1000, 머리글 DRAFT(force 재계산)."""
    m = _repl_seed(SOMock())
    at = _open_so(monkeypatch, m)
    assert at.button(key="rp_rv_1")
    at.button(key="rp_rv_1").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert m.line(1)["status"] == "PENDING" and m.line(1)["pending_qty"] == 1000 and m.line(1)["replaced_by_soi"] is None
    assert m.header(101)["status"] == "DRAFT"
    assert m.tables["so_line_replacements"][0]["reverted_at"]


def test_rp_revert_real_flow_blocked_when_closed(monkeypatch):
    """QA M-6 실제 흐름: 옛 수주가 종결 루틴으로 CLOSED(보존 라인 있음)면 대체 되돌리기 차단 — 아무것도 안 바뀜."""
    m = _repl_seed(SOMock(), old_so_status="CLOSED", extra=[(2, 50, 0, 0, "CLOSED", 50)])
    at = _open_so(monkeypatch, m)
    at.button(key="rp_rv_1").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert m.line(1)["status"] == "REPLACED" and m.header(101)["status"] == "CLOSED"
    assert m.tables["so_line_replacements"][0]["reverted_at"] is None
    assert any("먼저" in str(getattr(w, "value", "")) for w in at.warning)
