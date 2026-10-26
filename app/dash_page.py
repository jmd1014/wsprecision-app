# -*- coding: utf-8 -*-
"""업무 루틴(업무 대시보드 1단계) — 화면 3개 + 홈 카드 + 핸들러 (계획서 §3·§4, 2026-10-21).

본체(streamlit_app.py)는 `Ctx` 로 헬퍼(현재 사용자·클릭 가드·확인 게이트·flash·표·이동)를 넘기고
`render_today / render_rate / render_templates / render_home_card` 만 부른다.
쓰기는 dash_ 테이블과 RPC dash_generate_cards 뿐(정적 테스트). 날짜·교대 계산은 utils.dash_routine 만.
로컬 읽기 모드(ctx.readonly = secrets auth.disabled)에서는 생성·체크·취소·템플릿 저장 전부 차단(D7).
"""
from __future__ import annotations

import html as _html
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable
from urllib.parse import quote as _q

import streamlit as st

from utils import dash_routine as R

PART_CODE = "production"
SUBS = [("today", "오늘 루틴"), ("rate", "완료율"), ("tmpl", "템플릿 관리")]
RULE_KO = {"always": "매 교대", "pre_holiday": "휴무 전날만"}
NOT_READY_MSG = "업무 루틴 준비 중 — 데이터베이스에 루틴 테이블이 아직 없습니다 (migration 073)."
READONLY_MSG = "로컬 읽기 모드 — 업무 루틴 쓰기 차단 (생성·체크·취소·템플릿 저장은 배포 화면에서)"


def now_utc() -> datetime:
    """현재 시각(UTC, tz-aware). 테스트가 이 함수만 바꿔 시각을 고정한다 — 다른 곳에서 now() 금지."""
    return datetime.now(timezone.utc)


@dataclass
class Ctx:
    db: object
    current_user: Callable[[], dict]
    is_admin: bool
    readonly: bool
    click_guard: Callable[[str], bool]
    confirm_gate: Callable
    nav_flash: Callable
    nav_go: Callable
    toss_table: Callable
    load_users: Callable[[], dict]
    log_error: Callable = field(default=lambda *a, **k: None)

    # 실행 단위 캐시(같은 런에서 두 번 조회하지 않게)
    _users: dict | None = None
    _parts: list | None = None

    def users(self) -> dict:
        if self._users is None:
            try:
                self._users = self.load_users() or {}
            except Exception:
                self._users = {}
        return self._users

    def user_name(self, username) -> str:
        u = self.users().get(str(username or ""), {})
        return (u.get("name") if isinstance(u, dict) else None) or str(username or "-")


# ─── 데이터 ─────────────────────────────────────────────────────

def tables_ready(db) -> bool:
    """dash_ 테이블이 있는지(Old DB 보호). 조회 실패 = 준비 안 됨."""
    try:
        db.fetch("dash_parts", "id", "code=eq." + PART_CODE, limit=1)
        return True
    except Exception:
        return False


def load_parts(ctx: Ctx) -> list:
    if ctx._parts is None:
        ctx._parts = ctx.db.fetch("dash_parts", "id,code,name,sort_order", "order=sort_order.asc", limit=20)
    return ctx._parts


def part_id(ctx: Ctx, code=PART_CODE):
    for p in load_parts(ctx):
        if p.get("code") == code:
            return p.get("id")
    return None


CAL_FAIL_MSG = "휴무 달력을 읽지 못해 자동 생성을 멈췄습니다 — 새로 고침"


def load_calendar(db):
    """work_calendar → {cal_date: day_type}. 조회 실패는 **None**(빈 달력과 구분, Codex M1) —
    호출부는 None 이면 생성(RPC)을 하지 않는다(휴무일에 카드를 만들 위험). 카드 조회·표시는 그대로."""
    try:
        rows = db.fetch("work_calendar", "cal_date,day_type", "", limit=1000)
    except Exception:
        return None
    return {str(r.get("cal_date"))[:10]: r.get("day_type") for r in rows if r.get("cal_date")}


