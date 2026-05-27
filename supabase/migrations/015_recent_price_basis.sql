-- ════════════════════════════════════════════════════════════
-- Migration 015: 최근 단가 기준 + 사급 BOM_FULL 인정
-- ════════════════════════════════════════════════════════════
-- 정정 사항 (사용자 도메인 규칙):
--   1. 판매가 기준 = ERP 최근 거래가 (12M 평균 X)
--   2. 자재 단가 기준 = 매입 최근 거래가 (3M 평균 X)
--   3. 사급 제품은 자재 단가 부재해도 BOM 완료 인정
--
-- 변경 view (의존성 순서):
--   product_bom_cost_v          — 단가 우선순위 price_last, 사급 0 처리
--   product_cost_full_v         — sale_price=last, cost_source 사급 인식
--   product_material_price_status_v — 사급 표시
--   material_price_coverage_v   — 사급 제외 통계
-- ════════════════════════════════════════════════════════════

DROP VIEW IF EXISTS material_price_coverage_v CASCADE;
DROP VIEW IF EXISTS product_material_price_status_v CASCADE;
DROP VIEW IF EXISTS product_cost_full_v CASCADE;
DROP VIEW IF EXISTS product_bom_cost_v CASCADE;


-- ─────────────────────────────────────────
-- 1. product_bom_cost_v
--    자재 단가 우선순위: price_last → price_3m → price_12m → legacy
--    사급 제품은 자재행 가격 0 처리
-- ─────────────────────────────────────────
CREATE VIEW product_bom_cost_v AS
SELECT
  b.product_id,
  -- 합계
  SUM(
    CASE
      -- MATERIAL: 사급은 0, 도급/미설정은 fallback chain
      WHEN COALESCE(b.process_type,'MATERIAL') = 'MATERIAL' THEN
        CASE
          WHEN p.procurement_type = '사급' THEN 0::numeric
          ELSE COALESCE(mp.price_last, mp.price_3m, mp.price_12m,
                        p.material_unit_price, 0)
               * COALESCE(b.qty_per_pc, 1)
               / NULLIF(COALESCE(b.shared_factor, 1), 0)
        END
      -- 공정행: bom.unit_price 우선 → products.<공정>_per_pc fallback
      WHEN b.process_type = 'HEAT' THEN
        CASE WHEN b.unit_price IS NOT NULL
          THEN b.unit_price * COALESCE(b.qty_per_pc, 1)
               / NULLIF(COALESCE(b.shared_factor, 1), 0)
          ELSE COALESCE(p.heat_treat_per_pc, 0)
        END
      WHEN b.process_type = 'SURFACE' THEN
        CASE WHEN b.unit_price IS NOT NULL
          THEN b.unit_price * COALESCE(b.qty_per_pc, 1)
               / NULLIF(COALESCE(b.shared_factor, 1), 0)
          ELSE COALESCE(p.surface_per_pc, 0)
        END
      WHEN b.process_type = 'OUTSOURCE' THEN
        CASE WHEN b.unit_price IS NOT NULL
          THEN b.unit_price * COALESCE(b.qty_per_pc, 1)
               / NULLIF(COALESCE(b.shared_factor, 1), 0)
          ELSE COALESCE(p.outsourcing_per_pc, 0)
        END
      WHEN b.process_type IN ('PACKING','LABOR','OTHER') THEN
        COALESCE(b.unit_price, 0) * COALESCE(b.qty_per_pc, 1)
          / NULLIF(COALESCE(b.shared_factor, 1), 0)
      ELSE 0::numeric
    END
  )                                                                       AS bom_cost_per_pc,
  -- 항목별 분해
  SUM(
    CASE WHEN COALESCE(b.process_type,'MATERIAL') = 'MATERIAL'
    THEN
      CASE
        WHEN p.procurement_type = '사급' THEN 0::numeric
        ELSE COALESCE(mp.price_last, mp.price_3m, mp.price_12m,
                      p.material_unit_price, 0)
             * COALESCE(b.qty_per_pc, 1)
             / NULLIF(COALESCE(b.shared_factor, 1), 0)
      END
    ELSE 0 END
  )                                                                       AS material_cost_per_pc,
  SUM(
    CASE WHEN b.process_type = 'HEAT' THEN
      CASE WHEN b.unit_price IS NOT NULL
        THEN b.unit_price * COALESCE(b.qty_per_pc, 1)
             / NULLIF(COALESCE(b.shared_factor, 1), 0)
        ELSE COALESCE(p.heat_treat_per_pc, 0)
      END
    ELSE 0 END
  )                                                                       AS heat_cost_per_pc,
  SUM(
    CASE WHEN b.process_type = 'SURFACE' THEN
      CASE WHEN b.unit_price IS NOT NULL
        THEN b.unit_price * COALESCE(b.qty_per_pc, 1)
             / NULLIF(COALESCE(b.shared_factor, 1), 0)
        ELSE COALESCE(p.surface_per_pc, 0)
      END
    ELSE 0 END
  )                                                                       AS surface_cost_per_pc,
  SUM(
    CASE WHEN b.process_type = 'OUTSOURCE' THEN
      CASE WHEN b.unit_price IS NOT NULL
        THEN b.unit_price * COALESCE(b.qty_per_pc, 1)
             / NULLIF(COALESCE(b.shared_factor, 1), 0)
        ELSE COALESCE(p.outsourcing_per_pc, 0)
      END
    ELSE 0 END
  )                                                                       AS outsource_cost_per_pc,
  SUM(
    CASE WHEN b.process_type IN ('PACKING','LABOR','OTHER')
    THEN COALESCE(b.unit_price, 0) * COALESCE(b.qty_per_pc, 1)
         / NULLIF(COALESCE(b.shared_factor, 1), 0)
    ELSE 0::numeric END
  )                                                                       AS other_cost_per_pc,
  -- 메타
  COUNT(*)                                                                AS bom_row_count,
  COUNT(*) FILTER (WHERE COALESCE(b.process_type,'MATERIAL') = 'MATERIAL') AS material_rows,
  COUNT(*) FILTER (WHERE b.process_type IS NOT NULL AND b.process_type <> 'MATERIAL') AS process_rows,
  COUNT(*) FILTER (
    WHERE COALESCE(b.process_type,'MATERIAL') = 'MATERIAL'
      AND p.procurement_type IS DISTINCT FROM '사급'
      AND mp.price_last IS NULL
      AND mp.price_3m IS NULL
      AND mp.price_12m IS NULL
      AND (p.material_unit_price IS NULL OR p.material_unit_price = 0)
  ) AS rows_with_no_price,
  COUNT(*) FILTER (
    WHERE COALESCE(b.process_type,'MATERIAL') = 'MATERIAL'
      AND (mp.price_last IS NOT NULL OR mp.price_3m IS NOT NULL)
  ) AS rows_using_3m_avg,
  COUNT(*) FILTER (WHERE b.unit_price IS NOT NULL) AS rows_with_explicit_price
