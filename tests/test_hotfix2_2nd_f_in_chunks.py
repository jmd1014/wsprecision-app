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
def test_revision_prep_truncation_writes_nothing(rev_db, monkeypatch):
    """정정 준비(LOT·충당) 조회가 잘리면 정정 중단 — 역분개·회차 되돌림 쓰기 0."""
    from tests import test_shipment_revision_flow as rf
    _trunc_when(monkeypatch, lambda t, s, f: t == "inventory_transactions" and "lot_number" in s)
    rf._seed()
    at = rf._pick_confirmed(rf._open())
    at.text_input(key="cf_cx_reason_1").set_value("거래처 착오")
    at.run()
    at.button(key="cf_cancel").click()
    at.run()
    at.button(key="cf_cancel_cfm_ok").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert any("정정 준비 조회" in str(e.value) for e in at.error), [str(e.value) for e in at.error]
    assert not [t for t, _ in rf.INSERTED if t in ("inventory_transactions", "shipment_revisions")]
    assert not [1 for t, _f, _v in rf.UPDATED if t in ("so_delivery_schedule", "sales_order_items")]
    assert rf.SHIPMENTS[0]["status"] == "CONFIRMED"


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
