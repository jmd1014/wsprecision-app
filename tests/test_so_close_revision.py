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
    # D15 로 정정이 처음 닫는 라인: 회차 스냅샷(내리기 전)과 사유를 함께 쓴다 (Data r3 H1)
    assert fields["closed_rounds"] == [{"sched_id": 1, "qty_before": 500.0, "delivered": 500.0},
                                       {"sched_id": 2, "qty_before": 100.0, "delivered": 0.0}]
    assert fields["close_reason"].startswith("출고 정정 SH-20260901-01")
    assert {k: fields[k] for k in ("received_qty", "pending_qty", "status", "closed_qty")} == \
        {"received_qty": 0, "pending_qty": 0, "status": "CLOSED", "closed_qty": 500.0}
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
    # B1: 중단이면 전표 머리글(CANCELLED)·수주 머리글을 바꾸지 않고, 성공 안내 대신 오류로 보인다
    assert not [1 for t, f, v in RV.UPDATED if t in ("shipments", "sales_orders")]
    assert RV.SHIPMENTS[0]["status"] == "CONFIRMED"
    assert not any("역반영 완료" in str(getattr(x, "value", "")) for x in at.success)
    errs = " ".join(str(getattr(w, "value", "") or "") for w in at.error)
    assert "정정 중단" in errs and "남은 라인" in errs
    assert RV.LINES[11]["closed_qty"] == 1500 and RV.LINES[11]["pending_qty"] == 0   # 보존 잔량 유지


def test_revision_null_received_uses_is_null_filter(rev_db, monkeypatch):
    """H2: received_qty NULL(레거시) 라인은 조건부 필터가 is.null 이어야 1행 갱신된다."""
    RV._seed()
    RV.LINES[11].update({"received_qty": None, "pending_qty": 2000, "status": "PENDING"})
    _patch_header(monkeypatch, "PARTIAL")
    at = RV._pick_confirmed(RV._open())
    _cancel_confirmed(at)
    flt, fields = _line_updates()[-1]
    assert "received_qty=is.null" in flt and "received_qty=eq." not in flt
    assert fields["received_qty"] == 0 and fields["status"] == "PENDING"


def test_revision_on_active_header_unchanged_behaviour(rev_db, monkeypatch):
    """회귀: 활성 수주(PARTIAL)는 r1 과 같은 값(received 0·pending 2000·PENDING) — 조건부 갱신만 추가."""
    RV._seed()
    RV.LINES[11]["status"] = "PARTIAL"
    _patch_header(monkeypatch, "PARTIAL")
    at = RV._pick_confirmed(RV._open())
    _cancel_confirmed(at)
    flt, fields = _line_updates()[-1]
    assert fields == {"received_qty": 0, "pending_qty": 2000, "status": "PENDING"}
    assert "status=eq.PARTIAL" in flt and "received_qty=eq.500.0" in flt
    assert RV.SHIPMENTS[0]["status"] == "CANCELLED"


def test_revision_header_closed_between_read_and_patch_applies_d15(rev_db, monkeypatch):
    """H-2: 준비 조회 때 PARTIAL 이던 머리글이 PATCH 직전 재조회에서 CLOSED → 완납 라인도 D15 로 닫힌다."""
    RV._seed()
    RV.LINES[11].update({"qty": 500, "received_qty": 500, "pending_qty": 0, "status": "DELIVERED", "closed_qty": 0})
    _patch_header(monkeypatch, "PARTIAL", status_refetch="CLOSED")
    at = RV._pick_confirmed(RV._open())
    _cancel_confirmed(at)
    flt, fields = _line_updates()[-1]
    assert fields["status"] == "CLOSED" and fields["pending_qty"] == 0 and fields["closed_qty"] == 500.0


