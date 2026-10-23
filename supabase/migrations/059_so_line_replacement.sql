-- ════════════════════════════════════════════════════════════
-- 복구: 운영 ledger(supabase_migrations.schema_migrations) 에서 추출 2026-10-23 — 원본 파일 커밋 없음 (P1-5)
-- version: 20260910012832  name: 059_so_line_replacement
-- ════════════════════════════════════════════════════════════
-- 059: 수주 대체(단가 변경 재발주) / 별건(프로젝트 단가) 결정 이력 (2026-09-10)
alter table sales_order_items drop constraint if exists chk_soi_status;
alter table sales_order_items add constraint chk_soi_status
  check (status = any (array['PENDING','IN_PROD','PARTIAL','DELIVERED','CANCELLED','REPLACED']));
alter table sales_order_items
  add column if not exists price_kind text check (price_kind in ('STD','PROJECT','REPLACE')),
  add column if not exists replaced_by_soi integer;

create table if not exists so_line_replacements (
  repl_id            serial primary key,
  old_soi_id         integer not null references sales_order_items(soi_id),
  new_soi_id         integer not null references sales_order_items(soi_id),
  action             text not null check (action in ('REPLACE','KEEP')),
  old_price          numeric,
  new_price          numeric,
  closed_pending_qty numeric default 0,
  closed_rounds      jsonb,          -- 닫은 옛 회차 [{sched_id, qty_before}]
  moved_rounds       jsonb,          -- 새 라인에 만든 회차 sched_id 목록
  master_updated     boolean default false,
  master_old_price   numeric,
  old_so_status      text,
  old_line_status    text,
  reason             text,
  created_by         text,
  created_at         timestamptz default now(),
  reverted_at        timestamptz,
  reverted_by        text
);
create index if not exists so_line_repl_old_idx on so_line_replacements(old_soi_id);
create index if not exists so_line_repl_new_idx on so_line_replacements(new_soi_id);
alter table so_line_replacements enable row level security;
