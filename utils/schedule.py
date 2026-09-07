# -*- coding: utf-8 -*-
"""설비 스케줄 보드 — 작업 큐·보드 셀 상태·부하 계산 (순수 로직).

1단계 (2026-09-07 사용자 확정, 목업 승인):
  * 작업 큐 = 회차 미납이 있는 품번의 작업(품번#스텝) 목록. 잔여 = 미납 −
    완성 재고 − 재공(열린 배치). 필요 시간 = 잔여 ÷ 표준 UPH. 납기 = 가장
    이른 미충당 회차. 배정 = 보드에 잡힌 계획 수량 합.
  * 보드 셀 = 설비 × 날짜 × 교대(주간/야간). 실적(production_log, 같은 설비·
    날짜·교대·작업)이 붙으면 상태가 계획 → 진행 → 달성/미달로 바뀐다.
  * 부하 = 계획 시간 합 ÷ 가용 시간(가동 설비 × 교대 × 교대당 시간, 야간
    미운영 설비는 야간 제외).
"""
from datetime import date, timedelta

SHIFTS = ("주간", "야간")


def week_start(d):
    """d 가 속한 주의 월요일."""
    d = d if isinstance(d, date) else date.fromisoformat(str(d)[:10])
    return d - timedelta(days=d.weekday())


def week_days(start, n=6):
    """월~토 (n=6) 날짜 목록."""
    return [start + timedelta(days=i) for i in range(n)]


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def build_queue(lines, rounds, stock, wip, stds, alloc, capable=None):
    """작업 큐.

    lines:  미납 수주 라인 [{product_id, pn, pending_qty}]
    rounds: 회차 [{soi_id?, product_id, due_date, qty, delivered_qty}]
    stock:  {product_id: 완성 재고}
    wip:    {product_id: 재공 수량}
    stds:   [{product_id, pn, process, step, uph_std, setup_min, group_code}]
    alloc:  {(pn, process): 배정 수량}
    capable: {(pn, process): [machine_id, ...]}
    returns: [{product_id, pn, process, step, group, due, net, uph, hours,
               alloc, machines, no_std}] 납기순
    """
    pend, due = {}, {}
    for l in lines:
        pid = l.get("product_id")
        if not pid:
            continue
        pend[pid] = pend.get(pid, 0.0) + _f(l.get("pending_qty"))
    for r in rounds:
        pid = r.get("product_id")
        if not pid or _f(r.get("qty")) - _f(r.get("delivered_qty")) <= 0:
            continue
        d = str(r.get("due_date") or "")[:10]
        if d and (pid not in due or d < due[pid]):
            due[pid] = d
    by_pid = {}
    for s in stds:
        if s.get("product_id"):
            by_pid.setdefault(s["product_id"], []).append(s)
    out = []
    for pid, p in pend.items():
        net = max(p - max(_f(stock.get(pid)), 0.0) - _f(wip.get(pid)), 0.0)
        if net <= 0:
            continue
        ops = sorted(by_pid.get(pid, []),
                     key=lambda s: (s.get("step") is None,
                                    s.get("step") or 0, s.get("process")))
        if not ops:
            pn = next((l.get("pn") for l in lines
                       if l.get("product_id") == pid and l.get("pn")), pid)
            out.append({"product_id": pid, "pn": pn, "process": None,
                        "step": None, "group": None, "due": due.get(pid),
                        "net": net, "uph": None, "hours": None,
                        "alloc": 0.0, "machines": [], "no_std": True})
            continue
        for s in ops:
            uph = _f(s.get("uph_std"))
            hours = (net / uph + _f(s.get("setup_min")) / 60.0
                     if uph > 0 else None)
            k = (s["pn"], s["process"])
            out.append({
                "product_id": pid, "pn": s["pn"], "process": s["process"],
                "step": s.get("step"), "group": s.get("group_code"),
                "due": due.get(pid), "net": net, "uph": uph or None,
                "hours": round(hours, 1) if hours is not None else None,
                "alloc": _f((alloc or {}).get(k)),
                "machines": list((capable or {}).get(k) or []),
                "no_std": False})
    out.sort(key=lambda q: (q["due"] or "9999", q["pn"],
                            q["step"] is None, q["step"] or 0))
    return out


