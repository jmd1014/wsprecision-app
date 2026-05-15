-- ════════════════════════════════════════════════════════════
-- Migration 009: BOM = 수량 / 가격 = 원가·매입 분리
-- ════════════════════════════════════════════════════════════
-- 정책 변경:
--   BOM 은 "수량 관계" 만 저장 (qty_per_pc, shared_factor, process_type).
--   가격은 원가(products.* per_pc) 또는 매입(material_price_v) 에서.
--
-- product_bom_cost_v 재작성:
--   - MATERIAL 행:
--       단가 = material_price_v.price_3m → price_12m → products.material_unit_price (legacy fallback)
--       per_pc = 단가 × qty_per_pc / shared_factor
--   - HEAT/SURFACE/OUTSOURCE 행:
--       단가 = products.heat_treat_per_pc / surface_per_pc / outsourcing_per_pc
--       (이미 per_pc 단위. shared_factor 미반영.
--        향후 process_cost_v 로 LOT 단가 도입 가능)
--   - PACKING/LABOR/OTHER 행: 추후 process_cost_v 도입까지 0
--
-- bom.unit_price 컬럼은 그대로 두되 (legacy 호환), view 에서 미사용.
-- ════════════════════════════════════════════════════════════

-- 008 의 product_bom_cost_v 와 컬럼 타입이 달라지므로 CREATE OR REPLACE 불가.
-- DROP CASCADE 로 의존 view (product_cost_full_v) 까지 같이 제거 후 재생성.
DROP VIEW IF EXISTS product_cost_full_v CASCADE;
DROP VIEW IF EXISTS product_bom_cost_v  CASCADE;


