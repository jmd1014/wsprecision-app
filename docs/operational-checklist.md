# 운영 전 점검표 (Operational Checklist)

본격적인 사내 운영(여러 명이 동시에 사용) 직전에 반드시 한 번씩 점검한다.
한 항목씩 ✅ 표시하면서 진행할 것.

---

## A. DB / 인프라

- [ ] **A1. Supabase 자동 백업 활성화 확인**
  - 대시보드 → Database → Backups 에 최근 24시간 내 백업 존재.
  - Free 플랜은 7일 retention, Pro 플랜은 PITR 활성 여부 확인.

- [ ] **A2. `_INITIAL_SETUP_ONLY_schema.sql` 직접 실행 금지 주지**
  - 이 파일은 신규 환경 구축 전용. 운영 DB 에 절대 붙여넣지 말 것.
  - 관련자(현재는 김민수 1인) 가 인지하고 있음을 확인.

- [ ] **A3. 모든 마이그레이션이 운영 DB 에 적용되었는지 확인**
  - `supabase/README.md` 의 적용 표와 실제 DB 상태 일치.
  - 핵심: 003 (inventory_transactions), 004 (status CHECK), 005 (next_po_number), 006 (sales_order_items_v).

- [ ] **A4. service_role key 노출 범위 확인**
  - MVP 단계에서는 Streamlit Cloud Secrets 에만 존재.
  - 절대 GitHub 에 커밋되지 않았는지 `git log -p` 또는 `git secret-scan` 으로 확인.

---

## B. 동시성 / 데이터 무결성

- [ ] **B1. 발주번호 중복 발급 테스트**
  - 두 개의 브라우저 탭에서 거의 동시에 발주서 생성.
  - 생성된 두 발주번호가 **서로 다른지** 확인.
  - DB 함수 `next_po_number()` 가 advisory lock 으로 직렬화하므로 중복 없어야 함.

- [ ] **B2. 발주번호 형식 검증**
  - 모든 신규 발주번호가 `PO-YYYYMM-NNN` (예: `PO-202605-001`) 형식 준수.
  - `python -m pytest tests/test_po_number.py -v` 통과 확인.

- [ ] **B3. 상태값 CHECK 제약 작동 확인**
  - SQL Editor 에서 `UPDATE sales_orders SET status='INVALID' WHERE so_id=1` 실행 시 에러로 거부되어야 함.

---

## C. 핵심 기능 회귀 테스트

- [ ] **C1. 수주 업로드 (Excel - HDX 53열)**
  - 샘플 HDX 발주 Excel 업로드 → 라인 자동 파싱 → 저장 → DB 에 정상 INSERT.
  - 중복 SO 번호 입력 시 dup 알림 후 차단.

- [ ] **C2. 수주 업로드 (Excel - 미진 37열)**
  - 미진메탈 양식 업로드 → 정상 파싱.

- [ ] **C3. 수주 업로드 (PDF - MJT)**
  - MJT PDF 업로드 → text-line regex 파싱 → 수량/단가 정상 매핑.

- [ ] **C4. 발주서 생성 (수기 입력)**
  - 거래처/품목 수기 입력 → 발주번호 자동 발급 → Excel 양식 다운로드.

- [ ] **C5. 발주서 생성 (수주 기반 자동)**
  - 수주 라인 선택 → 자재 자동 산출 (BOM × 미납 수량) → 발주서 생성.

- [ ] **C6. BOM 편집**
  - 제품 검색 → BOM 라인 추가/수정/삭제 → 저장.
  - 검색 전 오류 메시지 노출 없음.

- [ ] **C7. 재고 입출고 (inventory_transactions)**
  - 입고 등록 → `material_stock` 뷰 수량 증가.
  - 생산 투입(PROD_INPUT) → 수량 감소.
  - 불량(DEFECT) 등록 → 수량 감소.
  - 조정(ADJUSTMENT) → 임의 +/− 반영.

- [ ] **C8. BOM 필요량 계산**
  - 수주 1건 선택 → 자재별 필요량 = `qty × qty_per_pc ÷ shared_factor` 산출.
  - 부족분 = `필요량 − 현재고` 가 정확히 계산.

---

## D. 자동화 테스트

- [ ] **D1. pytest 전체 통과**
  ```
  python -m pytest tests/ -v
  ```
  - 모든 테스트 PASS.

- [ ] **D2. Streamlit 앱 import 에러 없음**
  ```
  python -c "import ast; ast.parse(open('streamlit_app.py', encoding='utf-8').read())"
  ```

---

## E. 사용자/운영

- [ ] **E1. 운영 담당자(현재 김민수) 가 본 점검표를 한번 끝까지 수행했음.**
- [ ] **E2. 오류 발생 시 슬랙 (#개발) 에 보고하는 절차 공유.**
- [ ] **E3. 백업 복원 절차(`docs/db-migration-guide.md` 의 롤백 절차) 숙지.**

---

## F. 점검 결과

| 일자 | 점검자 | 결과 | 비고 |
|------|--------|------|------|
| | | | |

신규 점검 시마다 행 추가.
