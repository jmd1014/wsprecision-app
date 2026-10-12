# AGENTS.md — WSPRECISION 개발 Governance

우성정밀 업무관리 앱(실사용자 6명이 매일 쓰는 운영 ERP/MES)에서 Claude Lead·Reviewer·외부 모델이 **같은 기준으로 일하기 위한 규칙**이다. 업무 규칙·시스템 특성·사고 기록은 `CLAUDE.md`(Domain Knowledge)에 있고 여기서는 참조만 한다. 두 문서가 안전·보안·데이터 보호에서 다르게 읽히면 **더 엄격한 쪽**을 따른다.

우선순위: 운영 데이터 보존 → 데이터 정합성 → 기존 업무 흐름 호환 → 추적 가능성 → 회귀 방지 → 유지보수성 → 신규 기능 속도.

## 1. 규칙 우선순위

1. 현재 사용자의 명시적 결정
2. 같은 주제에 대한 **최신** 사용자 확정 결정 — 문서 위치가 아니라 결정 시점·내용으로 비교. 메모리 디렉터리(`~/.claude/projects/G-------------DB/memory/`)에 날짜와 함께 적힌 결정도 같은 등급이며, 장기 규칙은 저장소(CLAUDE.md)에 옮겨 적는다
3. 이 문서의 Governance 규칙
4. CLAUDE.md 의 Domain Knowledge
5. 기존 코드 동작
6. Agent 의 추론

상충하는 사용자 결정이나 안전상 모호함은 임의로 풀지 않고 보고한다.

## 2. 역할

| 역할 | 책임 | 할 수 없는 것 |
|---|---|---|
| **Claude Lead** (메인 세션) | 요구사항 해석, 변경 등급 판정, 규칙 확인, 영향 분석, Reviewer 호출·통합, 구현, 테스트, migration ownership, 배포 게이트, 최종 보고 | 한 변경의 구현 책임자는 항상 하나 |
| **Data & Backend Reviewer** (`.claude/agents/data-reviewer.md`) | Supabase/PostgreSQL schema·migration·FK·index·RLS·transaction/RPC·재고·LOT·BOM·routing·canonical identity·data integrity·SQL 성능. L3-D 정정 SQL·대상·백업·rollback·검증 사전 검토 | 코드·DB 수정 |
| **Frontend & UX Reviewer** (`ux-reviewer.md`) | Streamlit 화면·입력 흐름·검색/필터·오류 메시지·중복 클릭·현장 동선·상태 표시·캐시로 인한 오래된 화면·위험 작업 확인 UI | 수량 정합·transaction 판단(QA/Data 영역), 코드·DB 수정 |
| **QA & Integrity Reviewer** (`qa-reviewer.md`) | 수량 계산·상태 전이·idempotency·동시성·부분 실패·회귀·LOT 추적·역반영·레거시 호환·parser 경계값 | 화면 디자인 리뷰(UX 영역), 코드·DB 수정 |
| **Independent Reviewer (Codex 등)** | diff·회귀·보안·race condition·테스트 제안·설계 취약점 — review-only | main·운영 DB 변경, Lead 와 같은 파일 동시 수정, migration 독자 생성 후 병합 |

Reviewer 도구는 **Read·Grep·Glob 만**이다. Bash 는 읽기 전용이 아니고(파일 삭제 가능), Supabase MCP SQL 은 SELECT 와 UPDATE 를 구분하지 못하므로 주지 않는다. diff·DB 조회 결과·테스트 결과는 Lead 가 호출할 때 입력으로 넘긴다. Reviewer 출력은 `BLOCKER / HIGH / MEDIUM / LOW / REQUIRED TESTS / REVIEW LIMITATIONS` 순이며, 검토하지 않은 항목을 검토 완료로 쓰지 않는다. Reviewer 를 호출하지 못하면 Lead 가 그 사실과 대체 절차를 보고하고, 필수 Reviewer 없는 L3 는 진행하지 않는다.

## 3. 변경 위험 등급

