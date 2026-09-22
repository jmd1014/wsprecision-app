"""
마스터 관리 › 거래처 편집 — 상세 편집에 신규 등록과 같은 항목 전부 (2026-09-22)

사업자번호·팩스·이메일·담당자·업태·종목·메모·약칭·거래 구분이 상세 편집에 없고,
일괄 편집 표에서는 잠겨 있어 채울 수 없던 문제. DB 는 mock.
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

VENDOR = {"vendor_id": 205, "name": "삼경O&T", "short_name": None,
          "vendor_group": "MAT_CONSUMABLES", "category": None, "trade_type": "매입",
          "business_no": None, "ceo_name": None, "phone": None, "fax": None,
          "email": None, "contact_person": None, "contact_phone": None,
          "address": None, "business_type": None, "business_item": None,
          "payment_terms": "말일 마감 60일 현금", "memo": None, "in_use": True}
UPDATES = []


def _mock_fetch(table, select="*", filter_query="", limit=1000):
    if table == "vendors":
        if "normalized_name=eq." in filter_query:
            return []          # 이름 중복 없음
        return [dict(VENDOR)]
    return []


def _mock_update(table, filter_query, fields):
    UPDATES.append((table, filter_query, dict(fields)))
    return True


@pytest.fixture()
def mocked_db(monkeypatch):
    import db
    monkeypatch.setattr(db, "fetch", _mock_fetch)
    monkeypatch.setattr(db, "fetch_one", lambda *a, **k: None)
    monkeypatch.setattr(db, "insert", lambda t, r: len(r))
    monkeypatch.setattr(db, "update", _mock_update)
    monkeypatch.setattr(db, "health_check", lambda: {"status": "OK", "counts": {}})
    monkeypatch.setattr(db, "debug_check", lambda: {"url": "mock", "status": "mock"})
    if hasattr(db, "count_rows"):
        monkeypatch.setattr(db, "count_rows", lambda *a, **k: 0)
    if hasattr(db, "rpc"):
        monkeypatch.setattr(db, "rpc", lambda *a, **k: None)
    UPDATES.clear()
    return db


def _open_master():
    import streamlit as st
    from streamlit.testing.v1 import AppTest
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
    at.sidebar.radio[1].set_value("마스터 관리")
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def test_detail_form_has_all_registration_fields(mocked_db):
    at = _open_master()
    keys = {t.key for t in at.text_input}
    for k in ("nm", "sn", "biz", "ceo", "ph", "fx", "em", "cp", "cph", "ad",
              "bt", "bi", "pay", "mm"):
        assert f"vd_{k}_205" in keys, f"상세 편집에 {k} 입력 없음"
    sel = {s.key: s for s in at.selectbox}
    assert "vd_grp_205" in sel and "vd_tt_205" in sel
    assert sel["vd_tt_205"].options == ["매입", "매출", "혼합"]


def test_detail_save_writes_new_fields(mocked_db):
    at = _open_master()
    ti = {t.key: t for t in at.text_input}
    ti["vd_biz_205"].set_value("606-37-55556")
    ti["vd_em_205"].set_value("order@samkyung.co.kr")
    ti["vd_bt_205"].set_value("도소매")
    ti["vd_bi_205"].set_value("절삭유")
    [b for b in at.button if b.label == "변경 저장"][0].click().run()
    assert not at.exception, [str(e.value) for e in at.exception]
    ups = [u for u in UPDATES if u[0] == "vendors" and "vendor_id=eq.205" in u[1]]
    assert ups, f"vendors 업데이트 호출 없음: {UPDATES}"
    f = ups[-1][2]
    assert f.get("business_no") == "606-37-55556"
    assert f.get("email") == "order@samkyung.co.kr"
    assert f.get("business_type") == "도소매" and f.get("business_item") == "절삭유"
    assert "name" not in f, "이름을 안 바꿨는데 name 이 업데이트에 들어감"
