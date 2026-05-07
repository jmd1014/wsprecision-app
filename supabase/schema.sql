-- 우성정밀 업무관리 DB 스키마 v1
-- Supabase PostgreSQL용. SQL Editor에 그대로 붙여넣어 실행.

-- ════════════════════════════════════════════════
-- 마스터 테이블 (앱이 권위)
-- ════════════════════════════════════════════════

-- 제품 마스터
CREATE TABLE IF NOT EXISTS products (
  product_id TEXT PRIMARY KEY,           -- P0001 등
  pn TEXT NOT NULL UNIQUE,                -- 표준 품번
  alias_list TEXT,                        -- 콤마 구분
  drawing_no TEXT,
  sub_class TEXT,
  product_group TEXT,
  material TEXT,
  procurement_type TEXT,                  -- 도급/사급
  procurement_start_date DATE,
  procurement_prev_type TEXT,
  raw_material_name TEXT,
  raw_material_spec TEXT,
  customer TEXT,
  active TEXT,
  caution TEXT,
  abc_grade TEXT,
  activity_trend TEXT,
  -- 집계 컬럼 (DB sync로 자동 채움)
  sales_count INTEGER DEFAULT 0,
  total_qty NUMERIC DEFAULT 0,
  total_sales NUMERIC DEFAULT 0,
  avg_unit_price NUMERIC DEFAULT 0,
  recent_unit_price NUMERIC DEFAULT 0,
  last_trade_date DATE,
  sales_count_12m INTEGER DEFAULT 0,
  total_sales_12m NUMERIC DEFAULT 0,
  -- 원가
  material_kg_price NUMERIC,
  material_unit_price NUMERIC,
  estimated_cost_per_pc NUMERIC,
  margin_pct NUMERIC,
  cost_data_quality TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_products_pn ON products(pn);
CREATE INDEX IF NOT EXISTS idx_products_active ON products(active);

-- 거래처 마스터
CREATE TABLE IF NOT EXISTS vendors (
  vendor_id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  normalized_name TEXT NOT NULL,
  business_no TEXT UNIQUE,
  trade_type TEXT,                        -- 매입/매출/혼합
  category TEXT,                          -- CUSTOMER/MATERIAL_STS/...
  ceo_name TEXT,
  phone TEXT,
  fax TEXT,
  address TEXT,
  email TEXT,
  business_type TEXT,
  business_item TEXT,
  payment_terms TEXT,
  contact_person TEXT,
  contact_phone TEXT,
  receivable NUMERIC DEFAULT 0,
  payable NUMERIC DEFAULT 0,
  in_use BOOLEAN DEFAULT TRUE,
  memo TEXT,
  verification_status TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_vendors_norm ON vendors(normalized_name);
CREATE INDEX IF NOT EXISTS idx_vendors_category ON vendors(category);

-- 자재 마스터
CREATE TABLE IF NOT EXISTS materials (
  material_id TEXT PRIMARY KEY,           -- M001 등
  raw_name TEXT NOT NULL,
  material_type TEXT,                     -- SUS304 등
  spec TEXT,                              -- φ45*16L
  procurement_type TEXT,
  stock_qty NUMERIC DEFAULT 0,
  in_use TEXT DEFAULT '사용',
  main_supplier TEXT,
  recent_kg_price NUMERIC,
  recent_unit_price NUMERIC,
  unit TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_materials_type_spec ON materials(material_type, spec);

-- BOM (제품-자재 매핑)
CREATE TABLE IF NOT EXISTS bom (
  bom_id SERIAL PRIMARY KEY,
  product_id TEXT NOT NULL REFERENCES products(product_id),
  material_id TEXT REFERENCES materials(material_id),
  raw_material_name TEXT,
  qty_per_pc NUMERIC DEFAULT 1,
  shared_factor NUMERIC DEFAULT 1,        -- 1자재당 N제품 (소재 분할)
  source TEXT,
  match_basis TEXT,
  apply_start_date DATE,
  apply_end_date DATE,
  verification_status TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_bom_product ON bom(product_id);
CREATE INDEX IF NOT EXISTS idx_bom_material ON bom(material_id);

-- 도면 마스터
CREATE TABLE IF NOT EXISTS drawings (
  drawing_id SERIAL PRIMARY KEY,
  customer TEXT,
  pn TEXT,
  revision NUMERIC,
  revision_status TEXT,
  filename TEXT,
  file_ext TEXT,
  file_size_kb NUMERIC,
  modified_date DATE,
  file_url TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_drawings_pn ON drawings(pn);

-- ════════════════════════════════════════════════
-- 트랜잭션 테이블 (앱이 생성)
-- ════════════════════════════════════════════════

-- 발주서
CREATE TABLE IF NOT EXISTS purchase_orders (
  po_id SERIAL PRIMARY KEY,
  po_number TEXT UNIQUE NOT NULL,         -- PO-202605-001 등
  vendor_id INTEGER REFERENCES vendors(vendor_id),
  po_date DATE NOT NULL,
  delivery_date DATE,
  total_amount NUMERIC,
  vat NUMERIC,
  payment_terms TEXT,
  delivery_address TEXT,
  contact_person TEXT,
  status TEXT DEFAULT 'DRAFT',            -- DRAFT/SENT/RECEIVED/CANCELLED
  pdf_url TEXT,
  slack_message_ts TEXT,
  created_by TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  sent_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS purchase_order_items (
  poi_id SERIAL PRIMARY KEY,
  po_id INTEGER NOT NULL REFERENCES purchase_orders(po_id) ON DELETE CASCADE,
  line_no INTEGER NOT NULL,
  item_name TEXT NOT NULL,
  spec TEXT,
  qty NUMERIC NOT NULL,
  unit TEXT,
  unit_price NUMERIC NOT NULL,
  amount NUMERIC NOT NULL,
  remark TEXT
);

-- ════════════════════════════════════════════════
-- 거래 ledger (구글시트에서 sync)
-- ════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS sales_ledger (
  ledger_id SERIAL PRIMARY KEY,
  voucher_no INTEGER,
  voucher_date DATE,
  item_date DATE,
  customer TEXT,
  item TEXT,
  spec TEXT,
  qty NUMERIC,
  unit TEXT,
  unit_price NUMERIC,
  amount NUMERIC,
  vat NUMERIC,
  total NUMERIC,
  remark TEXT,
  trade_subtype TEXT,
  -- 정규화 컬럼
  canonical_pn TEXT,
  product_id TEXT,
  synced_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sales_canonical ON sales_ledger(canonical_pn);
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales_ledger(item_date);

CREATE TABLE IF NOT EXISTS purchase_ledger (
  ledger_id SERIAL PRIMARY KEY,
  trade_date DATE,
  vendor TEXT,
  item TEXT,
  unit TEXT,
  qty NUMERIC,
  weight NUMERIC,
  unit_price NUMERIC,
  amount NUMERIC,
  vat NUMERIC,
  total NUMERIC,
  remark TEXT,
  -- 정규화 컬럼
  category TEXT,
  vendor_normalized TEXT,
  kg_price NUMERIC,
  ea_price NUMERIC,
  matched_pn TEXT,
  synced_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_purchase_vendor ON purchase_ledger(vendor_normalized);
CREATE INDEX IF NOT EXISTS idx_purchase_date ON purchase_ledger(trade_date);

-- ════════════════════════════════════════════════
-- 생산 데이터 (구글시트에서 sync)
-- ════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS production_plan (
  plan_id SERIAL PRIMARY KEY,
  plan_date DATE NOT NULL,
  machine TEXT NOT NULL,
  process TEXT,                           -- 품번#10 형식
  pn TEXT,
  process_step INTEGER,                   -- 10/20/30
  shift TEXT,                             -- 주간/야간/특근
  synced_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS production_log (
  log_id SERIAL PRIMARY KEY,
  log_date DATE NOT NULL,
  shift TEXT,                             -- 주간/야간/특근
  worker TEXT,
  machine TEXT,
  process TEXT,
  pn TEXT,
  process_step INTEGER,
  cycle_time NUMERIC,
  total_qty NUMERIC,
  defect_qty NUMERIC,
  uptime_hours NUMERIC,
  uph_target NUMERIC,
  uph_actual NUMERIC,
  efficiency_pct NUMERIC,
  remark TEXT,
  synced_at TIMESTAMPTZ DEFAULT NOW()
);

-- ════════════════════════════════════════════════
-- 운영 메타
-- ════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS sync_log (
  sync_id SERIAL PRIMARY KEY,
  source TEXT,                            -- sales/purchase/production
  rows_inserted INTEGER,
  rows_updated INTEGER,
  status TEXT,
  error_message TEXT,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS app_users (
  user_id SERIAL PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  display_name TEXT,
  role TEXT,                              -- admin/po/production/erp/viewer
  is_active BOOLEAN DEFAULT TRUE,
  last_login TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 변경 이력 (마스터 수정 추적)
CREATE TABLE IF NOT EXISTS master_change_log (
  log_id SERIAL PRIMARY KEY,
  table_name TEXT NOT NULL,
  record_id TEXT NOT NULL,
  field_name TEXT,
  old_value TEXT,
  new_value TEXT,
  changed_by TEXT,
  changed_at TIMESTAMPTZ DEFAULT NOW(),
  reason TEXT
);
