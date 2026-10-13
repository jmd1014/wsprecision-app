-- ════════════════════════════════════════════════════════════
-- Migration 069: 출고 확정 트랜잭션 RPC confirm_shipment  (v3 — 2026-10-13 Data 리뷰 2차 반영: 키 누락·교차 soi 충당 거부)
-- (L3-S 계획서 docs/development/plans/20261012_L3S_출고확정RPC_채번RPC_오류기록.md A 항목)
-- ════════════════════════════════════════════════════════════
-- 문제:
--   출고 확정이 PostgREST 호출 6단계(수주 라인 → 회차 → 충당 → 재고 ISSUE →
--   수주 상태 → 전표 머리글)로 나뉘어 중간 실패 시 부분 반영이 남는다
--   (2026-10-08 SH-20261008-04: 머리글 CONFIRMED 저장만 실패 → 작성중 취소로 덮임).
-- 설계:
--   계산(회차 배분·LOT FIFO)은 앱이 하고, 이 함수는 payload 의 **증감값**을 검증한 뒤
--   한 트랜잭션으로 쓴다. 수주 라인 수량·상태, 수주 상태, 전표 confirmed_at 은 함수가
--   계산한다. 어느 검사든 실패하면 RAISE → 전부 롤백.
--   전표 라인(si)은 회차 단위라 같은 수주 라인(soi)에 si 가 여럿일 수 있다 → 수주 라인은
--   soi 로 합산해 한 번 갱신, 충당·ISSUE 는 si 별로 기록·검사한다.
--   payload (jsonb, 배열 키는 빼거나 [] — null 금지):
--   { "v": 1,
--     "allow_over": false,                                                    -- 완성 재고 부족 허용만
--     "lines":  [{"si_id", "soi_id", "qty", "expected_received_before"}],   -- qty = si.qty (깎지 않음)
--     "scheds": [{"sched_id", "soi_id", "delta"}],                           -- 회차 납품완료 증감(≥0)
--     "allocs": [{"si_id", "sched_id", "qty"}],                              -- 라인-회차 충당 기록
--     "txns":   [{"si_id", "product_id", "lot_number", "work_order", "qty"(음수),
--                 "unit", "txn_date", "remark", "created_by"}] }             -- 완성 재고 ISSUE
--   거부 사유(ERRCODE P0001, message):
--     bad_version · not_found · not_draft:<status> · already_applied · nothing_to_apply ·
--     line_missing · line_mismatch · stale · over_pending · sched_mismatch · sched_over ·
--     alloc_mismatch · txn_mismatch · stock:<product_id>
--   불변식: soi 별 Σ회차증감 ≤ Σ라인수량(회차 없음·다 참 허용) · 회차별 Σ충당 = 증감 ·
--           si 별 Σ충당 ≤ si.qty · 제품 연결 si 별 ΣISSUE = −si.qty(제품 일치) ·
--           제품 미연결 si 는 ISSUE 없음 · received+qty ≤ 수주량(과납 금지, 플래그 무관)
-- 잠금 순서: shipments → shipment_items(전표) → sales_order_items(soi 오름차순)
--           → so_delivery_schedule(sched 오름차순) → 제품 재고 advisory lock(product_id 오름차순)
-- 반환: {"ok": true, "lines": n(전표 라인 수), "sois": n, "allocs": n, "txns": n,
--        "skipped": [si_id…](수주 미연결 라인), "unallocated": [{soi_id, qty}](회차에 못 실은 수량),
--        "confirmed_at": ts}  — NULL 반환 없음
-- 보안: SECURITY INVOKER + search_path 고정, anon/authenticated 실행 차단, service_role 은
--       BYPASSRLS(2026-10-13 확인).
-- 되돌리기: DROP FUNCTION IF EXISTS public.confirm_shipment(integer, jsonb);
--   (함수가 쓴 행은 기존 경로와 같은 형식 — 데이터 되돌리기 불필요, 취소는 앱의
--    '확정 전표 전체 취소' 로)
-- 검증 호출(not_found / bad_version / not_draft:CONFIRMED)은 이 파일에 넣지 않는다 —
--   한 트랜잭션에서 예외가 migration 을 실패시킨다. execute_sql 로 따로.
-- ════════════════════════════════════════════════════════════

