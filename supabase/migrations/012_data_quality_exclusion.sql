-- ════════════════════════════════════════════════════════════
-- Migration 012: 데이터 품질 제외 규칙 + product_stats 적용
-- ════════════════════════════════════════════════════════════
-- 배경:
--   ERP 마이그레이션 / 시스템 교체 시점 이전 데이터는 가격 정합성이 떨어짐.
--   예) 미진 ERP 2023-02 이전 데이터가 평균 판매가에 노이즈로 작용.
--
-- 정책:
--   원본 sales_ledger 행은 보존 (히스토리/감사용).
--   집계 view 에서만 제외 규칙을 적용해 평균/마진 산출에서 빠짐.
--
-- 확장:
--   같은 패턴으로 추후 purchase_data_exclusion 도 추가 가능.
-- ════════════════════════════════════════════════════════════

-- 1. 제외 규칙 테이블
CREATE TABLE IF NOT EXISTS sales_data_exclusion (
  id               SERIAL      PRIMARY KEY,
  customer_pattern TEXT        NOT NULL,    -- ILIKE 패턴. 예: '%미진%'
  before_date      DATE,                    -- item_date < before_date 이면 제외
  after_date       DATE,                    -- item_date > after_date 이면 제외
  reason           TEXT,                    -- 사유 (감사용)
  active           BOOLEAN     DEFAULT TRUE,
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  updated_at       TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT chk_sde_dates CHECK (
    before_date IS NOT NULL OR after_date IS NOT NULL
  )
);

CREATE INDEX IF NOT EXISTS idx_sde_active ON sales_data_exclusion(active);

COMMENT ON TABLE sales_data_exclusion IS
  '매출 집계에서 제외할 거래 규칙. product_stats / product_cost_full_v 가 자동 반영.';


-- 2. 미진 ERP 2023-02 이전 데이터 제외 규칙 등록 (멱등)
INSERT INTO sales_data_exclusion (customer_pattern, before_date, reason)
SELECT '%미진%', '2023-02-01'::date,
       '미진 ERP 구버전 데이터 — 2023-02 시스템 교체 전 가격 정합성 부족'
WHERE NOT EXISTS (
  SELECT 1 FROM sales_data_exclusion
  WHERE customer_pattern = '%미진%'
    AND before_date = '2023-02-01'::date
);


-- 3. product_stats 재정의 — 제외 규칙 WHERE 적용
CREATE OR REPLACE VIEW product_stats AS
SELECT
  p.product_id,
  p.pn,
  COALESCE(s.sales_count, 0)                                      AS sales_count,
  COALESCE(s.total_qty, 0)                                        AS total_qty,
  COALESCE(s.total_sales, 0)                                      AS total_sales,
  COALESCE(s.avg_unit_price_12m, s.avg_unit_price_all, 0)         AS avg_unit_price,
  s.last_trade_date,
  s.first_trade_date,
  COALESCE(s.sales_count_12m, 0)                                  AS sales_count_12m,
  COALESCE(s.total_qty_12m, 0)                                    AS total_qty_12m,
  COALESCE(s.total_sales_12m, 0)                                  AS total_sales_12m,
  COALESCE(s.sales_count_thism, 0)                                AS sales_count_thism,
  COALESCE(s.total_sales_thism, 0)                                AS total_sales_thism,
  COALESCE(s.sales_count_lastm, 0)                                AS sales_count_lastm,
  COALESCE(s.total_sales_lastm, 0)                                AS total_sales_lastm,
  COALESCE(b.purchase_count, 0)                                   AS purchase_count_12m,
  COALESCE(b.purchase_amount, 0)                                  AS purchase_amount_12m,
  CASE
    WHEN s.last_trade_date IS NULL THEN 99999
    ELSE (CURRENT_DATE - s.last_trade_date)
  END                                                              AS dormant_days,
  CASE
    WHEN COALESCE(s.total_sales_12m, 0) > 100000000 THEN 'A'
    WHEN COALESCE(s.total_sales_12m, 0) > 30000000  THEN 'B'
    WHEN COALESCE(s.total_sales_12m, 0) > 5000000   THEN 'C'
    WHEN COALESCE(s.total_sales_12m, 0) > 0         THEN 'D'
    ELSE 'X'
  END                                                              AS abc_grade,
  CASE
    WHEN COALESCE(s.total_sales_lastm, 0) = 0 AND COALESCE(s.total_sales_thism, 0) > 0 THEN '🔥 신규'
    WHEN COALESCE(s.total_sales_thism, 0) > COALESCE(s.total_sales_lastm, 0) * 1.2     THEN '↗ 증가'
    WHEN COALESCE(s.total_sales_thism, 0) < COALESCE(s.total_sales_lastm, 0) * 0.8     THEN '↘ 감소'
    WHEN COALESCE(s.total_sales_thism, 0) = 0 AND COALESCE(s.total_sales_lastm, 0) > 0 THEN '⚠ 휴면진입'
    ELSE '→ 유지'
  END                                                              AS activity_trend,
  CASE
    WHEN COALESCE(s.avg_unit_price_12m, s.avg_unit_price_all, 0) > 0
     AND p.estimated_cost_per_pc > 0
    THEN ROUND(
      (COALESCE(s.avg_unit_price_12m, s.avg_unit_price_all)
        - p.estimated_cost_per_pc)
      / COALESCE(s.avg_unit_price_12m, s.avg_unit_price_all) * 100, 1)
    ELSE NULL
  END                                                              AS margin_pct,
  COALESCE(s.avg_unit_price_3m, 0)                                AS avg_unit_price_3m,
  COALESCE(s.avg_unit_price_12m, 0)                               AS avg_unit_price_12m,
  COALESCE(s.avg_unit_price_all, 0)                               AS avg_unit_price_all,
  s.last_unit_price
