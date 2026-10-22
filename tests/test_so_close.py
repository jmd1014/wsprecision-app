# -*- coding: utf-8 -*-
"""수주 상태 정리(2026-10-22, L3-S) — 종결·취소·되돌리기 루틴, 활성 필터 상수, 화면 버튼.

기준: _수주상태_검토의견_20261022.md §2 D1~D8 · 지시문 S3.
"""
import os
import re
import sys
import importlib.util

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils import so_close as C  # noqa: E402
from tests.so_mock import SOMock  # noqa: E402
from tests.conftest import goto  # noqa: E402

APP_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "streamlit_app.py")
SRC = open(APP_FILE, encoding="utf-8").read()
streamlit_available = importlib.util.find_spec("streamlit") is not None


# ════════ 순수 함수 ════════
def test_header_status_is_derived_draft_partial_delivered():
    assert C.header_status([]) == "DRAFT"
    assert C.header_status([{"qty": 10, "received_qty": 0}]) == "DRAFT"       # 옛 CONFIRMED 자리
    assert C.header_status([{"qty": 10, "received_qty": 3}, {"qty": 5, "received_qty": 0}]) == "PARTIAL"
    assert C.header_status([{"qty": 10, "received_qty": 10}, {"qty": 5, "received_qty": 5}]) == "DELIVERED"
    assert C.line_reopen_status({"received_qty": 0}) == "PENDING"
    assert C.line_reopen_status({"received_qty": 2}) == "PARTIAL"
    assert C.is_inactive("closed") and C.is_inactive("CANCELLED") and C.is_inactive("CANCELED")
    assert not C.is_inactive("DRAFT") and not C.is_inactive(None)
    assert C.SO_INACTIVE == ("CANCELLED", "CANCELED", "CLOSED")
    assert C.SO_INACTIVE_FQ == 'status=not.in.("CANCELLED","CANCELED","CLOSED")'


# ════════ 루틴 (목 DB) ════════
def _m(**kw):
    m = SOMock()
    m.seed(so_status=kw.pop("so_status", "PARTIAL"),
           lines=kw.pop("lines", [(1, 100, 40, 60, "PARTIAL"), (2, 50, 0, 50, "PENDING"),
                                  (3, 30, 30, 0, "DELIVERED")]),
           rounds=kw.pop("rounds", [(11, 1, 100, 40), (12, 2, 20, 0), (13, 2, 30, 0), (14, 3, 30, 30)]),
           drafts=kw.pop("drafts", ()))
    return m


def test_close_keeps_remaining_zeroes_pending_closes_rounds_and_header():
    m = _m()
    r = C.close_sales_order(m, 101, "CLOSED", "월 변경 이월", "김민수", today="2026-10-22")
    assert r["ok"] and r["blocked"] == [] and r["closed"] == 2 and r["failed"] == []
    l1, l2, l3 = m.line(1), m.line(2), m.line(3)
    assert (l1["pending_qty"], l1["closed_qty"], l1["status"], l1["close_reason"]) == (0, 60.0, "CLOSED", "월 변경 이월")
    assert (l2["pending_qty"], l2["closed_qty"], l2["status"]) == (0, 50.0, "CLOSED")
    assert "종결(월 변경 이월) 2026-10-22 김민수" in l1["remark"]
    assert (l3["pending_qty"], l3["closed_qty"], l3["status"]) == (0, 0, "DELIVERED")   # 완납 라인 무접촉
    # 회차: 미충당분 qty=delivered, 이미 충당된 회차는 그대로
    assert m.round(11)["qty"] == 40.0 and m.round(12)["qty"] == 0.0 and m.round(13)["qty"] == 0.0
    assert m.round(14)["qty"] == 30 and r["rounds"] == 3
    h = m.header()
    assert h["status"] == "CLOSED" and r["header"] is True and "종결(월 변경 이월)" in h["remark"]
    # 대사 불변식(회차 납품합 = received − presched) 유지
    for soi in (1, 2, 3):
        rsum = sum(x["delivered_qty"] for x in m.tables["so_delivery_schedule"] if x["soi_id"] == soi)
        assert rsum == m.line(soi)["received_qty"] - m.line(soi)["presched_qty"]
    # 계획·자재·현황이 보는 집합: pending>0 라인 0, 머리글은 비활성
    assert not [l for l in m.tables["sales_order_items"] if l["so_id"] == 101 and l["pending_qty"] > 0]
    assert C.is_inactive(h["status"])
    assert m.rpc_calls == []


def test_close_is_blocked_by_unconfirmed_shipment_and_writes_nothing():
    m = _m(drafts=[(7, "SH-20261021-02", "DRAFT", [2]), (8, "SH-20261020-01", "CONFIRMED", [1])])
    r = C.close_sales_order(m, 101, "CLOSED", "월 변경 이월", "김민수")
    assert not r["ok"] and r["blocked"] == ["SH-20261021-02"] and "SH-20261021-02" in r["msg"]
    assert m.writes == [] and m.line(2)["pending_qty"] == 50 and m.header()["status"] == "PARTIAL"


