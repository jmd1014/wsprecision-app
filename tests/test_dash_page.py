# -*- coding: utf-8 -*-
"""업무 루틴 화면 (app/dash_page.py + 본체 연결) — 계획서 §6 AppTest·정적 항목 (2026-10-21).

목 DB: tests/dash_mock.py (dash_ 테이블 리스트, 필터 AND 파싱, update_count 0/1/-1·예외, RPC 충돌 판정).
로그인은 실제 로그인 폼(app_settings.auth_users 목)으로 — auth.disabled 가 아닌 secrets 라 쓰기 모드.
시각은 app.dash_page.now_utc 를 고정한다(2026-10-21 수요일 10:00 KST = 주간 슬롯).
"""
import ast
import os
import re
import sys
import importlib.util
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from tests.conftest import goto, nav_sub_labels, nav_title           # noqa: E402
from tests.dash_mock import DashMock, USERS                           # noqa: E402
from utils.dash_routine import KST                                    # noqa: E402

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("streamlit") is None, reason="streamlit 미설치 — AppTest 불가")

ROOT = os.path.dirname(os.path.dirname(__file__))
APP_FILE = os.path.join(ROOT, "streamlit_app.py")
WED_DAY = datetime(2026, 10, 21, 10, 0, tzinfo=KST)        # 수요일 주간
WED_NIGHT = datetime(2026, 10, 21, 20, 30, tzinfo=KST)     # 수요일 야간
SAT_NIGHT = datetime(2026, 10, 24, 21, 0, tzinfo=KST)      # 토요일 야간(다음 날 일요일 OFF → pre_holiday)


@pytest.fixture()
def dash_db(monkeypatch):
    import db
    m = DashMock().install(monkeypatch, db)
    return m


def _fix_now(monkeypatch, when):
    import app.dash_page as dp
    monkeypatch.setattr(dp, "now_utc", lambda: when)


def _make(readonly=False):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP_FILE, default_timeout=60)
    at.secrets["supabase"] = {"url": "https://mock.local", "anon_key": "a", "service_role_key": "s"}
    if readonly:
        at.secrets["auth"] = {"disabled": True}
    return at


def _login(at, uid, pw):
    at.text_input[0].set_value(uid)
    at.text_input[1].set_value(pw)
    next(b for b in at.button if getattr(b, "label", "") == "로그인").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]


def _open(uid, pw, sub="today", readonly=False):
    at = _make(readonly)
    at.run()
    if not readonly:
        _login(at, uid, pw)
    goto(at, "dash", sub)
    return at


def _titles(at):
    return [str(h.value) for h in at.subheader] + [str(m.value) for m in at.markdown]


def _has_title(at, sub):
    return any(nav_title("dash", sub) in t for t in _titles(at))


def _flash(at):
    return [str(s.value) for s in at.success] + [str(w.value) for w in at.warning] + [str(i.value) for i in at.info]


def _done_buttons(at):
    return [b for b in at.button if str(b.key or "").startswith("dash_done_")]


# ─── 1. 생성: 멱등, 결과 문구 ───────────────────────────────────

def test_generation_is_idempotent_on_reentry(dash_db, monkeypatch):
    _fix_now(monkeypatch, WED_DAY)
    at = _open("김준오", "pw-day")
    assert _has_title(at, "today")
    assert len(dash_db.cards(work_date="2026-10-21", shift="day")) == 7
    assert len(dash_db.rpc_calls) == 1
    at.run()                                   # 재진입 — 빠진 템플릿 없음 → RPC 호출 없음, 행 수 불변
    goto(at, "home"); goto(at, "dash", "today")
    assert len(dash_db.cards(work_date="2026-10-21", shift="day")) == 7
    assert len(dash_db.rpc_calls) == 1
    assert len(_done_buttons(at)) == 7


def test_admin_sees_generation_caption(dash_db, monkeypatch):
    _fix_now(monkeypatch, WED_DAY)
    at = _open("김민수", "pw-admin")
    assert any("생성 7" in str(c.value) for c in at.caption), [str(c.value) for c in at.caption]


# ─── 2. 담당자 미지정 템플릿 제외 → 지정 뒤 추가분만 ─────────────────

