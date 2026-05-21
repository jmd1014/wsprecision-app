-- ════════════════════════════════════════════════════════════
-- Migration 013: 활성 마스터 정비 view + 자재 매칭 view 6종
-- ════════════════════════════════════════════════════════════
-- 배경:
--   마스터 안정화 단계 진입.
--   - 활성 제품 235건만 정비 대상 (휴면 599건 제외)
--   - purchase_ledger.matched_material_id ≈ 0% → 자재 매칭 최우선
--   - "후보 → 사용자 확인 → 반영" 흐름 위한 view 기반
--
-- 변경 내용:
--   1. active_bom_completion_v       활성 제품 BOM 완성도
--   2. bom_missing_active_products_v BOM 없는 활성 제품 (정비 대상)
--   3. bom_cleanup_todo_v            정비 우선순위 (불완전 BOM)
--   4. unresolved_purchase_materials 미매핑 매입 그룹핑
--   5. material_mapping_candidates   자재 후보 추천 (신뢰도 점수)
--   6. purchase_material_match_progress 매핑 진행률
--
-- 의존:
--   - products, bom (07), materials, purchase_ledger (07),
--     product_stats (11)
--
-- 비파괴:
--   모든 CREATE OR REPLACE VIEW. 새 view 만 추가. 기존 view 영향 없음.
--
-- 적용 후 검증:
--   SELECT completion_status, count(*) FROM active_bom_completion_v
--     GROUP BY 1;
--   SELECT * FROM purchase_material_match_progress;
-- ════════════════════════════════════════════════════════════


-- ─────────────────────────────────────────
-- 1. active_bom_completion_v
--    활성 제품별 BOM 완성도 + 무결성 체크
-- ─────────────────────────────────────────
CREATE OR REPLACE VIEW active_bom_completion_v AS
SELECT
  p.product_id,
  p.pn,
  p.customer,
  p.product_group,
  p.sub_class,
  -- BOM 행 카운트
  COUNT(b.bom_id)                                                              AS bom_row_count,
  COUNT(b.bom_id) FILTER (WHERE COALESCE(b.process_type,'MATERIAL') = 'MATERIAL') AS material_row_count,
  COUNT(b.bom_id) FILTER (WHERE b.process_type IS NOT NULL
                          AND b.process_type <> 'MATERIAL')                    AS process_row_count,
  -- 무결성 체크
  COUNT(b.bom_id) FILTER (WHERE b.material_id IS NULL
                          AND COALESCE(b.process_type,'MATERIAL') = 'MATERIAL') AS missing_material_id,
  COUNT(b.bom_id) FILTER (WHERE b.qty_per_pc IS NULL OR b.qty_per_pc = 0)      AS missing_qty,
  COUNT(b.bom_id) FILTER (WHERE b.shared_factor IS NULL OR b.shared_factor = 0) AS missing_sf,
  COUNT(b.bom_id) FILTER (WHERE COALESCE(b.verification_status,'') <> '확인완료') AS unverified,
  -- 상태 분류
  CASE
    WHEN COUNT(b.bom_id) = 0 THEN 'NO_BOM'
    WHEN COUNT(b.bom_id) FILTER (WHERE b.material_id IS NULL
                                  AND COALESCE(b.process_type,'MATERIAL') = 'MATERIAL') > 0
      THEN 'INCOMPLETE'
    WHEN COUNT(b.bom_id) FILTER (WHERE b.qty_per_pc IS NULL OR b.qty_per_pc = 0) > 0
      THEN 'INCOMPLETE'
    WHEN COUNT(b.bom_id) FILTER (WHERE b.shared_factor IS NULL OR b.shared_factor = 0) > 0
      THEN 'INCOMPLETE'
    WHEN COUNT(b.bom_id) FILTER (WHERE COALESCE(b.verification_status,'') <> '확인완료') > 0
      THEN 'UNVERIFIED'
    ELSE 'COMPLETE'
  END                                                                          AS completion_status
FROM products p
LEFT JOIN bom b ON b.product_id = p.product_id
WHERE p.archived_at IS NULL
GROUP BY p.product_id, p.pn, p.customer, p.product_group, p.sub_class;

COMMENT ON VIEW active_bom_completion_v IS
  '활성 제품별 BOM 완성도. completion_status: NO_BOM/INCOMPLETE/UNVERIFIED/COMPLETE.';


-- ─────────────────────────────────────────
-- 2. bom_missing_active_products_v
--    BOM 미보유 활성 제품 (가장 시급한 정비 대상)
-- ─────────────────────────────────────────
CREATE OR REPLACE VIEW bom_missing_active_products_v AS
SELECT
  p.product_id,
  p.pn,
  p.customer,
  p.product_group,
  p.sub_class,
  p.material,
  p.raw_material_name,
  p.raw_material_spec,
  p.material_unit_price,
  p.estimated_cost_per_pc,
  COALESCE(ps.total_sales_12m, 0)                  AS total_sales_12m,
  COALESCE(ps.sales_count_12m, 0)                  AS sales_count_12m,
  COALESCE(ps.abc_grade, 'X')                      AS abc_grade,
  COALESCE(ps.activity_trend, '-')                 AS activity_trend
