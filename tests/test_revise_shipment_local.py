# -*- coding: utf-8 -*-
"""082 revise_shipment 실 트랜잭션 시험 — 로컬 복원 DB(wsapp_restore)에서만 (P3-1a 커밋 4, 계획서 §11-D · §18-2).

운영 DB 는 쓰지 않는다. 개발 PC 의 로컬 PostgreSQL([restore_pg], scripts/restore_local.py 로 복원한 DB)이 없거나
082 가 적용돼 있지 않으면 건너뛴다(CI 포함). 시험 데이터는 각 시험의 트랜잭션 안에서 만들고 ROLLBACK 한다
(동시성 시험만 커밋된 시험 행을 만들고 끝나면 지운다 — id 는 OFF 위 영역, 품번·번호에 '-GV' 꼬리).

L1  골든 벡터 전부(g_*.json) + 시드 고정 무작위 200건 → SQL 결과 = utils.shipment_revise.plan_revision
L2  같은 전표 두 세션 동시 정정 → 하나 반영, 하나 stale_rev
L3  정정 ↔ 같은 수주 라인 확정 → 직렬화(확정은 기다렸다가 stale), 불변식 유지
L4  정정 ↔ so_close_lines / so_reopen_lines, 두 순서 → received + pending + closed = qty
L5  정정(취소) ↔ 형제 라인 확정, 두 순서 → 수주 머리글이 라인과 일치
L6  두 수주에 엇갈려 걸친 정정 ↔ 확정 → 교착 없음(또는 40P01 뒤 재호출 성공)
L7  검증 단계 실패 + 마지막 단계 실패(임시 트리거) → 쓰기 8개 표가 실행 전과 같음
L8  같은 request_id: 순차 두 번 / 두 세션 동시 / 다른 내용 / 거부된 뒤 재사용 + §18-2 6 확장
L9  서로 다른 전표가 같은 수주 라인을 동시에 취소(500, 300) → received = 처음 − 800
L10 정정 증가 ↔ 확정, 같은 제품 재고 100 에 각 80(둘 다 allow_over=false) → 정확히 하나만 stock: 거부
L11 정정 ↔ 납기 입력 저장(REST 조건부 갱신 — delivered 가드, qty 만 바꾸는 경우 포함) → 덮어쓰기 없음
L12 권한(anon·authenticated 불가) · 082 두 번 적용 · 세션 시간대 UTC 에서 원장 날짜 = KST
L13 전수 드라이런: 복원 DB 의 확정 전표 전부 BEGIN → CANCEL → 불변식 → ROLLBACK → 거부는 정확히 전표 12장
"""
import copy
import datetime as dt
import decimal
import glob
import importlib.util
import json
import os
import random
import threading
import time
import uuid

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLD = os.path.join(ROOT, "tests", "golden", "revise_shipment")
_SPEC = importlib.util.spec_from_file_location("restore_local", os.path.join(ROOT, "scripts", "restore_local.py"))
OFF = 900_000_000                        # 시험 행 id 영역(복원 DB 의 실제 id 와 겹치지 않음)
SFX = "-GV"
LEGACY_SI = (4, 10, 16, 17, 23, 36, 48, 60, 63, 78, 99, 148, 176)
EXPECTED_REJECTED_SHIPS = {"SH-20260810-01", "SH-20260812-01", "SH-20260812-02", "SH-20260817-01",
                           "SH-20260819-01", "SH-20260821-01", "SH-20260824-02", "SH-20260831-01",
                           "SH-20260907-01", "SH-20260909-02", "SH-20260923-02", "SH-20260929-01"}
RESULTS = {}                             # 결과 파일(04)용


def _rl():
    if importlib.util.find_spec("psycopg2") is None:
        pytest.skip("psycopg2 없음(개발 PC 전용 — requirements-dev.txt)")
    rl = importlib.util.module_from_spec(_SPEC)
    _SPEC.loader.exec_module(rl)
    try:
        cfg, _ = rl.load_dsn()
        c = rl.connect(cfg, rl.TARGET_DB)
    except BaseException as e:            # SafetyError(SystemExit) 포함
        pytest.skip(f"로컬 복원 DB 없음: {e}")
    cur = c.cursor()
    cur.execute("select 1 from pg_proc where proname = 'revise_shipment'")
    ok = cur.fetchone()
    c.close()
    if not ok:
        pytest.skip("wsapp_restore 에 revise_shipment(082) 없음")
    return rl, cfg


@pytest.fixture(scope="module")
def pg():
    rl, cfg = _rl()

    def connect():
        c = rl.connect(cfg, rl.TARGET_DB)
        c.autocommit = False
        return c
    return connect


def _kst_today():
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=9)).date().isoformat()


# ── 세계 적재(id 영역 이동) ──
INT_ID = {"shipments": ("shipment_id",), "shipment_items": ("si_id", "shipment_id", "soi_id", "so_id", "sched_id"),
          "shipment_allocations": ("alloc_id", "si_id", "sched_id"), "inventory_transactions": ("txn_id", "ref_id"),
          "shipment_revisions": ("rev_id", "shipment_id", "si_id"), "sales_order_items": ("soi_id", "so_id"),
          "sales_orders": ("so_id",), "so_delivery_schedule": ("sched_id", "so_id", "soi_id")}
TEXT_PROD = {"shipment_items": ("product_id",), "inventory_transactions": ("product_id",),
             "sales_order_items": ("product_id",)}


def _mi(v, si=False):
    """정수 id → 시험 영역. 전표 라인 id(si)가 고정 목록(옛 전표)이면 그대로 — 목록 판정이 si_id 로 하기 때문."""
    if v is None or isinstance(v, str):
        return v
    return int(v) if (si and int(v) in LEGACY_SI) else int(v) + OFF


def _ui(v):
    if v is None:
        return None
    v = int(v)
    return v - OFF if v >= OFF else v


def _mp(v):
    return None if v in (None, "") else f"{v}{SFX}"


def _up(v):
    return v[:-len(SFX)] if isinstance(v, str) and v.endswith(SFX) else v


def map_req(req):
    r = copy.deepcopy(req)
    for l in r.get("lines") or []:
        l["si_id"] = _mi(l["si_id"], si=True)
    inc = r.get("inc") or {}
    for e in inc.get("expected_received_before") or []:
        e["soi_id"] = _mi(e["soi_id"])
    for s in inc.get("scheds") or []:
        s["sched_id"], s["soi_id"] = _mi(s["sched_id"]), _mi(s["soi_id"])
    for a in inc.get("allocs") or []:
        a["si_id"], a["sched_id"] = _mi(a["si_id"], si=True), _mi(a["sched_id"])
    for t in inc.get("txns") or []:
        t["si_id"], t["product_id"] = _mi(t["si_id"], si=True), _mp(t["product_id"])
    return r


LOAD_ORDER = ("sales_orders", "sales_order_items", "so_delivery_schedule", "shipments", "shipment_items",
              "shipment_allocations", "inventory_transactions", "sales_month_close", "shipment_revisions")
_COLS = {}


def _db_cols(cur, t):
    if t not in _COLS:
        cur.execute("select column_name from information_schema.columns where table_schema='public' and table_name=%s",
                    (t,))
        _COLS[t] = {r[0] for r in cur.fetchall()}
    return _COLS[t]


def _map_val(t, k, v):
    if k in INT_ID.get(t, ()):
        return _mi(v, si=k in ("si_id", "ref_id"))
    if k == "product_id":
        return _mp(v)
    if (t, k) in (("shipments", "ship_no"), ("sales_orders", "so_number")):
        return None if v is None else v + SFX
    if k == "closed_rounds" and v is not None:
        return json.dumps([dict(e, sched_id=_mi(e.get("sched_id"))) for e in v])
    if k == "info" and v is not None:
        return json.dumps(v, ensure_ascii=False)
    return v


def load_world(cur, state):
    """golden state → 복원 DB(현재 트랜잭션), golden 행의 열을 전부(DB 에 있는 열만). 반환: 조회 범위 id."""
    st = copy.deepcopy(state)
    reqs = st.pop("_requests", None) or {}
    for r in st.get("shipment_revisions", []):            # 재실행 판정용 md5 를 옮긴 id 기준으로 다시(파이썬 request_md5)
        if r.get("request_id") in reqs:
            from utils.shipment_revise import request_md5
            r["info"] = dict(r.get("info") or {}, payload_md5=request_md5(map_req(reqs[r["request_id"]])))
    for si in LEGACY_SI:                                     # 고정 목록 id 를 쓰는 세계면 실제 행을 트랜잭션 안에서 비운다
        if any(x["si_id"] == si for x in st["shipment_items"]):
            cur.execute("delete from shipment_allocations where si_id = %s", (si,))
            cur.execute("delete from inventory_transactions where ref_table='shipment_items' and ref_id = %s", (si,))
            cur.execute("update shipment_revisions set si_id = null where si_id = %s", (si,))
            cur.execute("delete from shipment_items where si_id = %s", (si,))
    pids = sorted({x.get("product_id") for t in ("shipment_items", "inventory_transactions", "sales_order_items")
                   for x in st[t] if x.get("product_id")} | {p["product_id"] for p in st["product_stock_v"]})
    for p in pids:
        cur.execute("insert into products (product_id, pn) values (%s, %s)", (_mp(p), f"{p}{SFX}-PN"))
    for t in LOAD_ORDER:
        cols = _db_cols(cur, t)
        for r in st.get(t, []):
            ks = [k for k in r if k in cols]
            cur.execute(f"insert into {t} ({', '.join(ks)}) values ({', '.join(['%s'] * len(ks))})",
                        [_map_val(t, k, r[k]) for k in ks])
        if t == "inventory_transactions":                   # 재고 = 시드 값이 되게 ADJUSTMENT 1행
            for p in st["product_stock_v"]:
                issued = sum(float(x["qty"]) for x in st["inventory_transactions"]
                             if x.get("product_id") == p["product_id"])
                cur.execute("""insert into inventory_transactions (material_id, product_id, txn_type, qty, unit, txn_date,
                               remark) values (null, %s, 'ADJUSTMENT', %s, 'EA', '2026-10-01', 'P3-1a 로컬 시험 재고 시드')""",
                            (_mp(p["product_id"]), float(p["current_stock"]) - issued))
    return {"ships": [_mi(x["shipment_id"]) for x in st["shipments"]],
            "sis": [_mi(x["si_id"], si=True) for x in st["shipment_items"]],
            "sois": [_mi(x["soi_id"]) for x in st["sales_order_items"]],
            "sos": [_mi(x["so_id"]) for x in st["sales_orders"]],
            "scheds": [_mi(x["sched_id"]) for x in st["so_delivery_schedule"]]}


