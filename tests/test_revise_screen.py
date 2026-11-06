# -*- coding: utf-8 -*-
"""확정 전표 정정·취소 화면 흐름(새 경로) — P3-1a 커밋 5(이 시점 실패) (계획서 §4-6 · §18 A6·A9·A14 · 지시문 §6).

목 DB = tests/ship_mock.ReviseMock(가짜 revise_shipment · 뷰 shipment_revise_blockers_v = 파이썬 모델, select 적용). 옛 엔진(_cf_apply_deltas)의
화면 흐름 테스트(test_shipment_revision_flow · test_so_close_revision)에서 정정·취소 엔진을 타던 것을 새 경로 기대값으로
옮기고(이식 표는 패키지 README), qa REQUIRED C1~C9 · Codex REQUIRED 5·6 · 「그린 뒤 데이터가 바뀌고 클릭」을 더한다.
버튼 키는 그대로(cf_rv_go · cf_cancel — 작성중 취소와 공용, §18 A14).
"""
import copy
import importlib.util
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
APP_FILE = os.path.join(ROOT, "streamlit_app.py")
pytestmark = pytest.mark.skipif(importlib.util.find_spec("streamlit") is None, reason="streamlit 미설치 — AppTest 불가")

from tests.test_revise_legacy_characterize import (SID, SHIP_NO, base_world, _soi, _rd, _si, _tx)  # noqa: E402

REASON = "거래처 착오"


def _w(**patch):
    w = base_world()
    w.update(patch)
    return w


def _hdr(status, so=100):
    return {"so_id": so, "so_number": f"SO-{so}", "customer": "㈜엠제이티", "status": status, "so_date": "2026-10-01",
            "due_date": None, "remark": None, "total_amount": 0}


def _open(monkeypatch, m, clock=None):
    import db as _dbmod
    from streamlit.testing.v1 import AppTest
    from tests.conftest import goto
    m.install(monkeypatch, _dbmod)
    monkeypatch.setenv("WS_CF_RECHECK_SEC", "0")
    if clock is not None:
        import utils.shipment_revise as SRm
        monkeypatch.setattr(SRm, "_clock", clock)
    at = AppTest.from_file(APP_FILE, default_timeout=120)
    at.secrets["supabase"] = {"url": "https://mock.local", "anon_key": "a", "service_role_key": "s"}
    at.secrets["auth"] = {"disabled": True}
    at.run()
    goto(at, "ship", "slip")
    next(r for r in at.radio if r.key == "cf_filter").set_value("확정")
    at.session_state["ship_open_no"] = SHIP_NO
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def _texts(at):
    return [str(x.value) for x in list(at.error) + list(at.warning) + list(at.success) + list(at.info)
            + list(at.toast)]


def _cancel(at, reason=REASON, sid=SID):
    at.text_input(key=f"cf_cx_reason_{sid}").set_value(reason)
    at.run()
    at.button(key="cf_cancel").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    at.button(key="cf_cancel_cfm_ok").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]


def _edit(at, m, new_rows, reason=REASON, sid=SID, confirm=True):
    """data_editor 편집(세션 주입) → 사유 → [정정 적용] → (확인 창) [실행 확정]."""
    rev = next(s for s in m.tables["shipments"] if s["shipment_id"] == sid).get("rev_no") or 0
    items = sorted([x for x in m.tables["shipment_items"] if x["shipment_id"] == sid], key=lambda x: x["si_id"])
    at.session_state[f"cf_rv_ed_{sid}_{rev}"] = {
        "edited_rows": {[x["si_id"] for x in items].index(si): {"정정 수량": q} for si, q in new_rows.items()},
        "added_rows": [], "deleted_rows": []}
    at.text_input(key=f"cf_rv_reason_{sid}").set_value(reason)
    at.run()
    at.button(key="cf_rv_go").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    if confirm:
        at.button(key="cf_rv_cfm_ok").click()
        at.run()
        assert not at.exception, [str(e.value) for e in at.exception]


def _inflight(at):
    return at.session_state["cf_rv_inflight"] if "cf_rv_inflight" in at.session_state else None


def _ship(m, sid=SID):
    return next(s for s in m.tables["shipments"] if s["shipment_id"] == sid)


def _revise_calls(m):
    return [c for c in m.rpc_calls if c[0] == "revise_shipment"]


# ── 이식: 취소·정정 결과(옛 test_confirmed_cancel_reverses_delta_and_keeps_number 등) ──
def test_cancel_reverses_and_keeps_number(monkeypatch):
    from tests.ship_mock import ReviseMock
    m = ReviseMock(_w())
    at = _open(monkeypatch, m)
    _cancel(at)
    calls = _revise_calls(m)
    assert len(calls) == 1 and calls[0][1]["p_payload"]["action"] == "CANCEL", calls
    sh = _ship(m)
    assert (sh["status"], sh["ship_no"], sh["rev_no"], sh["cancel_reason"]) == ("CANCELLED", SHIP_NO, 1, REASON)
    assert sorted((t["lot_number"], t["qty"]) for t in m.tables["inventory_transactions"] if t["qty"] > 0) == \
        [("W01", 300), ("W02", 200)]                                           # 양수 ISSUE = 복원
    assert not m.tables["shipment_allocations"]
    assert next(r for r in m.tables["so_delivery_schedule"] if r["sched_id"] == 1)["delivered_qty"] == 0
    li = m.tables["sales_order_items"][0]
    assert (li["received_qty"], li["pending_qty"], li["status"]) == (0, 2000, "PENDING")
    revs = m.tables["shipment_revisions"]
    assert len(revs) == 1 and revs[0]["action"] == "CANCEL" and revs[0]["request_id"], revs
    assert (revs[0]["si_id"], revs[0]["qty_before"], revs[0]["qty_after"], revs[0]["reason"]) == \
        (501, 500, 0, REASON), revs                                            # 옛 단언(이력 500→0·사유) 이식(r1 QA M4)
    assert next(x for x in m.tables["shipment_items"] if x["si_id"] == 501)["qty"] == 500   # 라인 수량은 기록으로 보존
    assert any("취소" in t for t in _texts(at)), _texts(at)


