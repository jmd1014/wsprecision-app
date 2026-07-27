# -*- coding: utf-8 -*-
"""우성정밀 업무관리 시스템 — 사용 설명서 PDF 생성

실행: python docs/make_user_guide.py
출력: docs/우성정밀_업무관리_사용설명서.pdf

디자인은 앱과 동일한 2a 시안 토큰 (DESIGN_HANDOFF.md) 사용.
"""
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether,
                               PageBreak, PageTemplate, Paragraph, Spacer,
                               Table, TableStyle)

# ── 한글 폰트 (맑은 고딕) ──
_FONT_DIR = r"C:\Windows\Fonts"
pdfmetrics.registerFont(TTFont("Malgun", os.path.join(_FONT_DIR, "malgun.ttf")))
pdfmetrics.registerFont(TTFont("MalgunBd",
                               os.path.join(_FONT_DIR, "malgunbd.ttf")))
pdfmetrics.registerFontFamily("Malgun", normal="Malgun", bold="MalgunBd")

# ── 2a 시안 팔레트 ──
INK = colors.HexColor("#1b2a41")
BODY = colors.HexColor("#333a45")
DIM = colors.HexColor("#7a828d")
FAINT = colors.HexColor("#9aa1ab")
LINE = colors.HexColor("#e2e5ea")
PRIMARY = colors.HexColor("#24406b")
PRIMARY_BG = colors.HexColor("#eef2f8")
WARN = colors.HexColor("#d9480f")
WARN_BG = colors.HexColor("#fff4e6")
GOOD = colors.HexColor("#2f9e44")
GOOD_BG = colors.HexColor("#e6f7ec")

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "우성정밀_업무관리_사용설명서.pdf")

_ss = getSampleStyleSheet()


def S(name, size, leading, color=BODY, font="Malgun", **kw):
    return ParagraphStyle(name, parent=_ss["Normal"], fontName=font,
                          fontSize=size, leading=leading, textColor=color,
                          **kw)


ST = {
    "cover_t": S("cover_t", 26, 34, INK, "MalgunBd", alignment=TA_CENTER),
    "cover_s": S("cover_s", 12, 18, DIM, alignment=TA_CENTER),
    "cover_m": S("cover_m", 10, 16, FAINT, alignment=TA_CENTER),
    "h1": S("h1", 17, 24, INK, "MalgunBd", spaceBefore=2, spaceAfter=5),
    "h2": S("h2", 12.5, 18, PRIMARY, "MalgunBd", spaceBefore=9, spaceAfter=3),
    "p": S("p", 9.7, 15.2, BODY, spaceAfter=3),
    "small": S("small", 8.6, 13, DIM),
    "li": S("li", 9.7, 15.2, BODY, leftIndent=9, bulletIndent=1,
            spaceAfter=1.5),
    "cell": S("cell", 8.8, 12.6, BODY),
    "cellb": S("cellb", 8.8, 12.6, INK, "MalgunBd"),
    "cellh": S("cellh", 8.4, 11.6, FAINT, "MalgunBd"),
    "note": S("note", 9.2, 14, BODY),
    "noteb": S("noteb", 9.2, 14, INK, "MalgunBd"),
}


def h1(text, no=None):
    label = f'<font color="#24406b">{no}</font>  {text}' if no else text
    return Paragraph(label, ST["h1"])


def h2(text):
    return Paragraph(text, ST["h2"])


def p(text):
    return Paragraph(text, ST["p"])


def bullets(items, mark="•"):
    return [Paragraph(f"{mark}  {t}", ST["li"]) for t in items]


def steps(items):
    out = []
    for i, t in enumerate(items, 1):
        out.append(Paragraph(
            f'<font color="#24406b"><b>{i}.</b></font>  {t}', ST["li"]))
    return out


def table(rows, widths, header=True):
    data = []
    for r_i, row in enumerate(rows):
        cells = []
        for c_i, cell in enumerate(row):
            style = ST["cellh"] if (header and r_i == 0) else (
                ST["cellb"] if c_i == 0 else ST["cell"])
            cells.append(Paragraph(str(cell), style))
        data.append(cells)
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    cmds = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#f2f3f6")),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
    ]
    if header:
        cmds += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f4f5f7")),
                 ("LINEBELOW", (0, 0), (-1, 0), 0.6, LINE)]
    t.setStyle(TableStyle(cmds))
    return t


