# -*- coding: utf-8 -*-
"""거래명세서·출고 리스트 생성기 검증."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.statement_generator import (  # noqa: E402
    biz_no_fmt, delivery_list_html, transaction_statements_html)

BATCH = {"date": "2026-08-06", "rows": [
    {"pn": "80AHYBV-TU-05", "customer_pn": "S80AHYBV-TU-05;PM",
     "item_name": "FLANGE", "customer": "미진정밀",
     "so_number": "202606290006", "qty": 208, "unit": "EA",
     "unit_price": 18300, "date": "2026-08-06"},
    {"pn": "MRG6-07", "customer_pn": "MRG6-07;OUP", "item_name": None,
     "customer": "미진정밀", "so_number": "202606190014", "qty": 1890,
     "unit": "EA", "unit_price": None, "date": "2026-08-06"},
    {"pn": "4PDVN-03", "customer_pn": "4S4PDVN-03;OUP", "item_name": None,
     "customer": "㈜엠제이티", "so_number": "202604220014-MJT",
     "qty": 1400, "unit": "EA", "unit_price": 1000, "date": "2026-08-06"},
]}
VMAP = {"미진정밀": {"business_no": "6060394821", "ceo_name": "이미옥",
                  "business_type": "제조", "business_item": "기계부품",
                  "phone": None, "address": None}}


def test_biz_no_format():
    assert biz_no_fmt("6060394821") == "606-03-94821"
    assert biz_no_fmt("606-02-14529") == "606-02-14529"
    assert biz_no_fmt(None) == ""


def test_statement_has_two_copies_per_customer():
    html = transaction_statements_html(BATCH, VMAP)
    # 거래처 2곳 × (공급자용 + 공급받는자용) = 4장
    assert html.count('class="page"') == 4
    assert html.count("공급자용") == 2
    assert html.count("공급받는자용") == 2


def test_statement_amounts_and_customer_notation():
    html = transaction_statements_html(BATCH, VMAP)
    # 스캔 양식 검증값: 208 × 18,300 = 3,806,400 / 세액 380,640
    assert "3,806,400" in html
    assert "380,640" in html
    # 거래처 ERP 표기 우선
    assert "S80AHYBV-TU-05;PM / FLANGE" in html
    # 공급받는자 정보
    assert "606-03-94821" in html and "이미옥" in html
    # 단가 미입력 품목 안내
    assert "단가 미입력" in html
    # 공급자 고정 정보
    assert "606-02-14529" in html and "김태식" in html


def test_delivery_list_totals():
    html = delivery_list_html(BATCH)
    assert "출고 리스트" in html
    assert "3건" in html and "3,498" in html      # 208+1890+1400
    assert "202606290006" in html
    assert "확인" in html                          # 검수 확인란
    assert "(확정)" in html
    assert "정정 수량" not in html


def test_delivery_list_draft_has_correction_column():
    """현장 확인용 — 처리 전 안내와 정정 기입란이 있어야 한다."""
    html = delivery_list_html(BATCH, draft=True)
    assert "(현장 확인용)" in html
    assert "정정 수량" in html
    assert "출고 처리 전" in html
