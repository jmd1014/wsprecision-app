-- ════════════════════════════════════════════════════════════
-- Migration 070: 생산 계획 1차 — 주간 계획·근무 체계 (2026-10-14)
-- (계획서 docs/development/plans/20261014_L2_주간부하리포트.md v4, Data·QA 리뷰 반영)
-- ════════════════════════════════════════════════════════════
-- 단독 기능: 수주·실적과 연결하지 않는다. 운영 데이터 변경 없음(신규 테이블·시드 4행·설비 컬럼 1).
-- ① shift_profiles  요일 유형별 주/야 시간 (시드: 평일 10/10, 토·공휴일 6/6, 휴무 0/0)
-- ② work_calendar   예외일만 저장(공휴일·특근). 없으면 월~금 WEEKDAY, 토 SATURDAY, 일 OFF
-- ③ machines.sat_active  토·공휴일 가동 플래그
-- ④ production_plan_items  주간 계획 행 (작업 = 품번 × 스텝 묶음). hours 는 생성 컬럼.
-- ⑤ save_week_plan RPC  한 트랜잭션 저장 + fingerprint 로 동시 편집 거부
-- 되돌리기(코드 revert 뒤, 스냅샷 뒤 — production_plan_items 전체·shift_profiles·work_calendar·
--   machines 의 sat_active=false 설비 목록을 _주간계획_되돌리기전백업_YYYYMMDD.json 에 보존):
--   DROP FUNCTION IF EXISTS public.save_week_plan(date, text, jsonb, bigint[]);
--   DROP TABLE IF EXISTS public.production_plan_items;
--   DROP TABLE IF EXISTS public.work_calendar;
--   DROP TABLE IF EXISTS public.shift_profiles;
--   ALTER TABLE public.machines DROP COLUMN IF EXISTS sat_active;
-- ════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.shift_profiles (
    day_type    text PRIMARY KEY
                CHECK (day_type IN ('WEEKDAY','SATURDAY','HOLIDAY','OFF')),
    day_hours   numeric NOT NULL DEFAULT 0 CHECK (day_hours BETWEEN 0 AND 24),
    night_hours numeric NOT NULL DEFAULT 0 CHECK (night_hours BETWEEN 0 AND 24),
    note        text,
    updated_at  timestamptz NOT NULL DEFAULT now()
);
INSERT INTO public.shift_profiles (day_type, day_hours, night_hours, note) VALUES
  ('WEEKDAY', 10, 10, '평일 주/야 2교대'),
  ('SATURDAY', 6, 6, '토요일 주/야 2교대'),
  ('HOLIDAY', 6, 6, '공휴일 주/야 2교대'),
  ('OFF', 0, 0, '휴무(일요일)')
ON CONFLICT (day_type) DO NOTHING;
ALTER TABLE public.shift_profiles ENABLE ROW LEVEL SECURITY;
COMMENT ON TABLE public.shift_profiles IS '근무 체계 — 요일 유형별 주/야 가용 시간 (생산 계획 능력 계산). 시드 4행, 설비 탭에서 편집.';

