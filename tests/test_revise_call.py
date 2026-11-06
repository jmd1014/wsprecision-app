# -*- coding: utf-8 -*-
"""정정·취소 호출 상태 기계·문구 — P3-1a 커밋 5(이 시점 실패) (계획서 §4-6 · §18 A6).

호출별 분류 4가지: 성공 / 거부(P0001) / 미반영 확정(40P01·55P03·57014 — 같은 request_id 로 자동 재시도 최대 2회) /
불명(전송 오류·비정상 본문). 불명이 한 번이라도 있었으면 최종 판정은 request_id 재조회로만 하고, 없으면 '확인 대기'
(마지막 호출 시작 뒤 10초가 지나 재조회에 없으면 미반영 확정).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db  # noqa: E402


class Clock:
    def __init__(self):
        self.t = 1000.0
        self.slept = []

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.slept.append(s)
        self.t += s


def _seq(*outs):
    """호출마다 outs 를 차례로: dict = 반환, Exception = 발생."""
    calls = []

    def call():
        o = outs[min(len(calls), len(outs) - 1)]
        calls.append(o)
        if isinstance(o, BaseException):
            raise o
        return o
    call.calls = calls
    return call


OK = {"ok": True, "replayed": False, "action": "CANCEL", "rev_no": 1, "info": []}
REPLAY = {"ok": True, "replayed": True, "action": "CANCEL", "rev_no": 1, "info": []}


def _run(call, found=None, clock=None):
    from utils.shipment_revise import run_call
    clock = clock or Clock()
    return run_call(call, lambda: found, clock.sleep, clock), clock


def test_ok_first_call():
    r, _ = _run(_seq(OK))
    assert r["state"] == "ok" and r["res"] == OK and not r["unknown"]


def test_p0001_rejected_without_retry():
    call = _seq(db.RpcRejected("P0001", "stale_rev"))
    r, _ = _run(call)
    assert (r["state"], r["code"]) == ("rejected", "stale_rev") and len(call.calls) == 1


@pytest.mark.parametrize("code", ["40P01", "55P03", "57014"])
def test_not_applied_retried_then_ok(code):
    call = _seq(db.RpcRejected(code, "lock"), OK)
    r, clock = _run(call)
    assert r["state"] == "ok" and len(call.calls) == 2 and clock.slept, r


def test_not_applied_three_times_is_not_applied():
    call = _seq(db.RpcRejected("55P03", "lock"))
    r, _ = _run(call)
    assert r["state"] == "not_applied" and len(call.calls) == 3, (r, call.calls)     # 첫 호출 + 재시도 2회


def test_unknown_then_ok_on_retry_is_ok():
    """C1: 응답 유실 → 같은 request_id 로 재호출 → replayed(반영 1회)."""
    call = _seq(db.RpcTransportError("timeout"), REPLAY)
    r, _ = _run(call)
    assert r["state"] == "ok" and r["unknown"] and r["res"]["replayed"]


def test_unknown_then_reject_decided_by_requery_found():
    """C2: 불명 뒤 거부 → 재조회로 판정 — 이력에 있으면 성공."""
    call = _seq(db.RpcTransportError("timeout"), db.RpcRejected("P0001", "stale_rev"))
    r, _ = _run(call, found={"rev_no": 1, "action": "CANCEL", "info": []})
    assert r["state"] == "ok" and r["unknown"] and r["via"] == "requery", r


def test_unknown_then_reject_not_found_is_pending():
    """C2: 불명 뒤 거부 → 재조회에 없음 → '확인 대기'(반영되지 않았다고 말하지 않는다)."""
    call = _seq(db.RpcTransportError("timeout"), db.RpcRejected("P0001", "stale_rev"))
    r, clock = _run(call)
    assert r["state"] == "pending" and r["unknown"] and r["started_at"] <= clock.t, r


@pytest.mark.parametrize("body", [None, {}, {"ok": False}, [1]])
def test_abnormal_body_is_unknown(body):
    """C3: 비정상 본문은 불명 — 재호출 ok 면 성공, 아니면 재조회."""
    call = _seq(body, OK)
    r, _ = _run(call)
    assert r["state"] == "ok" and r["unknown"], r
    call = _seq(body, body)
    r, _ = _run(call)
    assert r["state"] == "pending", r


def test_unavailable_first_is_blocked():
    """C8: 함수 없음(첫 호출) → 차단(옛 경로로 넘어가지 않음)."""
    r, _ = _run(_seq(db.RpcUnavailable("revise_shipment")))
    assert r["state"] == "unavailable"


def test_recheck_ten_second_rule():
    """Codex REQUIRED 5: 확인 대기 → 10초 전 재조회 없음 = 계속 대기, 10초 뒤 없음 = 미반영 확정, 있으면 성공."""
    from utils.shipment_revise import recheck
    assert recheck(lambda: None, started_at=100.0, now=105.0)["state"] == "pending"
    assert recheck(lambda: None, started_at=100.0, now=110.5)["state"] == "not_applied"
    assert recheck(lambda: {"rev_no": 2, "action": "EDIT", "info": []}, started_at=100.0, now=101.0)["state"] == "ok"


def test_lookup_failure_is_never_not_applied():
    """r1 Codex H1·QA H1: 이력 조회 실패(LOOKUP_FAILED)는 「기록 없음」이 아니다 — 시간이 지나도 미반영 확정 금지."""
    from utils.shipment_revise import LOOKUP_FAILED, recheck
    assert not LOOKUP_FAILED
    for now in (101.0, 110.5, 10_000.0):
        r = recheck(lambda: LOOKUP_FAILED, started_at=100.0, now=now)
        assert r == {"state": "pending", "lookup_failed": True}, (now, r)
    assert recheck(lambda: None, started_at=100.0, now=105.0) == {"state": "pending", "lookup_failed": False}


def test_run_call_unknown_then_lookup_failure_is_pending():
    """불명 뒤 재조회 실패 → pending(lookup_failed) — ok·not_applied 로 바뀌지 않는다."""
    from utils.shipment_revise import LOOKUP_FAILED, run_call
    r = run_call(_seq(RuntimeError("reset"), RuntimeError("reset")), lambda: LOOKUP_FAILED, lambda s: None,
                 clock=lambda: 0.0)
    assert r["state"] == "pending" and r["lookup_failed"] is True and r["unknown"], r


# ── 문구 ──
def test_reject_texts_cover_codes():
    from utils.shipment_revise import reject_text
    codes = ["bad_version", "not_found", "not_confirmed:CANCELLED", "stale_rev", "stale_line", "stale",
             "request_conflict", "month_closed", "partial_cancel_legacy", "legacy_no_alloc", "issue_mismatch",
             "round_short", "recv_underflow", "use_cancel", "reason_required", "nothing_to_apply", "line_mismatch",
             "line_unlinked", "line_closed", "over_pending", "sched_mismatch", "sched_over", "alloc_mismatch",
             "txn_mismatch", "stock:P1", "postcondition:line_state"]
    for c in codes:
        t = reject_text(c)
        assert t and "아무것도 바뀌지 않았습니다" in t, (c, t)
    assert "다른 사용자" in reject_text("stale_rev")
    assert "P1" in reject_text("stock:P1")


def test_blocked_notice_lists_every_reason_per_line():
    """검토 세션 r1 회신 3: 한 라인에 사유가 여러 개면 전부(첫 사유만이 아니라)."""
    from utils.shipment_revise import blocked_notice
    items = [{"si_id": 35, "pn": "4PDVN-02", "so_number": "SO-1", "qty": 2016},
             {"si_id": 37, "pn": "4PDVN-02", "so_number": "SO-1", "qty": 2016}]
    t = blocked_notice("SH-20260817-01", items, {"35": ["issue_mismatch", "round_short"], "37": ["issue_mismatch"]})
    line35 = next(l for l in t.splitlines() if "2,016" in l and "회차" in l)
    assert "재고 차감" in line35 and "회차" in line35, t
    for s in ("SH-20260817-01", "아무것도 바뀌지 않았습니다", "다른 라인", "관리자", "전표번호", "원하는 결과", "사유"):
        assert s in t, (s, t)


def test_info_text_names_part_numbers():
    """안내 키(감소 = si_id, 증가 미충당 = soi_id)를 화면 문구에서 품번으로."""
    from utils.shipment_revise import info_text
    items = [{"si_id": 501, "soi_id": 11, "pn": "4PDVN-03"}, {"si_id": 502, "soi_id": 12, "pn": "4PDVN-05"}]
    t = info_text([{"si_id": 501, "kind": "unallocated", "qty": 100},
                   {"soi_id": 12, "kind": "unallocated", "qty": 30}], items)
    assert "4PDVN-03" in t and "100" in t and "4PDVN-05" in t and "30" in t, t
