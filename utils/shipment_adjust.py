# -*- coding: utf-8 -*-
"""확정 출고 전표의 정정·취소 — 차이(delta)만 되돌리는 순수 계산.

설계 (2026-09-04 사용자 확정):
  * 확정은 실물 출고 시점에 그대로 두고, 확정 전표는 **같은 전표번호를
    유지한 채** 라인 수량을 정정한다. 정정분(차이)만 수주 납품·회차 충당·
    완성 LOT 원장에 반영하고, 정정 이력(shipment_revisions)에 이전/이후
    수량·사유를 남긴다. 재발행 문서에는 '정정본 v{n}' 표기.
  * 원장은 append-only — 되돌림은 ISSUE 행을 **양수 수량**으로 추가한다
    (product_lot_stock_v 는 ISSUE 를 -qty 로 합산하므로 net 이 정확히 준다).
  * 회차 충당은 shipment_allocations(si_id, sched_id, qty) 에 저장된 내역을
    역순으로 줄인다. 저장 내역이 없는 옛 전표는 라인의 지정 회차 →
    납품완료가 있는 최근 회차 순으로 줄인다 (delivered_qty 한도).

이 모듈은 DB 를 모른다 — 입력은 조회된 행, 출력은 적용할 변경 목록.
"""


def net_issued_by_lot(txns):
    """한 라인의 ISSUE 원장 행들 → [(lot, net_issued_qty)] (원장 순서).

    txns: [{txn_id, lot_number, qty}] — qty 는 차감이 음수, 복원이 양수.
    net 이 0 이하인 LOT 은 제외. 순서는 최초 차감 순(txn_id 오름차순).
    """
    order, net = [], {}
    for t in sorted(txns, key=lambda r: int(r.get("txn_id") or 0)):
        lot = t.get("lot_number")
        if lot not in net:
            net[lot] = 0.0
            order.append(lot)
        net[lot] += -float(t.get("qty") or 0)
    return [(lot, net[lot]) for lot in order if net[lot] > 1e-9]


def plan_lot_restore(txns, qty):
    """수량 감소분을 LOT 별로 복원 — 마지막에 차감된 LOT 부터 (LIFO).

    returns: ([(lot, restore_qty)], 복원 못한 잔여)
    잔여가 남으면 원장에 차감 기록이 없던 수량(LOT 미지정 행은 lot None
    으로 net 에 포함되므로 보통 0).
    """
    left, out = float(qty), []
    for lot, n in reversed(net_issued_by_lot(txns)):
        if left <= 1e-9:
            break
        take = min(n, left)
        out.append((lot, take))
        left -= take
    return out, max(left, 0.0)


def plan_round_release(allocs, rounds, qty, line_sched_id=None):
    """수량 감소분만큼 회차 납품완료를 되돌린다.

    allocs: 이 라인의 shipment_allocations [{alloc_id, sched_id, qty}]
    rounds: 라인 수주의 회차 [{sched_id, due_date, delivered_qty}]
    qty: 되돌릴 수량
    line_sched_id: 저장 내역이 없을 때 우선 되돌릴 지정 회차

    returns: ({sched_id: new_delivered_qty}, [(alloc_id, new_alloc_qty)],
              되돌리지 못한 잔여)
    저장 내역이 있으면 그 내역을 최근 납기 회차부터 줄인다 (delivered
    한도). 없으면 지정 회차 → 납품완료가 있는 회차를 납기 최근순으로.
    """
    left = float(qty)
    by_sched = {r["sched_id"]: r for r in rounds}
    cur = {r["sched_id"]: float(r.get("delivered_qty") or 0)
           for r in rounds}
    new_del, alloc_upd = {}, []

    def _due(sid):
        r = by_sched.get(sid) or {}
        return str(r.get("due_date") or "")

    if allocs:
        for a in sorted(allocs, key=lambda a: _due(a["sched_id"]),
                        reverse=True):
            if left <= 1e-9:
                break
            sid = a["sched_id"]
            room = min(float(a.get("qty") or 0), cur.get(sid, 0.0))
            take = min(room, left)
            if take <= 1e-9:
                continue
            cur[sid] -= take
            new_del[sid] = cur[sid]
            alloc_upd.append((a.get("alloc_id"),
                              float(a.get("qty") or 0) - take))
            left -= take
        return new_del, alloc_upd, max(left, 0.0)

    cands = []
    if line_sched_id in cur:
        cands.append(line_sched_id)
    cands += [sid for sid in sorted(cur, key=_due, reverse=True)
              if sid != line_sched_id]
    for sid in cands:
        if left <= 1e-9:
            break
        take = min(cur[sid], left)
        if take <= 1e-9:
            continue
        cur[sid] -= take
        new_del[sid] = cur[sid]
        left -= take
    return new_del, alloc_upd, max(left, 0.0)


def plan_line_deltas(items, new_qtys):
    """전표 라인 vs 정정 수량 → [(item, old, new, delta)] (변경분만)."""
    out = []
    for x in items:
        old = float(x.get("qty") or 0)
        new = float(new_qtys.get(x["si_id"], old) or 0)
        if abs(new - old) > 1e-9:
            out.append((x, old, new, new - old))
    return out


def split_round_alloc(lines, deltas, prefer=None):
    """수주 라인 단위로 계산된 회차 충당 증가분을 전표 라인별로 나눈다.

    확정은 같은 수주 라인(soi)의 전표 라인들을 합산해 회차에 충당하므로,
    저장은 전표 라인(si) 별로 다시 나눠야 한다.
    lines: [(si_id, qty, sched_id)] — 전표 라인 순서
    deltas: {sched_id: 충당 증가분}
    returns: [(si_id, sched_id, qty)]
    """
    rem = {k: float(v) for k, v in deltas.items() if float(v) > 1e-9}
    out = []
    for si_id, qty, sched_id in lines:
        left = float(qty)
        order = ([sched_id] if sched_id in rem else []) + \
            [s for s in (prefer or []) if s in rem and s != sched_id] + \
            [s for s in rem if s != sched_id and s not in (prefer or [])]
        for sid in order:
            if left <= 1e-9:
                break
            take = min(rem.get(sid, 0.0), left)
            if take <= 1e-9:
                continue
            out.append((si_id, sid, take))
            rem[sid] -= take
            if rem[sid] <= 1e-9:
                rem.pop(sid, None)
            left -= take
    return out


def line_status(qty, received):
    q, r = float(qty or 0), float(received or 0)
    return "DELIVERED" if r >= q - 1e-9 else "PARTIAL" if r > 0 else "PENDING"


def rev_label(rev_no, revised_at=None):
    """재발행 문서 표기 — 정정 없으면 None."""
    if not rev_no:
        return None
    d = str(revised_at or "")[:10]
    return f"정정본 v{int(rev_no) + 1}" + (f" · {d}" if d else "")
