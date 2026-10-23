-- ════════════════════════════════════════════════════════════
-- 복구: 운영 ledger(supabase_migrations.schema_migrations) 에서 추출 2026-10-23 — 원본 파일 커밋 없음 (P1-5)
-- version: 20260812014245  name: 034_views_security_invoker
-- ════════════════════════════════════════════════════════════
-- Migration 034: 모든 public 뷰 security_invoker 설정
-- 배경: 뷰는 기본적으로 소유자(postgres) 권한으로 실행되어 RLS를 우회 —
--       anon 키로 뷰를 통해 전체 데이터 조회가 가능했음 (2026-08-12 실측 확인).
--       security_invoker=true 로 호출자 권한 실행 → anon 차단, service_role(앱)은 영향 없음.

ALTER VIEW public.active_bom_completion_v SET (security_invoker = true);
ALTER VIEW public.active_products SET (security_invoker = true);
ALTER VIEW public.archived_products SET (security_invoker = true);
ALTER VIEW public.bom_cleanup_todo_v SET (security_invoker = true);
ALTER VIEW public.bom_missing_active_products_v SET (security_invoker = true);
ALTER VIEW public.lot_trace_v SET (security_invoker = true);
ALTER VIEW public.material_mapping_candidates SET (security_invoker = true);
ALTER VIEW public.material_price_coverage_v SET (security_invoker = true);
ALTER VIEW public.material_price_v SET (security_invoker = true);
ALTER VIEW public.material_stats SET (security_invoker = true);
ALTER VIEW public.material_stock SET (security_invoker = true);
ALTER VIEW public.material_stock_by_lot SET (security_invoker = true);
ALTER VIEW public.po_item_receipt_v SET (security_invoker = true);
ALTER VIEW public.product_actual_cost_v SET (security_invoker = true);
ALTER VIEW public.product_bom_cost_v SET (security_invoker = true);
ALTER VIEW public.product_cost_full_v SET (security_invoker = true);
ALTER VIEW public.product_full SET (security_invoker = true);
ALTER VIEW public.product_lot_stock_v SET (security_invoker = true);
ALTER VIEW public.product_material_price_status_v SET (security_invoker = true);
ALTER VIEW public.product_stats SET (security_invoker = true);
ALTER VIEW public.product_stock_v SET (security_invoker = true);
ALTER VIEW public.product_trace_v SET (security_invoker = true);
ALTER VIEW public.purchase_material_match_progress SET (security_invoker = true);
ALTER VIEW public.sales_order_items_v SET (security_invoker = true);
ALTER VIEW public.sales_order_stats SET (security_invoker = true);
ALTER VIEW public.so_schedule_summary_v SET (security_invoker = true);
ALTER VIEW public.unresolved_purchase_materials SET (security_invoker = true);
ALTER VIEW public.vendor_stats SET (security_invoker = true);