def test_unassigned_templates_excluded_then_added_after_assignment(dash_db, monkeypatch):
    _fix_now(monkeypatch, WED_NIGHT)
    at = _open("김민수", "pw-admin")
    assert dash_db.cards(shift="night") == []
    assert any("담당자 미지정 3개 제외" in str(x) for x in [c.value for c in at.caption] + [i.value for i in at.info]), \
        [str(c.value) for c in at.caption]
    assert dash_db.rpc_calls == []
    for t in dash_db.tables["dash_routine_templates"]:
        if t["shift"] == "night" and t["code"] in ("prod_night_01", "prod_night_02"):
            t["assignee_user_ids"] = ["김만호"]
    goto(at, "home"); goto(at, "dash", "today")
    assert sorted(c["template_id"] for c in dash_db.cards(shift="night")) == [8, 9]
    assert len(dash_db.rpc_calls) == 1 and dash_db.rpc_calls[0][1]["p_template_ids"] == [8, 9]
    # pre_holiday 템플릿은 수요일 야간에 생성되지 않는다(토요일 야간 테스트는 순수 함수에서)


# ─── 3. 선착 완료 / 오래된 화면 ──────────────────────────────────

def test_first_come_done_and_stale_screen_gets_notice(dash_db, monkeypatch):
    _fix_now(monkeypatch, WED_DAY)
    a = _open("김준오", "pw-day")
    b = _open("김민수", "pw-admin")                    # B 도 같은 카드를 보고 있음(todo)
    cid = dash_db.cards(work_date="2026-10-21", shift="day")[0]["id"]
    a.button(key=f"dash_done_{cid}").click(); a.run()
    assert not a.exception, [str(e.value) for e in a.exception]
    card = dash_db.cards(id=cid)[0]
    assert card["status"] == "done" and card["completed_by"] == "김준오" and card["completed_at"]
    assert [x for x in dash_db.activity() if x["card_id"] == cid and x["action"] == "done" and x["user_id"] == "김준오"]
    assert any("완료 —" in f for f in _flash(a))
    # B 의 오래된 화면에서 같은 카드 [완료] → 다시 그린 화면에서 버튼이 사라져 처리 없음, 로그 1건 그대로
    b.button(key=f"dash_done_{cid}").click(); b.run()
    assert not b.exception, [str(e.value) for e in b.exception]
    assert not [x for x in b.button if x.key == f"dash_done_{cid}"]
    assert len([x for x in dash_db.activity() if x["card_id"] == cid]) == 1
    assert dash_db.cards(id=cid)[0]["completed_by"] == "김준오"
    # 같은 런 안의 경합(렌더 뒤 DB 가 먼저 바뀜) = update_count 0행 → 최신 행 재조회 + "OOO 이 HH:MM 완료함"
    import app.dash_page as dp
    flashes = []
    ctx = dp.Ctx(db=dash_db, current_user=lambda: {"username": "김민수", "role": "admin"}, is_admin=True,
                 readonly=False, click_guard=lambda k: True, confirm_gate=lambda *a, **k: False,
                 nav_flash=lambda m, action=None: flashes.append(m), nav_go=lambda *a, **k: None,
                 toss_table=lambda *a, **k: None, load_users=lambda: USERS)
    dash_db.update_mode = 0
    assert dp.handle_done(ctx, dict(card, status="todo")) is False
    assert flashes and "김준오 이" in flashes[-1] and "완료함" in flashes[-1], flashes
    assert len([x for x in dash_db.activity() if x["card_id"] == cid]) == 1


# ─── 4. 취소 게이트: 카드별 키, 오래된 확인 0행 ────────────────────

def test_undo_gate_is_per_card_and_stale_confirm_is_rejected(dash_db, monkeypatch):
    _fix_now(monkeypatch, WED_DAY)
    at = _open("김민수", "pw-admin")
    ids = [c["id"] for c in dash_db.cards(work_date="2026-10-21", shift="day")][:2]
    for cid in ids:
        at.button(key=f"dash_done_{cid}").click(); at.run()
    assert all(dash_db.cards(id=c)[0]["status"] == "done" for c in ids)
    at.button(key=f"dash_undo_{ids[0]}").click(); at.run()
    assert at.button(key=f"dash_undo_{ids[0]}_cfm_ok")
    assert not [b for b in at.button if b.key == f"dash_undo_{ids[1]}_cfm_ok"], "다른 카드에 확인창 없음"
    at.button(key=f"dash_undo_{ids[0]}_cfm_ok").click(); at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert dash_db.cards(id=ids[0])[0]["status"] == "todo"
    assert [x for x in dash_db.activity() if x["card_id"] == ids[0] and x["action"] == "undo"]
    # 취소 → 재완료 뒤, 오래된 확인창(이전 completed_at)으로 취소 → 0행 → 재확인 안내, 상태 유지
    at.button(key=f"dash_done_{ids[0]}").click(); at.run()
    at.button(key=f"dash_undo_{ids[0]}").click(); at.run()
    at.session_state[f"dash_undo_at_{ids[0]}"] = "2026-10-21T00:00:00+00:00"     # 오래된 값
    at.button(key=f"dash_undo_{ids[0]}_cfm_ok").click(); at.run()
    assert dash_db.cards(id=ids[0])[0]["status"] == "done"
    assert any("상태가 바뀌어" in f for f in _flash(at)), _flash(at)
    assert f"cfm_dash_undo_{ids[0]}" not in at.session_state
    assert len([x for x in dash_db.activity() if x["card_id"] == ids[0] and x["action"] == "undo"]) == 1


