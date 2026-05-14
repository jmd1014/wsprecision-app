-- ════════════════════════════════════════════════════════════
-- Migration 008: 통합 원가 view 4종
-- ════════════════════════════════════════════════════════════
-- 목적:
--   매입/매출/생산 raw 데이터와 BOM 을 결합해 원가/마진을 자동 계산.
--   각 view 는 데이터가 부족해도 NULL/0 로 graceful degrade.
--   기존 정적 컬럼은 fallback 으로 활용.
--
-- 의존:
--   purchase_ledger.matched_material_id  (007 추가)
--   production_log.product_id            (007 추가)
--   bom.process_type / unit_price        (007 추가)
-- ════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────
-- 1. material_price_v : 자재별 시점 단가
-- ─────────────────────────────────────────
-- purchase_ledger 에서 자재별 평균/최근 단가 산출.
-- matched_material_id 가 채워진 만큼만 활성. 미매핑 자재는 NULL.
CREATE OR REPLACE VIEW material_price_v AS
SELECT
  m.material_id,
  m.raw_name,
  m.material_type,
  m.spec,
  m.unit                                                                       AS material_unit,
  -- 시점별 평균 단가
  AVG(pl.unit_price) FILTER (WHERE pl.trade_date >= CURRENT_DATE - INTERVAL '3 months')   AS price_3m,
  AVG(pl.unit_price) FILTER (WHERE pl.trade_date >= CURRENT_DATE - INTERVAL '12 months')  AS price_12m,
  AVG(pl.kg_price)   FILTER (WHERE pl.trade_date >= CURRENT_DATE - INTERVAL '12 months')  AS kg_price_12m,
  AVG(pl.ea_price)   FILTER (WHERE pl.trade_date >= CURRENT_DATE - INTERVAL '12 months')  AS ea_price_12m,
  -- 최근 단가
  (SELECT pl2.unit_price
     FROM purchase_ledger pl2
     WHERE pl2.matched_material_id = m.material_id
     ORDER BY pl2.trade_date DESC NULLS LAST
     LIMIT 1)                                                                  AS price_last,
  MAX(pl.trade_date)                                                           AS last_purchase_date,
  COUNT(pl.ledger_id) FILTER (WHERE pl.trade_date >= CURRENT_DATE - INTERVAL '12 months') AS purchase_count_12m,
  COUNT(pl.ledger_id)                                                          AS purchase_count_total
FROM materials m
LEFT JOIN purchase_ledger pl ON pl.matched_material_id = m.material_id
GROUP BY m.material_id, m.raw_name, m.material_type, m.spec, m.unit;


-- ─────────────────────────────────────────
-- 2. product_bom_cost_v : BOM 기반 자동 원가
-- ─────────────────────────────────────────
-- 공식: per_pc = unit_price × qty_per_pc / shared_factor
-- 단가 우선순위:
--   ① bom.unit_price (행 직접 입력)
--   ② material_price_v.price_3m (최근 3개월)
--   ③ material_price_v.price_12m
--   ④ 0
CREATE OR REPLACE VIEW product_bom_cost_v AS
SELECT
  b.product_id,
  -- 합계
  SUM(
    COALESCE(b.unit_price, mp.price_3m, mp.price_12m, 0)
    * COALESCE(b.qty_per_pc, 1)
    / NULLIF(COALESCE(b.shared_factor, 1), 0)
  ) AS bom_cost_per_pc,
  -- 항목별 분해 (process_type 기준)
  SUM(
    CASE WHEN COALESCE(b.process_type,'MATERIAL') = 'MATERIAL'
    THEN COALESCE(b.unit_price, mp.price_3m, mp.price_12m, 0)
         * COALESCE(b.qty_per_pc, 1)
         / NULLIF(COALESCE(b.shared_factor, 1), 0)
    ELSE 0 END
  ) AS material_cost_per_pc,
  SUM(
    CASE WHEN b.process_type = 'HEAT'
    THEN COALESCE(b.unit_price, 0) * COALESCE(b.qty_per_pc, 1)
         / NULLIF(COALESCE(b.shared_factor, 1), 0)
    ELSE 0 END
  ) AS heat_cost_per_pc,
  SUM(
    CASE WHEN b.process_type = 'SURFACE'
    THEN COALESCE(b.unit_price, 0) * COALESCE(b.qty_per_pc, 1)
         / NULLIF(COALESCE(b.shared_factor, 1), 0)
    ELSE 0 END
  ) AS surface_cost_per_pc,
  SUM(
    CASE WHEN b.process_type = 'OUTSOURCE'
    THEN COALESCE(b.unit_price, 0) * COALESCE(b.qty_per_pc, 1)
         / NULLIF(COALESCE(b.shared_factor, 1), 0)
    ELSE 0 END
  ) AS outsource_cost_per_pc,
  SUM(
    CASE WHEN b.process_type IN ('PACKING','LABOR','OTHER')
    THEN COALESCE(b.unit_price, 0) * COALESCE(b.qty_per_pc, 1)
         / NULLIF(COALESCE(b.shared_factor, 1), 0)
    ELSE 0 END
  ) AS other_cost_per_pc,
  -- BOM 메타
  COUNT(*)                                                AS bom_row_count,
  COUNT(*) FILTER (WHERE COALESCE(b.process_type,'MATERIAL') = 'MATERIAL') AS material_rows,
  COUNT(*) FILTER (WHERE b.process_type <> 'MATERIAL'
                   AND b.process_type IS NOT NULL)        AS process_rows,
  -- 단가 출처 통계
  COUNT(*) FILTER (WHERE b.unit_price IS NOT NULL)        AS rows_with_explicit_price,
  COUNT(*) FILTER (WHERE b.unit_price IS NULL
                   AND mp.price_3m IS NOT NULL)           AS rows_using_3m_avg,
  COUNT(*) FILTER (WHERE b.unit_price IS NULL
                   AND mp.price_3m IS NULL
                   AND mp.price_12m IS NULL)              AS rows_with_no_price
