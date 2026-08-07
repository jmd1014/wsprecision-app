# -*- coding: utf-8 -*-
"""영업보고 — 확정 전표 기준 집계 + 인쇄용 리포트 HTML.

집계 원칙 (거래명세서와 동일):
- 확정(CONFIRMED) 전표의 shipment_items 스냅샷만 집계 대상
- 공급가액 = 수량 × 단가, 세액 = 공급가액의 10% (라인별 반올림)
- 단가 미입력 라인은 금액 집계에서 제외하고 건수를 따로 보여준다
  (수량 집계에는 포함 — 물량 자체는 나갔으므로)
"""

from utils.statement_generator import SUPPLIER


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return ""
    return f"{f:,.0f}"


def line_amounts(row):
    """한 라인의 (공급가액, 세액) — 단가 미입력이면 None."""
    qty = _f(row.get("qty"))
    up = row.get("unit_price")
    try:
        up = float(up) if up not in (None, "") else None
    except (TypeError, ValueError):
        up = None
    if up and up > 0:
        supply = qty * up
        return supply, float(round(supply * 0.1))
    return None


def _empty():
    return {"lines": 0, "qty": 0.0, "supply": 0.0, "vat": 0.0,
            "total": 0.0, "missing": 0, "missing_qty": 0.0}


def _acc(slot, row):
    slot["lines"] += 1
    slot["qty"] += _f(row.get("qty"))
    amt = line_amounts(row)
    if amt is None:
        slot["missing"] += 1
        slot["missing_qty"] += _f(row.get("qty"))
    else:
        slot["supply"] += amt[0]
        slot["vat"] += amt[1]
        slot["total"] = slot["supply"] + slot["vat"]


def aggregate(rows):
    """shipment_items 행 목록 → 전체/거래처별/일자별/품번별 집계.

    각 행에 customer, pn, qty, unit_price 가 있어야 하고,
    일자별 집계를 쓰려면 date(=ship_date), 전표 수 집계를 쓰려면
    ship_no 를 붙여서 넘긴다.
    """
    out = {"all": _empty(), "by_customer": {}, "by_date": {},
           "by_pn": {}, "ship_nos": set(), "customers": set()}
    for r in rows:
        cust = r.get("customer") or "-"
        out["customers"].add(cust)
        if r.get("ship_no"):
            out["ship_nos"].add(r["ship_no"])
        _acc(out["all"], r)
        _acc(out["by_customer"].setdefault(cust, _empty()), r)
        if r.get("date"):
            _acc(out["by_date"].setdefault(str(r["date"]), _empty()), r)
        _acc(out["by_pn"].setdefault((r.get("pn") or "-", cust),
                                     _empty()), r)
    return out


# ─── 인쇄용 리포트 (하우스 스타일 — 흐름 레이아웃, 표 머리글 반복) ───

_CSS = """
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'IBM Plex Sans KR',sans-serif;color:#1b2a41;
     background:#fff;font-size:12px;padding:10mm 8mm;max-width:200mm;
     margin:0 auto}
.hd{display:flex;align-items:baseline;justify-content:space-between;
    border-bottom:3px solid #24406b;padding-bottom:6px;margin-bottom:10px}
.hd .t{font-size:22px;font-weight:700;letter-spacing:6px}
.hd .meta{font-size:12px;color:#333a45;text-align:right}
.kpis{display:flex;gap:8px;margin:10px 0}
.kpis .k{flex:1;border:1px solid #c9cdd4;border-top:3px solid #24406b;
        padding:7px 9px}
.kpis .k .l{font-size:10.5px;color:#555c66}
.kpis .k .v{font-size:16px;font-weight:700;margin-top:2px}
h3{font-size:13px;margin:14px 0 5px;color:#24406b;
   border-left:4px solid #24406b;padding-left:7px}
table{border-collapse:collapse;width:100%}
th{border:1px solid #9aa1ab;background:#f4f5f7;padding:5px 6px;
   font-size:11.5px;font-weight:600;color:#333a45}
td{border:1px solid #c9cdd4;padding:4.5px 7px;font-size:12px}
.r{text-align:right}.c{text-align:center}
tr.tot td{background:#f9fafb;font-weight:700;border-color:#9aa1ab}
thead{display:table-header-group}
tr{page-break-inside:avoid}
.warn{font-size:11px;color:#d9480f;margin:5px 0}
.ft{margin-top:14px;padding-top:6px;border-top:1px solid #c9cdd4;
    display:flex;justify-content:space-between;font-size:10.5px;
    color:#9aa1ab}
@media print{ body{padding:0} .noprint{display:none} }
"""