def test_close_requires_reason_and_valid_mode():
    m = _m()
    r = C.close_sales_order(m, 101, "CLOSED", "  ", "김민수")
    assert not r["ok"] and m.writes == []
    with pytest.raises(ValueError):
        C.close_sales_order(m, 101, "IN_PROD", "x", "김민수")


def test_cancel_mode_same_routine_status_cancelled():
    m = _m()
    r = C.close_sales_order(m, 101, "CANCELLED", "거래처 발주 철회", "김민수", today="2026-10-22")
    assert r["ok"] and m.header()["status"] == "CANCELLED"
    assert m.line(1)["status"] == "CANCELLED" and m.line(1)["closed_qty"] == 60.0 and m.line(1)["pending_qty"] == 0
    assert "취소(거래처 발주 철회)" in m.line(1)["remark"]


def test_close_twice_is_idempotent():
    m = _m()
    C.close_sales_order(m, 101, "CLOSED", "월 변경 이월", "김민수")
    n_writes = len(m.writes)
    r = C.close_sales_order(m, 101, "CLOSED", "월 변경 이월", "김민수")
    assert r["closed"] == 0 and r["header"] is None and len(m.writes) == n_writes


def test_close_partial_failure_keeps_header_and_reports():
    m = _m()
    m.update_fail_ids = {2}
    r = C.close_sales_order(m, 101, "CLOSED", "고객 요청 중단", "김민수")
    assert not r["ok"] and r["closed"] == 1 and r["failed"] == [2] and r["header"] is None
    assert "일부만" in r["msg"] and "soi 2" in r["msg"]
    assert m.header()["status"] == "PARTIAL" and m.line(2)["pending_qty"] == 50
    assert m.line(1)["pending_qty"] == 0 and m.line(1)["closed_qty"] == 60.0


def test_close_header_update_failure_is_reported():
    m = _m()
    m.update_false = True          # db.update(머리글·회차) 가 False — update_count 는 정상
    r = C.close_sales_order(m, 101, "CLOSED", "월 변경 이월", "김민수")
    assert r["header"] is False and not r["ok"] and "머리글" in r["msg"]
    assert m.line(1)["pending_qty"] == 0


def test_reopen_restores_pending_recomputes_statuses_keeps_rounds():
    m = _m()
    C.close_sales_order(m, 101, "CLOSED", "월 변경 이월", "김민수", today="2026-10-22")
    r = C.reopen_sales_order(m, 101, "김민수", today="2026-10-23")
    assert r["ok"] and r["reopened"] == 2 and r["header"] == "PARTIAL"
    l1, l2 = m.line(1), m.line(2)
    assert (l1["pending_qty"], l1["closed_qty"], l1["status"], l1["close_reason"]) == (60.0, 0, "PARTIAL", None)
    assert (l2["pending_qty"], l2["closed_qty"], l2["status"]) == (50.0, 0, "PENDING")
    assert "되돌림 2026-10-23 김민수" in l1["remark"] and "되돌림" in m.header()["remark"]
    assert m.round(12)["qty"] == 0.0 and "회차는 복원하지 않았습니다" in r["msg"]   # 회차 그대로
    assert m.header()["status"] == "PARTIAL"
    # 납품 0 이던 수주를 되돌리면 접수(DRAFT) — CONFIRMED 아님
    m2 = _m(so_status="DRAFT", lines=[(1, 10, 0, 10, "PENDING")], rounds=[])
    C.close_sales_order(m2, 101, "CANCELLED", "오입력", "김민수")
    assert C.reopen_sales_order(m2, 101, "김민수")["header"] == "DRAFT"
    assert m2.header()["status"] == "DRAFT"


def test_reopen_without_closed_lines_is_noop():
    m = _m()
    r = C.reopen_sales_order(m, 101, "김민수")
    assert not r["ok"] and r["reopened"] == 0 and m.writes == []


def test_close_when_no_pending_lines_only_message():
    m = _m(lines=[(3, 30, 30, 0, "DELIVERED")], rounds=[])
    r = C.close_sales_order(m, 101, "CLOSED", "월 변경 이월", "김민수")
    assert r["closed"] == 0 and "잔량이 없습니다" in r["msg"] and m.writes == []


# ════════ 정적 검사 (본체) ════════
def test_static_no_manual_status_selectbox_and_no_confirmed_header_write():
    assert 'selectbox("상태 변경"' not in SRC
    assert 'else "CONFIRMED"' not in SRC
    # sales_orders 머리글 갱신 근처에 CONFIRMED 쓰기 없음 (출고 전표 CONFIRMED 는 shipments 라 무관)
    lines = SRC.splitlines()
    for i, ln in enumerate(lines):
        if 'update("sales_orders"' in ln or "update(\"sales_orders\"" in ln:
            window = "\n".join(lines[i:i + 6])
            assert '"CONFIRMED"' not in window, f"sales_orders 갱신에 CONFIRMED 쓰기 (line {i + 1})"


