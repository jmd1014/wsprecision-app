"""매입 OCR r2(2026-11-04) — 정정 기록 순수 함수 utils.scan_log (scan_diff · scan_log_row).

OCR 행 = 검토 표 기본값(ocr_row_defaults 키), 저장 행 = 장부 키. 둘 다 idx(판독 행 번호)로 짝짓는다.
"""
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from utils import scan_log as L  # noqa: E402
from utils import stmt_ocr as S  # noqa: E402


def _ocr(i, item="STS304환봉 40￠*27ℓ", unit="KG", qty=10.0, weight=21.0, price=9100.0, amount=191100.0,
         vat=19110.0, remark=""):
    return {"idx": i, "save_item": item, "ocr_item": item, "score": 90, "unit": unit, "qty": qty, "weight": weight,
            "price": price, "amount": amount, "vat": vat, "remark": remark, "note": "", "how": "mul",
            "fixed_from": None}


def _saved(o, **kw):
    """OCR 행을 그대로 저장한 장부 행(화면 _rows 와 같은 키) + 바꿀 값."""
    r = {"idx": o["idx"], "trade_date": "2026-10-23", "vendor": "(주)명진메탈", "item": o["save_item"],
         "unit": o["unit"], "qty": o["qty"], "weight": o["weight"], "unit_price": o["price"],
         "amount": o["amount"], "vat": o["vat"], "total": o["amount"] + o["vat"], "remark": o["remark"] or None}
    r.update(kw)
    return r


def _page(**kw):
    p = {"page": 3, "rot": 0, "psm": 6, "vendor": {"name": "(주)명진메탈"}, "vendor_how": "biz",
         "date": "2026-10-23", "items": [], "sum": 382200.0, "printed_totals": [382200.0, 420420.0],
         "total_ok": True, "vat_seen": True, "lines": ["1 STS304 ...", "합계 382,200"], "file": "scan.pdf"}
    p.update(kw)
    return p


HEAD = {"vendor": "(주)명진메탈", "date": "2026-10-23", "statement_no": ""}


def test_no_change_all_zero():
    ocr = [_ocr(0), _ocr(1)]
    d = L.scan_diff(ocr, [_saved(o) for o in ocr])
    assert d == {"changed": [], "added": [], "removed": [], "n_cells_changed": 0, "n_rows_added": 0,
                 "n_rows_removed": 0}


def test_one_cell_changed():
    ocr = [_ocr(0), _ocr(1)]
    sv = [_saved(ocr[0]), _saved(ocr[1], unit_price=9200.0)]
    d = L.scan_diff(ocr, sv)
    assert d["changed"] == [{"idx": 1, "field": "unit_price", "ocr": 9100.0, "saved": 9200.0}]
    assert (d["n_cells_changed"], d["n_rows_added"], d["n_rows_removed"]) == (1, 0, 0)


def test_rows_added_and_removed():
    ocr = [_ocr(0), _ocr(1), _ocr(2)]
    added = _saved(_ocr(9, item="절단비"), idx=None)
    sv = [_saved(ocr[0]), _saved(ocr[2]), added]
    d = L.scan_diff(ocr, sv)
    assert d["removed"] == [1] and d["added"] == [2], "added 는 저장 행 위치"
    assert (d["n_cells_changed"], d["n_rows_added"], d["n_rows_removed"]) == (0, 1, 1)


def test_nan_none_and_sub_won_equal():
    ocr = [_ocr(0, qty=None, remark="")]
    sv = [_saved(ocr[0], qty=float("nan"), amount=191100.4, vat=19110.9, remark=None, item="  STS304환봉 40￠*27ℓ ",
                 unit="kg")]
    assert L.scan_diff(ocr, sv)["n_cells_changed"] == 0, "None↔NaN·1원 미만·strip·단위 대소문자"
    sv2 = [_saved(ocr[0], qty=100.0, amount=191101.0)]
    ch = {c["field"] for c in L.scan_diff(ocr, sv2)["changed"]}
    assert ch == {"qty", "amount"}, "빈칸→값, 1원 차이는 정정"


