-- ════════════════════════════════════════════════════════════
-- Migration 075: 수주 상태 '종결(CLOSED)' + 라인 중단 수량 보존 (2026-10-22, L3-S 수주 상태 정리)
-- 기준: _수주상태_검토의견_20261022.md §2 D3·D8, _수주상태_개발세션_지시문_20261022.md S1
-- ════════════════════════════════════════════════════════════
-- 목적:
--   1) 수주 머리글·라인 상태에 CLOSED(종결) 추가 — 거래 무효(CANCELLED)와 구분되는 "발주 중단"
--      (DIC 월 변경 이월, 고객 요청 중단 등). 라인 pending_qty 를 0 으로 내려 계획·자재·현황에서 빠진다.
--   2) sales_order_items.closed_qty — 종결·취소 시 보존한 잔량(되돌리기용). close_reason — 사유.
--   3) 드리프트 해소: 운영 DB 의 chk_soi_status 에는 REPLACED(단가 변경 재발주 대체) 가 들어 있으나
--      migrations(004) 에는 REPLACED 추가 파일이 없다. 여기서 전문 재선언해 저장소가 운영 DB 를 재현하게 한다.
-- 유지: CONFIRMED·IN_PROD 값은 제거하지 않는다(기존 CONFIRMED 4건 처리 뒤 별도 마이그레이션).
-- 적용 조건: 기존 행 무접촉(제약은 값 추가만, 열은 DEFAULT 0 / NULL). 멱등(DROP IF EXISTS → ADD, ADD COLUMN IF NOT EXISTS).
-- 되돌리기: 열 2개 DROP + 004 의 제약(+REPLACED)으로 재선언. CLOSED 행이 있으면 먼저 되돌리기 처리.
-- ════════════════════════════════════════════════════════════

-- sales_orders.status: + CLOSED
ALTER TABLE public.sales_orders DROP CONSTRAINT IF EXISTS chk_so_status;
ALTER TABLE public.sales_orders
  ADD CONSTRAINT chk_so_status
  CHECK (status IN ('DRAFT', 'CONFIRMED', 'IN_PROD', 'PARTIAL', 'DELIVERED', 'CANCELLED', 'CLOSED'));

-- sales_order_items.status: 전문 재선언 (+ CLOSED, REPLACED 포함 — 004 드리프트 해소)
ALTER TABLE public.sales_order_items DROP CONSTRAINT IF EXISTS chk_soi_status;
ALTER TABLE public.sales_order_items
  ADD CONSTRAINT chk_soi_status
  CHECK (status IN ('PENDING', 'IN_PROD', 'PARTIAL', 'DELIVERED', 'CANCELLED', 'REPLACED', 'CLOSED'));

-- 라인 보존 수량·사유
ALTER TABLE public.sales_order_items ADD COLUMN IF NOT EXISTS closed_qty numeric NOT NULL DEFAULT 0;
ALTER TABLE public.sales_order_items ADD COLUMN IF NOT EXISTS close_reason text;
COMMENT ON COLUMN public.sales_order_items.closed_qty IS '종결·취소 시 보존한 미납 잔량(되돌리기용). 활성 라인은 0 (075)';
COMMENT ON COLUMN public.sales_order_items.close_reason IS '종결·취소 사유 — 월 변경 이월 / 고객 요청 중단 / 기타(입력) (075)';

-- 적용 후 검증(개발 세션):
--   select conname, pg_get_constraintdef(oid) from pg_constraint where conname in ('chk_so_status','chk_soi_status');
--   select column_name, data_type, column_default, is_nullable from information_schema.columns
--     where table_name='sales_order_items' and column_name in ('closed_qty','close_reason');
--   select count(*) from sales_order_items where closed_qty <> 0;  -- 0
--   select status, count(*) from sales_orders group by 1;  -- 적용 전과 동일(행 무접촉)
