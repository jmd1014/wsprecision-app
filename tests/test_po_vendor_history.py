"""
발주/입고 › ② 품목 담기 — 마스터에 없는 거래처 이력 품목 검색 (2026-09-22)

삼경O&T 처럼 발주 이력이 전부 직접 입력 품목(습동유·절삭유·유압작동유)인
거래처는 "이 거래처 이력만" 검색이 제품 마스터에서만 찾아 항상 비었다.
이력 품목을 '직접 입력 이력' 행으로 띄워 다시 담을 수 있어야 한다.

DB 는 mock — 실제 Supabase 접근 없음.
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

VENDOR = {"vendor_id": 205, "name": "삼경O&T", "vendor_group": "MAT_CONSUMABLES",
          "category": None, "business_no": None, "ceo_name": None,
          "phone": None, "fax": None, "address": None, "email": None,
          "payment_terms": None, "contact_person": None, "in_use": True}
def _po(po_id, no, date):
    # 발주 이력 탭이 같은 mock 을 읽으므로 그 탭이 쓰는 필드까지 채운다
    return {"po_id": po_id, "po_number": no, "vendor_id": 205, "po_date": date,
            "delivery_date": date, "total_amount": 0, "vat": 0, "status": "SENT",
            "contact_person": None, "payment_terms": None,
            "delivery_address": None, "remark": None}


POS = [_po(2, "26-0904", "2026-08-24"), _po(1, "26-0805", "2026-07-30")]
# 습동유는 자재 마스터(C001)에 연결된 이력, 나머지는 아직 미연결 직접 입력
ITEMS = [
    {"poi_id": 11, "po_id": 2, "item_name": "습동유", "material": None,
     "spec": "20L", "qty": 3, "unit_price": 0, "material_id": "C001"},
    {"poi_id": 12, "po_id": 2, "item_name": "절삭유", "material": None,
     "spec": None, "qty": 3, "unit_price": 0, "material_id": None},
    {"poi_id": 13, "po_id": 2, "item_name": "유압작동유", "material": None,
     "spec": None, "qty": 2, "unit_price": 0, "material_id": None},
    {"poi_id": 1, "po_id": 1, "item_name": "습동유", "material": None,
     "spec": None, "qty": 5, "unit_price": 0, "material_id": "C001"},
    {"poi_id": 2, "po_id": 1, "item_name": "절삭유", "material": None,
     "spec": None, "qty": 10, "unit_price": 0, "material_id": None},
]
# 자재 마스터의 비생산 자재(C###) — 검색어 '절삭' 에만 걸리는 절삭유 한 건
MATERIALS_C = [{"material_id": "C002", "raw_name": "절삭유",
                "material_type": "소모품", "spec": "20L",
                "main_supplier": "삼경O&T"}]


def _mock_fetch(table, select="*", filter_query="", limit=1000):
    if table == "vendors":
        return [VENDOR]
    if table == "purchase_orders":
        return POS
    if table == "purchase_order_items":
        return ITEMS
    if table == "materials" and "like.C" in filter_query:
        from urllib.parse import unquote   # 필터 값은 URL 인코딩되어 온다
        if "절삭" in unquote(filter_query):
            return MATERIALS_C
        return []
    return []   # products 등 — 마스터에는 아무것도 없음


@pytest.fixture()
def mocked_db(monkeypatch):
    import db
    monkeypatch.setattr(db, "fetch", _mock_fetch)
    monkeypatch.setattr(db, "fetch_one", lambda *a, **k: None)
    monkeypatch.setattr(db, "insert", lambda t, r: len(r))
    monkeypatch.setattr(db, "update", lambda *a, **k: True)
    monkeypatch.setattr(db, "health_check", lambda: {"status": "OK", "counts": {}})
    monkeypatch.setattr(db, "debug_check", lambda: {"url": "mock", "status": "mock"})
    if hasattr(db, "count_rows"):
        monkeypatch.setattr(db, "count_rows", lambda *a, **k: 0)
    if hasattr(db, "rpc"):
        monkeypatch.setattr(db, "rpc", lambda *a, **k: None)
    return db


def _open_po_page():
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    # 앞선 테스트의 빈 mock 결과가 st.cache_data 에 남아 거래처 목록이
    # 비는 순서 의존 실패 방지 (전체 스위트에서만 재현, 2026-09-22)
    for _c in (st.cache_data, st.cache_resource):
        try:
            _c.clear()
        except Exception:
            pass
    at = AppTest.from_file(APP_FILE, default_timeout=30)
    at.secrets["supabase"] = {"url": "https://mock.supabase.local",
                              "anon_key": "mock_anon",
                              "service_role_key": "mock_service"}
    at.secrets["auth"] = {"disabled": True}
    at.run()
    at.sidebar.radio[0].set_value("발주/입고")
    at.sidebar.radio[1].set_value(None)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def _grid_texts(at):
    """검색 결과 표(data_editor)의 셀 텍스트 — AppTest 는 data_editor 를
    `at.dataframe` 로 노출한다 (2026-09-22 확인)."""
    out = []
    for f in at.dataframe:
        try:
            out.append(f.value.to_string())
        except Exception:
            pass
    return "\n".join(out)


def test_adhoc_history_listed_without_query(mocked_db):
    """검색어 없이 [검색] → 이력 3종이 '직접 입력 이력' 행으로 나온다."""
    at = _open_po_page()
    cb = [c for c in at.checkbox if str(c.key).startswith("po_vh_only")]
    assert cb and cb[0].value is True, "이력 3종이 있으니 체크가 기본 켜져야 함"
    assert "3종" in cb[0].label

    search = [b for b in at.button if b.label == "검색"]
    assert search, "검색 버튼 없음"
    search[0].click().run()
    assert not at.exception, [str(e.value) for e in at.exception]

    assert not any("일치하는 품목 없음" in i.value for i in at.info), \
        "이력 품목이 있는데 '없음' 안내가 나옴"
    assert any(b.label == "체크한 품목 담기" for b in at.button), \
        "결과 표(담기 폼)가 렌더되지 않음"
    txt = _grid_texts(at)
    assert txt, "결과 표 값이 노출되지 않음 (at.dataframe)"
    for nm in ("습동유", "절삭유", "유압작동유"):
        assert nm in txt, f"{nm} 이력 행 누락"
    assert "자재 이력" in txt, "자재에 연결된 이력(습동유 C001)은 '자재 이력'"
    assert "직접 입력 이력" in txt, "미연결 이력은 '직접 입력 이력'"
    assert "26-0904" in txt, "최근 발주가 최신(26-0904) 이어야 함"


def test_query_finds_master_material_and_dedups_history(mocked_db):
    """검색어 '절삭' → 자재 마스터의 절삭유(C002, 소모품) 한 줄. 같은 이름의
    이력 행은 중복으로 띄우지 않고, 습동유는 검색어와 안 맞아 제외."""
    at = _open_po_page()
    q = [t for t in at.text_input if t.key == "po_q"]
    assert q
    q[0].set_value("절삭")
    [b for b in at.button if b.label == "검색"][0].click().run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert not any("일치하는 품목 없음" in i.value for i in at.info)
    assert any(b.label == "체크한 품목 담기" for b in at.button)
    txt = _grid_texts(at)
    assert txt
    assert "절삭유" in txt and "습동유" not in txt
    assert "자재 · 소모품" in txt, "자재 마스터 행은 '자재 · 소모품' 구분"
    assert txt.count("절삭유") == 1, "마스터 행과 이력 행이 중복되면 안 됨"


def test_query_with_no_match_still_says_none(mocked_db):
    """이력에도 마스터에도 없는 검색어는 기존대로 '없음' 안내."""
    at = _open_po_page()
    [t for t in at.text_input if t.key == "po_q"][0].set_value("ZZZZ")
    [b for b in at.button if b.label == "검색"][0].click().run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert any("일치하는 품목 없음" in i.value for i in at.info)
    assert not any(b.label == "체크한 품목 담기" for b in at.button)
