"""
마스터 관리 → 품번별 맞추기 툴 검증

발주 없이 소재를 입고하고 완성재고를 실사로 조정하는 도구가
  · 미납/완성재고/생산중/부족 KPI 를 맞게 계산하는지
  · BOM 소요량(분할 계수 포함)과 부족분을 맞게 내는지
  · 조정 사유 없이는 완성재고를 못 바꾸게 막는지
  · RECEIPT / ADJUSTMENT 원장을 규약대로 쓰는지
를 헤드리스로 확인한다.
"""
import os
import sys
import importlib.util

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

streamlit_available = importlib.util.find_spec("streamlit") is not None
pytestmark = pytest.mark.skipif(
    not streamlit_available, reason="streamlit 미설치 — AppTest 불가")

APP_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "streamlit_app.py")

PRODUCT = {"product_id": 7, "pn": "4PDVN-02", "customer": "㈜엠제이티",
           "unit": "EA"}
# 미납 1,200 · 완성재고 300 · 생산중 200 → 부족 700
LINES = [{"soi_id": 1, "so_id": 100, "pending_qty": 800, "due_date": None},
         {"soi_id": 2, "so_id": 101, "pending_qty": 400, "due_date": None},
         {"soi_id": 3, "so_id": 102, "pending_qty": 500, "due_date": None}]
CANCELLED_SO = 102          # 취소 수주 → 미납에서 빠져야 한다
LOTS = [{"lot_number": "20260720-001", "produced_qty": 500,
         "adjust_qty": 0, "issued_qty": 200, "remain_qty": 300,
         "first_output_date": "2026-07-20", "material_lot": "W0901"}]
BOM = [{"bom_id": 11, "material_id": "M110", "raw_material_name": "S304 Ø22*14",
        "qty_per_pc": 1, "shared_factor": 1, "process_type": "선삭"},
       {"bom_id": 12, "material_id": "M117", "raw_material_name": "S304 Ø45*16",
        "qty_per_pc": 1, "shared_factor": 2, "process_type": None}]
MSTOCK = {"M110": {"material_id": "M110", "raw_name": "S304 Ø22*14",
                   "material_type": "SUS304", "spec": "φ22*14L", "unit": "EA",
                   "current_stock": 100, "main_supplier": "(주)명진메탈"},
          "M117": {"material_id": "M117", "raw_name": "S304 Ø45*16",
                   "material_type": "SUS304", "spec": "φ45*16L", "unit": "EA",
                   "current_stock": 4020, "main_supplier": "(주)명진메탈"}}

INSERTED = []


def _fetch(table, select="*", filter_query="", limit=1000):
    if table == "products":
        return [PRODUCT]
    if table == "sales_order_items":
        return list(LINES)
    if table == "sales_orders":
        return [{"so_id": l["so_id"],
                 "status": ("CANCELLED" if l["so_id"] == CANCELLED_SO
                            else "CONFIRMED")} for l in LINES]
    if table == "product_lot_stock_v":
        return list(LOTS)
    if table == "wo_tracking":
        return [{"wo_number": "20260728-001", "input_qty": 500,
                 "output_qty": 300, "status": "IN_PROD"}]
    if table == "bom":
        return [dict(b) for b in BOM]
    if table == "material_stock":
        return list(MSTOCK.values())
    if table == "materials":
        return [dict(m, procurement_type="도급", archived_at=None,
                     stock_qty=m["current_stock"]) for m in MSTOCK.values()]
    return []


def _fetch_one(table, filter_query="", select="*"):
    if table == "product_stock_v":
        return {"current_stock": 300}
    return None


@pytest.fixture()
def fit_db(monkeypatch):
    import db
    INSERTED.clear()
    monkeypatch.setattr(db, "fetch", _fetch)
    monkeypatch.setattr(db, "fetch_one", _fetch_one)
    monkeypatch.setattr(db, "insert",
                        lambda t, r: (INSERTED.append((t, r)), len(r))[1])
    monkeypatch.setattr(db, "update", lambda t, f, v: True)
    monkeypatch.setattr(db, "delete", lambda t, f: 1)
    monkeypatch.setattr(db, "health_check",
                        lambda: {"status": "OK", "counts": {}})
    monkeypatch.setattr(db, "debug_check", lambda: {"status": "mock"})
    if hasattr(db, "count_rows"):
        monkeypatch.setattr(db, "count_rows", lambda t, f="": 0)
    return db


def _open_master(fit_db):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP_FILE, default_timeout=60)
    at.secrets["supabase"] = {"url": "https://mock.local",
                              "anon_key": "a", "service_role_key": "s"}
    at.secrets["auth"] = {"disabled": True}
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    at.sidebar.radio[1].set_value("마스터 관리")
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def _kpi(at):
    return next((m.value for m in at.markdown
                 if 'class="kpi-row"' in m.value and "미납 수주" in m.value),
                None)


