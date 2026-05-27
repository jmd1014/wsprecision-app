-- ════════════════════════════════════════════════════════════
-- Migration 014: 자재 가격 출처 상태 view
-- ════════════════════════════════════════════════════════════
-- 배경:
--   BOM 자재 연결은 잘 되어 있는데(material_id 채워짐), 자재 가격이
--   어디서 오는지(매입 매핑 / legacy 스냅샷 / 없음) 한눈에 안 보임.
--   원가 분석 시 가격 출처를 명확히 표시할 필요.
--
-- 변경 내용:
--   1. product_material_price_status_v   각 BOM 자재행의 가격 출처 / 유효 가격
--   2. material_price_coverage_v          BOM 자재 가격 보유율 전체 요약
--
-- 비파괴: CREATE OR REPLACE VIEW. 새 view 만 추가.
-- ════════════════════════════════════════════════════════════


-- ─────────────────────────────────────────
-- 1. product_material_price_status_v
--    BOM 자재행 단위로 가격 출처 + 유효 가격
-- ─────────────────────────────────────────
CREATE OR REPLACE VIEW product_material_price_status_v AS
SELECT
  b.product_id,
  p.pn,
  p.customer,
  p.procurement_type,
  p.archived_at,
  b.bom_id,
  b.material_id,
  b.raw_material_name                                              AS bom_material_name,
  m.raw_name                                                       AS master_raw_name,
  m.material_type,
  m.spec,
  b.qty_per_pc,
  b.shared_factor,
  -- 매입 매핑에서 온 가격
  mp.purchase_count_12m,
  mp.price_3m                                                      AS purchase_price_3m,
  mp.price_12m                                                     AS purchase_price_12m,
  mp.last_purchase_date,
  -- products legacy 스냅샷
  p.material_unit_price                                            AS legacy_price,
  -- 가격 출처 (우선순위 적용)
  CASE
    WHEN mp.price_3m IS NOT NULL                              THEN 'PURCHASE_3M'
    WHEN mp.price_12m IS NOT NULL                             THEN 'PURCHASE_12M'
    WHEN p.material_unit_price IS NOT NULL
     AND p.material_unit_price > 0                            THEN 'LEGACY'
    WHEN p.procurement_type = '사급'                          THEN 'NA_SAGEUP'
    ELSE 'NONE'
  END                                                              AS price_source,
  -- 유효 가격
  COALESCE(mp.price_3m, mp.price_12m,
           NULLIF(p.material_unit_price, 0))                       AS effective_price,
  -- 매입 매핑 이력 존재 여부 (어떤 raw 거래가 있는지)
  EXISTS (
    SELECT 1 FROM purchase_ledger pl
    WHERE pl.matched_material_id = b.material_id
  )                                                                AS has_purchase_history
FROM bom b
LEFT JOIN products p           ON p.product_id = b.product_id
LEFT JOIN materials m          ON m.material_id = b.material_id
LEFT JOIN material_price_v mp  ON mp.material_id = b.material_id
WHERE COALESCE(b.process_type, 'MATERIAL') = 'MATERIAL';

COMMENT ON VIEW product_material_price_status_v IS
  'BOM 자재행 단위 가격 출처 진단. price_source: PURCHASE_3M / PURCHASE_12M / LEGACY / NA_SAGEUP / NONE.';


-- ─────────────────────────────────────────
-- 2. material_price_coverage_v
--    활성 제품 BOM 자재행 기준 가격 보유율 요약
-- ─────────────────────────────────────────
CREATE OR REPLACE VIEW material_price_coverage_v AS
SELECT
  COUNT(*) FILTER (WHERE archived_at IS NULL)                          AS total_active_bom_material_rows,
  COUNT(*) FILTER (WHERE archived_at IS NULL
                   AND price_source = 'PURCHASE_3M')                   AS price_purchase_3m,
  COUNT(*) FILTER (WHERE archived_at IS NULL
                   AND price_source = 'PURCHASE_12M')                  AS price_purchase_12m,
  COUNT(*) FILTER (WHERE archived_at IS NULL
                   AND price_source = 'LEGACY')                        AS price_legacy,
  COUNT(*) FILTER (WHERE archived_at IS NULL
                   AND price_source = 'NA_SAGEUP')                     AS price_na_sageup,
  COUNT(*) FILTER (WHERE archived_at IS NULL
                   AND price_source = 'NONE')                          AS price_none,
  -- 비율
  ROUND(100.0 * COUNT(*) FILTER (WHERE archived_at IS NULL
                                  AND price_source IN ('PURCHASE_3M','PURCHASE_12M'))
        / NULLIF(COUNT(*) FILTER (WHERE archived_at IS NULL), 0), 1)   AS pct_from_purchase,
  ROUND(100.0 * COUNT(*) FILTER (WHERE archived_at IS NULL
                                  AND price_source = 'LEGACY')
        / NULLIF(COUNT(*) FILTER (WHERE archived_at IS NULL), 0), 1)   AS pct_from_legacy,
  ROUND(100.0 * COUNT(*) FILTER (WHERE archived_at IS NULL
                                  AND price_source = 'NONE')
        / NULLIF(COUNT(*) FILTER (WHERE archived_at IS NULL), 0), 1)   AS pct_none
FROM product_material_price_status_v;

COMMENT ON VIEW material_price_coverage_v IS
  '활성 제품 BOM 자재행 가격 출처 분포. 매입 매핑이 채워지면 PURCHASE 비율 자동 상승.';
