-- ════════════════════════════════════════════════════════════
-- Migration 076: 수주 종결·되돌리기 RPC 원자화 + 비활성 라인 규칙 (2026-10-22, 수주 상태 정리 r2)
-- 기준: _수주상태_r1리뷰_분류_및_수정지시문_20261022.md §2 D9~D14, F1·F2·F3b·F11
-- ════════════════════════════════════════════════════════════
-- 문제(r1 리뷰): 종결이 파이썬 요청 N개(라인·회차·머리글)로 쪼개져 중간 실패·경합·스냅샷 지연에 취약했고,
--   출고 정정·머리글 계산·집계 뷰가 비활성 라인(CLOSED·CANCELLED·REPLACED)을 몰라 잔량이 되살아나거나
--   목록 미납에 다시 잡혔다(REPLACED 는 이미 부풀어 있었음: so 40·53·58 등).
-- 설계:
--   D9  so_close_lines / so_reopen_lines — 한 트랜잭션(머리글 FOR UPDATE → 라인 FOR UPDATE soi 오름차순),
--       서버 값으로 계산, 멱등(두 번째 호출은 남은 일만: 머리글 마무리·거울상 재계산).
--   D10 잔량의 진실 = 라인 status + 저장된 pending_qty + closed_qty. 뷰·집계는 qty−received 를 쓰지 않는다(006 폐기).
--   D11 비활성 라인 집합 = {CLOSED, CANCELLED, REPLACED}: 뷰·069·머리글 계산 모두 제외. 머리글이 비활성이면 재계산 없음.
--   D12 종결 때 닫은 회차를 라인 closed_rounds jsonb [{sched_id, qty_before, delivered}] 에 보존 →
--       되돌리기에서 delivered_qty 가 그대로인 회차만 qty 복원, 아니면 rounds_skipped 로 보고.
--   D13 069 confirm_shipment 전문 재선언: 비활성 라인 → RAISE 'line_closed'; ⓔ-4 머리글은 활성 라인만·폴백 DRAFT.
--   D14 sales_orders.status·sales_order_items.status SET NOT NULL(사전 확인 NULL 0행), CHECK (closed_qty >= 0).
-- 거부 사유(ERRCODE P0001, message): bad_args · not_found · blocked(HINT = 미확정 전표 번호 목록) · line_closed(HINT = soi)
-- 반환: so_close_lines {closed, rounds, header(boolean), header_status} /
--       so_reopen_lines {reopened, rounds_restored, rounds_skipped, header(text|null), header_status}
-- 보안: SECURITY INVOKER + search_path 고정, anon/authenticated 실행 차단, service_role 만(069 와 동일).
-- 뷰: WITH (security_invoker = true) (034 규칙), 자기 참조 없이 본문 전부 명시(047 사고).
-- 멱등: CREATE OR REPLACE / DROP IF EXISTS → ADD / ADD COLUMN IF NOT EXISTS.
-- 되돌리기(075·076 공통, 08_migration_verify.md F10 — Data 리뷰 H1 반영 순서):
--   사전 조건 — closed_qty<>0 0행 ∧ 라인·머리글 CLOSED 0 ∧ 신루틴 CANCELLED(close_reason not null) 0 ∧ closed_rounds not null 0.
--   순서(한 트랜잭션) — ① 앱을 acab4c9 로 되돌린 뒤 ② chk_so_status·chk_soi_status 를 004(+REPLACED) 로 재선언
--   (CLOSED 행이 남아 있으면 여기서 안전하게 실패) ③ DROP FUNCTION so_close_lines·so_reopen_lines,
--   confirm_shipment 은 069 본문으로 재선언 ④ 두 뷰는 CREATE OR REPLACE 로 열을 뺄 수 없으므로
--   DROP VIEW sales_order_stats, sales_order_items_v → 006 본문 + WITH (security_invoker = true) 로 CREATE
--   (의존 뷰 없음 확인 2026-10-22 Q1) ⑤ 그 다음에야 closed_qty·close_reason·closed_rounds DROP COLUMN
--   (뷰가 참조하는 동안은 DROP 거부) ⑥ 선택: status DROP NOT NULL(기본값 DRAFT/PENDING 이 있어 Old App 무해).
-- ════════════════════════════════════════════════════════════

