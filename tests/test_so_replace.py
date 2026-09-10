# -*- coding: utf-8 -*-
"""수주 대체 감지 — 단가 다른 쌍·추천 규칙·회차 이관 초안."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.so_replace import detect_pairs, plan_round_move  # noqa: E402


def _l(soi, so, date, price, qty, pend, due=None, pid="P1", cust="미진정밀"):
    return {"soi_id": soi, "so_id": so, "so_number": f"SO-{so}",
            "so_date": date, "customer": cust, "product_id": pid, "pn": "A",
            "qty": qty, "pending_qty": pend, "unit_price": price,
            "due_date": due}


def test_detect_recommends_replace_when_qty_matches():
    lines = [_l(1, 10, "2026-08-01", 1000, 5000, 3000, "2026-09-20"),
             _l(2, 11, "2026-09-09", 1100, 3000, 3000, "2026-09-20")]
    p = detect_pairs(lines)
    assert len(p) == 1
    assert p[0]["old"]["soi_id"] == 1 and p[0]["new"]["soi_id"] == 2
    assert p[0]["recommend"] == "REPLACE" and round(p[0]["diff_pct"]) == 10


def test_detect_recommends_keep_when_qty_differs_and_skips_same_price():
    lines = [_l(1, 10, "2026-08-01", 1000, 5000, 3000),
             _l(2, 11, "2026-09-09", 1300, 800, 800),
             _l(3, 12, "2026-09-05", 1000, 100, 100, pid="P2"),
             _l(4, 13, "2026-09-09", 1000, 100, 100, pid="P2")]
    p = detect_pairs(lines)
    assert len(p) == 1 and p[0]["recommend"] == "KEEP"
    assert "수량이 옛 잔량과 다름" in p[0]["why"]


def test_detect_skips_decided_and_other_customers():
    lines = [_l(1, 10, "2026-08-01", 1000, 5000, 3000),
             _l(2, 11, "2026-09-09", 1100, 3000, 3000),
             _l(5, 14, "2026-09-09", 900, 3000, 3000, cust="(주)엠제이티")]
    assert detect_pairs(lines, decided={(1, 2)}) == []


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
