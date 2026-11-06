# -*- coding: utf-8 -*-
"""정정·취소 골든 벡터 — P3-1a 커밋 2 (2026-11-06, 계획서 v3 §11-A · §18-2).

`tests/golden/revise_shipment/g_<이름>.json` = {state, request, today, expect: {result, after}}.
같은 파일을 CI 는 `utils.shipment_revise.plan_revision`(파이썬 모델)으로, 로컬 복원 DB 시험(L1)은 실제
`revise_shipment` SQL 로 검증한다. 기대값은 업무 기대값이다 — 검토 세션이 파일을 직접 읽고 승인한다(§18-2 8).

- 골든 다시 만들기: `REGEN_REVISE_GOLDEN=1`(파이썬 모델 결과로 기록 — 검토 세션 승인 전 상태).
- 해시 도장 `HASH.json`: 모델·공용 계산 함수·082 본문의 md5. 코드가 바뀌었는데 도장이 그대로면 실패한다
  (로컬 SQL 등가성 시험을 다시 돌려 도장을 갱신해야 한다 — SQL·파이썬이 어긋난 채 CI 녹색 방지).
- 옛 엔진 대조(05): 커밋 1 의 legacy_*.json 과 같은 세계·요청으로 모델을 돌려 차이를 표로 낸다
  (`test_legacy_differences_are_the_listed_ones` — 계획서 §4-7 의 의도된 차이 밖이면 실패).
"""
import copy
import glob
import hashlib
import json
import os
import uuid

import pytest

from tests.test_revise_legacy_characterize import (SID, SHIP_NO, REASON, base_world, _soi, _rd, _si, _tx, _lot)
from utils import shipment_revise as SR

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLD = os.path.join(ROOT, "tests", "golden", "revise_shipment")
TODAY = "2026-11-06"
WHO = "테스트"
STATE_TABLES = ("shipments", "shipment_items", "shipment_allocations", "inventory_transactions",
                "shipment_revisions", "sales_order_items", "sales_orders", "so_delivery_schedule",
                "product_stock_v", "product_lot_stock_v", "sales_month_close")
AFTER_TABLES = ("shipments", "shipment_items", "shipment_allocations", "inventory_transactions",
                "shipment_revisions", "sales_order_items", "sales_orders", "so_delivery_schedule")
HASH_SOURCES = ("utils/shipment_revise.py", "utils/shipment_adjust.py", "utils/so_close.py",
                "utils/delivery_alloc.py")
SQL_FILE = "supabase/migrations/082_revise_shipment_rpc.sql"


def _rid(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "p3-1a/" + name))


def _state(w):
    return {t: copy.deepcopy(w.get(t, [])) for t in STATE_TABLES}


def _edit(name, w, new_qtys, allow_over=False):
    return _state(w), SR.build_payload(_state(w), SID, new_qtys, REASON, WHO, allow_over, _rid(name), TODAY)


def _cancel(name, w):
    return _state(w), SR.build_payload(_state(w), SID, {}, REASON, WHO, False, _rid(name), TODAY, action="CANCEL")


def _w(**patch):
    w = base_world()
    w.update(patch)
    return w


def _hdr(status, so=100, no="SO-100"):
    return {"so_id": so, "so_number": no, "customer": "㈜엠제이티", "status": status, "so_date": "2026-10-01",
            "due_date": None, "remark": None, "total_amount": 0}


# ── 시나리오: (state, request) — 이름은 파일명 g_<이름>.json ──
def g_cancel_basic(n):
    """A1 취소: 충당 500 해제·LOT W02 200 → W01 300 복원(최초 차감 역순)·수주 납품 0·머리글 DRAFT·전표 CANCELLED."""
    return _cancel(n, _w())


def g_edit_decrease(n):
    """A2 감소 500→400: 회차 1 납품완료 400·충당 400·LOT W02 100 복원."""
    return _edit(n, _w(), {501: 400})


def g_edit_increase(n):
    """A3 증가 500→700: 지정 회차 1 여유 0 → 납품일 회차 → 오래된 회차 2 에 200, LOT W03 선입선출."""
    return _edit(n, _w(), {501: 700})


def g_increase_then_cancel(n):
    """A3 증가 후 취소: 증가로 생긴 충당(회차 2)·ISSUE(W03)까지 전부 되돌린다."""
    st, req = _edit(n + "_inc", _w(), {501: 700})
    res, st2 = SR.plan_revision(st, req, TODAY)
    assert res["ok"], res
    w = {t: st2[t] for t in STATE_TABLES}
    return _cancel(n, w)


def g_edit_mixed_same_soi(n):
    """A4 혼합: 같은 수주 라인 두 줄 300→200·200→300 — 감소 전부 반영 뒤 증가를 회차 1 여유에 싣는다."""
    return _edit(n, _w(shipment_items=[_si(501, 11, 100, 1, "P1", "4PDVN-03", 300),
                                       _si(502, 11, 100, 1, "P1", "4PDVN-03", 200)],
                       shipment_allocations=[{"alloc_id": 1, "si_id": 501, "sched_id": 1, "qty": 300},
                                             {"alloc_id": 2, "si_id": 502, "sched_id": 1, "qty": 200}],
                       inventory_transactions=[_tx(1, 501, "W01", -300), _tx(2, 502, "W02", -200)]),
                 {501: 200, 502: 300})


