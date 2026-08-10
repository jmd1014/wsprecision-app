# -*- coding: utf-8 -*-
"""출고 라인 품명 보강 + LOT(W번호) 표기.

출고 리스트는 사내 품번 기준으로 준비하므로 품번 옆에 품명을 붙여
유사 품번 착오를 줄이고, 실물 대조용 LOT 를 함께 보여준다.
- 확정 전표: 원장(ISSUE, ref_table=shipment_items)의 실제 차감 LOT
- 작성중 전표: 완성 LOT 잔량 FIFO(first_output_date, lot_number 순)
  예정 배분 — 확정 시 같은 규칙으로 차감되므로 현장 대조에 쓸 수 있다
"""


def format_lots(pairs):
    """[(lot, qty)] → 'W0012' / 'W0012(400) W0013(100)' / ''."""
    pairs = [((l or "미지정"), float(q)) for l, q in pairs
             if q and float(q) > 0]
    if not pairs:
        return ""
    if len(pairs) == 1:
        return pairs[0][0]
    return " ".join(f"{l}({q:,.0f})" for l, q in pairs)


def issued_lots(txns):
    """ISSUE 원장 행(qty 음수 저장) → {si_id: LOT 표기}."""
    by_si = {}
    for t in txns:
        si = t.get("ref_id")
        if si is None:
            continue
        by_si.setdefault(si, []).append(
            (t.get("lot_number"), -float(t.get("qty") or 0)))
    return {si: format_lots(ps) for si, ps in by_si.items()}


def fifo_preview(items, lots_by_pid):
    """작성중 전표의 예정 LOT — 라인 순서대로 잔량 FIFO 배분.

    items: [{si_id, product_id, qty}]
    lots_by_pid: {product_id: [{lot_number, remain_qty}]} (FIFO 정렬)
    잔량이 모자라면 '(부족 n)' 을 덧붙인다.
    """
    used, out = {}, {}
    for x in items:
        pid = x.get("product_id")
        qty = float(x.get("qty") or 0)
        if x.get("si_id") is None or not pid or qty <= 0:
            continue
        left, pairs = qty, []
        for lot in lots_by_pid.get(pid, []):
            if left <= 0:
                break
            key = (pid, lot.get("lot_number"))
            rem = float(lot.get("remain_qty") or 0) - used.get(key, 0)
            take = min(left, max(rem, 0))
            if take <= 0:
                continue
            used[key] = used.get(key, 0) + take
            pairs.append((lot.get("lot_number"), take))
            left -= take
        s = format_lots(pairs)
        if left > 1e-9:
            s = (s + " " if s else "") + f"(부족 {left:,.0f})"
        out[x["si_id"]] = s
    return out


def names_and_lots(fetch, items, confirmed):
    """전표 라인 목록 → ({si_id: 품명}, {si_id: LOT 표기}).

    품명 = 스냅샷 item_name → products.sub_class 폴백.
    fetch 는 db.fetch 시그니처 (table, select, filter, limit=).
    """
    pids = sorted({x.get("product_id") for x in items
                   if x.get("product_id")})
    subs = {}
    if pids:
        _pstr = ",".join(f'"{p}"' for p in pids)
        try:
            subs = {p["product_id"]: p.get("sub_class")
                    for p in fetch("products", "product_id,sub_class",
                                   f"product_id=in.({_pstr})", limit=500)}
        except Exception:
            subs = {}
    names = {x["si_id"]:
             (x.get("item_name") or subs.get(x.get("product_id")) or "")
             for x in items if x.get("si_id") is not None}

    lots = {}
    try:
        if confirmed:
            _sis = ",".join(str(x["si_id"]) for x in items
                            if x.get("si_id") is not None)
            if _sis:
                lots = issued_lots(fetch(
                    "inventory_transactions", "ref_id,lot_number,qty",
                    "ref_table=eq.shipment_items&txn_type=eq.ISSUE"
                    f"&ref_id=in.({_sis})", limit=1000))
        elif pids:
            _pstr = ",".join(f'"{p}"' for p in pids)
            by_pid = {}
            for l in fetch("product_lot_stock_v",
                           "product_id,lot_number,remain_qty",
                           f"product_id=in.({_pstr})&remain_qty=gt.0"
                           "&order=first_output_date.asc,lot_number.asc",
                           limit=1000):
                by_pid.setdefault(l["product_id"], []).append(l)
            lots = fifo_preview(items, by_pid)
    except Exception:
        lots = {}
    return names, lots
