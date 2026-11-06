# -*- coding: utf-8 -*-
"""핫픽스 2 후속 2차 묶음 F — 묶음(in)·eq 잔여 38곳 (2026-10-30).

- utils.fetch_in.fetch_all_in: 50개 경계(50·51 id), 묶음 하나가 1,000행을 넘어도 끝까지, 절단 OR, 빈 목록,
  quote·extra, 묶음 순서.
- 출고 등록 완성 LOT offset 루프 → fetch_all: 같은 입력 → 같은 행·순서(대조군, 2,500행).
- 화면 게이트(절단 주입): 영업 보고(라인 절단 → 마감·출력 차단, 1,000행 넘는 전표 합계), 출고 전표(반영 흔적 절단 →
  잠금, 정정 준비 절단 → 쓰기 0), 출고 등록(작성중 라인 절단 → 기존 전표 추가 막음), 출고 현황(KPI 미확인),
  발주 소요량(BOM 절단 → 계산 중단), 주간 계획(저장 비활성), DIC 업로드(기존 라인 절단 → 추가 0).
- 정적: limit=1000|2000 잔여 0.
"""
import importlib.util
import os
import re
import sys
from datetime import date

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import db  # noqa: E402
from tests.test_shipment_revision_flow import rev_db  # noqa: E402,F401  (픽스처)
from tests.test_weekly_plan_page import plan_db  # noqa: E402,F401  (픽스처)
from tests.test_bulk_delivery import ship_db  # noqa: E402,F401  (픽스처)

APP_FILE = os.path.join(ROOT, "streamlit_app.py")
streamlit_available = importlib.util.find_spec("streamlit") is not None
app_only = pytest.mark.skipif(not streamlit_available, reason="streamlit 미설치 — AppTest 불가")


# ── fetch_all_in 단위 ────────────────────────────────────────────────

@pytest.fixture()
def som(monkeypatch):
    from tests.test_hotfix2_followup_a import _mock
    m = _mock()                    # 요청당 1,000행·order=·select 적용
    m.install(monkeypatch, db)
    db.clear_cache()
    return m


def _calls(monkeypatch):
    real, calls = db.fetch_all, []

    def _spy(t, select="*", filter_query="", **kw):
        calls.append((t, filter_query, kw))
        return real(t, select, filter_query, **kw)
    monkeypatch.setattr(db, "fetch_all", _spy)
    return calls


@pytest.mark.parametrize("n, chunks", [(50, 1), (51, 2), (100, 2), (101, 3)])
def test_chunk_boundary(som, monkeypatch, n, chunks):
    from utils.fetch_in import fetch_all_in
    som.tables["sales_order_items"] = [{"soi_id": i, "so_id": i, "qty": 1} for i in range(1, 121)]
    calls = _calls(monkeypatch)
    rows, tr = fetch_all_in("sales_order_items", "soi_id,so_id", "so_id", list(range(1, n + 1)))
    assert tr is False and sorted(r["so_id"] for r in rows) == list(range(1, n + 1))
    assert len(calls) == chunks
    assert all(len(fq.split("so_id=in.(")[1].split(")")[0].split(",")) <= 50 for _, fq, _ in calls)


def test_one_chunk_over_1000_rows_read_to_the_end(som):
    """예전 fetch(limit=2000) 은 서버 상한 1,000 에서 조용히 잘렸다 — 이제 끝까지."""
    from utils.fetch_in import fetch_all_in
    som.tables["shipment_items"] = [{"si_id": i, "shipment_id": 1 + (i % 3), "qty": 1}
                                    for i in range(1, 2501)]
    rows, tr = fetch_all_in("shipment_items", "si_id,shipment_id,qty", "shipment_id", [1, 2, 3],
                            order="si_id.asc")
    assert tr is False and len(rows) == 2500 and len({r["si_id"] for r in rows}) == 2500


def test_truncation_is_ored_over_chunks(som, monkeypatch):
    from utils.fetch_in import fetch_all_in
    som.tables["sales_order_items"] = [{"soi_id": i, "so_id": i} for i in range(1, 61)]
    real = db.fetch_all

    def _fa(t, select="*", filter_query="", **kw):
        rows, _ = real(t, select, filter_query, **kw)
        return rows, "so_id=in.(51" in filter_query          # 두 번째 묶음만 절단
    monkeypatch.setattr(db, "fetch_all", _fa)
    rows, tr = fetch_all_in("sales_order_items", "soi_id", "so_id", list(range(1, 61)))
    assert tr is True and len(rows) == 60


