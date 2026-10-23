-- ════════════════════════════════════════════════════════════
-- 복구: 운영 ledger(supabase_migrations.schema_migrations) 에서 추출 2026-10-23 — 원본 파일 커밋 없음 (P1-5)
-- version: 20260812085231  name: 036_product_routing
-- ════════════════════════════════════════════════════════════
-- Migration 036: 제품별 공정 라우팅 (공정 순서 마스터)
-- 배경: 공정 관리가 고정 5단계(투입→생산→외주→검사→완성)라 MRG6-07처럼
--       소재열처리(투입 전 외주)·제품열처리(가공 후 외주)가 구분되는 제품의
--       공정 순서를 표현할 수 없음. 라우팅은 순서를, BOM은 원가를 담당.
-- 규칙: 라우팅이 없는 제품은 앱이 기본 플로우(소재입고→생산→검사→완성) 사용.

CREATE TABLE product_routing (
  routing_id  serial PRIMARY KEY,
  product_id  text NOT NULL REFERENCES products(product_id),
  seq         int  NOT NULL,
  step_code   text NOT NULL,   -- MAT_IN | PROD | OUT | INSPECT | DONE
  step_name   text NOT NULL,   -- 화면 표기: 소재입고·생산·고용화·에이징·검사·완성
  step_kind   text NOT NULL DEFAULT 'INHOUSE',  -- INHOUSE | OUTSOURCE
  stage       text NOT NULL DEFAULT 'PRODUCT',  -- MATERIAL(투입 전) | PRODUCT
  bom_id      int REFERENCES bom(bom_id) ON DELETE SET NULL,  -- 원가 행 연결
  default_vendor text,
  confirmed   boolean NOT NULL DEFAULT false,   -- 순서 사용자 확정 여부
  created_at  timestamptz DEFAULT now(),
  updated_at  timestamptz DEFAULT now(),
  UNIQUE (product_id, seq)
);
COMMENT ON TABLE product_routing IS
  '제품별 공정 순서 마스터 — 기본 플로우와 다른 제품만 행을 가짐. '
  '순서는 여기, 공정 원가는 BOM(process_type 행) 담당. 라우팅 없으면 기본 플로우.';
ALTER TABLE product_routing ENABLE ROW LEVEL SECURITY;

-- 공정 이벤트에 라우팅 참조 (이력은 이름을 비정규화 보존)
ALTER TABLE wo_events ADD COLUMN IF NOT EXISTS routing_id int;
ALTER TABLE wo_events ADD COLUMN IF NOT EXISTS step_name text;

-- 시드: BOM에 공정 행(HEAT/SURFACE)이 있는 제품만 초기 라우팅 생성.
-- 외주 스텝 위치는 데이터에 없으므로 일단 생산 뒤에 두고 confirmed=false —
-- 마스터 관리 > 공정 라우팅에서 사용자가 순서 확정.
WITH p AS (
  SELECT product_id FROM bom
  WHERE process_type IN ('HEAT','SURFACE') GROUP BY product_id
), o AS (
  SELECT b.product_id, b.bom_id, b.raw_material_name, b.process_type,
         row_number() OVER (PARTITION BY b.product_id ORDER BY b.bom_id) rn
  FROM bom b WHERE b.process_type IN ('HEAT','SURFACE')
)
INSERT INTO product_routing
  (product_id, seq, step_code, step_name, step_kind, stage, bom_id)
SELECT product_id, 1, 'MAT_IN', '소재입고', 'INHOUSE', 'MATERIAL', NULL::int FROM p
UNION ALL
SELECT product_id, 10, 'PROD', '생산', 'INHOUSE', 'PRODUCT', NULL::int FROM p
UNION ALL
SELECT product_id, 10 + rn, 'OUT',
       COALESCE(NULLIF(raw_material_name, ''), process_type),
       'OUTSOURCE', 'PRODUCT', bom_id FROM o
UNION ALL
SELECT product_id, 50, 'INSPECT', '검사', 'INHOUSE', 'PRODUCT', NULL::int FROM p
UNION ALL
SELECT product_id, 60, 'DONE', '완성', 'INHOUSE', 'PRODUCT', NULL::int FROM p;
