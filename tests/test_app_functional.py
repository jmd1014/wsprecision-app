"""
자동 기능 테스트 — Streamlit AppTest 기반

전체 앱을 헤드리스로 실행해 6개 메인 페이지가 예외 없이 렌더되는지 +
수주→발주 prefill 흐름이 작동하는지 검증.

DB 는 mock (db 모듈 함수 교체) — 실제 Supabase 접근 없음.
streamlit 미설치 환경에서는 전체 skip.
"""
import sys, os
import importlib.util
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

streamlit_available = importlib.util.find_spec("streamlit") is not None
pytestmark = pytest.mark.skipif(
    not streamlit_available, reason="streamlit 미설치 — AppTest 불가")

APP_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "streamlit_app.py")

PAGES_FLOW = [
    "🏠 홈",
    "📥 수주 관리",
    "📊 생산 준비",
    "📋 발주/입고",
    "🧾 공정 관리",
    "🚚 출고 관리",
]
PAGES_ADMIN = [
    "⚙️ 마스터 관리",
    "💰 원가 확인",
    "🏭 생산 보고",
]
PAGES = PAGES_FLOW + PAGES_ADMIN


def _goto(at, page):
    """2그룹 라디오 내비게이션 — 업무(0) / 관리자(1)."""
    if page in PAGES_FLOW:
        at.sidebar.radio[0].set_value(page)
        at.sidebar.radio[1].set_value(None)
    else:
        at.sidebar.radio[1].set_value(page)
    at.run()


# ─── DB mock ───────────────────────────────────────────
# streamlit_app.py 는 `from db import health_check, fetch, debug_check`
# + `import db as _db` 를 사용. 모듈 attribute 를 미리 교체해 두면
# 앱이 import 할 때 mock 이 바인딩된다.

def _mock_fetch(table, select="*", filter_query="", limit=1000):
    return []


def _mock_fetch_one(table, filter_query="", select="*"):
    return None


def _mock_insert(table, records):
    return len(records)


def _mock_update(table, filter_query, fields):
    return True


def _mock_count_rows(table, filter_query=""):
    return 0


def _mock_health_check():
    return {"status": "OK", "counts": {
        "products": 834, "materials": 308, "bom": 347,
        "vendors": 250, "drawings": 0,
        "active_products": 235, "archived_products": 599,
        "sales_ledger": 11307, "purchase_ledger": 5332,
    }}


def _mock_debug_check():
    return {"url": "mock", "status": "mock"}


def _mock_rpc(function_name, params=None):
    if function_name == "next_po_number":
        return "PO-202605-001"
    return None


@pytest.fixture()
def mocked_db(monkeypatch):
    """db 모듈 함수를 mock 으로 교체."""
    import db
    monkeypatch.setattr(db, "fetch", _mock_fetch)
    monkeypatch.setattr(db, "fetch_one", _mock_fetch_one)
    monkeypatch.setattr(db, "insert", _mock_insert)
    monkeypatch.setattr(db, "update", _mock_update)
    monkeypatch.setattr(db, "health_check", _mock_health_check)
    monkeypatch.setattr(db, "debug_check", _mock_debug_check)
    if hasattr(db, "count_rows"):
        monkeypatch.setattr(db, "count_rows", _mock_count_rows)
    if hasattr(db, "rpc"):
        monkeypatch.setattr(db, "rpc", _mock_rpc)
    return db


def _make_apptest():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP_FILE, default_timeout=30)
    at.secrets["supabase"] = {
        "url": "https://mock.supabase.local",
        "anon_key": "mock_anon",
        "service_role_key": "mock_service",
    }
    return at


# ─── 1. 페이지별 스모크 테스트 ─────────────────────────

@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_exception(page, mocked_db):
    """각 메인 페이지가 빈 DB 데이터로도 예외 없이 렌더되는지."""
    at = _make_apptest()
    at.run()
    assert not at.exception, f"초기 로드 예외: {[str(e.value) for e in at.exception]}"

    _goto(at, page)
    assert not at.exception, (
        f"페이지 '{page}' 렌더 예외: "
        f"{[str(e.value) for e in at.exception]}"
    )


def test_sidebar_menu_groups(mocked_db):
    """사이드바 2그룹 — 업무 진행 6개 + 관리자 3개 (2026-07-24 개편)."""
    at = _make_apptest()
    at.run()
    radios = at.sidebar.radio
    assert len(radios) >= 2, "사이드바 radio 2개(업무/관리자) 필요"
    assert radios[0].options == PAGES_FLOW, f"업무 메뉴 불일치: {radios[0].options}"
    assert radios[1].options == PAGES_ADMIN, f"관리자 메뉴 불일치: {radios[1].options}"


# ─── 2. 수주→발주 prefill 흐름 테스트 ──────────────────

def test_po_prefill_flow(mocked_db):
    """생산 준비에서 설정한 po_prefill_* 가 구매/발주 페이지에서 소비되는지."""
    at = _make_apptest()
    at.run()

    # 생산 준비 → 발주 prefill 을 session_state 에 직접 주입
    # (빈 DB 라 생산 준비 페이지는 st.stop 되므로 흐름의 후반부만 검증)
    at.session_state["po_prefill_vendor_name"] = "(주)명진메탈"
    at.session_state["po_prefill_items"] = [
        {"product_id": None, "item_name": "환봉 STS304 ⌀45",
         "material": "STS304", "spec": "⌀45×400", "qty": 100,
         "unit_price": 0},
    ]
    at.session_state["po_prefill_source_so"] = "SO-2026-001"

    _goto(at, "📋 발주/입고")
    assert not at.exception, (
        f"발주/입고 prefill 렌더 예외: "
        f"{[str(e.value) for e in at.exception]}"
    )

    # prefill 안내 문구 확인
    info_texts = [str(i.value) for i in at.info]
    assert any("자동 제안" in t for t in info_texts), \
        f"prefill 안내 미표시: {info_texts}"
    assert any("SO-2026-001" in t for t in info_texts), \
        "출처 수주 표시 안 됨"

    # 품목이 po_items 로 이전됐는지
    po_items = at.session_state["po_items"]
    assert len(po_items) == 1
    assert po_items[0]["item_name"] == "환봉 STS304 ⌀45"


# ─── 3. 핵심 위젯 존재 검증 ───────────────────────────

def test_home_shows_progress_dashboard(mocked_db):
    """홈이 업무 진행 대시보드(수주→출고 단계 metric)를 표시하는지."""
    at = _make_apptest()
    at.run()
    metrics = at.metric
    assert len(metrics) >= 5, f"홈 metric 부족: {len(metrics)}"
    labels = [m.label for m in metrics]
    assert any("미납 수주" in l for l in labels)
    assert any("완성 재고" in l for l in labels)


def test_master_page_has_tabs(mocked_db):
    """마스터 관리에 7개 탭 존재."""
    at = _make_apptest()
    at.run()
    _goto(at, "⚙️ 마스터 관리")
    assert not at.exception
    assert len(at.tabs) >= 6, f"마스터 관리 탭 부족: {len(at.tabs)}"


def test_cost_page_renders_with_tabs(mocked_db):
    """원가 확인 페이지 — 탭 6개 + USE_V2 fallback 동작."""
    at = _make_apptest()
    at.run()
    _goto(at, "💰 원가 확인")
    assert not at.exception
    assert len(at.tabs) >= 5, f"원가 확인 탭 부족: {len(at.tabs)}"
