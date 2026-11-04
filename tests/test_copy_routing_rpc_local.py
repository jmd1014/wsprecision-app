# -*- coding: utf-8 -*-
"""081 copy_product_routing — 로컬 복원 DB(wsapp_restore)에서 실제 실행(마스터 관리 소수정 32, 2026-11-04).

운영 DB 는 쓰지 않는다. 개발 PC 의 로컬 PostgreSQL([restore_pg])이 없으면 건너뛴다(CI 포함).
한 트랜잭션 안에서 081 함수를 만들고, BOM·라우팅이 없는 기존 제품 둘에 원본 BOM·라우팅을 넣어 복사한 뒤
전부 ROLLBACK 한다(남는 것 없음).
"""
import importlib.util
import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SPEC = importlib.util.spec_from_file_location("restore_local", os.path.join(ROOT, "scripts", "restore_local.py"))
_SQL = os.path.join(ROOT, "supabase", "migrations", "081_copy_product_routing_rpc.sql")


@pytest.fixture()
def tx():
    if importlib.util.find_spec("psycopg2") is None:
        pytest.skip("psycopg2 없음(개발 PC 전용 — requirements-dev.txt)")
    rl = importlib.util.module_from_spec(_SPEC)
    _SPEC.loader.exec_module(rl)
    try:
        cfg, _ = rl.load_dsn()
        c = rl.connect(cfg, rl.TARGET_DB)
    except BaseException as e:      # SafetyError(SystemExit) 포함 — 설정 없음·접속 불가
        pytest.skip(f"로컬 복원 DB 없음: {e}")
    c.autocommit = False
    cur = c.cursor()
    cur.execute(open(_SQL, encoding="utf-8").read())
    cur.execute("""select product_id, pn from products p where archived_at is null
                     and not exists (select 1 from bom b where b.product_id = p.product_id)
                     and not exists (select 1 from product_routing r where r.product_id = p.product_id)
                   order by product_id limit 3""")
    ps = cur.fetchall()
    if len(ps) < 3:
        c.rollback(); c.close()
        pytest.skip("BOM·라우팅 없는 제품이 3개 미만")
    (src, src_pn), (tgt, _), (tgt2, _) = ps
    cur.execute("""insert into bom (product_id, material_id, raw_material_name, qty_per_pc, shared_factor, source,
                                    verification_status, process_type, unit_price, lot_label, process_vendor_id)
                   values (%s, (select material_id from materials where coalesce(btrim(raw_name), '') <> ''
                                    order by material_id limit 1),
                           'T81 소재', 1, 1, 'MES', '확인완료', 'MATERIAL', null, null, null),
                          (%s, null, 'T81 열처리', 0.35, 1, 'MES', '확인완료', 'HEAT', 1000, 'KG',
                           (select vendor_id from vendors order by vendor_id limit 1)),
                          (%s, null, 'T81 도금', 1, 1, 'MES', 'AUTO-추정', 'SURFACE', 50, null, null)
                   returning bom_id""", (src, src, src))
    b_mat, b_heat, b_surf = [r[0] for r in cur.fetchall()]
    cur.execute("""insert into product_routing (product_id, seq, step_code, step_name, step_kind, stage, bom_id,
                                                default_vendor, confirmed)
                   values (%s, 10, 'MAT_IN', '소재입고', 'INHOUSE', 'MATERIAL', null, null, true),
                          (%s, 20, 'PROD', '생산', 'INHOUSE', 'PRODUCT', null, null, true),
                          (%s, 30, 'OUT', 'T81 열처리', 'OUTSOURCE', 'PRODUCT', %s, '어떤업체', true),
                          (%s, 40, 'OUT', 'T81 도금', 'OUTSOURCE', 'PRODUCT', %s, null, true),
                          (%s, 60, 'DONE', '완성', 'INHOUSE', 'PRODUCT', null, null, true)""",
                (src, src, src, b_heat, src, b_surf, src))
    try:
        yield c, cur, {"src": src, "src_pn": src_pn, "tgt": tgt, "tgt2": tgt2,
                       "heat": b_heat, "surf": b_surf}
    finally:
        c.rollback()
        c.close()


def _call(cur, src, tgt, with_mat):
    cur.execute("select public.copy_product_routing(%s, %s, %s, %s)", (src, tgt, with_mat, "T81"))
    v = cur.fetchone()[0]
    return v if isinstance(v, dict) else json.loads(v)


def _reject(c, cur, src, tgt, with_mat):
    cur.execute("savepoint s")
    try:
        _call(cur, src, tgt, with_mat)
    except Exception as e:     # psycopg2.errors.RaiseException
        cur.execute("rollback to savepoint s")
        return getattr(getattr(e, "diag", None), "message_primary", None) or str(e)
    cur.execute("rollback to savepoint s")
    return None


