-- ════════════════════════════════════════════════════════════
-- 복구: 운영 ledger(supabase_migrations.schema_migrations) 에서 추출 2026-10-23 — 원본 파일 커밋 없음 (P1-5)
-- version: 20260824020427  name: flange_ledger_price_backup_0824
-- (번호 없는 adhoc 적용 — 번호 체계 밖이므로 adhoc/ 아래 보관)
-- ════════════════════════════════════════════════════════════
-- 플랜지 소재단가 원장기준 보정 전 백업 (2026-08-24)
create table if not exists products_flange_ledger_backup_0824 as
select * from products where pn in (
 '80AHYBV-TU-05','S50ABV-FL-01','S25ABV-FL-01','4S32BLD-MP','4S32LJF-MP','4ST32LJF-MP','4ST32BLD-MP',
 '4S50BLD-MP','4ST16BLD-MP','4ST16LJF-MP','4S40BLD-AP','4S40RFF-AP','4S15ABV-FL-01','4S25BLD-MP',
 'S15ABV-FL-01','S40ABV-FL-01','4S25ABV-FL-01','S25LJF-P','4S65BLD-MP','20ABV-FL-01','S15LJF-P','ST12LJF-P',
 '4S15BLD-MP','4S15LJF-MP','S20LJF-P','S20BLD');
