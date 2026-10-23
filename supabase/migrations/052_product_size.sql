-- ════════════════════════════════════════════════════════════
-- 복구: 운영 ledger(supabase_migrations.schema_migrations) 에서 추출 2026-10-23 — 원본 파일 커밋 없음 (P1-5)
-- version: 20260903065313  name: 052_product_size
-- ════════════════════════════════════════════════════════════
-- 052: 제품 사이즈 (완성품 치수) — 2026-09-02 사용자 확정
-- 자재 치수는 BOM(materials.spec)이 진실이므로, 제품 테이블의
-- raw_material_spec(옛 소재 규격 스냅샷)은 UI에서 내리고 완성품 치수를
-- 담는 product_size 를 신설. 발주서 품명 "품번 (사이즈)" 의 괄호 값.
alter table products add column if not exists product_size text;
comment on column products.product_size is
  '완성품 치수 (예: Ø40*23.5L) — 발주서 품명 괄호에 인쇄. 자재 치수는 BOM 자재의 spec';
comment on column products.raw_material_spec is
  '(deprecated 2026-09-02) 옛 소재 규격 스냅샷 — UI 미사용, 소재 치수는 BOM 자재 spec';

-- 백필: 기존 발주 라인 품명 "품번 (사이즈)" 에서 추출 (제품이 존재하는 것만)
with x as (
  select distinct on (upper(trim(substring(item_name from '^(.*?)\s*\('))))
         upper(trim(substring(item_name from '^(.*?)\s*\('))) pn_u,
         trim(substring(item_name from '\((.*)\)\s*$')) size_part
  from purchase_order_items
  where item_name ~ '\(.+\)\s*$'
  order by upper(trim(substring(item_name from '^(.*?)\s*\('))), poi_id desc
)
update products p set product_size = x.size_part, updated_at = now()
from x where upper(p.pn) = x.pn_u and p.product_size is null;