def call(cur, sid, payload, savepoint=True):
    """revise_shipment → ('ok', 결과) / ('err', 코드). 거부는 SAVEPOINT 로 되돌려 같은 트랜잭션에서 계속 읽는다."""
    if savepoint:
        cur.execute("savepoint sp_call")
    try:
        cur.execute("select public.revise_shipment(%s, %s::jsonb)", (sid, json.dumps(payload, ensure_ascii=False)))
        res = cur.fetchone()[0]
        if savepoint:
            cur.execute("release savepoint sp_call")
        return "ok", res
    except Exception as e:                                     # psycopg2 오류 — 메시지 첫 줄이 코드
        if savepoint:
            cur.execute("rollback to savepoint sp_call")
        msg = getattr(getattr(e, "diag", None), "message_primary", None) or str(e).splitlines()[0]
        return "err", msg


# ── 복원 DB → golden after 모양 ──
def read_world(cur, ids):
    def rows(sql, args):
        cur.execute(sql, args)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    sis, sois = ids["sis"], ids["sois"]
    out = {
        "shipments": rows("select * from shipments where shipment_id = any(%s)", (ids["ships"],)),
        "shipment_items": rows("select * from shipment_items where si_id = any(%s)", (sis,)),
        "shipment_allocations": rows("select * from shipment_allocations where si_id = any(%s)", (sis,)),
        "inventory_transactions": rows("""select * from inventory_transactions where ref_table='shipment_items'
                                          and ref_id = any(%s)""", (sis,)),
        "shipment_revisions": rows("select * from shipment_revisions where shipment_id = any(%s)", (ids["ships"],)),
        "sales_order_items": rows("select * from sales_order_items where soi_id = any(%s)", (sois,)),
        "sales_orders": rows("select * from sales_orders where so_id = any(%s)", (ids["sos"],)),
        "so_delivery_schedule": rows("select * from so_delivery_schedule where sched_id = any(%s)", (ids["scheds"],)),
    }
    return out


def _num(v):
    try:
        f = float(v)
        return int(f) if f.is_integer() else round(f, 6)
    except (TypeError, ValueError):
        return v


def _canon_val(k, v, today_gold):
    if v is None:
        return None
    if k in ("revised_at", "cancelled_at"):
        return "<NOW>"
    if isinstance(v, (dt.date, dt.datetime)):
        v = v.isoformat()
    if isinstance(v, uuid.UUID):
        v = str(v)
    if k == "txn_date" and str(v)[:10] == _kst_today():
        return today_gold
    if isinstance(v, dict) or isinstance(v, list):
        return json.loads(json.dumps(v, default=str), parse_float=float)
    if isinstance(v, str):
        return v.replace(SFX, "")
    return _num(v)


def canon(t, rows, keys, today_gold, from_db):
    """golden after 의 열만, PK 발급 표는 PK 를 빼고, id 를 원래 영역으로 되돌려 정렬된 목록."""
    drop = {"shipment_allocations": ("alloc_id",), "inventory_transactions": ("txn_id",),
            "shipment_revisions": ("rev_id",)}.get(t, ())
    out = []
    for r in rows:
        d = {}
        for k in keys:
            if k in drop:
                continue
            v = r.get(k)
            if from_db and k in INT_ID.get(t, ()):
                v = _ui(v)
            if k == "info" and isinstance(v, dict):
                v = {kk: vv for kk, vv in v.items() if kk != "payload_md5"}
                v = json.loads(json.dumps(v))
                for e in v.get("info") or []:
                    for kk in ("si_id", "soi_id"):
                        if kk in e and from_db:
                            e[kk] = _ui(e[kk])
            if k == "closed_rounds" and isinstance(v, list) and from_db:
                v = [dict(e, sched_id=_ui(e.get("sched_id"))) for e in v]
            if k == "product_id" and from_db:
                v = _up(v)
            d[k] = _canon_val(k, v, today_gold) if not (k == "info") else v
            if k == "closed_rounds" and d[k] is not None:
                d[k] = [{kk: _num(vv) for kk, vv in e.items()} for e in d[k]]
        out.append(d)
    return sorted(out, key=lambda r: json.dumps(r, sort_keys=True, ensure_ascii=False, default=str))


def compare_after(db_after, gold_after, today_gold):
    diffs = {}
    for t, grows in gold_after.items():
        keys = sorted({k for r in grows for k in r}) or ["_"]
        a = canon(t, db_after.get(t, []), keys, today_gold, True)
        b = canon(t, grows, keys, today_gold, False)
        if a != b:
            diffs[t] = {"db": [r for r in a if r not in b][:5], "golden": [r for r in b if r not in a][:5]}
    return diffs


def _norm_result(res, from_db):
    if not isinstance(res, dict):
        return res
    out = {k: v for k, v in res.items() if k not in ("hint",)}
    if from_db:
        out["so_ids"] = [_ui(x) for x in out.get("so_ids") or []] if "so_ids" in out else out.get("so_ids")
        out["info"] = [{k: (_ui(v) if k in ("si_id", "soi_id") else _num(v)) for k, v in e.items()}
                       for e in out.get("info") or []] if "info" in out else out.get("info")
    else:
        if "info" in out:
            out["info"] = [{k: _num(v) for k, v in e.items()} for e in out.get("info") or []]
    return {k: v for k, v in out.items() if v is not None}


def run_golden(pg, g):
    """한 골든을 SQL 로 → 차이(dict, 비면 같음)."""
    c = pg()
    try:
        cur = c.cursor()
        cur.execute("set local lock_timeout = '5s'")
        cur.execute("set local time zone 'UTC'")
        ids = load_world(cur, g["state"])
        req = map_req(g["request"])
        sid = _mi(g["request"]["shipment_id"]) if g["request"].get("shipment_id") is not None else None
        kind, res = call(cur, sid, req)
        exp = g["expect"]["result"]
        if not exp.get("ok"):
            got = res.replace(SFX, "") if kind == "err" else f"ok:{res}"
            return {} if got == exp["error"] else {"result": {"db": got, "golden": exp["error"]}}
        if kind != "ok":
            return {"result": {"db": res, "golden": "ok"}}
        diffs = {}
        a, b = _norm_result(res, True), _norm_result(exp, False)
        if a != b:
            diffs["result"] = {"db": a, "golden": b}
        diffs.update(compare_after(read_world(cur, ids), g["expect"]["after"], g["today"]))
        return diffs
    finally:
        c.rollback()
        c.close()


GOLDENS = sorted(glob.glob(os.path.join(GOLD, "g_*.json")))


@pytest.mark.parametrize("path", GOLDENS, ids=[os.path.basename(p)[2:-5] for p in GOLDENS])
def test_l1_golden_vectors_sql_equals_model(pg, path):
    g = json.load(open(path, encoding="utf-8"))
    d = run_golden(pg, g)
    RESULTS.setdefault("L1_golden", {})[g["name"]] = "pass" if not d else d
    assert not d, json.dumps(d, ensure_ascii=False, default=str)[:3000]