FROM products p
LEFT JOIN product_stats ps ON ps.product_id = p.product_id
WHERE p.archived_at IS NULL
  AND NOT EXISTS (SELECT 1 FROM bom b WHERE b.product_id = p.product_id);

COMMENT ON VIEW bom_missing_active_products_v IS
  'BOM 미연결 활성 제품. 매출 큰 순으로 정비 권장.';


-- ─────────────────────────────────────────
-- 3. bom_cleanup_todo_v
--    BOM 있지만 불완전한 활성 제품 (정비 우선순위 자동 부여)
-- ─────────────────────────────────────────
CREATE OR REPLACE VIEW bom_cleanup_todo_v AS
SELECT
  c.product_id,
  c.pn,
  c.customer,
  c.product_group,
  c.completion_status,
  c.bom_row_count,
  c.material_row_count,
  c.process_row_count,
  c.missing_material_id,
  c.missing_qty,
  c.missing_sf,
  c.unverified,
  COALESCE(ps.total_sales_12m, 0)         AS total_sales_12m,
  COALESCE(ps.sales_count_12m, 0)         AS sales_count_12m,
  COALESCE(ps.abc_grade, 'X')             AS abc_grade,
  -- 우선순위: 매출 있고 불완전한 것 우선
  CASE
    WHEN c.completion_status = 'NO_BOM' AND ps.total_sales_12m > 0     THEN 1
    WHEN c.completion_status = 'INCOMPLETE' AND ps.total_sales_12m > 0 THEN 2
    WHEN c.completion_status = 'UNVERIFIED' AND ps.total_sales_12m > 0 THEN 3
    WHEN c.completion_status = 'NO_BOM'                                THEN 4
    WHEN c.completion_status = 'INCOMPLETE'                            THEN 5
    WHEN c.completion_status = 'UNVERIFIED'                            THEN 6
    ELSE 99
  END                                      AS priority
FROM active_bom_completion_v c
LEFT JOIN product_stats ps ON ps.product_id = c.product_id
WHERE c.completion_status <> 'COMPLETE';

COMMENT ON VIEW bom_cleanup_todo_v IS
  '활성 제품 중 BOM 불완전 항목. priority 1=긴급(매출+NO_BOM) ~ 6=낮음.';


-- ─────────────────────────────────────────
-- 4. unresolved_purchase_materials
--    미매핑 매입 거래 그룹핑 (item + vendor + category 기준)
-- ─────────────────────────────────────────
CREATE OR REPLACE VIEW unresolved_purchase_materials AS
SELECT
  LOWER(TRIM(pl.item))                                  AS item_key,
  pl.item,
  pl.vendor_normalized,
  pl.category,
  COUNT(*)                                              AS purchase_count,
  AVG(pl.unit_price)                                    AS avg_unit_price,
  AVG(pl.kg_price)                                      AS avg_kg_price,
  AVG(pl.ea_price)                                      AS avg_ea_price,
  MAX(pl.trade_date)                                    AS last_purchase_date,
  MIN(pl.trade_date)                                    AS first_purchase_date,
  SUM(pl.amount)                                        AS total_amount,
  -- 표시용
  STRING_AGG(DISTINCT pl.vendor, ', ' ORDER BY pl.vendor) AS vendors_text
FROM purchase_ledger pl
WHERE pl.matched_material_id IS NULL
  AND pl.item IS NOT NULL
  AND TRIM(pl.item) <> ''
GROUP BY LOWER(TRIM(pl.item)), pl.item, pl.vendor_normalized, pl.category;

COMMENT ON VIEW unresolved_purchase_materials IS
  '미매핑 매입 거래를 item+vendor+category 로 그룹핑. 매칭 화면 입력.';


-- ─────────────────────────────────────────
-- 5. material_mapping_candidates
--    각 미매핑 그룹에 대한 자재 후보 추천 (신뢰도 점수 포함)
-- ─────────────────────────────────────────
-- LATERAL JOIN 으로 각 unresolved item 당 최대 5개 후보만 반환 (성능)
CREATE OR REPLACE VIEW material_mapping_candidates AS
SELECT
  upm.item_key,
  upm.item,
  upm.vendor_normalized,
  upm.category,
  upm.purchase_count,
  upm.avg_unit_price,
  upm.last_purchase_date,
  m.material_id,
  m.raw_name,
  m.material_type,
  m.spec,
  m.unit,
  m.main_supplier,
  m.confidence_score