def _doc(title, meta_html, body_html):
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{title}</title><style>{_CSS}</style></head><body>"
        f"<div class='hd'><span class='t'>{title}</span>"
        f"<span class='meta'>{meta_html}</span></div>"
        + body_html +
        f"<div class='ft'><span>{SUPPLIER['name']} · {SUPPLIER['addr']}"
        f"</span><span>Tel {SUPPLIER['tel']} · Fax {SUPPLIER['fax']}"
        "</span></div>"
        "<script>window.print&&setTimeout(()=>window.print(),300)"
        "</script></body></html>")


def _kpis(items):
    return ("<div class='kpis'>"
            + "".join(f"<div class='k'><div class='l'>{la}</div>"
                      f"<div class='v'>{va}</div></div>"
                      for la, va in items)
            + "</div>")


def _sum_table(headers, rows_html, tot_cells):
    return ("<table><thead><tr>"
            + "".join(f"<th>{h}</th>" for h in headers)
            + "</tr></thead><tbody>" + rows_html
            + "<tr class='tot'>" + tot_cells + "</tr></tbody></table>")


def _missing_note(agg):
    if agg["all"]["missing"]:
        return (f"<div class='warn'>단가 미입력 {agg['all']['missing']}건 "
                f"(수량 {_num(agg['all']['missing_qty'])}) 은 금액 집계에서 "
                "제외 — 수주 관리에서 단가를 채우면 반영됩니다</div>")
    return ""


def _by_customer_table(agg):
    rows = []
    for cust in sorted(agg["by_customer"],
                       key=lambda c: -agg["by_customer"][c]["total"]):
        s = agg["by_customer"][cust]
        rows.append(
            f"<tr><td>{cust}</td><td class='r'>{s['lines']}</td>"
            f"<td class='r'>{_num(s['qty'])}</td>"
            f"<td class='r'>{_num(s['supply'])}</td>"
            f"<td class='r'>{_num(s['vat'])}</td>"
            f"<td class='r'>{_num(s['total'])}</td></tr>")
    a = agg["all"]
    tot = ("<td class='c'>합계</td>"
           f"<td class='r'>{a['lines']}</td>"
           f"<td class='r'>{_num(a['qty'])}</td>"
           f"<td class='r'>{_num(a['supply'])}</td>"
           f"<td class='r'>{_num(a['vat'])}</td>"
           f"<td class='r'>{_num(a['total'])}</td>")
    return _sum_table(
        ["거래처", "품목수", "수량", "공급가액", "세액", "합계"],
        "".join(rows), tot)


def daily_report_html(day, rows, issued_by=""):
    """일일 출고 결산 — 거래처별 합계 + 품목 상세 (전표번호 포함).

    rows: 그날 확정 전표들의 shipment_items (ship_no 포함).
    """
    agg = aggregate(rows)
    a = agg["all"]
    detail = []
    for r in sorted(rows, key=lambda x: (x.get("ship_no") or "",
                                         x.get("customer") or "",
                                         x.get("pn") or "")):
        amt = line_amounts(r)
        name = r.get("customer_pn") or r.get("pn") or "-"
        detail.append(
            "<tr><td class='c'>{sn}</td><td>{cu}</td><td>{pn}</td>"
            "<td>{nm}</td><td class='r'>{q}</td><td class='r'>{up}</td>"
            "<td class='r'>{su}</td><td class='r'>{vt}</td></tr>".format(
                sn=r.get("ship_no") or "-", cu=r.get("customer") or "-",
                pn=r.get("pn") or "-", nm=name,
                q=_num(r.get("qty")),
                up=_num(r.get("unit_price")) if amt else "",
                su=_num(amt[0]) if amt else "",
                vt=_num(amt[1]) if amt else ""))
    tot = ("<td colspan='4' class='c'>합계</td>"
           f"<td class='r'>{_num(a['qty'])}</td><td></td>"
           f"<td class='r'>{_num(a['supply'])}</td>"
           f"<td class='r'>{_num(a['vat'])}</td>")
    body = (
        _kpis([("전표", f"{len(agg['ship_nos'])}건"),
               ("거래처", f"{len(agg['customers'])}곳"),
               ("총 수량", _num(a["qty"])),
               ("공급가액", _num(a["supply"])),
               ("세액", _num(a["vat"])),
               ("합계", _num(a["total"]))])
        + _missing_note(agg)
        + "<h3>거래처별 합계</h3>" + _by_customer_table(agg)
        + "<h3>품목 상세</h3>"
        + _sum_table(["전표", "거래처", "품번", "거래처 표기", "수량",
                      "단가", "공급가액", "세액"], "".join(detail), tot))
    meta = str(day) + (f"<br>작성 {issued_by}" if issued_by else "")
    return _doc("일일 출고 결산", meta, body)