def test_qty_compared_exactly_not_by_won():
    ocr = [_ocr(0, unit="EA", qty=1.016, weight=None)]
    assert L.scan_diff(ocr, [_saved(ocr[0], qty=1.0)])["n_cells_changed"] == 1, "수량·중량은 1원 허용 없음"


def test_float_idx_from_dataframe_and_duplicate_idx():
    ocr = [_ocr(0), _ocr(1)]
    sv = [_saved(ocr[0], idx=0.0), _saved(ocr[1], idx=1.0), _saved(ocr[1], idx=1.0)]
    d = L.scan_diff(ocr, sv)
    assert d["n_cells_changed"] == 0 and d["added"] == [2], "같은 idx 두 번째는 추가 행으로"


def test_log_row_counts_head_and_version():
    ocr = [_ocr(0), _ocr(1)]
    sv = [_saved(ocr[0]), _saved(ocr[1], item="STS304환봉 40￠*28ℓ")]
    row = L.scan_log_row(_page(), {"vendor": "명진메탈", "date": "2026-10-23", "statement_no": " 23-01 "},
                         ocr, sv, "홍길동", "scan.pdf")
    assert row["rules_version"] == S.OCR_RULES_VERSION == "r2"
    assert row["n_head_changed"] == 0, "법인 표기 '(주)' 차이는 정정 아님"
    assert (row["n_rows_ocr"], row["n_rows_saved"], row["n_cells_changed"]) == (2, 2, 1)
    assert row["statement_no"] == "23-01" and row["created_by"] == "홍길동" and row["file_name"] == "scan.pdf"
    assert row["printed_total"] == 420420.0 and row["ocr_sum"] == 382200.0 and row["saved_sum"] == 382200.0
    assert (row["page"], row["psm"], row["rot"], row["vendor_how"]) == (3, 6, 0, "biz")
    assert row["lines"] == ["1 STS304 ...", "합계 382,200"]
    assert row["diff"]["changed"][0]["field"] == "item"


def test_log_row_vendor_and_date_corrected():
    ocr = [_ocr(0)]
    row = L.scan_log_row(_page(), {"vendor": "성보정밀", "date": "2026-10-24"}, ocr, [_saved(ocr[0])], "u", "f")
    assert row["n_head_changed"] == 2 and row["n_cells_changed"] == 0
    assert (row["vendor_ocr"], row["vendor_saved"], row["date_ocr"], row["date_saved"]) == \
        ("(주)명진메탈", "성보정밀", "2026-10-23", "2026-10-24")
    row2 = L.scan_log_row(_page(vendor=None, vendor_how=None, date=None, printed_totals=[]),
                          HEAD, ocr, [_saved(ocr[0])], "u", "f")
    assert row2["n_head_changed"] == 2, "OCR 이 못 찾은 거래처·날짜를 채운 것도 정정"
    assert row2["vendor_ocr"] is None and row2["date_ocr"] is None and row2["printed_total"] is None


def test_log_row_is_json_safe():
    """NaN·numpy 수가 섞여도 PostgREST 로 보낼 수 있는 JSON(NaN 없음)."""
    import numpy as np
    ocr = [_ocr(0, qty=float("nan"))]
    sv = [_saved(ocr[0], qty=np.float64("nan"), weight=np.float64(21.0), amount=np.int64(191100))]
    row = L.scan_log_row(_page(sum=np.float64(191100.0)), HEAD, ocr, sv, "u", "f")
    txt = json.dumps(row, ensure_ascii=False, allow_nan=False)
    back = json.loads(txt)
    assert back["items_saved"][0]["qty"] is None and back["items_ocr"][0]["qty"] is None
    assert back["items_saved"][0]["amount"] == 191100 and isinstance(back["ocr_sum"], float)
    assert not any(isinstance(v, float) and math.isnan(v) for v in back.values())
