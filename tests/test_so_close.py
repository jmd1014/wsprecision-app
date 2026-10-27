# -*- coding: utf-8 -*-
"""수주 상태 정리 r2 (2026-10-22, L3-S, 마이그레이션 075·076) — RPC 래퍼·상태 규칙·출고 정정 보호·화면.

기준: _수주상태_검토의견_20261022.md D1~D8 · _수주상태_r1리뷰_분류_및_수정지시문_20261022.md D9~D14, F1~F12.
지적 → 테스트 매핑은 리뷰 패키지 06_risks_browser.md 의 표.
"""
import os
import re
import sys
import importlib.util

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import db as _dbmod  # noqa: E402
from utils import so_close as C  # noqa: E402
from utils.shipment_adjust import line_status  # noqa: E402
from tests.so_mock import SOMock  # noqa: E402
from tests.conftest import goto  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(__file__))
APP_FILE = os.path.join(ROOT, "streamlit_app.py")
SRC = open(APP_FILE, encoding="utf-8").read()
SQL076 = open(os.path.join(ROOT, "supabase", "migrations", "076_so_close_rpc.sql"), encoding="utf-8").read()
SQL077 = open(os.path.join(ROOT, "supabase", "migrations", "077_so_close_rounds_all.sql"), encoding="utf-8").read()
streamlit_available = importlib.util.find_spec("streamlit") is not None
app_test = pytest.mark.skipif(not streamlit_available, reason="streamlit 미설치 — AppTest 불가")


# ════════ 순수 함수 (D1·D11·F3·F5) ════════
def test_header_status_excludes_inactive_lines_and_keeps_current():
    assert C.header_status([]) == "DRAFT"
    assert C.header_status([], current="CLOSED") == "CLOSED"
    assert C.header_status([{"qty": 10, "received_qty": 0, "status": "PENDING"}]) == "DRAFT"   # 옛 CONFIRMED 자리
    assert C.header_status([{"qty": 10, "received_qty": 3, "status": "PARTIAL"},
                            {"qty": 5, "received_qty": 0, "status": "PENDING"}]) == "PARTIAL"
    # REPLACED·CLOSED 라인은 집계에서 빠진다 → 영구 PARTIAL 아님 (Data M2)
    assert C.header_status([{"qty": 10, "received_qty": 10, "status": "DELIVERED"},
                            {"qty": 5, "received_qty": 0, "status": "REPLACED"},
                            {"qty": 7, "received_qty": 2, "status": "CLOSED"}]) == "DELIVERED"
    # 전부 비활성이면 현 상태 유지 (대체-CANCELLED 수주)
    assert C.header_status([{"qty": 5, "received_qty": 0, "status": "REPLACED"}], current="CANCELLED") == "CANCELLED"
    assert C.line_reopen_status({"received_qty": 0}) == "PENDING" and C.line_reopen_status({"received_qty": 2}) == "PARTIAL"
    assert C.SO_INACTIVE == ("CANCELLED", "CANCELED", "CLOSED") and C.LINE_INACTIVE == ("CLOSED", "CANCELLED", "REPLACED")
    assert C.is_inactive("closed") and not C.is_inactive("DRAFT")


def test_line_status_keeps_inactive_and_revise_fields_protects_closed_lines():
    assert line_status(100, 40) == "PARTIAL" and line_status(100, 100) == "DELIVERED" and line_status(100, 0) == "PENDING"
    assert line_status(100, 0, "CLOSED") == "CLOSED" and line_status(100, 100, "REPLACED") == "REPLACED"
    # 활성 라인: 기존 규칙 그대로 (정정 테스트가 기대하는 dict 모양)
    assert C.revise_line_fields({"qty": 2000, "received_qty": 500, "status": "PARTIAL"}, 0) == \
        {"received_qty": 0, "pending_qty": 2000, "status": "PENDING"}
    # CLOSED 라인(qty 100·received 40·closed 60): 출고 취소 40 → received 0, pending 0 유지, closed 100 (불변식 received+pending+closed=qty)
    f = C.revise_line_fields({"qty": 100, "received_qty": 40, "pending_qty": 0, "closed_qty": 60, "status": "CLOSED"}, 0)
    assert f == {"received_qty": 0, "pending_qty": 0, "status": "CLOSED", "closed_qty": 100}
    # 증가(출고 정정 +20): closed 40
    f2 = C.revise_line_fields({"qty": 100, "received_qty": 40, "closed_qty": 60, "status": "CANCELLED"}, 60)
    assert f2["closed_qty"] == 40 and f2["status"] == "CANCELLED" and f2["pending_qty"] == 0
    # REPLACED: closed_qty 건드리지 않음
    f3 = C.revise_line_fields({"qty": 100, "received_qty": 40, "status": "REPLACED"}, 0)
    assert f3 == {"received_qty": 0, "pending_qty": 0, "status": "REPLACED"}
    # D15 (Codex r2 H1): 종결 머리글 아래 완납 라인(30/30) 출고 30 취소 → PENDING 으로 되살리지 않고 CLOSED·closed 30
    f4 = C.revise_line_fields({"qty": 30, "received_qty": 30, "pending_qty": 0, "status": "DELIVERED"}, 0, header_status="CLOSED")
    assert f4 == {"received_qty": 0, "pending_qty": 0, "status": "CLOSED", "closed_qty": 30.0}
    f5 = C.revise_line_fields({"qty": 30, "received_qty": 30, "status": "DELIVERED"}, 10, header_status="CANCELLED")
    assert f5 == {"received_qty": 10, "pending_qty": 0, "status": "CANCELLED", "closed_qty": 20.0}
    # 종결 머리글이어도 REPLACED 는 그대로, 활성 머리글이면 기존 규칙
    assert C.revise_line_fields({"qty": 30, "received_qty": 30, "status": "REPLACED"}, 0, header_status="CLOSED")["status"] == "REPLACED"
    assert C.revise_line_fields({"qty": 30, "received_qty": 30, "status": "DELIVERED"}, 0, header_status="PARTIAL")["status"] == "PENDING"


def test_recompute_header_skips_inactive_header_and_updates_active():
    m = SOMock().seed(so_status="PARTIAL", lines=[(1, 100, 40, 60, "PARTIAL"), (2, 50, 0, 0, "REPLACED")])
    m.line(1).update({"received_qty": 100, "pending_qty": 0, "status": "DELIVERED"})
    assert C.recompute_header(m, 101) == "DELIVERED" and m.header()["status"] == "DELIVERED"
    assert C.recompute_header(m, 101) is None                       # 변화 없음 → 쓰기 없음
    m2 = SOMock().seed(so_status="CLOSED", lines=[(1, 100, 40, 0, "CLOSED", 60)])
    n = len(m2.writes)
    assert C.recompute_header(m2, 101) is None and len(m2.writes) == n   # 비활성 머리글은 건드리지 않음


