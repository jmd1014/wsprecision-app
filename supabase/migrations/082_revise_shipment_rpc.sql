-- ════════════════════════════════════════════════════════════
-- 082: 확정 출고 전표 정정(EDIT)·취소(CANCEL)를 한 트랜잭션으로 — revise_shipment (P3-1a, 2026-11-06)
-- 계획서: docs/development/plans/ (_P3-1_출고정정취소_RPC_계획서_v3_20261106.md — §18 이 본문보다 우선)
-- 파이썬 모델 utils/shipment_revise.plan_revision 과 같은 규칙·같은 거부 순서. 골든 tests/golden/revise_shipment/g_*.json
--
-- 만드는 것
--   ① shipment_revisions.request_id uuid · info jsonb (+ 부분 유니크 인덱스, 머리글 이력 si NULL 은 COALESCE(si_id,0))
--   ② revise_shipment_reasons(shipment, 대상 라인, 감소량) — 데이터 사유 판정 한 곳(§4-5 · §18 A2·A8)
--   ③ revise_shipment(shipment, payload) — 쓰기 / ④ revise_shipment_check(shipment) — 읽기(STABLE, §18 A9)
--   전부 SECURITY INVOKER · search_path 고정 · 실행 권한 service_role 만
--
-- 잠금 순서(§4-3 ② · §18 A3·A11): 전표 → (재실행 판정) → 전표 라인 → 영향 수주의 전 라인(soi 오름차순)
--   → 그 수주 라인들의 전 회차(sched 오름차순) → 증가 제품 advisory(allow_over=false 일 때만, product 오름차순)
--   → 영향 수주 머리글(so 오름차순, FOR NO KEY UPDATE). 잠금 획득(PERFORM … FOR UPDATE)과 값 재조회는 별도 문장.
--   직렬화하는 것: 다른 revise_shipment · confirm_shipment · so_close_lines · so_reopen_lines.
--   직렬화하지 않는 것(범위 밖, 후보 58): 수주 라인 대체·대체 되돌리기·납기 입력 저장·수주 편집(REST 다중 요청).
--
-- 시간: 원장 txn_date 는 KST 오늘 (now() AT TIME ZONE 'Asia/Seoul')::date. 시간대 없는 timestamptz 상수 없음.
-- 되돌리기(코드 revert 뒤, 꼭 필요할 때만 — request_id 는 재실행 근거라 남기는 것이 기본):
--   DROP FUNCTION IF EXISTS public.revise_shipment_check(integer);
--   DROP FUNCTION IF EXISTS public.revise_shipment(integer, jsonb);
--   DROP FUNCTION IF EXISTS public.revise_shipment_reasons(integer, integer[], jsonb);
--   DROP INDEX IF EXISTS public.shipment_revisions_request_uq;
--   ALTER TABLE public.shipment_revisions DROP COLUMN IF EXISTS info, DROP COLUMN IF EXISTS request_id;
-- ════════════════════════════════════════════════════════════

ALTER TABLE public.shipment_revisions
    ADD COLUMN IF NOT EXISTS request_id uuid,
    ADD COLUMN IF NOT EXISTS info jsonb;
COMMENT ON COLUMN public.shipment_revisions.request_id IS
    '정정·취소 요청 id(화면이 만든 uuid) — 같은 요청의 재호출 판정(082). 옛 이력은 NULL';
COMMENT ON COLUMN public.shipment_revisions.info IS
    '{payload_md5, info:[{si_id|soi_id, kind:"unallocated", qty}]} — 재실행 내용 대조·안내 보존(082)';

CREATE UNIQUE INDEX IF NOT EXISTS shipment_revisions_request_uq
    ON public.shipment_revisions (shipment_id, request_id, COALESCE(si_id, 0))
    WHERE request_id IS NOT NULL;


