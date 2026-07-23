-- ════════════════════════════════════════════════════════════
-- Migration 023: Phase E-2 — 공정 처리 (인수/외주/검사/재작업/완성)
-- ════════════════════════════════════════════════════════════
-- wo_tracking 에 2개 컬럼 추가:
--   rework_in_qty : 재작업 복귀 누적 — 재작업중 = rework_qty - rework_in_qty
--                   (복귀분은 검사 대기 풀로 재진입)
--   output_qty    : 완성 확정 누적 — 완성 대기 = pass_qty - output_qty
--                   (확정 시 PROD_OUTPUT 원장 기록과 함께 증가)
--
-- 상태 유도 규칙 (앱에서 계산 — 직접 상태 변경 없음):
--   IN_PROD(생산중>0) → OUTSOURCE(외주중>0) → REWORK(재작업중>0)
--   → INSPECT(검사대기>0) → READY(완성대기>0) → CLOSED(전량 확정)
--
-- 비파괴 / 멱등.
-- ════════════════════════════════════════════════════════════

ALTER TABLE wo_tracking
  ADD COLUMN IF NOT EXISTS rework_in_qty NUMERIC NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS output_qty    NUMERIC NOT NULL DEFAULT 0;

COMMENT ON COLUMN wo_tracking.rework_in_qty IS
  '재작업 복귀 누적 — 재작업중 = rework_qty - rework_in_qty';
COMMENT ON COLUMN wo_tracking.output_qty IS
  '완성 확정 누적 (PROD_OUTPUT 연동) — 완성 대기 = pass_qty - output_qty';
