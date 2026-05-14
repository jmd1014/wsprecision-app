# 데이터 아키텍처 (Data Architecture)

우성정밀 ERP/MES 의 데이터 흐름을 단방향 4-Layer 로 정리한 문서.
**원칙: Raw → View 자동 계산 → UI**. 정적 컬럼은 fallback / 표시용 캐시.

---

## 1. Layer 구조

```
┌─ Layer 1: Raw Transactions (원천) ─────────────────────────┐
│  purchase_ledger       : 매입 거래 원장                     │
│  sales_ledger          : 매출 거래 원장                     │
│  production_log        : 생산 실적                          │
│  inventory_transactions: 재고 이력 (003 도입)               │
│  purchase_orders       : 발주서 (Stage 2)                   │
│  sales_orders          : 수주 (002)                          │
└────────────────┬───────────────────────────────────────────┘
                 │ 매핑 키
┌────────────────▼───────────────────────────────────────────┐
│ Layer 2: Master + Mapping (마스터 + 매핑)                   │
│  products      : 제품 마스터                                │
│  materials     : 자재 마스터                                │
│  vendors       : 거래처                                      │
│  bom           : 제품-자재-공정 매핑 (007 공정행 지원)       │
│                                                              │
│  매핑 키:                                                    │
│   - purchase_ledger.matched_material_id  → materials (007)  │
│   - purchase_ledger.matched_pn           → products         │
│   - production_log.product_id            → products (007)  │
│   - sales_ledger.product_id              → products         │
│   - inventory_transactions.material_id   → materials        │
└────────────────┬───────────────────────────────────────────┘
                 │
┌────────────────▼───────────────────────────────────────────┐
│ Layer 3: Computed Views (자동 계산)                         │
│  material_price_v       : 자재 시점 단가 (3M/12M/최근)       │
│  product_bom_cost_v     : BOM × 자재단가 → 자동 원가         │
│  product_actual_cost_v  : 생산실적 → 실원가 (Phase 3)        │
│  product_stats          : 매출 통계 (기존)                   │
│  material_stock         : 실시간 재고 (003)                  │
│  sales_order_items_v    : 미납 수량 자동 계산 (006)          │
└────────────────┬───────────────────────────────────────────┘
                 │
┌────────────────▼───────────────────────────────────────────┐
│ Layer 4: Application Views (UI 진입점)                      │
│  product_cost_full_v    : 통합 — legacy/BOM/실원가/마진      │
│  product_full           : 마스터 + stats (기존)              │
│  active_products        : 활성 제품 (기존)                   │
│  sales_order_stats      : 수주 통계 (기존)                   │
└────────────────┬───────────────────────────────────────────┘
                 │
            [Streamlit 화면]
```

---

## 2. 매핑 키 채움 정책 (단계적)

| 매핑 키 | 현재 상태 | 채우는 방법 | 화면 |
|---|---|---|---|
| `purchase_ledger.matched_pn` | 99.9% 매핑 완료 | Stage 1에서 자동 매칭 | (이미 활용) |
| `purchase_ledger.matched_material_id` | **0% (신규)** | UI 수동 + 자동 매칭 도구 | 마스터 관리 → "매입 매핑" 탭 |
| `production_log.product_id` | **미적재** | 생산실적 적재 시 동시 매칭 | Stage 4 활성 시 |
| `sales_ledger.product_id` | 99% 매핑 완료 | Stage 1에서 자동 매칭 | (이미 활용) |
| `inventory_transactions.material_id` | 신규 (003) | UI 입출고 등록 시 직접 선택 | 입출고 화면 |

**점진적 채움 원칙**:
- 비어 있어도 view 는 `NULL` 반환 / 기존 화면 영향 없음.
- 채워질수록 `product_cost_full_v.cost_source` 가 `LEGACY_ONLY` → `BOM_PARTIAL` → `BOM_FULL` 로 자동 격상.

---

## 3. 원가 계산 우선순위

`product_cost_full_v.final_cost_per_pc` 가 다음 순서로 fallback:

```
1순위: BOM 기반 자동 (product_bom_cost_v.bom_cost_per_pc)
       ─ unit_price → material_price_v(3M) → material_price_v(12M) → 0
       
2순위: products.estimated_cost_per_pc  (정적 스냅샷, legacy)

3순위: NULL (마진 산출 불가)
```

