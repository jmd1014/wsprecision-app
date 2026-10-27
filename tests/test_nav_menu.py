# -*- coding: utf-8 -*-
"""메뉴 구조 개편 — 사이드바 2단 (계획서 v3 §6-2 추가 테스트 1~10, 2026-10-19).

기존 페이지별 fixture(비어 있지 않은 목 데이터)를 재사용한다: 출고 ship_db, 공정 routing_db,
생산 계획 plan_db, 수주 sched_db, 구매 hist_db, 로그인 auth_db.
"""
import os
import re
import sys
import logging
import importlib.util
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from tests.conftest import (goto, msg_texts, nav_menu_labels, nav_sub_labels, nav_title,   # noqa: E402
                            NAV_LABELS, NAV_ADMIN_LABELS)
from tests.test_bulk_delivery import (ship_db, _open_shipping, _register,       # noqa: E402,F401
                                      SHIPMENTS, UPDATED as SHIP_UPDATED)
from tests.test_routing import routing_db, _boot                              # noqa: E402,F401
from tests.test_weekly_plan_page import plan_db, _open as _open_plan          # noqa: E402,F401
from tests.test_delivery_schedule_gantt import sched_db                       # noqa: E402,F401
from tests.test_po_history_pending import hist_db                             # noqa: E402,F401
from tests.test_auth import auth_db, _make as _make_auth, _login              # noqa: E402,F401

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("streamlit") is None, reason="streamlit 미설치 — AppTest 불가")

APP_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "streamlit_app.py")


def _at():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP_FILE, default_timeout=60)
    at.secrets["supabase"] = {"url": "https://mock.local", "anon_key": "a",
                              "service_role_key": "s"}
    at.secrets["auth"] = {"disabled": True}
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def _titles(at):
    return ([str(h.value) for h in at.subheader]
            + [str(m.value) for m in at.markdown])


def _has_title(at, main, sub):
    return any(nav_title(main, sub) in t for t in _titles(at))


# ─── 1. 비어 있지 않은 목 데이터로 6개 메뉴 × 모든 세부 화면 렌더 ───────────────────

def _render_all(at, main):
    for sk, _ in NAV_LABELS[main][1]:
        goto(at, main, sk)          # goto 가 예외 없음 + 제목 줄을 확인한다
        assert _has_title(at, main, sk)


def test_all_subscreens_render_ship(ship_db):
    _render_all(_at(), "ship")


def test_all_subscreens_render_proc(routing_db):
    _render_all(_at(), "proc")


def test_all_subscreens_render_plan(plan_db):
    _render_all(_at(), "plan")


def test_all_subscreens_render_so(sched_db):
    _render_all(_at(), "so")


def test_all_subscreens_render_po(hist_db):
    _render_all(_at(), "po")


def test_home_renders_without_title_line(ship_db):
    at = _at()
    goto(at, "home")
    assert at.session_state["nav_page"] == "home"
    assert not any(" › " in t for t in [str(h.value) for h in at.subheader])


# ─── 2. NAV ↔ 소스 `_sub == "<키>"` 1:1 정적 검사 + 없는 nav_sub 보정 ─────────────

