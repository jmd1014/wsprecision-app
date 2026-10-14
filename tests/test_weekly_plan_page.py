# -*- coding: utf-8 -*-
"""생산 계획 › 주간 계획 탭·설비 탭 확장 (migration 070, 2026-10-14) — AppTest.

data_editor 는 조작할 수 없으므로 렌더·요약·주 이동·편집 없는 저장(RPC 호출 인자)·
설비 추가·근무 체계·예외일 등록만 검증한다. 계산 규칙은 test_weekly_plan.py 가 고정.
"""
import os
import sys
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

APP_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "streamlit_app.py")

TODAY = date.today()
WEEK = TODAY - timedelta(days=TODAY.weekday())
MACHINES = [
    {"machine_id": "CNC01", "name": "CNC01", "group_code": "CNC", "shifts": 2,
     "hours_per_shift": 9, "active": True, "night_active": True, "sat_active": True, "note": None},
    {"machine_id": "MCT01", "name": "MCT01", "group_code": "MCT", "shifts": 2,
     "hours_per_shift": 9, "active": True, "night_active": False, "sat_active": False, "note": None},
]
PROFILES = [{"day_type": "WEEKDAY", "day_hours": 10, "night_hours": 10},
            {"day_type": "SATURDAY", "day_hours": 6, "night_hours": 6},
            {"day_type": "HOLIDAY", "day_hours": 6, "night_hours": 6},
            {"day_type": "OFF", "day_hours": 0, "night_hours": 0}]
PLAN = [
    {"plan_item_id": 1, "week_start": WEEK.isoformat(), "product_id": "P1", "pn": "4PDVN-03",
     "steps": [10], "op_label": "4PDVN-03#10", "op_key": "P1|10", "seq": 0, "group_code": "CNC",
     "qty": 100, "uph": 20, "uph_source": "CONFIRMED", "setup_min": 30, "hours": 5.5,
     "due_date": None, "note": None, "updated_at": "2026-10-14T01:00:00+00:00"},
    {"plan_item_id": 2, "week_start": WEEK.isoformat(), "product_id": "P1", "pn": "4PDVN-03",
     "steps": [30, 40], "op_label": "4PDVN-03#30#40", "op_key": "P1|30#40", "seq": 1,
     "group_code": "CNC", "qty": 100, "uph": None, "uph_source": None, "setup_min": 0,
     "hours": None, "due_date": None, "note": None, "updated_at": "2026-10-14T01:00:00+00:00"},
    {"plan_item_id": 3, "week_start": WEEK.isoformat(), "product_id": "P2", "pn": "MRG6-07",
     "steps": [20, 30], "op_label": "MRG6-07#20#30", "op_key": "P2|20#30", "seq": 2,
     "group_code": "MCT", "qty": 60, "uph": 20, "uph_source": "SHEET", "setup_min": 0,
     "hours": 3.0, "due_date": None, "note": None, "updated_at": "2026-10-14T01:00:00+00:00"},
]
PRODUCTS = [{"product_id": "P1", "pn": "4PDVN-03", "alias_list": None, "archived_at": None},
            {"product_id": "P2", "pn": "MRG6-07", "alias_list": None, "archived_at": None}]
STDS = [{"op_id": 1, "pn": "4PDVN-03", "product_id": "P1", "process": "4PDVN-03#10", "step": 10,
         "group_code": "CNC", "uph_std": 20, "std_status": "CONFIRMED", "setup_min": 30,
         "machines_used": "CNC01", "active": True}]

CALLS = {"insert": [], "update": [], "delete": [], "rpc": []}


def _fetch(table, select="*", filter_query="", limit=1000, cache=None):
    if table == "machines":
        if "machine_id=eq." in filter_query:
            mid = filter_query.split("machine_id=eq.")[1].split("&")[0]
            return [dict(m) for m in MACHINES if m["machine_id"] == mid]
        return [dict(m) for m in MACHINES]
    if table == "shift_profiles":
        return [dict(p) for p in PROFILES]
    if table == "work_calendar":
        return []
    if table == "production_plan_items":
        if "week_start=eq." in filter_query:
            w = filter_query.split("week_start=eq.")[1].split("&")[0]
            return [dict(r) for r in PLAN if r["week_start"] == w]
        return [dict(r) for r in PLAN]
    if table == "products" and "ilike" in filter_query:
        from urllib.parse import unquote
        q = unquote(filter_query).upper()
        return [dict(p) for p in PRODUCTS if p["pn"].split("-")[0] in q or p["pn"] in q]
    if table == "product_op_std":
        return [dict(s) for s in STDS]
    return []