-- ── ② 데이터 사유(§4-5 · §18 A2·A8) — revise_shipment·revise_shipment_check 공용 ──
--   p_target: 판정 대상 전표 라인(EDIT = 바뀌는 라인, CANCEL = 수량 > 0 전 라인)
--   p_dec   : {"si_id": 감소량} (recv_underflow 용, 사전 점검이면 {})
--   반환    : [{code, ids}] (legacy_no_alloc → issue_mismatch → round_short → recv_underflow 순, 없으면 [])
CREATE OR REPLACE FUNCTION public.revise_shipment_reasons(p_shipment_id integer, p_target integer[], p_dec jsonb)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
    WITH tgt AS (
        SELECT si.si_id, si.qty, si.product_id
          FROM shipment_items si
         WHERE si.shipment_id = p_shipment_id AND si.si_id = ANY (p_target)
    ),
    tx AS (
        SELECT t.si_id, it.lot_number, it.qty, it.product_id, it.material_id
          FROM tgt t
          JOIN inventory_transactions it
            ON it.ref_table = 'shipment_items' AND it.txn_type = 'ISSUE' AND it.ref_id = t.si_id
    ),
    r_legacy AS (       -- 충당 저장(2026-09-05) 전 옛 전표 라인 고정 목록 + Σ충당 < 수량
        SELECT array_agg(t.si_id ORDER BY t.si_id) AS ids
          FROM tgt t
         WHERE t.si_id = ANY ('{4,10,16,17,23,36,48,60,63,78,99,148,176}'::integer[])
           AND COALESCE((SELECT SUM(a.qty) FROM shipment_allocations a WHERE a.si_id = t.si_id), 0)
               < COALESCE(t.qty, 0) - 1e-9
    ),
    r_issue AS (        -- ISSUE 순합 ≠ −수량(제품 연결) / LOT 별 과복원 / 제품 불일치 / 자재 행
        SELECT array_agg(t.si_id ORDER BY t.si_id) AS ids
          FROM tgt t
         WHERE EXISTS (SELECT 1 FROM tx WHERE tx.si_id = t.si_id
                          AND (tx.product_id IS DISTINCT FROM t.product_id OR tx.material_id IS NOT NULL))
            OR EXISTS (SELECT 1 FROM tx WHERE tx.si_id = t.si_id
                        GROUP BY tx.lot_number HAVING SUM(tx.qty) > 1e-9)
            OR (t.product_id IS NOT NULL
                AND abs(COALESCE((SELECT SUM(tx.qty) FROM tx WHERE tx.si_id = t.si_id), 0) + COALESCE(t.qty, 0)) > 1e-9)
    ),
    r_round AS (        -- 회차 단위: 대상 라인 충당이 가리키는 회차의 전체 충당 합 > delivered
        SELECT array_agg(d.sched_id ORDER BY d.sched_id) AS ids
          FROM so_delivery_schedule d
         WHERE d.sched_id IN (SELECT a.sched_id FROM shipment_allocations a WHERE a.si_id = ANY (p_target))
           AND (SELECT SUM(a2.qty) FROM shipment_allocations a2 WHERE a2.sched_id = d.sched_id)
               > COALESCE(d.delivered_qty, 0) + 1e-9
    ),
    dec AS (
        SELECT (e.key)::integer AS si_id, (e.value #>> '{}')::numeric AS q
          FROM jsonb_each(COALESCE(p_dec, '{}'::jsonb)) e
    ),
    r_recv AS (         -- 수주 라인별 요청 전체 감소 합 > received
        SELECT array_agg(x.soi_id ORDER BY x.soi_id) AS ids
          FROM (SELECT si.soi_id, SUM(dec.q) AS q
                  FROM dec JOIN shipment_items si ON si.si_id = dec.si_id
                 WHERE si.soi_id IS NOT NULL
                 GROUP BY si.soi_id) x
          JOIN sales_order_items l ON l.soi_id = x.soi_id
         WHERE x.q > COALESCE(l.received_qty, 0) + 1e-9
    )
    SELECT COALESCE(jsonb_agg(z.o ORDER BY z.k), '[]'::jsonb)
      FROM (SELECT 1 AS k, jsonb_build_object('code', 'legacy_no_alloc', 'ids', to_jsonb(ids)) AS o
              FROM r_legacy WHERE ids IS NOT NULL
            UNION ALL
            SELECT 2, jsonb_build_object('code', 'issue_mismatch', 'ids', to_jsonb(ids)) FROM r_issue WHERE ids IS NOT NULL
            UNION ALL
            SELECT 3, jsonb_build_object('code', 'round_short', 'ids', to_jsonb(ids)) FROM r_round WHERE ids IS NOT NULL
            UNION ALL
            SELECT 4, jsonb_build_object('code', 'recv_underflow', 'ids', to_jsonb(ids)) FROM r_recv WHERE ids IS NOT NULL) z;
$$;

COMMENT ON FUNCTION public.revise_shipment_reasons(integer, integer[], jsonb) IS
    '확정 전표 정정·취소의 데이터 사유 판정(082, 계획서 §4-5·§18 A2·A8) — revise_shipment 와 revise_shipment_check 공용';
REVOKE EXECUTE ON FUNCTION public.revise_shipment_reasons(integer, integer[], jsonb) FROM PUBLIC, anon, authenticated;
GRANT  EXECUTE ON FUNCTION public.revise_shipment_reasons(integer, integer[], jsonb) TO service_role;


-- ── ③ 쓰기 ──
CREATE OR REPLACE FUNCTION public.revise_shipment(p_shipment_id integer, p_payload jsonb)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_action    text;
    v_req       uuid;
    v_exp_rev   integer;
    v_reason    text;
    v_who       text;
    v_allow     boolean;
    v_lines     jsonb;
    v_inc       jsonb;
    v_exp       jsonb;
    v_scheds    jsonb;
    v_allocs    jsonb;
    v_txns      jsonb;
    v_sh        record;
    v_md5       text;
    v_prev      record;
    v_l         jsonb;
    v_x         record;
    v_li        record;
    v_r         record;
    v_a         record;
    v_si        integer;
    v_soi       integer;
    v_so        integer;
    v_pid       text;
    v_b         numeric;
    v_af        numeric;
    v_q         numeric;
    v_left      numeric;
    v_take      numeric;
    v_nr        numeric;
    v_hs        text;
    v_st        text;
    v_new_st    text;
    v_was_act   boolean;
    v_has_li    boolean;
    v_unit      text;
    v_tag       text;
    v_today     date := (now() AT TIME ZONE 'Asia/Seoul')::date;
    v_now       timestamptz := now();
    v_chg       jsonb := '{}'::jsonb;     -- {"si": [전, 후]}
    v_dec       jsonb := '{}'::jsonb;     -- {"si": 감소량}
    v_incq      jsonb := '{}'::jsonb;     -- {"si": 증가량}
    v_need      jsonb := '{}'::jsonb;     -- {"soi": 증가 합}
    v_target    integer[];
    v_sois      integer[];
    v_sos       integer[];
    v_changed   integer[] := '{}';
    v_recv0     jsonb := '{}'::jsonb;     -- {"soi": 잠금 직후·감소 전 received}
    v_reasons   jsonb;
    v_info      jsonb := '[]'::jsonb;
    v_rev       integer;
    v_restored  integer := 0;
    v_released  integer := 0;
    v_inc_alloc integer := 0;
    v_inc_txn   integer := 0;
    v_tot       numeric;
    v_stock     numeric;
    v_issue     numeric;
    v_n         integer;
BEGIN
    -- 0. 형식
    IF p_payload IS NULL OR jsonb_typeof(p_payload) <> 'object'
       OR (p_payload->>'v') IS DISTINCT FROM '1'
       OR COALESCE(p_payload->>'action', '') NOT IN ('EDIT', 'CANCEL') THEN
        RAISE EXCEPTION 'bad_version' USING ERRCODE = 'P0001';
    END IF;
    -- 배열·원소 형식(utils/shipment_revise.shape_ok 와 같은 규칙) — 숫자 자리에 숫자가 아니면 캐스트 오류(22P02)가
    -- 아니라 bad_version 으로. md5·검증의 캐스트보다 앞
    v_lines := COALESCE(NULLIF(p_payload->'lines', 'null'::jsonb), '[]'::jsonb);
    v_inc   := COALESCE(NULLIF(p_payload->'inc', 'null'::jsonb), '{}'::jsonb);
    IF jsonb_typeof(v_lines) <> 'array' OR jsonb_typeof(v_inc) <> 'object'
       OR (jsonb_typeof(p_payload->'allow_over') IS NOT NULL
           AND jsonb_typeof(p_payload->'allow_over') NOT IN ('boolean', 'null')) THEN
        RAISE EXCEPTION 'bad_version' USING ERRCODE = 'P0001', HINT = 'shape';
    END IF;
    v_exp    := COALESCE(NULLIF(v_inc->'expected_received_before', 'null'::jsonb), '[]'::jsonb);
    v_scheds := COALESCE(NULLIF(v_inc->'scheds', 'null'::jsonb), '[]'::jsonb);
    v_allocs := COALESCE(NULLIF(v_inc->'allocs', 'null'::jsonb), '[]'::jsonb);
    v_txns   := COALESCE(NULLIF(v_inc->'txns', 'null'::jsonb), '[]'::jsonb);
    IF jsonb_typeof(v_exp) <> 'array' OR jsonb_typeof(v_scheds) <> 'array'
       OR jsonb_typeof(v_allocs) <> 'array' OR jsonb_typeof(v_txns) <> 'array' THEN
        RAISE EXCEPTION 'bad_version' USING ERRCODE = 'P0001', HINT = 'shape';
    END IF;
    IF EXISTS (SELECT 1 FROM jsonb_array_elements(v_lines) e
                WHERE jsonb_typeof(e) <> 'object' OR NOT COALESCE(jsonb_typeof(e->'si_id') = 'number' AND (e->'si_id' #>> '{}') ~ '^-?[0-9]+$', false)
                   OR jsonb_typeof(e->'qty_before') IS DISTINCT FROM 'number'
                   OR jsonb_typeof(e->'qty_after') IS DISTINCT FROM 'number')
       OR EXISTS (SELECT 1 FROM jsonb_array_elements(v_exp) e
                   WHERE jsonb_typeof(e) <> 'object' OR NOT COALESCE(jsonb_typeof(e->'soi_id') = 'number' AND (e->'soi_id' #>> '{}') ~ '^-?[0-9]+$', false)
                      OR jsonb_typeof(e->'received') IS DISTINCT FROM 'number')
       OR EXISTS (SELECT 1 FROM jsonb_array_elements(v_scheds) e
                   WHERE jsonb_typeof(e) <> 'object' OR NOT COALESCE(jsonb_typeof(e->'sched_id') = 'number' AND (e->'sched_id' #>> '{}') ~ '^-?[0-9]+$', false)
                      OR NOT COALESCE(jsonb_typeof(e->'soi_id') = 'number' AND (e->'soi_id' #>> '{}') ~ '^-?[0-9]+$', false)
                      OR jsonb_typeof(e->'delta') IS DISTINCT FROM 'number')
       OR EXISTS (SELECT 1 FROM jsonb_array_elements(v_allocs) e
                   WHERE jsonb_typeof(e) <> 'object' OR NOT COALESCE(jsonb_typeof(e->'si_id') = 'number' AND (e->'si_id' #>> '{}') ~ '^-?[0-9]+$', false)
                      OR NOT COALESCE(jsonb_typeof(e->'sched_id') = 'number' AND (e->'sched_id' #>> '{}') ~ '^-?[0-9]+$', false)
                      OR jsonb_typeof(e->'qty') IS DISTINCT FROM 'number')
       OR EXISTS (SELECT 1 FROM jsonb_array_elements(v_txns) e
                   WHERE jsonb_typeof(e) <> 'object' OR NOT COALESCE(jsonb_typeof(e->'si_id') = 'number' AND (e->'si_id' #>> '{}') ~ '^-?[0-9]+$', false)
                      OR jsonb_typeof(e->'qty') IS DISTINCT FROM 'number'
                      OR COALESCE(jsonb_typeof(e->'product_id'), 'null') NOT IN ('string', 'null')
                      OR COALESCE(jsonb_typeof(e->'unit'), 'null') NOT IN ('string', 'null')
                      OR COALESCE(jsonb_typeof(e->'lot_number'), 'null') NOT IN ('string', 'null')
                      OR COALESCE(jsonb_typeof(e->'work_order'), 'null') NOT IN ('string', 'null')) THEN
        RAISE EXCEPTION 'bad_version' USING ERRCODE = 'P0001', HINT = 'shape';
    END IF;
    IF jsonb_typeof(p_payload->'request_id') IS DISTINCT FROM 'string'
       OR (p_payload->>'request_id') !~ '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$' THEN
        RAISE EXCEPTION 'bad_version' USING ERRCODE = 'P0001', HINT = 'request_id';
    END IF;
    IF (p_payload->>'expected_rev_no') IS NULL OR (p_payload->>'expected_rev_no') !~ '^-?[0-9]+$' THEN
        RAISE EXCEPTION 'bad_version' USING ERRCODE = 'P0001', HINT = 'expected_rev_no';
    END IF;
    v_action  := p_payload->>'action';
    v_req     := (p_payload->>'request_id')::uuid;
    v_exp_rev := (p_payload->>'expected_rev_no')::integer;
    v_reason  := btrim(COALESCE(p_payload->>'reason', ''));
    v_who     := p_payload->>'who';
    v_allow   := COALESCE((p_payload->>'allow_over')::boolean, false);

    -- ① 전표 잠금 → 재실행 판정(상태 검사보다 앞, 나머지 잠금 전)
    SELECT shipment_id, ship_no, ship_date, status, rev_no INTO v_sh
      FROM shipments WHERE shipment_id = p_shipment_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'not_found' USING ERRCODE = 'P0001';
    END IF;
    -- 정규화 문자열 md5 (utils/shipment_revise.request_md5 와 같은 글자 — who 제외)
    v_md5 := md5(concat_ws('|',
        'a=' || v_action,
        'r=' || v_reason,
        'o=' || CASE WHEN v_allow THEN '1' ELSE '0' END,
        'l=' || COALESCE((SELECT string_agg(concat_ws(':', (l->>'si_id')::integer,
                                   trim_scale(round((l->>'qty_before')::numeric, 6)),
                                   trim_scale(round((l->>'qty_after')::numeric, 6))), ';'
                                   ORDER BY (l->>'si_id')::integer, (l->>'qty_before')::numeric, (l->>'qty_after')::numeric)
                            FROM jsonb_array_elements(v_lines) l), ''),
        'e=' || COALESCE((SELECT string_agg(concat_ws(':', (e->>'soi_id')::integer,
                                   trim_scale(round((e->>'received')::numeric, 6))), ';'
                                   ORDER BY (e->>'soi_id')::integer, (e->>'received')::numeric)
                            FROM jsonb_array_elements(v_exp) e), ''),
        's=' || COALESCE((SELECT string_agg(concat_ws(':', (s->>'sched_id')::integer, (s->>'soi_id')::integer,
                                   trim_scale(round((s->>'delta')::numeric, 6))), ';'
                                   ORDER BY (s->>'sched_id')::integer, (s->>'soi_id')::integer, (s->>'delta')::numeric)
                            FROM jsonb_array_elements(v_scheds) s), ''),
        'c=' || COALESCE((SELECT string_agg(concat_ws(':', (a->>'si_id')::integer, (a->>'sched_id')::integer,
                                   trim_scale(round((a->>'qty')::numeric, 6))), ';'
                                   ORDER BY (a->>'si_id')::integer, (a->>'sched_id')::integer, (a->>'qty')::numeric)
                            FROM jsonb_array_elements(v_allocs) a), ''),
        't=' || COALESCE((SELECT string_agg(concat_ws(':', (t->>'si_id')::integer, COALESCE(t->>'product_id', ''),
                                   trim_scale(round((t->>'qty')::numeric, 6)), COALESCE(t->>'unit', ''),
                                   COALESCE(t->>'lot_number', ''), COALESCE(t->>'work_order', '')), ';'
                                   ORDER BY (t->>'si_id')::integer, COALESCE(t->>'product_id', '') COLLATE "C",
                                            (t->>'qty')::numeric, COALESCE(t->>'unit', '') COLLATE "C",
                                            COALESCE(t->>'lot_number', '') COLLATE "C",
                                            COALESCE(t->>'work_order', '') COLLATE "C")
                            FROM jsonb_array_elements(v_txns) t), '')));
    SELECT rev_no, action, info INTO v_prev
      FROM shipment_revisions
     WHERE shipment_id = p_shipment_id AND request_id = v_req
     ORDER BY rev_id LIMIT 1;
    IF FOUND THEN
        IF (v_prev.info->>'payload_md5') IS DISTINCT FROM v_md5 THEN
            RAISE EXCEPTION 'request_conflict' USING ERRCODE = 'P0001';
        END IF;
        RETURN jsonb_build_object('ok', true, 'replayed', true, 'action', v_prev.action, 'rev_no', v_prev.rev_no,
                                  'info', COALESCE(v_prev.info->'info', '[]'::jsonb));
    END IF;

    -- ③ 전제 검사
    IF v_sh.status IS DISTINCT FROM 'CONFIRMED' THEN
        RAISE EXCEPTION 'not_confirmed:%', v_sh.status USING ERRCODE = 'P0001';
    END IF;
    IF COALESCE(v_sh.rev_no, 0) <> v_exp_rev THEN
        RAISE EXCEPTION 'stale_rev' USING ERRCODE = 'P0001';
    END IF;
    IF v_reason = '' THEN
        RAISE EXCEPTION 'reason_required' USING ERRCODE = 'P0001';
    END IF;
    IF EXISTS (SELECT 1 FROM sales_month_close m WHERE m.ym = to_char(v_sh.ship_date, 'YYYY-MM')) THEN
        RAISE EXCEPTION 'month_closed' USING ERRCODE = 'P0001';
    END IF;
    IF EXISTS (SELECT 1 FROM shipment_revisions r WHERE r.shipment_id = p_shipment_id AND r.action = 'CANCEL') THEN
        RAISE EXCEPTION 'partial_cancel_legacy' USING ERRCODE = 'P0001';
    END IF;

    -- ② 전표 라인 잠금
    PERFORM 1 FROM shipment_items WHERE shipment_id = p_shipment_id ORDER BY si_id FOR UPDATE;

    -- EDIT 입력 / CANCEL 대상
    IF v_action = 'EDIT' THEN
        IF jsonb_array_length(v_lines) = 0 THEN
            RAISE EXCEPTION 'nothing_to_apply' USING ERRCODE = 'P0001';
        END IF;
        IF EXISTS (SELECT 1 FROM jsonb_array_elements(v_lines) l
                    WHERE jsonb_typeof(l->'si_id') IS DISTINCT FROM 'number')
           OR (SELECT count(*) <> count(DISTINCT (l->>'si_id')::integer) FROM jsonb_array_elements(v_lines) l)
           OR EXISTS (SELECT 1 FROM jsonb_array_elements(v_lines) l
                        LEFT JOIN shipment_items si ON si.si_id = (l->>'si_id')::integer
                                                   AND si.shipment_id = p_shipment_id
                       WHERE si.si_id IS NULL) THEN
            RAISE EXCEPTION 'line_mismatch' USING ERRCODE = 'P0001';
        END IF;
        FOR v_l IN SELECT e FROM jsonb_array_elements(v_lines) WITH ORDINALITY AS x(e, n) ORDER BY n LOOP
            v_si := (v_l->>'si_id')::integer;
            IF jsonb_typeof(v_l->'qty_before') IS DISTINCT FROM 'number'
               OR jsonb_typeof(v_l->'qty_after') IS DISTINCT FROM 'number'
               OR (v_l->>'qty_after')::numeric < 0 THEN
                RAISE EXCEPTION 'line_mismatch' USING ERRCODE = 'P0001', HINT = format('si %s', v_si);
            END IF;
            v_b  := (v_l->>'qty_before')::numeric;
            v_af := (v_l->>'qty_after')::numeric;
            IF abs(v_b - (SELECT COALESCE(qty, 0) FROM shipment_items WHERE si_id = v_si)) > 1e-9 THEN
                RAISE EXCEPTION 'stale_line' USING ERRCODE = 'P0001', HINT = format('si %s', v_si);
            END IF;
            IF abs(v_af - v_b) <= 1e-9 THEN
                RAISE EXCEPTION 'line_mismatch' USING ERRCODE = 'P0001', HINT = format('si %s: no change', v_si);
            END IF;
            v_chg := v_chg || jsonb_build_object(v_si::text, jsonb_build_array(v_b, v_af));
        END LOOP;
        IF EXISTS (SELECT 1 FROM shipment_items WHERE shipment_id = p_shipment_id AND qty > 1e-9)
           AND NOT EXISTS (SELECT 1 FROM shipment_items si
                            WHERE si.shipment_id = p_shipment_id AND si.qty > 1e-9
                              AND (NOT v_chg ? si.si_id::text OR (v_chg->si.si_id::text->>1)::numeric > 1e-9)) THEN
            RAISE EXCEPTION 'use_cancel' USING ERRCODE = 'P0001';
        END IF;
    ELSE
        IF jsonb_array_length(v_lines) > 0 THEN
            RAISE EXCEPTION 'bad_version' USING ERRCODE = 'P0001', HINT = 'lines';
        END IF;
        SELECT COALESCE(jsonb_object_agg(si.si_id::text, jsonb_build_array(si.qty, 0)), '{}'::jsonb) INTO v_chg
          FROM shipment_items si WHERE si.shipment_id = p_shipment_id AND si.qty > 1e-9;
    END IF;
    SELECT COALESCE(array_agg(k::integer ORDER BY k::integer), '{}') INTO v_target FROM jsonb_object_keys(v_chg) k;
    SELECT COALESCE(jsonb_object_agg(k, (v_chg->k->>0)::numeric - (v_chg->k->>1)::numeric)
                        FILTER (WHERE (v_chg->k->>1)::numeric < (v_chg->k->>0)::numeric - 1e-9), '{}'::jsonb),
           COALESCE(jsonb_object_agg(k, (v_chg->k->>1)::numeric - (v_chg->k->>0)::numeric)
                        FILTER (WHERE (v_chg->k->>1)::numeric > (v_chg->k->>0)::numeric + 1e-9), '{}'::jsonb)
      INTO v_dec, v_incq
      FROM jsonb_object_keys(v_chg) k;

    -- ② 나머지 잠금: 영향 수주의 전 라인 → 그 라인들의 전 회차 → 제품 advisory → 수주 머리글
    SELECT COALESCE(array_agg(DISTINCT l.so_id ORDER BY l.so_id), '{}') INTO v_sos
      FROM sales_order_items l
     WHERE l.soi_id IN (SELECT si.soi_id FROM shipment_items si WHERE si.si_id = ANY (v_target));
    PERFORM 1 FROM sales_order_items WHERE so_id = ANY (v_sos) ORDER BY soi_id FOR UPDATE;
    SELECT COALESCE(array_agg(soi_id ORDER BY soi_id), '{}') INTO v_sois FROM sales_order_items WHERE so_id = ANY (v_sos);
    PERFORM 1 FROM so_delivery_schedule WHERE soi_id = ANY (v_sois) ORDER BY sched_id FOR UPDATE;
    IF NOT v_allow THEN
        FOR v_pid IN SELECT DISTINCT t->>'product_id' FROM jsonb_array_elements(v_txns) t
                      WHERE t->>'product_id' IS NOT NULL ORDER BY 1 LOOP
            PERFORM pg_advisory_xact_lock(hashtext('product_stock'), hashtext(v_pid));
        END LOOP;
    END IF;
    PERFORM 1 FROM sales_orders WHERE so_id = ANY (v_sos) ORDER BY so_id FOR NO KEY UPDATE;
    -- 잠금 직후(감소 전) 납품량 — 증가 payload 의 expected_received_before 와 비교
    SELECT COALESCE(jsonb_object_agg(soi_id::text, COALESCE(received_qty, 0)), '{}'::jsonb) INTO v_recv0
      FROM sales_order_items WHERE soi_id = ANY (v_sois);

    -- 데이터 사유(§4-5)
    v_reasons := public.revise_shipment_reasons(p_shipment_id, v_target, v_dec);
    IF jsonb_array_length(v_reasons) > 0 THEN
        RAISE EXCEPTION '%', v_reasons->0->>'code' USING ERRCODE = 'P0001',
            HINT = (SELECT string_agg(x, ',') FROM jsonb_array_elements_text(v_reasons->0->'ids') x);
    END IF;

    -- 증가분 형식(값 검사는 감소 적용 뒤)
    IF v_incq <> '{}'::jsonb THEN
        FOR v_si IN SELECT k::integer FROM jsonb_object_keys(v_incq) k ORDER BY 1 LOOP
            IF (SELECT soi_id IS NULL OR product_id IS NULL OR product_id = '' FROM shipment_items WHERE si_id = v_si) THEN
                RAISE EXCEPTION 'line_unlinked' USING ERRCODE = 'P0001', HINT = format('si %s', v_si);
            END IF;
        END LOOP;
        IF (SELECT array_agg((e->>'soi_id')::integer ORDER BY (e->>'soi_id')::integer) FROM jsonb_array_elements(v_exp) e)
           IS DISTINCT FROM
           (SELECT array_agg(DISTINCT si.soi_id ORDER BY si.soi_id) FROM shipment_items si
             WHERE si.si_id IN (SELECT k::integer FROM jsonb_object_keys(v_incq) k)) THEN
            RAISE EXCEPTION 'bad_version' USING ERRCODE = 'P0001', HINT = 'expected_received_before';
        END IF;
    ELSIF jsonb_array_length(v_exp) + jsonb_array_length(v_scheds) + jsonb_array_length(v_allocs)
          + jsonb_array_length(v_txns) > 0 THEN
        RAISE EXCEPTION 'bad_version' USING ERRCODE = 'P0001', HINT = 'inc without increase';
    END IF;

    -- ④ 감소분 — si 오름차순, 한 줄씩(집합 UPDATE 금지)
    FOR v_si IN SELECT k::integer FROM jsonb_object_keys(v_dec) k ORDER BY 1 LOOP
        v_q := (v_dec->>v_si::text)::numeric;
        SELECT si_id, soi_id, product_id, unit, so_number INTO v_x FROM shipment_items WHERE si_id = v_si;
        v_tag := format('%s %s: %s (%s)', CASE WHEN v_action = 'CANCEL' THEN '출고 취소' ELSE '출고 정정' END,
                        v_sh.ship_no, COALESCE(NULLIF(v_x.so_number, ''), '-'), COALESCE(NULLIF(v_reason, ''), '-'));
        v_unit := NULL;
        v_has_li := false;
        IF v_x.soi_id IS NOT NULL THEN
            SELECT soi_id, so_id, qty, received_qty, status, closed_rounds, unit INTO v_li
              FROM sales_order_items WHERE soi_id = v_x.soi_id;
            v_has_li := FOUND;
        END IF;
        IF v_has_li THEN
            v_unit := NULLIF(v_li.unit, '');
            SELECT status INTO v_hs FROM sales_orders WHERE so_id = v_li.so_id;
            v_st := upper(COALESCE(v_li.status, ''));
            v_hs := upper(COALESCE(v_hs, ''));
            v_was_act := v_st NOT IN ('CLOSED', 'CANCELLED', 'REPLACED');
            v_nr := GREATEST(COALESCE(v_li.received_qty, 0) - v_q, 0);
            -- D15 첫 닫힘: 환원 전 회차 스냅샷
            IF v_was_act AND v_hs IN ('CLOSED', 'CANCELLED', 'CANCELED')
               AND (v_li.closed_rounds IS NULL OR v_li.closed_rounds = '[]'::jsonb) THEN
                UPDATE sales_order_items
                   SET closed_rounds = (SELECT COALESCE(jsonb_agg(jsonb_build_object(
                                                 'sched_id', d.sched_id, 'qty_before', COALESCE(d.qty, 0),
                                                 'delivered', COALESCE(d.delivered_qty, 0)) ORDER BY d.sched_id), '[]'::jsonb)
                                          FROM so_delivery_schedule d WHERE d.soi_id = v_li.soi_id),
                       close_reason = '출고 정정 ' || v_sh.ship_no
                 WHERE soi_id = v_li.soi_id;
            END IF;
            -- 수주 라인 값(revise_line_fields 와 같은 규칙)
            IF v_st = 'REPLACED' THEN
                UPDATE sales_order_items SET received_qty = v_nr, pending_qty = 0 WHERE soi_id = v_li.soi_id;
                v_new_st := v_st;
            ELSIF v_st IN ('CLOSED', 'CANCELLED') THEN
                UPDATE sales_order_items
                   SET received_qty = v_nr, pending_qty = 0, closed_qty = GREATEST(COALESCE(qty, 0) - v_nr, 0)
                 WHERE soi_id = v_li.soi_id;
                v_new_st := v_st;
            ELSIF v_hs IN ('CLOSED', 'CANCELLED', 'CANCELED') THEN
                v_new_st := CASE WHEN v_hs = 'CLOSED' THEN 'CLOSED' ELSE 'CANCELLED' END;
                UPDATE sales_order_items
                   SET received_qty = v_nr, pending_qty = 0, status = v_new_st,
                       closed_qty = GREATEST(COALESCE(qty, 0) - v_nr, 0)
                 WHERE soi_id = v_li.soi_id;
            ELSE
                v_new_st := CASE WHEN v_nr >= COALESCE(v_li.qty, 0) - 1e-9 THEN 'DELIVERED'
                                 WHEN v_nr > 0 THEN 'PARTIAL' ELSE 'PENDING' END;
                UPDATE sales_order_items
                   SET received_qty = v_nr, pending_qty = GREATEST(COALESCE(qty, 0) - v_nr, 0), status = v_new_st
                 WHERE soi_id = v_li.soi_id;
            END IF;
            v_changed := array_append(v_changed, v_li.soi_id);
            -- 회차 환원: 충당 행을 회차 납기 최근순(동률 alloc_id 오름차순)으로
            v_left := v_q;
            FOR v_a IN SELECT a.alloc_id, a.sched_id, a.qty
                         FROM shipment_allocations a
                         LEFT JOIN so_delivery_schedule d ON d.sched_id = a.sched_id
                        WHERE a.si_id = v_si
                        ORDER BY COALESCE(d.due_date::text, '') DESC, a.alloc_id ASC LOOP
                EXIT WHEN v_left <= 1e-9;
                v_take := LEAST(COALESCE(v_a.qty, 0), v_left);
                CONTINUE WHEN v_take <= 1e-9;
                UPDATE so_delivery_schedule
                   SET delivered_qty = COALESCE(delivered_qty, 0) - v_take, updated_at = v_now
                 WHERE sched_id = v_a.sched_id;
                UPDATE shipment_allocations SET qty = qty - v_take WHERE alloc_id = v_a.alloc_id;
                v_left := v_left - v_take;
                v_released := v_released + 1;
            END LOOP;
            DELETE FROM shipment_allocations WHERE si_id = v_si AND qty <= 1e-9;
            IF v_left > 1e-9 THEN
                v_info := v_info || jsonb_build_array(jsonb_build_object('si_id', v_si, 'kind', 'unallocated', 'qty', v_left));
            END IF;
            IF v_new_st IN ('CLOSED', 'CANCELLED', 'REPLACED') THEN      -- 닫힌 채 남는 라인: 열린 회차를 닫는다(077)
                UPDATE so_delivery_schedule
                   SET qty = COALESCE(delivered_qty, 0), updated_at = v_now
                 WHERE soi_id = v_li.soi_id AND COALESCE(qty, 0) > COALESCE(delivered_qty, 0) + 1e-9;
            END IF;
        END IF;
        -- LOT 복원(제품 연결 라인) — LOT 별 최초 차감 txn_id 의 역순
        IF v_x.product_id IS NOT NULL AND v_x.product_id <> '' THEN
            v_left := v_q;
            FOR v_r IN SELECT n.lot_number, n.net
                         FROM (SELECT lot_number, MIN(txn_id) AS first_id, -SUM(qty) AS net
                                 FROM inventory_transactions
                                WHERE ref_table = 'shipment_items' AND txn_type = 'ISSUE' AND ref_id = v_si
                                GROUP BY lot_number) n
                        WHERE n.net > 1e-9
                        ORDER BY n.first_id DESC LOOP
                EXIT WHEN v_left <= 1e-9;
                v_take := LEAST(v_r.net, v_left);
                INSERT INTO inventory_transactions
                    (material_id, product_id, txn_type, qty, unit, lot_number, work_order,
                     ref_table, ref_id, txn_date, remark, created_by)
                VALUES (NULL, v_x.product_id, 'ISSUE', v_take, COALESCE(v_unit, NULLIF(v_x.unit, ''), 'EA'),
                        v_r.lot_number, v_r.lot_number, 'shipment_items', v_si, v_today, v_tag, v_who);
                v_restored := v_restored + 1;
                v_left := v_left - v_take;
            END LOOP;
        END IF;
    END LOOP;

    -- ⑤ 증가분 — 감소 적용 뒤 상태 기준
    IF v_incq <> '{}'::jsonb THEN
        FOR v_l IN SELECT e FROM jsonb_array_elements(v_exp) WITH ORDINALITY AS x(e, n) ORDER BY n LOOP
            IF abs(COALESCE((v_recv0->>((v_l->>'soi_id')::integer)::text)::numeric, -1) - (v_l->>'received')::numeric) > 1e-9 THEN
                RAISE EXCEPTION 'stale' USING ERRCODE = 'P0001', HINT = format('soi %s', v_l->>'soi_id');
            END IF;
        END LOOP;
        SELECT jsonb_object_agg(x.soi_id::text, x.q) INTO v_need
          FROM (SELECT si.soi_id, SUM((v_incq->>si.si_id::text)::numeric) AS q
                  FROM shipment_items si WHERE si.si_id IN (SELECT k::integer FROM jsonb_object_keys(v_incq) k)
                 GROUP BY si.soi_id) x;
        FOR v_soi IN SELECT k::integer FROM jsonb_object_keys(v_need) k ORDER BY 1 LOOP
            SELECT l.qty, l.received_qty, l.status, o.status AS hs INTO v_li
              FROM sales_order_items l LEFT JOIN sales_orders o ON o.so_id = l.so_id WHERE l.soi_id = v_soi;
            IF upper(COALESCE(v_li.status, '')) IN ('CLOSED', 'CANCELLED', 'REPLACED')
               OR upper(COALESCE(v_li.hs, '')) IN ('CLOSED', 'CANCELLED', 'CANCELED') THEN
                RAISE EXCEPTION 'line_closed' USING ERRCODE = 'P0001', HINT = format('soi %s', v_soi);
            END IF;
            IF COALESCE(v_li.received_qty, 0) + (v_need->>v_soi::text)::numeric > COALESCE(v_li.qty, 0) + 1e-9 THEN
                RAISE EXCEPTION 'over_pending' USING ERRCODE = 'P0001', HINT = format('soi %s', v_soi);
            END IF;
        END LOOP;
        -- 회차: 존재·soi 일치·delta ≥ 0·soi 는 증가 라인의 것
        IF EXISTS (SELECT 1 FROM jsonb_array_elements(v_scheds) s
                     LEFT JOIN so_delivery_schedule d ON d.sched_id = (s->>'sched_id')::integer
                    WHERE d.sched_id IS NULL OR (s->>'soi_id') IS NULL
                       OR d.soi_id IS DISTINCT FROM (s->>'soi_id')::integer
                       OR (s->>'delta')::numeric IS NULL OR (s->>'delta')::numeric < 0
                       OR NOT v_need ? ((s->>'soi_id')::integer)::text) THEN
            RAISE EXCEPTION 'sched_mismatch' USING ERRCODE = 'P0001';
        END IF;
        FOR v_soi IN SELECT k::integer FROM jsonb_object_keys(v_need) k LOOP
            SELECT COALESCE(SUM((s->>'delta')::numeric), 0) INTO v_tot
              FROM jsonb_array_elements(v_scheds) s WHERE (s->>'soi_id')::integer = v_soi;
            IF v_tot > (v_need->>v_soi::text)::numeric + 1e-9 THEN
                RAISE EXCEPTION 'sched_mismatch' USING ERRCODE = 'P0001', HINT = format('soi %s', v_soi);
            END IF;
        END LOOP;
        FOR v_soi IN SELECT k::integer FROM jsonb_object_keys(v_need) k ORDER BY 1 LOOP
            SELECT COALESCE(SUM((s->>'delta')::numeric), 0) INTO v_tot
              FROM jsonb_array_elements(v_scheds) s WHERE (s->>'soi_id')::integer = v_soi;
            IF v_tot < (v_need->>v_soi::text)::numeric - 1e-9 THEN
                v_info := v_info || jsonb_build_array(jsonb_build_object(
                    'soi_id', v_soi, 'kind', 'unallocated', 'qty', (v_need->>v_soi::text)::numeric - v_tot));
            END IF;
        END LOOP;
        -- 충당: si 는 증가 라인·qty > 0·회차는 그 라인 수주의 것, 회차별 Σ충당 = Σdelta, si 별 Σ충당 ≤ 증가량
        IF EXISTS (SELECT 1 FROM jsonb_array_elements(v_allocs) a
                     LEFT JOIN shipment_items si ON si.si_id = (a->>'si_id')::integer
                     LEFT JOIN so_delivery_schedule d ON d.sched_id = (a->>'sched_id')::integer
                    WHERE (a->>'si_id') IS NULL OR (a->>'sched_id') IS NULL
                       OR NOT v_incq ? ((a->>'si_id')::integer)::text
                       OR d.sched_id IS NULL OR (a->>'qty')::numeric IS NULL OR (a->>'qty')::numeric <= 1e-9
                       OR d.soi_id IS DISTINCT FROM si.soi_id) THEN
            RAISE EXCEPTION 'alloc_mismatch' USING ERRCODE = 'P0001';
        END IF;
        IF EXISTS (SELECT 1
                     FROM (SELECT (s->>'sched_id')::integer AS sched_id, SUM((s->>'delta')::numeric) AS d
                             FROM jsonb_array_elements(v_scheds) s GROUP BY 1) sd
                     FULL JOIN (SELECT (a->>'sched_id')::integer AS sched_id, SUM((a->>'qty')::numeric) AS q
                                  FROM jsonb_array_elements(v_allocs) a GROUP BY 1) ad USING (sched_id)
                    WHERE abs(COALESCE(sd.d, 0) - COALESCE(ad.q, 0)) > 1e-9) THEN
            RAISE EXCEPTION 'alloc_mismatch' USING ERRCODE = 'P0001', HINT = 'per sched';
        END IF;
        IF EXISTS (SELECT 1 FROM (SELECT (a->>'si_id')::integer AS si_id, SUM((a->>'qty')::numeric) AS q
                                    FROM jsonb_array_elements(v_allocs) a GROUP BY 1) x
                    WHERE x.q > (v_incq->>x.si_id::text)::numeric + 1e-9) THEN
            RAISE EXCEPTION 'alloc_mismatch' USING ERRCODE = 'P0001', HINT = 'si over qty';
        END IF;
        -- ISSUE: si 는 증가 라인, qty < 0, 제품 일치, si 별 Σ = −증가량
        IF EXISTS (SELECT 1 FROM jsonb_array_elements(v_txns) t
                     LEFT JOIN shipment_items si ON si.si_id = (t->>'si_id')::integer
                    WHERE (t->>'si_id') IS NULL OR NOT v_incq ? ((t->>'si_id')::integer)::text
                       OR (t->>'qty')::numeric IS NULL OR (t->>'qty')::numeric >= 0
                       OR (t->>'product_id') IS DISTINCT FROM si.product_id) THEN
            RAISE EXCEPTION 'txn_mismatch' USING ERRCODE = 'P0001';
        END IF;
        IF EXISTS (SELECT 1 FROM jsonb_object_keys(v_incq) k
                    WHERE abs(COALESCE((SELECT SUM((t->>'qty')::numeric) FROM jsonb_array_elements(v_txns) t
                                         WHERE (t->>'si_id')::integer = k::integer), 0)
                              + (v_incq->>k)::numeric) > 1e-9) THEN
            RAISE EXCEPTION 'txn_mismatch' USING ERRCODE = 'P0001';
        END IF;
        -- 적용: 수주 라인 → 회차(초과 금지) → 충당 → 재고 검사 → ISSUE
        FOR v_soi IN SELECT k::integer FROM jsonb_object_keys(v_need) k ORDER BY 1 LOOP
            UPDATE sales_order_items
               SET received_qty = COALESCE(received_qty, 0) + (v_need->>v_soi::text)::numeric,
                   pending_qty = GREATEST(COALESCE(qty, 0) - COALESCE(received_qty, 0) - (v_need->>v_soi::text)::numeric, 0),
                   status = CASE WHEN COALESCE(received_qty, 0) + (v_need->>v_soi::text)::numeric >= COALESCE(qty, 0) - 1e-9
                                 THEN 'DELIVERED'
                                 WHEN COALESCE(received_qty, 0) + (v_need->>v_soi::text)::numeric > 0 THEN 'PARTIAL'
                                 ELSE 'PENDING' END
             WHERE soi_id = v_soi;
            v_changed := array_append(v_changed, v_soi);
        END LOOP;
        FOR v_r IN SELECT (s->>'sched_id')::integer AS sched_id, SUM((s->>'delta')::numeric) AS d
                     FROM jsonb_array_elements(v_scheds) s GROUP BY 1 ORDER BY 1 LOOP
            CONTINUE WHEN v_r.d <= 1e-9;
            UPDATE so_delivery_schedule
               SET delivered_qty = COALESCE(delivered_qty, 0) + v_r.d, updated_at = v_now
             WHERE sched_id = v_r.sched_id AND COALESCE(delivered_qty, 0) + v_r.d <= COALESCE(qty, 0) + 1e-9;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'sched_over' USING ERRCODE = 'P0001', HINT = format('sched %s', v_r.sched_id);
            END IF;
        END LOOP;
        FOR v_l IN SELECT e FROM jsonb_array_elements(v_allocs) WITH ORDINALITY AS x(e, n) ORDER BY n LOOP
            INSERT INTO shipment_allocations (si_id, sched_id, qty)
            VALUES ((v_l->>'si_id')::integer, (v_l->>'sched_id')::integer, (v_l->>'qty')::numeric);
            v_inc_alloc := v_inc_alloc + 1;
        END LOOP;
        IF NOT v_allow THEN
            FOR v_pid, v_issue IN SELECT t->>'product_id', -SUM((t->>'qty')::numeric)
                                    FROM jsonb_array_elements(v_txns) t GROUP BY 1 ORDER BY 1 LOOP
                SELECT COALESCE(current_stock, 0) INTO v_stock FROM product_stock_v WHERE product_id = v_pid;
                IF COALESCE(v_stock, 0) + 1e-9 < v_issue THEN
                    RAISE EXCEPTION 'stock:%', v_pid USING ERRCODE = 'P0001',
                        HINT = format('stock %s < issue %s', COALESCE(v_stock, 0), v_issue);
                END IF;
            END LOOP;
        END IF;
        FOR v_l IN SELECT e FROM jsonb_array_elements(v_txns) WITH ORDINALITY AS x(e, n) ORDER BY n LOOP
            SELECT so_number INTO v_x FROM shipment_items WHERE si_id = (v_l->>'si_id')::integer;
            v_tag := format('%s %s: %s (%s)', CASE WHEN v_action = 'CANCEL' THEN '출고 취소' ELSE '출고 정정' END,
                            v_sh.ship_no, COALESCE(NULLIF(v_x.so_number, ''), '-'), COALESCE(NULLIF(v_reason, ''), '-'));
            INSERT INTO inventory_transactions
                (material_id, product_id, txn_type, qty, unit, lot_number, work_order,
                 ref_table, ref_id, txn_date, remark, created_by)
            VALUES (NULL, v_l->>'product_id', 'ISSUE', (v_l->>'qty')::numeric,
                    COALESCE(NULLIF(v_l->>'unit', ''), 'EA'), v_l->>'lot_number', v_l->>'work_order',
                    'shipment_items', (v_l->>'si_id')::integer, v_today,
                    v_tag || CASE WHEN NULLIF(v_l->>'lot_number', '') IS NULL THEN ' (LOT 미지정)' ELSE '' END, v_who);
            v_inc_txn := v_inc_txn + 1;
        END LOOP;
    END IF;

    -- ⑥ 전표 라인 수량(EDIT)
    IF v_action = 'EDIT' THEN
        FOR v_si IN SELECT k::integer FROM jsonb_object_keys(v_chg) k ORDER BY 1 LOOP
            UPDATE shipment_items SET qty = (v_chg->v_si::text->>1)::numeric WHERE si_id = v_si;
        END LOOP;
    END IF;

    -- ⑦ 이력(라인마다 1행, 처리 라인 0 인 취소는 머리글 이력 1행)
    v_rev := COALESCE(v_sh.rev_no, 0) + 1;
    IF v_chg = '{}'::jsonb THEN
        INSERT INTO shipment_revisions
            (shipment_id, rev_no, action, si_id, pn, qty_before, qty_after, reason, created_by, request_id, info)
        VALUES (p_shipment_id, v_rev, v_action, NULL, NULL, 0, 0, v_reason, v_who, v_req,
                jsonb_build_object('payload_md5', v_md5, 'info', v_info));
    ELSE
        INSERT INTO shipment_revisions
            (shipment_id, rev_no, action, si_id, pn, qty_before, qty_after, reason, created_by, request_id, info)
        SELECT p_shipment_id, v_rev, v_action, si.si_id, si.pn, (v_chg->si.si_id::text->>0)::numeric,
               (v_chg->si.si_id::text->>1)::numeric, v_reason, v_who, v_req,
               jsonb_build_object('payload_md5', v_md5, 'info', v_info)
          FROM shipment_items si
         WHERE si.si_id IN (SELECT k::integer FROM jsonb_object_keys(v_chg) k)
         ORDER BY si.si_id;
    END IF;

    -- ⑧ 수주 머리글 — 활성 라인만 재집계, 비활성 머리글 무접촉, 활성 라인 없으면 유지
    SELECT COALESCE(array_agg(DISTINCT so_id ORDER BY so_id), '{}') INTO v_sos
      FROM sales_order_items WHERE soi_id = ANY (v_changed);
    UPDATE sales_orders o
       SET status = sub.st
      FROM (SELECT i.so_id,
                   CASE WHEN bool_and(COALESCE(i.received_qty, 0) >= COALESCE(i.qty, 0) - 1e-9) THEN 'DELIVERED'
                        WHEN bool_or(COALESCE(i.received_qty, 0) > 0) THEN 'PARTIAL'
                        ELSE 'DRAFT' END AS st
              FROM sales_order_items i
             WHERE i.so_id = ANY (v_sos)
               AND upper(COALESCE(i.status, '')) NOT IN ('CLOSED', 'CANCELLED', 'REPLACED')
             GROUP BY i.so_id) sub
     WHERE o.so_id = sub.so_id
       AND upper(COALESCE(o.status, '')) NOT IN ('CLOSED', 'CANCELLED', 'CANCELED')
       AND o.status IS DISTINCT FROM sub.st;

    -- ⑨ 전표 머리글
    IF v_action = 'CANCEL' THEN
        UPDATE shipments
           SET rev_no = v_rev, revised_at = v_now, status = 'CANCELLED', cancelled_at = v_now, cancel_reason = v_reason
         WHERE shipment_id = p_shipment_id AND status = 'CONFIRMED';
    ELSE
        UPDATE shipments SET rev_no = v_rev, revised_at = v_now
         WHERE shipment_id = p_shipment_id AND status = 'CONFIRMED';
    END IF;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'postcondition:header' USING ERRCODE = 'P0001';
    END IF;

    -- ⑩ 사후 조건(§18 A1) — 어긋나면 전체 롤백
    IF v_action = 'CANCEL' THEN
        IF EXISTS (SELECT 1 FROM shipment_allocations a JOIN shipment_items si ON si.si_id = a.si_id
                    WHERE si.shipment_id = p_shipment_id) THEN
            RAISE EXCEPTION 'postcondition:alloc_left' USING ERRCODE = 'P0001';
        END IF;
        IF EXISTS (SELECT 1 FROM inventory_transactions t JOIN shipment_items si ON si.si_id = t.ref_id
                    WHERE t.ref_table = 'shipment_items' AND t.txn_type = 'ISSUE' AND si.shipment_id = p_shipment_id
                    GROUP BY si.si_id HAVING abs(SUM(t.qty)) > 1e-9) THEN
            RAISE EXCEPTION 'postcondition:issue_left' USING ERRCODE = 'P0001';
        END IF;
    END IF;
    SELECT count(*) INTO v_n
      FROM sales_order_items l
     WHERE l.soi_id = ANY (v_changed)
       AND (COALESCE(l.received_qty, 0) < -1e-9
            OR CASE WHEN upper(COALESCE(l.status, '')) IN ('CLOSED', 'CANCELLED')
                    THEN COALESCE(l.pending_qty, 0) > 1e-9
                         OR abs(COALESCE(l.closed_qty, 0) - GREATEST(COALESCE(l.qty, 0) - COALESCE(l.received_qty, 0), 0)) > 1e-9
                    WHEN upper(COALESCE(l.status, '')) = 'REPLACED'
                    THEN COALESCE(l.pending_qty, 0) > 1e-9
                    ELSE abs(COALESCE(l.pending_qty, 0) - GREATEST(COALESCE(l.qty, 0) - COALESCE(l.received_qty, 0), 0)) > 1e-9
                         OR COALESCE(l.closed_qty, 0) > 1e-9 END);
    IF v_n > 0 THEN
        RAISE EXCEPTION 'postcondition:line_state' USING ERRCODE = 'P0001';
    END IF;

    SELECT COALESCE(array_agg(DISTINCT so_id ORDER BY so_id), '{}') INTO v_sos
      FROM sales_order_items WHERE soi_id = ANY (v_changed);
    RETURN jsonb_build_object(
        'ok', true, 'replayed', false, 'action', v_action, 'rev_no', v_rev,
        'lines', (SELECT count(*) FROM jsonb_object_keys(v_chg)),
        'restored_txns', v_restored, 'released_allocs', v_released,
        'inc_allocs', v_inc_alloc, 'inc_txns', v_inc_txn,
        'so_ids', to_jsonb(v_sos), 'info', v_info);
END;
$$;

COMMENT ON FUNCTION public.revise_shipment(integer, jsonb) IS
    '확정 출고 전표 정정(EDIT)·취소(CANCEL)를 한 트랜잭션으로(082). 감소는 서버 계산, 증가는 화면 계획을 검증. '
    'request_id 재실행(내용 md5 대조), 데이터 사유·월 마감·부분 취소 거부, 상태별 사후 조건. 실패 시 전부 롤백(P0001 사유)';
REVOKE EXECUTE ON FUNCTION public.revise_shipment(integer, jsonb) FROM PUBLIC, anon, authenticated;
GRANT  EXECUTE ON FUNCTION public.revise_shipment(integer, jsonb) TO service_role;


-- ── ④ 읽기: 고정 데이터 사유만 라인별로(§18 A9) ──
CREATE OR REPLACE FUNCTION public.revise_shipment_check(p_shipment_id integer)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_sh      record;
    v_live    integer[];
    v_reasons jsonb;
    v_lines   jsonb := '{}'::jsonb;
    v_r       jsonb;
    v_id      integer;
BEGIN
    SELECT shipment_id, ship_date, status INTO v_sh FROM shipments WHERE shipment_id = p_shipment_id;
    IF NOT FOUND THEN
        RETURN jsonb_build_object('ok', false, 'error', 'not_found');
    END IF;
    SELECT COALESCE(array_agg(si_id ORDER BY si_id), '{}') INTO v_live
      FROM shipment_items WHERE shipment_id = p_shipment_id AND qty > 1e-9;
    v_reasons := public.revise_shipment_reasons(p_shipment_id, v_live, '{}'::jsonb);
    FOR v_r IN SELECT e FROM jsonb_array_elements(v_reasons) e LOOP
        IF v_r->>'code' = 'round_short' THEN
            FOR v_id IN SELECT DISTINCT a.si_id FROM shipment_allocations a
                         WHERE a.sched_id IN (SELECT x::integer FROM jsonb_array_elements_text(v_r->'ids') x)
                           AND a.si_id = ANY (v_live) ORDER BY 1 LOOP
                v_lines := jsonb_set(v_lines, ARRAY[v_id::text],
                                     COALESCE(v_lines->v_id::text, '[]'::jsonb) || to_jsonb(v_r->>'code'));
            END LOOP;
        ELSE
            FOR v_id IN SELECT x::integer FROM jsonb_array_elements_text(v_r->'ids') x LOOP
                v_lines := jsonb_set(v_lines, ARRAY[v_id::text],
                                     COALESCE(v_lines->v_id::text, '[]'::jsonb) || to_jsonb(v_r->>'code'));
            END LOOP;
        END IF;
    END LOOP;
    RETURN jsonb_build_object(
        'ok', true, 'status', v_sh.status,
        'month_closed', EXISTS (SELECT 1 FROM sales_month_close m WHERE m.ym = to_char(v_sh.ship_date, 'YYYY-MM')),
        'partial_cancel_legacy', v_sh.status = 'CONFIRMED'
            AND EXISTS (SELECT 1 FROM shipment_revisions r WHERE r.shipment_id = p_shipment_id AND r.action = 'CANCEL'),
        'lines', v_lines);
END;
$$;

COMMENT ON FUNCTION public.revise_shipment_check(integer) IS
    '확정 전표를 정정·취소할 수 없는 고정 데이터 사유(legacy_no_alloc·issue_mismatch·round_short)를 라인별로, '
    '월 마감·부분 취소 여부와 함께(082, 읽기 전용). 요청별 사유(recv_underflow 등)는 실행 때만';
REVOKE EXECUTE ON FUNCTION public.revise_shipment_check(integer) FROM PUBLIC, anon, authenticated;
GRANT  EXECUTE ON FUNCTION public.revise_shipment_check(integer) TO service_role;

NOTIFY pgrst, 'reload schema';

-- 적용 후 검증(검토 세션, REST 경유 — 쓰기 없음):
--   select column_name, data_type from information_schema.columns where table_name='shipment_revisions' and column_name in ('request_id','info');
--   select routine_name, grantee from information_schema.routine_privileges
--    where routine_name in ('revise_shipment','revise_shipment_check','revise_shipment_reasons') order by 1,2;
--   POST /rpc/revise_shipment {"p_shipment_id": -1, "p_payload": {"v":"1","action":"CANCEL","request_id":"<uuid>","expected_rev_no":0,"reason":"x"}} → not_found
--   POST /rpc/revise_shipment {실제 확정 전표, expected_rev_no:-1, …} → stale_rev (잠금·권한·열 이름을 ③ 까지 확인)
--   POST /rpc/revise_shipment_check {"p_shipment_id": <옛 전표 12장 각각>} → lines 에 사유
