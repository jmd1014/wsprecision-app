# 마스터 안정화 완료 기준 (Master Stabilization Exit Criteria)

현재 단계(마스터 정비 + BOM 정비 + 자재 매칭 + 원가 기준 단순화) 를 끝내고
**다음 단계 (생산/LOT 기능)** 로 진입하기 위한 객관적 완료 기준.

본 기준이 모두 충족되면 Stage 4 (생산·재고) 진입 가능.

---

## 1. 정량 기준

| # | 항목 | 목표 | 측정 |
|---|---|---|---|
| 1 | 활성 제품 BOM 연결률 | ≥ 90% | `active_bom_completion_v` 에서 `bom_row_count > 0` 비율 |
| 2 | active BOM row material_id 보유율 | 100% | MATERIAL 행 중 `material_id IS NULL` = 0 |
| 3 | 자재 매입 매칭률 (MAT_* 카테고리) | ≥ 80% | `purchase_material_match_progress.mat_match_rate_pct` |
| 4 | 원가 계산 가능 active 제품 | ≥ 80% | `product_cost_full_v` 에서 `cost_source IN ('BOM_FULL','BOM_PARTIAL','LEGACY_ONLY')` 비율 (활성) |
| 5 | BOM verification_status='확인완료' 비율 | ≥ 80% | active product 의 BOM row 중 |
| 6 | qty_per_pc / shared_factor NULL 또는 0 인 행 | ≤ 5% | `bom_cleanup_todo_v` 카운트 |

---

## 2. 정성 기준 (체크리스트)

- [ ] **휴면 제품 분리** — 활성 235건만 정비 대상. 휴면 599건은 분석/정비 화면 기본 제외.
- [ ] **BOM 화면 = 구조/수량만** — 단가/원가 입력 제거됨. 화면 검사 완료.
- [ ] **원가 화면 = 가격/원가만** — BOM 구조 편집 불가. 자동 overwrite 비활성.
- [ ] **자재/구매 매칭 화면 메인 메뉴 노출** — 미매칭 매입 우선순위 리스트 가시.
- [ ] **이상치 / 진단 메뉴 격리** — 보조 점검 페이지로 이동, 자동 수정 버튼 숨김.
- [ ] **중복 BOM 행 없음** — 같은 (product_id, material_id, process_type) 중복 없음.
- [ ] **migration 정책 준수** — 모든 DB 변경이 `supabase/migrations/` 파일에 기록.
- [ ] **운영 적용 표 일관성** — `supabase/README.md` 와 `docs/db-state-current.md` 동기화.

---

## 3. 검증 쿼리 (013 적용 후 실행)

### 3.1 활성 제품 BOM 연결률
```sql
SELECT
  count(*) AS active_total,
  count(*) FILTER (WHERE bom_row_count > 0) AS with_bom,
  ROUND(100.0 * count(*) FILTER (WHERE bom_row_count > 0) / NULLIF(count(*), 0), 1) AS connection_rate_pct
FROM active_bom_completion_v;
-- 목표: connection_rate_pct >= 90
```

### 3.2 BOM material_id 보유율
```sql
SELECT
  count(*) AS total_material_rows,
  count(*) FILTER (WHERE material_id IS NULL) AS missing_material_id,
  ROUND(100.0 * count(*) FILTER (WHERE material_id IS NOT NULL) / NULLIF(count(*), 0), 1) AS coverage_pct
FROM bom
WHERE COALESCE(process_type, 'MATERIAL') = 'MATERIAL'
  AND product_id IN (SELECT product_id FROM products WHERE archived_at IS NULL);
-- 목표: coverage_pct = 100
```

### 3.3 자재 매입 매칭률
```sql
SELECT * FROM purchase_material_match_progress;
-- 목표: mat_match_rate_pct >= 80
```

### 3.4 원가 계산 가능 비율 (활성만)
```sql
SELECT
  cost_source, count(*) AS cnt,
  ROUND(100.0 * count(*) / SUM(count(*)) OVER (), 1) AS pct
FROM product_cost_full_v
WHERE archived_at IS NULL
GROUP BY cost_source;
-- 목표: NO_DATA 비율 < 20%
```

### 3.5 verification_status 확인완료 비율
```sql
SELECT
  count(*) AS total_active_bom_rows,
  count(*) FILTER (WHERE verification_status = '확인완료') AS confirmed,
  ROUND(100.0 * count(*) FILTER (WHERE verification_status = '확인완료') / NULLIF(count(*), 0), 1) AS confirmed_pct
FROM bom
WHERE product_id IN (SELECT product_id FROM products WHERE archived_at IS NULL);
-- 목표: confirmed_pct >= 80
```

---

## 4. 진입 후 다음 단계

본 기준 충족 후 **Stage 4 (생산/LOT)** 진입:
- `production_log` 본격 운영
- LOT 추적 (sales_order_items.customer_lot, mes_work_order 활용)
- `inventory_transactions` 본격 운영 (입출고 화면)
- 생산실적 → 실원가 계산 (`product_actual_cost_v` 활성)

→ 이 시점부터 **생산 정보 + 자재 LOT** 가 BOM/원가에 연결되기 시작.
→ 본 마스터 정비가 견고할수록 Stage 4 가 매끄럽다.

---

## 5. 현재 상태 점검 (작성 시점)

| 항목 | 현재 | 목표 | 갭 |
|---|---|---|---|
| 활성 제품 BOM 연결률 | 측정 필요 (013 적용 후) | 90% | ? |
| material_id 보유율 | 측정 필요 | 100% | ? |
| 자재 매입 매칭률 | ~0% | 80% | **최대 갭** |
| 원가 계산 가능 비율 | 약 71% (168/235) | 80% | -9%p |
| verification_status | 측정 필요 | 80% | ? |

→ **자재 매입 매칭이 가장 큰 갭**. 이번 단계의 핵심 작업 1순위.

---

## 6. 이번 단계에서 명시적으로 안 하는 것

본 기준은 다음을 **포함하지 않는다**:
- LOT genealogy
- 공정별 LOT 추적
- 생산실적 적재/연결
- 실원가 계산
- APS/MRP 고도화
- 신규 이상치 알고리즘
- 자동 보정/자동 overwrite

→ 위 항목은 Stage 4 이후로 보류.
