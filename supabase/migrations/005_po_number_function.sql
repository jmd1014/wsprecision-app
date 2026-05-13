-- ════════════════════════════════════════════════════════════
-- Migration 005: 동시성 안전 발주번호 채번 함수
-- ════════════════════════════════════════════════════════════
-- 문제:
--   현재 Python의 generate_po_number()는 "MAX 조회 후 +1" 방식.
--   동일 시점에 두 사용자가 발주를 만들면 같은 번호가 부여될 수 있음.
--
-- 해결:
--   pg_advisory_xact_lock으로 같은 yyyymm 키에 대해 트랜잭션 직렬화.
--   동시 호출이 있어도 한 번에 하나씩 처리되어 중복 방지.
--
-- 사용:
--   Python: requests.post(f'{URL}/rest/v1/rpc/next_po_number', headers=H, json={})
--   →  결과: "PO-202605-001"  (다음 번호)
-- ════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION next_po_number()
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    yyyymm  TEXT;
    seq     INTEGER;
    new_no  TEXT;
BEGIN
    yyyymm := to_char(CURRENT_DATE, 'YYYYMM');

    -- 같은 yyyymm 키에 대한 트랜잭션 advisory lock
    PERFORM pg_advisory_xact_lock(hashtext('po_' || yyyymm));

    -- 이번 달 마지막 일련번호 조회
    SELECT COALESCE(
        MAX(
            CASE
                WHEN po_number ~ ('^PO-' || yyyymm || '-[0-9]+$')
                THEN CAST(SUBSTRING(po_number FROM 11) AS INTEGER)
                ELSE 0
            END
        ),
        0
    ) + 1
    INTO seq
    FROM purchase_orders
    WHERE po_number LIKE 'PO-' || yyyymm || '-%';

    new_no := 'PO-' || yyyymm || '-' || lpad(seq::text, 3, '0');
    RETURN new_no;
END;
$$;


-- 같은 패턴의 수주번호 채번 함수 (필요시 향후 사용)
CREATE OR REPLACE FUNCTION next_so_number(prefix TEXT DEFAULT 'SO')
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    yyyymm  TEXT;
    seq     INTEGER;
    new_no  TEXT;
    full_prefix TEXT;
BEGIN
    yyyymm := to_char(CURRENT_DATE, 'YYYYMM');
    full_prefix := prefix || '-' || yyyymm || '-';

    PERFORM pg_advisory_xact_lock(hashtext('so_' || yyyymm));

    SELECT COALESCE(
        MAX(
            CASE
                WHEN so_number ~ ('^' || prefix || '-' || yyyymm || '-[0-9]+$')
                THEN CAST(SUBSTRING(so_number FROM length(full_prefix)+1) AS INTEGER)
                ELSE 0
            END
        ),
        0
    ) + 1
    INTO seq
    FROM sales_orders
    WHERE so_number LIKE full_prefix || '%';

    new_no := full_prefix || lpad(seq::text, 3, '0');
    RETURN new_no;
END;
$$;