# ════════ RPC 루틴 (목 = 076 규칙) ════════
def _m(**kw):
    m = SOMock()
    m.seed(so_status=kw.pop("so_status", "PARTIAL"),
           lines=kw.pop("lines", [(1, 100, 40, 60, "PARTIAL"), (2, 50, 0, 50, "PENDING"), (3, 30, 30, 0, "DELIVERED")]),
           rounds=kw.pop("rounds", [(11, 1, 100, 40), (12, 2, 20, 0), (13, 2, 30, 0), (14, 3, 30, 30)]),
           drafts=kw.pop("drafts", ()))
    return m


def test_close_keeps_remaining_closes_rounds_header_and_view():
    m = _m()
    r = C.close_sales_order(m, 101, "CLOSED", "월 변경 이월", "김민수")
    assert r["ok"] and r["closed"] == 2 and r["rounds"] == 3 and r["header"] is True and r["header_status"] == "CLOSED"
    assert m.rpc_calls == [("so_close_lines", {"p_so_id": 101, "p_mode": "CLOSED", "p_reason": "월 변경 이월", "p_who": "김민수"})]
    l1, l2, l3 = m.line(1), m.line(2), m.line(3)
    assert (l1["pending_qty"], l1["closed_qty"], l1["status"], l1["close_reason"]) == (0, 60.0, "CLOSED", "월 변경 이월")
    assert l1["closed_rounds"] == [{"sched_id": 11, "qty_before": 100.0, "delivered": 40.0}]
    assert (l2["pending_qty"], l2["closed_qty"], l2["status"]) == (0, 50.0, "CLOSED")
    assert [c["sched_id"] for c in l2["closed_rounds"]] == [12, 13]
    assert "종결(월 변경 이월) 2026-10-22 김민수" in l1["remark"]
    assert (l3["pending_qty"], l3["closed_qty"], l3["status"]) == (0, 0, "DELIVERED")
    assert m.round(11)["qty"] == 40.0 and m.round(12)["qty"] == 0.0 and m.round(13)["qty"] == 0.0 and m.round(14)["qty"] == 30
    assert m.header()["status"] == "CLOSED" and "종결(월 변경 이월)" in m.header()["remark"]
    # 대사 불변식: 회차 납품합 = received − presched
    for soi in (1, 2, 3):
        assert sum(x["delivered_qty"] for x in m.tables["so_delivery_schedule"] if x["soi_id"] == soi) == \
            m.line(soi)["received_qty"] - m.line(soi)["presched_qty"]
    # 뷰(076): 미납 0·보존 110·납품상태 종결 — 목록 미납에 다시 잡히지 않는다 (Data H1)
    st = m.stats()
    assert (st["total_pending_qty"], st["total_closed_qty"], st["delivery_status"]) == (0, 110.0, "종결")
    assert not [l for l in m.tables["sales_order_items"] if l["so_id"] == 101 and l["pending_qty"] > 0]


def test_close_blocked_by_draft_shipment_reports_ship_no_from_hint_and_writes_nothing():
    m = _m(drafts=[(7, "SH-20261021-02", "DRAFT", [2]), (8, "SH-20261020-01", "CONFIRMED", [1])])
    r = C.close_sales_order(m, 101, "CLOSED", "월 변경 이월", "김민수")
    assert not r["ok"] and r["blocked"] == ["SH-20261021-02"] and "SH-20261021-02" in r["msg"]
    assert m.writes == [] and m.line(2)["pending_qty"] == 50 and m.header()["status"] == "PARTIAL"


def test_close_rejects_bad_args_locally_and_mode():
    m = _m()
    assert not C.close_sales_order(m, 101, "CLOSED", "  ", "k")["ok"] and m.rpc_calls == []
    with pytest.raises(ValueError):
        C.close_sales_order(m, 101, "IN_PROD", "x", "k")


def test_cancel_mode_same_routine():
    m = _m()
    r = C.close_sales_order(m, 101, "CANCELLED", "거래처 발주 철회", "김민수")
    assert r["ok"] and m.header()["status"] == "CANCELLED" and m.line(1)["status"] == "CANCELLED"
    assert m.line(1)["closed_qty"] == 60.0 and "취소(거래처 발주 철회)" in m.line(1)["remark"]
    assert m.stats()["delivery_status"] == "취소"


def test_close_twice_two_sessions_is_idempotent():
    m = _m()
    C.close_sales_order(m, 101, "CLOSED", "월 변경 이월", "a")
    n = len(m.writes)
    r = C.close_sales_order(m, 101, "CLOSED", "월 변경 이월", "b")
    assert r["ok"] and r["closed"] == 0 and r["header"] is False and len(m.writes) == n and "잔량이 없습니다" in r["msg"]
    assert m.header()["remark"].count("종결(") == 1


def test_header_failure_recovers_by_recalling_both_directions():
    # 종결: 라인만 반영되고 머리글은 못 쓴 '반쪽' → 같은 버튼 재호출이 머리글만 마무리 (H2)
    m = _m()
    m.rpc_header_fail_once = True
    r1 = C.close_sales_order(m, 101, "CLOSED", "월 변경 이월", "k")
    assert r1["ok"] and r1["closed"] == 2 and r1["header"] is False and m.header()["status"] == "PARTIAL"
    r2 = C.close_sales_order(m, 101, "CLOSED", "월 변경 이월", "k")
    assert r2["closed"] == 0 and r2["header"] is True and m.header()["status"] == "CLOSED" and "마무리" in r2["msg"]
    # 되돌리기 거울상: 라인 복원됐는데 머리글이 CLOSED 로 남음 → 재호출이 머리글만 재계산
    m.rpc_header_fail_once = True
    r3 = C.reopen_sales_order(m, 101, "k")
    assert r3["reopened"] == 2 and r3["header"] is None and m.header()["status"] == "CLOSED"
    r4 = C.reopen_sales_order(m, 101, "k")
    assert r4["ok"] and r4["reopened"] == 0 and r4["header"] == "PARTIAL" and m.header()["status"] == "PARTIAL"


