-- ════════════════════════════════════════════════════════════
-- 복구: 운영 ledger(supabase_migrations.schema_migrations) 에서 추출 2026-10-23 — 원본 파일 커밋 없음 (P1-5)
-- version: 20260911035515  name: 061_lot_stock_material_lot_fallback
-- ════════════════════════════════════════════════════════════
-- 061: 완성 LOT 잔량 뷰 — 배치 없는 LOT(기초 재고 OB·실사 조정)도 원장 work_order 에
-- 적은 소재 LOT(W번호, 히트 추적)을 material_lot 로 보여준다 (2026-09-11 품목별 기점 실사 방침)
create or replace view product_lot_stock_v with (security_invoker = true) as
 WITH lot_txn AS (
         SELECT it.product_id,
            it.lot_number,
            sum(CASE WHEN it.txn_type = 'PROD_OUTPUT'::text THEN it.qty ELSE 0::numeric END) AS produced_qty,
            sum(CASE WHEN it.txn_type = 'ISSUE'::text THEN - it.qty ELSE 0::numeric END) AS issued_qty,
            sum(CASE WHEN it.txn_type = 'ADJUSTMENT'::text THEN it.qty ELSE 0::numeric END) AS adjust_qty,
            min(it.txn_date) FILTER (WHERE it.txn_type = ANY (ARRAY['PROD_OUTPUT'::text, 'ADJUSTMENT'::text])) AS first_output_date,
            max(it.txn_date) AS last_txn_date,
            min(it.work_order) FILTER (WHERE it.work_order IS NOT NULL AND it.work_order ~ '^W[0-9]') AS wo_material_lot
           FROM inventory_transactions it
          WHERE it.product_id IS NOT NULL AND it.material_id IS NULL AND it.lot_number IS NOT NULL AND (it.txn_type = ANY (ARRAY['PROD_OUTPUT'::text, 'ISSUE'::text, 'ADJUSTMENT'::text]))
          GROUP BY it.product_id, it.lot_number
        )
 SELECT lt.product_id,
    p.pn,
    p.customer,
    lt.lot_number,
    lt.produced_qty,
    lt.issued_qty,
    lt.produced_qty + lt.adjust_qty - lt.issued_qty AS remain_qty,
    lt.first_output_date,
    lt.last_txn_date,
    COALESCE(w.tokusai_qty, 0::numeric) AS tokusai_qty,
    COALESCE(w.w_lot, lt.wo_material_lot) AS material_lot,
    lt.adjust_qty
   FROM lot_txn lt
     JOIN products p ON p.product_id = lt.product_id
     LEFT JOIN wo_tracking w ON w.wo_number = lt.lot_number AND w.product_id = lt.product_id;
