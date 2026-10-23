-- ════════════════════════════════════════════════════════════
-- 복구: 운영 ledger(supabase_migrations.schema_migrations) 에서 추출 2026-10-23 — 원본 파일 커밋 없음 (P1-5)
-- version: 20260907082538  name: 058_op_std_active_log
-- ════════════════════════════════════════════════════════════
-- 058: 공정 표준 정비 — 사용 여부(변형 공정 제외) + 표준 변경 이력
alter table product_op_std add column if not exists active boolean not null default true;

create table if not exists product_op_std_log (
  log_id     serial primary key,
  op_id      integer references product_op_std(op_id) on delete cascade,
  pn         text,
  process    text,
  field      text not null,
  old_value  text,
  new_value  text,
  reason     text,
  changed_by text,
  changed_at timestamptz default now()
);
create index if not exists product_op_std_log_op_idx on product_op_std_log(op_id);
alter table product_op_std_log enable row level security;