-- ── D14·D12 열·제약 ──
ALTER TABLE public.sales_order_items ADD COLUMN IF NOT EXISTS closed_rounds jsonb;
COMMENT ON COLUMN public.sales_order_items.closed_rounds IS '종결·취소 때 닫은 납품 회차 [{sched_id, qty_before, delivered}] — 되돌리기 복원용. NULL = 닫은 적 없음(활성), [] = 닫을 때 열린 회차가 없었음 (076 D12)';
ALTER TABLE public.sales_order_items DROP CONSTRAINT IF EXISTS chk_soi_closed_qty;
ALTER TABLE public.sales_order_items ADD CONSTRAINT chk_soi_closed_qty CHECK (closed_qty >= 0);
ALTER TABLE public.sales_orders      ALTER COLUMN status SET NOT NULL;
ALTER TABLE public.sales_order_items ALTER COLUMN status SET NOT NULL;

-- ── F1 so_close_lines ──
CREATE OR REPLACE FUNCTION public.so_close_lines(p_so_id integer, p_mode text, p_reason text, p_who text)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_hdr_status   text;
    v_hdr_remark   text;
    v_blocked      text;
    v_tag          text;
    v_reason       text := btrim(COALESCE(p_reason, ''));
    v_closed       integer := 0;
    v_rounds       integer := 0;
    v_n            integer;
    v_header       boolean := false;
    v_active_pend  numeric;
    v_has_closed   boolean;
    v_mode_mix     boolean;
    v_rounds_json  jsonb;
    r              record;
