# -*- coding: utf-8 -*-
"""옛 정정·취소 엔진(`_cf_apply_deltas`) 특성화 — P3-1a 커밋 1 (2026-11-06).

새 함수 `revise_shipment`(082)·`plan_revision` 으로 바꾸기 전에, 옛 엔진이 실제로 만드는 결과 행을
시나리오별로 `tests/golden/revise_shipment/legacy_<이름>.json` 에 남긴다. 새 경로는 계획서 §4-7(+§18)의
의도된 차이만 빼고 이 결과와 같아야 한다(대조군 — 05 옛 엔진 대조표).

- 실행: 출고 관리 › 출고 전표 › 확정 전표 화면을 AppTest 로 열고, 정정은 `cf_rv_plan` 세션 주입 + 확인 창,
  취소는 [전표 취소] + 확인 창으로 옛 엔진을 그대로 탄다(앱 코드 무변경). 목 DB = tests/ship_mock.ShipMock.
- 골든 다시 만들기: `REGEN_LEGACY_GOLDEN=1` 환경 변수. 평소에는 저장된 골든과 비교한다.
- 옛 엔진이 삭제된 뒤(P3-1a 커밋 6)에는 건너뛴다 — 결과는 골든 파일에 남는다(태그 p3-1a-legacy-baseline).
"""
import copy
import datetime as _dt
import importlib.util
import json
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_FILE = os.path.join(ROOT, "streamlit_app.py")
GOLD = os.path.join(ROOT, "tests", "golden", "revise_shipment")
_HAS_ST = importlib.util.find_spec("streamlit") is not None
_HAS_ENGINE = "def _cf_apply_deltas(" in open(APP_FILE, encoding="utf-8").read()
pytestmark = [pytest.mark.skipif(not _HAS_ST, reason="streamlit 미설치 — AppTest 불가"),
              pytest.mark.skipif(not _HAS_ENGINE, reason="옛 엔진 삭제됨(P3-1a) — 결과는 legacy_*.json 에 보존")]

SID, SHIP_NO, SHIP_DATE = 50, "SH-20261101-01", "2026-11-01"
REASON = "거래처 착오"


# ── 기본 세계: 수주 SO-100(라인 soi 11, 4PDVN-03) · 확정 전표 1장(라인 si 501 500개) ──
def base_world():
    return {
        "products": [{"product_id": "P1", "pn": "4PDVN-03", "archived_at": None},
                     {"product_id": "P2", "pn": "4PDVN-05", "archived_at": None}],
        "sales_orders": [{"so_id": 100, "so_number": "SO-100", "customer": "㈜엠제이티", "status": "PARTIAL",
                          "so_date": "2026-10-01", "due_date": None, "remark": None, "total_amount": 0}],
        "sales_order_items": [_soi(11, 100, "P1", "4PDVN-03", 2000, 500)],
        "so_delivery_schedule": [_rd(1, 11, 1, "2026-11-01", 500, 500), _rd(2, 11, 2, "2026-11-10", 500, 0),
                                 _rd(3, 11, 3, "2026-11-20", 1000, 0)],
        "shipments": [{"shipment_id": SID, "ship_no": SHIP_NO, "ship_date": SHIP_DATE, "status": "CONFIRMED",
                       "remark": None, "created_by": "테스트", "created_at": "2026-11-01T01:00:00+00:00",
                       "confirmed_at": "2026-11-01T01:05:00+00:00", "rev_no": 0, "revised_at": None,
                       "cancelled_at": None, "cancel_reason": None}],
        "shipment_items": [_si(501, 11, 100, 1, "P1", "4PDVN-03", 500)],
        "shipment_allocations": [{"alloc_id": 1, "si_id": 501, "sched_id": 1, "qty": 500}],
        "inventory_transactions": [_tx(1, 501, "W01", -300), _tx(2, 501, "W02", -200)],
        "shipment_revisions": [],
        "product_stock_v": [{"product_id": "P1", "pn": "4PDVN-03", "customer": "㈜엠제이티", "current_stock": 1000},
                            {"product_id": "P2", "pn": "4PDVN-05", "customer": "㈜엠제이티", "current_stock": 1000}],
        "product_lot_stock_v": [_lot("P1", "W03", 300, "2026-10-01"), _lot("P1", "W04", 700, "2026-10-05")],
        "sales_month_close": [],
    }


