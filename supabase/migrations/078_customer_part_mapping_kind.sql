-- ════════════════════════════════════════════════════════════
-- Migration 078: customer_part_mapping.kind — 출하 품번(variant) / 별칭(alias) 구분 (2026-11-02, PN 묶음 r2)
-- 기준: _거래처품번표시_묶음_지시문_r2_20261102.md §1 (사용자 결정 11-02)
-- ════════════════════════════════════════════════════════════
-- 배경: 엠제이티 P0005(H11SDF-2C-10-01)는 사내 생산·재고는 하나인데 거래처가 세 품번(기본·-RE-P·-RV-P)으로
--   따로 주문·납품받는다(유형 1 '출하 품번'). 미진 ERP 코드(4S/S/6 접두·;PM 접미·AP/MP·-P) 같은 나머지 매핑은
--   같은 출하 품번의 다른 표기(유형 2 '별칭'). 앱은 variant 로 등록된 (제품, 거래처 품번)만 라인 화면에 병기한다.
-- 변경: 열 1개 추가, 기본 'alias' → 기존 행은 모두 alias(화면 표시 = 지금과 동일).
-- 운영 데이터(이 파일 밖, L3-D): 코드 배포 뒤 사용자 "적용" 때
--   UPDATE customer_part_mapping SET kind='variant' WHERE mapping_id IN (14,15,16,17);   -- P0005 -RE-P/-RV-P 4행
--   + master_change_log 4행 '[일괄 정정 YYYY-MM-DD]'. 기대값: alias 28 · variant 4.
-- 적용 조건: 기존 행 값 무접촉(기본값 채움만). 멱등(IF NOT EXISTS). RLS·정책 변화 없음(열 추가).
-- 되돌리기: ALTER TABLE public.customer_part_mapping DROP COLUMN IF EXISTS kind;
--   (앱은 kind 조회 실패 시 variant 0건으로 동작 = 묶음 전 표시)
-- ════════════════════════════════════════════════════════════

ALTER TABLE public.customer_part_mapping
    ADD COLUMN IF NOT EXISTS kind text NOT NULL DEFAULT 'alias';

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conname = 'customer_part_mapping_kind_check') THEN
        ALTER TABLE public.customer_part_mapping
            ADD CONSTRAINT customer_part_mapping_kind_check
            CHECK (kind IN ('alias', 'variant'));
    END IF;
END $$;

COMMENT ON COLUMN public.customer_part_mapping.kind IS
    'alias = 같은 출하 품번의 다른 표기(화면에 안 보임) / variant = 출하 품번(같은 제품을 거래처가 구분 주문·납품, 라인에 병기)';