| 등급 | 예 | 절차 |
|---|---|---|
| **L1 Low** | 문구, 레이아웃, 표시 순서, 단순 검색/필터, PDF/HTML 디자인, Slack 문구, 명백한 UI 버그 | Lead 처리, 관련 테스트 |
| **L2 Business Logic** | BOM, 원가, 수주, 발주, 생산, 재고, LOT, 출고, 수량 계산, 상태 전이, parser, alias 해석, 구글시트 파싱, 기존 외부 연동 변경 | 변경 전 확인: Source of Truth·영향 파일/테이블·기존 데이터 호환·실패 시 상태·중복 실행·회귀 범위. Reviewer: 재고/LOT/수량/상태 전이 → **QA 필수**, DB query/transaction/성능 → **Data 필수**, 복잡한 화면 흐름 → **UX 필수**, 그 외 Lead 판단 |
| **L3-S Structural** | schema 변경, migration, transaction 구조, Source of Truth·identity 정책, 재고/LOT 핵심 구조, RLS/권한, 외부 자동 발송 활성화, 외부 시스템의 운영 DB 쓰기 연동 | `docs/development/CHANGE_PLAN.md` 의 L3-S 계획서 → Data + QA Reviewer → **사용자 승인** → 구현 |
| **L3-D Data Correction** | 대량 master 정정, backfill, LOT 이관, 제품/자재 재연결, 원장 수정, 과거 transaction 정정 (Agent 가 SQL 로 하는 것. 사용자가 앱 화면에서 하는 일상 등록·수정은 해당 없음) | L3-D 정정 계획서 → Data Reviewer 사전 검토 → **사용자 승인** → Lead 실행 |

**긴급 예외(L3-D):** 당일 출고·입고가 막혀 즉시 정정이 필요하면 **계획서 파일 작성만** 생략할 수 있다. 6항목(원인·대상 행 수·백업·정정 방법·되돌리기·검증)을 대화로 보고하고, **Data Reviewer 사전 검토는 원칙적으로 유지**한 뒤 승인을 받아 실행한다. Reviewer 를 실행할 수 없는 상황이면 "Data Reviewer 미검토"와 그로 인한 위험(검증 누락 가능 지점)을 보고에 명시하고 그 상태로 진행해도 되는지 **별도 승인**을 받는다. 백업 스냅샷과 변경 이력은 어떤 경우에도 생략하지 않는다. (2026-10-08 SH-20261008-04 역반영은 Reviewer 도입 전 선례 — 지금 규칙으로는 미검토 명시·별도 승인 대상)

**승인된 운영 수정(계획서 생략 가능):** 사용자가 대상과 값을 지정 · 10행 이하 · 단순 master 필드 · 재고·LOT·identity·FK·원장·Source of Truth 변경 없음 · 전후 값 기록 가능. 이 경우에도 실행 전 현재 값을 확인하고 변경 이력을 남긴다. 행 수가 적어도 재연결·재고·LOT 이면 L3-D.

## 4. 운영 데이터 안전

- 운영 DB 는 테스트 DB 가 아니다. 금지: destructive test, 승인 없는 UPDATE/DELETE, 테스트 전표 확정, **로컬 dev 서버(localhost:8501 = 운영 DB)에서 쓰기 화면 자동 조작**(CLAUDE.md 2026-09-18 사고), 불확실한 제품/자재 자동 매핑, master 자동 덮어쓰기, 무단 bulk correction.
- 확정 거래는 삭제 대신 취소·정정·역분개·append-only 이벤트로 다룬다.
- **MCP 직접 SQL:** SELECT 는 읽기 전용 점검으로 허용. INSERT/UPDATE/DELETE 는 "승인된 운영 수정" 또는 L3-D 절차로만. 실행 전 대상·예상 행 수·백업·rollback·검증 쿼리를 준비하고, 실행 후 실제 영향·정합·이력을 확인한다.
- 변경 이력: `master_change_log` 에 `changed_by='Claude'`, `reason='[일괄 정정 YYYY-MM-DD] 무엇을 왜'` (마스터 관리 › 이력 조회에서 "일괄 정정" 검색). 재고·출고처럼 전용 audit(`inventory_transactions` 역분개, `shipment_revisions`)이 있으면 그것도 함께.

