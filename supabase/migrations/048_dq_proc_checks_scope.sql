-- ════════════════════════════════════════════════════════════
-- 복구: 운영 ledger(supabase_migrations.schema_migrations) 에서 추출 2026-10-23 — 원본 파일 커밋 없음 (P1-5)
-- version: 20260821042856  name: 048_dq_proc_checks_scope
-- ════════════════════════════════════════════════════════════
-- 048: PROC_NO_PRICE / PROC_NO_VENDOR 를 공정행(HEAT/SURFACE/
-- OUTSOURCE)으로 한정 — 옛 라우팅의 소재입고 스텝이 소재행 bom_id 를
-- 연결하고 있어 소재행이 오검출되던 것 수정 (047 보완)
create or replace view data_quality_v
with (security_invoker = true) as
 SELECT 'FUTURE_ROUND'::text AS code,
    '미래 회차에 납품완료'::text AS check_name,
    (COALESCE(p.pn, '-'::text) || ' · '::text) || o.so_number AS ref,
    ((('납기 '::text || s.due_date::text) || ' 회차에 '::text) || s.delivered_qty::text) || ' 충당'::text AS detail
   FROM so_delivery_schedule s
     JOIN sales_order_items i ON i.soi_id = s.soi_id
     JOIN sales_orders o ON o.so_id = i.so_id
     LEFT JOIN products p ON p.product_id = i.product_id
  WHERE s.delivered_qty > 0::numeric AND s.due_date > CURRENT_DATE
UNION ALL
 SELECT 'ROUND_MISMATCH'::text,
    '회차 납품합 대사 불일치'::text,
    (COALESCE(p.pn, '-'::text) || ' · '::text) || o.so_number,
    ((((((('회차합 '::text || t.d::text) || ' vs 기대 '::text) || ((COALESCE(i.received_qty, 0::numeric) - COALESCE(i.presched_qty, 0::numeric))::text)) || ' (기납품 '::text) || COALESCE(i.received_qty, 0::numeric)::text) || ' − 스케줄이전 '::text) || COALESCE(i.presched_qty, 0::numeric)::text) || ')'::text
   FROM ( SELECT so_delivery_schedule.soi_id,
            sum(COALESCE(so_delivery_schedule.delivered_qty, 0::numeric)) AS d
           FROM so_delivery_schedule
          GROUP BY so_delivery_schedule.soi_id) t
     JOIN sales_order_items i ON i.soi_id = t.soi_id
     JOIN sales_orders o ON o.so_id = i.so_id
     LEFT JOIN products p ON p.product_id = i.product_id
  WHERE abs(t.d - (COALESCE(i.received_qty, 0::numeric) - COALESCE(i.presched_qty, 0::numeric))) > 0.5
UNION ALL
 SELECT 'PN_SPACE'::text, '품번 앞뒤 공백'::text,
    ('['::text || products.pn) || ']'::text,
    'product_id '::text || products.product_id
   FROM products
  WHERE products.pn <> btrim(products.pn)
UNION ALL
 SELECT 'PN_DUP'::text, '활성 품번 중복'::text,
    btrim(products.pn),
    (count(*)::text || '건: '::text) || string_agg(products.product_id, ', '::text)
   FROM products
  WHERE products.archived_at IS NULL
  GROUP BY (btrim(products.pn))
 HAVING count(*) > 1
UNION ALL
 SELECT 'BOM_NONE'::text, '활성 제품 BOM 소재 미연결'::text,
    p.pn,
    COALESCE('소재 표기: '::text || p.raw_material_name, '소재 정보 없음'::text)
   FROM products p
  WHERE p.archived_at IS NULL AND NOT (EXISTS ( SELECT 1
           FROM bom b
          WHERE b.product_id = p.product_id AND COALESCE(b.process_type, 'MATERIAL'::text) = 'MATERIAL'::text))
