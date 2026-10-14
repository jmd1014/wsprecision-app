# -*- coding: utf-8 -*-
"""생산 계획 › 주간 계획 순수 함수 (utils/weekly_plan.py, 2026-10-14)."""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils import weekly_plan as wp  # noqa: E402


# ─── 작업 키 ───
def test_parse_steps_forms():
    assert wp.parse_steps("#30#40") == [30, 40]
    assert wp.parse_steps("40,30") == [30, 40]
    assert wp.parse_steps("30 40") == [30, 40]
    assert wp.parse_steps("#10#10") == [10]
    assert wp.parse_steps("") == [] and wp.parse_steps("-") == []
    for bad in ("abc", "10-60", "#30#황삭"):
        with pytest.raises(ValueError):
            wp.parse_steps(bad)


def test_op_label_and_key():
    assert wp.op_label("H11SDF-2C-10", [60, 30, 40, 50]) == "H11SDF-2C-10#30#40#50#60"
    assert wp.op_label("4PDVN-03", []) == "4PDVN-03"
    assert wp.op_key("8HFDV-VM-09", [10], "P0738") == "P0738|10"
    assert wp.op_key("8HFDV-VM-09", [], None) == "8HFDV-09|"
    assert wp.op_key("x", [30, 20]) == wp.op_key("x", [20, 30])


def test_steps_from_process_variants():
    assert wp.steps_from_process("MRG6-07#20#30") == [20, 30]
    assert wp.steps_from_process("CNC#10") == [10]
    assert wp.steps_from_process("8HFDV-VM-09#10(픽시스#10)") == [10]
    assert wp.steps_from_process("40ABV-FL-01#10.#20") == [10, 20]
    assert wp.steps_from_process("4PDVN-03#30(수동)") == [30]
    assert wp.steps_from_process("4PDVN-03") == []
    assert wp.steps_from_process("80AHYBV-TU-05#황삭") == []


def test_op_key_from_process_unparsed():
    idx = {"4PDVN-03": "P0005"}
    assert wp.op_key_from_process("4PDVN-03#30#40", idx) == ("P0005|30#40", False)
    assert wp.op_key_from_process("80AHYBV-TU-05#황삭", idx) == ("80AHYBV-TU-05|", True)
    assert wp.op_key_from_process("4PDVN-03", idx) == ("P0005|", False)
    assert wp.op_key_from_process("8HFDV-VM-09#10(픽시스#10)", {"8HFDV-09": ("P1", True)}) \
        == ("P1|10", False)


# ─── 주·요일 유형·능력 ───
def test_week_bounds_and_day_type():
    assert wp.week_bounds(date(2026, 10, 18)) == (date(2026, 10, 12), date(2026, 10, 18))
    assert wp.week_bounds("2026-10-12") == (date(2026, 10, 12), date(2026, 10, 18))
    assert wp.day_type(date(2026, 10, 12)) == "WEEKDAY"
    assert wp.day_type(date(2026, 10, 17)) == "SATURDAY"
    assert wp.day_type(date(2026, 10, 18)) == "OFF"
    cal = {"2026-10-09": "HOLIDAY", date(2026, 10, 18): "SATURDAY"}
    assert wp.day_type(date(2026, 10, 9), cal) == "HOLIDAY"
    assert wp.day_type(date(2026, 10, 18), cal) == "SATURDAY"   # 일요일 특근


def test_profile_hours_defaults_and_overrides():
    assert wp.profile_hours("WEEKDAY") == (10.0, 10.0)
    assert wp.profile_hours("SATURDAY", {}) == (6.0, 6.0)
    assert wp.profile_hours("OFF", {"OFF": (5, 5)}) == (0.0, 0.0)      # 휴무 강제
    assert wp.profile_hours("WEEKDAY", {"WEEKDAY": {"day_hours": 9, "night_hours": None}}) == (9.0, 0.0)


def test_machine_day_hours_flags():
    m = {"active": True, "night_active": True, "sat_active": True}
    assert wp.machine_day_hours("WEEKDAY", None, m) == 20.0
    assert wp.machine_day_hours("WEEKDAY", None, {**m, "night_active": False}) == 10.0
    assert wp.machine_day_hours("SATURDAY", None, m) == 12.0
    assert wp.machine_day_hours("SATURDAY", None, {**m, "sat_active": False}) == 0.0
    assert wp.machine_day_hours("HOLIDAY", None, {**m, "sat_active": False}) == 0.0
    assert wp.machine_day_hours("OFF", None, m) == 0.0
    assert wp.machine_day_hours("WEEKDAY", None, {**m, "active": False}) == 0.0


