# -*- coding: utf-8 -*-
"""출고 확정 응답 불명(RPC 전송 오류·비정상 응답) 처리 — P3-0 v2 (2026-10-26).

계획서 `_P3-0_출고확정_응답불명_계획서_20261026.md` §7 상태 기계:
① 1차 rpc → ok 완료 / Rejected 중단 / Unavailable 6단계 / Transport·비정상 응답 → ②
② 재조회(cache=False) → CONFIRMED 완료(알림 구분) / DRAFT_WITH_TRACES·CANCELLED·UNKNOWN 중단 /
   DRAFT_CLEAN → 한 번 더 → ③
③ 2차 rpc(같은 payload) → ok 완료 / Transport·Unavailable → ④ / Rejected → 재조회 1회 → CONFIRMED 만 완료
④ 중단 + log_error("rpc_unknown"). 자동 3차 없음.

목 DB(test_bulk_delivery)는 잠금을 흉내 내지 못한다 — '늦은 커밋'은 rpc 목이 예외를 던지기 전에
전표를 CONFIRMED·흔적 생성으로 바꾸는 것으로 모사한다. 실제 잠금 직렬화는 T8(로컬 복원 DB).
"""
import ast
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from tests.test_bulk_delivery import (   # noqa: E402  (fixture·헬퍼 재사용)
    ship_db, _open_shipping, _register, _fetch as _base_fetch,
    SHIPMENTS, SHIP_ITEMS, INSERTED, UPDATED, streamlit_available)

APP_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "streamlit_app.py")
WRITE_TABLES = ("sales_order_items", "so_delivery_schedule", "shipment_allocations",
                "inventory_transactions", "sales_orders", "shipments")
TWICE = "출고 확정 응답을 두 번 받지 못했습니다"
RETRY_REJECTED = "재시도는 거부됐으나 최초 요청 반영 여부 미확인"
SEEN = "확정 확인됨(응답 지연)"


def _writes():
    return ([(t, f) for t, f, v in UPDATED if t in WRITE_TABLES]
            + [(t, None) for t, recs in INSERTED if t in WRITE_TABLES])


class World:
    """목 DB 위 상태: RPC 호출·'늦은 커밋'·흔적·로그·슬랙 알림을 기록한다."""

    def __init__(self, ship_db, monkeypatch):
        self.db = ship_db
        self.calls, self.applied = [], 0
        self.allocs, self.issues = [], []
        self.logs, self.notify = [], []
        self.head_raise = self.head_empty = self.trace_raise = False
        mp = monkeypatch

        def _fetch(table, select="*", filter_query="", limit=1000, **kw):
            if table == "shipments" and "shipment_id=eq." in filter_query and kw.get("cache") is False:
                if self.head_raise:
                    raise RuntimeError("머리글 조회 실패(시뮬레이션)")
                if self.head_empty:
                    return []
            if table == "shipment_allocations":
                if self.trace_raise:
                    raise RuntimeError("흔적 조회 실패(시뮬레이션)")
                return list(self.allocs)
            if table == "inventory_transactions" and "txn_type=eq.ISSUE" in filter_query:
                if self.trace_raise:
                    raise RuntimeError("흔적 조회 실패(시뮬레이션)")
                return list(self.issues)
            return _base_fetch(table, select, filter_query, limit)
        mp.setattr(ship_db, "fetch", _fetch)
        mp.setattr(ship_db, "log_error", lambda kind, detail, **k: self.logs.append((kind, str(detail))) or True)
        import utils.slack_notify as _sk
        mp.setattr(_sk, "notify", lambda *a, **k: self.notify.append(a) or True)

    # ── 'DB 함수가 실제로 한 일' 모사 ──
    def commit(self, traces=True):
        """confirm_shipment 가 커밋됐다: 머리글 CONFIRMED + (제품·회차 있으면) 충당·ISSUE."""
        self.applied += 1
        SHIPMENTS[0]["status"] = "CONFIRMED"
        if traces:
            self.allocs.append({"alloc_id": 900 + self.applied, "si_id": SHIP_ITEMS[0]["si_id"]})
            self.issues.append({"txn_id": 900 + self.applied, "ref_id": SHIP_ITEMS[0]["si_id"], "qty": -1})

    def rpc_seq(self, *steps):
        """steps[i] = i번째 호출 때 할 일(callable(world) → 반환값 또는 예외)."""
        def _rpc(name, params=None, **kw):
            self.calls.append((name, params))
            i = len(self.calls) - 1
            step = steps[min(i, len(steps) - 1)]
            return step(self)
        return _rpc

    def unknown_logs(self):
        return [d for k, d in self.logs if k == "rpc_unknown"]


def _transport(w):
    raise w.db.RpcTransportError("confirm_shipment: ReadTimeout")


def _commit_then_transport(w):
    w.commit()
    raise w.db.RpcTransportError("confirm_shipment: ReadTimeout")


def _ok_commit(w):
    w.commit()
    return {"ok": True, "lines": 3, "sois": 2, "allocs": 3, "txns": 3, "skipped": [],
            "unallocated": [], "confirmed_at": "2026-10-26T00:00:00+00:00"}


