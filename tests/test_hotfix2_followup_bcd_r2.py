"""핫픽스 2 후속 B·C·D r2(2026-10-28) — Codex BCD r1 H1~H4·M1·M2·REQUIRED.

① 뷰 키: 구조적 유일 키가 없는 뷰(data_quality_v·product_lot_stock_v)는 dedupe=False 로 같은 키 행을 모두 남기고,
  product_material_price_status_v 는 bom_id 로 — 같은 (product_id, material_id) 두 행도 보존.
② helper 경로 쓰기 0건: 설비 스케줄 조회 절단(T-H2), 생산 시트 ② 표준 조회 절단(T-H3a), 표준 재산출 설비
  매트릭스 조회 절단(T-H3b), 장부 동기화 ② 제품 조회 절단(T-H4, 대조 포함).
③ tuple pk 캐시 hit/miss·일부 NULL 키 보존·정확히 20,000/20,001행 경계.
"""
import importlib.util
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import db  # noqa: E402
from tests.test_db_fetch_all import Raw  # noqa: E402

streamlit_available = importlib.util.find_spec("streamlit") is not None
app_only = pytest.mark.skipif(not streamlit_available, reason="streamlit 미설치 — AppTest 불가")


@pytest.fixture()
def raw(monkeypatch):
    def _install(rows, **kw):
        r = Raw(rows, **kw)
        monkeypatch.setattr(db, "_fetch_raw", r)
        db.clear_cache()
        return r
    return _install


# ── ① 뷰 키 ──────────────────────────────────────────────────

def test_view_keys_registry():
    assert "data_quality_v" not in db.PK_OF and "product_lot_stock_v" not in db.PK_OF
    assert db.PK_OF["product_material_price_status_v"] == "bom_id"
    assert db.PK_OF["material_stock_by_lot"] == ("lot_number", "material_id")


def test_data_quality_rows_with_same_code_ref_are_all_kept(raw):
    """FUTURE_ROUND 처럼 회차마다 한 행인데 ref(pn·so_number)가 같은 진단 — 둘 다 남는다."""
    raw([{"code": "FUTURE_ROUND", "ref": "PN1 / PO-1", "detail": "회차 1", "check_name": "x"},
         {"code": "FUTURE_ROUND", "ref": "PN1 / PO-1", "detail": "회차 2", "check_name": "x"}])
    rows, tr = db.fetch_all("data_quality_v", "*", "", order="code,ref,detail",
                            pk=("code", "ref", "detail"), dedupe=False)
    assert not tr and [r["detail"] for r in rows] == ["회차 1", "회차 2"]


def test_dedupe_false_keeps_identical_keys(raw):
    raw([{"a": 1, "v": i} for i in range(3)])
    rows, _ = db.fetch_all("no_view", "v", "", pk=("a",), dedupe=False)
    assert len(rows) == 3
    rows2, _ = db.fetch_all("no_view", "v", "", pk=("a",))           # 대조: 기본은 키로 제거
    assert len(rows2) == 1


def test_price_status_same_product_material_two_bom_rows_kept(raw):
    raw([{"bom_id": 10, "product_id": "P1", "material_id": "M1", "price_source": "LEGACY"},
         {"bom_id": 11, "product_id": "P1", "material_id": "M1", "price_source": "NONE"}])
    rows, tr = db.fetch_all("product_material_price_status_v", "product_id,material_id,price_source",
                            "archived_at=is.null")
    assert not tr and sorted(r["bom_id"] for r in rows) == [10, 11]


# ── ③ tuple pk 캐시·NULL·경계 ─────────────────────────────────────

