-- ════════════════════════════════════════════════════════════
-- 복구: 운영 ledger(supabase_migrations.schema_migrations) 에서 추출 2026-10-23 — 원본 파일 커밋 없음 (P1-5)
-- version: 20260819071814  name: 039_poi_product_id
-- ════════════════════════════════════════════════════════════
-- Migration 039: 발주 라인 제품 ID화 (평가 로드맵 4)
-- 품명 텍스트 매칭 의존 제거 — 발주 라인이 제품을 ID 로 직접 참조.
ALTER TABLE purchase_order_items ADD COLUMN IF NOT EXISTS product_id text;
COMMENT ON COLUMN purchase_order_items.product_id IS
  '발주 대상 제품 (품번의 진실 = product_id). 품명 텍스트는 표시용';

-- 백필: 품명(규격 괄호 제거)이 활성 품번과 유일하게 일치하는 라인만
UPDATE purchase_order_items i
SET product_id = p.product_id
FROM products p
WHERE i.product_id IS NULL
  AND p.pn = btrim(split_part(i.item_name, '(', 1))
  AND (SELECT count(*) FROM products p2
       WHERE p2.pn = btrim(split_part(i.item_name, '(', 1))) = 1;

SELECT count(*) FILTER (WHERE product_id IS NOT NULL) AS mapped,
       count(*) AS total FROM purchase_order_items;