def test_nav_keys_match_source_branches():
    src = open(APP_FILE, encoding="utf-8").read()
    # 페이지 블록으로 나눠 세부 분기 키를 모은다
    heads = [(m.start(), m.group(1)) for m in re.finditer(r'^elif page == "([^"]+)":', src, re.M)]
    heads.append((len(src), None))
    by_label = {}
    for (a, lbl), (b, _) in zip(heads, heads[1:]):
        by_label[lbl] = set(re.findall(r'^    if _sub == "(\w+)"', src[a:b], re.M))
    for mk, (lbl, subs) in NAV_LABELS.items():
        if not subs:
            continue
        assert by_label.get(lbl) == {k for k, _ in subs}, (lbl, by_label.get(lbl), subs)
    # 소스의 NAV 정의와 테스트 테이블이 같다
    for mk, (lbl, subs) in NAV_LABELS.items():
        assert f'("{mk}", "{lbl}"' in src, mk
        for k, l in subs:
            assert f'("{k}", "{l}")' in src, (mk, k)
    for mk, lbl in NAV_ADMIN_LABELS.items():
        assert f'("{mk}", "{lbl}")' in src, mk
    # st.tabs 는 사용자 영역 5개 페이지에 남아 있지 않다
    user_block = src[heads[0][0]:]
    for lbl in [v[0] for v in NAV_LABELS.values() if v[1]]:
        a = src.index(f'elif page == "{lbl}":')
        b = min([m.start() for m in re.finditer(r'^elif page == ', src[a + 10:], re.M)] or [len(src) - a - 10]) + a + 10
        assert "st.tabs(" not in src[a:b], lbl


def test_unknown_nav_sub_falls_back_to_first(ship_db):
    at = _at()
    at.session_state["nav_page"] = "ship"
    at.session_state["nav_sub"] = {"ship": "bogus"}
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert _has_title(at, "ship", "deliver")


def test_no_tab_wording_in_user_pages():
    """§4-6: 사용자 영역 문자열에 '탭에서/탭의/탭에' 가 남아 있지 않다(주석 제외)."""
    src = open(APP_FILE, encoding="utf-8").read()
    a = src.index('elif page == "수주 관리":')
    b = src.index('elif page == "생산 보고":')
    bad = [l for l in src[a:b].split("\n")
           if re.search(r"탭(에서|의|에 )", l) and not l.strip().startswith("#")]
    assert not bad, bad[:5]


# ─── 3. 메인 전환 후 복귀 시 마지막 세부 유지 · 버튼 클릭 1회 = 실행 1회 ─────────────

def test_main_switch_keeps_last_sub_and_button_click_is_single_run(ship_db, monkeypatch):
    calls = []
    real = ship_db.fetch
    monkeypatch.setattr(ship_db, "fetch", lambda *a, **k: (calls.append(a[0]), real(*a, **k))[1])
    at = _at()
    goto(at, "ship", "slip")
    goto(at, "po")                                   # 메인 전환
    goto(at, "ship")                                 # 세부 없이 복귀
    assert _has_title(at, "ship", "slip"), "마지막 세부(출고 전표) 유지"
    assert at.session_state["nav_sub"]["ship"] == "slip"
    # 본문 탭 바 직접 선택 경로 — 세부(U3: 사이드바 세부 버튼 제거, 탭 바가 모든 폭)
    assert not [b for b in at.sidebar.button if str(b.key or "").startswith("nav_s_")]
    at.segmented_control(key="nav_sc_ship").set_value("완성 재고")
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert _has_title(at, "ship", "fstock")
    # 같은 화면을 다시 누르면 실행 1회(조회 수가 평범한 재실행과 같다 — st.rerun 없음)
    calls.clear(); at.run(); base = len(calls)
    calls.clear(); at.sidebar.button(key="nav_m_ship").click(); at.run()
    assert len(calls) == base, (len(calls), base)
    assert _has_title(at, "ship", "fstock")
    # 메인 버튼 클릭 → 그 메인의 마지막 세부
    at.sidebar.button(key="nav_m_po").click(); at.run()
    assert _has_title(at, "po", "new")


# ─── 4. 입력 유지 (_NAV_KEEP) — 경고 없음 ─────────────────────────────────────

class _Catch(logging.Handler):
    def __init__(self):
        super().__init__(); self.msgs = []

    def emit(self, record):
        self.msgs.append(record.getMessage())


@pytest.fixture()
def st_log():
    h = _Catch()
    for name in ("streamlit", "streamlit.elements.lib.policies"):
        logging.getLogger(name).addHandler(h)
    yield h
    for name in ("streamlit", "streamlit.elements.lib.policies"):
        logging.getLogger(name).removeHandler(h)


