-- ════════════════════════════════════════════════════════════
-- 복구: 운영 ledger(supabase_migrations.schema_migrations) 에서 추출 2026-10-23 — 원본 파일 커밋 없음 (P1-5)
-- version: 20260819065739  name: 038_presched_and_data_quality
-- ════════════════════════════════════════════════════════════
-- Migration 038: 수주 진행 이중 장부 해소 ①단계 + 정합 점검 뷰
-- 배경(2026-08-19 평가): 라인 누계(received_qty)와 회차 delivered_qty 가
-- 독립 저장되어 이관 기납품이 회차를 선점하는 왜곡 발생 (MRG6-07).
-- presched_qty(스케줄 이전 기납품)를 명시 분리해 대사 불변식을 세운다:
--   sum(회차 delivered) = received_qty − presched_qty
-- 어긋나면 data_quality_v 에 즉시 표시된다.

ALTER TABLE sales_order_items
  ADD COLUMN IF NOT EXISTS presched_qty numeric DEFAULT 0;
COMMENT ON COLUMN sales_order_items.presched_qty IS
  '스케줄 이전 기납품(이관분 등) — 대사 기준: 회차 delivered 합 = received_qty − presched_qty';

-- 백필: 회차가 있는 라인 — 현재 기납품에서 회차 충당분을 뺀 나머지
UPDATE sales_order_items i
SET presched_qty = greatest(coalesce(i.received_qty, 0) - s.d, 0)
FROM (SELECT soi_id, sum(coalesce(delivered_qty, 0)) d
      FROM so_delivery_schedule GROUP BY 1) s
WHERE s.soi_id = i.soi_id;

-- 정합 점검 뷰 — 마스터 관리 > 정합 점검 탭이 사용
CREATE VIEW data_quality_v WITH (security_invoker = true) AS
SELECT 'FUTURE_ROUND'::text AS code, '미래 회차에 납품완료'::text AS check_name,
       coalesce(p.pn, '-') || ' · ' || o.so_number AS ref,
       '납기 ' || s.due_date::text || ' 회차에 ' || s.delivered_qty::text || ' 충당' AS detail
FROM so_delivery_schedule s
JOIN sales_order_items i ON i.soi_id = s.soi_id
JOIN sales_orders o ON o.so_id = i.so_id
LEFT JOIN products p ON p.product_id = i.product_id
WHERE s.delivered_qty > 0 AND s.due_date::date > current_date
UNION ALL
SELECT 'ROUND_MISMATCH', '회차 납품합 대사 불일치',
       coalesce(p.pn, '-') || ' · ' || o.so_number,
       '회차합 ' || t.d::text || ' vs 기대 '
       || (coalesce(i.received_qty, 0) - coalesce(i.presched_qty, 0))::text
       || ' (기납품 ' || coalesce(i.received_qty, 0)::text
       || ' − 스케줄이전 ' || coalesce(i.presched_qty, 0)::text || ')'
FROM (SELECT soi_id, sum(coalesce(delivered_qty, 0)) d
      FROM so_delivery_schedule GROUP BY 1) t
JOIN sales_order_items i ON i.soi_id = t.soi_id
JOIN sales_orders o ON o.so_id = i.so_id
LEFT JOIN products p ON p.product_id = i.product_id
WHERE abs(t.d - (coalesce(i.received_qty, 0) - coalesce(i.presched_qty, 0))) > 0.5
UNION ALL
SELECT 'PN_SPACE', '품번 앞뒤 공백', '[' || pn || ']', 'product_id ' || product_id
FROM products WHERE pn <> btrim(pn)
UNION ALL
SELECT 'PN_DUP', '활성 품번 중복', btrim(pn),
       count(*)::text || '건: ' || string_agg(product_id, ', ')
FROM products WHERE archived_at IS NULL
GROUP BY btrim(pn) HAVING count(*) > 1
UNION ALL
SELECT 'BOM_NONE', '활성 제품 BOM 소재 미연결', p.pn,
       coalesce('소재 표기: ' || p.raw_material_name, '소재 정보 없음')
FROM products p
WHERE p.archived_at IS NULL
  AND NOT EXISTS (SELECT 1 FROM bom b WHERE b.product_id = p.product_id
                  AND coalesce(b.process_type, 'MATERIAL') = 'MATERIAL')
UNION ALL
SELECT 'MAT_TEXT', '제품 소재 표기 ≠ BOM 자재명', p.pn,
       coalesce(p.raw_material_name, '(없음)') || ' vs ' || m.raw_name
FROM products p
JOIN bom b ON b.product_id = p.product_id
          AND coalesce(b.process_type, 'MATERIAL') = 'MATERIAL'
JOIN materials m ON m.material_id = b.material_id
WHERE p.archived_at IS NULL
  AND p.raw_material_name IS DISTINCT FROM m.raw_name
UNION ALL
SELECT 'PO_UNMAPPED', '발주 라인 자재 미매핑',
       o.po_number || ' · ' || coalesce(i.item_name, '-'),
       '수량 ' || coalesce(i.qty, 0)::text
FROM purchase_order_items i
JOIN purchase_orders o ON o.po_id = i.po_id
WHERE i.material_id IS NULL AND coalesce(o.status, '') <> 'CANCELLED'
UNION ALL
SELECT 'SO_UNMATCHED', '수주 라인 제품 미매칭 (미납)',
       o.so_number || ' · ' || coalesce(i.customer_part_no, '-'),
       '미납 ' || coalesce(i.pending_qty, 0)::text
FROM sales_order_items i
JOIN sales_orders o ON o.so_id = i.so_id
WHERE i.product_id IS NULL AND coalesce(i.pending_qty, 0) > 0;
