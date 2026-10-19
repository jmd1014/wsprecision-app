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

from tests.conftest import (goto, nav_menu_labels, nav_sub_labels, nav_title,   # noqa: E402
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
        by_label[lbl] = set(re.findall(r'^    if _sub == "(\w+)":', src[a:b], re.M))
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
    # 사이드바 버튼 직접 클릭 경로 — 세부 버튼
    at.sidebar.button(key="nav_s_ship_fstock").click()
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
    assert _has_title(at, "po", "sug")


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

def test_po_suggestion_button_switches_to_new_po(hist_db):
    at = _at()
    goto(at, "po", "sug")
    vsel = [s for s in at.selectbox if str(s.key or "").startswith("po_vsel_")]
    if vsel:                                  # 거래처 미지정 묶음이면 먼저 고른다
        vsel[0].set_value("혜성철강(주)"); at.run()
    btn = [b for b in at.button if str(b.key or "").startswith("go_po_")]
    assert btn and not btn[0].disabled
    btn[0].click(); at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert _has_title(at, "po", "new")
    assert at.session_state["nav_sub"]["po"] == "new"
    assert at.session_state["po_prefill_vendor_name"] == "혜성철강(주)"
    n = len(at.session_state["po_prefill_items"])
    assert n >= 1 and len(at.session_state["po_items"]) == n
    assert at.radio(key="po_bucket").value == "소재"            # MAT_CARBON → 소재
    assert "혜성철강" in str(at.selectbox(key="po_vendor").value)
    assert any("미리 담긴 발주 데이터" in str(i.value) for i in at.info)


def test_po_copy_switches_to_new_po(hist_db):
    at = _at()
    goto(at, "po", "hist")
    at.button(key="po_copy_7").click(); at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert _has_title(at, "po", "new")
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
    calls.clear(); goto(at, "po", "sug")
    assert _mr_calls() == 1
    calls.clear(); goto(at, "po", "new")              # 5분 캐시 안 → 추가 0회
    assert _mr_calls() == 0


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