# ─── 5. 오류 처리: 로그 INSERT 실패 / UPDATE 예외·-1 / RPC 거부·미설치·timeout ───

def test_activity_insert_failure_keeps_state_and_warns(dash_db, monkeypatch):
    _fix_now(monkeypatch, WED_DAY)
    at = _open("김준오", "pw-day")
    cid = dash_db.cards(shift="day")[0]["id"]
    dash_db.insert_raise_for = "dash_card_activity"
    at.button(key=f"dash_done_{cid}").click(); at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert dash_db.cards(id=cid)[0]["status"] == "done"
    assert dash_db.activity() == []
    assert any("활동 기록에 실패" in f for f in _flash(at)), _flash(at)
    assert [e for e in dash_db.log_errors if "dash_card_activity" in e[1]]


@pytest.mark.parametrize("mode,msg", [("raise", "저장되지 않았습니다"), (-1, "저장되지 않았습니다"),
                                      (0, "상태가 바뀌어")])
def test_update_failures_are_reported(dash_db, monkeypatch, mode, msg):
    _fix_now(monkeypatch, WED_DAY)
    at = _open("김준오", "pw-day")
    cid = dash_db.cards(shift="day")[0]["id"]
    dash_db.update_mode = mode
    at.button(key=f"dash_done_{cid}").click(); at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert dash_db.cards(id=cid)[0]["status"] == "todo"
    assert dash_db.activity() == []
    assert any(msg in f for f in _flash(at)), _flash(at)


@pytest.mark.parametrize("exc", ["RpcRejected", "RpcUnavailable", "RpcTransportError"])
def test_rpc_errors_do_not_crash(dash_db, monkeypatch, exc):
    import db
    _fix_now(monkeypatch, WED_DAY)
    dash_db.rpc_raise = (db.RpcRejected("P0001", "거부") if exc == "RpcRejected"
                         else db.RpcUnavailable("없음") if exc == "RpcUnavailable"
                         else db.RpcTransportError("timeout"))
    at = _open("김민수", "pw-admin")
    assert not at.exception, [str(e.value) for e in at.exception]
    assert dash_db.cards() == []
    assert any("카드 생성에 실패" in str(w.value) for w in at.warning)
    assert len(dash_db.rpc_calls) == 1                     # 재시도 없음


# ─── 6. 권한: 비담당 작업자, 작업자 세부 숨김·주입 보정 ───────────────

def test_non_assignee_worker_cannot_write(dash_db, monkeypatch):
    _fix_now(monkeypatch, WED_DAY)
    at = _open("현장", "pw-field")
    assert _has_title(at, "today")
    btns = _done_buttons(at)
    assert btns and all(b.disabled for b in btns)
    before = len(dash_db.writes)
    # 핸들러 직접 호출(버튼은 잠겨 있으므로)로도 쓰기 0
    import app.dash_page as dp
    card = dash_db.cards(shift="day")[0]
    flashes = []
    ctx = dp.Ctx(db=dash_db, current_user=lambda: {"username": "현장", "role": "worker"}, is_admin=False,
                 readonly=False, click_guard=lambda k: True, confirm_gate=lambda *a, **k: False,
                 nav_flash=lambda m, action=None: flashes.append(m), nav_go=lambda *a, **k: None,
                 toss_table=lambda *a, **k: None, load_users=lambda: USERS)
    assert dp.handle_done(ctx, card) is False and dp.handle_undo(ctx, card, "x") is False
    assert len(dash_db.writes) == before and all("담당자" in f for f in flashes)


def test_worker_sees_only_today_and_injection_is_corrected(dash_db, monkeypatch):
    _fix_now(monkeypatch, WED_DAY)
    at = _open("김준오", "pw-day")
    assert nav_sub_labels(at, "dash") == ["오늘 루틴"]
    assert not [x for x in at.get("segmented_control")], "세부 1개 → 본문 세부 컨트롤 없음"
    for inject in ("rate", "tmpl"):
        at.session_state["nav_sub"] = {"dash": inject}
        at.session_state["nav_sc_dash"] = "템플릿 관리"
        at.run()
        assert not at.exception, [str(e.value) for e in at.exception]
        assert _has_title(at, "today")
        assert not [f for f in at.get("form") if "dash_tmpl_form" in str(getattr(f, "form_id", ""))] \
            and not [b for b in at.button if str(b.key or "").startswith("dash_tmpl_")]
    assert not [w for w in dash_db.writes if w[1] != "dash_cards"]     # 생성 외 쓰기 없음