def test_keep_ship_date_across_subscreens(ship_db, st_log):
    at = _at()
    goto(at, "ship", "deliver")
    d = date.today() + timedelta(days=3)
    at.date_input(key="bk_ship_date").set_value(d)
    at.date_input(key="bk_date").set_value(d)
    at.checkbox(key="bk_late").set_value(False)
    at.run()
    goto(at, "ship", "fstock")
    assert not [x for x in at.date_input if x.key == "bk_ship_date"], "완성 재고에는 날짜 위젯 없음"
    goto(at, "ship", "deliver")
    assert at.date_input(key="bk_ship_date").value == d
    assert at.date_input(key="bk_date").value == d
    assert at.checkbox(key="bk_late").value is False
    goto(at, "so", "list"); goto(at, "ship", "deliver")     # 다른 메인을 다녀와도
    assert at.date_input(key="bk_ship_date").value == d
    assert not [m for m in st_log.msgs if "default value" in m], st_log.msgs


def test_keep_po_bucket_vendor_items_across_subscreens(hist_db, st_log):
    at = _at()
    at.session_state["po_mode"] = "edit"
    goto(at, "po", "new")
    at.radio(key="po_bucket").set_value("소모성")
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    at.session_state["po_items"] = [{"item_name": "절삭유", "qty": 1, "unit_price": 0, "_uid": "x1"}]
    goto(at, "po", "hist")
    goto(at, "po", "new")
    assert at.radio(key="po_bucket").value == "소모성"
    assert len(at.session_state["po_items"]) == 1
    at.radio(key="po_bucket").set_value("소재")
    at.run()
    assert at.selectbox(key="po_vendor").value is not None
    v = at.selectbox(key="po_vendor").value
    goto(at, "po", "rstat"); goto(at, "po", "new")
    assert at.radio(key="po_bucket").value == "소재"
    assert at.selectbox(key="po_vendor").value == v
    assert not [m for m in st_log.msgs if "default value" in m], st_log.msgs


def test_keep_filters_text_inputs(ship_db, st_log):
    at = _at()
    goto(at, "ship", "slip")
    next(r for r in at.radio if r.key == "cf_filter").set_value("전체")
    at.text_input(key="cf_search").set_value("SO-100")
    at.run()
    goto(at, "ship", "fstock")
    at.text_input(key="fs_q").set_value("4PDVN")
    at.run()
    goto(at, "ship", "slip")
    assert next(r for r in at.radio if r.key == "cf_filter").value == "전체"
    assert at.text_input(key="cf_search").value == "SO-100"
    goto(at, "ship", "fstock")
    assert at.text_input(key="fs_q").value == "4PDVN"
    assert not [m for m in st_log.msgs if "default value" in m], st_log.msgs


# ─── 5. 확인 게이트: 전표 A 확인창 → 다른 세부 → 복귀 시 사라짐 ─────────────────────

def test_cancel_gate_cleared_by_subscreen_switch(ship_db):
    at = _at()
    goto(at, "ship", "deliver")
    _register(at)                                   # DRAFT 전표 1
    goto(at, "ship", "slip")
    at.button(key="cf_cancel").click(); at.run()    # 작성중 취소 → 확인창
    assert [b for b in at.button if b.key == "cf_cancel_cfm_ok"]
    goto(at, "ship", "fstock")
    goto(at, "ship", "slip")
    assert not [b for b in at.button if b.key == "cf_cancel_cfm_ok"], "세부 이동 뒤 확인창 없음"
    assert "cfm_cf_cancel_1" not in at.session_state        # AppTest 세션은 키 순회 불가 — 직접 확인
    assert SHIPMENTS[0]["status"] == "DRAFT"
    assert not [u for u in SHIP_UPDATED if u[0] == "shipments" and u[2].get("status") == "CANCELLED"]


