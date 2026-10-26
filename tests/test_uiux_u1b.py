"""UI/UX 정돈 U1b(2026-10-26) — 성공 메시지 flash·수기 수주 행 삭제/저장·빈 상태·읽기 모드 배너.

기준: _UIUX_U0U1_계획서_및_지시문_20261022.md §1 U1b ①~⑥, docs/design/DESIGN_SYSTEM.md §3·§5.
"""
import ast
import importlib.util
import os
import re
from datetime import date

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_FILE = os.path.join(ROOT, "streamlit_app.py")
DASH_FILE = os.path.join(ROOT, "app", "dash_page.py")
streamlit_available = importlib.util.find_spec("streamlit") is not None


def _read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


# ── 정적 ────────────────────────────────────────────────────────────────

def _success_then_rerun(src):
    L = src.split("\n")
    return [i + 1 for i, l in enumerate(L)
            if "st.success(" in l and any("st.rerun(" in w for w in L[i + 1:i + 4])]


def test_no_success_followed_by_rerun():
    """st.success 다음 3줄 안에 st.rerun 이 없다 — 메시지가 rerun 에 지워지던 65곳은 nav_flash 로(①)."""
    for p in (APP_FILE, DASH_FILE):
        assert _success_then_rerun(_read(p)) == [], (p, _success_then_rerun(_read(p)))


def _is_call(stmt, owner, attr):
    return (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)
            and isinstance(stmt.value.func, ast.Attribute) and stmt.value.func.attr == attr
            and isinstance(stmt.value.func.value, ast.Name) and stmt.value.func.value.id == owner)


def _success_rerun_ast(src):
    """같은 블록에서 st.success(...) 문 뒤에 st.rerun() 문이 오는 곳 — 같은 줄(;)·다중행 호출 모두 잡힌다(r2 R2)."""
    out = []
    for node in ast.walk(ast.parse(src)):
        for fld in ("body", "orelse", "finalbody"):
            blk = getattr(node, fld, None)
            if not isinstance(blk, list):
                continue
            for i, a in enumerate(blk):
                if _is_call(a, "st", "success") and any(_is_call(b, "st", "rerun") for b in blk[i + 1:]):
                    out.append(a.lineno)
    return out


def test_no_success_then_rerun_ast():
    for p in (APP_FILE, DASH_FILE):
        assert _success_rerun_ast(_read(p)) == [], (p, _success_rerun_ast(_read(p)))
    # 검사기 자체가 살아 있는지(역검사): 같은 줄·다중행·사이에 다른 문이 있는 경우
    bad = "\n".join([
        "if x: st.success('a'); st.rerun()",
        "def f():",
        "    st.success(",
        "        'b')",
        "    y = 1",
        "    st.rerun()",
        ""])
    assert len(_success_rerun_ast(bad)) == 2


def test_flash_also_toasts_once_in_renderer():
    """r2 R1: flash 를 그리는 한 곳(nav_flash_show)에서 st.toast 도 — 80자 넘으면 자름."""
    src = _read(APP_FILE)
    a = src.index("def nav_flash_show():"); b = src.index("\ndef ", a + 10)
    body = src[a:b]
    assert body.count("st.toast(") == 1 and "[:79]" in body


def test_flash_rendered_on_pages_without_page_head():
    """flash 를 쓰는 관리자 화면은 제목 아래에서 nav_flash_show() — 안 그리면 다음 사용자 화면으로 샌다."""
    src = _read(APP_FILE)
    assert "def nav_flash_show():" in src
    a = src.index("def nav_page_head():"); b = src.index("def nav_flash_show():")
    assert "nav_flash_show()" in src[a:b]                       # 사용자 영역은 nav_page_head 가
    heads = [(m.start(), m.group(1)) for m in re.finditer(r'^(?:el)?if page == "([^"]+)":', src, re.M)]
    heads.append((len(src), None))
    for (s0, lbl), (s1, _) in zip(heads, heads[1:]):
        blk = src[s0:s1]
        if "nav_flash(" in blk and "nav_page_head()" not in blk:
            first = blk.split("\n")[1:4]
            assert any("nav_flash_show()" in x for x in first), f"{lbl}: 제목 아래 nav_flash_show() 없음"


def test_empty_state_shared_by_three_helpers():
    src = _read(APP_FILE)
    assert 'EMPTY_MSG = "표시할 항목이 없습니다"' in src
    tree = ast.parse(src)
    fns = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    for name in ("toss_table", "toss_df", "toss_grid"):
        body = ast.get_source_segment(src, fns[name])
        assert "_empty_state()" in body, name
    assert '"표시할 데이터 없음"' not in src                     # 옛 toss_df 문구 제거


