-- ════════════════════════════════════════════════════════════
-- 복구: 운영 ledger(supabase_migrations.schema_migrations) 에서 추출 2026-10-23 — 원본 파일 커밋 없음 (P1-5)
-- version: 20260820070718  name: 043_po_line_level_close
-- ════════════════════════════════════════════════════════════
-- 043: 발주 잔량 종결을 라인(제품) 단위로
-- 제품별로 협의 종결 판단이 이뤄지므로 poi.closed_at 로 라인 종결.
-- 발주 헤더 CLOSED 는 유지 (전 라인 종결 시 자동 승격은 앱에서).
alter table purchase_order_items
  add column if not exists closed_at timestamptz;

drop view if exists po_item_receipt_v;
create view po_item_receipt_v
with (security_invoker = true) as
 SELECT poi.poi_id,
    poi.po_id,
    po.po_number,
    po.status AS po_status,
    poi.line_no,
    poi.item_name,
    poi.spec,
    poi.qty AS ordered_qty,
    poi.unit,
    poi.material_id,
    m.raw_name AS material_name,
    COALESCE(r.received, 0::numeric) AS received_qty,
        CASE
            WHEN po.status = ANY (ARRAY['CLOSED'::text, 'CANCELLED'::text])
                 OR poi.closed_at IS NOT NULL THEN 0::numeric
            ELSE GREATEST(poi.qty - COALESCE(r.received, 0::numeric), 0::numeric)
        END AS pending_qty,
        CASE
            WHEN (po.status = 'CLOSED'::text OR poi.closed_at IS NOT NULL)
                 AND COALESCE(r.received, 0::numeric) < poi.qty THEN 'CLOSED'::text
            WHEN COALESCE(r.received, 0::numeric) <= 0::numeric THEN 'PENDING'::text
            WHEN COALESCE(r.received, 0::numeric) >= poi.qty THEN 'RECEIVED'::text
            ELSE 'PARTIAL'::text
        END AS receipt_status,
    r.last_receipt_date,
    poi.closed_at
   FROM purchase_order_items poi
     LEFT JOIN purchase_orders po ON po.po_id = poi.po_id
     LEFT JOIN materials m ON m.material_id = poi.material_id
     LEFT JOIN ( SELECT inventory_transactions.ref_id,
            sum(inventory_transactions.qty) AS received,
            max(inventory_transactions.txn_date) AS last_receipt_date
           FROM inventory_transactions
          WHERE inventory_transactions.txn_type = 'RECEIPT'::text
            AND inventory_transactions.ref_table = 'purchase_order_items'::text
          GROUP BY inventory_transactions.ref_id) r ON r.ref_id = poi.poi_id;