def callout(title, text, kind="info"):
    bg, bd = {
        "info": (PRIMARY_BG, PRIMARY),
        "warn": (WARN_BG, WARN),
        "good": (GOOD_BG, GOOD),
    }[kind]
    inner = [Paragraph(title, ST["noteb"]), Paragraph(text, ST["note"])]
    t = Table([[inner]], colWidths=[168 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("LINEBEFORE", (0, 0), (0, -1), 2.5, bd),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def flow_strip(stages):
    cells = []
    for i, s in enumerate(stages):
        cells.append(Paragraph(s, ParagraphStyle(
            "fs", fontName="MalgunBd", fontSize=8.6, leading=11.5,
            textColor=PRIMARY, alignment=TA_CENTER)))
        if i < len(stages) - 1:
            cells.append(Paragraph("›", ParagraphStyle(
                "fa", fontName="Malgun", fontSize=10, textColor=FAINT,
                alignment=TA_CENTER)))
    w = []
    for i in range(len(cells)):
        w.append(6 * mm if i % 2 else (168 - 6 * (len(stages) - 1))
                 / len(stages) * mm)
    t = Table([cells], colWidths=w)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("BACKGROUND", (0, 0), (0, 0), PRIMARY_BG),
        ("BOX", (0, 0), (0, 0), 0.5, PRIMARY),
    ] + [c for i in range(2, len(cells), 2) for c in (
        ("BACKGROUND", (i, 0), (i, 0), PRIMARY_BG),
        ("BOX", (i, 0), (i, 0), 0.5, PRIMARY))]))
    return t


# ════════════════════════════════════════════════════════
#  본문
# ════════════════════════════════════════════════════════
APP_URL = "https://wsprecision-app-oj7qsh2mkuetydseqs6pyb.streamlit.app/"
story = []

# ── 표지 ──
story += [
    Spacer(1, 52 * mm),
    Paragraph("우성정밀 업무관리 시스템", ST["cover_t"]),
    Spacer(1, 5 * mm),
    Paragraph("단계별 사용 설명서", ST["cover_s"]),
    Spacer(1, 14 * mm),
]
story.append(flow_strip(["수주", "생산 계획", "발주·입고", "공정",
                         "출고"]))
story += [
    Spacer(1, 16 * mm),
    Paragraph("수주부터 출고까지, 화면 순서대로 따라 하면 되는 실무 안내서",
              ST["cover_m"]),
    Spacer(1, 3 * mm),
    Paragraph(f"접속 주소 : {APP_URL}", ST["cover_m"]),
    Spacer(1, 3 * mm),
    Paragraph("2026년 7월 기준 · 우성정밀", ST["cover_m"]),
    PageBreak(),
]

# ── 0. 시작하기 ──
story += [
    h1("시작하기 — 화면 구조", "0"),
    p("브라우저에서 접속 주소를 열면 바로 사용할 수 있습니다. 설치는 "
      "필요 없고, 입력한 내용은 즉시 저장되어 다른 사람 화면에도 반영됩니다."),
    h2("왼쪽 메뉴는 업무 순서대로 배열되어 있습니다"),
]
story.append(table([
    ["메뉴", "언제 쓰나", "핵심 기능"],
    ["홈", "출근 직후, 수시로", "미납 수주·소재 대기·생산중·외주중·완성 "
     "재고 한눈에"],
    ["수주 관리", "고객 발주서를 받았을 때", "파일 업로드 또는 수기 입력, "
     "수주 목록 조회"],
    ["생산 계획", "무엇을 얼마나 발주할지 정할 때", "BOM 기준 자재 필요량 "
     "산출, 발주 자동 제안"],
    ["발주/입고", "소재를 주문하고 받을 때", "발주서 작성·이력, 입고 처리, "
     "입고 현황"],
    ["공정 관리", "작업지시 발행 후 ~ 완성까지", "투입 등록, 인수·외주·검사, "
     "공정 현황판"],
    ["출고 관리", "제품을 납품할 때", "납품 등록, 납품 현황"],
], [26 * mm, 52 * mm, 90 * mm]))
story += [
    Spacer(1, 4 * mm),
    p("아래쪽 <b>관리자</b> 묶음(마스터 관리 · 원가 확인 · 생산 보고)은 "
      "기준 정보와 분석용입니다. 일상 업무에서는 위쪽 여섯 개 메뉴만 "
      "순서대로 쓰면 됩니다."),
    Spacer(1, 3 * mm),
    callout("기억할 원칙 한 가지",
            "상태(생산중·외주중·완성 등)는 <b>직접 바꾸지 않습니다</b>. "
            "입고·투입·검사 같은 <b>행위를 등록하면 상태가 자동으로</b> "
            "바뀝니다. 화면에서 상태가 이상하면 그 앞 단계 등록이 "
            "빠졌는지 확인하세요.", "info"),
    PageBreak(),
]

