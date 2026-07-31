# 우성정밀 업무관리 시스템 — 디자인 핸드오프

확정 시안: `디자인 시안.dc.html`의 **2a 스타일** (정밀 라이트 × IBM Plex Sans KR).
대상: Streamlit 앱 (`streamlit_app.py`). 클로드코드에 이 문서를 그대로 전달하면 됩니다.

---

## 1. 디자인 토큰

### 색상
```
배경(페이지)      #f4f5f7
카드/표면         #ffffff
테두리(기본)      #e2e5ea
테두리(연함/행)   #eceef2, #f2f3f6
잉크(제목)        #1b2a41
잉크(본문)        #333a45 / #444b56
잉크(보조)        #7a828d
잉크(비활성)      #9aa1ab / #b6bcc4 / #aeb4bd

주색(Primary)     #24406b   ← 버튼, 활성 메뉴, 진행바, 강조 숫자
주색 링크         #3b5b8c (hover #24406b)
주색 배경(연함)   #eef2f8 (활성 메뉴), #e7f0ff (파랑 배지 배경)

경고(주황)        #e8590c / 진한 #d9480f, 배경 #fff4e6, 행 하이라이트 #fffbf7
성공(초록)        #2f9e44 (진한 #2b8a3e), 배경 #e6f7ec
주의(노랑)        #f0b429 (텍스트 #b08a1e), 배경 #fdf6e3
위험 행 배경      #fff8f6
```

### 상태 색 매핑 (status-codes.md 기준)
| 상태 | 배경 | 글자 |
|---|---|---|
| 임시저장/작성중 DRAFT | #f2f3f6 | #7a828d |
| 확정 CONFIRMED / 발송 SENT | #eef2f8 | #3b5b8c |
| 생산중 IN_PROD / 활성 | #e7f0ff | #24406b |
| 부분납 PARTIAL / 외주중 / 부분입고 | #fff4e6 | #d9480f |
| 납품완료 DELIVERED / 입고완료 | #e6f7ec | #2f9e44 |
| cost_source: BOM_FULL | #e6f7ec | #2f9e44 |
| cost_source: BOM_PARTIAL | #fdf6e3 | #b08a1e |
| cost_source: LEGACY_ONLY | #fff1e6 | #d9480f |
| cost_source: NO_DATA | 좌측 4px 보더 #d9480f | — |

배지 공통: `font-size 11.5px; font-weight 600; padding 3px 9px; border-radius 4px;`

### 타이포그래피
```
폰트: 'IBM Plex Sans KR', sans-serif  (400/500/600/700)
      모노스페이스 사용 안 함 — 숫자·코드도 산세리프 + font-weight 600

페이지 제목       22px / 700 / #1b2a41
페이지 부제       13.5px / 400 / #7a828d
KPI 숫자          27px / 700  (홈 카드) · 21~24px (보조 카드)
카드 제목         14.5px / 600
테이블 헤더       11.5px / 600 / #9aa1ab / letter-spacing .02em
테이블 본문       13px / #333a45  (키 값은 600)
사이드바 메뉴     13.5px  (활성: 600 + #24406b)
사이드바 섹션     11px / 600 / #9aa1ab / letter-spacing .06em
```

로드:
```html
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap" rel="stylesheet">
```

### 형태
```
카드 radius        6px
배지 radius        4px  ·  필터 칩 radius 15px(pill)
카드 보더          1px solid #e2e5ea (그림자 없음, 보더로 구분)
KPI 카드 강조      border-top: 3px solid <상태색>  (홈)
cost_source 카드   border-left: 4px solid <신뢰도색>
진행바             높이 5px, 배경 #eceef2, 채움 #24406b(진행)/#2f9e44(완료)/#e8590c(지연)
```

---

## 2. 레이아웃 규칙

- **사이드바** 216px 고정, 흰 배경, 우측 1px 보더. 구성: 로고 → "업무 진행"(홈·수주·생산 계획·발주/입고·공정·출고) → "관리자"(마스터·원가·생산 보고) → 하단 Supabase 연동 상태 pill.
  - 활성 항목: 배경 #eef2f8 + radius 6px + 글자 #24406b 600
  - 건수 배지: 처리 필요 = 주황 #e8590c 흰 글자, 정보성 = #eef2f8 파란 글자