# ─── 1. 현황 집계 ──────────────────────────────────────

def test_kpi_excludes_cancelled_and_computes_shortfall(fit_db):
    """미납 1,200(취소 500 제외) · 완성 300 · 생산중 200 → 부족 700"""
    kpi = _kpi(_open_master(fit_db))
    assert kpi, "품번별 맞추기 KPI 카드가 없음"
    assert ">1,200<" in kpi, kpi          # 미납 (취소 수주 제외)
    assert ">300<" in kpi                 # 완성 재고
    assert ">200<" in kpi                 # 생산중 (투입 500 − 완성 300)
    assert ">700<" in kpi                 # 부족
    assert "2개 라인" in kpi              # 취소 라인은 세지 않는다


def test_bom_shared_factor_halves_requirement(fit_db):
    """분할 계수 2 → 1개당 0.5 · 필요량 600 · 재고 4,020 → 부족 0"""
    at = _open_master(fit_db)
    df = next((d.value for d in at.dataframe
               if hasattr(d.value, "columns") and "1개당" in d.value.columns),
              None)
    assert df is not None, "BOM 표가 없음"
    row = df[df["자재"] == "S304 Ø45*16"].iloc[0]
    assert round(float(row["1개당"]), 3) == 0.5
    assert float(row["필요량"]) == 600      # 1,200 × 0.5
    assert float(row["부족"]) == 0          # 재고 4,020 으로 충분
    row2 = df[df["자재"] == "S304 Ø22*14"].iloc[0]
    assert float(row2["필요량"]) == 1200
    assert float(row2["부족"]) == 1100      # 1,200 − 100


# ─── 2. 완성재고 조정 가드 ─────────────────────────────

def test_adjust_requires_reason(fit_db):
    """사유 없이 조정하면 원장에 아무것도 안 남고 오류를 띄운다"""
    at = _open_master(fit_db)
    real = next(n for n in at.number_input if n.key == "ft_real")
    real.set_value(350.0)          # 장부 300 → 실사 350, 차이 +50
    at.run()
    btn = next(b for b in at.button if b.key == "ft_adj_go")
    btn.click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert not [t for t, _ in INSERTED if t == "inventory_transactions"]
    assert any("조정 사유" in e.value for e in at.error)


def test_adjust_writes_adjustment_with_lot(fit_db):
    """사유가 있으면 차이만큼 ADJUSTMENT — 증가분에는 LOT 을 붙인다"""
    at = _open_master(fit_db)
    next(n for n in at.number_input if n.key == "ft_real").set_value(350.0)
    at.run()
    next(t for t in at.text_input if t.key == "ft_amemo").set_value("8/1 실사")
    at.run()
    next(b for b in at.button if b.key == "ft_adj_go").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    rows = [r for t, recs in INSERTED if t == "inventory_transactions"
            for r in recs]
    assert len(rows) == 1, rows
    r = rows[0]
    assert r["txn_type"] == "ADJUSTMENT"
    assert r["qty"] == 50
    assert r["product_id"] == 7 and r["material_id"] is None
    assert str(r["lot_number"]).startswith("ADJ-")
    assert "8/1 실사" in r["remark"]


def test_adjust_decrease_has_no_lot(fit_db):
    """감소 조정은 특정 LOT 을 특정할 수 없으므로 LOT 없이 기록"""
    at = _open_master(fit_db)
    next(n for n in at.number_input if n.key == "ft_real").set_value(250.0)
    at.run()
    next(t for t in at.text_input if t.key == "ft_amemo").set_value("파손 폐기")
    at.run()
    next(b for b in at.button if b.key == "ft_adj_go").click()
    at.run()
    rows = [r for t, recs in INSERTED if t == "inventory_transactions"
            for r in recs]
    assert rows[0]["qty"] == -50
    assert rows[0]["lot_number"] is None


# ─── 3. 발주 없는 소재 입고 ────────────────────────────

def test_direct_receipt_writes_receipt_txn(fit_db):
    at = _open_master(fit_db)
    next(n for n in at.number_input if n.key == "ft_rqty").set_value(500.0)
    at.run()
    next(b for b in at.button if b.key == "ft_rcv_go").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    rows = [r for t, recs in INSERTED if t == "inventory_transactions"
            for r in recs]
    assert len(rows) == 1
    r = rows[0]
    assert r["txn_type"] == "RECEIPT" and r["qty"] == 500
    assert r["material_id"] == "M110"
    assert r.get("product_id") is None      # 소재 입고에는 제품을 달지 않는다
    assert "발주 없이 직접 입고" in r["remark"] and "4PDVN-02" in r["remark"]


def test_receipt_button_disabled_at_zero(fit_db):
    at = _open_master(fit_db)
    assert next(b for b in at.button if b.key == "ft_rcv_go").disabled
