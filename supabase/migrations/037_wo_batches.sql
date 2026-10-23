-- ════════════════════════════════════════════════════════════
-- 복구: 운영 ledger(supabase_migrations.schema_migrations) 에서 추출 2026-10-23 — 원본 파일 커밋 없음 (P1-5)
-- version: 20260818014711  name: 037_wo_batches
-- ════════════════════════════════════════════════════════════
-- Migration 037: 공정 배치(서브랏) 원장 + 계보 — Phase A (병행 기록)
-- 배경: 공정 단계마다 자유로운 수량 분기·합류와 완전한 추적성(소재→
--       열처리 회차→완성 LOT→출고)을 위해 배치를 1급 개념으로 도입.
-- 규칙(2026-08-12 사용자 확정):
--   배치번호 = 지시번호-가지 (예: 20260812-003-A, 분기·합류로 B, C…)
--   합류는 같은 작업지시 안에서만 허용
-- Phase A 는 테이블 + 투입 시 배치 생성만 — 동작 변화 없음.
-- Phase B 에서 공정 처리를 배치 단위로 전환 예정.

CREATE TABLE wo_batches (
  batch_id   serial PRIMARY KEY,
  batch_no   text NOT NULL UNIQUE,     -- 지시번호-가지: 20260812-003-A
  wo_id      int,                      -- wo_tracking 참조 (지시 삭제 시 정리)
  wo_number  text NOT NULL,
  product_id text,
  pn         text,
  w_lot      text,                     -- 소재 LOT (추적 사슬의 뿌리)
  qty        numeric NOT NULL,
  routing_id int,                      -- 현재 라우팅 스텝 (없으면 step_code 기준)
  step_code  text NOT NULL DEFAULT 'PROD',   -- 현재 위치: PROD/OUT/INSPECT/DONE
  step_name  text,
  location   text,                     -- 사내 또는 외주 거래처명
  status     text NOT NULL DEFAULT 'OPEN',   -- OPEN | CLOSED(완성·폐기) | CANCELLED
  created_by text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);
COMMENT ON TABLE wo_batches IS
  '공정 배치(서브랏) — 공정을 흐르는 수량 덩어리의 정체성. 부분 처리=분기, '
  '합치기=합류(같은 지시 내만). 계보는 batch_links. Phase A: 병행 기록.';
ALTER TABLE wo_batches ENABLE ROW LEVEL SECURITY;
CREATE INDEX idx_wo_batches_wo ON wo_batches (wo_number);

CREATE TABLE batch_links (
  link_id         serial PRIMARY KEY,
  parent_batch_id int NOT NULL REFERENCES wo_batches(batch_id),
  child_batch_id  int NOT NULL REFERENCES wo_batches(batch_id),
  qty             numeric NOT NULL,    -- 부모→자식으로 넘어간 수량
  link_type       text NOT NULL,       -- SPLIT | MERGE
  created_at      timestamptz DEFAULT now()
);
COMMENT ON TABLE batch_links IS
  '배치 계보(genealogy) DAG — 분기(SPLIT)·합류(MERGE)의 부모-자식 관계. '
  '역추적: 완성 LOT→부모 사슬→소재. 전방추적: 소재→후손→출고처.';
ALTER TABLE batch_links ENABLE ROW LEVEL SECURITY;

ALTER TABLE wo_events ADD COLUMN IF NOT EXISTS batch_id int;

-- 백필: 진행 중 작업지시에 초기 배치(-A) 생성 (현재 위치 = 생산중)
INSERT INTO wo_batches
  (batch_no, wo_id, wo_number, product_id, pn, w_lot, qty,
   step_code, step_name, location, created_by)
SELECT wo_number || '-A', wo_id, wo_number, product_id, pn, w_lot,
       input_qty, 'PROD', '생산', '사내', created_by
FROM wo_tracking WHERE status <> 'CLOSED';
