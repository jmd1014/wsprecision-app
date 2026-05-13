"""
pytest 공통 설정 — Streamlit 의존성 회피용 fake 모듈
streamlit.secrets 접근 없이 단위 테스트가 돌도록 함.
"""
import sys
import types


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


_install_fake_streamlit()
