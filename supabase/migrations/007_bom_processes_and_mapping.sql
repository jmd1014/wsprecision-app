-- ════════════════════════════════════════════════════════════
-- Migration 007: BOM 공정행 + 데이터 매핑 컬럼 (스캐폴딩)
-- ════════════════════════════════════════════════════════════
-- 목적:
--   향후 매입/매출/생산 데이터와의 매핑을 위한 키 컬럼을 미리 확보.
--   현재는 NULL 허용 → 데이터 점진 입력. 화면 기능은 fallback 로직으로
--   기존 정적 컬럼 계속 사용.
--
-- 컬럼은 모두 IF NOT EXISTS — 멱등 실행.
-- 데이터 백필 없음. 운영 영향 최소.
-- ════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────
-- 1. BOM 확장 — 공정행 지원
-- ─────────────────────────────────────────
-- 자재 외 공정(열처리/표면처리/외주/포장/노무) 도 BOM 한 곳에서 관리.
-- 공식: per_pc_cost = unit_price × qty_per_pc / shared_factor
--   - MATERIAL : qty_per_pc=자재사용량, shared_factor=분할가공수
--   - HEAT/SURFACE : qty_per_pc=1, shared_factor=1 LOT 처리수, unit_price=LOT가격
--   - OUTSOURCE  : qty_per_pc=1, shared_factor=1, unit_price=EA당 외주비
ALTER TABLE bom
  ADD COLUMN IF NOT EXISTS process_type      TEXT DEFAULT 'MATERIAL',
  ADD COLUMN IF NOT EXISTS unit_price        NUMERIC,
  ADD COLUMN IF NOT EXISTS lot_label         TEXT,
  ADD COLUMN IF NOT EXISTS process_vendor_id INTEGER REFERENCES vendors(vendor_id);

-- CHECK 제약 (멱등)
ALTER TABLE bom DROP CONSTRAINT IF EXISTS chk_bom_process_type;
ALTER TABLE bom ADD CONSTRAINT chk_bom_process_type
  CHECK (process_type IN ('MATERIAL','HEAT','SURFACE','OUTSOURCE','PACKING','LABOR','OTHER'));

CREATE INDEX IF NOT EXISTS idx_bom_process_type ON bom(process_type);

COMMENT ON COLUMN bom.process_type IS
  'MATERIAL/HEAT/SURFACE/OUTSOURCE/PACKING/LABOR/OTHER. 자재 외 공정 라인도 BOM에 통합.';
COMMENT ON COLUMN bom.unit_price IS
  '행 단위 단가. MATERIAL은 NULL이면 material_price_v에서 fallback, 공정행은 직접 입력 필수.';
COMMENT ON COLUMN bom.lot_label IS
  'UI 표시용. 예: "LOT", "CH", "BATCH". 단가 계산에는 미사용.';
COMMENT ON COLUMN bom.process_vendor_id IS
  '공정 외주 거래처. 추후 발주 자동 제안용.';


-- ─────────────────────────────────────────
-- 2. purchase_ledger — 자재 매핑 키
-- ─────────────────────────────────────────
-- 현재는 matched_pn (제품 매칭) 만 있음. 자재 매핑이 없어
-- 자재별 시점 단가를 계산할 수 없었음.
-- 점진적으로 채우면 material_price_v 가 자동 활성화.
ALTER TABLE purchase_ledger
  ADD COLUMN IF NOT EXISTS matched_material_id TEXT REFERENCES materials(material_id),
  ADD COLUMN IF NOT EXISTS mapping_status TEXT;

CREATE INDEX IF NOT EXISTS idx_purchase_matched_material
  ON purchase_ledger(matched_material_id);

COMMENT ON COLUMN purchase_ledger.matched_material_id IS
  '자재 마스터 매핑 키. NULL = 미매핑. 마스터 관리 화면에서 점진 입력.';
COMMENT ON COLUMN purchase_ledger.mapping_status IS
  'AUTO_MATCHED / MANUAL / REVIEW_NEEDED / UNMAPPED 등';


-- ─────────────────────────────────────────
-- 3. production_log — 제품 ID 매핑 키
-- ─────────────────────────────────────────
-- 현재는 pn 텍스트만 있어 안전한 join 불가. 추후 자동 매핑 도구로 채움.
ALTER TABLE production_log
  ADD COLUMN IF NOT EXISTS product_id TEXT REFERENCES products(product_id);

CREATE INDEX IF NOT EXISTS idx_prodlog_product_id
  ON production_log(product_id);

COMMENT ON COLUMN production_log.product_id IS
  '제품 마스터 매핑 키. 기존 pn 텍스트와 병행. 자동 매핑 후 product_actual_cost_v 활성.';


-- ─────────────────────────────────────────
-- 4. materials — 시점 기반 단가 표시용 캐시 (선택)
-- ─────────────────────────────────────────
-- view 계산 결과를 materials 에 캐시할 수도 있지만,
-- 단일 진실원천 원칙상 view 가 매번 계산. 캐시 컬럼은 추가하지 않음.

-- materials.unit 이 NULL 인 행 보강 (BOM 공정행은 unit='EA' 가정)
UPDATE materials SET unit = 'EA' WHERE unit IS NULL;