def test_edit_decrease_via_editor(monkeypatch):
    from tests.ship_mock import ReviseMock
    m = ReviseMock(_w())
    at = _open(monkeypatch, m)
    _edit(at, m, {501: 400})
    p = _revise_calls(m)[0][1]["p_payload"]
    assert p["action"] == "EDIT" and p["lines"] == [{"si_id": 501, "qty_before": 500.0, "qty_after": 400.0}], p
    assert "inc" not in p or not (p.get("inc") or {}).get("txns"), p                  # 감소는 서버가 계산
    assert next(x for x in m.tables["shipment_items"] if x["si_id"] == 501)["qty"] == 400
    assert _ship(m)["rev_no"] == 1 and _ship(m)["status"] == "CONFIRMED"
    assert any("정정 완료" in t for t in _texts(at)), _texts(at)


def test_edit_increase_payload_planned_by_screen(monkeypatch):
    """증가는 화면이 계획(069 형식) — 회차·충당·LOT, expected_received_before 는 증가하는 수주 라인마다 1개."""
    from tests.ship_mock import ReviseMock
    m = ReviseMock(_w())
    at = _open(monkeypatch, m)
    _edit(at, m, {501: 700})
    inc = _revise_calls(m)[0][1]["p_payload"]["inc"]
    assert inc["expected_received_before"] == [{"soi_id": 11, "received": 500.0}], inc
    assert inc["scheds"] == [{"sched_id": 2, "soi_id": 11, "delta": 200.0}], inc
    assert [t["lot_number"] for t in inc["txns"]] == ["W03"], inc
    assert m.tables["sales_order_items"][0]["received_qty"] == 700


def test_d15_closed_header_cancel(monkeypatch):
    """옛 R1: 종결 수주(머리글 CLOSED) 완납 라인 취소 → 라인 CLOSED·pending 0·closed_qty 500, 머리글 유지."""
    from tests.ship_mock import ReviseMock
    m = ReviseMock(_w(sales_orders=[_hdr("CLOSED")], sales_order_items=[_soi(11, 100, "P1", "4PDVN-03", 500, 500)],
                      so_delivery_schedule=[_rd(1, 11, 1, "2026-11-01", 500, 500)]))
    at = _open(monkeypatch, m)
    _cancel(at)
    li = m.tables["sales_order_items"][0]
    assert (li["status"], li["pending_qty"], li["closed_qty"], li["received_qty"]) == ("CLOSED", 0, 500, 0), li
    assert li["closed_rounds"] == [{"sched_id": 1, "qty_before": 500, "delivered": 500}]
    assert m.tables["sales_orders"][0]["status"] == "CLOSED"


def test_header_closed_after_render_applies_d15(monkeypatch):
    """옛 H-2 · 지시문 §6: 전표를 연 뒤 수주가 종결됨 → 클릭 → 서버가 잠금 뒤 값으로 D15 적용."""
    from tests.ship_mock import ReviseMock
    m = ReviseMock(_w(sales_order_items=[_soi(11, 100, "P1", "4PDVN-03", 500, 500)],
                      so_delivery_schedule=[_rd(1, 11, 1, "2026-11-01", 500, 500)]))
    at = _open(monkeypatch, m)
    at.text_input(key=f"cf_cx_reason_{SID}").set_value(REASON)
    at.run()
    m.tables["sales_orders"][0]["status"] = "CLOSED"                 # 다른 세션이 종결
    at.button(key="cf_cancel").click()
    at.run()
    at.button(key="cf_cancel_cfm_ok").click()
    at.run()
    li = m.tables["sales_order_items"][0]
    assert (li["status"], li["closed_qty"]) == ("CLOSED", 500), li


def test_edit_increase_on_closed_header_rejected(monkeypatch):
    """옛 S3 ④: 종결 머리글 아래 라인의 증가 → line_closed 거부 문구, 쓰기 0."""
    from tests.ship_mock import ReviseMock
    m = ReviseMock(_w(sales_orders=[_hdr("CLOSED")]))
    before = m.snapshot()
    at = _open(monkeypatch, m)
    _edit(at, m, {501: 600})
    assert m.snapshot() == before
    assert any("종결" in t and "아무것도 바뀌지 않았습니다" in t for t in _texts(at)), _texts(at)


# ── 「그린 뒤 데이터가 바뀌고 클릭」(지시문 §6) ──
def test_other_session_revised_after_render_then_click(monkeypatch):
    from tests.ship_mock import ReviseMock
    m = ReviseMock(_w())
    at = _open(monkeypatch, m)
    at.text_input(key=f"cf_cx_reason_{SID}").set_value(REASON)
    at.run()
    at.button(key="cf_cancel").click()
    at.run()
    _ship(m)["rev_no"] = 1                                              # 다른 세션이 먼저 정정
    before = m.snapshot()
    at.button(key="cf_cancel_cfm_ok").click()
    at.run()
    assert m.snapshot() == before
    assert any("다른 사용자" in t for t in _texts(at)), _texts(at)


