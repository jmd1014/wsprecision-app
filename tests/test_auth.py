"""
계정 로그인 (1·2단계) 검증

- utils/auth 단위: 해시/검증, 토큰 서명·만료
- AppTest: 로그인 게이트 차단, 잘못된 비밀번호, 정상 로그인,
  작업자 계정의 관리자 메뉴 숨김 + created_by 실명 기록
"""
import os
import sys
import importlib.util

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils import auth  # noqa: E402

streamlit_available = importlib.util.find_spec("streamlit") is not None

APP_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "streamlit_app.py")


# ─── 1. 단위: 해시 / 토큰 ──────────────────────────────

def test_hash_and_verify_roundtrip():
    h = auth.hash_pw("ws0807!")
    assert h.startswith("pbkdf2$")
    assert auth.verify_pw("ws0807!", h)
    assert not auth.verify_pw("WS0807!", h)      # 대소문자 구분
    assert not auth.verify_pw("", h)
    assert not auth.verify_pw("ws0807!", "깨진값")
    assert not auth.verify_pw("ws0807!", None)


def test_hash_salt_is_unique():
    assert auth.hash_pw("같은비번") != auth.hash_pw("같은비번")


def test_token_roundtrip_and_tamper():
    secret = "s" * 64
    tok = auth.make_token("김민수", secret)
    assert auth.parse_token(tok, secret) == "김민수"
    assert auth.parse_token(tok, "다른키" * 16) is None
    assert auth.parse_token(tok + "x", secret) is None
    assert auth.parse_token("garbage", secret) is None


def test_token_expiry():
    secret = "k" * 64
    tok = auth.make_token("김민수", secret, days=-1)   # 이미 만료
    assert auth.parse_token(tok, secret) is None


def test_password_rules():
    """비밀번호 규칙 (2026-08-05 정립): 6자 이상 · 앞뒤 공백 불가 ·
    아이디와 동일 불가. 그 외 문자 구성은 자유."""
    assert auth.check_password("abc12!") is None          # 정확히 6자
    assert auth.check_password("한글비밀번호도됨") is None
    assert auth.check_password("abc12") is not None       # 5자
    assert auth.check_password("") is not None
    assert auth.check_password(None) is not None
    assert auth.check_password(" abc123") is not None     # 앞 공백
    assert auth.check_password("abc123 ") is not None     # 뒤 공백
    assert auth.check_password("ab cd12") is None         # 중간 공백은 허용
    assert auth.check_password("김민수김민수", "김민수김민수") is not None


def test_username_rules():
    assert auth.check_username("김민수") is None
    assert auth.check_username("hj") is None
    assert auth.check_username("김") is not None          # 1자
    assert auth.check_username("김 민수") is not None     # 공백
    assert auth.check_username("a|b") is not None         # 토큰 구분자
    assert auth.check_username("a$b") is not None         # 해시 구분자


# ─── 2. AppTest: 게이트 동작 ───────────────────────────

pytestmark_app = pytest.mark.skipif(
    not streamlit_available, reason="streamlit 미설치 — AppTest 불가")

USERS = {
    "김민수": {"name": "김민수", "role": "admin",
             "pw": auth.hash_pw("pw-admin")},
    "현장": {"name": "현장", "role": "worker",
            "pw": auth.hash_pw("pw-field")},
}
SECRET = "a1" * 32
INSERTED = []


def _fetch_one(table, filter_query="", select="*"):
    import json
    if table == "app_settings" and "auth_users" in filter_query:
        return {"value": json.dumps(USERS, ensure_ascii=False)}
    if table == "app_settings" and "auth_secret" in filter_query:
        return {"value": SECRET}
    return None


@pytest.fixture()
def auth_db(monkeypatch):
    import db
    INSERTED.clear()
    monkeypatch.setattr(db, "fetch", lambda *a, **k: [])
    monkeypatch.setattr(db, "fetch_one", _fetch_one)
    monkeypatch.setattr(db, "insert",
                        lambda t, r: (INSERTED.append((t, r)), len(r))[1])
    monkeypatch.setattr(db, "update", lambda t, f, v: True)
    monkeypatch.setattr(db, "delete", lambda t, f: 1)
    monkeypatch.setattr(db, "health_check",
                        lambda: {"status": "OK", "counts": {}})
    monkeypatch.setattr(db, "debug_check", lambda: {"status": "mock"})
    if hasattr(db, "count_rows"):
        monkeypatch.setattr(db, "count_rows", lambda t, f="": 0)
    return db


