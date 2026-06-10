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
