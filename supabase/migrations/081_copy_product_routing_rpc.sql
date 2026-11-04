-- ════════════════════════════════════════════════════════════
-- Migration 081: 다른 제품의 공정·라우팅 복사 RPC (마스터 관리 소수정 묶음 후보 32, 2026-11-04)
-- 기준: _마스터관리_소수정_묶음_지시문_r1_20261104.md §2 + 19:40 추록(소재행 복사) + Codex 1차 H1·H2 결정(제안 A)
-- ════════════════════════════════════════════════════════════
-- 문제(Codex 1차): 화면의 두 단계 insert(bom → 재조회 → product_routing)는 원자성이 없어 ① 다른 세션이 같은 대상에
--   넣은 BOM 을 실패 정리 때 함께 지우고 ② 재조회 실패·rerun 중단·응답 유실 때 BOM 만 남았다.
-- 설계: copy_product_routing — 한 트랜잭션.
--   ① 대상 products 행 FOR UPDATE(같은 대상 동시 복사 직렬화) ② 차단 조건 서버 재검사
--   ③ 원본 공정행(process_type<>'MATERIAL', bom_id 오름차순) insert … RETURNING → 원본 bom_id → 새 bom_id 매핑
--      (업체·단가 NULL, source 'MANUAL', verification_status 원본값, lot_label 원본값 — KG·CH 기준이면 수량의 뜻)
--   ④ p_with_mat 이면(대상 BOM 이 완전히 비었을 때만) 원본 소재행도(verification_status 'AUTO-추정') +
--      products.raw_material_name·bom_material_name = 첫 소재행 이름(진실=BOM, 2026-10-22 교훈)
--   ⑤ product_routing insert — 원본 seq·step_*·stage, bom_id = 매핑값(없으면 NULL), default_vendor NULL, confirmed true
--   ⑥ master_change_log 1행(product_routing, 대상 id, 'routing', 'N단계 복사 from 원본 pn')
-- 거부 사유(ERRCODE P0001, message): bad_args · not_found(HINT 제품 id) · archived(HINT) · target_has_routing ·
--   target_has_process · target_not_empty(소재행 복사인데 대상 BOM 있음) · source_no_routing · source_unconfirmed
-- 반환: {"proc": 공정행 수, "mat": 소재행 수, "routing": 라우팅 단계 수, "unmapped": 원본 공정행에 없는
--        bom_id 라 연결 없이 복사한 단계 수, "src_pn", "tgt_pn"}
-- 원본 일관성(Codex 2차 H1): 원본 라우팅·BOM 행을 FOR SHARE 로 잠그고 라우팅은 한 번 읽은 스냅샷으로만 검사·복사.
-- 소재 표기 원천(r2 ④): materials.raw_name 우선, 없으면 bom.raw_material_name.
-- 멱등성: 두 번째 호출은 target_has_routing 으로 거부된다(응답 유실 뒤 재조회 판정은 화면이 대상 라우팅 유무로).
-- 보안: SECURITY INVOKER + search_path 고정, anon/authenticated 실행 차단, service_role 만(069·076 과 동일).
-- 되돌리기: DROP FUNCTION IF EXISTS public.copy_product_routing(text, text, boolean, text);
--   (앱은 RpcUnavailable 이면 "복사 기능을 쓸 수 없음" 안내만 — 폴백 없음)
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
    v_map      jsonb := '{}'::jsonb;
    v_new      integer;
    v_proc     integer := 0;
    v_mat      integer := 0;
    v_rt       integer := 0;
    v_first    text;
    v_unmapped integer := 0;
    v_rts      jsonb := '[]'::jsonb;
    r          record;