def _make(bypass=False):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP_FILE, default_timeout=60)
    at.secrets["supabase"] = {"url": "https://mock.local",
                              "anon_key": "a", "service_role_key": "s"}
    if bypass:
        at.secrets["auth"] = {"disabled": True}
    return at


def _login(at, uid, pw):
    at.text_input[0].set_value(uid)
    at.text_input[1].set_value(pw)
    # 폼 제출 버튼은 form_submit_button — button 목록에 잡힌다
    next(b for b in at.button
         if getattr(b, "label", "") == "로그인").click()
    at.run()


@pytestmark_app
def test_gate_blocks_without_login(auth_db):
    at = _make()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    # st.stop() — 사이드바 메뉴가 렌더되지 않아야 한다
    assert not at.sidebar.radio
    assert any("로그인" in (m.value or "") for m in at.markdown)


@pytestmark_app
def test_wrong_password_rejected(auth_db):
    at = _make()
    at.run()
    _login(at, "김민수", "틀린비번")
    assert any("맞지 않습니다" in e.value for e in at.error)
    assert not at.sidebar.radio


@pytestmark_app
def test_admin_login_shows_all_menus(auth_db):
    at = _make()
    at.run()
    _login(at, "김민수", "pw-admin")
    assert not at.exception, [str(e.value) for e in at.exception]
    assert len(at.sidebar.radio) == 2          # 업무 + 관리자
    assert at.session_state["auth_user"]["role"] == "admin"


@pytestmark_app
def test_worker_login_hides_admin_menu(auth_db):
    at = _make()
    at.run()
    _login(at, "현장", "pw-field")
    assert not at.exception, [str(e.value) for e in at.exception]
    assert len(at.sidebar.radio) == 1          # 업무 진행만
    assert at.session_state["auth_user"]["role"] == "worker"


@pytestmark_app
def test_password_change_via_form(auth_db):
    """사이드바 비밀번호 변경 — st.form 이라 입력 경합 없이 저장된다"""
    SAVED = {}

    import db
    def _upd(t, f, v):
        SAVED[t] = v
        return True
    db.update = _upd

    at = _make()
    at.run()
    _login(at, "김민수", "pw-admin")
    # 사이드바 form 의 password 필드 3개 (로그인 폼은 이미 사라짐)
    pw_inputs = [t for t in at.sidebar.text_input]
    assert len(pw_inputs) >= 3, "비밀번호 변경 폼이 없음"
    pw_inputs[0].set_value("pw-admin")
    pw_inputs[1].set_value("newpw123")
    pw_inputs[2].set_value("newpw123")
    next(b for b in at.sidebar.button
         if getattr(b, "label", "") == "변경").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert "app_settings" in SAVED, "비밀번호가 저장되지 않음"
    import json as _j
    saved_users = _j.loads(SAVED["app_settings"]["value"])
    assert auth.verify_pw("newpw123", saved_users["김민수"]["pw"])


@pytestmark_app
def test_password_change_rejects_short(auth_db):
    at = _make()
    at.run()
    _login(at, "김민수", "pw-admin")
    pw_inputs = [t for t in at.sidebar.text_input]
    pw_inputs[0].set_value("pw-admin")
    pw_inputs[1].set_value("ab1")
    pw_inputs[2].set_value("ab1")
    next(b for b in at.sidebar.button
         if getattr(b, "label", "") == "변경").click()
    at.run()
    assert any("6자 이상" in e.value for e in at.error)


