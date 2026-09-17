-- 066: 공개 스키마 백업 테이블 20개 정리 (2026-09-17, DB 적용 완료)
-- 8월 마이그레이션·go-live 때 만든 스냅샷. 앱·뷰에서 참조 없음.
-- 삭제 전 전량 CSV 보존: docs/backups/2026-09-17-dropped-tables/*.csv.gz (2,334행)
drop table if exists public.backfill_backup_0806;
drop table if exists public.bom_ahybv_backup_0812;
drop table if exists public.bom_backup_0805;
drop table if exists public.flange_split_backup_0805;
drop table if exists public.materials_ahybv_backup_0812;
drop table if exists public.materials_baseline_backup_0805;
drop table if exists public.materials_cleanup_backup_028;
drop table if exists public.materials_name_backup_0805;
drop table if exists public.products_ahybv_backup_0812;
drop table if exists public.products_flange_ledger_backup_0824;
drop table if exists public.products_group_backup_0810;
drop table if exists public.products_mattext_backup_0819;
drop table if exists public.products_prefix_backup_0806;
drop table if exists public.soi_prefix_backup_0806;
drop table if exists public.zz_bak_golive_inventory_transactions;
drop table if exists public.zz_bak_golive_production_log_manual;
drop table if exists public.zz_bak_golive_purchase_order_items;
drop table if exists public.zz_bak_golive_purchase_orders;
drop table if exists public.zz_bak_golive_sales_order_items;
drop table if exists public.zz_bak_golive_sales_orders;
