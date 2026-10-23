-- ════════════════════════════════════════════════════════════
-- 복구: 운영 ledger(supabase_migrations.schema_migrations) 에서 추출 2026-10-23 — 원본 파일 커밋 없음 (P1-5)
-- version: 20260819083829  name: 040_poi_material
-- ════════════════════════════════════════════════════════════
-- Migration 040: 발주 라인 재질 정식 컬럼화 + 자재 사전 연결
-- ① 재질은 소재의 핵심 특성 — 비고(remark)에 합쳐 저장하던 것을 분리
-- ② 발주 시점에 제품 BOM 자재를 라인에 연결 → 입고 매핑 단계 소멸

ALTER TABLE purchase_order_items ADD COLUMN IF NOT EXISTS material text;
COMMENT ON COLUMN purchase_order_items.material IS '소재 재질 (표시·문서용)';

-- 백필 ①: 비고가 재질만 담긴 행 → material 로 이동
UPDATE purchase_order_items
SET material = remark, remark = NULL
WHERE material IS NULL AND remark IS NOT NULL
  AND remark NOT LIKE '% / %'
  AND remark ~* '^(SUS|STS|S[0-9]|SCM|HASTELLOY|AL|BRASS|C[0-9])';

-- 백필 ②: '메모 / 재질' 합침 형태 → 분리
UPDATE purchase_order_items
SET material = split_part(remark, ' / ', 2),
    remark = split_part(remark, ' / ', 1)
WHERE material IS NULL AND remark LIKE '% / %'
  AND split_part(remark, ' / ', 2)
      ~* '^(SUS|STS|S[0-9]|SCM|HASTELLOY|AL|BRASS|C[0-9])';

-- 백필 ③: 라인 product_id → BOM 소재로 material_id 사전 연결
UPDATE purchase_order_items i
SET material_id = b.material_id
FROM (SELECT DISTINCT ON (product_id) product_id, material_id
      FROM bom
      WHERE material_id IS NOT NULL
        AND coalesce(process_type, 'MATERIAL') = 'MATERIAL'
      ORDER BY product_id, bom_id) b
WHERE i.material_id IS NULL AND i.product_id = b.product_id;

SELECT count(*) FILTER (WHERE material IS NOT NULL) AS with_material,
       count(*) FILTER (WHERE material_id IS NULL) AS still_unmapped,
       count(*) AS total
FROM purchase_order_items;
