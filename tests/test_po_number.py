"""발주번호 포맷 검증"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.services.purchase_service import is_valid_po_number


def test_valid_po_number():
    assert is_valid_po_number("PO-202605-001")
    assert is_valid_po_number("PO-202512-999")


def test_invalid_po_number():
    assert not is_valid_po_number("")
    assert not is_valid_po_number("PO-20260-001")        # 5자리 yyyymm
    assert not is_valid_po_number("PO-202605-0001")      # 4자리 seq
    assert not is_valid_po_number("po-202605-001")       # 소문자
    assert not is_valid_po_number("PO_202605_001")       # underscore
    assert not is_valid_po_number("MJT-PO26-우성-414")    # 다른 양식