def test_static_active_filter_uses_constant_only():
    assert 'not.in.("CANCELLED"' not in SRC
    assert '("CANCELLED", "CANCELED")' not in SRC
    assert SRC.count("SO_INACTIVE") >= 12       # 정의 2 + 소비 11곳(1837·2478·5835·5927·7532·7895·8712·8755·10931·12915·발주서 품목)


def test_static_status_chips_and_label():
    m = re.search(r"_sl_opts = \[(.*?)\]", SRC, re.S)
    opts = [x.strip().strip('"') for x in m.group(1).replace("\n", "").split(",") if x.strip()]
    assert opts == ["전체", "DRAFT", "PARTIAL", "DELIVERED", "CLOSED", "CANCELLED"]
    assert '"DRAFT": "접수"' in SRC and '"CLOSED": "종결"' in SRC
    assert "IN_PROD" not in m.group(1) and "CONFIRMED" not in m.group(1)


def test_migration_075_declares_closed_and_columns():
    p = os.path.join(os.path.dirname(APP_FILE), "supabase", "migrations", "075_so_status_closed.sql")
    sql = open(p, encoding="utf-8").read()
    assert "'CLOSED'" in sql and "'REPLACED'" in sql and "closed_qty" in sql and "close_reason" in sql
    assert "chk_so_status" in sql and "chk_soi_status" in sql
    assert "DROP COLUMN" not in sql and "DELETE FROM" not in sql.upper()   # 기존 행 무접촉


# ════════ 화면 (AppTest) ════════
pytestmark_app = pytest.mark.skipif(not streamlit_available, reason="streamlit 미설치 — AppTest 불가")


def _open(monkeypatch, mock):
    import db
    mock.install(monkeypatch, db)
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP_FILE, default_timeout=90)
    at.secrets["supabase"] = {"url": "https://mock.local", "anon_key": "a", "service_role_key": "s"}
    at.secrets["auth"] = {"disabled": True}
    at.run()
    goto(at, "so", "list")
    return at


def _keys(at):
    return {b.key for b in at.button}


@pytestmark_app
def test_screen_close_button_flow_writes_through_routine(monkeypatch):
    m = _m()
    at = _open(monkeypatch, m)
    keys = _keys(at)
    assert "so_close_101" in keys and "so_cancel_101" in keys and "so_reopen_101" not in keys
    assert not any("상태 변경" in (s.label or "") for s in at.selectbox)
    at.button(key="so_close_101").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert m.writes == []                       # 첫 클릭은 확인창만
    assert "so_close_cfm_ok" in _keys(at)
    at.button(key="so_close_cfm_ok").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert m.header()["status"] == "CLOSED" and m.line(1)["pending_qty"] == 0 and m.line(1)["closed_qty"] == 60.0
    assert m.line(1)["close_reason"] == "월 변경 이월"      # 기본 사유
    assert m.round(12)["qty"] == 0.0
    texts = [str(getattr(x, "value", "") or "") for x in at.info]
    assert any("종결 — 라인 2줄" in t for t in texts)
    # 종결 뒤 화면: 되돌리기만
    keys2 = _keys(at)
    assert "so_reopen_101" in keys2 and "so_close_101" not in keys2 and "so_cancel_101" not in keys2


@pytestmark_app
def test_screen_cancel_requires_reason_then_reopen(monkeypatch):
    m = _m()
    at = _open(monkeypatch, m)
    assert at.button(key="so_cancel_101").disabled           # 사유 없으면 잠김
    at.text_input(key="so_cancel_reason_101").set_value("거래처 발주 철회")
    at.run()
    at.button(key="so_cancel_101").click()
    at.run()
    at.button(key="so_cancel_cfm_ok").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert m.header()["status"] == "CANCELLED" and m.line(2)["closed_qty"] == 50.0
    at.button(key="so_reopen_101").click()
    at.run()
    at.button(key="so_reopen_cfm_ok").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert m.header()["status"] == "PARTIAL" and m.line(2)["pending_qty"] == 50.0 and m.line(2)["closed_qty"] == 0


@pytestmark_app
def test_screen_blocked_by_draft_shipment(monkeypatch):
    m = _m(drafts=[(7, "SH-20261021-02", "DRAFT", [2])])
    at = _open(monkeypatch, m)
    at.button(key="so_close_101").click()
    at.run()
    at.button(key="so_close_cfm_ok").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert m.header()["status"] == "PARTIAL" and m.writes == []
    texts = [str(getattr(x, "value", "") or "") for x in at.info]
    assert any("SH-20261021-02" in t for t in texts)
