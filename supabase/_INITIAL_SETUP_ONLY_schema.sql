-- 우성정밀 업무관리 DB 스키마 v2
-- 정책: 마스터는 정적 정보만, 자동집계는 view로 분리, 휴면 제품은 archived_at으로 일상 화면 비표시
-- Supabase PostgreSQL용. SQL Editor에 그대로 붙여넣어 실행.
-- (CREATE TABLE/VIEW는 IF NOT EXISTS / OR REPLACE 사용 — 멱등 실행)

-- ════════════════════════════════════════════════
-- 0. (선택) 기존 v1 테이블이 있으면 정리
-- ════════════════════════════════════════════════
-- 데이터 import 전이라면 안전하게 DROP 후 재생성
DROP VIEW IF EXISTS active_products CASCADE;
DROP VIEW IF EXISTS archived_products CASCADE;
DROP VIEW IF EXISTS product_stats CASCADE;
DROP VIEW IF EXISTS product_full CASCADE;
DROP VIEW IF EXISTS vendor_stats CASCADE;
DROP VIEW IF EXISTS material_stats CASCADE;

-- ════════════════════════════════════════════════
-- 1. 제품 마스터 (정적 정보만 — 38개 컬럼)
-- ════════════════════════════════════════════════
DROP TABLE IF EXISTS products CASCADE;
CREATE TABLE products (
  -- 식별자
  product_id TEXT PRIMARY KEY,
  pn TEXT NOT NULL UNIQUE,
  alias_list TEXT,                            -- 콤마 구분 alias
  drawing_no TEXT,
  -- 분류
  sub_class TEXT,
  product_group TEXT,
  -- 재질/규격 (소재 매입과 매칭)
  material TEXT,
  raw_material_name TEXT,
  raw_material_spec TEXT,
  -- 조달 (시점 분기 지원)
  procurement_type TEXT,                      -- 도급/사급
  procurement_start_date DATE,
  procurement_prev_type TEXT,
  -- 거래처 (주거래 고객사)
  customer TEXT,
  -- BOM 자재 정보 (정적, 주 자재 1개)
  bom_material_name TEXT,
  material_unit TEXT,                         -- KG/EA
  material_kg_price NUMERIC,
  material_unit_price NUMERIC,                -- 개당 단가
  material_purchase_count INTEGER,
  material_last_purchase_date TEXT,
  material_main_supplier TEXT,
  material_data_quality TEXT,
  -- 추정 원가 (정적 스냅샷, 정확한 값은 product_stats view)
  outsourcing_per_pc NUMERIC,
  heat_treat_per_pc NUMERIC,
  surface_per_pc NUMERIC,
  estimated_cost_per_pc NUMERIC,
  cost_data_quality TEXT,
  -- 운영
  active TEXT,
  caution TEXT,
  inference_basis TEXT,                       -- 추정근거
  -- 휴면 관리 (일상 화면 비표시)
  archived_at TIMESTAMPTZ,
  archive_reason TEXT,
  -- 메타
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_products_pn ON products(pn);
CREATE INDEX idx_products_archived ON products(archived_at);
CREATE INDEX idx_products_customer ON products(customer);
CREATE INDEX idx_products_group ON products(product_group);

-- ════════════════════════════════════════════════
-- 2. 거래처 마스터
-- ════════════════════════════════════════════════
DROP TABLE IF EXISTS vendors CASCADE;
CREATE TABLE vendors (
  vendor_id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  normalized_name TEXT NOT NULL,
  business_no TEXT UNIQUE,
  trade_type TEXT,                            -- 매입/매출/혼합
  category TEXT,                              -- CUSTOMER/MATERIAL_STS/...
  ceo_name TEXT,
  -- 운영 중 채울 컬럼 (지금은 비어있음)
  phone TEXT,
  fax TEXT,
  address TEXT,
  email TEXT,
  contact_person TEXT,
  contact_phone TEXT,
  -- 사업 정보
  business_type TEXT,
  business_item TEXT,
  payment_terms TEXT,
  in_use BOOLEAN DEFAULT TRUE,
  memo TEXT,
  verification_status TEXT,
  -- 발주 화면 필터용 대분류 (SALES_*/MAT_*/OUTSOURCE_*/HEAT_TREAT/SURFACE/TOOL/INDIRECT_*)
  vendor_group TEXT,
  -- 휴면 관리
  archived_at TIMESTAMPTZ,
  archive_reason TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_vendors_norm ON vendors(normalized_name);
CREATE INDEX idx_vendors_category ON vendors(category);
CREATE INDEX idx_vendors_group ON vendors(vendor_group);
CREATE INDEX idx_vendors_archived ON vendors(archived_at);

-- ════════════════════════════════════════════════
-- 3. 자재 마스터
-- ════════════════════════════════════════════════
DROP TABLE IF EXISTS materials CASCADE;
CREATE TABLE materials (
  material_id TEXT PRIMARY KEY,
  raw_name TEXT NOT NULL,
  material_type TEXT,
  spec TEXT,
  procurement_type TEXT,
  stock_qty NUMERIC DEFAULT 0,
  in_use TEXT DEFAULT '사용',
  main_supplier TEXT,
  unit TEXT,
  archived_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_materials_type_spec ON materials(material_type, spec);

-- ════════════════════════════════════════════════
-- 4. BOM (제품-자재 매핑, 시점 분기 지원)
-- ════════════════════════════════════════════════
DROP TABLE IF EXISTS bom CASCADE;
CREATE TABLE bom (
  bom_id SERIAL PRIMARY KEY,
  product_id TEXT NOT NULL REFERENCES products(product_id),
  material_id TEXT REFERENCES materials(material_id),
  raw_material_name TEXT,
  qty_per_pc NUMERIC DEFAULT 1,
  shared_factor NUMERIC DEFAULT 1,            -- 1자재당 N제품 (분할 가공)
  source TEXT,
  match_basis TEXT,
  apply_start_date DATE,
  apply_end_date DATE,
  verification_status TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_bom_product ON bom(product_id);
CREATE INDEX idx_bom_material ON bom(material_id);

-- ════════════════════════════════════════════════
-- 5. 도면 마스터 (빈 11번째 컬럼 제거됨 — 10컬럼)
-- ════════════════════════════════════════════════
DROP TABLE IF EXISTS drawings CASCADE;
CREATE TABLE drawings (
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
CREATE INDEX idx_drawings_pn ON drawings(pn);
CREATE INDEX idx_drawings_customer ON drawings(customer);

-- ════════════════════════════════════════════════
-- 6. 트랜잭션 — 발주서
-- ════════════════════════════════════════════════
DROP TABLE IF EXISTS purchase_order_items CASCADE;
DROP TABLE IF EXISTS purchase_orders CASCADE;
CREATE TABLE purchase_orders (
  po_id SERIAL PRIMARY KEY,
  po_number TEXT UNIQUE NOT NULL,
  vendor_id INTEGER REFERENCES vendors(vendor_id),
  po_date DATE NOT NULL,
  delivery_date DATE,
  total_amount NUMERIC,
  vat NUMERIC,
  payment_terms TEXT,
  delivery_address TEXT,
  contact_person TEXT,
  status TEXT DEFAULT 'DRAFT',
  pdf_url TEXT,
  slack_message_ts TEXT,
  created_by TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  sent_at TIMESTAMPTZ
);
CREATE TABLE purchase_order_items (
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
-- 7. 거래 ledger (구글시트에서 sync — 자동집계의 원천)
-- ════════════════════════════════════════════════
DROP TABLE IF EXISTS sales_ledger CASCADE;
CREATE TABLE sales_ledger (
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
  canonical_pn TEXT,
  product_id TEXT,
  synced_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_sales_canonical ON sales_ledger(canonical_pn);
CREATE INDEX idx_sales_date ON sales_ledger(item_date);
CREATE INDEX idx_sales_product ON sales_ledger(product_id);

DROP TABLE IF EXISTS purchase_ledger CASCADE;
CREATE TABLE purchase_ledger (
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
  category TEXT,
  vendor_normalized TEXT,
  kg_price NUMERIC,
  ea_price NUMERIC,
  matched_pn TEXT,
  synced_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_purchase_vendor ON purchase_ledger(vendor_normalized);
CREATE INDEX idx_purchase_date ON purchase_ledger(trade_date);
CREATE INDEX idx_purchase_pn ON purchase_ledger(matched_pn);

-- ════════════════════════════════════════════════
-- 8. 생산 데이터
-- ════════════════════════════════════════════════
DROP TABLE IF EXISTS production_plan CASCADE;
CREATE TABLE production_plan (
  plan_id SERIAL PRIMARY KEY,
  plan_date DATE NOT NULL,
  machine TEXT NOT NULL,
  process TEXT,
  pn TEXT,
  process_step INTEGER,
  shift TEXT,
  synced_at TIMESTAMPTZ DEFAULT NOW()
);

DROP TABLE IF EXISTS production_log CASCADE;
CREATE TABLE production_log (
  log_id SERIAL PRIMARY KEY,
  log_date DATE NOT NULL,
  shift TEXT,
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
CREATE INDEX idx_prodlog_pn ON production_log(pn);
CREATE INDEX idx_prodlog_date ON production_log(log_date);

-- ════════════════════════════════════════════════
-- 9. 운영 메타
-- ════════════════════════════════════════════════
DROP TABLE IF EXISTS sync_log CASCADE;
CREATE TABLE sync_log (
  sync_id SERIAL PRIMARY KEY,
  source TEXT,
  rows_inserted INTEGER,
  rows_updated INTEGER,
  status TEXT,
  error_message TEXT,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ
);

DROP TABLE IF EXISTS app_users CASCADE;
CREATE TABLE app_users (
  user_id SERIAL PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  display_name TEXT,
  role TEXT,
  is_active BOOLEAN DEFAULT TRUE,
  last_login TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

DROP TABLE IF EXISTS master_change_log CASCADE;
CREATE TABLE master_change_log (
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

-- ════════════════════════════════════════════════
-- 10. VIEW: 자동집계 (마스터에서 분리된 28개 컬럼)
-- ════════════════════════════════════════════════

-- 10.1 product_stats: 매출/매입 raw에서 집계
CREATE OR REPLACE VIEW product_stats AS
SELECT
  p.product_id,
  p.pn,
  -- 전체 누적
  COALESCE(s.sales_count, 0) AS sales_count,
  COALESCE(s.total_qty, 0) AS total_qty,
  COALESCE(s.total_sales, 0) AS total_sales,
  COALESCE(s.avg_unit_price, 0) AS avg_unit_price,
  s.last_trade_date,
  s.first_trade_date,
  -- 12M
  COALESCE(s.sales_count_12m, 0) AS sales_count_12m,
  COALESCE(s.total_qty_12m, 0) AS total_qty_12m,
  COALESCE(s.total_sales_12m, 0) AS total_sales_12m,
  -- 이번달/지난달
  COALESCE(s.sales_count_thism, 0) AS sales_count_thism,
  COALESCE(s.total_sales_thism, 0) AS total_sales_thism,
  COALESCE(s.sales_count_lastm, 0) AS sales_count_lastm,
  COALESCE(s.total_sales_lastm, 0) AS total_sales_lastm,
  -- 매입
  COALESCE(b.purchase_count, 0) AS purchase_count_12m,
  COALESCE(b.purchase_amount, 0) AS purchase_amount_12m,
  -- 휴면일수
  CASE
    WHEN s.last_trade_date IS NULL THEN 99999
    ELSE (CURRENT_DATE - s.last_trade_date)
  END AS dormant_days,
  -- ABC 등급
  CASE
    WHEN COALESCE(s.total_sales_12m, 0) > 100000000 THEN 'A'
    WHEN COALESCE(s.total_sales_12m, 0) > 30000000 THEN 'B'
    WHEN COALESCE(s.total_sales_12m, 0) > 5000000 THEN 'C'
    WHEN COALESCE(s.total_sales_12m, 0) > 0 THEN 'D'
    ELSE 'X'
  END AS abc_grade,
  -- 활동 추세 (이번달 / 지난달 비교)
  CASE
    WHEN COALESCE(s.total_sales_lastm, 0) = 0 AND COALESCE(s.total_sales_thism, 0) > 0 THEN '🔥 신규'
    WHEN COALESCE(s.total_sales_thism, 0) > COALESCE(s.total_sales_lastm, 0) * 1.2 THEN '↗ 증가'
    WHEN COALESCE(s.total_sales_thism, 0) < COALESCE(s.total_sales_lastm, 0) * 0.8 THEN '↘ 감소'
    WHEN COALESCE(s.total_sales_thism, 0) = 0 AND COALESCE(s.total_sales_lastm, 0) > 0 THEN '⚠ 휴면진입'
    ELSE '→ 유지'
  END AS activity_trend,
  -- 마진율 (매출가 - 추정원가)
  CASE
    WHEN COALESCE(s.avg_unit_price, 0) > 0 AND p.estimated_cost_per_pc > 0 THEN
      ROUND((s.avg_unit_price - p.estimated_cost_per_pc) / s.avg_unit_price * 100, 1)
    ELSE NULL
  END AS margin_pct
FROM products p
LEFT JOIN (
  SELECT
    product_id,
    COUNT(*) AS sales_count,
    SUM(qty) AS total_qty,
    SUM(amount) AS total_sales,
    AVG(unit_price) AS avg_unit_price,
    MAX(item_date) AS last_trade_date,
    MIN(item_date) AS first_trade_date,
    COUNT(*) FILTER (WHERE item_date >= CURRENT_DATE - INTERVAL '12 months') AS sales_count_12m,
    SUM(qty) FILTER (WHERE item_date >= CURRENT_DATE - INTERVAL '12 months') AS total_qty_12m,
    SUM(amount) FILTER (WHERE item_date >= CURRENT_DATE - INTERVAL '12 months') AS total_sales_12m,
    COUNT(*) FILTER (WHERE date_trunc('month', item_date) = date_trunc('month', CURRENT_DATE)) AS sales_count_thism,
    SUM(amount) FILTER (WHERE date_trunc('month', item_date) = date_trunc('month', CURRENT_DATE)) AS total_sales_thism,
    COUNT(*) FILTER (WHERE date_trunc('month', item_date) = date_trunc('month', CURRENT_DATE - INTERVAL '1 month')) AS sales_count_lastm,
    SUM(amount) FILTER (WHERE date_trunc('month', item_date) = date_trunc('month', CURRENT_DATE - INTERVAL '1 month')) AS total_sales_lastm
  FROM sales_ledger
  WHERE product_id IS NOT NULL
  GROUP BY product_id
) s ON s.product_id = p.product_id
LEFT JOIN (
  SELECT
    matched_pn,
    COUNT(*) AS purchase_count,
    SUM(amount) AS purchase_amount
  FROM purchase_ledger
  WHERE matched_pn IS NOT NULL
    AND trade_date >= CURRENT_DATE - INTERVAL '12 months'
  GROUP BY matched_pn
) b ON b.matched_pn = p.pn;

-- 10.2 product_full: 마스터 + 자동집계 join (앱 화면용)
-- p.*에 product_id/pn이 이미 있으므로 ps에서는 stats 컬럼만 명시
CREATE OR REPLACE VIEW product_full AS
SELECT
  p.*,
  ps.sales_count,
  ps.total_qty,
  ps.total_sales,
  ps.avg_unit_price,
  ps.last_trade_date,
  ps.first_trade_date,
  ps.sales_count_12m,
  ps.total_qty_12m,
  ps.total_sales_12m,
  ps.sales_count_thism,
  ps.total_sales_thism,
  ps.sales_count_lastm,
  ps.total_sales_lastm,
  ps.purchase_count_12m,
  ps.purchase_amount_12m,
  ps.dormant_days,
  ps.abc_grade,
  ps.activity_trend,
  ps.margin_pct
FROM products p
LEFT JOIN product_stats ps ON ps.product_id = p.product_id;

-- 10.3 활성 제품 (일상 화면 기본 view)
CREATE OR REPLACE VIEW active_products AS
SELECT * FROM product_full
WHERE archived_at IS NULL;

-- 10.4 휴면 제품 (별도 archive 화면용)
CREATE OR REPLACE VIEW archived_products AS
SELECT * FROM product_full
WHERE archived_at IS NOT NULL;

-- 10.5 거래처 통계 view
CREATE OR REPLACE VIEW vendor_stats AS
SELECT
  v.vendor_id, v.name, v.normalized_name, v.category,
  COALESCE(s.sales_amount, 0) AS sales_amount_12m,
  COALESCE(s.sales_count, 0) AS sales_count_12m,
  COALESCE(b.purchase_amount, 0) AS purchase_amount_12m,
  COALESCE(b.purchase_count, 0) AS purchase_count_12m,
  GREATEST(s.last_sale, b.last_purchase) AS last_trade_date,
  v.archived_at
FROM vendors v
LEFT JOIN (
  SELECT customer, SUM(amount) AS sales_amount, COUNT(*) AS sales_count, MAX(item_date) AS last_sale
  FROM sales_ledger
  WHERE item_date >= CURRENT_DATE - INTERVAL '12 months'
  GROUP BY customer
) s ON s.customer = v.name
LEFT JOIN (
  SELECT vendor_normalized, SUM(amount) AS purchase_amount, COUNT(*) AS purchase_count, MAX(trade_date) AS last_purchase
  FROM purchase_ledger
  WHERE trade_date >= CURRENT_DATE - INTERVAL '12 months'
  GROUP BY vendor_normalized
) b ON b.vendor_normalized = v.normalized_name;

-- 10.6 자재 통계 view
CREATE OR REPLACE VIEW material_stats AS
SELECT
  m.material_id,
  m.raw_name,
  m.material_type,
  m.spec,
  m.main_supplier,
  m.unit,
  COALESCE(p.purchase_count, 0) AS purchase_count_12m,
  COALESCE(p.purchase_amount, 0) AS purchase_amount_12m,
  p.recent_kg_price,
  p.recent_unit_price,
  p.last_purchase_date
FROM materials m
LEFT JOIN (
  SELECT
    matched_pn,
    COUNT(*) AS purchase_count,
    SUM(amount) AS purchase_amount,
    MAX(kg_price) FILTER (WHERE trade_date = (SELECT MAX(trade_date) FROM purchase_ledger pl2 WHERE pl2.matched_pn = purchase_ledger.matched_pn)) AS recent_kg_price,
    MAX(ea_price) FILTER (WHERE trade_date = (SELECT MAX(trade_date) FROM purchase_ledger pl3 WHERE pl3.matched_pn = purchase_ledger.matched_pn)) AS recent_unit_price,
    MAX(trade_date) AS last_purchase_date
  FROM purchase_ledger
  WHERE trade_date >= CURRENT_DATE - INTERVAL '12 months'
  GROUP BY matched_pn
) p ON p.matched_pn = m.material_id;

-- ════════════════════════════════════════════════
-- 끝. 다음 단계: scripts/import_masters.py 실행 (앱 안의 "마스터 import" 버튼)
-- ════════════════════════════════════════════════