FROM bom b
LEFT JOIN material_price_v mp ON mp.material_id = b.material_id
LEFT JOIN products p ON p.product_id = b.product_id
WHERE (b.apply_end_date IS NULL OR b.apply_end_date >= CURRENT_DATE)
GROUP BY b.product_id;


-- ─────────────────────────────────────────
-- 2. product_cost_full_v
--    sale_price = last_unit_price 우선, cost_source 사급 인식
-- ─────────────────────────────────────────
CREATE VIEW product_cost_full_v AS
SELECT
  p.product_id, p.pn, p.customer, p.product_group, p.sub_class,
  p.archived_at, p.material, p.raw_material_name, p.raw_material_spec,
  p.cost_data_quality,
  -- Layer A: legacy
  p.material_unit_price        AS legacy_material_per_pc,
  p.outsourcing_per_pc         AS legacy_outsource_per_pc,
  p.heat_treat_per_pc          AS legacy_heat_per_pc,
  p.surface_per_pc             AS legacy_surface_per_pc,
  p.estimated_cost_per_pc      AS legacy_estimated_cost,
  -- Layer B: BOM
  bc.bom_cost_per_pc,
  bc.material_cost_per_pc,
  bc.heat_cost_per_pc,
  bc.surface_cost_per_pc,
  bc.outsource_cost_per_pc,
  bc.other_cost_per_pc,
  bc.bom_row_count,
  bc.material_rows,
  bc.process_rows,
  bc.rows_with_explicit_price,
  bc.rows_using_3m_avg,
  bc.rows_with_no_price,
  -- Layer C: actual (Phase 3)
  ac.avg_cycle_time_sec,
  ac.defect_rate,
  ac.avg_efficiency_pct,
  ac.labor_cost_per_pc_est,
  ac.log_count_6m,
  -- Layer D: 매출 — sale_price = last_unit_price 우선
  COALESCE(NULLIF(ps.last_unit_price, 0), ps.avg_unit_price) AS sale_price,
  COALESCE(NULLIF(ps.last_unit_price, 0), ps.avg_unit_price) AS avg_unit_price,
  ps.last_unit_price            AS recent_price,
  ps.avg_unit_price             AS avg_unit_price_12m,
  ps.avg_unit_price_3m,
  ps.total_sales_12m,
  ps.sales_count_12m,
  ps.abc_grade,
  ps.activity_trend,
  -- 통합 추정원가
  COALESCE(NULLIF(bc.bom_cost_per_pc, 0), p.estimated_cost_per_pc) AS final_cost_per_pc,
  COALESCE(NULLIF(bc.bom_cost_per_pc, 0), p.estimated_cost_per_pc) AS estimated_cost_per_pc,
  COALESCE(NULLIF(bc.material_cost_per_pc, 0), p.material_unit_price) AS material_unit_price,
  COALESCE(NULLIF(bc.outsource_cost_per_pc, 0), p.outsourcing_per_pc) AS outsourcing_per_pc,
  COALESCE(NULLIF(bc.heat_cost_per_pc, 0), p.heat_treat_per_pc)       AS heat_treat_per_pc,
  COALESCE(NULLIF(bc.surface_cost_per_pc, 0), p.surface_per_pc)       AS surface_per_pc,
  p.material_kg_price,
  -- 마진율 = last_unit_price 기준
  CASE
    WHEN COALESCE(NULLIF(ps.last_unit_price, 0), ps.avg_unit_price) > 0
     AND COALESCE(NULLIF(bc.bom_cost_per_pc, 0), p.estimated_cost_per_pc) > 0
    THEN ROUND(
      (COALESCE(NULLIF(ps.last_unit_price, 0), ps.avg_unit_price)
        - COALESCE(NULLIF(bc.bom_cost_per_pc, 0), p.estimated_cost_per_pc))
      / COALESCE(NULLIF(ps.last_unit_price, 0), ps.avg_unit_price) * 100, 1)
    ELSE NULL
  END AS margin_pct_calc,
  CASE
    WHEN COALESCE(NULLIF(ps.last_unit_price, 0), ps.avg_unit_price) > 0
     AND COALESCE(NULLIF(bc.bom_cost_per_pc, 0), p.estimated_cost_per_pc) > 0
    THEN ROUND(
      (COALESCE(NULLIF(ps.last_unit_price, 0), ps.avg_unit_price)
        - COALESCE(NULLIF(bc.bom_cost_per_pc, 0), p.estimated_cost_per_pc))
      / COALESCE(NULLIF(ps.last_unit_price, 0), ps.avg_unit_price) * 100, 1)
    ELSE NULL
  END AS margin_pct,
  -- 신뢰도 — 사급은 자재 가격 없어도 BOM_FULL 인정
  CASE
    WHEN bc.bom_row_count > 0
     AND bc.material_rows > 0
     AND (bc.rows_with_no_price = 0 OR p.procurement_type = '사급')
       THEN 'BOM_FULL'
    WHEN bc.bom_row_count > 0
     AND bc.material_rows > 0       THEN 'BOM_PARTIAL'
    WHEN p.estimated_cost_per_pc > 0 THEN 'LEGACY_ONLY'
    ELSE 'NO_DATA'
  END AS cost_source
