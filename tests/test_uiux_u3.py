"""UI/UX 3단계 U3(안 B 화면 재배치, 2026-10-27) — DESIGN_SYSTEM v2 §A·§B 고정.

정적: 탭 바 모든 폭(992 숨김 없음)·사이드바 세부 버튼 렌더 0·새 CSS hex 0·헬퍼 존재·
      .st-key-* 셀렉터 ↔ 실제 key·발주서 품목 구간 st.info/warning ≤ 1·스테퍼 상태.
AppTest: 수주 입력 블록 순서(입력 카드 → 결과 카드 → ActionBar)·첫 화면 입력 위젯(P9)·
         주 버튼 1개·ActionBar 요약·빈 상태 맥락 문구, 출고 등록 결과 카드·ActionBar,
         발주서 작성 스테퍼 ①진행 → ①완료 ②진행 ③대기, 단계별 숨김.
"""
import ast
import importlib.util
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
APP_FILE = os.path.join(ROOT, "streamlit_app.py")
HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
streamlit_available = importlib.util.find_spec("streamlit") is not None


def _src():
    with open(APP_FILE, encoding="utf-8") as f:
        return f.read()


def _func(src, name):
    tree = ast.parse(src)
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return ast.get_source_segment(src, n)
    raise AssertionError(name)


def _u3_css():
    tree = ast.parse(_src())
    for n in tree.body:
        if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "_U3_CSS" for t in n.targets):
            return n.value.value
    raise AssertionError("_U3_CSS 없음")


# ── 정적 ─────────────────────────────────────────────────────────────────

def test_tab_bar_all_widths_and_sidebar_main_only():
    src = _src()
    # 탭 바(nav_sc_*)를 숨기는 미디어 쿼리가 없다 — 모든 폭에서 PageHeader 탭 바
    for m in re.finditer(r"@media[^{]*\{([^{}]*\{[^{}]*\}\s*)+\}", src):
        assert not ("nav_sc_" in m.group(0) and "display:none" in m.group(0).replace(" ", "")), m.group(0)
    # 사이드바 세부 버튼(nav_s_*) 을 그리는 코드가 없다(key 패턴 0)
    assert 'key=f"nav_s_' not in src
    assert not re.search(r'\[class\*="st-key-nav_s_"\]', src)
    # 현재 메인 강조: --ink 700 + --primary-bg, 왼쪽 막대(inset 3px) 없음
    a = src.index("# 선택 항목 강조"); b = src.index('st.markdown("<style>" + _nav_css', a)
    blk = src[a:b]
    assert "var(--primary-bg)" in blk and "var(--ink)" in blk and "inset 3px" not in blk
    # 탭 바: 비선택 500, 선택 700, 가로 스크롤 1줄
    u1 = src[src.index("/* ⑦ 세부 탭 바"):src.index("/* U1b ⑤")]
    assert "flex-wrap:nowrap" in u1 and "overflow-x:auto" in u1
    assert "font-weight:500" in u1 and "font-weight:700" in u1


def test_u3_css_tokens_only_and_selectors_match_keys():
    css = _u3_css()
    assert not HEX.findall(css), HEX.findall(css)
    src = _src()
    lit = set(re.findall(r'key="([A-Za-z0-9_]+)"', src)) | set(re.findall(r'"key": "([A-Za-z0-9_]+)"', src))
    fpre = set(re.findall(r'key=f"([A-Za-z0-9_]*)\{', src))
    for p in set(re.findall(r'st-key-([A-Za-z0-9_]+)"', css)) | set(re.findall(r'\.st-key-([A-Za-z0-9_]+)', css)):
        ok = any(k.startswith(p) for k in lit) or any(f.startswith(p) or p.startswith(f) for f in fpre if f)
        assert ok, f".st-key-{p} 에 대응하는 key 없음"
    tokens = set(re.findall(r'"(--[a-z0-9-]+)":', src[: src.index("def _token(")]))
    used = set(re.findall(r"var\((--[a-z0-9-]+)\)", css))
    assert used <= tokens, used - tokens
    assert "_U3_CSS" in src[src.index("@import url("):]       # 전역 CSS 에 주입


