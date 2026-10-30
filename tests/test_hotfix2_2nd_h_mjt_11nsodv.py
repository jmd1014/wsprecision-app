# -*- coding: utf-8 -*-
"""핫픽스 2 후속 2차 묶음 H — 엠제이티 전용 품번에 11NSODV-06 추가 (사용자 결정 2026-10-30).

근거: 마감내역 2024-10 이후 ㈜엠제이티 전용 117건. 미진 외주발주품목조회 엑셀의 `4S11NSODV-06;OUP` 라인은
(주)엠제이티 '-MJT' 수주로 나뉜다. 기존 2025-03 ERP 수주 202503200012 라인은 코드와 무관(사용자가 화면에서 종결).
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests.test_hotfix3_mijin_excel_customer import MIJIN, MJT, PO, _workbook  # noqa: E402
from utils.so_parser import group_by_so_number, parse_mijin_excel  # noqa: E402


def test_11nsodv_06_is_mjt_only():
    from utils.mjt_rules import MJT_ONLY_PNS, customer_for
    assert "11NSODV-06" in MJT_ONLY_PNS
    assert customer_for("11NSODV-06") == MJT and customer_for(None, "11NSODV-06;OUP") == MJT
    assert customer_for("11NSODV-05") == MIJIN                     # 이웃 품번은 그대로


def test_mijin_excel_11nsodv_06_goes_to_mjt_group():
    rows = [("4S11NSODV-06;OUP", "NSODV 6", 30, 2500), ("4HDV-VM-04;OUP", "HDV 4", 50, 3000)]
    items = parse_mijin_excel(_workbook(rows), "외주발주품목조회.xlsx")
    assert [(it["customer"], it["so_number"], it["line_no"]) for it in items] == [
        (MJT, f"{PO}-MJT", 1), (MIJIN, PO, 1)]
    by = {(g["header"]["customer"], g["header"]["so_number"]): g for g in group_by_so_number(items)}
    assert set(by) == {(MIJIN, PO), (MJT, f"{PO}-MJT")}
    assert [it["customer_part_no"] for it in by[(MJT, f"{PO}-MJT")]["items"]] == ["4S11NSODV-06;OUP"]
    assert by[(MJT, f"{PO}-MJT")]["header"]["total_amount"] == 30 * 2500
