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
    # 옛 품번(휴면 쌍둥이) 이력 — 활성 제품 4D917140-00 의 별칭
    {"poi_id": 73, "po_id": 7, "item_name": "D917140/THRUST WASHER",
     "material": "SCM420H", "spec": "SCM420H 55*5", "qty": 1000,
     "unit_price": 280, "material_id": "M196", "product_id": None,
     "unit": "EA"},
]
TWIN = {"product_id": "P0854", "pn": "4D917140-00",
        "raw_material_name": "SCM420H Ø55*5", "product_size": None,
        "material": "SCM420H", "bom_material_name": None,
        "material_unit_price": 280, "archived_at": None,
        "alias_list": "D917140"}
PRODUCT = {"product_id": "P0738", "pn": "HA80-80092",
           "raw_material_name": "SCM420 Ø28*97", "product_size": None,
           "material": "SCM420", "bom_material_name": None,
           "material_unit_price": 806, "archived_at": None}
SO_LINES = [
    {"product_id": "P0738", "so_id": 90, "pending_qty": 300,
     "due_date": "2026-10-30"},
    {"product_id": "P0852", "so_id": 98, "pending_qty": 243,
     "due_date": "2026-10-07"},
    {"product_id": "P0854", "so_id": 98, "pending_qty": 1000,
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
    if table == "products" and "alias_list=not.is.null" in fq:
        return [{"pn": TWIN["pn"], "alias_list": TWIN["alias_list"]}]
    if table == "products" and "pn=in." in fq and "archived_at=is.null" in fq:
        return [dict(x) for x in (PRODUCT, TWIN) if f'"{x["pn"]}"' in fq]
    if table == "products" and "pn=in." in fq:
        # 휴면 여부 확인 조회 — 옛 품번 D917140 은 휴면 제품으로 존재
        out = [{"pn": x["pn"], "archived_at": None}
               for x in (PRODUCT, TWIN) if f'"{x["pn"]}"' in fq]
        if '"D917140"' in fq:
            out.append({"pn": "D917140", "archived_at": "2026-05-07"})
        return out
    if table == "bom" and "material_id=in." in fq and "M197" in fq:
        return [{"product_id": "P0852", "material_id": "M197",
                 "process_type": "MATERIAL", "qty_per_pc": 1,
                 "shared_factor": 1}]
    if table == "bom" and "product_id=in." in fq:
        # 유성핀은 1:1, 4D917140-00 은 봉재 1개에서 53개가 나온다고 가정
        return [b for b in (
            {"product_id": "P0738", "material_id": "M191",
             "raw_material_name": "SCM420 Ø28*97", "process_type": "MATERIAL",
             "qty_per_pc": 1, "shared_factor": 1},
            {"product_id": "P0854", "material_id": "M196",
             "raw_material_name": "SCM420H Ø55*5", "process_type": "MATERIAL",
             "qty_per_pc": 1, "shared_factor": 53}) if b["product_id"] in fq]
    if table == "wo_batches" and "status=eq.OPEN" in fq:
        # 유성핀 100개가 공정 중(재공) — 발주 필요에서 빠져야 한다
        return [{"product_id": "P0738", "qty": 100, "step_code": "PROD",
                 "status": "OPEN"}] if "P0738" in fq else []
    if table == "sales_order_items" and "pending_qty=gt.0" in fq:
        if "product_id=not.is.null" in fq:       # 발주 필요량 계산(전체)
            return [dict(l, soi_id=i, due_date=l["due_date"])
                    for i, l in enumerate(SO_LINES, 1)]
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
    assert rows["HA80-80092"]["다음 납기"] == "2026-10-30"
    # ② 품명으로 제품을 못 찾는 이력 → 자재의 BOM 제품 미납 합계
    h = rows["D917137/THRUST WASHER"]
    assert int(h["미납 수주"]) == 243 and h["다음 납기"] == "2026-10-07"
    # ③ 옛 품번(휴면 쌍둥이) 이력 → 별칭을 가진 활성 제품 행, 휴면 경고 없음
    assert "4D917140-00" in rows and "D917140/THRUST WASHER" not in rows
    assert int(rows["4D917140-00"]["미납 수주"]) == 1000
    assert not any("휴면 제품" in str(w.value) for w in at.warning)
    # ⑤ 발주 필요 = 미납 − 재공 (완성·소재 재고·미입고 발주는 0) — 유성핀 300 − 100
    assert int(rows["HA80-80092"]["발주 필요"]) == 200
    # 봉재(1개 → 53개): 미납 1,000 → 소재 19개
    assert int(rows["4D917140-00"]["발주 필요"]) == 19
    # ⑥ 발주 필요 근거 — 표 아래 접힌 표 (유성핀: 미납 300 · 재공 100 → 순 200)
    ex = [e for e in at.expander if "발주 필요 근거" in (e.label or "")]
    assert ex, "발주 필요 근거 접힘 표가 없음"
    md = " ".join(str(m.value) for m in ex[0].markdown)
    assert "HA80-80092" in md and "300" in md and "100" in md and "200" in md



def test_default_order_qty_is_pending_converted_to_material():
    """담을 때 기본 수량 = 미납 수주를 소재 수량으로 환산 (2026-10-05 사용자 요청).
    봉재 1개에서 53개가 나오면 미납 1,000 → 소재 19개(올림)."""
    src = open(APP_FILE, encoding="utf-8").read()
    ns = {}
    exec(src[src.index("def po_mat_factor"):src.index("def _proc_basis_label")], ns)
    fac, need = ns["po_mat_factor"], ns["po_need_qty"]
    assert fac({"qty_per_pc": 1, "shared_factor": 1}) == 1
    assert abs(fac({"qty_per_pc": 1, "shared_factor": 53}) - 1 / 53) < 1e-12
    assert fac({"qty_per_pc": None, "shared_factor": None}) == 1
    assert need([(300, 1)]) == 300
    assert need([(1000, 1 / 53)]) == 19
    assert need([(2000, 1 / 53)]) == 38
    assert need([(243, 1), (1000, 1)]) == 1243      # 같은 소재를 쓰는 제품 합산
    assert need([(0, 1)]) == 0 and need([]) == 0    # 미납 없으면 0 → 최근 수량 사용