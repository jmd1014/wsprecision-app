# -*- coding: utf-8 -*-
"""업무 루틴 순수 함수 (utils/dash_routine.py) — 계획서 §6 순수 함수 항목 (2026-10-21)."""
import os
import sys
from datetime import date, datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.dash_routine import (  # noqa: E402
    KST, shift_slot, prev_slot, slot_order, is_off, is_pre_holiday, plan_template_ids,
    can_write, can_check, completion, slot_state, new_template_code, kst_hhmm)


def _kst(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=KST)


# ─── shift_slot 경계 ──────────────────────────────────────────

@pytest.mark.parametrize("hh,mm,want", [
    (7, 29, (date(2026, 10, 20), "night")),   # 전날 야간
    (7, 30, (date(2026, 10, 21), "day")),
    (19, 29, (date(2026, 10, 21), "day")),
    (19, 30, (date(2026, 10, 21), "night")),
    (0, 30, (date(2026, 10, 20), "night")),
    (0, 0, (date(2026, 10, 20), "night")),
    (23, 59, (date(2026, 10, 21), "night")),
])
def test_shift_slot_boundaries_kst(hh, mm, want):
    assert shift_slot(_kst(2026, 10, 21, hh, mm)) == want


def test_shift_slot_accepts_utc_input():
    # 2026-10-21 10:29Z = KST 19:29 → day / 10:30Z = KST 19:30 → night
    assert shift_slot(datetime(2026, 10, 21, 10, 29, tzinfo=timezone.utc)) == (date(2026, 10, 21), "day")
    assert shift_slot(datetime(2026, 10, 21, 10, 30, tzinfo=timezone.utc)) == (date(2026, 10, 21), "night")
    # 월말·연말 자정 넘김: 2027-01-01 02:00 KST = 2026-12-31 야간
    assert shift_slot(_kst(2027, 1, 1, 2, 0)) == (date(2026, 12, 31), "night")
    assert shift_slot(_kst(2026, 11, 1, 3, 0)) == (date(2026, 10, 31), "night")


def test_shift_slot_rejects_naive_and_non_datetime():
    with pytest.raises(ValueError):
        shift_slot(datetime(2026, 10, 21, 9, 0))
    with pytest.raises(TypeError):
        shift_slot("2026-10-21")


def test_prev_slot_and_order():
    assert prev_slot((date(2026, 10, 21), "night")) == (date(2026, 10, 20), "night")
    assert prev_slot(("2026-10-21", "day")) == (date(2026, 10, 20), "day")
    assert slot_order((date(2026, 10, 21), "day")) < slot_order((date(2026, 10, 21), "night")) \
        < slot_order((date(2026, 10, 22), "day"))


# ─── 휴무 ──────────────────────────────────────────────────────

def test_is_off_and_pre_holiday_with_calendar():
    sun, sat, fri, thu = date(2026, 10, 25), date(2026, 10, 24), date(2026, 10, 23), date(2026, 10, 22)
    assert is_off(sun) and not is_off(sat) and not is_off(fri)
    assert is_off(date(2026, 10, 21), {date(2026, 10, 21): "OFF"})          # 평일 OFF 등록
    assert not is_off(sun, {sun: "WEEKDAY"})                               # 일요일 특근
    assert not is_off(sun, {sun.isoformat(): "HOLIDAY"})                  # 일요일 HOLIDAY 는 근무일 취급
    assert is_pre_holiday(sat)                                             # 다음 날 일요일 OFF
    assert not is_pre_holiday(fri)                                         # 다음 날 토요일 = SATURDAY 근무
    assert is_pre_holiday(fri, {sat: "HOLIDAY"})                           # 토요일이 HOLIDAY
    assert is_pre_holiday(thu, {fri: "OFF"})
    assert not is_pre_holiday(sun, {})                                     # 다음 날 월요일


# ─── plan_template_ids ────────────────────────────────────────

TPL = [
    {"id": 1, "shift": "day", "seq": 2, "active": True, "active_rule": "always", "assignee_user_ids": ["김준오"]},
    {"id": 2, "shift": "day", "seq": 1, "active": True, "active_rule": "always", "assignee_user_ids": ["김준오"]},
    {"id": 3, "shift": "day", "seq": 3, "active": False, "active_rule": "always", "assignee_user_ids": ["김준오"]},
    {"id": 4, "shift": "night", "seq": 1, "active": True, "active_rule": "always", "assignee_user_ids": []},
    {"id": 5, "shift": "night", "seq": 2, "active": True, "active_rule": "always", "assignee_user_ids": ["김만호"]},
    {"id": 6, "shift": "night", "seq": 3, "active": True, "active_rule": "pre_holiday", "assignee_user_ids": ["김만호"]},
    {"id": 7, "shift": "night", "seq": 4, "active": True, "active_rule": "pre_holiday", "assignee_user_ids": [" "]},
]


