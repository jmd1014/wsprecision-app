# 현재 DB 상태 스냅샷 (2026-05-20 기준)

운영 DB (Supabase project `iryhamvxpboumnrtajwb`) 의 실제 상태를 기록.
GitHub 저장소의 SQL 파일과 실제 상태가 일치하는지 추적용.

---

## 1. 테이블 / 행 수 요약

| 테이블 | 행 수 (대략) | 상태 |
|---|---|---|
| `products` | 834 (활성 235 + 휴면 599) | 운영 중 |
| `materials` | 308 | 운영 중 |
| `bom` | 347 | 정비 진행 중 |
| `vendors` | 250+ | 운영 중 |
| `sales_ledger` | 11,307 | 적재 완료 (raw) |
| `purchase_ledger` | 5,332 | 적재 완료 (raw) |
| `sales_orders` / `sales_order_items` | 운영 중 (Stage 2) | 운영 중 |
| `purchase_orders` / `purchase_order_items` | 운영 중 (Stage 2) | 운영 중 |
| `inventory_transactions` | 0 | 미사용 (Stage 4 대기) |
| `production_log` | 0 | 미사용 (Stage 4 대기) |
| `production_plan` | 0 | 미사용 (Stage 4 대기) |
| `sales_data_exclusion` | 1 | 운영 중 (미진 2023-02 이전 제외) |
| `customer_part_mapping` | 운영 중 | 운영 중 |

## 2. BOM 현황

- 자재 row: ~344
- 공정 row: ~3 (열처리/표면 등)
- BOM 보유 활성 제품 수: 측정 필요 (active_bom_completion_v 통해 산출)
- verification_status='확인완료' 비율: 측정 필요

## 3. 원가 신뢰도 (cost_source from `product_cost_full_v`)

| 신뢰도 | 활성 | 휴면 | 합계 |
|---|---|---|---|
| BOM_FULL | 113 | 90 | 203 |
| BOM_PARTIAL | 38 | 102 | 140 |
| LEGACY_ONLY | 16 | 8 | 24 |
| NO_DATA | 68 | 399 | 467 |

→ **활성 235건 중 BOM_FULL 113건 (48%)**, NO_DATA 68건 (29%).

## 4. 매핑 진행률

| 매핑 키 | 매핑률 |
|---|---|
| `sales_ledger.product_id` | 약 99% |
| `purchase_ledger.matched_pn` (제품 매칭) | 약 99% |
| `purchase_ledger.matched_material_id` (자재 매칭) | **거의 0%** — 정비 최우선 |
| `production_log.product_id` | N/A (테이블 미사용) |

## 5. 적용된 마이그레이션

| # | 파일 | 적용 일자 | 핵심 변경 |
|---|---|---|---|
| 001 | vendor_group.sql | 2026-05-07 | vendors.vendor_group |
| 002 | sales_orders.sql | 2026-05-08 | sales_orders/items + customer_part_mapping |
| 003 | inventory_transactions.sql | 2026-05-13 | inventory_transactions + material_stock view |
| 004 | status_constraints.sql | 2026-05-13 | sales/po status CHECK 제약 |
| 005 | po_number_function.sql | 2026-05-13 | next_po_number() advisory lock |
| 006 | pending_qty_view.sql | 2026-05-13 | sales_order_items_v |
| 007 | bom_processes_and_mapping.sql | 2026-05-14 | bom.process_type / matched_material_id / production_log.product_id |
| 008 | cost_views.sql | 2026-05-14 | material_price_v / product_bom_cost_v / product_cost_full_v |
| 009 | cost_view_refactor.sql | 2026-05-15 | BOM=수량 / 가격=원가·매입 분리 + alias |
| 010 | bom_process_price.sql | 2026-05-15 | 공정행 LOT 단가 사용 |
| 011 | sales_stats_recent_avg.sql | 2026-05-17 | avg_unit_price = 12M 필터 |
| 012 | data_quality_exclusion.sql | 2026-05-17 | sales_data_exclusion + 미진 제외 규칙 |

## 6. 적용 예정 (이번 단계)

| # | 파일 | 목적 |
|---|---|---|
| 013 | active_master_views.sql | 활성 기준 정비 view + 매칭 view 6종 |

## 7. 알려진 정합성 이슈

| 이슈 | 영향 | 대응 |
|---|---|---|
| `purchase_ledger.category` 대부분 NULL | MAT_* 필터 제한적 | 향후 매입 입력 화면 신규 분류 |
| `products.active` 컬럼 거의 NULL | 사용 안 함 | `archived_at` 만 운영 기준 |
| 휴면 599건 (자동/일괄?) | 활성 235건만 정비 대상 | 기준 미상 — 운영자 확인 권장 |
| `purchase_ledger.matched_material_id` 0% | 자재 단가 시점화 안 됨 | Migration 013 매칭 화면 신설 |

## 8. 정책 메모

- **휴면 제품** 은 현재 단계 정비 대상에서 제외 (`archived_at IS NULL` 필터 항상 적용).
- **자동 수정 / 자동 overwrite 금지**. 모든 변경은 "후보 → 사용자 확인 → 반영".
- **destructive SQL 금지**. DROP TABLE / TRUNCATE / DELETE WITHOUT WHERE 모두 운영 적용 금지.
- **`_INITIAL_SETUP_ONLY_schema.sql`** 운영 실행 절대 금지 (DROP CASCADE 포함).

## 9. 재진단 명령

```sql
-- 활성/휴면 분포
SELECT count(*) FILTER (WHERE archived_at IS NULL) AS active,
       count(*) FILTER (WHERE archived_at IS NOT NULL) AS archived,
       count(*) AS total FROM products;

-- BOM 완성도 (013 적용 후)
SELECT completion_status, count(*) FROM active_bom_completion_v GROUP BY 1;

-- 매핑 진행률 (013 적용 후)
SELECT * FROM purchase_material_match_progress;
```
