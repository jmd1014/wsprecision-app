-- ════════════════════════════════════════════════════════════
-- 복구: 운영 ledger(supabase_migrations.schema_migrations) 에서 추출 2026-10-23 — 원본 파일 커밋 없음 (P1-5)
-- version: 20260907034232  name: 055_production_standards
-- ════════════════════════════════════════════════════════════
-- 055: 생산 계획 기초 — 설비 마스터 · 공정 표준(품번×공정 UPH) · 능력 매트릭스
-- (2026-09-07 사용자 확정: 표준을 먼저 실적에서 만들고 확정·보완한 뒤 전개)

create table if not exists machines (
  machine_id  text primary key,              -- 정규화 이름 (MCT03, CNC07)
  name        text,
  group_code  text not null,                 -- 장비군 CNC / MCT …
  shifts      integer not null default 2,    -- 주야 2교대
  hours_per_shift numeric not null default 9,
  active      boolean not null default true,
  note        text,
  created_at  timestamptz default now(),
  updated_at  timestamptz default now()
);
alter table machines enable row level security;

create table if not exists product_op_std (
  op_id        serial primary key,
  product_id   text references products(product_id),
  pn           text not null,
  process      text not null,                -- 공정 스텝명 (CNC#10)
  step         integer,
  group_code   text,                         -- 배정 장비군
  uph_std      numeric,                      -- 계획에 쓰는 표준 UPH
  uph_auto     numeric,                      -- 실적 중앙값 (재산출 시 갱신)
  uph_mean     numeric,
  sample_n     integer default 0,
  hours_n      numeric default 0,
  machines_used text,                        -- 실적 설비 (콤마)
  setup_min    numeric default 0,
  std_status   text not null default 'AUTO' check (std_status in ('AUTO','CONFIRMED')),
  calc_at      timestamptz,
  first_date   date,
  last_date    date,
  confirmed_by text,
  confirmed_at timestamptz,
  note         text,
  created_at   timestamptz default now(),
  updated_at   timestamptz default now(),
  unique (pn, process)
);
alter table product_op_std enable row level security;

create table if not exists product_op_machine (
  pom_id      serial primary key,
  pn          text not null,
  process     text not null,
  machine_id  text not null,
  runs        integer default 0,
  hours       numeric default 0,
  qty         numeric default 0,
  uph_actual  numeric,
  last_date   date,
  calc_at     timestamptz default now(),
  unique (pn, process, machine_id)
);
alter table product_op_machine enable row level security;

-- 설비 시드: 생산 실적의 설비명 정규화 (MCT 03 → MCT03)
insert into machines (machine_id, name, group_code)
select distinct
  upper(regexp_replace(machine, '^\s*([A-Za-z]+)\s*[-_ ]?\s*0*(\d+)\s*$', '\1' || lpad('\2', 2, '0'))) as mid,
  machine,
  upper(substring(machine from '^\s*([A-Za-z]+)'))
from production_log
where machine is not null and machine ~ '^\s*[A-Za-z]+\s*[-_ ]?\s*\d+\s*$'
on conflict (machine_id) do nothing;