@pytestmark_app
def test_account_tab_creates_user(auth_db):
    """계정 관리 — 신규 계정이 규칙 검증을 거쳐 저장된다"""
    SAVED = {}
    import db
    db.update = lambda t, f, v: (SAVED.update({t: v}), True)[1]

    at = _make()
    at.run()
    _login(at, "김민수", "pw-admin")
    at.sidebar.radio[1].set_value("마스터 관리")
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    # 계정 관리 폼: 아이디 / 이름 / 초기 비밀번호
    acct_inputs = [t for t in at.text_input if t.key is None]
    ids = next(t for t in acct_inputs if "아이디" in (t.label or ""))
    name = next(t for t in acct_inputs if "이름" in (t.label or ""))
    pw = next(t for t in acct_inputs if "초기 비밀번호" in (t.label or ""))
    ids.set_value("박작업")
    name.set_value("박작업")
    pw.set_value("wk1234!")
    next(b for b in at.button
         if getattr(b, "label", "") == "계정 추가").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    import json as _j
    saved = _j.loads(SAVED["app_settings"]["value"])
    assert "박작업" in saved
    assert saved["박작업"]["role"] == "worker"
    assert auth.verify_pw("wk1234!", saved["박작업"]["pw"])


@pytestmark_app
def test_account_tab_rejects_duplicate_id(auth_db):
    at = _make()
    at.run()
    _login(at, "김민수", "pw-admin")
    at.sidebar.radio[1].set_value("마스터 관리")
    at.run()
    acct_inputs = [t for t in at.text_input if t.key is None]
    next(t for t in acct_inputs
         if "아이디" in (t.label or "")).set_value("현장")
    next(t for t in acct_inputs
         if "초기 비밀번호" in (t.label or "")).set_value("abc123!")
    next(b for b in at.button
         if getattr(b, "label", "") == "계정 추가").click()
    at.run()
    assert any("이미 있는 아이디" in e.value for e in at.error)


@pytestmark_app
def test_account_tab_protects_last_admin(auth_db):
    """유일한 관리자(김민수)는 작업자로 강등할 수 없다"""
    at = _make()
    at.run()
    _login(at, "김민수", "pw-admin")
    at.sidebar.radio[1].set_value("마스터 관리")
    at.run()
    sel = next(s for s in at.selectbox if s.key == "acct_pick")
    sel.set_value("김민수")
    at.run()
    # 기존 계정 폼의 역할 radio → 작업자로 변경 시도
    role_radio = [r for r in at.radio
                  if r.key is None and r.options == ["작업자", "관리자"]]
    role_radio[-1].set_value("작업자")
    next(b for b in at.button
         if getattr(b, "label", "") == "저장").click()
    at.run()
    assert any("마지막 관리자" in e.value for e in at.error)
    # 삭제 버튼도 비활성
    assert next(b for b in at.button if b.key == "acct_del").disabled


@pytestmark_app
def test_created_by_uses_logged_in_name(auth_db):
    """작업자 계정으로 직접 입고 → 원장 created_by 에 실명이 남는다"""
    import json as _json

    def _fetch(table, select="*", filter_query="", limit=1000):
        if table == "products":
            return [{"product_id": 1, "pn": "4PDVN-02", "customer": "미진"}]
        if table == "bom":
            return [{"bom_id": 1, "material_id": "M110",
                     "raw_material_name": "S304 Ø22*14",
                     "qty_per_pc": 1, "shared_factor": 1,
                     "process_type": None}]
        if table == "material_stock":
            return [{"material_id": "M110", "raw_name": "S304 Ø22*14",
                     "material_type": "SUS304", "spec": "φ22*14L",
                     "unit": "EA", "current_stock": 0,
                     "main_supplier": None}]
        return []

    import db
    db.fetch = _fetch
    at = _make()
    at.run()
    _login(at, "현장", "pw-field")
    # 작업자는 마스터 관리 접근 불가 — 홈에서 확인 대신, 관리자로 재로그인
    at2 = _make()
    at2.run()
    _login(at2, "김민수", "pw-admin")
    at2.sidebar.radio[1].set_value("마스터 관리")
    at2.run()
    assert not at2.exception, [str(e.value) for e in at2.exception]
    _rq = next(n for n in at2.number_input if n.key == "ft_rqty")
    _rq.set_value(100.0)
    at2.run()
    next(b for b in at2.button if b.key == "ft_rcv_go").click()
    at2.run()
    rows = [r for t, recs in INSERTED if t == "inventory_transactions"
            for r in recs]
    assert rows and rows[-1]["created_by"] == "김민수"
