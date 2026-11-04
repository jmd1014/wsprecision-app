-- ════════════════════════════════════════════════════════════
-- Migration 081: 다른 제품의 공정·라우팅 복사 RPC (마스터 관리 소수정 묶음 후보 32, 2026-11-04)
-- 기준: _마스터관리_소수정_묶음_지시문_r1_20261104.md §2 + 19:40 추록(소재행 복사) + Codex 1차 H1·H2 결정(제안 A)
--       + _마스터관리_소수정_리뷰분류_및_r2지시_20261105.md(r2 ④·⑨·⑩·⑪·⑫, Codex 2차 H1)
-- ════════════════════════════════════════════════════════════
-- 문제(Codex 1차): 화면의 두 단계 insert(bom → 재조회 → product_routing)는 원자성이 없어 ① 다른 세션이 같은 대상에
--   넣은 BOM 을 실패 정리 때 함께 지우고 ② 재조회 실패·rerun 중단·응답 유실 때 BOM 만 남았다.
-- 설계: copy_product_routing — 한 트랜잭션.
--   ① 원본·대상 products 행을 product_id 오름차순으로 FOR UPDATE — 같은 제품에 대한 동시 RPC 호출만 직렬화한다
--      (화면의 BOM 편집 저장은 이 잠금을 쓰지 않는다; 원본 쪽 일관성은 ③의 FOR SHARE 스냅샷이 맡는다)
--   ② 차단 조건 서버 재검사(대상)
--   ③ 원본 라우팅·공정행·소재행을 각각 한 번 읽어(FOR SHARE) jsonb 배열 스냅샷으로 — 이후 검사·복사는 스냅샷만 쓴다
--   ④ p_with_mat 이면(대상 BOM 이 완전히 비었을 때만) 원본 소재행 복사(verification_status 'AUTO-추정').
--      소재행 이름·제품 소재 표기(products.raw_material_name·bom_material_name) 모두
--      COALESCE(materials.raw_name, bom.raw_material_name) — 화면의 소재행 추가·교체 경로와 같은 원천(진실=자재 마스터)
--      휴면 자재(materials.archived_at)를 가리키는 소재행이 있으면 거부(source_material_archived)
--   ⑤ 원본 공정행(process_type<>'MATERIAL', bom_id 오름차순) insert … RETURNING → 원본 bom_id → 새 bom_id 매핑
--      (업체·단가 NULL, source 'MANUAL', verification_status·lot_label 원본값 — KG·CH 기준이면 수량의 뜻)
--   ⑥ product_routing insert — 스냅샷의 seq·step_*·stage, bom_id = 매핑값(원본 공정행에 없으면 NULL → unmapped 로 셈),
--      default_vendor NULL, confirmed true
--   ⑦ master_change_log 1행(product_routing, 대상 id, 'routing', 'N단계 복사 from 원본 pn', changed_by 빈 값이면 '-')
-- 거부 사유(ERRCODE P0001, message): bad_args · not_found(HINT 제품 id) · archived(HINT 제품 id) · target_has_routing ·
--   target_has_process · target_not_empty(소재행 복사인데 대상 BOM 있음) · source_no_routing · source_unconfirmed ·
--   source_material_archived(HINT 자재 id)
-- 반환: {"proc": 공정행 수, "mat": 소재행 수, "routing": 라우팅 단계 수, "unmapped": 연결 없이 복사한 단계 수,
--        "src_pn", "tgt_pn"}
-- 멱등성: 두 번째 호출은 target_has_routing 으로 거부된다(응답 유실 뒤 재조회 판정은 화면이 대상 라우팅 유무로).
-- 보안: SECURITY INVOKER + search_path 고정, anon/authenticated 실행 차단, service_role 만(069·076 과 동일).
-- 되돌리기: DROP FUNCTION IF EXISTS public.copy_product_routing(text, text, boolean, text);
--   (앱은 RpcUnavailable 이면 "복사 기능을 쓸 수 없음" 안내만 — 폴백 없음. 이미 복사된 BOM·라우팅은 그대로 남는다)
--
-- 적용 후 검증(076 형식):
--   V1 함수·보안: select p.prosecdef, p.proconfig, has_function_privilege('anon', p.oid, 'execute') as anon_exec,
--        has_function_privilege('service_role', p.oid, 'execute') as svc_exec
--        from pg_proc p where p.proname = 'copy_product_routing';
--      기대: prosecdef false · proconfig {search_path=public, pg_temp} · anon_exec false · svc_exec true
--   V2 설명: select obj_description('public.copy_product_routing(text,text,boolean,text)'::regprocedure, 'pg_proc');
--   V3 거부 경로(쓰기 없음): select public.copy_product_routing('X', 'X', false, 'verify');  → bad_args
--   V4 PostgREST: POST /rest/v1/rpc/copy_product_routing {"p_src":"X","p_tgt":"X","p_with_mat":false,"p_who":"v"}
--      → 400 P0001 bad_args (404 PGRST202 면 스키마 캐시 미반영 — NOTIFY pgrst, 'reload schema')
-- ════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION public.copy_product_routing(p_src text, p_tgt text, p_with_mat boolean, p_who text)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_src_pn   text;
    v_tgt_pn   text;
    v_src_arch timestamptz;
    v_tgt_arch timestamptz;
    v_with_mat boolean := COALESCE(p_with_mat, false);
    v_map      jsonb := '{}'::jsonb;
    v_rts      jsonb := '[]'::jsonb;
    v_procs    jsonb := '[]'::jsonb;
    v_mats     jsonb := '[]'::jsonb;
    v_new      integer;
    v_proc     integer := 0;
    v_mat      integer := 0;
    v_rt       integer := 0;
    v_unmapped integer := 0;
    v_first    text;
    v_bad_mat  text;
    v_who      text := COALESCE(NULLIF(btrim(COALESCE(p_who, '')), ''), '-');
    r          record;
    e          jsonb;