def test_machine_shift_hours_split():
    m = {"active": True, "night_active": True, "sat_active": True}
    assert wp.machine_shift_hours("WEEKDAY", None, m) == (10.0, 10.0)
    assert wp.machine_shift_hours("SATURDAY", None, m) == (6.0, 6.0)
    assert wp.machine_shift_hours("SATURDAY", None, {**m, "sat_active": False}) == (0.0, 0.0)
    assert wp.machine_shift_hours("WEEKDAY", None, {**m, "night_active": False}) == (10.0, 0.0)
    assert wp.machine_shift_hours("OFF", None, m) == (0.0, 0.0)


def test_week_capacity_groups_and_holiday():
    machines = [
        {"machine_id": "CNC01", "group_code": "CNC", "active": True, "night_active": True, "sat_active": True},
        {"machine_id": "CNC02", "group_code": "CNC", "active": True, "night_active": False, "sat_active": True},
        {"machine_id": "MCT01", "group_code": "MCT", "active": False},
        {"machine_id": "X01", "group_code": None, "active": True, "night_active": True, "sat_active": True},
    ]
    cap = wp.week_capacity(date(2026, 10, 12), machines)
    assert cap["CNC"] == 112 + 56          # (20×5+12) + (10×5+6)
    assert cap["MCT"] == 0
    assert cap["ETC"] == 112
    cap2 = wp.week_capacity(date(2026, 10, 5), machines, calendar={"2026-10-09": "HOLIDAY"})
    assert cap2["CNC"] == (20 * 4 + 12 + 12) + (10 * 4 + 6 + 6)


# ─── 시간·UPH ───
def test_row_hours_edges():
    assert wp.row_hours(100, 20, 30) == 5.5
    assert wp.row_hours(100, 0, 30) is None
    assert wp.row_hours(100, None, 0) is None
    assert wp.row_hours(0, 20, 30) == 0.0
    assert wp.row_hours(100, 20, None) == 5.0
    with pytest.raises(ValueError):
        wp.row_hours(-1, 20, 0)


def test_est_uph():
    assert wp.est_uph([20, 30]) == 12.0
    assert wp.est_uph([20, 0]) is None
    assert wp.est_uph([20, None]) is None
    assert wp.est_uph([]) is None
    assert wp.est_uph([25]) == 25.0


def test_std_uph_priority():
    assert wp.std_uph({"uph_std": 20, "std_status": "CONFIRMED", "uph_sheet": 15, "uph_auto": 10}) == (20.0, "CONFIRMED")
    assert wp.std_uph({"uph_std": 20, "std_status": "AUTO", "uph_sheet": 15, "uph_auto": 10}) == (15.0, "SHEET")
    assert wp.std_uph({"uph_std": None, "std_status": "AUTO", "uph_sheet": None, "uph_auto": 10}) == (10.0, "AUTO")
    assert wp.std_uph({"uph_std": None, "uph_sheet": None, "uph_auto": None}) == (None, None)


def test_std_group_corrects_polluted_group():
    groups = ["CNC", "MCT"]
    assert wp.std_group({"group_code": "MCT"}, groups) == ("MCT", False)
    assert wp.std_group({"group_code": "MRG", "machines_used": "CNC09,CNC10"}, groups) == ("CNC", True)
    assert wp.std_group({"group_code": "HA", "machines_used": ["MCT05"]}, groups) == ("MCT", True)
    assert wp.std_group({"group_code": "T", "machines_used": None}, groups) == ("ETC", True)


# ─── 전개·합치기·나누기 ───
STDS = [
    {"process": "4PDVN-03#10", "step": 10, "group_code": "CNC", "uph_std": 20,
     "std_status": "CONFIRMED", "setup_min": 10, "active": True},
    {"process": "4PDVN-03#30#40", "step": 30, "group_code": "MCT", "uph_sheet": 15,
     "std_status": "AUTO", "setup_min": 20, "active": True},
    {"process": "4PDVN-03#50", "step": 50, "group_code": "MCT", "uph_auto": 9,
     "std_status": "AUTO", "active": False},
]