def test_admin_sees_three_subs_and_rate_table(dash_db, monkeypatch):
    _fix_now(monkeypatch, WED_DAY)
    at = _open("김민수", "pw-admin", sub="rate")
    assert nav_sub_labels(at, "dash") == ["오늘 루틴", "완료율", "템플릿 관리"]
    assert _has_title(at, "rate")
    md = " ".join(str(m.value) for m in at.markdown)
    assert "2026-10-21" in md and "생성 없음" in md


# ─── 7. 홈 카드 / 과거·미래 슬롯 ───────────────────────────────

def test_home_card_opens_today_only_on_click(dash_db, monkeypatch):
    _fix_now(monkeypatch, WED_DAY)
    at = _make(); at.run(); _login(at, "김준오", "pw-day")
    assert at.session_state["nav_page"] == "home"
    assert at.button(key="dash_home_open")
    assert dash_db.rpc_calls == []                         # 홈 카드는 읽기만
    at.run()
    assert at.session_state["nav_page"] == "home"          # 렌더만으로는 이동하지 않는다(on_click 콜백)
    at.button(key="dash_home_open").click(); at.run()
    assert at.session_state["nav_page"] == "dash" and _has_title(at, "today")


def test_past_and_future_slots_are_read_only(dash_db, monkeypatch):
    _fix_now(monkeypatch, WED_DAY)
    at = _open("김민수", "pw-admin")
    assert len(_done_buttons(at)) == 7
    dash_db.rpc("dash_generate_cards", {"p_work_date": "2026-10-20", "p_shift": "day", "p_template_ids": [1, 2]})
    at.date_input(key="dash_date").set_value(datetime(2026, 10, 20).date()); at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert any("읽기 전용" in str(i.value) for i in at.info)
    assert _done_buttons(at) == [] and not [b for b in at.button if b.key == "dash_gen"]
    at.date_input(key="dash_date").set_value(datetime(2026, 10, 22).date()); at.run()
    assert any("읽기 전용" in str(i.value) for i in at.info) and _done_buttons(at) == []
    assert len(dash_db.rpc_calls) == 2                     # 과거·미래 슬롯은 생성하지 않는다


# ─── 8. 템플릿 관리: 스냅샷 보존, 담당자 검증 ──────────────────────

def test_template_edit_keeps_existing_card_snapshot(dash_db, monkeypatch):
    _fix_now(monkeypatch, WED_DAY)
    at = _open("김민수", "pw-admin")                      # 카드 7개 생성
    at = _open("김민수", "pw-admin", sub="tmpl")
    assert _has_title(at, "tmpl")
    pick = next(s for s in at.selectbox if str(s.key or "").startswith("dash_tmpl_pick_"))
    pick.set_value(next(o for o in pick.options if o.startswith("1 · "))); at.run()
    form_inputs = [t for t in at.text_input if t.label == "제목 *"]
    form_inputs[0].set_value("야간 인수 확인(개정)")
    next(b for b in at.button if b.label == "저장").click(); at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert dash_db.tables["dash_routine_templates"][0]["title"] == "야간 인수 확인(개정)"
    assert dash_db.cards(template_id=1)[0]["title"] == "야간 인수 확인"         # 스냅샷 보존
    # 비활성화 — 카드는 남고 다음 생성에서만 빠진다
    pick = next(s for s in at.selectbox if str(s.key or "").startswith("dash_tmpl_pick_"))
    pick.set_value(next(o for o in pick.options if o.startswith("1 · "))); at.run()
    at.button(key="dash_tmpl_off_1").click(); at.run()
    assert dash_db.tables["dash_routine_templates"][0]["active"] is False
    assert len(dash_db.cards(template_id=1)) == 1
    dash_db.rpc("dash_generate_cards", {"p_work_date": "2026-10-22", "p_shift": "day", "p_template_ids": [1]})
    assert dash_db.cards(work_date="2026-10-22") == []