# ── L1 무작위 등가성(시드 고정 200건) ──
def rand_case(seed):
    """일관성이 대체로 맞되 가끔 어긋난(데이터 사유·요청 오류) 세계 + 화면 payload."""
    from utils.shipment_revise import build_payload
    rng = random.Random(seed)
    dates = ["2026-10-28", "2026-11-01", "2026-11-01", "2026-11-05", "2026-11-10"]
    w = {k: [] for k in ("sales_orders", "sales_order_items", "so_delivery_schedule", "shipments", "shipment_items",
                         "shipment_allocations", "inventory_transactions", "shipment_revisions", "product_stock_v",
                         "product_lot_stock_v", "sales_month_close")}
    sois = []
    for so in ([100] if rng.random() < .6 else [100, 200]):
        w["sales_orders"].append({"so_id": so, "so_number": "SO-%d" % so, "customer": "㈜엠제이티",
                                  "so_date": "2026-10-01",
                                  "status": rng.choices(["PARTIAL", "DELIVERED", "CLOSED", "CANCELLED", "DRAFT"],
                                                        [50, 15, 15, 10, 10])[0]})
        for k in range(rng.choice([1, 1, 2])):
            pid = rng.choice(["P1", "P2"])
            sois.append({"soi_id": so // 10 + k + 1, "so_id": so, "line_no": k + 1, "product_id": pid,
                         "canonical_pn": "4PDVN-0" + pid[1], "qty": rng.randrange(200, 1500, 50), "unit": "EA",
                         "status": rng.choices(["ACTIVE", "CLOSED", "CANCELLED", "REPLACED"], [75, 10, 5, 10])[0]})
    sched = 1
    for l in sois:
        left = l["qty"]
        for seq in range(1, rng.choice([1, 2, 3]) + 1):
            if left <= 50:
                break
            q = rng.randrange(50, left, 10)
            w["so_delivery_schedule"].append({"sched_id": sched, "so_id": l["so_id"], "soi_id": l["soi_id"],
                                              "seq": seq, "due_date": rng.choice(dates), "qty": q,
                                              "delivered_qty": 0, "note": None})
            sched += 1
            left -= q
    w["shipments"].append({"shipment_id": 50, "ship_no": "SH-20261101-01", "ship_date": "2026-11-01",
                           "status": "CONFIRMED", "created_by": "테스트",
                           "confirmed_at": "2026-11-01T01:05:00+00:00", "rev_no": rng.choice([0, 0, 1, 2]),
                           "revised_at": None, "cancelled_at": None, "cancel_reason": None})
    recv = {l["soi_id"]: 0 for l in sois}
    aid = tid = 1
    for i in range(rng.choice([1, 2, 2, 3])):
        si = 501 + i
        l = rng.choice(sois) if rng.random() > .05 else None
        pid = ((l["product_id"] if l else "P1") if rng.random() > .05 else None)
        qty = 0 if rng.random() < .1 else rng.randrange(20, 400, 10)
        w["shipment_items"].append({"si_id": si, "shipment_id": 50, "soi_id": l and l["soi_id"],
                                    "so_id": l and l["so_id"], "sched_id": None, "product_id": pid,
                                    "pn": "4PDVN-03", "customer_pn": None, "item_name": None,
                                    "customer": "㈜엠제이티", "so_number": l and ("SO-%d" % l["so_id"]),
                                    "qty": qty, "unit": "EA", "unit_price": 1000})
        if l:
            recv[l["soi_id"]] += qty
            rs = [r for r in w["so_delivery_schedule"] if r["soi_id"] == l["soi_id"]]
            mode = rng.choices(["full", "partial", "none"], [70, 20, 10])[0]
            left = qty if mode == "full" else (qty - rng.randrange(0, qty + 1, 10) if mode == "partial" else 0)
            if rs and qty > 0:
                w["shipment_items"][-1]["sched_id"] = rs[0]["sched_id"]
            for r in rng.sample(rs, len(rs)):
                if left <= 0:
                    break
                take = min(left, max(r["qty"] - r["delivered_qty"], 0)) if rng.random() < .8 else left
                if take <= 0:
                    continue
                w["shipment_allocations"].append({"alloc_id": aid, "si_id": si, "sched_id": r["sched_id"],
                                                  "qty": take})
                r["delivered_qty"] += take
                aid += 1
                left -= take
        if pid and qty > 0:
            left = qty
            while left > 0:
                take = min(left, rng.randrange(10, qty + 10, 10))
                w["inventory_transactions"].append({
                    "txn_id": tid, "material_id": None, "product_id": pid, "txn_type": "ISSUE", "qty": -take,
                    "unit": "EA", "lot_number": rng.choice(["A", "B", "C", None]), "work_order": None,
                    "ref_table": "shipment_items", "ref_id": si, "txn_date": "2026-11-01", "remark": "출고",
                    "created_by": "테스트"})
                tid += 1
                left -= take
            if rng.random() < .08:                               # 순합 어긋남(issue_mismatch)
                w["inventory_transactions"][-1]["qty"] -= 10
    for r in w["so_delivery_schedule"]:
        if rng.random() < .07 and r["delivered_qty"] > 0:        # 충당 > 납품완료(round_short)
            r["delivered_qty"] -= 10
        elif rng.random() < .3:
            r["delivered_qty"] = min(r["qty"], r["delivered_qty"] + rng.randrange(0, 60, 10))
    for l in sois:
        rv = recv[l["soi_id"]] + rng.randrange(0, 200, 10)
        if rng.random() < .07:
            rv = max(recv[l["soi_id"]] - 20, 0)                 # 수주 납품량 부족(recv_underflow)
        st = l.pop("status")
        if st == "ACTIVE":
            st = "DELIVERED" if rv >= l["qty"] else "PARTIAL" if rv > 0 else "PENDING"
            pend, closed = max(l["qty"] - rv, 0), 0
        elif st in ("CLOSED", "CANCELLED"):
            pend, closed = 0, max(l["qty"] - rv, 0)
        else:
            pend, closed = 0, 0
        w["sales_order_items"].append(dict(l, received_qty=rv, pending_qty=pend, status=st, closed_qty=closed,
                                           closed_rounds=None, close_reason=None))
    for pid in ("P1", "P2"):
        w["product_stock_v"].append({"product_id": pid, "pn": "4PDVN-0" + pid[1], "customer": "-",
                                     "current_stock": rng.choice([0, 50, 300, 2000])})
        for lot, rem in (("A", rng.choice([0, 40, 500])), ("D", rng.choice([0, 100]))):
            if rem:
                w["product_lot_stock_v"].append({"product_id": pid, "lot_number": lot, "remain_qty": rem,
                                                 "first_output_date": "2026-10-0%d" % rng.randint(1, 9)})
    if rng.random() < .03:
        w["sales_month_close"].append({"ym": "2026-11", "closed_by": "관리자"})
    rid = str(uuid.uuid5(uuid.NAMESPACE_URL, "p3-1a/rand/%d" % seed))
    if rng.random() < .4:
        req = build_payload(w, 50, {}, "무작위", "테스트", rng.random() < .2, rid, action="CANCEL")
    else:
        new = {}
        for x in w["shipment_items"]:
            if rng.random() < .7:
                new[x["si_id"]] = max(0, x["qty"] + rng.randrange(-x["qty"] - 20, 300, 10))
        if not any(new.get(x["si_id"], x["qty"]) != x["qty"] for x in w["shipment_items"]):
            new[w["shipment_items"][0]["si_id"]] = w["shipment_items"][0]["qty"] + 10
        req = build_payload(w, 50, new, "무작위", "테스트", rng.random() < .2, rid)
    return w, req


def test_l1_random_200_sql_equals_model(pg):
    from utils.shipment_revise import plan_revision
    from tests.test_revise_golden import _sorted_state, AFTER_TABLES
    bad, codes = [], {}
    for seed in range(200):
        w, req = rand_case(seed)
        res, after = plan_revision(w, req, "2026-11-06")
        g = {"state": w, "request": req, "today": "2026-11-06",
             "expect": {"result": json.loads(json.dumps(res)), "after": _sorted_state(after, AFTER_TABLES)}}
        d = run_golden(pg, g)
        key = "ok" if res.get("ok") else res["error"].split(":")[0]
        codes[key] = codes.get(key, 0) + 1
        if d:
            bad.append((seed, d))
    RESULTS["L1_random"] = {"n": 200, "mismatch": len(bad), "by_result": codes}
    assert not bad, json.dumps(bad[:3], ensure_ascii=False, default=str)[:4000]
    assert codes.get("ok", 0) >= 40, codes                      # 반영 경로가 충분히 섞였는지


# ── 동시성·실패 시험 보조(커밋된 시험 행 — 끝나면 지운다) ──
def _gold(name):
    return json.load(open(os.path.join(GOLD, f"g_{name}.json"), encoding="utf-8"))


def cleanup(pg):
    c = pg()
    cur = c.cursor()
    cur.execute("delete from shipment_revisions where shipment_id >= %s", (OFF,))
    cur.execute("delete from shipment_allocations where si_id >= %s or alloc_id >= %s", (OFF, OFF))
    cur.execute("delete from inventory_transactions where product_id like %s or ref_id >= %s or txn_id >= %s",
                ("%" + SFX, OFF, OFF))
    cur.execute("delete from shipment_items where si_id >= %s", (OFF,))
    cur.execute("delete from shipments where shipment_id >= %s", (OFF,))
    cur.execute("delete from so_delivery_schedule where sched_id >= %s", (OFF,))
    cur.execute("delete from sales_order_items where soi_id >= %s", (OFF,))
    cur.execute("delete from sales_orders where so_id >= %s", (OFF,))
    cur.execute("delete from products where product_id like %s", ("%" + SFX,))
    c.commit()
    c.close()


class World:
    """골든 state 를 커밋해 두 세션이 함께 보게 한다(with 블록 끝에 지움)."""

    def __init__(self, pg, state, extra=None):
        self.pg, self.state, self.extra = pg, state, extra

    def __enter__(self):
        cleanup(self.pg)
        c = self.pg()
        cur = c.cursor()
        self.ids = load_world(cur, self.state)
        if self.extra:
            self.extra(cur)
        c.commit()
        c.close()
        return self

    def __exit__(self, *a):
        cleanup(self.pg)


def _pid(conn):
    cur = conn.cursor()
    cur.execute("select pg_backend_pid()")
    return cur.fetchone()[0]


def _waiting(pg, pid, secs=6.0):
    """pid 가 잠금 대기 중인지(최대 secs 초 관찰)."""
    c = pg()
    c.autocommit = True
    try:
        cur = c.cursor()
        end = time.time() + secs
        while time.time() < end:
            cur.execute("select wait_event_type from pg_stat_activity where pid = %s", (pid,))
            r = cur.fetchone()
            if r and r[0] == "Lock":
                return True
            time.sleep(0.05)
        return False
    finally:
        c.close()


def _bg(pg, fn):
    """다른 세션에서 fn(cur) 실행 → (스레드, 결과 dict{pid, out})."""
    out = {}
    conn = pg()
    out["pid"] = _pid(conn)

    def run():
        try:
            cur = conn.cursor()
            cur.execute("set local lock_timeout = '20s'")
            out["out"] = fn(cur)
            conn.commit()
        except Exception as e:                                  # 거부·오류
            conn.rollback()
            out["out"] = ("exc", getattr(getattr(e, "diag", None), "message_primary", None) or str(e))
        finally:
            conn.close()
    th = threading.Thread(target=run)
    th.start()
    return th, out


def _rpc(name, *args):
    def fn(cur):
        cur.execute(f"select public.{name}({', '.join(['%s'] * len(args))})", args)
        return ("ok", cur.fetchone()[0])
    return fn


def _rev(payload, sid):
    return _rpc("revise_shipment", sid, json.dumps(payload, ensure_ascii=False))


def _q1(pg, sql, args=()):
    c = pg()
    try:
        cur = c.cursor()
        cur.execute(sql, args)
        return cur.fetchall()
    finally:
        c.rollback()
        c.close()


def _err_code(out):
    o = out["out"]
    return o[1].replace(SFX, "") if o[0] == "exc" else ("ok" if o[1].get("ok", True) else o)   # 종결 함수는 ok 키 없음


def _req(g, **kw):
    r = map_req(g["request"])
    r.update(kw)
    return r


