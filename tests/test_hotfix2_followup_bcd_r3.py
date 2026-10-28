"""핫픽스 2 후속 B·C·D r3(2026-10-28) — Codex BCD r2 H-r2-1·H-r2-2·M-r2-1·M-r2-2·REQUIRED.

- H2: 기간 저장의 '기존 배정' 추가 조회만 실패해도 쓰기 0건 + 완전 조회 대조군(저장 payload 고정값 — 7ee8468 코드와
  같다는 것은 같은 테스트를 그 코드에서 돌려 확인, 00_README).
- H3: 완전 조회에서 생산 시트 ②·표준 재산출의 쓰기 순서·건수(대조군).
- H4: 제품 조회 일반 예외 → 중단 / 정상 빈 제품 목록 → 진행(matched_pn None) / 매핑표 조회 실패·절단 → 중단.
- 월 마감: 기간 조회 절단이면 버튼 비활성 + 확인 상태 주입해도 sales_month_close 쓰기 0건. 출력물 비활성.
- 완성 재고: 조회 예외도 '미확인'. 복합키 전부 NULL 행 보존.
"""
import importlib.util
import os
import sys
from datetime import date, timedelta

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import db  # noqa: E402
from tests.test_db_fetch_all import Raw  # noqa: E402
from tests.test_hotfix2_followup_bcd_r2 import _allow, _sync_case  # noqa: E402

streamlit_available = importlib.util.find_spec("streamlit") is not None
app_only = pytest.mark.skipif(not streamlit_available, reason="streamlit 미설치 — AppTest 불가")


def _force_fail(monkeypatch, table, when=lambda filt: True):
    """table 의 fetch_all 이 (조건에 맞으면) 일반 예외 — 네트워크 실패 흉내."""
    real = db.fetch_all

    def _wrap(t, select="*", filter_query="", *a, **kw):
        if t == table and when(filter_query or ""):
            raise RuntimeError(f"{t} 조회 실패 (시뮬레이션)")
        return real(t, select, filter_query, *a, **kw)
    monkeypatch.setattr(db, "fetch_all", _wrap)


def test_composite_all_null_key_rows_kept(monkeypatch):
    r = Raw([{"lot_number": None, "material_id": None, "lot_balance": i} for i in range(3)])
    monkeypatch.setattr(db, "_fetch_raw", r)
    db.clear_cache()
    rows, tr = db.fetch_all("material_stock_by_lot", "lot_balance", "")
    assert not tr and sorted(x["lot_balance"] for x in rows) == [0, 1, 2]


# ── H2 기간 저장 ────────────────────────────────────────────────

def _sb_mock():
    from tests.test_hotfix2_fetch_all_sites import TODAY, _mock
    m = _mock(target_due=(TODAY + timedelta(days=14)).isoformat(), filler=5)
    _allow(m, "production_schedule")
    m.tables["machines"] = [{"machine_id": "CNC1", "name": "CNC1", "group_code": "CNC", "active": True,
                             "night_active": False, "sat_active": False, "hours_per_shift": 9}]
    m.tables["product_op_std"] = [{
        "op_id": 1, "product_id": "P601", "pn": "TAIL-PN-01", "process": "선삭", "step": 1, "group_code": "CNC",
        "uph_std": 10, "uph_auto": 10, "uph_mean": 10, "uph_sheet": None, "ct_sec": 360, "sample_n": 1,
        "hours_n": 1, "machines_used": "CNC1", "setup_min": 0, "std_status": "CONFIRMED", "std_source": "LOG",
        "active": True, "calc_at": None, "first_date": None, "last_date": None, "confirmed_by": None,
        "confirmed_at": None, "note": None}]
    _ins0 = m.insert

    def _ins(table, records):                   # 목 insert 는 id 만 붙인다 — 실제 PK(sched_id)를 채워 재실행 화면이 읽게
        if table == "production_schedule":
            records = [dict(r, sched_id=1000 + i) for i, r in enumerate(records)]
        return _ins0(table, records)
    m.insert = _ins
    return m


def _period_save(monkeypatch, m):
    from tests.test_hotfix2_followup_a import _open
    at = _open(monkeypatch, m, "plan", "sb")
    assert any(s.key == "sb_op" for s in at.selectbox), "작업 선택지가 없음 — 시드 확인"
    d0 = next(d for d in at.date_input if d.key == "sb_d0").value
    next(d for d in at.date_input if d.key == "sb_d1").set_value(d0)       # 하루만
    next(x for x in at.multiselect if x.key == "sb_sh").set_value(["주간"])
    next(n for n in at.number_input if n.key == "sb_qty").set_value(50)
    next(b for b in at.button if str(b.label) == "기간 저장").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at, d0