@pytest.fixture()
def plan_db(monkeypatch):
    import db
    for k in CALLS:
        CALLS[k].clear()
    monkeypatch.setattr(db, "fetch", _fetch)
    monkeypatch.setattr(db, "fetch_one", lambda *a, **k: None)
    monkeypatch.setattr(db, "insert", lambda t, r: CALLS["insert"].append((t, r)) or len(r))
    monkeypatch.setattr(db, "update", lambda t, f, v: CALLS["update"].append((t, f, v)) or True)
    monkeypatch.setattr(db, "delete", lambda t, f: CALLS["delete"].append((t, f)) or 1)
    monkeypatch.setattr(db, "rpc", lambda n, p=None, **k: CALLS["rpc"].append((n, p)) or {
        "ok": True, "inserted": 0, "updated": len(p["p_rows"]), "deleted": len(p["p_delete"])})
    monkeypatch.setattr(db, "health_check", lambda: {"status": "OK", "counts": {}})
    monkeypatch.setattr(db, "debug_check", lambda: {"url": "mock", "status": "mock"})
    if hasattr(db, "count_rows"):
        monkeypatch.setattr(db, "count_rows", lambda *a, **k: 0)
    return db


def _open(plan_db):
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    for _c in (st.cache_data, st.cache_resource):
        try:
            _c.clear()
        except Exception:
            pass
    at = AppTest.from_file(APP_FILE, default_timeout=60)
    at.secrets["supabase"] = {"url": "https://mock.supabase.local",
                              "anon_key": "a", "service_role_key": "s"}
    at.secrets["auth"] = {"disabled": True}
    at.run()
    at.sidebar.radio[0].set_value("생산 계획")
    at.sidebar.radio[1].set_value(None)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def _texts(at):
    out = []
    for f in at.dataframe:
        try:
            out.append(f.value.to_string())
        except Exception:
            pass
    return "\n".join(out)


def test_tabs_and_summary_render(plan_db):
    at = _open(plan_db)
    labels = [t.label for t in at.tabs]
    assert labels[:4] == ["주간 계획", "설비 스케줄", "공정 표준", "설비"]
    txt = _texts(at)
    assert "CNC" in txt and "MCT" in txt
    # CNC 필요 8.5h? → 5.5(행1) + 미정(행2) = 5.5, MCT 3.0 ; UPH 미정 1행 경고
    assert "5.5" in txt and "3.0" in txt
    assert any("UPH 미정 1행" in w.value for w in at.warning)
    assert not any(c.value for c in at.caption if "주간" in c.value), "설명은 help 로만"


def test_board_survives_stale_modules(plan_db, monkeypatch):
    """Cloud 재시작 전 구버전 모듈: build_board 가 hours_fn 을 모르고 weekly_plan 에
    machine_shift_hours 가 없어도 보드 탭은 경고 1건과 함께 그려진다 (2026-10-14 사고)."""
    import utils.schedule as sch
    import utils.weekly_plan as wp
    real = sch.build_board

    def old_build_board(machines, days, sched, logs, today):
        return real(machines, days, sched, logs, today)
    monkeypatch.setattr(sch, "build_board", old_build_board)
    monkeypatch.delattr(wp, "machine_shift_hours")
    at = _open(plan_db)
    assert not at.exception, [str(e.value) for e in at.exception]
    assert sum(1 for w in at.warning if "구버전 모듈" in w.value) == 1


def test_week_navigation_is_independent_from_board(plan_db):
    at = _open(plan_db)
    at.button(key="wp_prev").click().run()
    assert not at.exception
    assert at.session_state["wp_week"] == WEEK - timedelta(days=7)
    assert "sb_week" not in at.session_state or at.session_state["sb_week"] != WEEK - timedelta(days=7)
    at.button(key="wp_this").click().run()
    assert at.session_state["wp_week"] == TODAY


def test_save_without_edits_calls_rpc_with_fingerprint(plan_db):
    at = _open(plan_db)
    btn = next(b for b in at.button if b.label == "저장" and "wp_form" in str(getattr(b, "form_id", "")))
    btn.click().run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert len(CALLS["rpc"]) == 1
    name, params = CALLS["rpc"][0]
    assert name == "save_week_plan"
    assert params["p_week"] == WEEK.isoformat()
    assert params["p_fingerprint"] == "3:6:1791939600"      # floor(epoch(2026-10-14T01:00Z))
    assert [r["plan_item_id"] for r in params["p_rows"]] == [1, 2, 3]
    assert params["p_delete"] == []
    assert all("hours" not in r for r in params["p_rows"]), "hours 는 생성 컬럼 — 보내지 않는다"
    assert params["p_rows"][0]["uph_source"] == "CONFIRMED"      # 참고값 그대로 → 출처 유지
    assert params["p_rows"][1]["uph"] is None and params["p_rows"][1]["uph_source"] is None
    assert any("저장" in s.value for s in at.success)
    assert CALLS["insert"] == [] and CALLS["update"] == [] and CALLS["delete"] == []
    assert at.session_state["wp_nonce"] == 1
    assert all("_ui_row" not in r for r in params["p_rows"])


def test_save_rejected_stale_shows_message_and_no_writes(plan_db, monkeypatch):
    def _rpc(n, p=None, **k):
        raise plan_db.RpcRejected("P0001", "stale")
    monkeypatch.setattr(plan_db, "rpc", _rpc)
    at = _open(plan_db)
    btn = next(b for b in at.button if b.label == "저장" and "wp_form" in str(getattr(b, "form_id", "")))
    btn.click().run()
    assert any("다른 곳에서 바뀌었습니다" in e.value for e in at.error)
    assert CALLS["insert"] == [] and CALLS["update"] == [] and CALLS["delete"] == []
    assert at.session_state["wp_nonce"] == 0 and len(at.session_state["wp_rows"]) == 3


