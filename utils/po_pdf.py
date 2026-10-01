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


def wrap_lines(text, width_of, max_w):
    """text 를 max_w 안에 들어가는 줄들로 나눈다 — 글자를 버리지 않는다.
    공백에서 끊을 수 있으면 단어 단위로, 아니면 글자 단위로."""
    lines, cur = [], ""
    for ch in str(text or ""):
        if cur and width_of(cur + ch) > max_w:
            cut = cur.rfind(" ")
            if cut > len(cur) * 0.5:
                lines.append(cur[:cut])
                cur = cur[cut + 1:] + ch
            else:
                lines.append(cur)
                cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines or [""]


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
    # 값이 칸보다 길 때 규칙 (2026-10-01 사용자: 주소가 칸을 벗어남):
    #   ① 글자를 9.5pt → 8pt 까지 줄여 한 줄에 맞춘다
    #   ② 그래도 넘치면 8pt 로 칸 안에서 줄바꿈하고 그 행 높이를 늘린다
    #   (좌우 상자의 같은 행은 높이를 맞춰 줄이 어긋나지 않게)
    # 예전에는 38자에서 잘라 내기만 해서 폭을 넘거나 뒤가 잘렸다.
    LAB_W, ROW_H, PAD = 22, 6.2, 2.0
    bw = W / 2 - 3
    val_w = bw - LAB_W

    def _fit(text):
        """(글자 크기, 줄 목록) — 한 줄 축소 우선, 안 되면 8pt 줄바꿈."""
        text = str(text or "-")
        fs = 9.5
        pdf.set_font("NG", "", fs)
        while pdf.get_string_width(text) > val_w - PAD and fs > 8:
            fs -= 0.5
            pdf.set_font("NG", "", fs)
        if pdf.get_string_width(text) <= val_w - PAD:
            return fs, [text]
        return fs, wrap_lines(text, pdf.get_string_width, val_w - PAD)

    def _box_title(x, y, title):
        pdf.set_xy(x, y)
        pdf.set_fill_color(*FILL_HEAD)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("NG", "B", 10)
        pdf.cell(bw, 7, title, fill=True)

    def _box_row(x, y, h, lab, fs, lines):
        pdf.set_xy(x, y)
        pdf.set_font("NG", "B", 9)
        pdf.set_text_color(*GRAY)
        pdf.cell(LAB_W, h, lab, border="LB")
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("NG", "", fs)
        pdf.cell(val_w, h, "", border="RB")            # 테두리
        lh = h / len(lines) if len(lines) > 1 else h
        for i, ln in enumerate(lines):
            pdf.set_xy(x + LAB_W, y + i * lh)
            pdf.cell(val_w, lh, ln)

    pdf.set_draw_color(*LINE)
    left = [
        ("상호", po_data.get("vendor_name")),
        ("사업자번호", vendor_info.get("biz_no")),
        ("대표자", vendor_info.get("ceo")),
        ("주소", vendor_info.get("address")),
        ("전화", vendor_info.get("phone")),
    ]
    right = [
        ("상호", COMPANY_INFO["name"]),
        ("사업자번호", COMPANY_INFO["biz_no"]),
        ("대표자", COMPANY_INFO["ceo"]),
        ("주소", COMPANY_INFO["address"]),
        ("전화/팩스", f"{COMPANY_INFO['phone']} / {COMPANY_INFO['fax']}"),
    ]
    xl, xr = pdf.l_margin, pdf.l_margin + W / 2 + 3
    y = pdf.get_y()
    _box_title(xl, y, "수신 (공급자)")
    _box_title(xr, y, "발주 (공급받는자)")
    y += 7
    for (ll, lv), (rl, rv) in zip(left, right):
        lf, llines = _fit(lv)
        rf, rlines = _fit(rv)
        n = max(len(llines), len(rlines))
        h = ROW_H if n == 1 else 4.4 * n + 1.4
        _box_row(xl, y, h, ll, lf, llines)
        _box_row(xr, y, h, rl, rf, rlines)
        y += h
    pdf.set_y(y + 5)

    # ── 품목 표 ── 소재 발주: 품명·재질·규격 / 소모성·공구(item_layout=unit):
    # 품명·규격·단위 — 단위는 수량 앞 (2026-09-22 사용자 요청)
    unit_layout = (po_data.get("item_layout") == "unit")
    if unit_layout:
        cols = [("NO", 10, "C"), ("품명", 68, "L"), ("규격", 32, "C"),
                ("단위", 14, "C"), ("수량", 18, "R"), ("단가", 22, "R"),
                ("금액", 26, "R")]
    else:
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
        if unit_layout:
            vals = [str(i), str(it.get("item_name") or ""), str(it.get("spec") or ""),
                    str(it.get("unit") or "EA"), _num(qty), _num(up), _num(amt)]
        else:
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
        # 지불조건은 비워 두면 공란으로 (2026-10-01 사용자 요청)
        pdf.cell(W - 24, 6.5,
                 str(val or ("" if lab == "지불조건" else "-")), border="B",
                 new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)
    # 서명란(발주자·수신 확인)은 쓰지 않아 제거 (2026-09-23 사용자 확정)
    # 바닥글 — 자동 페이지 나눔을 끄고 현재 페이지 하단에 고정
    pdf.set_auto_page_break(auto=False)
    pdf.set_font("NG", "", 8)
    pdf.set_text_color(*GRAY)
    pdf.set_y(pdf.h - 12)
    pdf.cell(W, 5, f"{COMPANY_INFO['name']} · {COMPANY_INFO['address']} · "
                   f"Tel {COMPANY_INFO['phone']} · Fax {COMPANY_INFO['fax']}",
             align="C")
    return bytes(pdf.output())
