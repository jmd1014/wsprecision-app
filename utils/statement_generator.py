# -*- coding: utf-8 -*-
"""출고 리스트·거래명세서 인쇄용 HTML 생성 (2a 하우스 스타일).

기존 수기 양식(TAX23 2매 카본지)을 그대로 계승:
- 공급자용(주황 강조) / 공급받는자용(초록 강조) 각 1장
- 헤더: 공급자·공급받는자 정보 / 본문: 날짜·품명·규격·수량·단가·
  공급가액·세액·비고 / 하단: 인수인 (인) + 합계
품명은 거래처 ERP 표기(customer_part_no)를 우선 사용 — 거래처가
자기 전산과 대조하기 쉽게.
"""

SUPPLIER = {
    "biz_no": "606-02-14529",
    "name": "우성정밀",
    "ceo": "김태식",
    "tel": "051-527-9963",
    "fax": "051-526-6024",
    "biz_type": "제조",
    "biz_item": "자동차부품",
    "addr": "부산시 기장군 정관읍 산단4로 71",
}

_ROWS_PER_PAGE = 14


def biz_no_fmt(v):
    s = "".join(ch for ch in str(v or "") if ch.isdigit())
    if len(s) == 10:
        return f"{s[:3]}-{s[3:5]}-{s[5:]}"
    return str(v or "")


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return ""
    return f"{f:,.0f}"


def _base_css(accent):
    return f"""
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap');
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'IBM Plex Sans KR',sans-serif;color:#1b2a41;
     background:#fff;font-size:12px}}
.page{{width:200mm;min-height:280mm;margin:0 auto;padding:10mm 8mm;
      page-break-after:always;position:relative}}
.page:last-child{{page-break-after:auto}}
.hd{{display:flex;align-items:baseline;justify-content:space-between;
    border-bottom:3px solid {accent};padding-bottom:6px;margin-bottom:8px}}
.hd .t{{font-size:24px;font-weight:700;letter-spacing:12px;color:#1b2a41}}
.hd .copy{{font-size:12px;font-weight:600;color:{accent}}}
.hd .meta{{font-size:12px;color:#333a45;text-align:right}}
table{{border-collapse:collapse;width:100%}}
.party td{{border:1px solid #c9cdd4;padding:4px 7px;font-size:11.5px}}
.party .lab{{background:#f4f5f7;color:#555c66;font-weight:600;width:52px;
            text-align:center}}
.party .side{{background:{accent}14;color:{accent};font-weight:700;
             width:26px;text-align:center;font-size:12px}}
.items{{margin-top:8px}}
.items th{{border:1px solid #9aa1ab;background:#f4f5f7;padding:5px 6px;
          font-size:11.5px;font-weight:600;color:#333a45;
          letter-spacing:.04em}}
.items td{{border:1px solid #c9cdd4;padding:4.5px 7px;font-size:12px;
          height:24px}}
.items .r{{text-align:right}}
.items .c{{text-align:center}}
.tot td{{border:1px solid #9aa1ab;background:#f9fafb;font-weight:700;
        padding:6px 7px}}
.sign{{margin-top:10px;display:flex;justify-content:space-between;
      align-items:center;font-size:12px;color:#333a45}}
.sign .stamp{{border-bottom:1px solid #9aa1ab;min-width:170px;
             display:inline-block;padding:0 6px 2px}}
.ft{{position:absolute;bottom:6mm;left:8mm;right:8mm;display:flex;
    justify-content:space-between;font-size:10.5px;color:#9aa1ab}}
@media print{{ .noprint{{display:none}} body{{font-size:12px}} }}
"""