BEGIN
    IF p_mode IS NULL OR p_mode NOT IN ('CLOSED', 'CANCELLED') OR v_reason = '' THEN
        RAISE EXCEPTION 'bad_args' USING ERRCODE = 'P0001', HINT = 'mode CLOSED|CANCELLED, reason required';
    END IF;
    -- 잠금 순서 = 069 와 동일(라인 soi 오름차순 → 머리글) — confirm_shipment 와 교착 방지 (Data 리뷰 M1)
    PERFORM 1 FROM sales_order_items WHERE so_id = p_so_id ORDER BY soi_id FOR UPDATE;
    SELECT status, remark INTO v_hdr_status, v_hdr_remark FROM sales_orders WHERE so_id = p_so_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'not_found' USING ERRCODE = 'P0001';
    END IF;

    -- 미확정(DRAFT) 출고 전표가 미납 라인을 참조하면 차단 — 같은 트랜잭션에서 검사(TOCTOU 없음)
    SELECT string_agg(DISTINCT s.ship_no, ', ' ORDER BY s.ship_no) INTO v_blocked
      FROM shipment_items si
      JOIN shipments s ON s.shipment_id = si.shipment_id
      JOIN sales_order_items i ON i.soi_id = si.soi_id
     WHERE i.so_id = p_so_id AND COALESCE(i.pending_qty, 0) > 0 AND s.status = 'DRAFT';
    IF v_blocked IS NOT NULL THEN
        RAISE EXCEPTION 'blocked' USING ERRCODE = 'P0001', HINT = v_blocked;
    END IF;

    v_tag := format('%s(%s) %s %s',
                    CASE p_mode WHEN 'CLOSED' THEN '종결' ELSE '취소' END, v_reason,
                    to_char(now() AT TIME ZONE 'Asia/Seoul', 'YYYY-MM-DD'),
                    COALESCE(NULLIF(btrim(COALESCE(p_who, '')), ''), '-'));

    -- 미납 라인(활성 상태만): 잔량 보존 → pending 0 → 상태 → 회차 보존·닫기
    FOR r IN
        SELECT soi_id FROM sales_order_items
         WHERE so_id = p_so_id AND COALESCE(pending_qty, 0) > 0
           AND status NOT IN ('CLOSED', 'CANCELLED', 'REPLACED')
         ORDER BY soi_id
    LOOP
        SELECT COALESCE(jsonb_agg(jsonb_build_object('sched_id', d.sched_id, 'qty_before', COALESCE(d.qty, 0),
                                                     'delivered', COALESCE(d.delivered_qty, 0))
                                  ORDER BY d.sched_id), '[]'::jsonb)
          INTO v_rounds_json
          FROM so_delivery_schedule d
         WHERE d.soi_id = r.soi_id AND COALESCE(d.qty, 0) > COALESCE(d.delivered_qty, 0) + 1e-9;
        UPDATE sales_order_items
           SET closed_qty = pending_qty, pending_qty = 0, status = p_mode, close_reason = v_reason,
               closed_rounds = v_rounds_json,
               remark = CASE WHEN COALESCE(btrim(remark), '') = '' THEN v_tag ELSE remark || ' · ' || v_tag END
         WHERE soi_id = r.soi_id;
        UPDATE so_delivery_schedule
           SET qty = COALESCE(delivered_qty, 0), updated_at = now()
         WHERE soi_id = r.soi_id AND COALESCE(qty, 0) > COALESCE(delivered_qty, 0) + 1e-9;
        GET DIAGNOSTICS v_n = ROW_COUNT;
        v_rounds := v_rounds + v_n;
        v_closed := v_closed + 1;
    END LOOP;

    -- 머리글: 활성 라인 잔량 합 0 이고 (이번에 닫았거나, 닫힌 라인만 남은 채 머리글이 아직 활성이면 마무리).
    -- 마무리(v_closed = 0)는 남은 닫힌 라인의 상태와 p_mode 가 같을 때만 — CLOSED 라인에 CANCELLED 머리글 혼재 금지 (QA M-2)
    SELECT COALESCE(SUM(CASE WHEN status IN ('CLOSED', 'CANCELLED', 'REPLACED') THEN 0
                             ELSE COALESCE(pending_qty, 0) END), 0),
           COALESCE(bool_or(status IN ('CLOSED', 'CANCELLED')), false),
           COALESCE(bool_or(status IN ('CLOSED', 'CANCELLED') AND status <> p_mode), false)
      INTO v_active_pend, v_has_closed, v_mode_mix
      FROM sales_order_items WHERE so_id = p_so_id;
    IF v_closed = 0 AND v_has_closed AND v_hdr_status NOT IN ('CLOSED', 'CANCELLED') AND v_mode_mix THEN
        RAISE EXCEPTION 'bad_args' USING ERRCODE = 'P0001', HINT = 'mode mismatch: closed lines have another mode';
    END IF;
    IF v_active_pend <= 1e-9
       AND (v_closed > 0 OR (v_has_closed AND v_hdr_status NOT IN ('CLOSED', 'CANCELLED'))) THEN
        UPDATE sales_orders
           SET status = p_mode, updated_at = now(),
               remark = CASE WHEN COALESCE(btrim(v_hdr_remark), '') = '' THEN v_tag
                             ELSE v_hdr_remark || ' · ' || v_tag END
         WHERE so_id = p_so_id;
        v_header := true;
        v_hdr_status := p_mode;
    END IF;

    RETURN jsonb_build_object('closed', v_closed, 'rounds', v_rounds, 'header', v_header,
                              'header_status', v_hdr_status);
END;
$$;
COMMENT ON FUNCTION public.so_close_lines(integer, text, text, text) IS
  '수주 종결(CLOSED)·취소(CANCELLED)를 한 트랜잭션으로: 미확정 전표 차단 → 활성 미납 라인 closed_qty 보존·pending 0·회차 보존(closed_rounds)·닫기 → 활성 잔량 0 이면 머리글. 멱등. 거부 bad_args/not_found/blocked(HINT 전표) (076)';
REVOKE EXECUTE ON FUNCTION public.so_close_lines(integer, text, text, text) FROM PUBLIC, anon, authenticated;
GRANT  EXECUTE ON FUNCTION public.so_close_lines(integer, text, text, text) TO service_role;

-- ── F1 so_reopen_lines ──
CREATE OR REPLACE FUNCTION public.so_reopen_lines(p_so_id integer, p_who text)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_hdr_status  text;
    v_hdr_remark  text;
    v_tag         text;
    v_reopened    integer := 0;
    v_restored    integer := 0;
    v_skipped     integer := 0;
    v_new         text;
    v_header      text := NULL;
    v_left        boolean;
    v_active_open boolean;
    r             record;
    cr            jsonb;