def test_template_rejects_unknown_assignee_and_new_code_format(dash_db, monkeypatch):
    _fix_now(monkeypatch, WED_DAY)
    at = _open("김민수", "pw-admin", sub="tmpl")
    import app.dash_page as dp
    flashes = []
    ctx = dp.Ctx(db=dash_db, current_user=lambda: {"username": "김민수", "role": "admin"}, is_admin=True,
                 readonly=False, click_guard=lambda k: True, confirm_gate=lambda *a, **k: False,
                 nav_flash=lambda m, action=None: flashes.append(m), nav_go=lambda *a, **k: None,
                 toss_table=lambda *a, **k: None, load_users=lambda: USERS)
    assert dp._validate_assignees(ctx, ["김준오", "없는사람"])[1] == "등록되지 않은 계정: 없는사람"
    assert dp._validate_assignees(ctx, ["김준오", " "])[1] == "담당자 값이 비어 있습니다"
    assert dp._validate_assignees(ctx, ["김준오", "김준오"])[0] == ["김준오"]
    # 새 템플릿 추가(폼) → code 형식
    n0 = len(dash_db.tables["dash_routine_templates"])
    [t for t in at.text_input if t.label == "제목 *"][0].set_value("새 항목")
    next(b for b in at.button if b.label == "저장").click(); at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    rows = dash_db.tables["dash_routine_templates"]
    assert len(rows) == n0 + 1 and re.fullmatch(r"production_day_[0-9a-f]{8}", rows[-1]["code"]) \
        and rows[-1]["assignee_user_ids"] == [] and rows[-1]["active"] is True


# ─── 9. 로컬 읽기 모드 / Old DB ────────────────────────────────

def test_local_readonly_mode_writes_nothing(dash_db, monkeypatch):
    _fix_now(monkeypatch, WED_DAY)
    at = _open(None, None, readonly=True)                  # auth.disabled → 테스트 관리자, 읽기 모드
    assert _has_title(at, "today")
    assert any("로컬 읽기 모드" in str(w.value) for w in at.warning)
    at.run()
    assert at.button(key="dash_gen").disabled              # 수동 생성 버튼 잠김(AppTest 도 클릭 거부)
    assert dash_db.writes == [] and dash_db.rpc_calls == []
    # 핸들러·생성 함수를 직접 불러도 읽기 모드면 쓰기 0
    import app.dash_page as dp
    flashes = []
    ctx = dp.Ctx(db=dash_db, current_user=lambda: {"username": "test", "role": "admin"}, is_admin=True,
                 readonly=True, click_guard=lambda k: True, confirm_gate=lambda *a, **k: False,
                 nav_flash=lambda m, action=None: flashes.append(m), nav_go=lambda *a, **k: None,
                 toss_table=lambda *a, **k: None, load_users=lambda: USERS)
    _, info = dp.ensure_cards(ctx, dash_db.tables["dash_routine_templates"], (WED_DAY.date(), "day"), {}, [])
    assert "읽기 모드" in (info["msg"] or "") and dash_db.rpc_calls == []
    fake = {"id": 1, "work_date": "2026-10-21", "shift": "day", "assignee_user_ids": ["test"], "title": "x"}
    assert dp.handle_done(ctx, fake) is False and dp.handle_undo(ctx, fake, "t") is False
    assert dash_db.writes == [] and all("읽기 모드" in f for f in flashes)
    # 템플릿 저장도 차단
    goto(at, "dash", "tmpl")
    assert any("로컬 읽기 모드" in str(w.value) for w in at.warning)
    assert dash_db.writes == []


def test_old_db_without_tables_degrades_safely(monkeypatch):
    import db
    m = DashMock(tables_missing=True).install(monkeypatch, db)
    _fix_now(monkeypatch, WED_DAY)
    at = _make(); at.run(); _login(at, "김민수", "pw-admin")
    assert not at.exception
    assert not [b for b in at.button if b.key == "dash_home_open"], "테이블 없으면 홈 카드 생략"
    goto(at, "dash", "today")
    assert any("준비 중" in str(i.value) for i in at.info)
    goto(at, "dash", "rate"); goto(at, "dash", "tmpl")
    assert not at.exception and m.writes == []


# ─── 10. 정적: dash_ 외 쓰기 0, date.today()/naive now 금지 ─────────────

def _write_calls(tree):
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr in ("insert", "update", "update_count", "delete", "rpc"):
            arg = node.args[0] if node.args else None
            out.append((node.func.attr, arg.value if isinstance(arg, ast.Constant) else "<dynamic>", node.lineno))
    return out


_HOME_WRITE_TOKENS = (".insert(", ".update(", ".update_count(", ".upsert(", ".rpc(", ".delete(")


def _home_block(app_src):
    h0 = app_src.index("# 업무 루틴 홈 카드")
    h1 = app_src.index("_h_so = fetch(", h0)
    return app_src[h0:h1]


def _assert_home_block_readonly(home):
    """홈 카드 호출부는 읽기 전용(C12): 쓰기 메서드 문자열·시각 생성 호출이 없어야 한다."""
    for tok in _HOME_WRITE_TOKENS:
        assert tok not in home, tok
    assert "today()" not in home and ".now(" not in home