def test_revision_partial_stop_keeps_shipment_then_second_cancel_finishes(rev_db, monkeypatch):
    """B-1(QA REQ 1): 2라인 전표 취소 중 2번째 라인 0행 → 1번째만 반영·전표 CONFIRMED 유지·이력 1건 →
    2차 취소는 이력 없는 라인만 역반영하고 전표를 취소한다(이중 역반영 없음)."""
    RV._seed()
    RV.LINES[11]["status"] = "PARTIAL"
    RV.LINES[12] = {"soi_id": 12, "so_id": 100, "canonical_pn": "4PDVN-04", "customer_part_no": "X", "customer_item_name": None,
                    "product_id": "P1", "qty": 1000, "received_qty": 200, "pending_qty": 800, "unit": "EA", "unit_price": 1000,
                    "due_date": None, "status": "PARTIAL", "closed_qty": 0}
    RV.SHIP_ITEMS.append({"si_id": 3, "shipment_id": 1, "soi_id": 12, "so_id": 100, "sched_id": None, "product_id": "P1",
                          "pn": "4PDVN-04", "customer_pn": "X", "item_name": None, "customer": "㈜엠제이티", "so_number": "SO-100",
                          "qty": 200, "unit": "EA", "unit_price": 1000})
    stale12 = dict(RV.LINES[12])
    RV.LINES[12].update({"status": "CLOSED", "pending_qty": 0, "closed_qty": 800})       # 그 사이 종결된 현재 라인
    _patch_header(monkeypatch, "PARTIAL", stale_lines={12: stale12})
    at = RV._pick_confirmed(RV._open())
    _cancel_confirmed(at)
    ups = _line_updates()
    assert [f.split("&")[0] for f, v in ups] == ["soi_id=eq.11"]                       # 1번째만
    assert RV.SHIPMENTS[0]["status"] == "CONFIRMED" and RV.SHIPMENTS[0]["rev_no"] == 0
    revs = [r for tt, recs in RV.INSERTED if tt == "shipment_revisions" for r in recs]
    assert [r["si_id"] for r in revs] == [1]
    assert any("정정 중단" in str(getattr(w, "value", "")) for w in at.error)
    # 2차 취소: 라인 12 가 다시 정정 가능한 상태(종결 되돌림 흉내)로 돌아옴 → 이력 없는 라인 12 만 역반영, 전표 CANCELLED
    RV.LINES[12].update({"status": "PARTIAL", "pending_qty": 800, "closed_qty": 0})
    RV.UPDATED.clear()
    _patch_header(monkeypatch, "PARTIAL")
    at2 = RV._pick_confirmed(RV._open())
    _cancel_confirmed(at2)
    ups2 = _line_updates()
    _msgs2 = [str(getattr(w, "value", "")) for w in list(at2.error) + list(at2.warning) + list(at2.success) + list(at2.info)]
    assert [f.split("&")[0] for f, v in ups2] == ["soi_id=eq.12"], (ups2, _msgs2, RV.UPDATED[-5:])   # 11 은 이중 역반영 안 함
    assert RV.SHIPMENTS[0]["status"] == "CANCELLED"


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
def test_revision_failclosed_on_lookup_failure(rev_db, monkeypatch, kw, why):
    """S1/D18: 머리글 재조회 실패·빈 결과, D15 스냅샷 조회 실패 → 그 라인부터 쓰기 없이 중단, 전표 유지, 빨간 안내."""
    RV._seed()
    RV.LINES[11].update({"qty": 500, "received_qty": 500, "pending_qty": 0, "status": "DELIVERED", "closed_qty": 0})
    _patch_header(monkeypatch, "CLOSED", **kw)
    at = RV._pick_confirmed(RV._open())
    _cancel_confirmed(at)
    _no_writes()
    e = _errs(at)
    assert "정정 중단" in e and why in e and "쓰기 없음" in e


def test_cancel_failclosed_on_history_failure(rev_db, monkeypatch):
    """S1/D18: CANCEL 이력 조회 실패 → 취소 진입 전 중단(쓰기 0). 화면도 D19 로 취소 버튼이 잠긴다."""
    RV._seed()
    RV.LINES[11]["status"] = "PARTIAL"
    _patch_header(monkeypatch, "PARTIAL", hist_raise=True)
    at = RV._pick_confirmed(RV._open())
    assert at.button(key="cf_cancel").disabled                      # D19: 이력 조회 실패 → 취소 버튼 잠김
    assert at.button(key="cf_rv_go").disabled
    assert "취소 이력 조회 실패" in _errs(at)
    # 버튼이 잠겼어도 루틴 자체도 fail-closed 인지: 확인 플래그를 직접 세워 호출 경로를 밟는다
    at.text_input(key="cf_cx_reason_1").set_value("정정 테스트")
    at.run()
    at.session_state["cfm_cf_cancel_1"] = True
    at.run()
    assert "cf_cancel_cfm_ok" not in {b.key for b in at.button}      # 게이트 자체가 열리지 않는다
    _no_writes()


