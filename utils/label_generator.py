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