def _draft(sid, ship_no, lines, rounds_delta, pid_lot):
    """작성중 전표 + 확정 payload(069 형식). lines=[(si, soi, so, sched, pid, qty)], rounds_delta=[(sched, soi, d)]."""
    def extra(cur):
        cur.execute("""insert into shipments (shipment_id, ship_no, ship_date, status, rev_no)
                       values (%s, %s, '2026-11-02', 'DRAFT', 0)""", (sid, ship_no + SFX))
        for si, soi, so, sched, pid, qty in lines:
            cur.execute("""insert into shipment_items (si_id, shipment_id, soi_id, so_id, sched_id, product_id, pn, qty, unit,
                           so_number) values (%s,%s,%s,%s,%s,%s,'4PDVN-03',%s,'EA','SO-x')""",
                        (si, sid, soi, so, sched, pid, qty))
    return extra


def _confirm_payload(lines, exp, scheds, allocs, lot):
    return json.dumps({
        "v": 1, "allow_over": False,
        "lines": [{"si_id": si, "soi_id": soi, "qty": q, "expected_received_before": exp[soi]}
                  for si, soi, so, sched, pid, q in lines],
        "scheds": [{"sched_id": s, "soi_id": soi, "delta": d} for s, soi, d in scheds],
        "allocs": [{"si_id": si, "sched_id": s, "qty": q} for si, s, q in allocs],
        "txns": [{"si_id": si, "product_id": pid, "qty": -q, "unit": "EA", "lot_number": lot, "work_order": lot,
                  "txn_date": "2026-11-02", "remark": "확정", "created_by": "테스트"}
                 for si, soi, so, sched, pid, q in lines]})


def _snap(pg, ids):
    c = pg()
    try:
        cur = c.cursor()
        w = read_world(cur, ids)
        return json.dumps(w, default=str, sort_keys=True)
    finally:
        c.rollback()
        c.close()


def _line_invariant(pg, sois):
    rows = _q1(pg, """select soi_id, qty, received_qty, pending_qty, closed_qty, status from sales_order_items
                      where soi_id = any(%s)""", (sois,))
    bad = []
    for soi, q, r, p, cl, st in rows:
        q, r, p, cl = float(q or 0), float(r or 0), float(p or 0), float(cl or 0)
        if st in ("CLOSED", "CANCELLED"):
            ok = p == 0 and abs(cl - max(q - r, 0)) < 1e-9
        elif st == "REPLACED":
            ok = p == 0
        else:
            ok = abs(p - max(q - r, 0)) < 1e-9 and cl == 0
        if not ok:
            bad.append((soi, q, r, p, cl, st))
    return bad


def _header_matches_lines(pg, so):
    from utils.so_close import header_status, is_inactive
    hdr = _q1(pg, "select status from sales_orders where so_id = %s", (so,))[0][0]
    if is_inactive(hdr):
        return True
    lines = [{"qty": q, "received_qty": r, "status": s} for q, r, s in
             _q1(pg, "select qty, received_qty, status from sales_order_items where so_id = %s", (so,))]
    return header_status(lines, hdr) == hdr


# ── L2 ──
def test_l2_same_shipment_two_sessions(pg):
    g = _gold("edit_decrease")
    with World(pg, g["state"]):
        a = pg()
        try:
            cur = a.cursor()
            k, r = call(cur, OFF + 50, _req(g), savepoint=False)
            assert k == "ok", r
            th, out = _bg(pg, _rev(_req(g, request_id=str(uuid.uuid4())), OFF + 50))
            assert _waiting(pg, out["pid"]), "B 가 전표 잠금에서 기다리지 않음"
            a.commit()
        finally:
            a.close()
        th.join(30)
        assert _err_code(out) == "stale_rev", out
        assert _q1(pg, "select rev_no from shipments where shipment_id=%s", (OFF + 50,))[0][0] == 1
        assert float(_q1(pg, "select received_qty from sales_order_items where soi_id=%s", (OFF + 11,))[0][0]) == 400
    RESULTS["L2"] = "pass"


# ── L3 ──
def _l3_world(g):
    ln = [(OFF + 701, OFF + 11, OFF + 100, OFF + 2, "P1" + SFX, 100)]
    return ln, _draft(OFF + 52, "SH-20261102-01", ln, None, None)


@pytest.mark.parametrize("first", ["revise", "confirm"])
def test_l3_revise_vs_confirm_same_line(pg, first):
    g = _gold("edit_decrease")
    ln, extra = _l3_world(g)
    with World(pg, g["state"], extra) as w:
        a = pg()
        try:
            cur = a.cursor()
            if first == "revise":
                k, r = call(cur, OFF + 50, _req(g), savepoint=False)
                assert k == "ok", r
                pay = _confirm_payload(ln, {OFF + 11: 500}, [(OFF + 2, OFF + 11, 100)], [(OFF + 701, OFF + 2, 100)], "W03")
                th, out = _bg(pg, _rpc("confirm_shipment", OFF + 52, pay))
            else:
                pay = _confirm_payload(ln, {OFF + 11: 500}, [(OFF + 2, OFF + 11, 100)], [(OFF + 701, OFF + 2, 100)], "W03")
                cur.execute("select public.confirm_shipment(%s, %s)", (OFF + 52, pay))
                th, out = _bg(pg, _rev(_req(g), OFF + 50))
            assert _waiting(pg, out["pid"]), "두 번째 세션이 수주 라인 잠금에서 기다리지 않음"
            a.commit()
        finally:
            a.close()
        th.join(30)
        if first == "revise":
            assert _err_code(out) == "stale", out                # 확정은 옛 납품량으로 계획 → stale(직렬화)
            pay = _confirm_payload(ln, {OFF + 11: 400}, [(OFF + 2, OFF + 11, 100)], [(OFF + 701, OFF + 2, 100)], "W03")
            c = pg()
            c.cursor().execute("select public.confirm_shipment(%s, %s)", (OFF + 52, pay))
            c.commit()
            c.close()
        else:
            assert _err_code(out) == "ok", out
        recv = float(_q1(pg, "select received_qty from sales_order_items where soi_id=%s", (OFF + 11,))[0][0])
        dsum = float(_q1(pg, "select sum(delivered_qty) from so_delivery_schedule where soi_id=%s", (OFF + 11,))[0][0])
        assert recv == 500 and dsum == 500, (recv, dsum)          # 500 − 100 + 100, 회차 합 = 납품
        assert not _line_invariant(pg, w.ids["sois"])
    RESULTS.setdefault("L3", {})[first] = "pass"


# ── L4 ──
@pytest.mark.parametrize("first", ["revise", "close"])
def test_l4_revise_vs_so_close(pg, first):
    g = _gold("edit_decrease")
    with World(pg, g["state"]) as w:
        a = pg()
        try:
            cur = a.cursor()
            if first == "revise":
                k, r = call(cur, OFF + 50, _req(g), savepoint=False)
                assert k == "ok", r
                th, out = _bg(pg, _rpc("so_close_lines", OFF + 100, "CLOSED", "월 변경 이월", "테스트"))
            else:
                cur.execute("select public.so_close_lines(%s, 'CLOSED', '월 변경 이월', '테스트')", (OFF + 100,))
                th, out = _bg(pg, _rev(_req(g), OFF + 50))
            assert _waiting(pg, out["pid"])
            a.commit()
        finally:
            a.close()
        th.join(30)
        assert _err_code(out) == "ok", out
        assert not _line_invariant(pg, w.ids["sois"]), _line_invariant(pg, w.ids["sois"])
        st, recv, cl = _q1(pg, "select status, received_qty, closed_qty from sales_order_items where soi_id=%s",
                           (OFF + 11,))[0]
        assert st == "CLOSED" and float(recv) == 400 and float(cl) == 1600, (st, recv, cl)
    RESULTS.setdefault("L4", {})[first] = "pass"


def test_l4_revise_d15_then_reopen(pg):
    """종결된 수주(D15)에서 정정 감소 ↔ so_reopen_lines: 되돌린 라인의 received + pending = qty."""
    g = _gold("edit_decrease")
    with World(pg, g["state"]) as w:
        c = pg()
        c.cursor().execute("select public.so_close_lines(%s, 'CLOSED', '월 변경 이월', '테스트')", (OFF + 100,))
        c.commit()
        c.close()
        a = pg()
        try:
            k, r = call(a.cursor(), OFF + 50, _req(g), savepoint=False)
            assert k == "ok", r
            th, out = _bg(pg, _rpc("so_reopen_lines", OFF + 100, "테스트"))
            assert _waiting(pg, out["pid"])
            a.commit()
        finally:
            a.close()
        th.join(30)
        assert _err_code(out) == "ok", out
        assert not _line_invariant(pg, w.ids["sois"]), _line_invariant(pg, w.ids["sois"])
        assert _header_matches_lines(pg, OFF + 100)
    RESULTS.setdefault("L4", {})["reopen"] = "pass"


