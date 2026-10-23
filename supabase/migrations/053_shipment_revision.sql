-- ════════════════════════════════════════════════════════════
-- 복구: 운영 ledger(supabase_migrations.schema_migrations) 에서 추출 2026-10-23 — 원본 파일 커밋 없음 (P1-5)
-- version: 20260904082936  name: 053_shipment_revision
-- ════════════════════════════════════════════════════════════
-- 053: 확정 출고 전표 정정·취소 인프라 (2026-09-04)
--  * shipment_allocations : 확정 시 전표 라인 → 회차 충당 내역 (정정 시 정확 되돌림)
--  * shipment_revisions   : 정정/취소 이력 (이전·이후 수량, 사유, 담당)
--  * shipments.rev_no 등  : 개정 카운터 · 취소 사유
--  * sales_month_close    : 월 마감 잠금 (마감 월 전표는 정정·취소·확정 차단)
--  * data_quality_v       : SHIP_ALLOC_MISMATCH 검사 추가 (전체 정의 재명시)

create table if not exists shipment_allocations (
  alloc_id   serial primary key,
  si_id      integer not null references shipment_items(si_id) on delete cascade,
  sched_id   integer not null references so_delivery_schedule(sched_id) on delete cascade,
  qty        numeric not null default 0,
  created_at timestamptz default now()
);
create index if not exists shipment_allocations_si_idx on shipment_allocations(si_id);
create index if not exists shipment_allocations_sched_idx on shipment_allocations(sched_id);
alter table shipment_allocations enable row level security;

create table if not exists shipment_revisions (
  rev_id      serial primary key,
  shipment_id integer not null references shipments(shipment_id) on delete cascade,
  rev_no      integer not null,
  action      text not null check (action in ('EDIT','CANCEL')),
  si_id       integer references shipment_items(si_id) on delete set null,
  pn          text,
  qty_before  numeric,
  qty_after   numeric,
  reason      text,
  created_by  text,
  created_at  timestamptz default now()
);
create index if not exists shipment_revisions_ship_idx on shipment_revisions(shipment_id);
alter table shipment_revisions enable row level security;

alter table shipments
  add column if not exists rev_no        integer not null default 0,
  add column if not exists revised_at    timestamptz,
  add column if not exists cancelled_at  timestamptz,
  add column if not exists cancel_reason text;

create table if not exists sales_month_close (
  ym        text primary key check (ym ~ '^[0-9]{4}-[0-9]{2}$'),
  closed_at timestamptz default now(),
  closed_by text,
  note      text
);
alter table sales_month_close enable row level security;

-- 백필: 확정 전표 라인의 지정 회차에 라인 수량을 충당한 것으로 기록
-- (사전 검증: 회차별 라인 합 > delivered_qty 인 회차 0건, 2026-09-04)
insert into shipment_allocations (si_id, sched_id, qty)
select si.si_id, si.sched_id, si.qty
  from shipment_items si
  join shipments s on s.shipment_id = si.shipment_id
 where s.status = 'CONFIRMED' and si.sched_id is not null and si.qty > 0
   and exists (select 1 from so_delivery_schedule d where d.sched_id = si.sched_id)
   and not exists (select 1 from shipment_allocations a where a.si_id = si.si_id);

create or replace view data_quality_v with (security_invoker = true) as
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
 SELECT 'ROUND_MISMATCH'::text AS code,
    '회차 납품합 대사 불일치'::text AS check_name,
    (COALESCE(p.pn, '-'::text) || ' · '::text) || o.so_number AS ref,
    ((((((('회차합 '::text || t.d::text) || ' vs 기대 '::text) || ((COALESCE(i.received_qty, 0::numeric) - COALESCE(i.presched_qty, 0::numeric))::text)) || ' (기납품 '::text) || COALESCE(i.received_qty, 0::numeric)::text) || ' − 스케줄이전 '::text) || COALESCE(i.presched_qty, 0::numeric)::text) || ')'::text AS detail
   FROM ( SELECT so_delivery_schedule.soi_id,
            sum(COALESCE(so_delivery_schedule.delivered_qty, 0::numeric)) AS d
           FROM so_delivery_schedule
          GROUP BY so_delivery_schedule.soi_id) t
     JOIN sales_order_items i ON i.soi_id = t.soi_id
     JOIN sales_orders o ON o.so_id = i.so_id
     LEFT JOIN products p ON p.product_id = i.product_id
  WHERE abs(t.d - (COALESCE(i.received_qty, 0::numeric) - COALESCE(i.presched_qty, 0::numeric))) > 0.5
UNION ALL
 SELECT 'PN_SPACE'::text AS code,
    '품번 앞뒤 공백'::text AS check_name,
    ('['::text || products.pn) || ']'::text AS ref,
    'product_id '::text || products.product_id AS detail
   FROM products
  WHERE products.pn <> btrim(products.pn)
UNION ALL
 SELECT 'PN_DUP'::text AS code,
    '활성 품번 중복'::text AS check_name,
    btrim(products.pn) AS ref,
    (count(*)::text || '건: '::text) || string_agg(products.product_id, ', '::text) AS detail
   FROM products
  WHERE products.archived_at IS NULL
  GROUP BY (btrim(products.pn))
 HAVING count(*) > 1