## 5. 백업·복구

- 야간 백업: `scripts/backup_tables.py`, Windows 작업 스케줄러 `wsapp-backup` 매일 02:30(주 개발 PC), `G:\내 드라이브\제품관리DB\backup\YYYYMMDD\`, 30일 보존, 읽기 전용. 손대지 않는다.
- 데이터 정정 전 스냅샷: 영향 행만 `G:\내 드라이브\제품관리DB\_<주제>_정정전백업_YYYYMMDD.json` 으로 저장하고 실제 생성·읽기 가능 여부를 확인한다. JSON 만으로 복구된다고 보지 않는다 — 계획서에 **역방향 SQL 또는 복구 스크립트**를 적는다.
- `public.*_backup_MMDD` 임시 백업 테이블은 더 만들지 않는다(2026-09-17 정리).

## 6. DB·마이그레이션·배포 호환

- schema 변경은 `supabase/migrations/NNN_*.sql` + Supabase MCP `apply_migration` 으로만. 새 번호는 문서를 믿지 말고 `supabase_migrations.schema_migrations` 와 파일 목록으로 실제 확인하고, 적용 후 CLAUDE.md 번호를 갱신한다. CLAUDE.md "DB 작업 규칙"의 뷰 전체 재정의·CHECK 제약 동시 확인·새 테이블 RLS·새 뷰 security_invoker 규칙을 따른다.
- 여러 테이블에 걸친 하나의 업무 사건(출고 확정, 입고 확정, 생산 완료, 검사 판정, 재고 이동, 취소/정정)은 원자성·중복 실행·부분 실패를 검토한다. 부분 성공이 불일치를 만들면 PostgreSQL transaction/RPC 를 우선 검토한다. (2026-10-08 출고 확정: 라인 반영 뒤 머리글 저장만 실패한 사고가 실제 사례)
- **git branch 는 운영 DB 를 격리하지 않는다.** 가능하면 하위 호환 migration 을 쓰고 Old App + New DB 를 확인한다. 깨지는 migration 은 승인된 시간에 migration 적용과 main 푸시를 연속으로 한다. DB rollback 과 코드 rollback 은 따로 계획한다.

## 7. 캐시

CLAUDE.md "읽기 캐시·조회 상한"을 따른다. 앱 쓰기는 `db.py` 경로(캐시 무효화 포함)만, 직접 requests 쓰기 금지, MCP/외부 SQL 로 고친 값은 TTL(마스터 5분, 그 외 60초) 동안 이전 값으로 보일 수 있다. Reviewer 는 오래된 화면을 DB 오류로 오판하지 않는다.

## 8. 테스트

| 변경 | 필수 테스트 |
|---|---|
| 문서만 | pytest 생략 가능, 문서 구조·Agent 형식 확인 |
| L1 | 작업 중 관련 테스트, **push 전 전체 pytest** |
| L2 | 관련 테스트 + 전체 pytest |
| L3-S | 전체 pytest + 관련 회귀 + migration 호환 검증 + 필요한 Data Integrity 검증 |
| L3-D | 변경 전후 데이터 검증 필수, 코드 변경 없으면 pytest 생략 가능 |

**배포 게이트(CLAUDE.md 작업 흐름 4·5와 동일):** 코드가 바뀐 push 는 등급과 무관하게 **로컬 전체 `C:\Python311\python.exe -m pytest tests -q`(약 11분) 통과 후에만** 한다. 결과 줄(`N passed`, failed 0)을 확인한 뒤 push 하고, push 뒤 GitHub Actions `tests`(약 15분)가 같은 스위트를 다시 돌린다. 테스트 실패 상태에서는 push 금지. 기존 실패도 "원래 실패"로 넘기지 말고 baseline 과 비교해 보고한다. 테스트는 mock DB(AppTest) 라 migration 적용 자체는 검증하지 못한다.

## 9. 커밋·푸시·배포 게이트

- **main push = Streamlit Cloud 즉시 배포.** 커밋과 푸시를 구분한다.
- 푸시 전: 전체 pytest 통과(8절 배포 게이트), 필수 Reviewer 완료, BLOCKER 해결, DB 호환 확인, 변경 범위 확인.
- 푸시 후: Lead 는 Streamlit Cloud 배포 완료와 앱 기동(로그인 화면 렌더), GitHub Actions `tests` 결과를 확인한다. 로그인 뒤 화면·핵심 조회·신규 오류 확인은 **사용자가 하거나 AppTest 결과로 갈음**한다 — Lead 는 운영 계정으로 로그인하지 않는다.
- 문제 시 복구 우선: 코드는 `git revert` 후 재푸시. migration 이 섞였으면 revert 만으로 복구되지 않는다.
- 브랜치: L1 은 main 직접, L2 는 테스트·Reviewer 게이트 충족 시 main, L3 는 별도 branch 권장. 불필요한 PR 절차는 강제하지 않는다. 외부 모델이 코드를 쓰기 시작하면 branch/PR 정책을 다시 강화한다.
- 커밋 메시지는 한글 요약 + 본문에 변경 항목, 끝에 `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## 10. 무인(예약) 작업

