# -*- coding: utf-8 -*-
"""생산 계획 › 주간 계획·부하 — 순수 함수 (2026-10-14, 계획서 20261014_L2_주간부하리포트.md).

설계 요지(사용자 결정 2026-10-14):
  * 계획 단위 = 작업(op) = 품번 × 스텝 묶음. 한 행 = "어느 장비군에서 몇 개를 몇 UPH 로".
    한 설비에서 이어서 하는 스텝들은 한 행('#30#40#50#60'), 설비가 바뀌면 행을 나눈다.
  * 표준(product_op_std)은 참고값 — 행마다 UPH·장비군을 고칠 수 있고 표준에는 영향 없음.
  * 근무 체계: 요일 유형(WEEKDAY/SATURDAY/HOLIDAY/OFF)별 주/야 시간. 기본 평일 10/10,
    토·공휴일 6/6, 일요일 OFF. 예외일(공휴일·특근)은 work_calendar 에만 저장.
  * 능력 = Σ설비 Σ날짜 [day_h + night_h×night_active] × (토·공휴일이면 sat_active), active 만.
  * 수주·실적과는 연결하지 않는다(단독 기능). 이 모듈은 DB 를 모른다.
"""
import re
from datetime import date, timedelta

from utils.op_std import machine_group, normalize_machine
from utils.prod_sheet import pn_key

DAY_TYPES = ("WEEKDAY", "SATURDAY", "HOLIDAY", "OFF")
DEFAULT_PROFILES = {
    "WEEKDAY": (10.0, 10.0),
    "SATURDAY": (6.0, 6.0),
    "HOLIDAY": (6.0, 6.0),
    "OFF": (0.0, 0.0),
}
UPH_SOURCES = ("CONFIRMED", "SHEET", "AUTO", "MANUAL", "EST")
ETC_GROUP = "ETC"

_STEP_NUM_RE = re.compile(r"#\s*(\d+)")
_PAREN_RE = re.compile(r"[(（\[][^)）\]]*[)）\]]")


# ─────────────────────────── 주·요일 유형 ───────────────────────────
def week_bounds(d):
    """d 가 속한 주의 (월요일, 일요일)."""
    d = _to_date(d)
    start = d - timedelta(days=d.weekday())
    return start, start + timedelta(days=6)


def week_dates(week_start):
    """월~일 7일."""
    s = _to_date(week_start)
    return [s + timedelta(days=i) for i in range(7)]


def day_type(d, calendar=None):
    """요일 유형. calendar {date|'YYYY-MM-DD': day_type} 의 예외가 우선.
    기본: 월~금 WEEKDAY, 토 SATURDAY, 일 OFF."""
    d = _to_date(d)
    if calendar:
        v = calendar.get(d) or calendar.get(d.isoformat())
        if v in DAY_TYPES:
            return v
    wd = d.weekday()
    if wd == 6:
        return "OFF"
    if wd == 5:
        return "SATURDAY"
    return "WEEKDAY"


def profile_hours(dt, profiles=None):
    """요일 유형 → (주간 h, 야간 h). 표가 비거나 값이 없으면 기본값."""
    if dt == "OFF":
        return 0.0, 0.0
    row = (profiles or {}).get(dt)
    if row is None:
        return DEFAULT_PROFILES.get(dt, (0.0, 0.0))
    if isinstance(row, dict):
        dh, nh = row.get("day_hours"), row.get("night_hours")
    else:
        dh, nh = row
    return _f(dh), _f(nh)


def machine_day_hours(dt, profiles, machine):
    """설비 한 대의 그 날 가용 시간."""
    if not machine or not _truthy(machine.get("active", True)):
        return 0.0
    dh, nh = profile_hours(dt, profiles)
    if dt in ("SATURDAY", "HOLIDAY") and not _truthy(machine.get("sat_active", True)):
        return 0.0
    hours = dh
    if _truthy(machine.get("night_active", True)):
        hours += nh
    return hours


