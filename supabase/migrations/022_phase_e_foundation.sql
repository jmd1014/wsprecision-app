-- ════════════════════════════════════════════════════════════
-- Migration 022: Phase E 기반 — 공정 관리 (투입~외주~검사~완성)
-- ════════════════════════════════════════════════════════════
-- 배경 (2026-07-23 합의):
--   생산은 MES, 생산 앞뒤는 앱 분업. 앱이 소재입고(W번호 채번+라벨)
--   → 투입 등록(작업지시 NO) → 완료 인수 → 외주(의뢰서) → 검사
--   (합격/불합격: 재작업·폐기·특채) → 완성 재고 → 출고를 담당.
--   상태는 행위의 부산물 (직접 상태 변경 없음).
--
-- 1) app_settings — W번호 채번 카운터 등 앱 설정 (시작점은 사용자 지정)
-- 2) inventory_transactions.work_order — 원장 ↔ 작업지시 연결
--    (MES 실적 production_log.work_order 와 같은 키로 만남)
-- 3) wo_tracking — 작업지시 단위 추적 (투입/인수/합격/불합격 수량 누적)
--
-- 비파괴 / 멱등.
-- ════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS app_settings (
  key        TEXT PRIMARY KEY,
  value      TEXT,
  updated_at TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE app_settings IS '앱 설정 (w_lot_counter: W번호 채번 마지막 번호 등)';

ALTER TABLE inventory_transactions
  ADD COLUMN IF NOT EXISTS work_order TEXT;
CREATE INDEX IF NOT EXISTS idx_invtxn_workorder
  ON inventory_transactions(work_order);
COMMENT ON COLUMN inventory_transactions.work_order IS
  'MES 작업지시 번호 (YYYYMMDD-NNN) — 투입/외주/완성 원장을 작업지시로 연결';

CREATE TABLE IF NOT EXISTS wo_tracking (
  wo_id        SERIAL PRIMARY KEY,
  wo_number    TEXT NOT NULL,              -- 작업지시 NO (예: 20260723-001)
  product_id   TEXT,
  pn           TEXT,
  material_id  TEXT,
  w_lot        TEXT,                       -- 소재 LOT (W번호, 예: W0905)
  input_qty    NUMERIC NOT NULL DEFAULT 0, -- 투입 수량 (소재)
  received_qty NUMERIC NOT NULL DEFAULT 0, -- 공정 완료 인수 누적
  outsource_qty NUMERIC NOT NULL DEFAULT 0,-- 외주 출고 누적 (미복귀분 = 외주 재공)
  outsource_in_qty NUMERIC NOT NULL DEFAULT 0, -- 외주 입고(복귀) 누적
  pass_qty     NUMERIC NOT NULL DEFAULT 0, -- 검사 합격 누적 (특채 포함)
  tokusai_qty  NUMERIC NOT NULL DEFAULT 0, -- 그중 특채 수량
  rework_qty   NUMERIC NOT NULL DEFAULT 0, -- 재작업 (재검사 재진입 대상)
  scrap_qty    NUMERIC NOT NULL DEFAULT 0, -- 폐기
  status       TEXT NOT NULL DEFAULT 'IN_PROD',
               -- IN_PROD(생산중)/RECEIVED(인수)/OUTSOURCE(외주중)/
               -- INSPECT(검사중)/DONE(완성)/CLOSED(종결) — 수량에서 자동 유도
  remark       TEXT,
  created_by   TEXT,
  created_at   TIMESTAMPTZ DEFAULT now(),
  updated_at   TIMESTAMPTZ DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_wo_tracking_wo_lot
  ON wo_tracking(wo_number, w_lot);
CREATE INDEX IF NOT EXISTS idx_wo_tracking_status ON wo_tracking(status);
COMMENT ON TABLE wo_tracking IS
  'Phase E 작업지시 추적 — 투입(생산중)→인수→외주→검사→완성 수량 누적. 상태는 수량에서 유도';
