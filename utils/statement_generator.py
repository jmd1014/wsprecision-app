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

# 회사 로고(가로형, 바탕 투명) — assets/logo_h.png 를 data URI 로 임베드해
# HTML 한 파일로 인쇄·보관 가능 (2026-09-23 사용자 요청: 거래명세서에 로고)
_LOGO_PATH = __import__("os").path.join(
    __import__("os").path.dirname(__import__("os").path.dirname(
        __import__("os").path.abspath(__file__))), "assets", "logo_h.png")
_LOGO_URI = None


def logo_data_uri():
    global _LOGO_URI
    if _LOGO_URI is None:
        try:
            import base64
            with open(_LOGO_PATH, "rb") as f:
                _LOGO_URI = ("data:image/png;base64,"
                             + base64.b64encode(f.read()).decode())
        except Exception:
            _LOGO_URI = ""
    return _LOGO_URI


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
/* 머리 3분할: 로고(좌) · 제목+사본표기(중앙) · 날짜/페이지(우) — 제목은
   가운데, 로고는 붙지 않게 (2026-09-23 사용자 요청) */
.hd{{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;
    border-bottom:3px solid {accent};padding-bottom:8px;margin-bottom:8px}}
.hd .tl{{justify-self:start}}
.hd .logo{{height:16px;width:auto;display:block;opacity:.95}}
.hd .tc{{text-align:center;display:flex;flex-direction:column;
        align-items:center;gap:2px}}
.hd .t{{font-size:24px;font-weight:700;letter-spacing:12px;color:#1b2a41;
       padding-left:12px}}   /* letter-spacing 끝 여백 보정 → 시각적 중앙 */