def machine_shift_hours(dt, profiles, machine):
    """설비 한 대의 그 날 (주간 h, 야간 h) — 플래그 반영. 보드 칸 시간용."""
    if not machine or not _truthy(machine.get("active", True)):
        return 0.0, 0.0
    dh, nh = profile_hours(dt, profiles)
    if dt in ("SATURDAY", "HOLIDAY") and not _truthy(machine.get("sat_active", True)):
        return 0.0, 0.0
    if not _truthy(machine.get("night_active", True)):
        nh = 0.0
    return dh, nh


def week_capacity(week_start, machines, profiles=None, calendar=None):
    """{장비군: 가용 h} — 장비군 없는 설비는 ETC."""
    cap = {}
    days = [(d, day_type(d, calendar)) for d in week_dates(week_start)]
    for m in machines or []:
        g = (m.get("group_code") or "").strip().upper() or ETC_GROUP
        total = sum(machine_day_hours(dt, profiles, m) for _, dt in days)
        cap[g] = cap.get(g, 0.0) + total
    return cap


# ─────────────────────────── 작업(op) 키 ───────────────────────────
def parse_steps(text):
    """'#30#40' / '40,30' / '30 40' / '' / '-' → 정렬·중복 제거한 스텝 목록.
    숫자가 아닌 토큰이 있으면 ValueError."""
    s = str(text or "").strip()
    if s in ("", "-"):
        return []
    toks = [t for t in re.split(r"[#,\s]+", s) if t]
    out = set()
    for t in toks:
        if not t.isdigit():
            raise ValueError(f"스텝이 숫자가 아닙니다: {t!r}")
        out.add(int(t))
    return sorted(out)


def op_label(pn, steps):
    """작업 표기: 스텝 없음 → pn, 있으면 pn#10#20."""
    steps = sorted(set(int(s) for s in (steps or [])))
    return str(pn).strip() + ("".join(f"#{s}" for s in steps) if steps else "")


def steps_from_process(process):
    """표준·실적 공정명 → 스텝 목록. 'MRG6-07#20#30'→[20,30], 'CNC#10'→[10],
    '8HFDV-VM-09#10(픽시스#10)'→[10], '40ABV-FL-01#10.#20'→[10,20], '4PDVN-03'→[]."""
    s = _PAREN_RE.sub("", str(process or ""))
    return sorted({int(m) for m in _STEP_NUM_RE.findall(s)})


def op_key(pn, steps, product_id=None):
    """정규화 키 — 실적 매칭용(2차). product_id 우선, 없으면 pn_key."""
    base = product_id or pn_key(pn)
    return f"{base}|" + "#".join(str(s) for s in sorted(set(int(x) for x in (steps or []))))


def op_key_from_process(process, pn_index=None):
    """실적 공정명 → (op_key, unparsed). 괄호 제거 후 첫 '#' 앞 = 품번.
    숫자 스텝이 하나도 없고 '#' 뒤에 글자가 있으면 unparsed=True."""
    s = _PAREN_RE.sub("", str(process or "")).strip()
    pn, _, rest = s.partition("#")
    steps = steps_from_process(s)
    unparsed = bool(rest.strip()) and not steps
    pid = None
    if pn_index:
        pid = pn_index.get(pn_key(pn))
        if isinstance(pid, tuple):
            pid = pid[0]
    return op_key(pn.strip(), steps, pid), unparsed


# ─────────────────────────── 시간·UPH ───────────────────────────
def row_hours(qty, uph, setup_min=0):
    """수량 ÷ UPH + 준비(분)/60. UPH 없음·0 → None. 수량 0 → 0.0(준비 미가산)."""
    q = _f(qty)
    if q < 0:
        raise ValueError("수량이 음수입니다")
    u = _f(uph)
    if u < 0:
        raise ValueError("UPH 가 음수입니다")
    if u <= 0:
        return None
    if q == 0:
        return 0.0
    return round(q / u + _f(setup_min) / 60.0, 2)


def est_uph(uphs):
    """합친 작업 UPH 참고값 = 1/Σ(1/UPH_i). 하나라도 없거나 0 이면 None."""
    vals = []
    for u in uphs or []:
        v = _f(u)
        if v <= 0:
            return None
        vals.append(v)
    if not vals:
        return None
    return round(1.0 / sum(1.0 / v for v in vals), 2)