def test_save_transport_error_asks_to_reload(plan_db, monkeypatch):
    def _rpc(n, p=None, **k):
        raise plan_db.RpcTransportError("timeout")
    monkeypatch.setattr(plan_db, "rpc", _rpc)
    at = _open(plan_db)
    btn = next(b for b in at.button if b.label == "저장" and "wp_form" in str(getattr(b, "form_id", "")))
    btn.click().run()
    assert any("반영됐을 수 있으니" in e.value for e in at.error)
    assert CALLS["insert"] == [] and CALLS["update"] == [] and CALLS["delete"] == []


def test_add_product_expands_standard_ops(plan_db, monkeypatch):
    monkeypatch.setattr(plan_db, "fetch", lambda t, s="*", f="", limit=1000, cache=None:
                        [] if t == "production_plan_items" else _fetch(t, s, f, limit))
    at = _open(plan_db)
    at.text_input(key="wp_q").set_value("4PDVN")
    next(b for b in at.button
         if b.label == "검색" and "wp_search_form" in str(getattr(b, "form_id", ""))).click().run()
    at.button(key="wp_add").click().run()
    assert not at.exception, [str(e.value) for e in at.exception]
    rows = at.session_state["wp_rows"]
    assert len(rows) == 1 and rows[0]["op_label"] == "4PDVN-03#10"
    assert rows[0]["uph"] == 20.0 and rows[0]["uph_source"] == "CONFIRMED"
    assert rows[0]["plan_item_id"] is None and rows[0]["qty"] == 0
    assert any("저장되지 않은 행 1개" in w.value for w in at.warning)
    at.button(key="wp_next").click().run()
    try:
        left = at.session_state["wp_rows"]
    except KeyError:
        left = []
    assert left == [], "주 이동 뒤 미저장 행은 남지 않는다(경고로 안내)"


def test_machine_add_rejects_bad_id_and_group(plan_db):
    at = _open(plan_db)
    ti = [t for t in at.text_input if t.label == "설비 ID"][0]
    ti.set_value("28")
    next(b for b in at.button if b.label == "설비 등록").click().run()
    assert any("영문 + 번호" in e.value for e in at.error) and CALLS["insert"] == []
    at2 = _open(plan_db)
    [t for t in at2.text_input if t.label == "설비 ID"][0].set_value("CNC30")
    [t for t in at2.text_input if t.label == "장비군"][0].set_value("MCT-5")
    next(b for b in at2.button if b.label == "설비 등록").click().run()
    assert any("장비군" in e.value and "영문 대문자" in e.value for e in at2.error), [e.value for e in at2.error]
    assert CALLS["insert"] == []


def test_machine_editor_includes_sat_active_column(plan_db):
    at = _open(plan_db)
    cols = [list(f.value.columns) for f in at.dataframe]
    assert any("토·공휴일 가동" in c for c in cols)


def test_machine_add_normalizes_and_rejects_duplicate(plan_db):
    at = _open(plan_db)
    ti = [t for t in at.text_input if t.label == "설비 ID"][0]
    ti.set_value("cnc 7")
    btn = next(b for b in at.button if b.label == "설비 등록")
    btn.click().run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert CALLS["insert"] and CALLS["insert"][-1][0] == "machines"
    rec = CALLS["insert"][-1][1][0]
    assert rec["machine_id"] == "CNC07" and rec["group_code"] == "CNC" and rec["sat_active"] is True
    # 중복
    at2 = _open(plan_db)
    ti = [t for t in at2.text_input if t.label == "설비 ID"][0]
    ti.set_value("CNC01")
    next(b for b in at2.button if b.label == "설비 등록").click().run()
    assert any("이미 등록된 설비" in e.value for e in at2.error)


def test_shift_profile_save_without_change_is_noop(plan_db):
    at = _open(plan_db)
    next(b for b in at.button if b.label == "근무 체계 저장").click().run()
    assert not at.exception
    assert any("변경 없음" in s.value for s in at.success)
    assert CALLS["update"] == []
    at.number_input(key="sp_WEEKDAY_d").set_value(9.0)
    next(b for b in at.button if b.label == "근무 체계 저장").click().run()
    assert [u for u in CALLS["update"] if u[0] == "shift_profiles"] == [
        ("shift_profiles", "day_type=eq.WEEKDAY",
         {"day_hours": 9.0, "night_hours": 10.0, "updated_at": "now()"})]
    assert any("근무 체계 1건 저장" in s.value for s in at.success)


def test_calendar_rejects_sunday_holiday(plan_db):
    at = _open(plan_db)
    sunday = WEEK + timedelta(days=6)
    at.date_input(key="cal_date_in").set_value(sunday)
    next(b for b in at.button
         if b.label == "등록" and "cal_add_form" in str(getattr(b, "form_id", ""))).click().run()
    assert any("일요일은 휴무" in e.value for e in at.error), [e.value for e in at.error]
    assert CALLS["insert"] == []
