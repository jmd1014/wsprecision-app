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


def _patch_header(monkeypatch, status, stale_line=None, current_line=None, status_refetch=None, stale_lines=None,
                  refetch_raise=False, refetch_empty=False, snapshot_raise=False, hist_raise=False,
                  hist_raise_routine=False):
    """sales_orders 머리글 상태를 덮고, 선택적으로 정정이 읽는 라인(stale)과 조건부 갱신이 보는 라인(current)을 가른다.
    status_refetch: PATCH 직전 재조회(so_id=eq., cache=False)가 돌려줄 머리글 상태(H-2 창 재현)."""
    # 같은 테스트에서 두 번 부르면 래퍼가 겹쳐 조건을 두 번 검사(두 번째는 이미 바뀐 라인) → 0행 오판. 원본(rev_db)을 기억해 그 위에만 씌운다
    if not hasattr(monkeypatch, "_so_base"):
        monkeypatch._so_base = (_dbmod.fetch, _dbmod.update_count, _dbmod.update)
    real_fetch, real_uc, real_update = monkeypatch._so_base
    stale_map = dict(stale_lines or {})
    if stale_line is not None:
        stale_map[stale_line["soi_id"]] = stale_line
    cur_map = {}
    if current_line is not None:
        cur_map[current_line["soi_id"]] = current_line

    def _fetch(table, select="*", filter_query="", limit=1000, **kw):
        if table == "sales_orders" and "so_id=eq." in (filter_query or ""):
            if refetch_raise:
                raise RuntimeError("머리글 재조회 실패(시뮬레이션)")
            if refetch_empty:
                return []
        if table == "so_delivery_schedule" and snapshot_raise and "order=sched_id.asc" in (filter_query or ""):
            raise RuntimeError("회차 스냅샷 조회 실패(시뮬레이션)")
        if table == "shipment_revisions" and hist_raise and "action=eq.CANCEL" in (filter_query or ""):
            raise RuntimeError("취소 이력 조회 실패(시뮬레이션)")
        # 루틴 안의 조회만 실패(select rev_id,si_id) — 화면의 D19 조회(select si_id)는 성공 (A6, Codex r4 M1)
        if table == "shipment_revisions" and hist_raise_routine and select == "rev_id,si_id" \
                and "action=eq.CANCEL" in (filter_query or ""):
            raise RuntimeError("취소 이력 조회 실패(루틴 시뮬레이션)")
        if table == "sales_orders":
            st_ = status_refetch if (status_refetch and "so_id=eq." in (filter_query or "")) else status
            return [{"so_id": 100, "so_number": "SO-100", "customer": "㈜엠제이티", "status": st_,
                     "so_date": "2026-08-01", "due_date": None}]
        if table == "sales_order_items" and stale_map and "soi_id=in." in (filter_query or ""):
            return [dict(stale_map.get(l["soi_id"], l)) for l in RV.LINES.values()]
        return real_fetch(table, select, filter_query, limit)
    monkeypatch.setattr(_dbmod, "fetch", _fetch)

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
        if t == "sales_order_items" and "soi_id=eq." in f:
            soi = int(f.split("soi_id=eq.")[1].split("&")[0])
            cur = cur_map.get(soi) or RV.LINES.get(soi)
            if cur is not None:
                # 조건부 갱신: 읽은 status·received 가 현재 라인과 다르면 0행 (운영 PostgREST 와 같은 의미)
                st_ok = f"status=eq.{cur.get('status')}" in f
                rc_ok = ("received_qty=is.null" in f) if cur.get("received_qty") is None \
                    else (f"received_qty=eq.{float(cur['received_qty'])}" in f)
                if not (st_ok and rc_ok):
                    return 0
                cur.update(v)                                   # 목 라인도 바뀐다(2차 취소 시나리오)
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

# ── r4: D18 fail-closed · D19 부분 취소 전표 · 증가 정정 머리글 거부 실제 흐름 ──
def _no_writes():
    assert _line_updates() == []
    assert not [1 for t, recs in RV.INSERTED if t in ("inventory_transactions", "shipment_revisions") and recs]
    assert not [1 for t, f, v in RV.UPDATED if t in ("so_delivery_schedule", "shipments", "sales_orders")]
    assert RV.SHIPMENTS[0]["status"] == "CONFIRMED"


def _errs(at):
    return " ".join(str(getattr(w, "value", "") or "") for w in at.error)


@pytest.mark.parametrize("kw,why", [({"refetch_raise": True}, "머리글 조회 실패"),
                                    ({"refetch_empty": True}, "머리글 없음"),
                                    ({"snapshot_raise": True}, "납품 회차 조회 실패")])
def _seed_two_lines():
    RV._seed()
    RV.LINES[11]["status"] = "PARTIAL"
    RV.LINES[12] = {"soi_id": 12, "so_id": 100, "canonical_pn": "4PDVN-04", "customer_part_no": "X", "customer_item_name": None,
                    "product_id": "P1", "qty": 1000, "received_qty": 200, "pending_qty": 800, "unit": "EA", "unit_price": 1000,
                    "due_date": None, "status": "PARTIAL", "closed_qty": 0}
    RV.SHIP_ITEMS.append({"si_id": 3, "shipment_id": 1, "soi_id": 12, "so_id": 100, "sched_id": None, "product_id": "P1",
                          "pn": "4PDVN-04", "customer_pn": "X", "item_name": None, "customer": "㈜엠제이티", "so_number": "SO-100",
                          "qty": 200, "unit": "EA", "unit_price": 1000})


# P3-1a(2026-11-06): 확정 전표 정정·취소(옛 엔진 _cf_apply_deltas)의 화면 흐름 테스트는 082 revise_shipment 로 바뀌며
# tests/test_revise_screen.py(화면) · tests/test_revise_golden.py(규칙) · tests/test_revise_shipment_local.py(SQL)로 이식:
#   R1 닫힌 머리글 취소 → test_d15_closed_header_cancel / g_edit_decrease_d15_first_close
#   H-2 읽은 뒤 종결 → test_header_closed_after_render_applies_d15 · 활성 머리글 → test_cancel_reverses_and_keeps_number
#   S3 ④ 종결 머리글 증가 → test_edit_increase_on_closed_header_rejected / g_reject_line_closed_increase
#   S2/D19 부분 취소 → test_c9_partial_cancel_locks_both / g_reject_partial_cancel_legacy(정정·취소 모두 거부로 바뀜)
#   S1/D18 조회 실패 → test_check_failure_fail_closed · test_c8_unavailable_blocks_without_old_engine
#   R2/D16 조건부 갱신 0행·H2 is.null·B-1 부분 중단 — 한 트랜잭션(L2~L9)·SQL COALESCE 로 대체(부분 반영 상태가 없음)