def test_transport_error_is_retried_once_and_unavailable_reported():
    m = _m()
    m.rpc_transport_fail_once = True
    r = C.close_sales_order(m, 101, "CLOSED", "월 변경 이월", "k")
    assert r["ok"] and r["retried"] and len(m.rpc_calls) == 2 and m.header()["status"] == "CLOSED"
    assert "재호출" in r["msg"] and m.header()["remark"].count("종결(") == 1   # 멱등 — 두 번째는 머리글 그대로
    m2 = _m()
    m2.rpc_unavailable = True
    r2 = C.close_sales_order(m2, 101, "CLOSED", "월 변경 이월", "k")
    assert not r2["ok"] and "076" in r2["msg"] and m2.writes == []
    m3 = _m()
    m3.rpc_fail = ("55P03", "lock timeout", "")
    assert "겹쳐" in C.close_sales_order(m3, 101, "CLOSED", "x", "k")["msg"]


def test_transport_error_twice_reports_unknown():
    m = _m()
    calls = {"n": 0}
    real = m.rpc

    def _rpc(name, params=None, timeout=None):
        calls["n"] += 1
        real(name, params, timeout)
        raise _dbmod.RpcTransportError("timeout")
    m.rpc = _rpc
    r = C.close_sales_order(m, 101, "CLOSED", "월 변경 이월", "k")
    assert not r["ok"] and r["retried"] and calls["n"] == 2 and "응답 불명" in r["msg"]


def test_reopen_restores_pending_rounds_and_recomputes_header():
    m = _m()
    C.close_sales_order(m, 101, "CLOSED", "월 변경 이월", "k")
    r = C.reopen_sales_order(m, 101, "k")
    assert r["ok"] and r["reopened"] == 2 and r["rounds_restored"] == 3 and r["rounds_skipped"] == 0 and r["header"] == "PARTIAL"
    l1, l2 = m.line(1), m.line(2)
    assert (l1["pending_qty"], l1["closed_qty"], l1["status"], l1["close_reason"], l1["closed_rounds"]) == (60.0, 0, "PARTIAL", None, None)
    assert (l2["pending_qty"], l2["closed_qty"], l2["status"]) == (50.0, 0, "PENDING")
    assert m.round(11)["qty"] == 100.0 and m.round(12)["qty"] == 20.0 and m.round(13)["qty"] == 30.0   # D12 복원
    assert m.header()["status"] == "PARTIAL" and "되돌림" in m.header()["remark"]
    # 되돌린 뒤 출고 60 확정(라인·회차 반영 흉내) → 회차 납품합 = received − presched (QA REQ 7)
    l1.update({"received_qty": 100, "pending_qty": 0, "status": "DELIVERED"})
    m.round(11)["delivered_qty"] = 100
    assert sum(x["delivered_qty"] for x in m.tables["so_delivery_schedule"] if x["soi_id"] == 1) == l1["received_qty"] - l1["presched_qty"]
    # 납품 0 이던 수주를 되돌리면 접수(DRAFT)
    m2 = _m(so_status="DRAFT", lines=[(1, 10, 0, 10, "PENDING")], rounds=[])
    C.close_sales_order(m2, 101, "CANCELLED", "오입력", "k")
    assert C.reopen_sales_order(m2, 101, "k")["header"] == "DRAFT" and m2.header()["status"] == "DRAFT"


def test_reopen_skips_round_whose_delivery_changed():
    m = _m()
    C.close_sales_order(m, 101, "CLOSED", "월 변경 이월", "k")
    m.round(12)["delivered_qty"] = 5          # 닫힌 회차에 납품완료가 바뀜(비정상 경로)
    r = C.reopen_sales_order(m, 101, "k")
    assert r["rounds_restored"] == 2 and r["rounds_skipped"] == 1 and "미복원" in r["msg"]
    assert m.round(12)["qty"] == 0.0 and m.round(13)["qty"] == 30.0   # 열린 회차(qty 0 < delivered 5)는 건드리지 않음


def test_replaced_mix_and_replacement_cancelled_reopen_is_noop():
    # REPLACED 라인 혼재: 종결은 활성 미납만, 머리글은 활성 잔량 0 이면 CLOSED
    m = _m(lines=[(1, 100, 40, 60, "PARTIAL"), (2, 50, 0, 0, "REPLACED")], rounds=[])
    r = C.close_sales_order(m, 101, "CLOSED", "월 변경 이월", "k")
    assert r["closed"] == 1 and m.line(2)["status"] == "REPLACED" and m.line(2)["closed_qty"] == 0 and m.header()["status"] == "CLOSED"
    # 대체-CANCELLED 수주(REPLACED 만, closed_qty 0): 되돌리기는 머리글 유지·noop (QA L1 / F12)
    m2 = _m(so_status="CANCELLED", lines=[(1, 100, 40, 0, "REPLACED"), (2, 50, 0, 0, "REPLACED")], rounds=[])
    r2 = C.reopen_sales_order(m2, 101, "k")
    assert r2["reopened"] == 0 and r2["header"] is None and m2.header()["status"] == "CANCELLED"   # 정당한 취소는 유지 (H-1)
    assert m2.stats()["total_pending_qty"] == 0 and m2.stats()["delivery_status"] == "취소"


def test_revision_cannot_revive_closed_or_replaced_lines():
    """출고 정정 루틴이 쓰는 값(revise_line_fields) + 머리글(recompute_header)이 종결을 풀지 않는다 (H1)."""
    m = _m()
    C.close_sales_order(m, 101, "CLOSED", "월 변경 이월", "k")
    l1 = m.line(1)
    f = C.revise_line_fields(l1, 0)             # 기존 확정 출고 40 전체 취소
    m.update("sales_order_items", "soi_id=eq.1", f)
    assert (l1["pending_qty"], l1["closed_qty"], l1["status"]) == (0, 100.0, "CLOSED")
    assert C.recompute_header(m, 101) is None and m.header()["status"] == "CLOSED"
    assert m.stats()["total_pending_qty"] == 0
    # 되돌리면 보존 100 → 미납 100 (received 0)
    C.reopen_sales_order(m, 101, "k")
    assert m.line(1)["pending_qty"] == 100.0 and m.line(1)["status"] == "PENDING"
    assert m.header()["status"] == "PARTIAL"            # 라인 3(완납 30)이 활성이라 부분 진행