def test_expand_ops_from_standards():
    rows = wp.expand_ops("4PDVN-03", "P0005", STDS, ["CNC", "MCT"])
    assert [r["steps"] for r in rows] == [[10], [30, 40]]
    assert [r["op_label"] for r in rows] == ["4PDVN-03#10", "4PDVN-03#30#40"]
    assert [r["uph_source"] for r in rows] == ["CONFIRMED", "SHEET"]
    assert [r["group_code"] for r in rows] == ["CNC", "MCT"]
    assert rows[0]["op_key"] == "P0005|10" and rows[0]["hours"] == 0.0   # qty 0
    none = wp.expand_ops("NEW-PN", None, [], ["CNC", "MCT"])
    assert len(none) == 1 and none[0]["steps"] == [] and none[0]["uph"] is None \
        and none[0]["group_code"] == "ETC" and none[0]["group_check"]


def test_expand_prefers_single_steps_over_merged_and_skips_stepless():
    """MRG6-07: #10, #20, #20#30, #30 표준이 함께 있으면 #10·#20·#30 만 전개(겹침 방지),
    합친 '#20#30' 은 합칠 때 참고값. 11SDF-BL-10: 스텝 없는 행은 스텝 행이 있으면 건너뜀."""
    stds = [
        {"process": "MRG6-07#10", "step": 10, "group_code": "MRG", "uph_auto": 21, "machines_used": "CNC09", "active": True},
        {"process": "MRG6-07#20", "step": 20, "group_code": "CNC", "uph_auto": 47, "active": True},
        {"process": "MRG6-07#20#30", "step": 20, "group_code": "MRG", "uph_auto": 36, "machines_used": "CNC19", "active": True},
        {"process": "MRG6-07#30", "step": 30, "group_code": "CNC", "uph_auto": 139, "active": True},
        {"process": "MRG6-07", "step": None, "group_code": "MRG", "uph_auto": 5, "active": True},
    ]
    rows = wp.expand_ops("MRG6-07", "P0006", stds, ["CNC", "MCT"])
    assert [r["steps"] for r in rows] == [[10], [20], [30]]
    assert rows[0]["group_code"] == "CNC" and rows[0]["group_check"]
    # 합칠 때는 합친 공정명 표준(36)을 그대로 참고
    merged = wp.build_payload(
        [{**rows[1], "plan_item_id": 2, "qty": 100}, {**rows[2], "plan_item_id": 3, "qty": 100}],
        [{"delete": False, "steps": "#20#30", "group": "CNC", "qty": 100, "uph": 47, "setup": 0, "due": None, "note": "", "split": False},
         {"delete": True, "steps": "#30", "group": "CNC", "qty": 100, "uph": 139, "setup": 0, "due": None, "note": "", "split": False}],
        lambda pn, pid: stds, ["CNC", "MCT"])
    out, dele, errors, _ = merged
    assert not errors and dele == [3] and out[0]["uph"] == 36.0 and out[0]["uph_source"] == "AUTO"
    # 합친 표준만 있는 스텝 묶음은 그대로 전개
    only_merged = [{"process": "X#30#40", "step": 30, "group_code": "MCT", "uph_sheet": 15, "active": True}]
    assert [r["steps"] for r in wp.expand_ops("X", None, only_merged, ["CNC", "MCT"])] == [[30, 40]]


def test_merge_and_split():
    rows = wp.expand_ops("4PDVN-03", "P0005", STDS, ["CNC", "MCT"])
    for r in rows:
        r["qty"] = 100
    merged = wp.merge_rows(rows)
    assert merged["steps"] == [10, 30, 40] and merged["op_label"] == "4PDVN-03#10#30#40"
    assert merged["uph"] == 8.57 and merged["uph_source"] == "EST"
    assert merged["setup_min"] == 30 and merged["qty"] == 100
    back = wp.split_row(merged, STDS, ["CNC", "MCT"])
    assert [r["steps"] for r in back] == [[10], [30], [40]]
    assert all(r["qty"] == 100 for r in back), "나누기는 전량 통과 — 수량을 나누지 않는다"
    assert back[0]["uph"] == 20.0 and back[1]["uph"] == 15.0 and back[2]["uph"] == 15.0
    # 표준에 없는 스텝은 UPH 없음
    only = wp.split_row({"pn": "4PDVN-03", "product_id": "P0005", "steps": [70], "qty": 5,
                         "group_code": "MCT"}, STDS, ["CNC", "MCT"])
    assert only[0]["uph"] is None and only[0]["hours"] is None
    assert wp.merge_rows([{"pn": "A", "steps": [10], "uph": 20, "qty": 1},
                          {"pn": "A", "steps": [20], "uph": 0, "qty": 1}])["uph"] is None


