# Supabase DB 운영 가이드

## ⚠️ 가장 중요 — 운영 중 절대 실행 금지 파일

### `_INITIAL_SETUP_ONLY_schema.sql`
- **최초 1회 빈 프로젝트에 적용한 파일**
- `DROP TABLE ... CASCADE` + `CREATE TABLE` 패턴이라 **운영 중 실행하면 모든 데이터 삭제**
- 이름 앞에 `_INITIAL_SETUP_ONLY_`를 붙여 시각적으로 격리
- 새 환경에 1번만 적용 → 그 이후로는 절대 열지 않을 것

### 운영 중 DB 변경은 반드시 `migrations/` 폴더의 파일로

```
migrations/
├── 001_vendor_group.sql
├── 002_sales_orders.sql
├── 003_inventory_transactions.sql
├── 004_status_constraints.sql
├── 005_po_number_function.sql
├── 006_pending_qty_view.sql
├── 007_bom_processes_and_mapping.sql
├── 008_cost_views.sql
├── 009_cost_view_refactor.sql
├── 010_bom_process_price.sql
├── 011_sales_stats_recent_avg.sql
└── ...
```

모든 migration은 다음 원칙을 따름:
1. **멱등 (idempotent)** — 두 번 실행해도 안전 (`IF NOT EXISTS`, `OR REPLACE`)
2. **비파괴 (non-destructive)** — DROP TABLE 사용 금지
3. **순서 보장** — 파일명 앞 번호로 적용 순서 명확
4. **기존 데이터 보존** — ALTER TABLE ADD COLUMN 우선

---

## DB 변경 절차

상세 절차는 [/docs/db-migration-guide.md](../docs/db-migration-guide.md) 참고.

### 요약

1. 백업 (Supabase Dashboard → Database → Backups)
2. 새 migration 파일을 `supabase/migrations/NNN_xxx.sql`로 작성
3. Supabase SQL Editor에서 해당 파일 내용 실행
4. 결과 검증 (Table Editor, 쿼리)
5. `docs/db-migration-guide.md`의 적용 로그에 기록

---

## 현재 마이그레이션 적용 현황

| # | 파일 | 적용 일자 | 비고 |
|---|---|---|---|
| 001 | vendor_group.sql | 2026-05-07 | vendors에 vendor_group 컬럼 추가 |
| 002 | sales_orders.sql | 2026-05-08 | sales_orders / sales_order_items / customer_part_mapping |
| 003 | inventory_transactions.sql | 2026-05-13 | 재고 거래 이력 + material_stock view |
| 004 | status_constraints.sql | 2026-05-13 | CHECK 제약 |
| 005 | po_number_function.sql | 2026-05-13 | 동시성 안전 채번 함수 |
| 006 | pending_qty_view.sql | 2026-05-13 | pending_qty view 계산 |
| 007 | bom_processes_and_mapping.sql | (미적용) | BOM 공정행 + 매입/생산 매핑 컬럼 |
| 008 | cost_views.sql | (미적용) | material_price_v / product_cost_full_v 등 |
| 009 | cost_view_refactor.sql | (미적용) | BOM=수량 / 가격=원가·매입 분리. 호환 alias 추가 |
| 010 | bom_process_price.sql | (미적용) | 공정행 unit_price (LOT 단가) 우선 활용 |
| 011 | sales_stats_recent_avg.sql | (미적용) | avg_unit_price=12M 필터, 3M/all/last 컬럼 추가 |