UNION ALL
 SELECT 'MAT_TEXT'::text, '제품 소재 표기 ≠ BOM 자재명'::text,
    p.pn,
    (COALESCE(p.raw_material_name, '(없음)'::text) || ' vs '::text) || m.raw_name
   FROM products p
     JOIN bom b ON b.product_id = p.product_id AND COALESCE(b.process_type, 'MATERIAL'::text) = 'MATERIAL'::text
     JOIN materials m ON m.material_id = b.material_id
  WHERE p.archived_at IS NULL AND p.raw_material_name IS DISTINCT FROM m.raw_name
UNION ALL
 SELECT 'PO_UNMAPPED'::text, '발주 라인 자재 미매핑'::text,
    (o.po_number || ' · '::text) || COALESCE(i.item_name, '-'::text),
    '수량 '::text || COALESCE(i.qty, 0::numeric)::text
   FROM purchase_order_items i
     JOIN purchase_orders o ON o.po_id = i.po_id
  WHERE i.material_id IS NULL AND COALESCE(o.status, ''::text) <> 'CANCELLED'::text
UNION ALL
 SELECT 'SO_UNMATCHED'::text, '수주 라인 제품 미매칭 (미납)'::text,
    (o.so_number || ' · '::text) || COALESCE(i.customer_part_no, '-'::text),
    '미납 '::text || COALESCE(i.pending_qty, 0::numeric)::text
   FROM sales_order_items i
     JOIN sales_orders o ON o.so_id = i.so_id
  WHERE i.product_id IS NULL AND COALESCE(i.pending_qty, 0::numeric) > 0::numeric
UNION ALL
 SELECT 'ROUTE_COST_ORPHAN'::text,
    '공정 원가행 라우팅 미연결'::text,
    p.pn,
    (COALESCE(b.process_type, '-'::text) || ' '::text)
      || COALESCE(b.raw_material_name, '-'::text)
   FROM bom b
     JOIN products p ON p.product_id = b.product_id
  WHERE p.archived_at IS NULL
    AND COALESCE(b.process_type, 'MATERIAL'::text)
        IN ('HEAT'::text, 'SURFACE'::text, 'OUTSOURCE'::text)
    AND EXISTS ( SELECT 1 FROM product_routing r
                  WHERE r.product_id = b.product_id)
    AND NOT EXISTS ( SELECT 1 FROM product_routing r
                      WHERE r.bom_id = b.bom_id)
UNION ALL
 SELECT 'PROC_NO_PRICE'::text,
    '공정행 표준 단가 미입력'::text,
    p.pn,
    (COALESCE(b.raw_material_name, '-'::text)
     || ' — 원가 확인 > 단가 관리에서 입력'::text)
   FROM bom b
     JOIN products p ON p.product_id = b.product_id
  WHERE p.archived_at IS NULL
    AND b.unit_price IS NULL
    AND COALESCE(b.process_type, 'MATERIAL'::text)
        IN ('HEAT'::text, 'SURFACE'::text, 'OUTSOURCE'::text)
    AND EXISTS ( SELECT 1 FROM product_routing r
                  WHERE r.bom_id = b.bom_id)
UNION ALL
 SELECT 'PROC_NO_VENDOR'::text,
    '공정행 업체 미매칭'::text,
    p.pn,
    (COALESCE(b.raw_material_name, '-'::text)
     || ' — BOM 편집 공정행 카드에서 업체 매칭 후 라우팅 재저장'::text)
   FROM bom b
     JOIN products p ON p.product_id = b.product_id
  WHERE p.archived_at IS NULL
    AND b.process_vendor_id IS NULL
    AND COALESCE(b.process_type, 'MATERIAL'::text)
        IN ('HEAT'::text, 'SURFACE'::text, 'OUTSOURCE'::text)
    AND EXISTS ( SELECT 1 FROM product_routing r
                  WHERE r.bom_id = b.bom_id);