# ── 1. 홈 ──
story += [
    h1("홈 — 오늘 무엇을 처리할지 확인", "1"),
    p("홈은 전체 진행 상황을 요약해서 보여줍니다. 숫자를 보고 어느 메뉴로 "
      "가야 할지 판단하면 됩니다."),
    h2("상단 카드 다섯 개"),
]
story.append(table([
    ["카드", "의미", "0이 아니면 할 일"],
    ["미납 수주", "아직 납품하지 않은 수량", "생산 계획에서 자재 확인"],
    ["소재 입고 대기", "발주했지만 아직 안 들어온 수량", "발주/입고 → "
     "입고 처리에서 입고"],
    ["생산중 (투입)", "작업지시 투입 후 아직 인수 안 된 수량",
     "공정 관리 → 공정 처리에서 완료 인수"],
    ["외주중", "외주 보내고 아직 안 돌아온 수량", "회수되면 외주 입고 등록"],
    ["완성 재고", "검사까지 끝나 출고 가능한 수량", "출고 관리에서 납품"],
], [30 * mm, 68 * mm, 70 * mm]))
story += [
    Spacer(1, 4 * mm),
    h2("아래 표 두 개"),
]
story += bullets([
    "<b>수주 진행 (미납 · 납기순)</b> — 납기가 급한 순서로 정렬됩니다. "
    "납기가 지난 건은 <font color='#d9480f'><b>빨간색</b></font>으로 "
    "표시되니 이것부터 처리하세요.",
    "<b>공정 진행 (작업지시)</b> — 현재 진행 중인 작업지시와 단계별 수량.",
])
story += [
    Spacer(1, 2 * mm),
    p("수주가 많아지면 거래처 선택 상자가 나타나고, 표 아래에 "
      "「외 ○○건은 수주 관리에서 검색」 안내가 붙습니다."),
    PageBreak(),
]

# ── 2. 수주 관리 ──
story += [
    h1("수주 관리 — 고객 발주 등록", "2"),
    h2("방법 A. 파일 업로드 (거래처 발주서)"),
]
story += steps([
    "<b>수주 관리 → 새 수주 입력 → 파일 업로드 자동 파싱</b> 선택",
    "엑셀 또는 PDF 파일을 올리면 양식을 자동 인식합니다 "
    "(HDX / 미진정밀 / 엠제이티).",
    "인식된 내용을 표에서 확인합니다. 같은 내용이 두 줄 있으면 "
    "중복으로 표시되고 기본 한 줄만 저장됩니다.",
    "<b>저장</b>을 누르면 등록됩니다.",
])
story += [
    Spacer(1, 3 * mm),
    h2("방법 B. 수기 입력 (전화·메일 수주)"),
]
story += steps([
    "<b>수기 입력</b> 선택 후 거래처 발주번호 · 거래처명 · 납기일 입력",
    "<b>품목 추가</b>에서 품번을 검색해 <b>목록에서 선택</b>합니다.",
    "수량 · 단가 · 품목 납기를 넣고 <b>추가</b>를 누릅니다.",
    "품목을 다 넣었으면 <b>수주 저장</b>.",
])
story += [
    Spacer(1, 3 * mm),
    callout("품번은 반드시 검색해서 선택하세요",
            "수주에는 <b>마스터에 등록된 품목만</b> 넣을 수 있습니다. "
            "직접 타이핑한 품번(오타 포함)은 재고·자재 산출과 연결되지 "
            "않기 때문입니다. 검색해도 안 나오면 바로 아래 "
            "<b>「신규 품목 등록」</b>에서 품번·재질·규격을 넣어 등록한 뒤 "
            "선택하면 됩니다.", "warn"),
    Spacer(1, 4 * mm),
    h2("수주 목록 — 다섯 가지 보기"),
]
story.append(table([
    ["보기", "무엇을 확인하나"],
    ["수주별 (헤더)", "수주 단위 진행률과 상태"],
    ["품목별", "품번 단위 수량·미납"],
    ["거래처별", "거래처별 합계와 상태 분포 (미납 / 부분 / 완납 건수)"],
    ["납기 임박순", "납기가 급한 순서 — D-day와 라인 상태"],
    ["매칭 안된 품목", "우리 품번과 연결되지 않은 라인 (업로드 수주에서 "
     "발생) — 마스터에서 품번을 연결해야 생산·출고로 넘어갑니다"],
], [34 * mm, 134 * mm]))
story += [
    Spacer(1, 3 * mm),
    p("위쪽 <b>상태 필터</b>에서 임시저장 · 확정 · 부분납 · 납품완료 · 취소를 "
      "골라 볼 수 있습니다. <b>취소한 수주는 홈과 생산 계획에서 자동으로 "
      "빠집니다.</b>"),
    PageBreak(),
]