def test_tuple_pk_cache_hit_and_miss(raw):
    r = raw([{"x": i // 2, "y": i % 2, "v": i} for i in range(20)])
    db.fetch_all("no_view", "v", "", pk=("x", "y"))
    n = len(r.calls)
    db.fetch_all("no_view", "v", "", pk=("x", "y"))
    assert len(r.calls) == n                                            # 같은 인자 → 적중
    db.fetch_all("no_view", "v", "", pk=("y", "x"))
    assert len(r.calls) > n                                             # pk 순서가 다르면 다른 키


def test_tuple_pk_partial_null_rows_kept(raw):
    raw([{"lot_number": "W1", "material_id": None, "lot_balance": 1},
         {"lot_number": "W1", "material_id": "M1", "lot_balance": 2},
         {"lot_number": "W2", "material_id": None, "lot_balance": 3}])
    rows, _ = db.fetch_all("material_stock_by_lot", "lot_balance", "")
    assert sorted(r["lot_balance"] for r in rows) == [1, 2, 3]


@pytest.mark.parametrize("n,want_tr", [(20000, False), (20001, True)])
def test_tuple_pk_exact_max_rows_boundary(raw, n, want_tr):
    raw([{"lot_number": f"W{i:06d}", "material_id": "M1", "lot_balance": 1} for i in range(n)])
    rows, tr = db.fetch_all("material_stock_by_lot", "lot_balance", "")
    assert tr is want_tr and len(rows) == 20000


# ── ② helper 경로 쓰기 0건 ─────────────────────────────────────────

def _allow(m, *tables):
    from tests import so_mock as _sm
    for t in tables:
        m.tables.setdefault(t, [])
    allowed = set(_sm.WRITABLE) | set(tables)

    def _guard(op, table):
        if table not in allowed:
            raise AssertionError(f"허용되지 않은 쓰기 ({op} {table})")
    m._assert_dash = _guard


@app_only
def test_h2_schedule_truncated_blocks_saves(monkeypatch):
    from datetime import timedelta
    from tests.test_hotfix2_fetch_all_sites import TODAY, _mock, _open
    from tests.test_hotfix2_followup_a import _force_truncated
    m = _mock(target_due=(TODAY + timedelta(days=14)).isoformat(), filler=5)
    _allow(m, "production_schedule")
    m.tables["production_schedule"] = [{"sched_id": 1, "machine_id": "CNC1", "plan_date": TODAY.isoformat(),
                                        "shift": "주간", "pn": "TAIL-PN-01", "process": "선삭",
                                        "product_id": "P601", "plan_qty": 10, "plan_hours": 9, "wo_number": None,
                                        "worker": None, "note": None, "status": "PLAN"}]
    _force_truncated(monkeypatch, "production_schedule")
    at = _open(monkeypatch, m, "plan", "sb")
    assert any("저장을 막았습니다" in str(e.value) for e in at.error), [str(e.value) for e in at.error]
    assert any("부하 미확인" in str(x.value) for x in at.markdown)
    saves = [b for b in at.button if str(b.label) in ("보드 저장", "기간 저장")]
    assert saves and all(b.disabled for b in saves), [(b.label, b.disabled) for b in saves]
    # AppTest 는 비활성 버튼 클릭 자체를 거부한다(브라우저와 같음) — 실행 분기는 `and not _sb_bad` 로 이중 차단
    assert not [w for w in m.writes if w[1] == "production_schedule"], m.writes


def _open_app(monkeypatch, m, main, sub=None):
    from tests.test_hotfix2_followup_a import _open
    return _open(monkeypatch, m, main, sub)


@app_only
def test_h3a_sheet_apply_no_log_insert_when_std_truncated(monkeypatch):
    from tests.test_hotfix2_followup_a import _force_truncated, _mock
    m = _mock()
    _allow(m, "production_log", "product_op_std")
    _force_truncated(monkeypatch, "product_op_std")
    at = _open_app(monkeypatch, m, "report")
    at.session_state["psh_preview"] = {
        "new": [{"sheet_key": "K1", "log_date": "2026-10-27", "pn": "PN1", "process": "선삭",
                 "total_qty": 10}],
        "stds": {("PN1", "선삭"): {"uph_sheet": 30, "ct_sec": 120, "product_id": "P1", "pn": "PN1",
                                    "process": "선삭"}},
        "stats": {"rows": 1, "run": 1, "stop": 0, "matched": 1, "unmatched": {}}, "have": 0}
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    btn = next(b for b in at.button if b.key == "psh_apply")
    btn.click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert not [w for w in m.writes if w[1] in ("production_log", "product_op_std")], m.writes


@app_only
def test_h3b_std_recalc_no_writes_when_machine_matrix_truncated(monkeypatch):
    from tests.test_hotfix2_followup_a import _force_truncated, _mock
    m = _mock()
    _allow(m, "product_op_std", "product_op_machine")
    m.tables["production_log"] = [{"log_id": 1, "pn": "PN1", "product_id": "P1", "process": "선삭",
                                   "process_step": 1, "machine": "CNC1", "shift": "주간", "total_qty": 100,
                                   "defect_qty": 0, "work_start": None, "work_end": None,
                                   "log_date": "2026-10-27", "uptime_hours": 5}]
    _force_truncated(monkeypatch, "product_op_machine")
    at = _open_app(monkeypatch, m, "plan", "std")
    btn = next(b for b in at.button if b.key == "std_recalc")
    btn.click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert not [w for w in m.writes if w[1] in ("product_op_std", "product_op_machine")], m.writes


def _sync_case(monkeypatch, truncate):
    from tests.test_hotfix2_followup_a import _force_truncated, _mock
    m = _mock()
    _allow(m, "purchase_ledger", "purchase_item_map", "materials")
    m.tables["products"] = [{"product_id": "P0001", "pn": "MRG6-07", "archived_at": None}]
    if truncate:
        _force_truncated(monkeypatch, "products")
    at = _open_app(monkeypatch, m, "po", "pur")
    at.session_state["cost_sync_preview"] = {
        "new": [{"trade_date": "2026-10-27", "vendor": "명진", "item": "S304 Ø22*14", "unit": "EA",
                 "qty": 10, "weight": None, "unit_price": 100, "amount": 1000, "vat": 100, "total": 1100,
                 "remark": "MRG6-07 외주", "kg_price": None, "ea_price": None}],
        "match_n": 0, "miss": {}, "sheet": 1, "cut_n": 0, "pp_n": 0, "map_n": 0}
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    go = next(b for b in at.button if b.key == "cost_sync_go")
    go.click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return m, at


@app_only
def test_h4_sync_stops_when_products_truncated(monkeypatch):
    m, at = _sync_case(monkeypatch, truncate=True)
    assert not [w for w in m.writes if w[0] == "insert" and w[1] == "purchase_ledger"], m.writes
    assert any("동기화를 중단했습니다" in str(e.value) for e in at.error), [str(e.value) for e in at.error]


@app_only
def test_h4_sync_contrast_fills_matched_pn_when_complete(monkeypatch):
    """대조: 제품 조회가 완전하면 비고 첫 단어가 제품 품번일 때 matched_pn 이 채워진다(예전 기본 정렬
    ledger_id 로 products 조회가 실패해 늘 None 이던 잠재 버그의 정상화)."""
    m, at = _sync_case(monkeypatch, truncate=False)
    ins = [w for w in m.writes if w[0] == "insert" and w[1] == "purchase_ledger"]
    assert len(ins) == 1 and ins[0][2].get("matched_pn") == "MRG6-07", m.writes


# ── M1·M2 — 집계 미확인 ─────────────────────────────────────────

@app_only
def test_m1_finished_stock_kpis_unknown_when_truncated(monkeypatch):
    from tests.test_hotfix2_followup_a import _force_truncated, _mock
    m = _mock()
    m.seed(so_id=701, so_status="CONFIRMED", lines=[(971, 10, 0, 10, "PENDING")], pn="FS-PN", product_id="PFS")
    _force_truncated(monkeypatch, "product_stock_v")
    at = _open_app(monkeypatch, m, "ship", "fstock")
    for lbl in ("재고 보유 품목", "완성 재고 합계", "미납 대비 부족 품목"):
        got = [x.value for x in at.metric if x.label == lbl]
        assert got == ["미확인"], (lbl, got)


@app_only
def test_m2_daily_closing_kpis_unknown_when_truncated(monkeypatch):
    from datetime import date
    from tests.test_hotfix2_followup_a import _force_truncated, _mock
    m = _mock()
    m.seed(so_id=801, so_status="CONFIRMED", lines=[(981, 10, 10, 0, "DELIVERED")], pn="SR-PN", product_id="PSR")
    today = date.today().isoformat()
    m.tables["shipments"].append({"shipment_id": 91, "ship_no": "SH-T-01", "ship_date": today,
                                  "status": "CONFIRMED", "created_by": "t", "confirmed_at": today,
                                  "rev_no": 0, "revised_at": None})
    m.tables["shipment_items"].append({"si_id": 9101, "shipment_id": 91, "soi_id": 981, "so_id": 801,
                                       "product_id": "PSR", "pn": "SR-PN", "customer_pn": "CP-981",
                                       "item_name": "-", "customer": "(주)디아이씨두서공장", "so_number": "PO-801",
                                       "qty": 10, "unit": "EA", "unit_price": 100})
    _force_truncated(monkeypatch, "shipments")
    at = _open_app(monkeypatch, m, "sales")
    kpi = next((str(x.value) for x in at.markdown
                if 'class="kpi-row"' in str(x.value) and "공급가액" in str(x.value)), "")
    assert kpi and kpi.count('<div class="v">미확인</div>') >= 5, kpi[:500]
    assert any("결산 합계는 미확인" in str(w.value) for w in at.warning)
