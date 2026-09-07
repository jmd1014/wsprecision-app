# -*- coding: utf-8 -*-
"""설비 스케줄 보드 — 작업 큐·셀 상태·부하."""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.schedule import (  # noqa: E402
    week_start, week_days, build_queue, suggest_qty, cell_status,
    build_board, group_load)


def test_week_helpers():
    assert week_start(date(2026, 9, 10)) == date(2026, 9, 7)
    assert week_start("2026-09-07") == date(2026, 9, 7)
    assert [d.isoformat() for d in week_days(date(2026, 9, 7))][-1] == \
        "2026-09-12"


def test_queue_net_and_ops_order():
    lines = [{"product_id": "P1", "pn": "4PDVN-03", "pending_qty": 3000},
             {"product_id": "P2", "pn": "XX", "pending_qty": 100},
             {"product_id": "P3", "pn": "NOSTD", "pending_qty": 50}]
    rounds = [{"product_id": "P1", "due_date": "2026-09-16", "qty": 800,
               "delivered_qty": 0},
              {"product_id": "P1", "due_date": "2026-09-09", "qty": 800,
               "delivered_qty": 800},               # 충당 완료 → 무시
              {"product_id": "P1", "due_date": "2026-09-11", "qty": 800,
               "delivered_qty": 100}]
    stds = [{"product_id": "P1", "pn": "4PDVN-03", "process": "4PDVN-03#20",
             "step": 20, "uph_std": 20, "setup_min": 0, "group_code": "CNC"},
            {"product_id": "P1", "pn": "4PDVN-03", "process": "4PDVN-03#10",
             "step": 10, "uph_std": 18, "setup_min": 30, "group_code": "CNC"}]
    q = build_queue(lines, rounds, stock={"P1": 400, "P2": 500},
                    wip={"P1": 200}, stds=stds,
                    alloc={("4PDVN-03", "4PDVN-03#10"): 640},
                    capable={("4PDVN-03", "4PDVN-03#10"): ["CNC15"]})
    assert [x["process"] for x in q if x["pn"] == "4PDVN-03"] == \
        ["4PDVN-03#10", "4PDVN-03#20"]
    a = q[0]
    assert a["net"] == 2400 and a["due"] == "2026-09-11"
    assert a["hours"] == round(2400 / 18 + 0.5, 1)
    assert a["alloc"] == 640 and a["machines"] == ["CNC15"]
    assert not [x for x in q if x["product_id"] == "P2"]   # 재고로 충당
    ns = [x for x in q if x["product_id"] == "P3"][0]
    assert ns["no_std"] and ns["hours"] is None and ns["pn"] == "NOSTD"


def test_suggest_qty_and_status():
    assert suggest_qty(9, 20) == 180
    assert suggest_qty(9, 20, setup_min=30) == 170
    assert suggest_qty(9, None) == 0
    assert cell_status(180, 0, "2026-09-09", "2026-09-08") == "PLAN"
    assert cell_status(180, 0, "2026-09-07", "2026-09-08") == "SHORT"
    assert cell_status(180, 100, "2026-09-08", "2026-09-08") == "RUN"
    assert cell_status(180, 172, "2026-09-08", "2026-09-08") == "DONE"
    assert cell_status(180, 100, "2026-09-07", "2026-09-08") == "SHORT"


def test_board_cells_and_load():
    machines = [{"machine_id": "CNC09", "group_code": "CNC", "active": True,
                 "night_active": True, "hours_per_shift": 9},
                {"machine_id": "CNC16", "group_code": "CNC", "active": True,
                 "night_active": False, "hours_per_shift": 9},
                {"machine_id": "MCT99", "group_code": "MCT", "active": False}]
    days = week_days(date(2026, 9, 7))
    sched = [{"machine_id": "CNC09", "plan_date": "2026-09-07",
              "shift": "주간", "process": "MRG6-07#10", "plan_qty": 190,
              "plan_hours": 9, "status": "PLAN"},
             {"machine_id": "CNC09", "plan_date": "2026-09-07",
              "shift": "야간", "process": "MRG6-07#10", "plan_qty": 190,
              "plan_hours": 9, "status": "CANCELLED"}]
    logs = [{"machine": "CNC09", "log_date": "2026-09-07", "shift": "주간",
             "process": "MRG6-07#10", "total_qty": 201, "run_flag": "가동"},
            {"machine": "CNC09", "log_date": "2026-09-07", "shift": "주간",
             "process": "OTHER#10", "total_qty": 10, "run_flag": "가동"},
            {"machine": "CNC16", "log_date": "2026-09-07", "shift": "야간",
             "process": None, "total_qty": 0, "run_flag": "비가동",
             "stop_reason": "M09 야간미운영"},
            {"machine": "CNC16", "log_date": "2026-09-08", "shift": "주간",
             "process": "4PDVN-03#20", "total_qty": 150, "run_flag": "가동"},
            {"machine": "CNC16", "log_date": "2026-09-08", "shift": "주간",
             "process": "4PDVN-03#20", "total_qty": 30, "run_flag": "가동"},
            {"machine": "CNC16", "log_date": "2026-09-08", "shift": "주간",
             "process": "X#10", "total_qty": 5, "run_flag": "가동"}]
    cells, load = build_board(machines, days, sched, logs, "2026-09-08")
    c = cells[("CNC09", "2026-09-07", "주간")]
    assert c["status"] == "DONE" and c["actual"] == 201
    assert c["other"] == 10 and c["other_process"] == "OTHER#10"
    assert ("CNC09", "2026-09-07", "야간") not in cells        # 취소 셀
    assert cells[("CNC16", "2026-09-07", "야간")]["status"] == "STOP"
    ca = cells[("CNC16", "2026-09-08", "주간")]
    assert ca["status"] == "ACTUAL" and ca["actual"] == 185
    assert ca["process"] == "4PDVN-03#20 +"
    assert load["CNC09"] == (9, 108) and load["CNC16"] == (0, 54)
    assert "MCT99" not in load
    assert group_load(machines, load) == {"CNC": (9, 162)}
