-- ════════════════════════════════════════════════════════════
-- Migration 003: inventory_transactions + material_stock view
-- ════════════════════════════════════════════════════════════
-- 목적:
-- 1. 재고 변동을 거래 이력(transactional)으로 관리
-- 2. 현재고는 view에서 SUM 계산 → 단일 진실원천 보장
-- 3. 기존 materials.stock_qty는 보존하되 신규 로직에서는 직접 수정 X
--
-- 적용 방식: Supabase SQL Editor에서 이 파일 그대로 실행 (멱등)
-- ════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS inventory_transactions (
    txn_id        SERIAL      PRIMARY KEY,
    material_id   TEXT        NOT NULL REFERENCES materials(material_id),
    txn_type      TEXT        NOT NULL,
    qty           NUMERIC     NOT NULL,           -- 양수: 증가, 음수: 감소
    unit          TEXT        DEFAULT 'EA',
    ref_table     TEXT,                            -- 'purchase_orders', 'sales_orders', 'production_log' 등
    ref_id        INTEGER,                         -- 해당 테이블의 PK
    lot_number    TEXT,                            -- LOT 추적 (선택)
    product_id    TEXT        REFERENCES products(product_id),  -- 생산 관련 시 제품 연결
    txn_date      DATE        NOT NULL DEFAULT CURRENT_DATE,
    remark        TEXT,
    created_by    TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    -- 거래 유형 제약
    CONSTRAINT chk_inv_txn_type CHECK (txn_type IN (
        'RECEIPT',      -- 자재 입고 (양수)
        'ISSUE',        -- 자재 출고 (음수)
        'PROD_INPUT',   -- 생산 투입 — 자재 차감 (음수)
        'PROD_OUTPUT',  -- 생산 완성 — 제품 증가 (양수, 제품 자재의 경우)
        'DEFECT',       -- 불량 폐기 (음수)
        'ADJUSTMENT'    -- 재고 조정 (양수/음수 모두 가능)
    ))
);

CREATE INDEX IF NOT EXISTS idx_inv_txn_material ON inventory_transactions(material_id);
CREATE INDEX IF NOT EXISTS idx_inv_txn_date     ON inventory_transactions(txn_date);
CREATE INDEX IF NOT EXISTS idx_inv_txn_ref      ON inventory_transactions(ref_table, ref_id);
CREATE INDEX IF NOT EXISTS idx_inv_txn_lot      ON inventory_transactions(lot_number);


-- 현재고 = SUM(qty) 누적
CREATE OR REPLACE VIEW material_stock AS
SELECT
    m.material_id,
    m.raw_name,
    m.material_type,
    m.spec,
    m.unit,
    m.main_supplier,
    COALESCE(SUM(it.qty), 0)         AS current_stock,
    COALESCE(SUM(CASE WHEN it.txn_type = 'RECEIPT'    THEN it.qty ELSE 0 END), 0) AS total_received,
    COALESCE(SUM(CASE WHEN it.txn_type = 'PROD_INPUT' THEN it.qty ELSE 0 END), 0) AS total_consumed,
    COALESCE(SUM(CASE WHEN it.txn_type = 'DEFECT'     THEN it.qty ELSE 0 END), 0) AS total_defect,
    MAX(it.txn_date)                  AS last_txn_date,
    COUNT(it.txn_id)                  AS txn_count
FROM materials m
LEFT JOIN inventory_transactions it USING (material_id)
GROUP BY m.material_id, m.raw_name, m.material_type, m.spec, m.unit, m.main_supplier;


-- LOT별 재고 view
CREATE OR REPLACE VIEW material_stock_by_lot AS
SELECT
    material_id,
    lot_number,
    SUM(qty) AS lot_balance,
    MAX(txn_date) AS last_date
FROM inventory_transactions
WHERE lot_number IS NOT NULL
GROUP BY material_id, lot_number
HAVING SUM(qty) > 0;


-- 코멘트 (legacy 컬럼 표시)
COMMENT ON COLUMN materials.stock_qty IS
    'LEGACY: 신규 로직에서는 사용 금지. 현재고는 material_stock view 사용.';