def g_edit_decrease_d15_first_close(n):
    """A5 머리글 CLOSED·완납 라인 500→400: 라인 CLOSED·closed_qty 100·closed_rounds 스냅샷(환원 전)·회차 qty=delivered."""
    return _edit(n, _w(sales_orders=[_hdr("CLOSED")], sales_order_items=[_soi(11, 100, "P1", "4PDVN-03", 500, 500)],
                       so_delivery_schedule=[_rd(1, 11, 1, "2026-11-01", 500, 500)]), {501: 400})


def g_d15_dup_soi_two_lines(n):
    """Codex 7: 머리글 CLOSED, 같은 수주 라인 두 줄 취소 — 스냅샷은 첫 감소 전 1회(두 번째 줄은 덮지 않음)."""
    return _cancel(n, _w(sales_orders=[_hdr("CLOSED")], sales_order_items=[_soi(11, 100, "P1", "4PDVN-03", 500, 500)],
                         so_delivery_schedule=[_rd(1, 11, 1, "2026-11-01", 300, 300),
                                               _rd(2, 11, 2, "2026-11-10", 200, 200)],
                         shipment_items=[_si(501, 11, 100, 1, "P1", "4PDVN-03", 300),
                                         _si(502, 11, 100, 2, "P1", "4PDVN-03", 200)],
                         shipment_allocations=[{"alloc_id": 1, "si_id": 501, "sched_id": 1, "qty": 300},
                                               {"alloc_id": 2, "si_id": 502, "sched_id": 2, "qty": 200}],
                         inventory_transactions=[_tx(1, 501, "W01", -300), _tx(2, 502, "W02", -200)]))


def g_cancel_closed_line(n):
    """A6 닫힌(CLOSED) 라인 취소: received 만 0, pending 0, closed_qty 2000, 회차 qty=delivered."""
    return _cancel(n, _w(sales_order_items=[_soi(11, 100, "P1", "4PDVN-03", 2000, 500, status="CLOSED",
                                                 closed=1500)]))


def g_edit_decrease_cancelled_line(n):
    """§18-2 1: CANCELLED 라인 감소 500→300: closed_qty = qty − received."""
    return _edit(n, _w(sales_order_items=[_soi(11, 100, "P1", "4PDVN-03", 2000, 500, status="CANCELLED",
                                               closed=1500)]), {501: 300})


def g_cancel_replaced_line(n):
    """A7 대체(REPLACED) 라인 취소: received 만 0, pending 0, closed_qty 그대로(합계 등식 대상 아님 — §18 A1)."""
    return _cancel(n, _w(sales_order_items=[_soi(11, 100, "P1", "4PDVN-03", 2000, 500, status="REPLACED")]))


def g_replaced_sibling(n):
    """§18-2 1: 같은 수주에 합계 등식을 만족하지 않는 REPLACED 형제 라인이 있어도 활성 라인 취소는 통과."""
    w = _w()
    w["sales_order_items"].append(_soi(12, 100, "P1", "4PDVN-03", 1000, 300, status="REPLACED"))
    return _cancel(n, w)


def g_edit_decrease_partial_unalloc(n):
    """A8 부분 미충당(라인 1400 중 충당 1300) 400 감소 — 충당분부터 줄인다."""
    return _edit(n, _w(sales_order_items=[_soi(11, 100, "P1", "4PDVN-03", 2000, 1400)],
                       so_delivery_schedule=[_rd(1, 11, 1, "2026-11-01", 1300, 1300),
                                             _rd(2, 11, 2, "2026-11-10", 700, 0)],
                       shipment_items=[_si(501, 11, 100, 1, "P1", "4PDVN-03", 1400)],
                       shipment_allocations=[{"alloc_id": 1, "si_id": 501, "sched_id": 1, "qty": 1300}],
                       inventory_transactions=[_tx(1, 501, "W01", -1400)]), {501: 1000})


def g_cancel_partial_unalloc(n):
    """A8 부분 미충당 라인 취소 — 충당 1300 해제, 미충당 100 은 안내(unallocated)."""
    return _cancel(n, _w(sales_order_items=[_soi(11, 100, "P1", "4PDVN-03", 2000, 1400)],
                         so_delivery_schedule=[_rd(1, 11, 1, "2026-11-01", 1300, 1300),
                                               _rd(2, 11, 2, "2026-11-10", 700, 0)],
                         shipment_items=[_si(501, 11, 100, 1, "P1", "4PDVN-03", 1400)],
                         shipment_allocations=[{"alloc_id": 1, "si_id": 501, "sched_id": 1, "qty": 1300}],
                         inventory_transactions=[_tx(1, 501, "W01", -1400)]))


def g_reject_round_short(n):
    """A9 충당 500 > 회차 납품완료 300 → round_short(sched 1)."""
    return _cancel(n, _w(so_delivery_schedule=[_rd(1, 11, 1, "2026-11-01", 500, 300),
                                               _rd(2, 11, 2, "2026-11-10", 500, 0)]))


