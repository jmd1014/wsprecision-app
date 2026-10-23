-- ════════════════════════════════════════════════════════════
-- 복구: 운영 ledger(supabase_migrations.schema_migrations) 에서 추출 2026-10-23 — 원본 파일 커밋 없음 (P1-5)
-- version: 20260820034831  name: 042_po_status_allow_closed
-- ════════════════════════════════════════════════════════════
-- 042: 발주 잔량 종결(short-close) 상태 'CLOSED' 허용
-- 041 뷰(po_item_receipt_v)는 CLOSED 발주의 pending_qty 를 0 으로
-- 계산하지만, 정작 status CHECK 제약에 CLOSED 가 빠져 있어
-- 종결 업데이트가 400 으로 거부되던 버그 수정.
alter table purchase_orders drop constraint chk_po_status;
alter table purchase_orders add constraint chk_po_status
  check (status in ('DRAFT','SENT','RECEIVED','PARTIAL',
                    'CANCELLED','CLOSED'));
