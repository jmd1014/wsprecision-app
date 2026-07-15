-- ════════════════════════════════════════════════════════════
-- Migration 021: 자재 최근가에 앱 발주 단가 반영 (A안)
-- ════════════════════════════════════════════════════════════
-- 배경:
--   material_price_v 의 최근가(price_last)는 매입 ledger 의
--   matched_material_id 기반인데 매칭이 0건 → 소재비가 5월 스냅샷에
--   고정되어 있었음. 앱 발주(입고 완료 라인)에는 합의된 단가가
--   이미 있으므로 이를 최근가 소스로 추가 → 발주→입고가 일어날
--   때마다 원가 확인의 소재비가 자동 최신화.
--
-- 변경:
--   1. price_last = (매입 ledger 최근가) vs (입고 완료된 발주 단가)
--      중 더 최근 날짜의 단가. 미래 날짜 ledger 행 제외.
--   2. 3m/12m 평균에도 미래 날짜 가드 (trade_date <= CURRENT_DATE).
--      (실데이터에 2026-12-30 등 파싱 이상 행 존재)
--   3. 끝에 참고 컬럼 추가: po_price_last, po_price_date
--      (CREATE OR REPLACE 규칙 — 기존 컬럼 순서/타입 유지, 끝에만 추가)
--
-- 비파괴 / 멱등. 하위 뷰(product_bom_cost_v → product_cost_full_v)는
-- price_last 를 그대로 읽으므로 자동 반영.
-- ════════════════════════════════════════════════════════════

CREATE OR REPLACE VIEW material_price_v AS
SELECT m.material_id,
    m.raw_name,
    m.material_type,
    m.spec,
    m.unit AS material_unit,
    avg(pl.unit_price) FILTER (WHERE pl.trade_date >= (CURRENT_DATE - interval '3 mons')
                                 AND pl.trade_date <= CURRENT_DATE) AS price_3m,
    avg(pl.unit_price) FILTER (WHERE pl.trade_date >= (CURRENT_DATE - interval '1 year')
                                 AND pl.trade_date <= CURRENT_DATE) AS price_12m,
    avg(pl.kg_price)  FILTER (WHERE pl.trade_date >= (CURRENT_DATE - interval '1 year')
                                 AND pl.trade_date <= CURRENT_DATE) AS kg_price_12m,
    avg(pl.ea_price)  FILTER (WHERE pl.trade_date >= (CURRENT_DATE - interval '1 year')
                                 AND pl.trade_date <= CURRENT_DATE) AS ea_price_12m,
    -- 최근가: 매입 ledger vs 앱 발주(입고 완료) 중 더 최근 날짜의 단가
    ( SELECT s.price FROM (
        SELECT pl2.trade_date::date AS d, pl2.unit_price AS price
          FROM purchase_ledger pl2
         WHERE pl2.matched_material_id = m.material_id
           AND pl2.unit_price IS NOT NULL
           AND pl2.trade_date <= CURRENT_DATE
        UNION ALL
        SELECT po2.po_date::date AS d, poi2.unit_price AS price
          FROM purchase_order_items poi2
          JOIN purchase_orders po2 ON po2.po_id = poi2.po_id
         WHERE poi2.material_id = m.material_id
           AND COALESCE(poi2.unit_price, 0) > 0
           AND EXISTS (SELECT 1 FROM inventory_transactions it
                        WHERE it.txn_type = 'RECEIPT'
                          AND it.ref_table = 'purchase_order_items'
                          AND it.ref_id = poi2.poi_id)
      ) s ORDER BY s.d DESC NULLS LAST LIMIT 1) AS price_last,
    max(pl.trade_date) AS last_purchase_date,
    count(pl.ledger_id) FILTER (WHERE pl.trade_date >= (CURRENT_DATE - interval '1 year')) AS purchase_count_12m,
    count(pl.ledger_id) AS purchase_count_total,
    -- (021 추가) 앱 발주 기반 최근 단가/발주일 — 화면 참고용
    ( SELECT poi3.unit_price
        FROM purchase_order_items poi3
        JOIN purchase_orders po3 ON po3.po_id = poi3.po_id
       WHERE poi3.material_id = m.material_id
         AND COALESCE(poi3.unit_price, 0) > 0
         AND EXISTS (SELECT 1 FROM inventory_transactions it2
                      WHERE it2.txn_type = 'RECEIPT'
                        AND it2.ref_table = 'purchase_order_items'
                        AND it2.ref_id = poi3.poi_id)
       ORDER BY po3.po_date DESC LIMIT 1) AS po_price_last,
    ( SELECT po4.po_date::date
        FROM purchase_order_items poi4
        JOIN purchase_orders po4 ON po4.po_id = poi4.po_id
       WHERE poi4.material_id = m.material_id
         AND COALESCE(poi4.unit_price, 0) > 0
         AND EXISTS (SELECT 1 FROM inventory_transactions it3
                      WHERE it3.txn_type = 'RECEIPT'
                        AND it3.ref_table = 'purchase_order_items'
                        AND it3.ref_id = poi4.poi_id)
       ORDER BY po4.po_date DESC LIMIT 1) AS po_price_date
FROM materials m
LEFT JOIN purchase_ledger pl ON pl.matched_material_id = m.material_id
GROUP BY m.material_id, m.raw_name, m.material_type, m.spec, m.unit;

COMMENT ON VIEW material_price_v IS
  '자재 단가 뷰 — price_last: 매입 ledger vs 입고 완료된 앱 발주 단가 중 최근 (021). 소재비 우선순위: price_last > price_3m > price_12m > products.material_unit_price(스냅샷)';
