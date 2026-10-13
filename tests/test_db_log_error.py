"""오류 기록(app_errors, migration 067)·RPC 헬퍼 — db.py 단위 테스트 (2026-10-13).

conftest 의 autouse fixture 가 db.requests 를 차단 스텁으로, db.log_error 를 no-op 로
바꾸므로 여기서는 monkeypatch 로 되돌려 실제 함수를 검증한다.
"""
import importlib
import os
import time

import pytest

APP_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "streamlit_app.py")


class _Resp:
    def __init__(self, status, text="", body=None):
        self.status_code, self.text, self._body = status, text, body

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


class _Req:
    """requests 대역 — 호출 기록 + 지정한 응답/예외."""

    class Timeout(Exception):
        pass

    class ConnectionError(Exception):
        pass

    def __init__(self, resp=None, raise_exc=None):
        self.resp, self.raise_exc, self.calls = resp, raise_exc, []

    def _do(self, method, url, **kw):
        self.calls.append((method, url, kw))
        if self.raise_exc:
            raise self.raise_exc
        return self.resp

    def post(self, url, **kw):
        return self._do("post", url, **kw)

    def patch(self, url, **kw):
        return self._do("patch", url, **kw)

    def delete(self, url, **kw):
        return self._do("delete", url, **kw)


@pytest.fixture()
def dbm(monkeypatch):
    import db
    db = importlib.reload(db)
    monkeypatch.setattr(db, "_url", lambda: "https://mock.local")
    monkeypatch.setattr(db, "_headers", lambda role="service_role": {
        "apikey": "SECRET_KEY_X", "Authorization": "Bearer SECRET_KEY_X",
        "Content-Type": "application/json"})
    monkeypatch.setattr(db, "clear_cache", lambda: None)
    db._ERR_RECENT.clear()
    return db


# ─── T-C1 log_error 는 어떤 경우에도 예외를 내지 않는다 ───
@pytest.mark.parametrize("resp,exc", [
    (_Resp(404, "not found"), None),
    (_Resp(500, "boom"), None),
    (None, _Req.ConnectionError("dns")),
    (None, _Req.Timeout("slow")),
])
def test_log_error_never_raises(dbm, monkeypatch, resp, exc):
    monkeypatch.setattr(dbm, "requests", _Req(resp, exc))
    assert dbm.log_error("manual", "x" * 10) is False


def test_log_error_posts_truncated_record_without_secrets(dbm, monkeypatch):
    req = _Req(_Resp(201))
    monkeypatch.setattr(dbm, "requests", req)
    ok = dbm.log_error("db_write", "D" * 900, table_name="shipments",
                       tb="T" * 9000, page="출고 관리", user_name="홍길동")
    assert ok is True
    assert len(req.calls) == 1
    method, url, kw = req.calls[0]
    assert method == "post" and url.endswith("/rest/v1/app_errors")
    assert kw["timeout"] == (2, 3)
    body = kw["data"]
    assert "SECRET_KEY_X" not in body and "mock.local" not in body
    import json
    rec = json.loads(body)[0]
    assert rec["kind"] == "db_write" and rec["table_name"] == "shipments"
    assert len(rec["detail"]) == 500 and len(rec["traceback"]) == 4000
    assert rec["page"] == "출고 관리" and rec["user_name"] == "홍길동"


def test_log_error_unknown_kind_becomes_manual(dbm, monkeypatch):
    req = _Req(_Resp(201))
    monkeypatch.setattr(dbm, "requests", req)
    dbm.log_error("weird", "y")
    import json
    assert json.loads(req.calls[0][2]["data"])[0]["kind"] == "manual"


def test_log_error_without_streamlit_context(dbm, monkeypatch):
    """스크립트(백업·요약)처럼 session_state 가 없는 컨텍스트에서도 예외 없음."""
    class _NoCtx:
        def get(self, *a, **k):
            raise RuntimeError("no script run context")
    monkeypatch.setattr(dbm.st, "session_state", _NoCtx(), raising=False)
    req = _Req(_Resp(201))
    monkeypatch.setattr(dbm, "requests", req)
    assert dbm.log_error("manual", "ctx-less") is True
    import json
    rec = json.loads(req.calls[0][2]["data"])[0]
    assert rec["page"] is None and rec["user_name"] is None