DROP FUNCTION IF EXISTS public.confirm_shipment(integer, jsonb);

CREATE FUNCTION public.confirm_shipment(p_shipment_id integer, p_payload jsonb)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_status      text;
    v_lines       jsonb;
    v_scheds      jsonb;
    v_allocs      jsonb;
    v_txns        jsonb;
    v_sched       jsonb;
    v_alloc       jsonb;
    v_txn         jsonb;
    v_soi         integer;
    v_qty         numeric;
    v_exp         numeric;
    v_nexp        integer;
    v_ordered     numeric;
    v_recv        numeric;
    v_new_recv    numeric;
    v_new_pend    numeric;
    v_new_status  text;
    v_sum         numeric;
    v_issue       numeric;
    v_n_sois      integer := 0;
    v_n_allocs    integer := 0;
    v_n_txns      integer := 0;
    v_now         timestamptz := now();
    v_skipped     integer[] := '{}';
    v_pid         text;
    v_stock       numeric;
    v_allow_over  boolean;
    v_unalloc     jsonb := '[]'::jsonb;
BEGIN
    -- 0. 형식
    IF p_payload IS NULL OR (p_payload->>'v') IS DISTINCT FROM '1' THEN
        RAISE EXCEPTION 'bad_version' USING ERRCODE = 'P0001';
    END IF;
    v_lines  := COALESCE(p_payload->'lines',  '[]'::jsonb);
    v_scheds := COALESCE(p_payload->'scheds', '[]'::jsonb);
    v_allocs := COALESCE(p_payload->'allocs', '[]'::jsonb);
    v_txns   := COALESCE(p_payload->'txns',   '[]'::jsonb);
    IF jsonb_typeof(v_lines) <> 'array' OR jsonb_typeof(v_scheds) <> 'array'
       OR jsonb_typeof(v_allocs) <> 'array' OR jsonb_typeof(v_txns) <> 'array' THEN
        RAISE EXCEPTION 'bad_version' USING ERRCODE = 'P0001', HINT = 'arrays';
    END IF;
    v_allow_over := COALESCE((p_payload->>'allow_over')::boolean, false);

    -- ⓐ 전표 잠금 + 상태, 전표 라인 잠금(동시 쓰기 직렬화 — '정정 저장' 자체를 막지는 못하므로 앱이 상태 재확인)
    SELECT status INTO v_status FROM shipments WHERE shipment_id = p_shipment_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'not_found' USING ERRCODE = 'P0001';
    END IF;
    IF v_status IS DISTINCT FROM 'DRAFT' THEN
        RAISE EXCEPTION 'not_draft:%', v_status USING ERRCODE = 'P0001';
    END IF;
    PERFORM 1 FROM shipment_items WHERE shipment_id = p_shipment_id FOR UPDATE;

    -- ⓑ 흔적: 충당 존재 또는 ISSUE 순합 ≠ 0 (앱 _cf_draft_applied 와 같은 기준)
    IF EXISTS (SELECT 1 FROM shipment_allocations a
                 JOIN shipment_items si ON si.si_id = a.si_id
                WHERE si.shipment_id = p_shipment_id) THEN
        RAISE EXCEPTION 'already_applied' USING ERRCODE = 'P0001';
    END IF;
    IF EXISTS (SELECT 1 FROM inventory_transactions t
                 JOIN shipment_items si ON si.si_id = t.ref_id
                WHERE t.ref_table = 'shipment_items' AND t.txn_type = 'ISSUE'
                  AND si.shipment_id = p_shipment_id
                GROUP BY si.si_id HAVING SUM(t.qty) <> 0) THEN
        RAISE EXCEPTION 'already_applied' USING ERRCODE = 'P0001';
    END IF;

    -- ⓓ-1 라인 집합: 전표의 qty>0·수주 연결 라인은 모두 payload 에, payload 라인은 모두
    --     이 전표 소속·soi·qty 일치·중복 없음. 수주 미연결 라인은 건너뜀(현행과 같음).
    SELECT COALESCE(array_agg(si.si_id ORDER BY si.si_id), '{}') INTO v_skipped
      FROM shipment_items si
     WHERE si.shipment_id = p_shipment_id AND si.qty > 0 AND si.soi_id IS NULL;

    IF jsonb_array_length(v_lines) = 0 THEN
        RAISE EXCEPTION 'nothing_to_apply' USING ERRCODE = 'P0001';
    END IF;
    IF (SELECT count(*) <> count(DISTINCT (l->>'si_id')::integer)
          FROM jsonb_array_elements(v_lines) l) THEN
        RAISE EXCEPTION 'line_mismatch' USING ERRCODE = 'P0001', HINT = 'duplicate si';
    END IF;
    IF EXISTS (SELECT 1 FROM jsonb_array_elements(v_lines) l
                 LEFT JOIN shipment_items si ON si.si_id = (l->>'si_id')::integer
                WHERE si.si_id IS NULL OR si.shipment_id <> p_shipment_id
                   OR si.soi_id IS NULL
                   OR si.soi_id IS DISTINCT FROM (l->>'soi_id')::integer
                   OR (l->>'qty')::numeric IS NULL OR (l->>'qty')::numeric <= 0
                   OR (l->>'qty')::numeric IS DISTINCT FROM si.qty
                   OR (l->>'expected_received_before')::numeric IS NULL) THEN
        RAISE EXCEPTION 'line_mismatch' USING ERRCODE = 'P0001';
    END IF;
    IF EXISTS (SELECT si.si_id FROM shipment_items si
                WHERE si.shipment_id = p_shipment_id AND si.qty > 0 AND si.soi_id IS NOT NULL
               EXCEPT
               SELECT (l->>'si_id')::integer FROM jsonb_array_elements(v_lines) l) THEN
        RAISE EXCEPTION 'line_missing' USING ERRCODE = 'P0001';
    END IF;

    -- ⓓ-2 회차: 존재·soi 일치·delta ≥ 0·soi 는 lines 안
    IF EXISTS (SELECT 1 FROM jsonb_array_elements(v_scheds) s
                 LEFT JOIN so_delivery_schedule d ON d.sched_id = (s->>'sched_id')::integer
                WHERE d.sched_id IS NULL
                   OR (s->>'soi_id') IS NULL
                   OR d.soi_id IS DISTINCT FROM (s->>'soi_id')::integer
                   OR (s->>'delta')::numeric IS NULL OR (s->>'delta')::numeric < 0
                   OR (s->>'soi_id')::integer NOT IN (
                        SELECT (l->>'soi_id')::integer FROM jsonb_array_elements(v_lines) l)) THEN
        RAISE EXCEPTION 'sched_mismatch' USING ERRCODE = 'P0001';
    END IF;
    -- ⓓ-3 충당: si 는 lines 안·qty > 0, 회차별 Σ충당 = 증감, si 별 Σ충당 ≤ si.qty
    IF EXISTS (SELECT 1 FROM jsonb_array_elements(v_allocs) a
                WHERE (a->>'qty')::numeric IS NULL OR (a->>'qty')::numeric <= 0
                   OR (a->>'si_id') IS NULL OR (a->>'sched_id') IS NULL
                   OR (a->>'si_id')::integer NOT IN (
                        SELECT (l->>'si_id')::integer FROM jsonb_array_elements(v_lines) l)) THEN
        RAISE EXCEPTION 'alloc_mismatch' USING ERRCODE = 'P0001';
    END IF;
    -- M-2 교차 수주 라인 충당 금지: 충당의 회차는 그 전표 라인의 수주 라인에 속해야
    IF EXISTS (SELECT 1 FROM jsonb_array_elements(v_allocs) a
                 JOIN shipment_items si ON si.si_id = (a->>'si_id')::integer
                 LEFT JOIN so_delivery_schedule d ON d.sched_id = (a->>'sched_id')::integer
                WHERE d.sched_id IS NULL OR d.soi_id IS DISTINCT FROM si.soi_id) THEN
        RAISE EXCEPTION 'alloc_mismatch' USING ERRCODE = 'P0001', HINT = 'sched not of line soi';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM (SELECT (s->>'sched_id')::integer AS sched_id, SUM((s->>'delta')::numeric) AS d
                  FROM jsonb_array_elements(v_scheds) s GROUP BY 1) sd
          FULL JOIN (SELECT (a->>'sched_id')::integer AS sched_id, SUM((a->>'qty')::numeric) AS q
                  FROM jsonb_array_elements(v_allocs) a GROUP BY 1) ad
            USING (sched_id)
         WHERE abs(COALESCE(sd.d, 0) - COALESCE(ad.q, 0)) > 1e-9) THEN
        RAISE EXCEPTION 'alloc_mismatch' USING ERRCODE = 'P0001', HINT = 'per sched';
    END IF;
    IF EXISTS (SELECT 1 FROM jsonb_array_elements(v_lines) l
                WHERE (SELECT COALESCE(SUM((a->>'qty')::numeric), 0)
                         FROM jsonb_array_elements(v_allocs) a
                        WHERE (a->>'si_id')::integer = (l->>'si_id')::integer)
                      > (l->>'qty')::numeric + 1e-9) THEN
        RAISE EXCEPTION 'alloc_mismatch' USING ERRCODE = 'P0001', HINT = 'si over qty';
    END IF;
    -- ⓓ-4 ISSUE: si 는 lines 안, 제품 연결 si 는 Σqty = −si.qty 이고 product_id 일치,
    --     제품 미연결 si 는 ISSUE 없음, qty < 0
    IF EXISTS (SELECT 1 FROM jsonb_array_elements(v_txns) t
                WHERE (t->>'si_id') IS NULL
                   OR (t->>'si_id')::integer NOT IN (
                        SELECT (l->>'si_id')::integer FROM jsonb_array_elements(v_lines) l)) THEN
        RAISE EXCEPTION 'txn_mismatch' USING ERRCODE = 'P0001', HINT = 'si not in lines';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM jsonb_array_elements(v_lines) l
          JOIN shipment_items si ON si.si_id = (l->>'si_id')::integer
          LEFT JOIN LATERAL (
              SELECT COALESCE(SUM((t->>'qty')::numeric), 0) AS q,
                     bool_or((t->>'product_id') IS DISTINCT FROM si.product_id) AS bad_pid,
                     bool_or((t->>'qty') IS NULL OR (t->>'qty')::numeric >= 0) AS bad_qty
                FROM jsonb_array_elements(v_txns) t
               WHERE (t->>'si_id')::integer = si.si_id) tx ON true
         WHERE COALESCE(tx.bad_pid, false) OR COALESCE(tx.bad_qty, false)
            OR (si.product_id IS NOT NULL AND abs(COALESCE(tx.q, 0) + (l->>'qty')::numeric) > 1e-9)
            OR (si.product_id IS NULL     AND COALESCE(tx.q, 0) <> 0)) THEN
        RAISE EXCEPTION 'txn_mismatch' USING ERRCODE = 'P0001';
    END IF;

    -- ⓒ 수주 라인: soi 단위로 합산해 한 번만 잠금(soi 오름차순)·검사·갱신
    FOR v_soi, v_qty, v_exp, v_nexp IN
        SELECT (l->>'soi_id')::integer,
               SUM((l->>'qty')::numeric),
               MIN((l->>'expected_received_before')::numeric),
               COUNT(DISTINCT (l->>'expected_received_before')::numeric)
          FROM jsonb_array_elements(v_lines) l
         GROUP BY 1 ORDER BY 1
    LOOP
        IF v_nexp > 1 THEN
            RAISE EXCEPTION 'stale' USING ERRCODE = 'P0001',
                HINT = format('soi %s: expected_received_before differs across lines', v_soi);
        END IF;
        SELECT COALESCE(qty, 0), COALESCE(received_qty, 0)
          INTO v_ordered, v_recv
          FROM sales_order_items WHERE soi_id = v_soi FOR UPDATE;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'line_mismatch' USING ERRCODE = 'P0001', HINT = 'soi';
        END IF;
        IF v_recv <> v_exp THEN
            RAISE EXCEPTION 'stale' USING ERRCODE = 'P0001',
                HINT = format('soi %s: received %s ≠ expected %s', v_soi, v_recv, v_exp);
        END IF;
        IF v_recv + v_qty > v_ordered + 1e-9 THEN       -- 과납 금지 (플래그 무관)
            RAISE EXCEPTION 'over_pending' USING ERRCODE = 'P0001',
                HINT = format('soi %s: %s + %s > %s', v_soi, v_recv, v_qty, v_ordered);
        END IF;
        SELECT COALESCE(SUM((s->>'delta')::numeric), 0) INTO v_sum
          FROM jsonb_array_elements(v_scheds) s
         WHERE (s->>'soi_id')::integer = v_soi;
        IF v_sum > v_qty + 1e-9 THEN                     -- 회차 없음·다 참(0) 허용
            RAISE EXCEPTION 'sched_mismatch' USING ERRCODE = 'P0001',
                HINT = format('soi %s sum %s > qty %s', v_soi, v_sum, v_qty);
        END IF;
        IF v_sum < v_qty - 1e-9 THEN                     -- 회차에 못 실은 수량은 알린다
            v_unalloc := v_unalloc || jsonb_build_object('soi_id', v_soi, 'qty', v_qty - v_sum);
        END IF;

        v_new_recv   := v_recv + v_qty;
        v_new_pend   := GREATEST(v_ordered - v_new_recv, 0);
        v_new_status := CASE WHEN v_new_recv >= v_ordered THEN 'DELIVERED'
                             WHEN v_new_recv > 0 THEN 'PARTIAL'
                             ELSE 'PENDING' END;
        UPDATE sales_order_items
           SET received_qty = v_new_recv, pending_qty = v_new_pend, status = v_new_status
         WHERE soi_id = v_soi;
        v_n_sois := v_n_sois + 1;
    END LOOP;

    -- ⓔ-1 회차 납품완료 += delta (sched 오름차순 잠금), 회차 수량 초과 금지
    FOR v_sched IN
        SELECT s FROM jsonb_array_elements(v_scheds) s
         ORDER BY (s->>'sched_id')::integer
    LOOP
        IF (v_sched->>'delta')::numeric = 0 THEN
            CONTINUE;
        END IF;
        PERFORM 1 FROM so_delivery_schedule WHERE sched_id = (v_sched->>'sched_id')::integer FOR UPDATE;
        UPDATE so_delivery_schedule
           SET delivered_qty = COALESCE(delivered_qty, 0) + (v_sched->>'delta')::numeric,
               updated_at = v_now
         WHERE sched_id = (v_sched->>'sched_id')::integer
           AND COALESCE(delivered_qty, 0) + (v_sched->>'delta')::numeric <= COALESCE(qty, 0) + 1e-9;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'sched_over' USING ERRCODE = 'P0001', HINT = format('sched %s', v_sched->>'sched_id');
        END IF;
    END LOOP;

    -- ⓔ-2 충당 기록
    FOR v_alloc IN SELECT a FROM jsonb_array_elements(v_allocs) a LOOP
        INSERT INTO shipment_allocations (si_id, sched_id, qty)
        VALUES ((v_alloc->>'si_id')::integer, (v_alloc->>'sched_id')::integer, (v_alloc->>'qty')::numeric);
        v_n_allocs := v_n_allocs + 1;
    END LOOP;

    -- ⓔ-3 완성 재고 ISSUE — allow_over=false 면 제품별 현재고 검사(제품별 advisory lock 으로
    --     동시 확정의 이중 차감 방지, product_id 오름차순)
    IF NOT v_allow_over THEN
        FOR v_pid, v_issue IN
            SELECT t->>'product_id', -SUM((t->>'qty')::numeric)
              FROM jsonb_array_elements(v_txns) t
             GROUP BY 1 ORDER BY 1
        LOOP
            PERFORM pg_advisory_xact_lock(hashtext('product_stock'), hashtext(v_pid));
            SELECT COALESCE(current_stock, 0) INTO v_stock FROM product_stock_v WHERE product_id = v_pid;
            IF COALESCE(v_stock, 0) + 1e-9 < v_issue THEN
                RAISE EXCEPTION 'stock:%', v_pid USING ERRCODE = 'P0001',
                    HINT = format('stock %s < issue %s', COALESCE(v_stock, 0), v_issue);
            END IF;
        END LOOP;
    END IF;
    FOR v_txn IN SELECT t FROM jsonb_array_elements(v_txns) t LOOP
        INSERT INTO inventory_transactions
            (material_id, product_id, txn_type, qty, unit, lot_number, work_order,
             ref_table, ref_id, txn_date, remark, created_by)
        VALUES (NULL, v_txn->>'product_id', 'ISSUE', (v_txn->>'qty')::numeric,
                COALESCE(v_txn->>'unit', 'EA'), v_txn->>'lot_number', v_txn->>'work_order',
                'shipment_items', (v_txn->>'si_id')::integer,
                COALESCE(NULLIF(v_txn->>'txn_date', 'None')::date, CURRENT_DATE),
                v_txn->>'remark', v_txn->>'created_by');
        v_n_txns := v_n_txns + 1;
    END LOOP;

    -- ⓔ-4 수주 머리글 상태 — 라인 재집계 (현행 규칙, 대상은 수주 라인의 so_id)
    UPDATE sales_orders o
       SET status = sub.st
      FROM (SELECT i.so_id,
                   CASE WHEN bool_and(COALESCE(i.received_qty, 0) >= COALESCE(i.qty, 0)) THEN 'DELIVERED'
                        WHEN bool_or(COALESCE(i.received_qty, 0) > 0) THEN 'PARTIAL'
                        ELSE 'CONFIRMED' END AS st
              FROM sales_order_items i
             WHERE i.so_id IN (SELECT DISTINCT i2.so_id FROM sales_order_items i2
                                WHERE i2.soi_id IN (SELECT (l->>'soi_id')::integer
                                                      FROM jsonb_array_elements(v_lines) l))
             GROUP BY i.so_id) sub
     WHERE o.so_id = sub.so_id;

    -- ⓔ-5 전표 머리글 (ⓐ 의 잠금으로 상태는 바뀔 수 없음 — 방어용 조건)
    UPDATE shipments SET status = 'CONFIRMED', confirmed_at = v_now
     WHERE shipment_id = p_shipment_id AND status = 'DRAFT';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'not_draft:changed' USING ERRCODE = 'P0001';
    END IF;

    RETURN jsonb_build_object(
        'ok', true, 'lines', jsonb_array_length(v_lines), 'sois', v_n_sois,
        'allocs', v_n_allocs, 'txns', v_n_txns,
        'skipped', to_jsonb(v_skipped), 'unallocated', v_unalloc,
        'confirmed_at', v_now);
END;
$$;

COMMENT ON FUNCTION public.confirm_shipment(integer, jsonb) IS
    '출고 확정을 한 트랜잭션으로: payload(증감값) 검증 → 수주 라인(soi 합산)·회차·충당·ISSUE·수주 상태·전표 CONFIRMED. 실패 시 전부 롤백(P0001 사유).';

REVOKE EXECUTE ON FUNCTION public.confirm_shipment(integer, jsonb) FROM PUBLIC, anon, authenticated;
GRANT  EXECUTE ON FUNCTION public.confirm_shipment(integer, jsonb) TO service_role;