def std_uph(std):
    """표준 한 행의 참고 UPH 와 출처: 확정 > 시트 > 실적 중앙값."""
    if not std:
        return None, None
    if _f(std.get("uph_std")) > 0 and (std.get("std_status") or "").upper() == "CONFIRMED":
        return _f(std.get("uph_std")), "CONFIRMED"
    if _f(std.get("uph_sheet")) > 0:
        return _f(std.get("uph_sheet")), "SHEET"
    for k in ("uph_auto", "uph_std", "uph_mean"):
        if _f(std.get(k)) > 0:
            return _f(std.get(k)), "AUTO"
    return None, None


def std_group(std, machine_groups):
    """표준의 장비군 — 설비 장비군 집합에 있으면 그대로, 아니면 machines_used 의
    첫 설비 장비군, 그것도 없으면 ETC. 반환 (group, 확인 필요 여부)."""
    groups = {g.upper() for g in (machine_groups or []) if g}
    g = (std.get("group_code") or "").strip().upper() if std else ""
    if g and g in groups:
        return g, False
    used = std.get("machines_used") if std else None
    if isinstance(used, str):
        used = [x for x in re.split(r"[,\s;]+", used) if x]
    for m in used or []:
        mg = machine_group(m)
        if mg and mg in groups:
            return mg, True
    return ETC_GROUP, True


# ─────────────────────────── 전개·합치기·나누기 ───────────────────────────
def expand_ops(pn, product_id, stds, machine_groups):
    """품번 → 계획 행 목록(표준이 있으면 공정명 단위, 없으면 품번 한 행).
    행: {pn, product_id, steps, op_label, op_key, seq, group_code, group_check,
         qty, uph, uph_source, setup_min, hours}"""
    rows = []
    stds = [s for s in (stds or []) if _truthy(s.get("active", True))]
    units = []
    for s in stds:
        steps = steps_from_process(s.get("process"))
        if not steps and s.get("step") is not None:
            steps = [int(s["step"])]
        units.append((steps, s))
    # 세부 공정(단일 스텝) 표준이 기본. 합친 공정명('#20#30') 표준은 그 스텝 전부가 단일 스텝으로
    # 없을 때만 전개하고, 있으면 사용자가 합칠 때 참고값으로만 쓴다(겹침 방지). 스텝 없는 행은
    # 스텝 있는 행이 하나라도 있으면 건너뛴다 (2026-10-14 현장 테스트: MRG6-07·11SDF-BL-10)
    singles = {st[0] for st, _ in units if len(st) == 1}
    any_stepped = any(st for st, _ in units)
    picked, covered = [], set()
    for st, s in sorted(units, key=lambda t: (len(t[0]) != 1, t[0] or [9999])):
        if not st:
            if any_stepped:
                continue
            picked.append((st, s))
            continue
        if len(st) > 1 and (set(st) & singles or set(st) & covered):
            continue
        if set(st) & covered:
            continue
        picked.append((st, s))
        covered |= set(st)
    picked.sort(key=lambda t: (t[0] or [9999]))
    for i, (steps, s) in enumerate(picked):
        uph, src = std_uph(s)
        g, chk = std_group(s, machine_groups)
        rows.append(_row(pn, product_id, steps, i, g, chk, 0, uph, src,
                         _f(s.get("setup_min"))))
    if not rows:
        rows.append(_row(pn, product_id, [], 0, ETC_GROUP, True, 0, None, None, 0.0))
    return rows


def merge_rows(rows):
    """여러 작업 행 → 한 행(같은 품번). UPH 는 est_uph, setup 은 합, qty 는 최대,
    장비군은 첫 행. 스텝은 합집합."""
    rows = list(rows)
    if not rows:
        return None
    pn, pid = rows[0]["pn"], rows[0].get("product_id")
    steps = sorted({s for r in rows for s in (r.get("steps") or [])})
    uph = est_uph([r.get("uph") for r in rows])
    src = "EST" if uph is not None else None
    return _row(pn, pid, steps, min(r.get("seq", 0) for r in rows),
                rows[0].get("group_code") or ETC_GROUP,
                any(r.get("group_check") for r in rows),
                max(_f(r.get("qty")) for r in rows), uph, src,
                sum(_f(r.get("setup_min")) for r in rows))