@app_only
def test_h2_period_save_blocked_when_existing_lookup_fails(monkeypatch):
    m = _sb_mock()
    _force_fail(monkeypatch, "production_schedule", when=lambda f: "machine_id=eq." in f)
    at, _ = _period_save(monkeypatch, m)
    assert not [w for w in m.writes if w[1] == "production_schedule"], m.writes
    assert any("기존 계획 조회가 불완전해 저장하지 않았습니다" in str(e.value) for e in at.error)


@app_only
def test_h2_period_save_contrast_payload(monkeypatch):
    """대조군: 완전 조회면 저장 — 신규 1행(CNC1 · 시작일 · 주간 · 50개 · PLAN)."""
    m = _sb_mock()
    at, d0 = _period_save(monkeypatch, m)
    ins = [w for w in m.writes if w[0] == "insert" and w[1] == "production_schedule"]
    assert len(ins) == 1, m.writes
    row = ins[0][2]
    got = {k: row.get(k) for k in ("machine_id", "plan_date", "shift", "pn", "process", "product_id",
                                   "plan_qty", "plan_hours", "status")}
    assert got == {"machine_id": "CNC1", "plan_date": d0.isoformat(), "shift": "주간", "pn": "TAIL-PN-01",
                   "process": "선삭", "product_id": "P601", "plan_qty": 50.0, "plan_hours": 9.0,
                   "status": "PLAN"}, got


# ── H3 완전 조회 대조군 ───────────────────────────────────────────

@app_only
def test_h3_sheet_apply_contrast_order(monkeypatch):
    from tests.test_hotfix2_followup_a import _mock, _open
    m = _mock()
    _allow(m, "production_log", "product_op_std")
    at = _open(monkeypatch, m, "report")
    at.session_state["psh_preview"] = {
        "new": [{"sheet_key": "K1", "log_date": "2026-10-27", "pn": "PN1", "process": "선삭", "total_qty": 10}],
        "stds": {("PN1", "선삭"): {"uph_sheet": 30, "ct_sec": 120, "idle_sec": 0, "product_id": "P1", "pn": "PN1",
                                    "process": "선삭", "step": 1}},
        "stats": {"rows": 1, "run": 1, "stop": 0, "matched": 1, "unmatched": {}}, "have": 0}
    at.run()
    next(b for b in at.button if b.key == "psh_apply").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    seq = [(w[0], w[1]) for w in m.writes if w[1] in ("production_log", "product_op_std")]
    assert seq == [("insert", "production_log"), ("insert", "product_op_std")], seq


@app_only
def test_h3_std_recalc_contrast_writes(monkeypatch):
    from tests.test_hotfix2_followup_a import _mock, _open
    m = _mock()
    _allow(m, "product_op_std", "product_op_machine")
    m.tables["production_log"] = [{"log_id": 1, "pn": "PN1", "product_id": "P1", "process": "선삭",
                                   "process_step": 1, "machine": "CNC1", "shift": "주간", "total_qty": 100,
                                   "defect_qty": 0, "work_start": None, "work_end": None,
                                   "log_date": "2026-10-27", "uptime_hours": 5}]
    at = _open(monkeypatch, m, "plan", "std")
    next(b for b in at.button if b.key == "std_recalc").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    seq = [(w[0], w[1]) for w in m.writes if w[1] in ("product_op_std", "product_op_machine")]
    assert seq[0] == ("insert", "product_op_std") and ("insert", "product_op_machine") in seq, seq


# ── H4 동기화 ② 구분 ─────────────────────────────────────────────

def _sync(monkeypatch, *, fail=None, trunc=None, products=None):
    from tests.test_hotfix2_followup_a import _force_truncated
    if fail:
        _force_fail(monkeypatch, fail)
    if trunc:
        _force_truncated(monkeypatch, trunc)
    if products is not None:
        return _sync_case_with_products(monkeypatch, products)
    return _sync_case(monkeypatch, truncate=False)


def _sync_case_with_products(monkeypatch, products):
    from tests.test_hotfix2_followup_a import _mock, _open
    m = _mock()
    _allow(m, "purchase_ledger", "purchase_item_map", "materials")
    m.tables["products"] = list(products)
    at = _open(monkeypatch, m, "po", "pur")
    at.session_state["cost_sync_preview"] = {
        "new": [{"trade_date": "2026-10-27", "vendor": "명진", "item": "S304 Ø22*14", "unit": "EA", "qty": 10,
                 "weight": None, "unit_price": 100, "amount": 1000, "vat": 100, "total": 1100,
                 "remark": "MRG6-07 외주", "kg_price": None, "ea_price": None}],
        "match_n": 0, "miss": {}, "sheet": 1, "cut_n": 0, "pp_n": 0, "map_n": 0}
    at.run()
    next(b for b in at.button if b.key == "cost_sync_go").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return m, at


