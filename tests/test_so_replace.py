# -*- coding: utf-8 -*-
"""수주 대체 감지 — 품번당 묶음·추천 규칙·회차 이관 초안."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.so_replace import detect_groups, plan_round_move  # noqa: E402


def _l(soi, so, date, price, qty, pend, due=None, pid="P1", cust="미진정밀",
       kind=None):
    return {"soi_id": soi, "so_id": so, "so_number": f"SO-{so}",
            "so_date": date, "customer": cust, "product_id": pid, "pn": "A",
            "qty": qty, "pending_qty": pend, "unit_price": price,
            "due_date": due, "price_kind": kind}


def test_group_replace_when_new_covers_sum_of_old_remaining():
    # 옛 수주 3건(미납 3,280 + 5,000 + 1,000) → 새 수주 1건 9,280 (단가 인상)
    lines = [_l(1, 10, "2026-04-16", 13200, 4000, 3280),
             _l(2, 11, "2026-06-19", 13200, 5000, 5000),
             _l(3, 12, "2026-07-07", 13200, 1000, 1000),
             _l(9, 20, "2026-09-08", 14300, 9280, 9280)]
    g = detect_groups(lines)
    assert len(g) == 1
    assert g[0]["new"]["soi_id"] == 9
    assert [o["soi_id"] for o in g[0]["olds"]] == [1, 2, 3]
    assert g[0]["sum_left"] == 9280 and g[0]["recommend"] == "REPLACE"
    assert round(g[0]["diff_pct"], 1) == 8.3


def test_group_replace_with_extra_qty_and_keep_when_smaller():
    lines = [_l(1, 10, "2026-04-16", 33000, 1700, 1232),
             _l(2, 11, "2026-06-19", 33000, 1000, 1000),
             _l(9, 20, "2026-09-08", 36000, 3232, 3232)]      # +1,000 추가
    g = detect_groups(lines)
    assert g[0]["recommend"] == "REPLACE" and "추가 1,000" in g[0]["why"]
    lines2 = [_l(1, 10, "2026-04-16", 1000, 5000, 3000),
              _l(9, 20, "2026-09-08", 1300, 800, 800, pid="P2"),
              _l(2, 11, "2026-05-01", 1000, 2000, 2000, pid="P2")]
    g2 = detect_groups(lines2)
    assert len(g2) == 1 and g2[0]["recommend"] == "KEEP"


def test_group_excludes_special_priced_decided_and_same_price():
    lines = [_l(1, 10, "2025-05-08", 4100, 20000, 11788, kind="CUSTOMER_MAT"),
             _l(2, 11, "2026-06-29", 7500, 30000, 27500),
             _l(3, 12, "2026-07-01", 7500, 500, 500),
             _l(9, 20, "2026-09-08", 7880, 78500, 77500)]
    g = detect_groups(lines)
    assert [o["soi_id"] for o in g[0]["olds"]] == [2, 3]     # 사급 라인 제외
    assert detect_groups(lines, decided={(2, 9), (3, 9)}) == []
    # 단가가 같으면 후보 아님
    assert detect_groups([_l(1, 10, "2026-01-01", 100, 10, 10),
                          _l(2, 11, "2026-02-01", 100, 10, 10)]) == []


def test_plan_round_move():
    rounds = [{"sched_id": 1, "due_date": "2026-09-02", "qty": 500,
               "delivered_qty": 500},
              {"sched_id": 2, "due_date": "2026-09-09", "qty": 500,
               "delivered_qty": 200},
              {"sched_id": 3, "due_date": "2026-09-16", "qty": 500,
               "delivered_qty": 0}]
    close, create = plan_round_move(rounds, new_line_has_rounds=False)
    assert [c[0] for c in close] == [2, 3]
    assert [(c["due_date"], c["qty"]) for c in create] == \
        [("2026-09-09", 300), ("2026-09-16", 500)]
    close2, create2 = plan_round_move(rounds, new_line_has_rounds=True)
    assert len(close2) == 2 and create2 == []