.hd .copy{{font-size:11.5px;font-weight:600;color:{accent}}}
.hd .meta{{font-size:12px;color:#333a45;text-align:right;justify-self:end}}
table{{border-collapse:collapse;width:100%}}
/* 공급자·공급받는자 두 블록을 같은 폭으로 — colgroup 고정 (2026-09-23:
   두 사본의 비율이 달라 보이던 문제). 값은 칸 안에서 자연스럽게 줄바꿈 */
.party{{table-layout:fixed}}
.party td{{border:1px solid #c9cdd4;padding:4px 5px;font-size:11.5px;
          vertical-align:middle;word-break:keep-all;overflow-wrap:anywhere;
          line-height:1.35}}
.party td.tel{{white-space:nowrap;letter-spacing:-.01em}}
.party .lab{{background:#f4f5f7;color:#555c66;font-weight:600;
            text-align:center;white-space:nowrap;font-size:11px}}
.party .side{{background:{accent}14;color:{accent};font-weight:700;
             text-align:center;font-size:12px;line-height:1.3}}
.items{{margin-top:8px;table-layout:fixed}}
.items th{{border:1px solid #9aa1ab;background:#f4f5f7;padding:5px 4px;
          font-size:11px;font-weight:600;color:#333a45;
          letter-spacing:.02em;white-space:nowrap}}
.items td{{border:1px solid #c9cdd4;padding:4px 4px;font-size:11.5px;
          height:24px;overflow:hidden;white-space:nowrap;
          text-overflow:ellipsis}}
.items td.pn{{font-weight:600;font-family:'IBM Plex Sans KR',sans-serif}}
.items td.nm{{font-size:10.5px;color:#333a45}}
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
           'rowspan="5"')
    # 좌우 대칭 colgroup: 구분 24 · 라벨 46 · 값 · 라벨 34 · 값 (한쪽 50%)
    cols = ("<colgroup>"
            "<col style='width:22px'><col style='width:46px'><col>"
            "<col style='width:34px'><col style='width:14%'>"
            "<col style='width:22px'><col style='width:46px'><col>"
            "<col style='width:34px'><col style='width:14%'></colgroup>")
    return f"""
<table class="party">{cols}<tr>
 <td {_sd}>공<br>급<br>자</td>
 <td class="lab">등록번호</td><td colspan="3">{s['biz_no']}</td>
 <td {_sd}>공급<br>받는<br>자</td>
 <td class="lab">등록번호</td><td colspan="3">{biz_no_fmt(v.get('business_no'))}</td>
</tr><tr>
 <td class="lab">상호</td><td>{s['name']}</td>
 <td class="lab">성명</td><td>{s['ceo']}</td>
 <td class="lab">상호</td><td>{customer}</td>
 <td class="lab">성명</td><td>{v.get('ceo_name') or ''}</td>
</tr><tr>
 <td class="lab">업태</td><td>{s['biz_type']}</td>
 <td class="lab">종목</td><td>{s['biz_item']}</td>
 <td class="lab">업태</td><td>{v.get('business_type') or ''}</td>
 <td class="lab">종목</td><td>{v.get('business_item') or ''}</td>
</tr><tr>
 <td class="lab">전화</td><td class="tel">{s['tel']}</td>
 <td class="lab">팩스</td><td class="tel">{s['fax']}</td>
 <td class="lab">전화</td><td class="tel">{v.get('phone') or ''}</td>
 <td class="lab">팩스</td><td class="tel">{v.get('fax') or ''}</td>
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
        # 품번(거래처 ERP 표기 우선)과 품명은 별도 열 (2026-09-23 사용자 요청)
        pn = r.get("customer_pn") or r.get("pn") or "-"
        nm = str(r.get("item_name") or "")
        body.append(
            "<tr><td class='c'>{d}</td><td class='pn' title='{pn}'>{pn}</td>"
            "<td class='nm' title='{nm}'>{nm}</td><td class='c'>{sp}</td>"
            "<td class='r'>{q}{u}</td><td class='r'>{up}</td>"
            "<td class='r'>{su}</td><td class='r'>{vt}</td><td>{rm}</td></tr>"
            .format(d=str(r.get("date") or "")[5:10].replace("-", "/"),
                    pn=pn, nm=nm, sp=r.get("spec") or "",
                    q=_num(qty), u=(r.get("unit") or "EA"),
                    up=up_s, su=sp_s, vt=vt_s, rm=r.get("remark") or ""))
    return body, sup_sum, vat_sum, missing


def _statement_page(customer, vendor, rows, date_s, accent, copy_label,
                    page_no, page_cnt):
    body, sup_sum, vat_sum, missing = _item_rows(rows)
    while len(body) < _ROWS_PER_PAGE:
        body.append("<tr>" + "<td>&nbsp;</td>" * 9 + "</tr>")
    note = ("<div style='font-size:10.5px;color:#d9480f;margin-top:4px'>"
            "단가 미입력 품목은 공란 — 협의 단가로 기입하세요</div>"
            if missing else "")
    return f"""
<div class="page">
 <div class="hd">
  <span class="tl">{('<img class="logo" src="' + logo_data_uri() + '" alt="우성정밀">')
                    if logo_data_uri() else ''}</span>
  <span class="tc"><span class="t">거래명세서</span>
   <span class="copy">({copy_label})</span></span>
  <span class="meta">{date_s}<br>PAGE {page_no}/{page_cnt}</span>
 </div>
 {_party_table(customer, vendor, accent)}
 <table class="items">
  <colgroup><col style="width:46px"><col style="width:130px"><col>
   <col style="width:44px"><col style="width:62px"><col style="width:56px">
   <col style="width:80px"><col style="width:76px"><col style="width:54px">
  </colgroup>
  <tr><th>월/일</th><th>품번</th><th>품명</th><th>규격</th><th>수량</th>
      <th>단가</th><th>공급가액</th><th>세액</th><th>비고</th></tr>
  {''.join(body)}
  <tr class="tot"><td colspan="4" style="text-align:center">합계</td>
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


def transaction_statements_html(batch, vendors_map=None, rev_label=None):
    """거래처별 거래명세서 — 공급자용(주황)·공급받는자용(초록) 각 1장.

    batch: {"date": "YYYY-MM-DD", "rows": [{customer, customer_pn, pn,
            item_name, spec, qty, unit, unit_price, remark, date}]}
    vendors_map: {거래처명: vendors 행}
    rev_label: 확정 후 정정된 전표의 재발행 표기 (예: '정정본 v2 · 2026-09-04')
        — 파기되지 않은 옛 출력물과 구분하기 위해 사본 라벨 옆에 찍는다
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
        # 앱 전체 톤에 맞춰 블루 계열 — 공급자용 남색, 공급받는자용 파랑
        # (2026-09-23 사용자 요청; 이전 주황/초록)
        for accent, label in (("#24406b", "공급자용"),
                              ("#1b64da", "공급받는자용")):
            for pi, ch in enumerate(chunks, 1):
                pages.append((accent, _statement_page(
                    cust, vendors_map.get(cust), ch, date_s, accent,
                    label + (f" · {rev_label}" if rev_label else ""),
                    pi, len(chunks))))
    # 강조색은 페이지 생성 시 이미 반영됨 (공급자용 주황 / 받는자용 초록)
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>거래명세서 {date_s}</title>"
            f"<style>{_base_css('#24406b')}</style></head><body>"
            + "".join(p for _, p in pages)
            + "<script>window.print&&setTimeout("
              "()=>window.print(),300)</script></body></html>")


def delivery_list_html(batch, draft=False, rev_label=None):
    """내부 출고 리스트 — 상차·검수 확인용 (A4, 확인란 포함).

    사내 품번 기준으로 준비하므로 거래처 표기·수주번호는 싣지 않고
    품번 옆에 품명(유사 품번 착오 방지)과 LOT(W번호)를 보여준다.
    행 키: pn, disp_name(또는 item_name), lots, customer, qty, unit.

    draft=True: 출고 처리 전 '현장 확인용' — 수량 정정 기입란을 두어
    현장에서 고친 수량을 앱에 반영한 뒤 확정 처리하도록 한다.
    LOT 는 완성 재고 FIFO 예정 배분.
    """
    date_s = str(batch.get("date") or "")
    rows = batch.get("rows", [])
    title = "출고 리스트" + (" (현장 확인용)" if draft else "")
    extra_th = ('<th style="width:64px">정정 수량</th>' if draft else "")
    body = []
    for i, r in enumerate(rows, 1):
        # 품번이 식별의 최우선 — 절대 잘리지 않게, 품명은 보조 (2026-09-23)
        body.append(
            "<tr><td class='c'>{i}</td><td class='pn'>{pn}</td>"
            "<td class='nm'>{nm}</td>"
            "<td>{lot}</td><td>{cu}</td><td class='r'>{q} {u}</td>"
            "{ex}<td class='c chk'></td></tr>".format(
                i=i, pn=r.get("pn") or "-",
                nm=str(r.get("disp_name") or r.get("item_name")
                       or "-")[:24],
                lot=r.get("lots") or "-",
                cu=r.get("customer") or "-",
                q=_num(r.get("qty")), u=r.get("unit") or "EA",
                ex=("<td class='chk'></td>" if draft else "")))
    total = sum(float(r.get("qty") or 0) for r in rows)
    accent = "#e8590c" if draft else "#24406b"
    css = _base_css(accent) + """
.items .chk{width:44px}
.items td.chk{border:1px solid #9aa1ab}
.items td.pn{font-size:12.5px;font-weight:700;white-space:nowrap;overflow:visible}
.items td.nm{font-size:10px;color:#555c66}
"""
    note = ("<div style='font-size:11px;color:#d9480f;margin-top:5px'>"
            "확인용 — 아직 출고 처리 전입니다. 수량이 달라지면 정정 "
            "수량에 적고, 앱에서 고친 뒤 출고 처리하세요. LOT 는 "
            "완성 재고 잔량의 예정 배분(FIFO)이니 실물 LOT 와 다르면 "
            "함께 표시하세요.</div>"
            if draft else "")
    return f"""<!doctype html><html><head><meta charset='utf-8'>
<title>{title} {date_s}</title><style>{css}</style></head><body>
<div class="page">
 <div class="hd"><span class="t">출고 리스트</span>
  <span class="copy">{'(현장 확인용)' if draft
                      else f'(확정 · {rev_label})' if rev_label
                      else '(확정)'}</span>
  <span class="meta">{date_s} · {len(rows)}건 · 총 {_num(total)}개</span>
 </div>
 <table class="items">
  <colgroup><col style="width:30px"><col style="width:190px"><col>
   <col style="width:104px"><col style="width:72px"><col style="width:80px">
   {'<col style="width:64px">' if draft else ''}<col style="width:44px">
  </colgroup>
  <tr><th>NO</th><th>품번</th><th>품명</th><th>LOT</th><th>거래처</th>
      <th>수량</th>{extra_th}<th>확인</th></tr>
  {''.join(body)}
 </table>
 {note}
 <div class="sign"><span>출고 담당 : <span class="stamp">&nbsp;</span> (인)</span>
  <span>검수 : <span class="stamp">&nbsp;</span> (인)</span></div>
 <div class="ft"><span>{SUPPLIER['name']} 출고 관리</span>
  <span>{date_s} 발행</span></div>
</div>
<script>window.print&&setTimeout(()=>window.print(),300)</script>
</body></html>"""
