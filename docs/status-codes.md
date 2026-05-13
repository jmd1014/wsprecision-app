# 상태 코드 (Status Enum) 정의서

ERP/MES 의 모든 상태 컬럼은 본 문서의 enum 값만 허용한다.
DB 단에서는 `004_status_constraints.sql` 의 CHECK 제약으로 강제된다.

값 추가 시:
1. 본 문서 갱신
2. CHECK 제약 마이그레이션 추가 (예: `007_status_xxx_add_value.sql`)
3. UI 사이드(코드의 selectbox / 필터) 동기 수정

---

## 1. sales_orders.status (수주 헤더)

| 값 | 의미 | 비고 |
|---|---|---|
| `DRAFT` | 임시 저장 (입력 중) | 자동 파싱 결과 검토 단계 |
| `CONFIRMED` | 확정 (영업 승인) | 발주/생산 가능 상태 |
| `IN_PROD` | 생산 진행 중 | 1개 이상의 라인이 생산 들어감 |
| `PARTIAL` | 부분 납품 완료 | 일부 라인 DELIVERED |
| `DELIVERED` | 모든 라인 납품 완료 | 종결 후보 |
| `CANCELLED` | 취소 | 영업 측 취소 / 거래처 요청 |

---

## 2. sales_order_items.status (수주 라인)

| 값 | 의미 |
|---|---|
| `PENDING` | 미진행 (received_qty = 0) |
| `IN_PROD` | 생산 투입됨 |
| `PARTIAL` | 일부 출고 (0 < received_qty < qty) |
| `DELIVERED` | 전량 출고 (received_qty ≥ qty) |
| `CANCELLED` | 라인 취소 |

> **참고**: `pending_qty` 컬럼은 legacy (수기 입력 가능). 정확한 미납 수량은 view `sales_order_items_v.pending_qty_calc` 사용.

---

## 3. purchase_orders.status (발주)

| 값 | 의미 |
|---|---|
| `DRAFT` | 작성 중 (양식 미발송) |
| `SENT` | 거래처로 발주서 발송 완료 |
| `RECEIVED` | 전량 입고 완료 |
| `PARTIAL` | 일부 입고 |
| `CANCELLED` | 취소 |

---

## 4. inventory_transactions.txn_type (재고 트랜잭션 유형)

| 값 | 의미 | 부호 |
|---|---|---|
| `RECEIPT` | 매입 입고 | + |
| `ISSUE` | 출고 (일반) | − |
| `PROD_INPUT` | 생산 투입 (BOM 차감) | − |
| `PROD_OUTPUT` | 생산 산출 (완제품 입고) | + |
| `DEFECT` | 불량 폐기 | − |
| `ADJUSTMENT` | 재고 조정 (실사 차이) | ± |

**원칙**: `materials.stock_qty` 는 legacy. 실시간 재고는 view `material_stock` (`SUM(qty)`) 을 사용.

---

## 5. 상태 전이 규칙 (권장)

```
[sales_orders]
  DRAFT → CONFIRMED → IN_PROD → PARTIAL → DELIVERED
                                       ↘ CANCELLED (어디서나 가능)

[purchase_orders]
  DRAFT → SENT → PARTIAL → RECEIVED
              ↘ CANCELLED
```

UI 측은 권장 전이 외 경로도 허용 (운영자 판단 우선) 하되, 로그로 남길 것.
