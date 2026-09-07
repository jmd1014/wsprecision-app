# -*- coding: utf-8 -*-
"""생산일정 구글시트 → 생산 실적(production_log)·공정 표준(product_op_std).

시트 구조 (2026-09-07 확인, "26년 생산일정"):
  * [데이터DB] 탭: 날짜·요일·교대·장비명·작업자명·공정명('품번#스텝')·C.T.(초)·
    C.T.(분당환산)·총생산량·가동시간(H)·불량·UPH목표·시간당실생산량·실가동율·
    가동구분(가동/비가동)·정지사유분류·비고 — 입력폼→저장으로 누적 (6월~)
  * [제품별 목표생산량(백데이터)] 탭: 공정('품번#스텝')·가공시간(초)·C.T·
    유휴시간(초)·시간당 목표수량(UPH)·산정 근거·비고(장비군 CNC/MCT)
    → 공정 표준의 1차 출처 (실적 중앙값은 보조)

품번 표기: 시트는 '8HFDV-05' 처럼 '-VM' 을 뺀 약칭을 쓴다 → 마스터 pn 에서
'-VM' 을 제거한 키로 매칭 (별칭 alias_list 도 참조). 공정명의 '#' 앞이 품번,
뒤가 스텝 ('#20#30' 합병·'#황삭'·'#30(수동)' 같은 변형은 텍스트 유지).
"""
import hashlib
import re

from utils.op_std import normalize_machine

DEFAULT_SHEET_ID = "1a33c-kO4YufEtQB-iJN6sJZFm4n9pXgxJj0ZsfRkoS0"
DATA_TAB = "데이터DB"
STD_TAB = "제품별 목표생산량(백데이터)"

_STEP_RE = re.compile(r"#\s*(\d+)")


def pn_key(pn):
    """매칭 키: 대문자, 공백 제거, '-VM' 제거."""
    if not pn:
        return ""
    s = re.sub(r"\s+", "", str(pn)).upper()
    return s.replace("-VM-", "-").replace("-VM", "")


def split_process(proc):
    """'4PDVN-03#20' → ('4PDVN-03', '#20', 20); '11SDF-BL-10' → (pn, '', None)."""
    s = str(proc or "").strip()
    if not s:
        return "", "", None
    if "#" in s:
        pn, _, rest = s.partition("#")
        step_s = "#" + rest
    else:
        pn, step_s = s, ""
    m = _STEP_RE.search(step_s)
    return pn.strip(), step_s.strip(), (int(m.group(1)) if m else None)


def build_pn_index(products):
    """products [{product_id, pn, alias_list, archived_at}] → {key: product_id}
    활성 우선, 같은 키에 활성이 둘이면 None(모호)."""
    idx, amb = {}, set()

    def _put(k, pid, active):
        if not k:
            return
        cur = idx.get(k)
        if cur is None:
            idx[k] = (pid, active)
        elif cur[0] != pid:
            if active and not cur[1]:
                idx[k] = (pid, active)
            elif active == cur[1]:
                amb.add(k)

    for p in products:
        active = not p.get("archived_at")
        _put(pn_key(p.get("pn")), p["product_id"], active)
        for a in str(p.get("alias_list") or "").split(","):
            _put(pn_key(a), p["product_id"], active)
    return {k: v[0] for k, v in idx.items() if k not in amb}


def _num(v):
    try:
        if v in (None, "", "-"):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def row_key(date_s, shift, machine, process, qty, hours, worker):
    raw = "|".join(str(x or "") for x in
                   (date_s, shift, machine, process, qty, hours, worker))
    return "PS-" + hashlib.md5(raw.encode("utf-8")).hexdigest()[:20]


