-- 065: 보안 점검 반영 (2026-09-17)
-- 1) 로그인 기록 — 성공/실패/잠금, IP·UA (프록시 헤더가 있을 때만)
create table if not exists public.login_log (
  log_id     bigserial primary key,
  username   text,
  ok         boolean not null default false,
  note       text,
  ip         text,
  user_agent text,
  created_at timestamptz not null default now()
);
create index if not exists login_log_created_idx on public.login_log (created_at desc);
alter table public.login_log enable row level security;   -- 앱은 service_role 로만 접근

-- 2) RLS 가 꺼져 있던 백업 테이블 (Supabase 보안 자문 ERROR 1건)
alter table if exists public.products_flange_ledger_backup_0824 enable row level security;