**BOM 단가 채움 우선순위**:
```
bom.unit_price        ← 1순위 (운영자 수기 / 외주·열처리)
material_price_v.price_3m   ← 2순위 (최근 매입 평균)
material_price_v.price_12m  ← 3순위 (장기 평균)
0                            ← 4순위
```

이렇게 하면:
- BOM 행에 단가 직접 입력 시 → 즉시 반영
- 매입 ledger 매핑 시 → 시점별 자동 단가 활용
- 둘 다 없으면 → legacy 스냅샷
- 모든 데이터 없으면 → NO_DATA 신호

---

## 4. 공정행 (BOM 통합) 의 의미

기존: 자재만 BOM, 외주/열처리/표면처리는 `products` 의 별도 컬럼.

**개선 (007 이후)**: `bom.process_type` 으로 모두 한 곳에서 관리.

| process_type | 의미 | qty_per_pc | shared_factor | unit_price |
|---|---|---|---|---|
| `MATERIAL` | 자재 | 자재 사용량 | 분할가공 N제품 | NULL ↓ fallback |
| `HEAT` | 열처리 | 1 | 1 LOT 처리수량 | LOT 가격 |
| `SURFACE` | 표면처리 | 1 | 1 LOT 처리수량 | LOT 가격 |
| `OUTSOURCE` | 외주 가공 | 1 | 1 | EA당 외주비 |
| `PACKING` | 포장재 | 사용량 | 1 | 단가 |
| `LABOR` | 노무 직접 | 1 | 1 | EA당 노무 |
| `OTHER` | 기타 | 임의 | 임의 | 임의 |

**공식 일관**: `per_pc = unit_price × qty_per_pc / shared_factor`

---

## 5. 데이터 신뢰도 표기

`product_cost_full_v.cost_source` 값:

| 값 | 의미 | UI 색상 가이드 |
|---|---|---|
| `BOM_FULL` | BOM + 모든 단가 보유 | 🟢 초록 |
| `BOM_PARTIAL` | BOM 있으나 단가 일부 누락 | 🟡 노랑 |
| `LEGACY_ONLY` | 정적 스냅샷만 (BOM 미입력) | 🟠 주황 |
| `NO_DATA` | 원가 데이터 없음 | 🔴 빨강 |

화면에서 이 값을 배지로 노출하면 어느 품목부터 정비해야 할지 한눈에 파악.

---

## 6. 적용 단계 (현재 위치)

| Phase | 작업 | 상태 | 의존 |
|---|---|---|---|
| 1 | 마스터 적재 + 매출/매입 매핑 (matched_pn) | ✅ 완료 | - |
| 2a | Migration 007 (스키마 스캐폴딩) | 🟡 적용 대기 | - |
| 2b | Migration 008 (view 4종) | 🟡 적용 대기 | 007 |
| 2c | BOM 편집 UI 에 공정행 지원 | 🟡 개발 중 | 007 |
| 2d | 매입↔자재 매핑 UI (수동/반자동) | 🟡 개발 중 | 007 |
| 3a | 생산실적 적재 (Stage 4) | ⚪ 대기 | - |
| 3b | production_log.product_id 자동 매칭 | ⚪ 대기 | 3a |
| 4 | 시계열 분석 (월별 마진, 자재가 추이) | ⚪ 대기 | 2 완료 |

---

## 7. 운영자 행동 가이드

새 품목 등록 시:
1. **products** 에 마스터 등록 (pn, customer, material 등)
2. **bom** 에 자재행 + 공정행 입력 (`shared_factor` 정확히)
3. 자재 매입 발생 시 **매입 매핑 화면** 에서 `matched_material_id` 지정
4. **원가 분석 → 마진 대시보드** 확인. `cost_source = BOM_FULL` 이면 정상.

기존 품목 정비 시:
1. **원가 분석 → 이상치** 에서 `LEGACY_ONLY` 또는 `BOM_PARTIAL` 추출
2. 매출 큰 품목부터 BOM 행 보완 (단가 직접 입력)
3. 정기적으로 매입 매핑 화면에서 미매핑 거래 처리