def test_empty_quote_extra_dedup_and_order(som, monkeypatch):
    from utils.fetch_in import fetch_all_in
    calls = _calls(monkeypatch)
    assert fetch_all_in("bom", "bom_id", "product_id", []) == ([], False)
    assert fetch_all_in("bom", "bom_id", "product_id", [None]) == ([], False)
    assert calls == []                                        # 빈 목록은 조회하지 않는다
    som.tables["bom"] = [{"bom_id": 1, "product_id": "P1", "material_id": "M1"},
                         {"bom_id": 2, "product_id": "P2", "material_id": "M1"},
                         {"bom_id": 3, "product_id": "P2", "material_id": None}]
    rows, tr = fetch_all_in("bom", "bom_id,product_id", "product_id", ["P2", "P1", "P2"],
                            "material_id=not.is.null", quote=True, order="bom_id.desc")
    assert tr is False and [r["bom_id"] for r in rows] == [2, 1]
    fq = calls[-1][1]
    assert fq.startswith('product_id=in.("P2","P1")&material_id=not.is.null'), fq
    assert calls[-1][2]["order"] == "bom_id.desc"


# ── 출고 등록 완성 LOT: offset 루프 → fetch_all 대조군 ─────────────────────

def _old_lot_loop(grp):
    """7b0bd80 출고 등록의 offset 루프(그대로)."""
    out, off = [], 0
    while True:
        pg = db.fetch("product_lot_stock_v", "product_id,remain_qty",
                      "remain_qty=gt.0&product_id=in.({})&order=product_id.asc,"
                      "lot_number.asc&offset={}".format(",".join(f'"{x}"' for x in grp), off),
                      limit=1000)
        out += pg
        if len(pg) < 1000:
            break
        off += 1000
    return out


def test_lot_loop_replacement_same_rows_and_order(som):
    from utils.fetch_in import fetch_all_in
    rows = []
    for p in ("PA", "PB", "PC"):
        for k in range(850):
            rows.append({"product_id": p, "lot_number": f"L{k:04d}", "remain_qty": (k % 7) + 1})
    rows.append({"product_id": "PA", "lot_number": "L0001", "remain_qty": 3})    # 비유일(조인 중복) 행도 그대로
    rows.append({"product_id": "PB", "lot_number": "Z", "remain_qty": 0})         # remain 0 은 제외
    som.tables["product_lot_stock_v"] = rows
    grp = ["PA", "PB", "PC"]
    old = _old_lot_loop(grp)
    new, tr = fetch_all_in("product_lot_stock_v", "product_id,remain_qty", "product_id", grp,
                           "remain_qty=gt.0", quote=True, chunk=80, order="product_id.asc,lot_number.asc",
                           pk=("product_id", "lot_number"), dedupe=False)
    assert tr is False and len(old) == 2551
    key = [(r["product_id"], r["remain_qty"]) for r in old]
    assert [(r["product_id"], r["remain_qty"]) for r in new] == key
    s_old, s_new = {}, {}
    for r in old:
        s_old[r["product_id"]] = s_old.get(r["product_id"], 0) + r["remain_qty"]
    for r in new:
        s_new[r["product_id"]] = s_new.get(r["product_id"], 0) + r["remain_qty"]
    assert s_old == s_new


# ── 정적 ────────────────────────────────────────────────────────────

def test_no_limit_1000_or_2000_left():
    src = open(APP_FILE, encoding="utf-8").read()
    assert not re.findall(r"limit=(?:1000|2000)\b", src)
    assert "_d_tr = _d_tr or _d_itr" in src and "_m_tr = _m_tr or _m_itr" in src \
        and "_r_tr = _r_tr or _r_itr" in src
    assert "disabled=len(inc) == 0 or bool(bad_pn) or exist_tr" in src          # MES 중복 판정 절단
    assert "같은 날짜 장부 {TRUNC_MSG} — 중복 검사를 끝낼 수 없어" in src        # 매입 장부 중복 검사 절단