def test_other_session_cancelled_after_render_then_click(monkeypatch):
    from tests.ship_mock import ReviseMock
    m = ReviseMock(_w())
    at = _open(monkeypatch, m)
    at.session_state[f"cf_rv_ed_{SID}_0"] = {"edited_rows": {0: {"정정 수량": 400}}, "added_rows": [], "deleted_rows": []}
    at.text_input(key=f"cf_rv_reason_{SID}").set_value(REASON)
    at.run()
    at.button(key="cf_rv_go").click()
    at.run()
    _ship(m)["status"] = "CANCELLED"                                    # 다른 세션이 먼저 취소
    before = m.snapshot()
    at.button(key="cf_rv_cfm_ok").click()
    at.run()
    assert m.snapshot() == before
    assert any("이미 취소" in t or "확정 전표가 아닙" in t for t in _texts(at)), _texts(at)


# ── qa REQUIRED C1~C9 ──
def test_c1_response_lost_then_replay_applies_once(monkeypatch):
    from tests.ship_mock import ReviseMock
    m = ReviseMock(_w())
    m.faults = ["transport_after"]
    at = _open(monkeypatch, m)
    _cancel(at)
    calls = _revise_calls(m)
    assert len(calls) == 2 and calls[0][1]["p_payload"]["request_id"] == calls[1][1]["p_payload"]["request_id"]
    assert m.applied == 1 and _ship(m)["status"] == "CANCELLED"
    assert len([t for t in m.tables["inventory_transactions"] if t["qty"] > 0]) == 2      # 이중 복원 없음
    assert any("취소" in t for t in _texts(at))


def test_c2_unknown_then_reject_requery_decides_pending(monkeypatch):
    """불명(반영 없음) 뒤 재호출이 거부 → 재조회에 없음 → 확인 대기: 버튼 잠금·[결과 다시 확인], 「반영되지 않았습니다」 아님."""
    from tests.ship_mock import ReviseMock
    m = ReviseMock(_w())
    m.faults = ["transport_before", "na:55P03", "na:55P03", "na:55P03"]
    at = _open(monkeypatch, m)
    _cancel(at)
    t = " ".join(_texts(at))
    assert "확인하지 못했습니다" in t and "반영되지 않았습니다" not in t, t
    assert (_inflight(at) or {}).get("shipment_id") == SID
    assert at.button(key="cf_cancel").disabled
    assert [b for b in at.button if b.key == "cf_rv_recheck"]


def test_c3_abnormal_body_then_ok(monkeypatch):
    from tests.ship_mock import ReviseMock
    m = ReviseMock(_w())
    m.faults = ["abnormal"]
    at = _open(monkeypatch, m)
    _cancel(at)
    assert m.applied == 1 and _ship(m)["status"] == "CANCELLED", m.rpc_calls


def test_c5_new_request_id_each_click(monkeypatch):
    from tests.ship_mock import ReviseMock
    m = ReviseMock(_w())
    at = _open(monkeypatch, m)
    _edit(at, m, {501: 400}, confirm=False)
    r1 = at.session_state["cf_rv_plan"]["request_id"]
    at.button(key="cf_rv_cfm_no").click()
    at.run()
    _edit(at, m, {501: 400}, confirm=False)
    r2 = at.session_state["cf_rv_plan"]["request_id"]
    assert r1 != r2 and not _revise_calls(m)


def test_c6_switching_shipment_drops_confirm(monkeypatch):
    """전표 A 의 정정 확인 창 상태에서 B 가 선택되면 B 에 확인 창이 없고, A 의 계획으로 B 를 실행하지 않는다."""
    from tests.ship_mock import ReviseMock
    w = _w()
    w["shipments"].append(dict(w["shipments"][0], shipment_id=49, ship_no="SH-20261101-02"))   # 기본 정렬에서 A 뒤
    w["shipment_items"].append(dict(_si(491, 11, 100, 1, "P1", "4PDVN-03", 100), shipment_id=49))
    m = ReviseMock(w)
    at = _open(monkeypatch, m)
    _edit(at, m, {501: 400}, confirm=False)
    at.session_state["ship_open_no"] = "SH-20261101-02"
    at.run()
    assert not [b for b in at.button if b.key == "cf_rv_cfm_ok"], "B 에 확인 창"
    assert not _revise_calls(m)


def test_c7_info_shown_after_rerun_with_part_number(monkeypatch):
    """부분 미충당 라인 취소 → 안내(미충당 100)가 rerun 뒤 화면에 남고 품번으로."""
    from tests.ship_mock import ReviseMock
    m = ReviseMock(_w(sales_order_items=[_soi(11, 100, "P1", "4PDVN-03", 2000, 1400)],
                      so_delivery_schedule=[_rd(1, 11, 1, "2026-11-01", 1300, 1300)],
                      shipment_items=[_si(501, 11, 100, 1, "P1", "4PDVN-03", 1400)],
                      shipment_allocations=[{"alloc_id": 1, "si_id": 501, "sched_id": 1, "qty": 1300}],
                      inventory_transactions=[_tx(1, 501, "W01", -1400)]))
    at = _open(monkeypatch, m)
    _cancel(at)
    t = " ".join(_texts(at))
    assert "4PDVN-03" in t and "100" in t and "회차" in t, t