def test_home_block_readonly_check_detects_injection():
    """역검사(C12): 검사 자체가 살아있는지 — 홈 카드 블록에 쓰기 호출 문자열을 주입하면 실패해야 한다."""
    home = _home_block(open(APP_FILE, encoding="utf-8").read())
    _assert_home_block_readonly(home)                                   # 원본은 통과
    for inj in ("_db.update_count('dash_cards', 'card_id=eq.1', {})", "db.upsert('dash_cards', [])",
                "fetch_one('x').insert('dash_cards', [])", "datetime.now()"):
        with pytest.raises(AssertionError):
            _assert_home_block_readonly(home + "\n" + inj)


def test_static_only_dash_tables_are_written():
    for path in ("app/dash_page.py", "utils/dash_routine.py"):
        src = open(os.path.join(ROOT, path), encoding="utf-8").read()
        for op, target, ln in _write_calls(ast.parse(src)):
            assert isinstance(target, str) and (target.startswith("dash_") or target == "dash_generate_cards"), \
                (path, op, target, ln)
        tree = ast.parse(src)
        now_defs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "now_utc"]
        inside_now_utc = {id(c) for f in now_defs for c in ast.walk(f)}
        for node in ast.walk(tree):                  # 주석·docstring 제외, 호출만
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in ("today", "utcnow", "fromtimestamp"), (path, node.lineno)
                if node.func.attr == "now":
                    # 시각 생성은 now_utc() 정의 안에서만(Codex L1) — 그 밖은 now_utc() 호출만 허용
                    assert id(node) in inside_now_utc, (path, node.lineno, "now() 는 now_utc 안에서만")
    # 본체의 업무 루틴 블록·홈 카드 호출부
    app_src = open(APP_FILE, encoding="utf-8").read()
    a = app_src.index('elif page == "업무 루틴":')
    b = app_src.index('elif page == "생산 보고":')
    block = app_src[a:b]
    block_src = block.replace('elif page == "업무 루틴":', "if True:", 1)
    for op, target, ln in _write_calls(ast.parse(block_src)):
        assert isinstance(target, str) and target.startswith("dash_"), (op, target)
    assert "today()" not in block and ".now(" not in block
    # 홈 카드 호출부(업무 루틴 홈 카드 try 블록)도 검사 범위
    _assert_home_block_readonly(_home_block(app_src))
    # Ctx 생성 헬퍼도 쓰기 없음
    c0 = app_src.index("def _dash_ctx_make("); c1 = app_src.index("\n\n\n", c0)
    assert not _write_calls(ast.parse(app_src[c0:c1]))


def test_static_nav_and_subs_for_consumers():
    src = open(APP_FILE, encoding="utf-8").read()
    assert '("dash", "업무 루틴", [("today", "오늘 루틴"), ("rate", "완료율"),' in src
    assert 'NAV_SUB_ADMIN = {("dash", "rate"), ("dash", "tmpl")}' in src
    assert src.count("_subs_for(") >= 6          # 정의 1 + 소비자 5
    a = src.index('elif page == "업무 루틴":'); b = src.index('elif page == "생산 보고":')
    assert set(re.findall(r'^    if _sub == "(\w+)"', src[a:b], re.M)) == {"today", "rate", "tmpl"}
    assert not re.search(r"탭(에서|의|에 )", src[a:b])


# ─── 11. 조회 프로파일: 오늘 루틴 진입 ≤ 6회 (목 기준 — dash_·work_calendar 조회만 센다) ─────

def _dash_fetches(dash_db):
    return [t for t, _ in dash_db.fetch_calls if t.startswith("dash_") or t == "work_calendar"]


def test_today_first_generation_query_budget(dash_db, monkeypatch):
    """첫 생성 진입: 조회 ≤ 8 (RPC 1 + 생성 뒤 재조회 1 포함) — 계획서 §6.
    C12(2026-10-23): RPC 도 왕복이므로 조회+RPC 합산 ≤ 8 로 조인다. REQ3 은 P5-4 보류."""
    _fix_now(monkeypatch, WED_DAY)
    at = _make(); at.run(); _login(at, "김준오", "pw-day")
    dash_db.fetch_calls.clear(); dash_db.rpc_calls.clear()
    goto(at, "dash", "today")
    assert len(dash_db.rpc_calls) == 1
    assert len(_dash_fetches(dash_db)) <= 8, _dash_fetches(dash_db)
    assert len(_dash_fetches(dash_db)) + len(dash_db.rpc_calls) <= 8, (_dash_fetches(dash_db), dash_db.rpc_calls)


