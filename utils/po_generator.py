"""
발주서 xlsx 자동 채움 + 발주번호 발급
"""
import os
import io
from datetime import date, datetime
import openpyxl
from openpyxl.utils import get_column_letter

TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "po_template.xlsx")

# 템플릿 셀 위치 (명진메탈 양식 기준)
CELLS = {
    "po_number": "F6",          # 발주번호 (NO. ...)
    "po_date": "B6",            # 발주일 라벨 옆 (B6에는 "발 주 일 :" 라벨, 실제 날짜는 F6 또는 별도)
    "po_date_value": "F6",      # 실제 날짜 셀 (병합셀 주의)
    "vendor_name": "B7",        # 거래처명
    "items_start_row": 15,      # 품목 시작 행
    "items_end_row": 34,        # 품목 끝 행 (20개 max)
    "col_no": 1,                # NO
    "col_item_name": 3,         # 품명 (C)
    "col_material": 14,         # 재질 (N)
    "col_spec": 16,             # 규격 (P)
    "col_qty": 17,              # 수량 (Q) — 명진 양식엔 없을 수도
    "col_unit_price": 19,       # 단가 (S)
    "col_amount": 21,           # 공급가액 (U)
    "row_subtotal": 35,         # 합계
    "delivery_date": "F36",     # 1. 납기
    "payment_terms": "F37",     # 2. 지불조건
    "delivery_address": "F38",  # 3. 배송지
    "contact_person": "F39",    # 4. 담당자
}


def generate_po_number(client) -> str:
    """발주번호 생성: PO-YYYYMM-### (월별 일련번호)"""
    today = date.today()
    prefix = f"PO-{today.strftime('%Y%m')}-"
    # 이번 달 가장 큰 일련번호 조회
    try:
        rows = client.fetch("purchase_orders",
                            select="po_number",
                            filter_query=f"po_number=like.{prefix}*&order=po_number.desc&limit=1")
        if rows:
            last = rows[0]["po_number"]
            seq = int(last.replace(prefix, "")) + 1
        else:
            seq = 1
    except Exception:
        seq = 1
    return f"{prefix}{seq:03d}"


def safe_set(ws, cell_ref, value):
    """병합셀이면 anchor만 설정, 아니면 그대로"""
    try:
        ws[cell_ref] = value
    except AttributeError:
        # 병합 영역의 anchor 찾기
        for mr in ws.merged_cells.ranges:
            if cell_ref in mr:
                anchor = mr.min_row, mr.min_col
                ws.cell(anchor[0], anchor[1], value)
                return


def fill_po_template(po_data: dict, items: list[dict]) -> bytes:
    """
    템플릿 xlsx에 발주 정보를 채워서 bytes로 반환 (Streamlit 다운로드 버튼용)

    po_data: {
        po_number, po_date (date), vendor_name, delivery_date,
        payment_terms, delivery_address, contact_person
    }
    items: [{item_name, material, spec, qty, unit_price, amount}, ...]  최대 20개
    """
    wb = openpyxl.load_workbook(TEMPLATE_PATH)
    ws = wb["발주서"]

    # 헤더 정보
    safe_set(ws, "B7", po_data.get("vendor_name", ""))
    # 발주일은 셀이 병합되어 있을 수 있어 안전하게
    po_date = po_data.get("po_date", date.today())
    if isinstance(po_date, str):
        po_date_str = po_date
    elif isinstance(po_date, (date, datetime)):
        po_date_str = po_date.strftime("%Y년 %m월 %d일")
    else:
        po_date_str = str(po_date)

    # F6 위치 — 보통 명진 양식에서는 발주일이 들어가는 칸. 발주번호도 같이 표시 가능
    # 안전을 위해 발주번호를 R5 근처, 발주일은 F6에 시도
    safe_set(ws, "F6", po_date_str)

    # 발주번호: R5 시도 (안되면 패스)
    try:
        ws["R5"] = po_data.get("po_number", "")
    except (AttributeError, Exception):
        # 병합셀 — anchor만
        for mr in ws.merged_cells.ranges:
            if "R5" in mr:
                ws.cell(mr.min_row, mr.min_col, po_data.get("po_number", ""))
                break

    # 품목 채움 (행 15~34)
    total_amount = 0
    for i, item in enumerate(items[:20]):
        r = CELLS["items_start_row"] + i
        ws.cell(r, CELLS["col_no"], i + 1)
        ws.cell(r, CELLS["col_item_name"], item.get("item_name", ""))
        if item.get("material"):
            ws.cell(r, CELLS["col_material"], item.get("material"))
        if item.get("spec"):
            ws.cell(r, CELLS["col_spec"], item.get("spec"))
        if item.get("qty") is not None:
            ws.cell(r, CELLS["col_qty"], item.get("qty"))
        if item.get("unit_price") is not None:
            ws.cell(r, CELLS["col_unit_price"], item.get("unit_price"))
        amt = item.get("amount") or (item.get("qty") or 0) * (item.get("unit_price") or 0)
        ws.cell(r, CELLS["col_amount"], amt)
        total_amount += amt

    # 합계 (A35 옆 셀에 기록 시도)
    try:
        ws.cell(CELLS["row_subtotal"], CELLS["col_amount"], total_amount)
    except Exception:
        pass

    # 푸터 정보
    safe_set(ws, "F36", po_data.get("delivery_date", ""))
    safe_set(ws, "F37", po_data.get("payment_terms", "말일 마감 60일 현금"))
    safe_set(ws, "F38", po_data.get("delivery_address", "부산광역시 기장군 산단4로 71"))
    safe_set(ws, "F39", po_data.get("contact_person", "김민수 과장 / 010-3881-1165"))

    # bytes로 반환
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()
