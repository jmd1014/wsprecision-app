# -*- coding: utf-8 -*-
"""업무 루틴(업무 대시보드 1단계) — 순수 함수 (계획서 §2, 2026-10-21).

Streamlit·DB 의존 없음. 모든 날짜·교대 계산은 이 모듈만 한다(`date.today()`·naive now 금지 —
정적 테스트가 검사). 시각은 tz-aware datetime 을 받아 KST 로 바꿔 판정한다.

교대 경계(KST): 07:30 ≤ t < 19:30 → 주간(day), 19:30 ≤ t → 야간(night, 같은 날짜),
00:00 ≤ t < 07:30 → 전날의 야간. work_date 는 "교대가 시작한 날".
휴무: `utils.weekly_plan.day_type`(월~금 WEEKDAY, 토 SATURDAY, 일 OFF, work_calendar 예외 우선).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone

from utils.weekly_plan import day_type

KST = timezone(timedelta(hours=9))
DAY_START = time(7, 30)
NIGHT_START = time(19, 30)
SHIFTS = ("day", "night")
SHIFT_KO = {"day": "주간", "night": "야간"}


# ─── 시각 → 슬롯 ────────────────────────────────────────────────

def shift_slot(now_utc: datetime) -> tuple[date, str]:
    """tz-aware 현재 시각 → (work_date, shift). naive 는 거부(ValueError)."""
    if not isinstance(now_utc, datetime):
        raise TypeError("shift_slot: datetime 필요")
    if now_utc.tzinfo is None or now_utc.utcoffset() is None:
        raise ValueError("shift_slot: tz-aware datetime 만 (naive 금지)")
    k = now_utc.astimezone(KST)
    t = k.timetz().replace(tzinfo=None)
    if DAY_START <= t < NIGHT_START:
        return k.date(), "day"
    if t >= NIGHT_START:
        return k.date(), "night"
    return k.date() - timedelta(days=1), "night"


def prev_slot(slot: tuple[date, str]) -> tuple[date, str]:
    """같은 교대의 전날."""
    d, s = slot
    return _to_date(d) - timedelta(days=1), s


def slot_order(slot: tuple[date, str]) -> tuple[date, int]:
    """정렬·비교용 (날짜, 0=day/1=night)."""
    d, s = slot
    return _to_date(d), 0 if s == "day" else 1


# ─── 휴무 ──────────────────────────────────────────────────────

def is_off(d, cal=None) -> bool:
    return day_type(_to_date(d), cal) == "OFF"


def is_pre_holiday(d, cal=None) -> bool:
    """다음 날이 OFF/HOLIDAY 면 True (SATURDAY 는 근무일이라 False)."""
    return day_type(_to_date(d) + timedelta(days=1), cal) in ("OFF", "HOLIDAY")


# ─── 생성 대상 ───────────────────────────────────────────────────

def plan_template_ids(templates, work_date, shift, cal=None) -> tuple[list[int], int]:
    """이 슬롯에 생성할 템플릿 id 목록(seq 순)과 '담당자 미지정으로 제외된 수'.

    활성 + shift 일치 + (always 또는 pre_holiday 이고 다음 날 휴무) + 담당자 비어 있지 않음(D2/H4).
    휴무일(OFF)이면 빈 목록. templates 는 dict 리스트(id, shift, active, active_rule, assignee_user_ids, seq).
    """
    d = _to_date(work_date)
    if shift not in SHIFTS:
        raise ValueError(f"plan_template_ids: shift {shift!r}")
    if is_off(d, cal):
        return [], 0
    pre = is_pre_holiday(d, cal)
    picked, excluded = [], 0
    for t in sorted(templates or [], key=lambda x: (int(x.get("seq") or 0), int(x.get("id") or 0))):
        if not t.get("active", True) or t.get("shift") != shift:
            continue
        rule = t.get("active_rule") or "always"
        if rule == "pre_holiday" and not pre:
            continue
        if rule not in ("always", "pre_holiday"):
            continue
        if not [u for u in (t.get("assignee_user_ids") or []) if str(u or "").strip()]:
            excluded += 1
            continue
        picked.append(int(t["id"]))
    return picked, excluded


# ─── 쓰기 가능 ─────────────────────────────────────────────────

def can_write(card, slot) -> bool:
    """현재 슬롯의 카드만 쓰기 가능(D6/H3). 과거·종료·미래 교대는 읽기 전용."""
    try:
        return (_to_date(card.get("work_date")), card.get("shift")) == (_to_date(slot[0]), slot[1])
    except Exception:
        return False


def can_check(card, username, role) -> bool:
    """담당자 본인 또는 관리자. username 빈 값은 거부(H2)."""
    u = str(username or "").strip()
    if not u:
        return False
    if role == "admin":
        return True
    return u in [str(x or "").strip() for x in (card.get("assignee_user_ids") or [])]


# ─── 집계 ──────────────────────────────────────────────────────

def completion(cards) -> float | None:
    """완료율(0~1). 카드가 없으면 None."""
    cards = list(cards or [])
    if not cards:
        return None
    done = sum(1 for c in cards if c.get("status") == "done")
    return done / len(cards)


def slot_state(d, shift, cards, cal=None, now_slot=None) -> str:
    """표 셀 상태: 'off'(휴무) / 'none'(미생성) / 'open'(진행중 = 현재 슬롯) / 'closed'(종료) / 'future'."""
    d = _to_date(d)
    if is_off(d, cal):
        return "off"
    if not cards:
        return "none"
    if now_slot is not None:
        if (d, shift) == (_to_date(now_slot[0]), now_slot[1]):
            return "open"
        if slot_order((d, shift)) > slot_order(now_slot):
            return "future"
    return "closed"


# ─── 템플릿 코드 ───────────────────────────────────────────────

def new_template_code(part_code, shift, existing_codes=(), _uuid=None) -> str:
    """`{part_code}_{shift}_{uuid8}`. 시드 `prod_day_NN` 과 겹치지 않고, 충돌 시 1회 재생성(M6)."""
    gen = _uuid or (lambda: uuid.uuid4().hex)
    existing = set(existing_codes or ())
    for _ in range(2):
        code = f"{part_code}_{shift}_{str(gen())[:8]}"
        if code not in existing:
            return code
    raise RuntimeError("new_template_code: 코드 충돌 2회 — 다시 시도")


# ─── 표시 보조 ────────────────────────────────────────────────

def kst_hhmm(ts) -> str:
    """UTC ISO 타임스탬프 → 'HH:MM'(KST). 빈 값은 '-'."""
    if not ts:
        return "-"
    try:
        s = str(ts).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(KST).strftime("%H:%M")
    except Exception:
        return str(ts)[:16]


def _to_date(d) -> date:
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    return date.fromisoformat(str(d)[:10])
