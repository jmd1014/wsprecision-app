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


# ─── 화면 이동 (메뉴 구조 개편 2026-10-19, 계획서 §6-1) ───────────────────────
# AppTest 는 전부 goto() 로 화면을 연다. 개편 전(사이드바 radio 2개 + 페이지 안 탭)과
# 개편 후(사이드바 2단 버튼, 세션 키 nav_page / nav_sub)를 모두 지원해, 개편 전 코드에서
# 먼저 전체 통과시킨 뒤 개편 커밋을 올린다. 개편 후에는 이동 뒤 본문 "메인 › 세부" 제목
# 줄이 렌더됐는지 반드시 확인한다 — "없어야 한다" 단언이 엉뚱한 세부 화면에서 공짜로
# 통과하지 않게.
NAV_LABELS = {
    "home": ("홈", []),
    "so": ("수주 관리", [("input", "수주 입력"), ("list", "수주 목록"),
                        ("sched", "납품 스케줄")]),
    "po": ("구매 관리", [("new", "발주서 작성"), ("hist", "발주 이력"),
                        ("rcv", "입고 처리"), ("rstat", "입고 현황"),
                        ("pur", "매입 등록")]),
    "plan": ("생산 계획", [("wp", "주간 계획"), ("sb", "설비 스케줄"),
                          ("std", "공정 표준"), ("mc", "설비")]),
    "proc": ("공정 관리", [("in", "투입 등록"), ("proc", "공정 처리"),
                          ("board", "공정 현황판"), ("closed", "종결 지시서"),
                          ("trace", "LOT 추적")]),
    "ship": ("출고 관리", [("deliver", "출고 등록"), ("slip", "출고 전표"),
                          ("dstat", "출고 현황"), ("fstock", "완성 재고")]),
    "dash": ("업무 루틴", [("today", "오늘 루틴"), ("rate", "완료율"),
                          ("tmpl", "템플릿 관리")]),
}
NAV_ADMIN_LABELS = {
    "master": "마스터 관리", "cost": "원가 확인",
    "report": "생산 보고", "sales": "영업 보고",
}
TITLE_SEP = " › "


def _nav_main_key(main):
    """메인 키 또는 한글 이름 → 키."""
    if main in NAV_LABELS or main in NAV_ADMIN_LABELS:
        return main
    for k, (lbl, _) in NAV_LABELS.items():
        if lbl == main:
            return k
    for k, lbl in NAV_ADMIN_LABELS.items():
        if lbl == main:
            return k
    raise KeyError(f"goto: 알 수 없는 메인 메뉴 {main!r}")


def _nav_sub_key(main_key, sub):
    subs = NAV_LABELS.get(main_key, ("", []))[1]
    if sub is None:
        return None
    for k, lbl in subs:
        if sub in (k, lbl):
            return k
    raise KeyError(f"goto: {main_key} 에 세부 {sub!r} 없음")


def nav_title(main_key, sub_key):
    lbl, subs = NAV_LABELS[main_key]
    return lbl + TITLE_SEP + dict(subs)[sub_key]


def _nav_is_new(at):
    return "nav_page" in at.session_state


def _ss_get(at, key, default=None):
    """AppTest 의 session_state(SafeSessionState)는 .get 이 없다."""
    return at.session_state[key] if key in at.session_state else default


def goto(at, main, sub=None):
    """화면 이동. main/sub 는 키("ship", "slip") 또는 한글 이름 모두 가능.

    개편 전: 사이드바 radio 로 메인만 바꾼다(탭은 전부 그려지므로 sub 는 무시).
    개편 후: nav_page / nav_sub 세션 키를 바꿔 실행하고, 사용자 영역이면 본문 제목 줄
    "메인 › 세부" 가 렌더됐는지 확인한다(sub 를 주지 않으면 그 메인의 마지막·첫 세부).
    """
    mk = _nav_main_key(main)
    sk = _nav_sub_key(mk, sub) if mk in NAV_LABELS else None
    if _nav_is_new(at):
        at.session_state["nav_page"] = mk
        if sk is not None:
            _subs = dict(_ss_get(at, "nav_sub") or {})
            _subs[mk] = sk
            at.session_state["nav_sub"] = _subs
        at.run()
        assert not at.exception, [str(e.value) for e in at.exception]
        subs = NAV_LABELS.get(mk, ("", []))[1]
        if subs:
            cur = sk or (_ss_get(at, "nav_sub") or {}).get(mk) or subs[0][0]
            title = nav_title(mk, cur)
            texts = [str(getattr(m, "value", "") or "") for m in at.markdown]
            texts += [str(getattr(h, "value", "") or "") for h in at.subheader]
            assert any(title in t for t in texts), \
                f"goto: 제목 줄 {title!r} 이 렌더되지 않음"
        return at
    # ── 개편 전 경로 ──
    radios = at.sidebar.radio
    if mk in NAV_ADMIN_LABELS:
        radios[1].set_value(NAV_ADMIN_LABELS[mk])
    else:
        radios[0].set_value(NAV_LABELS[mk][0])
        if len(radios) > 1:
            radios[1].set_value(None)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def nav_menu_labels(at):
    """사이드바 메뉴 이름 (업무 리스트, 관리자 리스트). 로그인 전이면 둘 다 빈 리스트."""
    if _nav_is_new(at):
        flow = [b.label for b in at.sidebar.button
                if str(b.key or "").startswith("nav_m_")
                and str(b.key)[6:] in NAV_LABELS]
        admin = [b.label for b in at.sidebar.button
                 if str(b.key or "").startswith("nav_m_")
                 and str(b.key)[6:] in NAV_ADMIN_LABELS]
        return flow, admin
    radios = at.sidebar.radio
    flow = list(radios[0].options) if len(radios) > 0 else []
    admin = list(radios[1].options) if len(radios) > 1 else []
    return flow, admin


def nav_sub_labels(at, main):
    """선택된 메인의 세부 화면 이름 순서 — 개편 전은 페이지 탭 라벨, 개편 후는 사이드바
    세부 버튼 라벨."""
    mk = _nav_main_key(main)
    if _nav_is_new(at):
        pref = f"nav_s_{mk}_"
        return [b.label for b in at.sidebar.button
                if str(b.key or "").startswith(pref)]
    return [t.label for t in at.tabs]
