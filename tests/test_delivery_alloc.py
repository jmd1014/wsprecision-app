# -*- coding: utf-8 -*-
"""회차 충당 규칙 단위 검증 — 납품일 우선 + 오래된 회차 만회."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.delivery_alloc import allocate_rounds, carry_delivered  # noqa: E402


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


# ─── 재저장 승계 (carry_delivered) ─────────────────────

def test_carry_survives_middle_round_deletion():
    """8/3 휴가 회차를 지우고 재저장 → 8/5 의 1,400 이 8/5 에 남아야
    한다 (순번 승계는 8/7 로 밀리던 실버그, 2026-08-06)."""
    old = [{"due_date": "2026-07-29", "delivered_qty": 1400},
           {"due_date": "2026-07-31", "delivered_qty": 1400},
           {"due_date": "2026-08-03", "delivered_qty": 0},
           {"due_date": "2026-08-05", "delivered_qty": 1400},
           {"due_date": "2026-08-07", "delivered_qty": 0}]
    new = [{"due_date": "2026-07-29", "qty": 1400},
           {"due_date": "2026-07-31", "qty": 1400},
           {"due_date": "2026-08-05", "qty": 1400},   # 8/3 삭제됨
           {"due_date": "2026-08-07", "qty": 1400}]
    done, lost = carry_delivered(old, new)
    assert done == [1400, 1400, 1400, 0]
    assert lost == 0


def test_carry_deleted_delivered_date_falls_back_to_oldest():
    """납품된 회차의 날짜 자체를 지우면 실적은 사라지지 않고
    가장 오래된 회차 여유로 승계된다."""
    old = [{"due_date": "2026-07-29", "delivered_qty": 500}]
    new = [{"due_date": "2026-08-03", "qty": 300},
           {"due_date": "2026-08-05", "qty": 400}]
    done, lost = carry_delivered(old, new)
    assert done == [300, 200]
    assert lost == 0


def test_carry_qty_reduced_overflows_to_next():
    """회차 수량을 납품량보다 줄이면 초과분은 다음 회차로."""
    old = [{"due_date": "2026-07-29", "delivered_qty": 1400}]
    new = [{"due_date": "2026-07-29", "qty": 1000},
           {"due_date": "2026-08-05", "qty": 1000}]
    done, lost = carry_delivered(old, new)
    assert done == [1000, 400]
    assert lost == 0


def test_carry_reports_lost_when_plan_too_small():
    """새 회차 총량 < 납품완료 — 잃는 만큼 반환 (경고용)."""
    old = [{"due_date": "2026-07-29", "delivered_qty": 1400}]
    new = [{"due_date": "2026-08-05", "qty": 1000}]
    done, lost = carry_delivered(old, new)
    assert done == [1000]
    assert lost == 400


# ─── 같은 납기 병합 (2026-08-13, 4PDVN-02 중복 날짜 사례) ───

def test_merge_same_date_sums_qty_and_joins_notes():
    """같은 날짜 회차는 하나로 — 수량 합산, 비고 이어붙임."""
    from utils.delivery_alloc import merge_same_date
    rounds = [
        {"due_date": "2026-08-12", "qty": 1732,
         "note": "이전 회차 잔여 보충"},
        {"due_date": "2026-08-12", "qty": 2016, "note": None},
        {"due_date": "2026-08-14", "qty": 1008, "note": None},
    ]
    out = merge_same_date(rounds)
    assert len(out) == 2
    assert out[0]["due_date"] == "2026-08-12"
    assert out[0]["qty"] == 3748
    assert out[0]["note"] == "이전 회차 잔여 보충"
    assert out[1]["qty"] == 1008
    # 원본은 불변
    assert rounds[0]["qty"] == 1732


def test_merge_distinct_dates_untouched():
    from utils.delivery_alloc import merge_same_date
    rounds = [{"due_date": "2026-08-12", "qty": 100, "note": "a"},
              {"due_date": "2026-08-14", "qty": 200, "note": "b"}]
    assert merge_same_date(rounds) == rounds


def test_allocate_duplicate_dates_never_double_counts():
    """중복 날짜 회차가 있어도 한 번의 납품은 총량만큼만 배분된다."""
    rounds = [
        {"sched_id": 1, "due_date": "2026-08-12", "qty": 1732,
         "delivered_qty": 0},
        {"sched_id": 2, "due_date": "2026-08-12", "qty": 2016,
         "delivered_qty": 0},
    ]
    out = allocate_rounds(rounds, 1732, "2026-08-12")
    assert out == {1: 1732}          # 첫 회차만, 둘째는 손대지 않음


def test_carry_duplicate_dates_never_double_counts():
    """재저장 승계도 중복 날짜에 실적을 나눠 담되 총량을 보존한다."""
    old = [{"due_date": "2026-08-12", "delivered_qty": 1732}]
    new = [{"due_date": "2026-08-12", "qty": 1732},
           {"due_date": "2026-08-12", "qty": 2016}]
    done, lost = carry_delivered(old, new)
    assert done == [1732, 0]
    assert lost == 0
