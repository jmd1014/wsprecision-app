# -*- coding: utf-8 -*-
"""매입 스캔 정정 기록 — 순수 함수 (2026-11-04, 매입 OCR r2 / 마이그레이션 079).

기준: _매입OCR_r2_정정기록_묶음_지시문_20261104.md §2.

- 담당자가 검토 표에서 고쳐 "이 장을 장부에 추가"에 성공하면 화면이 장마다 `scan_log_row()` 1행을
  purchase_scan_log 에 남긴다(실패는 화면이 삼킴). 검토 세션은 그 표를 읽어 셀 정확도·반복 유형을 집계한다.
- OCR 행 = 검토 표 기본값(`stmt_ocr.ocr_row_defaults` 키: save_item·price…), 저장 행 = 장부 키(item·unit_price…).
  둘 다 `idx`(판독 행 번호, 0부터)를 가진다. 담당자가 추가한 행은 idx 가 None.
- 이 모듈은 Streamlit·DB 를 모른다.
"""
import math
from datetime import date, datetime

from utils import stmt_ocr as _socr
from utils.purchase_sync import vendor_key

# (저장 행 키, OCR 행 키) — diff 의 field 이름은 저장(장부) 키
DIFF_FIELDS = (("item", "save_item"), ("unit", "unit"), ("qty", "qty"), ("weight", "weight"),
               ("unit_price", "price"), ("amount", "amount"), ("vat", "vat"), ("remark", "remark"))
_MONEY = {"unit_price", "amount", "vat"}          # 1원 미만 차이는 같은 값
_NUMS = _MONEY | {"qty", "weight"}


def _num(v):
    """None·NaN·빈 문자열 → None, 숫자 문자열 포함 → float. 숫자가 아니면 None."""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(str(v).replace(",", "")) if isinstance(v, str) else float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _idx(v):
    f = _num(v)
    return int(f) if f is not None else None


def _same(field, a, b):
    if field in _NUMS:
        x, y = _num(a), _num(b)
        if x is None or y is None:
            return x is None and y is None
        return abs(x - y) < (1.0 if field in _MONEY else 1e-9)
    sa = "" if a is None or (isinstance(a, float) and not math.isfinite(a)) else str(a).strip()
    sb = "" if b is None or (isinstance(b, float) and not math.isfinite(b)) else str(b).strip()
    if field == "unit":
        sa, sb = sa.upper(), sb.upper()
    return sa == sb


def scan_diff(ocr_rows, saved_rows):
    """OCR 행(검토 표 기본값) ↔ 저장 행 비교.

    idx 가 양쪽에 있으면 DIFF_FIELDS 를 비교(숫자는 None↔NaN 같음, 금액·단가·세액은 1원 미만 같음, 문자열은 strip),
    OCR 에만 있으면 removed(담당자가 지웠거나 품명을 비워 저장 안 됨), 저장에만 있으면 added.
    → {"changed": [{idx, field, ocr, saved}], "added": [저장 행 위치], "removed": [idx],
       "n_cells_changed", "n_rows_added", "n_rows_removed"}
    added 는 OCR idx 가 없어 저장 행 목록(items_saved) 안의 위치(0부터)로 적는다.
    """
    ocr_by = {}
    for r in ocr_rows or []:
        i = _idx(r.get("idx"))
        if i is not None:
            ocr_by[i] = r
    changed, added, seen = [], [], set()
    for pos, s in enumerate(saved_rows or []):
        i = _idx(s.get("idx"))
        if i is None or i not in ocr_by or i in seen:
            added.append(pos)
            continue
        seen.add(i)
        o = ocr_by[i]
        for sf, of in DIFF_FIELDS:
            if not _same(sf, o.get(of), s.get(sf)):
                changed.append({"idx": i, "field": sf, "ocr": o.get(of), "saved": s.get(sf)})
    removed = sorted(i for i in ocr_by if i not in seen)
    return {"changed": changed, "added": added, "removed": removed,
            "n_cells_changed": len(changed), "n_rows_added": len(added), "n_rows_removed": len(removed)}


def _clean(v):
    """jsonb·PostgREST 로 보낼 수 있게 — NaN·inf → None, numpy 수 → 파이썬 수, 날짜 → ISO 문자열."""
    if isinstance(v, dict):
        return {str(k): _clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_clean(x) for x in v]
    if v is None or isinstance(v, (bool, str, int)):
        return v
    if isinstance(v, float):
        return v if math.isfinite(v) else None
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if hasattr(v, "item"):                       # numpy 수
        try:
            return _clean(v.item())
        except (TypeError, ValueError):
            pass
    return str(v)


def scan_log_row(page, head_saved, ocr_rows, saved_rows, user, file_name):
    """purchase_scan_log 1행(079).

    page: 판독 결과 한 장(stmt_ocr.parse_document 원소 — vendor·vendor_how·date·sum·printed_totals·total_ok·lines·psm·rot·page)
    head_saved: {"vendor", "date"(ISO), "statement_no"} — 담당자가 저장한 머리
    n_head_changed = 거래처 다름(법인 표기 무시) + 거래일 다름 (0~2).
    """
    page = page or {}
    head_saved = head_saved or {}
    d = scan_diff(ocr_rows, saved_rows)
    v_ocr = ((page.get("vendor") or {}).get("name") or "").strip() or None
    v_saved = str(head_saved.get("vendor") or "").strip() or None
    d_ocr = str(page.get("date") or "")[:10] or None
    d_saved = str(head_saved.get("date") or "")[:10] or None
    pt = [x for x in (_num(t) for t in (page.get("printed_totals") or [])) if x is not None]
    row = {
        "created_by": user,
        "rules_version": getattr(_socr, "OCR_RULES_VERSION", None),
        "file_name": file_name,
        "page": _idx(page.get("page")),
        "psm": _idx(page.get("psm")),
        "rot": _idx(page.get("rot")),
        "vendor_ocr": v_ocr,
        "vendor_how": page.get("vendor_how"),
        "vendor_saved": v_saved,
        "date_ocr": d_ocr,
        "date_saved": d_saved,
        "statement_no": (str(head_saved.get("statement_no") or "").strip() or None),
        "total_ok": bool(page.get("total_ok")),
        "printed_total": max(pt) if pt else None,
        "ocr_sum": _num(page.get("sum")),
        "saved_sum": sum(_num(s.get("amount")) or 0.0 for s in (saved_rows or [])),
        "lines": list(page.get("lines") or []),
        "items_ocr": list(ocr_rows or []),
        "items_saved": list(saved_rows or []),
        "diff": d,
        "n_rows_ocr": len(ocr_rows or []),
        "n_rows_saved": len(saved_rows or []),
        "n_rows_added": d["n_rows_added"],
        "n_rows_removed": d["n_rows_removed"],
        "n_cells_changed": d["n_cells_changed"],
        "n_head_changed": int(vendor_key(v_ocr) != vendor_key(v_saved)) + int(d_ocr != d_saved),
    }
    return _clean(row)
