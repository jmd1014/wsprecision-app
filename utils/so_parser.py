"""
수주 파일 자동 파싱 (3개 거래처 양식)
- HDX 엑셀 (53열, 자재코드는 우성정밀 품번 형식 — 거의 자동 매칭)
- 미진정밀 외주발주품목조회 엑셀 (37열, 제품번호=우성정밀 품번 100%)
- 엠제이티 PDF (단순 표 1개)
"""
import io
import re
from datetime import date, datetime
import openpyxl


def _to_num(v):
    if v is None or v == "": return None
    try: return float(str(v).replace(",", ""))
    except: return None


def _to_int(v):
    n = _to_num(v)
    return int(n) if n is not None else None


def _to_date(v):
    if v is None: return None
    if isinstance(v, datetime): return v.date()
    if isinstance(v, date): return v
    s = str(v).strip()
    if not s: return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d", "%Y%m%d"):
        try: return datetime.strptime(s, fmt).date()
        except: pass
    return None


def parse_hdx_excel(file_bytes: bytes, filename: str = "") -> list[dict]:
    """
    HDX 수주 엑셀 파싱 — 행이 곧 품목.
    같은 수주번호가 여러 행 (= 한 수주에 여러 품목)일 수 있어 그룹핑은 호출자가 처리.

    반환: 각 품목별 dict 리스트 (so_number, line_no, item, qty, price 등)
    """
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    ws = wb[wb.sheetnames[0]]
    headers = [c.value for c in ws[1]]

    def col(name):
        try: return headers.index(name) + 1
        except: return None

    items = []
    for r in range(2, ws.max_row + 1):
        no = ws.cell(r, col("No")).value if col("No") else None
        if no is None: continue
        item = {
            "_source": "HDX_EXCEL",
            "_raw_filename": filename,
            "customer": "HDX",
            "so_number": str(ws.cell(r, col("수주번호")).value) if col("수주번호") else "",
            "line_no": int(ws.cell(r, col("항번")).value) if col("항번") and ws.cell(r, col("항번")).value else int(no),
            "so_date": _to_date(ws.cell(r, col("수주일자")).value) if col("수주일자") else None,
            "due_date": _to_date(ws.cell(r, col("납기요청일")).value) if col("납기요청일") else None,
            "customer_part_no": ws.cell(r, col("자재코드")).value if col("자재코드") else None,
            "customer_item_name": ws.cell(r, col("자재명")).value if col("자재명") else None,
            "qty": _to_num(ws.cell(r, col("수량")).value) if col("수량") else None,
            "unit": ws.cell(r, col("단위")).value if col("단위") else "EA",
            "unit_price": _to_num(ws.cell(r, col("단가")).value) if col("단가") else None,
            "amount": _to_num(ws.cell(r, col("금액")).value) if col("금액") else None,
            "delivery_address": ws.cell(r, col("납품처 장소")).value if col("납품처 장소") else None,
            "remark": ws.cell(r, col("특이사항")).value if col("특이사항") else None,
            "status_raw": ws.cell(r, col("입고상태")).value if col("입고상태") else None,
            "raw_row": {h: ws.cell(r, ci+1).value for ci, h in enumerate(headers) if h},
        }
        items.append(item)
    return items