CREATE TABLE IF NOT EXISTS public.work_calendar (
    cal_date   date PRIMARY KEY,
    day_type   text NOT NULL REFERENCES public.shift_profiles(day_type),
    note       text,
    created_by text,
    created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.work_calendar ENABLE ROW LEVEL SECURITY;
COMMENT ON TABLE public.work_calendar IS '근무 예외일(공휴일·특근·휴무)만 저장. 없는 날짜는 요일 규칙(월~금 평일, 토, 일 휴무).';

ALTER TABLE public.machines
    ADD COLUMN IF NOT EXISTS sat_active boolean NOT NULL DEFAULT true;
COMMENT ON COLUMN public.machines.sat_active IS '토·공휴일 가동(주간 계획 능력). shifts·hours_per_shift 는 설비 스케줄 보드의 구기준(교대당 9h).';

CREATE TABLE IF NOT EXISTS public.production_plan_items (
    plan_item_id bigserial PRIMARY KEY,
    week_start   date NOT NULL CHECK (extract(isodow FROM week_start) = 1),
    product_id   text REFERENCES public.products(product_id),
    pn           text NOT NULL CHECK (pn = btrim(pn) AND pn <> ''),
    steps        int[] NOT NULL DEFAULT '{}',
    op_label     text NOT NULL,
    op_key       text NOT NULL,
    seq          int  NOT NULL DEFAULT 0,
    group_code   text NOT NULL CHECK (group_code ~ '^[A-Z][A-Z0-9]{0,9}$'),
    qty          numeric NOT NULL CHECK (qty >= 0),
    uph          numeric CHECK (uph IS NULL OR uph > 0),
    uph_source   text CHECK (uph_source IN ('CONFIRMED','SHEET','AUTO','MANUAL','EST')),
    setup_min    numeric NOT NULL DEFAULT 0 CHECK (setup_min >= 0),
    hours        numeric GENERATED ALWAYS AS
                 (CASE WHEN uph > 0 AND qty > 0 THEN round(qty / uph + setup_min / 60.0, 2)
                       WHEN uph > 0 THEN 0 END) STORED,
    due_date     date,
    note         text,
    created_by   text,
    updated_by   text,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    CHECK ((uph IS NULL) = (uph_source IS NULL)),
    CHECK (op_label = pn || CASE WHEN cardinality(steps) = 0 THEN ''
                                 ELSE '#' || array_to_string(steps, '#') END)
);
CREATE INDEX IF NOT EXISTS production_plan_items_week_grp_idx
    ON public.production_plan_items (week_start, group_code);
CREATE INDEX IF NOT EXISTS production_plan_items_week_key_idx
    ON public.production_plan_items (week_start, op_key);
CREATE INDEX IF NOT EXISTS production_plan_items_product_idx
    ON public.production_plan_items (product_id) WHERE product_id IS NOT NULL;
ALTER TABLE public.production_plan_items ENABLE ROW LEVEL SECURITY;
COMMENT ON TABLE public.production_plan_items IS '주간 생산 계획 행 — 작업(품번×스텝 묶음)별 장비군·수량·UPH(참고값, 수정 가능). hours 는 생성 컬럼. 수주·실적과 미연결(1차). 실적 매칭(2차)은 (product_id, steps) 로 매번 계산하고 op_key 는 product_id 없는 행의 보조 키로만.';

-- ⑤ 한 트랜잭션 저장. p_rows: [{plan_item_id|null, product_id, pn, steps[], op_label, op_key, seq,
--    group_code, qty, uph, uph_source, setup_min, due_date, note, by}], p_delete: 삭제할 id.
--    fingerprint = count:sum(id):floor(epoch(max(updated_at))) — 문자열 형식에 의존하지 않도록
--    초 단위 정수(앱 utils.weekly_plan.fingerprint 와 동일)
DROP FUNCTION IF EXISTS public.save_week_plan(date, text, jsonb, bigint[]);
CREATE FUNCTION public.save_week_plan(p_week date, p_fingerprint text, p_rows jsonb, p_delete bigint[])
RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_fp     text;
    v_row    jsonb;
    v_id     bigint;
    v_steps  int[];
    v_label  text;
    v_now    timestamptz := now();
    n_ins    int := 0;
    n_upd    int := 0;
    n_del    int := 0;
BEGIN
    IF p_week IS NULL OR extract(isodow FROM p_week) <> 1 THEN
        RAISE EXCEPTION 'bad_week' USING ERRCODE = 'P0001';
    END IF;
    IF p_rows IS NULL OR jsonb_typeof(p_rows) <> 'array' THEN
        RAISE EXCEPTION 'bad_rows' USING ERRCODE = 'P0001';
    END IF;
    -- 주 전체를 잠그고 fingerprint 비교 (다른 사용자가 먼저 저장했으면 거부)
    PERFORM pg_advisory_xact_lock(hashtext('week_plan'), hashtext(p_week::text));
    SELECT count(*)::text || ':' || COALESCE(sum(plan_item_id), 0)::text || ':'
           || COALESCE(floor(extract(epoch FROM max(updated_at)))::bigint::text, '')
      INTO v_fp
      FROM production_plan_items WHERE week_start = p_week;
    IF p_fingerprint IS DISTINCT FROM v_fp THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'P0001',
            HINT = format('server %s client %s', v_fp, p_fingerprint);
    END IF;

    FOR v_row IN SELECT r FROM jsonb_array_elements(p_rows) r LOOP
        v_id := NULLIF(v_row->>'plan_item_id', '')::bigint;
        SELECT COALESCE(array_agg(DISTINCT x::int ORDER BY x::int), '{}')
          INTO v_steps
          FROM jsonb_array_elements_text(
                 CASE WHEN jsonb_typeof(v_row->'steps') = 'array' THEN v_row->'steps'
                      ELSE '[]'::jsonb END) x;
        v_label := btrim(v_row->>'pn') || CASE WHEN cardinality(v_steps) = 0 THEN ''
                                               ELSE '#' || array_to_string(v_steps, '#') END;
        IF v_id IS NULL THEN
            INSERT INTO production_plan_items
                (week_start, product_id, pn, steps, op_label, op_key, seq, group_code, qty,
                 uph, uph_source, setup_min, due_date, note, created_by, updated_by)
            VALUES (p_week, NULLIF(v_row->>'product_id', ''), btrim(v_row->>'pn'), v_steps,
                    v_label, v_row->>'op_key',
                    COALESCE((v_row->>'seq')::int, 0), upper(v_row->>'group_code'),
                    (v_row->>'qty')::numeric, NULLIF(v_row->>'uph', '')::numeric,
                    NULLIF(v_row->>'uph_source', ''),
                    COALESCE(NULLIF(v_row->>'setup_min', '')::numeric, 0),
                    NULLIF(v_row->>'due_date', '')::date, NULLIF(v_row->>'note', ''),
                    v_row->>'by', v_row->>'by');
            n_ins := n_ins + 1;
        ELSE
            UPDATE production_plan_items
               SET product_id = NULLIF(v_row->>'product_id', ''), pn = btrim(v_row->>'pn'),
                   steps = v_steps, op_label = v_label, op_key = v_row->>'op_key',
                   seq = COALESCE((v_row->>'seq')::int, 0),
                   group_code = upper(v_row->>'group_code'),
                   qty = (v_row->>'qty')::numeric, uph = NULLIF(v_row->>'uph', '')::numeric,
                   uph_source = NULLIF(v_row->>'uph_source', ''),
                   setup_min = COALESCE(NULLIF(v_row->>'setup_min', '')::numeric, 0),
                   due_date = NULLIF(v_row->>'due_date', '')::date,
                   note = NULLIF(v_row->>'note', ''),
                   updated_by = v_row->>'by', updated_at = v_now
             WHERE plan_item_id = v_id AND week_start = p_week;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'row_missing:%', v_id USING ERRCODE = 'P0001';
            END IF;
            n_upd := n_upd + 1;
        END IF;
    END LOOP;

    IF p_delete IS NOT NULL AND cardinality(p_delete) > 0 THEN
        DELETE FROM production_plan_items
         WHERE week_start = p_week AND plan_item_id = ANY(p_delete);
        GET DIAGNOSTICS n_del = ROW_COUNT;
    END IF;

    RETURN jsonb_build_object('ok', true, 'inserted', n_ins, 'updated', n_upd,
                              'deleted', n_del, 'saved_at', v_now);
END;
$$;
COMMENT ON FUNCTION public.save_week_plan(date, text, jsonb, bigint[]) IS
    '주간 계획 저장(한 트랜잭션): fingerprint 비교 → upsert → delete. 거부 사유 stale/bad_week/bad_rows/row_missing.';
REVOKE EXECUTE ON FUNCTION public.save_week_plan(date, text, jsonb, bigint[]) FROM PUBLIC, anon, authenticated;
GRANT  EXECUTE ON FUNCTION public.save_week_plan(date, text, jsonb, bigint[]) TO service_role;