def test_helpers_exist_with_spec_signatures():
    src = _src()
    for name, sig in (("kpi_strip", "def kpi_strip(items, chips=()):"),
                      ("section_card", "def section_card(title, sub=None, right_html=None, *, key, btn=None):"),
                      ("card_head_btn", "def card_head_btn(title, sub=None, right_html=None, btn=None):"),
                      ("action_bar", "def action_bar(secondary=None, summary=\"\", primary=None, *, key):"),
                      ("stepper", "def stepper(steps, current):"),
                      ("card_head", "def card_head(title, sub=None, right_html=None):"),
                      ("_empty_state", "def _empty_state(msg=EMPTY_MSG, action=None):")):
        assert sig in src, name
    assert "mobile_cols=None" in _func(src, "toss_table")
    assert "def nav_page_head(right=None):" in src
    # 수주 세부 3화면에서 st.metric 4열 제거 → 요약 띠
    a = src.index('elif page == "수주 관리":'); b = src.index('    # 세부 화면(사이드바 2단): 수주 입력')
    assert "st.metric(" not in src[a:b] and "kpi_strip(" in src[a:b]


def test_badge_class_spec_keywords():
    ns = {}
    tree = ast.parse(_src())
    keep = [n for n in tree.body
            if (isinstance(n, ast.Assign) and any(getattr(t, "id", "").startswith("_ST_") for t in n.targets))
            or (isinstance(n, ast.FunctionDef) and n.name == "_badge_class")]
    exec(compile(ast.Module(body=keep, type_ignores=[]), APP_FILE, "exec"), ns)
    bc = ns["_badge_class"]
    assert bc("매칭") == "b-green" and bc("미매칭") == "b-amber" and bc("품번 확인") == "b-amber"
    assert bc("스케줄") == "b-blue" and bc("회차 없음") == "b-gray" and bc("지연 3") == "b-red"
    assert bc("완납") == "b-green"                     # 기존 규칙 그대로


def test_stepper_states_static():
    src = _src()
    ns = {}
    exec("import streamlit as st\nout=[]\nclass _S:\n    def markdown(self, h, **k): out.append(h)\nst=_S()\n"
         + _func(src, "stepper"), ns)
    ns["stepper"]([("① 거래처", "디와이모터스"), ("② 품목 담기", "4개"), ("③ 발주서", None)], 2)
    h = ns["out"][-1]
    assert re.findall(r'class="step (\w+)"', h) == ["done", "on", "wait"]
    assert "✓ ① 거래처" in h and "디와이모터스" in h
    ns["stepper"]([("a", None), ("b", None), ("c", None)], 4)
    assert re.findall(r'class="step (\w+)"', ns["out"][-1]) == ["done", "done", "done"]


def _guide_calls(seg):
    """st.info/st.warning 호출 중 안내(실패류 제외 — r2 D8: '실패' 가 든 경고는 세지 않는다)."""
    out = []
    for m in re.finditer(r"\bst\.(?:info|warning)\(", seg):
        if "실패" not in seg[m.end():m.end() + 160]:
            out.append(seg[m.start():m.end() + 60])
    return out


def test_po_item_section_info_warning_at_most_one():
    """발주서 작성 › ② 품목 담기 구간의 st.info/st.warning 은 1개 이하(U3 — 안내 6종 축소, 실패류 제외)."""
    src = _src()
    a = src.index('with st.container(border=True, key="wscard_po_st2"):')
    b = src.index("# ─── ③ 발주서 한 장", a)
    seg = src[a:b]
    assert len(_guide_calls(seg)) <= 1, _guide_calls(seg)
    assert 'st.warning("발주 라인에 연결된 제품 조회에 실패' in seg       # 실패는 경고 그대로(D8)
    # 편집 모드 진입부(보류 prefill 경고 1개만 st.warning) 도 포함해 셈
    e0 = src.index('    if _sub == "new" and _po_mode == "edit":')
    pre = src[e0:src.index("_po_s1 = st.container(", e0)]
    assert len(_guide_calls(pre)) <= 1


def test_po_step_hide_style_before_cards_and_actionbar_nondestructive():
    """r2 F7·D1: 단계 숨김 style 은 ① 카드보다 먼저, ActionBar 좌측에 파괴 버튼 key 없음."""
    src = _src()
    e0 = src.index('    if _sub == "new" and _po_mode == "edit":')
    i_style = src.index('+ "{display:none !important}</style>"', e0)
    i_card = src.index('_po_s1 = st.container(border=True, key="wscard_po_st1")', e0)
    assert i_style < i_card
    a = src.index("_po_sec = (None if _po_step == 1 else", e0)
    b = src.index('_po_pri, key="po")', a)
    for k in ("po_reset_all", "po_clear_all"):
        assert k not in src[a:b], k
    # 수주 ActionBar 좌측도 비파괴(None) — [초기화]는 카드 머리
    for k in ("so_up_reset", "so_m_reset"):
        i = src.index(f'"key": "{k}"')
        assert "action_bar(" not in src[i - 300:i], k
    # 숨은 단계 폼 제출 무시(⑨)
    assert "if _po_make and _po_step != 3 and not _por:" in src
    assert "if _nv_go and _po_step != 1:" in src


