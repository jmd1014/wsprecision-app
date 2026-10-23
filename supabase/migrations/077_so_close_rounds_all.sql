-- ════════════════════════════════════════════════════════════
-- Migration 077: so_close_lines — 종결 때 라인의 **전 회차**를 closed_rounds 에 보존 (2026-10-23, 수주 상태 정리 r3)
-- 기준: _수주상태_r2리뷰_분류_및_r3지시문_20261022.md §2 D17 (Codex r2 H3), R3
-- ════════════════════════════════════════════════════════════
-- 문제(Codex r2 H3): 076 은 열린 회차(qty > delivered)만 closed_rounds 에 남겼다. 종결 뒤 과거 출고를 취소(정정)하면
--   완납 회차(40/40)가 0/0 이 되는데, 그 회차는 보존 목록에 없어 되돌리기가 계획 40 을 복원하지 못했다(rounds_skipped 도 0).
-- 변경: 회차 수집 조건 한 줄 — `WHERE d.soi_id = r.soi_id` (전 회차, 완납 회차 포함). 닫기 UPDATE(qty = delivered 인 열린 회차만)와
--   so_reopen_lines(복원 조건 qty = delivered 인 회차만 GREATEST(qty_before, delivered))는 076 그대로. 본문은 CREATE OR REPLACE 전문 재선언.
--
-- ── 최종 규칙(076 머리 주석 9·13행은 구식 — 076 파일은 적용된 그대로 두고 여기에 기록, Codex r2 L1) ──
--   잠금 순서: 라인(sales_order_items, soi 오름차순 FOR UPDATE) → 머리글(sales_orders FOR UPDATE) — 069 confirm_shipment 와 동일.
--   closed_rounds: 종결 시점의 라인 전 회차 [{sched_id, qty_before, delivered}] (NULL = 닫은 적 없음, [] = 회차 없음).
--   회차 닫기: qty > delivered 인 회차만 qty = delivered. 되돌리기 복원: 현재 qty = delivered(아직 닫힌 상태)인 회차만
--     qty = GREATEST(qty_before, delivered); 열려 있는 회차는 rounds_skipped. (종결 라인의 출고 정정은 앱이 회차 qty 를
--     delivered 로 같이 내려 닫힌 상태를 유지한다 — QA r2 H-2.)
--   비활성 라인 집합 {CLOSED, CANCELLED, REPLACED}; 종결·취소 머리글 아래 라인은 정정 시 전부 비활성 취급(D15, 앱).
--   거울상 머리글 복구: 머리글 비활성 ∧ 보존 라인 없음 ∧ 활성 미납 라인 있음(불변식 ③ 위반)일 때만.
-- 적용 조건: 기존 행 무접촉(함수 재선언만). 멱등. 되돌리기: 076 본문의 so_close_lines 로 재선언(열린 회차만 보존).
-- ════════════════════════════════════════════════════════════

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
    -- 잠금 순서 = 069 와 동일(라인 soi 오름차순 → 머리글)
    PERFORM 1 FROM sales_order_items WHERE so_id = p_so_id ORDER BY soi_id FOR UPDATE;
    SELECT status, remark INTO v_hdr_status, v_hdr_remark FROM sales_orders WHERE so_id = p_so_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'not_found' USING ERRCODE = 'P0001';
    END IF;

    -- 미확정(DRAFT) 출고 전표가 미납 라인을 참조하면 차단 — 같은 트랜잭션에서 검사
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

    -- 미납 라인(활성 상태만): 잔량 보존 → pending 0 → 상태 → 회차 보존(전 회차, 077)·닫기(열린 회차만)
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
         WHERE d.soi_id = r.soi_id;                                           -- 077 D17: 전 회차(완납 회차 포함)
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
    -- 마무리(v_closed = 0)는 남은 닫힌 라인의 상태와 p_mode 가 같을 때만
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
  '수주 종결(CLOSED)·취소(CANCELLED)를 한 트랜잭션으로: 미확정 전표 차단 → 활성 미납 라인 closed_qty 보존·pending 0·전 회차 보존(closed_rounds, 077)·열린 회차 닫기 → 활성 잔량 0 이면 머리글. 멱등. 거부 bad_args/not_found/blocked(HINT 전표) (076·077)';
REVOKE EXECUTE ON FUNCTION public.so_close_lines(integer, text, text, text) FROM PUBLIC, anon, authenticated;
GRANT  EXECUTE ON FUNCTION public.so_close_lines(integer, text, text, text) TO service_role;

-- 적용 후 검증(개발 세션, 08): 드라이런(ROLLBACK) — 완납 회차 + 열린 회차 혼재 라인을 종결 → 과거 출고 취소 흉내(delivered 감소 + qty = delivered)
--   → so_reopen_lines → 두 회차 모두 qty_before 복원, rounds_skipped 0. 그리고 종결 라인을 참조하는 DRAFT 전표를 트랜잭션 안에서 만들어
--   confirm_shipment 호출 → P0001 line_closed 확인 → ROLLBACK.