def _reject(code, msg, status=None):
    def _f(w):
        if status:
            SHIPMENTS[0]["status"] = status
        raise w.db.RpcRejected(code, msg)
    return _f


def _ret(value):
    return lambda w: value


@pytest.fixture(autouse=True)
def _no_wait(monkeypatch):
    monkeypatch.setenv("WS_CF_RECHECK_SEC", "0")     # 재조회 대기 2초 생략


def _confirm(ship_db, monkeypatch, world, rpc_impl, register=True):
    if register:
        at = _open_shipping(ship_db)
        _register(at)
        UPDATED.clear(); INSERTED.clear()
    monkeypatch.setattr(ship_db, "rpc", rpc_impl)
    at2 = _open_shipping(ship_db, "slip")
    at2.button(key="cf_go").click()
    at2.run()
    assert not at2.exception, [str(e.value) for e in at2.exception]
    return at2


def _errs(at):
    return " ".join(str(e.value) for e in at.error)


def _succ(at):
    return " ".join(str(s.value) for s in at.success)


pytestmark = pytest.mark.skipif(not streamlit_available, reason="streamlit 미설치 — AppTest 불가")


# ── T1 재조회 분류: CONFIRMED 만 완료 ────────────────────────────────

@pytest.mark.parametrize("case", ["confirmed_traces", "confirmed_no_traces", "draft_traces", "cancelled"])
def test_t1_first_unknown_then_recheck_classification(ship_db, monkeypatch, case):
    w = World(ship_db, monkeypatch)

    def _first(w):
        if case == "confirmed_traces":
            w.commit(traces=True)
        elif case == "confirmed_no_traces":       # 제품·회차 없는 전표 — 흔적 없이 CONFIRMED
            w.commit(traces=False)
        elif case == "draft_traces":               # 기존 경로 부분 반영 같은 상태(머리글 DRAFT + 충당)
            w.allocs.append({"alloc_id": 1, "si_id": SHIP_ITEMS[0]["si_id"]})
        elif case == "cancelled":
            SHIPMENTS[0]["status"] = "CANCELLED"
        raise w.db.RpcTransportError("confirm_shipment: ReadTimeout")
    at2 = _confirm(ship_db, monkeypatch, w, w.rpc_seq(_first))
    assert len(w.calls) == 1, "재조회만으로 판정 — 재호출 없음"
    assert _writes() == [], "앱 직접 쓰기 0 (기존 6단계 금지)"
    if case.startswith("confirmed"):
        assert SEEN in _succ(at2) and not at2.error
        assert w.notify == [], "재조회 확인은 슬랙 알림 없음(다른 세션 확정일 수 있음)"
        assert at2.session_state["ship_open_no"] == SHIPMENTS[0]["ship_no"]
    else:
        assert SEEN not in _succ(at2) and "출고 확정 —" not in _succ(at2)
        assert ("일부 반영 흔적" if case == "draft_traces" else "다른 곳에서 취소") in _errs(at2)
        assert w.notify == []


# ── T2 1차 불명 + 커밋 없음 → 2차 같은 payload 로 반영 ────────────────────

def test_t2_retry_same_payload_applies_once(ship_db, monkeypatch):
    w = World(ship_db, monkeypatch)
    at2 = _confirm(ship_db, monkeypatch, w, w.rpc_seq(_transport, _ok_commit))
    assert len(w.calls) == 2 and w.calls[0] == w.calls[1], "2차는 같은 payload"
    assert w.applied == 1 and _writes() == []
    assert "출고 확정 —" in _succ(at2) and not at2.error
    assert len(w.notify) == 1, "이번 호출이 반영 → 슬랙 알림 1회"
    assert len(w.unknown_logs()) == 1


# ── T3 2차 거부는 재조회 계기 — CONFIRMED 일 때만 완료 ─────────────────────

@pytest.mark.parametrize("second,status,done", [
    (("P0001", "not_draft:CONFIRMED"), "CONFIRMED", True),    # 1차가 그 사이 커밋(늦은 커밋)
    (("P0001", "not_draft:CANCELLED"), "CANCELLED", False),
    (("P0001", "already_applied"), None, False),              # 머리글 DRAFT 그대로
    (("P0001", "stale"), None, False),                        # 다른 전표 반영으로 미납 변경
    (("55P03", "lock timeout"), None, False),                 # 잠금 대기 초과 — 1차 불명은 남음(M2)
])
def test_t3_second_rejected_rechecks(ship_db, monkeypatch, second, status, done):
    w = World(ship_db, monkeypatch)
    at2 = _confirm(ship_db, monkeypatch, w, w.rpc_seq(_transport, _reject(*second, status=status)))
    assert len(w.calls) == 2 and _writes() == []
    if done:
        assert SEEN in _succ(at2) and not at2.error and w.notify == []
    else:
        assert RETRY_REJECTED in _errs(at2)
        assert "출고 확정 —" not in _succ(at2) and SEEN not in _succ(at2) and w.notify == []


# ── T4 2차도 불명 → 중단, 재진입은 ①부터·중복 0 ────────────────────────