FROM bom b
LEFT JOIN material_price_v mp ON mp.material_id = b.material_id
WHERE (b.apply_end_date IS NULL OR b.apply_end_date >= CURRENT_DATE)
GROUP BY b.product_id;


-- ─────────────────────────────────────────
-- 3. product_actual_cost_v : 생산실적 기반 실원가 (Phase 3 활성)
-- ─────────────────────────────────────────
-- production_log.product_id 가 채워지면 자동 산출.
-- 노무비 단가는 상수 (HOURLY_LABOR_KRW) — 추후 운영 설정 테이블로 분리 권장.
CREATE OR REPLACE VIEW product_actual_cost_v AS
SELECT
  pl.product_id,
  AVG(pl.cycle_time)                          AS avg_cycle_time_sec,
  AVG(NULLIF(pl.total_qty, 0))                AS avg_lot_size,
  COALESCE(
    SUM(pl.defect_qty) * 1.0 / NULLIF(SUM(pl.total_qty), 0),
    0
  )                                            AS defect_rate,
  AVG(pl.efficiency_pct)                       AS avg_efficiency_pct,
  AVG(pl.uph_actual)                           AS avg_uph_actual,
  -- 추정 노무비/EA (cycle_time 초 × 시간당 노무단가)
  -- 노무단가 23,000원/시간 가정 (추후 설정 테이블로)
  AVG(pl.cycle_time) * (23000.0 / 3600.0)      AS labor_cost_per_pc_est,
  COUNT(*)                                     AS log_count_6m,
  MAX(pl.log_date)                             AS last_log_date
FROM production_log pl
WHERE pl.log_date >= CURRENT_DATE - INTERVAL '6 months'
  AND pl.product_id IS NOT NULL
GROUP BY pl.product_id;


-- ─────────────────────────────────────────
-- 4. product_cost_full_v : 통합 view (UI 권장 진입점)
-- ─────────────────────────────────────────
-- 정적 스냅샷(legacy) + BOM 자동 + 생산실적 + 매출 → 통합 마진.
-- cost_source 신호로 데이터 신뢰도 표기.
CREATE OR REPLACE VIEW product_cost_full_v AS
SELECT
  p.product_id,
  p.pn,
  p.customer,
  p.product_group,
  p.sub_class,
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
  -- ── 통합 추정원가 (BOM 우선, 없으면 legacy) ──
  COALESCE(NULLIF(bc.bom_cost_per_pc, 0), p.estimated_cost_per_pc) AS final_cost_per_pc,
  -- ── 마진 계산 (final_cost 기준) ───
  CASE
    WHEN ps.avg_unit_price > 0
     AND COALESCE(NULLIF(bc.bom_cost_per_pc, 0), p.estimated_cost_per_pc) > 0
    THEN ROUND(
      (ps.avg_unit_price - COALESCE(NULLIF(bc.bom_cost_per_pc, 0), p.estimated_cost_per_pc))
      / ps.avg_unit_price * 100, 1)
    ELSE NULL
  END AS margin_pct_calc,
  -- ── 데이터 신뢰도 신호 ─────────────
  CASE
    WHEN bc.bom_row_count > 0
     AND bc.rows_with_no_price = 0
     AND bc.material_rows > 0       THEN 'BOM_FULL'      -- BOM 완전 + 단가 모두 있음
    WHEN bc.bom_row_count > 0
     AND bc.material_rows > 0       THEN 'BOM_PARTIAL'   -- BOM 있으나 단가 일부 누락
    WHEN p.estimated_cost_per_pc > 0 THEN 'LEGACY_ONLY'  -- 정적 스냅샷만
    ELSE 'NO_DATA'
  END AS cost_source
FROM products p
LEFT JOIN product_bom_cost_v   bc ON bc.product_id = p.product_id
LEFT JOIN product_actual_cost_v ac ON ac.product_id = p.product_id
LEFT JOIN product_stats        ps ON ps.product_id = p.product_id;


COMMENT ON VIEW material_price_v       IS '자재별 시점 단가 (purchase_ledger.matched_material_id 기반)';
COMMENT ON VIEW product_bom_cost_v     IS 'BOM × 자재단가 자동 원가. unit_price → 3M평균 → 12M평균 fallback.';
COMMENT ON VIEW product_actual_cost_v  IS '생산실적 기반 실원가. production_log.product_id 매핑 시 활성.';
COMMENT ON VIEW product_cost_full_v    IS '통합 view. UI 진입점. cost_source 컬럼으로 신뢰도 표기.';
