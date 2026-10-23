-- ════════════════════════════════════════════════════════════
-- 복구: 운영 ledger(supabase_migrations.schema_migrations) 에서 추출 2026-10-23 — 원본 파일 커밋 없음 (P1-5)
-- version: 20260907050139  name: 057_production_schedule
-- ════════════════════════════════════════════════════════════
-- 057: 설비 스케줄 보드 1단계 — 설비 × 날짜 × 교대 셀에 작업(품번#스텝) 하나
create table if not exists production_schedule (
  sched_id    serial primary key,
  machine_id  text not null references machines(machine_id),
  plan_date   date not null,
  shift       text not null check (shift in ('주간','야간')),
  pn          text not null,
  process     text not null,                 -- 작업 = 품번#스텝 (시트 표기)
  product_id  text references products(product_id),
  plan_qty    numeric not null default 0,
  plan_hours  numeric not null default 9,
  wo_number   text,
  worker      text,
  note        text,
  status      text not null default 'PLAN' check (status in ('PLAN','LOCKED','CANCELLED')),
  created_by  text,
  created_at  timestamptz default now(),
  updated_at  timestamptz default now(),
  unique (machine_id, plan_date, shift)
);
create index if not exists production_schedule_date_idx on production_schedule (plan_date);
create index if not exists production_schedule_op_idx on production_schedule (pn, process);
alter table production_schedule enable row level security;

-- 야간 미운영 설비(정지사유 M09 다수) — 야간 가용시간에서 제외
alter table machines add column if not exists night_active boolean not null default true;