def test_mock_not_in_filter_and_exact_fail_match():
    m = _m()
    assert [r["so_id"] for r in m.fetch("sales_orders", "*", C.SO_INACTIVE_FQ)] == [101]
    C.close_sales_order(m, 101, "CLOSED", "x", "k")
    assert m.fetch("sales_orders", "*", C.SO_INACTIVE_FQ) == []
    assert m.fetch("sales_order_stats", "*", C.SO_INACTIVE_FQ) == []
    m2 = _m(lines=[(1, 10, 0, 10, "PENDING"), (11, 10, 0, 10, "PENDING")], rounds=[])
    m2.update_fail_ids = {1}
    assert m2.update_count("sales_order_items", "soi_id=eq.11&pending_qty=gt.0", {"pending_qty": 0}) == 1
    assert m2.update_count("sales_order_items", "soi_id=eq.1&pending_qty=gt.0", {"pending_qty": 0}) == -1


# ════════ 정적 검사 ════════
def test_static_no_manual_selectbox_no_confirmed_header_write_no_direct_recalc():
    assert 'selectbox("상태 변경"' not in SRC
    assert 'else "CONFIRMED"' not in SRC
    assert "_soc.header_status(" not in SRC                        # 본체는 recompute_header 만
    assert '"status": r["old_so_status"]' not in SRC               # _rp_revert 과거 상태 덮기 제거 (F5)
    assert "line_status(_nq" not in SRC                            # 정정 라인 값은 revise_line_fields 만 (F3)
    assert SRC.count("_soc.revise_line_fields(") == 1 and SRC.count("_soc.recompute_header(") == 3   # 정정은 _line_patch 한 곳
    lines = SRC.splitlines()
    for i, ln in enumerate(lines):
        if 'update("sales_orders"' in ln:
            assert '"CONFIRMED"' not in "\n".join(lines[i:i + 6]), f"sales_orders 갱신에 CONFIRMED (line {i + 1})"
    # 루틴은 쓰기 전 조회 없이 RPC 만 (D9)
    src_mod = open(os.path.join(ROOT, "utils", "so_close.py"), encoding="utf-8").read()
    assert "update_count(" not in src_mod and "shipment_items" not in src_mod and 'db.rpc(' in src_mod


def test_static_active_filter_constant_chips_label_and_cache():
    assert 'not.in.("CANCELLED"' not in SRC and '("CANCELLED", "CANCELED")' not in SRC
    assert SRC.count("SO_INACTIVE") >= 12
    m = re.search(r"_sl_opts = \[(.*?)\]", SRC, re.S)
    opts = [x.strip().strip('"') for x in m.group(1).replace("\n", "").split(",") if x.strip()]
    assert opts == ["전체", "DRAFT", "PARTIAL", "DELIVERED", "CLOSED", "CANCELLED"]
    assert '"DRAFT": "접수"' in SRC and '"CLOSED": "종결"' in SRC
    assert 'if m == "line_closed":' in SRC                        # F3b 메시지
    assert SRC.count('st.session_state.pop("mr_cache", None)') >= 8   # F9: 종결·되돌리기(_so_flash_rerun)·정정 경로 추가


def test_migration_076_declares_rpcs_views_and_guards():
    for s in ("FUNCTION public.so_close_lines(p_so_id integer, p_mode text, p_reason text, p_who text)",
              "FUNCTION public.so_reopen_lines(p_so_id integer, p_who text)",
              "RAISE EXCEPTION 'blocked' USING ERRCODE = 'P0001', HINT = v_blocked",
              "RAISE EXCEPTION 'line_closed'", "closed_rounds jsonb", "CHECK (closed_qty >= 0)",
              "ALTER COLUMN status SET NOT NULL", "WITH (security_invoker = true)", "total_closed_qty",
              "AND o.status NOT IN ('CLOSED', 'CANCELLED')", "ELSE 'DRAFT' END AS st",
              "GRANT  EXECUTE ON FUNCTION public.so_close_lines", "GRANT  EXECUTE ON FUNCTION public.so_reopen_lines",
              "REVOKE EXECUTE ON FUNCTION public.confirm_shipment"):
        assert s in SQL076, s
    assert "ELSE 'CONFIRMED' END AS st" not in SQL076
    assert SQL076.count("IN ('CLOSED', 'CANCELLED', 'REPLACED')") >= 6
    assert not re.search(r"^\s*ALTER TABLE.*DROP COLUMN", SQL076, re.M) and "DELETE FROM" not in SQL076.upper()
    assert "SECURITY DEFINER" not in SQL076


# ════════ 화면 (AppTest) ════════
GRIDS = {}          # AgGrid 에 넘어간 DataFrame (key → df) — 화면이 그린 데이터 단언용 (R5 ②)
SEL = {}            # key → 선택 행 인덱스 (A→B 전환 테스트용)


def _hook_aggrid(monkeypatch):
    """st_aggrid.AgGrid 를 기록기로 — 본체 toss_grid 가 함수 안에서 import 하므로 모듈 속성 교체가 그대로 적용된다."""
    try:
        import st_aggrid
    except Exception:
        return

    class _G:
        def __init__(self, df, key):
            self.selected_rows = df.iloc[[SEL[key]]] if key in SEL and 0 <= SEL[key] < len(df) else None

    def _fake(df, *a, key=None, **kw):
        GRIDS[key] = df.copy()
        return _G(df, key)
    monkeypatch.setattr(st_aggrid, "AgGrid", _fake)


def _grid_text():
    return "\n".join(df.to_string() for df in GRIDS.values())


def _open(monkeypatch, mock, main="so", sub="list"):
    GRIDS.clear()
    SEL.clear()
    _hook_aggrid(monkeypatch)
    mock.install(monkeypatch, _dbmod)
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP_FILE, default_timeout=90)
    at.secrets["supabase"] = {"url": "https://mock.local", "anon_key": "a", "service_role_key": "s"}
    at.secrets["auth"] = {"disabled": True}
    at.run()
    goto(at, main, sub)
    return at


def _keys(at):
    return {b.key for b in at.button}


def _texts(at):
    out = []
    for attr in ("markdown", "caption", "text", "subheader", "info", "warning", "error", "success"):
        for e in getattr(at, attr):
            out.append(str(getattr(e, "value", "") or getattr(e, "body", "") or ""))
    for d in at.dataframe:
        try:
            out.append(d.value.to_string())
        except Exception:
            pass
    return "\n".join(out)