def load_templates(ctx: Ctx, part=PART_CODE, include_inactive=False) -> list:
    pid = part_id(ctx, part)
    if pid is None:
        return []
    rows = ctx.db.fetch("dash_routine_templates", "*",
                        f"part_id=eq.{pid}&order=shift.asc,seq.asc,id.asc", limit=500, cache=False)
    if not include_inactive:
        rows = [t for t in rows if t.get("active", True)]
    return rows


def load_cards(db, work_date, shift) -> list:
    d = R._to_date(work_date).isoformat()
    return db.fetch("dash_cards", "*", f"work_date=eq.{d}&shift=eq.{shift}&order=seq.asc,id.asc",
                    limit=500, cache=False)


# ─── 생성 ─────────────────────────────────────────────────────

def ensure_cards(ctx: Ctx, templates, slot, cal, cards) -> tuple[list, dict]:
    """현재 슬롯의 카드를 멱등 생성. (cards, info) — info: inserted/skipped/excluded/missing/error/msg."""
    d, shift = slot
    info = {"inserted": 0, "skipped": 0, "excluded": 0, "missing": 0, "error": None, "msg": None}
    if ctx.readonly:
        info["msg"] = "읽기 모드 — 이 교대의 카드는 배포 화면에서 생성됩니다" if not cards else None
        return cards, info
    if cal is None:                 # 달력 조회 실패 — 휴무 판정 불가 → 생성 중단(M1)
        info["error"] = CAL_FAIL_MSG
        return cards, info
    ids, excluded = R.plan_template_ids(templates, d, shift, cal)
    info["excluded"] = excluded
    if R.is_off(d, cal):
        info["msg"] = "휴무일 — 루틴 카드를 만들지 않습니다"
        return cards, info
    have = {c.get("template_id") for c in cards}
    missing = [i for i in ids if i not in have]
    info["missing"] = len(missing)
    if not ids:
        info["msg"] = (f"담당자 미지정 {excluded}개 제외 — 템플릿 관리에서 담당자를 지정하세요" if excluded
                       else "생성할 템플릿이 없습니다")
        return cards, info
    if not missing:
        return cards, info
    try:
        res = ctx.db.rpc("dash_generate_cards", {
            "p_work_date": R._to_date(d).isoformat(), "p_shift": shift, "p_template_ids": missing})
        info["inserted"] = int((res or {}).get("inserted") or 0)
        info["skipped"] = int((res or {}).get("skipped") or 0)
        cards = load_cards(ctx.db, d, shift)
    except Exception as e:          # RpcUnavailable / RpcRejected / RpcTransportError — 재시도 없음
        info["error"] = f"{type(e).__name__}: {e}"
        try:
            cards = load_cards(ctx.db, d, shift)
        except Exception:
            pass
    return cards, info


# ─── 핸들러 ──────────────────────────────────────────────────────

def _username(ctx: Ctx) -> str:
    return str((ctx.current_user() or {}).get("username") or "").strip()


def _role(ctx: Ctx) -> str:
    return str((ctx.current_user() or {}).get("role") or "")


def _precheck(ctx: Ctx, card, guard_key) -> str | None:
    """공통 사전 검사(읽기 모드 → 클릭 가드 → 사용자 → 권한 → 슬롯). 거부 사유 또는 None."""
    if ctx.readonly:
        return READONLY_MSG
    if not ctx.click_guard(guard_key):
        return "방금 같은 처리가 실행됐습니다"
    u = _username(ctx)
    if not u:
        return "로그인 사용자를 확인할 수 없습니다 — 다시 로그인하세요"
    if not R.can_check(card, u, _role(ctx)):
        return "담당자(또는 관리자)만 처리할 수 있습니다"
    if not R.can_write(card, R.shift_slot(now_utc())):
        return "현재 교대의 카드만 처리할 수 있습니다 — 교대가 바뀌었습니다"
    return None


