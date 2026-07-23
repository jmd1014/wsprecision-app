# -*- coding: utf-8 -*-
"""
라벨 HTML 생성기 — Phase E 실물 연동 라벨 (입고/합격/불합격/완성 공용)

출력 방식: HTML 다운로드 → 브라우저에서 열기 → 인쇄(Ctrl+P)
- mode="label": 라벨 프린터 단표 (기본 100×70mm, @page 로 판형 지정)
- mode="a4"   : A4 한 장에 2열 배치 (예비 — 라벨 프린터 문제 시)

디자인은 기능적 최소 (큰 글씨 + 필수 정보) — 현장 피드백 후 마감 예정.
"""

_LABEL_CSS = """
@page {{ size: {page_size}; margin: {page_margin}; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'Malgun Gothic', sans-serif; color: #1c2433; }}
.label {{
  width: {w}; height: {h}; padding: 4mm 5mm;
  border: {border}; border-radius: 2mm;
  display: flex; flex-direction: column;
  page-break-after: {page_break};
  overflow: hidden; background: #fff;
}}
.hdr {{ display: flex; justify-content: space-between; align-items: center;
        border-bottom: 1.5pt solid #1F3864; padding-bottom: 1.5mm; }}
.hdr .t {{ font-size: 11pt; font-weight: 800; color: #1F3864; }}
.hdr .co {{ font-size: 8pt; color: #5a6577; }}
.big {{ font-size: 26pt; font-weight: 900; letter-spacing: 1px;
        text-align: center; padding: 2mm 0 1mm; color: #111; }}
.badge {{ text-align: center; font-size: 10pt; font-weight: 800;
          padding: 0.5mm 0 1.5mm; }}
.badge.ok {{ color: #1e7a45; }}
.badge.ng {{ color: #c0392b; }}
.badge.tk {{ color: #b26a00; }}
.rows {{ flex: 1; display: table; width: 100%; }}
.row {{ display: table-row; }}
.row .k {{ display: table-cell; font-size: 8.5pt; color: #5a6577;
           padding: 0.6mm 2mm 0.6mm 0; white-space: nowrap; width: 18mm; }}
.row .v {{ display: table-cell; font-size: 10.5pt; font-weight: 700; }}
.ft {{ border-top: 0.5pt solid #d4dbe8; padding-top: 1mm;
       font-size: 7.5pt; color: #8b94a4; display: flex;
       justify-content: space-between; }}
.a4grid {{ display: flex; flex-wrap: wrap; gap: 6mm; padding: 8mm; }}
"""

_BADGE_CLASS = {"합격": "ok", "불합격": "ng", "특채": "tk"}


def labels_html(labels: list, mode: str = "label",
                label_size_mm=(100, 70)) -> str:
    """라벨 목록 → 인쇄용 HTML.

    labels 항목: {
      "title":  라벨 종류 (예: "소재 입고", "검사 합격"),
      "big":    크게 표시할 식별자 (W번호 / LOT),
      "badge":  선택 — "합격"/"불합격"/"특채" 등 상태 강조,
      "rows":   [(라벨, 값), ...] 상세 정보,
      "footer": 선택 — 하단 좌측 소문구 (기본: 발행일),
    }
    """
    w, h = label_size_mm
    if mode == "a4":
        css = _LABEL_CSS.format(
            page_size="A4", page_margin="0",
            w=f"{w * 0.9}mm", h=f"{h * 0.9}mm",
            border="0.5pt solid #999", page_break="auto")
        open_wrap, close_wrap = '<div class="a4grid">', "</div>"
    else:
        css = _LABEL_CSS.format(
            page_size=f"{w}mm {h}mm", page_margin="0",
            w=f"{w}mm", h=f"{h}mm",
            border="none", page_break="always")
        open_wrap, close_wrap = "", ""

    cards = []
    for lb in labels:
        rows_html = "".join(
            f'<div class="row"><span class="k">{k}</span>'
            f'<span class="v">{v if v not in (None, "") else "-"}</span></div>'
            for k, v in lb.get("rows", []))
        badge = lb.get("badge")
        badge_html = (
            f'<div class="badge {_BADGE_CLASS.get(badge, "")}">'
            f'{"■ " + badge + " ■"}</div>' if badge else "")
        cards.append(f"""
<div class="label">
  <div class="hdr"><span class="t">{lb.get('title', '')}</span>
    <span class="co">우성정밀</span></div>
  <div class="big">{lb.get('big', '')}</div>
  {badge_html}
  <div class="rows">{rows_html}</div>
  <div class="ft"><span>{lb.get('footer', '')}</span>
    <span>WS-ERP</span></div>
</div>""")

    return (f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<title>라벨 출력</title><style>{css}</style></head>"
            f"<body onload='window.print()'>{open_wrap}{''.join(cards)}"
            f"{close_wrap}</body></html>")


def receipt_labels(items: list, mode: str = "label") -> str:
    """소재 입고 라벨 — 타이틀=품번 (2026-07-24 사용자 확정).
    items: [{w_lot, pn, material_name, spec, qty, po_number, vendor, date}]"""
    labels = [{
        "title": "소재 입고",
        "big": it.get("pn") or "-",
        "rows": [
            ("소재 LOT", it.get("w_lot")),
            ("재질", it.get("material_name")),
            ("사이즈", it.get("spec")),
            ("수량", f"{it.get('qty', 0):,.0f} {it.get('unit', 'EA')}"),
            ("발주번호", it.get("po_number")),
            ("거래처", it.get("vendor")),
        ],
        "footer": f"입고일 {it.get('date', '')}",
    } for it in items]
    return labels_html(labels, mode=mode)