# ── 화면 게이트 ──────────────────────────────────────────────────────

def _trunc_when(monkeypatch, pred):
    """pred(table, select, filter) 가 참인 fetch_all 결과를 truncated=True 로."""
    real = db.fetch_all

    def _w(t, select="*", filter_query="", *a, **kw):
        rows, tr = real(t, select, filter_query, *a, **kw)
        return rows, (tr or pred(t, select, filter_query or ""))
    monkeypatch.setattr(db, "fetch_all", _w)


def _kpi_html(at, label):
    return next((str(x.value) for x in at.markdown
                 if 'class="kpi-row"' in str(x.value) and label in str(x.value)), "")


@app_only
def test_sales_report_reads_ship_lines_past_1000(monkeypatch):
    """전표 하나에 1,200줄 — 일일 결산 총 수량이 끝까지 합산(예전 limit=2000 은 서버 1,000 에서 잘림)."""
    from tests.test_hotfix2_followup_a import _open
    from tests.test_hotfix2_followup_bcd_r3 import _sales_mock
    m = _sales_mock()
    base = dict(m.tables["shipment_items"][0])
    m.tables["shipment_items"] = [dict(base, si_id=20000 + i, qty=1) for i in range(1200)]
    at = _open(monkeypatch, m, "sales")
    kpi = _kpi_html(at, "총 수량")
    assert '<div class="v">1,200</div>' in kpi, kpi[:600]
    assert not [b for b in at.button if b.key == "sr_mc_close" and b.disabled]


@app_only
def test_sales_report_line_truncation_blocks_close_and_outputs(monkeypatch):
    from tests.test_hotfix2_followup_a import _force_truncated, _open
    from tests.test_hotfix2_2nd_e_month_close import MONTH_OUTPUTS, _dl
    from tests.test_hotfix2_followup_bcd_r3 import _sales_mock
    m = _sales_mock()
    _force_truncated(monkeypatch, "shipment_items")
    at = _open(monkeypatch, m, "sales")
    assert '<div class="v">미확인</div>' in _kpi_html(at, "총 수량")
    btn = [b for b in at.button if b.key == "sr_mc_close"]
    assert btn and btn[0].disabled
    dl = _dl(at)
    assert dl.get("일일 결산 리포트 인쇄") is True and all(dl.get(k) is True for k in MONTH_OUTPUTS), dl
    at.session_state["cfm_sr_mc_close"] = True
    at.run()
    assert not [w for w in m.writes if w[1] == "sales_month_close"], m.writes


@app_only
def test_slip_effects_truncation_locks_everything(rev_db, monkeypatch):
    """반영 흔적(ISSUE·충당) 조회가 잘리면 '모름' — 예외와 같이 확정·정정·취소 잠금."""
    from tests import test_shipment_revision_flow as rf
    _trunc_when(monkeypatch, lambda t, s, f: t == "shipment_allocations")
    rf._seed()
    at = rf._open()
    assert any("반영 여부를 확인하지 못했습니다" in str(e.value) for e in at.error), \
        [str(e.value) for e in at.error]
    assert at.button(key="cf_go").proto.disabled
    assert at.button(key="cf_cancel").proto.disabled
    assert rf.SHIPMENTS[1]["status"] == "DRAFT"


@app_only
def test_ship_register_draft_lines_truncated_blocks_add_to_draft(monkeypatch):
    from tests.test_hotfix2_followup_a import _mock, _open
    m = _mock()
    m.tables["shipments"].append({"shipment_id": 7, "ship_no": "SH-T-07", "ship_date": date.today().isoformat(),
                                  "status": "DRAFT", "created_by": "t", "confirmed_at": None,
                                  "rev_no": 0, "revised_at": None})
    m.tables["shipment_items"].append({"si_id": 701, "shipment_id": 7, "soi_id": 1, "qty": 1})
    _trunc_when(monkeypatch, lambda t, s, f: t == "shipment_items" and "shipment_id=in." in f)
    at = _open(monkeypatch, m, "ship", "deliver")
    assert any("작성중 전표 라인" in str(w.value) and "추가는 잠시 막습니다" in str(w.value)
               for w in at.warning), [str(w.value) for w in at.warning]


