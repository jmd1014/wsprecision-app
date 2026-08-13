# -*- coding: utf-8 -*-
"""공정 라우팅 (Migration 036) — 라우팅 편집 탭 + 공정 처리 스테퍼 검증."""
import os
import sys
import importlib.util

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

streamlit_available = importlib.util.find_spec("streamlit") is not None
pytestmark = pytest.mark.skipif(
    not streamlit_available, reason="streamlit 미설치 — AppTest 불가")

APP_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "streamlit_app.py")

# MRG6-07 시나리오 — 소재열처리(고용화, MATERIAL 단계)와
# 제품열처리(에이징, PRODUCT 단계)가 구분되는 라우팅
ROUTING = [
    {"routing_id": 1, "product_id": "P1", "seq": 1, "step_code": "MAT_IN",
     "step_name": "소재입고", "step_kind": "INHOUSE", "stage": "MATERIAL",
     "bom_id": None, "confirmed": False},
    {"routing_id": 2, "product_id": "P1", "seq": 5, "step_code": "OUT",
     "step_name": "고용화", "step_kind": "OUTSOURCE", "stage": "MATERIAL",
     "bom_id": 346, "confirmed": False},
    {"routing_id": 3, "product_id": "P1", "seq": 10, "step_code": "PROD",
     "step_name": "생산", "step_kind": "INHOUSE", "stage": "PRODUCT",
     "bom_id": None, "confirmed": False},
    {"routing_id": 4, "product_id": "P1", "seq": 12, "step_code": "OUT",
     "step_name": "에이징", "step_kind": "OUTSOURCE", "stage": "PRODUCT",
     "bom_id": 347, "confirmed": False},
    {"routing_id": 5, "product_id": "P1", "seq": 50, "step_code": "INSPECT",
     "step_name": "검사", "step_kind": "INHOUSE", "stage": "PRODUCT",
     "bom_id": None, "confirmed": False},
    {"routing_id": 6, "product_id": "P1", "seq": 60, "step_code": "DONE",
     "step_name": "완성", "step_kind": "INHOUSE", "stage": "PRODUCT",
     "bom_id": None, "confirmed": False},
]

WO = {"wo_id": 9, "wo_number": "20260812-001", "product_id": "P1",
      "pn": "MRG6-07", "material_id": "M1", "w_lot": "W2608-001",
      "input_qty": 100.0, "received_qty": 40.0, "outsource_qty": 0.0,
      "outsource_in_qty": 0.0, "pass_qty": 0.0, "tokusai_qty": 0.0,
      "rework_qty": 0.0, "rework_in_qty": 0.0, "scrap_qty": 0.0,
      "output_qty": 0.0, "return_qty": 0.0, "status": "IN_PROD",
      "remark": None, "created_by": "테스트",
      "created_at": "2026-08-12T00:00:00+00:00",
      "updated_at": "2026-08-12T00:00:00+00:00"}

WO_LIST = [WO]

MAT_EVENTS = [
    {"event_id": 1, "event_type": "MAT_OUT_SEND", "qty": 100,
     "step_name": "고용화", "detail": {"vendor": "성보정밀"},
     "event_date": "2026-08-10", "created_by": "테스트"},
    {"event_id": 2, "event_type": "MAT_OUT_RETURN", "qty": 100,
     "step_name": "고용화", "detail": {"vendor": "성보정밀"},
     "event_date": "2026-08-11", "created_by": "테스트"},
]

INSERTED = []


def _fetch(table, select="*", filter_query="", limit=1000):
    if table == "product_routing":
        if "confirmed=eq.false" in filter_query:
            return [r for r in ROUTING if not r["confirmed"]]
        if "product_id=eq.P1" in filter_query:
            return sorted(ROUTING, key=lambda r: r["seq"])
        return []
    if table == "products":
        if "ilike" in filter_query and "MRG6" in filter_query:
            return [{"product_id": "P1", "pn": "MRG6-07",
                     "item_name": "가이드핀"}]
        if "product_id=in." in filter_query and "P1" in filter_query:
            return [{"product_id": "P1", "pn": "MRG6-07"}]
        return []
    if table == "bom":
        if "process_type=neq.MATERIAL" in filter_query:
            return [{"bom_id": 346, "process_type": "HEAT",
                     "raw_material_name": "고용화", "unit_price": 200000},
                    {"bom_id": 347, "process_type": "HEAT",
                     "raw_material_name": "에이징", "unit_price": 200000}]
        return []
    if table == "wo_tracking":
        return [dict(w) for w in WO_LIST]
    if table == "wo_events":
        if "MAT_OUT" in filter_query:
            return [dict(e) for e in MAT_EVENTS]
        return []
    if table == "vendors":
        if "in_use=eq.true" in filter_query:
            return [{"name": "성보정밀"}]
        return []
    return []


def _fetch_one(table, filter_query, select="*"):
    rows = _fetch(table, select, filter_query, 1)
    return rows[0] if rows else None


