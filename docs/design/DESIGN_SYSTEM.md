# WSPRECISION 디자인 시스템 v1 (2026-10-22)

> 저장소 위치: `docs/design/DESIGN_SYSTEM.md` (U0 에서 개발 세션이 커밋). 이 문서가 **디자인 단일 기준**이다. `docs/DESIGN_HANDOFF.md`(2026-07-23)와 `docs/design-data.json`(2026-07-30)은 토스 스타일 결정(2026-08-12) 이전 안이라 `docs/design/legacy/` 로 옮기고 "대체됨" 표기. 토큰 값은 `streamlit_app.py` 전역 CSS(30~400행)에서 그대로 옮겼다 — **문서와 CSS 가 어긋나면 CSS 를 고친다**(문서가 기준).
> 로드맵 ID: F-UI/UX. 근거: `_UIUX개선_사전분석_보고서_20261021.md`.

## 1. 원칙

- 토스 스타일(2026-08-12 사용자 확정): 테두리 없는 흰 카드 + 은은한 그림자, 회색면 보조 버튼, 파란 주 버튼, 상태는 색·배지로만(이모지 금지).
- 화면당 **주 버튼은 하나**. 위험 버튼은 빨간 글자. 확인 게이트의 [실행 확정]은 위험색.
- 직원 화면에 절차 설명 caption 을 두지 않는다. 설명은 `help` 툴팁. 성공·실패는 **flash**(다음 실행 제목 아래)로 — `st.success` 뒤 `st.rerun` 금지.
- 모든 색은 토큰(`var(--…)`)으로. CSS·파이썬·AgGrid JS 어디서든 hex 직접 쓰기 금지(AgGrid 는 `_TOSS_GRID_CSS` 한 곳에서 토큰 값을 복제).
- 숫자는 `tabular-nums`, 우측 정렬.

## 2. 토큰

### 2-1. 색 (현행 CSS 그대로)
| 토큰 | 값 | 용도 |
|---|---|---|
| `--primary` / `--primary-hov` | #3182f6 / #1b64da | 주 버튼, 활성, 진행 |
| `--link` | #1b64da | 링크, 파란 배지 글자 |
| `--bg` / `--card` | #f9fafb / #ffffff | 페이지 / 카드 |
| `--line` / `--line2` / `--line3` | #eef1f4 / #f2f4f6 / #f7f8fa | 표 선 / 구분·회색면 / 아주 연한 면 |
| `--ink` / `--body` / `--dim` / `--faint` / `--mute` | #191f28 / #333d4b / #6b7684 / #8b95a1 / #b0b8c1 | 제목 / 본문 / 보조 / 라벨 / 비활성 |
| `--warn` / `--warn-bg` | #dd6b02 / #fff3e0 | 대기·부분·주의 |
| `--warn2` | #f04452 (배경 #fdecec) | 문제·지연·위험 |
| `--good` / `--good-bg` | #01a76b / #e6f9f1 | 완료 |
| `--note` / `--note-txt` / `--note-bg` | #ffb331 / #a86e00 / #fff7e1 | 참고(노랑) |
| `--primary-bg` (= `--blue-bg`) | #e8f3ff | 진행·활성 배지 배경, 선택 강조 |
| `--shadow` | 0 1px 3px rgba(2,32,71,.05), 0 5px 14px rgba(2,32,71,.06) | 카드 |
| **추가** `--danger-bg` | #fdecec | 위험 배지·행 배경(지금은 hex 직접 사용 3곳) |
| **추가** `--focus` | 0 0 0 2px var(--primary) | 포커스 링 |

상태 색 규칙(전 화면 고정, CLAUDE.md): 문제·지연 = `--warn2` / 대기·부분 = `--warn` / 완료 = `--good` / 진행·활성 = `--primary` / 중립(작성중·취소) = 회색(`--line2` + `--faint`).

### 2-2. 타이포 (Pretendard)
| 역할 | 크기/굵기 | 색 | 비고 |
|---|---|---|---|
| 페이지 제목(h1·`st.subheader` 제목 줄) | 22 / 800 | `--ink` | letter-spacing −.4px |
| 섹션 제목(h5, `#####`) | 14.5 / 700 | `--ink` | 카드 안 첫 줄 |
| 본문 | 14 / 400 | `--body` | Streamlit 기본 |
| 라벨·보조 | 13 / 500 | `--faint` | 폼 라벨, KPI 라벨 |
| 캡션 | 12 / 500 | `--faint` | 표 보조, 배지 |
| KPI 값 | 26 / 800 (**1024px 미만 22**) | `--ink` | `tabular-nums`, 잘림 금지 |
| 사이드바 메인 / 세부 | 14 / 600 / `--body` · 13 / 500 / `--dim` → **세부 `--body` 로 상향** | | |