def _party_table(customer, vendor, accent="#24406b"):
    v = vendor or {}
    s = SUPPLIER
    _sd = (f'class="side" style="background:{accent}14;color:{accent}" '
           'rowspan="4"')
    return f"""
<table class="party"><tr>
 <td {_sd}>공 급 자</td>
 <td class="lab">등록번호</td><td colspan="3">{s['biz_no']}</td>
 <td {_sd}>공급받는자</td>
 <td class="lab">등록번호</td><td colspan="3">{biz_no_fmt(v.get('business_no'))}</td>
</tr><tr>
 <td class="lab">상호</td><td>{s['name']}</td>
 <td class="lab">성명</td><td>{s['ceo']}</td>
 <td class="lab">상호</td><td>{customer}</td>
 <td class="lab">성명</td><td>{v.get('ceo_name') or ''}</td>
</tr><tr>
 <td class="lab">업태/종목</td><td>{s['biz_type']} / {s['biz_item']}</td>
 <td class="lab">전화</td><td>{s['tel']}</td>
 <td class="lab">업태/종목</td>
 <td>{(v.get('business_type') or '')} / {(v.get('business_item') or '')}</td>
 <td class="lab">전화</td><td>{v.get('phone') or ''}</td>
</tr><tr>
 <td class="lab">주소</td><td colspan="3">{s['addr']}</td>
 <td class="lab">주소</td><td colspan="3">{v.get('address') or ''}</td>
</tr></table>
"""


def _item_rows(rows):
    """행 → (표시행 html, 공급가액합, 세액합, 단가누락여부)"""
    body, sup_sum, vat_sum, missing = [], 0.0, 0.0, False
    for r in rows:
        qty = float(r.get("qty") or 0)
        up = r.get("unit_price")
        try:
            up = float(up) if up not in (None, "") else None
        except (TypeError, ValueError):
            up = None
        if up and up > 0:
            supply = qty * up
            vat = round(supply * 0.1)
            sup_sum += supply
            vat_sum += vat
            up_s, sp_s, vt_s = _num(up), _num(supply), _num(vat)
        else:
            missing = True
            up_s = sp_s = vt_s = ""
        name = r.get("customer_pn") or r.get("pn") or "-"
        if r.get("item_name"):
            name += " / " + str(r["item_name"])[:26]
        body.append(
            "<tr><td class='c'>{d}</td><td>{n}</td><td class='c'>{sp}</td>"
            "<td class='r'>{q}{u}</td><td class='r'>{up}</td>"
            "<td class='r'>{su}</td><td class='r'>{vt}</td><td>{rm}</td></tr>"
            .format(d=str(r.get("date") or "")[5:10].replace("-", "/"),
                    n=name, sp=r.get("spec") or "",
                    q=_num(qty), u=(r.get("unit") or "EA"),
                    up=up_s, su=sp_s, vt=vt_s, rm=r.get("remark") or ""))
    return body, sup_sum, vat_sum, missing


def _statement_page(customer, vendor, rows, date_s, accent, copy_label,
                    page_no, page_cnt):
    body, sup_sum, vat_sum, missing = _item_rows(rows)
    while len(body) < _ROWS_PER_PAGE:
        body.append("<tr>" + "<td>&nbsp;</td>" * 8 + "</tr>")
    note = ("<div style='font-size:10.5px;color:#d9480f;margin-top:4px'>"
            "단가 미입력 품목은 공란 — 협의 단가로 기입하세요</div>"
            if missing else "")
    return f"""
<div class="page">
 <div class="hd">
  <span class="t">거래명세서</span>
  <span class="copy">({copy_label})</span>
  <span class="meta">{date_s}<br>PAGE {page_no}/{page_cnt}</span>
 </div>
 {_party_table(customer, vendor, accent)}
 <table class="items">
  <tr><th style="width:40px">날짜</th><th>품명</th>
      <th style="width:56px">규격</th><th style="width:72px">수량</th>
      <th style="width:64px">단가</th><th style="width:84px">공급가액</th>
      <th style="width:70px">세액</th><th style="width:64px">비고</th></tr>
  {''.join(body)}
  <tr class="tot"><td colspan="3" style="text-align:center">합계</td>
   <td class="r">{_num(sum(float(r.get('qty') or 0) for r in rows))}</td>
   <td></td><td class="r">{_num(sup_sum) if sup_sum else ''}</td>
   <td class="r">{_num(vat_sum) if vat_sum else ''}</td><td></td></tr>
 </table>
 {note}
 <div class="sign">
  <span>인수인 : <span class="stamp">&nbsp;</span> (인)</span>
  <span style="font-weight:700">총액 (공급가액+세액) :
   {_num(sup_sum + vat_sum) if sup_sum else '&nbsp;&nbsp;&nbsp;'} 원</span>
 </div>
 <div class="ft"><span>{SUPPLIER['name']} · {SUPPLIER['addr']}</span>
  <span>Tel {SUPPLIER['tel']} · Fax {SUPPLIER['fax']}</span></div>
</div>
"""