def g_reject_round_short_shared_same_ship(n):
    """§18 A2: 같은 전표 두 줄이 회차 1 에 60 씩(합 120) · 납품완료 100 — 각 줄은 이하지만 회차 합이 초과 → round_short."""
    return _cancel(n, _w(sales_order_items=[_soi(11, 100, "P1", "4PDVN-03", 2000, 120)],
                         so_delivery_schedule=[_rd(1, 11, 1, "2026-11-01", 120, 100)],
                         shipment_items=[_si(501, 11, 100, 1, "P1", "4PDVN-03", 60),
                                         _si(502, 11, 100, 1, "P1", "4PDVN-03", 60)],
                         shipment_allocations=[{"alloc_id": 1, "si_id": 501, "sched_id": 1, "qty": 60},
                                               {"alloc_id": 2, "si_id": 502, "sched_id": 1, "qty": 60}],
                         inventory_transactions=[_tx(1, 501, "W01", -60), _tx(2, 502, "W01", -60)]))


def g_reject_round_short_shared_other_ship(n):
    """§18 A2: 다른 전표(51)의 충당 60 + 이 전표 60 이 회차 1(납품완료 100)을 함께 씀 → 이 전표 취소도 round_short."""
    w = _w(sales_order_items=[_soi(11, 100, "P1", "4PDVN-03", 2000, 120)],
           so_delivery_schedule=[_rd(1, 11, 1, "2026-11-01", 120, 100)],
           shipment_items=[_si(501, 11, 100, 1, "P1", "4PDVN-03", 60)],
           shipment_allocations=[{"alloc_id": 1, "si_id": 501, "sched_id": 1, "qty": 60},
                                 {"alloc_id": 2, "si_id": 601, "sched_id": 1, "qty": 60}],
           inventory_transactions=[_tx(1, 501, "W01", -60)])
    w["shipments"].append(dict(w["shipments"][0], shipment_id=51, ship_no="SH-20261031-01", ship_date="2026-10-31"))
    w["shipment_items"].append(dict(_si(601, 11, 100, 1, "P1", "4PDVN-03", 60), shipment_id=51))
    return _cancel(n, w)


def g_reject_issue_on_sibling(n):
    """A10 같은 수주 라인 두 줄인데 ISSUE 가 한 줄에 몰림 → issue_mismatch(501·502)."""
    return _cancel(n, _w(shipment_items=[_si(501, 11, 100, 1, "P1", "4PDVN-03", 300),
                                         _si(502, 11, 100, 1, "P1", "4PDVN-03", 200)],
                         shipment_allocations=[{"alloc_id": 1, "si_id": 501, "sched_id": 1, "qty": 300},
                                               {"alloc_id": 2, "si_id": 502, "sched_id": 1, "qty": 200}],
                         inventory_transactions=[_tx(1, 501, "W01", -500)]))


def g_reject_lot_over_restore(n):
    """§18 A8: LOT A 순차감 15·LOT B 순 +5(과복원) — 합은 −10 = 라인 수량이지만 LOT 별 과복원 → issue_mismatch."""
    return _cancel(n, _w(sales_order_items=[_soi(11, 100, "P1", "4PDVN-03", 2000, 10)],
                         so_delivery_schedule=[_rd(1, 11, 1, "2026-11-01", 10, 10)],
                         shipment_items=[_si(501, 11, 100, 1, "P1", "4PDVN-03", 10)],
                         shipment_allocations=[{"alloc_id": 1, "si_id": 501, "sched_id": 1, "qty": 10}],
                         inventory_transactions=[_tx(1, 501, "A", -15), _tx(2, 501, "B", 5)]))


def g_reject_recv_underflow(n):
    """A11 수주 납품량 300 < 이 라인이 줄이는 500 → recv_underflow(soi 11)."""
    return _cancel(n, _w(sales_order_items=[_soi(11, 100, "P1", "4PDVN-03", 2000, 300)]))


def g_reject_recv_underflow_by_sum(n):
    """§18 A2: 두 줄(300+300)이 같은 수주 라인(납품 500)을 줄임 — 줄별로는 이하지만 요청 합 600 > 500."""
    return _cancel(n, _w(sales_order_items=[_soi(11, 100, "P1", "4PDVN-03", 2000, 500)],
                         so_delivery_schedule=[_rd(1, 11, 1, "2026-11-01", 600, 600)],
                         shipment_items=[_si(501, 11, 100, 1, "P1", "4PDVN-03", 300),
                                         _si(502, 11, 100, 1, "P1", "4PDVN-03", 300)],
                         shipment_allocations=[{"alloc_id": 1, "si_id": 501, "sched_id": 1, "qty": 300},
                                               {"alloc_id": 2, "si_id": 502, "sched_id": 1, "qty": 300}],
                         inventory_transactions=[_tx(1, 501, "W01", -300), _tx(2, 502, "W01", -300)]))