def split_row(row, stds, machine_groups):
    """합친 행 → 스텝별 행(각각 전량 qty). 표준에 그 스텝이 있으면 그 UPH·setup."""
    out = []
    by_step = {}
    for s in stds or []:
        for st in steps_from_process(s.get("process")) or (
                [int(s["step"])] if s.get("step") is not None else []):
            by_step.setdefault(st, s)
    for i, st in enumerate(sorted(set(row.get("steps") or []))):
        s = by_step.get(st)
        uph, src = std_uph(s) if s else (None, None)
        g, chk = (std_group(s, machine_groups) if s
                  else (row.get("group_code") or ETC_GROUP, True))
        out.append(_row(row["pn"], row.get("product_id"), [st],
                        row.get("seq", 0) + i, g, chk, _f(row.get("qty")),
                        uph, src, _f(s.get("setup_min")) if s else 0.0))
    return out or [row]


# ─────────────────────────── 검증·요약·변경 감지 ───────────────────────────
def validate_week(rows):
    """저장 전 검증. 반환 (errors, warnings) — 각 항목 (행 번호 1-base, 메시지)."""
    errors, warnings = [], []
    seen_steps = {}
    seen_label = {}
    for i, r in enumerate(rows, start=1):
        pn = str(r.get("pn") or "").strip()
        if not pn:
            errors.append((i, "품번이 비어 있습니다"))
            continue
        q = r.get("qty")
        if q is None or (isinstance(q, float) and q != q):
            errors.append((i, f"{pn}: 수량을 입력하세요"))
            continue
        if _f(q) < 0:
            errors.append((i, f"{pn}: 수량이 음수입니다"))
        if r.get("uph") is not None and _f(r.get("uph")) < 0:
            errors.append((i, f"{pn}: UPH 가 음수입니다"))
        g = str(r.get("group_code") or "").strip().upper()
        if not GROUP_RE.fullmatch(g):
            errors.append((i, f"{pn}: 장비군 형식 오류 '{g}' (영문·숫자 10자 이내)"))
        steps = set(r.get("steps") or [])
        for j, prev in seen_steps.get(pn, []):
            if steps and prev and steps & prev and steps != prev:
                errors.append((i, f"{pn}: {j}행과 스텝이 겹칩니다 "
                                  f"({_lbl(steps)} ↔ {_lbl(prev)})"))
        seen_steps.setdefault(pn, []).append((i, steps))
        key = (pn, op_label(pn, steps), (r.get("group_code") or "").upper())
        if key in seen_label:
            warnings.append((i, f"{pn}{_lbl(steps)}: {seen_label[key]}행과 같은 작업·장비군"))
        else:
            seen_label[key] = i
    return errors, warnings


def summarize(rows, capacity):
    """장비군별 {need, cap, ratio, rows, unknown}. ratio 는 cap 0 이면 None."""
    out = {}
    for r in rows or []:
        g = (r.get("group_code") or ETC_GROUP).upper()
        e = out.setdefault(g, {"need": 0.0, "cap": 0.0, "ratio": None,
                               "rows": 0, "unknown": 0})
        e["rows"] += 1
        h = r.get("hours")
        if h is None:
            h = row_hours(r.get("qty"), r.get("uph"), r.get("setup_min"))
        if h is None:
            e["unknown"] += 1
        else:
            e["need"] += float(h)
    for g, c in (capacity or {}).items():
        e = out.setdefault(g.upper(), {"need": 0.0, "cap": 0.0, "ratio": None,
                                       "rows": 0, "unknown": 0})
        e["cap"] = float(c)
    for e in out.values():
        e["need"] = round(e["need"], 1)
        e["ratio"] = round(e["need"] / e["cap"], 3) if e["cap"] > 0 else None
    return out


GROUP_RE = re.compile(r"^[A-Z][A-Z0-9]{0,9}$")