def transaction_statements_html(batch, vendors_map=None):
    """거래처별 거래명세서 — 공급자용(주황)·공급받는자용(초록) 각 1장.

    batch: {"date": "YYYY-MM-DD", "rows": [{customer, customer_pn, pn,
            item_name, spec, qty, unit, unit_price, remark, date}]}
    vendors_map: {거래처명: vendors 행}
    """
    vendors_map = vendors_map or {}
    date_s = str(batch.get("date") or "")
    by_cust = {}
    for r in batch.get("rows", []):
        by_cust.setdefault(r.get("customer") or "-", []).append(r)

    pages = []
    for cust, rows in by_cust.items():
        chunks = [rows[i:i + _ROWS_PER_PAGE]
                  for i in range(0, len(rows), _ROWS_PER_PAGE)] or [[]]
        for accent, label in (("#e8590c", "공급자용"),
                              ("#2f9e44", "공급받는자용")):
            for pi, ch in enumerate(chunks, 1):
                pages.append((accent, _statement_page(
                    cust, vendors_map.get(cust), ch, date_s, accent,
                    label, pi, len(chunks))))
    # 강조색은 페이지 생성 시 이미 반영됨 (공급자용 주황 / 받는자용 초록)
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>거래명세서 {date_s}</title>"
            f"<style>{_base_css('#e8590c')}</style></head><body>"
            + "".join(p for _, p in pages)
            + "<script>window.print&&setTimeout("
              "()=>window.print(),300)</script></body></html>")


def delivery_list_html(batch):
    """내부 출고 리스트 — 상차·검수 확인용 (A4 1장, 확인란 포함)."""
    date_s = str(batch.get("date") or "")
    rows = batch.get("rows", [])
    body = []
    for i, r in enumerate(rows, 1):
        body.append(
            "<tr><td class='c'>{i}</td><td>{pn}</td><td>{cpn}</td>"
            "<td>{cu}</td><td>{so}</td><td class='r'>{q} {u}</td>"
            "<td class='c chk'></td></tr>".format(
                i=i, pn=r.get("pn") or "-",
                cpn=r.get("customer_pn") or "-",
                cu=r.get("customer") or "-",
                so=r.get("so_number") or "-",
                q=_num(r.get("qty")), u=r.get("unit") or "EA"))
    total = sum(float(r.get("qty") or 0) for r in rows)
    css = _base_css("#24406b") + """
.items .chk{width:44px}
.items td.chk{border:1px solid #9aa1ab}
"""
    return f"""<!doctype html><html><head><meta charset='utf-8'>
<title>출고 리스트 {date_s}</title><style>{css}</style></head><body>
<div class="page">
 <div class="hd"><span class="t">출고 리스트</span>
  <span class="meta">{date_s} · {len(rows)}건 · 총 {_num(total)}개</span>
 </div>
 <table class="items">
  <tr><th style="width:30px">NO</th><th>품번</th><th>거래처 표기</th>
      <th style="width:80px">거래처</th><th style="width:120px">수주번호</th>
      <th style="width:90px">수량</th><th style="width:44px">확인</th></tr>
  {''.join(body)}
 </table>
 <div class="sign"><span>출고 담당 : <span class="stamp">&nbsp;</span> (인)</span>
  <span>검수 : <span class="stamp">&nbsp;</span> (인)</span></div>
 <div class="ft"><span>{SUPPLIER['name']} 출고 관리</span>
  <span>{date_s} 발행</span></div>
</div>
<script>window.print&&setTimeout(()=>window.print(),300)</script>
</body></html>"""
