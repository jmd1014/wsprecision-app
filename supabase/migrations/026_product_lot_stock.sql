-- ════════════════════════════════════════════════════════════
-- Migration 026: 제품 LOT별 완성 재고 (선입선출 출고 기반)
-- ════════════════════════════════════════════════════════════
-- 배경 (2026-07-27 사용자 지적):
--   완성(PROD_OUTPUT)은 lot_number = 작업지시NO 로 LOT 이 구분되는데
--   출고(ISSUE)는 LOT 없이 제품 총량에서만 차감되어,
--   ① LOT 별 잔량 파악 불가 ② 선입선출 강제 불가
--   ③ 클레임 시 출고분 → 작업지시 → 소재 역추적 단절
--   ④ 특채 포함 LOT 의 행방 추적 불가.
--
-- 해결: LOT 별 잔량 뷰 + 앱에서 FIFO 배분해 ISSUE 를 LOT 단위로 분할 기록.
--
-- 비파괴 / 멱등.
-- ════════════════════════════════════════════════════════════

CREATE OR REPLACE VIEW product_lot_stock_v AS
WITH lot_txn AS (
  SELECT
    it.product_id,
    it.lot_number,
    SUM(CASE WHEN it.txn_type = 'PROD_OUTPUT' THEN it.qty ELSE 0 END)
      AS produced_qty,
    SUM(CASE WHEN it.txn_type = 'ISSUE' THEN -it.qty ELSE 0 END)
      AS issued_qty,
    MIN(it.txn_date) FILTER (WHERE it.txn_type = 'PROD_OUTPUT')
      AS first_output_date,
    MAX(it.txn_date) AS last_txn_date
  FROM inventory_transactions it
  WHERE it.product_id IS NOT NULL
    AND it.material_id IS NULL
    AND it.lot_number IS NOT NULL
    AND it.txn_type IN ('PROD_OUTPUT', 'ISSUE')
  GROUP BY it.product_id, it.lot_number
)
SELECT
  lt.product_id,
  p.pn,
  p.customer,
  lt.lot_number,
  lt.produced_qty,
  lt.issued_qty,
  lt.produced_qty - lt.issued_qty AS remain_qty,
  lt.first_output_date,
  lt.last_txn_date,
  -- 특채 포함 여부 (해당 작업지시의 특채 수량)
  COALESCE(w.tokusai_qty, 0) AS tokusai_qty,
  w.w_lot AS material_lot
FROM lot_txn lt
JOIN products p ON p.product_id = lt.product_id
LEFT JOIN wo_tracking w ON w.wo_number = lt.lot_number
                       AND w.product_id = lt.product_id;

COMMENT ON VIEW product_lot_stock_v IS
  '제품 LOT(작업지시NO)별 완성 재고 — remain_qty>0 이 출고 가능분. '
  'first_output_date 오름차순이 선입선출 순서. 소재 LOT(W번호)까지 연결';