def test_manual_so_delete_key_follows_danger_rule():
    src = _read(APP_FILE)
    assert 'key=f"so_item_{_soi_i}_del"' in src                  # 접미 _del → 위험 버튼 CSS
    assert "on_click=_m_so_item_del" in src


def test_dash_readonly_notice_shown_once():
    src = _read(DASH_FILE)
    a = src.index("def render_today("); b = src.index("def _render_cards(")
    blk = src[a:b]
    assert blk.count("st.warning(READONLY_MSG)") == 1
    # r2 R3: 읽기 모드 계열 안내만 숨기고(휴무일·담당자 안내는 표시), 카드 0 안내는 msg 와 무관하게
    assert 'info["msg"] not in (READONLY_MSG, READONLY_GEN_MSG)' in blk
    i = blk.index("    if not cards:\n")
    assert blk[i:i + 120].count('st.info("이 교대의 루틴 카드가 없습니다")') == 1
    assert "if not info or not info.get(\"msg\")" not in blk


def test_po_mode_label_and_ship_caption_moved_to_help():
    src = _read(APP_FILE)
    assert 'st.segmented_control("작업 방식", [l for _, l in _PO_MODES], key="po_mode_sc",' in src
    assert '_rg2.caption("등록 시점에는' not in src
    i = src.index('key="ship_reg"')
    assert "등록 시점에는 아무것도 차감되지 않습니다" in src[i:i + 400]


# ── AppTest: 빈 상태 3종 같은 문구 ──────────────────────────────────────

def _empty_script(app_file):
    import ast as _ast
    import streamlit as st
    _src = open(app_file, encoding="utf-8").read()
    _keep = [n for n in _ast.parse(_src).body
             if (isinstance(n, _ast.FunctionDef) and n.name in
                 ("_empty_state", "toss_table", "toss_df", "toss_grid", "_badge_class"))
             or (isinstance(n, _ast.Assign) and any(getattr(t, "id", "") == "EMPTY_MSG" for t in n.targets))]
    ns = {"st": st}
    exec(compile(_ast.Module(body=_keep, type_ignores=[]), app_file, "exec"), ns)
    ns["toss_table"]([])
    ns["toss_df"]([])
    st.session_state["_grid_ret"] = ns["toss_grid"]([], key="g_empty")


@pytest.mark.skipif(not streamlit_available, reason="streamlit 미설치 — AppTest 불가")
def test_empty_state_same_line_for_three_helpers():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_function(_empty_script, args=(APP_FILE,), default_timeout=30)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    md = [m.value for m in at.markdown if "ws-empty" in (m.value or "")]
    assert len(md) == 3 and all("표시할 항목이 없습니다" in m for m in md), md
    assert at.session_state["_grid_ret"] is None                # 반환 의미는 그대로


# ── AppTest: 수기 수주 행 삭제 → 저장 → 표 비움·flash ───────────────────

if streamlit_available:
    from tests.so_mock import SOMock

    class _ManualSOMock(SOMock):
        """수기 수주 저장 경로용 — insert 가 so_id/soi_id 를 채운다(운영 serial 과 같은 의미)."""

        def insert(self, table, records):
            recs = []
            for r in records:
                r = dict(r)
                if table == "sales_orders":
                    self._seq["sales_orders"] = self._seq.get("sales_orders", 0) + 1
                    r.setdefault("so_id", 500 + self._seq["sales_orders"])
                if table == "sales_order_items":
                    self._seq["sales_order_items"] = self._seq.get("sales_order_items", 0) + 1
                    r.setdefault("soi_id", 900 + self._seq["sales_order_items"])
                recs.append(r)
            return super().insert(table, recs)


def _item(n, pn, qty):
    return {"line_no": n, "customer_part_no": pn, "qty": qty, "unit_price": 100,
            "amount": qty * 100, "due_date": date(2026, 11, 9), "product_id": f"P{n}", "canonical_pn": pn}