def _ledger_ins(m):
    return [w for w in m.writes if w[0] == "insert" and w[1] == "purchase_ledger"]


@app_only
def test_h4_products_general_failure_stops(monkeypatch):
    m, at = _sync(monkeypatch, fail="products")
    assert not _ledger_ins(m), m.writes
    assert any("제품 조회 실패 — 동기화를 중단했습니다" in str(e.value) for e in at.error)


@app_only
def test_h4_empty_products_still_syncs(monkeypatch):
    """정상 빈 제품 목록은 '실패'가 아니다 — 그대로 넣고 matched_pn 은 None."""
    m, at = _sync(monkeypatch, products=[])
    ins = _ledger_ins(m)
    assert len(ins) == 1 and ins[0][2].get("matched_pn") is None, m.writes


@pytest.mark.parametrize("mode", ["fail", "trunc"])
@app_only
def test_h4_item_map_failure_or_truncation_stops(monkeypatch, mode):
    m, at = (_sync(monkeypatch, fail="purchase_item_map") if mode == "fail"
             else _sync(monkeypatch, trunc="purchase_item_map"))
    assert not _ledger_ins(m), m.writes
    assert any("매핑표·자재 조회 실패 — 동기화를 중단했습니다" in str(e.value) for e in at.error), \
        [str(e.value) for e in at.error]


# ── 월 마감·출력물·완성 재고 ───────────────────────────────────────

def _sales_mock():
    from tests.test_hotfix2_followup_a import _mock
    m = _mock()
    m.seed(so_id=801, so_status="CONFIRMED", lines=[(981, 10, 10, 0, "DELIVERED")], pn="SR-PN",
           product_id="PSR")
    today = date.today().isoformat()
    m.tables["shipments"].append({"shipment_id": 91, "ship_no": "SH-T-01", "ship_date": today,
                                  "status": "CONFIRMED", "created_by": "t", "confirmed_at": today,
                                  "rev_no": 0, "revised_at": None})
    m.tables["shipment_items"].append({"si_id": 9101, "shipment_id": 91, "soi_id": 981, "so_id": 801,
                                       "product_id": "PSR", "pn": "SR-PN", "customer_pn": "CP-981",
                                       "item_name": "-", "customer": "(주)디아이씨두서공장",
                                       "so_number": "PO-801", "qty": 10, "unit": "EA", "unit_price": 100})
    _allow(m, "sales_month_close")
    return m


@app_only
def test_month_close_blocked_when_period_truncated(monkeypatch):
    from tests.test_hotfix2_followup_a import _force_truncated, _open
    m = _sales_mock()
    _force_truncated(monkeypatch, "shipments")
    at = _open(monkeypatch, m, "sales")
    btn = [b for b in at.button if b.key == "sr_mc_close"]
    assert btn and btn[0].disabled, [(b.key, b.disabled) for b in btn]
    at.session_state["cfm_sr_mc_close"] = True                   # 이전 실행의 확인 상태 주입
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert not any(str(b.key or "").startswith("sr_mc_close_cfm") for b in at.button)
    assert not [w for w in m.writes if w[1] == "sales_month_close"], m.writes
    assert any("마감할 수 없습니다" in str(c.value) for c in at.caption)


@app_only
def test_outputs_disabled_when_truncated(monkeypatch):
    from tests.test_hotfix2_followup_a import _force_truncated, _open
    m = _sales_mock()
    _force_truncated(monkeypatch, "shipments")
    at = _open(monkeypatch, m, "sales")
    dl = {getattr(b, "label", ""): getattr(b, "disabled", None) for b in at.get("download_button")}
    assert dl.get("일일 결산 리포트 인쇄") is True, dl


@app_only
def test_finished_stock_failure_is_unknown(monkeypatch):
    from tests.test_hotfix2_followup_a import _mock, _open
    m = _mock()
    m.seed(so_id=701, so_status="CONFIRMED", lines=[(971, 10, 0, 10, "PENDING")], pn="FS-PN", product_id="PFS")
    _force_fail(monkeypatch, "sales_order_items", when=lambda f: f == "pending_qty=gt.0&product_id=not.is.null")
    at = _open(monkeypatch, m, "ship", "fstock")
    got = [x.value for x in at.metric if x.label == "미납 대비 부족 품목"]
    assert got == ["미확인"], got
