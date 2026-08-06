# -*- coding: utf-8 -*-
"""회차 충당 규칙 단위 검증 — 납품일 우선 + 오래된 회차 만회."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.delivery_alloc import allocate_rounds  # noqa: E402


def _rounds():
    """4PDVN-03 실사례: 7/29·7/31·8/3·8/5 회차 (8/3 은 800)"""
    return [
        {"sched_id": 65, "due_date": "2026-07-29", "qty": 1400,
         "delivered_qty": 1400},
        {"sched_id": 66, "due_date": "2026-07-31", "qty": 1400,
         "delivered_qty": 1400},
        {"sched_id": 67, "due_date": "2026-08-03", "qty": 800,
         "delivered_qty": 0},
        {"sched_id": 68, "due_date": "2026-08-05", "qty": 1400,
         "delivered_qty": 0},
    ]


def test_skipped_round_stays_late():
    """8/3(800)을 건너뛰고 8/5 에 1,400 납품 → 8/5 회차가 다 차고
    8/3 이 잔량 800 지연으로 남아야 한다 (실물과 일치)."""
    out = allocate_rounds(_rounds(), 1400, "2026-08-05")
    assert out == {68: 1400}          # 8/3(67) 은 손대지 않는다


def test_makeup_fills_oldest_after_today():
    """8/5 에 2,200 납품 (당일 1,400 + 밀린 800 만회) →
    당일 회차 먼저, 남는 800 은 8/3 회차로."""
    out = allocate_rounds(_rounds(), 2200, "2026-08-05")
    assert out == {68: 1400, 67: 800}


def test_exact_date_sequence():
    """날짜대로 순서 납품하면 각 회차가 제 날짜에 채워진다."""
    rounds = _rounds()
    for r in rounds:
        r["delivered_qty"] = 0
    done = {}
    for due, q in [("2026-07-29", 1400), ("2026-07-31", 1400),
                   ("2026-08-03", 800), ("2026-08-05", 1400)]:
        for sid, v in allocate_rounds(rounds, q, due).items():
            done[sid] = v
            for r in rounds:
                if r["sched_id"] == sid:
                    r["delivered_qty"] = v
    assert done == {65: 1400, 66: 1400, 67: 800, 68: 1400}


def test_no_matching_date_falls_back_to_oldest():
    """납기와 다른 날 납품(조기·지연 납품)은 오래된 회차부터."""
    rounds = _rounds()
    for r in rounds:
        r["delivered_qty"] = 0
    out = allocate_rounds(rounds, 2000, "2026-07-30")
    assert out == {65: 1400, 66: 600}


def test_overflow_beyond_rounds_is_returned_partially():
    """회차 총량을 넘는 납품 — 채울 수 있는 만큼만 기록."""
    out = allocate_rounds(_rounds(), 5000, "2026-08-05")
    assert out == {68: 1400, 67: 800}   # 남는 2,800 은 회차 밖 (라인엔 반영)


def test_partial_today_round():
    out = allocate_rounds(_rounds(), 900, "2026-08-05")
    assert out == {68: 900}
