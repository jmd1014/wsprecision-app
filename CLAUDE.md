# 우성정밀 업무관리 시스템 (wsprecision-app)

부산 우성정밀의 수주·발주·재고·생산·출고·원가를 관리하는 사내 웹앱.
**실사용자 6명이 매일 쓰는 운영 시스템**이다 — main 푸시 = 즉시 배포임을 항상 의식할 것.

## 아키텍처

- 앱: Streamlit 단일 파일 `streamlit_app.py` (~1만 줄) + `utils/`(문서 생성·파서) + `db.py`(Supabase REST 래퍼)
- DB: Supabase PostgreSQL (프로젝트 `iryhamvxpboumnrtajwb`, 서울 리전)
- 배포: Streamlit Community Cloud — **main 브랜치 푸시 시 자동 배포** (https://wsprecision.streamlit.app)
- DB 접속: **service_role 키만 사용** (RLS 우회). anon 키 경로는 전부 RLS로 차단되어 있음
- 인증: 자체 로그인 (사용자·비밀번호 해시는 DB `app_settings`에 저장)

## 이 PC 개발 환경 (주 개발 머신)

- 저장소: `C:\Users\우성 02\wsprecision-app` — **작업은 junction `C:\wsapp` 경로로** (한글 경로가 cmd/도구에서 인코딩 문제를 일으킴)
- Python: `C:\Python311\python.exe` (3.11.9, NuGet zip 설치 — 이 PC는 MSI 설치가 실패함)
- 실행: `C:\Python311\python.exe -m streamlit run streamlit_app.py` (로컬 미리보기는 `.claude/launch.json`의 "wsprecision" 구성, port 8501)
- 테스트: `C:\Python311\python.exe -m pytest tests -q` (AppTest 기반 — st.dataframe→toss_table 전환 시 관련 테스트 확인)
- 로컬 secrets: `.streamlit/secrets.toml` (커밋 금지, `auth.disabled=true`로 로그인 우회) — 키 원본은 Supabase 대시보드·Streamlit Cloud Secrets

## 작업 흐름

1. `design/...` 또는 `feat/...` 브랜치에서 작업
2. 로컬 미리보기로 화면·기능 검증 (9개 페이지 예외 없이 렌더되는지)
3. 사용자 확인 후 main 머지 → 자동 배포
4. 커밋 메시지: `feat:`/`fix:`/`design:` + 한글 요약 + 본문에 변경 항목 나열

## 디자인 시스템 (토스 스타일, 2026-08-12 확정)

- 폰트 **Pretendard** / 주색 **#3182f6** (hover #1b64da) / 배경 #f9fafb
- 카드: 테두리 없음 + radius 16px + `var(--shadow)` / 버튼: radius 10px, 보조는 회색 면 #f2f4f6
- 상태 색 규칙(전 페이지 고정): 문제=#f04452 / 대기·부분=#dd6b02 / 완료=#01a76b / 진행·활성=#3182f6
- **이모지로 상태 표시 금지** — 색·배지로만 (신호등 이모지는 2026-08-12 제거됨)
- 토큰·컴포넌트 CSS는 `streamlit_app.py` 상단 CSS 블록 한 곳에만 정의
- 읽기 전용 표에서 배지·강조가 필요하면 `toss_table()` 헬퍼 사용 (st.dataframe은 CSS 불가). 편집 표는 data_editor 유지
- 인쇄물(거래명세서·라벨·영업보고 HTML)은 **인쇄용 자체 디자인 유지** — 앱 토큰 적용 대상 아님

## 공정 라우팅·배치 (2026-08-12 확정)

- `product_routing` = 공정 '순서', BOM = 공정 '원가', `default_vendor` = PPAP 승인 업체 고정(마스터에서만 변경)
- 기본 플로우: 소재입고 → 생산 → 검사 → 완성 (외주 없음). 외주 있는 제품만 라우팅 정의
- 순차 강제: 라우팅 제품은 스텝별 출고/회수 누계 기준 — 인수 전량 통과 전 검사 잠금
- **배치(wo_batches)**: 공정을 흐르는 수량의 정체성. 배치번호 = `지시번호-가지`(예: 20260812-003-A),
  분기·합류 계보는 `batch_links`(SPLIT/MERGE). **합류는 같은 작업지시 안에서만.**
  Phase B·C 적용됨 — 공정 처리는 배치 단위(행 선택 → 위치가 액션 결정, 부분 수량=자동 분기,
  완성 LOT 번호=배치번호), 공정 관리 > LOT 추적 탭에서 소재→공정→완성→출고 계보 조회.
  배치 없는 옛 지시만 수량 풀 방식 유지. 배치 처리 영역은 파란 헤더 밴드+카드로 구분(.bt-hdr)
- 선택 UI 패턴: selectbox 대신 `st.dataframe` 행 선택(미선택 시 첫 행 기본 — AppTest 호환)

## 데이터 정합 원칙 (2026-08-19 평가로 확정 — "진실은 한 곳")

- **소재 정보의 진실 = BOM(material_id)**. 제품 마스터의 소재 텍스트(raw_material_name 등)는
  표시용이며 BOM 변경 시 자동 동기화된다(편집 잠금). 원가·투입·발주 추천은 BOM만 본다
- **수주 진행 대사 불변식**: 회차 delivered 합 = 라인 received_qty − presched_qty(스케줄 이전
  기납품, Migration 038). 출고 확정은 등록 때 지정한 회차를 우선 충당
- **품번의 진실 = product_id** (pn은 사람용 표기 — 저장 시 공백 자동 제거). 텍스트 조인 지양
- **정합 감시 = `data_quality_v`** → 마스터 관리 > 정합 점검 탭. 전 항목 0건 유지가 목표.
  새 규칙을 만들면 검사도 이 뷰에 추가할 것
- 상태값은 코드화: active '1'/'0', 조달 '도급'/'사급'

## DB 작업 규칙

- 스키마 변경은 Supabase MCP `apply_migration`으로 (이력 유지). 2026-08-12 기준 마이그레이션 035까지
- **새 테이블은 반드시 `ENABLE ROW LEVEL SECURITY`**, **새 뷰는 `WITH (security_invoker = true)`** — 정책은 만들지 않음 (anon 차단이 목적, 앱은 service_role)
- 파괴적 변경 전 백업 테이블(`*_backup_MMDD`) 생성 관례 유지