def g_cancel_all_zero_lines(n):
    """A12 수량 > 0 라인이 없는 확정 전표 취소 — 머리글 이력 1행(si NULL, 0→0)·전표 CANCELLED, 다른 쓰기 없음."""
    return _cancel(n, _w(shipment_items=[_si(501, 11, 100, 1, "P1", "4PDVN-03", 0)], shipment_allocations=[],
                         inventory_transactions=[]))


def g_reject_legacy_no_alloc(n):
    """A13 고정 목록 안(si 4)·충당 0 < 수량 → legacy_no_alloc."""
    w = _w(shipment_allocations=[], inventory_transactions=[_tx(1, 4, "W01", -500)])
    w["shipment_items"] = [_si(4, 11, 100, 1, "P1", "4PDVN-03", 500)]
    return _cancel(n, w)


def g_no_alloc_outside_list(n):
    """A13 목록 밖 충당 0행 라인(si 501) 취소 — 회차 변동 없음 + 미충당 안내(추정으로 회차를 줄이지 않음)."""
    return _cancel(n, _w(shipment_allocations=[]))


def g_unlinked_line_decrease(n):
    """A14 수주 미연결 라인(soi NULL, 제품 연결) 감소 — 수주·회차는 건드리지 않고 LOT 만 복원."""
    return _edit(n, _w(shipment_items=[dict(_si(501, None, None, None, "P1", "4PDVN-03", 500), so_number=None)],
                       shipment_allocations=[]), {501: 400})


def g_reject_unlinked_line_increase(n):
    """A14 수주 미연결 라인 증가 → line_unlinked."""
    st, req = _edit(n, _w(shipment_items=[dict(_si(501, None, None, None, "P1", "4PDVN-03", 500), so_number=None)],
                          shipment_allocations=[]), {501: 600})
    return st, req


def g_increase_unallocated(n):
    """A15 증가분이 회차 여유보다 큼(여유 100) — 회차에 못 실은 100 은 수주 납품만 늘고 unallocated 안내."""
    return _edit(n, _w(so_delivery_schedule=[_rd(1, 11, 1, "2026-11-01", 500, 500),
                                             _rd(2, 11, 2, "2026-11-10", 100, 0)]), {501: 700})


def g_edit_increase_lot_short(n):
    """증가 200, LOT 잔량 50 → W03 50 + LOT 미지정 150(remark 끝 「 (LOT 미지정)」)."""
    return _edit(n, _w(product_lot_stock_v=[_lot("P1", "W03", 50, "2026-10-01")]), {501: 700})


def g_edit_lot_aba(n):
    """§18 A4: 원장 A −5 → B −5 → A −5, 5 감소 → LOT 별 최초 차감 역순이라 B 를 복원(옛 엔진과 같음)."""
    return _edit(n, _w(sales_order_items=[_soi(11, 100, "P1", "4PDVN-03", 2000, 15)],
                       so_delivery_schedule=[_rd(1, 11, 1, "2026-11-01", 15, 15), _rd(2, 11, 2, "2026-11-10", 500, 0)],
                       shipment_items=[_si(501, 11, 100, 1, "P1", "4PDVN-03", 15)],
                       shipment_allocations=[{"alloc_id": 1, "si_id": 501, "sched_id": 1, "qty": 15}],
                       inventory_transactions=[_tx(1, 501, "A", -5), _tx(2, 501, "B", -5), _tx(3, 501, "A", -5)]),
                 {501: 10})


def g_lot_restore_then_reissue(n):
    """§18-2 3: A −10 → (정정 복원) A +5 → (재정정 증가) A −5 → 순 A 10, 4 감소 → A 4 복원."""
    return _edit(n, _w(sales_order_items=[_soi(11, 100, "P1", "4PDVN-03", 2000, 10)],
                       so_delivery_schedule=[_rd(1, 11, 1, "2026-11-01", 10, 10)],
                       shipment_items=[_si(501, 11, 100, 1, "P1", "4PDVN-03", 10)],
                       shipment_allocations=[{"alloc_id": 1, "si_id": 501, "sched_id": 1, "qty": 10}],
                       inventory_transactions=[_tx(1, 501, "A", -10), _tx(2, 501, "A", 5), _tx(3, 501, "A", -5)]),
                 {501: 6})


def g_lot_null(n):
    """§18-2 3: LOT 미지정(NULL) ISSUE 만 있는 라인 취소 — NULL LOT 을 한 LOT 처럼 복원."""
    return _cancel(n, _w(inventory_transactions=[_tx(1, 501, None, -500)]))


def g_edit_due_tie(n):
    """§18 A4: 충당 2행이 납기 같은 회차(1·4) — 200 감소는 동률이면 alloc_id 오름차순(1 먼저)."""
    return _edit(n, _w(so_delivery_schedule=[_rd(1, 11, 1, "2026-11-01", 300, 300),
                                             _rd(4, 11, 2, "2026-11-01", 200, 200),
                                             _rd(2, 11, 3, "2026-11-10", 500, 0)],
                       shipment_allocations=[{"alloc_id": 1, "si_id": 501, "sched_id": 1, "qty": 300},
                                             {"alloc_id": 2, "si_id": 501, "sched_id": 4, "qty": 200}]),
                 {501: 300})


