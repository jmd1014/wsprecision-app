"""
발주서 문서 — 소모성·공구 발주(item_layout=unit)는 재질 대신 단위 열을 수량 앞에
(2026-09-22 사용자 요청). 소재 발주는 품명·재질·규격 그대로.
"""
import io
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

PO = {"po_number": "26-0999", "po_date": "2026-09-22", "vendor_name": "두리T.M.S",
      "delivery_date": "14일 이내", "payment_terms": "말일 마감 60일 현금",
      "delivery_address": "부산광역시 기장군 산단4로 71", "contact_person": "테스트"}
ITEMS = [{"item_name": "INSERT TIP VBMT 160404HQ PR1125", "material": "", "spec": "",
          "unit": "BOX", "qty": 2, "unit_price": 87200, "memo": ""},
         {"item_name": "절삭유", "material": "", "spec": "20L", "unit": "통",
          "qty": 3, "unit_price": 45000, "memo": "긴급"}]


def _xlsx_rows(data):
    import openpyxl
    ws = openpyxl.load_workbook(io.BytesIO(data)).active
    return [[c.value for c in r] for r in ws.iter_rows()]


def test_xlsx_unit_layout_has_unit_before_qty():
    from utils.po_generator import fill_po_template
    rows = _xlsx_rows(fill_po_template(dict(PO, item_layout="unit"), ITEMS, {}))
    hdr = next(r for r in rows if r[0] == "NO")
    assert hdr[1:5] == ["품  명", "규 격", "단 위", "수 량"], hdr
    line = next(r for r in rows if r[1] and "VBMT" in str(r[1]))
    assert (line[2] or "") == "" and line[3] == "BOX" and line[4] == 2
    line2 = next(r for r in rows if r[1] and str(r[1]).startswith("절삭유"))
    assert line2[2] == "20L" and line2[3] == "통"


def test_xlsx_material_layout_unchanged():
    from utils.po_generator import fill_po_template
    items = [dict(ITEMS[0], material="SUS304", spec="Ø45*20")]
    rows = _xlsx_rows(fill_po_template(dict(PO), items, {}))
    hdr = next(r for r in rows if r[0] == "NO")
    assert hdr[1:5] == ["품  명", "재 질", "규 격", "수 량"], hdr
    line = next(r for r in rows if r[1] and "VBMT" in str(r[1]))
    assert line[2] == "SUS304" and line[3] == "Ø45*20"


@pytest.mark.skipif(__import__("importlib").util.find_spec("fpdf") is None,
                    reason="fpdf2 미설치")
def test_pdf_builds_in_both_layouts():
    from utils.po_pdf import build_po_pdf
    a = build_po_pdf(dict(PO, item_layout="unit"), ITEMS, {})
    b = build_po_pdf(dict(PO), ITEMS, {})
    assert a[:4] == b"%PDF" and b[:4] == b"%PDF"
    assert a != b, "단위 레이아웃과 재질 레이아웃의 PDF 가 같으면 안 됨"
