# 조달 분류 (도급 / 사급) 정책

우성정밀의 제품은 조달 방식에 따라 **도급** 또는 **사급** 으로 구분된다.
같은 기능의 제품이라도 분기되어 다른 PN 으로 관리한다.

---

## 1. 정의

| 구분 | 의미 | 원가 구성 | 매출가에 포함 |
|---|---|---|---|
| **도급** | 우성정밀이 소재 구매 + 가공 + 납품 | 소재비 + 외주 + 열처리 + 표면 + ... | 전체 |
| **사급** | 고객이 소재 공급 + 우성정밀이 가공만 | 0(소재) + 외주 + 열처리 + 표면 + ... | 가공비만 |

---

## 2. PN 명명 컨벤션

```
도급 (소재 포함):   4S<원본PN>      예) 4S20AHYBV-03-X1413
사급 (가공만):     <원본PN>          예) 20AHYBV-03-X1413
```

→ `4S` 접두사가 도급 식별자.

---

## 3. 메타데이터 (products 테이블)

| 컬럼 | 값 |
|---|---|
| `procurement_type` | `'도급'` 또는 `'사급'` |
| `procurement_start_date` | 분류 변경 시작일 (시점 분기) |
| `procurement_prev_type` | 이전 분류 (변경 추적) |

→ 분류가 바뀌면 새 PN 부여 + procurement_type 변경 + prev_type / start_date 자동 기록.

---

## 4. 분기 시점 처리

### A. PN 분기 방식 (현재 정책)
- 도급/사급 전환 시 **새 PN** 생성 (4S 접두사 추가/제거)
- 기존 PN 의 거래는 그대로 유지
- 새 PN 으로 발주받기 시작
- **장점**: 매출/원가/마진 통계가 PN 단위로 자동 분리
- **단점**: 도면/스펙 같은데 PN 두 개 관리

### B. 메타데이터만 변경 (대안)
- 같은 PN 유지 + `procurement_type` 변경 + `procurement_start_date` 기록
- 통계는 시점으로 분리해야 함 (복잡)
- **장점**: PN 하나로 관리
- **단점**: 통계 분리 어려움, 거래처 발주서와 매칭 어려움

→ **현재는 A 방식 채택**. 매출/원가 분석 명확성 우선.

---

## 5. BOM 처리

### 도급 (4S~)
- BOM 자재행: 정확히 입력 (qty_per_pc, shared_factor, material_id)
- 자재 단가: `products.material_unit_price` 또는 매입 매핑
- BOM 공정행: 외주/열처리 LOT 단가 입력
- 추정원가 = 소재 + 모든 공정

### 사급 (일반 PN)
- BOM 자재행: 자재 정보 입력 (참고용 — 어떤 자재를 쓰는지 추적)
- 자재 단가: **0 또는 NULL** (소재비 미산입)
- BOM 공정행: 외주/열처리 LOT 단가 입력
- 추정원가 = 공정만 (소재 제외)

---

## 6. 화면 동작

### 🎯 TOP 우선 정비
- 제품 선택 시 `procurement_type` 자동 인식
- 4S 접두사 + 미설정 → "도급 추정" 안내
- **사급** 인 경우:
  - 자재 단가 입력 영역 **비활성화** (정보 안내)
  - 이미 단가가 입력되어 있으면 **"0으로 초기화"** 버튼 노출
- **도급** 인 경우:
  - 자재 단가 입력 영역 활성 (필수 체크리스트)
  - 현재 값 위에 새 값 덮어쓰기 가능 (정정)

### 마스터 관리 → 🧱 제품 편집
- `procurement_type` 컬럼 selectbox 로 직접 편집
- 변경 시 자동으로 변경 이력 기록 (procurement_prev_type, procurement_start_date)

---

## 7. 매출 데이터 처리

- `sales_ledger.product_id` 가 정확히 매핑되어 있어야 PN 분기 의미 있음
- 같은 자재 사용 제품이라도 PN 다르면 별도 매출 → product_stats 자동 분리
- 12M 평균 / 마진 / 추세 모두 PN 단위

---

## 8. 자동 감지 규칙

```python
# 4S 접두사 자동 도급 추정
if pn.upper().startswith('4S') and not procurement_type:
    suggested_type = '도급'
    # UI 에서 "도급 추정" 표시 + 사용자 확인 후 저장
```

→ 자동 저장 X, 사용자 확인 필수.

---

## 9. 변경/정정 시 주의

1. 분류 변경(도급↔사급) 은 **새 거래에만** 적용 권장
2. 과거 거래는 그대로 (원본 보존)
3. 사급 → 도급 전환 시: 새 PN (4S 접두사) 부여 권장
4. 도급 → 사급 전환 시: 4S 접두사 제거된 PN 부여 권장
5. **같은 PN 으로 분류만 변경하는 케이스** 는 `procurement_start_date` 로 시점 표시

---

## 10. 검증 SQL

```sql
-- 4S 접두사 + procurement_type 일치 검증
SELECT pn, procurement_type,
  CASE
    WHEN pn LIKE '4S%' AND procurement_type = '도급' THEN '✅ OK'
    WHEN pn NOT LIKE '4S%' AND procurement_type = '사급' THEN '✅ OK'
    WHEN procurement_type IS NULL THEN '⚠️ 분류 미설정'
    ELSE '❌ 명명 불일치'
  END AS status
FROM products
WHERE archived_at IS NULL
ORDER BY status DESC, pn;
```
