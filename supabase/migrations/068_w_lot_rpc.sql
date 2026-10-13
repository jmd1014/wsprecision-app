-- ════════════════════════════════════════════════════════════
-- Migration 068: 소재 식별 번호(W LOT) 채번 RPC + 입고 유니크
-- (L3-S 계획서 docs/development/plans/20261012_L3S_출고확정RPC_채번RPC_오류기록.md B 항목)
-- ════════════════════════════════════════════════════════════
-- 문제:
--   앱 w_lot_next() 가 "max(카운터, 원장 최대) + 1 → 카운터 갱신" 을 잠금 없이
--   해서 두 사용자가 동시에 입고하면 같은 번호가 나올 수 있다 (예방 조치).
-- 해결:
--   ① RECEIPT 행의 W 번호 부분 유니크 인덱스 — 혼합 버전 창(옛 앱 폴백)·
--      "식별 번호 변경" 중복까지 DB 가 거부. PROD_INPUT 은 분할 투입으로
--      같은 LOT 가 여러 행이라 RECEIPT 만 (2026-10-12 확인: RECEIPT 중복 0).
--      인덱스를 먼저 만든다 — 중복이 있어 실패하면 함수만 남지 않도록.
--   ② next_w_lot(p_count): advisory lock 아래에서 base 계산·카운터 갱신까지
--      한 트랜잭션 — 예약 자체가 원자적. 카운터 미설정이면 예외
--      (앱은 지금처럼 "식별 번호 없이 입고" 안내).
-- F 번호(YYYYMMDD-F##) 채번은 번호 제시와 insert 사이 간격 때문에 함수로
-- 예약이 안 되어 제외 (2026-10-13 사용자 결정: 현행 유지).
-- 보안: SECURITY INVOKER + search_path 고정, anon/authenticated 실행 차단.
-- 되돌리기:
--   DROP FUNCTION IF EXISTS public.next_w_lot(integer);
--   DROP INDEX IF EXISTS public.inventory_transactions_w_receipt_uidx;
--   (카운터 값은 그대로 두어도 앱 폴백과 호환 — 둘 중 큰 값 규칙)
-- ════════════════════════════════════════════════════════════

-- ① 입고(RECEIPT) 행의 W 번호는 하나만
CREATE UNIQUE INDEX IF NOT EXISTS inventory_transactions_w_receipt_uidx
    ON public.inventory_transactions (lot_number)
    WHERE txn_type = 'RECEIPT' AND lot_number ~ '^W[0-9]+$';

-- ② 채번 함수
DROP FUNCTION IF EXISTS public.next_w_lot(integer);

CREATE FUNCTION public.next_w_lot(p_count integer DEFAULT 1)
RETURNS text[]
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_counter_txt text;
    v_counter     integer;
    v_ledger_max  integer;
    v_base        integer;
    v_out         text[] := '{}';
    i             integer;
BEGIN
    IF p_count IS NULL OR p_count <= 0 THEN
        RETURN '{}';
    END IF;
    IF p_count > 100 THEN
        RAISE EXCEPTION 'w_lot_count_too_large' USING ERRCODE = 'P0001',
            HINT = '한 번에 100개까지';
    END IF;

    -- 같은 키의 호출을 트랜잭션 단위로 직렬화 (005 의 next_po_number 와 같은 방식,
    -- 2-key 형으로 키 공간 분리)
    PERFORM pg_advisory_xact_lock(1, hashtext('w_lot'));

    SELECT value INTO v_counter_txt FROM app_settings WHERE key = 'w_lot_counter';
    IF v_counter_txt IS NULL OR v_counter_txt !~ '^[0-9]+$' THEN
        RAISE EXCEPTION 'w_lot_counter_unset' USING ERRCODE = 'P0001',
            HINT = '입고 처리 탭 하단에서 마지막 사용 번호를 저장';
    END IF;
    v_counter := v_counter_txt::integer;

    -- 원장 실사용 최대 번호 — 'W' + 숫자만 (앱 폴백 파서와 같은 규칙)
    SELECT COALESCE(MAX(substring(lot_number FROM '^W([0-9]+)$')::integer), 0)
      INTO v_ledger_max
      FROM inventory_transactions
     WHERE lot_number LIKE 'W%' AND lot_number ~ '^W[0-9]+$';

    v_base := GREATEST(v_counter, v_ledger_max);

    FOR i IN 1..p_count LOOP
        v_out := v_out || ('W' || lpad((v_base + i)::text, 4, '0'));
    END LOOP;

    UPDATE app_settings
       SET value = (v_base + p_count)::text,
           updated_at = now()
     WHERE key = 'w_lot_counter';

    RETURN v_out;
END;
$$;

COMMENT ON FUNCTION public.next_w_lot(integer) IS
    '소재 식별 번호(W####) p_count 개 예약 — advisory lock 아래 max(카운터, 원장 최대)+1, 카운터 갱신까지 한 트랜잭션. 미설정이면 w_lot_counter_unset.';

REVOKE EXECUTE ON FUNCTION public.next_w_lot(integer) FROM PUBLIC, anon, authenticated;
GRANT  EXECUTE ON FUNCTION public.next_w_lot(integer) TO service_role;
