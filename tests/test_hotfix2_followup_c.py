"""핫픽스 2 후속 C(2026-10-28) — 범위·전체 조회 db.fetch_all 통일, 로컬 페이지 루프 4종 제거, 복합키(tuple) pk.

- db: tuple pk 의 select·정렬 보강·중복 제거, 단일 열 pk 는 그대로.
- 로컬 루프 4종(_std_fetch_all·_sb_all·_pl_fetch_pages·_off9): 바뀐 호출 인자 그대로 2,500행 목에서 예전
  루프와 같은 결과(전체 행, 같은 순서)인지 — 예전 루프는 정렬 열이 유일하지 않으면 페이지 경계가 흔들렸다.
- 앱: 집계에 쓰이는 범위 조회가 잘리면 '미확인'(수주 KPI 지연·납품 스케줄 미납 라인·투입 대기 LOT),
  소요량 계산은 중단.
"""
import importlib.util
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import db  # noqa: E402
from tests.test_db_fetch_all import Raw  # noqa: E402

APP_FILE = os.path.join(ROOT, "streamlit_app.py")
streamlit_available = importlib.util.find_spec("streamlit") is not None


@pytest.fixture()
def raw(monkeypatch):
    def _install(rows, **kw):
        r = Raw(rows, **kw)
        monkeypatch.setattr(db, "_fetch_raw", r)
        db.clear_cache()
        return r
    return _install


# ── db: 복합키 tuple pk ───────────────────────────────────────────

def _lot_rows(n):
    # (lot_number, material_id) 복합키. material_id 는 일부 NULL(운영 material_stock_by_lot 18행과 같은 모양)
    return [{"lot_number": f"W{(n - i) // 3:05d}", "material_id": (None if i % 3 == 0 else f"M{i % 3}"),
             "lot_balance": 1} for i in range(n)]


def test_tuple_pk_select_order_and_dedupe(raw):
    r = raw(_lot_rows(2500))
    rows, tr = db.fetch_all("material_stock_by_lot", "lot_balance", "", order="lot_number.desc")
    assert not tr and len(rows) == 2500
    sel, fq, _ = r.calls[0]
    assert sel == "lot_balance,lot_number,material_id", sel                 # 빠진 키 열을 순서대로
    assert "order=lot_number.desc,material_id.asc" in fq, fq                # 정렬 보강(이미 있는 열은 그대로)
    keys = [(x["lot_number"], x["material_id"]) for x in rows]
    assert len(set(keys)) == 2500


def test_tuple_pk_dedupes_boundary_duplicates(raw):
    """다음 페이지 시작이 당겨져(삽입 모사) 경계 행이 두 번 와도 tuple 키로 한 번만."""
    raw(_lot_rows(2500), dup_shift=3)
    rows, _ = db.fetch_all("material_stock_by_lot", "lot_balance", "", order="lot_number.desc")
    keys = [(x["lot_number"], x["material_id"]) for x in rows]
    assert len(keys) == len(set(keys))


