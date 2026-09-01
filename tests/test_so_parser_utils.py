"""수주 파서의 헬퍼 함수 — 날짜/숫자 변환"""
import sys, os
from datetime import date, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.so_parser import _to_num, _to_int, _to_date, _pick_line_nums


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


def test_pick_line_nums_normal_line_not_merged():
    """정상 라인은 병합 금지 — MJT-PO26-우성-708 사고 (100 이
    6,000·600,000 과 이어붙어 1조가 되던 버그) 회귀 방지"""
    assert _pick_line_nums(["100", "6,000", "600,000"]) == \
        [100, 6000, 600000]


def test_pick_line_nums_split_amount_merged():
    """PDF 가 쪼갠 금액("7 8,000,000")은 검산으로 복원"""
    assert _pick_line_nums(["13,000", "6,000", "7", "8,000,000"]) == \
        [13000, 6000, 78000000]


def test_pick_line_nums_two_tokens_kept():
    assert _pick_line_nums(["50", "1,200"]) == [50, 1200]


def test_pick_line_nums_double_split_merged():
    """수량·금액이 한 행에서 동시에 쪼개진 경우 — MJT-PO26-우성-725
    ("3 ,600 6,000 2 1,600,000" = 3,600 × 6,000 = 21,600,000).
    단일 병합만 시도하던 버그는 3 / 600 / 6,000 으로 읽었다"""
    assert _pick_line_nums(["3", ",600", "6,000", "2", "1,600,000"]) == \
        [3600, 6000, 21600000]


def test_to_date_formats():
    assert _to_date("2026-05-08") == date(2026, 5, 8)
    assert _to_date("2026/05/08") == date(2026, 5, 8)
    assert _to_date("20260508") == date(2026, 5, 8)
    assert _to_date(datetime(2026, 5, 8, 13, 30)) == date(2026, 5, 8)
    assert _to_date(None) is None
    assert _to_date("") is None
    assert _to_date("not a date") is None