CREATE OR REPLACE VIEW product_bom_cost_v AS
SELECT
  b.product_id,
  -- ── 합계 ──
  SUM(
    -- MATERIAL: BOM 수량 × 자재 단가 fallback chain
    CASE WHEN COALESCE(b.process_type,'MATERIAL') = 'MATERIAL'
      THEN COALESCE(mp.price_3m, mp.price_12m, p.material_unit_price, 0)
           * COALESCE(b.qty_per_pc, 1)
           / NULLIF(COALESCE(b.shared_factor, 1), 0)
    -- HEAT: products.heat_treat_per_pc (이미 per_pc)
    WHEN b.process_type = 'HEAT'
      THEN COALESCE(p.heat_treat_per_pc, 0)
    WHEN b.process_type = 'SURFACE'
      THEN COALESCE(p.surface_per_pc, 0)
    WHEN b.process_type = 'OUTSOURCE'
      THEN COALESCE(p.outsourcing_per_pc, 0)
    ELSE 0
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
  -- 공정행이 있는 경우만 해당 단가 적용 (DISTINCT 효과를 위해 MAX 사용)
  MAX(
    CASE WHEN b.process_type = 'HEAT'
    THEN COALESCE(p.heat_treat_per_pc, 0)
    ELSE 0 END
  ) AS heat_cost_per_pc,
  MAX(
    CASE WHEN b.process_type = 'SURFACE'
    THEN COALESCE(p.surface_per_pc, 0)
    ELSE 0 END
  ) AS surface_cost_per_pc,
  MAX(
    CASE WHEN b.process_type = 'OUTSOURCE'
    THEN COALESCE(p.outsourcing_per_pc, 0)
    ELSE 0 END
  ) AS outsource_cost_per_pc,
  -- 기타 공정 (PACKING/LABOR/OTHER) — 추후 process_cost_v 로 확장
  SUM(
    CASE WHEN b.process_type IN ('PACKING','LABOR','OTHER')
    THEN 0::numeric  -- 현재는 단가 없음. 향후 process_cost_v 도입 시 활성
    ELSE 0::numeric END
  ) AS other_cost_per_pc,
  -- ── 메타 ──
  COUNT(*)                                                                                AS bom_row_count,
  COUNT(*) FILTER (WHERE COALESCE(b.process_type,'MATERIAL') = 'MATERIAL')                AS material_rows,
  COUNT(*) FILTER (WHERE b.process_type IS NOT NULL AND b.process_type <> 'MATERIAL')     AS process_rows,
  -- 단가 출처 통계 (자재행 기준)
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
  -- legacy 호환 (008 컬럼) — BOM 가격 미사용 정책이지만 컬럼 유지
  COUNT(*) FILTER (WHERE b.unit_price IS NOT NULL)                                        AS rows_with_explicit_price
FROM bom b
LEFT JOIN material_price_v mp ON mp.material_id = b.material_id
LEFT JOIN products p ON p.product_id = b.product_id
WHERE (b.apply_end_date IS NULL OR b.apply_end_date >= CURRENT_DATE)
GROUP BY b.product_id;


COMMENT ON VIEW product_bom_cost_v IS
  'BOM 수량 × 가격(매입/원가). 가격 출처:
   MATERIAL = material_price_v(3M/12M) → products.material_unit_price
   HEAT/SURFACE/OUTSOURCE = products.{heat_treat,surface,outsourcing}_per_pc
   향후 process_cost_v 도입 시 공정행도 매입 기반 활성.';


-- ─────────────────────────────────────────
-- product_cost_full_v 도 새 view 사용하므로 재정의 (변경 없음, 참조 갱신)
-- ─────────────────────────────────────────
CREATE OR REPLACE VIEW product_cost_full_v AS
SELECT
  p.product_id,
  p.pn,
  p.customer,
  p.product_group,
  p.sub_class,
  p.archived_at,
  p.material,
  p.raw_material_name,
  p.raw_material_spec,
  p.cost_data_quality,
  -- ── Layer A: legacy 정적 스냅샷 ─────
  p.material_unit_price        AS legacy_material_per_pc,
  p.outsourcing_per_pc         AS legacy_outsource_per_pc,
  p.heat_treat_per_pc          AS legacy_heat_per_pc,
  p.surface_per_pc             AS legacy_surface_per_pc,
  p.estimated_cost_per_pc      AS legacy_estimated_cost,
  -- ── Layer B: BOM 자동 계산 ─────────
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
  -- ── Layer C: 생산실적 (Phase 3) ────
  ac.avg_cycle_time_sec,
  ac.defect_rate,
  ac.avg_efficiency_pct,
  ac.labor_cost_per_pc_est,
  ac.log_count_6m,
  -- ── Layer D: 매출/판매가 ───────────
  ps.avg_unit_price            AS sale_price,
  ps.total_sales_12m,
  ps.sales_count_12m,
  ps.abc_grade,
  ps.activity_trend,
  -- ── 통합 추정원가: BOM > legacy ────
  COALESCE(NULLIF(bc.bom_cost_per_pc, 0), p.estimated_cost_per_pc) AS final_cost_per_pc,
  -- ── 호환 alias (기존 UI 작동 보장) ──
  COALESCE(NULLIF(bc.bom_cost_per_pc, 0), p.estimated_cost_per_pc) AS estimated_cost_per_pc,
  COALESCE(NULLIF(bc.material_cost_per_pc, 0), p.material_unit_price) AS material_unit_price,
  COALESCE(NULLIF(bc.outsource_cost_per_pc, 0), p.outsourcing_per_pc) AS outsourcing_per_pc,
  COALESCE(NULLIF(bc.heat_cost_per_pc, 0), p.heat_treat_per_pc)       AS heat_treat_per_pc,
  COALESCE(NULLIF(bc.surface_cost_per_pc, 0), p.surface_per_pc)       AS surface_per_pc,
  p.material_kg_price,
  -- ── 마진 계산 ─────────────────────
  CASE
    WHEN ps.avg_unit_price > 0
     AND COALESCE(NULLIF(bc.bom_cost_per_pc, 0), p.estimated_cost_per_pc) > 0
    THEN ROUND(
      (ps.avg_unit_price - COALESCE(NULLIF(bc.bom_cost_per_pc, 0), p.estimated_cost_per_pc))
      / ps.avg_unit_price * 100, 1)
    ELSE NULL
  END AS margin_pct_calc,
  -- 호환 alias
  CASE
    WHEN ps.avg_unit_price > 0
     AND COALESCE(NULLIF(bc.bom_cost_per_pc, 0), p.estimated_cost_per_pc) > 0
    THEN ROUND(
      (ps.avg_unit_price - COALESCE(NULLIF(bc.bom_cost_per_pc, 0), p.estimated_cost_per_pc))
      / ps.avg_unit_price * 100, 1)
    ELSE NULL
  END AS margin_pct,
  -- ── 데이터 신뢰도 ────────────────
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
