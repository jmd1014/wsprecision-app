-- ════════════════════════════════════════════════════════════
-- 복구: 운영 ledger(supabase_migrations.schema_migrations) 에서 추출 2026-10-23 — 원본 파일 커밋 없음 (P1-5)
-- version: 20260812014135  name: 033_enable_rls_all_tables
-- ════════════════════════════════════════════════════════════
-- Migration 033: 모든 public 테이블 RLS 활성화
-- 배경: 앱/sync는 service_role 키 사용(RLS 우회) 확인됨 — 정책 0개인 기존 RLS 테이블이 정상 동작 중.
--       따라서 정책 없이 RLS만 켜면 anon/authenticated 키 접근만 차단되고 앱은 영향 없음.

ALTER TABLE public.zz_bak_golive_sales_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.zz_bak_golive_sales_order_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.zz_bak_golive_purchase_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.zz_bak_golive_purchase_order_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.zz_bak_golive_inventory_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.zz_bak_golive_production_log_manual ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.app_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.wo_tracking ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.wo_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.so_delivery_schedule ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.materials_cleanup_backup_028 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.materials_baseline_backup_0805 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.flange_split_backup_0805 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bom_backup_0805 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.materials_name_backup_0805 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.products_prefix_backup_0806 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.soi_prefix_backup_0806 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.backfill_backup_0806 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.shipments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.shipment_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.products_group_backup_0810 ENABLE ROW LEVEL SECURITY;
