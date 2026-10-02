"""
구매 관리 › 발주서 작성 ② — 옛 발주 품명('품번/품명')의 미납 수주 (2026-10-05)

혜성철강 이력은 'HA80-80092/유성 핀', 'D917137/THRUST WASHER' 형식이다.
- 품번이 제품 마스터에 있으면 제품 행으로 이어져 미납 수주가 보여야 한다
- 품명으로는 제품을 못 찾는 이력(DIC 'D917137' ↔ 제품 '4D917137-00')은 이력 행으로
  남되, 그 자재(M###)를 BOM 으로 쓰는 제품의 미납 합계가 보여야 한다
(이전: 둘 다 이력 행으로 떨어지고 미납 수주가 0 고정). DB 는 mock.
"""
import os
import sys
import importlib.util
from urllib.parse import unquote

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("streamlit") is None,
    reason="streamlit 미설치 — AppTest 불가")

APP_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "streamlit_app.py")
VENDOR = {"vendor_id": 189, "name": "혜성철강(주)", "vendor_group": "MAT_CARBON",
          "category": None, "business_no": None, "ceo_name": None,
          "phone": None, "fax": None, "address": None, "email": None,
          "payment_terms": None, "contact_person": None, "in_use": True}
POS = [{"po_id": 7, "po_number": "26-0901", "vendor_id": 189,
        "po_date": "2026-08-20", "delivery_date": "2026-08-27",
        "total_amount": 0, "vat": 0, "status": "RECEIVED",
        "contact_person": None, "payment_terms": None,
        "delivery_address": None, "remark": None}]
ITEMS = [
    {"poi_id": 71, "po_id": 7, "item_name": "HA80-80092/유성 핀",
     "material": "SCM420", "spec": "SCM420H 28*97", "qty": 700,
     "unit_price": 806, "material_id": "M191", "product_id": "P0738",
     "unit": "EA"},
    {"poi_id": 72, "po_id": 7, "item_name": "D917137/THRUST WASHER",
     "material": "SCM420H", "spec": "SCM420H 55*6", "qty": 1000,
     "unit_price": 300, "material_id": "M197", "product_id": None,
     "unit": "EA"},
]
PRODUCT = {"product_id": "P0738", "pn": "HA80-80092",
           "raw_material_name": "SCM420 Ø28*97", "product_size": None,
           "material": "SCM420", "bom_material_name": None,
           "material_unit_price": 806, "archived_at": None}
SO_LINES = [
    {"product_id": "P0738", "so_id": 90, "pending_qty": 300,
     "due_date": "2026-10-30"},
    {"product_id": "P0852", "so_id": 98, "pending_qty": 243,
     "due_date": "2026-10-07"},
]
SOS = [{"so_id": 90, "so_number": "G269920030", "customer": "현대제뉴인(주)",
        "status": "PARTIAL"},
       {"so_id": 98, "so_number": "PO2609000000549",
        "customer": "(주)디아이씨두서공장", "status": "DRAFT"}]


def _fetch(table, select="*", filter_query="", limit=1000):
    fq = unquote(filter_query or "")
    if table == "vendors":
        return [VENDOR]
    if table == "purchase_orders":
        return POS
    if table == "purchase_order_items":
        return [dict(i) for i in ITEMS]
    if table == "products" and "HA80-80092" in fq:
        return [dict(PRODUCT)]
    if table == "bom" and "M197" in fq:
        return [{"product_id": "P0852", "material_id": "M197",
                 "process_type": "MATERIAL"}]
    if table == "sales_order_items" and "pending_qty=gt.0" in fq:
        return [l for l in SO_LINES if l["product_id"] in fq]
    if table == "sales_orders" and "so_id=in." in fq:
        return SOS
    return []


@pytest.fixture()
def hist_db(monkeypatch):
    import db
    monkeypatch.setattr(db, "fetch", _fetch)
    monkeypatch.setattr(db, "fetch_one", lambda *a, **k: None)
    monkeypatch.setattr(db, "insert", lambda t, r: len(r))
    monkeypatch.setattr(db, "update", lambda *a, **k: True)
    monkeypatch.setattr(db, "health_check",
                        lambda: {"status": "OK", "counts": {}})
    monkeypatch.setattr(db, "debug_check", lambda: {"status": "mock"})
    if hasattr(db, "count_rows"):
        monkeypatch.setattr(db, "count_rows", lambda *a, **k: 0)
    if hasattr(db, "rpc"):
        monkeypatch.setattr(db, "rpc", lambda *a, **k: None)
    return db


def test_hist_pn_helper():
    src = open(APP_FILE, encoding="utf-8").read()
    ns = {}
    exec(src[src.index("def po_hist_pn"):src.index("def _proc_basis_label")], ns)
    f = ns["po_hist_pn"]
    assert f("HA80-80092/유성 핀") == "HA80-80092"
    assert f("80AHYBV-TU-05(Ø99.9*12L)") == "80AHYBV-TU-05"
    assert f("12HFDVN-VM-03 (Ø44 * 26.4L)") == "12HFDVN-VM-03"
    assert f("4S50LJF-MP") == "4S50LJF-MP"


def test_old_format_history_shows_pending_orders(hist_db):
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    for _c in (st.cache_data, st.cache_resource):
        try:
            _c.clear()
        except Exception:
            pass
    at = AppTest.from_file(APP_FILE, default_timeout=60)
    at.secrets["supabase"] = {"url": "https://mock.local",
                              "anon_key": "a", "service_role_key": "s"}
    at.secrets["auth"] = {"disabled": True}
    at.run()
    at.sidebar.radio[0].set_value("구매 관리")
    at.sidebar.radio[1].set_value(None)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    [b for b in at.button if b.label == "검색"][0].click().run()
    assert not at.exception, [str(e.value) for e in at.exception]

    frames = [f.value for f in at.dataframe if "미납 수주" in f.value.columns]
    assert frames, "품목 담기 표가 없음"
    df = frames[0]
    rows = {r["품번"]: r for _, r in df.iterrows()}
    # ① 'HA80-80092/유성 핀' → 제품 행으로 이어짐 (이력 행 중복 없음)
    assert "HA80-80092" in rows and "HA80-80092/유성 핀" not in rows
    assert int(rows["HA80-80092"]["미납 수주"]) == 300
    assert rows["HA80-80092"]["최근 납기"] == "2026-10-30"
    # ② 품명으로 제품을 못 찾는 이력 → 자재의 BOM 제품 미납 합계
    h = rows["D917137/THRUST WASHER"]
    assert int(h["미납 수주"]) == 243 and h["최근 납기"] == "2026-10-07"