# ─── 6. 출고 흐름 한 세션: 등록 → '출고 전표 열기' → 첫 행 = 새 전표 → 확정 ─────────

def test_ship_flow_register_open_slip_confirm(ship_db):
    # 먼저 만들어진 빈 작성중 전표가 목록 앞에 있어도, '출고 전표 열기'는 새 전표를 첫 행으로
    SHIPMENTS.append({"shipment_id": 1, "ship_no": "SH-20261001-01", "ship_date": "2026-10-01",
                      "status": "DRAFT", "created_by": "테스트"})
    at = _at()
    goto(at, "ship", "deliver")
    at.button(key="ship_reg").click(); at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert len(SHIPMENTS) == 2
    new = SHIPMENTS[1]
    ship_no = new["ship_no"]
    # 자동 전환 없음 — 출고 등록에 남고, 안내 + '출고 전표 열기'
    assert _has_title(at, "ship", "deliver")
    assert any(ship_no in str(s.value) for s in at.success)
    at.button(key="nav_flash_go").click(); at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert _has_title(at, "ship", "slip")
    # 첫 행(기본 선택) = 새 전표: 빈 옛 전표가 선택됐다면 [출고 확정] 대신 '품목이 없습니다'
    # (AgGrid 표는 AppTest 에 보이지 않아 상세의 버튼·확정 결과로 판정)
    assert "ship_open_no" not in at.session_state          # 소비됨
    assert at.button(key="cf_go"), "새 전표가 첫 행이 아님"
    at.button(key="cf_go").click(); at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    soi11 = [v for t, f, v in SHIP_UPDATED if t == "sales_order_items" and "soi_id=eq.11" in f]
    assert soi11 and soi11[-1]["received_qty"] == 700
    assert new["status"] == "CONFIRMED" and SHIPMENTS[0]["status"] == "DRAFT"


# ─── 7. 자동 전환: 발주 제안 → 발주서 작성 / 복사해서 수정 ─────────────────────

def test_po_suggestion_button_switches_to_edit_mode(hist_db, st_log):
    at = _at()
    goto(at, "po", "new")
    assert at.session_state["po_mode"] == "pick", "담긴 품목이 없으면 기본 모드 = 부족 자재"
    vsel = [s for s in at.selectbox if str(s.key or "").startswith("po_vsel_")]
    if vsel:                                  # 거래처 미지정 묶음이면 먼저 고른다
        vsel[0].set_value("혜성철강(주)"); at.run()
    btn = [b for b in at.button if str(b.key or "").startswith("go_po_")]
    assert btn and not btn[0].disabled
    btn[0].click(); at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert _has_title(at, "po", "new")
    assert at.session_state["nav_sub"]["po"] == "new"
    assert at.session_state["po_mode"] == "edit", "같은 화면에서 모드 = 편집"
    assert at.session_state["po_prefill_vendor_name"] == "혜성철강(주)"
    n = len(at.session_state["po_prefill_items"])
    assert n >= 1 and len(at.session_state["po_items"]) == n
    assert at.radio(key="po_bucket").value == "소재"            # MAT_CARBON → 소재
    assert "혜성철강" in str(at.selectbox(key="po_vendor").value)
    assert any("미리 담긴 발주 데이터" in t for t in msg_texts(at))
    assert not [b for b in at.button if str(b.key or "").startswith("go_po_")], "편집 모드엔 제안 블록 없음"
    assert not [m for m in st_log.msgs if "default value" in m], st_log.msgs


def test_po_copy_switches_to_new_po(hist_db):
    at = _at()
    goto(at, "po", "hist")
    at.button(key="po_copy_7").click(); at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert _has_title(at, "po", "new")
    assert at.session_state["po_mode"] == "edit"
    assert len(at.session_state["po_items"]) == 3
    assert "26-0901" in at.session_state["po_prefill_note"]
    assert "혜성철강" in str(at.selectbox(key="po_vendor").value)


