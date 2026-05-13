-- ════════════════════════════════════════════════════════════
-- Migration 006: pending_qty 계산을 view로 (중복 저장 제거)
-- ════════════════════════════════════════════════════════════
-- 문제:
--   sales_order_items.pending_qty가 (qty - received_qty)와 중복 저장됨.
--   received_qty 업데이트 시 pending_qty가 자동 갱신 안 되어 불일치 가능.
--
-- 해결:
--   기존 pending_qty 컬럼은 유지(legacy, 호환성), 신규 view에서 계산값 제공.
--   앱 화면은 view 우선 사용.
-- ════════════════════════════════════════════════════════════

-- 1. legacy 표시
COMMENT ON COLUMN sales_order_items.pending_qty IS
    'LEGACY: 신규 로직에서는 sales_order_items_v.pending_qty (계산값) 사용 권장.';


-- 2. 계산 컬럼 포함 view
CREATE OR REPLACE VIEW sales_order_items_v AS
SELECT
    soi.soi_id,
    soi.so_id,
    soi.line_no,
    soi.customer_part_no,
    soi.customer_item_name,
    soi.product_id,
    soi.canonical_pn,
    soi.qty,
    COALESCE(soi.received_qty, 0)                                            AS received_qty,
    GREATEST(soi.qty - COALESCE(soi.received_qty, 0), 0)                     AS pending_qty_calc,
    CASE
        WHEN COALESCE(soi.received_qty, 0) = 0      THEN 'PENDING'
        WHEN soi.received_qty >= soi.qty            THEN 'DELIVERED'
        ELSE 'PARTIAL'
    END                                                                       AS computed_status,
    soi.unit,
    soi.unit_price,
    soi.amount,
    soi.vat,
    soi.total,
    soi.due_date,
    soi.customer_lot,
    soi.mes_work_order,
    soi.status                                                                AS status_stored,
    soi.remark,
    soi.created_at
FROM sales_order_items soi;


-- 3. sales_order_stats view 재정의 — pending_qty_calc 기반
CREATE OR REPLACE VIEW sales_order_stats AS
SELECT
    so.so_id,
    so.so_number,
    so.customer,
    so.so_date,
    so.due_date,
    so.status,
    so.total_amount,
    COUNT(soi.soi_id)                                              AS item_count,
    SUM(soi.qty)                                                    AS total_qty,
    SUM(COALESCE(soi.received_qty, 0))                              AS total_received_qty,
    SUM(GREATEST(soi.qty - COALESCE(soi.received_qty, 0), 0))       AS total_pending_qty,
    CASE
        WHEN SUM(COALESCE(soi.received_qty, 0)) = 0            THEN '미납'
        WHEN SUM(GREATEST(soi.qty - COALESCE(soi.received_qty, 0), 0)) = 0 THEN '완납'
        ELSE '부분납'
    END                                                              AS delivery_status,
    ROUND(100.0 * COUNT(soi.product_id) / NULLIF(COUNT(soi.soi_id), 0), 1) AS match_rate_pct
FROM sales_orders so
LEFT JOIN sales_order_items soi ON soi.so_id = so.so_id
GROUP BY so.so_id;