# ─── T-C4 같은 내용은 60초에 한 번 ───
def test_log_error_dedups_same_detail_within_60s(dbm, monkeypatch):
    req = _Req(_Resp(201))
    monkeypatch.setattr(dbm, "requests", req)
    t = [1000.0]
    monkeypatch.setattr(dbm.time, "monotonic", lambda: t[0])
    assert dbm.log_error("db_write", "same") is True
    assert dbm.log_error("unhandled", "same") is False      # kind 무관
    t[0] += 61
    assert dbm.log_error("db_write", "same") is True
    assert len(req.calls) == 2


# ─── T-C2 db 쓰기 실패가 기록된다, 재귀 없음 ───
def test_update_failure_logs_once_and_returns_false(dbm, monkeypatch):
    monkeypatch.setattr(dbm, "requests", _Req(_Resp(400, '{"code":"23505"}')))
    calls = []
    monkeypatch.setattr(dbm, "log_error", lambda *a, **k: calls.append((a, k)) or True)
    assert dbm.update("shipments", "shipment_id=eq.1", {"status": "X"}) is False
    assert len(calls) == 1
    assert calls[0][0][0] == "db_write" and calls[0][1]["table_name"] == "shipments"
    assert "400" in calls[0][0][1]


def test_insert_and_delete_failure_log_then_raise(dbm, monkeypatch):
    monkeypatch.setattr(dbm, "requests", _Req(_Resp(409, "dup")))
    calls = []
    monkeypatch.setattr(dbm, "log_error", lambda *a, **k: calls.append(a) or True)
    with pytest.raises(RuntimeError):
        dbm.insert("wo_tracking", [{"a": 1}])
    with pytest.raises(RuntimeError):
        dbm.delete("wo_tracking", "wo_id=eq.1")
    assert [c[0] for c in calls] == ["db_write", "db_write"]


def test_log_error_does_not_call_insert(dbm, monkeypatch):
    monkeypatch.setattr(dbm, "insert", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("log_error 가 insert 를 불렀다")))
    monkeypatch.setattr(dbm, "requests", _Req(_Resp(201)))
    assert dbm.log_error("manual", "no-recursion") is True


# ─── update_count ───
def test_update_count_returns_matched_rows(dbm, monkeypatch):
    monkeypatch.setattr(dbm, "requests", _Req(_Resp(200, "[{}]", [{"shipment_id": 1}])))
    assert dbm.update_count("shipments", "shipment_id=eq.1&status=eq.DRAFT",
                            {"status": "CANCELLED"}) == 1
    monkeypatch.setattr(dbm, "requests", _Req(_Resp(200, "[]", [])))
    assert dbm.update_count("shipments", "shipment_id=eq.1&status=eq.DRAFT",
                            {"status": "CANCELLED"}) == 0
    monkeypatch.setattr(dbm, "requests", _Req(_Resp(400, "bad")))
    monkeypatch.setattr(dbm, "log_error", lambda *a, **k: True)
    assert dbm.update_count("shipments", "x=eq.1", {"a": 1}) == -1


# ─── rpc 예외 3종 ───
def test_rpc_success_returns_body_and_clears_cache(dbm, monkeypatch):
    cleared = []
    monkeypatch.setattr(dbm, "clear_cache", lambda: cleared.append(1))
    monkeypatch.setattr(dbm, "requests", _Req(_Resp(200, '{"ok":true}', {"ok": True})))
    assert dbm.rpc("confirm_shipment", {"p": 1}) == {"ok": True}
    assert cleared == [1]


