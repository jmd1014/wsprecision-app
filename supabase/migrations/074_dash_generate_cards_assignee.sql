-- ════════════════════════════════════════════════════════════
-- Migration 074: dash_generate_cards — 담당자 빈 템플릿은 DB 에서도 생성 제외 (2026-10-21, Codex 구현 리뷰 M3)
-- (L3-S 계획서 v2 §10-A C10: docs/development/plans/20261020_L3S_업무루틴_dash.md)
-- ════════════════════════════════════════════════════════════
-- 목적:
--   앱 순수 함수(plan_template_ids)가 생성 대상을 정한 뒤 RPC 를 부르기까지의 사이에 템플릿 담당자가 비워지면
--   담당자 없는 카드가 생길 수 있다(D2 규칙이 경합에서 깨짐). 함수 WHERE 에 `cardinality(assignee_user_ids) > 0`
--   을 더해 DB 가 같은 규칙을 강제한다. 그 외 본문은 073 과 동일(CREATE OR REPLACE 전문 재선언).
-- 적용 조건: dash_cards 0행 확인 뒤(2026-10-21 0행). 기존 데이터 무접촉.
-- 되돌리기: 073 의 함수 본문으로 CREATE OR REPLACE 재선언(이 파일에서 `AND cardinality(...) > 0` 한 줄만 빼면 됨).
-- 멱등: CREATE OR REPLACE — 두 번 적용해도 오류 없음.
-- ════════════════════════════════════════════════════════════

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
      AND cardinality(t.assignee_user_ids) > 0          -- 074: 담당자 빈 템플릿은 DB 에서도 제외(D2)
    ON CONFLICT ON CONSTRAINT dash_cards_routine_key DO NOTHING;
    GET DIAGNOSTICS v_inserted = ROW_COUNT;

    RETURN jsonb_build_object('inserted', v_inserted,
                              'skipped', v_requested - v_inserted,
                              'requested', v_requested,
                              'work_date', p_work_date, 'shift', p_shift);
END;
$$;
COMMENT ON FUNCTION public.dash_generate_cards(date, text, bigint[]) IS
  '업무 루틴 카드 멱등 생성. 활성·교대 일치·담당자 있는 템플릿만(074), 같은 (template_id, work_date, shift) 는 건너뜀. 동시 호출 안전. 반환 {inserted, skipped, requested}.';
REVOKE EXECUTE ON FUNCTION public.dash_generate_cards(date, text, bigint[]) FROM PUBLIC, anon, authenticated;
GRANT  EXECUTE ON FUNCTION public.dash_generate_cards(date, text, bigint[]) TO service_role;

-- 적용 후 검증(개발 세션):
--   select public.dash_generate_cards(current_date, 'night', array(select id from public.dash_routine_templates where cardinality(assignee_user_ids)=0));  -- inserted 0
--   select grantee, privilege_type from information_schema.routine_privileges where routine_name='dash_generate_cards' order by 1;  -- service_role EXECUTE (+ postgres 소유자)
--   select count(*) from public.dash_cards;  -- 0 (검증 호출이 행을 만들지 않았음)
