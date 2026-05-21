# 마이그레이션 정책 (Migration Policy)

본 문서는 우성정밀 ERP/MES Supabase 운영 환경에서 마이그레이션을 작성·적용하는 규칙을 정의한다.
모든 DB 변경은 이 정책을 따라야 한다.

---

## 1. 핵심 원칙

1. **destructive SQL 금지**
   - `DROP TABLE`, `DROP SCHEMA CASCADE`, `TRUNCATE`, `DELETE` (전체 행) 사용 금지.
   - 컬럼 삭제(`DROP COLUMN`) 도 운영에서 금지 (사용 중지 시 COMMENT 로 deprecated 표시).
   - VIEW 재정의 시 `DROP VIEW CASCADE` 는 의존성 명시 후에만.

2. **멱등(idempotent)**
   - 같은 마이그레이션을 두 번 실행해도 에러 없이 통과해야 함.
   - `CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`,
     `CREATE OR REPLACE VIEW`, `CREATE INDEX IF NOT EXISTS` 사용.

3. **자동 수정 / 자동 overwrite 금지**
   - 마이그레이션에서 기존 데이터를 임의로 변경하지 않음.
   - 데이터 변환이 필요하면 별도 검토·승인 후 일회성 스크립트로 분리.

4. **DB 변경은 migration 파일로만**
   - SQL Editor 에서 임시 SQL 실행 금지 (운영자 임시 조사 제외).
   - 모든 스키마/view 변경은 `supabase/migrations/NNN_*.sql` 파일에 기록.

5. **운영 적용은 SQL Editor 에서 수동**
   - 코드(Streamlit / app) 가 DB 스키마를 자동 적용하지 않음.
   - PR 머지 + Supabase SQL Editor 수동 RUN.

---

## 2. 파일 명명 규칙

```
supabase/migrations/NNN_<short_purpose>.sql
```

- `NNN` — 3자리 일련번호 (기존 최대 +1)
- `<short_purpose>` — snake_case 짧은 목적 (예: `cost_views`, `bom_processes_and_mapping`)
- 확장자 `.sql`

예시:
- `013_active_master_views.sql`
- `014_purchase_material_matching_ui_helpers.sql`

---

## 3. 파일 구조 (표준 헤더)

```sql
-- ════════════════════════════════════════════════════════════
-- Migration NNN: <한국어 목적>
-- ════════════════════════════════════════════════════════════
-- 배경:
--   <왜 이 변경이 필요한지>
--
-- 변경 내용:
--   1. <변경 1>
--   2. <변경 2>
--
-- 의존:
--   - 선행 마이그레이션 NNN_xxx
--   - 사용하는 컬럼/뷰
--
-- 적용 후 검증:
--   <검증 쿼리>
-- ════════════════════════════════════════════════════════════

-- (실제 SQL)
```

---

## 4. CREATE OR REPLACE VIEW 제약

PostgreSQL 의 `CREATE OR REPLACE VIEW` 는 다음 조건에서만 성공:
- 기존 컬럼 순서/이름/타입 유지
- 새 컬럼은 끝에만 추가 가능

위 조건을 위반해야 한다면:
1. `DROP VIEW IF EXISTS <view> CASCADE` (의존 view 도 함께 drop 됨)
2. `CREATE VIEW` 새로 작성
3. 의존 view 도 같은 마이그레이션 안에서 재생성

⚠️ CASCADE 사용 시 마이그레이션 본문에 영향 view 명시.

---

## 5. 적용 절차

| Step | 작업 |
|---|---|
| 1 | 백업 확인 (Supabase Dashboard → Database → Backups, 24h 이내) |
| 2 | 마이그레이션 파일 작성 (PR 또는 직접) |
| 3 | 로컬/dev 환경 검증 (가능한 경우) |
| 4 | `python -m pytest tests/` 통과 |
| 5 | Supabase SQL Editor → 에디터 비우고 → 파일 내용 붙여넣기 → RUN |
| 6 | 검증 쿼리 실행 |
| 7 | `supabase/README.md` 적용 표 갱신 |
| 8 | `docs/db-state-current.md` 갱신 |
| 9 | 슬랙 (#개발) 공지 |

---

## 6. 롤백 절차

1. 적용 직후 문제 발견 → 슬랙 즉시 공지
2. 가능하면 inverse 마이그레이션 (`ALTER TABLE ... DROP COLUMN` 등 — 운영에서는 신중)
3. 데이터 손상 시 Supabase Backups → Point-in-Time Restore
4. 사후 원인 분석 후 마이그레이션 재작성

---

## 7. 금지 사항

| 행위 | 사유 |
|---|---|
| 운영 DB 에 `_INITIAL_SETUP_ONLY_schema.sql` 실행 | `DROP TABLE CASCADE` 포함 — 전체 데이터 삭제 |
| `DELETE FROM <table>` (WHERE 없음) | 전체 행 삭제 |
| `UPDATE ... SET col = NULL` (검토 없이) | 데이터 손실 |
| 동시에 두 사람이 같은 테이블에 마이그레이션 | 충돌 |
| 마이그레이션 본문에 secrets / credentials | 노출 위험 |
| 트리거(TRIGGER) 도입 | 동작 추적 어려움 — 현재 단계 보류 |

---

## 8. View 명명 규칙

| 접미사 / 접두사 | 의미 | 예 |
|---|---|---|
| `_v` | 일반 view | `material_price_v`, `sales_order_items_v` |
| `_stats` | 통계 view | `product_stats`, `vendor_stats` |
| `active_*` | 활성 제품/자재만 | `active_products`, `active_bom_completion_v` |
| `archived_*` | 휴면만 | `archived_products` |
| `unresolved_*` | 미해결/미매칭 | `unresolved_purchase_materials` |
| `*_candidates` | 후보 (사용자 확인 대상) | `material_mapping_candidates` |
| `*_progress` | 진행률 | `purchase_material_match_progress` |
| `*_todo` | 정비 대상 | `bom_cleanup_todo_v` |

---

## 9. 보존 정책

- `sales_ledger` / `purchase_ledger` 원본 행 **영구 보존** (감사·이력).
- 노이즈/이상 거래는 컬럼 플래그 또는 별도 제외 규칙 테이블로 표현. **삭제 금지**.
- 휴면 제품은 `archived_at` 으로 표시. 행 삭제 금지.

---

## 10. 향후 작업 (이번 단계 X)

- production_log → product_id 자동 매칭 (Stage 4)
- inventory_transactions 본격 운영 (Stage 4)
- 시계열 분석 view (Phase 4)
- 이상치 자동 정제 — **이번 단계 X** (보조 진단으로만 격리)
