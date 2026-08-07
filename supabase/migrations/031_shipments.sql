-- 031_shipments.sql (2026-08-07)
-- 출고 전표 — 장바구니식 출하 흐름의 영속 단위.
-- 등록(DRAFT) → 현장 확인·정정 → 확정(CONFIRMED: 수주 반영·재고
-- 차감·거래명세서 발행). 발행 문서는 전표에서 언제든 재발행.
CREATE TABLE IF NOT EXISTS shipments (
  shipment_id serial PRIMARY KEY,
  ship_no text UNIQUE NOT NULL,          -- SH-YYYYMMDD-NN
  ship_date date NOT NULL,
  status text NOT NULL DEFAULT 'DRAFT'
    CHECK (status IN ('DRAFT','CONFIRMED','CANCELLED')),
  remark text,
  created_by text,
  created_at timestamptz DEFAULT now(),
  confirmed_at timestamptz
);
CREATE TABLE IF NOT EXISTS shipment_items (
  si_id serial PRIMARY KEY,
  shipment_id int NOT NULL REFERENCES shipments(shipment_id)
    ON DELETE CASCADE,
  soi_id int REFERENCES sales_order_items(soi_id),
  so_id int,
  sched_id int,
  product_id text,
  pn text,
  customer_pn text,                      -- 거래처 ERP 표기 (명세서 품명)
  item_name text,
  customer text,
  so_number text,
  qty numeric NOT NULL,
  unit text DEFAULT 'EA',
  unit_price numeric
);
CREATE INDEX IF NOT EXISTS idx_shipments_date ON shipments (ship_date);
CREATE INDEX IF NOT EXISTS idx_shipment_items_sid
  ON shipment_items (shipment_id);