def inspection_labels(items: list, mode: str = "label") -> str:
    """검사 판정 라벨 — 합격/불합격(재작업·폐기)/특채.
    items: [{verdict("합격"/"불합격"/"특채"), pn, wo_number, w_lot, qty,
             date, note(선택 — 재작업/폐기 등 처분)}]"""
    labels = []
    for it in items:
        rows = [
            ("작업지시", it.get("wo_number")),
            ("소재 LOT", it.get("w_lot")),
            ("수량", f"{it.get('qty', 0):,.0f} EA"),
            ("검사일", it.get("date")),
        ]
        if it.get("note"):
            rows.append(("처분", it["note"]))
        labels.append({
            "title": "검사 판정",
            "big": it.get("pn") or "-",
            "badge": it.get("verdict"),
            "rows": rows,
            "footer": f"검사일 {it.get('date', '')}",
        })
    return labels_html(labels, mode=mode)


def finished_labels(items: list, mode: str = "label") -> str:
    """완성품 라벨 — 완성 확정(합격분) 시 부착.
    items: [{pn, wo_number, w_lot, qty, date, tokusai(선택 — 특채 포함 수량)}]"""
    labels = []
    for it in items:
        rows = [
            ("수량", f"{it.get('qty', 0):,.0f} EA"),
            ("작업지시", it.get("wo_number")),
            ("소재 LOT", it.get("w_lot")),
            ("완성일", it.get("date")),
        ]
        if it.get("tokusai"):
            rows.append(("특채 포함", f"{it['tokusai']:,.0f} EA"))
        labels.append({
            "title": "완성품",
            "big": it.get("pn") or "-",
            "rows": rows,
            "footer": f"완성일 {it.get('date', '')}",
        })
    return labels_html(labels, mode=mode)


_DOC_CSS = """
@page { size: A4; margin: 15mm; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Malgun Gothic', sans-serif; color: #1c2433;
       font-size: 10.5pt; }
h1 { font-size: 18pt; color: #1F3864; text-align: center;
     letter-spacing: 6px; padding: 4mm 0 2mm;
     border-bottom: 2pt solid #1F3864; margin-bottom: 6mm; }
.meta { display: flex; justify-content: space-between;
        margin-bottom: 5mm; font-size: 10pt; }
.meta b { color: #1F3864; }
table { width: 100%; border-collapse: collapse; margin-bottom: 6mm; }
th, td { border: 0.5pt solid #5a6577; padding: 2.5mm 3mm;
         text-align: center; }
th { background: #eef1f6; color: #1F3864; font-size: 9.5pt; }
td.l { text-align: left; }
.note { border: 0.5pt solid #d4dbe8; min-height: 25mm; padding: 3mm;
        margin-bottom: 8mm; font-size: 9.5pt; color: #5a6577; }
.sign { display: flex; justify-content: flex-end; gap: 10mm;
        margin-top: 10mm; }
.sign .box { text-align: center; font-size: 9.5pt; }
.sign .line { border-bottom: 0.7pt solid #1c2433; width: 40mm;
              height: 12mm; margin-bottom: 1.5mm; }
.ft { margin-top: 12mm; text-align: center; font-size: 8.5pt;
      color: #8b94a4; }
"""


def outsource_request_html(data: dict) -> str:
    """외주 가공 의뢰서 (A4) — 외주 출고 시 실물과 함께 전달.

    data: {vendor, process, due_date, issue_date,
           items: [{pn, wo_number, w_lot, qty, note}], remark}
    """
    rows = "".join(
        f"<tr><td>{i + 1}</td><td class='l'>{it.get('pn') or '-'}</td>"
        f"<td>{it.get('wo_number') or '-'}</td>"
        f"<td>{it.get('w_lot') or '-'}</td>"
        f"<td>{it.get('qty', 0):,.0f}</td>"
        f"<td class='l'>{it.get('note') or ''}</td></tr>"
        for i, it in enumerate(data.get("items", [])))
    return f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<title>외주 가공 의뢰서</title><style>{_DOC_CSS}</style></head>
<body onload='window.print()'>
<h1>외주 가공 의뢰서</h1>
<div class="meta">
  <span>의뢰처: <b>{data.get('vendor', '-')}</b></span>
  <span>가공 공정: <b>{data.get('process', '-')}</b></span>
  <span>납기 요청일: <b>{data.get('due_date', '-')}</b></span>
  <span>발행일: {data.get('issue_date', '')}</span>
</div>
<table>
<tr><th style="width:8mm">No</th><th>품번</th><th>작업지시</th>
<th>소재 LOT</th><th style="width:22mm">수량 (EA)</th><th>비고</th></tr>
{rows}
</table>
<div class="note">특기사항: {data.get('remark') or ''}</div>
<div class="sign">
  <div class="box"><div class="line"></div>발주: 우성정밀</div>
  <div class="box"><div class="line"></div>인수: {data.get('vendor', '')}</div>
</div>
<div class="ft">우성정밀 · 부산광역시 기장군 산단4로 71 · WS-ERP</div>
</body></html>"""