def test_cancel_routine_failclosed_when_only_routine_lookup_fails(rev_db, monkeypatch):
    """A6(Codex r4 M1 이월): 화면의 D19 이력 조회(select si_id)는 성공해 취소 게이트가 열리고,
    루틴 안의 이력 조회(select rev_id,si_id)만 실패 → 루틴의 D18 분기에 실제로 도달한다:
    쓰기 0·전표 CONFIRMED 유지·'정정 중단 … 취소 이력 조회 실패 … 쓰기 없음'·db_read 오류 기록 1건."""
    RV._seed()
    RV.LINES[11]["status"] = "PARTIAL"
    _patch_header(monkeypatch, "PARTIAL", hist_raise_routine=True)
    logged = []
    monkeypatch.setattr(_dbmod, "log_error", lambda *a, **k: logged.append((a, k)) or False)
    at = RV._pick_confirmed(RV._open())
    at.text_input(key="cf_cx_reason_1").set_value("정정 테스트")
    at.run()
    assert not at.button(key="cf_cancel").disabled                   # 화면 조회는 성공 → D19 잠금 없음(사유 입력 뒤)
    at.button(key="cf_cancel").click(); at.run()
    at.button(key="cf_cancel_cfm_ok").click(); at.run()              # 확인 게이트까지 통과해 루틴 호출
    assert not at.exception, [str(e.value) for e in at.exception]
    _no_writes()
    e = _errs(at)
    assert "정정 중단" in e and "취소 이력 조회 실패" in e and "쓰기 없음" in e
    assert [a for a, _ in logged if a and a[0] == "db_read" and "취소 이력 조회 실패" in str(a[1])], logged


def _seed_two_lines():
    RV._seed()
    RV.LINES[11]["status"] = "PARTIAL"
    RV.LINES[12] = {"soi_id": 12, "so_id": 100, "canonical_pn": "4PDVN-04", "customer_part_no": "X", "customer_item_name": None,
                    "product_id": "P1", "qty": 1000, "received_qty": 200, "pending_qty": 800, "unit": "EA", "unit_price": 1000,
                    "due_date": None, "status": "PARTIAL", "closed_qty": 0}
    RV.SHIP_ITEMS.append({"si_id": 3, "shipment_id": 1, "soi_id": 12, "so_id": 100, "sched_id": None, "product_id": "P1",
                          "pn": "4PDVN-04", "customer_pn": "X", "item_name": None, "customer": "㈜엠제이티", "so_number": "SO-100",
                          "qty": 200, "unit": "EA", "unit_price": 1000})


def test_partial_cancelled_shipment_blocks_edit_allows_cancel_resume(rev_db, monkeypatch):
    """S2/D19: CANCEL 이력이 si 1 에만 있는 전표 → 정정 버튼 잠김·안내, 취소 재개는 si 3 만 역반영."""
    _seed_two_lines()
    RV.REVS[:] = [{"shipment_id": 1, "rev_no": 1, "action": "CANCEL", "si_id": 1, "pn": "4PDVN-03", "qty_before": 500,
                   "qty_after": 0, "reason": "x", "created_by": "t"}]
    _patch_header(monkeypatch, "PARTIAL")
    at = RV._pick_confirmed(RV._open())
    at.text_input(key="cf_cx_reason_1").set_value("재개")
    at.run()
    assert at.button(key="cf_rv_go").disabled and not at.button(key="cf_cancel").disabled
    assert any("부분 취소 상태" in str(getattr(w, "value", "")) for w in at.warning)
    # 정정 게이트를 억지로 열어도 막힌다
    at.session_state["cfm_cf_rv"] = True
    at.session_state["cf_rv_plan"] = ({1: 0.0, 3: 0.0}, "억지", False)
    at.run()
    assert "cf_rv_cfm_ok" not in {b.key for b in at.button}
    _cancel_confirmed(at)
    assert [f.split("&")[0] for f, v in _line_updates()] == ["soi_id=eq.12"]
    assert RV.SHIPMENTS[0]["status"] == "CANCELLED"


def test_edit_increase_on_closed_header_is_rejected_in_flow(rev_db, monkeypatch):
    """S3 ④: 종결 머리글 아래 라인의 출고 증가 정정(EDIT) → 사전 검증 거부, 쓰기 0."""
    RV._seed()
    RV.LINES[11]["status"] = "PARTIAL"
    _patch_header(monkeypatch, "CLOSED")
    at = RV._pick_confirmed(RV._open())
    at.session_state["cfm_cf_rv"] = True
    at.session_state["cf_rv_plan"] = ({1: 600.0}, "증가 시도", False)       # si 1: 500 → 600
    at.run()
    at.button(key="cf_rv_cfm_ok").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert "종결·취소된 수주" in _errs(at)
    _no_writes()
