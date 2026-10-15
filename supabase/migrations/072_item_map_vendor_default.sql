-- ════════════════════════════════════════════════════════════
-- Migration 072: 매입 품명 매핑표 — 업체 기본 유형(와일드카드) 허용 (2026-10-15)
-- ════════════════════════════════════════════════════════════
-- 사용자 요청: 두리T.M.S 처럼 업체가 통째로 한 유형(공구·소모품)이면 품명마다 자재를 고르지 않고 업체 단위로 분류.
-- item_key = '*' 행 = 그 업체의 기본 라인 유형. 정확한 (업체, 품명) 행이 있으면 그것이 우선(코드 apply_item_map).
-- 와일드카드 행은 자재/제품 없이 SUPPLY/PROCESS/OTHER 만 허용. 되돌리기: 아래 제약을 071 원문으로 복원.
-- ════════════════════════════════════════════════════════════
ALTER TABLE public.purchase_item_map DROP CONSTRAINT IF EXISTS purchase_item_map_check;    -- 071: (MATERIAL,SUPPLY) = material_id 존재
ALTER TABLE public.purchase_item_map
    ADD CONSTRAINT purchase_item_map_check
    CHECK ((item_key = '*' AND material_id IS NULL AND product_id IS NULL AND line_type IN ('SUPPLY','PROCESS','OTHER'))
           OR (item_key <> '*' AND ((line_type IN ('MATERIAL','SUPPLY')) = (material_id IS NOT NULL))));
COMMENT ON COLUMN public.purchase_item_map.item_key IS '품명 키(utils/purchase_sync.item_key). ''*'' = 업체 기본 유형(와일드카드, 072)';
