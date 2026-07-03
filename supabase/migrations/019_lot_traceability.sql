-- ════════════════════════════════════════════════════════════
-- Migration 019: Phase C — 납품-생산 연결 (LOT 추적 + 역추적)
-- ════════════════════════════════════════════════════════════
-- 배경:
--   go-live 로드맵 Phase C.
--   1) 납품 등록 시 제품 재고 차감 (ISSUE) — 코드에서 원장 기록
--   2) 생산 LOT ↔ 납품 연결 — inventory_transactions.lot_number 활용
--   3) 역추적: 제품/LOT 로 입고→생산→납품 타임라인 조회
--
-- 변경 내용:
--   1. production_log.lot_number — 생산 보고와 원장 LOT 연결
--   2. lot_trace_v — LOT 단위 원장 타임라인 (역추적 핵심)
--   3. product_trace_v — 제품 단위 원장 타임라인 (입고/생산/납품 통합)
--
-- 비파괴 / 멱등.
-- ════════════════════════════════════════════════════════════

-- 1. 생산 보고 LOT 번호
ALTER TABLE production_log
  ADD COLUMN IF NOT EXISTS lot_number TEXT;

CREATE INDEX IF NOT EXISTS idx_prodlog_lot ON production_log(lot_number);

COMMENT ON COLUMN production_log.lot_number IS
  '생산 LOT. inventory_transactions.lot_number 와 연결되어 역추적 키가 됨.';


-- 2. LOT 단위 타임라인 (역추적)
CREATE OR REPLACE VIEW lot_trace_v AS
SELECT
  it.lot_number,
  it.txn_id,
  it.txn_date,
  it.txn_type,
  CASE it.txn_type
    WHEN 'RECEIPT'     THEN '① 자재 입고'
    WHEN 'PROD_INPUT'  THEN '② 생산 투입 (자재)'
    WHEN 'PROD_OUTPUT' THEN '③ 생산 완성 (제품)'
    WHEN 'ISSUE'       THEN '④ 납품 출고'
    WHEN 'DEFECT'      THEN '불량 폐기'
    WHEN 'ADJUSTMENT'  THEN '재고 조정'
  END                                            AS step_label,
  it.material_id,
  m.raw_name                                     AS material_name,
  it.product_id,
  p.pn,
  it.qty,
  it.unit,
  it.ref_table,
  it.ref_id,
  it.remark,
  it.created_at
FROM inventory_transactions it
LEFT JOIN materials m ON m.material_id = it.material_id
LEFT JOIN products  p ON p.product_id  = it.product_id
WHERE it.lot_number IS NOT NULL;

COMMENT ON VIEW lot_trace_v IS
  'LOT 번호 기준 원장 타임라인. 자재 입고 → 생산 투입/완성 → 납품 출고 역추적.';


-- 3. 제품 단위 타임라인 (LOT 없는 거래 포함 — 통합 이력)
CREATE OR REPLACE VIEW product_trace_v AS
SELECT
  p.product_id,
  p.pn,
  it.txn_id,
  it.txn_date,
  it.txn_type,
  CASE it.txn_type
    WHEN 'RECEIPT'     THEN '① 자재 입고'
    WHEN 'PROD_INPUT'  THEN '② 생산 투입 (자재)'
    WHEN 'PROD_OUTPUT' THEN '③ 생산 완성 (제품)'
    WHEN 'ISSUE'       THEN '④ 납품 출고'
    WHEN 'DEFECT'      THEN '불량 폐기'
    WHEN 'ADJUSTMENT'  THEN '재고 조정'
  END                                            AS step_label,
  it.material_id,
  m.raw_name                                     AS material_name,
  it.qty,
  it.unit,
  it.lot_number,
  it.ref_table,
  it.ref_id,
  it.remark,
  it.created_at
FROM inventory_transactions it
JOIN products p ON p.product_id = it.product_id
LEFT JOIN materials m ON m.material_id = it.material_id;

COMMENT ON VIEW product_trace_v IS
  '제품 기준 원장 타임라인 (LOT 유무 무관). 생산 투입 자재까지 포함한 통합 이력.';