# ─── 8. _mr_compute 호출 횟수 / 입고 처리 조회 ──────────────────────────────────

def test_mr_compute_runs_only_where_used(hist_db, monkeypatch):
    calls = []
    real = hist_db.fetch

    def _f(table, select="*", filter_query="", limit=1000, **kw):
        calls.append((table, filter_query or ""))
        return real(table, select, filter_query, limit)
    monkeypatch.setattr(hist_db, "fetch", _f)

    def _mr_calls():
        return sum(1 for t, f in calls if t == "sales_order_items"
                   and "product_id=not.is.null" in f and "pending_qty=gt.0" in f)
    at = _at()
    for sk in ("hist", "rcv", "rstat", "pur"):
        calls.clear(); goto(at, "po", sk)
        assert _mr_calls() == 0, sk
    calls.clear(); goto(at, "po", "rcv")
    assert not [t for t, _ in calls if t in ("sales_order_items", "bom", "material_stock")], \
        [t for t, _ in calls if t in ("sales_order_items", "bom", "material_stock")]
    calls.clear(); goto(at, "po", "new")              # 첫 진입(부족 자재 모드) 1회
    assert at.session_state["po_mode"] == "pick"
    assert _mr_calls() == 1
    at.session_state["po_mode"] = "edit"              # 5분 안 모드 전환 → 추가 0회
    calls.clear(); at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert _mr_calls() == 0
    # 편집 모드 rerun 에는 B1 블록(부족 자재 목록·거래처별 담기)이 없다 — purchase_orders 등은 편집
    # 화면 자체(거래처 최근 단가·발주 필요 열)가 조회하므로 표 이름이 아니라 블록 요소로 판정(§10 C8)
    calls.clear(); at.run()
    assert not [b for b in at.button if str(b.key or "").startswith("go_po_")]
    assert not [e for e in at.expander if "자재 부족" in str(e.label)]
    assert _mr_calls() == 0


def test_po_mode_default_and_legacy_sug_state(hist_db):
    """기본 모드: 담긴 품목이 있으면 편집. 옛 nav_sub['po']='sug' 는 발주서 작성 + 부족 자재 모드."""
    at = _at()
    at.session_state["po_items"] = [{"item_name": "절삭유", "qty": 1, "unit_price": 0, "_uid": "x1"}]
    goto(at, "po", "new")
    assert at.session_state["po_mode"] == "edit"
    assert at.selectbox(key="po_vendor") is not None
    at2 = _at()
    at2.session_state["nav_page"] = "po"
    at2.session_state["nav_sub"] = {"po": "sug"}
    at2.run()
    assert not at2.exception, [str(e.value) for e in at2.exception]
    assert _has_title(at2, "po", "new")
    assert at2.session_state["nav_sub"]["po"] == "new" and at2.session_state["po_mode"] == "pick"
    assert [b for b in at2.button if str(b.key or "").startswith("go_po_")], "부족 자재 모드 = 제안 블록"


# ─── 9. 계정: 작업자 메뉴 / 로그인 전 / 로그아웃 뒤 ─────────────────────────────

def test_worker_has_no_admin_menu_and_is_forced_home(auth_db):
    at = _make_auth(); at.run()
    assert nav_menu_labels(at) == ([], []), "로그인 전 메뉴 버튼 0개"
    assert not [b for b in at.sidebar.button if str(b.key or "").startswith("nav_")]
    _login(at, "현장", "pw-field")
    flow, admin = nav_menu_labels(at)
    assert flow and not admin
    at.session_state["nav_page"] = "master"            # 관리자 메인 상태 강제
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert at.session_state["nav_page"] == "home"