# ── 3. 생산 계획 ──
story += [
    h1("생산 계획 — 무엇을 얼마나 발주할지", "3"),
    p("미납 수주의 BOM을 펼쳐 필요한 자재량을 자동 계산합니다. "
      "완성 재고와 소재 재고를 모두 차감한 <b>발주 필요량</b>이 결론입니다."),
    Spacer(1, 2 * mm),
    callout("계산 방식",
            "총필요량 = (미납수량 − 제품 완성 재고) × BOM 소요량<br/>"
            "<b>발주 필요량 = 총필요량 − 소재 실재고</b><br/>"
            "즉, 이미 만들어 둔 제품과 창고에 있는 소재를 먼저 쓰고 "
            "모자란 만큼만 발주합니다.", "info"),
    Spacer(1, 4 * mm),
    h2("탭 세 개"),
]
story.append(table([
    ["탭", "내용"],
    ["자재별 필요량", "자재별로 총필요량 · 소재 재고 · 재고 충당 · 발주 "
     "필요량. 부족한 행은 배경이 붉게 표시됩니다."],
    ["수주별 BOM 전개", "어느 수주 때문에 이 자재가 필요한지 역으로 확인"],
    ["발주 자동 제안", "부족 자재를 <b>공급처별로 묶어</b> 보여줍니다. "
     "「발주서 작성 화면으로」를 누르면 발주 화면에 품목이 자동으로 "
     "담깁니다."],
], [34 * mm, 134 * mm]))
story += [
    Spacer(1, 3 * mm),
    p("<b>BOM 미등록 품목</b> 경고가 보이면 마스터 관리 → BOM 편집에서 "
      "소요 자재를 등록해야 계산에 포함됩니다."),
    PageBreak(),
]

