# -*- coding: utf-8 -*-
"""수주 대체(단가 변경 재발주) 감지 — 순수 로직 (2026-09-10 사용자 확정).

같은 거래처·같은 품번의 미납 라인이 둘 이상이고 단가가 다르면 '단가 변동'
후보다. 옛 수주가 여러 건으로 나뉘어 있고 고객이 단가 변경으로 한 번에
재발주하는 실제 케이스(2026-09-10, 20/40/80/150AHYBV) 때문에 **품번당 카드
하나**로 묶는다: 새 라인(수주일이 가장 늦은 것) 하나 + 옛 라인 여러 개.
도구는 판단하지 않고 근거와 추천만 보여 준다:
  * 대체 추천: 새 수량 ≥ 옛 미납 합계의 95% (남은 물량을 다시 낸 것,
    추가 물량 포함 가능)
  * 별건 추천: 새 수량이 옛 미납 합계보다 뚜렷이 작음 (일부 물량만 별도 단가)
특수 단가로 표시된 옛 라인(price_kind: 사급 소재·프로젝트)은 후보에서 뺀다.
결정(REPLACE/KEEP)은 so_line_replacements 에 남고 다시 묻지 않는다.
"""


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def detect_groups(lines, decided=()):
    """미납 라인 → 품번별 (새 라인, 옛 라인들) 묶음.

    lines: [{soi_id, so_id, so_number, so_date, customer, product_id, pn,
             qty, pending_qty, unit_price, due_date, price_kind}] (미납 > 0)
    decided: {(old_soi, new_soi)} 이미 결정된 쌍
    returns: [{new, olds, sum_left, diff_pct, recommend, why}]
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
        np_ = _f(new.get("unit_price"))
        olds = [o for o in ls[:-1]
                if abs(_f(o.get("unit_price")) - np_) >= 0.5
                and not o.get("price_kind")
                and (o["soi_id"], new["soi_id"]) not in decided]
        if not olds:
            continue
        out.append(_judge(olds, new))
    out.sort(key=lambda g: (g["new"].get("so_date") or "", g["new"].get("pn") or ""))
    return out


def _judge(olds, new):
    np_ = _f(new.get("unit_price"))
    op = _f(olds[0].get("unit_price"))
    diff = (np_ - op) / op * 100 if op else None
    sum_left = sum(_f(o.get("pending_qty")) for o in olds)
    new_qty = _f(new.get("qty"))
    if sum_left > 0 and abs(new_qty - sum_left) <= max(sum_left * 0.05, 1):
        rec, why = "REPLACE", "새 수량이 옛 미납 합계와 같음"
    elif sum_left > 0 and new_qty >= sum_left * 0.95:
        rec, why = "REPLACE", "새 수량이 옛 미납 합계를 포함함 (추가 {:,.0f})".format(
            new_qty - sum_left)
    else:
        rec, why = "KEEP", "새 수량이 옛 미납 합계보다 작음 ({:,.0f} vs {:,.0f})".format(
            new_qty, sum_left)
    return {"new": new, "olds": olds, "sum_left": sum_left,
            "diff_pct": diff, "recommend": rec, "why": why}


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
