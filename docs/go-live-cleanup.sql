-- ════════════════════════════════════════════════════════════
-- 실무 전환일 테스트 데이터 정리 스크립트
-- ⚠️ 전환일에 사용자 확인 후 단 한 번만 실행. 평상시 실행 금지.
-- ⚠️ 실행 전 Supabase Dashboard → Database → Backups 에서 백업 확인.
-- 기준: 2026-07-07 점검 — 수주 29건(전부 테스트) / PO 3건 / 원장 6건(7/3 E2E)
--       / production_log MANUAL 2건(테스트). MES_UPLOAD 297건은 실데이터 → 유지.
-- ════════════════════════════════════════════════════════════

-- 0) 실행 전 현황 확인 (결과 캡처해 둘 것)
SELECT 'sales_orders' t, count(*) FROM sales_orders
UNION ALL SELECT 'sales_order_items', count(*) FROM sales_order_items
UNION ALL SELECT 'purchase_orders', count(*) FROM purchase_orders
UNION ALL SELECT 'purchase_order_items', count(*) FROM purchase_order_items
UNION ALL SELECT 'inventory_transactions', count(*) FROM inventory_transactions
UNION ALL SELECT 'production_log(MANUAL)', count(*) FROM production_log WHERE source='MANUAL';

-- 1) 테스트 수주 삭제 (2026-05-11 일괄 import 29건 + 이후 테스트 추가분)
-- DELETE FROM sales_order_items WHERE so_id IN (SELECT so_id FROM sales_orders);
-- DELETE FROM sales_orders;

-- 2) 테스트 발주 삭제 — ⚠️ 실제 진행 중 발주가 섞여 있으면 po_id 지정으로 변경
-- DELETE FROM purchase_order_items WHERE po_id IN (SELECT po_id FROM purchase_orders);
-- DELETE FROM purchase_orders;

-- 3) 테스트 재고 원장 삭제 (7/3 E2E: RECEIPT/PROD_INPUT/PROD_OUTPUT/ISSUE)
--    → material_stock 은 기초 스냅샷(stock_qty)으로 복귀
-- DELETE FROM inventory_transactions;

-- 4) 테스트 생산 보고 삭제 (수기 MANUAL 만 — MES_UPLOAD 실데이터는 유지)
-- DELETE FROM production_log WHERE source = 'MANUAL';

-- 5) 정리 후 확인: 모두 0 이어야 함 (production_log 는 MES 행만 남음)
-- (0번 쿼리 재실행)

-- 6) 이후 절차 (docs/go-live-checklist.md):
--    HDX/미진 ERP 진행 수주 다운로드 → 수주 관리 업로드 → 매칭 보정
--    → 슬랙 운영 시작 공지