# ─── 검증·요약·변경 감지 ───
def test_validate_week_overlap_duplicate_and_qty():
    rows = [
        {"pn": "A", "steps": [30, 40], "qty": 10, "group_code": "CNC"},
        {"pn": "A", "steps": [40], "qty": 10, "group_code": "CNC"},
        {"pn": "B", "steps": [10], "qty": float("nan"), "group_code": "CNC"},
        {"pn": "C", "steps": [10], "qty": 5, "group_code": "MCT"},
        {"pn": "C", "steps": [10], "qty": 5, "group_code": "MCT"},
        {"pn": "", "steps": [], "qty": 1},
    ]
    errors, warnings = wp.validate_week(rows)
    assert any(i == 2 and "겹칩니다" in m for i, m in errors)
    assert any(i == 3 and "수량" in m for i, m in errors)
    assert any(i == 6 for i, m in errors)
    assert any(i == 5 and "같은 작업" in m for i, m in warnings)
    assert wp.validate_week([{"pn": "A", "steps": [10], "qty": 1, "group_code": "CNC"},
                             {"pn": "A", "steps": [20], "qty": 2, "group_code": "MCT"}]) == ([], [])


def _stds_for_factory(table):
    return lambda pn, pid: table.get(pn, [])


def test_build_payload_rules():
    rows = [
        {"plan_item_id": 1, "pn": "4PDVN-03", "product_id": "P0005", "steps": [10],
         "uph": 20, "uph_source": "CONFIRMED", "group_code": "CNC", "qty": 100, "setup_min": 10},
        {"plan_item_id": 2, "pn": "4PDVN-03", "product_id": "P0005", "steps": [30, 40],
         "uph": 15, "uph_source": "SHEET", "group_code": "MCT", "qty": 100, "setup_min": 20},
        {"plan_item_id": 3, "pn": "ZZ", "product_id": None, "steps": [], "uph": None,
         "uph_source": None, "group_code": "ETC", "qty": 5, "setup_min": 0},
    ]
    stds = {"4PDVN-03": STDS}
    base = [{"delete": False, "steps": "#10", "group": "CNC", "qty": 100, "uph": 20, "setup": 10,
             "due": None, "note": "", "split": False},
            {"delete": False, "steps": "#30#40", "group": "MCT", "qty": 100, "uph": 15, "setup": 20,
             "due": None, "note": "", "split": False},
            {"delete": False, "steps": "", "group": "ETC", "qty": 5, "uph": None, "setup": float("nan"),
             "due": "NaT", "note": None, "split": False}]
    out, dele, errors, warnings = wp.build_payload(rows, base, _stds_for_factory(stds), ["CNC", "MCT"])
    assert not errors and dele == []
    assert [r["seq"] for r in out] == [0, 1, 2]
    assert out[0]["uph_source"] == "CONFIRMED" and out[2]["setup_min"] == 0.0 and out[2]["due_date"] is None
    # UPH 조금 다름 → 출처 유지, 많이 다름 → MANUAL, 비움 → None/None
    e = [dict(b) for b in base]
    e[0]["uph"] = 20.02; e[1]["uph"] = 25; e[2]["uph"] = None
    out, _, errors, _ = wp.build_payload(rows, e, _stds_for_factory(stds), ["CNC", "MCT"])
    assert out[0]["uph_source"] == "CONFIRMED" and out[1]["uph_source"] == "MANUAL" and out[2]["uph"] is None
    # 합치기: 1행 스텝을 #10#30#40 으로 → 표준으로 다시 추정(EST), 흡수 행 미삭제 → 겹침 오류(표 행 번호 2)
    e = [dict(b) for b in base]
    e[0]["steps"] = "#10#30#40"
    out, _, errors, _ = wp.build_payload(rows, e, _stds_for_factory(stds), ["CNC", "MCT"])
    assert out[0]["uph"] == 8.57 and out[0]["uph_source"] == "EST"
    assert any(i == 2 and "겹칩니다" in m for i, m in errors)
    e[1]["delete"] = True
    out, dele, errors, _ = wp.build_payload(rows, e, _stds_for_factory(stds), ["CNC", "MCT"])
    assert not errors and dele == [2] and [r["op_label"] for r in out] == ["4PDVN-03#10#30#40", "ZZ"]
    # 스텝 변경인데 표준 없음 → UPH 비움 + 경고
    e = [dict(b) for b in base]
    e[2]["steps"] = "#10#20"
    out, _, errors, warnings = wp.build_payload(rows, e, _stds_for_factory(stds), ["CNC", "MCT"])
    assert not errors and out[2]["uph"] is None and any(i == 3 for i, _ in warnings)
    # 나누기: 수량 없으면 오류, 있으면 스텝별 전량 + 원본 삭제 + seq 재번호
    e = [dict(b) for b in base]
    e[1]["split"] = True; e[1]["qty"] = None
    _, _, errors, _ = wp.build_payload(rows, e, _stds_for_factory(stds), ["CNC", "MCT"])
    assert any(i == 2 and "나누기 전에 수량" in m for i, m in errors)
    e[1]["qty"] = 100
    out, dele, errors, _ = wp.build_payload(rows, e, _stds_for_factory(stds), ["CNC", "MCT"])
    assert not errors and dele == [2]
    assert [r["op_label"] for r in out] == ["4PDVN-03#10", "4PDVN-03#30", "4PDVN-03#40", "ZZ"]
    assert [r["seq"] for r in out] == [0, 1, 2, 3] and all(r["qty"] == 100 for r in out[1:3])
    # 삭제 + 나누기 동시 → 삭제 우선
    e = [dict(b) for b in base]
    e[1]["split"] = True; e[1]["delete"] = True
    out, dele, errors, _ = wp.build_payload(rows, e, _stds_for_factory(stds), ["CNC", "MCT"])
    assert dele == [2] and len(out) == 2
    # 스텝 하나 나누기 → 경고만
    e = [dict(b) for b in base]
    e[0]["split"] = True
    out, _, errors, warnings = wp.build_payload(rows, e, _stds_for_factory(stds), ["CNC", "MCT"])
    assert not errors and any("나눌 수 없습니다" in m for _, m in warnings) and len(out) == 3