def g_cancel_two_so(n):
    """두 수주에 걸친 전표 취소 — 수주 머리글 2개 재집계(SO-100 DRAFT·SO-200 DRAFT)."""
    w = _w()
    w["sales_orders"].append(_hdr("DELIVERED", so=200, no="SO-200"))
    w["sales_order_items"].append(_soi(21, 200, "P2", "4PDVN-05", 100, 100))
    w["so_delivery_schedule"].append(_rd(21, 21, 1, "2026-11-01", 100, 100, so=200))
    w["shipment_items"].append(_si(502, 21, 200, 21, "P2", "4PDVN-05", 100, so_number="SO-200"))
    w["shipment_allocations"].append({"alloc_id": 2, "si_id": 502, "sched_id": 21, "qty": 100})
    w["inventory_transactions"].append(_tx(3, 502, "V01", -100, pid="P2"))
    return _cancel(n, w)


def g_reject_month_closed(n):
    """월 마감(2026-11) → month_closed."""
    return _cancel(n, _w(sales_month_close=[{"ym": "2026-11", "closed_at": "2026-11-05T00:00:00+00:00",
                                             "closed_by": "관리자", "note": None}]))


def g_reject_partial_cancel_legacy(n):
    """확정인데 CANCEL 이력 있음(옛 부분 취소) → partial_cancel_legacy."""
    return _cancel(n, _w(shipment_revisions=[{"rev_id": 1, "shipment_id": SID, "rev_no": 1, "action": "CANCEL",
                                              "si_id": 501, "pn": "4PDVN-03", "qty_before": 500, "qty_after": 0,
                                              "reason": "옛 취소", "created_by": "테스트", "request_id": None,
                                              "info": None}]))


def g_reject_stale_rev(n):
    """화면이 본 rev_no(0) ≠ 현재(1) → stale_rev."""
    w = _w()
    st, req = _cancel(n, w)
    st["shipments"][0]["rev_no"] = 1
    return st, req


def g_reject_use_cancel(n):
    """수량 > 0 라인을 전부 0 으로 만드는 EDIT → use_cancel."""
    return _edit(n, _w(), {501: 0})


def g_reject_stock(n):
    """증가 200, 재고 100(allow_over 아님) → stock:P1."""
    w = _w(product_stock_v=[{"product_id": "P1", "pn": "4PDVN-03", "customer": "㈜엠제이티", "current_stock": 100}])
    return _edit(n, w, {501: 700})


def g_reject_over_pending(n):
    """증가 1600 > 미납 1500 → over_pending."""
    return _edit(n, _w(so_delivery_schedule=[_rd(1, 11, 1, "2026-11-01", 500, 500),
                                             _rd(3, 11, 2, "2026-11-20", 2000, 0)]), {501: 2100}, allow_over=True)


def g_reject_line_closed_increase(n):
    """닫힌(CLOSED) 수주 라인의 증가 → line_closed."""
    return _edit(n, _w(sales_order_items=[_soi(11, 100, "P1", "4PDVN-03", 2000, 500, status="CLOSED",
                                               closed=1500)]), {501: 600})


def g_replay_same_request(n):
    """같은 request_id·같은 내용 재호출 → replayed(쓰기 없음, 저장된 rev_no·안내)."""
    st, req = _cancel(n, _w())
    res, st2 = SR.plan_revision(st, req, TODAY)
    assert res["ok"], res
    # _requests: 이력 행을 만든 원래 요청 — 로컬 SQL 시험이 id 를 옮긴 뒤 payload_md5 를 다시 계산하는 데 쓴다
    return dict({t: st2[t] for t in STATE_TABLES}, _requests={req["request_id"]: req}), req


def g_reject_request_conflict(n):
    """같은 request_id 인데 사유가 다름 → request_conflict."""
    st, req = _cancel(n, _w())
    res, st2 = SR.plan_revision(st, req, TODAY)
    assert res["ok"], res
    req2 = dict(req, reason="다른 사유")
    return dict({t: st2[t] for t in STATE_TABLES}, _requests={req["request_id"]: req}), req2


def g_reject_stale(n):
    """증가 payload 의 expected_received_before(500)와 잠금 직후 납품량(480 — 화면이 본 뒤 바뀜)이 다름 → stale."""
    st, req = _edit(n, _w(), {501: 700})
    st["sales_order_items"][0]["received_qty"] = 480
    st["sales_order_items"][0]["pending_qty"] = 1520
    return st, req


def g_reject_sched_over(n):
    """증가 payload 가 회차 2(여유 500)에 600 을 싣도록 조작됨 → sched_over."""
    st, req = _edit(n, _w(), {501: 1100})
    req["inc"]["scheds"] = [{"sched_id": 2, "soi_id": 11, "delta": 600}]
    req["inc"]["allocs"] = [{"si_id": 501, "sched_id": 2, "qty": 600}]
    return st, req


def g_reject_bad_version_no_request_id(n):
    """request_id 없음 → bad_version(쓰기 없음)."""
    st, req = _cancel(n, _w())
    req = {k: v for k, v in req.items() if k != "request_id"}
    return st, req