# ── L5 ──
@pytest.mark.parametrize("first", ["revise", "confirm"])
def test_l5_cancel_vs_sibling_line_confirm(pg, first):
    """같은 수주의 형제 라인(soi 12)을 확정하는 동안 soi 11 전표 취소 → 머리글이 라인과 일치."""
    g = _gold("cancel_basic")

    def extra(cur):
        # soi 11 을 완납(500/500)으로 — 형제 확정이 옛 스냅샷으로 머리글을 집계하면 DELIVERED(틀림, 실제는 PARTIAL)가
        # 되어 「수주 전 라인 잠금」이 빠진 변이(02b ②)를 잡는다
        cur.execute("update sales_order_items set qty = 500, pending_qty = 0, status = 'DELIVERED' where soi_id = %s",
                    (OFF + 11,))
        # 형제 라인(soi 12)은 회차 없이(확정 미충당) — 회차 잠금이 아니라 「수주 전 라인 잠금」만으로 직렬화되는지 본다
        cur.execute("""insert into sales_order_items (soi_id, so_id, line_no, product_id, qty, received_qty, pending_qty,
                       status, unit, closed_qty) values (%s, %s, 2, %s, 100, 0, 100, 'PENDING', 'EA', 0)""",
                    (OFF + 12, OFF + 100, "P1" + SFX))
        _draft(OFF + 53, "SH-20261102-02", [(OFF + 712, OFF + 12, OFF + 100, None, "P1" + SFX, 100)], None, None)(cur)
    ln = [(OFF + 712, OFF + 12, OFF + 100, None, "P1" + SFX, 100)]
    pay = _confirm_payload(ln, {OFF + 12: 0}, [], [], "W03")
    with World(pg, g["state"], extra) as w:
        a = pg()
        try:
            cur = a.cursor()
            if first == "revise":
                k, r = call(cur, OFF + 50, _req(g), savepoint=False)
                assert k == "ok", r
                th, out = _bg(pg, _rpc("confirm_shipment", OFF + 53, pay))
            else:
                cur.execute("select public.confirm_shipment(%s, %s)", (OFF + 53, pay))
                th, out = _bg(pg, _rev(_req(g), OFF + 50))
            assert _waiting(pg, out["pid"]), "형제 라인 확정이 수주 전 라인 잠금에서 기다리지 않음"
            a.commit()
        finally:
            a.close()
        th.join(30)
        assert _err_code(out) == "ok", out
        assert _header_matches_lines(pg, OFF + 100), _q1(pg, "select status from sales_orders where so_id=%s",
                                                         (OFF + 100,))
        assert not _line_invariant(pg, w.ids["sois"] + [OFF + 12])
    RESULTS.setdefault("L5", {})[first] = "pass"


# ── L6 ──
def test_l6_crossing_two_orders_no_deadlock(pg):
    """전표 X(수주 100·200 취소) ↔ 작성중 Y(수주 200·100 확정)를 동시에 5회 — 교착 없음(또는 40P01 뒤 재호출 성공)."""
    g = _gold("cancel_two_so")
    ln = [(OFF + 721, OFF + 21, OFF + 200, OFF + 21, "P2" + SFX, 0), (OFF + 711, OFF + 11, OFF + 100, OFF + 2, "P1" + SFX, 0)]
    results = []
    for it in range(5):
        lines = [(si, soi, so, sc, pid, 10) for si, soi, so, sc, pid, _ in ln]

        def extra(cur, lines=lines):
            cur.execute("update so_delivery_schedule set qty = qty + 10 where sched_id = %s", (OFF + 21,))
            cur.execute("update sales_order_items set qty = qty + 10, pending_qty = pending_qty + 10, status='PARTIAL' "
                        "where soi_id = %s", (OFF + 21,))
            _draft(OFF + 54, "SH-20261102-03", lines, None, None)(cur)
        with World(pg, g["state"], extra):
            pay = _confirm_payload(lines, {OFF + 21: 100, OFF + 11: 500},
                                   [(OFF + 21, OFF + 21, 10), (OFF + 2, OFF + 11, 10)],
                                   [(OFF + 721, OFF + 21, 10), (OFF + 711, OFF + 2, 10)], "W03")
            th1, o1 = _bg(pg, _rev(_req(g), OFF + 50))
            th2, o2 = _bg(pg, _rpc("confirm_shipment", OFF + 54, pay))
            th1.join(40)
            th2.join(40)
            codes = (_err_code(o1), _err_code(o2))
            results.append(codes)
            for code, retry in ((codes[0], lambda: _rev(_req(g), OFF + 50)), ):
                pass
            assert all(c in ("ok", "stale") or "deadlock" in str(c) or "교착" in str(c) for c in codes), codes
    RESULTS["L6"] = results


# ── L7 ──
def test_l7_failures_leave_tables_unchanged(pg):
    g = _gold("edit_increase")
    c = pg()
    try:
        cur = c.cursor()
        ids = load_world(cur, g["state"])
        before = json.dumps(read_world(cur, ids), default=str, sort_keys=True)
        bad = _req(g)
        bad["inc"]["txns"][0]["qty"] = -150                     # 검증 단계 실패(txn_mismatch)
        k, r = call(cur, OFF + 50, bad)
        assert (k, r.replace(SFX, "")) == ("err", "txn_mismatch"), (k, r)
        assert json.dumps(read_world(cur, ids), default=str, sort_keys=True) == before
        # 마지막 단계(전표 머리글 UPDATE) 실패 — 임시 트리거(같은 트랜잭션, 롤백으로 사라짐)
        cur.execute("""create function pg_temp.p31_boom() returns trigger language plpgsql as
                       $$ begin raise exception 'boom_last_step'; end $$""")
        cur.execute("create trigger p31_boom before update on shipments for each row execute function pg_temp.p31_boom()")
        k, r = call(cur, OFF + 50, _req(g))
        assert k == "err" and "boom_last_step" in r, (k, r)
        cur.execute("drop trigger p31_boom on shipments")
        assert json.dumps(read_world(cur, ids), default=str, sort_keys=True) == before
    finally:
        c.rollback()
        c.close()
    RESULTS["L7"] = "pass"


@pytest.mark.parametrize("kind", ["alloc_left", "line_state", "issue_net", "alloc_over", "round"])
def test_l7b_postconditions_catch_defect(pg, kind):
    """사후 조건(§18 A1 · r2 data M3)이 실제로 걸리는지 — 임시 트리거로 구현 결함 상태를 만든다(같은 트랜잭션, 롤백).
    alloc_left: 충당 삭제를 막아 취소 뒤 충당이 남음 / line_state: 수주 라인 갱신 때 pending 을 어긋나게 /
    (정정 500→400) issue_net: 복원 ISSUE 를 두 배로 / alloc_over: 충당 감소·삭제를 막음 / round: 회차 납품완료를 1 덜."""
    g = _gold("edit_decrease" if kind in ("issue_net", "alloc_over", "round") else "cancel_basic")
    c = pg()
    try:
        cur = c.cursor()
        ids = load_world(cur, g["state"])
        before = json.dumps(read_world(cur, ids), default=str, sort_keys=True)
        if kind == "alloc_left":
            cur.execute("""create function pg_temp.p31_keep() returns trigger language plpgsql as
                           $$ begin return null; end $$""")
            cur.execute("create trigger p31_keep before delete on shipment_allocations for each row "
                        "execute function pg_temp.p31_keep()")
        elif kind == "issue_net":
            cur.execute("""create function pg_temp.p31_dbl() returns trigger language plpgsql as
                           $$ begin new.qty := new.qty * 2; return new; end $$""")
            cur.execute("create trigger p31_dbl before insert on inventory_transactions for each row "
                        "execute function pg_temp.p31_dbl()")
        elif kind == "alloc_over":
            cur.execute("""create function pg_temp.p31_keep() returns trigger language plpgsql as
                           $$ begin return null; end $$""")
            cur.execute("create trigger p31_keep before update or delete on shipment_allocations for each row "
                        "execute function pg_temp.p31_keep()")
        elif kind == "round":
            cur.execute("""create function pg_temp.p31_short() returns trigger language plpgsql as
                           $$ begin new.delivered_qty := new.delivered_qty - 1; return new; end $$""")
            cur.execute("create trigger p31_short before update on so_delivery_schedule for each row "
                        "execute function pg_temp.p31_short()")
        else:
            cur.execute("""create function pg_temp.p31_skew() returns trigger language plpgsql as
                           $$ begin new.pending_qty := coalesce(new.pending_qty, 0) + 1; return new; end $$""")
            cur.execute("create trigger p31_skew before update on sales_order_items for each row "
                        "execute function pg_temp.p31_skew()")
        k, r = call(cur, OFF + 50, _req(g))
        assert (k, r) == ("err", f"postcondition:{kind}"), (k, r)
        assert json.dumps(read_world(cur, ids), default=str, sort_keys=True) == before
    finally:
        c.rollback()
        c.close()
    RESULTS.setdefault("L7b", {})[kind] = "pass"


# ── L8 ──
def test_l8_request_id_replay_conflict_and_reuse(pg):
    g = _gold("edit_increase")
    c = pg()
    try:
        cur = c.cursor()
        ids = load_world(cur, g["state"])
        req = _req(g)
        k1, r1 = call(cur, OFF + 50, req)
        assert k1 == "ok" and not r1["replayed"], r1
        n_rows = len(read_world(cur, ids)["inventory_transactions"])
        k2, r2 = call(cur, OFF + 50, dict(req, who="다른 사람"))           # who 는 대조 밖
        assert k2 == "ok" and r2["replayed"] and r2["rev_no"] == r1["rev_no"], r2
        assert len(read_world(cur, ids)["inventory_transactions"]) == n_rows
        swapped = copy.deepcopy(req)
        swapped["inc"]["allocs"] = list(reversed(swapped["inc"]["allocs"]))
        swapped["lines"] = list(reversed(swapped["lines"]))
        assert call(cur, OFF + 50, swapped)[1]["replayed"]                  # 순서만 다른 동등 요청
        for mut in ("lot", "allow_over", "sched"):
            m = copy.deepcopy(req)
            if mut == "lot":
                m["inc"]["txns"][0]["lot_number"] = "W04"
                m["inc"]["txns"][0]["work_order"] = "W04"
            elif mut == "allow_over":
                m["allow_over"] = True
            else:
                m["inc"]["allocs"][0]["sched_id"] = OFF + 3
                m["inc"]["scheds"][0]["sched_id"] = OFF + 3
            assert call(cur, OFF + 50, m) == ("err", "request_conflict"), mut
    finally:
        c.rollback()
        c.close()
    # 거부된 뒤 같은 request_id 재사용 → 정상 반영(거부는 아무것도 쓰지 않았다)
    c = pg()
    try:
        cur = c.cursor()
        load_world(cur, g["state"])
        req = _req(g)
        assert call(cur, OFF + 50, dict(req, expected_rev_no=7)) == ("err", "stale_rev")
        k, r = call(cur, OFF + 50, req)
        assert k == "ok" and not r["replayed"], r
    finally:
        c.rollback()
        c.close()
    # 취소 재실행(CANCEL 정규화)
    gc = _gold("cancel_basic")
    c = pg()
    try:
        cur = c.cursor()
        load_world(cur, gc["state"])
        req = _req(gc)
        assert call(cur, OFF + 50, req)[0] == "ok"
        k, r = call(cur, OFF + 50, dict(req, who="재시도", reason=req["reason"] + "  "))
        assert k == "ok" and r["replayed"], r                    # 사유 앞뒤 공백·who 무관
    finally:
        c.rollback()
        c.close()
    # 두 세션 동시 같은 요청 → 하나 반영, 다른 하나는 기다렸다가 replayed(stale_rev 아님)
    with World(pg, g["state"]) as wd:
        a = pg()
        try:
            k, r = call(a.cursor(), OFF + 50, _req(g), savepoint=False)
            assert k == "ok", r
            th, out = _bg(pg, _rev(_req(g), OFF + 50))
            assert _waiting(pg, out["pid"])
            a.commit()
        finally:
            a.close()
        th.join(30)
        assert out["out"][0] == "ok" and out["out"][1]["replayed"], out
        # r3(data REQ 3): 유니크 인덱스 대신 전표 잠금 + 재실행 판정 — 이력 행 = 라인 수, 원장은 A 의 반영분만
        rid = _req(g)["request_id"]
        n_rev = _q1(pg, "select count(*) from shipment_revisions where request_id = %s", (rid,))[0][0]
        assert n_rev == len(_req(g)["lines"]), n_rev
        n_tx = _q1(pg, "select count(*) from inventory_transactions where ref_table = 'shipment_items' "
                       "and ref_id = any(%s)", (wd.ids["sis"],))[0][0]
        assert n_tx == len(g["state"]["inventory_transactions"]) + r["inc_txns"] + r["restored_txns"], n_tx
        RESULTS["L8_concurrent"] = {"revisions": n_rev, "ledger_rows": n_tx, "b_replayed": True}
    RESULTS["L8"] = "pass"