@pytest.mark.parametrize("second", ["transport", "unavailable"])
def test_t4_second_unknown_stops(ship_db, monkeypatch, second):
    w = World(ship_db, monkeypatch)
    step2 = _transport if second == "transport" else (lambda w: (_ for _ in ()).throw(w.db.RpcUnavailable("x")))
    at2 = _confirm(ship_db, monkeypatch, w, w.rpc_seq(_transport, step2))
    assert len(w.calls) == 2, "자동 3차 없음"
    assert TWICE in _errs(at2)
    assert _writes() == [] and SHIPMENTS[0]["status"] == "DRAFT", "2차 Unavailable 이어도 기존 6단계 금지"
    assert len(w.unknown_logs()) == 2 and w.notify == []
    # 사용자가 다시 누르면 ① 부터 — 이번엔 정상 반영, 중복 0
    at3 = _confirm(ship_db, monkeypatch, w, w.rpc_seq(_ok_commit), register=False)
    assert w.applied == 1 and _writes() == [] and len(w.calls) == 3
    assert "출고 확정 —" in _succ(at3) and len(w.notify) == 1


# ── T5 조회 실패는 재호출하지 않고 중단 ──────────────────────────────

@pytest.mark.parametrize("fail,text", [
    ("head_raise", "전표 상태도 읽지 못했습니다"),
    ("head_empty", "전표 상태도 읽지 못했습니다"),
    ("trace_raise", "흔적(충당·재고 차감) 조회에 실패"),
])
def test_t5_lookup_failure_stops_without_retry(ship_db, monkeypatch, fail, text):
    w = World(ship_db, monkeypatch)

    def _first(w):
        setattr(w, fail, True)                     # 응답 불명 뒤의 재조회부터 실패
        raise w.db.RpcTransportError("confirm_shipment: ConnectionError")
    at2 = _confirm(ship_db, monkeypatch, w, w.rpc_seq(_first))
    assert len(w.calls) == 1 and _writes() == []
    assert text in _errs(at2) and w.notify == []


# ── T6 비정상 정상응답도 불명 + 정적 검사 ────────────────────────────

@pytest.mark.parametrize("value", [None, {}, {"ok": False}, [], "ok"])
def test_t6_abnormal_success_body_is_unknown(ship_db, monkeypatch, value):
    w = World(ship_db, monkeypatch)
    at2 = _confirm(ship_db, monkeypatch, w, w.rpc_seq(_ret(value)))
    assert len(w.calls) == 2 and TWICE in _errs(at2)
    assert _writes() == [] and SHIPMENTS[0]["status"] == "DRAFT" and w.notify == []


def _func_src(src, name):
    tree = ast.parse(src)
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return ast.get_source_segment(src, n)
    raise AssertionError(name)


def test_t6_static_legacy_only_on_unavailable_and_helpers_write_nothing():
    src = open(APP_FILE, encoding="utf-8").read()
    lines = src.split("\n")
    hits = [i for i, l in enumerate(lines) if "_cf_legacy = True" in l]
    assert len(hits) == 1, hits
    assert 'elif _cf_r["state"] == "unavailable":' in lines[hits[0] - 1]
    for fn in ("_cf_confirm_via_rpc", "_cf_head_state"):
        body = _func_src(src, fn)
        for w_ in (".update(", ".insert(", ".delete(", "update_count(", "_cf_set_status_if_draft("):
            assert w_ not in body, (fn, w_)
    head = _func_src(src, "_cf_head_state")
    assert head.count("cache=False") >= 2            # 머리글 + 흔적(_cf_draft_applied) 모두 캐시 우회
    body = _func_src(src, "_cf_confirm_via_rpc")
    assert body.count('_db.rpc("confirm_shipment"') == 1 and body.count("= _call()") == 2   # 최대 2회
    assert "rpc_unknown" in body and "RpcUnavailable" in body


# ── T7 후처리 횟수 (기존 경로·성공·재조회 확인) ───────────────────────

def test_t7_ok_path_flash_and_notify_once(ship_db, monkeypatch):
    w = World(ship_db, monkeypatch)
    at2 = _confirm(ship_db, monkeypatch, w, w.rpc_seq(_ok_commit))
    assert len(w.calls) == 1 and len(w.notify) == 1
    assert _succ(at2).count("출고 확정 —") == 1 and not at2.error


def test_t7_default_fixture_is_unavailable_legacy_path(ship_db, monkeypatch):
    """공통 fixture 기본 RPC = RpcUnavailable → 기존 6단계가 반영(M3). 알림 1회."""
    w = World(ship_db, monkeypatch)
    at = _open_shipping(ship_db)
    _register(at)
    UPDATED.clear(); INSERTED.clear()
    at2 = _open_shipping(ship_db, "slip")
    at2.button(key="cf_go").click()
    at2.run()
    assert not at2.exception
    assert SHIPMENTS[0]["status"] == "CONFIRMED" and any(t == "sales_order_items" for t, _ in _writes())
    assert len(w.notify) == 1 and w.unknown_logs() == []
