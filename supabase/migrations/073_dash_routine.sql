-- ════════════════════════════════════════════════════════════
-- Migration 073: 업무 루틴(업무 대시보드 1단계) — dash_ 테이블 4개 + 멱등 생성 RPC + 시드  (2026-10-21 적용)
-- (L3-S 계획서 v2: docs/development/plans/20261020_L3S_업무루틴_dash.md)
-- ════════════════════════════════════════════════════════════
-- 계획서 v2(Codex 계획 리뷰 2026-10-20 반영): RPC 입력을 template_id 배열로(템플릿에서 스냅샷 복사),
--   완료자 정합 CHECK, 카드에 done_criteria·seq 스냅샷, SECURITY INVOKER + search_path, 검증 쿼리 확장.
-- 목적:
--   생산 파트 데일리 루틴(주간 7·야간 4)을 교대별 카드로 생성하고, 담당자가 체크한다.
-- 데이터 원칙:
--   dash_ 테이블에만 쓴다. 기존 테이블은 읽기 전용(FK 없음 — 사용자 테이블이 없고 계정은 app_settings.auth_users JSON).
--   담당자 ID = auth_users 의 키(username). 앱이 템플릿 저장 시 검증한다.
-- 보안:
--   RLS ENABLE, 정책 없음 → service_role 만 읽고 쓴다(067·070 과 동일). 권한(담당자·관리자·교대 시각)은 앱 코드에서 강제.
-- 시간:
--   work_date·shift 는 앱의 shift_slot(KST 07:30/19:30 경계)이 정한다. completed_at 은 timestamptz.
-- 되돌리기:
--   ** 카드가 한 건이라도 생성된 뒤에는 DROP 하지 않는다 ** — 기본 복구는 코드 revert + DB 유지.
--   첫 생성 전(select count(*) from dash_cards = 0)에만 아래 역순 DROP 허용:
--   DROP FUNCTION IF EXISTS public.dash_generate_cards(date, text, bigint[]);
--   DROP TABLE IF EXISTS public.dash_card_activity;
--   DROP TABLE IF EXISTS public.dash_cards;
--   DROP TABLE IF EXISTS public.dash_routine_templates;
--   DROP TABLE IF EXISTS public.dash_parts;
-- 멱등: IF NOT EXISTS + ON CONFLICT DO NOTHING — 두 번 적용해도 오류 없음.
-- ════════════════════════════════════════════════════════════

