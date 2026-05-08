"""
발주서 xlsx 자동 채움 + 발주번호 발급
- 병합셀 안전 처리: 모든 merge 풀고 값 쓴 후 재merge
"""
import os
import io
from datetime import date, datetime
import openpyxl

TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "templates", "po_template.xlsx"
)


def generate_po_number(client) -> str:
    """발주번호 생성: PO-YYYYMM-### (월별 일련)"""
    today = date.today()
    prefix = f"PO-{today.strftime('%Y%m')}-"
    try:
        rows = client.fetch(
            "purchase_orders", "po_number",
            f"po_number=like.{prefix}*&order=po_number.desc&limit=1"
        )
        if rows:
            seq = int(rows[0]["po_number"].replace(prefix, "")) + 1
        else:
            seq = 1
    except Exception:
        seq = 1
    return f"{prefix}{seq:03d}"


def fill_po_template(po_data: dict, items: list[dict]) -> bytes:
    """
    템플릿 xlsx에 발주 정보 채워서 bytes 반환.
    병합셀 안전 처리 — 모든 merge 풀고 값 쓰고 재merge.
    """
    wb = openpyxl.load_workbook(TEMPLATE_PATH)
    ws = wb["발주서"]

    # ─── 1. 모든 병합 풀기 (값 쓸 수 있도록) ───
    merge_backup = [str(mr) for mr in list(ws.merged_cells.ranges)]
    for mr_str in merge_backup:
        try:
            ws.unmerge_cells(mr_str)
        except Exception:
            pass

    # ─── 2. 헤더 정보 ───
    po_date = po_data.get("po_date", date.today())
    if isinstance(po_date, str):
        po_date_str = po_date
    elif isinstance(po_date, (date, datetime)):
        po_date_str = po_date.strftime("%Y년 %m월 %d일")
    else:
        po_date_str = str(po_date)

    ws["F6"] = po_date_str
    ws["B7"] = po_data.get("vendor_name", "")
    ws["R5"] = po_data.get("po_number", "")

    # ─── 3. 품목 (행 15~34, 최대 20개) ───
    total_amount = 0
    for i, item in enumerate(items[:20]):
        r = 15 + i
        ws.cell(r, 1, i + 1)                                        # NO (A)
        ws.cell(r, 3, item.get("item_name", ""))                     # 품명 (C)
        if item.get("material"):
            ws.cell(r, 14, item["material"])                         # 재질 (N)
        if item.get("spec"):
            ws.cell(r, 16, item["spec"])                             # 규격 (P)
        qty = item.get("qty") or 0
        up = item.get("unit_price") or 0
        amt = qty * up
        if qty:
            ws.cell(r, 17, qty)                                      # 수량 (Q)
        if up:
            ws.cell(r, 19, up)                                       # 단가 (S)
        if amt:
            ws.cell(r, 21, amt)                                      # 공급가액 (U)
        total_amount += amt

    # ─── 4. 합계 (행 35) ───
    ws.cell(35, 21, total_amount)

    # ─── 5. 푸터 ───
    ws["F36"] = po_data.get("delivery_date", "") or ""
    ws["F37"] = po_data.get("payment_terms", "") or "말일 마감 60일 현금"
    ws["F38"] = po_data.get("delivery_address", "") or "부산광역시 기장군 산단4로 71"
    ws["F39"] = po_data.get("contact_person", "") or "김민수 과장 / 010-3881-1165"

    # ─── 6. 발주금액 표시 (A12 옆) ───
    try:
        ws.cell(12, 6, f"₩{total_amount:,}")
    except Exception:
        pass

    # ─── 7. 병합 복원 ───
    for mr_str in merge_backup:
        try:
            ws.merge_cells(mr_str)
        except Exception:
            pass

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()