# ── L9 ──
def test_l9_two_shipments_cancel_same_line(pg):
    g = _gold("cancel_basic")

    def extra(cur):
        cur.execute("update sales_order_items set received_qty = 800, pending_qty = 1200 where soi_id = %s", (OFF + 11,))
        cur.execute("update so_delivery_schedule set delivered_qty = 300 where sched_id = %s", (OFF + 2,))
        cur.execute("""insert into shipments (shipment_id, ship_no, ship_date, status, rev_no)
                       values (%s, %s, '2026-11-02', 'CONFIRMED', 0)""", (OFF + 55, "SH-20261102-05" + SFX))
        cur.execute("""insert into shipment_items (si_id, shipment_id, soi_id, so_id, sched_id, product_id, pn, qty, unit,
                       so_number) values (%s,%s,%s,%s,%s,%s,'4PDVN-03',300,'EA','SO-100')""",
                    (OFF + 755, OFF + 55, OFF + 11, OFF + 100, OFF + 2, "P1" + SFX))
        cur.execute("insert into shipment_allocations (si_id, sched_id, qty) values (%s, %s, 300)", (OFF + 755, OFF + 2))
        cur.execute("""insert into inventory_transactions (material_id, product_id, txn_type, qty, unit, lot_number,
                       ref_table, ref_id, txn_date) values (null, %s, 'ISSUE', -300, 'EA', 'W05', 'shipment_items', %s,
                       '2026-11-02')""", ("P1" + SFX, OFF + 755))
    with World(pg, g["state"], extra):
        req2 = {"v": "1", "action": "CANCEL", "request_id": str(uuid.uuid4()), "expected_rev_no": 0,
                "reason": "동시 취소", "who": "테스트"}
        th1, o1 = _bg(pg, _rev(_req(g), OFF + 50))
        th2, o2 = _bg(pg, _rev(req2, OFF + 55))
        th1.join(30)
        th2.join(30)
        assert _err_code(o1) == "ok" and _err_code(o2) == "ok", (o1, o2)
        assert float(_q1(pg, "select received_qty from sales_order_items where soi_id=%s", (OFF + 11,))[0][0]) == 0
    RESULTS["L9"] = "pass"


# ── L10 ──
def test_l10_increase_vs_confirm_stock(pg):
    """재고 100 에 정정 증가 80 ↔ 확정 80(둘 다 allow_over=false) → 정확히 하나만 stock: 거부."""
    g = _gold("edit_increase")
    st = copy.deepcopy(g["state"])
    for p in st["product_stock_v"]:
        if p["product_id"] == "P1":
            p["current_stock"] = 100
    # 확정은 같은 제품의 다른 수주 라인(soi 12)으로 — 같은 수주 라인이면 라인 잠금에서 먼저 stale 로 갈린다
    ln = [(OFF + 731, OFF + 12, OFF + 100, OFF + 12, "P1" + SFX, 80)]
    req = map_req(g["request"])
    req["lines"][0]["qty_after"] = 580
    req["inc"]["scheds"][0]["delta"] = 80
    req["inc"]["allocs"][0]["qty"] = 80
    req["inc"]["txns"] = [dict(req["inc"]["txns"][0], qty=-80)]

    def extra(cur):
        cur.execute("""insert into sales_order_items (soi_id, so_id, line_no, product_id, qty, received_qty, pending_qty,
                       status, unit, closed_qty) values (%s, %s, 2, %s, 100, 0, 100, 'PENDING', 'EA', 0)""",
                    (OFF + 12, OFF + 100, "P1" + SFX))
        cur.execute("""insert into so_delivery_schedule (sched_id, so_id, soi_id, seq, due_date, qty, delivered_qty)
                       values (%s, %s, %s, 1, '2026-11-02', 100, 0)""", (OFF + 12, OFF + 100, OFF + 12))
        _draft(OFF + 56, "SH-20261102-06", ln, None, None)(cur)
    with World(pg, st, extra):
        pay = _confirm_payload(ln, {OFF + 12: 0}, [(OFF + 12, OFF + 12, 80)], [(OFF + 731, OFF + 12, 80)], "W04")
        th1, o1 = _bg(pg, _rev(req, OFF + 50))
        th2, o2 = _bg(pg, _rpc("confirm_shipment", OFF + 56, pay))
        th1.join(30)
        th2.join(30)
        codes = sorted([_err_code(o1), _err_code(o2)], key=str)
        oks = [c for c in codes if c == "ok"]
        rej = [c for c in codes if str(c).startswith("stock:")]
        assert len(oks) == 1 and len(rej) == 1, codes
    RESULTS["L10"] = codes


# ── L11 ──
def test_l11_revise_vs_sched_save(pg):
    """정정이 회차 잠금을 쥔 동안 납기 저장(REST 조건부 갱신)은 기다리고, delivered 가 바뀐 회차는 0행(덮어쓰기 없음).
    정정이 건드리지 않는 회차의 qty 만 바꾸는 저장은 기다렸다가 반영된다."""
    g = _gold("edit_decrease")
    with World(pg, g["state"]):
        a = pg()
        try:
            k, r = call(a.cursor(), OFF + 50, _req(g), savepoint=False)
            assert k == "ok", r

            def save(cur):
                cur.execute("update so_delivery_schedule set qty = 600 where sched_id = %s and delivered_qty = 500",
                            (OFF + 1,))
                n1 = cur.rowcount
                cur.execute("update so_delivery_schedule set qty = 550 where sched_id = %s and delivered_qty = 0",
                            (OFF + 2,))
                return ("ok", {"ok": True, "n1": n1, "n2": cur.rowcount})
            th, out = _bg(pg, save)
            assert _waiting(pg, out["pid"])
            a.commit()
        finally:
            a.close()
        th.join(30)
        assert out["out"][1]["n1"] == 0 and out["out"][1]["n2"] == 1, out
        q1, d1 = _q1(pg, "select qty, delivered_qty from so_delivery_schedule where sched_id=%s", (OFF + 1,))[0]
        assert (float(q1), float(d1)) == (500, 400), (q1, d1)
        assert float(_q1(pg, "select qty from so_delivery_schedule where sched_id=%s", (OFF + 2,))[0][0]) == 550
    RESULTS["L11"] = "pass"


# ── L12 ──
def test_l12_permissions_tz_and_reapply(pg):
    g = _gold("cancel_basic")
    c = pg()
    try:
        cur = c.cursor()
        for role in ("anon", "authenticated"):
            cur.execute("savepoint r")
            cur.execute(f"set local role {role}")
            try:
                cur.execute("select public.revise_shipment(%s, '{}'::jsonb)", (OFF + 50,))
                assert False, f"{role} 가 실행함"
            except Exception as e:
                assert "permission" in str(e).lower() or "권한" in str(e), e
            cur.execute("rollback to savepoint r")
        cur.execute("set local time zone 'UTC'")
        ids = load_world(cur, g["state"])
        assert call(cur, OFF + 50, _req(g))[0] == "ok"
        dates = {str(t["txn_date"])[:10] for t in read_world(cur, ids)["inventory_transactions"] if t["qty"] > 0}
        assert dates == {_kst_today()}, dates
        cur.execute(open(os.path.join(ROOT, "supabase", "migrations", "082_revise_shipment_rpc.sql"),
                         encoding="utf-8").read())               # 한 번 더 적용(멱등) — 롤백
    finally:
        c.rollback()
        c.close()
    RESULTS["L12"] = "pass"


# ── L13 ── 전수 드라이런(복원 DB 의 실제 확정 전표, 전표마다 SAVEPOINT → ROLLBACK)
DATA_REASON_CODES = {"legacy_no_alloc", "issue_mismatch", "round_short", "recv_underflow"}
DQ_CODES = ("ROUND_MISMATCH", "SHIP_ALLOC_MISMATCH")


