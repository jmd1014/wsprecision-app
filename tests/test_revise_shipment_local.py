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
        req = build_payload(w, 50, {}, "무작위", "테스트", rng.random() < .2, rid, "2026-11-06", action="CANCEL")
    else:
        new = {}
        for x in w["shipment_items"]:
            if rng.random() < .7:
                new[x["si_id"]] = max(0, x["qty"] + rng.randrange(-x["qty"] - 20, 300, 10))
        if not any(new.get(x["si_id"], x["qty"]) != x["qty"] for x in w["shipment_items"]):
            new[w["shipment_items"][0]["si_id"]] = w["shipment_items"][0]["qty"] + 10
        req = build_payload(w, 50, new, "무작위", "테스트", rng.random() < .2, rid, "2026-11-06")
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


@pytest.mark.parametrize("kind", ["alloc_left", "line_state"])
def test_l7b_postconditions_catch_defect(pg, kind):
    """사후 조건(§18 A1)이 실제로 걸리는지 — 임시 트리거로 구현 결함 상태를 만든다(같은 트랜잭션, 롤백으로 사라짐).
    alloc_left: 충당 삭제를 막아 취소 뒤 충당이 남음 / line_state: 수주 라인 갱신 때 pending 을 어긋나게."""
    g = _gold("cancel_basic")
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
    with World(pg, g["state"]):
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


# ── L13 ──
def test_l13_full_dry_run_cancel_every_confirmed(pg):
    c = pg()
    rejected, ok, slow, errs = {}, 0, (0.0, None), []
    try:
        cur = c.cursor()
        cur.execute("select shipment_id, ship_no, rev_no from shipments where status='CONFIRMED' and shipment_id < %s "
                    "order by shipment_id", (OFF,))
        ships = cur.fetchall()
        for sid, no, rev in ships:
            cur.execute("savepoint dry")
            t0 = time.perf_counter()
            k, r = call(cur, sid, {"v": "1", "action": "CANCEL", "request_id": str(uuid.uuid4()),
                                   "expected_rev_no": rev or 0, "reason": "전수 드라이런", "who": "시험"},
                        savepoint=False) if True else None
            el = time.perf_counter() - t0
            if el > slow[0]:
                slow = (el, no)
            if k == "ok":
                ok += 1
                cur.execute("""select count(*) from shipment_allocations a join shipment_items si on si.si_id=a.si_id
                               where si.shipment_id=%s""", (sid,))
                if cur.fetchone()[0]:
                    errs.append((no, "alloc_left"))
            else:
                rejected[no] = r
            cur.execute("rollback to savepoint dry")
    finally:
        c.rollback()
        c.close()
    RESULTS["L13"] = {"confirmed": len(ships), "ok": ok, "rejected": rejected, "slowest_sec": round(slow[0], 3),
                      "slowest_ship": slow[1], "post_errors": errs}
    assert not errs, errs
    assert set(rejected) == EXPECTED_REJECTED_SHIPS, sorted(set(rejected) ^ EXPECTED_REJECTED_SHIPS)


@pytest.fixture(scope="module", autouse=True)
def _write_results(request):
    yield
    out = os.environ.get("REVISE_LOCAL_RESULTS")
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(RESULTS, f, ensure_ascii=False, indent=1, default=str)
