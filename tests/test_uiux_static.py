"""UI/UX 정돈(U1·U1b, 2026-10-26) 정적 검사 — AppTest 는 CSS 를 보지 못하므로 소스로 고정한다.

기준: docs/design/DESIGN_SYSTEM.md §5.
- 새 CSS 는 토큰만(hex 금지). 옛 전역 CSS 블록은 hex 개수가 늘지 않게(줄이기만 허용).
- `.st-key-*` 셀렉터는 실제 위젯 key 와 대응.
- 위험 버튼 key 접미(_del·_cancel·_cfm_ok) ↔ 생성 CSS 셀렉터 일치(1.66 클래스 순서 대응 포함).
"""
import ast
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_FILE = os.path.join(ROOT, "streamlit_app.py")
HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")

# 옛 전역 CSS 블록(@import 로 시작하는 st.markdown 문자열)의 hex 개수 상한 — U1 시점 값.
# 토큰으로 바꿀 때마다 낮춘다. 늘어나면 새 규칙에 hex 를 쓴 것이다.
LEGACY_HEX_MAX = 58


def _src():
    with open(APP_FILE, encoding="utf-8") as f:
        return f.read()


def _tree():
    return ast.parse(_src())


_NAMES = ("_TOKENS", "_token", "_BADGE_CSS", "_badge_css_html", "_badge_css_grid",
          "_DANGER_KEY_SUFFIXES", "_DANGER_KEY_EXCLUDE", "_DANGER_KEY_PREFIXES", "_DANGER_KEYS",
          "_DANGER_KEY_COMBOS", "_danger_btn_css", "_U1_CSS")


def _design_ns():
    """디자인 상수·생성 함수만 골라 실행(앱 전체 실행 없이)."""
    tree = _tree()
    keep = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in _NAMES:
            keep.append(node)
        elif isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id in _NAMES for t in node.targets):
            keep.append(node)
    mod = ast.Module(body=keep, type_ignores=[])
    ns = {}
    exec(compile(mod, APP_FILE, "exec"), ns)
    missing = [n for n in _NAMES if n not in ns]
    assert not missing, missing
    return ns


def _legacy_block():
    """@import 가 든 전역 st.markdown 호출의 문자열 상수 조각(생성 부분 제외)."""
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "markdown" and node.args:
            parts = [n.value for n in ast.walk(node.args[0])
                     if isinstance(n, ast.Constant) and isinstance(n.value, str)]
            if any("@import url(" in p for p in parts):
                return "".join(parts)
    raise AssertionError("전역 CSS 블록을 찾지 못함")


# ── 1. 토큰만 ────────────────────────────────────────────────────────────

def test_new_css_has_no_hex():
    ns = _design_ns()
    for name, css in (("_U1_CSS", ns["_U1_CSS"]), ("_danger_btn_css()", ns["_danger_btn_css"]()),
                      ("_badge_css_html()", ns["_badge_css_html"]())):
        assert not HEX.findall(css), (name, HEX.findall(css))
    # 사이드바 선택 강조(실행마다 생성) 코드 구간도 토큰만
    src = _src()
    a = src.index("# 선택 항목 강조")
    b = src.index('st.markdown("<style>" + _nav_css', a)
    assert not HEX.findall(src[a:b]), HEX.findall(src[a:b])


def test_legacy_css_hex_does_not_grow():
    n = len(HEX.findall(_legacy_block()))
    assert n <= LEGACY_HEX_MAX, f"전역 CSS 블록 hex {n}개 > 상한 {LEGACY_HEX_MAX} — 새 규칙은 var(--토큰)만"


def test_tokens_cover_design_system_and_root_is_generated():
    ns = _design_ns()
    t = ns["_TOKENS"]
    for k in ("--primary", "--link", "--line2", "--warn2", "--good", "--primary-bg",
              "--danger-bg", "--focus", "--sp-1", "--sp-6"):
        assert k in t, k
    assert [t[f"--sp-{i}"] for i in range(1, 7)] == ["4px", "8px", "12px", "16px", "24px", "32px"]
    assert "_TOKENS.items()" in _src()[: _src().index("@import url(") + 400]   # :root 는 _TOKENS 에서 생성
    # var(--x) 로 쓰는 토큰은 모두 정의돼 있어야 한다(오타 = 조용한 실패)
    used = set(re.findall(r"var\((--[a-z0-9-]+)\)", ns["_U1_CSS"] + ns["_danger_btn_css"]()
                          + ns["_badge_css_html"]()))
    assert used <= set(t), used - set(t)


def test_badge_single_definition_shared_by_html_and_grid():
    ns = _design_ns()
    html, grid = ns["_badge_css_html"](), ns["_badge_css_grid"]()
    base = ns["_BADGE_CSS"]["base"]
    assert grid[".tt-badge"] == base
    for cls, (bg, fg) in ns["_BADGE_CSS"]["colors"].items():
        assert f".tt .{cls}{{background:var({bg});color:var({fg})}}" in html
        assert grid[f".{cls}"] == {"background": ns["_TOKENS"][bg], "color": ns["_TOKENS"][fg]}
    assert {"padding": "2px 10px", "border-radius": "7px", "font-size": "12px"}.items() <= base.items()
    src = _src()
    assert "**_badge_css_grid()" in src                       # AgGrid 가 같은 상수를 읽는다
    legacy = _legacy_block()
    assert ".tt .badge{" not in legacy and ".tt .b-red{" not in legacy   # 옛 중복 정의 제거
    g0 = src.index("_TOSS_GRID_CSS = {"); g1 = src.index("\n}\n", g0)
    assert '".b-red"' not in src[g0:g1] and '".tt-badge"' not in src[g0:g1]