def parse_data_rows(rows, pn_index):
    """[데이터DB] 행(values_only, 헤더 제외) → production_log 레코드 목록.

    returns: (records, stats) — stats: rows, run, stop, matched, unmatched_pns
    """
    recs, stats = [], {"rows": 0, "run": 0, "stop": 0, "matched": 0,
                       "unmatched": {}}
    seen = {}
    for r in rows:
        r = list(r) + [None] * (17 - len(r))
        dt, _wd, shift, machine, worker, proc, ct, _ctm, qty, hrs, ng, \
            uph_t, _uph_a, _eff, run, stop, rmk = r[:17]
        if dt is None or not machine:
            continue
        date_s = (dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime")
                  else str(dt)[:10])
        stats["rows"] += 1
        is_run = (str(run or "").strip() == "가동") or bool(_num(qty))
        pn_raw, step_s, step = split_process(proc)
        pid = pn_index.get(pn_key(pn_raw)) if pn_raw else None
        if is_run:
            stats["run"] += 1
            if pid:
                stats["matched"] += 1
            elif pn_raw:
                stats["unmatched"][pn_raw] = stats["unmatched"].get(
                    pn_raw, 0) + 1
        else:
            stats["stop"] += 1
        q, h = _num(qty) or 0.0, _num(hrs)
        # 같은 값의 행이 시트에 두 번 있으면(같은 교대에 같은 공정 두 번
        # 입력) 둘 다 유지 — 키에 발생 순번을 붙인다
        k0 = row_key(date_s, shift, normalize_machine(machine), proc, q, h,
                     worker)
        seen[k0] = seen.get(k0, 0) + 1
        recs.append({
            "log_date": date_s,
            "shift": (str(shift).strip() if shift else None),
            "machine": normalize_machine(machine),
            "worker": (str(worker).strip() if worker else None),
            "process": (str(proc).strip() if proc else None),
            "process_step": step,
            "pn": pn_raw or None,
            "product_id": pid,
            "cycle_time": _num(ct),
            "total_qty": q,
            "defect_qty": _num(ng) or 0.0,
            "uptime_hours": h,
            "uph_target": _num(uph_t),
            "uph_actual": (round(q / h, 1) if h and h > 0 and q else None),
            "efficiency_pct": (round(q / h / _num(uph_t) * 100, 1)
                               if h and _num(uph_t) and q else None),
            "run_flag": ("가동" if is_run else "비가동"),
            "stop_reason": (str(stop).strip() if stop and str(stop).strip()
                            not in ("", "-") else None),
            "remark": (str(rmk).strip() if rmk else None)
                      or (None if (pid or not is_run)
                          else f"품번 미매칭 (시트 표기: {pn_raw})"),
            "source": "SHEET_DB",
            "sheet_key": k0 + (f"-{seen[k0]}" if seen[k0] > 1 else ""),
        })
    return recs, stats


def parse_std_rows(rows, pn_index):
    """[제품별 목표생산량] 행 → 공정 표준 후보 {(pn, process): {...}}."""
    out = {}
    for r in rows:
        r = list(r) + [None] * (8 - len(r))
        _no, proc, work_sec, _ct, idle_sec, uph, basis, note = r[:8]
        if not proc or "#" not in str(proc) and not _num(uph):
            continue
        if not _num(uph):
            continue
        pn_raw, step_s, step = split_process(proc)
        if not pn_raw:
            continue
        grp = str(note or "").strip().upper() or None
        out[(pn_raw, str(proc).strip())] = {
            "pn": pn_raw, "process": str(proc).strip(), "step": step,
            "product_id": pn_index.get(pn_key(pn_raw)),
            "group_code": grp if grp in ("CNC", "MCT") else None,
            "ct_sec": _num(work_sec), "idle_sec": _num(idle_sec),
            "uph_sheet": _num(uph),
            "note": (str(basis).strip() if basis else None),
        }
    return out


def load_workbook_tabs(path):
    """xlsx 경로 → (데이터DB 행, 표준 행) — 헤더 제거."""
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    data = list(wb[DATA_TAB].iter_rows(values_only=True))[1:] \
        if DATA_TAB in wb.sheetnames else []
    std = []
    if STD_TAB in wb.sheetnames:
        for r in wb[STD_TAB].iter_rows(values_only=True):
            if r and len(r) > 5 and r[1] and "#" in str(r[1]):
                std.append(r)
    return data, std