@app_test
def test_screen_close_then_reopen_buttons_and_columns(monkeypatch):
    m = _m()
    at = _open(monkeypatch, m)
    keys = _keys(at)
    assert "so_close_101" in keys and "so_cancel_101" in keys and "so_reopen_101" not in keys
    assert not any("상태 변경" in (s.label or "") for s in at.selectbox)
    at.button(key="so_close_101").click()
    at.run()
    assert m.writes == [] and "so_close_cfm_ok" in _keys(at)
    at.session_state["mr_cache"] = {"stale": True}          # F9: 종결이 자재 소요 캐시를 비우는지
    at.button(key="so_close_cfm_ok").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert "mr_cache" not in at.session_state
    assert m.header()["status"] == "CLOSED" and m.line(1)["closed_qty"] == 60.0 and m.line(1)["close_reason"] == "월 변경 이월"
    assert m.rpc_calls[-1][0] == "so_close_lines"
    assert any("종결 — 라인 2줄" in str(getattr(x, "value", "")) for x in at.info)
    keys2 = _keys(at)
    assert "so_reopen_101" in keys2 and "so_close_101" not in keys2 and "so_cancel_101" not in keys2
    at.button(key="so_reopen_101").click()
    at.run()
    at.button(key="so_reopen_cfm_ok").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert m.header()["status"] == "PARTIAL" and m.line(2)["pending_qty"] == 50.0 and m.round(12)["qty"] == 20.0
    assert "so_close_101" in _keys(at)


@app_test
def test_screen_half_state_shows_finish_button(monkeypatch):
    """라인은 종결됐는데 머리글이 활성(비정상) → '종결 마무리' 버튼 + 되돌리기 둘 다 (F4)."""
    m = _m(so_status="PARTIAL", lines=[(1, 100, 40, 0, "CLOSED", 60), (2, 50, 0, 0, "CLOSED", 50)], rounds=[])
    at = _open(monkeypatch, m)
    b = at.button(key="so_close_101")
    assert "종결 마무리" in b.label and not b.disabled and "so_reopen_101" in _keys(at)
    b.click()
    at.run()
    at.button(key="so_close_cfm_ok").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert m.header()["status"] == "CLOSED"


@app_test
def test_screen_replacement_cancelled_shows_caption_not_reopen(monkeypatch):
    m = _m(so_status="CANCELLED", lines=[(1, 100, 40, 0, "REPLACED"), (2, 50, 0, 0, "REPLACED")], rounds=[])
    at = _open(monkeypatch, m)
    assert at.button(key="so_reopen_101").disabled and "so_close_101" not in _keys(at)
    assert any("재발주 대체분" in (c.value or "") for c in at.caption)


@app_test
def test_screen_cancel_requires_reason_and_blocked_message(monkeypatch):
    m = _m(drafts=[(7, "SH-20261021-02", "DRAFT", [2])])
    at = _open(monkeypatch, m)
    assert at.button(key="so_cancel_101").disabled
    at.button(key="so_close_101").click()
    at.run()
    at.button(key="so_close_cfm_ok").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert m.header()["status"] == "PARTIAL" and m.writes == []
    assert any("SH-20261021-02" in str(getattr(x, "value", "")) for x in at.info)




# ════════ r2 리뷰 반영 (QA B-1·H-1·H-2·M-1·M-2·M-3·M-4, Data M3·M4) ════════
def test_replacement_revert_guard_and_forced_header(monkeypatch):
    """B-1: 대체가 만든 CANCELLED 머리글은 되돌리기 뒤 force 재계산 → DRAFT/PARTIAL. 종결·보존 라인이 있으면 차단."""
    # 대체-CANCELLED(REPLACED 만, closed 0) → 허용 → force 재계산
    m = SOMock().seed(so_status="CANCELLED", lines=[(1, 1000, 0, 0, "REPLACED")])
    assert C.replacement_revert_block("CANCELLED", m.tables["sales_order_items"]) is None
    m.line(1).update({"pending_qty": 1000, "status": "PENDING", "replaced_by_soi": None})   # _rp_revert 라인 복원 흉내
    assert C.recompute_header(m, 101) is None                        # 기본은 비활성 머리글 유지
    assert C.recompute_header(m, 101, force=True) == "DRAFT" and m.header()["status"] == "DRAFT"
    m2 = SOMock().seed(so_status="CANCELLED", lines=[(1, 1000, 0, 0, "REPLACED"), (2, 500, 500, 0, "DELIVERED")])
    m2.line(1).update({"pending_qty": 1000, "status": "PENDING"})
    assert C.recompute_header(m2, 101, force=True) == "PARTIAL"
    # 종결 루틴이 만든 상태는 차단
    assert "먼저" in C.replacement_revert_block("CLOSED", [{"status": "REPLACED", "closed_qty": 0}])
    assert "먼저" in C.replacement_revert_block("CANCELLED", [{"status": "CANCELLED", "closed_qty": 60}])
    assert C.replacement_revert_block("PARTIAL", [{"status": "REPLACED", "closed_qty": 0}]) is None
    assert C.kept_mode([{"status": "CLOSED", "closed_qty": 5}]) == "CLOSED"
    assert C.kept_mode([{"status": "CLOSED", "closed_qty": 5}, {"status": "CANCELLED", "closed_qty": 1}]) == "MIXED"
    assert C.kept_mode([{"status": "REPLACED", "closed_qty": 0}]) is None


def test_reopen_mirror_only_when_invariant_violated():
    """H-1: 거울상 재계산은 머리글 비활성 ∧ 보존 라인 없음 ∧ 활성 미납 라인 있음(불변식 ③ 위반)일 때만."""
    a = SOMock().seed(so_status="CANCELLED", lines=[(1, 100, 100, 0, "DELIVERED"), (2, 50, 0, 0, "REPLACED")])
    r = C.reopen_sales_order(a, 101, "k")
    assert r["reopened"] == 0 and r["header"] is None and a.header()["status"] == "CANCELLED" and not r["ok"]
    b = SOMock().seed(so_status="CANCELLED", lines=[(1, 100, 0, 0, "PENDING")])          # 옛 수동 취소(pending 0)
    assert C.reopen_sales_order(b, 101, "k")["header"] is None and b.header()["status"] == "CANCELLED"
    c = SOMock().seed(so_status="CANCELLED", lines=[(1, 100, 0, 100, "PENDING")])        # 불변식 ③ 위반 → 복구
    r3 = C.reopen_sales_order(c, 101, "k")
    assert r3["header"] == "DRAFT" and c.header()["status"] == "DRAFT" and r3["ok"]


