-- 마이그레이션 #2: 수주 (Sales Order) 테이블
-- Supabase SQL Editor에서 1번만 실행

-- 수주 헤더
CREATE TABLE IF NOT EXISTS sales_orders (
  so_id SERIAL PRIMARY KEY,
  so_number TEXT NOT NULL,                    -- 거래처 발주번호 (G263130685, 202605080006, MJT-PO26-우성-414)
  customer TEXT NOT NULL,                     -- HDX / 미진정밀 / ㈜엠제이티 등
  vendor_id INTEGER REFERENCES vendors(vendor_id),
  so_date DATE,                               -- 수주일자 (거래처가 발주한 날짜)
  due_date DATE,                              -- 납기 (가장 이른 품목 기준)
  total_amount NUMERIC DEFAULT 0,
  vat NUMERIC DEFAULT 0,
  status TEXT DEFAULT 'DRAFT',                -- DRAFT/CONFIRMED/IN_PROD/PARTIAL/DELIVERED/CANCELLED
  source TEXT,                                -- MANUAL/HDX_EXCEL/MIJIN_EXCEL/MJT_PDF/...
  source_file TEXT,                           -- 업로드한 원본 파일명
  delivery_address TEXT,                      -- 납품처 주소
  delivery_contact TEXT,                      -- 납품처 담당자
  remark TEXT,
  created_by TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(so_number, customer)                 -- 같은 거래처에 같은 발주번호 중복 X
);
CREATE INDEX IF NOT EXISTS idx_so_number ON sales_orders(so_number);
CREATE INDEX IF NOT EXISTS idx_so_customer ON sales_orders(customer);
CREATE INDEX IF NOT EXISTS idx_so_date ON sales_orders(so_date);
CREATE INDEX IF NOT EXISTS idx_so_status ON sales_orders(status);

-- 수주 품목
CREATE TABLE IF NOT EXISTS sales_order_items (
  soi_id SERIAL PRIMARY KEY,
  so_id INTEGER NOT NULL REFERENCES sales_orders(so_id) ON DELETE CASCADE,
  line_no INTEGER NOT NULL,                   -- HDX 항번 / 미진 작업지시 순번 / PDF 라인
  customer_part_no TEXT,                      -- 거래처 자재코드 (HDX의 HA50-80110 등)
  customer_item_name TEXT,                    -- 거래처 표기 자재명 (HDX의 "허브 로크 너트")
  product_id TEXT REFERENCES products(product_id),  -- 우성정밀 product_id (자동 매칭)
  canonical_pn TEXT,                          -- 우성정밀 품번 (매칭 결과)
  qty NUMERIC NOT NULL,
  received_qty NUMERIC DEFAULT 0,             -- 누적 납품 수량
  pending_qty NUMERIC,                        -- 미납 수량 (qty - received_qty)
  unit TEXT DEFAULT 'EA',
  unit_price NUMERIC,
  amount NUMERIC,
  vat NUMERIC,
  total NUMERIC,
  due_date DATE,                              -- 품목별 납기 (헤더와 다를 수 있음)
  customer_lot TEXT,                          -- 고객사 LOT 번호 (있으면)
  mes_work_order TEXT,                        -- MES 작업지시번호 (미진 등)
  status TEXT DEFAULT 'PENDING',              -- PENDING/IN_PROD/PARTIAL/DELIVERED
  remark TEXT,
  raw_row JSONB,                              -- 원본 행 데이터 보존 (감사용)
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_soi_so ON sales_order_items(so_id);
CREATE INDEX IF NOT EXISTS idx_soi_product ON sales_order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_soi_status ON sales_order_items(status);

-- 고객사별 자재코드 ↔ 우성정밀 품번 매핑 (HDX 같이 자체 코드 쓰는 곳)
CREATE TABLE IF NOT EXISTS customer_part_mapping (
  mapping_id SERIAL PRIMARY KEY,
  customer TEXT NOT NULL,                     -- HDX / 미진 / DIC 등
  customer_part_no TEXT NOT NULL,             -- 거래처 자재코드
  product_id TEXT NOT NULL REFERENCES products(product_id),
  canonical_pn TEXT NOT NULL,
  customer_item_name TEXT,
  verified BOOLEAN DEFAULT FALSE,             -- 사용자 검증 여부
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(customer, customer_part_no)
);
CREATE INDEX IF NOT EXISTS idx_cpm_customer_part ON customer_part_mapping(customer, customer_part_no);

-- 수주 통계 view
CREATE OR REPLACE VIEW sales_order_stats AS
SELECT
  so.so_id,
  so.so_number,
  so.customer,
  so.so_date,
  so.due_date,
  so.status,
  so.total_amount,
  COUNT(soi.soi_id) AS item_count,
  SUM(soi.qty) AS total_qty,
  SUM(soi.received_qty) AS total_received_qty,
  SUM(soi.qty - COALESCE(soi.received_qty, 0)) AS total_pending_qty,
  CASE
    WHEN SUM(COALESCE(soi.received_qty, 0)) = 0 THEN '미납'
    WHEN SUM(soi.qty - COALESCE(soi.received_qty, 0)) = 0 THEN '완납'
    ELSE '부분납'
  END AS delivery_status,
  -- 매칭률
  ROUND(100.0 * COUNT(soi.product_id) / NULLIF(COUNT(soi.soi_id), 0), 1) AS match_rate_pct
FROM sales_orders so
LEFT JOIN sales_order_items soi ON soi.so_id = so.so_id
GROUP BY so.so_id;