FROM unresolved_purchase_materials upm
CROSS JOIN LATERAL (
  SELECT
    mm.material_id, mm.raw_name, mm.material_type, mm.spec,
    mm.unit, mm.main_supplier,
    -- 신뢰도 점수 (100=완전일치, 80=raw_name 포함, ...)
    CASE
      WHEN LOWER(mm.raw_name) = LOWER(upm.item)                                  THEN 100
      WHEN LOWER(mm.raw_name) LIKE '%' || LOWER(upm.item) || '%'                  THEN 80
      WHEN LOWER(upm.item)    LIKE '%' || LOWER(mm.raw_name) || '%'               THEN 75
      WHEN mm.material_type IS NOT NULL
       AND LOWER(upm.item) LIKE '%' || LOWER(mm.material_type) || '%'             THEN 50
      WHEN mm.spec IS NOT NULL
       AND LOWER(upm.item) LIKE '%' || LOWER(mm.spec) || '%'                      THEN 40
      WHEN mm.main_supplier IS NOT NULL
       AND upm.vendor_normalized IS NOT NULL
       AND LOWER(mm.main_supplier) = LOWER(upm.vendor_normalized)                 THEN 30
      ELSE 0
    END                                                                          AS confidence_score
  FROM materials mm
  WHERE
    (LOWER(mm.raw_name)        LIKE '%' || LOWER(upm.item) || '%'
     OR LOWER(upm.item)        LIKE '%' || LOWER(mm.raw_name) || '%'
     OR (mm.material_type IS NOT NULL
         AND LOWER(upm.item) LIKE '%' || LOWER(mm.material_type) || '%')
     OR (mm.spec IS NOT NULL
         AND LOWER(upm.item) LIKE '%' || LOWER(mm.spec) || '%')
     OR (mm.main_supplier IS NOT NULL
         AND upm.vendor_normalized IS NOT NULL
         AND LOWER(mm.main_supplier) = LOWER(upm.vendor_normalized))
    )
  ORDER BY
    CASE
      WHEN LOWER(mm.raw_name) = LOWER(upm.item)                                  THEN 100
      WHEN LOWER(mm.raw_name) LIKE '%' || LOWER(upm.item) || '%'                  THEN 80
      WHEN LOWER(upm.item)    LIKE '%' || LOWER(mm.raw_name) || '%'               THEN 75
      WHEN mm.material_type IS NOT NULL
       AND LOWER(upm.item) LIKE '%' || LOWER(mm.material_type) || '%'             THEN 50
      WHEN mm.spec IS NOT NULL
       AND LOWER(upm.item) LIKE '%' || LOWER(mm.spec) || '%'                      THEN 40
      ELSE 0
    END DESC,
    mm.material_id
  LIMIT 5
) m
WHERE upm.purchase_count >= 1;

COMMENT ON VIEW material_mapping_candidates IS
  '미매핑 매입 그룹별 자재 후보 (최대 5개). confidence_score 0-100. 자동 확정 금지.';


-- ─────────────────────────────────────────
-- 6. purchase_material_match_progress
--    매핑 진행률 (전체 + MAT_* 카테고리)
-- ─────────────────────────────────────────
CREATE OR REPLACE VIEW purchase_material_match_progress AS
SELECT
  COUNT(*)                                                                  AS total_purchase_rows,
  COUNT(*) FILTER (WHERE matched_material_id IS NOT NULL)                   AS matched_rows,
  COUNT(*) FILTER (WHERE matched_material_id IS NULL)                       AS unmatched_rows,
  ROUND(100.0 * COUNT(*) FILTER (WHERE matched_material_id IS NOT NULL)
        / NULLIF(COUNT(*), 0), 1)                                           AS match_rate_pct,
  -- 자재 카테고리만 (MAT_*)
  COUNT(*) FILTER (WHERE category ILIKE 'MAT%')                             AS total_mat_rows,
  COUNT(*) FILTER (WHERE category ILIKE 'MAT%'
                   AND matched_material_id IS NOT NULL)                     AS matched_mat_rows,
  ROUND(100.0 * COUNT(*) FILTER (WHERE category ILIKE 'MAT%'
                                  AND matched_material_id IS NOT NULL)
        / NULLIF(COUNT(*) FILTER (WHERE category ILIKE 'MAT%'), 0), 1)      AS mat_match_rate_pct,
  -- distinct 미매핑 item 수
  (SELECT COUNT(DISTINCT LOWER(TRIM(item)))
   FROM purchase_ledger
   WHERE matched_material_id IS NULL
     AND item IS NOT NULL AND TRIM(item) <> '')                             AS unique_unresolved_items
FROM purchase_ledger;

COMMENT ON VIEW purchase_material_match_progress IS
  '매입 ledger → materials 매핑 진행률. mat_match_rate_pct ≥ 80 이면 단계 종료 기준 충족.';