def test_today_reentry_query_budget(dash_db, monkeypatch):
    """재진입(카드 이미 있음): 조회 ≤ 6, RPC 0."""
    _fix_now(monkeypatch, WED_DAY)
    at = _open("김준오", "pw-day")
    dash_db.fetch_calls.clear(); dash_db.rpc_calls.clear()
    at.run()
    assert len(_dash_fetches(dash_db)) <= 6, _dash_fetches(dash_db)
    assert dash_db.rpc_calls == []


# ─── Codex 재리뷰 반영 (2026-10-21): M1 달력 실패 / M2 저장 반환값 / REQ 보강 ─────────────

def test_calendar_fetch_failure_stops_generation_but_keeps_cards(dash_db, monkeypatch):
    """M1: work_calendar 조회 실패 → 자동·수동 생성 0회 + 경고, 기존 카드는 보인다."""
    _fix_now(monkeypatch, WED_DAY)
    at = _open("김민수", "pw-admin")                      # 카드 7개 생성
    assert len(dash_db.cards(shift="day")) == 7
    dash_db.fetch_raise_for = "work_calendar"
    dash_db.rpc_calls.clear()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert any("휴무 달력을 읽지 못해" in str(w.value) for w in at.warning)
    assert dash_db.rpc_calls == [] and len(_done_buttons(at)) == 7
    # 수동 생성 버튼도 생성하지 않는다
    at.button(key="dash_gen").click(); at.run()
    assert dash_db.rpc_calls == [] and any("휴무 달력을 읽지 못해" in f for f in _flash(at))
    # 새 템플릿을 넣어도(빠진 템플릿 있음) 달력 실패면 RPC 없음
    dash_db.tables["dash_routine_templates"].append({"id": 99, "code": "prod_day_99", "part_id": 1, "shift": "day",
        "seq": 9, "title": "추가", "done_criteria": "", "assignee_user_ids": ["김준오"], "active_rule": "always",
        "active": True, "created_at": "", "updated_at": ""})
    at.run()
    assert dash_db.rpc_calls == []
    import app.dash_page as dp
    assert dp.load_calendar(dash_db) is None
    dash_db.fetch_raise_for = None
    assert dp.load_calendar(dash_db) == {}


def _ctx(dash_db, username="김민수", role="admin", readonly=False, flashes=None, guard=None):
    import app.dash_page as dp
    return dp.Ctx(db=dash_db, current_user=lambda: {"username": username, "role": role}, is_admin=(role == "admin"),
                  readonly=readonly, click_guard=guard or (lambda k: True), confirm_gate=lambda *a, **k: False,
                  nav_flash=lambda m, action=None: (flashes if flashes is not None else []).append(m),
                  nav_go=lambda *a, **k: None, toss_table=lambda *a, **k: None, load_users=lambda: USERS)


def test_template_update_false_is_not_reported_as_success(dash_db, monkeypatch):
    """M2: db.update 가 False → 성공 안내 없음·오류 안내. 순서 저장은 행별 결과 N/M."""
    import app.dash_page as dp
    tpl = dash_db.tables["dash_routine_templates"][0]
    fl = []
    ctx = _ctx(dash_db, flashes=fl)
    dash_db.update_false = True
    assert dp._set_template_active(ctx, tpl, False) is False
    assert fl and "저장되지 않았습니다" in fl[-1] and not any("비활성화 —" in f for f in fl)
    assert tpl["active"] is True
    dash_db.update_false = False
    assert dp._set_template_active(ctx, tpl, False) is True and tpl["active"] is False
    assert any("비활성화 —" in f for f in fl)
    # 순서 저장: 2번 행만 실패 → 2/3 반영, 부분 실패 안내
    fl.clear()
    dash_db.update_fail_ids = {2}
    assert dp.save_template_order(ctx, [1, 2, 3]) == (2, 3)
    assert "2/3 반영" in fl[-1] and "일부만" in fl[-1]
    assert [t["seq"] for t in dash_db.tables["dash_routine_templates"][:3]] == [1, 2, 3]
    dash_db.update_fail_ids = set()
    assert dp.save_template_order(ctx, [3, 2, 1]) == (3, 3) and "3/3 반영" in fl[-1]
    assert [t["seq"] for t in dash_db.tables["dash_routine_templates"][:3]] == [3, 2, 1]