@app_only
def test_delivery_status_kpis_unknown_when_lines_truncated(monkeypatch):
    from tests.test_hotfix2_followup_a import _force_truncated, _open
    from tests.test_hotfix2_followup_bcd_r3 import _sales_mock
    m = _sales_mock()
    _force_truncated(monkeypatch, "shipment_items")
    at = _open(monkeypatch, m, "ship", "dstat")
    kpi = _kpi_html(at, "출고 수량")
    assert kpi.count('<div class="v">미확인</div>') == 4, kpi[:600]


@app_only
def test_delivery_status_kpis_complete_contrast(monkeypatch):
    from tests.test_hotfix2_followup_a import _open
    from tests.test_hotfix2_followup_bcd_r3 import _sales_mock
    m = _sales_mock()
    at = _open(monkeypatch, m, "ship", "dstat")
    kpi = _kpi_html(at, "출고 수량")
    assert '<div class="v">10</div>' in kpi and "미확인" not in kpi, kpi[:600]


@app_only
def test_po_requirement_stops_when_bom_truncated(monkeypatch):
    from tests.test_hotfix2_followup_a import _force_truncated, _mock, _open
    m = _mock()
    m.seed(so_id=901, so_status="CONFIRMED", lines=[(991, 10, 0, 10, "PENDING")], pn="MR-PN", product_id="PMR")
    m.tables["bom"] = [{"bom_id": 1, "product_id": "PMR", "material_id": "M1", "raw_material_name": "SUS",
                        "qty_per_pc": 1, "shared_factor": 1, "process_type": "MATERIAL"}]
    _force_truncated(monkeypatch, "bom")
    at = _open(monkeypatch, m, "po", "new")
    from tests.test_hotfix2_followup_a import _texts
    assert "BOM 행이 너무 많아 일부만 조회됐습니다 — 소요량을 계산하지 않았습니다" in _texts(at)


@app_only
def test_weekly_plan_truncated_load_disables_save(monkeypatch):
    from tests.test_hotfix2_followup_a import _force_truncated, _mock, _open
    m = _mock()
    m.tables["production_plan_items"] = []
    _force_truncated(monkeypatch, "production_plan_items")
    at = _open(monkeypatch, m, "plan", "wp")
    assert any("이 주 계획 행이 너무 많아" in str(w.value) for w in at.warning), \
        [str(w.value) for w in at.warning]
    sv = [b for b in at.button if (b.label or "") == "저장"]
    assert not sv or all(b.disabled for b in sv), [(b.label, b.disabled) for b in sv]


@app_only
def test_dic_upload_existing_lines_truncated_appends_nothing(monkeypatch):
    """DIC 재업로드: 기존 수주 라인을 일부만 읽으면 '있는 라인'을 새 행번으로 또 넣을 수 있다 → 추가 0."""
    from tests import test_so_upload_dic as td
    _dic_db(monkeypatch, td)
    _trunc_when(monkeypatch, lambda t, s, f: t == "sales_order_items")
    from streamlit.testing.v1 import AppTest
    from tests.conftest import goto, msg_texts
    import utils.slack_notify as _sn
    monkeypatch.setattr(_sn, "notify", lambda text, sync=False: True)
    at = AppTest.from_file(APP_FILE, default_timeout=60)
    at.secrets["supabase"] = {"url": "https://mock.local", "anon_key": "a", "service_role_key": "s"}
    at.secrets["auth"] = {"disabled": True}
    at.run()
    goto(at, "so", "input")
    at.get("file_uploader")[0].upload("납품예정서등록-DIC.xls", td._workbook()).run()
    assert not at.exception, [str(e.value) for e in at.exception]
    txt = " ".join(msg_texts(at))
    assert "기존 수주 대조 실패" in txt and "추가하지 않았습니다" in txt, txt[:800]
    assert "새 행번 0개" in txt, txt[:800]
    save = [b for b in at.button if b.key == "so_up_save"]
    if save:
        save[0].click().run()
    assert not any(x["so_id"] == 500 for t, rows in td.INSERTED if t == "sales_order_items" for x in rows)


