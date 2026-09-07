# -*- coding: utf-8 -*-
"""생산일정 시트 파서 — 품번 약칭 매칭·공정 분해·중복 키·표준 행."""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.prod_sheet import (  # noqa: E402
    pn_key, split_process, build_pn_index, parse_data_rows, parse_std_rows)

PRODS = [
    {"product_id": "P1", "pn": "8HFDV-VM-05", "alias_list": None,
     "archived_at": None},
    {"product_id": "P2", "pn": "4PDVN-03", "alias_list": "4S4PDVN-03",
     "archived_at": None},
    {"product_id": "P9", "pn": "4PDVN-03", "alias_list": None,
     "archived_at": "2026-01-01"},          # 휴면 중복 → 활성 우선
]


def test_pn_key_and_split():
    assert pn_key("8HFDV-VM-05") == pn_key("8HFDV-05")
    assert pn_key("4HDV-VM-04") == "4HDV-04"
    assert split_process("4PDVN-03#20") == ("4PDVN-03", "#20", 20)
    assert split_process("MRG6-07#20#30") == ("MRG6-07", "#20#30", 20)
    assert split_process("11SDF-BL-10") == ("11SDF-BL-10", "", None)


def test_index_prefers_active_and_alias():
    idx = build_pn_index(PRODS)
    assert idx[pn_key("8HFDV-05")] == "P1"
    assert idx[pn_key("4PDVN-03")] == "P2"
    assert idx[pn_key("4S4PDVN-03")] == "P2"


def _row(date, shift, machine, proc, qty, hrs, uph_t, run="가동",
         stop=None, worker="티엔"):
    return (datetime(2026, 6, int(date)), "화", shift, machine, worker,
            proc, 95.0, "1분", qty, hrs, 0, uph_t, None, None, run, stop,
            None)


def test_parse_data_rows_matching_and_keys():
    idx = build_pn_index(PRODS)
    rows = [
        _row(2, "야간", "CNC07", "8HFDV-05#20", 199, 10, 32),
        _row(2, "야간", "CNC08", None, None, None, None, run="비가동",
             stop="M01 자재부족"),
        _row(2, "주간", "CNC13(다인로봇)", "THNV-08", 40, 8, 5),
        _row(2, "야간", "CNC07", "8HFDV-05#20", 199, 10, 32),   # 동일 행
    ]
    recs, st = parse_data_rows(rows, idx)
    assert (st["rows"], st["run"], st["stop"], st["matched"]) == (4, 3, 1, 2)
    assert st["unmatched"] == {"THNV-08": 1}
    r0 = recs[0]
    assert r0["product_id"] == "P1" and r0["pn"] == "8HFDV-05"
    assert r0["process"] == "8HFDV-05#20" and r0["process_step"] == 20
    assert r0["uptime_hours"] == 10 and r0["uph_target"] == 32
    assert r0["uph_actual"] == 19.9 and r0["run_flag"] == "가동"
    assert recs[1]["run_flag"] == "비가동"
    assert recs[1]["stop_reason"] == "M01 자재부족"
    assert recs[2]["machine"] == "CNC13"
    assert "품번 미매칭" in recs[2]["remark"]
    assert recs[3]["sheet_key"] == recs[0]["sheet_key"] + "-2"
    assert len({r["sheet_key"] for r in recs}) == 4


def test_parse_std_rows():
    idx = build_pn_index(PRODS)
    rows = [
        (1.0, "8HFDV-05#10", 66.0, None, 9.9, 46, None, "CNC"),
        (2.0, "XYZ#10", 30.0, None, 4.5, 102, "근거", None),
        (3.0, "BAD#10", None, None, None, None, None, None),
    ]
    out = parse_std_rows(rows, idx)
    s = out[("8HFDV-05", "8HFDV-05#10")]
    assert s["product_id"] == "P1" and s["uph_sheet"] == 46
    assert s["ct_sec"] == 66 and s["group_code"] == "CNC" and s["step"] == 10
    assert out[("XYZ", "XYZ#10")]["product_id"] is None
    assert ("BAD", "BAD#10") not in out
