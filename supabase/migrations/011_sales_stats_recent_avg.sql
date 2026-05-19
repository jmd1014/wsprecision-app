-- ════════════════════════════════════════════════════════════
-- Migration 011: product_stats.avg_unit_price → 12M 필터 적용
-- ════════════════════════════════════════════════════════════
-- 증상:
--   UI 라벨은 "평균 판매가 (12M)" 인데 실제 계산은 전체 기간 평균.
--   예) MRG6-07: 12M 거래는 모두 2,000원, 하지만 avg_unit_price=1,840
--       (과거 더 낮은 단가 거래가 평균에 섞임)
--
-- 수정:
--   avg_unit_price 의 정의를 12M 필터로 변경 (라벨과 일치).
--   추가 컬럼: avg_unit_price_3m, avg_unit_price_12m, avg_unit_price_all,
--             last_unit_price (감사·추적용)
--
-- 영향:
--   - product_stats.avg_unit_price 값 변경 → 마진 산출 갱신 (정확화)
--   - product_cost_full_v.avg_unit_price / sale_price / margin_pct
--     자동 재계산 (view 의존성)
--
-- 호환성:
--   기존 컬럼 순서/타입 유지 + 새 컬럼 끝에 추가 → CREATE OR REPLACE 안전.
-- ════════════════════════════════════════════════════════════

CREATE OR REPLACE VIEW product_stats AS
SELECT
  p.product_id,
  p.pn,
  -- 전체 누적
  COALESCE(s.sales_count, 0)                                      AS sales_count,
  COALESCE(s.total_qty, 0)                                        AS total_qty,
  COALESCE(s.total_sales, 0)                                      AS total_sales,
  -- ⭐ avg_unit_price = 12M 평균 (없으면 전체기간 fallback) — 정의 변경
  COALESCE(s.avg_unit_price_12m, s.avg_unit_price_all, 0)         AS avg_unit_price,
  s.last_trade_date,
  s.first_trade_date,
  -- 12M
  COALESCE(s.sales_count_12m, 0)                                  AS sales_count_12m,
  COALESCE(s.total_qty_12m, 0)                                    AS total_qty_12m,
  COALESCE(s.total_sales_12m, 0)                                  AS total_sales_12m,
  -- 이번/지난달
  COALESCE(s.sales_count_thism, 0)                                AS sales_count_thism,
  COALESCE(s.total_sales_thism, 0)                                AS total_sales_thism,
  COALESCE(s.sales_count_lastm, 0)                                AS sales_count_lastm,
  COALESCE(s.total_sales_lastm, 0)                                AS total_sales_lastm,
  -- 매입
  COALESCE(b.purchase_count, 0)                                   AS purchase_count_12m,
  COALESCE(b.purchase_amount, 0)                                  AS purchase_amount_12m,
  -- 휴면일수
  CASE
    WHEN s.last_trade_date IS NULL THEN 99999
    ELSE (CURRENT_DATE - s.last_trade_date)
  END                                                              AS dormant_days,
  -- ABC 등급
  CASE
    WHEN COALESCE(s.total_sales_12m, 0) > 100000000 THEN 'A'
    WHEN COALESCE(s.total_sales_12m, 0) > 30000000  THEN 'B'
    WHEN COALESCE(s.total_sales_12m, 0) > 5000000   THEN 'C'
    WHEN COALESCE(s.total_sales_12m, 0) > 0         THEN 'D'
    ELSE 'X'
  END                                                              AS abc_grade,
  -- 활동 추세
  CASE
    WHEN COALESCE(s.total_sales_lastm, 0) = 0 AND COALESCE(s.total_sales_thism, 0) > 0 THEN '🔥 신규'
    WHEN COALESCE(s.total_sales_thism, 0) > COALESCE(s.total_sales_lastm, 0) * 1.2     THEN '↗ 증가'
    WHEN COALESCE(s.total_sales_thism, 0) < COALESCE(s.total_sales_lastm, 0) * 0.8     THEN '↘ 감소'
    WHEN COALESCE(s.total_sales_thism, 0) = 0 AND COALESCE(s.total_sales_lastm, 0) > 0 THEN '⚠ 휴면진입'
    ELSE '→ 유지'
  END                                                              AS activity_trend,
  -- 마진율 (12M 평균 기준)
  CASE
    WHEN COALESCE(s.avg_unit_price_12m, s.avg_unit_price_all, 0) > 0
     AND p.estimated_cost_per_pc > 0
    THEN ROUND(
      (COALESCE(s.avg_unit_price_12m, s.avg_unit_price_all)
        - p.estimated_cost_per_pc)
      / COALESCE(s.avg_unit_price_12m, s.avg_unit_price_all) * 100, 1)
    ELSE NULL
  END                                                              AS margin_pct,
  -- ── 신규 컬럼 (끝에 추가) ──
  COALESCE(s.avg_unit_price_3m, 0)                                AS avg_unit_price_3m,
  COALESCE(s.avg_unit_price_12m, 0)                               AS avg_unit_price_12m,
  COALESCE(s.avg_unit_price_all, 0)                               AS avg_unit_price_all,
  s.last_unit_price