def parse_mijin_excel(file_bytes: bytes, filename: str = "") -> list[dict]:
    """
    미진정밀 외주발주품목조회 엑셀 파싱.
    행 1 = 타이틀 ("외주발주품목조회"), 행 2 = 헤더, 행 3 = TOTAL, 행 4부터 데이터.
    """
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    ws = wb[wb.sheetnames[0]]
    headers = [c.value for c in ws[2]]  # 행 2가 헤더

    def col(name):
        try: return headers.index(name) + 1
        except: return None

    items = []
    line_seq = {}  # so_number → 다음 line_no
    for r in range(4, ws.max_row + 1):  # 행 3은 TOTAL, 행 4부터
        sel = ws.cell(r, 1).value  # 선택 컬럼
        # TOTAL 행 또는 빈 행 skip
        if sel is None: continue
        po = ws.cell(r, col("외주발주번호")).value
        if not po or str(po).strip() in ("TOTAL", ""): continue

        so_num = str(po)
        line_seq[so_num] = line_seq.get(so_num, 0) + 1

        item = {
            "_source": "MIJIN_EXCEL",
            "_raw_filename": filename,
            "customer": "미진정밀",
            "so_number": so_num,
            "line_no": line_seq[so_num],
            "so_date": _to_date(ws.cell(r, col("외주발주일")).value) if col("외주발주일") else None,
            "due_date": _to_date(ws.cell(r, col("납기일")).value) if col("납기일") else None,
            # 미진은 제품번호가 우성정밀 품번
            "customer_part_no": ws.cell(r, col("제품번호")).value if col("제품번호") else None,
            "canonical_pn_hint": ws.cell(r, col("제품번호")).value if col("제품번호") else None,
            "customer_item_name": ws.cell(r, col("제품명")).value if col("제품명") else None,
            "qty": _to_num(ws.cell(r, col("발주수량")).value) if col("발주수량") else None,
            "received_qty": _to_num(ws.cell(r, col("납품수량")).value) if col("납품수량") else 0,
            "unit_price": _to_num(ws.cell(r, col("단가")).value) if col("단가") else None,
            "amount": _to_num(ws.cell(r, col("금액")).value) if col("금액") else None,
            "vat": _to_num(ws.cell(r, col("부가세")).value) if col("부가세") else None,
            "total": _to_num(ws.cell(r, col("금액계")).value) if col("금액계") else None,
            "mes_work_order": ws.cell(r, col("작업지시번호")).value if col("작업지시번호") else None,
            "status_raw": ws.cell(r, col("진행상태")).value if col("진행상태") else None,
            "raw_row": {h: ws.cell(r, ci+1).value for ci, h in enumerate(headers) if h},
        }
        items.append(item)
    return items


def parse_mjt_pdf(file_bytes: bytes, filename: str = "") -> list[dict]:
    """엠제이티(MJT) PDF 발주서 파싱"""
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError("pdfplumber 필요")

    items = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        full_text = "\n".join(pg.extract_text() or "" for pg in pdf.pages)

        # 발주번호: MJT-PO26-우성-414
        m_no = re.search(r'발주번호\s+(MJT-[A-Z0-9가-힣\-]+)', full_text)
        so_number = m_no.group(1) if m_no else ""
        # 발주일자
        m_date = re.search(r'발주일자\s+(\d{4}-\d{2}-\d{2})', full_text)
        so_date = _to_date(m_date.group(1)) if m_date else None
        # 납기일자
        m_due = re.search(r'납기일자\s+(\d{4}-\d{2}-\d{2})', full_text)
        due_date = _to_date(m_due.group(1)) if m_due else None

        # 표 추출
        for pg in pdf.pages:
            tables = pg.extract_tables() or []
            for tbl in tables:
                for row in tbl:
                    if not row or not row[0]: continue
                    # 행 첫 셀이 숫자(라인 번호)면 품목 행
                    cell0 = str(row[0]).strip()
                    if not cell0.isdigit(): continue
                    line_no = int(cell0)
                    # 품번, 단위, 수량, 단가, 금액, 비고
                    pn = str(row[1] or "").strip() if len(row) > 1 else ""
                    unit = str(row[2] or "").strip() if len(row) > 2 else "EA"
                    qty = _to_num(row[3]) if len(row) > 3 else None
                    unit_price = _to_num(row[4]) if len(row) > 4 else None
                    amount_raw = row[5] if len(row) > 5 else None
                    # 일부 PDF는 amount에 공백 들어감 (예: "7 8,000,000")
                    if amount_raw:
                        amount_str = re.sub(r'\s+', '', str(amount_raw))
                        amount = _to_num(amount_str)
                    else:
                        amount = None
                    remark = str(row[6] or "").strip() if len(row) > 6 else ""
                    if not pn: continue

                    items.append({
                        "_source": "MJT_PDF",
                        "_raw_filename": filename,
                        "customer": "㈜엠제이티",
                        "so_number": so_number,
                        "line_no": line_no,
                        "so_date": so_date,
                        "due_date": due_date,
                        # 엠제이티 품번도 우성정밀 형식 그대로
                        "customer_part_no": pn,
                        "canonical_pn_hint": pn,
                        "customer_item_name": "",
                        "qty": qty,
                        "unit": unit,
                        "unit_price": unit_price,
                        "amount": amount,
                        "remark": remark,
                        "raw_row": {"line": line_no, "pn": pn, "qty": qty, "unit_price": unit_price},
                    })

    return items