# ── AppTest ─────────────────────────────────────────────────────────────

app_test = pytest.mark.skipif(not streamlit_available, reason="streamlit 미설치 — AppTest 불가")

if streamlit_available:
    from tests.test_bulk_delivery import ship_db  # noqa: E402,F401  (fixture)


def _md(at):
    return [str(m.value or "") for m in at.markdown]


def _order(at, *needles):
    """마크다운 렌더 순서에서 각 needle 이 처음 나오는 위치."""
    md = _md(at)
    pos = []
    for nd in needles:
        pos.append(next(i for i, m in enumerate(md) if nd in m))
    return pos


@app_test
def test_so_input_blocks_order_first_widget_and_empty_preview(monkeypatch):
    from tests.test_uiux_u1b import _ManualSOMock
    import db as _dbmod
    from streamlit.testing.v1 import AppTest
    from tests.conftest import goto
    _ManualSOMock().install(monkeypatch, _dbmod)
    at = AppTest.from_file(APP_FILE, default_timeout=90)
    at.secrets["supabase"] = {"url": "https://mock.local", "anon_key": "a", "service_role_key": "s"}
    at.secrets["auth"] = {"disabled": True}
    at.run()
    goto(at, "so", "input")
    assert not at.exception, [str(e.value) for e in at.exception]
    # 요약 띠(KPI 4장 대신) — st.metric 없음
    assert not at.metric
    strip = next(m for m in _md(at) if 'class="kpi-strip"' in m)
    for k in ("미납 수량", "진행 수주", "납기 지연", "이번 달 수주"):
        assert k in strip
    # P9: 첫 화면에 입력 위젯(입력 방식 + 파일 업로더)
    assert at.segmented_control(key="so_mode").value == "파일 업로드 자동 파싱"
    assert at.get("file_uploader")
    # 블록 순서: 요약 띠 → 입력 카드 → 결과 카드(빈 상태 맥락 문구)
    p = _order(at, 'class="kpi-strip"', '<span class="t">입력</span>', '<span class="t">미리보기</span>',
               "파일을 올리면 여기에 미리보기가 뜹니다")
    assert p == sorted(p), p
    # PageHeader 우측 링크
    assert at.button(key="ph_go_so_list").label == "수주 목록 보기"


@app_test
def test_so_manual_actionbar_single_primary_and_summary(monkeypatch):
    from tests.test_uiux_u1b import _manual_open, _ManualSOMock
    at = _manual_open(monkeypatch, _ManualSOMock())
    prim = [b for b in at.button if getattr(b.proto, "type", "") == "primary"]
    assert [b.key for b in prim] == ["so_m_save"], [b.key for b in prim]
    assert at.button(key="so_m_save").label == "수주 저장 (3줄)"
    summ = next(m for m in _md(at) if 'class="ws-ab-sum"' in m)
    assert "3줄" in summ and "합계 6,000원 (부가세 별도)" in summ, summ   # r2 D10 문구
    # 결과 카드(담긴 품목) → ActionBar 순서, 행 삭제 버튼은 위험색 key 접미(_del)
    p = _order(at, '<span class="t">담긴 품목</span>', 'class="ws-ab-sum"')
    assert p == sorted(p)
    assert {"so_item_0_del", "so_item_1_del", "so_item_2_del"} <= {b.key for b in at.button}
    # [초기화] = 카드 머리 위험 버튼 → 2단계 확인 뒤에만 비움(r2 D1)
    at.button(key="so_m_reset").click(); at.run()
    assert len(at.session_state["m_so_items"]) == 3, "확인 전에는 그대로"
    at.button(key="so_m_reset_cfm_ok").click(); at.run()
    assert at.session_state["m_so_items"] == []
    assert at.button(key="so_m_save").disabled
    assert any("품번을 검색해 [추가]하면" in m for m in _md(at))


