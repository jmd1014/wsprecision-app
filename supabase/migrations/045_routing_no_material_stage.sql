-- ════════════════════════════════════════════════════════════
-- 복구: 운영 ledger(supabase_migrations.schema_migrations) 에서 추출 2026-10-23 — 원본 파일 커밋 없음 (P1-5)
-- version: 20260820085354  name: 045_routing_no_material_stage
-- ════════════════════════════════════════════════════════════
-- 045: 투입 전 '소재 단계' 외주 개념 폐지 (2026-08-20 사용자 확정)
-- 공정 투입 후 라우팅 순서대로 모든 공정(열처리 포함)이 배치 단위로
-- 처리된다. 기존 소재 단계 외주 스텝(고용화 등)을 제품 단계로 전환
-- — 스텝 순서(seq)는 그대로이므로 공정 순서는 변하지 않는다.
update product_routing set stage = 'PRODUCT'
 where stage = 'MATERIAL' and step_code <> 'MAT_IN';