BEGIN
    PERFORM 1 FROM sales_order_items WHERE so_id = p_so_id ORDER BY soi_id FOR UPDATE;   -- 069 와 같은 순서
    SELECT status, remark INTO v_hdr_status, v_hdr_remark FROM sales_orders WHERE so_id = p_so_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'not_found' USING ERRCODE = 'P0001';
    END IF;
    v_tag := format('되돌림 %s %s', to_char(now() AT TIME ZONE 'Asia/Seoul', 'YYYY-MM-DD'),
                    COALESCE(NULLIF(btrim(COALESCE(p_who, '')), ''), '-'));

    FOR r IN
        SELECT soi_id, closed_qty, COALESCE(received_qty, 0) AS received_qty, COALESCE(closed_rounds, '[]'::jsonb) AS closed_rounds
          FROM sales_order_items
         WHERE so_id = p_so_id AND closed_qty > 0 AND status IN ('CLOSED', 'CANCELLED')
         ORDER BY soi_id
    LOOP
        UPDATE sales_order_items
           SET pending_qty = closed_qty, closed_qty = 0,
               status = CASE WHEN r.received_qty > 0 THEN 'PARTIAL' ELSE 'PENDING' END,
               close_reason = NULL, closed_rounds = NULL,
               remark = CASE WHEN COALESCE(btrim(remark), '') = '' THEN v_tag ELSE remark || ' · ' || v_tag END
         WHERE soi_id = r.soi_id;
        -- D12 회차 복원: 아직 닫힌 상태(qty = delivered_qty)인 회차만 qty_before 로 되돌린다
        -- (종결 뒤 출고 정정이 delivered 를 바꿔도 정정 루틴이 qty 를 같이 내려 닫힌 상태를 유지하므로 복원 가능 — QA H-2)
        IF jsonb_typeof(r.closed_rounds) = 'array' THEN
            FOR cr IN SELECT x FROM jsonb_array_elements(r.closed_rounds) x LOOP
                UPDATE so_delivery_schedule
                   SET qty = GREATEST((cr->>'qty_before')::numeric, COALESCE(delivered_qty, 0)), updated_at = now()
                 WHERE sched_id = (cr->>'sched_id')::integer
                   AND soi_id = r.soi_id
                   AND abs(COALESCE(qty, 0) - COALESCE(delivered_qty, 0)) <= 1e-9;
                IF FOUND THEN
                    v_restored := v_restored + 1;
                ELSE
                    v_skipped := v_skipped + 1;
                END IF;
            END LOOP;
        END IF;
        v_reopened := v_reopened + 1;
    END LOOP;

    -- 머리글 재계산: 되돌린 라인이 있거나, 거울상 복구 = 머리글이 비활성인데 보존 잔량 라인은 없고
    -- 활성 미납 라인(pending > 0)이 남아 있을 때만(불변식 ③ 위반) — 정당한 취소·대체 수주는 건드리지 않는다 (QA H-1)
    SELECT EXISTS (SELECT 1 FROM sales_order_items WHERE so_id = p_so_id AND closed_qty > 0) INTO v_left;
    SELECT EXISTS (SELECT 1 FROM sales_order_items WHERE so_id = p_so_id
                     AND status NOT IN ('CLOSED', 'CANCELLED', 'REPLACED') AND COALESCE(pending_qty, 0) > 0)
      INTO v_active_open;
    IF v_reopened > 0 OR (v_hdr_status IN ('CLOSED', 'CANCELLED') AND NOT v_left AND v_active_open) THEN
        SELECT CASE WHEN count(*) = 0 THEN v_hdr_status
                    WHEN bool_and(COALESCE(received_qty, 0) >= COALESCE(qty, 0)) THEN 'DELIVERED'
                    WHEN bool_or(COALESCE(received_qty, 0) > 0) THEN 'PARTIAL'
                    ELSE 'DRAFT' END
          INTO v_new
          FROM sales_order_items
         WHERE so_id = p_so_id AND status NOT IN ('CLOSED', 'CANCELLED', 'REPLACED');
        IF v_new IS DISTINCT FROM v_hdr_status OR v_reopened > 0 THEN
            UPDATE sales_orders
               SET status = v_new, updated_at = now(),
                   remark = CASE WHEN v_reopened = 0 THEN remark
                                 WHEN COALESCE(btrim(v_hdr_remark), '') = '' THEN v_tag
                                 ELSE v_hdr_remark || ' · ' || v_tag END
             WHERE so_id = p_so_id;
        END IF;
        v_header := v_new;
        v_hdr_status := v_new;
    END IF;

    RETURN jsonb_build_object('reopened', v_reopened, 'rounds_restored', v_restored,
                              'rounds_skipped', v_skipped, 'header', v_header,
                              'header_status', v_hdr_status);
