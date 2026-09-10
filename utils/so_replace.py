# -*- coding: utf-8 -*-
"""수주 대체(단가 변경 재발주) 감지 — 순수 로직 (2026-09-10 사용자 확정).

같은 거래처·같은 품번의 미납 라인이 둘 이상이고 단가가 다르면 '단가 변동'
후보다. 도구는 판단하지 않고 근거와 추천만 보여 준다:
  * 대체 추천: 새 수량 ≈ 옛 미납 잔량(±5%) 이고 납기가 겹치거나 없음
  * 별건 추천: 그 외 (프로젝트성 별도 단가)
결정(REPLACE/KEEP)은 so_line_replacements 에 남고 다시 묻지 않는다.
"""


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def detect_pairs(lines, decided=()):
    """미납 라인 → 단가가 다른 (옛, 새) 쌍 목록.

    lines: [{soi_id, so_id, so_number, so_date, customer, product_id, pn,
             qty, pending_qty, unit_price, due_date}]  (미납 > 0 만)
    decided: {(old_soi, new_soi)} 이미 결정된 쌍
    returns: [{old, new, diff_pct, recommend, why}] — 새 라인 = 같은
             거래처·품번 중 수주일이 가장 늦은 라인, 옛 = 나머지 각각
    """
    groups = {}
    for l in lines:
        if not l.get("product_id") or _f(l.get("pending_qty")) <= 0:
            continue
        k = ((l.get("customer") or "").strip(), l["product_id"])
        groups.setdefault(k, []).append(l)
    out = []
    for k, ls in groups.items():
        if len(ls) < 2:
            continue
        ls = sorted(ls, key=lambda l: (str(l.get("so_date") or ""),
                                       l.get("soi_id") or 0))
        new = ls[-1]
        for old in ls[:-1]:
            if (old["soi_id"], new["soi_id"]) in decided:
                continue
            op, np_ = _f(old.get("unit_price")), _f(new.get("unit_price"))
            if abs(op - np_) < 0.5:
                continue
            out.append(_judge(old, new))
    out.sort(key=lambda p: (p["new"].get("so_date") or "", p["old"].get("pn")))
    return out


def _judge(old, new):
    op, np_ = _f(old.get("unit_price")), _f(new.get("unit_price"))
    diff = (np_ - op) / op * 100 if op else None
    old_left = _f(old.get("pending_qty"))
    new_qty = _f(new.get("qty"))
    qty_match = old_left > 0 and abs(new_qty - old_left) <= max(old_left * 0.05, 1)
    od, nd = str(old.get("due_date") or "")[:10], str(new.get("due_date") or "")[:10]
    due_ok = (not od or not nd or nd <= od) or (od and nd and abs(
        _days(nd) - _days(od)) <= 14)
    if qty_match and due_ok:
        rec, why = "REPLACE", "새 수량이 옛 미납 잔량과 같음"
    elif qty_match:
        rec, why = "REPLACE", "수량은 같으나 납기가 다름 — 확인"
    else:
        rec, why = "KEEP", "수량이 옛 잔량과 다름 ({:,.0f} vs {:,.0f})".format(
            new_qty, old_left)
    return {"old": old, "new": new, "diff_pct": diff,
            "recommend": rec, "why": why}


def _days(iso):
    from datetime import date
    try:
        return date.fromisoformat(iso).toordinal()
    except Exception:
        return 0


def plan_round_move(old_rounds, new_line_has_rounds):
    """옛 라인의 미충당 회차 → 새 라인 회차 초안.

    old_rounds: [{sched_id, due_date, qty, delivered_qty, note}]
    returns: (닫을 회차 [(sched_id, qty_before, delivered)], 만들 회차
              [{due_date, qty, note}])  — 새 라인에 이미 회차가 있으면
              만들지 않는다(닫기만).
    """
    close, create = [], []
    for r in sorted(old_rounds, key=lambda r: str(r.get("due_date") or "")):
        left = _f(r.get("qty")) - _f(r.get("delivered_qty"))
        if left <= 0:
            continue
        close.append((r["sched_id"], _f(r.get("qty")), _f(r.get("delivered_qty"))))
        if not new_line_has_rounds:
            create.append({"due_date": str(r.get("due_date"))[:10],
                           "qty": left, "note": "구 수주 회차 이관"})
    return close, create
