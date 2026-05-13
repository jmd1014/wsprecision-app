"""수주 파서의 헬퍼 함수 — 날짜/숫자 변환"""
import sys, os
from datetime import date, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.so_parser import _to_num, _to_int, _to_date


def test_to_num_basic():
    assert _to_num("1,234") == 1234.0
    assert _to_num("1234") == 1234.0
    assert _to_num(1234) == 1234.0
    assert _to_num(None) is None
    assert _to_num("") is None
    assert _to_num("abc") is None


def test_to_int_basic():
    assert _to_int("100") == 100
    assert _to_int("1,234") == 1234
    assert _to_int(None) is None


def test_to_date_formats():
    assert _to_date("2026-05-08") == date(2026, 5, 8)
    assert _to_date("2026/05/08") == date(2026, 5, 8)
    assert _to_date("20260508") == date(2026, 5, 8)
    assert _to_date(datetime(2026, 5, 8, 13, 30)) == date(2026, 5, 8)
    assert _to_date(None) is None
    assert _to_date("") is None
    assert _to_date("not a date") is None