# ── 보고 1 회신(2026-11-06 15:3x) 추가분 ──
def _two_lines(lot_view, stock):
    return _w(shipment_items=[_si(501, 11, 100, 1, "P1", "4PDVN-03", 300),
                              _si(502, 11, 100, 1, "P1", "4PDVN-03", 200)],
              shipment_allocations=[{"alloc_id": 1, "si_id": 501, "sched_id": 1, "qty": 300},
                                    {"alloc_id": 2, "si_id": 502, "sched_id": 1, "qty": 200}],
              inventory_transactions=[_tx(1, 501, "W01", -300), _tx(2, 502, "W02", -200)],
              product_lot_stock_v=lot_view,
              product_stock_v=[{"product_id": "P1", "pn": "4PDVN-03", "customer": "㈜엠제이티", "current_stock": stock}])


def g_move_qty_restored_lot_only(n):
    """같은 제품 두 줄 −100/+100, 뷰 잔량 0·재고 0 → 증가가 같은 요청의 복원 LOT(W01)에서 차감, LOT 미지정 행 없음."""
    return _edit(n, _two_lines([], 0), {501: 200, 502: 300})


def g_move_qty_view_then_restored(n):
    """같은 조건에 뷰 LOT W09 잔량 60 → W09 60 + 복원 LOT W01 40(뷰 LOT 먼저, 복원 LOT 은 뒤)."""
    return _edit(n, _two_lines([_lot("P1", "W09", 60, "2026-10-20")], 60), {501: 200, 502: 300})


def g_edit_increase_own_sched_first(n):
    """지정 회차(1)에 여유 300 이 있는 증가 200 → 지정 회차 먼저(회차 2 는 그대로)."""
    return _edit(n, _w(so_delivery_schedule=[_rd(1, 11, 1, "2026-11-01", 800, 500),
                                             _rd(2, 11, 2, "2026-11-10", 500, 0)]), {501: 700})


def g_edit_increase_completes_line(n):
    """증가로 수주 라인 완납(700/700) → 라인 DELIVERED·pending 0, 머리글 DELIVERED."""
    return _edit(n, _w(sales_order_items=[_soi(11, 100, "P1", "4PDVN-03", 700, 500)],
                       so_delivery_schedule=[_rd(1, 11, 1, "2026-11-01", 500, 500),
                                             _rd(2, 11, 2, "2026-11-10", 200, 0)]), {501: 700})


def g_unlinked_product_decrease(n):
    """제품 미연결 라인(product_id NULL, 수주 연결) 감소 → 수주·회차·충당은 되돌리고 ISSUE 0, 안내 없음."""
    return _edit(n, _w(shipment_items=[dict(_si(501, 11, 100, 1, None, "X-1", 500), product_id=None)],
                       inventory_transactions=[]), {501: 400})


def g_reject_not_found(n):
    """없는 전표 → not_found."""
    st, req = _cancel(n, _w())
    return st, dict(req, shipment_id=999)


def g_reject_not_confirmed_draft(n):
    """작성중 전표 → not_confirmed:DRAFT."""
    st, req = _cancel(n, _w())
    st["shipments"][0]["status"] = "DRAFT"
    return st, req


def g_reject_not_confirmed_cancelled(n):
    """취소 전표(다른 request_id) → not_confirmed:CANCELLED."""
    st, req = _cancel(n, _w())
    st["shipments"][0]["status"] = "CANCELLED"
    return st, req


def g_reject_reason_required(n):
    """사유 공백 → reason_required."""
    st, req = _cancel(n, _w())
    return st, dict(req, reason="   ")


def g_reject_line_other_shipment(n):
    """다른 전표의 라인(601)을 정정 대상으로 보냄 → line_mismatch."""
    w = _w()
    w["shipments"].append(dict(w["shipments"][0], shipment_id=51, ship_no="SH-20261031-01"))
    w["shipment_items"].append(dict(_si(601, 11, 100, 1, "P1", "4PDVN-03", 50), shipment_id=51))
    st, req = _edit(n, w, {501: 400})
    req["lines"] = [{"si_id": 601, "qty_before": 50, "qty_after": 40}]
    return st, req


def g_reject_line_duplicate(n):
    """같은 라인을 두 번 → line_mismatch."""
    st, req = _edit(n, _w(), {501: 400})
    req["lines"] = req["lines"] * 2
    return st, req


def g_reject_bad_version_no_rev(n):
    """expected_rev_no 누락 → bad_version."""
    st, req = _cancel(n, _w())
    return st, {k: v for k, v in req.items() if k != "expected_rev_no"}


def g_reject_sched_mismatch(n):
    """증가 payload 의 회차가 다른 수주 라인의 회차(soi 불일치) → sched_mismatch."""
    w = _w()
    w["sales_order_items"].append(_soi(12, 100, "P1", "4PDVN-03", 100, 0))
    w["so_delivery_schedule"].append(_rd(9, 12, 1, "2026-11-15", 100, 0))
    st, req = _edit(n, w, {501: 700})
    req["inc"]["scheds"] = [{"sched_id": 9, "soi_id": 11, "delta": 200}]
    return st, req


