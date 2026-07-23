-- ════════════════════════════════════════════════════════════
-- Migration 024: 공정 이벤트 이력 (wo_events)
-- ════════════════════════════════════════════════════════════
-- 배경 (2026-07-23 피드백):
--   wo_tracking 은 누적 수량만 보유 → 스텝별 흐름 확인 불가,
--   라벨/의뢰서가 발행 직후에만 다운로드 가능 (재발행 불가).
--   → 모든 공정 행위를 이벤트로 기록해 타임라인 조회 + 문서
--   재발행(외주 의뢰서/검사 판정 라벨/완성 라벨)을 지원.
--
-- event_type: INPUT(투입)/RECEIVE(완료 인수)/OUT_SEND(외주 출고)/
--   OUT_RETURN(외주 입고)/INSPECT(검사)/REWORK_BACK(재작업 복귀)/
--   OUTPUT(완성 확정)
-- detail(JSONB): 외주 {vendor,process,due,note} /
--   검사 {pass,rework,scrap,tokusai} / 완성 {tokusai}
--
-- 비파괴 / 멱등.
-- ════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS wo_events (
  event_id   SERIAL PRIMARY KEY,
  wo_id      INTEGER,
  wo_number  TEXT NOT NULL,
  w_lot      TEXT,
  pn         TEXT,
  event_type TEXT NOT NULL,
  qty        NUMERIC,
  detail     JSONB,
  event_date DATE,
  created_by TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_wo_events_wo ON wo_events(wo_number);
COMMENT ON TABLE wo_events IS
  '공정 행위 이벤트 이력 — 타임라인 조회 + 라벨/의뢰서 재발행 근거';
