-- 030_product_lot_stock_include_adjustment.sql
-- 완성재고 실사 조정(ADJUSTMENT)도 LOT 재고에 잡히게 한다 (2026-07-31).
--
-- 마스터 → 품번별 맞추기에서 실사 수량으로 완성재고를 조정할 때
-- ADJUSTMENT 원장에 LOT(ADJ-YYYYMMDD)을 부여한다. 이 뷰가 그 LOT을
-- 포함해야 출고 선입선출 배분이 조정분까지 정상 동작한다.
-- 생산 실적(produced_qty)과는 분리해 adjust_qty 로 따로 집계.
CREATE OR REPLACE VIEW product_lot_stock_v AS
WITH lot_txn AS (
  SELECT it.product_id, it.lot_number,
    sum(CASE WHEN it.txn_type = 'PROD_OUTPUT' THEN it.qty ELSE 0 END) AS produced_qty,
    sum(CASE WHEN it.txn_type = 'ISSUE' THEN -it.qty ELSE 0 END) AS issued_qty,
    sum(CASE WHEN it.txn_type = 'ADJUSTMENT' THEN it.qty ELSE 0 END) AS adjust_qty,
    min(it.txn_date) FILTER (
      WHERE it.txn_type IN ('PROD_OUTPUT', 'ADJUSTMENT')) AS first_output_date,
    max(it.txn_date) AS last_txn_date
  FROM inventory_transactions it
  WHERE it.product_id IS NOT NULL AND it.material_id IS NULL
    AND it.lot_number IS NOT NULL
    AND it.txn_type IN ('PROD_OUTPUT', 'ISSUE', 'ADJUSTMENT')
  GROUP BY it.product_id, it.lot_number)
SELECT lt.product_id, p.pn, p.customer, lt.lot_number,
       lt.produced_qty, lt.issued_qty,
       lt.produced_qty + lt.adjust_qty - lt.issued_qty AS remain_qty,
       lt.first_output_date, lt.last_txn_date,
       COALESCE(w.tokusai_qty, 0::numeric) AS tokusai_qty,
       w.w_lot AS material_lot,
       lt.adjust_qty
FROM lot_txn lt
JOIN products p ON p.product_id = lt.product_id
LEFT JOIN wo_tracking w ON w.wo_number = lt.lot_number
                       AND w.product_id = lt.product_id;
