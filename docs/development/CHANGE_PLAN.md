# 변경 계획서 템플릿 (AGENTS.md 3절)

L3 변경은 아래 템플릿을 채운 뒤 Reviewer 검토 → 사용자 승인 → 실행 순으로 간다. 계획서는 이 파일을 복사해 `docs/development/plans/YYYYMMDD_<주제>.md` 로 두거나, 긴급 L3-D 는 대화에 같은 항목을 적는다(AGENTS.md 긴급 예외).

---

## L3-S Structural Change Plan

| # | 항목 | 내용 |
|---|---|---|
| 1 | 문제 | 무엇이 안 되거나 위험한가 (사고 번호·날짜·화면) |
| 2 | 원인 | 코드·구조상 원인 (파일:함수) |
| 3 | 현재 구조 | 관련 테이블·뷰·RPC·쓰기 순서 |
| 4 | 제안 구조 | 바뀐 뒤 테이블·뷰·RPC·쓰기 순서, Source of Truth 변동 여부 |
| 5 | 영향 파일 | streamlit_app.py 줄 범위, utils/, db.py, tests/ |
| 6 | 영향 테이블 | 읽기/쓰기 구분, CHECK 제약·뷰·RLS |
| 7 | 기존 데이터 영향 | backfill 필요 여부, 이관 데이터(2026-08) 예외, 행 수 |
| 8 | Migration 계획 | 번호(실제 확인), 파일, apply 순서, 하위 호환 여부 |
| 9 | 배포 호환성 | Old App + New DB 동작, migration 과 main 푸시 순서·시간 |
| 10 | Rollback / Reversal | DB 되돌리기(역 migration 또는 SQL)와 코드 revert 를 따로 |
| 11 | 테스트 계획 | 전체 pytest, 추가할 AppTest, migration 호환 검증, Data Integrity 검증 쿼리 |
| 12 | 예상 위험 | 동시성, 부분 실패, 캐시 TTL, 사용 중인 화면 |
| 13 | Reviewer 결과 | Data / QA (/UX) 각 BLOCKER·HIGH 요약과 처리 |
| 14 | 사용자 승인 상태 | 승인 일시·문구, 조건부면 조건 |

---

## L3-D Production Data Correction Plan

| # | 항목 | 내용 |
|---|---|---|
| 1 | 원인 | 왜 틀어졌나 (사고 경위, 코드 원인, 날짜) |
| 2 | 대상 및 예상 영향 행 수 | 테이블별 행 수와 산출 쿼리 |
| 3 | 백업 위치 및 검증 | `G:\내 드라이브\제품관리DB\_<주제>_정정전백업_YYYYMMDD.json`, 행 수 확인 결과 |
| 4 | 정정 SQL / 방법 | 결정적(deterministic) SQL 전문, 임시 테이블 사용 시 포함 |
| 5 | 역방향 SQL / 복구 스크립트 | 스냅샷 기준 원복 방법 (삭제 행 재삽입, 역분개 행 삭제 등) |
| 6 | 정정 후 검증 쿼리 | 불변식(수주 대사, 회차 합, 재고 순합 등)과 기대값 |
| 7 | Data Reviewer 결과 | BLOCKER·HIGH 와 처리 |
| 8 | 사용자 승인 상태 | 승인 일시·문구 |

변경 이력: `master_change_log` 에 `changed_by='Claude'`, `reason='[일괄 정정 YYYY-MM-DD] …'`. 재고·전표는 전용 audit(역분개 거래, `shipment_revisions`)도 함께.

---

## 작성 예 (2026-10-08 SH-20261008-04 역반영, 긴급 L3-D)

1. 원인: 출고 확정이 12라인 반영 뒤 전표 머리글 CONFIRMED 저장만 실패 → DRAFT 로 남아 '작성중 취소'가 덮임.
2. 대상: `sales_order_items` 12, `so_delivery_schedule` 12, `shipment_allocations` 12(삭제), `inventory_transactions` 16(역분개 추가), `sales_orders` 2, `shipments` 1, `shipment_revisions` 12(추가).
3. 백업: `_출고취소복원_SH20261008-04_정정전백업_20261008.json` (7 테이블, 행 수 확인).
4. 방법: 앱의 '확정 전표 전체 취소'와 동일한 역반영 SQL(임시 테이블 `_si/_al/_li/_tx`).
5. 복구: 역분개 거래 16행 삭제, 스냅샷으로 라인·회차·충당·전표 원복.
6. 검증: 12라인 `received − presched = Σ delivered`, `pending = qty − received`, 전표별 ISSUE 순합 0, 충당 0건.
7. Reviewer: 긴급이라 생략(사후 샘플 리뷰 대상).
8. 승인: 2026-10-08 사용자 "정정은 바로 해주세요".