def test_rpc_unavailable_on_pgrst202_and_logs_fallback(dbm, monkeypatch):
    monkeypatch.setattr(dbm, "requests", _Req(_Resp(
        404, "x", {"code": "PGRST202", "message": "Could not find the function"})))
    calls = []
    monkeypatch.setattr(dbm, "log_error", lambda *a, **k: calls.append(a) or True)
    with pytest.raises(dbm.RpcUnavailable):
        dbm.rpc("confirm_shipment", {})
    assert calls and calls[0][0] == "rpc_fallback"


def test_rpc_rejected_keeps_code_and_message(dbm, monkeypatch):
    cleared = []
    monkeypatch.setattr(dbm, "clear_cache", lambda: cleared.append(1))
    monkeypatch.setattr(dbm, "requests", _Req(_Resp(
        400, "x", {"code": "P0001", "message": "stale"})))
    monkeypatch.setattr(dbm, "log_error", lambda *a, **k: True)
    with pytest.raises(dbm.RpcRejected) as ei:
        dbm.rpc("confirm_shipment", {})
    assert ei.value.code == "P0001" and ei.value.message == "stale"
    assert cleared == [1], "거부 뒤에도 캐시를 비운다"


@pytest.mark.parametrize("resp,exc", [
    (None, _Req.Timeout("t")),
    (None, _Req.ConnectionError("c")),
    (_Resp(502, "bad gateway"), None),
    (_Resp(404, "<html>", None), None),          # JSON 아님 → 함수 없음 아님
    (_Resp(200, "", None), None),                # 본문 없음
])
def test_rpc_transport_error_is_unknown_state(dbm, monkeypatch, resp, exc):
    monkeypatch.setattr(dbm, "requests", _Req(resp, exc))
    with pytest.raises(dbm.RpcTransportError):
        dbm.rpc("confirm_shipment", {})


# ─── T-C3 미처리 예외 훅 (AppTest) ───
def _mini_app(at_src):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_string(at_src, default_timeout=30)
    at.secrets["supabase"] = {"url": "https://mock.supabase.local",
                              "anon_key": "a", "service_role_key": "s"}
    return at


def test_uncaught_exception_is_logged_and_still_shown(monkeypatch):
    import db
    db._HOOK_INSTALLED = False
    calls = []
    monkeypatch.setattr(db, "log_error", lambda *a, **k: calls.append((a, k)) or True)
    at = _mini_app(
        "import streamlit as st, db\n"
        "db.install_uncaught_hook()\n"
        "st.session_state['_err_ctx'] = {'page': '테스트', 'user': 'u'}\n"
        "raise RuntimeError('boom-067')\n")
    at.run()
    assert len(at.exception) == 1, "기존 오류 화면은 그대로"
    assert "boom-067" in at.exception[0].value
    assert len(calls) == 1
    (kind, detail), kw = calls[0]
    assert kind == "unhandled" and "boom-067" in detail
    assert "RuntimeError" in kw["tb"]


def test_rerun_and_stop_are_not_logged(monkeypatch):
    import db
    db._HOOK_INSTALLED = False
    calls = []
    monkeypatch.setattr(db, "log_error", lambda *a, **k: calls.append(a) or True)
    at = _mini_app(
        "import streamlit as st, db\n"
        "db.install_uncaught_hook()\n"
        "n = st.session_state.get('n', 0)\n"
        "st.session_state['n'] = n + 1\n"
        "if n == 0:\n"
        "    st.rerun()\n"
        "st.write('done')\n"
        "st.stop()\n")
    at.run()
    assert not at.exception
    assert calls == []


def test_hook_installs_once(monkeypatch):
    import db
    import logging
    db._HOOK_INSTALLED = False
    lg = logging.getLogger("streamlit.error_util")
    for h in list(lg.handlers):
        if getattr(h, "name", "") == "wsapp_app_errors":
            lg.removeHandler(h)
    assert db.install_uncaught_hook() is True
    assert db.install_uncaught_hook() is True
    assert sum(1 for h in lg.handlers
               if getattr(h, "name", "") == "wsapp_app_errors") == 1


