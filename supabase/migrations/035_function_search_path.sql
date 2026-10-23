-- ════════════════════════════════════════════════════════════
-- 복구: 운영 ledger(supabase_migrations.schema_migrations) 에서 추출 2026-10-23 — 원본 파일 커밋 없음 (P1-5)
-- version: 20260812014324  name: 035_function_search_path
-- ════════════════════════════════════════════════════════════
-- Migration 035: 채번 함수 search_path 고정 (advisor: function_search_path_mutable)
ALTER FUNCTION public.next_po_number() SET search_path = public;
ALTER FUNCTION public.next_so_number(text) SET search_path = public;
