# -*- coding: utf-8 -*-
"""공정 표준(품번 × 공정 스텝 UPH) — 생산 실적(production_log)에서 산출.

생산 계획 기초 (2026-09-07 사용자 확정):
  * 계획 단위는 **작업 = 품번 × 공정 스텝**(예: 4PDVN-03 CNC#10). 품목 하나가
    여러 공정을 거치고 공정마다 수량·시간이 다르므로 품목 단위로는 부하를
    셀 수 없다. 작업은 장비군(CNC/MCT)에 배정되고, 품목 완성 = 마지막 작업.
  * 표준 UPH 는 실적에서 자동 산출(중앙값) → 확인 후 확정. 확정된 표준은
    재산출해도 덮어쓰지 않고 자동값만 갱신한다 (표준이 빈약하면 전개 중
    수정이 많아 힘들다 — 사용자 경험).
  * 가동률 = 표준 UPH 대비 실제 생산량 (생산 보고와 같은 기준).

이 모듈은 DB 를 모른다 — 입력은 production_log 행, 출력은 표준 dict.
"""
import re
from statistics import median

_MACHINE_RE = re.compile(r"^\s*([A-Za-z]+)\s*[-_ ]?\s*(\d+)\s*$")


def normalize_machine(name):
    """'MCT 03' / 'mct-3' / 'CNC07' → 'MCT03' / 'MCT03' / 'CNC07'."""
    if not name:
        return None
    # 'CNC13(다인로봇)' 처럼 괄호 설명이 붙은 표기는 괄호 앞만 (2026-09-07)
    base = re.split(r"[(\[（]", str(name), 1)[0]
    m = _MACHINE_RE.match(base)
    if not m:
        return str(name).strip().upper().replace(" ", "")
    return f"{m.group(1).upper()}{int(m.group(2)):02d}"


def machine_group(name):
    """장비군 = 알파벳 접두어 (CNC / MCT …)."""
    n = normalize_machine(name)
    if not n:
        return None
    m = re.match(r"^([A-Z]+)", n)
    return m.group(1) if m else n


def process_group(process):
    """공정명 'CNC#10' → 'CNC' (공정이 지정하는 장비군)."""
    if not process:
        return None
    m = re.match(r"^\s*([A-Za-z]+)", str(process))
    return m.group(1).upper() if m else None


def _hhmm(t):
    try:
        h, m = str(t).strip().split(":")[:2]
        return int(h) * 60 + int(m)
    except Exception:
        return None


def row_hours(work_start, work_end, shift=None):
    """작업 구간 시간(h). 야간 자정 넘김 처리, 시작=종료(스캔형)는 None."""
    a, b = _hhmm(work_start), _hhmm(work_end)
    if a is None or b is None or a == b:
        return None
    if shift == "야간" and a < 360:
        a += 1440
    if shift == "야간" and b < 360:
        b += 1440
    if b < a:
        b += 1440
    h = (b - a) / 60.0
    return h if 0 < h <= 14 else None


def aggregate(rows, min_hours=0.25):
    """production_log 행 → 표준 후보.

    rows: [{pn, product_id, process, process_step, machine, shift,
            total_qty, defect_qty, work_start, work_end, log_date}]
    returns: {"ops": {(pn, process): {...}}, "machines": {(pn, process,
              machine): {...}}}
      op: pn, product_id, process, step, group, uph_auto(중앙값),
          uph_mean, sample_n(구간 행 수), hours, qty, machines(list),
          first_date, last_date
    """
    per_op, per_m = {}, {}
    for r in rows:
        pn = (r.get("pn") or "").strip()
        proc = (r.get("process") or "").strip()
        qty = float(r.get("total_qty") or 0)
        if not pn or not proc or qty <= 0:
            continue
        # 시트 동기화 행은 가동시간(H)이 직접 있다 — 우선 사용
        h = r.get("uptime_hours")
        try:
            h = float(h) if h not in (None, "") else None
        except (TypeError, ValueError):
            h = None
        if h is None or h <= 0:
            h = row_hours(r.get("work_start"), r.get("work_end"),
                          r.get("shift"))
        if h is None or h < min_hours:
            continue
        uph = qty / h
        mach = normalize_machine(r.get("machine"))
        k = (pn, proc)
        o = per_op.setdefault(k, {
            "pn": pn, "product_id": r.get("product_id"), "process": proc,
            "step": r.get("process_step"),
            "group": process_group(proc) or machine_group(mach),
            "uphs": [], "hours": 0.0, "qty": 0.0, "machines": set(),
            "first_date": None, "last_date": None})
        if not o["product_id"] and r.get("product_id"):
            o["product_id"] = r.get("product_id")
        o["uphs"].append(uph)
        o["hours"] += h
        o["qty"] += qty
        if mach:
            o["machines"].add(mach)
        d = str(r.get("log_date") or "")[:10]
        if d:
            o["first_date"] = min(o["first_date"] or d, d)
            o["last_date"] = max(o["last_date"] or d, d)
        if mach:
            m = per_m.setdefault((pn, proc, mach), {
                "pn": pn, "process": proc, "machine": mach,
                "uphs": [], "hours": 0.0, "qty": 0.0, "runs": 0,
                "last_date": None})
            m["uphs"].append(uph)
            m["hours"] += h
            m["qty"] += qty
            m["runs"] += 1
            if d:
                m["last_date"] = max(m["last_date"] or d, d)

    ops = {}
    for k, o in per_op.items():
        ops[k] = {
            "pn": o["pn"], "product_id": o["product_id"],
            "process": o["process"], "step": o["step"],
            "group": o["group"],
            "uph_auto": round(median(o["uphs"]), 1),
            "uph_mean": round(o["qty"] / o["hours"], 1) if o["hours"] else None,
            "sample_n": len(o["uphs"]),
            "hours": round(o["hours"], 2), "qty": o["qty"],
            "machines": sorted(o["machines"]),
            "first_date": o["first_date"], "last_date": o["last_date"],
        }
    machines = {}
    for k, m in per_m.items():
        machines[k] = {
            "pn": m["pn"], "process": m["process"], "machine": m["machine"],
            "uph_actual": round(median(m["uphs"]), 1),
            "runs": m["runs"], "hours": round(m["hours"], 2),
            "qty": m["qty"], "last_date": m["last_date"],
        }
    return {"ops": ops, "machines": machines}


def op_hours(qty, uph, setup_min=0):
    """작업 소요 시간(h) = 수량 ÷ 표준 UPH + 준비시간."""
    if not uph or float(uph) <= 0:
        return None
    return float(qty) / float(uph) + float(setup_min or 0) / 60.0
