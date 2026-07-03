-- ════════════════════════════════════════════════════════════
-- Migration 017: Phase A — 소재 입고 (발주 → 입고 → 실재고)
-- ════════════════════════════════════════════════════════════
-- 배경:
--   go-live 로드맵 Phase A. 발주 라인의 입고를 inventory_transactions
--   (RECEIPT) 로 기록하고, 실재고를 기초재고 + 거래 누적으로 계산.
--
-- 변경 내용:
--   1. purchase_order_items.material_id — 발주 라인 ↔ 자재 매핑
--      (입고 시 한 번 지정하면 재사용. 원장 기록의 필수 키)
--   2. po_item_receipt_v — 발주 라인별 입고 현황 (원장 집계, 저장 X)
--   3. material_stock 재정의 — current_stock = 기초(stock_qty) + 거래 SUM
--      (기존: 거래 SUM 만 → 기초재고 96건 164,454 EA 반영 안 되던 문제)
--
-- 원칙:
--   - 입고량은 inventory_transactions 원장이 단일 진실원천
--   - purchase_order_items 에 received_qty 저장 안 함 (pending_qty 교훈)
--   - 비파괴 / 멱등
--
-- 적용 후 검증:
--   SELECT * FROM po_item_receipt_v LIMIT 5;
--   SELECT current_stock, baseline_qty FROM material_stock
--     WHERE baseline_qty > 0 LIMIT 5;
-- ════════════════════════════════════════════════════════════

-- 1. 발주 라인 ↔ 자재 매핑 키
ALTER TABLE purchase_order_items
  ADD COLUMN IF NOT EXISTS material_id TEXT REFERENCES materials(material_id);

CREATE INDEX IF NOT EXISTS idx_poi_material ON purchase_order_items(material_id);

COMMENT ON COLUMN purchase_order_items.material_id IS
  '자재 마스터 매핑. 입고 처리 시 지정 (한 번 지정하면 재입고 시 재사용).';


-- 2. 발주 라인별 입고 현황 view (원장 집계)
CREATE OR REPLACE VIEW po_item_receipt_v AS
SELECT
  poi.poi_id,
  poi.po_id,
  po.po_number,
  po.status                                            AS po_status,
  poi.line_no,
  poi.item_name,
  poi.spec,
  poi.qty                                              AS ordered_qty,
  poi.unit,
  poi.material_id,
  m.raw_name                                           AS material_name,
  COALESCE(r.received, 0)                              AS received_qty,
  GREATEST(poi.qty - COALESCE(r.received, 0), 0)       AS pending_qty,
  CASE
    WHEN COALESCE(r.received, 0) <= 0                  THEN 'PENDING'
    WHEN COALESCE(r.received, 0) >= poi.qty            THEN 'RECEIVED'
    ELSE 'PARTIAL'
  END                                                  AS receipt_status,
  r.last_receipt_date
FROM purchase_order_items poi
LEFT JOIN purchase_orders po ON po.po_id = poi.po_id
LEFT JOIN materials m ON m.material_id = poi.material_id
LEFT JOIN (
  SELECT ref_id,
         SUM(qty)          AS received,
         MAX(txn_date)     AS last_receipt_date
  FROM inventory_transactions
  WHERE txn_type = 'RECEIPT'
    AND ref_table = 'purchase_order_items'
  GROUP BY ref_id
) r ON r.ref_id = poi.poi_id;

COMMENT ON VIEW po_item_receipt_v IS
  '발주 라인별 입고 현황. received_qty 는 inventory_transactions 원장 집계 (저장 안 함).';


-- 3. material_stock 재정의 — 기초재고 반영
--    (003 정의와 컬럼 순서/타입 동일 + 끝에 baseline_qty 추가 → OR REPLACE 안전)
CREATE OR REPLACE VIEW material_stock AS
SELECT
    m.material_id,
    m.raw_name,
    m.material_type,
    m.spec,
    m.unit,
    m.main_supplier,
    COALESCE(m.stock_qty, 0) + COALESCE(SUM(it.qty), 0)  AS current_stock,
    COALESCE(SUM(CASE WHEN it.txn_type = 'RECEIPT'    THEN it.qty ELSE 0 END), 0) AS total_received,
    COALESCE(SUM(CASE WHEN it.txn_type = 'PROD_INPUT' THEN it.qty ELSE 0 END), 0) AS total_consumed,
    COALESCE(SUM(CASE WHEN it.txn_type = 'DEFECT'     THEN it.qty ELSE 0 END), 0) AS total_defect,
    MAX(it.txn_date)                  AS last_txn_date,
    COUNT(it.txn_id)                  AS txn_count,
    COALESCE(m.stock_qty, 0)          AS baseline_qty
FROM materials m
LEFT JOIN inventory_transactions it USING (material_id)
GROUP BY m.material_id, m.raw_name, m.material_type, m.spec, m.unit,
         m.main_supplier, m.stock_qty;

COMMENT ON VIEW material_stock IS
  '실재고 = 기초재고(materials.stock_qty, import 스냅샷) + inventory_transactions 누적.';
