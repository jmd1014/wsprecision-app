# -*- coding: utf-8 -*-
"""납품 수량의 분납 회차 충당 규칙.

원칙 (2026-08-06 확정 — 4PDVN-03 사례):
  1차. 납품일과 납기가 같은 회차부터 채운다
  2차. 남는 수량은 가장 오래된 미충당 회차부터 채운다 (밀린 회차 만회)

'오래된 회차부터'만 쓰면 건너뛴 회차가 완료로 보이고 당일 회차가
부분 납품으로 잡힌다 — 실제 8/3 회차를 건너뛰고 8/5 에 1,400 을
납품했는데 장부는 8/3 완료 · 8/5 600 으로 기록되던 왜곡.
총 잔량은 같아도 '어느 회차가 밀렸는지'가 뒤바뀌므로 수기 대조가
어긋난다.
"""


def allocate_rounds(rounds, qty, deliver_date):
    """납품 수량을 회차에 배분.

    rounds: [{"sched_id", "due_date", "qty", "delivered_qty"}] — 납기순
    qty: 이번 납품 수량
    deliver_date: 납품일 (date 또는 'YYYY-MM-DD')

    returns: {sched_id: new_delivered_qty} — 값이 바뀐 회차만
    """
    d_iso = str(deliver_date)[:10]
    left = float(qty)
    cur = {r["sched_id"]: float(r.get("delivered_qty") or 0)
           for r in rounds}
    changed = {}

    def _fill(target_rounds):
        nonlocal left
        for r in target_rounds:
            if left <= 0:
                break
            room = float(r.get("qty") or 0) - cur[r["sched_id"]]
            if room <= 0:
                continue
            take = min(room, left)
            cur[r["sched_id"]] += take
            changed[r["sched_id"]] = cur[r["sched_id"]]
            left -= take

    # 1차: 납품일 = 납기 회차
    _fill([r for r in rounds if str(r.get("due_date"))[:10] == d_iso])
    # 2차: 오래된 회차부터 (이미 찬 회차는 room 0 으로 자연 통과)
    _fill(rounds)
    return changed