def suggest_qty(hours, uph, setup_min=0):
    """셀 계획 수량 = (가동 시간 − 준비시간) × UPH."""
    if not uph or _f(uph) <= 0:
        return 0
    h = max(_f(hours) - _f(setup_min) / 60.0, 0.0)
    return int(round(h * _f(uph)))


def cell_status(plan, actual, plan_date, today):
    """계획 셀 상태: PLAN / RUN / DONE / SHORT."""
    p, a = _f(plan), _f(actual)
    d = str(plan_date)[:10]
    t = str(today)[:10]
    if a <= 0:
        return "SHORT" if d < t and p > 0 else "PLAN"
    if a >= p * 0.95:
        return "DONE"
    return "SHORT" if d < t else "RUN"


def build_board(machines, days, sched, logs, today):
    """보드 셀 사전.

    machines: [{machine_id, group_code, active, night_active}]
    sched:    production_schedule 행 (해당 주)
    logs:     production_log 행 (해당 주, 설비·날짜·교대·공정·수량·가동/정지)
    returns: {(machine_id, 'YYYY-MM-DD', shift): {plan, actual, status,
              stop, ...}}, {machine_id: (plan_hours, avail_hours)}
    """
    cells = {}
    for s in sched:
        if s.get("status") == "CANCELLED":
            continue
        k = (s["machine_id"], str(s["plan_date"])[:10], s["shift"])
        cells[k] = {"plan": s, "actual": 0.0, "stop": None,
                    "status": "PLAN"}
    for l in logs:
        k = (l.get("machine"), str(l.get("log_date"))[:10], l.get("shift"))
        if k[0] is None or k[2] not in SHIFTS:
            continue
        c = cells.get(k)
        if l.get("run_flag") == "비가동" or (not _f(l.get("total_qty"))
                                          and l.get("stop_reason")):
            if c is None:
                cells[k] = {"plan": None, "actual": 0.0,
                            "stop": l.get("stop_reason") or "비가동",
                            "status": "STOP"}
            elif not c["stop"]:
                c["stop"] = l.get("stop_reason")
            continue
        if c is None:
            cells[k] = {"plan": None, "actual": _f(l.get("total_qty")),
                        "stop": None, "status": "ACTUAL",
                        "process": l.get("process")}
            continue
        if c["plan"] is None:            # 계획 없는 셀에 실적 행이 또 옴
            c["actual"] += _f(l.get("total_qty"))
            c["status"] = "ACTUAL"
            if not c.get("process"):
                c["process"] = l.get("process")
            elif (l.get("process") and l["process"] != c["process"]
                  and "+" not in c["process"]):
                c["process"] = f"{c['process']} +"
            continue
        if (l.get("process") or "").strip() == (
                c["plan"].get("process") or "").strip():
            c["actual"] += _f(l.get("total_qty"))
        else:
            c.setdefault("other", 0.0)
            c["other"] += _f(l.get("total_qty"))
            c.setdefault("other_process", l.get("process"))
    for k, c in cells.items():
        if c["plan"]:
            c["status"] = cell_status(c["plan"].get("plan_qty"), c["actual"],
                                      k[1], today)
    load = {}
    ndays = len(days)
    for m in machines:
        if not m.get("active", True):
            continue
        hps = _f(m.get("hours_per_shift")) or 9.0
        avail = ndays * hps * (2 if m.get("night_active", True) else 1)
        planned = sum(_f(c["plan"].get("plan_hours"))
                      for k, c in cells.items()
                      if k[0] == m["machine_id"] and c["plan"])
        load[m["machine_id"]] = (planned, avail)
    return cells, load


def group_load(machines, load):
    """{group: (planned, avail)}"""
    out = {}
    for m in machines:
        if m["machine_id"] not in load:
            continue
        g = m.get("group_code") or "ETC"
        p, a = load[m["machine_id"]]
        gp, ga = out.get(g, (0.0, 0.0))
        out[g] = (gp + p, ga + a)
    return out