def g_reject_alloc_mismatch(n):
    """회차 증가 200 인데 충당 합 150 → alloc_mismatch."""
    st, req = _edit(n, _w(), {501: 700})
    req["inc"]["allocs"] = [dict(req["inc"]["allocs"][0], qty=150)]
    return st, req


def g_reject_txn_mismatch(n):
    """ISSUE 합(−150) ≠ 증가 200 → txn_mismatch."""
    st, req = _edit(n, _w(), {501: 700})
    req["inc"]["txns"] = [dict(req["inc"]["txns"][0], qty=-150)]
    return st, req


SCEN = {k[2:]: v for k, v in sorted(globals().items()) if k.startswith("g_") and callable(v)}


# ── 정규화·실행 ──
def _norm(o):
    if isinstance(o, dict):
        return {k: _norm(v) for k, v in o.items() if k != "payload_md5"}
    if isinstance(o, list):
        return [_norm(v) for v in o]
    if isinstance(o, float) and o.is_integer():
        return int(o)
    return o


def _sorted_state(st, tables):
    from tests.ship_mock import PK
    return {t: sorted(st.get(t, []), key=lambda r, pk=PK[t]: (r.get(pk) is None, str(r.get(pk)).zfill(12)))
            for t in tables}


def build(name):
    st, req = SCEN[name](name)
    res, after = SR.plan_revision(st, req, TODAY)
    return _norm({"name": name, "doc": (SCEN[name].__doc__ or "").strip(), "today": TODAY, "state": st,
                  "request": req, "expect": {"result": res, "after": _sorted_state(after, AFTER_TABLES)}})


def _code_hash():
    h = hashlib.md5()
    for p in HASH_SOURCES:
        h.update(open(os.path.join(ROOT, p), "rb").read().replace(b"\r\n", b"\n"))
    py = h.hexdigest()
    sql_p = os.path.join(ROOT, SQL_FILE)
    sql = (hashlib.md5(open(sql_p, "rb").read().replace(b"\r\n", b"\n")).hexdigest()
           if os.path.exists(sql_p) else None)
    return py, sql


