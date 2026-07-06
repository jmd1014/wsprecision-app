-- ════════════════════════════════════════════════════════════
-- Migration 020: MES 실적 업로드 (공정 실적 raw)
-- ════════════════════════════════════════════════════════════
-- 배경:
--   사내 MES (작업지시서 스캔 실적) 의 일간 보고서 엑셀을 앱에
--   업로드 → 검수 → production_log 저장. 시트 수기 전기 대체.
--   ⚠️ 재고 연동 없음 — 공정 실적은 원장 밖 raw (보고서/분석용).
--   완성 확정 → 재고 연결은 별도 결정 후 (보류).
--
-- 변경 내용:
--   production_log 확장 3컬럼:
--   1. source     — 'MANUAL'(수기 생산 보고) / 'MES_UPLOAD'(MES 엑셀)
--   2. work_order — 작업지시서 번호 (예: 20260702-002 [001])
--   3. work_start / work_end — 작업시간 구간 (TEXT HH:MM)
--
-- 비파괴 / 멱등.
-- ════════════════════════════════════════════════════════════

ALTER TABLE production_log
  ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'MANUAL',
  ADD COLUMN IF NOT EXISTS work_order TEXT,
  ADD COLUMN IF NOT EXISTS work_start TEXT,
  ADD COLUMN IF NOT EXISTS work_end TEXT;

CREATE INDEX IF NOT EXISTS idx_prodlog_source ON production_log(source);
CREATE INDEX IF NOT EXISTS idx_prodlog_workorder ON production_log(work_order);

COMMENT ON COLUMN production_log.source IS
  'MANUAL=앱 수기 생산 보고(재고 연동) / MES_UPLOAD=MES 엑셀 업로드(공정 실적 raw, 재고 연동 없음)';
COMMENT ON COLUMN production_log.work_order IS
  'MES 작업지시서 번호. 수주-생산 연결 키 후보 (형식: YYYYMMDD-NNN [SEQ])';

-- 기존 수기 보고 행 명시
UPDATE production_log SET source = 'MANUAL' WHERE source IS NULL;