def updated_epoch(s):
    """PostgREST 의 updated_at 문자열('2026-10-14T01:00:00.5+00:00' 등) → 초 단위 정수.
    형식을 못 읽으면 None."""
    if not s:
        return None
    try:
        from datetime import datetime, timezone
        t = str(s).strip().replace("Z", "+00:00")
        if " " in t and "T" not in t:
            t = t.replace(" ", "T", 1)
        d = datetime.fromisoformat(t)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return int(d.timestamp() // 1)
    except Exception:
        return None


def fingerprint(rows):
    """저장 전 변경 감지 — 행 수 : id 합 : 최신 updated_at(초 단위 정수).
    서버 save_week_plan 의 count:sum(id):floor(epoch(max(updated_at))) 와 같은 형식.
    문자열 형식(T/공백, +00/+00:00)에 의존하지 않는다. 행이 없으면 'n:0:'."""
    ids = sorted(int(r.get("plan_item_id") or 0) for r in rows or [])
    eps = [e for e in (updated_epoch(r.get("updated_at")) for r in rows or []) if e is not None]
    last = str(max(eps)) if eps else ""
    return f"{len(ids)}:{sum(ids)}:{last}"


def build_payload(rows, edits, stds_for, machine_groups, by=None):
    """표 편집 결과 → 저장 페이로드.

    rows:  로드된(또는 추가된) 계획 행 목록(표 순서)
    edits: 표 행과 같은 순서의 dict 목록 — {delete:bool, steps:str, group:str, qty, uph,
           setup, due:(date|str|None), note:str, split:bool}
    stds_for(pn, product_id) → 표준 목록 (합치기·나누기 참고값용)
    반환: (out_rows, delete_ids, errors[(표 행번호, 메시지)], warnings[(표 행번호, 메시지)])
    규칙: 스텝이 바뀌면 UPH 는 표준으로 다시 추정(합친 작업 = 1/Σ(1/UPH), EST) — 표준이 없으면
    UPH 비움. UPH 를 참고값과 다르게 고치면 MANUAL. 삭제가 나누기보다 우선. 나누기는 수량 필수.
    seq 는 결과 순서로 재번호. errors 가 있으면 저장하지 않는다."""
    out, dele, errors, warnings = [], [], [], []
    cache = {}

    def _stds(pn, pid):
        k = (pn, pid)
        if k not in cache:
            cache[k] = stds_for(pn, pid) or []
        return cache[k]

    for i, (r0, e) in enumerate(zip(rows, edits), start=1):
        pn = str(r0.get("pn") or "").strip()
        if e.get("delete"):
            if r0.get("plan_item_id"):
                dele.append(int(r0["plan_item_id"]))
            continue
        try:
            steps = parse_steps(e.get("steps"))
        except ValueError as ex:
            errors.append((i, f"{pn}: {ex}"))
            continue
        q = e.get("qty")
        qty = None if q is None or (isinstance(q, float) and q != q) else float(q)
        u = e.get("uph")
        uph_new = (None if u is None or (isinstance(u, float) and u != u) or float(u) <= 0
                   else float(u))
        uph_old = (float(r0["uph"]) if r0.get("uph") not in (None, "") else None)
        old_steps = sorted(set(int(x) for x in (r0.get("steps") or [])))
        if steps != old_steps:
            # 합치기/스텝 변경 → 표준으로 다시 추정 (H-1)
            uph_new, src = _est_from_stds(pn, steps, _stds(pn, r0.get("product_id")))
            if uph_new is None:
                warnings.append((i, f"{pn}{_lbl(set(steps))}: 표준이 없어 UPH 를 비웠습니다 — 직접 적으세요"))
        elif uph_new is None:
            src = None
        elif uph_old is not None and abs(uph_new - uph_old) < 0.05:
            src = r0.get("uph_source") or "MANUAL"
        else:
            src = "MANUAL"
        sm = e.get("setup")
        setup = 0.0 if sm is None or (isinstance(sm, float) and sm != sm) else float(sm)
        due = e.get("due")
        due_s = None
        if due not in (None, "") and str(due) != "NaT":
            due_s = str(due)[:10]
        row = {"plan_item_id": r0.get("plan_item_id"), "product_id": r0.get("product_id"),
               "pn": pn, "steps": steps, "op_label": op_label(pn, steps),
               "op_key": op_key(pn, steps, r0.get("product_id")), "seq": 0,
               "group_code": str(e.get("group") or r0.get("group_code") or ETC_GROUP).strip().upper(),
               "qty": qty, "uph": uph_new, "uph_source": src, "setup_min": setup,
               "due_date": due_s, "note": (str(e.get("note") or "").strip() or None),
               "by": by, "_ui_row": i}
        if e.get("split"):
            if len(steps) <= 1:
                warnings.append((i, f"{pn}: 스텝이 하나라 나눌 수 없습니다 — 그대로 저장"))
            elif qty is None:
                errors.append((i, f"{pn}: 나누기 전에 수량을 입력하세요"))
                continue
            else:
                for sp in split_row({**row, "qty": qty}, _stds(pn, r0.get("product_id")), machine_groups):
                    out.append({**row, "plan_item_id": None, "steps": sp["steps"],
                                "op_label": sp["op_label"], "op_key": sp["op_key"],
                                "group_code": sp["group_code"], "uph": sp["uph"],
                                "uph_source": sp["uph_source"], "setup_min": sp["setup_min"]})
                if row.get("plan_item_id"):
                    dele.append(int(row["plan_item_id"]))
                continue
        out.append(row)
    for k, r in enumerate(out):
        r["seq"] = k
    v_err, v_warn = validate_week(out)
    errors += [(out[j - 1].get("_ui_row", j), m) for j, m in v_err]
    warnings += [(out[j - 1].get("_ui_row", j), m) for j, m in v_warn]
    return out, dele, errors, warnings


def _est_from_stds(pn, steps, stds):
    """스텝 묶음의 UPH 참고값 — 표준을 '단위'로 조합한다: 요청 스텝에 포함되는 표준 중
    큰 묶음부터 겹치지 않게 고르고, 전부 덮이면 1/Σ(1/UPH)(단위가 하나면 그 값·출처).
    덮지 못하는 스텝이 있으면 (None, None)."""
    want = set(int(x) for x in (steps or []))
    if not want:
        return None, None
    units, covered = [], set()
    cands = []
    for s in stds or []:
        if not _truthy(s.get("active", True)):
            continue
        st = set(steps_from_process(s.get("process")))
        if not st and s.get("step") is not None:
            st = {int(s["step"])}
        if st and st <= want:
            cands.append((st, s))
    cands.sort(key=lambda t: (-len(t[0]), sorted(t[0])))
    for st, s in cands:
        if st & covered:
            continue
        u, _ = std_uph(s)
        if u is None:
            return None, None
        units.append(s)
        covered |= st
    if covered != want or not units:
        return None, None
    if len(units) == 1:
        return std_uph(units[0])
    e = est_uph([std_uph(u)[0] for u in units])
    return (e, "EST") if e is not None else (None, None)


# ─────────────────────────── 내부 ───────────────────────────
def _row(pn, pid, steps, seq, group, check, qty, uph, src, setup):
    steps = sorted(set(int(s) for s in (steps or [])))
    return {"pn": str(pn).strip(), "product_id": pid, "steps": steps,
            "op_label": op_label(pn, steps), "op_key": op_key(pn, steps, pid),
            "seq": int(seq or 0), "group_code": (group or ETC_GROUP).upper(),
            "group_check": bool(check), "qty": _f(qty), "uph": uph,
            "uph_source": src, "setup_min": _f(setup),
            "hours": row_hours(qty, uph, setup)}


def _lbl(steps):
    return "".join(f"#{s}" for s in sorted(steps)) if steps else "(스텝 없음)"


def _to_date(d):
    if isinstance(d, date):
        return d
    return date.fromisoformat(str(d)[:10])


def _f(v):
    try:
        if v is None or v == "" or (isinstance(v, float) and v != v):
            return 0.0
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _truthy(v):
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "t", "y", "yes")
    return bool(v)