UNION ALL
 SELECT 'BOM_NONE'::text AS code,
    '활성 제품 BOM 소재 미연결'::text AS check_name,
    p.pn AS ref,
    COALESCE('소재 표기: '::text || p.raw_material_name, '소재 정보 없음'::text) AS detail
   FROM products p
  WHERE p.archived_at IS NULL AND NOT (EXISTS ( SELECT 1
           FROM bom b
          WHERE b.product_id = p.product_id AND COALESCE(b.process_type, 'MATERIAL'::text) = 'MATERIAL'::text))
UNION ALL
 SELECT 'MAT_TEXT'::text AS code,
    '제품 소재 표기 ≠ BOM 자재명'::text AS check_name,
    p.pn AS ref,
    (COALESCE(p.raw_material_name, '(없음)'::text) || ' vs '::text) || m.raw_name AS detail
   FROM products p
     JOIN bom b ON b.product_id = p.product_id AND COALESCE(b.process_type, 'MATERIAL'::text) = 'MATERIAL'::text
     JOIN materials m ON m.material_id = b.material_id
  WHERE p.archived_at IS NULL AND p.raw_material_name IS DISTINCT FROM m.raw_name
UNION ALL
 SELECT 'PO_UNMAPPED'::text AS code,
    '발주 라인 자재 미매핑'::text AS check_name,
    (o.po_number || ' · '::text) || COALESCE(i.item_name, '-'::text) AS ref,
    '수량 '::text || COALESCE(i.qty, 0::numeric)::text AS detail
   FROM purchase_order_items i
     JOIN purchase_orders o ON o.po_id = i.po_id
  WHERE i.material_id IS NULL AND COALESCE(o.status, ''::text) <> 'CANCELLED'::text
UNION ALL
 SELECT 'SO_UNMATCHED'::text AS code,
    '수주 라인 제품 미매칭 (미납)'::text AS check_name,
    (o.so_number || ' · '::text) || COALESCE(i.customer_part_no, '-'::text) AS ref,
    '미납 '::text || COALESCE(i.pending_qty, 0::numeric)::text AS detail
   FROM sales_order_items i
     JOIN sales_orders o ON o.so_id = i.so_id
  WHERE i.product_id IS NULL AND COALESCE(i.pending_qty, 0::numeric) > 0::numeric
UNION ALL
 SELECT 'ROUTE_COST_ORPHAN'::text AS code,
    '공정 원가행 라우팅 미연결'::text AS check_name,
    p.pn AS ref,
    (COALESCE(b.process_type, '-'::text) || ' '::text) || COALESCE(b.raw_material_name, '-'::text) AS detail
   FROM bom b
     JOIN products p ON p.product_id = b.product_id
  WHERE p.archived_at IS NULL AND (COALESCE(b.process_type, 'MATERIAL'::text) = ANY (ARRAY['HEAT'::text, 'SURFACE'::text, 'OUTSOURCE'::text])) AND (EXISTS ( SELECT 1
           FROM product_routing r
          WHERE r.product_id = b.product_id)) AND NOT (EXISTS ( SELECT 1
           FROM product_routing r
          WHERE r.bom_id = b.bom_id))
UNION ALL
 SELECT 'PROC_NO_PRICE'::text AS code,
    '공정행 표준 단가 미입력'::text AS check_name,
    p.pn AS ref,
    COALESCE(b.raw_material_name, '-'::text) || ' — 원가 확인 > 단가 관리에서 입력'::text AS detail
   FROM bom b
     JOIN products p ON p.product_id = b.product_id
  WHERE p.archived_at IS NULL AND b.unit_price IS NULL AND (COALESCE(b.process_type, 'MATERIAL'::text) = ANY (ARRAY['HEAT'::text, 'SURFACE'::text, 'OUTSOURCE'::text])) AND (EXISTS ( SELECT 1
           FROM product_routing r
          WHERE r.bom_id = b.bom_id))
UNION ALL
 SELECT 'PROC_NO_VENDOR'::text AS code,
    '공정행 업체 미매칭'::text AS check_name,
    p.pn AS ref,
    COALESCE(b.raw_material_name, '-'::text) || ' — BOM 편집 공정행 카드에서 업체 매칭 후 라우팅 재저장'::text AS detail
   FROM bom b
     JOIN products p ON p.product_id = b.product_id
  WHERE p.archived_at IS NULL AND b.process_vendor_id IS NULL AND (COALESCE(b.process_type, 'MATERIAL'::text) = ANY (ARRAY['HEAT'::text, 'SURFACE'::text, 'OUTSOURCE'::text])) AND (EXISTS ( SELECT 1
           FROM product_routing r
          WHERE r.bom_id = b.bom_id))
UNION ALL
 SELECT 'SHIP_ALLOC_MISMATCH'::text AS code,
    '확정 전표 라인 회차 충당 불일치'::text AS check_name,
    (s.ship_no || ' · '::text) || COALESCE(si.pn, '-'::text) AS ref,
    (('라인 '::text || si.qty::text) || ' vs 회차 충당 '::text) || COALESCE(a.q, 0::numeric)::text AS detail
   FROM shipment_items si
     JOIN shipments s ON s.shipment_id = si.shipment_id
     LEFT JOIN ( SELECT shipment_allocations.si_id, sum(shipment_allocations.qty) AS q
                   FROM shipment_allocations GROUP BY shipment_allocations.si_id) a ON a.si_id = si.si_id
  WHERE s.status = 'CONFIRMED'::text AND si.qty > 0::numeric AND abs(si.qty - COALESCE(a.q, 0::numeric)) > 0.5;
