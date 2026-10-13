"""
pytest 공통 설정.

- streamlit 이 설치되어 있으면 그대로 사용 (AppTest 기능 테스트 가능)
- 설치 안 된 환경 (CI 미니멀 등) 에서는 fake 모듈로 단위 테스트만 지원
"""
import sys
import types
import importlib.util


def _streamlit_available() -> bool:
    return importlib.util.find_spec("streamlit") is not None


def _install_fake_streamlit():
    if "streamlit" in sys.modules:
        return
    fake = types.ModuleType("streamlit")

    class _Secrets(dict):
        def __getitem__(self, k):
            return {
                "supabase": {
                    "url": "https://fake.local",
                    "anon_key": "fake_anon",
                    "service_role_key": "fake_service",
                }
            }[k]

    fake.secrets = _Secrets()
    sys.modules["streamlit"] = fake


if not _streamlit_available():
    _install_fake_streamlit()


# ─── 운영 DB·네트워크 차단 (2026-10-13, migration 067 오류 기록 도입과 함께) ───
# 테스트는 전부 mock DB(AppTest) 다. db.py 의 requests 호출이 fixture 밖으로
# 새면 DNS 실패를 기다리거나(느림) 환경에 따라 실제로 나갈 수 있어, 모든
# 테스트에서 db.requests 를 즉시 실패하는 스텁으로 바꾸고 log_error 는 no-op 로
# 둔다. 오류 기록·RPC 자체를 검증하는 테스트는 monkeypatch 로 되돌려 쓴다.
import pytest


class _BlockedRequests:
    class ConnectionError(Exception):
        pass

    def _blocked(self, *a, **k):
        raise self.ConnectionError("tests: 실제 HTTP 호출 차단 (db.requests 스텁)")

    get = post = patch = delete = put = _blocked


@pytest.fixture(autouse=True)
def _block_db_network(monkeypatch):
    try:
        import db
    except Exception:
        yield
        return
    monkeypatch.setattr(db, "requests", _BlockedRequests())
    monkeypatch.setattr(db, "log_error", lambda *a, **k: False)
    yield