def _dic_db(monkeypatch, td):
    """test_so_upload_dic.dic_db 와 같은 목(픽스처를 직접 부를 수 없어 같은 설치를 반복)."""
    td.INSERTED.clear()
    td.UPDATED.clear()
    monkeypatch.setattr(db, "fetch", td._fetch)
    monkeypatch.setattr(db, "fetch_one", td._fetch_one)
    monkeypatch.setattr(db, "insert", lambda t, r: (td.INSERTED.append((t, r)), len(r))[1])
    monkeypatch.setattr(db, "update", lambda t, f, v: (td.UPDATED.append((t, f, v)), True)[1])
    monkeypatch.setattr(db, "health_check", lambda: {"status": "OK", "counts": {}})
    monkeypatch.setattr(db, "debug_check", lambda: {"status": "mock"})
    monkeypatch.setattr(db, "count_rows", lambda *a, **k: 0)
    monkeypatch.setattr(db, "rpc", lambda *a, **k: None)


# ══ r2 (Codex r1 M1 · REQUIRED TESTS 선별, 2026-10-30) ══════════════════════

# ── r2-2 fetch_all_in ──

def test_second_chunk_exception_propagates_without_partial_rows(som, monkeypatch):
    from utils.fetch_in import fetch_all_in
    som.tables["sales_order_items"] = [{"soi_id": i, "so_id": i} for i in range(1, 61)]
    real = db.fetch_all

    def _fa(t, select="*", filter_query="", **kw):
        if "so_id=in.(51" in filter_query:
            raise RuntimeError("두 번째 묶음 실패(시뮬레이션)")
        return real(t, select, filter_query, **kw)
    monkeypatch.setattr(db, "fetch_all", _fa)
    got = None
    with pytest.raises(RuntimeError, match="두 번째 묶음"):
        got = fetch_all_in("sales_order_items", "soi_id", "so_id", list(range(1, 61)))
    assert got is None                       # 부분 행을 돌려주지 않는다


def test_cache_false_is_passed_to_fetch_all(som, monkeypatch):
    from utils.fetch_in import fetch_all_in
    som.tables["sales_order_items"] = [{"soi_id": 1, "so_id": 1}]
    calls = _calls(monkeypatch)
    fetch_all_in("sales_order_items", "soi_id", "so_id", [1], cache=False)
    fetch_all_in("sales_order_items", "soi_id", "so_id", [1])
    assert calls[0][2].get("cache") is False and "cache" not in calls[1][2]


def test_duplicate_ids_across_boundary_two_calls_no_dup_rows(som, monkeypatch):
    from utils.fetch_in import fetch_all_in
    som.tables["sales_order_items"] = [{"soi_id": i, "so_id": i} for i in range(1, 61)]
    calls = _calls(monkeypatch)
    rows, tr = fetch_all_in("sales_order_items", "soi_id", "so_id", list(range(1, 51)) + [50, 51])
    assert len(calls) == 2 and tr is False
    assert sorted(r["soi_id"] for r in rows) == list(range(1, 52))


def test_machine_capability_sets_same_as_old_60_chunks(som):
    """설비 스케줄 가능 장비: 예전 60개 묶음 → 50개 묶음. pn 51개·runs 동률에서 (pn, process)→장비 집합 동일."""
    from utils.fetch_in import fetch_all_in
    pns = [f"PN{i:03d}" for i in range(51)]
    rows, k = [], 0
    for p in pns:
        for mc, runs in (("CNC01", 5), ("CNC02", 5), ("MCT01", 3)):      # 동률 2건
            k += 1
            rows.append({"pom_id": k, "pn": p, "process": f"{p}#10", "machine_id": mc, "runs": runs})
    som.tables["product_op_machine"] = rows

    old = {}
    for i0 in range(0, len(pns), 60):
        for m in db.fetch("product_op_machine", "pn,process,machine_id,runs",
                          "pn=in.({})&order=runs.desc".format(",".join(f'"{p}"' for p in pns[i0:i0 + 60])),
                          limit=1000):
            old.setdefault((m["pn"], m["process"]), set()).add(m["machine_id"])
    new = {}
    got, tr = fetch_all_in("product_op_machine", "pn,process,machine_id,runs", "pn", pns,
                           quote=True, order="runs.desc")
    for m in got:
        new.setdefault((m["pn"], m["process"]), set()).add(m["machine_id"])
    assert tr is False and new == old and len(new) == 51