def handle_done(ctx: Ctx, card) -> bool:
    """[완료]: status=todo 조건부 갱신(선착). True 면 1행 갱신됨."""
    cid = card["id"]
    why = _precheck(ctx, card, f"dash_chk_{cid}")
    if why:
        ctx.nav_flash(why)
        return False
    u = _username(ctx)
    ts = now_utc().isoformat()
    try:
        n = ctx.db.update_count("dash_cards", f"id=eq.{cid}&status=eq.todo",
                                {"status": "done", "completed_by": u, "completed_at": ts})
    except Exception as e:
        ctx.log_error("dash_write", f"dash_cards done update 예외: {e}", table_name="dash_cards")
        n = -1
    if n == 1:
        try:
            ctx.db.insert("dash_card_activity", [{"card_id": cid, "user_id": u, "action": "done",
                                                  "from_value": "todo", "to_value": "done"}])
            ctx.nav_flash(f"완료 — {card.get('title')}")
        except Exception as e:
            ctx.log_error("dash_write", f"dash_card_activity insert 실패(card {cid}): {e}",
                          table_name="dash_card_activity")
            ctx.nav_flash(f"완료는 저장됐지만 활동 기록에 실패했습니다 — 관리자에게 알려 주세요 ({card.get('title')})")
        return True
    if n == 0:
        latest = _latest(ctx, cid)
        if latest and latest.get("status") == "done":
            ctx.nav_flash(f"{ctx.user_name(latest.get('completed_by'))} 이 "
                          f"{R.kst_hhmm(latest.get('completed_at'))} 완료함 — 화면을 갱신했습니다")
        else:
            ctx.nav_flash("상태가 바뀌어 처리하지 않았습니다 — 화면을 갱신했습니다")
        return False
    ctx.nav_flash("저장되지 않았습니다 — 새로고침 후 다시 시도하세요")
    return False


def handle_undo(ctx: Ctx, card, completed_at_seen) -> bool:
    """[취소]: status=done & completed_at 일치 조건부 갱신(오래된 확인창 차단)."""
    cid = card["id"]
    why = _precheck(ctx, card, f"dash_undo_{cid}")
    if why:
        ctx.nav_flash(why)
        return False
    u = _username(ctx)
    if not completed_at_seen:
        ctx.nav_flash("상태가 바뀌어 다시 확인하세요")
        return False
    try:
        n = ctx.db.update_count(
            "dash_cards",
            f"id=eq.{cid}&status=eq.done&completed_at=eq.{_q(str(completed_at_seen), safe='')}",
            {"status": "todo", "completed_by": None, "completed_at": None})
    except Exception as e:
        ctx.log_error("dash_write", f"dash_cards undo update 예외: {e}", table_name="dash_cards")
        n = -1
    if n == 1:
        try:
            ctx.db.insert("dash_card_activity", [{"card_id": cid, "user_id": u, "action": "undo",
                                                  "from_value": "done", "to_value": "todo"}])
            ctx.nav_flash(f"완료 취소 — {card.get('title')}")
        except Exception as e:
            ctx.log_error("dash_write", f"dash_card_activity insert 실패(undo card {cid}): {e}",
                          table_name="dash_card_activity")
            ctx.nav_flash(f"취소는 저장됐지만 활동 기록에 실패했습니다 — 관리자에게 알려 주세요 ({card.get('title')})")
        return True
    if n == 0:
        ctx.nav_flash("상태가 바뀌어 다시 확인하세요")
        return False
    ctx.nav_flash("저장되지 않았습니다 — 새로고침 후 다시 시도하세요")
    return False


def _latest(ctx: Ctx, cid):
    try:
        rows = ctx.db.fetch("dash_cards", "*", f"id=eq.{cid}", limit=1, cache=False)
        return rows[0] if rows else None
    except Exception:
        return None


# ─── 화면: 오늘 루틴 ───────────────────────────────────────────

