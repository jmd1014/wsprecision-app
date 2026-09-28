"""
작업지시 NO — 사내 생산 없음 제품의 자동채번 YYYYMMDD-F01 (2026-09-28).
MES 번호(YYYYMMDD-NNN)와 자동채번 번호 모두 형식 검사를 통과해야 하고,
같은 날 F 번호는 최대값 +1 로 이어진다.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def _load():
    src = open(os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "streamlit_app.py"), encoding="utf-8").read()
    i = src.index("WO_NUMBER_RE = ")
    j = src.index("def kst_date")
    ns = {}
    exec(src[i:j], ns)
    return ns


def test_format_accepts_mes_and_auto_numbers():
    ns = _load()
    rx = ns["WO_NUMBER_RE"]
    assert re.fullmatch(rx, "20260723-001")
    assert re.fullmatch(rx, "20260928-F01")
    assert not re.fullmatch(rx, "20260928-901x")
    assert not re.fullmatch(rx, "20260928-S01")     # 정한 글자(F)만
    assert not re.fullmatch(rx, "2026-09-28-F01")


def test_next_auto_number_increments_per_day():
    ns = _load()
    nxt = ns["next_auto_wo_number"]
    assert nxt("2026-09-28", []) == "20260928-F01"
    assert nxt("2026-09-28", ["20260928-F01", "20260928-F02", "20260928-003"]) == "20260928-F03"
    assert nxt("2026-09-29", ["20260928-F09"]) == "20260929-F01"   # 날짜별 초기화