@pytest.fixture
def routing_db(monkeypatch):
    import db
    INSERTED.clear()
    WO_LIST[:] = [WO]
    monkeypatch.setattr(db, "fetch", _fetch)
    monkeypatch.setattr(db, "fetch_one", _fetch_one)
    monkeypatch.setattr(db, "insert",
                        lambda t, recs: INSERTED.append((t, recs)) or 1)
    monkeypatch.setattr(db, "update", lambda t, f, v: True)
    monkeypatch.setattr(db, "delete", lambda t, f: 1)
    monkeypatch.setattr(db, "health_check",
                        lambda: {"status": "ok", "detail": "mock"})
    monkeypatch.setattr(db, "debug_check", lambda: {"status": "mock"})
    return db


def _boot(routing_db):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP_FILE, default_timeout=60)
    at.secrets["supabase"] = {"url": "https://mock.local",
                              "anon_key": "a", "service_role_key": "s"}
    at.secrets["auth"] = {"disabled": True}
    at.run()
    return at


def test_routing_editor_tab(routing_db):
    """마스터 관리 > 공정 라우팅 — 확정 대기 경고 + 편집기 + 저장 버튼."""
    at = _boot(routing_db)
    at.sidebar.radio[0].set_value(None)
    at.sidebar.radio[1].set_value("마스터 관리")
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]

    # 확정 대기 경고에 시드 제품 표기
    warns = " ".join(w.value for w in at.warning)
    assert "순서 확정 필요" in warns and "MRG6-07" in warns

    # 제품 검색 → 편집기 + 저장 버튼
    at.text_input(key="rout_q").set_value("MRG6-07")
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    btn_labels = [b.label for b in at.button]
    assert any("라우팅 저장" in l for l in btn_labels)


def test_process_stepper_follows_routing(routing_db):
    """공정 처리 — 스테퍼가 라우팅 순서를 따르고, 소재 외주(고용화)
    회수 완료가 반영되며, 외주 출고 공정 선택지가 라우팅에서 온다."""
    at = _boot(routing_db)
    at.sidebar.radio[0].set_value("공정 관리")
    at.sidebar.radio[1].set_value(None)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]

    md = " ".join(m.value for m in at.markdown)
    # 스테퍼가 라우팅 이름·순서로 렌더 (소재입고 → 고용화 → 생산 → 에이징)
    assert '<div class="stepper">' in md
    _i_mat = md.find(">소재입고<")
    _i_sol = md.find(">고용화<")
    _i_prod = md.find(">생산<")
    _i_age = md.find(">에이징<")
    assert -1 not in (_i_mat, _i_sol, _i_prod, _i_age)
    assert _i_mat < _i_sol < _i_prod < _i_age
    # 소재 외주(고용화)는 회수 완료 → done 칸
    assert 'step done">고용화' in md
    # 순차 강제 — 에이징(외주)이 남아 있으므로 '검사'는 잠긴다
    _pr = next(r for r in at.radio
               if r.options and "외주 출고" in r.options)
    assert "검사" not in _pr.options, "라우팅 순차 강제 실패 — 검사가 열려 있음"
    # 외주 출고 → 가공 공정이 다음 라우팅 공정(에이징)으로 고정
    _pr.set_value("외주 출고")
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    _fx = [t for t in at.text_input if t.key == "pe_o_proc_fixed"]
    assert _fx and _fx[0].value == "에이징", "다음 외주 공정 고정 실패"


def test_input_cancel_action(routing_db):
    """투입 취소 — 후속 처리 없는 투입만 관리자에게 노출, 실행 시
    취소 이벤트 기록 + 작업지시 삭제."""
    # 후속 처리 없는 갓 투입된 지시
    WO_LIST[:] = [dict(WO, received_qty=0.0, status="IN_PROD")]
    at = _boot(routing_db)
    at.sidebar.radio[0].set_value("공정 관리")
    at.sidebar.radio[1].set_value(None)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    _pr = next(r for r in at.radio
               if r.options and "완료 인수" in r.options)
    assert "투입 취소" in _pr.options
    _pr.set_value("투입 취소")
    at.run()
    at.checkbox(key="pe_cx_ok").set_value(True)
    at.run()
    at.button(key="pe_cx_btn").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    _ev = [(t, r) for t, recs in INSERTED if t == "wo_events"
           for r in recs if r.get("event_type") == "INPUT_CANCEL"]
    assert _ev, "INPUT_CANCEL 이벤트가 기록되지 않음"


def test_input_cancel_hidden_after_downstream(routing_db):
    """후속 처리(인수)가 시작된 지시에는 투입 취소가 노출되지 않는다."""
    WO_LIST[:] = [dict(WO)]  # received_qty 40 — 후속 있음
    at = _boot(routing_db)
    at.sidebar.radio[0].set_value("공정 관리")
    at.sidebar.radio[1].set_value(None)
    at.run()
    _pr = next(r for r in at.radio
               if r.options and ("외주 출고" in r.options
                                 or "완료 인수" in r.options))
    assert "투입 취소" not in _pr.options