def test_logout_clears_nav_and_kept_inputs(auth_db):
    at = _make_auth(); at.run()
    _login(at, "김민수", "pw-admin")
    goto(at, "ship", "deliver")
    d = date.today() + timedelta(days=2)
    at.date_input(key="bk_ship_date").set_value(d); at.run()
    goto(at, "ship", "fstock")
    assert at.session_state["_kv_bk_ship_date"] == d
    at.sidebar.button(key="auth_out").click(); at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    _login(at, "김민수", "pw-admin")
    assert at.session_state["nav_page"] == "home"
    assert "_kv_bk_ship_date" not in at.session_state      # 그림자 키 비움 (AppTest 세션은 순회 불가)
    goto(at, "ship", "deliver")
    assert at.date_input(key="bk_ship_date").value == date.today()


# ─── 10. 관리자 영역은 여전히 탭 ─────────────────────────────────────────────

def test_admin_pages_still_use_tabs(ship_db):
    at = _at()
    goto(at, "sales")
    assert len(at.tabs) >= 3
    goto(at, "report")
    assert len(at.tabs) >= 4
    # 관리자 페이지에는 세부 버튼이 없다
    assert not [b for b in at.sidebar.button if str(b.key or "").startswith("nav_s_")]


# ─── 보조: 세부 화면 이름 순서 = 옛 탭 순서 ────────────────────────────────────

def test_sub_labels_keep_tab_order(ship_db):
    at = _at()
    goto(at, "ship", "deliver")
    assert nav_sub_labels(at, "ship") == ["출고 등록", "출고 전표", "출고 현황", "완성 재고"]
    goto(at, "plan")
    assert nav_sub_labels(at, "plan") == ["주간 계획", "설비 스케줄", "공정 표준", "설비"]


# ─── Codex 리뷰 반영 (2026-10-19): H1 prefill 1회 적용 / H2 품목표 보류 교체 / M1 sch_view ──

VENDOR2 = {"vendor_id": 190, "name": "테스트철강(주)", "vendor_group": "MAT_STS",
           "category": None, "business_no": None, "ceo_name": None, "phone": None,
           "fax": None, "address": None, "email": None, "payment_terms": None,
           "contact_person": None, "in_use": True}


@pytest.fixture()
def hist_db2(hist_db, monkeypatch):
    """hist_db + 소재 그룹 거래처 하나 더(사용자가 다른 거래처를 고를 수 있게)."""
    real = hist_db.fetch

    def _f(table, select="*", filter_query="", limit=1000, **kw):
        if table == "vendors":
            from tests.test_po_history_pending import VENDOR
            fq = filter_query or ""
            if "name=eq." in fq:
                return [v for v in (VENDOR, VENDOR2) if v["name"] in fq]
            return [VENDOR, VENDOR2]
        return real(table, select, filter_query, limit)
    monkeypatch.setattr(hist_db, "fetch", _f)
    return hist_db


def _vendor_value(at):
    return str(at.selectbox(key="po_vendor").value)


def test_prefill_vendor_applied_once_then_user_choice_wins(hist_db2, st_log):
    """H1: prefill A 적용 뒤 사용자가 B 를 고르면 세부 화면·모드를 다녀와도 B 가 유지된다."""
    at = _at()
    goto(at, "po", "new")                               # 담긴 품목 없음 → 부족 자재 모드
    btn = [b for b in at.button if str(b.key or "").startswith("go_po_")]
    btn[0].click(); at.run()
    assert at.session_state["po_mode"] == "edit"
    assert "혜성철강" in _vendor_value(at)               # prefill 거래처 1회 적용
    b_key = next(k for k in at.selectbox(key="po_vendor").options if "테스트철강" in k)
    at.selectbox(key="po_vendor").set_value(b_key); at.run()
    assert "테스트철강" in _vendor_value(at)
    n_items = len(at.session_state["po_items"])
    goto(at, "po", "hist"); goto(at, "po", "new")
    assert "테스트철강" in _vendor_value(at), "복귀 시 사용자가 고른 B 유지"
    assert at.session_state["po_mode"] == "edit" and len(at.session_state["po_items"]) == n_items
    at.session_state["po_mode"] = "pick"; at.run()
    at.session_state["po_mode"] = "edit"; at.run()
    assert "테스트철강" in _vendor_value(at), "모드 왕복 뒤에도 B 유지"
    assert at.radio(key="po_bucket").value == "소재"
    assert any("미리 담긴 발주 데이터" in t for t in msg_texts(at))   # 안내는 그대로(한 줄 보조 설명)
    assert not [m for m in st_log.msgs if "default value" in m], st_log.msgs