- **본문** padding 28px 32px, 세로 간격 18~22px.
- 화면 공통 순서: ① 제목+부제 / 우측 주요 액션 버튼 → ② KPI/필터 칩 행 → ③ 테이블·카드.
- 주요 버튼: 배경 #24406b, 흰 글자 13px 600, padding 9px 16px, radius 6px. 보조 버튼: 흰 배경 + #d8dbe0 보더.
- 테이블: 헤더/행 모두 CSS grid, `column-gap 14px`, 행 padding 12px 16px, 행 구분 1px #f2f3f6.
- **주의 행 하이라이트**: 처리 필요한 행에만 배경 #fffbf7 (역마진 등 위험 행은 #fff8f6).
- 숫자 정렬: 수량·금액은 우측 정렬. 0/빈 값은 #b6bcc4로 톤 다운.
- 납기 임박: `07-25 (D-2)` 형식, #d9480f 600.

---

## 3. 화면별 핵심 (시안 id 참조)

- **홈 (2a)**: 5단계 KPI 카드(미납 수주→소재→생산중→외주→완성), 상단 3px 상태색 보더, 값 0인 카드는 회색 톤 다운. 아래 수주 진행/공정 진행 2컬럼 테이블.
- **수주 관리 (3a)**: 검색 + 상태 필터 칩(전체/임시저장/확정/생산중/부분납/납품완료 + 건수), Excel/PDF 업로드 보조 버튼. DRAFT 행은 전체 회색 + "파싱 결과 검토 대기".
- **공정 관리 (3b)**: 작업지시별 카드. 내부에 투입→가공→외주→검사→완성 5칸 스테퍼(진행 칸만 상태색 배경). 액션: 실적 입력/외주 이동·회수/LOT 이력. 불량 미입력 경고는 빨간 텍스트.
- **발주/입고 (3c)**: PO 테이블, 입고율 진행바, 입고 예정 D-1 강조.
- **생산 계획 (4a)**: 자재 필요량 테이블 — 부족분은 `−228 kg` 빨강 700 + 행 하이라이트 + "발주서에 담기" 버튼. BOM 미입력 경고 배너(주황 보더 카드) 하단 배치.
- **출고 관리 (4b)**: 좌측 출고 가능 재고(수주 연결 버튼) / 우측 출고 이력(명세서 PDF 링크) 1:1.4 그리드.
- **원가 확인 (4c)**: cost_source 4단계 요약 카드(좌측 보더 초록→노랑→주황→빨강), 마진 테이블(역마진 행 #fff8f6 + 하단 경고 스트립).
- **마스터 관리 (5a)**: 상단 마스터 칩(제품 834 등), 제품 테이블(조달유형·alias·BOM 연결·도면 Rev·활성/휴면), 하단 BOM 커버리지/매핑률/백업 3카드.
- **생산 보고 (5b)**: 날짜 네비 + 일보 다운로드, 작업자별 실적(입력 대기 행 표시), 주간 스택 바 차트(합격 #24406b + 불량 #f0b8a8).

---

## 3-1. 납품 스케줄 탭 (확정: 7b 회차 간트) — 최우선 구현

수주 관리 > "납품 스케줄" 탭. 데이터: `so_delivery_schedule` (seq · due_date · qty · delivered_qty).

### 뷰 토글
`주차별 물량 | 회차 간트 | 납기 입력` — **회차 간트가 기본**. 세그먼트 컨트롤: 흰 배경 + #d8dbe0 보더, 활성 칸만 #24406b/흰 글자.

### 간트 그리드
```
grid-template-columns: 250px repeat(6, 1fr) 96px;
```
- 좌측 250px 고정 열: 품번(13px 600) / 거래처 · 미납(11.5px #7a828d) / **계획률**(11px 600, 색은 임계값 규칙)
- 가운데 6열 = 주차(월요일 기준). 이번 주 헤더는 #24406b 700 + 배경 #f7f9fc, 본문 셀 배경 #fbfcfe
- 우측 96px "이후" 열 = 표시 기간 밖 회차 요약
- 열 구분선 1px #f2f3f6, 좌측 열만 #eceef2
- 하단 주 합계 행: **본문과 동일한 그리드**로 렌더 (열 정렬 필수), 배경 #f9fafb

### 회차 칩
한 셀에 회차 1개 = 칩 1개, `flex-direction:column; gap:5px`.
| 상태 | 배경 | 보더 | 좌측 보더 | radius | 날짜 글자 |
|---|---|---|---|---|---|
| 지연 (due_date < today) | #fff8f6 | 1px #f0b8a8 | 3px #d9480f | 12px | #d9480f 700 |
| 예정 | #eef2f8 | 1px #c9d6e8 | 3px #24406b | 12px | #3b5b8c 600 |
| 완료 | #f6f7f9 | 1px #e2e5ea | 3px #2f9e44 | 12px | #9aa1ab 600 |
| 단발 (회차 1개뿐) | #f6f7f9 | 1px #d8dbe0 | 3px #7a828d | **4px** | #444b56 600 |

칩 내부: `padding:4px 9px; display:flex; justify-content:space-between` — 좌측 요일+일(11px), 우측 수량(11.5px 700 #1b2a41). radius로 반복/단발을 구분하는 게 포인트.

### 계획률 (실데이터상 가장 중요한 지표)
`계획 합계 ÷ 미납` — 회차 계획이 잡힌 비율.
```
< 30%  #d9480f 700   (예: 4PDVN-02 9%, 8HFDV-VM-05 16%)
30~70% #e8590c 600
> 70%  #2f9e44 600
```

### 미계획 물량 배너 (필수)
현재 미납 343,460 중 **256,973(75%)이 납기 미협의** — 간트에 아예 나타나지 않으므로 하단 카드로 상시 노출:
> "계획이 없는 품번 39종 · 256,973개" + 상위 3품번 나열 + `미계획 품번 보기` / `납기 입력 탭으로` 버튼

### 상단 KPI 4카드 (border-top 3px)
지연 회차(#d9480f) / 이번 주 납품(#e8590c) / 다음 주(#24406b) / 전체 잔여 계획(#24406b). 부제에 회차수·품번수 병기.

### 구현 주의
- 합계 행과 본문은 **같은 grid 정의**를 공유할 것 (별도 flex로 만들면 열이 어긋남).
- 표시 기간(6주) 밖 물량은 "이후" 열로 모으고, 하단 합계의 총계는 *표시된 품번 실합계*와 *전 품목 합계*를 함께 표기.
- 준비율(완성 재고 기반)은 현재 재고 데이터가 0이라 **넣지 말 것**. 공정/재고 데이터가 쌓인 뒤 계획률 옆에 추가.
- 칩 클릭 → 수량·날짜 인라인 수정, 드래그 → 회차 이동(2차).

---

## 4. Streamlit 적용 가이드

`.streamlit/config.toml`:
```toml
[theme]
primaryColor = "#24406b"
backgroundColor = "#f4f5f7"
secondaryBackgroundColor = "#ffffff"
textColor = "#333a45"
font = "sans serif"
```

전역 CSS 주입 (앱 시작 시 1회):
```python
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap');
html, body, [class*="css"], font, div { font-family: 'IBM Plex Sans KR', sans-serif !important; }
h1 { font-size:22px !important; font-weight:700 !important; color:#1b2a41 !important; }
[data-testid="stSidebar"] { background:#ffffff; border-right:1px solid #e2e5ea; }
[data-testid="stMetric"] { background:#fff; border:1px solid #e2e5ea; border-radius:6px; padding:14px 16px; }
button[kind="primary"] { background:#24406b !important; border-radius:6px !important; }
</style>
""", unsafe_allow_html=True)
```

구현 팁:
- KPI 카드: `st.metric` 대신 `st.markdown` HTML 카드 권장 (border-top 상태색 표현).
- 상태 배지: DataFrame에 넣지 말고 `st.column_config` 또는 HTML 렌더링. `st.dataframe`을 쓰면 배지 불가 → 배지가 중요한 테이블(수주/원가)은 HTML 테이블로.
- 스테퍼(공정 관리)는 `st.columns(5)` + HTML 카드로 구성 가능.
- 이모지 아이콘(🏠📥 등)은 제거 — 시안은 텍스트+색상만으로 위계 표현.