def test_finish_requires_same_mode():
    """M-2: 닫힌 라인이 CLOSED 인데 취소로 마무리하면 bad_args(mode mismatch); 같은 mode 면 마무리."""
    m = SOMock().seed(so_status="PARTIAL", lines=[(1, 100, 40, 0, "CLOSED", 60), (2, 50, 0, 0, "CLOSED", 50)])
    r = C.close_sales_order(m, 101, "CANCELLED", "x", "k")
    assert not r["ok"] and "마무리" in r["msg"] and m.header()["status"] == "PARTIAL"
    r2 = C.close_sales_order(m, 101, "CLOSED", "x", "k")
    assert r2["ok"] and r2["header"] is True and m.header()["status"] == "CLOSED"


def test_revision_on_closed_line_keeps_rounds_closed_then_reopen_restores():
    """H-2: 종결 라인의 확정 출고 취소 → 정정 루틴이 회차 qty 도 내려 닫힌 상태 유지 → 되돌리기가 qty_before 로 복원."""
    m = _m(lines=[(1, 100, 40, 60, "PARTIAL")], rounds=[(11, 1, 100, 40)])
    C.close_sales_order(m, 101, "CLOSED", "월 변경 이월", "k")
    assert m.round(11)["qty"] == 40.0
    # 출고 40 취소(정정 루틴 흉내): 라인 received 0·closed 100, 회차 delivered 0 → 앱 규칙: 비활성 라인 회차 qty = delivered
    m.update("sales_order_items", "soi_id=eq.1", C.revise_line_fields(m.line(1), 0))
    m.round(11)["delivered_qty"] = 0
    if m.round(11)["qty"] > m.round(11)["delivered_qty"]:
        m.round(11)["qty"] = m.round(11)["delivered_qty"]
    assert (m.line(1)["received_qty"], m.line(1)["closed_qty"], m.round(11)["qty"]) == (0, 100.0, 0)
    r = C.reopen_sales_order(m, 101, "k")
    assert r["rounds_restored"] == 1 and r["rounds_skipped"] == 0 and r["header"] == "DRAFT"
    assert m.line(1)["pending_qty"] == 100.0 and m.round(11)["qty"] == 100.0
    assert m.line(1)["pending_qty"] == sum(x["qty"] - x["delivered_qty"] for x in m.tables["so_delivery_schedule"] if x["soi_id"] == 1)


def test_reopen_transport_retry_message_and_ok():
    """M-1: 되돌리기 응답 유실 → 재호출 → ok·재호출 안내(현재 머리글)."""
    m = _m()
    C.close_sales_order(m, 101, "CLOSED", "x", "k")
    m.rpc_transport_fail_once = True
    r = C.reopen_sales_order(m, 101, "k")
    assert r["ok"] and r["retried"] and r["reopened"] == 0 and "재호출" in r["msg"] and "PARTIAL" in r["msg"]
    assert m.header()["status"] == "PARTIAL" and m.line(1)["pending_qty"] == 60.0
    m2 = _m()
    m2.rpc_transport_fail_once = True
    r2 = C.close_sales_order(m2, 101, "CLOSED", "x", "k")
    assert r2["ok"] and r2["retried"] and "재호출" in r2["msg"] and "CLOSED" in r2["msg"]


def test_static_r2b_guards_present():
    assert SRC.count("_soc.replacement_revert_block(") == 1 and 'force=True' in SRC
    assert "종결·취소·대체된 수주 라인 — 수주 목록에서" in SRC            # 폴백·증가 정정 가드 (M-3·L-5)
    assert SRC.count("_soc.LINE_INACTIVE") >= 4
    assert '"소,unit,status"' not in SRC and '"soi_id,so_id,qty,received_qty,pending_qty,unit,status"' in SRC
    assert "or _r.get(\"retried\")" in SRC                                     # F9 재호출 경로
    assert "mode mismatch" in SQL076 and "v_active_open" in SQL076 and "ORDER BY soi_id FOR UPDATE" in SQL076
    assert SQL076.index("ORDER BY soi_id FOR UPDATE") < SQL076.index("FROM sales_orders WHERE so_id = p_so_id FOR UPDATE")
    assert SQL076.count("DROP FUNCTION IF EXISTS public.confirm_shipment") == 1


@app_test
def test_screen_retried_close_clears_cache(monkeypatch):
    """M-1 화면: 응답 유실 재호출 경로에서도 mr_cache 를 비운다."""
    m = _m()
    at = _open(monkeypatch, m)
    m.rpc_transport_fail_once = True
    at.button(key="so_close_101").click()
    at.run()
    at.session_state["mr_cache"] = {"stale": True}
    at.button(key="so_close_cfm_ok").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert "mr_cache" not in at.session_state and m.header()["status"] == "CLOSED" and len(m.rpc_calls) == 2


@app_test
def test_screen_finish_buttons_follow_kept_mode(monkeypatch):
    """M-2 화면: 라인이 CANCELLED 로 보존된 반쪽 상태면 [취소 마무리] 만 활성, 종결 버튼 잠김."""
    m = _m(so_status="PARTIAL", lines=[(1, 100, 40, 0, "CANCELLED", 60)], rounds=[])
    at = _open(monkeypatch, m)
    assert at.button(key="so_close_101").disabled
    at.text_input(key="so_cancel_reason_101").set_value("정리")
    at.run()
    b = at.button(key="so_cancel_101")
    assert "취소 마무리" in b.label and not b.disabled




# ════════ r3 (D15·D17, R5 ④) ════════
def test_close_keeps_all_rounds_then_cancel_shipment_then_reopen_restores_both():
    """D17/Codex r2 H3: 완납 회차(40/40)+열린 회차(60/0) 라인을 종결 → 과거 출고 40 취소(정정 흉내: delivered 0 + 닫힌 유지)
    → 되돌리기가 두 회차 모두 qty_before 로 복원, rounds_skipped 0."""
    m = _m(lines=[(1, 100, 40, 60, "PARTIAL")], rounds=[(11, 1, 40, 40), (12, 1, 60, 0)])
    C.close_sales_order(m, 101, "CLOSED", "월 변경 이월", "k")
    assert [c["sched_id"] for c in m.line(1)["closed_rounds"]] == [11, 12]          # 전 회차 보존
    assert m.round(11)["qty"] == 40 and m.round(12)["qty"] == 0.0
    # 과거 출고 40 취소(정정 루틴 규칙): 라인 received 0·closed 100, 회차 11 delivered 0 → qty 도 0(닫힌 유지)
    m.update("sales_order_items", "soi_id=eq.1", C.revise_line_fields(m.line(1), 0, header_status="CLOSED"))
    m.round(11)["delivered_qty"] = 0
    m.round(11)["qty"] = 0
    r = C.reopen_sales_order(m, 101, "k")
    assert r["rounds_restored"] == 2 and r["rounds_skipped"] == 0 and r["header"] == "DRAFT"
    assert m.round(11)["qty"] == 40.0 and m.round(12)["qty"] == 60.0 and m.line(1)["pending_qty"] == 100.0
    assert m.line(1)["pending_qty"] == sum(x["qty"] - x["delivered_qty"] for x in m.tables["so_delivery_schedule"] if x["soi_id"] == 1)