def test_c8_unavailable_blocks_without_old_engine(monkeypatch):
    from tests.ship_mock import ReviseMock
    m = ReviseMock(_w())
    m.check_unavailable = True
    before = m.snapshot()
    at = _open(monkeypatch, m)
    assert at.button(key="cf_cancel").disabled and at.button(key="cf_rv_go").disabled
    assert any("관리자" in t for t in _texts(at)), _texts(at)
    assert m.snapshot() == before
    src = open(APP_FILE, encoding="utf-8").read()
    assert "def _cf_apply_deltas(" not in src and "plan_round_release" not in src     # 옛 엔진·추정 분기 부재


def test_c9_partial_cancel_locks_both(monkeypatch):
    from tests.ship_mock import ReviseMock
    m = ReviseMock(_w(shipment_revisions=[{"rev_id": 1, "shipment_id": SID, "rev_no": 1, "action": "CANCEL",
                                           "si_id": 501, "pn": "4PDVN-03", "qty_before": 500, "qty_after": 0,
                                           "reason": "옛 취소", "created_by": "테스트", "request_id": None,
                                           "info": None}]))
    at = _open(monkeypatch, m)
    assert at.button(key="cf_cancel").disabled and at.button(key="cf_rv_go").disabled
    assert any("관리자" in t and "부분" in t for t in _texts(at)), _texts(at)


def test_check_failure_fail_closed(monkeypatch):
    """사전 점검(revise_shipment_check) 조회 실패 → 정정·취소 모두 잠금(D18 fail-closed)."""
    from tests.ship_mock import ReviseMock
    m = ReviseMock(_w())
    m.check_fail = True
    at = _open(monkeypatch, m)
    assert at.button(key="cf_cancel").disabled and at.button(key="cf_rv_go").disabled
    assert any("확인하지 못했습니다" in t for t in _texts(at)), _texts(at)


# ── 데이터 사유 선차단(§4-5 · §18 A9 · r1 회신 3) ──
def test_blocked_line_locks_cancel_and_lists_all_reasons(monkeypatch):
    """한 라인에 issue_mismatch·round_short 두 사유 → 안내에 둘 다, 취소 잠금, 다른 라인 정정은 가능."""
    from tests.ship_mock import ReviseMock
    w = _w(sales_order_items=[_soi(11, 100, "P1", "4PDVN-03", 2000, 600)],
           so_delivery_schedule=[_rd(1, 11, 1, "2026-11-01", 500, 400), _rd(2, 11, 2, "2026-11-10", 500, 100)],
           shipment_items=[_si(501, 11, 100, 1, "P1", "4PDVN-03", 500), _si(502, 11, 100, 2, "P1", "4PDVN-03", 100)],
           shipment_allocations=[{"alloc_id": 1, "si_id": 501, "sched_id": 1, "qty": 500},
                                 {"alloc_id": 2, "si_id": 502, "sched_id": 2, "qty": 100}],
           inventory_transactions=[_tx(1, 501, "W01", -450), _tx(2, 502, "W02", -100)])
    m = ReviseMock(w)
    at = _open(monkeypatch, m)
    t = " ".join(_texts(at))
    assert "재고 차감" in t and "회차" in t and SHIP_NO in t, t
    assert at.button(key="cf_cancel").disabled
    _edit(at, m, {502: 50})                                             # 사유 없는 라인 정정은 통과
    assert next(x for x in m.tables["shipment_items"] if x["si_id"] == 502)["qty"] == 50


def test_editing_blocked_line_is_refused_on_screen(monkeypatch):
    from tests.ship_mock import ReviseMock
    w = _w(inventory_transactions=[_tx(1, 501, "W01", -450)])      # 501 = issue_mismatch
    m = ReviseMock(w)
    at = _open(monkeypatch, m)
    at.session_state[f"cf_rv_ed_{SID}_0"] = {"edited_rows": {0: {"정정 수량": 400}}, "added_rows": [], "deleted_rows": []}
    at.text_input(key=f"cf_rv_reason_{SID}").set_value(REASON)
    at.run()
    assert at.button(key="cf_rv_go").disabled
    assert not _revise_calls(m)


# ── Codex REQUIRED 5: 지연 커밋 ──
def test_delayed_commit_pending_then_recheck_success_once(monkeypatch):
    """첫 호출 미커밋(응답 유실) → 재호출 미반영 확정 반복 → 재조회 없음 → 확인 대기(버튼 잠금·기록 유지) → 이후 커밋
    → [결과 다시 확인] → 성공 안내 1회. 20초 규칙은 시계 주입."""
    from tests.ship_mock import ReviseMock
    clock = {"t": 1000.0}
    m = ReviseMock(_w())
    m.faults = ["hold", "na:55P03", "na:55P03", "na:55P03"]
    at = _open(monkeypatch, m, clock=lambda: clock["t"])
    _cancel(at)
    assert (_inflight(at) or {}).get("shipment_id") == SID and at.button(key="cf_cancel").disabled
    m.commit_held()                                                     # 늦게 커밋됨
    clock["t"] += 3
    at.button(key="cf_rv_recheck").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    t = " ".join(_texts(at))
    assert "취소" in t and "반영" in t, t
    assert not _inflight(at)
    assert m.applied == 1