BEGIN
    IF p_src IS NULL OR p_tgt IS NULL OR p_src = p_tgt THEN
        RAISE EXCEPTION 'bad_args' USING ERRCODE = 'P0001', HINT = 'p_src·p_tgt 필요, 서로 달라야 함';
    END IF;

    -- ① 대상 잠금(같은 대상의 동시 복사·BOM 편집 저장과 직렬화)
    SELECT pn, archived_at INTO v_tgt_pn, v_tgt_arch FROM products WHERE product_id = p_tgt FOR UPDATE;
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
    IF COALESCE(p_with_mat, false) AND EXISTS (SELECT 1 FROM bom WHERE product_id = p_tgt) THEN
        RAISE EXCEPTION 'target_not_empty' USING ERRCODE = 'P0001';
    END IF;

    -- 원본 라우팅 스냅샷(Codex 2차 H1): 행을 FOR SHARE 로 잠그고 한 번 읽은 값으로만 검사·복사한다 —
    -- 검사 뒤 원본에 단계가 추가·삭제돼도 복사 결과가 섞이지 않는다(공정행 삭제의 ON DELETE SET NULL 도 대기).
    FOR r IN SELECT * FROM product_routing WHERE product_id = p_src ORDER BY seq FOR SHARE LOOP
        v_rts := v_rts || jsonb_build_array(to_jsonb(r));
    END LOOP;
    IF jsonb_array_length(v_rts) = 0 THEN
        RAISE EXCEPTION 'source_no_routing' USING ERRCODE = 'P0001';
    END IF;
    IF EXISTS (SELECT 1 FROM jsonb_array_elements(v_rts) e WHERE NOT COALESCE((e ->> 'confirmed')::boolean, false)) THEN
        RAISE EXCEPTION 'source_unconfirmed' USING ERRCODE = 'P0001';
    END IF;

    -- ④ 소재행(선택) — 공정행보다 먼저(화면 표시 순서 = 소재 → 공정). 제품 소재 표기 원천은 자재 마스터
    -- materials.raw_name(없으면 BOM 의 이름) — 화면의 소재행 추가·교체 경로와 같은 원천(r2 ④)
    IF COALESCE(p_with_mat, false) THEN
        FOR r IN SELECT b.*, m.raw_name AS m_raw_name
                   FROM bom b LEFT JOIN materials m ON m.material_id = b.material_id
                  WHERE b.product_id = p_src AND COALESCE(b.process_type, 'MATERIAL') = 'MATERIAL'
                  ORDER BY b.bom_id FOR SHARE OF b LOOP
            INSERT INTO bom (product_id, material_id, raw_material_name, qty_per_pc, shared_factor, source,
                             verification_status, process_type, unit_price, lot_label, process_vendor_id)
            VALUES (p_tgt, r.material_id, r.raw_material_name, r.qty_per_pc, r.shared_factor, 'MANUAL',
                    'AUTO-추정', 'MATERIAL', NULL, r.lot_label, NULL);
            v_mat := v_mat + 1;
            IF v_first IS NULL THEN
                v_first := COALESCE(NULLIF(btrim(r.m_raw_name), ''), r.raw_material_name);
            END IF;
        END LOOP;
        IF v_first IS NOT NULL THEN
            UPDATE products SET raw_material_name = v_first, bom_material_name = v_first WHERE product_id = p_tgt;
        END IF;
    END IF;

    -- ③ 공정행 + 매핑(원본 공정행도 FOR SHARE)
    FOR r IN SELECT * FROM bom WHERE product_id = p_src AND COALESCE(process_type, 'MATERIAL') <> 'MATERIAL'
             ORDER BY bom_id FOR SHARE LOOP
        INSERT INTO bom (product_id, material_id, raw_material_name, qty_per_pc, shared_factor, source,
                         verification_status, process_type, unit_price, lot_label, process_vendor_id)
        VALUES (p_tgt, NULL, r.raw_material_name, r.qty_per_pc, r.shared_factor, 'MANUAL',
                r.verification_status, r.process_type, NULL, r.lot_label, NULL)
        RETURNING bom_id INTO v_new;
        v_map := v_map || jsonb_build_object(r.bom_id::text, v_new);
        v_proc := v_proc + 1;
    END LOOP;

    -- ⑤ 라우팅 — 스냅샷에서. 원본 공정행에 없는 bom_id(소재행 연결 등)는 NULL 로 복사하고 unmapped 로 센다(r2 ⑨)
    SELECT count(*) INTO v_unmapped
      FROM jsonb_array_elements(v_rts) e
     WHERE e ->> 'bom_id' IS NOT NULL AND NOT (v_map ? (e ->> 'bom_id'));
    INSERT INTO product_routing (product_id, seq, step_code, step_name, step_kind, stage, bom_id,
                                 default_vendor, confirmed)
    SELECT p_tgt, (e ->> 'seq')::integer, e ->> 'step_code', e ->> 'step_name', e ->> 'step_kind', e ->> 'stage',
           (v_map ->> (e ->> 'bom_id'))::integer, NULL, true
      FROM jsonb_array_elements(v_rts) e
     ORDER BY (e ->> 'seq')::integer;
    GET DIAGNOSTICS v_rt = ROW_COUNT;

    -- ⑥ 변경 이력
    INSERT INTO master_change_log (table_name, record_id, field_name, old_value, new_value, changed_by, reason)
    VALUES ('product_routing', p_tgt, 'routing', NULL, v_rt || '단계 복사 from ' || v_src_pn,
            NULLIF(btrim(COALESCE(p_who, '')), ''),
            '라우팅 복사 — 공정행 ' || v_proc || CASE WHEN v_mat > 0 THEN '·소재행 ' || v_mat ELSE '' END
            || CASE WHEN v_unmapped > 0 THEN '·연결 못한 단계 ' || v_unmapped ELSE '' END);

    RETURN jsonb_build_object('proc', v_proc, 'mat', v_mat, 'routing', v_rt, 'unmapped', v_unmapped,
                              'src_pn', v_src_pn, 'tgt_pn', v_tgt_pn);
END;
$$;

REVOKE EXECUTE ON FUNCTION public.copy_product_routing(text, text, boolean, text) FROM PUBLIC, anon, authenticated;
GRANT  EXECUTE ON FUNCTION public.copy_product_routing(text, text, boolean, text) TO service_role;
