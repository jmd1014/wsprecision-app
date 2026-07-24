-- Migration 025: 검사 반품 (2026-07-24 피드백)
-- 검사 불합격 4분기: 재작업/폐기/특채 + 반품(공급처 반품, 재고 미편입).
-- 동시에 검사 재설계 — 합격·특채는 검사 시 즉시 완성(PROD_OUTPUT),
-- '완성 대기(READY)' 상태와 완성 확정 액션 제거 (앱 코드).
ALTER TABLE wo_tracking
  ADD COLUMN IF NOT EXISTS return_qty NUMERIC NOT NULL DEFAULT 0;
COMMENT ON COLUMN wo_tracking.return_qty IS
  '검사 반품 누적 (소재/가공 불량 — 공급처 반품, 재고 미편입)';