def test_tuple_pk_from_list_is_hashable_and_explicit(raw):
    raw([{"a": i // 10, "b": i % 10, "v": i} for i in range(1500)])
    rows, tr = db.fetch_all("no_such_view", "v", "", pk=["a", "b"])
    assert not tr and len(rows) == 1500 and {x["v"] for x in rows} == set(range(1500))


def test_registered_view_keys():
    # BCD r2 H1: 구조적 유일 키만 — data_quality_v·product_lot_stock_v 는 없음(호출에서 dedupe=False)
    assert "data_quality_v" not in db.PK_OF and "product_lot_stock_v" not in db.PK_OF
    assert db.PK_OF["material_stock_by_lot"] == ("lot_number", "material_id")
    assert db.PK_OF["product_material_price_status_v"] == "bom_id"
    for t, k in (("product_routing", "routing_id"), ("bom", "bom_id"), ("vendors", "vendor_id"),
                 ("product_op_std", "op_id"), ("production_log", "log_id"), ("wo_batches", "batch_id"),
                 ("product_stock_v", "product_id"), ("product_cost_full_v", "product_id")):
        assert db.PK_OF[t] == k, t


# ── 로컬 루프 4종 → db.fetch_all: 같은 인자로 2,500행 끝까지·같은 순서 ─────────────────

def _old_loop(raw_rows, table, select, filt, order):
    """예전 앱 루프(order 열만 정렬, offset 1,000씩)를 목에서 그대로 — 기준 결과."""
    r = Raw(raw_rows)
    out, off = [], 0
    while True:
        pg = r(table, select, (filt + "&" if filt else "") + f"order={order}&offset={off}", 1000)
        out += pg
        if len(pg) < 1000:
            return out
        off += 1000


@pytest.mark.parametrize("table,select,filt,order,mk", [
    # _std_fetch_all(공정 표준 재산출·표준 목록)
    ("production_log", "pn,process,total_qty", "", "log_id",
     lambda i: {"log_id": 2500 - i, "pn": f"P{i % 40}", "process": "선삭", "total_qty": i}),
    ("product_op_std", "op_id,pn,process", "", "op_id",
     lambda i: {"op_id": 2500 - i, "pn": f"P{i}", "process": "선삭"}),
    # _sb_all(설비 스케줄) — 필터의 order= 를 order 인자로 뺐다
    ("production_schedule", "sched_id,machine_id,plan_qty", "status=neq.CANCELLED", "sched_id",
     lambda i: {"sched_id": 2500 - i, "machine_id": f"MC{i % 9}", "plan_qty": i, "status": "PLANNED"}),
    # _pl_fetch_pages(장부 동기화) — 기본 정렬 = 표의 PK
    ("purchase_ledger", "vendor,item,unit_price", "", "ledger_id",
     lambda i: {"ledger_id": 2500 - i, "vendor": "V", "item": f"I{i}", "unit_price": i}),
    ("purchase_item_map", "product_id,process_type", "", "map_id",
     lambda i: {"map_id": 2500 - i, "product_id": f"P{i}", "process_type": None}),
    # _off9(생산 보고 시트 업로드)
    ("products", "product_id,pn,alias_list,archived_at", "", "product_id",
     lambda i: {"product_id": f"P{2500 - i:05d}", "pn": f"PN{i}", "alias_list": None, "archived_at": None}),
    ("production_log", "sheet_key", "sheet_key=not.is.null", "log_id",
     lambda i: {"log_id": 2500 - i, "sheet_key": f"K{i}"}),
])
def test_loop_replacement_same_result_2500(raw, table, select, filt, order, mk):
    rows_src = [mk(i) for i in range(2500)]
    if "sheet_key" in filt:       # Raw 는 필터를 적용하지 않는다 — 조건에 맞는 행만 둔다
        rows_src = [x for x in rows_src if x.get("sheet_key") is not None]
    want = _old_loop(rows_src, table, select, "", order)
    raw(rows_src)
    got, tr = db.fetch_all(table, select, filt, order=order)
    assert not tr and len(got) == len(want) == 2500
    cols = [c for c in select.split(",")]
    assert [{c: x[c] for c in cols} for x in got] == want


def test_non_unique_order_keeps_every_row_once(raw):
    """예전 _std_fetch_all('product_op_std', …, 'pn,step,process') 처럼 정렬 열이 유일하지 않아도 PK 보강으로
    2,500행이 한 번씩(예전 루프는 페이지 경계 동률 행이 빠지거나 겹칠 수 있었다)."""
    src = [{"op_id": i + 1, "pn": f"P{i % 3}", "step": 1, "process": "선삭"} for i in range(2500)]
    r = raw(src)
    got, _ = db.fetch_all("product_op_std", "pn,step,process", "", order="pn,step,process")
    assert sorted(x["op_id"] for x in got) == list(range(1, 2501))
    assert "order=pn,step,process,op_id.asc" in r.calls[0][1]


def test_no_manual_offset_loops_left_for_the_four_helpers():
    src = open(APP_FILE, encoding="utf-8").read()
    assert "_off9" not in src
    for name in ("_std_fetch_all", "_sb_all", "_pl_fetch_pages"):
        body = src.split(f"def {name}(", 1)[1].split("\n\n", 1)[0]
        assert "offset=" not in body and "fetch_all(" in body, name
    assert "&order=sched_id\")" not in src and "&order=log_id\")" not in src   # _sb_all 필터의 order= 제거


# ── 앱: 집계 범위 조회 절단 → 미확인 ─────────────────────────────────────

pytestmark_app = pytest.mark.skipif(not streamlit_available, reason="streamlit 미설치 — AppTest 불가")


@pytestmark_app
def test_so_kpi_late_unknown_when_late_lines_truncated(monkeypatch):
    from tests.test_hotfix2_fetch_all_sites import TODAY, _late_value, _mock, _open
    from tests.test_hotfix2_followup_a import _force_truncated
    from datetime import timedelta
    m = _mock(target_due=(TODAY + timedelta(days=60)).isoformat(), filler=5)
    _force_truncated(monkeypatch, "sales_order_items")
    at = _open(monkeypatch, m, "so", "input")
    assert _late_value(at) == "미확인", _late_value(at)


@pytestmark_app
def test_schedule_unknown_when_open_lines_truncated(monkeypatch):
    from tests.test_hotfix2_fetch_all_sites import TODAY, _mock, _open
    from tests.test_hotfix2_followup_a import _force_truncated
    from datetime import timedelta
    m = _mock(target_due=(TODAY + timedelta(days=7)).isoformat(), target_qty=50, line_pending=100, filler=5)
    _force_truncated(monkeypatch, "sales_order_items")
    at = _open(monkeypatch, m, "so", "sched")
    kpi = next((str(x.value) for x in at.markdown
                if 'class="kpi-row"' in str(x.value) and "지연 회차" in str(x.value)), "")
    assert kpi.count('<div class="v">미확인</div>') == 4, kpi[:300]
    assert any("미납 라인 행이 너무 많아" in str(x.value) for x in at.markdown)
    assert not any('class="unplan"' in str(x.value) for x in at.markdown)


@pytestmark_app
def test_receipt_status_pending_lot_count_unknown(monkeypatch):
    from tests.test_hotfix2_followup_a import _force_truncated, _mock, _open
    m = _mock()
    m.tables["material_stock_by_lot"] = [{"material_id": "M1", "lot_number": "W00001", "lot_balance": 5,
                                          "last_date": "2026-10-27"}]
    _force_truncated(monkeypatch, "material_stock_by_lot")
    at = _open(monkeypatch, m, "po", "rstat")
    kpi = next((str(x.value) for x in at.markdown
                if 'class="kpi-row"' in str(x.value) and "투입 대기 LOT" in str(x.value)), "")
    assert re.search(r"투입 대기 LOT</div><div class=\"v\">미확인<", kpi), kpi[-400:]
