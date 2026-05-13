-- ════════════════════════════════════════════════════════════
-- Migration 004: status 컬럼 CHECK 제약 추가
-- ════════════════════════════════════════════════════════════
-- 목적: 상태값 오타 / 잘못된 값 방지
--
-- 적용 전 확인 사항 (앱 코드에서 사용하는 status 값):
--   sales_orders.status        : DRAFT / CONFIRMED / IN_PROD / PARTIAL / DELIVERED / CANCELLED
--   sales_order_items.status   : PENDING / IN_PROD / PARTIAL / DELIVERED / CANCELLED
--   purchase_orders.status     : DRAFT / SENT / RECEIVED / CANCELLED
--
-- 멱등 처리: DROP CONSTRAINT IF EXISTS 후 ADD
-- ════════════════════════════════════════════════════════════

-- sales_orders
ALTER TABLE sales_orders DROP CONSTRAINT IF EXISTS chk_so_status;
ALTER TABLE sales_orders
  ADD CONSTRAINT chk_so_status
  CHECK (status IN ('DRAFT', 'CONFIRMED', 'IN_PROD', 'PARTIAL', 'DELIVERED', 'CANCELLED'));

-- sales_order_items
ALTER TABLE sales_order_items DROP CONSTRAINT IF EXISTS chk_soi_status;
ALTER TABLE sales_order_items
  ADD CONSTRAINT chk_soi_status
  CHECK (status IN ('PENDING', 'IN_PROD', 'PARTIAL', 'DELIVERED', 'CANCELLED'));

-- purchase_orders
ALTER TABLE purchase_orders DROP CONSTRAINT IF EXISTS chk_po_status;
ALTER TABLE purchase_orders
  ADD CONSTRAINT chk_po_status
  CHECK (status IN ('DRAFT', 'SENT', 'RECEIVED', 'PARTIAL', 'CANCELLED'));
  -- PARTIAL: 일부 입고 (purchase 측에도 부분 입고 가능성 대비)