# ─── 2026-10-13 Data 리뷰 반영: 3xx/408/403, 빈 필터, 회로 차단 ───
def test_rpc_3xx_is_never_success(dbm, monkeypatch):
    monkeypatch.setattr(dbm, "log_error", lambda *a, **k: True)
    monkeypatch.setattr(dbm, "requests", _Req(_Resp(
        300, "x", {"code": "PGRST203", "message": "ambiguous overload"})))
    with pytest.raises(dbm.RpcRejected) as ei:
        dbm.rpc("confirm_shipment", {})
    assert ei.value.code == "PGRST203"
    monkeypatch.setattr(dbm, "requests", _Req(_Resp(302, "x", {"ok": True})))
    with pytest.raises(dbm.RpcTransportError):
        dbm.rpc("confirm_shipment", {})


def test_rpc_408_is_transport_and_403_keeps_code(dbm, monkeypatch):
    monkeypatch.setattr(dbm, "log_error", lambda *a, **k: True)
    monkeypatch.setattr(dbm, "requests", _Req(_Resp(408, "", None)))
    with pytest.raises(dbm.RpcTransportError):
        dbm.rpc("next_w_lot", {})
    monkeypatch.setattr(dbm, "requests", _Req(_Resp(
        403, "x", {"code": "42501", "message": "permission denied"})))
    with pytest.raises(dbm.RpcRejected) as ei:
        dbm.rpc("next_w_lot", {})
    assert ei.value.code == "42501"


def test_update_count_rejects_empty_filter(dbm, monkeypatch):
    req = _Req(_Resp(200, "[]", []))
    monkeypatch.setattr(dbm, "requests", req)
    with pytest.raises(ValueError):
        dbm.update_count("shipments", "", {"status": "X"})
    with pytest.raises(ValueError):
        dbm.update_count("shipments", "   ", {"status": "X"})
    assert req.calls == []
    dbm.update_count("shipments", "shipment_id=eq.1", {"a": 1}, select="shipment_id")
    assert req.calls[0][1].endswith("shipment_id=eq.1&select=shipment_id")


def test_log_error_circuit_breaker_after_post_failure(dbm, monkeypatch):
    req = _Req(None, _Req.ConnectionError("down"))
    monkeypatch.setattr(dbm, "requests", req)
    t = [5000.0]
    monkeypatch.setattr(dbm.time, "monotonic", lambda: t[0])
    assert dbm.log_error("db_write", "first") is False
    assert dbm.log_error("db_write", "second-different") is False
    assert len(req.calls) == 1, "기록 서버가 안 받으면 60초 동안 다른 내용도 보내지 않는다"
    t[0] += 61
    dbm.log_error("db_write", "third")
    assert len(req.calls) == 2


def test_log_error_rate_cap_per_minute(dbm, monkeypatch):
    req = _Req(_Resp(201))
    monkeypatch.setattr(dbm, "requests", req)
    t = [9000.0]
    monkeypatch.setattr(dbm.time, "monotonic", lambda: t[0])
    dbm._ERR_RATE[0], dbm._ERR_RATE[1] = 0.0, 0
    for i in range(40):
        dbm.log_error("db_write", f"err-{i}")
    assert len(req.calls) == dbm._ERR_RATE_MAX
    t[0] += 61
    assert dbm.log_error("db_write", "after-window") is True


def test_rpc_lock_timeout_500_is_rejected_not_transport(dbm, monkeypatch):
    """55P03/57014/40P01 은 PostgREST 가 500 으로 보내지만 함수는 롤백됨 — 거부(재시도 가능)."""
    monkeypatch.setattr(dbm, "log_error", lambda *a, **k: True)
    for code in ("55P03", "57014", "40P01"):
        monkeypatch.setattr(dbm, "requests", _Req(_Resp(
            500, "x", {"code": code, "message": "canceling statement"})))
        with pytest.raises(dbm.RpcRejected) as ei:
            dbm.rpc("confirm_shipment", {})
        assert ei.value.code == code