FROM products p
LEFT JOIN (
  SELECT
    product_id,
    COUNT(*)                                                       AS sales_count,
    SUM(qty)                                                        AS total_qty,
    SUM(amount)                                                     AS total_sales,
    -- 시점별 평균
    AVG(unit_price) FILTER (WHERE item_date >= CURRENT_DATE - INTERVAL '12 months') AS avg_unit_price_12m,
    AVG(unit_price) FILTER (WHERE item_date >= CURRENT_DATE - INTERVAL '3 months')  AS avg_unit_price_3m,
    AVG(unit_price)                                                 AS avg_unit_price_all,
    -- 최근 단가 (item_date 가장 최근 행)
    (ARRAY_AGG(unit_price ORDER BY item_date DESC NULLS LAST))[1]   AS last_unit_price,
    MAX(item_date)                                                  AS last_trade_date,
    MIN(item_date)                                                  AS first_trade_date,
    COUNT(*) FILTER (WHERE item_date >= CURRENT_DATE - INTERVAL '12 months') AS sales_count_12m,
    SUM(qty)  FILTER (WHERE item_date >= CURRENT_DATE - INTERVAL '12 months') AS total_qty_12m,
    SUM(amount) FILTER (WHERE item_date >= CURRENT_DATE - INTERVAL '12 months') AS total_sales_12m,
    COUNT(*)  FILTER (WHERE date_trunc('month', item_date) = date_trunc('month', CURRENT_DATE)) AS sales_count_thism,
    SUM(amount) FILTER (WHERE date_trunc('month', item_date) = date_trunc('month', CURRENT_DATE)) AS total_sales_thism,
    COUNT(*)  FILTER (WHERE date_trunc('month', item_date) = date_trunc('month', CURRENT_DATE - INTERVAL '1 month')) AS sales_count_lastm,
    SUM(amount) FILTER (WHERE date_trunc('month', item_date) = date_trunc('month', CURRENT_DATE - INTERVAL '1 month')) AS total_sales_lastm
  FROM sales_ledger
  WHERE product_id IS NOT NULL
  GROUP BY product_id
) s ON s.product_id = p.product_id
LEFT JOIN (
  SELECT
    matched_pn,
    COUNT(*)    AS purchase_count,
    SUM(amount) AS purchase_amount
  FROM purchase_ledger
  WHERE matched_pn IS NOT NULL
    AND trade_date >= CURRENT_DATE - INTERVAL '12 months'
  GROUP BY matched_pn
) b ON b.matched_pn = p.pn;


COMMENT ON VIEW product_stats IS
  'product_stats — avg_unit_price 는 12M 필터 적용 (라벨 일치). '
  'avg_unit_price_3m/_12m/_all/last_unit_price 별도 컬럼 제공 (감사·시계열).';
