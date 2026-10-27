# -*- coding: utf-8 -*-
"""T8 (P3-0 v2): confirm_shipment 두 세션 잠금 직렬화 — 로컬 복원 DB(wsapp_restore)에서만.

운영 DB 는 쓰지 않는다. 개발 PC 의 로컬 PostgreSQL([restore_pg], scripts/restore_local.py 로 복원한 DB)이
없으면 건너뛴다(CI 포함). 테스트용 수주·전표를 만들고 끝나면 지운다.

검증(계획서 v2 §7 H2):
  ① A 가 트랜잭션 안에서 confirm_shipment 실행 후 커밋 보류 → B 의 같은 호출은 잠금 대기(Lock)
  ② A 커밋 → B 는 not_draft:CONFIRMED 로 거부(이중 반영 없음)
  ③ A 롤백 → 기다리던 B 가 정상 반영
"""
import importlib.util
import json
import os
import threading
import time
import uuid

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SPEC = importlib.util.spec_from_file_location("restore_local", os.path.join(ROOT, "scripts", "restore_local.py"))


def _local():
    if importlib.util.find_spec("psycopg2") is None:
        pytest.skip("psycopg2 없음(개발 PC 전용 — requirements-dev.txt)")
    rl = importlib.util.module_from_spec(_SPEC)
    _SPEC.loader.exec_module(rl)
    try:
        cfg, _ = rl.load_dsn()
        c = rl.connect(cfg, rl.TARGET_DB)
    except BaseException as e:      # SafetyError(SystemExit) 포함 — 설정 없음·접속 불가
        pytest.skip(f"로컬 복원 DB 없음: {e}")
    cur = c.cursor()
    cur.execute("select 1 from pg_proc where proname = 'confirm_shipment'")
    if not cur.fetchone():
        c.close()
        pytest.skip("wsapp_restore 에 confirm_shipment 없음")
    c.close()
    return rl, cfg


def _make_case(conn, tag):
    """수주 1(라인 qty 10) + 작성중 전표 1(라인 qty 5, 제품·회차 없음). 반환 ids·payload."""
    cur = conn.cursor()
    cur.execute("insert into sales_orders (so_number, customer, status) values (%s, %s, 'DRAFT') returning so_id",
                (f"T8-{tag}", "T8 잠금검증"))
    so = cur.fetchone()[0]
    cur.execute("""insert into sales_order_items (so_id, line_no, qty, received_qty, pending_qty, status)
                   values (%s, 1, 10, 0, 10, 'PENDING') returning soi_id""", (so,))
    soi = cur.fetchone()[0]
    cur.execute("insert into shipments (ship_no, ship_date, status) values (%s, current_date, 'DRAFT') returning shipment_id",
                (f"T8-{tag}",))
    sh = cur.fetchone()[0]
    cur.execute("insert into shipment_items (shipment_id, soi_id, so_id, qty) values (%s, %s, %s, 5) returning si_id",
                (sh, soi, so))
    si = cur.fetchone()[0]
    conn.commit()
    payload = {"v": 1, "allow_over": False,
               "lines": [{"si_id": si, "soi_id": soi, "qty": 5, "expected_received_before": 0}],
               "scheds": [], "allocs": [], "txns": []}
    return {"so": so, "soi": soi, "sh": sh, "si": si, "payload": payload}


def _cleanup(conn, ids):
    cur = conn.cursor()
    cur.execute("set statement_timeout = 10000")   # 잠금이 남아도 정리가 무한 대기하지 않게 (r2 M3)
    cur.execute("delete from shipment_items where si_id = %s", (ids["si"],))
    cur.execute("delete from shipments where shipment_id = %s", (ids["sh"],))
    cur.execute("delete from sales_order_items where soi_id = %s", (ids["soi"],))
    cur.execute("delete from sales_orders where so_id = %s", (ids["so"],))
    conn.commit()


def _call(conn, ids):
    cur = conn.cursor()
    cur.execute("select confirm_shipment(%s, %s::jsonb)", (ids["sh"], json.dumps(ids["payload"])))
    return cur.fetchone()[0]


def _run_b(rl, cfg, ids, out):
    b = rl.connect(cfg, rl.TARGET_DB)
    b.cursor().execute("set statement_timeout = '20s'")
    t0 = time.perf_counter()
    try:
        out["res"] = _call(b, ids)
        b.commit()
    except Exception as e:
        b.rollback()
        diag = getattr(e, "diag", None)          # 서버 언어(한국어 '오류:')와 무관하게 본문만
        out["err"] = (getattr(diag, "message_primary", None) or str(e).strip().splitlines()[0])
        out["pgcode"] = getattr(e, "pgcode", None)
    out["sec"] = time.perf_counter() - t0
    b.close()