def render_today(ctx: Ctx):
    db = ctx.db
    if not tables_ready(db):
        st.info(NOT_READY_MSG)
        return
    if ctx.readonly:
        st.warning(READONLY_MSG)
    now_slot = R.shift_slot(now_utc())
    cal = load_calendar(db)
    # 교대·날짜 선택(기본 = 현재 슬롯; _NAV_KEEP 제외)
    c1, c2, c3 = st.columns([1.2, 1.2, 2])
    shift_lbl = c1.radio("교대", ["주간", "야간"], index=0 if now_slot[1] == "day" else 1,
                         horizontal=True, key="dash_shift", label_visibility="collapsed")
    shift = "day" if shift_lbl == "주간" else "night"
    d = c2.date_input("날짜", value=now_slot[0], key="dash_date", label_visibility="collapsed")
    slot = (R._to_date(d), shift)
    is_now = slot == now_slot
    templates = load_templates(ctx)
    try:
        cards = load_cards(db, *slot)
    except Exception as e:
        st.error(f"루틴 카드 조회 실패: {e}")
        return
    info = None
    if is_now and cal is None:
        st.warning(CAL_FAIL_MSG)
        info = {"msg": None, "excluded": 0, "inserted": 0, "error": None}
    elif is_now and not R.is_off(slot[0], cal):
        cards, info = ensure_cards(ctx, templates, slot, cal, cards)
    elif is_now:
        info = {"msg": "휴무일 — 루틴 카드를 만들지 않습니다", "excluded": 0, "inserted": 0, "error": None}
    rate = R.completion(cards)
    with c3:
        if rate is None:
            st.markdown('<span class="ws-chip">완료율 —</span>', unsafe_allow_html=True)
        else:
            color = "#01a76b" if rate >= 0.8 else "#dd6b02"
            st.markdown(f'<span class="ws-chip" style="color:{color}"><b>완료율 {rate * 100:.0f}%</b> · '
                        f'{sum(1 for c in cards if c.get("status") == "done")}/{len(cards)}</span>',
                        unsafe_allow_html=True)
    if not is_now:
        st.info("읽기 전용 — 종료됐거나 아직 시작하지 않은 교대입니다 (현재 교대: "
                f"{now_slot[0].isoformat()} {R.SHIFT_KO[now_slot[1]]})")
    if info:
        if info.get("error") and info["error"] != CAL_FAIL_MSG:
            st.warning(f"카드 생성에 실패했습니다 — 화면을 다시 열어 보세요 ({info['error']})")
        if ctx.is_admin:
            bits = []
            if info.get("inserted"):
                bits.append(f"생성 {info['inserted']}")
            if info.get("skipped"):
                bits.append(f"이미 있음 {info['skipped']}")
            if info.get("excluded"):
                bits.append(f"담당자 미지정 {info['excluded']}개 제외")
            if bits:
                st.caption(" · ".join(bits))
        # 읽기 모드 안내는 상단 배너(READONLY_MSG) 하나로 — 같은 화면 두 번 표시 제거(U1b ④, 2026-10-26)
        if info.get("msg") and not cards and not ctx.readonly:
            st.info(info["msg"])
    # 어제(같은 교대의 전날) 미완료
    try:
        prev_cards = load_cards(db, *R.prev_slot(slot))
    except Exception:
        prev_cards = []
    prev_open = [c for c in prev_cards if c.get("status") != "done"]
    if prev_open:
        with st.expander(f"어제 미완료 {len(prev_open)}건 — 오늘로 넘어오지 않습니다"):
            for c in prev_open:
                st.markdown(f'<span style="color:#dd6b02">● {_html.escape(str(c.get("title") or ""))}</span>',
                            unsafe_allow_html=True)
    # 관리자 수동 생성
    if ctx.is_admin and is_now:
        if st.button("카드 생성 (수동)", key="dash_gen", disabled=ctx.readonly,
                     help="화면 진입 때 자동 생성되지만, 템플릿·담당을 바꾼 직후 바로 만들 때"):
            if ctx.readonly:
                ctx.nav_flash(READONLY_MSG)
            elif cal is None:
                ctx.nav_flash(CAL_FAIL_MSG)
            elif ctx.click_guard("dash_gen"):
                _, info2 = ensure_cards(ctx, templates, slot, cal, load_cards(db, *slot))
                ctx.nav_flash(f"생성 {info2.get('inserted', 0)} · 이미 있음 {info2.get('skipped', 0)}"
                              + (f" · 담당자 미지정 {info2['excluded']}개 제외" if info2.get("excluded") else "")
                              + (f" · 실패: {info2['error']}" if info2.get("error") else ""))
            st.rerun()
    if not cards:
        if not info or not info.get("msg"):
            st.info("이 교대의 루틴 카드가 없습니다")
        return
    _render_cards(ctx, cards, slot, now_slot)


