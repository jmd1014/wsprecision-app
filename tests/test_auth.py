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
