# -*- coding: utf-8 -*-
"""출고 확정 RPC 경로 (migration 069 confirm_shipment, 2026-10-13).

test_bulk_delivery 의 상태 저장 mock 을 그대로 쓴다. 폴백(기존 6단계) 경로는
그 파일의 확정 테스트가 고정하고, 여기서는 ① RPC payload(증감값) 내용과 "쓰기 없음",
② 거부 → 무반영, ③ 응답 불명 + 흔적 → 폴백 금지, ④ 함수 없음 → 폴백(전송 오류는 P3-0
부터 폴백 금지 — tests/test_shipment_confirm_unknown.py), ⑤ 미납 초과는 RPC 호출 전 중단을 검증한다.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from tests.test_bulk_delivery import (   # noqa: E402  (fixture·헬퍼 재사용)
    ship_db, _open_shipping, _register, _fetch as _base_fetch,
    SHIPMENTS, SHIP_ITEMS, INSERTED, UPDATED, LINES, streamlit_available)

pytestmark = pytest.mark.skipif(
    not streamlit_available, reason="streamlit 미설치 — AppTest 불가")


@pytest.fixture(autouse=True)
def _no_recheck_wait(monkeypatch):
    monkeypatch.setenv("WS_CF_RECHECK_SEC", "0")    # P3-0 재조회 대기(2초)를 테스트에서 생략

WRITE_TABLES = ("sales_order_items", "so_delivery_schedule",
                "shipment_allocations", "inventory_transactions",
                "sales_orders", "shipments")


def _writes():
    return ([(t, f) for t, f, v in UPDATED if t in WRITE_TABLES]
            + [(t, None) for t, recs in INSERTED if t in WRITE_TABLES])


def _confirm_with_rpc(ship_db, monkeypatch, rpc_impl):
    at = _open_shipping(ship_db)
    _register(at)
    UPDATED.clear(); INSERTED.clear()
    monkeypatch.setattr(ship_db, "rpc", rpc_impl)
    at2 = _open_shipping(ship_db, "slip")
    at2.button(key="cf_go").click()
    at2.run()
    assert not at2.exception, [str(e.value) for e in at2.exception]
    return at2


def test_rpc_payload_is_deltas_and_nothing_is_written_directly(ship_db, monkeypatch):
    """RPC 성공: payload 는 증감값(라인·회차·충당·LOT ISSUE), 앱은 6개 테이블에
    직접 쓰지 않는다. 같은 입력의 폴백 경로(test_bulk_delivery)와 수치가 같다."""
    calls = []

    def _rpc(name, params=None, **kw):
        calls.append((name, params))
        SHIPMENTS[0]["status"] = "CONFIRMED"      # DB 함수가 머리글까지 바꾼 상태
        return {"ok": True, "lines": 3, "sois": 2, "allocs": 3, "txns": 3,
                "skipped": [], "confirmed_at": "2026-10-13T00:00:00+00:00"}
    at2 = _confirm_with_rpc(ship_db, monkeypatch, _rpc)

    assert len(calls) == 1 and calls[0][0] == "confirm_shipment"
    p = calls[0][1]["p_payload"]
    assert calls[0][1]["p_shipment_id"] == SHIPMENTS[0]["shipment_id"]
    assert p["v"] == 1 and p["allow_over"] is False
    # 라인: 회차 단위 전표 라인 3줄 (soi 11: 500+200, soi 12: 200), 렌더 시점 기납품
    by_soi = {}
    for l in p["lines"]:
        by_soi.setdefault(l["soi_id"], []).append(l)
    assert sorted(x["qty"] for x in by_soi[11]) == [200, 500]
    assert [x["qty"] for x in by_soi[12]] == [200]
    assert {x["expected_received_before"] for x in by_soi[11]} == {0}
    assert {x["expected_received_before"] for x in by_soi[12]} == {100}
    assert all(x["qty"] == next(i["qty"] for i in SHIP_ITEMS
                                if i["si_id"] == x["si_id"])
               for x in p["lines"]), "payload qty = 전표 라인 qty (깎지 않음)"
    # 회차 증감: 1:+500, 3:+200, 2:+200 (기존 100 → 300)
    assert {s["sched_id"]: s["delta"] for s in p["scheds"]} == {1: 500, 3: 200, 2: 200}
    assert all(s["delta"] > 0 for s in p["scheds"])
    # 충당: 회차별 합 = 증감, si 별 합 ≤ 라인 qty
    per_sched = {}
    for a in p["allocs"]:
        per_sched[a["sched_id"]] = per_sched.get(a["sched_id"], 0) + a["qty"]
    assert per_sched == {1: 500, 3: 200, 2: 200}
    # ISSUE: 전표 라인(si)별 합 = −qty, LOT FIFO, 제품 일치
    per_si = {}
    for t in p["txns"]:
        per_si[t["si_id"]] = per_si.get(t["si_id"], 0) + t["qty"]
        assert t["qty"] < 0 and t["product_id"] in ("P1", "P2")
    assert per_si == {l["si_id"]: -l["qty"] for l in p["lines"]}
    p1 = [t for t in p["txns"] if t["product_id"] == "P1"]
    assert sum(-t["qty"] for t in p1) == 700
    assert sum(-t["qty"] for t in p1 if t["lot_number"] == "20260801-001") == 600
    assert sum(-t["qty"] for t in p1 if t["lot_number"] == "20260803-001") == 100
    # 앱은 직접 쓰지 않았다
    assert _writes() == []
    # 성공 뒤 st.rerun() 이라 success 요소는 남지 않는다 — 전표 열림 상태로 판정
    assert at2.session_state["ship_open_no"] == SHIPMENTS[0]["ship_no"]


def test_rpc_rejected_writes_nothing_and_explains(ship_db, monkeypatch):
    def _rpc(name, params=None, **kw):
        raise ship_db.RpcRejected("P0001", "stale")
    at2 = _confirm_with_rpc(ship_db, monkeypatch, _rpc)
    assert _writes() == []
    assert any("다른 사용자" in e.value and "stale" in e.value for e in at2.error)
    assert not at2.success
    assert SHIPMENTS[0]["status"] == "DRAFT"


def test_rpc_unknown_response_with_traces_does_not_fall_back(ship_db, monkeypatch):
    """RPC 가 실제로 반영했는데 응답이 None/유실 → 흔적이 보이면 기존 경로로 가지
    않는다 (2026-10-12 QA 리뷰 BLOCKER: 이중 반영 방지)."""
    traces, calls = [], []

    def _fetch(table, select="*", filter_query="", limit=1000, **kw):
        if table == "shipment_allocations":
            return list(traces)
        return _base_fetch(table, select, filter_query, limit)
    monkeypatch.setattr(ship_db, "fetch", _fetch)

    def _rpc(name, params=None, **kw):
        calls.append(name)
        traces.append({"alloc_id": 1, "si_id": SHIP_ITEMS[0]["si_id"]})
        return None
    at2 = _confirm_with_rpc(ship_db, monkeypatch, _rpc)
    assert _writes() == [] and len(calls) == 1            # DRAFT + 흔적 → 재호출 금지(P3-0)
    assert any("일부 반영 흔적" in e.value for e in at2.error)
    assert not at2.success


@pytest.mark.parametrize("exc_name", ["RpcUnavailable"])
def test_rpc_unavailable_without_traces_falls_back(ship_db, monkeypatch, exc_name):
    """함수 없음(RpcUnavailable 1차)만 기존 6단계 — 전송 오류는 P3-0 부터 폴백 금지."""
    def _rpc(name, params=None, **kw):
        raise getattr(ship_db, exc_name)("mock")
    at2 = _confirm_with_rpc(ship_db, monkeypatch, _rpc)
    soi11 = [v for t, f, v in UPDATED if t == "sales_order_items" and "soi_id=eq.11" in f]
    assert soi11 and soi11[-1]["received_qty"] == 700
    txns = [r for t, recs in INSERTED if t == "inventory_transactions" for r in recs]
    assert sum(-r["qty"] for r in txns if r["product_id"] == "P1") == 700
    assert SHIPMENTS[0]["status"] == "CONFIRMED"
    assert at2.session_state["ship_open_no"] == SHIPMENTS[0]["ship_no"]


def test_legacy_issue_rows_are_per_shipment_line(ship_db, monkeypatch):
    """폴백 경로도 ISSUE 를 전표 라인(si)별로 나눈다 — 취소가 si 의 ref_id 로 LOT 를
    복원하므로 (2026-10-13 Data 리뷰 H-1, 종전엔 soi 의 첫 줄에 몰아 기록)."""
    def _rpc(name, params=None, **kw):
        raise ship_db.RpcUnavailable("mock")
    _confirm_with_rpc(ship_db, monkeypatch, _rpc)
    txns = [r for t, recs in INSERTED if t == "inventory_transactions" for r in recs]
    per_si = {}
    for r in txns:
        per_si[r["ref_id"]] = per_si.get(r["ref_id"], 0) - r["qty"]
    expected = {i["si_id"]: i["qty"] for i in SHIP_ITEMS if i.get("product_id")}
    assert per_si == expected


def test_over_pending_is_blocked_before_rpc(ship_db, monkeypatch):
    """렌더 뒤·클릭 전에 다른 출고로 미납이 줄면 깎아서 반영하지 않고 중단한다
    (화면 사전 검사는 통과한 상태 — 확정 직전 재조회에서만 줄어든 경우)."""
    calls = []

    def _rpc(name, params=None, **kw):
        calls.append(name)
        return {"ok": True, "sois": 2}
    at = _open_shipping(ship_db)
    _register(at)
    UPDATED.clear(); INSERTED.clear()
    monkeypatch.setattr(ship_db, "rpc", _rpc)

    def _fetch(table, select="*", filter_query="", limit=1000):
        rows = _base_fetch(table, select, filter_query, limit)
        # 확정 핸들러의 재조회(select 에 unit 포함)만 미납이 줄어든 값을 돌려준다
        if table == "sales_order_items" and "unit" in select:
            for r in rows:
                if r["soi_id"] == 11:
                    r["received_qty"], r["pending_qty"] = 1900, 100
        return rows
    monkeypatch.setattr(ship_db, "fetch", _fetch)
    at2 = _open_shipping(ship_db, "slip")
    at2.button(key="cf_go").click()
    at2.run()
    assert not at2.exception, [str(e.value) for e in at2.exception]
    assert calls == [] and _writes() == []
    assert any("확정 중단" in e.value for e in at2.error)


# ─── 2026-10-13 Data 리뷰(069 구현) 반영 ───
def test_transport_error_rechecks_bypass_cache_every_time(ship_db, monkeypatch):
    """응답 불명 재조회는 매 회차 cache=False (P3-0 v2 M1 — clear_cache 1회로는 2회째가
    60초 캐시를 읽는다). 전송 오류 뒤 기존 경로로 가지 않는다."""
    seen = []

    def _fetch(table, select="*", filter_query="", limit=1000, **kw):
        if table in ("shipments", "inventory_transactions", "shipment_allocations") \
                and ("shipment_id=eq." in filter_query or "ref_id=in." in filter_query
                     or "si_id=in." in filter_query):
            seen.append((table, kw.get("cache")))
        return _base_fetch(table, select, filter_query, limit)
    monkeypatch.setattr(ship_db, "fetch", _fetch)

    def _rpc(name, params=None, **kw):
        raise ship_db.RpcTransportError("timeout")
    _confirm_with_rpc(ship_db, monkeypatch, _rpc)
    heads = [c for t, c in seen if t == "shipments"]
    assert len(heads) >= 2 and all(c is False for c in heads), seen   # 재조회 2회 이상, 전부 캐시 우회
    assert all(c is False for t, c in seen if t != "shipments" and c is not None)
    assert _writes() == [] and SHIPMENTS[0]["status"] == "DRAFT"      # 폴백 없음


def test_unknown_response_with_confirmed_header_does_not_fall_back(ship_db, monkeypatch):
    """함수가 커밋돼 머리글이 CONFIRMED 인데 응답만 유실 → 폴백 금지, 재조회로 확정 확인
    (P3-0: '확정 확인됨(응답 지연)' 안내, 재호출 없음)."""
    calls = []

    def _rpc(name, params=None, **kw):
        calls.append(name)
        SHIPMENTS[0]["status"] = "CONFIRMED"
        return None
    at2 = _confirm_with_rpc(ship_db, monkeypatch, _rpc)
    assert _writes() == [] and len(calls) == 1
    assert not at2.error
    assert any("확정 확인됨(응답 지연)" in s.value for s in at2.success)


def test_unknown_response_with_unreadable_header_does_not_fall_back(ship_db, monkeypatch):
    """머리글을 못 읽으면(None) 불명 그대로 중단 — 제품·회차 없는 전표는 흔적으로
    가릴 수 없다 (M-4)."""
    calls = []

    def _fetch(table, select="*", filter_query="", limit=1000, **kw):
        if table == "shipments" and "shipment_id=eq." in filter_query and kw.get("cache") is False:
            return []              # 재조회에서 머리글을 못 읽는 상황
        return _base_fetch(table, select, filter_query, limit)
    monkeypatch.setattr(ship_db, "fetch", _fetch)

    def _rpc(name, params=None, **kw):
        calls.append(name)
        return None
    at2 = _confirm_with_rpc(ship_db, monkeypatch, _rpc)
    assert _writes() == [] and len(calls) == 1            # 읽기도 안 되면 재호출하지 않는다
    assert any("전표 상태도 읽지 못했습니다" in e.value for e in at2.error)


def test_fallback_skips_issue_rows_of_failed_so_line(ship_db, monkeypatch):
    """폴백에서 수주 라인 갱신이 실패한 soi 의 재고 차감은 넣지 않는다 (H-1)."""
    from tests import test_bulk_delivery as _m

    def _update(table, filter_query, fields):
        if table == "sales_order_items" and "soi_id=eq.11" in filter_query:
            UPDATED.append((table, filter_query, fields))
            return False
        return _m._update(table, filter_query, fields)
    monkeypatch.setattr(ship_db, "update", _update)

    def _rpc(name, params=None, **kw):
        raise ship_db.RpcUnavailable("mock")
    _confirm_with_rpc(ship_db, monkeypatch, _rpc)
    txns = [r for t, recs in INSERTED if t == "inventory_transactions" for r in recs]
    assert not any(r["product_id"] == "P1" for r in txns), "soi 11(P1) ISSUE 없음"
    assert sum(-r["qty"] for r in txns if r["product_id"] == "P2") == 200


def test_schedule_fetch_failure_aborts_before_rpc(ship_db, monkeypatch):
    """회차 조회 실패를 '회차 없음'으로 보지 않고 중단한다 (H-3)."""
    calls = []

    def _rpc(name, params=None, **kw):
        calls.append(name)
        return {"ok": True, "sois": 2}
    at = _open_shipping(ship_db)
    _register(at)
    UPDATED.clear(); INSERTED.clear()
    monkeypatch.setattr(ship_db, "rpc", _rpc)

    def _fetch(table, select="*", filter_query="", limit=1000):
        if table == "so_delivery_schedule" and "soi_id=eq." in filter_query:
            raise RuntimeError("mock: schedule fetch failed")
        return _base_fetch(table, select, filter_query, limit)
    monkeypatch.setattr(ship_db, "fetch", _fetch)
    at2 = _open_shipping(ship_db, "slip")
    at2.button(key="cf_go").click()
    at2.run()
    assert not at2.exception, [str(e.value) for e in at2.exception]
    assert calls == [] and _writes() == []
    assert any("확정 중단" in e.value and "회차 조회 실패" in e.value for e in at2.error)


# ─── 2026-10-13 QA 리뷰(069 구현) 반영 ───
@pytest.mark.parametrize("code,msg,expect", [
    ("P0001", "not_draft:CONFIRMED", "이미 확정 또는 취소"),
    ("P0001", "already_applied", "반영 흔적"),
    ("P0001", "stock:P2", "완성 재고 부족 — P2"),
    ("P0001", "line_mismatch", "전표 라인이 화면과 다릅니다"),
    ("55P03", "canceling statement due to lock timeout", "잠시 후 다시"),
    ("P0001", "sched_over", "다른 사용자"),
])
def test_reject_messages_and_no_writes(ship_db, monkeypatch, code, msg, expect):
    def _rpc(name, params=None, **kw):
        raise ship_db.RpcRejected(code, msg)
    at2 = _confirm_with_rpc(ship_db, monkeypatch, _rpc)
    assert _writes() == []
    assert any(expect in e.value for e in at2.error), [e.value for e in at2.error]
    assert SHIPMENTS[0]["status"] == "DRAFT"
    assert "cf_alloc_warn" not in at2.session_state or not at2.session_state["cf_alloc_warn"]


def test_double_click_calls_rpc_once(ship_db, monkeypatch):
    calls = []

    def _rpc(name, params=None, **kw):
        calls.append(name)
        return {"ok": True, "sois": 2}      # 전표 mock 은 DRAFT 로 둔다
    at = _open_shipping(ship_db)
    _register(at)
    monkeypatch.setattr(ship_db, "rpc", _rpc)
    at2 = _open_shipping(ship_db, "slip")
    at2.button(key="cf_go").click()
    at2.run()
    assert not at2.exception
    if [b for b in at2.button if b.key == "cf_go"]:
        at2.button(key="cf_go").click()
        at2.run()
        assert not at2.exception
    assert len(calls) == 1, "5초 이중 클릭 가드"


def test_rpc_and_fallback_produce_same_rows(ship_db, monkeypatch):
    """같은 입력으로 RPC payload 와 폴백 경로의 결과 집합을 프로그램으로 비교한다
    (계획서 T-A1 — 회귀 스위트 상시)."""
    captured = []

    def _rpc_ok(name, params=None, **kw):
        captured.append(params["p_payload"])
        SHIPMENTS[0]["status"] = "CONFIRMED"
        return {"ok": True, "sois": 2}
    _confirm_with_rpc(ship_db, monkeypatch, _rpc_ok)
    payload = captured[0]
    # 같은 상태로 다시 등록해 폴백 경로 실행
    SHIPMENTS.clear(); SHIP_ITEMS.clear(); UPDATED.clear(); INSERTED.clear()

    def _rpc_unavail(name, params=None, **kw):
        raise ship_db.RpcUnavailable("mock")
    _confirm_with_rpc(ship_db, monkeypatch, _rpc_unavail)
    # si_id 는 등록마다 새로 매겨지므로 (sched_id, qty)·(lot, qty)·soi 기준으로 비교
    p_allocs = sorted((a["sched_id"], a["qty"]) for a in payload["allocs"])
    f_allocs = sorted((a["sched_id"], a["qty"]) for t, recs in INSERTED
                      if t == "shipment_allocations" for a in recs)
    assert p_allocs == f_allocs
    p_txns = sorted((t["product_id"], t["lot_number"], t["qty"]) for t in payload["txns"])
    f_txns = sorted((t["product_id"], t["lot_number"], t["qty"]) for tb, recs in INSERTED
                    if tb == "inventory_transactions" for t in recs)
    assert p_txns == f_txns
    f_lines = {int(f.split("soi_id=eq.")[1].split("&")[0]): v["received_qty"]
               for t, f, v in UPDATED if t == "sales_order_items"}
    p_lines = {}
    for l in payload["lines"]:
        p_lines[l["soi_id"]] = p_lines.get(l["soi_id"], l["expected_received_before"]) + l["qty"]
    assert p_lines == f_lines == {11: 700, 12: 300}
    f_sched = {int(f.split("sched_id=eq.")[1].split("&")[0]): v["delivered_qty"]
               for t, f, v in UPDATED if t == "so_delivery_schedule"}
    prev = {1: 0, 2: 100, 3: 0}
    assert f_sched == {s["sched_id"]: prev[s["sched_id"]] + s["delta"] for s in payload["scheds"]}


def test_unlinked_line_is_skipped_and_reported(ship_db, monkeypatch):
    """수주 미연결 라인은 payload 에서 빠지고, 함수의 skipped 를 경고로 보여 준다."""
    captured = []

    def _rpc(name, params=None, **kw):
        captured.append(params["p_payload"])
        SHIPMENTS[0]["status"] = "CONFIRMED"
        extra = [i["si_id"] for i in SHIP_ITEMS if i.get("soi_id") is None]
        return {"ok": True, "sois": 2, "skipped": extra}
    at = _open_shipping(ship_db)
    _register(at)
    SHIP_ITEMS.append({"si_id": 99, "shipment_id": SHIPMENTS[0]["shipment_id"],
                       "soi_id": None, "so_id": None, "sched_id": None,
                       "product_id": "P1", "pn": "NO-SO", "customer": "-",
                       "so_number": None, "qty": 50, "unit": "EA"})
    UPDATED.clear(); INSERTED.clear()
    monkeypatch.setattr(ship_db, "rpc", _rpc)
    at2 = _open_shipping(ship_db, "slip")
    at2.button(key="cf_go").click()
    at2.run()
    assert not at2.exception, [str(e.value) for e in at2.exception]
    p = captured[0]
    assert all(l["si_id"] != 99 for l in p["lines"])
    assert all(t["si_id"] != 99 for t in p["txns"])
    try:
        warns = list(at2.session_state["cf_alloc_warn"])
    except KeyError:
        warns = []
    assert any("수주와 연결되지 않아" in w and "NO-SO" in w for w in warns), warns