def test_d15_closed_line_with_snapshot_restores_rounds_on_reopen():
    """Data r3 H1: 종결 머리글 아래 완납 라인(30/30, 회차 30/30, closed_rounds NULL)을 정정이 닫을 때 회차 스냅샷을 함께 쓰면
    되돌리기가 회차 계획 30 을 복원한다(스냅샷 없으면 복원 0 — 소실)."""
    m = SOMock().seed(so_status="CLOSED", lines=[(1, 30, 30, 0, "DELIVERED")], rounds=[(11, 1, 30, 30)])
    m.line(1)["closed_rounds"] = None
    f = C.revise_line_fields(m.line(1), 0, header_status="CLOSED")
    f["closed_rounds"] = [{"sched_id": 11, "qty_before": 30.0, "delivered": 30.0}]      # 앱이 함께 쓰는 스냅샷
    m.update("sales_order_items", "soi_id=eq.1", f)
    m.round(11).update({"delivered_qty": 0, "qty": 0})                                   # 출고 30 취소 → 회차 닫힌 유지
    r = C.reopen_sales_order(m, 101, "k")
    assert r["reopened"] == 1 and r["rounds_restored"] == 1 and r["rounds_skipped"] == 0
    assert m.round(11)["qty"] == 30.0 and m.line(1)["pending_qty"] == 30.0 and m.header()["status"] == "DRAFT"
    assert m.line(1)["pending_qty"] == sum(x["qty"] - x["delivered_qty"] for x in m.tables["so_delivery_schedule"] if x["soi_id"] == 1)


def test_recompute_header_limit_warning_logs_once():
    """M-3: 라인 500건이면 log_error 1회, 반환은 정상 계산(예외 없음)."""
    m = SOMock().seed(so_status="PARTIAL", lines=[(i, 10, 10, 0, "DELIVERED") for i in range(1, 501)])
    assert C.recompute_header(m, 101) == "DELIVERED"
    assert len(m.log_errors) == 1 and "500 한도" in m.log_errors[0][1]


def test_migration_077_declares_all_rounds_and_final_rules():
    assert "WHERE d.soi_id = r.soi_id;" in SQL077 and "077 D17" in SQL077
    assert "CREATE OR REPLACE FUNCTION public.so_close_lines(p_so_id integer, p_mode text, p_reason text, p_who text)" in SQL077
    assert "so_reopen_lines" not in SQL077.split("CREATE OR REPLACE FUNCTION")[1].split("COMMENT ON")[0]   # reopen 은 재선언 안 함
    assert "ORDER BY soi_id FOR UPDATE" in SQL077 and SQL077.index("ORDER BY soi_id FOR UPDATE") < SQL077.index("FROM sales_orders WHERE so_id = p_so_id FOR UPDATE")
    assert "076 머리 주석" in SQL077 and "구식" in SQL077                       # Codex r2 L1 — 최종 규칙 기록
    assert "GRANT  EXECUTE ON FUNCTION public.so_close_lines" in SQL077 and "SECURITY DEFINER" not in SQL077
    assert "DROP COLUMN" not in SQL077 and "DELETE FROM" not in SQL077.upper()


def test_static_r3_revision_conditional_and_order():
    i_patch = SRC.index("def _line_patch(_li_, _nr_, _pn_=None)")
    assert "soi_id=eq.{}&status=eq.{}&{}" in SRC and '"received_qty=eq.{}".format(_fq(float(' in SRC   # D16 조건부
    assert SRC.count("_n9, _lf9 = _line_patch(_li, _nr, x.get(\"pn\"))") == 2    # 감소·증가 두 경로
    dec = SRC.index("# ③→① 수주 라인 먼저, 조건부 (D16)")
    lot = SRC.index("# ① LOT 복원 — 마지막 차감 LOT 부터", dec)
    rnd = SRC.index("# ② 회차 충당 되돌림", dec)
    assert i_patch < dec < lot < rnd                                             # 라인 → LOT → 회차
    assert "_hdr_by[_so_] = _hs_" in SRC and "cache=False" in SRC[SRC.index("def _line_patch"):SRC.index("def _stop_msg")]   # D15 + H-2 재조회
    assert "종결·취소된 수주 — 수주 목록에서 되돌린 뒤 정정하세요" in SRC             # M-1 증가 정정 머리글 검사
    assert "_todo_cx" in SRC and '"rev_id,si_id"' in SRC                            # B-1 권장 2 라인 단위 재취소
    assert "갱신 실패(통신·서버 오류" in SRC                                          # B-1 권장 3 (-1 구분)
    assert SRC.count('return -9, {"_why": ') == 3 and "_rv_blocked" in SRC and "_cx_hist_fail" in SRC   # r4 D18·D19
    assert 'except Exception:\n                            pass\n                    _lf_ = _soc.revise_line_fields' not in SRC   # fail-open 제거
    assert "sched_id=eq.{_fq(_rc9['sched_id'])}&qty=gt.{_fq(_dv9)}" in SRC          # R4 조건부 회차 정리
    assert SRC.count("정정 중단 — ") == 4 and "앞 라인은 반영됨" in SRC          # 0행·−1·조회 실패(-9)·취소 이력 조회 실패
    assert "received_qty=is.null" in SRC                                          # H2 NULL received
    assert 'startswith("정정 중단")' in SRC and SRC.count("not _stop9") >= 4         # B1·M4 호출부
    assert "if _stopped:\n                    # 중단: 전표는 CONFIRMED" in SRC          # B1 머리글 무변경