def test_prefill_pending_when_items_exist(hist_db2, st_log):
    """H2: 품목표가 있으면 다른 거래처 prefill 은 보류 — [교체]/[취소]를 사용자가 고른다."""
    at = _at()
    at.session_state["po_mode"] = "edit"
    goto(at, "po", "new")
    b_key = next(k for k in at.selectbox(key="po_vendor").options if "테스트철강" in k)
    at.selectbox(key="po_vendor").set_value(b_key); at.run()
    at.session_state["po_items"] = [{"item_name": "A 품목", "qty": 1, "unit_price": 0, "_uid": "a1"}]
    at.session_state["po_mode"] = "pick"; at.run()
    btn = [b for b in at.button if str(b.key or "").startswith("go_po_")]
    btn[0].click(); at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    # 편집 모드 + 보류 안내, 거래처·품목은 그대로
    assert at.session_state["po_mode"] == "edit"
    assert at.button(key="po_pending_replace") and at.button(key="po_pending_cancel")
    assert "테스트철강" in _vendor_value(at)
    assert [x["item_name"] for x in at.session_state["po_items"]] == ["A 품목"]
    assert not at.session_state.get("po_prefill_vendor_name") if "po_prefill_vendor_name" in at.session_state else True
    # [취소] → 보류 삭제, 기존 상태 유지
    at.button(key="po_pending_cancel").click(); at.run()
    assert not [b for b in at.button if b.key == "po_pending_replace"]
    assert "테스트철강" in _vendor_value(at)
    assert [x["item_name"] for x in at.session_state["po_items"]] == ["A 품목"]
    # 다시 담기 → [교체] → B 거래처 + B 품목
    at.session_state["po_mode"] = "pick"; at.run()
    btn = [b for b in at.button if str(b.key or "").startswith("go_po_")]
    btn[0].click(); at.run()
    at.button(key="po_pending_replace").click(); at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert "혜성철강" in _vendor_value(at)
    n = len(at.session_state["po_prefill_items"])
    assert n >= 1 and len(at.session_state["po_items"]) == n
    assert "A 품목" not in [x["item_name"] for x in at.session_state["po_items"]]
    assert not [b for b in at.button if b.key == "po_pending_replace"]
    # '복사해서 수정'도 같은 경로: 품목표가 있으면 보류
    goto(at, "po", "hist")
    at.button(key="po_copy_7").click(); at.run()
    assert _has_title(at, "po", "new") and at.session_state["po_mode"] == "edit"
    assert at.button(key="po_pending_replace")
    assert len(at.session_state["po_items"]) == n                 # 그대로
    assert not [m for m in st_log.msgs if "default value" in m], st_log.msgs


def test_sch_view_kept_and_auto_switch_overrides(sched_db, st_log):
    """M1: 납품 스케줄 보기(sch_view)는 유지 대상 — 다른 세부를 다녀와도 유지, sch_view_next 자동 전환이 우선."""
    at = _at()
    goto(at, "so", "sched")
    assert at.session_state["sch_view"] == "회차 간트"
    at.session_state["sch_view"] = "납기 입력"; at.run()
    goto(at, "so", "list"); goto(at, "so", "sched")
    assert at.session_state["sch_view"] == "납기 입력", "세부 화면을 다녀와도 보기 유지"
    # 자동 전환(sch_view_next)은 그림자보다 우선
    at.session_state["_kv_sch_view"] = "회차 간트"
    at.session_state["sch_view_next"] = "납기 입력"; at.run()
    assert at.session_state["sch_view"] == "납기 입력"
    goto(at, "so", "list"); goto(at, "so", "sched")
    assert at.session_state["sch_view"] == "납기 입력"
    assert not [m for m in st_log.msgs if "default value" in m], st_log.msgs   # Codex REQUIRED 4