def _render_cards(ctx: Ctx, cards, slot, now_slot):
    u = _username(ctx)
    role = _role(ctx)
    writable_slot = slot == now_slot
    for c in cards:
        cid = c["id"]
        done = c.get("status") == "done"
        assignees = [str(x) for x in (c.get("assignee_user_ids") or [])]
        names = ", ".join(ctx.user_name(a) for a in assignees) or "담당 미지정"
        col_a, col_b = st.columns([3, 1.1])
        with col_a:
            st.markdown(
                f'<div style="line-height:1.35"><b>{c.get("seq") or ""}. {_html.escape(str(c.get("title") or ""))}</b>'
                + (f'<br><span style="color:#6b7684;font-size:13px">{_html.escape(str(c.get("done_criteria") or ""))}</span>'
                   if c.get("done_criteria") else "")
                + f'<br><span style="color:#8b95a1;font-size:12px">담당 {_html.escape(names)}</span></div>',
                unsafe_allow_html=True)
        with col_b:
            allowed = writable_slot and (not ctx.readonly) and R.can_check(c, u, role)
            help_txt = (READONLY_MSG if ctx.readonly else
                        "담당자(또는 관리자)만" if not R.can_check(c, u, role) else None)
            if not writable_slot:
                # 과거·종료·미래 교대: 읽기 전용 — 버튼을 그리지 않는다(D6/H3)
                st.markdown(
                    '<div style="text-align:center;color:#01a76b;font-weight:700;padding:6px 0">'
                    f'{_html.escape(ctx.user_name(c.get("completed_by")))} · {R.kst_hhmm(c.get("completed_at"))}</div>'
                    if done else '<div style="text-align:center;color:#8b95a1;padding:6px 0">미완료</div>',
                    unsafe_allow_html=True)
            elif not done:
                if st.button("완료", key=f"dash_done_{cid}", use_container_width=True,
                             disabled=not allowed, help=help_txt):
                    handle_done(ctx, c)
                    st.rerun()
            else:
                st.markdown(
                    f'<div style="text-align:center;color:#01a76b;font-weight:700;padding:6px 0">'
                    f'{_html.escape(ctx.user_name(c.get("completed_by")))} · {R.kst_hhmm(c.get("completed_at"))}</div>',
                    unsafe_allow_html=True)
                flag = f"cfm_dash_undo_{cid}"
                if allowed:
                    if st.button("취소", key=f"dash_undo_{cid}", use_container_width=True, help=help_txt):
                        st.session_state[flag] = True
                        st.session_state[f"dash_undo_at_{cid}"] = c.get("completed_at")
                if st.session_state.get(flag):
                    if not allowed:
                        st.session_state.pop(flag, None)
                    elif ctx.confirm_gate(f"dash_undo_{cid}",
                                          f"'{c.get('title')}' 완료를 취소합니다 — 다시 '완료' 를 눌러야 합니다."):
                        seen = st.session_state.pop(f"dash_undo_at_{cid}", None)
                        handle_undo(ctx, c, seen)
                        st.rerun()


# ─── 화면: 완료율 (관리자) ──────────────────────────────────────