def _soi(soi, so, pid, pn, qty, recv, status=None, closed=0, closed_rounds=None):
    st = status or ("DELIVERED" if recv >= qty else "PARTIAL" if recv > 0 else "PENDING")
    pend = 0 if st in ("CLOSED", "CANCELLED", "REPLACED") else max(qty - recv, 0)
    return {"soi_id": soi, "so_id": so, "line_no": 1, "product_id": pid, "canonical_pn": pn,
            "customer_part_no": "4S" + pn, "customer_item_name": None, "qty": qty, "received_qty": recv,
            "pending_qty": pend, "status": st, "unit": "EA", "unit_price": 1000, "closed_qty": closed,
            "closed_rounds": closed_rounds, "close_reason": None, "replaced_by_soi": None, "presched_qty": 0,
            "due_date": None}


def _rd(sched, soi, seq, due, qty, delivered, so=100):
    return {"sched_id": sched, "so_id": so, "soi_id": soi, "seq": seq, "due_date": due, "qty": qty,
            "delivered_qty": delivered, "note": None}


def _si(si, soi, so, sched, pid, pn, qty, so_number="SO-100"):
    return {"si_id": si, "shipment_id": SID, "soi_id": soi, "so_id": so, "sched_id": sched, "product_id": pid,
            "pn": pn, "customer_pn": "4S" + pn, "item_name": None, "customer": "㈜엠제이티",
            "so_number": so_number, "qty": qty, "unit": "EA", "unit_price": 1000}


def _tx(txn, ref, lot, qty, pid="P1"):
    return {"txn_id": txn, "material_id": None, "product_id": pid, "txn_type": "ISSUE", "qty": qty, "unit": "EA",
            "lot_number": lot, "work_order": lot, "ref_table": "shipment_items", "ref_id": ref,
            "txn_date": SHIP_DATE, "remark": f"출고 {SHIP_NO}: SO-100", "created_by": "테스트"}


def _lot(pid, lot, remain, first):
    return {"product_id": pid, "lot_number": lot, "remain_qty": remain, "first_output_date": first}


# ── 시나리오 ──
def _w(**patch):
    w = base_world()
    for k, v in patch.items():
        w[k] = v
    return w


def sc_cancel_basic():
    return _w(), ("CANCEL", None, False)


def sc_edit_decrease():
    return _w(), ("EDIT", {501: 400}, False)


def sc_edit_increase():
    """+200: 지정 회차(1) 여유 0 → 납품일 회차 → 오래된 회차(2)에 충당, LOT 선입선출 W03."""
    return _w(), ("EDIT", {501: 700}, False)


def sc_edit_increase_lot_short():
    """+200, LOT 잔량 50 뿐 → W03 50 + LOT 미지정 150 (재고 검사는 product_stock_v 1000 으로 통과)."""
    return _w(product_lot_stock_v=[_lot("P1", "W03", 50, "2026-10-01")]), ("EDIT", {501: 700}, False)


def sc_edit_mixed_same_soi():
    """같은 수주 라인 두 줄: si 501 300→200(감소 100), si 502 200→300(증가 100)."""
    return _w(shipment_items=[_si(501, 11, 100, 1, "P1", "4PDVN-03", 300),
                              _si(502, 11, 100, 1, "P1", "4PDVN-03", 200)],
              shipment_allocations=[{"alloc_id": 1, "si_id": 501, "sched_id": 1, "qty": 300},
                                    {"alloc_id": 2, "si_id": 502, "sched_id": 1, "qty": 200}],
              inventory_transactions=[_tx(1, 501, "W01", -300), _tx(2, 502, "W02", -200)]), \
        ("EDIT", {501: 200, 502: 300}, False)


def sc_edit_lot_aba():
    """원장 A −5 → B −5 → A −5(라인 15), 5 감소 → 옛 엔진은 LOT 최초 차감 순서의 역순(B 먼저)."""
    return _w(sales_order_items=[_soi(11, 100, "P1", "4PDVN-03", 2000, 15)],
              so_delivery_schedule=[_rd(1, 11, 1, "2026-11-01", 15, 15), _rd(2, 11, 2, "2026-11-10", 500, 0)],
              shipment_items=[_si(501, 11, 100, 1, "P1", "4PDVN-03", 15)],
              shipment_allocations=[{"alloc_id": 1, "si_id": 501, "sched_id": 1, "qty": 15}],
              inventory_transactions=[_tx(1, 501, "A", -5), _tx(2, 501, "B", -5), _tx(3, 501, "A", -5)]), \
        ("EDIT", {501: 10}, False)


