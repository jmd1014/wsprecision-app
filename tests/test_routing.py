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
     "bom_id": 346, "default_vendor": "성보정밀", "confirmed": False},
    {"routing_id": 3, "product_id": "P1", "seq": 10, "step_code": "PROD",
     "step_name": "생산", "step_kind": "INHOUSE", "stage": "PRODUCT",
     "bom_id": None, "confirmed": False},
    {"routing_id": 4, "product_id": "P1", "seq": 12, "step_code": "OUT",
     "step_name": "에이징", "step_kind": "OUTSOURCE", "stage": "PRODUCT",
     "bom_id": 347, "default_vendor": "성보정밀", "confirmed": False},
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

MAT_EVENTS_FULL = [
    {"event_id": 1, "event_type": "MAT_OUT_SEND", "qty": 100,
     "routing_id": 2, "step_name": "고용화",
     "detail": {"vendor": "성보정밀"},
     "event_date": "2026-08-10", "created_by": "테스트"},
    {"event_id": 2, "event_type": "MAT_OUT_RETURN", "qty": 100,
     "routing_id": 2, "step_name": "고용화",
     "detail": {"vendor": "성보정밀"},
     "event_date": "2026-08-11", "created_by": "테스트"},
]
MAT_EVENTS = list(MAT_EVENTS_FULL)

# 투입 등록 탭용 — 잔여 소재 W-LOT (RECEIPT 210)
W_LOT_TXNS = [
    {"lot_number": "W2608-001", "material_id": "M1", "qty": 210.0,
     "txn_type": "RECEIPT", "ref_id": None},
]

# 공정 배치 (Phase B) — 기본: 인수분 40 이 에이징 대기
WO_BATCHES_FULL = [
    {"batch_id": 1, "batch_no": "20260812-001-B", "wo_id": 9,
     "wo_number": "20260812-001", "qty": 40.0, "step_code": "OUT",
     "routing_id": 4, "step_name": "에이징", "location": "사내",
     "status": "OPEN"},
]
WO_BATCHES = list(WO_BATCHES_FULL)

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
        if "pn=eq.MRG6-07" in filter_query:
            return [{"product_id": "P1", "pn": "MRG6-07"}]
        if "product_id=in." in filter_query and "P1" in filter_query:
            return [{"product_id": "P1", "pn": "MRG6-07"}]
        return []
    if table == "bom":
        if ("product_id=eq.P1" in filter_query
                and "material_id=eq.M1" in filter_query):
            return [{"qty_per_pc": 1, "shared_factor": 1,
                     "bom_id": 164, "material_id": "M1",
                     "process_type": "MATERIAL"}]
        if "material_id=eq.M1" in filter_query:
            return [{"product_id": "P1"}]
        if "product_id=eq.P1" in filter_query:
            return [{"bom_id": 346, "process_type": "HEAT",
                     "raw_material_name": "고용화", "unit_price": 200000},
                    {"bom_id": 347, "process_type": "HEAT",
                     "raw_material_name": "에이징", "unit_price": 200000}]
        return []
    if table == "inventory_transactions":
        if "lot_number=like.W*" in filter_query:
            return [dict(t) for t in W_LOT_TXNS]
        return []
    if table == "materials":
        if "material_id=in." in filter_query:
            return [{"material_id": "M1", "raw_name": "S630"}]
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
    if table == "wo_batches":
        return [dict(b) for b in WO_BATCHES]
    return []


def _fetch_one(table, filter_query, select="*"):
    rows = _fetch(table, select, filter_query, 1)
    return rows[0] if rows else None


@pytest.fixture
def routing_db(monkeypatch):
    import db
    INSERTED.clear()
    WO_LIST[:] = [WO]
    MAT_EVENTS[:] = list(MAT_EVENTS_FULL)
    WO_BATCHES[:] = [dict(b) for b in WO_BATCHES_FULL]
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
    # 배치 경로 (Phase B) — 에이징 대기 배치가 선택되어 외주 출고
    # 폼이 열리고, 공정·승인 업체가 고정 표시된다
    assert "20260812-001-B" in md, "배치 처리 섹션이 렌더되지 않음"
    _fp = [t for t in at.text_input if (t.key or "") == "bt_p_1"]
    assert _fp and _fp[0].value == "에이징", "배치 공정 고정 실패"
    _fv = [t for t in at.text_input if (t.key or "") == "bt_v_1"]
    assert _fv and _fv[0].value == "성보정밀", "승인 업체 고정 실패"
    # 레거시 수량 풀 radio(검사/외주 선택)는 배치 경로에서 비노출
    assert not any(r.options and "검사" in r.options for r in at.radio), \
        "배치 경로에서 레거시 검사 선택지가 노출됨"