def test_pending_prefill_discarded_by_reset_and_new_apply(hist_db2, st_log):
    """R2-M1: 보류 요청은 [모두 초기화]·새 prefill 직접 적용·발주 생성 완료 뒤 남지 않는다."""
    at = _at()
    goto(at, "po", "new")                               # 담긴 품목 없음 → 부족 자재 모드
    btn = [b for b in at.button if str(b.key or "").startswith("go_po_")]
    btn[0].click(); at.run()                            # A 적용(편집 모드, 품목 담김)
    n_a = len(at.session_state["po_items"]); assert n_a >= 1
    at.session_state["po_mode"] = "pick"; at.run()
    btn = [b for b in at.button if str(b.key or "").startswith("go_po_")]
    btn[0].click(); at.run()                            # B 요청 → 품목표가 있어 보류
    assert at.button(key="po_pending_replace")
    # U3 r2 D1: [모두 초기화] = 담긴 품목 카드 머리 위험 버튼 + 2단계 확인
    at.button(key="po_reset_all").click(); at.run()
    assert at.session_state["po_items"], "확인 전에는 그대로"
    at.button(key="po_reset_all_cfm_ok").click(); at.run()
    assert not [b for b in at.button if b.key == "po_pending_replace"], "초기화 뒤 보류 안내 없음"
    assert "po_prefill_pending" not in at.session_state
    assert not at.session_state["po_items"]
    # 빈 품목표에 C 직접 적용 → 보류 없음, 거래처·품목 = C
    at.session_state["po_mode"] = "pick"; at.run()
    btn = [b for b in at.button if str(b.key or "").startswith("go_po_")]
    btn[0].click(); at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert not [b for b in at.button if b.key == "po_pending_replace"]
    assert "혜성철강" in _vendor_value(at) and len(at.session_state["po_items"]) == n_a
    # 보류가 있는 상태에서 새 prefill 이 빈 품목표에 직접 적용되면 보류는 새 요청으로 대체
    at.session_state["po_prefill_pending"] = {"vendor": "옛 요청", "items": [{"item_name": "x"}],
                                              "source_so": None, "note": None}
    at.session_state["po_items"] = []
    at.session_state["po_mode"] = "pick"; at.run()
    btn = [b for b in at.button if str(b.key or "").startswith("go_po_")]
    btn[0].click(); at.run()
    assert "po_prefill_pending" not in at.session_state
    assert not [b for b in at.button if b.key == "po_pending_replace"]
    # '새 발주서 시작'(품목표 비우기)도 보류를 폐기 — po_result 가 있을 때만 그려지는 버튼이라
    # 완료 카드를 세션으로 흉내 낸다(발주 생성 자체는 쓰기 흐름이라 AppTest 로 만들지 않음)
    at.session_state["po_prefill_pending"] = {"vendor": "옛 요청", "items": [{"item_name": "x"}],
                                              "source_so": None, "note": None}
    at.session_state["po_result"] = {"po_no": "26-TEST", "vendor": "혜성철강(주)", "vendor_email": None,
                                     "delivery": None, "date": "2026-10-20", "n": 1, "total": 0,
                                     "items": [{"item_name": "x", "qty": 1, "unit_price": 0}],
                                     "pdf": b"%PDF", "xlsx": b""}
    at.run()
    assert at.button(key="po_new")
    at.button(key="po_new").click(); at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert "po_prefill_pending" not in at.session_state
    assert not [m for m in st_log.msgs if "default value" in m], st_log.msgs
