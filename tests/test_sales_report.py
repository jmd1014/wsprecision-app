# -*- coding: utf-8 -*-
"""영업 보고 집계·리포트 생성기 검증."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.sales_report import (  # noqa: E402
    aggregate, daily_report_html, line_amounts, monthly_report_html)

ROWS = [
    {"ship_no": "SH-20260806-01", "date": "2026-08-06",
     "customer": "미진정밀", "pn": "80AHYBV-TU-05",
     "customer_pn": "S80AHYBV-TU-05;PM", "qty": 208,
     "unit_price": 18300},
    {"ship_no": "SH-20260806-01", "date": "2026-08-06",
     "customer": "미진정밀", "pn": "MRG6-07",
     "customer_pn": "MRG6-07;OUP", "qty": 1890, "unit_price": None},
    {"ship_no": "SH-20260807-01", "date": "2026-08-07",
     "customer": "㈜엠제이티", "pn": "4PDVN-03",
     "customer_pn": "4S4PDVN-03;OUP", "qty": 1400, "unit_price": 1000},
]


def test_line_amounts_rules():
    assert line_amounts({"qty": 208, "unit_price": 18300}) == \
        (3806400.0, 380640.0)
    assert line_amounts({"qty": 100, "unit_price": None}) is None
    assert line_amounts({"qty": 100, "unit_price": 0}) is None
    assert line_amounts({"qty": 100, "unit_price": "bad"}) is None


def test_aggregate_totals_and_missing():
    agg = aggregate(ROWS)
    a = agg["all"]
    assert a["lines"] == 3
    assert a["qty"] == 3498
    assert a["supply"] == 5206400
    assert a["vat"] == 520640
    assert a["total"] == 5727040
    # 단가 미입력 — 금액 제외·수량 포함, 건수 따로
    assert a["missing"] == 1
    assert a["missing_qty"] == 1890
    assert agg["ship_nos"] == {"SH-20260806-01", "SH-20260807-01"}
    assert agg["customers"] == {"미진정밀", "㈜엠제이티"}


def test_aggregate_groupings():
    agg = aggregate(ROWS)
    mj = agg["by_customer"]["미진정밀"]
    assert mj["lines"] == 2 and mj["qty"] == 2098
    assert mj["supply"] == 3806400 and mj["missing"] == 1
    assert agg["by_date"]["2026-08-06"]["qty"] == 2098
    assert agg["by_date"]["2026-08-07"]["total"] == 1540000
    assert agg["by_pn"][("4PDVN-03", "㈜엠제이티")]["supply"] == 1400000


def test_daily_report_contents():
    html = daily_report_html("2026-08-06", ROWS[:2], issued_by="김민수")
    assert "일일 출고 결산" in html and "2026-08-06" in html
    assert "SH-20260806-01" in html
    assert "3,806,400" in html and "380,640" in html
    assert "미진정밀" in html
    assert "단가 미입력 1건" in html
    assert "김민수" in html
    assert "window.print" in html


def test_monthly_report_contents_and_order():
    html = monthly_report_html("2026-08", ROWS, issued_by="김민수")
    assert "월 마감 보고서" in html and "2026년 8월" in html
    # 일자별 두 줄 + 월 합계
    assert "2026-08-06" in html and "2026-08-07" in html
    assert "5,206,400" in html and "5,727,040" in html
    # 품번별 금액순 — 80AHYBV(4,187,040) 가 4PDVN(1,540,000) 보다 먼저
    assert html.find("80AHYBV-TU-05") < html.find("4PDVN-03")
    assert "단가 미입력 1건" in html


def test_reports_without_missing_have_no_warning():
    html = daily_report_html("2026-08-07", [ROWS[2]])
    assert "단가 미입력" not in html
    assert "1,400,000" in html and "140,000" in html