@app_test
def test_ship_deliver_result_card_and_actionbar(ship_db):
    from tests.test_bulk_delivery import _open_shipping
    at = _open_shipping(ship_db)
    assert not at.exception, [str(e.value) for e in at.exception]
    md = _md(at)
    head = next(m for m in md if '<span class="t">미납 회차</span>' in m)
    assert "선택 3" in head, head
    ed = next(d.value for d in at.dataframe if "잔량" in d.value.columns and "출고" in d.value.columns)
    assert "완성 재고" in ed.columns and "구분" in ed.columns
    summ = next(m for m in md if 'class="ws-ab-sum"' in m)
    assert summ.count("선택 3건") == 1 and "납품일" in summ
    assert any("확정할 때 한 번에" in m for m in md)
    prim = [b.key for b in at.button if getattr(b.proto, "type", "") == "primary"]
    assert prim == ["ship_reg"], prim
    # [선택 해제] → 선택 0 · 등록 비활성 → 같은 자리 [전체 선택](비파괴 토글, r2 F12) → 다시 3
    at.button(key="ship_unsel").click(); at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert at.button(key="ship_reg").disabled
    assert any('<span class="t">미납 회차</span>' in m and "선택 0" in m for m in _md(at))
    at.button(key="ship_selall").click(); at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert not at.button(key="ship_reg").disabled
    assert any('<span class="t">미납 회차</span>' in m and "선택 3" in m for m in _md(at))
    # 열 순서(r2 D4): 선택·품번·출고·잔량·완성 재고 … (data_editor column_order)
    src = _src()
    assert ('column_order=("선택", "품번", "출고", "잔량", "완성 재고", "납기", "거래처",\n'
            '                              "수주번호", "구분")') in src


@app_test
def test_po_stepper_current_step_only(monkeypatch):
    from tests import test_po_vendor_history as PV
    import db
    monkeypatch.setattr(db, "fetch", PV._mock_fetch)
    monkeypatch.setattr(db, "fetch_one", lambda *a, **k: None)
    monkeypatch.setattr(db, "insert", lambda t, r: len(r))
    monkeypatch.setattr(db, "update", lambda *a, **k: True)
    monkeypatch.setattr(db, "health_check", lambda: {"status": "OK", "counts": {}})
    monkeypatch.setattr(db, "debug_check", lambda: {"status": "mock"})
    at = PV._open_po_page()

    def _steps():
        h = next(m for m in _md(at) if "stepper ws-steps" in m)
        return re.findall(r'class="step (\w+)"', h)

    def _hidden():
        css = next(m for m in _md(at) if m.startswith("<style>.st-key-") and "{display:none !important}" in m)
        return set(re.findall(r"\.st-key-(\w+)", css))

    # 담긴 품목 없음 → ① 진행
    assert _steps() == ["on", "wait", "wait"]
    assert _hidden() == {"wscard_po_st2", "po_st3"}
    assert at.button(key="po_step_next").label == "② 품목 담기로"
    # ② 로 → ① 완료(거래처 요약) ② 진행 ③ 대기, ① 카드·③ 폼 숨김
    at.button(key="po_step_next").click(); at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert _steps() == ["done", "on", "wait"]
    assert _hidden() == {"wscard_po_st1", "po_st3"}
    assert at.button(key="po_step_back").label == "① 거래처 바꾸기"
    assert at.button(key="po_step_next").disabled          # 담긴 품목 0 → ③ 으로 못 감
    # 품목을 담으면 ③ 으로 → ③ 진행, 발주 정보 폼 보임(①② 숨김)
    at.session_state["po_items"] = [{"_uid": "u1", "product_id": None, "item_name": "TEST-1",
                                     "material": "", "spec": "", "unit": "EA", "qty": 5,
                                     "unit_price": 100, "memo": ""}]
    at.run()
    assert at.button(key="po_step_next").label == "③ 발주서로 (1품목)"
    assert any('class="ws-ab-sum"' in m and "합계 500원" in m for m in _md(at))
    at.button(key="po_step_next").click(); at.run()
    assert _steps() == ["done", "done", "on"]
    assert _hidden() == {"wscard_po_st1", "wscard_po_st2"}
    assert at.button(key="po_step_back").label == "② 품목으로"
    # 주 버튼은 폼의 [발주서 만들기] 하나(ActionBar 주 버튼 없음)
    assert not [b for b in at.button if b.key == "po_step_next"]


# ── r2(2026-10-27) C7 ─────────────────────────────────────────────────

