-- ════════════════════════════════════════════════════════════
-- Migration 067: 앱 오류 기록 테이블 app_errors
-- (L3-S 계획서 docs/development/plans/20261012_L3S_출고확정RPC_채번RPC_오류기록.md C 항목)
-- ════════════════════════════════════════════════════════════
-- 목적:
--   db 쓰기 실패·미처리 예외·RPC 폴백/거부를 서버에 남겨 사후 추적한다
--   (2026-10-08 SH-20261008-04: 머리글 저장 실패가 except: pass 로 묻힘).
-- 성격:
--   기록 전용. 업무 데이터 아님 — 야간 백업(scripts/backup_tables.py)에는 자동으로
--   포함되지만 복구 대상은 아니다(손실 허용). 자동 purge 없음(무인 작업 DB 쓰기 금지) — 분기별 수동 정리.
-- 보안:
--   RLS ENABLE, 정책 없음 → service_role 만 읽고 쓴다 (anon/authenticated 차단).
-- 되돌리기:
--   DROP TABLE public.app_errors;
-- ════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.app_errors (
    err_id      bigserial PRIMARY KEY,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    page        text,
    user_name   text,
    kind        text NOT NULL
                CHECK (kind IN ('db_write', 'unhandled', 'rpc_fallback',
                                'rpc_rejected', 'manual')),
    table_name  text,
    detail      text,
    traceback   text
);

CREATE INDEX IF NOT EXISTS app_errors_occurred_at_idx
    ON public.app_errors (occurred_at DESC);

ALTER TABLE public.app_errors ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE public.app_errors IS
    '앱 오류 기록 (db 쓰기 실패·미처리 예외·RPC 폴백). 기록 전용, 복구 대상 아님, 수동 정리.';
