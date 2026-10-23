-- ════════════════════════════════════════════════════════════
-- 복구: 운영 ledger(supabase_migrations.schema_migrations) 에서 추출 2026-10-23 — 원본 파일 커밋 없음 (P1-5)
-- version: 20260910013707  name: 060_price_kind_customer_mat
-- ════════════════════════════════════════════════════════════
-- 060: 특수 단가 종류에 사급 소재(CUSTOMER_MAT) 추가 + 별건 유지 때 어느 라인을
-- 특수 단가로 표시했는지 기록 (되돌리기 정확성)
alter table sales_order_items drop constraint if exists sales_order_items_price_kind_check;
alter table sales_order_items add constraint sales_order_items_price_kind_check
  check (price_kind in ('STD','PROJECT','REPLACE','CUSTOMER_MAT'));
alter table so_line_replacements
  add column if not exists tagged_soi_id integer,
  add column if not exists tagged_kind text;