def _po_db(monkeypatch, vendors=True, inserts=None):
    from tests import test_po_vendor_history as PV
    import db

    def _f(table, select="*", filter_query="", limit=1000, **kw):
        if table == "vendors" and not vendors:
            return []
        return PV._mock_fetch(table, select, filter_query, limit)
    monkeypatch.setattr(db, "fetch", _f)
    monkeypatch.setattr(db, "fetch_one", lambda *a, **k: None)
    monkeypatch.setattr(db, "insert", lambda t, r: (inserts.append(t) if inserts is not None else None)
                        or len(r))
    monkeypatch.setattr(db, "update", lambda *a, **k: True)
    monkeypatch.setattr(db, "health_check", lambda: {"status": "OK", "counts": {}})
    monkeypatch.setattr(db, "debug_check", lambda: {"status": "mock"})
    return PV


def _steps(at):
    h = next(m for m in _md(at) if "stepper ws-steps" in m)
    return re.findall(r'class="step (\w+)"', h)


@app_test
def test_r2_prefill_path_always_has_step_back_and_reset_outside_actionbar(monkeypatch):
    """① prefill(부족 자재 → 발주서 작성) 경로 ② → ③ 에서 [① 거래처 바꾸기]/[② 품목으로] 가 항상 있고,
    [모두 초기화]는 담긴 품목 카드 머리(ActionBar 밖)에서 2단계 확인 뒤에만 비운다(D1·D2)."""
    PV = _po_db(monkeypatch)
    from streamlit.testing.v1 import AppTest
    from tests.conftest import goto
    at = AppTest.from_file(APP_FILE, default_timeout=30)
    at.secrets["supabase"] = {"url": "https://mock.local", "anon_key": "a", "service_role_key": "s"}
    at.secrets["auth"] = {"disabled": True}
    at.run()
    at.session_state["po_mode"] = "edit"
    at.session_state["po_prefill_vendor_name"] = PV.VENDOR["name"]
    at.session_state["po_prefill_items"] = [{"product_id": None, "item_name": "환봉 STS304",
                                             "material": "STS304", "spec": "⌀45", "qty": 100,
                                             "unit_price": 1000}]
    goto(at, "po", "new")
    assert not at.exception, [str(e.value) for e in at.exception]
    assert _steps(at) == ["done", "on", "wait"]                 # prefill → ② 부터
    assert at.button(key="po_step_back").label == "① 거래처 바꾸기"
    assert at.button(key="po_reset_all").label == "모두 초기화"
    at.button(key="po_step_next").click(); at.run()              # ③ 으로
    assert _steps(at) == ["done", "done", "on"]
    assert at.button(key="po_step_back").label == "② 품목으로"
    # ③ 거래처명: 담긴 품목 카드 머리 + ActionBar 요약(D5)
    import html as _html
    _vn = _html.escape(PV.VENDOR["name"])                       # 화면은 HTML escape("O&T" → "O&amp;T")
    assert any('<span class="t">담긴 품목</span>' in m and _vn in m for m in _md(at))
    assert any('class="ws-ab-sum"' in m and _vn in m for m in _md(at))
    # [모두 초기화] → 확인 전에는 그대로, 확인 뒤 비움 + ① 로
    at.button(key="po_reset_all").click(); at.run()
    assert len(at.session_state["po_items"]) == 1
    at.button(key="po_reset_all_cfm_ok").click(); at.run()
    assert at.session_state["po_items"] == [] and at.session_state["po_step"] == 1


@app_test
def test_r2_vendor_lookup_empty_shows_step1_card_and_actionbar(monkeypatch):
    """② 거래처 조회가 비면 ① 카드가 보이고(숨김 해제) ActionBar 가 그려진다(D3)."""
    PV = _po_db(monkeypatch, vendors=False)
    at = PV._open_po_page()
    at.session_state["po_step"] = 2
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert at.session_state["po_step"] == 1
    assert any(".st-key-wscard_po_st1{display:block !important}" in m for m in _md(at))
    nxt = at.button(key="po_step_next")
    assert nxt.label == "② 품목 담기로" and nxt.disabled
    assert any('class="ws-ab-sum"' in m and "거래처를 고르세요" in m for m in _md(at))