@app_test
def test_screen_confirm_gate_follows_selected_order_and_double_click(monkeypatch):
    """R5 ④: 확인창은 선택 수주(scope)에 붙는다 — A 에서 확인창 연 뒤 B 로 바꾸면 B 에는 안 뜨고, 연속 클릭은 1회만 반영."""
    m = _two()
    at = _open(monkeypatch, m)
    SEL["so_grid"] = 0                                   # A(101)
    at.run()
    at.button(key="so_close_101").click()
    at.run()
    assert "so_close_cfm_ok" in _keys(at)
    SEL["so_grid"] = 1                                   # B(102) 로 전환 — A 의 확인창이 따라오지 않는다
    at.run()
    assert "so_close_cfm_ok" not in _keys(at) and "so_close_102" in _keys(at) and m.writes == []
    SEL["so_grid"] = 0
    at.run()
    assert "so_close_cfm_ok" in _keys(at)                # A 로 돌아오면 확인창 유지
    at.button(key="so_close_cfm_ok").click()
    at.run()
    assert m.header(101)["status"] == "CLOSED" and len([w for w in m.writes if w[1] == "sales_orders"]) == 1
    n_rpc = len(m.rpc_calls)
    # 연속 클릭: 이미 종결된 뒤 되돌리기 버튼을 두 번(확인 2회) — click_guard 가 두 번째를 막는다
    at.button(key="so_reopen_101").click()
    at.run()
    at.button(key="so_reopen_cfm_ok").click()
    at.run()
    assert m.header(101)["status"] == "PARTIAL" and len(m.rpc_calls) == n_rpc + 1
    # 연속 클릭(Codex r3 M1): 두 번의 독립 run — 2차 확정 클릭 직전에 가드 시각을 '방금'으로 두어
    # (AppTest 는 run 하나가 5초를 넘겨 실제 연타를 재현할 수 없다) click_guard 가 막아 RPC 수 불변
    import time as _time
    n_rpc = len(m.rpc_calls)
    at.button(key="so_close_101").click()
    at.run()
    at.session_state["_guard_so_close"] = _time.time()
    at.button(key="so_close_cfm_ok").click()
    at.run()
    assert len(m.rpc_calls) == n_rpc and m.header(101)["status"] == "PARTIAL"   # 가드가 막음(경고 뒤 rerun 으로 문구는 사라짐)
    # 역검사: 가드를 지우면 같은 클릭이 RPC 를 부른다(테스트가 가드에 의존함을 증명)
    at.session_state["_guard_so_close"] = 0.0
    at.button(key="so_close_101").click()
    at.run()
    at.button(key="so_close_cfm_ok").click()
    at.run()
    assert len(m.rpc_calls) == n_rpc + 1 and m.header(101)["status"] == "CLOSED"
    at.button(key="so_reopen_101").click()
    at.run()
    at.session_state["_guard_so_reopen"] = 0.0
    at.button(key="so_reopen_cfm_ok").click()
    at.run()
    assert m.header(101)["status"] == "PARTIAL"
    at.session_state["mr_cache"] = {"stale": True}
    at.text_input(key="so_cancel_reason_101").set_value("거래 무효")
    at.run()
    at.button(key="so_cancel_101").click()
    at.run()
    at.button(key="so_cancel_cfm_ok").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert m.header(101)["status"] == "CANCELLED" and "mr_cache" not in at.session_state   # 취소 뒤 캐시 비움


# ── 종결 전/후 화면 비교(활성 대조 수주 유지) — F7 ──
def _two():
    m = SOMock()
    m.seed(so_id=101, so_number="PO-CLOSE-777", lines=[(1, 1000, 223, 777, "PARTIAL")], rounds=[(11, 1, 1000, 223)],
           pn="4DI0622A4-5M-1", product_id="P1")
    m.seed(so_id=102, so_number="PO-KEEP-555", lines=[(2, 600, 45, 555, "PARTIAL")], rounds=[(12, 2, 600, 45)],
           customer="미진정밀", pn="8RHP-VM-C-02", product_id="P2")
    return m


SCREENS = [("home", None, "홈 미납 수주·수주 진행"), ("so", "list", "수주 KPI(미납 수량)"), ("so", "sched", "계획률·미계획"),
           ("po", "new", "자재 소요(발주서 작성)"), ("ship", "fstock", "완성 재고"), ("ship", "deliver", "출고 후보")]


def _metric(at, label):
    """KPI 값 — st.metric 또는 U3 요약 띠(kpi-strip, 수주 세부 3화면)."""
    import re as _re
    v = next((str(x.value) for x in at.metric if (x.label or "") == label), None)
    if v is not None:
        return v
    for m in at.markdown:
        hit = _re.search(r'<span class="k">' + _re.escape(label) + r'</span><span class="v[^"]*">([^<]+)</span>',
                         str(m.value or ""))
        if hit:
            return hit.group(1)
    return None


@app_test
@pytest.mark.parametrize("main,sub,label", SCREENS)
def test_screens_exclude_closed_order_keep_control(monkeypatch, main, sub, label):
    m = _two()
    at = _open(monkeypatch, m, main, sub)
    before = _texts(at) + "\n" + "\n".join(str(getattr(x, "value", "")) for x in at.metric)
    before += "\n" + "\n".join(str(getattr(sb, "options", "")) for sb in at.selectbox) + "\n" + _grid_text()
    if sub == "list":
        assert _metric(at, "미납 수량") == "1,332"          # 777 + 555
    # R5 ①: 종결 전 대상(777)·대조(555) 노출을 모든 화면에서 필수 단언 (그리드 데이터 포함)
    assert "777" in before, f"{label}: 종결 대상 수주가 화면에 없음(공허한 비교)"
    assert "555" in before, f"{label}: 대조 수주가 화면에 없음(공허한 비교)"
    r = C.close_sales_order(m, 101, "CLOSED", "월 변경 이월", "k")
    assert r["ok"] and m.stats(101)["total_pending_qty"] == 0
    _dbmod.clear_cache()
    if "mr_cache" in at.session_state:                      # 화면 경로는 F9 가 비운다(screen 테스트) — 여기선 루틴 직접 호출
        del at.session_state["mr_cache"]
    GRIDS.clear()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    after = _texts(at) + "\n" + "\n".join(str(getattr(x, "value", "")) for x in at.metric)
    after += "\n" + "\n".join(str(getattr(sb, "options", "")) for sb in at.selectbox) + "\n" + _grid_text()
    if sub == "list":
        # 수주 목록 자체는 종결 수주를 보여준다(필터 '전체', 보존 777) — KPI 미납 수량만 대조 수주로 줄어든다
        assert _metric(at, "미납 수량") == "555" and "PO-CLOSE-777" in after
        return
    # 종결 수주와 그 미납 777 은 사라지고, 대조 수주 555 는 남는다
    assert "PO-CLOSE-777" not in after and "777" not in after, label
    assert "555" in after, label