def _waiting_on_lock(conn, pid_a):
    cur = conn.cursor()
    cur.execute("""select count(*) from pg_stat_activity
                   where datname = current_database() and wait_event_type = 'Lock'
                     and pid <> %s and query ilike '%%confirm_shipment%%'""", (pid_a,))
    return cur.fetchone()[0]


def _scenario(rl, cfg, a_end, fail_while_locked=False):
    adm = rl.connect(cfg, rl.TARGET_DB)
    ids = _make_case(adm, uuid.uuid4().hex[:8])
    a, tb = None, None
    try:
        a = rl.connect(cfg, rl.TARGET_DB)
        a_pid = a.get_backend_pid()
        res_a = _call(a, ids)                      # ① A 반영, 커밋 보류(잠금 보유)
        assert res_a["ok"] is True
        out = {}
        tb = threading.Thread(target=_run_b, args=(rl, cfg, ids, out), daemon=True)
        tb.start()
        time.sleep(1.5)
        assert tb.is_alive(), "B 는 A 의 shipments FOR UPDATE 를 기다려야 한다"
        mon = rl.connect(cfg, rl.TARGET_DB)
        assert _waiting_on_lock(mon, a_pid) >= 1, "pg_stat_activity: B 가 Lock 대기"
        mon.close()
        assert not fail_while_locked, "의도한 실패(잠금 보유 중)"
        (a.commit if a_end == "commit" else a.rollback)()
        a.close()
        a = None
        tb.join(25)
        assert not tb.is_alive()
        # 대기 증거는 위 pg_stat_activity Lock 확인 — 시간은 여유를 둔다(A 가 1.5초 잡는 동안 B 연결·시작
        # 지연이 있어 1.39초가 나온 적 있음, 2026-10-27 전체 pytest 두 벌 동시 실행 중)
        assert out["sec"] >= 1.0, out
        chk = adm.cursor()
        chk.execute("select status from shipments where shipment_id = %s", (ids["sh"],))
        status = chk.fetchone()[0]
        chk.execute("select received_qty from sales_order_items where soi_id = %s", (ids["soi"],))
        recv = float(chk.fetchone()[0])
        adm.commit()
        if a_end == "commit":                       # ② 1차 커밋 → 2차 거부, 반영 1회분
            assert out.get("err", "").startswith("not_draft:CONFIRMED"), out
            assert status == "CONFIRMED" and recv == 5.0
        else:                                       # ③ 1차 롤백 → 기다리던 2차가 반영
            assert out.get("res", {}).get("ok") is True, out
            assert status == "CONFIRMED" and recv == 5.0
        print(f"T8[{a_end}] B 대기 {out['sec']:.2f}s → " + (out.get("err") or json.dumps(out.get("res"), ensure_ascii=False)[:80])
              + f" / 전표 {status} / 수주 라인 기납품 {recv:g}")
    finally:
        # 정리 순서(r2 M3): A 롤백·닫기(잠금 해제) → B 끝나길 제한 시간 대기 → 그 뒤 행 삭제
        if a is not None:
            try:
                a.rollback()
                a.close()
            except Exception:
                pass
        if tb is not None:
            tb.join(25)
        adm.rollback()
        _cleanup(adm, ids)
        adm.close()
    return ids


@pytest.mark.parametrize("a_end", ["commit", "rollback"])
def test_t8_two_sessions_serialize_on_shipment_lock(a_end):
    rl, cfg = _local()
    _scenario(rl, cfg, a_end)


def test_t8_failure_while_locked_cleans_up_quickly():
    """잠금 보유 중 단언이 실패해도 정리가 막히지 않고 끝난다(r2 M3) — 테스트 행이 남지 않는다."""
    rl, cfg = _local()
    t0 = time.perf_counter()
    with pytest.raises(AssertionError, match="의도한 실패"):
        _scenario(rl, cfg, "rollback", fail_while_locked=True)
    sec = time.perf_counter() - t0
    chk = rl.connect(cfg, rl.TARGET_DB)
    cur = chk.cursor()
    cur.execute("select count(*) from shipments where ship_no like 'T8-%%'")
    left = cur.fetchone()[0]
    cur.execute("select count(*) from sales_orders where so_number like 'T8-%%'")
    left += cur.fetchone()[0]
    chk.close()
    print(f"T8[실패 유도] 종료 {sec:.2f}s / 남은 테스트 행 {left}")
    assert sec < 20, sec
    assert left == 0