def _inv(cur, sid):
    """외부 불변식 스냅샷(r2 data M4) — 이 전표 라인·영향 수주 라인·그 회차·머리글·dq 건수."""
    cur.execute("select si_id, soi_id, nullif(product_id, ''), coalesce(qty, 0) from shipment_items "
                "where shipment_id = %s order by si_id", (sid,))
    items = cur.fetchall()
    sois = sorted({x[1] for x in items if x[1] is not None})
    cur.execute("select distinct so_id from sales_order_items where soi_id = any(%s)", (sois,))
    sos = sorted(r[0] for r in cur.fetchall() if r[0] is not None)
    cur.execute("""select d.sched_id from so_delivery_schedule d
                   cross join lateral (select coalesce(sum(a.qty), 0) al from shipment_allocations a
                                        where a.sched_id = d.sched_id) x
                   where d.soi_id in (select soi_id from sales_order_items where so_id = any(%s))
                     and (coalesce(d.delivered_qty, 0) < x.al - 1e-9 or x.al < -1e-9)""", (sos,))
    bad_rounds = {r[0] for r in cur.fetchall()}
    cur.execute("""select d.sched_id from so_delivery_schedule d join sales_order_items l on l.soi_id = d.soi_id
                   where l.so_id = any(%s) and upper(coalesce(l.status, '')) in ('CLOSED', 'CANCELLED')
                     and coalesce(d.qty, 0) > coalesce(d.delivered_qty, 0) + 1e-9""", (sos,))
    open_closed = {r[0] for r in cur.fetchall()}
    cur.execute("select code, count(*) from data_quality_v where code = any(%s) group by 1", (list(DQ_CODES),))
    dq = dict(cur.fetchall())
    return {"items": items, "sos": sos, "bad_rounds": bad_rounds, "open_closed": open_closed, "dq": dq}


def _line_net(cur, si):
    cur.execute("""select coalesce(sum(qty), 0) from inventory_transactions
                   where ref_table = 'shipment_items' and txn_type = 'ISSUE' and ref_id = %s""", (si,))
    return float(cur.fetchone()[0])


def _line_alloc(cur, si):
    cur.execute("select coalesce(sum(qty), 0) from shipment_allocations where si_id = %s", (si,))
    return float(cur.fetchone()[0])


def _check_after(cur, sid, b, changed, so_ids, dq_may_rise=False):
    """성공한 정정·취소 뒤 외부 불변식 → 위반 목록. changed = {si: 정정 뒤 수량}(취소면 전 라인 0),
    so_ids = 함수가 머리글을 다시 계산한 수주(결과 so_ids) — 그 밖의 수주 머리글은 무접촉이라 비교하지 않는다
    (복원 DB 에 원래 어긋난 머리글이 있음: so 59·60 PARTIAL·활성 라인 전부 DELIVERED — 범위 밖 관찰)."""
    from utils.so_close import header_status
    errs = []
    a = _inv(cur, sid)
    for si, soi, pid, _q in b["items"]:
        if si not in changed:
            continue
        net, al = _line_net(cur, si), _line_alloc(cur, si)
        if pid is not None and abs(net + changed[si]) > 1e-6:
            errs.append(f"si {si} ISSUE 순합 {net} ≠ −{changed[si]}")
        if al > changed[si] + 1e-6:
            errs.append(f"si {si} 충당 {al} > {changed[si]}")
    if a["bad_rounds"] - b["bad_rounds"]:
        errs.append("회차 납품완료 < Σ충당 새로 생김 " + str(sorted(a["bad_rounds"] - b["bad_rounds"])))
    if a["open_closed"] - b["open_closed"]:
        errs.append("닫힌 라인에 열린 회차 새로 생김 " + str(sorted(a["open_closed"] - b["open_closed"])))
    for so in so_ids:
        cur.execute("select status from sales_orders where so_id = %s", (so,))
        hs = cur.fetchone()[0]
        if str(hs or "").upper() in ("CLOSED", "CANCELLED", "CANCELED"):
            continue
        cur.execute("select qty, received_qty, status from sales_order_items where so_id = %s", (so,))
        lines = [{"qty": q, "received_qty": r, "status": st_} for q, r, st_ in cur.fetchall()]
        if header_status(lines, hs) != hs:
            errs.append(f"so {so} 머리글 {hs} ≠ {header_status(lines, hs)}")
    for k in DQ_CODES:
        # 증가분을 실을 회차 여유가 없어 미충당(unallocated 안내, §4-7 #11 · 069 와 같음)이면 두 dq 가 늘 수 있다(설계)
        if not dq_may_rise and a["dq"].get(k, 0) > b["dq"].get(k, 0):
            errs.append(f"dq {k} {b['dq'].get(k, 0)} → {a['dq'].get(k, 0)}")
    return errs


def _confirmed(cur):
    cur.execute("select shipment_id, ship_no, rev_no from shipments where status='CONFIRMED' and shipment_id < %s "
                "order by shipment_id", (OFF,))
    return cur.fetchall()


def test_l13_full_dry_run_cancel_every_confirmed(pg):
    c = pg()
    rejected, ok, slow, errs = {}, 0, (0.0, None), []
    try:
        cur = c.cursor()
        ships = _confirmed(cur)
        for sid, no, rev in ships:
            cur.execute("savepoint dry")
            b = _inv(cur, sid)
            t0 = time.perf_counter()
            k, r = call(cur, sid, {"v": "1", "action": "CANCEL", "request_id": str(uuid.uuid4()),
                                   "expected_rev_no": rev or 0, "reason": "전수 드라이런", "who": "시험"},
                        savepoint=False)
            el = time.perf_counter() - t0
            if el > slow[0]:
                slow = (el, no)
            if k == "ok":
                ok += 1
                cur.execute("""select count(*) from shipment_allocations a join shipment_items si on si.si_id=a.si_id
                               where si.shipment_id=%s""", (sid,))
                if cur.fetchone()[0]:
                    errs.append((no, "alloc_left"))
                errs += [(no, e) for e in _check_after(cur, sid, b, {x[0]: 0.0 for x in b["items"]},
                                                       r.get("so_ids") or [])]
            else:
                rejected[no] = r
            cur.execute("rollback to savepoint dry")
    finally:
        c.rollback()
        c.close()
    RESULTS["L13"] = {"confirmed": len(ships), "ok": ok, "rejected": rejected, "slowest_sec": round(slow[0], 3),
                      "slowest_ship": slow[1], "post_errors": errs,
                      "external_invariants": "라인 ISSUE 순합 0·충당 0·회차 납품완료≥Σ충당≥0·닫힌 라인 열린 회차·"
                                             "머리글=header_status·dq ROUND/SHIP_ALLOC 증가 없음"}
    assert not errs, errs
    assert set(rejected) == EXPECTED_REJECTED_SHIPS, sorted(set(rejected) ^ EXPECTED_REJECTED_SHIPS)


def test_l13b_edit_dry_run_every_confirmed(pg):
    """r2 data M4: 운영 형태 EDIT 드라이런 — 확정 전표마다 ① 각 라인 −1 ② 단일 라인(가장 작은 si) 전량 감소
    → 외부 불변식 → ROLLBACK. 거부는 데이터 사유(고정 목록 12장 안)나 use_cancel 만."""
    c = pg()
    out = {"minus1": {"ok": 0, "rejected": {}}, "one_line_zero": {"ok": 0, "rejected": {}, "skipped": 0}}
    errs, slow = [], (0.0, None)
    try:
        cur = c.cursor()
        ships = _confirmed(cur)
        for sid, no, rev in ships:
            cur.execute("select si_id, qty from shipment_items where shipment_id = %s and qty > 1e-9 order by si_id",
                        (sid,))
            live = [(si, float(q)) for si, q in cur.fetchall()]
            cases = [("minus1", {si: q - 1 for si, q in live if q >= 1})]
            if len(live) >= 2:
                cases.append(("one_line_zero", {live[0][0]: 0.0}))
            else:
                out["one_line_zero"]["skipped"] += 1
            for name, new in cases:
                if not new:
                    continue
                cur.execute("savepoint dry")
                b = _inv(cur, sid)
                qmap = dict(live)
                payload = {"v": "1", "action": "EDIT", "request_id": str(uuid.uuid4()), "expected_rev_no": rev or 0,
                           "reason": "EDIT 드라이런", "who": "시험",
                           "lines": [{"si_id": si, "qty_before": qmap[si], "qty_after": q}
                                     for si, q in sorted(new.items())]}
                t0 = time.perf_counter()
                k, r = call(cur, sid, payload, savepoint=False)
                el = time.perf_counter() - t0
                if el > slow[0]:
                    slow = (el, f"{no} {name}")
                if k == "ok":
                    out[name]["ok"] += 1
                    errs += [(no, name, e) for e in _check_after(cur, sid, b, new, r.get("so_ids") or [])]
                else:
                    out[name]["rejected"][no] = r
                cur.execute("rollback to savepoint dry")
    finally:
        c.rollback()
        c.close()
    out.update({"confirmed": len(ships), "post_errors": errs, "slowest_sec": round(slow[0], 3), "slowest": slow[1]})
    RESULTS["L13b"] = out
    assert not errs, errs
    for name in ("minus1", "one_line_zero"):
        rej = out[name]["rejected"]
        bad = {no: code for no, code in rej.items() if code not in DATA_REASON_CODES and code != "use_cancel"}
        assert not bad, (name, bad)
        assert {no for no, code in rej.items() if code in DATA_REASON_CODES} <= EXPECTED_REJECTED_SHIPS, (name, rej)


# ── L13c ── 증가 운영 형태 드라이런(r3, data M2·qa REQUIRED 6)
INC_OK_REJECTS = {"line_closed", "over_pending", "line_unlinked"} | DATA_REASON_CODES


def _rows(cur, sql, args=()):
    cur.execute(sql, args)
    cols = [d[0] for d in cur.description]
    out = []
    for r in cur.fetchall():
        d = {}
        for k, v in zip(cols, r):
            if isinstance(v, decimal.Decimal):
                v = float(v)
            elif isinstance(v, (dt.date, dt.datetime)):
                v = v.isoformat()
            d[k] = v
        out.append(d)
    return out


