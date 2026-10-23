-- ════════════════════════════════════════════════════════════
-- 복구: 운영 ledger(supabase_migrations.schema_migrations) 에서 추출 2026-10-23 — 원본 파일 커밋 없음 (P1-5)
-- version: 20260911044949  name: 062_poi_adhoc_once
-- ════════════════════════════════════════════════════════════
-- 062: 마스터에 없는 발주 라인의 처리 결정 — 일회성 표시 (자재 등록 대신)
alter table purchase_order_items add column if not exists adhoc_once boolean not null default false;