허용: pytest, 정적 분석, 보안 스캔, 읽기 전용 integrity 쿼리, 승인된 읽기 전용 백업, 상태 보고. 금지: migration 적용, 운영 DB 쓰기, RLS 변경, master·재고 수정, 전표 확정, 승인되지 않은 외부 발송, L3 자동 실행. commit/push 가 포함되면 테스트 통과 조건과 변경 범위를 명시한다. 무인 작업은 사용자 승인 절차를 대체하지 않는다. 예약 실행은 첫 셸 명령의 권한 프롬프트에서 멈출 수 있으므로(2026-10-06·10-08 두 번 발생) 필요한 도구 승인을 미리 확보하거나 사용자가 보는 자리에서 돌린다.

## 11. 외부 연동

Slack 문구 변경 L1 · 기존 Slack 이벤트 추가 L2 · 사용자 지시가 있는 일회성 소급 발송 L2 · 구글시트 parser 변경 L2 · 실제 자동 메일 발송 활성화 L3-S · 외부 시스템의 운영 DB 쓰기 연동 L3-S. 외부 발송 전 대상·내용·중복 실행 위험을 확인한다. Secrets 는 코드·문서·로그·대화에 남기지 않는다(키 조각 표시 금지).

## 12. 충돌 규칙

한 변경의 구현자는 한 명. Reviewer 는 의견을 내고 Lead 가 하나의 안을 고른다. 같은 파일을 여러 Agent 가 따로 고친 뒤 단순 병합하지 않는다. migration, LOT, 재고, 출고 확정, identity 는 특히 단일 ownership.

## 13. Data Integrity P0/P1 (개념만)

P0 = 업무적으로 존재해서는 안 되는 상태. P1 = 업무는 되지만 검토가 필요한 상태. 단순한 장부 음수는 자동 P0 가 아니다(자재 기준재고+거래 합산 구조상 실사 전 음수가 정상일 수 있음). 구체 항목·baseline·검증 SQL 은 Phase 2 `docs/development/DATA_INTEGRITY.md` 에서 설계한다. 후보: 확정 아닌 전표에 재고 차감·회차 충당이 남은 것, 회차 납품완료 ≠ 확정 전표 충당 합(8월 이관분 제외), 수주 라인 `납품량 − 스케줄이전 ≠ 회차 완료 합`.

## 14. 중단 조건

다음이면 자동 구현을 멈추고 보고한다: 사용자 확정 규칙과 충돌, Source of Truth 불명확, 운영 데이터 손실 가능성, 예상 밖의 대량 영향, rollback 불명확, migration 호환 미확보, 새로운 테스트 회귀, 신규 P0, 승인되지 않은 외부 side effect, 필수 Reviewer 검토 불가.

## 15. 보고 형식

변경 완료 보고에는 목적, 수정 파일, DB 변경 여부, 테스트 결과(숫자), 기존 데이터 영향, 알려진 제한, 후속 작업을 적는다. L2/L3 는 회귀 가능성과 정합성 검증 결과를 명시한다. "코드가 실행된다"는 완료가 아니다.