-- 1) 파트 ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.dash_parts (
    id              bigserial PRIMARY KEY,
    code            text NOT NULL UNIQUE
                    CHECK (code IN ('production','quality','equipment','management')),
    name            text NOT NULL,
    manager_user_id text,                              -- auth_users 키(username), 앱 검증
    sort_order      integer NOT NULL DEFAULT 0,
    created_at      timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.dash_parts ENABLE ROW LEVEL SECURITY;
COMMENT ON TABLE  public.dash_parts IS '업무 루틴 파트(생산/품질/설비/관리). 1단계는 생산만 사용. 권한은 앱 코드에서 강제.';
COMMENT ON COLUMN public.dash_parts.manager_user_id IS 'auth_users 키(username). FK 불가 — 앱이 저장 시 검증.';

-- 2) 루틴 템플릿 ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.dash_routine_templates (
    id                bigserial PRIMARY KEY,
    code              text NOT NULL UNIQUE,            -- 시드 prod_day_NN / 앱 추가 {part}_{shift}_{uuid8}
    part_id           bigint NOT NULL REFERENCES public.dash_parts(id) ON DELETE RESTRICT,
    shift             text NOT NULL CHECK (shift IN ('day','night')),
    seq               integer NOT NULL DEFAULT 0,      -- 표시 순서(unique 아님 — 순서 교환 허용)
    title             text NOT NULL CHECK (length(btrim(title)) > 0),
    done_criteria     text,
    assignee_user_ids text[] NOT NULL DEFAULT '{}',    -- auth_users 키 배열, 앱 검증. 빈 배열이면 생성 제외(앱 plan_rows)
    active_rule       text NOT NULL DEFAULT 'always' CHECK (active_rule IN ('always','pre_holiday')),
    active            boolean NOT NULL DEFAULT true,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS dash_routine_templates_part_shift_idx
    ON public.dash_routine_templates (part_id, shift, active, seq);
ALTER TABLE public.dash_routine_templates ENABLE ROW LEVEL SECURITY;
COMMENT ON TABLE  public.dash_routine_templates IS '루틴 항목 템플릿. 삭제 대신 active=false. 수정은 이후 생성 카드에만 반영(카드는 제목·기준·순서·담당자를 생성 시점 스냅샷으로 가짐).';
COMMENT ON COLUMN public.dash_routine_templates.active_rule IS 'always=매 교대 생성, pre_holiday=다음 날 day_type 이 OFF/HOLIDAY 일 때만 생성(앱 순수 함수가 판정).';

-- 3) 카드 ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.dash_cards (
    id                bigserial PRIMARY KEY,
    type              text NOT NULL DEFAULT 'routine' CHECK (type IN ('routine','project','monthly')),
    part_id           bigint NOT NULL REFERENCES public.dash_parts(id) ON DELETE RESTRICT,
    template_id       bigint REFERENCES public.dash_routine_templates(id) ON DELETE RESTRICT,
    work_date         date,
    shift             text CHECK (shift IN ('day','night')),
    seq               integer NOT NULL DEFAULT 0,       -- 스냅샷
    title             text NOT NULL,                    -- 스냅샷
    done_criteria     text,                             -- 스냅샷
    status            text NOT NULL DEFAULT 'todo' CHECK (status IN ('todo','done')),
    assignee_user_ids text[] NOT NULL DEFAULT '{}',     -- 스냅샷(권한 판정은 이 값으로)
    completed_by      text,                             -- auth_users 키(username)
    completed_at      timestamptz,
    created_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT dash_cards_routine_key UNIQUE (template_id, work_date, shift),
    CONSTRAINT dash_cards_done_at_consistent CHECK ((status = 'done') = (completed_at IS NOT NULL)),
    CONSTRAINT dash_cards_done_by_consistent CHECK ((status = 'done') = (completed_by IS NOT NULL)),
    CONSTRAINT dash_cards_routine_fields CHECK (
        type <> 'routine' OR (template_id IS NOT NULL AND work_date IS NOT NULL AND shift IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS dash_cards_date_shift_idx ON public.dash_cards (work_date, shift);
ALTER TABLE public.dash_cards ENABLE ROW LEVEL SECURITY;
COMMENT ON TABLE  public.dash_cards IS '교대별 루틴 카드. (template_id, work_date, shift) 유니크 = 멱등 생성 키. 미완료는 이월하지 않음(다음 교대 화면에 "어제 미완료"로만 표시). 생성 뒤 DROP 금지(기록).';
COMMENT ON COLUMN public.dash_cards.completed_by IS '선착 완료자(username). 앱은 status=todo 조건부 UPDATE(update_count) 로만 done 처리, 취소는 status=done & completed_at 일치 조건.';

-- 4) 체크 활동 로그 ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.dash_card_activity (
    id          bigserial PRIMARY KEY,
    card_id     bigint NOT NULL REFERENCES public.dash_cards(id) ON DELETE RESTRICT,
    user_id     text NOT NULL CHECK (length(btrim(user_id)) > 0),   -- username
    action      text NOT NULL CHECK (action IN ('done','undo')),
    from_value  text,                                   -- 'todo' | 'done'
    to_value    text,                                   -- 'done' | 'todo'
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS dash_card_activity_card_idx ON public.dash_card_activity (card_id, created_at);
ALTER TABLE public.dash_card_activity ENABLE ROW LEVEL SECURITY;
COMMENT ON TABLE public.dash_card_activity IS '체크/체크 취소 기록(append-only). 카드 UPDATE 가 1행 성공했을 때만 INSERT — 실패 시 앱이 flash warning + log_error(조용히 삼키지 않음).';

-- 5) 멱등 생성 RPC ──────────────────────────────────────────
-- 앱(순수 함수)이 "이 슬롯에 생성할 템플릿 id 목록"을 정하고, DB 가 템플릿에서 스냅샷을 복사해 삽입한다.
-- part·title·기준·순서·담당자를 앱이 넘기지 않으므로 템플릿↔파트 불일치가 생길 수 없다.
CREATE OR REPLACE FUNCTION public.dash_generate_cards(p_work_date date, p_shift text, p_template_ids bigint[])
RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_inserted  integer := 0;
    v_requested integer := 0;
BEGIN
    IF p_work_date IS NULL THEN
        RAISE EXCEPTION 'dash_generate_cards: work_date 필수';
    END IF;
    IF p_shift IS NULL OR p_shift NOT IN ('day','night') THEN
        RAISE EXCEPTION 'dash_generate_cards: shift 는 day/night 만 (%)', p_shift;
    END IF;
    v_requested := COALESCE(array_length(p_template_ids, 1), 0);
    IF v_requested = 0 THEN
        RETURN jsonb_build_object('inserted', 0, 'skipped', 0, 'requested', 0,
                                  'work_date', p_work_date, 'shift', p_shift);
    END IF;

    INSERT INTO public.dash_cards
        (type, part_id, template_id, work_date, shift, seq, title, done_criteria, assignee_user_ids)
    SELECT 'routine', t.part_id, t.id, p_work_date, p_shift, t.seq, t.title, t.done_criteria, t.assignee_user_ids
    FROM public.dash_routine_templates t
    WHERE t.id = ANY (p_template_ids)
      AND t.active
      AND t.shift = p_shift
    ON CONFLICT ON CONSTRAINT dash_cards_routine_key DO NOTHING;
    GET DIAGNOSTICS v_inserted = ROW_COUNT;

    RETURN jsonb_build_object('inserted', v_inserted,
                              'skipped', v_requested - v_inserted,
                              'requested', v_requested,
                              'work_date', p_work_date, 'shift', p_shift);
END;
$$;
COMMENT ON FUNCTION public.dash_generate_cards(date, text, bigint[]) IS
  '업무 루틴 카드 멱등 생성. 활성·교대 일치 템플릿만, 같은 (template_id, work_date, shift) 는 건너뜀. 동시 호출 안전. 반환 {inserted, skipped, requested}.';
REVOKE EXECUTE ON FUNCTION public.dash_generate_cards(date, text, bigint[]) FROM PUBLIC, anon, authenticated;
GRANT  EXECUTE ON FUNCTION public.dash_generate_cards(date, text, bigint[]) TO service_role;

-- 6) 시드 ─────────────────────────────────────────────────────
INSERT INTO public.dash_parts (code, name, sort_order) VALUES
    ('production', '생산', 1),
    ('quality',    '품질', 2),
    ('equipment',  '설비', 3),
    ('management', '관리', 4)
ON CONFLICT (code) DO NOTHING;

-- 담당자: 주간 = 김준오(auth_users 키 확인, 2026-10-19). 야간 = 계정 발급(D2) 뒤 템플릿 관리에서 지정 → 시드는 빈 배열
-- (빈 배열 템플릿은 앱 plan_rows 가 생성에서 제외 → 지정 뒤 다음 진입에서 생성).
INSERT INTO public.dash_routine_templates (code, part_id, shift, seq, title, done_criteria, assignee_user_ids, active_rule)
SELECT v.code, p.id, v.shift, v.seq, v.title, v.done_criteria, v.assignees, v.rule
FROM (VALUES
    ('prod_day_01',   'day',   1, '야간 인수 확인',              '야간 특이사항·설비 알람 유무를 회의록에 반영',                        ARRAY['김준오']::text[], 'always'),
    ('prod_day_02',   'day',   2, '현장 회의록 게시',            '인원·출고·특이사항 3단 양식으로 #생산-일반 게시, 09:00까지',         ARRAY['김준오']::text[], 'always'),
    ('prod_day_03',   'day',   3, '당일 출고 수량·검사 확인',    '출고 품목별 수량 체크, 외주 출고 포함',                               ARRAY['김준오']::text[], 'always'),
    ('prod_day_04',   'day',   4, '소재·공정 대기 재고 확인',    '부족 품목은 비가동 여부 판단 후 기록',                                 ARRAY['김준오']::text[], 'always'),
    ('prod_day_05',   'day',   5, '전일 불량 내역 등록',         '품번·불량 유형·수량을 #생산-공정관리에 게시',                          ARRAY['김준오']::text[], 'always'),
    ('prod_day_06',   'day',   6, '출퇴근·연장근무 승인 확인',   '타임인아웃 누락·수정 요청 처리',                                       ARRAY['김준오']::text[], 'always'),
    ('prod_day_07',   'day',   7, '연장·야간 편성 라인 게시',    '라인별 설비·품번·공정 게시, 19:30 전',                                  ARRAY['김준오']::text[], 'always'),
    ('prod_night_01', 'night', 1, '편성 라인 가동 확인',         '게시된 편성대로 가동 시작, 변경 시 사유 기록',                          '{}'::text[],            'always'),
    ('prod_night_02', 'night', 2, '자동화 라인 알람 기록',       '로봇·설비 알람 발생 호기와 조치 기록',                                  '{}'::text[],            'always'),
    ('prod_night_03', 'night', 3, '퇴근 전 특이사항 남기기',     '다음 날 회의록에 넘길 내용 1줄 이상',                                   '{}'::text[],            'always'),
    ('prod_night_04', 'night', 4, '휴무 전 문단속·인수인계',     '토요일·공휴일 전날만 활성',                                             '{}'::text[],            'pre_holiday')
) AS v(code, shift, seq, title, done_criteria, assignees, rule)
JOIN public.dash_parts p ON p.code = 'production'
ON CONFLICT (code) DO NOTHING;

-- 7) 적용 후 검증(개발 세션, 리뷰 패키지에 결과 첨부) ───────────
--   -- 테이블 4·RLS on·정책 0
--   select c.relname, c.relrowsecurity, (select count(*) from pg_policies p where p.tablename=c.relname) as policies
--     from pg_class c join pg_namespace n on n.oid=c.relnamespace
--    where n.nspname='public' and c.relkind='r' and c.relname like 'dash\_%' order by 1;         -- 4행, true, 0
--   -- 제약·인덱스
--   select conrelid::regclass, conname, pg_get_constraintdef(oid) from pg_constraint
--    where conrelid::regclass::text like 'dash\_%' order by 1,2;
--   select tablename, indexname from pg_indexes where tablename like 'dash\_%' order by 1,2;
--   -- 시드 분포
--   select count(*) from public.dash_parts;                                                        -- 4
--   select shift, active_rule, cardinality(assignee_user_ids) as n_assignee, count(*)
--     from public.dash_routine_templates group by 1,2,3 order by 1,2,3;                            -- day/always/1 ×7, night/always/0 ×3, night/pre_holiday/0 ×1
--   -- 함수 권한
--   select grantee, privilege_type from information_schema.routine_privileges
--    where routine_name='dash_generate_cards' order by 1;                                          -- service_role EXECUTE 만
--   -- 멱등 호출(빈 배열 → 쓰기 없음)
--   select public.dash_generate_cards(current_date, 'day', '{}'::bigint[]);                        -- inserted 0
--   -- 불변식(적용 직후 0)
--   select count(*) from public.dash_cards where (status='done') <> (completed_by is not null);    -- 0
--   show timezone;