def monthly_report_html(month, rows, issued_by=""):
    """월 마감 보고서 — 거래처별 + 일자별 + 품번별 합계.

    month: "YYYY-MM", rows: 해당 월 확정 전표 라인
    (date=ship_date, ship_no 포함).
    """
    agg = aggregate(rows)
    a = agg["all"]

    by_date = []
    date_ships = {}
    for r in rows:
        if r.get("date") and r.get("ship_no"):
            date_ships.setdefault(str(r["date"]), set()).add(r["ship_no"])
    for d in sorted(agg["by_date"]):
        s = agg["by_date"][d]
        by_date.append(
            f"<tr><td class='c'>{d}</td>"
            f"<td class='r'>{len(date_ships.get(d, set()))}</td>"
            f"<td class='r'>{_num(s['qty'])}</td>"
            f"<td class='r'>{_num(s['supply'])}</td>"
            f"<td class='r'>{_num(s['vat'])}</td>"
            f"<td class='r'>{_num(s['total'])}</td></tr>")
    dt_tot = ("<td class='c'>합계</td>"
              f"<td class='r'>{len(agg['ship_nos'])}</td>"
              f"<td class='r'>{_num(a['qty'])}</td>"
              f"<td class='r'>{_num(a['supply'])}</td>"
              f"<td class='r'>{_num(a['vat'])}</td>"
              f"<td class='r'>{_num(a['total'])}</td>")

    by_pn = []
    for (pn, cust) in sorted(agg["by_pn"],
                             key=lambda k: (-agg["by_pn"][k]["total"],
                                            -agg["by_pn"][k]["qty"])):
        s = agg["by_pn"][(pn, cust)]
        by_pn.append(
            f"<tr><td>{pn}</td><td>{cust}</td>"
            f"<td class='r'>{s['lines']}</td>"
            f"<td class='r'>{_num(s['qty'])}</td>"
            f"<td class='r'>{_num(s['total'])}</td></tr>")
    pn_tot = ("<td colspan='2' class='c'>합계</td>"
              f"<td class='r'>{a['lines']}</td>"
              f"<td class='r'>{_num(a['qty'])}</td>"
              f"<td class='r'>{_num(a['total'])}</td>")

    body = (
        _kpis([("전표", f"{len(agg['ship_nos'])}건"),
               ("출고일수", f"{len(agg['by_date'])}일"),
               ("거래처", f"{len(agg['customers'])}곳"),
               ("총 수량", _num(a["qty"])),
               ("공급가액", _num(a["supply"])),
               ("합계(VAT포함)", _num(a["total"]))])
        + _missing_note(agg)
        + "<h3>거래처별 합계</h3>" + _by_customer_table(agg)
        + "<h3>일자별 합계</h3>"
        + _sum_table(["출고일", "전표", "수량", "공급가액", "세액",
                      "합계"], "".join(by_date), dt_tot)
        + "<h3>품번별 합계 (금액순)</h3>"
        + _sum_table(["품번", "거래처", "라인", "수량", "합계(VAT포함)"],
                     "".join(by_pn), pn_tot))
    try:
        y, m = str(month).split("-")
        title_month = f"{y}년 {int(m)}월"
    except ValueError:
        title_month = str(month)
    meta = title_month + (f"<br>작성 {issued_by}" if issued_by else "")
    return _doc("월 마감 보고서", meta, body)