END;
$$;
COMMENT ON FUNCTION public.so_reopen_lines(integer, text) IS
  '종결·취소 되돌리기를 한 트랜잭션으로: closed_qty → pending, 라인 상태 재계산, 보존 회차 복원(아직 닫힌 상태인 것만), 머리글 활성 라인 재계산(없으면 유지; 거울상 복구는 활성 미납 라인이 있을 때만). 멱등 (076)';
REVOKE EXECUTE ON FUNCTION public.so_reopen_lines(integer, text) FROM PUBLIC, anon, authenticated;
GRANT  EXECUTE ON FUNCTION public.so_reopen_lines(integer, text) TO service_role;

-- ── F2 뷰 재정의 (006 본문 전부 명시 + D10·D11) ──
CREATE OR REPLACE VIEW public.sales_order_items_v WITH (security_invoker = true) AS
SELECT
    soi.soi_id,
    soi.so_id,
    soi.line_no,
    soi.customer_part_no,
    soi.customer_item_name,
    soi.product_id,
    soi.canonical_pn,
    soi.qty,
    COALESCE(soi.received_qty, 0)                                               AS received_qty,
    CASE WHEN soi.status IN ('CLOSED', 'CANCELLED', 'REPLACED') THEN 0
         ELSE COALESCE(soi.pending_qty, 0) END                                   AS pending_qty_calc,
    CASE
        WHEN soi.status IN ('CLOSED', 'CANCELLED', 'REPLACED') THEN soi.status
        WHEN COALESCE(soi.received_qty, 0) = 0                  THEN 'PENDING'
        WHEN soi.received_qty >= soi.qty                        THEN 'DELIVERED'
        ELSE 'PARTIAL'
    END                                                                          AS computed_status,
    soi.unit,
    soi.unit_price,
    soi.amount,
    soi.vat,
    soi.total,
    soi.due_date,
    soi.customer_lot,
    soi.mes_work_order,
    soi.status                                                                   AS status_stored,
    soi.remark,
    soi.created_at,
    COALESCE(soi.closed_qty, 0)                                                  AS closed_qty,
    soi.close_reason
FROM sales_order_items soi;

CREATE OR REPLACE VIEW public.sales_order_stats WITH (security_invoker = true) AS
SELECT
    so.so_id,
    so.so_number,
    so.customer,
    so.so_date,
    so.due_date,
    so.status,
    so.total_amount,
    COUNT(soi.soi_id)                                                            AS item_count,
    SUM(soi.qty)                                                                 AS total_qty,
    SUM(COALESCE(soi.received_qty, 0))                                           AS total_received_qty,
    SUM(CASE WHEN soi.status IN ('CLOSED', 'CANCELLED', 'REPLACED') THEN 0
             ELSE COALESCE(soi.pending_qty, 0) END)                              AS total_pending_qty,
    CASE
        WHEN so.status = 'CLOSED'                                          THEN '종결'
        WHEN so.status = 'CANCELLED'                                       THEN '취소'
        WHEN SUM(COALESCE(soi.received_qty, 0)) = 0                        THEN '미납'
        WHEN SUM(CASE WHEN soi.status IN ('CLOSED', 'CANCELLED', 'REPLACED') THEN 0
                      ELSE COALESCE(soi.pending_qty, 0) END) = 0           THEN '완납'
        ELSE '부분납'
    END                                                                          AS delivery_status,
    ROUND(100.0 * COUNT(soi.product_id) / NULLIF(COUNT(soi.soi_id), 0), 1)      AS match_rate_pct,
    SUM(COALESCE(soi.closed_qty, 0))                                             AS total_closed_qty
