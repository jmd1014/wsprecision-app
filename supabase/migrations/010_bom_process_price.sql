-- ════════════════════════════════════════════════════════════
-- Migration 010: BOM 공정행 unit_price 활용 (LOT 단가)
-- ════════════════════════════════════════════════════════════
-- 정책 조정:
--   같은 process_type (예: HEAT) 안에서도 단계별로 LOT 단가/수량이 다름.
--   예) MRG6-07: 소재열처리(200,000/5000EA) + 제품열처리(200,000/2000EA)
--   → 각 BOM 공정행마다 unit_price 직접 입력 필요.
--
-- product_bom_cost_v 갱신:
--   공정행 단가 우선순위:
--     ① bom.unit_price × qty_per_pc / shared_factor  (BOM 직접)
--     ② products.<공정>_per_pc                          (legacy fallback)
--   자재행 정책은 그대로 유지 (BOM 가격 입력 없음).
-- ════════════════════════════════════════════════════════════

DROP VIEW IF EXISTS product_cost_full_v CASCADE;
DROP VIEW IF EXISTS product_bom_cost_v  CASCADE;


CREATE OR REPLACE VIEW product_bom_cost_v AS
SELECT
  b.product_id,
  -- ── 합계 ──
  SUM(
    CASE
      -- MATERIAL: 매입/원가 fallback chain
      WHEN COALESCE(b.process_type,'MATERIAL') = 'MATERIAL'
        THEN COALESCE(mp.price_3m, mp.price_12m, p.material_unit_price, 0)
             * COALESCE(b.qty_per_pc, 1)
             / NULLIF(COALESCE(b.shared_factor, 1), 0)
      -- HEAT: BOM unit_price 우선, 없으면 products.heat_treat_per_pc
      WHEN b.process_type = 'HEAT' THEN
        CASE
          WHEN b.unit_price IS NOT NULL THEN
            b.unit_price * COALESCE(b.qty_per_pc, 1)
              / NULLIF(COALESCE(b.shared_factor, 1), 0)
          ELSE COALESCE(p.heat_treat_per_pc, 0)
        END
      WHEN b.process_type = 'SURFACE' THEN
        CASE
          WHEN b.unit_price IS NOT NULL THEN
            b.unit_price * COALESCE(b.qty_per_pc, 1)
              / NULLIF(COALESCE(b.shared_factor, 1), 0)
          ELSE COALESCE(p.surface_per_pc, 0)
        END
      WHEN b.process_type = 'OUTSOURCE' THEN
        CASE
          WHEN b.unit_price IS NOT NULL THEN
            b.unit_price * COALESCE(b.qty_per_pc, 1)
              / NULLIF(COALESCE(b.shared_factor, 1), 0)
          ELSE COALESCE(p.outsourcing_per_pc, 0)
        END
      WHEN b.process_type IN ('PACKING','LABOR','OTHER') THEN
        COALESCE(b.unit_price, 0) * COALESCE(b.qty_per_pc, 1)
          / NULLIF(COALESCE(b.shared_factor, 1), 0)
      ELSE 0::numeric
    END
  ) AS bom_cost_per_pc,

  -- ── 항목별 분해 ──
  SUM(
    CASE WHEN COALESCE(b.process_type,'MATERIAL') = 'MATERIAL'
    THEN COALESCE(mp.price_3m, mp.price_12m, p.material_unit_price, 0)
         * COALESCE(b.qty_per_pc, 1)
         / NULLIF(COALESCE(b.shared_factor, 1), 0)
    ELSE 0 END
  ) AS material_cost_per_pc,
  SUM(
    CASE WHEN b.process_type = 'HEAT' THEN
      CASE
        WHEN b.unit_price IS NOT NULL THEN
          b.unit_price * COALESCE(b.qty_per_pc, 1)
            / NULLIF(COALESCE(b.shared_factor, 1), 0)
        ELSE COALESCE(p.heat_treat_per_pc, 0)
      END
    ELSE 0 END
  ) AS heat_cost_per_pc,
  SUM(
    CASE WHEN b.process_type = 'SURFACE' THEN
      CASE
        WHEN b.unit_price IS NOT NULL THEN
          b.unit_price * COALESCE(b.qty_per_pc, 1)
            / NULLIF(COALESCE(b.shared_factor, 1), 0)
        ELSE COALESCE(p.surface_per_pc, 0)
      END
    ELSE 0 END
  ) AS surface_cost_per_pc,
  SUM(
    CASE WHEN b.process_type = 'OUTSOURCE' THEN
      CASE
        WHEN b.unit_price IS NOT NULL THEN
          b.unit_price * COALESCE(b.qty_per_pc, 1)
            / NULLIF(COALESCE(b.shared_factor, 1), 0)
        ELSE COALESCE(p.outsourcing_per_pc, 0)
      END
    ELSE 0 END
  ) AS outsource_cost_per_pc,
  SUM(
    CASE WHEN b.process_type IN ('PACKING','LABOR','OTHER')
    THEN COALESCE(b.unit_price, 0) * COALESCE(b.qty_per_pc, 1)
         / NULLIF(COALESCE(b.shared_factor, 1), 0)
    ELSE 0::numeric END
  ) AS other_cost_per_pc,

  -- ── 메타 ──
  COUNT(*)                                                              AS bom_row_count,
  COUNT(*) FILTER (WHERE COALESCE(b.process_type,'MATERIAL') = 'MATERIAL') AS material_rows,
  COUNT(*) FILTER (WHERE b.process_type IS NOT NULL
                   AND b.process_type <> 'MATERIAL')                    AS process_rows,
  COUNT(*) FILTER (
    WHERE COALESCE(b.process_type,'MATERIAL') = 'MATERIAL'
      AND mp.price_3m IS NOT NULL
  ) AS rows_using_3m_avg,
  COUNT(*) FILTER (
    WHERE COALESCE(b.process_type,'MATERIAL') = 'MATERIAL'
      AND mp.price_3m IS NULL
      AND mp.price_12m IS NULL
      AND p.material_unit_price IS NULL
  ) AS rows_with_no_price,
  COUNT(*) FILTER (WHERE b.unit_price IS NOT NULL)                      AS rows_with_explicit_price