# ── r2-1 주간 계획: 기존 행 + 절단 → 저장 버튼 존재·비활성, 쓰기 0 ──

def _wp_save_buttons(at):
    return [b for b in at.button if b.label == "저장" and "wp_form" in str(getattr(b, "form_id", ""))]


@app_only
def test_weekly_plan_truncated_existing_rows_save_disabled_and_no_writes(plan_db, monkeypatch):
    from tests import test_weekly_plan_page as wp
    _trunc_when(monkeypatch, lambda t, s, f: t == "production_plan_items")
    at = wp._open(plan_db)
    assert any("이 주 계획 행이 너무 많아" in str(w.value) for w in at.warning), \
        [str(w.value) for w in at.warning]
    sv = _wp_save_buttons(at)
    assert sv and all(b.disabled for b in sv), [(b.label, b.disabled) for b in sv]
    try:                                        # 비활성 버튼 강제 클릭 시도(AppTest 가 거부하면 그대로)
        sv[0].click().run()
    except Exception:
        pass
    assert not at.exception, [str(e.value) for e in at.exception]
    assert wp.CALLS["rpc"] == [] and wp.CALLS["insert"] == [] and wp.CALLS["update"] == [] \
        and wp.CALLS["delete"] == [], wp.CALLS


@app_only
def test_weekly_plan_complete_contrast_save_enabled(plan_db):
    from tests import test_weekly_plan_page as wp
    at = wp._open(plan_db)
    sv = _wp_save_buttons(at)
    assert sv and not any(b.disabled for b in sv)
    assert not any("이 주 계획 행이 너무 많아" in str(w.value) for w in at.warning)


# ── r2-1 출고 등록: ① 작성중 전표 추가 선택지 미노출 ② 등록 직전 재확인 절단 → 등록 중단 ──

def _bd_new_line():
    from tests import test_bulk_delivery as bd
    bd.SOS.append({"so_id": 102, "so_number": "SO-102", "customer": "미진정밀", "status": "CONFIRMED",
                   "so_date": "2026-07-03", "due_date": None})
    bd.LINES[13] = {"soi_id": 13, "so_id": 102, "canonical_pn": "4PDVN-03", "customer_part_no": None,
                    "customer_item_name": None, "product_id": "P1", "qty": 100, "received_qty": 0,
                    "pending_qty": 100, "unit": "EA", "unit_price": 1000, "due_date": None}
    bd.ROUNDS.append({"sched_id": 4, "soi_id": 13, "so_id": 102, "seq": 1, "due_date": bd.TODAY,
                      "qty": 100, "delivered_qty": 0})
    db.clear_cache()


def _bd_cleanup():
    from tests import test_bulk_delivery as bd
    bd.SOS[:] = [s for s in bd.SOS if s["so_id"] != 102]
    bd.LINES.pop(13, None)
    bd.ROUNDS[:] = [r for r in bd.ROUNDS if r["sched_id"] != 4]


@app_only
def test_ship_register_truncated_draft_lines_hide_add_to_draft(ship_db, monkeypatch):
    """test_bulk_delivery.test_add_lines_to_open_draft 의 절단판 — 그 테스트가 대조군(버튼 있음)."""
    from tests import test_bulk_delivery as bd
    at = bd._open_shipping(ship_db)
    bd._register(at)                                  # 전표 1(DRAFT)
    assert len(bd.SHIPMENTS) == 1
    _bd_new_line()
    try:
        _trunc_when(monkeypatch, lambda t, s, f: t == "shipment_items" and s == "si_id,soi_id,shipment_id")
        at2 = bd._open_shipping(ship_db)
        assert not at2.exception, [str(e.value) for e in at2.exception]
        assert not [b for b in at2.button if b.key == "ship_add_draft"]
        assert any("작성중 전표 라인" in str(w.value) and "추가는 잠시 막습니다" in str(w.value)
                   for w in at2.warning), [str(w.value) for w in at2.warning]
        opts = [o for sb in at2.selectbox for o in (sb.options or [])]
        assert not any(bd.SHIPMENTS[0]["ship_no"] in str(o) for o in opts), opts
    finally:
        _bd_cleanup()


