# -*- coding: utf-8 -*-
"""082 revise_shipment 정적 검사 — P3-1a 커밋 3 (2026-11-06, 계획서 §11-C · 지시문 r1 §2-3).

잠금 순서 · REVOKE·GRANT · SECURITY DEFINER 없음 · 재실행 판정이 상태 검사보다 앞 · CURRENT_DATE 없음 ·
시간대 없는 timestamptz 상수 없음 · 사후 조건 존재 · 데이터 사유 판정 한 곳.
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQL = open(os.path.join(ROOT, "supabase", "migrations", "082_revise_shipment_rpc.sql"), encoding="utf-8").read()
CODE = re.sub(r"--[^\n]*", "", SQL)          # 주석 제외


def _body(name):
    m = re.search(rf"CREATE OR REPLACE FUNCTION public\.{name}\(.*?AS \$\$(.*?)\$\$;", CODE, re.S)
    assert m, name
    return m.group(1)


FUNCS = ("revise_shipment", "revise_shipment_check", "revise_shipment_reasons")


def test_security_invoker_and_search_path():
    assert "SECURITY DEFINER" not in CODE.upper()
    for f in FUNCS:
        head = re.search(rf"CREATE OR REPLACE FUNCTION public\.{f}\(.*?AS \$\$", CODE, re.S).group(0)
        assert "SECURITY INVOKER" in head and "SET search_path = public, pg_temp" in head, f


def test_revoke_and_grant_service_role_only():
    for f in FUNCS:
        assert re.search(rf"REVOKE EXECUTE ON FUNCTION public\.{f}\([^)]*\) FROM PUBLIC, anon, authenticated;", CODE), f
        assert re.search(rf"GRANT\s+EXECUTE ON FUNCTION public\.{f}\([^)]*\) TO service_role;", CODE), f
    assert "NOTIFY pgrst, 'reload schema'" in CODE


def test_no_current_date_and_kst_today():
    assert "CURRENT_DATE" not in CODE.upper()
    assert "(now() AT TIME ZONE 'Asia/Seoul')::date" in CODE
    assert not re.search(r"'\d{4}-\d{2}-\d{2}[^']*'::timestamptz", CODE)       # 시간대 없는 상수 금지


def test_replay_check_before_status_checks():
    b = _body("revise_shipment")
    i_lock = b.index("FROM shipments WHERE shipment_id = p_shipment_id FOR UPDATE")
    i_replay = b.index("request_id = v_req")
    i_status = b.index("'not_confirmed:%'")
    i_items = b.index("PERFORM 1 FROM shipment_items")
    assert i_lock < i_replay < i_status < i_items, (i_lock, i_replay, i_status, i_items)


def test_lock_order():
    """전표 → 전표 라인 → 영향 수주 전 라인(soi 순) → 그 라인의 전 회차(sched 순) → advisory → 수주 머리글(so 순)."""
    b = _body("revise_shipment")
    seq = [b.index("FROM shipments WHERE shipment_id = p_shipment_id FOR UPDATE"),
           b.index("PERFORM 1 FROM shipment_items WHERE shipment_id = p_shipment_id ORDER BY si_id FOR UPDATE"),
           b.index("PERFORM 1 FROM sales_order_items WHERE so_id = ANY (v_sos) ORDER BY soi_id FOR UPDATE"),
           b.index("PERFORM 1 FROM so_delivery_schedule WHERE soi_id = ANY (v_sois) ORDER BY sched_id FOR UPDATE"),
           b.index("pg_advisory_xact_lock(hashtext('product_stock'), hashtext(v_pid))"),
           b.index("PERFORM 1 FROM sales_orders WHERE so_id = ANY (v_sos) ORDER BY so_id FOR NO KEY UPDATE")]
    assert seq == sorted(seq), seq
    # advisory 는 allow_over = false 일 때만(§18 A11), 머리글 잠금은 데이터 사유 판정보다 앞
    adv = b.index("pg_advisory_xact_lock")
    assert b.rfind("IF NOT v_allow THEN", 0, adv) > b.rfind("END IF;", 0, adv)
    assert seq[-1] < b.index("revise_shipment_reasons(p_shipment_id")
    # 잠금 문장은 값을 읽지 않는다(PERFORM) — 값은 잠금 뒤 별도 문장으로(§18 A3)
    assert len(re.findall(r"PERFORM 1 FROM \w+ WHERE .*?FOR (?:NO KEY )?UPDATE", b)) == 4


def test_data_reasons_in_one_place():
    for f in ("revise_shipment", "revise_shipment_check"):
        assert "public.revise_shipment_reasons(p_shipment_id" in _body(f), f
    r = _body("revise_shipment_reasons")
    for code in ("legacy_no_alloc", "issue_mismatch", "round_short", "recv_underflow"):
        assert f"'{code}'" in r, code
    assert "'{4,10,16,17,23,36,48,60,63,78,99,148,176}'::integer[]" in r
    assert "STABLE" in re.search(r"FUNCTION public\.revise_shipment_reasons\(.*?AS \$\$", CODE, re.S).group(0)


def test_postconditions_present():
    b = _body("revise_shipment")
    for name in ("postcondition:alloc_left", "postcondition:issue_left", "postcondition:line_state",
                 "postcondition:header", "postcondition:issue_net", "postcondition:alloc_over",
                 "postcondition:round"):                                   # r2 data M3
        assert name in b, name
    assert "'REPLACED'" in b[b.index("postcondition:issue_left"):]            # 상태별(§18 A1)


def test_no_set_update_on_lines_and_rounds_in_decrease():
    """감소는 si 순서로 한 줄씩 — 회차·충당 갱신은 alloc_id/sched_id 단건 조건."""
    b = _body("revise_shipment")
    dec = b[b.index("jsonb_object_keys(v_dec)"):b.index("RAISE EXCEPTION 'stale'")]
    assert "WHERE sched_id = v_a.sched_id" in dec and "WHERE alloc_id = v_a.alloc_id" in dec
    assert "ORDER BY COALESCE(d.due_date::text, '') DESC, a.alloc_id ASC" in dec
    assert "ORDER BY n.first_id DESC" in dec                                     # LOT 최초 차감 역순(§18 A4)


def test_check_is_read_only():
    head = re.search(r"CREATE OR REPLACE FUNCTION public\.revise_shipment_check\(.*?AS \$\$", CODE, re.S).group(0)
    assert "STABLE" in head
    body = _body("revise_shipment_check")
    assert not re.search(r"\b(INSERT|UPDATE|DELETE)\b", body), "읽기 전용"


def test_existing_functions_untouched():
    """confirm_shipment·so_close_lines·so_reopen_lines 본문은 건드리지 않는다(지시문 §6)."""
    for f in ("confirm_shipment", "so_close_lines", "so_reopen_lines"):
        assert f"FUNCTION public.{f}" not in CODE, f


def test_request_index_not_unique_and_view_locked_down():
    """r2: request_id 인덱스는 유니크가 아님(data M1 — FK si_id SET NULL 충돌), 화면용 뷰는 security_invoker·권한 회수(qa M3)."""
    assert "CREATE UNIQUE INDEX" not in CODE.upper()
    assert re.search(r"CREATE INDEX IF NOT EXISTS shipment_revisions_request_idx\s+ON public\.shipment_revisions "
                     r"\(shipment_id, request_id\)\s+WHERE request_id IS NOT NULL;", CODE)
    v = re.search(r"CREATE OR REPLACE VIEW public\.shipment_revise_blockers_v(.*?);", CODE, re.S).group(1)
    assert "security_invoker = true" in v and "public.revise_shipment_check(s.shipment_id)" in v
    assert "REVOKE ALL ON public.shipment_revise_blockers_v FROM PUBLIC, anon, authenticated;" in CODE
    assert "GRANT SELECT ON public.shipment_revise_blockers_v TO service_role;" in CODE
    assert CODE.index("shipment_revise_blockers_v") < CODE.index("NOTIFY pgrst")


def test_precision_check_before_md5_and_casts():
    """r2 Codex M2: 소수 6자리 초과 수량 → bad_version(precision), md5·재실행 판정보다 앞."""
    b = _body("revise_shipment")
    i_prec = b.index("HINT = 'precision'")
    assert b.index("HINT = 'shape'") < i_prec < b.index("v_md5 := md5(") < b.index("request_id = v_req")