def render_rate(ctx: Ctx, days: int = 14):
    db = ctx.db
    if not tables_ready(db):
        st.info(NOT_READY_MSG)
        return
    now_slot = R.shift_slot(now_utc())
    cal = load_calendar(db)
    if cal is None:
        st.warning("휴무 달력을 읽지 못했습니다 — 휴무 표시('-')가 빠질 수 있습니다")
        cal = {}
    d1 = now_slot[0]
    d0 = d1 - timedelta(days=days - 1)
    try:
        rows = db.fetch("dash_cards", "work_date,shift,status",
                        f"work_date=gte.{d0.isoformat()}&work_date=lte.{d1.isoformat()}", limit=5000, cache=False)
    except Exception as e:
        st.error(f"완료율 조회 실패: {e}")
        return
    by = {}
    for r in rows:
        by.setdefault((str(r.get("work_date"))[:10], r.get("shift")), []).append(r)
    out = []
    for i in range(days):
        d = d1 - timedelta(days=i)
        row = {"날짜": d.isoformat(), "요일": "월화수목금토일"[d.weekday()]}
        for shift, lbl in (("day", "주간"), ("night", "야간")):
            cards = by.get((d.isoformat(), shift), [])
            state = R.slot_state(d, shift, cards, cal, now_slot)
            if state == "off":
                cell = "-"
            elif state == "none":
                cell = "생성 없음" if state != "future" else ""
            else:
                rate = R.completion(cards) or 0.0
                pct = f"{rate * 100:.0f}%"
                if state == "open":
                    cell = f'<span style="color:#3182f6">진행 중 {pct}</span>'
                elif rate < 0.8:
                    cell = f'<span style="color:#dd6b02;font-weight:700">{pct}</span>'
                else:
                    cell = pct
            row[lbl] = cell
        out.append(row)
    st.caption(f"최근 {days}일 · 완료율 = 완료 카드 ÷ 생성 카드 · 80% 미만 강조 · '-' 휴무 · '생성 없음' 미생성")
    ctx.toss_table(out, ["날짜", "요일", "주간", "야간"], raw_cols=("주간", "야간"), strong_cols=("날짜",))


# ─── 화면: 템플릿 관리 (관리자) ─────────────────────────────────

def _validate_assignees(ctx: Ctx, values) -> tuple[list, str | None]:
    users = ctx.users()
    out = []
    for v in values or []:
        if not isinstance(v, str) or not v.strip():
            return [], "담당자 값이 비어 있습니다"
        v = v.strip()
        if v not in users:
            return [], f"등록되지 않은 계정: {v}"
        if v in out:
            continue
        out.append(v)
    return out, None


def _set_template_active(ctx: Ctx, tpl, active: bool) -> bool:
    """활성/비활성 저장 — db.update 가 False 면 실패로 알린다(성공 안내 금지, Codex M2)."""
    label = "다시 사용" if active else "비활성화"
    if ctx.readonly:
        ctx.nav_flash(READONLY_MSG)
        return False
    try:
        ok = ctx.db.update("dash_routine_templates", f"id=eq.{tpl['id']}",
                           {"active": active, "updated_at": now_utc().isoformat()})
    except Exception as e:
        ctx.log_error("dash_write", f"dash_routine_templates {label} 실패: {e}",
                      table_name="dash_routine_templates")
        ctx.nav_flash(f"저장 실패: {e}")
        return False
    if not ok:
        ctx.nav_flash(f"저장되지 않았습니다 — {label} 요청이 반영되지 않았습니다. 새로 고침 후 다시 시도하세요")
        return False
    ctx.nav_flash(f"{label} — {tpl.get('title')}" + (" (오늘 생성된 카드는 남습니다)" if not active else ""))
    return True


def save_template_order(ctx: Ctx, ids_in_order) -> tuple[int, int]:
    """순서 저장 — 행별 결과를 모아 'N/M 반영'. 부분 실패면 재조회된 현재 순서가 화면에 보인다(M2)."""
    ok_n, total = 0, len(ids_in_order)
    failed = []
    if ctx.readonly:
        ctx.nav_flash(READONLY_MSG)
        return 0, total
    for i, tid in enumerate(ids_in_order, 1):
        try:
            ok = ctx.db.update("dash_routine_templates", f"id=eq.{tid}",
                               {"seq": i, "updated_at": now_utc().isoformat()})
        except Exception as e:
            ctx.log_error("dash_write", f"dash_routine_templates 순서 저장 실패(id {tid}): {e}",
                          table_name="dash_routine_templates")
            ok = False
        if ok:
            ok_n += 1
        else:
            failed.append(tid)
    if ok_n == total:
        ctx.nav_flash(f"순서 저장 — {ok_n}/{total} 반영")
    else:
        ctx.nav_flash(f"순서 일부만 저장됐습니다 — {ok_n}/{total} 반영 (실패 id {', '.join(map(str, failed))}). "
                      "현재 순서를 다시 확인하세요")
    return ok_n, total