def test_pending_twenty_seconds_then_not_applied(monkeypatch):
    from tests.ship_mock import ReviseMock
    clock = {"t": 1000.0}
    m = ReviseMock(_w())
    m.faults = ["transport_before", "transport_before"]
    at = _open(monkeypatch, m, clock=lambda: clock["t"])
    _cancel(at)
    assert _inflight(at)
    clock["t"] += 19
    at.button(key="cf_rv_recheck").click()
    at.run()
    assert _inflight(at), "20초 전에는 확인 대기 유지(r2)"
    clock["t"] += 2
    at.button(key="cf_rv_recheck").click()
    at.run()
    t = " ".join(_texts(at))
    assert "20초 동안 기록이 없습니다" in t and "반영되지 않은 것으로 보입니다" in t, t
    assert not _inflight(at), "확인 대기 기록이 지워져야 한다"
    assert not at.button(key="cf_cancel").disabled
    assert m.applied == 0


# ── 이식: §5-2 확인 창 전표 단위·사유 필수(옛 test_cancel_gate_is_scoped_to_slip_and_needs_reason) ──
def test_cancel_gate_is_scoped_to_slip_and_needs_reason(monkeypatch):
    """전표 A 의 취소 확인 창 상태에서 B(작성중)가 선택되면 B 에 확인 창이 없고 아무것도 취소되지 않는다. A 로 돌아와도
    다시 눌러야 뜬다. 사유가 비면 플래그가 있어도 확인 창이 없다. 정상 경로(사유 + 확인)는 동작."""
    from tests.ship_mock import ReviseMock
    w = _w()
    w["shipments"].append(dict(w["shipments"][0], shipment_id=49, ship_no="SH-20261031-01", status="DRAFT",
                               confirmed_at=None))
    m = ReviseMock(w)
    at = _open(monkeypatch, m)
    next(r for r in at.radio if r.key == "cf_filter").set_value("전체")

    def _show(no):
        at.session_state["ship_open_no"] = no
        at.run()
        assert not at.exception, [str(e.value) for e in at.exception]
    A, B = SHIP_NO, "SH-20261031-01"
    _show(A)
    at.text_input(key=f"cf_cx_reason_{SID}").set_value(REASON)
    _show(A)
    at.button(key="cf_cancel").click()
    _show(A)
    assert [b for b in at.button if b.key == "cf_cancel_cfm_ok"], "A 확인 창"
    _show(B)
    assert not [b for b in at.button if b.key == "cf_cancel_cfm_ok"], "B 에 확인 창 없음"
    assert not _revise_calls(m) and _ship(m)["status"] == "CONFIRMED"
    _show(A)
    assert not [b for b in at.button if b.key == "cf_cancel_cfm_ok"], "다른 전표 선택으로 A 플래그 정리"
    at.session_state[f"cfm_cf_cancel_{SID}"] = {"request_id": "6f1c1d2e-0000-4000-8000-000000000001", "rev_no": 0}
    _show(A)
    assert not [b for b in at.button if b.key == "cf_cancel_cfm_ok"], "사유 없음 → 확인 창 없음"
    at.text_input(key=f"cf_cx_reason_{SID}").set_value(REASON)
    _show(A)
    at.button(key="cf_cancel_cfm_ok").click()
    _show(A)
    assert _ship(m)["status"] == "CANCELLED" and len(_revise_calls(m)) == 1


# ── 이식: 정정 준비 조회 절단(옛 test_hotfix2_2nd_f_in_chunks::test_revision_prep_*) ──
@pytest.mark.parametrize("table", ["inventory_transactions", "shipment_allocations"])
def test_revision_prep_truncation_calls_nothing(monkeypatch, table):
    """증가 계획용 조회(충당·ISSUE)가 잘리면 정정 중단 — RPC 호출 0·쓰기 0."""
    import db
    from tests.ship_mock import ReviseMock
    m = ReviseMock(_w())
    at = _open(monkeypatch, m)
    real = db.fetch_all

    def _w2(t, select="*", filter_query="", *a, **kw):
        rows, tr = real(t, select, filter_query, *a, **kw)
        return rows, (tr or t == table)
    monkeypatch.setattr(db, "fetch_all", _w2)
    before = m.snapshot()
    _edit(at, m, {501: 700})
    assert any("정정 준비 조회" in t for t in _texts(at)), _texts(at)
    assert not _revise_calls(m) and m.snapshot() == before


# ── 이식: 출하 품번 병기(옛 test_pn_display::test_cancel_warning_label*) — 선차단 안내의 라인 표기 ──
@pytest.mark.parametrize("variants", [True, False])
def test_blocked_notice_uses_variant_label(monkeypatch, variants):
    from tests.ship_mock import ReviseMock
    m = ReviseMock(_w(inventory_transactions=[]))                     # 차감 기록 없음 → issue_mismatch
    if variants:
        m.tables["customer_part_mapping"] = [{"product_id": "P1", "customer_part_no": "4S4PDVN-03", "kind": "variant"}]
    at = _open(monkeypatch, m)
    t = "\n".join(_texts(at))
    head = "- 4PDVN-03 (4S4PDVN-03) · 수주 SO-100" if variants else "- 4PDVN-03 · 수주 SO-100"
    assert any(l.startswith(head) for l in t.splitlines()), t


def test_mock_returns_only_selected_columns():
    """r1 QA B1 — 화면이 select 하지 않은 열(shipment_id)을 build_payload 가 써서 운영에서만 KeyError 가 나던 것.
    ReviseMock 은 PostgREST 처럼 select 한 열만 돌려줘야 화면 테스트가 같은 결함을 잡는다."""
    from tests.ship_mock import ReviseMock
    m = ReviseMock(_w())
    assert m.apply_select is True
    row = m.fetch("shipment_items", "si_id,qty", f"shipment_id=eq.{SID}")[0]
    assert set(row) == {"si_id", "qty"}, row