FROM products p
LEFT JOIN (
  SELECT
    sl.product_id,
    COUNT(*)                                                       AS sales_count,
    SUM(sl.qty)                                                    AS total_qty,
    SUM(sl.amount)                                                 AS total_sales,
    AVG(sl.unit_price) FILTER (WHERE sl.item_date >= CURRENT_DATE - INTERVAL '12 months') AS avg_unit_price_12m,
    AVG(sl.unit_price) FILTER (WHERE sl.item_date >= CURRENT_DATE - INTERVAL '3 months')  AS avg_unit_price_3m,
    AVG(sl.unit_price)                                             AS avg_unit_price_all,
    (ARRAY_AGG(sl.unit_price ORDER BY sl.item_date DESC NULLS LAST))[1] AS last_unit_price,
    MAX(sl.item_date)                                              AS last_trade_date,
    MIN(sl.item_date)                                              AS first_trade_date,
    COUNT(*) FILTER (WHERE sl.item_date >= CURRENT_DATE - INTERVAL '12 months') AS sales_count_12m,
    SUM(sl.qty)  FILTER (WHERE sl.item_date >= CURRENT_DATE - INTERVAL '12 months') AS total_qty_12m,
    SUM(sl.amount) FILTER (WHERE sl.item_date >= CURRENT_DATE - INTERVAL '12 months') AS total_sales_12m,
    COUNT(*)  FILTER (WHERE date_trunc('month', sl.item_date) = date_trunc('month', CURRENT_DATE)) AS sales_count_thism,
    SUM(sl.amount) FILTER (WHERE date_trunc('month', sl.item_date) = date_trunc('month', CURRENT_DATE)) AS total_sales_thism,
    COUNT(*)  FILTER (WHERE date_trunc('month', sl.item_date) = date_trunc('month', CURRENT_DATE - INTERVAL '1 month')) AS sales_count_lastm,
    SUM(sl.amount) FILTER (WHERE date_trunc('month', sl.item_date) = date_trunc('month', CURRENT_DATE - INTERVAL '1 month')) AS total_sales_lastm
  FROM sales_ledger sl
  WHERE sl.product_id IS NOT NULL
    -- 📌 제외 규칙 적용
    AND NOT EXISTS (
      SELECT 1 FROM sales_data_exclusion e
      WHERE e.active = TRUE
        AND sl.customer ILIKE e.customer_pattern
        AND (e.before_date IS NULL OR sl.item_date < e.before_date)
        AND (e.after_date  IS NULL OR sl.item_date > e.after_date)
    )
  GROUP BY sl.product_id
) s ON s.product_id = p.product_id
LEFT JOIN (
  SELECT matched_pn, COUNT(*) AS purchase_count, SUM(amount) AS purchase_amount
  FROM purchase_ledger
  WHERE matched_pn IS NOT NULL AND trade_date >= CURRENT_DATE - INTERVAL '12 months'
  GROUP BY matched_pn
) b ON b.matched_pn = p.pn;


COMMENT ON VIEW product_stats IS
  '제품 매출 통계. sales_data_exclusion 규칙으로 노이즈 거래 자동 제외. '
  'avg_unit_price = 12M 평균 (라벨 일치). 3M/12M/all/last 별도 컬럼 제공.';