FROM bom b
LEFT JOIN material_price_v mp ON mp.material_id = b.material_id
LEFT JOIN products p ON p.product_id = b.product_id
WHERE (b.apply_end_date IS NULL OR b.apply_end_date >= CURRENT_DATE)
GROUP BY b.product_id;


-- product_cost_full_v 도 함께 재생성 (의존성 때문에 위에서 DROP CASCADE 됨)
CREATE OR REPLACE VIEW product_cost_full_v AS
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
  -- Layer C: actual cost (Phase 3)
  ac.avg_cycle_time_sec,
  ac.defect_rate,
  ac.avg_efficiency_pct,
  ac.labor_cost_per_pc_est,
  ac.log_count_6m,
  -- Layer D: 매출
  ps.avg_unit_price            AS sale_price,
  ps.avg_unit_price            AS avg_unit_price,
  ps.total_sales_12m,
  ps.sales_count_12m,
  ps.abc_grade,
  ps.activity_trend,
  -- 통합
  COALESCE(NULLIF(bc.bom_cost_per_pc, 0), p.estimated_cost_per_pc) AS final_cost_per_pc,
  COALESCE(NULLIF(bc.bom_cost_per_pc, 0), p.estimated_cost_per_pc) AS estimated_cost_per_pc,
  COALESCE(NULLIF(bc.material_cost_per_pc, 0), p.material_unit_price) AS material_unit_price,
  COALESCE(NULLIF(bc.outsource_cost_per_pc, 0), p.outsourcing_per_pc) AS outsourcing_per_pc,
  COALESCE(NULLIF(bc.heat_cost_per_pc, 0), p.heat_treat_per_pc)       AS heat_treat_per_pc,
  COALESCE(NULLIF(bc.surface_cost_per_pc, 0), p.surface_per_pc)       AS surface_per_pc,
  p.material_kg_price,
  -- 마진
  CASE
    WHEN ps.avg_unit_price > 0
     AND COALESCE(NULLIF(bc.bom_cost_per_pc, 0), p.estimated_cost_per_pc) > 0
    THEN ROUND(
      (ps.avg_unit_price - COALESCE(NULLIF(bc.bom_cost_per_pc, 0), p.estimated_cost_per_pc))
      / ps.avg_unit_price * 100, 1)
    ELSE NULL
  END AS margin_pct_calc,
  CASE
    WHEN ps.avg_unit_price > 0
     AND COALESCE(NULLIF(bc.bom_cost_per_pc, 0), p.estimated_cost_per_pc) > 0
    THEN ROUND(
      (ps.avg_unit_price - COALESCE(NULLIF(bc.bom_cost_per_pc, 0), p.estimated_cost_per_pc))
      / ps.avg_unit_price * 100, 1)
    ELSE NULL
  END AS margin_pct,
  -- 신뢰도
  CASE
    WHEN bc.bom_row_count > 0
     AND bc.rows_with_no_price = 0
     AND bc.material_rows > 0       THEN 'BOM_FULL'
    WHEN bc.bom_row_count > 0
     AND bc.material_rows > 0       THEN 'BOM_PARTIAL'
    WHEN p.estimated_cost_per_pc > 0 THEN 'LEGACY_ONLY'
    ELSE 'NO_DATA'
  END AS cost_source
FROM products p
LEFT JOIN product_bom_cost_v   bc ON bc.product_id = p.product_id
LEFT JOIN product_actual_cost_v ac ON ac.product_id = p.product_id
LEFT JOIN product_stats        ps ON ps.product_id = p.product_id;


COMMENT ON VIEW product_bom_cost_v IS
  'BOM 수량 × 가격. 공정행은 bom.unit_price 우선 (LOT 단가), 자재행은 매입 평균 우선.';
