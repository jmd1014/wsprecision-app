-- ════════════════════════════════════════════════════════════
-- 080: 특수 단가 종류에 단가 조정(PRICE_ADJ) 추가 (마스터 관리 소수정 묶음 후보 34, 2026-11-04)
-- 옛 수주는 옛 단가로 계속 납품하고, 새 수주 단가를 마스터 판매 단가로 갱신하는 '별건' —
-- 단가 변동 감지에서 옛 라인에 PRICE_ADJ 를 표시한다(현대제뉴인 G26A920118 사례).
-- 060 과 같은 형식. 멱등(drop if exists → add). so_line_replacements.tagged_kind 는 CHECK 없음(무변경).
-- 운영 적용: 검토 세션이 사용자 승인 뒤 apply_migration → 그다음 앱 push.
--
-- 되돌리기(PRICE_ADJ 라인이 없을 때만 — 있으면 먼저 화면 결정 이력에서 되돌리거나 price_kind 를 NULL 로):
--   alter table sales_order_items drop constraint if exists sales_order_items_price_kind_check;
--   alter table sales_order_items add constraint sales_order_items_price_kind_check
--     check (price_kind in ('STD','PROJECT','REPLACE','CUSTOMER_MAT'));
-- ════════════════════════════════════════════════════════════
alter table sales_order_items drop constraint if exists sales_order_items_price_kind_check;
alter table sales_order_items add constraint sales_order_items_price_kind_check
  check (price_kind in ('STD','PROJECT','REPLACE','CUSTOMER_MAT','PRICE_ADJ'));