def test_cookie_login_uses_username_for_completion(dash_db, monkeypatch):
    """REQ: 쿠키 자동 로그인 경로도 auth_user.username 으로 체크된다."""
    import base64
    import streamlit as st_mod
    from tests.dash_mock import SECRET
    from utils import auth as _auth
    tok = base64.urlsafe_b64encode(_auth.make_token("김준오", SECRET).encode("utf-8")).decode()

    class _Ctx:
        cookies = {"ws_auth": tok}
        headers = {}
    monkeypatch.setattr(st_mod, "context", _Ctx())
    _fix_now(monkeypatch, WED_DAY)
    at = _make(); at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert at.session_state["auth_user"]["username"] == "김준오", at.session_state["auth_user"]
    goto(at, "dash", "today")
    cid = dash_db.cards(shift="day")[0]["id"]
    at.button(key=f"dash_done_{cid}").click(); at.run()
    assert dash_db.cards(id=cid)[0]["completed_by"] == "김준오"
    assert dash_db.activity()[-1]["user_id"] == "김준오"


def test_readonly_with_existing_cards_and_templates_writes_nothing(dash_db, monkeypatch):
    """REQ: 읽기 모드에서 todo/done 카드·활성 템플릿이 있어도 완료·취소·활성화·순서 저장 전부 쓰기 0."""
    _fix_now(monkeypatch, WED_DAY)
    dash_db.rpc("dash_generate_cards", {"p_work_date": "2026-10-21", "p_shift": "day", "p_template_ids": [1, 2]})
    done = dash_db.cards(template_id=2)[0]
    done.update({"status": "done", "completed_by": "김준오", "completed_at": "2026-10-21T01:00:00+00:00"})
    dash_db.writes.clear(); dash_db.rpc_calls.clear()
    at = _open(None, None, readonly=True)
    assert _has_title(at, "today")
    btns = [b for b in at.button if str(b.key or "").startswith(("dash_done_", "dash_undo_"))]
    assert btns and all(b.disabled for b in btns)
    at.run(); goto(at, "dash", "tmpl"); goto(at, "dash", "today")
    assert dash_db.writes == [] and dash_db.rpc_calls == []
    import app.dash_page as dp
    fl = []
    ctx = _ctx(dash_db, username="test", readonly=True, flashes=fl)
    todo = dash_db.cards(template_id=1)[0]
    assert dp.handle_done(ctx, todo) is False
    assert dp.handle_undo(ctx, done, done["completed_at"]) is False
    assert dp._set_template_active(ctx, dash_db.tables["dash_routine_templates"][0], False) is False
    assert dp.save_template_order(ctx, [1, 2]) == (0, 2)
    assert dash_db.writes == [] and all("읽기 모드" in f for f in fl) and len(fl) == 4


def test_handler_rejects_when_shift_boundary_passed(dash_db, monkeypatch):
    """REQ: 화면은 19:29 주간이었는데 핸들러 실행 시점이 19:30 이면 주간 카드 체크 거부(슬롯 재계산)."""
    import app.dash_page as dp
    dash_db.rpc("dash_generate_cards", {"p_work_date": "2026-10-21", "p_shift": "day", "p_template_ids": [1]})
    card = dash_db.cards(template_id=1)[0]
    fl = []
    ctx = _ctx(dash_db, username="김준오", role="worker", flashes=fl)
    monkeypatch.setattr(dp, "now_utc", lambda: datetime(2026, 10, 21, 19, 29, tzinfo=KST))
    assert dp.handle_done(ctx, card) is True and dash_db.cards(template_id=1)[0]["status"] == "done"
    monkeypatch.setattr(dp, "now_utc", lambda: datetime(2026, 10, 21, 19, 30, tzinfo=KST))
    c = dash_db.cards(template_id=1)[0]
    assert dp.handle_undo(ctx, c, c["completed_at"]) is False
    assert "현재 교대" in fl[-1] and dash_db.cards(template_id=1)[0]["status"] == "done"
    assert len(dash_db.activity()) == 1


def test_duplicate_call_in_same_run_logs_once(dash_db, monkeypatch):
    """REQ: 같은 카드 중복 호출(이중 클릭)은 클릭 가드가 막아 활동 로그 1건."""
    import app.dash_page as dp
    dash_db.rpc("dash_generate_cards", {"p_work_date": "2026-10-21", "p_shift": "day", "p_template_ids": [1]})
    card = dash_db.cards(template_id=1)[0]
    seen = []

    def guard(k):               # click_guard 와 같은 의미: 같은 키는 ttl 안 두 번째 거부
        if k in seen:
            return False
        seen.append(k)
        return True
    fl = []
    ctx = _ctx(dash_db, username="김준오", role="worker", flashes=fl, guard=guard)
    monkeypatch.setattr(dp, "now_utc", lambda: WED_DAY)
    assert dp.handle_done(ctx, card) is True
    assert dp.handle_done(ctx, dict(card, status="todo")) is False
    assert "방금 같은 처리" in fl[-1]
    assert len([x for x in dash_db.activity() if x["card_id"] == card["id"]]) == 1