FROM products p
LEFT JOIN product_bom_cost_v   bc ON bc.product_id = p.product_id
LEFT JOIN product_actual_cost_v ac ON ac.product_id = p.product_id
LEFT JOIN product_stats        ps ON ps.product_id = p.product_id;


-- ─────────────────────────────────────────
-- 3. product_material_price_status_v
--    BOM 자재행 단위 가격 출처 (last 우선 + 사급 NA)
-- ─────────────────────────────────────────
CREATE VIEW product_material_price_status_v AS
SELECT
  b.product_id, p.pn, p.customer, p.procurement_type, p.archived_at,
  b.bom_id, b.material_id, b.raw_material_name AS bom_material_name,
  m.raw_name AS master_raw_name, m.material_type, m.spec,
  b.qty_per_pc, b.shared_factor,
  mp.purchase_count_12m,
  mp.price_3m AS purchase_price_3m,
  mp.price_12m AS purchase_price_12m,
  mp.price_last AS purchase_price_last,
  mp.last_purchase_date,
  p.material_unit_price AS legacy_price,
  CASE
    WHEN p.procurement_type = '사급' THEN 'NA_SAGEUP'
    WHEN mp.price_last IS NOT NULL THEN 'PURCHASE_LAST'
    WHEN mp.price_3m IS NOT NULL   THEN 'PURCHASE_3M'
    WHEN mp.price_12m IS NOT NULL  THEN 'PURCHASE_12M'
    WHEN p.material_unit_price IS NOT NULL
     AND p.material_unit_price > 0 THEN 'LEGACY'
    ELSE 'NONE'
  END AS price_source,
  CASE
    WHEN p.procurement_type = '사급' THEN 0::numeric
    ELSE COALESCE(mp.price_last, mp.price_3m, mp.price_12m,
                  NULLIF(p.material_unit_price, 0))
  END AS effective_price,
  EXISTS (SELECT 1 FROM purchase_ledger pl
          WHERE pl.matched_material_id = b.material_id) AS has_purchase_history