# ── 2. .st-key-* ↔ 실제 key ─────────────────────────────────────────────

def _keys_in_source(src):
    lit = set(re.findall(r'key="([A-Za-z0-9_]+)"', src))
    # U3: action_bar·card_head_btn 의 버튼 인자 dict("key": "...") 도 실제 key
    lit |= set(re.findall(r'"key": "([A-Za-z0-9_]+)"', src))
    fpre = set(re.findall(r'key=f"([A-Za-z0-9_]*)\{', src))      # f"nav_m_{...}" → 접두 "nav_m_"
    # 변수로 만든 key(_sck = f"nav_sc_{...}" → key=_sck) — 이름이 k 로 끝나는 지역 변수만
    fpre |= set(re.findall(r'\b_\w*k\s*=\s*f"([A-Za-z0-9_]+)\{', src))
    return lit, fpre


def test_st_key_selectors_match_real_keys():
    src = _src()
    ns = _design_ns()
    css = _legacy_block() + ns["_U1_CSS"]
    lit, fpre = _keys_in_source(src)
    # [class*="st-key-<접두>"] 와 .st-key-<key> 두 형태
    pref = set(re.findall(r'st-key-([A-Za-z0-9_]+)"', css))
    exact = set(re.findall(r'\.st-key-([A-Za-z0-9_]+)', css))
    assert pref, "접두 셀렉터가 하나도 없음 — 파서 확인"
    for p in pref | exact:
        ok = any(k.startswith(p) for k in lit) or any(f.startswith(p) or p.startswith(f) for f in fpre if f)
        assert ok, f".st-key-{p} 에 대응하는 위젯 key 가 소스에 없음"
    for k in ns["_DANGER_KEY_EXCLUDE"]:
        assert k in lit, f"위험 제외 목록의 {k} 가 실제 key 가 아님"


# ── 3. 위험 버튼 접미 ↔ 셀렉터 ──────────────────────────────────────────

def test_danger_suffix_rule_matches_selectors():
    ns = _design_ns()
    css = ns["_danger_btn_css"]()
    sufs = ns["_DANGER_KEY_SUFFIXES"]
    assert set(sufs) == {"_del", "_cancel", "_cfm_ok"}
    for s in sufs:
        # 1.66: st-key 클래스 뒤에 emotion 클래스가 붙는다 → "접미+공백" 과 끝 매칭 둘 다
        assert f'[class*="{s} "]' in css and f'[class$="{s}"]' in css, s
    assert "button:not(:disabled)" in css                    # 잠긴 버튼은 회색 유지
    assert "var(--warn2)" in css and "var(--danger-bg)" in css
    for k in ns["_DANGER_KEY_EXCLUDE"]:
        assert f":not(.st-key-{k})" in css
    src = _src()
    # confirm_gate [실행 확정] 은 _cfm_ok 접미 → 위험색, [돌아가기] 는 보조
    assert 'key=f"{key}_cfm_ok"' in src and 'key=f"{key}_cfm_no"' in src
    # 접미 규칙에 걸리는 실제 key 목록 고정(새 위험 버튼은 접미 규칙으로 — 바뀌면 06 표 갱신)
    lit, _ = _keys_in_source(src)
    hit = sorted(k for k in lit if k.endswith(sufs))
    assert hit == ["acct_del", "cf_cancel", "po_pending_cancel"], hit
    # r2 R4: primary [실행 확정]의 파란 테두리까지 지운다
    assert "border-color:transparent !important" in css


def test_danger_extra_lists_match_real_keys():
    """r2 R5: 접미 규칙 밖 파괴 버튼(접두·정확한 key·접두+접미)도 위험색 — key 는 그대로, 실제 key 와 대응."""
    ns = _design_ns()
    css = ns["_danger_btn_css"]()
    src = _src()
    lit, fpre = _keys_in_source(src)
    assert ns["_DANGER_KEY_PREFIXES"] == ("bom_del_",)
    # U3 r2 D1: 카드 머리 [모두 초기화]·수주 [초기화] 2종 추가(ActionBar 밖, confirm_gate 2단계)
    assert set(ns["_DANGER_KEYS"]) == {"po_clear_all", "sc_clear", "po_reset_all",
                                       "so_up_reset", "so_m_reset"}
    assert ns["_DANGER_KEY_COMBOS"] == (("sch_reset_", "_ok"),)
    for p in ns["_DANGER_KEY_PREFIXES"]:
        assert f'[class*="st-key-{p}"]' in css and p in fpre, p
    for k in ns["_DANGER_KEYS"]:
        assert f".st-key-{k}" in css and k in lit, k
    for pre, suf in ns["_DANGER_KEY_COMBOS"]:
        assert f'[class*="st-key-{pre}"][class*="{suf} "]' in css and pre in fpre
    assert 'key=f"{_rk}_ok"' in src
    # 회차 [삭제 확정] 은 primary(파랑)가 아니다 — 위험색이 덮을 대상이 일반 버튼이어야 한다
    i = src.index('key=f"{_rk}_ok"')
    assert 'button("삭제 확정",' in src[i - 200:i] and 'type="primary"' not in src[i - 200:i]