# ── 4. 발주/입고 ──
story += [
    h1("발주 / 입고 — 소재 주문과 입고", "4"),
    p("탭 네 개가 순서대로 배열되어 있습니다: "
      "<b>새 발주서 작성 → 발주 이력 → 입고 처리 → 입고 현황</b>."),
    h2("① 새 발주서 작성"),
]
story += steps([
    "거래처를 고릅니다. (생산 계획에서 넘어온 경우 자동으로 채워집니다)",
    "품번을 검색해 <b>＋</b> 버튼으로 담습니다. 검색 범위는 기본적으로 "
    "<b>그 거래처와 거래한 품번</b>으로 좁혀집니다 — 전체에서 찾으려면 "
    "「이 거래처 이력만」 체크를 해제하세요.",
    "품목 표에서 수량 · 단가를 편집합니다. 그 거래처의 최근 단가가 자동 "
    "제안됩니다.",
    "발주일 · 납기 · 담당자를 확인하고 <b>발주서 xlsx 생성</b>을 누르면 "
    "발주번호가 채번되고 엑셀 파일을 내려받을 수 있습니다.",
])
story += [
    Spacer(1, 3 * mm),
    h2("② 입고 처리 — 두 가지 경로"),
    p("<b>발주 기반 입고</b> — 입고 대기 중인 발주를 선택하고, 라인별로 "
      "자재를 한 번만 매핑한 뒤 수량을 넣고 <b>입고 처리</b>를 누릅니다. "
      "자재 매핑은 처음 한 번만 하면 다음부터 자동으로 기억합니다."),
    p("<b>직접 입고</b> — 발주 없이 들어온 소재(<b>신규 자재, 고객 "
      "사급자재</b>)를 등록합니다. 자재를 검색해 고르고 수량을 넣은 뒤, "
      "고객이 지급한 자재면 <b>「사급자재」</b>에 체크하세요."),
    Spacer(1, 2 * mm),
    callout("입고하면 자동으로 일어나는 일",
            "① 소재 LOT 번호(W번호)가 자동 채번됩니다 &nbsp;②&nbsp;"
            "재고가 늘어납니다 &nbsp;③&nbsp;<b>소재 입고 라벨</b>이 "
            "발행됩니다. 라벨을 내려받아 인쇄하고 소재에 부착한 뒤, "
            "MES에 소재를 등록할 때 라벨의 W번호를 그대로 입력하세요.",
            "good"),
    Spacer(1, 3 * mm),
    h2("③ 입고 현황 · 라벨 재발행"),
]
story += bullets([
    "발주 라인별 입고 대기 / 완료 상태와 미입고 수량",
    "소재 LOT(W번호)별 잔여 수량 — 투입 대기인지 전량 투입인지 확인",
    "<b>입고 라벨 재발행</b> — 라벨을 잃어버리거나 훼손했을 때 W번호를 "
    "골라 다시 인쇄할 수 있습니다.",
])
story += [
    Spacer(1, 3 * mm),
    callout("W번호 채번 설정 (최초 1회)",
            "입고 처리 탭 맨 아래에 있습니다. <b>현장에서 마지막으로 사용한 "
            "번호</b>를 입력해 두면 다음 입고부터 +1로 자동 채번됩니다. "
            "예를 들어 904를 등록하면 다음 입고는 W0905입니다.", "info"),
    PageBreak(),
]

# ── 5. 공정 관리 ──
story += [
    h1("공정 관리 — 투입에서 완성까지", "5"),
    p("MES는 생산 실적을 담당하고, 앱은 <b>생산 앞뒤</b>(소재 투입 · 외주 · "
      "검사 · 완성)를 담당합니다."),
    Spacer(1, 2 * mm),
]
story.append(flow_strip(["투입", "생산", "외주", "검사", "완성"]))
story += [
    Spacer(1, 4 * mm),
    h2("① 투입 등록 — 작업지시서를 발행한 직후"),
]
story += steps([
    "<b>소재 W번호</b>를 고릅니다 (잔여 수량이 있는 것만 표시됩니다).",
    "품번은 <b>자동으로 매핑</b>됩니다. 소재를 여러 제품에 쓰는 경우 후보 "
    "목록에서 고르며, 미납 수주가 있는 제품이 위에 표시됩니다.",
    "작업지시서에 적힌 <b>작업지시 NO</b>를 입력합니다 (예: 20260727-001). "
    "이 번호로 MES 실적과 자동 연결됩니다.",
    "<b>소재 투입 수량</b>을 넣으면 BOM 기준으로 <b>예상 생산 수량</b>이 "
    "자동 환산됩니다. 다르면 수정하세요.",
    "<b>투입 등록</b> — 소재 재고가 차감되고 상태가 「생산중」이 됩니다.",
])
story += [
    Spacer(1, 3 * mm),
    h2("② 공정 처리 — 작업지시를 골라 단계별로 처리"),
    p("작업지시를 선택하면 현재 단계가 스테퍼로 표시되고, <b>지금 할 수 "
      "있는 처리만</b> 선택지로 나타납니다."),
]
story.append(table([
    ["처리", "언제", "결과"],
    ["완료 인수", "MES 생산이 끝나 제품이 나왔을 때", "검사 대기로 이동 "
     "(부분 인수 가능)"],
    ["외주 출고", "열처리·도금 등 외주를 보낼 때", "<b>외주 의뢰서(A4)</b> "
     "발행 — 실물과 함께 전달"],
    ["외주 입고", "외주품이 돌아왔을 때", "검사 대기로 복귀"],
    ["검사", "검사를 마쳤을 때", "완성 / 재작업 / 폐기 / 특채 / 반품 "
     "수량을 입력 → <b>완성분은 즉시 완성 재고</b>로 잡히고 라벨 발행"],
    ["재작업 복귀", "재작업이 끝났을 때", "다시 검사 대기로 — 재검사 후 "
     "판정"],
], [26 * mm, 62 * mm, 80 * mm]))
story += [
    Spacer(1, 3 * mm),
    callout("검사에서 기억할 점",
            "<b>완성(합격)과 특채는 검사하는 순간 완성 재고가 됩니다.</b> "
            "따로 완성 확정을 누를 필요가 없습니다. "
            "<b>재작업 수량만 작업지시에 남아</b> 복귀 → 재검사로 이어지고, "
            "폐기·반품은 재고에 들어가지 않습니다.", "good"),
    Spacer(1, 3 * mm),
    h2("③ 공정 이력과 라벨 재발행"),
    p("작업지시를 고르면 화면 아래에 <b>공정 이력</b>이 시간 순서대로 "
      "표시됩니다. 그 아래 <b>라벨·의뢰서 재발행</b>에서 예전에 발행한 "
      "외주 의뢰서 · 검사 판정 라벨 · 완성 라벨을 다시 인쇄할 수 있습니다."),
    p("이미 끝난 작업지시를 보려면 <b>「종결된 작업지시 포함」</b>에 "
      "체크하세요."),
    PageBreak(),
]