def sc_edit_due_tie():
    """충당 2행이 납기 같은 회차(1·4)에 → 200 감소: 납기 최근순 안정 정렬(동률은 alloc_id 오름차순)."""
    return _w(so_delivery_schedule=[_rd(1, 11, 1, "2026-11-01", 300, 300), _rd(4, 11, 2, "2026-11-01", 200, 200),
                                    _rd(2, 11, 3, "2026-11-10", 500, 0)],
              shipment_allocations=[{"alloc_id": 1, "si_id": 501, "sched_id": 1, "qty": 300},
                                    {"alloc_id": 2, "si_id": 501, "sched_id": 4, "qty": 200}]), \
        ("EDIT", {501: 300}, False)


def sc_edit_decrease_d15():
    """머리글 CLOSED, 라인 완납(500/500) → 100 감소: 라인 CLOSED·closed_qty 100·closed_rounds 스냅샷·회차 qty 정리."""
    return _w(sales_orders=[{"so_id": 100, "so_number": "SO-100", "customer": "㈜엠제이티", "status": "CLOSED",
                             "so_date": "2026-10-01", "due_date": None, "remark": None, "total_amount": 0}],
              sales_order_items=[_soi(11, 100, "P1", "4PDVN-03", 500, 500)],
              so_delivery_schedule=[_rd(1, 11, 1, "2026-11-01", 500, 500)]), ("EDIT", {501: 400}, False)


def sc_cancel_replaced_line():
    return _w(sales_order_items=[_soi(11, 100, "P1", "4PDVN-03", 2000, 500, status="REPLACED")]), \
        ("CANCEL", None, False)


def sc_cancel_closed_line():
    return _w(sales_order_items=[_soi(11, 100, "P1", "4PDVN-03", 2000, 500, status="CLOSED", closed=1500)]), \
        ("CANCEL", None, False)


def sc_cancel_legacy_no_alloc():
    """충당 기록 없음(옛 전표) → 지정 회차 → 최근 납품 회차 추정(새 함수는 legacy_no_alloc 거부)."""
    return _w(shipment_allocations=[]), ("CANCEL", None, False)


def sc_cancel_issue_on_sibling():
    """같은 수주 라인 두 줄인데 ISSUE 가 한 줄(501)에 몰림 → 501 은 300 만 복원, 502 는 차감 기록 없음(issue_mismatch)."""
    return _w(shipment_items=[_si(501, 11, 100, 1, "P1", "4PDVN-03", 300),
                              _si(502, 11, 100, 1, "P1", "4PDVN-03", 200)],
              shipment_allocations=[{"alloc_id": 1, "si_id": 501, "sched_id": 1, "qty": 300},
                                    {"alloc_id": 2, "si_id": 502, "sched_id": 1, "qty": 200}],
              inventory_transactions=[_tx(1, 501, "W01", -500)]), ("CANCEL", None, False)


def sc_cancel_round_short():
    """충당 500 인데 회차 납품완료 300 → 300 만 되돌리고 충당 200 남음(round_short)."""
    return _w(so_delivery_schedule=[_rd(1, 11, 1, "2026-11-01", 500, 300), _rd(2, 11, 2, "2026-11-10", 500, 0)]), \
        ("CANCEL", None, False)


def sc_edit_decrease_partial_unalloc():
    """라인 1400 중 충당 1300(유형 D) → 400 감소: 충당분부터 줄임."""
    return _w(sales_order_items=[_soi(11, 100, "P1", "4PDVN-03", 2000, 1400)],
              so_delivery_schedule=[_rd(1, 11, 1, "2026-11-01", 1300, 1300), _rd(2, 11, 2, "2026-11-10", 700, 0)],
              shipment_items=[_si(501, 11, 100, 1, "P1", "4PDVN-03", 1400)],
              shipment_allocations=[{"alloc_id": 1, "si_id": 501, "sched_id": 1, "qty": 1300}],
              inventory_transactions=[_tx(1, 501, "W01", -1400)]), ("EDIT", {501: 1000}, False)


def sc_cancel_all_zero_lines():
    """수량 > 0 라인이 없는 확정 전표 → 옛 엔진은 '변경된 수량이 없습니다'(새 함수는 머리글 이력으로 취소)."""
    return _w(shipment_items=[_si(501, 11, 100, 1, "P1", "4PDVN-03", 0)], shipment_allocations=[],
              inventory_transactions=[]), ("CANCEL", None, False)


