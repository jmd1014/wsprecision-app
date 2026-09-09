# -*- coding: utf-8 -*-
"""발주서 PDF 생성 (fpdf2 + NanumGothic, 2026-09-09 사용자 요청).

xlsx 양식(po_generator.fill_po_template)과 같은 내용을 A4 PDF 로 —
거래처에 바로 보낼 수 있는 완성 문서. 글꼴은 저장소 fonts/ 의
NanumGothic(OFL) 을 임베드해 Cloud 에서도 한글이 깨지지 않는다.
"""
import os
from datetime import date, datetime

from utils.po_generator import COMPANY_INFO

_FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "fonts")
NAVY = (31, 56, 100)
GRAY = (89, 89, 89)
LINE = (191, 191, 191)
FILL_HEAD = (48, 84, 148)
FILL_SOFT = (222, 230, 240)
FILL_TOTAL = (255, 242, 204)


def _num(v):
    try:
        return f"{int(round(float(v or 0))):,}"
    except (TypeError, ValueError):
        return "-"


def _date_s(v):
    if isinstance(v, (date, datetime)):
        return v.strftime("%Y년 %m월 %d일")
    return str(v or "")


def build_po_pdf(po_data, items, vendor_info=None):
    """po_data/items/vendor_info 는 fill_po_template 과 같은 형식. bytes 반환."""
    from fpdf import FPDF

    vendor_info = vendor_info or {}
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font("NG", "", os.path.join(_FONT_DIR, "NanumGothic-Regular.ttf"))
    pdf.add_font("NG", "B", os.path.join(_FONT_DIR, "NanumGothic-Bold.ttf"))
    pdf.add_page()
    W = pdf.w - pdf.l_margin - pdf.r_margin

    # ── 제목 ──
    pdf.set_font("NG", "B", 22)
    pdf.set_text_color(*NAVY)
    pdf.cell(W, 12, "발  주  서", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("NG", "", 10)
    pdf.set_text_color(*GRAY)
    pdf.cell(W, 6, "PURCHASE ORDER", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("NG", "B", 10.5)
    pdf.set_text_color(*NAVY)
    pdf.cell(W / 2, 7, f"발주번호: {po_data.get('po_number', '')}")
    pdf.cell(W / 2, 7, f"발주일: {_date_s(po_data.get('po_date', date.today()))}",
             align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # ── 수신처 / 발주자 두 상자 ──
    def box(x, title, rows):
        bw = W / 2 - 3
        y0 = pdf.get_y()
        pdf.set_xy(x, y0)
        pdf.set_fill_color(*FILL_HEAD)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("NG", "B", 10)
        pdf.cell(bw, 7, title, fill=True, new_x="LEFT", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        for lab, val in rows:
            pdf.set_x(x)
            pdf.set_font("NG", "B", 9)
            pdf.set_text_color(*GRAY)
            pdf.cell(22, 6.2, lab, border="LB")
            pdf.set_font("NG", "", 9.5)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(bw - 22, 6.2, str(val or "-")[:38], border="RB",
                     new_x="LEFT", new_y="NEXT")
        return pdf.get_y()

    pdf.set_draw_color(*LINE)
    y_top = pdf.get_y()
    y1 = box(pdf.l_margin, "수신 (공급자)", [
        ("상호", po_data.get("vendor_name")),
        ("사업자번호", vendor_info.get("biz_no")),
        ("대표자", vendor_info.get("ceo")),
        ("주소", vendor_info.get("address")),
        ("전화", vendor_info.get("phone")),
    ])
    pdf.set_y(y_top)
    y2 = box(pdf.l_margin + W / 2 + 3, "발주 (공급받는자)", [
        ("상호", COMPANY_INFO["name"]),
        ("사업자번호", COMPANY_INFO["biz_no"]),
        ("대표자", COMPANY_INFO["ceo"]),
        ("주소", COMPANY_INFO["address"]),
        ("전화/팩스", f"{COMPANY_INFO['phone']} / {COMPANY_INFO['fax']}"),
    ])
    pdf.set_y(max(y1, y2) + 5)

    # ── 품목 표 ──
    cols = [("NO", 10, "C"), ("품명", 62, "L"), ("재질", 20, "C"),
            ("규격", 32, "C"), ("수량", 18, "R"), ("단가", 22, "R"),
            ("금액", 26, "R")]
    pdf.set_font("NG", "B", 9.5)
    pdf.set_fill_color(*FILL_HEAD)
    pdf.set_text_color(255, 255, 255)
    for name, w, _ in cols:
        pdf.cell(w, 7.5, name, border=1, align="C", fill=True)
    pdf.ln()
    pdf.set_text_color(0, 0, 0)
    supply = 0
    for i, it in enumerate(items, 1):
        qty = float(it.get("qty") or 0)
        up = float(it.get("unit_price") or 0)
        amt = it.get("amount")
        amt = float(amt) if amt not in (None, "") else qty * up
        supply += amt
        pdf.set_font("NG", "", 9.5)
        vals = [str(i), str(it.get("item_name") or ""), str(it.get("material") or ""),
                str(it.get("spec") or ""), _num(qty), _num(up), _num(amt)]
        # 긴 품명은 글자 크기 축소
        for (name, w, al), v in zip(cols, vals):
            fs = 9.5
            if name in ("품명", "규격") and pdf.get_string_width(v) > w - 3:
                fs = 8
                pdf.set_font("NG", "", fs)
                while pdf.get_string_width(v) > w - 3 and fs > 6:
                    fs -= 0.5
                    pdf.set_font("NG", "", fs)
            pdf.cell(w, 7, v, border=1, align=al)
            pdf.set_font("NG", "", 9.5)
        pdf.ln()
        memo = (it.get("memo") or it.get("remark") or "").strip()
        if memo:
            pdf.set_font("NG", "", 8)
            pdf.set_text_color(*GRAY)
            pdf.cell(10, 5.5, "", border="LB")
            pdf.cell(sum(w for _, w, _ in cols) - 10, 5.5, "비고: " + memo,
                     border="RB", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
    for _ in range(max(0, 8 - len(items))):
        for name, w, al in cols:
            pdf.cell(w, 7, "", border=1)
        pdf.ln()

    # ── 합계 ──
    vat = round(supply * 0.1)
    total_w = sum(w for _, w, _ in cols)
    pdf.set_font("NG", "B", 10)
    for lab, val, fill in (("공급가액", supply, FILL_SOFT), ("부가세 (10%)", vat, FILL_SOFT),
                           ("합계 (VAT 포함)", supply + vat, FILL_TOTAL)):
        pdf.set_fill_color(*fill)
        pdf.cell(total_w - 48, 7.5, lab, border=1, align="R", fill=True)
        pdf.cell(48, 7.5, _num(val) + " 원", border=1, align="R", fill=True,
                 new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # ── 조건 ──
    pdf.set_font("NG", "B", 10)
    pdf.set_text_color(*NAVY)
    pdf.cell(W, 7, "발주 조건", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    for lab, val in (("납기", po_data.get("delivery_date")),
                     ("지불조건", po_data.get("payment_terms")),
                     ("배송지", po_data.get("delivery_address")),
                     ("담당자", po_data.get("contact_person")),
                     ("비고", po_data.get("remark"))):
        if lab == "비고" and not val:
            continue
        pdf.set_font("NG", "B", 9)
        pdf.set_text_color(*GRAY)
        pdf.cell(24, 6.5, lab, border="B")
        pdf.set_font("NG", "", 9.5)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(W - 24, 6.5, str(val or "-"), border="B",
                 new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)

    # ── 서명 ──
    pdf.set_font("NG", "", 9.5)
    pdf.cell(W / 2, 8, f"발주자: {COMPANY_INFO['name']}   (인)", align="C")
    pdf.cell(W / 2, 8, "수신 확인:                (인)", align="C",
             new_x="LMARGIN", new_y="NEXT")
    # 바닥글 — 자동 페이지 나눔을 끄고 현재 페이지 하단에 고정
    pdf.set_auto_page_break(auto=False)
    pdf.set_font("NG", "", 8)
    pdf.set_text_color(*GRAY)
    pdf.set_y(pdf.h - 12)
    pdf.cell(W, 5, f"{COMPANY_INFO['name']} · {COMPANY_INFO['address']} · "
                   f"Tel {COMPANY_INFO['phone']} · Fax {COMPANY_INFO['fax']}",
             align="C")
    return bytes(pdf.output())