def test_summarize_and_fingerprint():
    rows = [{"group_code": "CNC", "hours": 5.5}, {"group_code": "CNC", "hours": None},
            {"group_code": "CNC", "qty": 40, "uph": 20, "setup_min": 0},
            {"group_code": "MCT", "hours": 3.0}]
    s = wp.summarize(rows, {"CNC": 168, "MCT": 0})
    assert s["CNC"]["need"] == 7.5 and s["CNC"]["ratio"] == 0.045 and s["CNC"]["unknown"] == 1
    assert s["MCT"]["need"] == 3.0 and s["MCT"]["ratio"] is None
    a = [{"plan_item_id": 1, "updated_at": "2026-10-14T01:00:00+00:00"},
         {"plan_item_id": 2, "updated_at": "2026-10-14T02:00:00.5+00:00"}]
    assert wp.fingerprint(a) == wp.fingerprint(list(reversed(a)))
    assert wp.fingerprint(a) == "2:3:1791943200"          # floor(epoch(02:00:00.5Z))
    assert wp.fingerprint(a) != wp.fingerprint([{**a[0]}, {**a[1], "updated_at": "2026-10-14T03:00:00+00:00"}])
    assert wp.fingerprint(a) != wp.fingerprint(a[:1])
    assert wp.fingerprint([]) == "0:0:"
    # 서버(timestamptz::text, 공백·+00)와 PostgREST(T·+00:00) 형식이 같은 초로 읽힌다
    assert wp.updated_epoch("2026-10-14 03:58:04.765808+00") == wp.updated_epoch("2026-10-14T03:58:04.765808+00:00") == 1791950284
    assert wp.updated_epoch("2026-10-14T03:58:04Z") == 1791950284


def test_validate_week_group_format():
    errors, _ = wp.validate_week([{"pn": "A", "steps": [10], "qty": 1, "group_code": "MCT-5"},
                                  {"pn": "B", "steps": [10], "qty": 1, "group_code": "cnc"}])
    assert any("장비군 형식" in m for _, m in errors) and len(errors) == 1   # 소문자는 upper 로 통과
