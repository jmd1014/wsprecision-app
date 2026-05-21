# Legacy / Deprecated 필드 정리

운영 중인 컬럼/뷰 중 **현재 사용 안 함** 또는 **fallback 용** 으로만 유지되는 것을 모은 문서.
삭제 금지 (호환성). 신규 코드에서는 권장 view/컬럼을 사용한다.

---

## 1. 필드 분류

| 컬럼 | 테이블 | 상태 | 권장 대체 | 사유 |
|---|---|---|---|---|
| `stock_qty` | materials | 🟠 LEGACY | `material_stock` view | Migration 003 이후 inventory_transactions 집계 view 사용 |
| `pending_qty` | sales_order_items | 🟠 LEGACY | `sales_order_items_v.pending_qty_calc` | Migration 006 이후 view 자동 계산 |
| `unit_price` | bom | 🟠 LEGACY (공정행만 사용) | products.<공정>_per_pc | BOM 자재행 단가 입력 정책 폐지. 공정행은 LOT 단가 보유 |
| `material_unit_price` | products | 🟠 LEGACY (fallback) | `material_price_v` (매입 평균) | 매입 매핑이 채워지면 매입 평균 우선 사용 |
| `heat_treat_per_pc` | products | 🟠 LEGACY (fallback) | BOM 공정행 unit_price | 정확도 ↑ — BOM 공정행 LOT 단가 입력 시 자동 우선 |
| `surface_per_pc` | products | 🟠 LEGACY (fallback) | BOM 공정행 unit_price (SURFACE) | 동상 |
| `outsourcing_per_pc` | products | 🟠 LEGACY (fallback) | BOM 공정행 unit_price (OUTSOURCE) | 동상 |
| `estimated_cost_per_pc` | products | 🟠 LEGACY (fallback) | `product_cost_full_v.final_cost_per_pc` | BOM 자동 계산 우선. NULL 일 때만 estimated 사용 |
| `active` | products | 🔴 DEPRECATED | `archived_at IS NULL` | 거의 NULL — 운영 사용 안 함 |
| `avg_unit_price` | product_stats | 🟢 ACTIVE (12M 필터됨) | (동일) | Migration 011 에서 12M 평균으로 정의 변경됨 |

---

## 2. 컬럼 사용 변화 표

### `materials.stock_qty`
```
이전 (Migration 003 전)
  - UI 에서 직접 stock_qty 표시
  - 입출고 시 stock_qty 직접 UPDATE

현재
  - inventory_transactions INSERT 만
  - 재고는 material_stock view 에서 SUM(qty) 자동 계산
  - stock_qty 컬럼은 보존 (감사용)
```

### `sales_order_items.pending_qty`
```
이전 (Migration 006 전)
  - 미납 수량을 컬럼에 저장
  - received_qty 갱신 시 별도 UPDATE 필요

현재
  - pending_qty 컬럼은 보존 (호환)
  - 신규 계산: sales_order_items_v.pending_qty_calc
  - = GREATEST(qty - received_qty, 0)
```

### `bom.unit_price`
```
정책 변화:
  - 자재행: 단가 입력 안 함 (매입 평균 / products fallback)
  - 공정행: LOT 단가 직접 입력 (Migration 010 이후)
  - product_bom_cost_v 에서 공정행 unit_price 우선 사용

신규 코드 가이드:
  - UI 에서 자재행의 unit_price 는 read-only
  - 공정행만 LOT 단가 입력 가능
  - 자재행 unit_price 변경 시도 → 저장 로직에서 무시
```

### `products.material_unit_price` (외 4 컬럼)
```
fallback chain (product_bom_cost_v.material_cost_per_pc 산정):
  1. material_price_v.price_3m  (매입 ledger 매핑된 자재)
  2. material_price_v.price_12m
  3. products.material_unit_price  (legacy 스냅샷)
  4. 0

→ 매칭이 채워지면 자동으로 LEGACY → 매입 평균으로 우월 사용.
→ 사용자가 products.material_unit_price 를 직접 편집해도 됨 (fallback 유지).
```

### `products.active`
```
거의 모든 행에서 NULL.
운영 기준은 archived_at IS NULL/NOT NULL 만 사용.
신규 코드에서 active 컬럼 참조 금지.
```

---

## 3. 정리 정책

- **삭제 금지** — legacy 필드도 모두 보존 (호환성, 감사).
- **마이그레이션** — 삭제하지 않음. COMMENT 로만 LEGACY 표시.
- **UI** — 가능하면 표시 안 함, 또는 disabled 로 표시.
- **신규 코드** — 권장 view/컬럼 사용. legacy 직접 참조 지양.

---

## 4. 향후 처리 로드맵

| 컬럼 | 향후 처리 |
|---|---|
| `materials.stock_qty` | inventory_transactions 본격 운영 시 → COMMENT 만 갱신 |
| `sales_order_items.pending_qty` | Stage 5 (매출 대조) 후 → UI 표시 제거 |
| `bom.unit_price` 자재행 | 신규 코드 path 에서 무시 (이미 정책) |
| `products.material_unit_price` 외 | 매칭 80% 달성 후 → 표시 약화 |
| `products.active` | Stage 4 진입 시 컬럼 자체 제거 검토 |

→ Stage 4 진입 후 legacy 정리 별도 마이그레이션 작성 가능 (현재 단계 X).

---

## 5. 신규 view (Migration 013) 활용 매핑

| 운영 영역 | 권장 view | 대체 대상 (legacy) |
|---|---|---|
| 활성 BOM 완성도 | `active_bom_completion_v` | 별도 카운팅 SQL |
| BOM 미보유 활성 제품 | `bom_missing_active_products_v` | 수동 LEFT JOIN |
| 정비 우선순위 | `bom_cleanup_todo_v` | 수동 정렬 |
| 미매핑 매입 | `unresolved_purchase_materials` | DISTINCT GROUP BY |
| 자재 후보 추천 | `material_mapping_candidates` | 수동 LIKE 검색 |
| 매핑 진행률 | `purchase_material_match_progress` | COUNT 쿼리 |