@pytest.mark.skipif(not streamlit_available, reason="streamlit 미설치 — AppTest 불가")
def test_manual_so_row_delete_then_save_clears_and_flashes(monkeypatch):
    import db as _dbmod
    from streamlit.testing.v1 import AppTest
    from tests.conftest import goto
    mock = _ManualSOMock()
    mock.install(monkeypatch, _dbmod)
    at = AppTest.from_file(APP_FILE, default_timeout=90)
    at.secrets["supabase"] = {"url": "https://mock.local", "anon_key": "a", "service_role_key": "s"}
    at.secrets["auth"] = {"disabled": True}
    at.run()
    goto(at, "so", "input")
    next(r for r in at.radio if r.label == "입력 방식").set_value("수기 입력")
    at.run()
    at.session_state["m_so_items"] = [_item(1, "AAA-1", 10), _item(2, "BBB-2", 20), _item(3, "CCC-3", 30)]
    at.text_input(key="m_so_no").set_value("PO-T-1")
    at.text_input(key="m_cust").set_value("(주)테스트")
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    keys = {b.key for b in at.button}
    assert {"so_item_0_del", "so_item_1_del", "so_item_2_del"} <= keys
    # 가운데 행 삭제 → 번호 다시 매김
    at.button(key="so_item_1_del").click()
    at.run()
    its = at.session_state["m_so_items"]
    assert [(i["line_no"], i["customer_part_no"]) for i in its] == [(1, "AAA-1"), (2, "CCC-3")]
    assert "so_item_2_del" not in {b.key for b in at.button}
    # 저장 → 품목표 비움 + flash + 삭제 버튼 사라짐
    next(b for b in at.button if b.label == "수주 저장").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert at.session_state["m_so_items"] == []
    assert any("PO-T-1" in str(s.value) and "저장 완료" in str(s.value) for s in at.success), \
        [s.value for s in at.success]
    assert not [b.key for b in at.button if (b.key or "").startswith("so_item_")]
    so = [r for r in mock.tables["sales_orders"] if r.get("so_number") == "PO-T-1"]
    assert len(so) == 1
    lines = [r for r in mock.tables["sales_order_items"] if r.get("so_id") == so[0]["so_id"]]
    assert [(r["line_no"], r["customer_part_no"]) for r in lines] == [(1, "AAA-1"), (2, "CCC-3")]


# ── r2 R8: flash 1회성·관리자 화면·저장 실패·라인 중간 실패·삭제 불일치·마지막 행 ─────────

def _manual_open(monkeypatch, mock, items=None):
    import db as _dbmod
    from streamlit.testing.v1 import AppTest
    from tests.conftest import goto
    mock.install(monkeypatch, _dbmod)
    at = AppTest.from_file(APP_FILE, default_timeout=90)
    at.secrets["supabase"] = {"url": "https://mock.local", "anon_key": "a", "service_role_key": "s"}
    at.secrets["auth"] = {"disabled": True}
    at.run()
    goto(at, "so", "input")
    next(r for r in at.radio if r.label == "입력 방식").set_value("수기 입력")
    at.run()
    at.session_state["m_so_items"] = items if items is not None else \
        [_item(1, "AAA-1", 10), _item(2, "BBB-2", 20), _item(3, "CCC-3", 30)]
    at.text_input(key="m_so_no").set_value("PO-T-9")
    at.text_input(key="m_cust").set_value("(주)테스트")
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def _save(at):
    next(b for b in at.button if b.label == "수주 저장").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]


def _succ(at):
    return [str(s.value) for s in at.success]


@pytest.mark.skipif(not streamlit_available, reason="streamlit 미설치 — AppTest 불가")
def test_flash_shows_once_then_gone(monkeypatch):
    """① 저장 뒤 안내는 한 번만 — 다음 실행에는 성공 안내 0·_nav_flash 없음."""
    at = _manual_open(monkeypatch, _ManualSOMock())
    _save(at)
    assert any("PO-T-9" in m for m in _succ(at))
    at.run()
    assert not [m for m in _succ(at) if "PO-T-9" in m]
    assert "_nav_flash" not in at.session_state


@pytest.mark.skipif(not streamlit_available, reason="streamlit 미설치 — AppTest 불가")
@pytest.mark.parametrize("main", ["master", "cost", "report", "sales"])
def test_admin_page_flash_shown_there_not_leaked(monkeypatch, main):
    """② 관리자 4화면: 세운 flash 가 그 화면 제목 아래 1건, 다음 사용자 화면으로 옮겨 가면 0건."""
    import db as _dbmod
    from streamlit.testing.v1 import AppTest
    from tests.conftest import goto
    _ManualSOMock().install(monkeypatch, _dbmod)
    at = AppTest.from_file(APP_FILE, default_timeout=90)
    at.secrets["supabase"] = {"url": "https://mock.local", "anon_key": "a", "service_role_key": "s"}
    at.secrets["auth"] = {"disabled": True}
    at.run()
    at.session_state["_nav_flash"] = {"msg": f"관리자 안내 {main}", "action": None}
    goto(at, main)
    assert _succ(at).count(f"관리자 안내 {main}") == 1, _succ(at)
    goto(at, "so", "list")
    assert f"관리자 안내 {main}" not in _succ(at)