def sc_cancel_two_so():
    """두 수주(SO-100·SO-200)에 걸친 전표 취소 — 머리글 재집계 2건."""
    w = _w()
    w["sales_orders"].append({"so_id": 200, "so_number": "SO-200", "customer": "㈜엠제이티", "status": "DELIVERED",
                              "so_date": "2026-10-02", "due_date": None, "remark": None, "total_amount": 0})
    w["sales_order_items"].append(_soi(21, 200, "P2", "4PDVN-05", 100, 100))
    w["so_delivery_schedule"].append(_rd(21, 21, 1, "2026-11-01", 100, 100, so=200))
    w["shipment_items"].append(_si(502, 21, 200, 21, "P2", "4PDVN-05", 100, so_number="SO-200"))
    w["shipment_allocations"].append({"alloc_id": 2, "si_id": 502, "sched_id": 21, "qty": 100})
    w["inventory_transactions"].append(_tx(3, 502, "V01", -100, pid="P2"))
    return w, ("CANCEL", None, False)


SCENARIOS = {n[3:]: f for n, f in sorted(globals().items()) if n.startswith("sc_") and callable(f)}


# ── 실행 ──
def _run(monkeypatch, world, action):
    import db as _dbmod
    from streamlit.testing.v1 import AppTest
    from tests.conftest import goto
    from tests.ship_mock import ShipMock
    m = ShipMock(world).install(monkeypatch, _dbmod)
    before = m.snapshot()
    at = AppTest.from_file(APP_FILE, default_timeout=120)
    at.secrets["supabase"] = {"url": "https://mock.local", "anon_key": "a", "service_role_key": "s"}
    at.secrets["auth"] = {"disabled": True}
    at.run()
    goto(at, "ship", "slip")
    next(r for r in at.radio if r.key == "cf_filter").set_value("확정")
    at.session_state["ship_open_no"] = SHIP_NO
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    kind, new_qtys, over = action
    if kind == "EDIT":
        at.session_state["cfm_cf_rv"] = True
        at.session_state["cf_rv_plan"] = ({int(k): float(v) for k, v in new_qtys.items()}, REASON, over)
        at.run()
        at.button(key="cf_rv_cfm_ok").click()
    else:
        at.text_input(key=f"cf_cx_reason_{SID}").set_value(REASON)
        at.run()
        at.button(key="cf_cancel").click()
        at.run()
        assert not at.exception, [str(e.value) for e in at.exception]
        at.button(key="cf_cancel_cfm_ok").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    msgs = ([("success", str(x.value)) for x in at.success] + [("warning", str(x.value)) for x in at.warning]
            + [("error", str(x.value)) for x in at.error] + [("toast", str(x.value)) for x in at.toast])
    return before, m.snapshot(), [w for w in m.writes if w[0] in ("insert", "update", "delete")], msgs


_TODAY = _dt.date.today().isoformat()
_NOW_KEYS = ("revised_at", "cancelled_at")


def _norm(obj):
    """오늘 날짜·현재 시각을 고정 표기로(골든이 실행일에 따라 바뀌지 않게)."""
    if isinstance(obj, dict):
        return {k: ("<NOW>" if k in _NOW_KEYS and isinstance(v, str) and v else _norm(v)) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_norm(v) for v in obj]
    if isinstance(obj, str):
        return obj.replace(_TODAY, "<TODAY>")
    if isinstance(obj, float) and obj.is_integer():
        return int(obj)
    return obj


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_legacy_engine_characterized(monkeypatch, name):
    world, action = SCENARIOS[name]()
    doc_world = copy.deepcopy(world)
    before, after, writes, msgs = _run(monkeypatch, world, action)
    got = _norm({
        "name": name, "doc": (SCENARIOS[name].__doc__ or "").strip(),
        "action": action[0], "reason": REASON, "new_qtys": {str(k): v for k, v in (action[1] or {}).items()},
        "allow_over": action[2], "world": doc_world, "before": before, "after": after,
        "writes": [list(w) for w in writes], "messages": msgs})
    path = os.path.join(GOLD, f"legacy_{name}.json")
    if os.environ.get("REGEN_LEGACY_GOLDEN") == "1":
        os.makedirs(GOLD, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(got, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write("\n")
    with open(path, encoding="utf-8") as f:
        want = json.load(f)
    assert json.loads(json.dumps(got, ensure_ascii=False, sort_keys=True)) == want, name


def test_legacy_scenarios_cover_required():
    """지시문 r1 커밋 1: 부분 감소 · 증가 · 증감 혼합 · A→B→A LOT · 납기 동률 · 취소."""
    need = {"edit_decrease", "edit_increase", "edit_mixed_same_soi", "edit_lot_aba", "edit_due_tie", "cancel_basic"}
    assert need <= set(SCENARIOS), need - set(SCENARIOS)
    assert re.search(r"def _cf_apply_deltas\(", open(APP_FILE, encoding="utf-8").read())