BEGIN
    IF p_src IS NULL OR p_tgt IS NULL OR p_src = p_tgt THEN
        RAISE EXCEPTION 'bad_args' USING ERRCODE = 'P0001', HINT = 'p_src·p_tgt 필요, 서로 달라야 함';
    END IF;

    -- ① 원본·대상 products 잠금 — product_id 오름차순(교차 복사 A→B·B→A 동시 호출의 교착 방지)
    PERFORM 1 FROM products WHERE product_id IN (p_src, p_tgt) ORDER BY product_id FOR UPDATE;
    SELECT pn, archived_at INTO v_tgt_pn, v_tgt_arch FROM products WHERE product_id = p_tgt;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'not_found' USING ERRCODE = 'P0001', HINT = p_tgt;
    END IF;
    SELECT pn, archived_at INTO v_src_pn, v_src_arch FROM products WHERE product_id = p_src;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'not_found' USING ERRCODE = 'P0001', HINT = p_src;
    END IF;
    IF v_tgt_arch IS NOT NULL OR v_src_arch IS NOT NULL THEN
        RAISE EXCEPTION 'archived' USING ERRCODE = 'P0001',
            HINT = CASE WHEN v_tgt_arch IS NOT NULL THEN p_tgt ELSE p_src END;
    END IF;

    -- ② 차단 조건(덮어쓰기 없음) — 대상
    IF EXISTS (SELECT 1 FROM product_routing WHERE product_id = p_tgt) THEN
        RAISE EXCEPTION 'target_has_routing' USING ERRCODE = 'P0001';
    END IF;
    IF EXISTS (SELECT 1 FROM bom WHERE product_id = p_tgt AND COALESCE(process_type, 'MATERIAL') <> 'MATERIAL') THEN
        RAISE EXCEPTION 'target_has_process' USING ERRCODE = 'P0001';
    END IF;
    IF v_with_mat AND EXISTS (SELECT 1 FROM bom WHERE product_id = p_tgt) THEN
        RAISE EXCEPTION 'target_not_empty' USING ERRCODE = 'P0001';
    END IF;

    -- ③ 원본 스냅샷(Codex 2차 H1·r2 ⑩): 행을 FOR SHARE 로 잠그고 한 번 읽은 값으로만 검사·복사한다
    FOR r IN SELECT * FROM product_routing WHERE product_id = p_src ORDER BY seq FOR SHARE LOOP
        v_rts := v_rts || jsonb_build_array(to_jsonb(r));
    END LOOP;
    FOR r IN SELECT * FROM bom WHERE product_id = p_src AND COALESCE(process_type, 'MATERIAL') <> 'MATERIAL'
             ORDER BY bom_id FOR SHARE LOOP
        v_procs := v_procs || jsonb_build_array(to_jsonb(r));
    END LOOP;
    IF v_with_mat THEN
        FOR r IN SELECT b.*, m.raw_name AS m_raw_name, m.archived_at AS m_archived_at
                   FROM bom b LEFT JOIN materials m ON m.material_id = b.material_id
                  WHERE b.product_id = p_src AND COALESCE(b.process_type, 'MATERIAL') = 'MATERIAL'
                  ORDER BY b.bom_id FOR SHARE OF b LOOP
            v_mats := v_mats || jsonb_build_array(to_jsonb(r));
        END LOOP;
    END IF;
    IF jsonb_array_length(v_rts) = 0 THEN
        RAISE EXCEPTION 'source_no_routing' USING ERRCODE = 'P0001';
    END IF;
    IF EXISTS (SELECT 1 FROM jsonb_array_elements(v_rts) x WHERE NOT COALESCE((x ->> 'confirmed')::boolean, false)) THEN
        RAISE EXCEPTION 'source_unconfirmed' USING ERRCODE = 'P0001';
    END IF;
    SELECT x ->> 'material_id' INTO v_bad_mat
      FROM jsonb_array_elements(v_mats) x
     WHERE x ->> 'm_archived_at' IS NOT NULL
     LIMIT 1;
    IF v_bad_mat IS NOT NULL THEN
        RAISE EXCEPTION 'source_material_archived' USING ERRCODE = 'P0001', HINT = v_bad_mat;
    END IF;

    -- ④ 소재행(선택) — 공정행보다 먼저(화면 표시 순서 = 소재 → 공정)
    FOR e IN SELECT x FROM jsonb_array_elements(v_mats) x LOOP
        INSERT INTO bom (product_id, material_id, raw_material_name, qty_per_pc, shared_factor, source,
                         verification_status, process_type, unit_price, lot_label, process_vendor_id)
        VALUES (p_tgt, e ->> 'material_id',
                COALESCE(NULLIF(btrim(e ->> 'm_raw_name'), ''), e ->> 'raw_material_name'),
                (e ->> 'qty_per_pc')::numeric, (e ->> 'shared_factor')::numeric, 'MANUAL',
                'AUTO-추정', 'MATERIAL', NULL, e ->> 'lot_label', NULL);
        v_mat := v_mat + 1;
        IF v_first IS NULL THEN
            v_first := COALESCE(NULLIF(btrim(e ->> 'm_raw_name'), ''), e ->> 'raw_material_name');
        END IF;
    END LOOP;
    IF v_first IS NOT NULL THEN
        UPDATE products SET raw_material_name = v_first, bom_material_name = v_first WHERE product_id = p_tgt;
    END IF;

    -- ⑤ 공정행 + 매핑
    FOR e IN SELECT x FROM jsonb_array_elements(v_procs) x LOOP
        INSERT INTO bom (product_id, material_id, raw_material_name, qty_per_pc, shared_factor, source,
                         verification_status, process_type, unit_price, lot_label, process_vendor_id)
        VALUES (p_tgt, NULL, e ->> 'raw_material_name', (e ->> 'qty_per_pc')::numeric,
                (e ->> 'shared_factor')::numeric, 'MANUAL', e ->> 'verification_status', e ->> 'process_type',
                NULL, e ->> 'lot_label', NULL)
        RETURNING bom_id INTO v_new;
        v_map := v_map || jsonb_build_object(e ->> 'bom_id', v_new);
        v_proc := v_proc + 1;
    END LOOP;

    -- ⑥ 라우팅 — 스냅샷에서. 원본 공정행에 없는 bom_id(소재행 연결 등)는 NULL 로 복사하고 unmapped 로 센다(r2 ⑨)
    SELECT count(*) INTO v_unmapped
      FROM jsonb_array_elements(v_rts) x
     WHERE x ->> 'bom_id' IS NOT NULL AND NOT (v_map ? (x ->> 'bom_id'));
    INSERT INTO product_routing (product_id, seq, step_code, step_name, step_kind, stage, bom_id,
                                 default_vendor, confirmed)
    SELECT p_tgt, (x ->> 'seq')::integer, x ->> 'step_code', x ->> 'step_name', x ->> 'step_kind', x ->> 'stage',
           (v_map ->> (x ->> 'bom_id'))::integer, NULL, true
      FROM jsonb_array_elements(v_rts) x
     ORDER BY (x ->> 'seq')::integer;
    GET DIAGNOSTICS v_rt = ROW_COUNT;

    -- ⑦ 변경 이력
    INSERT INTO master_change_log (table_name, record_id, field_name, old_value, new_value, changed_by, reason)
    VALUES ('product_routing', p_tgt, 'routing', NULL, v_rt || '단계 복사 from ' || COALESCE(v_src_pn, p_src),
            v_who,
            '라우팅 복사 — 공정행 ' || v_proc || CASE WHEN v_mat > 0 THEN '·소재행 ' || v_mat ELSE '' END
            || CASE WHEN v_unmapped > 0 THEN '·연결 못한 단계 ' || v_unmapped ELSE '' END);

    RETURN jsonb_build_object('proc', v_proc, 'mat', v_mat, 'routing', v_rt, 'unmapped', v_unmapped,
                              'src_pn', v_src_pn, 'tgt_pn', v_tgt_pn);
END;
$$;

COMMENT ON FUNCTION public.copy_product_routing(text, text, boolean, text) IS
  '다른 제품의 공정행·라우팅(선택: 소재행) 복사 — 한 트랜잭션, 대상에 라우팅·공정행이 없을 때만. '
  '업체·단가는 복사하지 않음. 마이그레이션 081(마스터 관리 소수정 후보 32, 2026-11-04)';

REVOKE EXECUTE ON FUNCTION public.copy_product_routing(text, text, boolean, text) FROM PUBLIC, anon, authenticated;
GRANT  EXECUTE ON FUNCTION public.copy_product_routing(text, text, boolean, text) TO service_role;