@app_only
def test_ship_register_recheck_truncated_stops_registration(ship_db, monkeypatch):
    """등록 직전 재확인(작성중 전표 라인, select soi_id,shipment_id)이 잘리면 등록 중단 — 새 전표·라인 insert 0.
    대조: 같은 흐름에서 절단을 끄면 전표 2 가 생긴다(마지막 단계)."""
    from tests import test_bulk_delivery as bd
    at = bd._open_shipping(ship_db)
    bd._register(at)                                  # 전표 1(DRAFT) — 재확인 분기(_g_drafts) 진입 조건
    _bd_new_line()
    try:
        bd.INSERTED.clear()
        state = {"on": True}
        _trunc_when(monkeypatch, lambda t, s, f: state["on"] and t == "shipment_items"
                    and s == "soi_id,shipment_id")
        at2 = bd._open_shipping(ship_db)
        bd._register(at2)
        assert any("등록 중단 — 작성중 전표 라인" in str(w.value) for w in at2.warning), \
            [str(w.value) for w in at2.warning]
        assert not [t for t, _ in bd.INSERTED if t in ("shipments", "shipment_items")], bd.INSERTED
        assert len(bd.SHIPMENTS) == 1
        state["on"] = False                           # 대조군 — 절단을 끄면 같은 등록이 전표 2
        db.clear_cache()
        at3 = bd._open_shipping(ship_db)
        bd._register(at3)
        assert len(bd.SHIPMENTS) == 2, [s["ship_no"] for s in bd.SHIPMENTS]
    finally:
        _bd_cleanup()


# ── r2-2 출고 전표 _effects(cache=False) · 정정 준비 충당 절단 · 영업 보고 라인 예외 ──

@app_only
def test_slip_recheck_effects_use_cache_false(ship_db, monkeypatch):
    """확정 응답 불명 → 재조회의 반영 흔적(_effects cache=False)이 fetch_all 에 cache=False 로 간다."""
    from tests import test_shipment_confirm_unknown as cu
    monkeypatch.setenv("WS_CF_RECHECK_SEC", "0")
    w = cu.World(ship_db, monkeypatch)
    calls = _calls(monkeypatch)
    cu._confirm(ship_db, monkeypatch, w, w.rpc_seq(cu._transport, cu._ok_commit))
    rec = [(t, kw.get("cache")) for t, _f, kw in calls if t in ("inventory_transactions", "shipment_allocations")]
    assert ("inventory_transactions", False) in rec and ("shipment_allocations", False) in rec, rec


@app_only
def test_sales_report_line_exception_blocks_all_three_tabs(monkeypatch):
    from tests.test_hotfix2_followup_a import _open
    from tests.test_hotfix2_2nd_e_month_close import MONTH_OUTPUTS, _dl
    from tests.test_hotfix2_followup_bcd_r3 import _force_fail, _sales_mock
    m = _sales_mock()
    _force_fail(monkeypatch, "shipment_items")
    at = _open(monkeypatch, m, "sales")
    assert sum("전표 라인 조회 실패" in str(e.value) for e in at.error) >= 3, [str(e.value) for e in at.error]
    assert '<div class="v">미확인</div>' in _kpi_html(at, "총 수량")                 # 일일
    btn = [b for b in at.button if b.key == "sr_mc_close"]
    assert btn and btn[0].disabled                                                  # 마감
    dl = _dl(at)
    assert dl.get("일일 결산 리포트 인쇄") is True
    assert not any(dl.get(k) is False for k in MONTH_OUTPUTS), dl
    assert not any(dl.get(k) is False for k in ("출고 리스트 재발행", "거래명세서 재발행")), dl   # 재발행
    at.session_state["cfm_sr_mc_close"] = True
    at.run()
    assert not [w for w in m.writes if w[1] == "sales_month_close"], m.writes


# P3-1a(2026-11-06): 정정 준비 조회 절단 테스트 2건은 새 경로로 이식 —
#   tests/test_revise_screen.py::test_revision_prep_truncation_calls_nothing[inventory_transactions|shipment_allocations]
#   (취소는 서버가 계산해 준비 조회가 없다 — 절단 검사는 증가 계획의 정정에만)
