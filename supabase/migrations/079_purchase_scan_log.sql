-- ════════════════════════════════════════════════════════════
-- Migration 079: 매입 스캔 정정 기록 purchase_scan_log (2026-11-04, 매입 OCR r2)
-- 기준: _매입OCR_r2_정정기록_묶음_지시문_20261104.md §1 (사용자 결정 11-04)
-- ════════════════════════════════════════════════════════════
-- 목적:
--   매입 등록 스캔 판독에서 "이 장을 장부에 추가"가 성공할 때마다 장 1행을 남긴다 —
--   OCR 이 읽은 값(검토 표 기본값)과 담당자가 고쳐 저장한 값, 그 차이(diff). 검토 세션이 읽기 전용으로
--   집계해 해석 규칙 추록·테스트 픽스처를 만든다(원본 이미지는 넣지 않는다).
-- 성격:
--   기록 전용. 업무 데이터 아님 — 장부(purchase_ledger)와 연결 키 없음, 손실 허용.
--   앱은 이 표 insert 실패를 삼킨다(장부 저장은 그대로) → 표가 없어도 매입 등록은 동작.
--   보존: 자동 purge 없음 — 연 1회 또는 rules_version 2판 지난 행 수동 정리. 야간 백업에 자동 포함.
-- 변경: 새 표 1개·인덱스 2개. 기존 표·RPC·정책 무변경. 멱등(IF NOT EXISTS).
-- 보안:
--   RLS ENABLE, 정책 없음 → service_role 만 읽고 쓴다 (anon/authenticated 차단, 067 app_errors 와 같은 방식).
-- 되돌리기:
--   DROP TABLE IF EXISTS public.purchase_scan_log;
-- ════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.purchase_scan_log (
    log_id          bigserial PRIMARY KEY,
    created_at      timestamptz NOT NULL DEFAULT now(),
    created_by      text,
    rules_version   text,               -- utils.stmt_ocr.OCR_RULES_VERSION
    file_name       text,
    page            int,
    psm             int,
    rot             int,
    vendor_ocr      text,               -- OCR 이 찾은 거래처(못 찾으면 NULL)
    vendor_how      text,               -- biz | name | NULL
    vendor_saved    text,
    date_ocr        date,
    date_saved      date,
    statement_no    text,
    total_ok        boolean,
    printed_total   numeric,            -- 합계 줄 숫자 중 최댓값
    ocr_sum         numeric,            -- OCR 라인 공급가액 합
    saved_sum       numeric,            -- 저장 라인 공급가액 합(합산·KG 변환 전)
    lines           jsonb,              -- 판독 줄 텍스트 배열(픽스처 재료)
    items_ocr       jsonb,              -- 검토 표 기본값 행(+ idx)
    items_saved     jsonb,              -- 저장 직전 행(+ idx, 추가 행은 idx NULL)
    diff            jsonb,              -- utils.scan_log.scan_diff 결과
    n_rows_ocr      int,
    n_rows_saved    int,
    n_rows_added    int,
    n_rows_removed  int,
    n_cells_changed int,
    n_head_changed  int                 -- 거래처·거래일 정정 수(0~2)
);

CREATE INDEX IF NOT EXISTS purchase_scan_log_created_at_idx
    ON public.purchase_scan_log (created_at DESC);
CREATE INDEX IF NOT EXISTS purchase_scan_log_vendor_date_idx
    ON public.purchase_scan_log (vendor_saved, date_saved);

ALTER TABLE public.purchase_scan_log ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE public.purchase_scan_log IS
    '매입 스캔 판독 정정 기록(장 1행, 저장 성공 때만). 기록 전용, 손실 허용, 검토 세션 읽기 전용 집계.';