def _screen_state(cur, sid, rev, ship_date):
    """화면 _cf_rv_state 와 같은 열·같은 범위의 상태(build_payload 입력)."""
    items = _rows(cur, "select si_id, shipment_id, soi_id, so_id, sched_id, product_id, pn, customer_pn, qty, unit, "
                       "so_number from shipment_items where shipment_id = %s order by si_id", (sid,))
    sis = [x["si_id"] for x in items]
    sois = sorted({x["soi_id"] for x in items if x["soi_id"] is not None})
    pids = sorted({x["product_id"] for x in items if x["product_id"]})
    return {"shipments": [{"shipment_id": sid, "rev_no": rev or 0, "ship_date": ship_date}],
            "shipment_items": items,
            "shipment_allocations": _rows(cur, "select alloc_id, si_id, sched_id, qty from shipment_allocations "
                                               "where si_id = any(%s) order by alloc_id", (sis,)),
            "inventory_transactions": _rows(cur, "select txn_id, ref_table, ref_id, txn_type, lot_number, qty, product_id, "
                                                 "material_id from inventory_transactions where ref_table='shipment_items' "
                                                 "and txn_type='ISSUE' and ref_id = any(%s) order by txn_id", (sis,)),
            "sales_order_items": _rows(cur, "select soi_id, so_id, qty, received_qty, pending_qty, unit, status "
                                            "from sales_order_items where soi_id = any(%s)", (sois,)),
            "so_delivery_schedule": _rows(cur, "select sched_id, so_id, soi_id, seq, due_date, qty, delivered_qty "
                                               "from so_delivery_schedule where soi_id = any(%s) order by sched_id",
                                          (sois,)),
            "product_lot_stock_v": _rows(cur, "select product_id, lot_number, remain_qty, first_output_date "
                                              "from product_lot_stock_v where product_id = any(%s) and remain_qty > 0 "
                                              "order by first_output_date, lot_number", (pids,))}


def test_l13c_increase_dry_run_every_confirmed(pg):
    """확정 전표마다 미납이 남은 제품 연결 라인 하나에 +1(화면과 같은 build_payload, allow_over) → 거부는 정해진 코드만,
    postcondition:* 0건, 성공 건은 외부 불변식 위반 0 → ROLLBACK."""
    from utils.shipment_revise import build_payload
    c = pg()
    out = {"ok": 0, "rejected": {}, "no_candidate": 0, "unallocated": 0}
    errs, bad, slow = [], {}, (0.0, None)
    try:
        cur = c.cursor()
        cur.execute("select shipment_id, ship_no, rev_no, ship_date from shipments where status='CONFIRMED' "
                    "and shipment_id < %s order by shipment_id", (OFF,))
        ships = cur.fetchall()
        for sid, no, rev, sdate in ships:
            cur.execute("""select si.si_id, si.qty from shipment_items si
                             join sales_order_items l on l.soi_id = si.soi_id
                             join sales_orders o on o.so_id = l.so_id
                            where si.shipment_id = %s and nullif(si.product_id, '') is not null
                              and coalesce(l.qty, 0) - coalesce(l.received_qty, 0) >= 1
                              and upper(coalesce(l.status, '')) not in ('CLOSED', 'CANCELLED', 'REPLACED')
                              and upper(coalesce(o.status, '')) not in ('CLOSED', 'CANCELLED', 'CANCELED')
                            order by si.si_id limit 1""", (sid,))
            pick = cur.fetchone()
            if not pick:
                out["no_candidate"] += 1
                continue
            si, q = pick[0], float(pick[1])
            cur.execute("savepoint dry")
            b = _inv(cur, sid)
            payload = build_payload(_screen_state(cur, sid, rev, str(sdate)), sid, {si: q + 1}, "증가 드라이런", "시험",
                                    True, str(uuid.uuid4()))
            payload.pop("shipment_id", None)
            t0 = time.perf_counter()
            k, r = call(cur, sid, payload, savepoint=False)
            el = time.perf_counter() - t0
            if el > slow[0]:
                slow = (el, no)
            if k == "ok":
                out["ok"] += 1
                unal = any(e.get("kind") == "unallocated" for e in r.get("info") or [])
                out["unallocated"] += unal
                errs += [(no, e) for e in _check_after(cur, sid, b, {si: q + 1}, r.get("so_ids") or [],
                                                       dq_may_rise=unal)]
            else:
                out["rejected"][no] = r
                if r.split(":")[0] not in INC_OK_REJECTS:
                    bad[no] = r
            cur.execute("rollback to savepoint dry")
    finally:
        c.rollback()
        c.close()
    out.update({"confirmed": len(ships), "post_errors": errs, "unexpected_rejects": bad,
                "slowest_sec": round(slow[0], 3), "slowest": slow[1]})
    RESULTS["L13c"] = out
    assert not [v for v in out["rejected"].values() if v.startswith("postcondition")], out["rejected"]
    assert not bad, bad
    assert not errs, errs


# ── L14 ── 뷰 shipment_revise_blockers_v 실DB(r3, qa M4·REQUIRED 5)
def _model_world(cur):
    """모델 check 용 전체 상태(복원 DB 의 실제 행)."""
    return {"shipments": _rows(cur, "select shipment_id, ship_no, ship_date, status, rev_no from shipments"),
            "shipment_items": _rows(cur, "select si_id, shipment_id, soi_id, product_id, qty from shipment_items"),
            "shipment_allocations": _rows(cur, "select alloc_id, si_id, sched_id, qty from shipment_allocations"),
            "inventory_transactions": _rows(cur, "select txn_id, ref_table, ref_id, txn_type, lot_number, qty, product_id, "
                                                 "material_id from inventory_transactions where ref_table='shipment_items' "
                                                 "and txn_type='ISSUE'"),
            "so_delivery_schedule": _rows(cur, "select sched_id, soi_id, qty, delivered_qty, due_date from so_delivery_schedule"),
            "sales_order_items": _rows(cur, "select soi_id, so_id, qty, received_qty, status from sales_order_items"),
            "shipment_revisions": _rows(cur, "select rev_id, shipment_id, action, si_id from shipment_revisions"),
            "sales_month_close": _rows(cur, "select ym from sales_month_close")}


def test_l14_blockers_view_equals_function_and_model(pg):
    from utils.shipment_revise import check
    c = pg()
    res = {"confirmed": 0, "blocked": {}, "mismatch": []}
    try:
        cur = c.cursor()
        world = _model_world(cur)
        for sh in sorted((s for s in world["shipments"] if s["status"] == "CONFIRMED" and s["shipment_id"] < OFF),
                         key=lambda s: s["shipment_id"]):
            sid = sh["shipment_id"]
            res["confirmed"] += 1
            cur.execute("select chk from shipment_revise_blockers_v where shipment_id = %s", (sid,))
            rows = cur.fetchall()
            cur.execute("select public.revise_shipment_check(%s)", (sid,))
            fn = cur.fetchone()[0]
            if len(rows) != 1 or rows[0][0] != fn:
                res["mismatch"].append((sh["ship_no"], "view≠function"))
                continue
            mo = check(world, sid)
            mo_lines = {str(k): sorted(v) for k, v in mo["lines"].items()}
            fn_lines = {k: sorted(v) for k, v in (fn.get("lines") or {}).items()}
            if (mo_lines != fn_lines or bool(mo["month_closed"]) != bool(fn.get("month_closed"))
                    or bool(mo["partial_cancel_legacy"]) != bool(fn.get("partial_cancel_legacy"))):
                res["mismatch"].append((sh["ship_no"], {"sql": fn_lines, "model": mo_lines}))
            if fn_lines:
                res["blocked"][sh["ship_no"]] = fn_lines
        cur.execute("select count(*) from shipment_revise_blockers_v v join shipments s using (shipment_id) "
                    "where s.status <> 'CONFIRMED'")
        assert cur.fetchone()[0] == 0
        # 권한·옵션·인덱스
        for role in ("anon", "authenticated"):
            cur.execute("savepoint r")
            cur.execute(f"set local role {role}")
            try:
                cur.execute("select 1 from shipment_revise_blockers_v limit 1")
                assert False, f"{role} 가 뷰를 읽음"
            except Exception as e:
                assert "permission" in str(e).lower() or "권한" in str(e), e
            cur.execute("rollback to savepoint r")
        cur.execute("select reloptions from pg_class where relname = 'shipment_revise_blockers_v'")
        assert "security_invoker=true" in (cur.fetchone()[0] or []), "security_invoker"
        cur.execute("select privilege_type from information_schema.role_table_grants "
                    "where table_name = 'shipment_revise_blockers_v' and grantee = 'service_role'")
        res["service_role_privileges"] = sorted(r[0] for r in cur.fetchall())
        assert res["service_role_privileges"] == ["SELECT"], res["service_role_privileges"]
        cur.execute("select indexname, indexdef from pg_indexes where tablename = 'shipment_revisions' "
                    "and indexname like 'shipment_revisions_request%%'")
        idx = dict(cur.fetchall())
        res["indexes"] = idx
        assert set(idx) == {"shipment_revisions_request_idx"} and "UNIQUE" not in idx["shipment_revisions_request_idx"], idx
        cur.execute("explain (analyze, format json) select shipment_id, chk from shipment_revise_blockers_v "
                    "where shipment_id = %s limit 1", (ships_first(cur),))
        res["explain_filtered_ms"] = cur.fetchone()[0][0]["Execution Time"]
    finally:
        c.rollback()
        c.close()
    RESULTS["L14"] = res
    assert not res["mismatch"], res["mismatch"]
    assert set(res["blocked"]) == EXPECTED_REJECTED_SHIPS, sorted(set(res["blocked"]) ^ EXPECTED_REJECTED_SHIPS)


def ships_first(cur):
    cur.execute("select min(shipment_id) from shipments where status = 'CONFIRMED' and shipment_id < %s", (OFF,))
    return cur.fetchone()[0]


@pytest.fixture(scope="module", autouse=True)
def _write_results(request):
    yield
    out = os.environ.get("REVISE_LOCAL_RESULTS")
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(RESULTS, f, ensure_ascii=False, indent=1, default=str)