FROM bom b
LEFT JOIN products p ON p.product_id = b.product_id
LEFT JOIN materials m ON m.material_id = b.material_id
LEFT JOIN material_price_v mp ON mp.material_id = b.material_id
WHERE COALESCE(b.process_type, 'MATERIAL') = 'MATERIAL';


-- ─────────────────────────────────────────
-- 4. material_price_coverage_v
-- ─────────────────────────────────────────
CREATE VIEW material_price_coverage_v AS
SELECT
  COUNT(*) FILTER (WHERE archived_at IS NULL) AS total_active_bom_material_rows,
  COUNT(*) FILTER (WHERE archived_at IS NULL AND price_source = 'PURCHASE_LAST') AS price_purchase_last,
  COUNT(*) FILTER (WHERE archived_at IS NULL AND price_source = 'PURCHASE_3M') AS price_purchase_3m,
  COUNT(*) FILTER (WHERE archived_at IS NULL AND price_source = 'PURCHASE_12M') AS price_purchase_12m,
  COUNT(*) FILTER (WHERE archived_at IS NULL AND price_source = 'LEGACY') AS price_legacy,
  COUNT(*) FILTER (WHERE archived_at IS NULL AND price_source = 'NA_SAGEUP') AS price_na_sageup,
  COUNT(*) FILTER (WHERE archived_at IS NULL AND price_source = 'NONE') AS price_none,
  ROUND(100.0 * COUNT(*) FILTER (
    WHERE archived_at IS NULL
      AND price_source IN ('PURCHASE_LAST','PURCHASE_3M','PURCHASE_12M')
  ) / NULLIF(COUNT(*) FILTER (WHERE archived_at IS NULL), 0), 1) AS pct_from_purchase,
  ROUND(100.0 * COUNT(*) FILTER (
    WHERE archived_at IS NULL AND price_source = 'LEGACY'
  ) / NULLIF(COUNT(*) FILTER (WHERE archived_at IS NULL), 0), 1) AS pct_from_legacy,
  ROUND(100.0 * COUNT(*) FILTER (
    WHERE archived_at IS NULL AND price_source = 'NONE'
  ) / NULLIF(COUNT(*) FILTER (WHERE archived_at IS NULL), 0), 1) AS pct_none
FROM product_material_price_status_v;