@pytest.mark.skipif(not streamlit_available, reason="streamlit 미설치 — AppTest 불가")
def test_manual_so_header_fail_keeps_items(monkeypatch):
    """③ 머리글 insert 실패 → 품목 3행 유지·오류 안내·성공 안내 0."""
    class _M(_ManualSOMock):
        def insert(self, table, records):
            if table == "sales_orders":
                raise RuntimeError("insert sales_orders 실패(시뮬레이션)")
            return super().insert(table, records)
    at = _manual_open(monkeypatch, _M())
    _save(at)
    assert len(at.session_state["m_so_items"]) == 3
    assert any("저장 실패" in str(e.value) for e in at.error)
    assert not [m for m in _succ(at) if "PO-T-9" in m]


@pytest.mark.skipif(not streamlit_available, reason="streamlit 미설치 — AppTest 불가")
def test_manual_so_line_fail_reports_saved_header(monkeypatch):
    """④ 라인 2번째 insert 실패 → 머리글 1·라인 1(현재 동작 고정)·안내에 so_id·표 유지."""
    class _M(_ManualSOMock):
        n_lines = 0

        def insert(self, table, records):
            if table == "sales_order_items":
                _M.n_lines += 1
                if _M.n_lines == 2:
                    raise RuntimeError("insert sales_order_items 실패(시뮬레이션)")
            return super().insert(table, records)
    mock = _M()
    at = _manual_open(monkeypatch, mock)
    _save(at)
    hdr = [r for r in mock.tables["sales_orders"] if r.get("so_number") == "PO-T-9"]
    assert len(hdr) == 1
    assert len([r for r in mock.tables["sales_order_items"] if r.get("so_id") == hdr[0]["so_id"]]) == 1
    err = " ".join(str(e.value) for e in at.error)
    assert "머리글은 저장됨" in err and f"so_id={hdr[0]['so_id']}" in err
    assert len(at.session_state["m_so_items"]) == 3
    assert not [m for m in _succ(at) if "PO-T-9" in m]


@pytest.mark.skipif(not streamlit_available, reason="streamlit 미설치 — AppTest 불가")
def test_manual_so_delete_mismatch_or_out_of_range_no_change(monkeypatch):
    """⑤ 렌더 뒤 목록이 바뀌어 (번호, 품번)이 맞지 않거나 범위 밖 → 아무 행도 지우지 않는다."""
    at = _manual_open(monkeypatch, _ManualSOMock(), [_item(1, "AAA-1", 10), _item(2, "BBB-2", 20)])
    # 불일치: so_item_1_del 은 (2, "BBB-2") 로 렌더됨 → 2번 자리가 CCC-3 로 바뀐 뒤 클릭
    at.session_state["m_so_items"] = [_item(1, "AAA-1", 10), _item(2, "CCC-3", 30)]
    at.button(key="so_item_1_del").click()
    at.run()
    assert [i["customer_part_no"] for i in at.session_state["m_so_items"]] == ["AAA-1", "CCC-3"]
    # 범위 밖: 1행만 남은 상태에서 옛 2번째 행 버튼(같은 key, 이제 (2,"CCC-3")) — 목록에서 2번을 없앤 뒤 클릭
    at.session_state["m_so_items"] = [_item(1, "AAA-1", 10)]
    at.button(key="so_item_1_del").click()
    at.run()
    assert [i["customer_part_no"] for i in at.session_state["m_so_items"]] == ["AAA-1"]


@pytest.mark.skipif(not streamlit_available, reason="streamlit 미설치 — AppTest 불가")
def test_manual_so_delete_last_row_disables_save(monkeypatch):
    """⑥ 마지막 행 삭제 → 빈 목록·[수주 저장] 비활성·삭제 버튼 0."""
    at = _manual_open(monkeypatch, _ManualSOMock(), [_item(1, "AAA-1", 10)])
    at.button(key="so_item_0_del").click()
    at.run()
    assert at.session_state["m_so_items"] == []
    assert next(b for b in at.button if b.label == "수주 저장").disabled
    assert not [b.key for b in at.button if (b.key or "").startswith("so_item_")]