FROM sales_orders so
LEFT JOIN sales_order_items soi ON soi.so_id = so.so_id
GROUP BY so.so_id;

-- ── F3b 069 confirm_shipment 전문 재선언 (v3 본문 + 두 곳: line_closed 거부, ⓔ-4 활성 라인만·폴백 DRAFT) ──
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
    v_lstatus     text;
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
        SELECT COALESCE(qty, 0), COALESCE(received_qty, 0), status
          INTO v_ordered, v_recv, v_lstatus
          FROM sales_order_items WHERE soi_id = v_soi FOR UPDATE;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'line_mismatch' USING ERRCODE = 'P0001', HINT = 'soi';
        END IF;
        IF v_lstatus IN ('CLOSED', 'CANCELLED', 'REPLACED') THEN      -- 076 D13: 비활성 라인은 출고 불가
            RAISE EXCEPTION 'line_closed' USING ERRCODE = 'P0001',
                HINT = format('soi %s: %s', v_soi, v_lstatus);
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

    -- ⓔ-4 수주 머리글 상태 — 활성 라인(CLOSED·CANCELLED·REPLACED 제외)만 재집계 (076 D11·D13):
    --     납품 0 은 DRAFT(접수, CONFIRMED 폐기), 활성 라인이 없으면 행이 안 나와 현 상태 유지,
    --     머리글이 비활성(CLOSED·CANCELLED)이면 건드리지 않는다
    UPDATE sales_orders o
       SET status = sub.st
      FROM (SELECT i.so_id,
                   CASE WHEN bool_and(COALESCE(i.received_qty, 0) >= COALESCE(i.qty, 0)) THEN 'DELIVERED'
                        WHEN bool_or(COALESCE(i.received_qty, 0) > 0) THEN 'PARTIAL'
                        ELSE 'DRAFT' END AS st
              FROM sales_order_items i
             WHERE i.so_id IN (SELECT DISTINCT i2.so_id FROM sales_order_items i2
                                WHERE i2.soi_id IN (SELECT (l->>'soi_id')::integer
                                                      FROM jsonb_array_elements(v_lines) l))
               AND i.status NOT IN ('CLOSED', 'CANCELLED', 'REPLACED')
             GROUP BY i.so_id) sub
     WHERE o.so_id = sub.so_id
       AND o.status NOT IN ('CLOSED', 'CANCELLED');

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
    '출고 확정을 한 트랜잭션으로: payload(증감값) 검증 → 수주 라인(soi 합산)·회차·충당·ISSUE·수주 상태·전표 CONFIRMED. 실패 시 전부 롤백(P0001 사유). 076: 비활성 라인(CLOSED·CANCELLED·REPLACED)은 line_closed 거부, 머리글은 활성 라인만 재집계(납품 0 = DRAFT).';

REVOKE EXECUTE ON FUNCTION public.confirm_shipment(integer, jsonb) FROM PUBLIC, anon, authenticated;
GRANT  EXECUTE ON FUNCTION public.confirm_shipment(integer, jsonb) TO service_role;

-- 적용 후 검증(개발 세션, 08):
--   select conname, pg_get_constraintdef(oid) from pg_constraint where conname='chk_soi_closed_qty';
--   select column_name, is_nullable from information_schema.columns where table_name in ('sales_orders','sales_order_items') and column_name='status';
--   select so_id, status, total_pending_qty, total_closed_qty, delivery_status from sales_order_stats where so_id in (40,53,55,58,59,62);  -- REPLACED 부풀림 해소
--   select routine_name, grantee from information_schema.routine_privileges where routine_name in ('so_close_lines','so_reopen_lines') order by 1,2;
--   select public.so_close_lines(-1, 'CLOSED', 'x', 'test');   -- not_found (execute_sql 로 따로, 트랜잭션 밖)
