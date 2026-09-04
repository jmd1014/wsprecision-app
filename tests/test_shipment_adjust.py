# -*- coding: utf-8 -*-
"""확정 전표 정정 — 차이만 되돌리는 계산 검증."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.shipment_adjust import (  # noqa: E402
    net_issued_by_lot, plan_lot_restore, plan_round_release,
    plan_line_deltas, split_round_alloc, line_status, rev_label)


TXNS = [
    {"txn_id": 1, "lot_number": "W01", "qty": -600},
    {"txn_id": 2, "lot_number": "W02", "qty": -400},
    {"txn_id": 3, "lot_number": "W02", "qty": 100},   # 이전 정정 복원
]


def test_net_issued_by_lot_nets_restores():
    assert net_issued_by_lot(TXNS) == [("W01", 600), ("W02", 300)]


def test_lot_restore_lifo_and_bounded():
    plan, rest = plan_lot_restore(TXNS, 500)
    assert plan == [("W02", 300), ("W01", 200)]
    assert rest == 0
    plan, rest = plan_lot_restore(TXNS, 1000)
    assert sum(q for _, q in plan) == 900 and rest == 100


def test_round_release_uses_saved_allocations_latest_first():
    allocs = [{"alloc_id": 1, "sched_id": 1, "qty": 300},
              {"alloc_id": 2, "sched_id": 2, "qty": 200}]
    rounds = [{"sched_id": 1, "due_date": "2026-09-01",
               "delivered_qty": 300},
              {"sched_id": 2, "due_date": "2026-09-08",
               "delivered_qty": 200}]
    new_del, upd, rest = plan_round_release(allocs, rounds, 250)
    assert new_del == {2: 0, 1: 250}
    assert upd == [(2, 0), (1, 250)]
    assert rest == 0


def test_round_release_legacy_prefers_line_sched():
    rounds = [{"sched_id": 1, "due_date": "2026-09-01",
               "delivered_qty": 100},
              {"sched_id": 2, "due_date": "2026-09-08",
               "delivered_qty": 500}]
    new_del, upd, rest = plan_round_release([], rounds, 150,
                                            line_sched_id=1)
    assert new_del == {1: 0, 2: 450} and upd == [] and rest == 0


def test_round_release_reports_unreleasable():
    rounds = [{"sched_id": 1, "due_date": "2026-09-01",
               "delivered_qty": 50}]
    _, _, rest = plan_round_release([], rounds, 80)
    assert rest == 30


def test_line_deltas_only_changes():
    items = [{"si_id": 1, "qty": 100}, {"si_id": 2, "qty": 50}]
    d = plan_line_deltas(items, {1: 80, 2: 50})
    assert [(x["si_id"], o, n, dl) for x, o, n, dl in d] == \
        [(1, 100, 80, -20)]


def test_split_round_alloc_prefers_line_sched():
    out = split_round_alloc([(10, 300, 2), (11, 200, None)],
                            {1: 200, 2: 300})
    assert out == [(10, 2, 300), (11, 1, 200)]


def test_line_status_and_rev_label():
    assert line_status(100, 100) == "DELIVERED"
    assert line_status(100, 30) == "PARTIAL"
    assert line_status(100, 0) == "PENDING"
    assert rev_label(0) is None
    assert rev_label(2, "2026-09-04T10:00") == "정정본 v3 · 2026-09-04"
