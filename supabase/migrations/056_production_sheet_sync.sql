-- ════════════════════════════════════════════════════════════
-- 복구: 운영 ledger(supabase_migrations.schema_migrations) 에서 추출 2026-10-23 — 원본 파일 커밋 없음 (P1-5)
-- version: 20260907041734  name: 056_production_sheet_sync
-- ════════════════════════════════════════════════════════════
-- 056: 생산일정 시트(데이터DB 탭) 동기화 컬럼 + 공정 표준의 시트 목표(UPH·C.T.)
alter table production_log
  add column if not exists run_flag    text,        -- 가동 / 비가동
  add column if not exists stop_reason text,        -- M01 자재부족 …
  add column if not exists sheet_key   text;        -- 시트 행 중복 방지 키
create unique index if not exists production_log_sheet_key_uq
  on production_log (sheet_key) where sheet_key is not null;
create index if not exists production_log_date_idx on production_log (log_date);

alter table product_op_std
  add column if not exists ct_sec     numeric,      -- 시트 가공시간(초)
  add column if not exists idle_sec   numeric,      -- 시트 유휴시간(초)
  add column if not exists uph_sheet  numeric,      -- 시트 UPH 목표 (제품별 목표생산량 탭)
  add column if not exists std_source text;         -- SHEET / LOG / MANUAL
