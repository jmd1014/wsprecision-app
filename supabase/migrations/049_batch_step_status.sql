-- ════════════════════════════════════════════════════════════
-- 복구: 운영 ledger(supabase_migrations.schema_migrations) 에서 추출 2026-10-23 — 원본 파일 커밋 없음 (P1-5)
-- version: 20260826103528  name: 049_batch_step_status
-- ════════════════════════════════════════════════════════════
-- 049: 배치 상태 기계 — 공정별 '투입 대기(WAIT)/진행 중(RUN)' 도입
-- (2026-08-27 사용자 확정: 소재입고 칸 폐지, 공정마다 투입/완료/취소.
--  기존 배치는 위치로 역산 — 업체에 나가 있으면 진행 중, 사내는 대기)
alter table wo_batches
  add column if not exists step_status text not null default 'WAIT'
  check (step_status in ('WAIT', 'RUN'));

update wo_batches
set step_status = 'RUN'
where coalesce(location, '사내') not in ('사내', '재작업')
  and status = 'OPEN';