def test_plan_template_ids_by_weekday():
    mon, fri, sat, sun = date(2026, 10, 19), date(2026, 10, 23), date(2026, 10, 24), date(2026, 10, 25)
    assert plan_template_ids(TPL, mon, "day") == ([2, 1], 0)          # seq 순, 비활성 제외
    assert plan_template_ids(TPL, mon, "night") == ([5], 1)           # 담당 빈 4 제외(7 은 pre_holiday 규칙으로 먼저 걸러짐)
    assert plan_template_ids(TPL, fri, "night") == ([5], 1)           # 금 → 다음 날 토(근무) → pre ✕
    assert plan_template_ids(TPL, sat, "night") == ([5, 6], 2)        # 토 → 다음 날 일 OFF → pre ○
    assert plan_template_ids(TPL, sat, "day") == ([2, 1], 0)          # 토 주간 생성
    assert plan_template_ids(TPL, sun, "day") == ([], 0)              # 일 휴무
    assert plan_template_ids(TPL, sun, "night") == ([], 0)
    assert plan_template_ids(TPL, mon, "night", {date(2026, 10, 20): "HOLIDAY"}) == ([5, 6], 2)   # pre ○ → 4·7 담당 빈 제외
    assert plan_template_ids(TPL, sun, "day", {sun: "HOLIDAY"}) == ([2, 1], 0)   # HOLIDAY 는 근무일 취급
    with pytest.raises(ValueError):
        plan_template_ids(TPL, mon, "evening")


def test_plan_template_ids_after_assignment_adds_only_new():
    mon = date(2026, 10, 19)
    before, _ = plan_template_ids(TPL, mon, "night")
    tpl2 = [dict(t, assignee_user_ids=["김성용"]) if t["id"] == 4 else t for t in TPL]
    after, excl = plan_template_ids(tpl2, mon, "night")
    assert set(after) - set(before) == {4} and excl == 0


# ─── can_write / can_check ─────────────────────────────────────

def test_can_write_only_current_slot():
    card = {"work_date": "2026-10-24", "shift": "night"}
    assert can_write(card, (date(2026, 10, 24), "night"))
    assert can_write(card, shift_slot(_kst(2026, 10, 25, 3, 0)))          # 토요일 야간의 일요일 새벽 = 토 슬롯 유지
    assert not can_write(card, (date(2026, 10, 24), "day"))                # 종료 교대
    assert not can_write(card, (date(2026, 10, 25), "night"))              # 다음 교대
    assert not can_write({"work_date": "2026-10-25", "shift": "day"}, (date(2026, 10, 24), "night"))   # 미래 교대
    assert not can_write({}, (date(2026, 10, 24), "night"))


def test_can_check_assignee_or_admin_and_rejects_empty_user():
    card = {"assignee_user_ids": ["김준오", "김만호"]}
    assert can_check(card, "김준오", "worker")
    assert not can_check(card, "현장", "worker")
    assert can_check(card, "김민수", "admin")
    assert not can_check(card, "", "admin")
    assert not can_check(card, None, "worker")
    assert not can_check({"assignee_user_ids": []}, "김준오", "worker")


# ─── completion / slot_state ──────────────────────────────────

def test_completion_and_slot_state():
    assert completion([]) is None
    assert completion([{"status": "done"}, {"status": "todo"}, {"status": "done"}]) == pytest.approx(2 / 3)
    now = (date(2026, 10, 21), "day")
    cards = [{"status": "todo"}]
    assert slot_state(date(2026, 10, 25), "day", cards, None, now) == "off"
    assert slot_state(date(2026, 10, 20), "day", [], None, now) == "none"
    assert slot_state(date(2026, 10, 21), "day", cards, None, now) == "open"
    assert slot_state(date(2026, 10, 20), "night", cards, None, now) == "closed"
    assert slot_state(date(2026, 10, 21), "night", cards, None, now) == "future"
    assert slot_state(date(2026, 10, 20), "day", cards) == "closed"


# ─── new_template_code / kst_hhmm ─────────────────────────────

def test_new_template_code_format_and_collision():
    code = new_template_code("production", "day", existing_codes={"prod_day_01"})
    assert code.startswith("production_day_") and len(code) == len("production_day_") + 8
    seq = iter(["aaaaaaaa", "bbbbbbbb"])
    assert new_template_code("production", "night", {"production_night_aaaaaaaa"},
                             _uuid=lambda: next(seq)) == "production_night_bbbbbbbb"
    with pytest.raises(RuntimeError):
        new_template_code("production", "night", {"production_night_cccccccc"}, _uuid=lambda: "cccccccc")


def test_kst_hhmm():
    assert kst_hhmm("2026-10-21T23:12:00+00:00") == "08:12"
    assert kst_hhmm("2026-10-21T23:12:00Z") == "08:12"
    assert kst_hhmm(None) == "-"
