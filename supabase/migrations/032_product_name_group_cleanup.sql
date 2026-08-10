-- Migration 032: 제품 마스터 정리 — 품명(item_name) 추가 + product_group 삭제
-- (2026-08-10 사용자 확정)
--
-- 배경:
-- - products 에 자유 품명 컬럼이 없어 출고 리스트 품명이 수주 스냅샷에만 의존
-- - product_group 값 분포가 사실상 거래처 구분(밸브류/DIC/HDX…)이라 정보 가치 없음
-- - sub_class(YPBV, LJF, ABV-FL…)가 실제 제품군 — UI 라벨만 "제품군"으로 변경
--   (DB 컬럼명 sub_class 는 유지 — 뷰·코드 파급 최소화)
--
-- 롤백: products_group_backup_0810 에 product_id/pn/product_group 보존

-- 1) 백업
CREATE TABLE IF NOT EXISTS products_group_backup_0810 AS
  SELECT product_id, pn, product_group FROM products;

-- 2) 품명 컬럼 + 백필 (수주 라인 거래처 품명의 제품별 최빈값)
ALTER TABLE products ADD COLUMN IF NOT EXISTS item_name TEXT;

WITH ranked AS (
  SELECT product_id, customer_item_name,
         ROW_NUMBER() OVER (
           PARTITION BY product_id
           ORDER BY count(*) DESC, max(soi_id) DESC) AS rn
  FROM sales_order_items
  WHERE product_id IS NOT NULL
    AND customer_item_name IS NOT NULL
    AND btrim(customer_item_name) <> ''
  GROUP BY product_id, customer_item_name
)
UPDATE products p SET item_name = r.customer_item_name
FROM ranked r
WHERE r.product_id = p.product_id AND r.rn = 1
  AND p.item_name IS NULL;

-- 3) product_group 참조 뷰 삭제 (의존 역순)
DROP VIEW IF EXISTS bom_cleanup_todo_v;
DROP VIEW IF EXISTS active_bom_completion_v;
DROP VIEW IF EXISTS bom_missing_active_products_v;
DROP VIEW IF EXISTS active_products;
DROP VIEW IF EXISTS archived_products;
DROP VIEW IF EXISTS product_cost_full_v;
DROP VIEW IF EXISTS product_full;

-- 4) 컬럼 삭제
DROP INDEX IF EXISTS idx_products_group;
ALTER TABLE products DROP COLUMN product_group;

-- 5) 뷰 재생성 — product_group 제거, item_name(품명) 노출
CREATE VIEW product_full AS
 SELECT p.product_id, p.pn, p.item_name, p.alias_list, p.drawing_no,
    p.sub_class, p.material, p.raw_material_name, p.raw_material_spec,
    p.procurement_type, p.procurement_start_date, p.procurement_prev_type,
    p.customer, p.bom_material_name, p.material_unit, p.material_kg_price,
    p.material_unit_price, p.material_purchase_count,
    p.material_last_purchase_date, p.material_main_supplier,
    p.material_data_quality, p.outsourcing_per_pc, p.heat_treat_per_pc,
    p.surface_per_pc, p.estimated_cost_per_pc, p.cost_data_quality,
    p.active, p.caution, p.inference_basis, p.archived_at,
    p.archive_reason, p.created_at, p.updated_at,
    ps.sales_count, ps.total_qty, ps.total_sales, ps.avg_unit_price,
    ps.last_trade_date, ps.first_trade_date, ps.sales_count_12m,
    ps.total_qty_12m, ps.total_sales_12m, ps.sales_count_thism,
    ps.total_sales_thism, ps.sales_count_lastm, ps.total_sales_lastm,
    ps.purchase_count_12m, ps.purchase_amount_12m, ps.dormant_days,
    ps.abc_grade, ps.activity_trend, ps.margin_pct
   FROM products p
     LEFT JOIN product_stats ps ON ps.product_id = p.product_id;

CREATE VIEW active_products AS
  SELECT * FROM product_full WHERE archived_at IS NULL;

CREATE VIEW archived_products AS
  SELECT * FROM product_full WHERE archived_at IS NOT NULL;