# ── 6. 출고 ──
story += [
    h1("출고 관리 — 납품", "6"),
    h2("납품 등록"),
]
story += steps([
    "수주를 검색해 선택합니다.",
    "라인별로 수주 · 기납품 · 미납 · <b>완성 재고</b>가 표시됩니다.",
    "납품 수량을 입력합니다. <b>완성 재고를 넘는 수량은 입력할 수 "
    "없습니다.</b>",
    "필요하면 출고 LOT를 입력해 생산 이력과 연결합니다.",
    "<b>납품 처리</b> — 미납이 줄고 완성 재고가 차감됩니다.",
])
story += [
    Spacer(1, 3 * mm),
    callout("「재고 없음」이라고 나온다면",
            "아직 완성 처리가 안 된 것입니다. 공정 관리에서 검사까지 "
            "마치면 완성 재고가 생기고 출고할 수 있습니다.<br/>"
            "다만 시스템 도입 전에 이미 만들어 둔 재고를 출고해야 한다면 "
            "<b>「재고 없이 출고 허용」</b>에 체크하면 됩니다 "
            "(예외 처리이므로 꼭 필요할 때만).", "warn"),
    Spacer(1, 4 * mm),
    h2("납품 현황"),
    p("수주별 납품률과 진행 상황, 최근 출고 이력을 확인합니다. "
      "기본은 <b>미납만 보기</b>이며, 검색으로 특정 수주를 찾을 수 있습니다."),
    PageBreak(),
]