@app_test
def test_r2_hidden_step_form_submit_writes_nothing(monkeypatch):
    """⑨ ② 단계에서 숨은 ③ 발주 정보 폼을 제출해도 발주서·DB 쓰기 없음."""
    inserts = []
    PV = _po_db(monkeypatch, inserts=inserts)
    at = PV._open_po_page()
    at.session_state["po_items"] = [{"_uid": "u1", "product_id": None, "item_name": "TEST-1",
                                     "material": "", "spec": "", "unit": "EA", "qty": 5,
                                     "unit_price": 100, "memo": ""}]
    at.session_state["po_step"] = 2
    at.run()
    mk = next(b for b in at.button if b.label == "발주서 만들기 (PDF)")
    mk.click(); at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert inserts == [] and "po_result" not in at.session_state


def _ship_stock(monkeypatch, ship_db, lots_fn):
    real = ship_db.fetch

    def _f(table, select="*", filter_query="", limit=1000, **kw):
        if table == "product_lot_stock_v":
            return lots_fn(filter_query, limit)
        return real(table, select, filter_query, limit, **kw)
    monkeypatch.setattr(ship_db, "fetch", _f)


@app_test
def test_r2_stock_lookup_failure_is_unknown_not_shortage(ship_db, monkeypatch):
    from tests.test_bulk_delivery import _open_shipping

    def _boom(fq, limit):
        raise RuntimeError("view down")
    _ship_stock(monkeypatch, ship_db, _boom)
    at = _open_shipping(ship_db)
    assert not at.exception, [str(e.value) for e in at.exception]
    head = next(m for m in _md(at) if '<span class="t">미납 회차</span>' in m)
    assert "완성 재고 부족" not in head, head
    assert any("완성 재고" in str(w.value) and "미확인" in str(w.value) for w in at.warning)
    ed = next(d.value for d in at.dataframe if "잔량" in d.value.columns and "출고" in d.value.columns)
    assert ed["완성 재고"].isna().all()


@app_test
def test_r2_stock_paginates_and_shortage_is_cumulative_per_product(ship_db, monkeypatch):
    """1,001 LOT(2페이지) 전량 합산 + 같은 품번 여러 회차는 잔량 합으로 부족 판정(D6)."""
    from tests.test_bulk_delivery import _open_shipping
    calls = []

    def _pages(fq, limit):
        calls.append(fq)
        off = int(fq.split("offset=")[1].split("&")[0]) if "offset=" in fq else 0
        # P1: 1,001개 LOT × 0.6 = 600.6 (회차 500 + 200 = 700 > 600.6 → 부족), P2: 300
        rows = [{"product_id": "P1", "remain_qty": 0.6} for _ in range(1001)]
        rows += [{"product_id": "P2", "remain_qty": 300}]
        return rows[off:off + limit]
    _ship_stock(monkeypatch, ship_db, _pages)
    at = _open_shipping(ship_db)
    assert not at.exception, [str(e.value) for e in at.exception]
    assert len(calls) == 2 and "offset=1000" in calls[1], calls          # 2페이지
    ed = next(d.value for d in at.dataframe if "잔량" in d.value.columns and "출고" in d.value.columns)
    p1 = ed[ed["품번"] == "4PDVN-03"]["완성 재고"].tolist()
    assert p1 and all(abs(v - 600.6) < 1e-6 for v in p1), p1
    head = next(m for m in _md(at) if '<span class="t">미납 회차</span>' in m)
    assert "완성 재고 부족 1" in head, head                            # 행별(500, 200 각각 < 600.6)이면 0


@app_test
def test_r2_so_mode_kept_across_mains_and_bad_value_fixed(monkeypatch):
    """⑥ so_mode '수기 입력' → 다른 메인 → 복귀 유지(_kv_), 잘못된 값은 기본으로 보정."""
    from tests.test_uiux_u1b import _manual_open, _ManualSOMock
    from tests.conftest import goto
    at = _manual_open(monkeypatch, _ManualSOMock())
    goto(at, "ship", "deliver")
    goto(at, "so", "input")
    assert not at.exception, [str(e.value) for e in at.exception]
    assert at.segmented_control(key="so_mode").value == "수기 입력"
    assert at.text_input(key="m_so_no").value == "PO-T-9"
    # 잘못된 값 보정 — AppTest 는 segmented 에 없는 값을 넣지 못해 정적으로 고정
    src = _src()
    i = src.index('"입력 방식", _SO_MODES, key="so_mode"')
    blk = src[i - 500:i]
    assert 'if st.session_state.get("so_mode") not in _SO_MODES:' in blk
    assert 'st.session_state["so_mode"] = _SO_MODES[0]' in blk
