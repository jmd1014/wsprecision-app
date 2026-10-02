"""
마스터 관리 › BOM 편집 — 공정행 단가 기준 KG (2026-10-02)

열처리는 KG당 단가로 청구된다 (예: KG당 1,000원 × 개당 0.35kg = 350원).
공정행 추가 폼에서 단가 기준 = KG 를 고르면 '개당 중량 (KG)'·'KG 단가' 입력으로
바뀌고, 저장은 기존 계산식(단가 × qty/PC ÷ LOT 처리수량)에 맞게
qty_per_pc = 중량, shared_factor = 1, lot_label = KG 로 들어간다. DB 는 mock.
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
INSERTED = []
PRODUCT = {"product_id": "P0738", "pn": "HA80-80092", "item_name": "유성 핀",
           "customer": "현대제뉴인(주)", "sub_class": "HDX부품"}
BOM_ROWS = [
    {"bom_id": 150, "product_id": "P0738", "material_id": "M191",
     "raw_material_name": "SCM420 Ø28*97", "qty_per_pc": 1.0,
     "shared_factor": 1, "process_type": "MATERIAL", "unit_price": None,
     "lot_label": None, "process_vendor_id": None,
     "verification_status": "확인완료", "source": "MES"},
    {"bom_id": 900, "product_id": "P0738", "material_id": None,
     "raw_material_name": "침탄 열처리", "qty_per_pc": 0.35,
     "shared_factor": 1, "process_type": "HEAT", "unit_price": 1000,
     "lot_label": "KG", "process_vendor_id": 116,
     "verification_status": "확인완료", "source": "MANUAL"},
]


def _fetch(table, select="*", filter_query="", limit=1000):
    fq = unquote(filter_query or "")
    if table == "products" and "80092" in fq:
        return [dict(PRODUCT)]
    if table == "bom" and "P0738" in fq:
        return [dict(b) for b in BOM_ROWS]
    if table == "vendors":
        return [{"vendor_id": 116, "name": "위드열처리",
                 "vendor_group": "HEAT_TREAT", "in_use": True}]
    return []


@pytest.fixture()
def bom_db(monkeypatch):
    import db
    INSERTED.clear()
    monkeypatch.setattr(db, "fetch", _fetch)
    monkeypatch.setattr(db, "fetch_one", lambda *a, **k: None)
    monkeypatch.setattr(db, "insert",
                        lambda t, r: (INSERTED.append((t, r)), len(r))[1])
    monkeypatch.setattr(db, "update", lambda *a, **k: True)
    monkeypatch.setattr(db, "health_check",
                        lambda: {"status": "OK", "counts": {}})
    monkeypatch.setattr(db, "debug_check", lambda: {"status": "mock"})
    if hasattr(db, "count_rows"):
        monkeypatch.setattr(db, "count_rows", lambda *a, **k: 0)
    if hasattr(db, "rpc"):
        monkeypatch.setattr(db, "rpc", lambda *a, **k: None)
    return db


def _open_bom(q="80092"):
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
    at.sidebar.radio[1].set_value("마스터 관리")
    at.run()
    [t for t in at.text_input if t.key == "bom_pq"][0].set_value(q)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def test_basis_label_helper():
    src = open(APP_FILE, encoding="utf-8").read()
    i = src.index("def _proc_basis_label")
    ns = {}
    exec(src[i:src.index("WO_NUMBER_RE = ")], ns)
    f = ns["_proc_basis_label"]
    assert f("") == "개당 (EA)" and f("KG") == "KG당 (중량)"
    assert f("CH") == "CH당" and f("LOT") == "LOT당"


def test_add_process_row_with_kg_basis(bom_db):
    at = _open_bom()
    [r for r in at.radio if r.key == "bom_add_kind"][0].set_value("공정행")
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    basis = [s for s in at.selectbox if s.key == "bom_proc_label"][0]
    assert "KG당 (중량)" in basis.options     # AppTest 는 표시 라벨을 노출
    # 기본(개당)은 qty/PC · LOT 처리수량
    keys = {n.key for n in at.number_input}
    assert "bom_proc_qty" in keys and "bom_proc_lot" in keys

    basis.set_value("KG")
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    nums = {n.key: n for n in at.number_input}
    assert "bom_proc_qty_kg" in nums and "bom_proc_price_kg" in nums
    assert nums["bom_proc_qty_kg"].label == "개당 중량 (KG)"
    assert nums["bom_proc_price_kg"].label == "KG 단가 (원)"
    assert "bom_proc_lot" not in nums, "KG 기준에는 LOT 처리수량 입력이 없어야 함"

    [t for t in at.text_input if t.key == "bom_proc_name"][0] \
        .set_value("침탄 열처리")
    nums["bom_proc_qty_kg"].set_value(0.35)
    nums["bom_proc_price_kg"].set_value(1000.0)
    at.run()
    assert any("개당 공정비 **350원**" in str(c.value) for c in at.caption)

    [b for b in at.button if b.key == "bom_proc_btn"][0].click().run()
    assert not at.exception, [str(e.value) for e in at.exception]
    rec = next(r for t, rows in INSERTED if t == "bom" for r in rows)
    assert rec["raw_material_name"] == "침탄 열처리"
    assert rec["lot_label"] == "KG" and rec["shared_factor"] == 1
    assert abs(rec["qty_per_pc"] - 0.35) < 1e-9 and rec["unit_price"] == 1000
    # 기존 계산식 그대로 350원
    assert abs(rec["unit_price"] * rec["qty_per_pc"] / rec["shared_factor"]
               - 350) < 1e-6