def test_recheck_lookup_failure_keeps_pending(monkeypatch):
    """r1 Codex H1·QA H1: 반영됐는데 응답 유실 → 재조회도 실패 → 확인 대기. 20초가 지나도 이력 조회가 실패하면
    「반영되지 않았습니다」가 아니라 조회 실패 안내 + 기록·잠금 유지. 조회가 살아나면 성공 안내 1회."""
    from tests.ship_mock import ReviseMock
    clock = {"t": 1000.0}
    m = ReviseMock(_w())
    m.faults = ["transport_after", "transport_before"]
    at = _open(monkeypatch, m, clock=lambda: clock["t"])
    m.fetch_raise_for = "shipment_revisions"                            # 이력 조회 실패(망·스키마 캐시)
    _cancel(at)
    assert m.applied == 1 and _ship(m)["status"] == "CANCELLED"        # 서버에는 반영됨(확정 목록에서 빠짐)
    assert (_inflight(at) or {}).get("shipment_id") == SID
    assert [b for b in at.button if b.key == "cf_rv_recheck"]
    clock["t"] += 21
    at.button(key="cf_rv_recheck").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    t = " ".join(_texts(at))
    assert "조회하지 못했습니다" in t and "반영되지 않은 것으로" not in t, t
    assert (_inflight(at) or {}).get("shipment_id") == SID, "조회 실패로 확인 대기 기록을 지우면 안 된다"
    m.fetch_raise_for = None
    clock["t"] += 5
    at.button(key="cf_rv_recheck").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    t = " ".join(_texts(at))
    assert "취소" in t and "반영" in t and "반영되지 않은 것으로" not in t, t
    assert not _inflight(at) and m.applied == 1


def test_pending_on_other_shipment_locks_this_one(monkeypatch):
    """r1 Codex H2·QA M1: 다른 전표의 확인 대기가 있으면 이 전표의 정정·취소도 잠근다(대기 기록이 덮이지 않게).
    확인 플래그를 억지로 넣어도 RPC 를 부르지 않고, 남의 대기 기록도 그대로."""
    from tests.ship_mock import ReviseMock
    m = ReviseMock(_w())
    at = _open(monkeypatch, m)
    other = {"shipment_id": 777, "ship_no": "SH-20261105-09", "request_id": "11111111-2222-4333-8444-555555555555",
             "action": "CANCEL", "since": 0.0, "summary": {}, "items": []}
    at.text_input(key=f"cf_cx_reason_{SID}").set_value(REASON)       # 사유가 있어야 잠금이 「대기」 때문임을 본다
    at.run()
    assert not at.button(key="cf_cancel").disabled, "대기 없음 + 사유 있음이면 취소 버튼이 열려 있어야(대조)"
    at.session_state["cf_rv_inflight"] = dict(other)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert at.button(key="cf_cancel").disabled, "다른 전표의 확인 대기 중엔 이 전표 취소도 잠겨야 한다"
    assert any("SH-20261105-09" in x and "모든 전표" in x for x in _texts(at)), _texts(at)
    at.session_state[f"cfm_cf_cancel_{SID}"] = {"request_id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee", "rev_no": 0}
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    if [b for b in at.button if b.key == "cf_cancel_cfm_ok"]:
        at.button(key="cf_cancel_cfm_ok").click()
        at.run()
    assert not _revise_calls(m) and m.applied == 0
    assert _inflight(at) == other


def test_pending_does_not_lock_draft_confirm(monkeypatch):
    """r1 분류 H2: 확인 대기가 있어도 작성중 전표의 [출고 확정] 은 잠그지 않는다(정정·취소만 잠금)."""
    from tests.ship_mock import ReviseMock
    w = _w()
    w["shipments"].append(dict(w["shipments"][0], shipment_id=49, ship_no="SH-20261031-01", status="DRAFT",
                               confirmed_at=None))
    w["shipment_items"].append(dict(_si(601, 11, 100, 2, "P1", "4PDVN-03", 50), shipment_id=49))
    m = ReviseMock(w)
    at = _open(monkeypatch, m)
    at.session_state["cf_rv_inflight"] = {"shipment_id": SID, "ship_no": SHIP_NO, "action": "CANCEL", "since": 0.0,
                                          "request_id": "11111111-2222-4333-8444-555555555555", "summary": {},
                                          "items": []}
    next(r for r in at.radio if r.key == "cf_filter").set_value("전체")
    at.session_state["ship_open_no"] = "SH-20261031-01"
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert not at.button(key="cf_go").disabled, "작성중 전표 확정은 확인 대기와 무관"
    assert _inflight(at)["shipment_id"] == SID