def render_templates(ctx: Ctx):
    db = ctx.db
    if not tables_ready(db):
        st.info(NOT_READY_MSG)
        return
    if ctx.readonly:
        st.warning(READONLY_MSG)
    pid = part_id(ctx)
    if pid is None:
        st.error("파트 '생산' 이 없습니다 (dash_parts 시드 확인)")
        return
    c1, c2 = st.columns([1.2, 2])
    shift_lbl = c1.radio("교대", ["주간", "야간"], horizontal=True, key="dash_tmpl_shift",
                         label_visibility="collapsed")
    shift = "day" if shift_lbl == "주간" else "night"
    show_all = c2.checkbox("사용 안 함 포함", key="dash_tmpl_all")
    all_tpl = load_templates(ctx, include_inactive=True)
    tpl = [t for t in all_tpl if t.get("shift") == shift and (show_all or t.get("active", True))]
    if tpl:
        ctx.toss_table([{
            "순서": t.get("seq"), "제목": t.get("title"), "완료 기준": t.get("done_criteria") or "",
            "담당": ", ".join(ctx.user_name(a) for a in (t.get("assignee_user_ids") or [])) or "미지정",
            "활성 조건": RULE_KO.get(t.get("active_rule"), t.get("active_rule")),
            "상태": "사용" if t.get("active", True) else "사용 안 함",
        } for t in tpl], ["순서", "제목", "완료 기준", "담당", "활성 조건", "상태"],
            num_cols=("순서",), badge_cols=("상태",))
    else:
        st.info("이 교대에 템플릿이 없습니다")
    st.caption("파트: 생산 · 템플릿 수정은 이후 생성되는 카드에만 반영됩니다(오늘 생성된 카드는 그대로).")

    users = ctx.users()
    user_opts = sorted(users.keys())
    pick_opts = ["(새 템플릿)"] + [f"{t['id']} · {t.get('title')}" for t in tpl]
    pick = st.selectbox("추가 / 수정할 항목", pick_opts, key=f"dash_tmpl_pick_{shift}")
    cur = next((t for t in tpl if pick.startswith(f"{t['id']} · ")), None)
    with st.form(f"dash_tmpl_form_{shift}"):
        title = st.text_input("제목 *", value=(cur or {}).get("title") or "")
        crit = st.text_input("완료 기준", value=(cur or {}).get("done_criteria") or "")
        cur_as = [a for a in ((cur or {}).get("assignee_user_ids") or []) if a in users]
        assignees = st.multiselect("담당자 (계정)", user_opts, default=cur_as)
        rule = st.radio("활성 조건", ["always", "pre_holiday"], format_func=lambda r: RULE_KO[r],
                        index=0 if (cur or {}).get("active_rule", "always") == "always" else 1,
                        horizontal=True)
        seq = st.number_input("순서", min_value=0, step=1,
                              value=int((cur or {}).get("seq") or (max([int(t.get("seq") or 0) for t in tpl] + [0]) + 1)))
        saved = st.form_submit_button("저장", type="primary", disabled=ctx.readonly)
    if saved:
        if ctx.readonly:
            ctx.nav_flash(READONLY_MSG); st.rerun()
        if not ctx.click_guard("dash_tmpl_save"):
            st.rerun()
        err = None
        if not (title or "").strip():
            err = "제목은 비울 수 없습니다"
        clean, aerr = _validate_assignees(ctx, assignees)
        err = err or aerr
        if err:
            st.error(err)
        else:
            fields = {"title": title.strip(), "done_criteria": (crit or "").strip() or None,
                      "assignee_user_ids": clean, "active_rule": rule, "seq": int(seq)}
            try:
                if cur:
                    ok = db.update("dash_routine_templates", f"id=eq.{cur['id']}",
                                   {**fields, "updated_at": now_utc().isoformat()})
                    ctx.nav_flash("템플릿 수정 저장" if ok else "저장되지 않았습니다 — 다시 시도하세요")
                else:
                    code = R.new_template_code(PART_CODE, shift, {t.get("code") for t in all_tpl})
                    db.insert("dash_routine_templates", [{**fields, "code": code, "part_id": pid,
                                                          "shift": shift, "active": True}])
                    ctx.nav_flash(f"템플릿 추가 — {fields['title']}")
            except Exception as e:
                ctx.log_error("dash_write", f"dash_routine_templates 저장 실패: {e}",
                              table_name="dash_routine_templates")
                ctx.nav_flash(f"저장 실패: {e}")
            st.rerun()
    if cur and cur.get("active", True):
        if st.button("사용 안 함 (비활성화)", key=f"dash_tmpl_off_{cur['id']}", disabled=ctx.readonly,
                     help="삭제하지 않습니다. 오늘 생성된 카드는 남습니다"):
            if not ctx.readonly and ctx.click_guard(f"dash_tmpl_off_{cur['id']}"):
                _set_template_active(ctx, cur, False)
            st.rerun()
    elif cur:
        if st.button("다시 사용", key=f"dash_tmpl_on_{cur['id']}", disabled=ctx.readonly):
            if not ctx.readonly and ctx.click_guard(f"dash_tmpl_on_{cur['id']}"):
                _set_template_active(ctx, cur, True)
            st.rerun()
    # 순서 변경 — 드래그 컴포넌트가 있을 때만(없으면 폼의 '순서' 숫자로). 컴포넌트 import 와 저장은 분리(M2)
    active_tpl = [t for t in tpl if t.get("active", True)]
    if len(active_tpl) >= 2:
        sort_items = None
        try:
            from streamlit_sortables import sort_items
        except Exception:
            st.caption("드래그 순서 변경 컴포넌트 미탑재 — 폼의 '순서' 값으로 바꾸세요")
        if sort_items is not None:
            labels = [f"{t['id']} · {t.get('title')}" for t in active_tpl]
            try:
                ordered = sort_items(labels, direction="vertical", key=f"dash_tmpl_sort_{shift}")
            except Exception:
                ordered = None
                st.caption("드래그 순서 변경 컴포넌트 오류 — 폼의 '순서' 값으로 바꾸세요")
            if ordered and ordered != labels and sorted(ordered) == sorted(labels):
                if st.button("이 순서로 저장", key=f"dash_tmpl_sort_save_{shift}", disabled=ctx.readonly):
                    if not ctx.readonly and ctx.click_guard("dash_tmpl_sort_save"):
                        save_template_order(ctx, [int(lbl.split(" · ", 1)[0]) for lbl in ordered])
                    st.rerun()


# ─── 홈 카드 ─────────────────────────────────────────────────────

def render_home_card(ctx: Ctx):
    db = ctx.db
    if not tables_ready(db):
        return
    slot = R.shift_slot(now_utc())
    try:
        cards = load_cards(db, *slot)
    except Exception:
        return
    n_done = sum(1 for c in cards if c.get("status") == "done")
    txt = (f"오늘 루틴 {n_done}/{len(cards)} 완료" if cards else "오늘 루틴 생성 전")
    c1, c2 = st.columns([3, 1.2])
    c1.markdown(f'<div class="ws-chip"><b>{_html.escape(txt)}</b> · {slot[0].isoformat()} {R.SHIFT_KO[slot[1]]}</div>',
                unsafe_allow_html=True)
    c2.button("오늘 루틴 열기", key="dash_home_open", on_click=ctx.nav_go, args=("dash", "today"),
              use_container_width=True)
