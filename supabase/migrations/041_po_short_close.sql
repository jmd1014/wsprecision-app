-- ════════════════════════════════════════════════════════════
-- 복구: 운영 ledger(supabase_migrations.schema_migrations) 에서 추출 2026-10-23 — 원본 파일 커밋 없음 (P1-5)
-- version: 20260820010243  name: 041_po_short_close
-- ════════════════════════════════════════════════════════════
-- Migration 041: 발주 부분 종결 (short-close)
-- 협의로 잔량 없이 발주를 끝내는 경우(90개 중 89개 입고 등):
-- 발주 status='CLOSED' 로 표시하면 뷰가 잔량을 0으로 계산해
-- 입고 대기에서 사라진다. 발주 수량(문서)과 입고 원장은 그대로 보존.
CREATE OR REPLACE VIEW po_item_receipt_v WITH (security_invoker = true) AS
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
    CASE WHEN po.status IN ('CLOSED', 'CANCELLED') THEN 0::numeric
         ELSE GREATEST(poi.qty - COALESCE(r.received, 0::numeric),
                       0::numeric)
    END AS pending_qty,
    CASE
        WHEN po.status = 'CLOSED'
             AND COALESCE(r.received, 0::numeric) < poi.qty
            THEN 'CLOSED'::text
        WHEN COALESCE(r.received, 0::numeric) <= 0::numeric
            THEN 'PENDING'::text
        WHEN COALESCE(r.received, 0::numeric) >= poi.qty
            THEN 'RECEIVED'::text
        ELSE 'PARTIAL'::text
    END AS receipt_status,
    r.last_receipt_date
   FROM purchase_order_items poi
     LEFT JOIN purchase_orders po ON po.po_id = poi.po_id
     LEFT JOIN materials m ON m.material_id = poi.material_id
     LEFT JOIN ( SELECT ref_id, sum(qty) AS received,
                        max(txn_date) AS last_receipt_date
                   FROM inventory_transactions
                  WHERE txn_type = 'RECEIPT'
                    AND ref_table = 'purchase_order_items'
                  GROUP BY ref_id) r ON r.ref_id = poi.poi_id;