def test_material_outsource_gate_blocks_input(routing_db):
    """소재 외주 미완료면 투입 차단 — 배너에 고정 업체 표시,
    관리자 우회 체크 시에만 투입 버튼이 열린다."""
    MAT_EVENTS[:] = []          # 소재 외주 이력 없음
    at = _boot(routing_db)
    at.sidebar.radio[0].set_value("공정 관리")
    at.sidebar.radio[1].set_value(None)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]

    _errs = " ".join(e.value for e in at.error)
    assert "선행 공정 미완료" in _errs and "고용화" in _errs
    # 작업지시 NO 를 채워도 투입 버튼은 잠겨 있어야 한다
    at.text_input(key="pe_wo_no").set_value("20260812-099")
    at.run()
    assert at.button(key="pe_in_submit").disabled, "소재 외주 차단 실패"
    # 배너의 공정·업체 고정 표기
    _bp = [t for t in at.text_input if (t.key or "").startswith("mo2_p_")]
    assert _bp and _bp[0].value == "고용화"
    _bv = [t for t in at.text_input if (t.key or "").startswith("mo2_v_")]
    assert _bv and _bv[0].value == "성보정밀"
    # 관리자 우회 → 투입 버튼 활성
    _ov = [c for c in at.checkbox if (c.key or "").startswith("mo2_ov_")]
    assert _ov, "관리자 우회 체크박스가 없습니다"
    _ov[0].set_value(True)
    at.run()
    assert not at.button(key="pe_in_submit").disabled


def test_batch_split_on_partial_outsource(routing_db):
    """부분 출고 = 자동 분기 — 새 배치 생성 + SPLIT 계보 + 이벤트에
    배치번호 기록 (수량 분기 추적의 핵심 경로)."""
    at = _boot(routing_db)
    at.sidebar.radio[0].set_value("공정 관리")
    at.sidebar.radio[1].set_value(None)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    at.number_input(key="bt_oq_1").set_value(20.0)
    at.run()
    at.button(key="bt_o_btn_1").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    _nb = [r for t, recs in INSERTED if t == "wo_batches" for r in recs]
    assert _nb and float(_nb[0]["qty"]) == 20.0, "분기 배치 미생성"
    assert _nb[0]["location"] == "성보정밀", "분기 배치 위치(거래처) 오류"
    _lk = [r for t, recs in INSERTED if t == "batch_links" for r in recs]
    assert _lk and _lk[0]["link_type"] == "SPLIT" \
        and float(_lk[0]["qty"]) == 20.0, "SPLIT 계보 미기록"
    _ev = [r for t, recs in INSERTED if t == "wo_events" for r in recs
           if r.get("event_type") == "OUT_SEND"]
    assert _ev and (_ev[0].get("detail") or {}).get("batch_no"), \
        "출고 이벤트에 배치번호 누락"


def test_input_cancel_action(routing_db):
    """투입 취소 — 후속 처리 없는 투입만 관리자에게 노출, 실행 시
    취소 이벤트 기록 + 작업지시 삭제. 배치(생산 위치)에는 인수
    버튼이 열린다."""
    # 후속 처리 없는 갓 투입된 지시 + 생산 위치 배치
    WO_LIST[:] = [dict(WO, received_qty=0.0, status="IN_PROD")]
    WO_BATCHES[:] = [{"batch_id": 1, "batch_no": "20260812-001-A",
                      "wo_id": 9, "wo_number": "20260812-001",
                      "qty": 100.0, "step_code": "PROD",
                      "routing_id": None, "step_name": "생산",
                      "location": "사내", "status": "OPEN"}]
    at = _boot(routing_db)
    at.sidebar.radio[0].set_value("공정 관리")
    at.sidebar.radio[1].set_value(None)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    # 배치 경로: 인수 버튼 존재
    assert at.button(key="bt_rq_btn_1"), "배치 인수 버튼이 없습니다"
    # 투입 취소 radio (배치 경로에서도 유지)
    _pr = next(r for r in at.radio
               if r.options and "투입 취소" in r.options)
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
    assert not any(r.options and "투입 취소" in r.options
                   for r in at.radio)