@pytest.mark.parametrize("name", sorted(SCEN))
def test_golden_vector(name):
    got = build(name)
    path = os.path.join(GOLD, f"g_{name}.json")
    if os.environ.get("REGEN_REVISE_GOLDEN") == "1":
        os.makedirs(GOLD, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(got, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write("\n")
    with open(path, encoding="utf-8") as f:
        want = json.load(f)
    assert json.loads(json.dumps(got, ensure_ascii=False, sort_keys=True)) == want, name


def test_golden_files_have_no_strays():
    names = {os.path.basename(p)[2:-5] for p in glob.glob(os.path.join(GOLD, "g_*.json"))}
    assert names == set(SCEN), (names ^ set(SCEN))


def write_stamp(local_sql_check):
    """도장 기록 — 로컬 SQL 등가성 시험(L1)이 통과 결과와 함께 부른다. 수동: STAMP_REVISE_HASH="메모" 환경 변수."""
    py, sql = _code_hash()
    with open(os.path.join(GOLD, "HASH.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"python": py, "sql": sql, "local_sql_check": local_sql_check}, f, ensure_ascii=False, indent=1)
        f.write("\n")


def test_hash_stamp_matches_code():
    """모델·공용 함수·082 가 바뀌었는데 도장이 그대로면 실패 — 로컬 SQL 등가성(L1)을 다시 돌려 도장을 갱신할 것."""
    path = os.path.join(GOLD, "HASH.json")
    py, sql = _code_hash()
    # 082 가 생기기 전에만 골든 재생성이 도장을 쓴다 — 그 뒤로는 로컬 SQL 등가성 시험(L1)만 갱신한다
    if os.environ.get("REGEN_REVISE_GOLDEN") == "1" and sql is None:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"python": py, "sql": sql, "local_sql_check": None}, f, indent=1)
            f.write("\n")
    if os.environ.get("STAMP_REVISE_HASH"):
        write_stamp(os.environ["STAMP_REVISE_HASH"])
    stamp = json.load(open(path, encoding="utf-8"))
    assert stamp["python"] == py, "파이썬 모델·공용 계산 함수가 바뀜 — 골든·로컬 SQL 등가성을 다시 확인하고 도장 갱신"
    assert stamp["sql"] == sql, "082 본문이 바뀜(또는 새로 생김) — 로컬 SQL 등가성(L1)을 다시 돌려 도장 갱신"


# ── 옛 엔진 대조(05) ──
# 계획서 §4-7(+§18) 의 의도된 차이 — 이 밖의 차이는 실패
INTENDED = {
    "cancel_issue_on_sibling": "§4-7 #4 형제 차감 → issue_mismatch 거부",
    "cancel_round_short": "§4-7 #5 충당 > 납품완료 → round_short 거부",
    "cancel_all_zero_lines": "§4-7 #9 전 라인 0 확정 전표도 취소(머리글 이력 1행)",
    "cancel_legacy_no_alloc": "§4-5 목록 밖 충당 0행: 추정으로 회차를 줄이지 않음(회차 변동 없음 + 미충당 안내) — §4-7 #3 의 짝",
}


def _legacy_compare(name):
    d = json.load(open(os.path.join(GOLD, f"legacy_{name}.json"), encoding="utf-8"))
    st = _state(d["world"])
    if d["action"] == "EDIT":
        req = SR.build_payload(st, SID, {int(k): v for k, v in d["new_qtys"].items()}, d["reason"], WHO,
                               d["allow_over"], _rid("legacy/" + name), "<TODAY>")
    else:
        req = SR.build_payload(st, SID, {}, d["reason"], WHO, False, _rid("legacy/" + name), "<TODAY>",
                               action="CANCEL")
    res, after = SR.plan_revision(st, req, "<TODAY>", now="<NOW>")
    if not res["ok"]:
        return {"result": res["error"]}
    diffs = {}
    for t in AFTER_TABLES:
        new_rows = _canon(t, after.get(t, []))
        old_rows = _canon(t, d["after"].get(t, []))
        if new_rows != old_rows:
            diffs[t] = {"legacy": [r for r in old_rows if r not in new_rows],
                        "new": [r for r in new_rows if r not in old_rows]}
    return diffs


def _canon(t, rows):
    """비교에서 빼는 것: 발급 PK(insert 순서가 다르다)·새 열(request_id·info)."""
    drop = {"shipment_allocations": ("alloc_id",), "inventory_transactions": ("txn_id",),
            "shipment_revisions": ("rev_id", "request_id", "info")}.get(t, ())
    out = [{k: (int(v) if isinstance(v, float) and v.is_integer() else v) for k, v in r.items() if k not in drop}
           for r in rows]
    return sorted(out, key=lambda r: json.dumps(r, sort_keys=True, ensure_ascii=False))


LEGACY_NAMES = sorted(os.path.basename(p)[7:-5] for p in glob.glob(os.path.join(GOLD, "legacy_*.json")))


@pytest.mark.parametrize("name", LEGACY_NAMES)
def test_legacy_differences_are_the_listed_ones(name):
    diffs = _legacy_compare(name)
    if name in INTENDED:
        assert diffs, f"{name}: 의도된 차이({INTENDED[name]})가 사라짐"
    else:
        assert not diffs, f"{name}: §4-7 밖의 차이 — {json.dumps(diffs, ensure_ascii=False)[:1500]}"


def legacy_diff_table():
    """05 옛 엔진 대조표(README 용) — `python -c "from tests.test_revise_golden import legacy_diff_table as t; t()"`."""
    for name in LEGACY_NAMES:
        d = _legacy_compare(name)
        print(f"| {name} | {'같음' if not d else json.dumps(d, ensure_ascii=False)[:400]} | {INTENDED.get(name, '')} |")


# ── 보조 함수 ──
def test_request_md5_ignores_who_and_line_order():
    a = {"action": "EDIT", "reason": "사유", "allow_over": False, "who": "갑",
         "lines": [{"si_id": 2, "qty_before": 5, "qty_after": 3}, {"si_id": 1, "qty_before": 4.0, "qty_after": 6}]}
    b = dict(a, who="을", lines=list(reversed(a["lines"])))
    assert SR.request_md5(a) == SR.request_md5(b)
    assert SR.request_md5(a) != SR.request_md5(dict(a, allow_over=True))
    assert SR.request_md5(a) != SR.request_md5(dict(a, reason="다른"))
    inc = {"expected_received_before": [{"soi_id": 11, "received": 500}],
           "txns": [{"si_id": 1, "product_id": "P1", "qty": -2, "unit": "EA", "lot_number": "A", "work_order": "A"}]}
    c = dict(a, inc=inc)
    d = dict(a, inc=dict(inc, txns=[dict(inc["txns"][0], lot_number="B", work_order="B")]))
    assert SR.request_md5(c) != SR.request_md5(d)            # LOT 만 달라도 다른 요청(Codex M1)


def test_check_reports_fixed_reasons_per_line():
    st, _ = g_reject_issue_on_sibling("x")
    r = SR.check(st, SID)
    assert r["ok"] and r["lines"] == {501: ["issue_mismatch"], 502: ["issue_mismatch"]}, r
    st, _ = g_reject_round_short_shared_other_ship("x")
    assert SR.check(st, SID)["lines"] == {501: ["round_short"]}
    st, _ = g_reject_recv_underflow("x")
    assert SR.check(st, SID)["lines"] == {}                   # 요청별 사유는 사전 점검에 없음(§18 A9)
    st, _ = g_reject_month_closed("x")
    assert SR.check(st, SID)["month_closed"] is True
    st, _ = g_reject_partial_cancel_legacy("x")
    assert SR.check(st, SID)["partial_cancel_legacy"] is True


def test_tag_matches_legacy_text():
    assert SR.tag("CANCEL", SHIP_NO, "SO-100", REASON) == f"출고 취소 {SHIP_NO}: SO-100 ({REASON})"
    assert SR.tag("EDIT", SHIP_NO, None, REASON) == f"출고 정정 {SHIP_NO}: - ({REASON})"
