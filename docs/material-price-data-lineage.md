# 자재 가격 데이터 출처 (Data Lineage)

자재 가격 정보가 **어디서 오는지** 명확히 추적하는 문서.
사용자 우려 "v11 매핑이 떨어진 게 아닌가?" 에 대한 답.

---

## 1. 핵심 답: **v11 매핑 데이터는 손실 없음**

`product_master_v11.xlsx` (Stage 1 import 원본) ↔ 현재 DB 비교:

| 컬럼 (v11) | products 컬럼 (DB) | v11 행수 | DB 행수 | 손실 |
|---|---|---:|---:|---:|
| 자재_KG단가 | `material_kg_price` | 183 | 183 | 0 |
| 자재_개당단가 | `material_unit_price` | 227 | 227 | 0 |
| 자재_매입건수 | `material_purchase_count` | 228 | 228 | 0 |
| 자재_최근매입일 | `material_last_purchase_date` | 228 | 228 | 0 |
| 자재_주공급사 | `material_main_supplier` | 228 | 228 | 0 |
| 자재_데이터품질 | `material_data_quality` | 834 | 834 | 0 |
| 추정원가/PC | `estimated_cost_per_pc` | 228 | 228 | 0 |
| 외주가공비/PC | `outsourcing_per_pc` | 3 | 2 | 1 (작음) |
| 열처리비/PC | `heat_treat_per_pc` | 4 | 1 | 3 (작음) |

→ **자재 가격 관련 모든 컬럼 손실 0**.

---

## 2. 그럼 왜 "매핑 떨어진 것처럼" 보였나?

**두 가지 매입 매핑 영역이 혼동되었기 때문**:

### A. v11 매입 매핑 (Stage 1, 이미 완료)
- 위치: `products.material_unit_price`, `material_main_supplier`, `material_purchase_count` 등
- 출처: product_master_v11.xlsx (Apps Script 가 매입 데이터 분석 후 자동 채움)
- 상태: **228건 보존, 활성 130건 / 휴면 98건**
- 역할: BOM 자동 원가 계산의 **legacy fallback** (`product_bom_cost_v` 의 3순위)

### B. purchase_ledger raw 매핑 (Migration 007 에서 추가, 신규 영역)
- 위치: `purchase_ledger.matched_material_id`
- 출처: 매입 ledger 의 각 raw 거래 행을 자재 마스터와 1:1 매핑
- 상태: **0%** (정책상 사후 매핑 안 함)
- 역할: `material_price_v` 의 시점별 평균 산출 (3M/12M)

**A 와 B 는 서로 다른 영역**.
- A 는 v11 시점의 매입 데이터 분석 결과를 products 에 스냅샷 저장
- B 는 매입 ledger 의 raw 거래를 자재 마스터로 매핑 (시간 흐름에 따른 자재가 변동 추적용)

→ B 가 0% 이지만, A 는 그대로 살아있음.

---

## 3. cost_source 신뢰도가 'LEGACY_ONLY' 로 표시되는 이유

`product_cost_full_v` 의 `cost_source` 우선순위:

```
1. material_price_v (B 매입 매핑 기반)   ← 현재 0%
2. products.material_unit_price (A v11) ← 살아있음
   → cost_source = 'LEGACY_ONLY' 표시
3. 없으면 NO_DATA
```

→ **"LEGACY_ONLY" 라벨이 부정적으로 보이지만 실제로는 v11 매핑이 정상 작동 중**.

---

## 4. 데이터 흐름 (단가 출처)

```
[Stage 1 시점 매입 분석]
  product_master_library.gs (Apps Script)
       ↓ 자동 분석
  product_master_v11.xlsx 의 자재_* 컬럼
       ↓ import_masters.py
  products.material_unit_price, ...   ← ✅ 보존됨

[향후 매입 데이터 흐름]
  새 매입 거래 입력 (앱)
       ↓ 입력 시 자재 선택
  purchase_ledger.matched_material_id 자동 채움
       ↓ Migration 008 view
  material_price_v.price_3m / price_12m  ← 점진 활성
       ↓ product_bom_cost_v
  자동 원가 계산 (BOM 자재행)
```

→ **두 흐름이 같이 작동**. v11 매핑은 fallback, 신규 매입 매핑이 우선시되는 구조.

---

## 5. BOM 자재행 152건 가격 출처 현황 (Migration 014 검증)

| 출처 | 건수 | 비율 |
|---|---|---|
| 🟢 매입 매핑 (B) | 0 | 0% |
| 🟠 legacy (A — v11 출신) | **114** | **75%** |
| 🟡 사급 N/A | 4 | 2.6% |
| 🔴 없음 | 34 | 22.4% |

→ **75% 가 v11 매핑으로 작동 중**. 진짜 미정비는 34건만.

---

## 6. UI 변경 (가시화 추가)

### 🎯 TOP 우선 정비
- 제품 선택 시 **"📜 v11 매입 매핑 이력"** expander 표시 (해당 데이터 있는 경우)
  - 매입 건수 / 주 공급사 / 최근 매입일 / 데이터 품질
  - 매입 평균 단가 (KG, EA)
  - "이 값이 products.material_unit_price 의 근거" 명시

### 🩺 보조 점검 → 종합 진단
- **"🧪 자재 가격 출처 분포"** 섹션 (Migration 014)
- 매입 매핑 vs legacy vs 없음 비율
- "🔴 가격 없는 자재행 N건 보기"

---

## 7. 결론 — 정비 진행 가이드

| 작업 | 우선 |
|---|---|
| v11 매핑 데이터 보존 확인 (이 문서) | ✅ 완료 |
| BOM 자재행 152건 중 🟠 legacy 114건 | 그대로 사용 (정상) |
| 🔴 가격 없는 34건 → 자재 단가 직접 입력 | 🥇 1순위 |
| 사급 N/A 4건 → procurement_type 확정 | 🥈 |
| 향후 매입 입력 화면 → 자동 매핑 (B 영역 점진 활성) | 🥉 |
| BOM 공정행 (열처리/외주/표면) 추가 정비 | 🟡 분리 작업 |

**원본 데이터 보존이 확인되었으니, 정비 작업은 누락된 34건 자재 가격 입력 부터 진행하시면 됩니다.**
