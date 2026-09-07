# -*- coding: utf-8 -*-
"""공정 표준 산출 — 설비명 정규화·야간 시간·UPH 중앙값."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.op_std import (  # noqa: E402
    normalize_machine, machine_group, process_group, row_hours,
    aggregate, op_hours)


def test_normalize_machine_variants():
    assert normalize_machine("MCT 03") == "MCT03"
    assert normalize_machine("MCT09") == "MCT09"
    assert normalize_machine("cnc-7") == "CNC07"
    assert machine_group("MCT 03") == "MCT"
    assert process_group("CNC#20") == "CNC"


def test_row_hours_overnight_and_scan_rows():
    assert row_hours("09:27", "12:28") == (3 * 60 + 1) / 60
    assert row_hours("22:00", "02:00", "야간") == 4
    assert row_hours("01:00", "05:00", "야간") == 4
    assert row_hours("10:00", "10:00") is None      # 스캔형 등록
    assert row_hours(None, "10:00") is None


def test_aggregate_median_uph_and_machines():
    rows = [
        {"pn": "4PDVN-03", "product_id": "P1", "process": "CNC#10",
         "process_step": 10, "machine": "CNC26", "shift": "주간",
         "total_qty": 60, "work_start": "09:00", "work_end": "12:00",
         "log_date": "2026-07-02"},                         # 20 UPH
        {"pn": "4PDVN-03", "product_id": None, "process": "CNC#10",
         "process_step": 10, "machine": "CNC 27", "shift": "야간",
         "total_qty": 100, "work_start": "22:00", "work_end": "02:00",
         "log_date": "2026-07-03"},                         # 25 UPH
        {"pn": "4PDVN-03", "product_id": None, "process": "CNC#10",
         "process_step": 10, "machine": "CNC26", "shift": "주간",
         "total_qty": 300, "work_start": "13:00", "work_end": "18:00",
         "log_date": "2026-07-03"},                         # 60 UPH (이상)
        {"pn": "4PDVN-03", "process": "MCT#10", "machine": "MCT 03",
         "total_qty": 50, "work_start": "10:00", "work_end": "10:00"},
    ]
    out = aggregate(rows)
    op = out["ops"][("4PDVN-03", "CNC#10")]
    assert op["uph_auto"] == 25 and op["sample_n"] == 3
    assert op["product_id"] == "P1" and op["group"] == "CNC"
    assert op["machines"] == ["CNC26", "CNC27"]
    assert op["first_date"] == "2026-07-02" and op["last_date"] == "2026-07-03"
    assert ("4PDVN-03", "MCT#10") not in out["ops"]   # 구간 없는 행 제외
    m = out["machines"][("4PDVN-03", "CNC#10", "CNC26")]
    assert m["runs"] == 2 and m["uph_actual"] == 40


def test_op_hours():
    assert op_hours(200, 25, setup_min=30) == 8.5
    assert op_hours(10, 0) is None