def test_081_copy_maps_bom_ids_and_logs(tx):
    c, cur, k = tx
    out = _call(cur, k["src"], k["tgt"], False)
    assert (out["proc"], out["mat"], out["routing"], out["unmapped"], out["src_pn"]) == (2, 0, 5, 0, k["src_pn"])
    cur.execute("""select bom_id, raw_material_name, process_type, material_id, unit_price, process_vendor_id,
                          source, verification_status, lot_label
                     from bom where product_id = %s order by bom_id""", (k["tgt"],))
    rows = cur.fetchall()
    assert [(r[1], r[2]) for r in rows] == [("T81 열처리", "HEAT"), ("T81 도금", "SURFACE")]
    assert all(r[3] is None and r[4] is None and r[5] is None and r[6] == "MANUAL" for r in rows), "업체·단가 복사 안 함"
    assert [(r[7], r[8]) for r in rows] == [("확인완료", "KG"), ("AUTO-추정", None)]
    new = {r[1]: r[0] for r in rows}
    cur.execute("""select seq, step_code, bom_id, default_vendor, confirmed from product_routing
                    where product_id = %s order by seq""", (k["tgt"],))
    rt = cur.fetchall()
    assert [(r[0], r[2]) for r in rt] == [(10, None), (20, None), (30, new["T81 열처리"]), (40, new["T81 도금"]),
                                          (60, None)], "원본 bom_id → 새 id"
    assert all(r[3] is None and r[4] is True for r in rt)
    cur.execute("""select new_value, reason, changed_by from master_change_log
                    where table_name = 'product_routing' and record_id = %s""", (k["tgt"],))
    assert cur.fetchall() == [(f"5단계 복사 from {k['src_pn']}", "라우팅 복사 — 공정행 2", "T81")]
    assert _reject(c, cur, k["src"], k["tgt"], False) == "target_has_routing", "두 번째 호출은 거부(멱등)"


def test_081_with_material_syncs_product_name(tx):
    c, cur, k = tx
    out = _call(cur, k["src"], k["tgt2"], True)
    assert (out["proc"], out["mat"], out["routing"]) == (2, 1, 5)
    cur.execute("select process_type, verification_status from bom where product_id = %s order by bom_id",
                (k["tgt2"],))
    assert cur.fetchall() == [("MATERIAL", "AUTO-추정"), ("HEAT", "확인완료"), ("SURFACE", "AUTO-추정")]
    cur.execute("""select m.raw_name from bom b join materials m on m.material_id = b.material_id
                    where b.product_id = %s and b.process_type = 'MATERIAL'""", (k["tgt2"],))
    mname = cur.fetchone()[0]
    cur.execute("select raw_material_name, bom_material_name from products where product_id = %s", (k["tgt2"],))
    assert cur.fetchone() == (mname, mname), "제품 소재 표기 = 자재 마스터 raw_name(r2 ④)"
    cur.execute("select reason from master_change_log where record_id = %s and table_name = 'product_routing'",
                (k["tgt2"],))
    assert cur.fetchone()[0] == "라우팅 복사 — 공정행 2·소재행 1"


def test_081_blocks(tx):
    c, cur, k = tx
    assert _reject(c, cur, k["src"], k["src"], False) == "bad_args"
    assert _reject(c, cur, k["src"], "NO-SUCH-PID", False) == "not_found"
    cur.execute("insert into bom (product_id, raw_material_name, process_type) values (%s, 'T81 기존 소재', 'MATERIAL')",
                (k["tgt"],))
    assert _reject(c, cur, k["src"], k["tgt"], True) == "target_not_empty", "소재행 복사는 빈 대상만"
    cur.execute("insert into bom (product_id, raw_material_name, process_type) values (%s, 'T81 기존 공정', 'HEAT')",
                (k["tgt"],))
    assert _reject(c, cur, k["src"], k["tgt"], False) == "target_has_process"
    cur.execute("update product_routing set confirmed = false where product_id = %s and seq = 20", (k["src"],))
    assert _reject(c, cur, k["src"], k["tgt2"], False) == "source_unconfirmed"
    assert _reject(c, cur, k["tgt"], k["tgt2"], False) == "source_no_routing"
    cur.execute("select count(*) from bom where product_id = %s", (k["tgt2"],))
    assert cur.fetchone()[0] == 0, "거부된 호출은 아무것도 남기지 않음"


def test_081_unmapped_step_counted_and_source_snapshot(tx):
    """원본 라우팅이 소재행(공정행 아님)을 가리키면 연결 없이 복사하고 unmapped 로 센다(r2 ⑨)."""
    c, cur, k = tx
    cur.execute("select bom_id from bom where product_id = %s and process_type = 'MATERIAL'", (k["src"],))
    b_mat = cur.fetchone()[0]
    cur.execute("update product_routing set bom_id = %s where product_id = %s and seq = 20", (b_mat, k["src"]))
    out = _call(cur, k["src"], k["tgt"], False)
    assert (out["routing"], out["unmapped"]) == (5, 1)
    cur.execute("select bom_id from product_routing where product_id = %s and seq = 20", (k["tgt"],))
    assert cur.fetchone()[0] is None
    cur.execute("select reason from master_change_log where record_id = %s and table_name = 'product_routing'",
                (k["tgt"],))
    assert cur.fetchone()[0] == "라우팅 복사 — 공정행 2·연결 못한 단계 1"