CREATE VIEW active_bom_completion_v AS
 SELECT p.product_id, p.pn, p.customer, p.sub_class,
    count(b.bom_id) AS bom_row_count,
    count(b.bom_id) FILTER (WHERE COALESCE(b.process_type, 'MATERIAL') = 'MATERIAL') AS material_row_count,
    count(b.bom_id) FILTER (WHERE b.process_type IS NOT NULL AND b.process_type <> 'MATERIAL') AS process_row_count,
    count(b.bom_id) FILTER (WHERE b.material_id IS NULL AND COALESCE(b.process_type, 'MATERIAL') = 'MATERIAL') AS missing_material_id,
    count(b.bom_id) FILTER (WHERE b.qty_per_pc IS NULL OR b.qty_per_pc = 0) AS missing_qty,
    count(b.bom_id) FILTER (WHERE b.shared_factor IS NULL OR b.shared_factor = 0) AS missing_sf,
    count(b.bom_id) FILTER (WHERE COALESCE(b.verification_status, '') <> '확인완료') AS unverified,
    CASE
      WHEN count(b.bom_id) = 0 THEN 'NO_BOM'
      WHEN count(b.bom_id) FILTER (WHERE b.material_id IS NULL AND COALESCE(b.process_type, 'MATERIAL') = 'MATERIAL') > 0 THEN 'INCOMPLETE'
      WHEN count(b.bom_id) FILTER (WHERE b.qty_per_pc IS NULL OR b.qty_per_pc = 0) > 0 THEN 'INCOMPLETE'
      WHEN count(b.bom_id) FILTER (WHERE b.shared_factor IS NULL OR b.shared_factor = 0) > 0 THEN 'INCOMPLETE'
      WHEN count(b.bom_id) FILTER (WHERE COALESCE(b.verification_status, '') <> '확인완료') > 0 THEN 'UNVERIFIED'
      ELSE 'COMPLETE'
    END AS completion_status
   FROM products p
     LEFT JOIN bom b ON b.product_id = p.product_id
  WHERE p.archived_at IS NULL
  GROUP BY p.product_id, p.pn, p.customer, p.sub_class;

CREATE VIEW bom_cleanup_todo_v AS
 SELECT c.product_id, c.pn, c.customer, c.sub_class,
    c.completion_status, c.bom_row_count, c.material_row_count,
    c.process_row_count, c.missing_material_id, c.missing_qty,
    c.missing_sf, c.unverified,
    COALESCE(ps.total_sales_12m, 0) AS total_sales_12m,
    COALESCE(ps.sales_count_12m, 0) AS sales_count_12m,
    COALESCE(ps.abc_grade, 'X') AS abc_grade,
    CASE
      WHEN c.completion_status = 'NO_BOM' AND ps.total_sales_12m > 0 THEN 1
      WHEN c.completion_status = 'INCOMPLETE' AND ps.total_sales_12m > 0 THEN 2
      WHEN c.completion_status = 'UNVERIFIED' AND ps.total_sales_12m > 0 THEN 3
      WHEN c.completion_status = 'NO_BOM' THEN 4
      WHEN c.completion_status = 'INCOMPLETE' THEN 5
      WHEN c.completion_status = 'UNVERIFIED' THEN 6
      ELSE 99
    END AS priority
   FROM active_bom_completion_v c
     LEFT JOIN product_stats ps ON ps.product_id = c.product_id
  WHERE c.completion_status <> 'COMPLETE';

CREATE VIEW bom_missing_active_products_v AS
 SELECT p.product_id, p.pn, p.customer, p.sub_class, p.material,
    p.raw_material_name, p.raw_material_spec, p.material_unit_price,
    p.estimated_cost_per_pc,
    COALESCE(ps.total_sales_12m, 0) AS total_sales_12m,
    COALESCE(ps.sales_count_12m, 0) AS sales_count_12m,
    COALESCE(ps.abc_grade, 'X') AS abc_grade,
    COALESCE(ps.activity_trend, '-') AS activity_trend
   FROM products p
     LEFT JOIN product_stats ps ON ps.product_id = p.product_id
  WHERE p.archived_at IS NULL
    AND NOT (EXISTS (SELECT 1 FROM bom b WHERE b.product_id = p.product_id));

