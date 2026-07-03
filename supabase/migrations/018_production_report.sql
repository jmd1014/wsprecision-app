-- ════════════════════════════════════════════════════════════
-- Migration 018: Phase B — 생산 보고 (자재 차감 + 제품 재고)
-- ════════════════════════════════════════════════════════════
-- 배경:
--   go-live 로드맵 Phase B. 생산 완료 보고 시:
--   1) production_log 기록 (product_id 포함)
--   2) BOM 기준 자재 차감 — inventory_transactions PROD_INPUT (음수)
--   3) 제품 완성 재고 — inventory_transactions PROD_OUTPUT (양수)
--
-- 변경 내용:
--   1. inventory_transactions.material_id NOT NULL 해제
--      + CHECK (material_id / product_id 중 하나는 필수)
--      → 제품 단위 PROD_OUTPUT 행 지원 (자재 없이 제품만 참조)
--   2. product_stock_v — 제품 완성 재고 view
--      (PROD_OUTPUT − ISSUE 누적, Phase C 납품 차감 대비)
--
-- 비파괴 / 멱등.
-- ════════════════════════════════════════════════════════════

-- 1. material_id 선택화 + 무결성 CHECK
ALTER TABLE inventory_transactions
  ALTER COLUMN material_id DROP NOT NULL;

ALTER TABLE inventory_transactions
  DROP CONSTRAINT IF EXISTS chk_inv_txn_target;
ALTER TABLE inventory_transactions
  ADD CONSTRAINT chk_inv_txn_target
  CHECK (material_id IS NOT NULL OR product_id IS NOT NULL);

COMMENT ON CONSTRAINT chk_inv_txn_target ON inventory_transactions IS
  '자재(material_id) 또는 제품(product_id) 중 하나는 반드시 참조.';


-- 2. 제품 완성 재고 view
CREATE OR REPLACE VIEW product_stock_v AS
SELECT
  p.product_id,
  p.pn,
  p.customer,
  COALESCE(SUM(CASE WHEN it.txn_type = 'PROD_OUTPUT' THEN it.qty ELSE 0 END), 0) AS produced_qty,
  COALESCE(SUM(CASE WHEN it.txn_type = 'ISSUE'       THEN it.qty ELSE 0 END), 0) AS issued_qty,
  COALESCE(SUM(it.qty) FILTER (WHERE it.txn_type IN ('PROD_OUTPUT','ISSUE','ADJUSTMENT')), 0) AS current_stock,
  MAX(it.txn_date) AS last_txn_date,
  COUNT(it.txn_id) AS txn_count
FROM products p
JOIN inventory_transactions it ON it.product_id = p.product_id
  AND it.material_id IS NULL          -- 제품 단위 거래만 (자재 차감 행 제외)
GROUP BY p.product_id, p.pn, p.customer;

COMMENT ON VIEW product_stock_v IS
  '제품 완성 재고 = PROD_OUTPUT(+) + ISSUE(−) + ADJUSTMENT 누적. Phase C 납품 차감 대비.';
