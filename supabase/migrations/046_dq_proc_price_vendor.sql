-- ════════════════════════════════════════════════════════════
-- 복구: 운영 ledger(supabase_migrations.schema_migrations) 에서 추출 2026-10-23 — 원본 파일 커밋 없음 (P1-5)
-- version: 20260821042713  name: 046_dq_proc_price_vendor
-- ════════════════════════════════════════════════════════════
-- 046: 정합 점검 — 라우팅에 쓰이는 공정행의 표준 원가 완성도 감시
-- (표준 단가 방식 확정, 2026-08-21: 단가·업체가 비면 원가 분석과
--  라우팅 업체 고정이 미완성이므로 워크리스트로 노출)
create or replace view data_quality_v
with (security_invoker = true) as
select * from (
  select code, check_name, ref, detail from data_quality_v
) old_checks
union all
 SELECT 'PROC_NO_PRICE'::text AS code,
    '공정행 표준 단가 미입력'::text AS check_name,
    p.pn AS ref,
    (COALESCE(b.raw_material_name, '-'::text)
     || ' — 원가 확인 > 단가 관리에서 입력'::text) AS detail
   FROM bom b
     JOIN products p ON p.product_id = b.product_id
  WHERE p.archived_at IS NULL
    AND b.unit_price IS NULL
    AND EXISTS ( SELECT 1 FROM product_routing r
                  WHERE r.bom_id = b.bom_id)
UNION ALL
 SELECT 'PROC_NO_VENDOR'::text,
    '공정행 업체 미매칭'::text,
    p.pn,
    (COALESCE(b.raw_material_name, '-'::text)
     || ' — BOM 편집 공정행 카드에서 업체 매칭 후 라우팅 재저장'::text)
   FROM bom b
     JOIN products p ON p.product_id = b.product_id
  WHERE p.archived_at IS NULL
    AND b.process_vendor_id IS NULL
    AND EXISTS ( SELECT 1 FROM product_routing r
                  WHERE r.bom_id = b.bom_id);