CREATE VIEW product_cost_full_v AS
 SELECT p.product_id, p.pn, p.item_name, p.customer, p.sub_class,
    p.archived_at, p.material, p.raw_material_name, p.raw_material_spec,
    p.cost_data_quality,
    p.material_unit_price AS legacy_material_per_pc,
    p.outsourcing_per_pc AS legacy_outsource_per_pc,
    p.heat_treat_per_pc AS legacy_heat_per_pc,
    p.surface_per_pc AS legacy_surface_per_pc,
    p.estimated_cost_per_pc AS legacy_estimated_cost,
    bc.bom_cost_per_pc, bc.material_cost_per_pc, bc.heat_cost_per_pc,
    bc.surface_cost_per_pc, bc.outsource_cost_per_pc, bc.other_cost_per_pc,
    bc.bom_row_count, bc.material_rows, bc.process_rows,
    bc.rows_with_explicit_price, bc.rows_using_3m_avg, bc.rows_with_no_price,
    ac.avg_cycle_time_sec, ac.defect_rate, ac.avg_efficiency_pct,
    ac.labor_cost_per_pc_est, ac.log_count_6m,
    COALESCE(NULLIF(ps.last_unit_price, 0), ps.avg_unit_price) AS sale_price,
    COALESCE(NULLIF(ps.last_unit_price, 0), ps.avg_unit_price) AS avg_unit_price,
    ps.last_unit_price AS recent_price,
    ps.avg_unit_price AS avg_unit_price_12m,
    ps.avg_unit_price_3m, ps.total_sales_12m, ps.sales_count_12m,
    ps.abc_grade, ps.activity_trend,
    COALESCE(NULLIF(bc.bom_cost_per_pc, 0), p.estimated_cost_per_pc) AS final_cost_per_pc,
    COALESCE(NULLIF(bc.bom_cost_per_pc, 0), p.estimated_cost_per_pc) AS estimated_cost_per_pc,
    COALESCE(NULLIF(bc.material_cost_per_pc, 0), p.material_unit_price) AS material_unit_price,
    COALESCE(NULLIF(bc.outsource_cost_per_pc, 0), p.outsourcing_per_pc) AS outsourcing_per_pc,
    COALESCE(NULLIF(bc.heat_cost_per_pc, 0), p.heat_treat_per_pc) AS heat_treat_per_pc,
    COALESCE(NULLIF(bc.surface_cost_per_pc, 0), p.surface_per_pc) AS surface_per_pc,
    p.material_kg_price,
    CASE
      WHEN COALESCE(NULLIF(ps.last_unit_price, 0), ps.avg_unit_price) > 0
       AND COALESCE(NULLIF(bc.bom_cost_per_pc, 0), p.estimated_cost_per_pc) > 0
      THEN round((COALESCE(NULLIF(ps.last_unit_price, 0), ps.avg_unit_price)
                  - COALESCE(NULLIF(bc.bom_cost_per_pc, 0), p.estimated_cost_per_pc))
                 / COALESCE(NULLIF(ps.last_unit_price, 0), ps.avg_unit_price) * 100, 1)
      ELSE NULL
    END AS margin_pct_calc,
    CASE
      WHEN COALESCE(NULLIF(ps.last_unit_price, 0), ps.avg_unit_price) > 0
       AND COALESCE(NULLIF(bc.bom_cost_per_pc, 0), p.estimated_cost_per_pc) > 0
      THEN round((COALESCE(NULLIF(ps.last_unit_price, 0), ps.avg_unit_price)
                  - COALESCE(NULLIF(bc.bom_cost_per_pc, 0), p.estimated_cost_per_pc))
                 / COALESCE(NULLIF(ps.last_unit_price, 0), ps.avg_unit_price) * 100, 1)
      ELSE NULL
    END AS margin_pct,
    CASE
      WHEN bc.bom_row_count > 0 AND bc.material_rows > 0
       AND (bc.rows_with_no_price = 0 OR p.procurement_type = '사급')
      THEN 'BOM_FULL'
      WHEN bc.bom_row_count > 0 AND bc.material_rows > 0 THEN 'BOM_PARTIAL'
      WHEN p.estimated_cost_per_pc > 0 THEN 'LEGACY_ONLY'
      ELSE 'NO_DATA'
    END AS cost_source
   FROM products p
     LEFT JOIN product_bom_cost_v bc ON bc.product_id = p.product_id
     LEFT JOIN product_actual_cost_v ac ON ac.product_id = p.product_id
     LEFT JOIN product_stats ps ON ps.product_id = p.product_id;