# ── 7. 인쇄물 ──
story += [
    h1("인쇄물 정리 — 어디서 무엇이 나오나", "7"),
    p("모든 인쇄물은 HTML 파일로 내려받아 브라우저에서 열면 인쇄 창이 "
      "자동으로 뜹니다. 라벨은 라벨 프린터용(100×70mm)이 기본이고, "
      "문제가 있을 때를 대비해 A4 배치본도 함께 제공됩니다."),
    Spacer(1, 2 * mm),
]
story.append(table([
    ["인쇄물", "발행 위치", "재발행 위치"],
    ["소재 입고 라벨", "발주/입고 → 입고 처리 (입고 직후)",
     "발주/입고 → 입고 현황"],
    ["외주 의뢰서 (A4)", "공정 관리 → 공정 처리 → 외주 출고",
     "공정 관리 → 공정 처리 → 공정 이력"],
    ["검사 판정 라벨", "공정 관리 → 공정 처리 → 검사",
     "공정 관리 → 공정 처리 → 공정 이력"],
    ["완성품 라벨", "공정 관리 → 공정 처리 → 검사 (완성분)",
     "공정 관리 → 공정 처리 → 공정 이력"],
    ["발주서 (xlsx)", "발주/입고 → 새 발주서 작성",
     "발주/입고 → 발주 이력 → 재발급"],
], [30 * mm, 72 * mm, 66 * mm]))
story += [
    Spacer(1, 5 * mm),
    h1("자주 묻는 상황", "8"),
]
story.append(table([
    ["증상", "원인과 해결"],
    ["출고에서 완성 재고가 0으로 보인다",
     "① 검사까지 끝났는지 확인 &nbsp;② 수주 품번이 마스터와 연결되어 "
     "있는지 확인 (수주 관리 → 매칭 안된 품목)"],
    ["생산 계획에 수주가 안 나온다",
     "품번이 마스터와 연결되지 않았거나, BOM이 등록되지 않은 경우입니다."],
    ["투입 등록에서 W번호가 안 보인다",
     "그 소재가 이미 전량 투입되었거나 아직 입고되지 않은 것입니다. "
     "입고 현황에서 잔여를 확인하세요. 시스템 도입 전부터 창고에 있던 "
     "재고는 W번호가 없으므로, <b>직접 입고</b>로 수량을 등록해 "
     "W번호를 부여한 뒤 투입하세요."],
    ["투입 등록의 품번 후보가 여러 개다",
     "그 소재를 쓰는 제품이 여럿인 경우입니다. <b>「← 미납 수주 있음」</b>이 "
     "붙은 품번이 위에 표시되니 대개 그것을 고르면 됩니다."],
    ["작업지시가 목록에서 사라졌다",
     "모든 수량 처리가 끝나 종결된 것입니다. 「종결된 작업지시 포함」에 "
     "체크하면 보입니다."],
    ["숫자가 방금 바꾼 값과 다르다",
     "화면 오른쪽 위 새로고침을 누르거나 브라우저를 새로고침하세요."],
    ["잘못 입력한 수주를 없애고 싶다",
     "수주 목록에서 상태를 <b>취소</b>로 바꾸면 홈·생산 계획 집계에서 "
     "제외됩니다."],
], [46 * mm, 122 * mm]))
story += [
    Spacer(1, 6 * mm),
    callout("하루 사용 흐름 요약",
            "아침에 <b>홈</b>에서 지연·대기 확인 → 새 발주서가 오면 "
            "<b>수주 관리</b> 등록 → <b>생산 계획</b>에서 부족 자재 발주 → "
            "소재가 오면 <b>입고 처리</b>(라벨 부착) → 작업지시 발행 후 "
            "<b>투입 등록</b> → 생산·외주·검사는 <b>공정 처리</b> → "
            "완성되면 <b>출고 관리</b>에서 납품.", "info"),
]


# ── 문서 빌드 (머리말/꼬리말) ──
def _decorate(canv, doc):
    canv.saveState()
    if doc.page > 1:
        canv.setFont("Malgun", 8)
        canv.setFillColor(FAINT)
        canv.drawString(21 * mm, A4[1] - 12 * mm,
                        "우성정밀 업무관리 시스템 · 사용 설명서")
        canv.drawRightString(A4[0] - 21 * mm, A4[1] - 12 * mm,
                             "2026.07")
        canv.setStrokeColor(LINE)
        canv.setLineWidth(0.5)
        canv.line(21 * mm, A4[1] - 14.5 * mm, A4[0] - 21 * mm,
                  A4[1] - 14.5 * mm)
        canv.setFont("Malgun", 8)
        canv.setFillColor(FAINT)
        canv.drawCentredString(A4[0] / 2, 12 * mm, str(doc.page))
    canv.restoreState()


doc = BaseDocTemplate(OUT, pagesize=A4,
                      leftMargin=21 * mm, rightMargin=21 * mm,
                      topMargin=20 * mm, bottomMargin=18 * mm,
                      title="우성정밀 업무관리 시스템 사용 설명서",
                      author="우성정밀")
frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height,
              id="body")
doc.addPageTemplates([PageTemplate(id="all", frames=[frame],
                                   onPage=_decorate)])
doc.build(story)
print("OK ->", OUT)