# ─── 우성정밀 품번 매칭 ───
def match_canonical_pn(items: list[dict], canonical_map: dict) -> list[dict]:
    """
    파싱된 items에 우성정밀 품번/product_id 자동 매칭.
    canonical_map: { match_key: canonical_pn } (db.fetch로 product_master에서 빌드)
    """
    def mk(s):
        if not s: return ""
        s = str(s).upper()
        s = re.sub(r'\([^)]*\)', '', s)
        s = re.sub(r'[\s\-_·,\.]+', '', s)
        return s

    def normalize_item(item_text):
        """;OP, ;PM 등 제거"""
        if not item_text: return ""
        pn = str(item_text).strip().split(';')[0].strip()
        return pn

    for it in items:
        candidates = [
            it.get("canonical_pn_hint"),
            it.get("customer_part_no"),
        ]
        matched = None
        for c in candidates:
            if not c: continue
            # 1) 정확 매칭
            if mk(c) in canonical_map:
                matched = canonical_map[mk(c)]; break
            # 2) ;XXX 제거 후 매칭
            norm = normalize_item(c)
            if mk(norm) in canonical_map:
                matched = canonical_map[mk(norm)]; break
        it["matched_pn"] = matched
    return items


def parse_so_file(customer_type: str, file_bytes: bytes, filename: str = "") -> list[dict]:
    """통합 진입점"""
    if customer_type == "HDX":
        return parse_hdx_excel(file_bytes, filename)
    elif customer_type == "미진정밀":
        return parse_mijin_excel(file_bytes, filename)
    elif customer_type in ("㈜엠제이티", "엠제이티"):
        return parse_mjt_pdf(file_bytes, filename)
    else:
        raise ValueError(f"지원하지 않는 양식: {customer_type}")


def group_by_so_number(items: list[dict]) -> list[dict]:
    """
    같은 so_number 행들을 그룹핑하여 sales_orders 헤더 + items로 변환.
    반환: [{header: {...}, items: [{...}, ...]}, ...]
    """
    groups = {}
    for it in items:
        so = it.get("so_number") or "(no_number)"
        if so not in groups:
            groups[so] = {"header": None, "items": []}
        groups[so]["items"].append(it)

    result = []
    for so, g in groups.items():
        items_list = g["items"]
        first = items_list[0]
        header = {
            "so_number": so,
            "customer": first["customer"],
            "so_date": first.get("so_date"),
            "due_date": min((i["due_date"] for i in items_list if i.get("due_date")), default=None),
            "total_amount": sum((i.get("amount") or 0) for i in items_list),
            "vat": sum((i.get("vat") or (i.get("amount") or 0) * 0.1) for i in items_list),
            "source": first.get("_source"),
            "source_file": first.get("_raw_filename"),
            "delivery_address": first.get("delivery_address"),
            "status": "DRAFT",
        }
        result.append({"header": header, "items": items_list})
    return result
