# DB 변경 절차 (Migration Guide)

본 문서는 우성정밀 ERP/MES (Supabase PostgreSQL) 스키마 변경 작업의 표준 절차를 정의한다.
**모든 DB 변경은 반드시 이 절차에 따라 진행한다.**

---

## 1. 원칙

1. **`supabase/_INITIAL_SETUP_ONLY_schema.sql` 은 절대 운영 DB에 직접 실행하지 않는다.**
   - 이 파일에는 `DROP TABLE CASCADE` 가 포함되어 있어 운영 데이터가 모두 삭제된다.
   - 신규 환경(DEV) 초기 구축에만 사용.
2. **모든 스키마 변경은 `supabase/migrations/NNN_*.sql` 형식의 마이그레이션 파일로 작성한다.**
3. **마이그레이션은 idempotent(재실행 가능) 해야 한다.**
   - `CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, `CREATE OR REPLACE VIEW/FUNCTION` 등 사용.
4. **DROP / TRUNCATE 는 마이그레이션에 포함하지 않는다.** (필요 시 별도 핫픽스 절차)
5. **컬럼 의미 변경(예: legacy 처리)은 `COMMENT ON COLUMN` 으로 명시한다.**

---

## 2. 표준 절차

### Step 1 — 변경 사유 정리
- 어떤 화면/기능 변경에 필요한지, 왜 필요한지 1~2줄로 기록.

### Step 2 — 백업 확인
- Supabase 대시보드 → **Database → Backups** 에서 최근 24시간 내 자동 백업 존재 확인.
- 대규모 변경 시 수동 스냅샷(Pro 플랜) 또는 `pg_dump` 로 별도 백업.

### Step 3 — 마이그레이션 파일 작성
- `supabase/migrations/` 디렉터리에 다음 형식으로 신규 파일 생성:
  ```
  NNN_<짧은_설명>.sql
  ```
  - `NNN` 은 기존 파일들의 다음 번호 (예: `007_xxx.sql`).
- 파일 상단에 주석으로 목적/적용일/관련 화면 기록.

### Step 4 — 로컬/개발 환경 검증
- 가능한 경우 별도 dev 프로젝트에서 먼저 실행.
- 실행 후 다음 점검:
  - 기존 화면들이 정상 동작 (수주 업로드 / 발주서 생성 / BOM 편집 / 재고 조회)
  - `pytest tests/ -v` 통과

### Step 5 — 운영 적용
1. Supabase 대시보드 → **SQL Editor** 진입.
2. **에디터를 비운 후** 새 마이그레이션 파일 내용을 붙여넣기.
3. `RUN` 실행.
4. 결과 확인:
   - 에러 없이 완료.
   - 영향받은 테이블의 row count 가 변경 의도와 일치.

### Step 6 — 로그 기록
- `supabase/README.md` 의 마이그레이션 표에 적용 일자/적용자 추가.
- 슬랙 (#개발) 에 적용 사실 공유.

### Step 7 — 코드 배포
- 마이그레이션을 사용하는 Python 코드 변경을 `git push`.
- Streamlit Cloud 가 자동 재배포.

---

## 3. 롤백 절차

마이그레이션이 의도와 다르게 동작했을 때:

1. **즉시 운영 사용 중단 슬랙 공지.**
2. 가능하면 inverse 마이그레이션 (예: `ALTER TABLE ... DROP COLUMN`) 으로 되돌리기.
3. 데이터 손상이 의심되면 Supabase Backups 에서 Point-in-Time Restore.
4. 사후 원인 분석 후 마이그레이션 재작성.

---

## 4. 현재까지 적용된 마이그레이션

| 번호 | 파일 | 내용 | 운영 적용 |
|------|------|------|-----------|
| 001 | `001_vendor_group.sql` | vendors.vendor_group 컬럼 추가 | ✅ |
| 002 | `002_sales_orders.sql` | sales_orders / sales_order_items / customer_part_mapping | ✅ |
| 003 | `003_inventory_transactions.sql` | inventory_transactions 트랜잭션 원장 + material_stock 뷰 | ⏳ 적용 대기 |
| 004 | `004_status_constraints.sql` | 상태 컬럼 CHECK 제약 | ⏳ 적용 대기 |
| 005 | `005_po_number_function.sql` | next_po_number / next_so_number DB 함수 | ⏳ 적용 대기 |
| 006 | `006_pending_qty_view.sql` | sales_order_items_v 뷰 (pending_qty_calc 등) | ⏳ 적용 대기 |

신규 적용 시 표 갱신할 것.