### 2-3. 간격·모양 (추가 토큰)
| 토큰 | 값 |
|---|---|
| `--sp-1 … --sp-6` | 4 / 8 / 12 / 16 / 24 / 32 px |
| 카드 padding | 16px 20px (KPI 18×20 유지) |
| 섹션 간격 | `--sp-5`(24) |
| radius: 카드 16 / 버튼 10 / 배지 7 / 입력 8 / 칩 20 | 지금 값 그대로(6종 → 5종, 12 는 알림·데이터프레임 전용) |
| 브레이크포인트 | **992px 하나**(`--bp` 는 CSS 변수로 못 쓰므로 주석으로 고정) |

## 3. 컴포넌트

| 컴포넌트 | 구현(현행) | 규격 | 상태 |
|---|---|---|---|
| **PageHeader** | `nav_page_head()` — 제목 줄 + (좁은 화면) 세부 segmented + flash | 제목 22/800, 세부 컨트롤은 탭 바 모양(`.st-key-nav_sc_*` 전용 CSS, 필터 컨트롤과 구분) | U1: 전용 CSS 추가 |
| **AppHeader** | `.ws-hdr`(회사명·부제·LIVE 칩) + `st.divider` | **1줄**: 회사명 + LIVE 점. 부제는 992px 미만 숨김, divider 제거 | U1 |
| **Sidebar nav** | `nav_m_*`/`nav_s_*` 버튼 | 메인 선택 = 글자 `--ink` 700 + 왼쪽 막대 없음, **세부 선택 = 연한 주색 배경 + 왼쪽 막대**(강조는 한 곳). 세부 글자 13/500 `--body`. 휴대폰도 왼쪽 정렬·간격 축소 | U1 |
| **KpiCard** | `st.metric`(CSS) / `.kpi` HTML 두 종 | `.kpi-row` 하나로 통일 권고(2단계). 1단계: `st.metric` 값 1024px 미만 22px + `overflow:visible; white-space:nowrap` 폭 보정 | U1(잘림), U3(통일) |
| **StatusBadge** | `.tt .badge .b-*` (HTML 표) + `.tt-badge` (AgGrid JS) + `_badge_class` | 높이 22, 12/600, padding 2px 10px, radius 7, 배경+글자 쌍. **정의 한 곳**(`_BADGE_CSS` 상수 → HTML 과 AgGrid 가 같은 값을 읽음) | U1 |
| **Button** | 보조(회색면) / 주(파랑) / 비활성 | **위험 3단계 추가**: key 가 `_del`·`_cancel`·`_cfm_ok` 로 끝나면 빨간 글자·투명 배경·호버 `--danger-bg`. 화면당 주 버튼 1 | U1 |
| **ConfirmGate** | `confirm_gate()` | [실행 확정] = 위험 버튼, [돌아가기] = 보조 | U1 |
| **Flash** | `nav_go(flash=)` + 제목 아래 안내 | 모든 저장·생성·취소 결과는 flash. `st.success`+`rerun` 패턴 금지 | U1b |
| **SectionCard** | `st.container(border=True)` + `#####` | padding 16/20, 제목 14.5/700, 하단에 액션 | U3 |
| **ActionBar** | (없음) | 섹션 끝 한 줄: 좌 보조·우 주 버튼, 위험은 별도 줄 | U3 |
| **EmptyState** | `toss_table` 빈 입력 → 아무것도 없음 / `toss_df` caption / `toss_grid` None | 한 줄 안내("표시할 항목이 없습니다") + 다음 행동 버튼(있으면). 세 헬퍼 동일 | U1b |
| **Stepper** | `.stepper .step` CSS 있음(공정 처리만 사용) | 발주서 작성 ①②③ 을 이 컴포넌트로(완료 체크 포함) | U3 |
| **Table** | `toss_table`(HTML, 읽기) / `toss_grid`(AgGrid, 선택) / `toss_grid_edit`(AgGrid, 편집) / `data_editor` | 행 높이 36(HTML)·42(AgGrid) 유지, 숫자 우측, 배지 열은 `badge_cols`. 첫 열 고정은 2단계 | 유지 |

## 4. 반응형

- 992px 미만: 세부 탭 바 표시(현행), 부제 숨김, KPI 값 22px, 사이드바 간격 축소.
- 1024px 미만(새로 추가): `st.columns(4)` KPI 2열로 보이게 하지 못하므로 값 축소로 대응. `st.columns(7)` 메트릭은 `.kpi-row` 로 교체(U3).

## 5. 정적 검사(테스트로 고정)

- 새 CSS 에 hex 직접 사용 금지(토큰만) — `_TOSS_GRID_CSS`·`.sb` 예외 목록.
- `.st-key-*` 셀렉터가 실제 `key=` 와 대응(기존 `test_nav_keys_match_source_branches` 방식).
- `st.success(` 다음 3줄 안에 `st.rerun(` 없음(U1b 뒤).
- 위험 버튼 key 접미 규칙(`_del`·`_cancel`·`_cfm_ok`)과 CSS 셀렉터 일치.

## 6. 변경 이력
- v1 2026-10-22: 현행 CSS 토큰 정리 + 추가 토큰 2 + 컴포넌트 표 + U1·U1b·U3 상태.
- 2026-10-26: 저장소 커밋(U0). 초안 `_DESIGN_SYSTEM_초안_v1_20261022.md` 본문 그대로, 제목의 "초안"만 제거.