def test_partial_cancel_forced_plan_and_flags_do_nothing(monkeypatch):
    """qa M4(옛 D19 단언 이식): 부분 취소 전표에 정정 계획·확인 플래그·취소 플래그를 억지로 넣어도 확인 창이 없고 RPC 0."""
    from tests.ship_mock import ReviseMock
    m = ReviseMock(_w(shipment_revisions=[{"rev_id": 1, "shipment_id": SID, "rev_no": 0, "action": "CANCEL",
                                           "si_id": 501, "pn": "4PDVN-03", "qty_before": 500, "qty_after": 0,
                                           "reason": "옛 취소", "created_by": "테스트", "request_id": None,
                                           "info": None}]))
    at = _open(monkeypatch, m)
    at.session_state["cf_rv_plan"] = {"shipment_id": SID, "rev_no": 0, "request_id": "aaaaaaaa-bbbb-4ccc-8ddd-000000000001",
                                      "new_qtys": {501: 400}, "reason": REASON, "over": False,
                                      "changes": [{"si_id": 501, "before": 500, "after": 400}]}
    at.session_state[f"cfm_cf_rv_{SID}"] = True
    at.session_state[f"cf_cx_reason_{SID}"] = REASON
    at.session_state[f"cfm_cf_cancel_{SID}"] = {"request_id": "aaaaaaaa-bbbb-4ccc-8ddd-000000000002", "rev_no": 0}
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    keys = {b.key for b in at.button}
    assert "cf_rv_cfm_ok" not in keys and "cf_cancel_cfm_ok" not in keys, keys
    assert not _revise_calls(m) and m.applied == 0


def test_recv_null_cancel_rejected_on_screen(monkeypatch):
    """qa M4: 수주 납품량 NULL 라인 취소 → 서버(모델) recv_underflow 거부, 쓰기 0, 사유 문구."""
    from tests.ship_mock import ReviseMock
    m = ReviseMock(_w(sales_order_items=[dict(_soi(11, 100, "P1", "4PDVN-03", 2000, 500), received_qty=None)]))
    at = _open(monkeypatch, m)
    before = copy.deepcopy(m.snapshot())
    _cancel(at)
    assert len(_revise_calls(m)) == 1 and m.applied == 0
    assert m.snapshot() == before
    t = " ".join(_texts(at))
    assert "수주 납품량이 줄일 수량보다 적음" in t and "아무것도 바뀌지 않았습니다" in t, t


def test_render_reads_blockers_view_without_rpc(monkeypatch):
    """qa M3(qa REQUIRED 5): 확정 전표를 그릴 때 사전 점검은 뷰 조회(캐시) — RPC 호출 0(RPC 성공은 앱 캐시를 비운다)."""
    import db as _dbmod
    from tests.ship_mock import ReviseMock
    m = ReviseMock(_w())
    at = _open(monkeypatch, m)
    n = {"clear": 0}
    monkeypatch.setattr(_dbmod, "clear_cache", lambda *a, **k: n.__setitem__("clear", n["clear"] + 1))
    m.rpc_calls.clear()
    m.fetch_calls.clear()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert not m.rpc_calls, m.rpc_calls
    assert ("shipment_revise_blockers_v", f"shipment_id=eq.{SID}") in m.fetch_calls, m.fetch_calls
    assert n["clear"] == 0
    # 대조: 목 install 은 db.rpc 성공 뒤 db.clear_cache 를 부른다(실제 db.rpc 처럼) — RPC 로 점검하면 세어진다
    _dbmod.rpc("revise_shipment_check", {"p_shipment_id": SID})
    assert n["clear"] == 1


def test_blockers_view_missing_is_unavailable(monkeypatch):
    """뷰가 없음(082 미적용 — PostgREST 404 PGRST205) → '서버 함수를 쓸 수 없음' + 정정·취소 잠금(옛 엔진 없음)."""
    from tests.ship_mock import ReviseMock
    from utils.shipment_revise import UNAVAILABLE_TEXT
    m = ReviseMock(_w())
    m.check_unavailable = True
    at = _open(monkeypatch, m)
    assert at.button(key="cf_cancel").disabled and at.button(key="cf_rv_go").disabled
    assert UNAVAILABLE_TEXT in _texts(at), _texts(at)


def _two_ships():
    """전표 A(SID 50, si 501 500) + 전표 B(51, si 511 100, 다른 수주 라인 soi 12)."""
    w = _w()
    w["sales_order_items"].append(_soi(12, 100, "P1", "4PDVN-03", 500, 100))
    w["so_delivery_schedule"].append(_rd(9, 12, 1, "2026-11-02", 100, 100))
    w["shipments"].append(dict(w["shipments"][0], shipment_id=51, ship_no="SH-20261102-01", ship_date="2026-11-02"))
    w["shipment_items"].append(dict(_si(511, 12, 100, 9, "P1", "4PDVN-03", 100), shipment_id=51))
    w["shipment_allocations"].append({"alloc_id": 9, "si_id": 511, "sched_id": 9, "qty": 100})
    w["inventory_transactions"].append(_tx(9, 511, "W05", -100))
    return w


def test_h2_real_flow_pending_a_locks_b_until_resolved(monkeypatch):
    """r3 qa REQUIRED 2: A 취소 응답 불명 → B 를 열어 사유·편집해도 정정·취소 잠김(A 기록 유지, RPC 늘지 않음)
    → 20초 뒤 A 미반영 → B 풀림 → B 취소 반영. A 는 그대로."""
    from tests.ship_mock import ReviseMock
    clock = {"t": 1000.0}
    m = ReviseMock(_two_ships())
    m.faults = ["transport_before", "transport_before"]
    at = _open(monkeypatch, m, clock=lambda: clock["t"])
    A, B = SHIP_NO, "SH-20261102-01"

    def _run(no):                     # 전표가 둘이면 매 rerun 마다 연 전표를 다시 지정(목록 기본 선택에 끌려가지 않게)
        at.session_state["ship_open_no"] = no
        at.run()
        assert not at.exception, [str(e.value) for e in at.exception]

    at.text_input(key=f"cf_cx_reason_{SID}").set_value(REASON)
    _run(A)
    at.button(key="cf_cancel").click()
    _run(A)
    at.button(key="cf_cancel_cfm_ok").click()
    _run(A)
    assert (_inflight(at) or {}).get("shipment_id") == SID and m.applied == 0
    n_calls = len(_revise_calls(m))
    assert n_calls == 2, m.rpc_calls
    _run(B)
    at.text_input(key="cf_cx_reason_51").set_value(REASON)
    at.session_state["cf_rv_ed_51_0"] = {"edited_rows": {0: {"정정 수량": 90}}, "added_rows": [], "deleted_rows": []}
    at.text_input(key="cf_rv_reason_51").set_value(REASON)
    _run(B)
    assert at.button(key="cf_cancel").disabled and at.button(key="cf_rv_go").disabled
    assert _inflight(at)["shipment_id"] == SID and len(_revise_calls(m)) == n_calls
    clock["t"] += 21
    at.button(key="cf_rv_recheck").click()
    _run(B)
    assert not _inflight(at)
    _run(B)
    assert not at.button(key="cf_cancel").disabled, "A 대기가 풀리면 B 취소가 열린다"
    at.button(key="cf_cancel").click()
    _run(B)
    at.button(key="cf_cancel_cfm_ok").click()
    _run(B)
    assert m.applied == 1 and _ship(m, 51)["status"] == "CANCELLED"
    assert _ship(m)["status"] == "CONFIRMED" and _ship(m)["rev_no"] == 0


@pytest.mark.parametrize("action", ["CANCEL", "EDIT"])
def test_cf_rv_run_refuses_when_pending_appears_after_gate(monkeypatch, action):
    """r3 qa REQUIRED 2(이중 거부 분기): 확인 창을 통과한 뒤 호출 직전에 확인 대기 기록이 생기면(같은 세션의 다른
    rerun 모사 — build_payload 를 감싸 그 사이에 기록을 넣음) _cf_rv_run 이 RPC 를 부르지 않고 안내만 한다."""
    import utils.shipment_revise as SRm
    from tests.ship_mock import ReviseMock
    m = ReviseMock(_w())
    at = _open(monkeypatch, m)
    other = {"shipment_id": 777, "ship_no": "SH-20261105-09", "request_id": "11111111-2222-4333-8444-555555555555",
             "action": "CANCEL", "since": 0.0, "summary": {}, "items": []}
    orig = SRm.build_payload

    def _hooked(*a, **k):
        import streamlit as _st
        _st.session_state["cf_rv_inflight"] = dict(other)
        return orig(*a, **k)

    monkeypatch.setattr(SRm, "build_payload", _hooked)
    if action == "CANCEL":
        _cancel(at)
    else:
        _edit(at, m, {501: 400})
    assert not _revise_calls(m) and m.applied == 0
    assert any("이전 요청의 결과를 확인하기 전에는" in t for t in _texts(at)), _texts(at)
    assert _inflight(at) == other


@pytest.mark.parametrize("action", ["CANCEL", "EDIT"])
def test_payload_guard_failure_shows_error_logs_and_calls_nothing(monkeypatch, action):
    """r3 qa REQUIRED 4: build_payload 가 실패하면 안내 + 오류 기록 1건, RPC 0, 확인 플래그 남지 않음."""
    import utils.shipment_revise as SRm
    from tests.ship_mock import ReviseMock
    m = ReviseMock(_w())
    at = _open(monkeypatch, m)

    def _boom(*a, **k):
        raise ValueError("build_payload: 전표 라인에 shipment_id 가 없음")

    monkeypatch.setattr(SRm, "build_payload", _boom)
    if action == "CANCEL":
        _cancel(at)
        word, flag = "취소", f"cfm_cf_cancel_{SID}"
    else:
        _edit(at, m, {501: 400})
        word, flag = "정정", f"cfm_cf_rv_{SID}"
    assert not _revise_calls(m) and m.applied == 0
    assert any(f"{word} 내용을 준비하지 못했습니다" in t for t in _texts(at)), _texts(at)
    assert len([e for e in m.log_errors if f"{word} 준비 실패" in e[1]]) == 1, m.log_errors
    assert flag not in at.session_state or not at.session_state[flag]


def test_lookup_failure_five_times_keeps_pending_and_escalates_text(monkeypatch):
    """r3 qa REQUIRED 3·M1: 이력 조회 실패 5회 연속 → 기록·잠금 유지, 예외 없음, 3회째부터 직접 확인 안내, 매번 오류 기록."""
    from tests.ship_mock import ReviseMock
    from utils.shipment_revise import LOOKUP_FAILED_MANY_TEXT, LOOKUP_FAILED_TEXT
    clock = {"t": 1000.0}
    m = ReviseMock(_w())
    m.faults = ["transport_before", "transport_before"]
    at = _open(monkeypatch, m, clock=lambda: clock["t"])
    m.fetch_raise_for = "shipment_revisions"
    _cancel(at)
    assert _inflight(at)
    clock["t"] += 30
    for i in range(1, 6):
        at.button(key="cf_rv_recheck").click()
        at.run()
        assert not at.exception, [str(e.value) for e in at.exception]
        t = " ".join(_texts(at))
        assert (LOOKUP_FAILED_MANY_TEXT in t) if i >= 3 else (LOOKUP_FAILED_TEXT in t), (i, t)
        assert "반영되지 않은 것으로" not in t
        assert (_inflight(at) or {}).get("lookup_fails") == i
    assert at.button(key="cf_cancel").disabled
    assert len([e for e in m.log_errors if "lookup_failed" in e[1]]) == 5, m.log_errors
