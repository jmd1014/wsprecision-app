# -*- coding: utf-8 -*-
"""L3-D: 열린 작업지시 일괄 정리 (2026-10-26, 계획서 _작업지시_일괄정리_L3D_계획서_20261026.md §1~§3).

규칙: 출고 근거로 끝난 것으로 보이는 열린 지시(완료 추정·출고 근거만·부분 완료·근거 없음·수량 0)는
남은 수량 전량을 완성 확정하고 종결. 외주·재작업 잔량(확인 필요)과 7일 내 투입(유지)은 건드리지 않는다.
분류 계산은 기획 세션 C:\\Users\\Public\\wsapp-review\\tools\\make_wo_cleanup.py 와 같다(옮겨 씀).

사용:
  python scripts/wo_bulk_cleanup_20261026.py                    드라이런(읽기 전용) — 대상·유지 목록, 품번별 PROD_OUTPUT 합,
                                                                10-23 후보표 대조 → _작업지시_일괄정리_드라이런_YYYYMMDD.md
  python scripts/wo_bulk_cleanup_20261026.py --apply            백업 JSON(없을 때만 작성, 덮어쓰지 않음) → 지시마다 조건부 갱신
                                                                → wo_events 3행 → PROD_OUTPUT 1행 → 열린 배치 DONE → 이력
                                                                → _작업지시_일괄정리_결과_YYYYMMDD.md
  python scripts/wo_bulk_cleanup_20261026.py --revert           백업의 대상 전체 되돌리기
  python scripts/wo_bulk_cleanup_20261026.py --revert-wo <지시번호>   한 건만 되돌리기(백업 행 복원 + 태그 이벤트·PROD_OUTPUT 삭제)
선택: --asof YYYY-MM-DD  '7일 내 투입' 판정 기준일(기본 오늘). 10-23 후보표와 같은 유지 집합을 원하면 --asof 2026-10-23.
      --lot-null          PROD_OUTPUT 의 lot_number 를 모두 NULL 로 — 제품 합계(product_stock_v)에만 잡히고 LOT 재고
                          (product_lot_stock_v·출고 LOT 선입선출)에는 안 잡힌다(기획 세션 2026-10-26 결정, Data 리뷰 H2).
                          기본은 배치 1개면 배치 번호, 아니면 wo_number(앱 검사 완성 경로와 같음).

멱등: wo_tracking.remark 에 태그 [bulk_cleanup_20261026] 가 있으면 건너뜀. 이벤트는 detail.reason, PROD_OUTPUT 은 remark 에 같은 태그.
안전: 지시 갱신은 읽은 값(status·투입·인수·합격·완성)이 그대로일 때만(조건부 PATCH, 1행 확인). 실패한 지시는 건너뛰고 기록.
범위 밖: 소재 재고(PROD_INPUT)·출고·수주 무접촉.
"""
import argparse
import datetime as dt
import io
import json
import os
import sys

os.chdir(r"C:\wsapp")
sys.path.insert(0, r"C:\wsapp")
import pandas as pd  # noqa: E402
import db  # noqa: E402

TAG = "bulk_cleanup_20261026"
D = "2026-10-26"
WHO = "검토 세션 정정"
G = r"G:\내 드라이브\제품관리DB"
BACKUP = os.path.join(G, "_작업지시_일괄정리_정정전백업_20261026.json")
CAND_XLSX = os.path.join(G, "_실사", "작업지시_정리후보_20261023.xlsx")
JOURNAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wo_bulk_cleanup_20261026_journal.jsonl")
REASON = f"[일괄 정정 {D}] 열린 작업지시 일괄 정리(출고 근거) {TAG}"
REASON_R = f"[일괄 정정 되돌림 {D}] 열린 작업지시 일괄 정리 {TAG}"
REMARK_ADD = f" · 2026-10 일괄 정리(출고 근거, 검토 세션) [{TAG}]"
FORCE = False

CLOSE = ("완료(수량 0)", "완료 추정", "완료 추정(출고 근거만)", "부분 완료 추정", "근거 없음")
KEEP = ("확인 필요(외주·재작업 잔량)", "유지(최근 투입)")
ORDER = {k: i for i, k in enumerate(CLOSE + KEEP)}
WO_COLS = ("wo_id,wo_number,product_id,pn,material_id,w_lot,input_qty,received_qty,outsource_qty,outsource_in_qty,"
           "pass_qty,tokusai_qty,rework_qty,scrap_qty,status,remark,created_by,created_at,updated_at,rework_in_qty,"
           "output_qty,return_qty")
GUARD = ("status", "input_qty", "received_qty", "pass_qty", "output_qty", "updated_at")   # 앱 쓰기는 updated_at 을 항상 갱신(Data 리뷰 M1)


def f(v):
    return float(v or 0)


def fetch_pages(table, select, filt, order):
    out, off = [], 0
    while True:
        q = "&".join(x for x in (filt, f"order={order}", f"offset={off}") if x)
        pg = db.fetch(table, select, q, limit=1000, cache=False)
        out += pg
        if len(pg) < 1000:
            return out
        off += 1000


def journal(rec):
    with io.open(JOURNAL, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": dt.datetime.now().isoformat(), **rec}, ensure_ascii=False, default=str) + "\n")


# ─── 앱과 같은 단계 수량(streamlit_app.wo_stage_qty·wo_derive_status) ───
def stage_qty(t):
    rew = f(t.get("rework_qty")) - f(t.get("rework_in_qty"))
    pre_out = max(0.0, f(t.get("outsource_qty")) - f(t.get("outsource_in_qty")) - f(t.get("received_qty")))
    return {"생산중": max(0.0, f(t.get("input_qty")) - f(t.get("received_qty")) - pre_out),
            "외주중": max(0.0, f(t.get("outsource_qty")) - f(t.get("outsource_in_qty"))),
            "재작업중": max(0.0, rew),
            "검사대기": max(0.0, f(t.get("received_qty")) + f(t.get("outsource_in_qty")) - f(t.get("outsource_qty"))
                          - f(t.get("pass_qty")) - f(t.get("tokusai_qty")) - f(t.get("scrap_qty"))
                          - f(t.get("return_qty")) - rew),
            "완성": f(t.get("output_qty")), "반품": f(t.get("return_qty"))}


def derive_status(t):
    q = stage_qty(t)
    if q["생산중"] > 0:
        return "IN_PROD"
    if q["외주중"] > 0:
        return "OUTSOURCE"
    if q["재작업중"] > 0:
        return "REWORK"
    if q["검사대기"] > 0:
        return "INSPECT"
    if q["완성"] > 0 or q["반품"] > 0 or f(t.get("scrap_qty")) > 0:
        return "CLOSED"
    return t.get("status") or "IN_PROD"


# ─── 분류 (make_wo_cleanup.py 와 같은 계산) ───
def classify(asof):
    wos = fetch_pages("wo_tracking", WO_COLS, "status=not.in.(DONE,CLOSED,CANCELLED)", "created_at.asc,wo_id.asc")
    if not wos:
        return [], {}
    since = min(w["created_at"][:10] for w in wos)
    tx = pd.DataFrame(fetch_pages("inventory_transactions", "txn_id,product_id,txn_type,qty,txn_date,work_order",
                                  f"material_id=is.null&txn_date=gte.{since}", "txn_id.asc"))
    pl = pd.DataFrame(fetch_pages("production_log", "log_id,product_id,total_qty,defect_qty,log_date,source",
                                  f"log_date=gte.{since}&product_id=not.is.null", "log_id.asc"))
    prods = {p["product_id"]: p for p in fetch_pages("products", "product_id,pn,customer,procurement_type,item_name",
                                                     "", "product_id.asc")}
    rt = pd.DataFrame(fetch_pages("product_routing", "routing_id,product_id,step_code", "", "routing_id.asc"))
    has_prod = set(rt[rt.step_code == "PROD"].product_id) if len(rt) else set()
    has_rt = set(rt.product_id) if len(rt) else set()
    if len(tx):
        tx["qty"] = tx["qty"].astype(float)
        tx["d"] = pd.to_datetime(tx.txn_date).dt.date
    if len(pl):
        pl["good"] = pl.total_qty.astype(float) - pl.defect_qty.fillna(0).astype(float)
        pl["d"] = pd.to_datetime(pl.log_date).dt.date

    rows, by_prod = [], {}
    for w in wos:
        by_prod.setdefault(w["product_id"], []).append(w)
    for pid, lst in by_prod.items():
        ship_pool = sheet_pool = None
        for w in lst:
            c = dt.date.fromisoformat(w["created_at"][:10])
            q = stage_qty(w)
            prodn, outs, rewk, insp = q["생산중"], q["외주중"], q["재작업중"], q["검사대기"]
            remain = prodn + outs + rewk + insp
            if ship_pool is None:
                ship_pool = (-tx[(tx.product_id == pid) & (tx.txn_type == "ISSUE") & (tx.d >= c)].qty.sum()
                             if len(tx) else 0.0)
                sheet_pool = pl[(pl.product_id == pid) & (pl.d >= c)].good.sum() if len(pl) else 0.0
            ship_use = min(remain, max(0.0, ship_pool)); ship_pool -= ship_use
            sheet_use = min(remain, max(0.0, sheet_pool)); sheet_pool -= sheet_use
            no_prod = (pid in has_rt and pid not in has_prod) or (prods.get(pid, {}).get("procurement_type") in ("도급",))
            age = (asof - c).days
            if remain <= 0:
                cls = "완료(수량 0)"
            elif outs > 0 or rewk > 0:
                cls = "확인 필요(외주·재작업 잔량)"
            elif age <= 7:
                cls = "유지(최근 투입)"
            elif ship_use >= remain * 0.95 and (no_prod or sheet_use >= remain * 0.8):
                cls = "완료 추정"
            elif ship_use >= remain * 0.95:
                cls = "완료 추정(출고 근거만)"
            elif ship_use > 0 or sheet_use > 0:
                cls = "부분 완료 추정"
            else:
                cls = "근거 없음"
            p = prods.get(pid, {})
            rows.append({"wo": w, "wo_number": w["wo_number"], "pn": w.get("pn") or p.get("pn") or "",
                         "customer": p.get("customer") or "", "created": c.isoformat(), "age": age,
                         "status": w["status"], "prodn": prodn, "outs": outs, "rewk": rewk, "insp": insp,
                         "remain": remain, "ship_use": ship_use, "sheet_use": sheet_use, "cls": cls,
                         "close": cls in CLOSE})
    rows.sort(key=lambda r: (ORDER[r["cls"]], -r["age"]))
    return rows, prods


def load_candidates():
    try:
        df = pd.read_excel(CAND_XLSX, header=4)
        df = df[df["추정"].notna() & df["지시번호"].notna()]
        return {str(r["지시번호"]): str(r["추정"]) for _, r in df.iterrows()}
    except Exception as e:
        print("후보표 읽기 실패:", e)
        return None


def open_batches(wos):
    """대상 지시의 열린 배치 — wo_id 와 wo_number 둘 다로 찾아 합친다(앱 공정 처리는 wo_number 로 찾음, Data 리뷰 M7)."""
    out, seen = {}, set()
    by_no = {w["wo_number"]: w["wo_id"] for w in wos}
    ids = [w["wo_id"] for w in wos]
    nos = list(by_no)
    for i in range(0, len(ids), 100):
        q_id = ",".join(str(x) for x in ids[i:i + 100])
        q_no = ",".join(db.qo(x) for x in nos[i:i + 100])
        for filt in (f"wo_id=in.({q_id})&status=eq.OPEN", f"wo_number=in.({q_no})&status=eq.OPEN"):
            for b in fetch_pages("wo_batches", "*", filt, "batch_id.asc"):
                if b["batch_id"] in seen:
                    continue
                seen.add(b["batch_id"])
                owner = by_no.get(b.get("wo_number")) or b.get("wo_id")
                out.setdefault(owner, []).append(b)
    return out


def plan_writes(r, batches, lot_null):
    """지시 1건의 쓰기 계획(드라이런·적용 공용)."""
    w = r["wo"]
    remain, prodn = r["remain"], r["prodn"]
    new = {"received_qty": f(w.get("received_qty")) + prodn,
           "pass_qty": f(w.get("pass_qty")) + remain,
           "output_qty": f(w.get("output_qty")) + remain}
    derived = derive_status({**w, **new})
    new["status"] = "CLOSED"
    new["remark"] = (w.get("remark") or "") + REMARK_ADD
    new["updated_at"] = dt.datetime.utcnow().isoformat()
    bl = batches.get(w["wo_id"], [])
    lot = None if lot_null else (bl[0]["batch_no"] if len(bl) == 1 else w["wo_number"])
    return {"fields": new, "derived": derived, "batches": bl, "lot": lot,
            "lot_src": "NULL(--lot-null)" if lot_null else ("배치" if len(bl) == 1 else f"wo_number(열린 배치 {len(bl)}개)")}


def guard_filter(w):
    parts = [f"wo_id=eq.{w['wo_id']}"]
    for k in GUARD:
        v = w.get(k)
        parts.append(f"{k}=is.null" if v is None else f"{k}=eq.{db.qv(v)}")
    # 태그 확인은 classify(처리된 지시 제외) + updated_at 변화로 충분 — 빈 remark 오판 제거(Data 리뷰 M2)
    return "&".join(parts)


def stock_snapshot(pids):
    out = {}
    pids = sorted(set(pids))
    for i in range(0, len(pids), 100):
        ins = ",".join(db.qo(p) for p in pids[i:i + 100])
        for s in db.fetch("product_stock_v", "product_id,pn,current_stock", f"product_id=in.({ins})", limit=1000,
                          cache=False):
            out[s["product_id"]] = s
    return out


def fmt(v):
    return f"{v:,.0f}"


# ─── 드라이런 ───
def dry_run(args, asof, md_suffix=""):
    rows, _ = classify(asof)
    cand = load_candidates()
    tgt = [r for r in rows if r["close"] and TAG not in (r["wo"].get("remark") or "")]
    keep = [r for r in rows if not r["close"]]
    done_before = [r for r in rows if TAG in (r["wo"].get("remark") or "")]
    batches = open_batches([r["wo"] for r in tgt])
    plans = {r["wo_number"]: plan_writes(r, batches, args.lot_null) for r in tgt}
    stock = stock_snapshot([r["wo"]["product_id"] for r in tgt if r["wo"].get("product_id")])

    # 후보표 대조
    diffs, missing, new_wo = [], [], []
    if cand is not None:
        now = {r["wo_number"]: r["cls"] for r in rows}
        for wo, c0 in cand.items():
            if wo not in now:
                missing.append((wo, c0))
            elif now[wo] != c0:
                diffs.append((wo, c0, now[wo]))
        new_wo = [(wo, c) for wo, c in now.items() if wo not in cand]
    grp = lambda c: "종결" if c in CLOSE else "유지"  # noqa: E731
    grp_diffs = [d for d in diffs if grp(d[1]) != grp(d[2])]

    from collections import Counter
    cnt = Counter(r["cls"] for r in rows)
    by_pn = {}
    for r in tgt:
        k = (r["pn"], r["wo"].get("product_id"))
        by_pn.setdefault(k, [0, 0.0])
        by_pn[k][0] += 1; by_pn[k][1] += r["remain"]
    tot = sum(r["remain"] for r in tgt)

    L = [f"# 열린 작업지시 일괄 정리 — 드라이런 ({dt.datetime.now():%Y-%m-%d %H:%M}, 운영 DB 읽기만)", "",
         f"스크립트 `scripts/wo_bulk_cleanup_20261026.py`(기본 드라이런). '7일 내 투입' 기준일 **{asof.isoformat()}**"
         + (" (기본 = 오늘)" if not args.asof else " (--asof)") + ". LOT 규칙: "
         + ("**모두 NULL(--lot-null)** — 제품 합계에만 잡히고 LOT 재고·출고 LOT 선입선출에는 안 잡힘" if args.lot_null
            else "배치 1개면 배치 번호, 아니면 wo_number(앱 검사 완성 경로와 같음)") + ".", "",
         "## 1. 요약", "",
         f"| 항목 | 값 |", "|---|---|",
         f"| 열린 지시(DONE·CLOSED·CANCELLED 제외) | {len(rows)} |",
         f"| **종결 대상** | **{len(tgt)}** |",
         f"| 유지 | {len(keep)} (확인 필요 {cnt.get(KEEP[0], 0)} · 7일 내 {cnt.get(KEEP[1], 0)}) |",
         f"| 이미 태그 있음(건너뜀) | {len(done_before)} |",
         f"| 예상 PROD_OUTPUT 합 | **{fmt(tot)}** EA ({sum(1 for r in tgt if r['remain'] > 0)}행) |",
         f"| 영향 품번 | {len(by_pn)} |", "",
         "분류별: " + " · ".join(f"{k} {cnt.get(k, 0)}" for k in CLOSE + KEEP), ""]
    L += ["## 2. 10-23 후보표 대조", ""]
    if cand is None:
        L += ["후보표를 읽지 못함 — 대조 생략.", ""]
    else:
        L += [f"- 후보표 {len(cand)}건 / 지금 열린 지시 {len(rows)}건. 분류 문자열이 다른 지시 **{len(diffs)}**건, "
              f"그중 종결↔유지가 바뀐 지시 **{len(grp_diffs)}**건. 후보표에만 있음(그 사이 종결·취소) {len(missing)}건, "
              f"새로 열린 지시 {len(new_wo)}건.",
              f"- 멈춤 조건(분류 10건 이상 다름): **{'해당' if len(diffs) >= 10 else '해당 없음'}**.", ""]
        if diffs:
            L += ["| 지시번호 | 10-23 | 지금 | 종결/유지 변화 |", "|---|---|---|---|"]
            L += [f"| {a} | {b} | {c} | {grp(b)} → {grp(c)} |" for a, b, c in diffs]
            L += [""]
        if missing:
            L += ["후보표에만 있음: " + ", ".join(f"{a}({b})" for a, b in missing), ""]
        if new_wo:
            L += ["새로 열린 지시: " + ", ".join(f"{a}({b})" for a, b in new_wo), ""]
    L += ["## 3. 종결 대상", "",
          "| # | 지시번호 | 품번 | 거래처 | 투입일 | 경과 | 상태 | 생산중 | 검사대기 | 남은=PROD_OUTPUT | 이후 출고 | 시트 양품 | 분류 | 열린 배치 | LOT | 유도 상태 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(tgt, 1):
        p = plans[r["wo_number"]]
        L.append(f"| {i} | {r['wo_number']} | {r['pn']} | {r['customer']} | {r['created']} | {r['age']} | {r['status']} | "
                 f"{fmt(r['prodn'])} | {fmt(r['insp'])} | {fmt(r['remain'])} | {fmt(r['ship_use'])} | {fmt(r['sheet_use'])} | "
                 f"{r['cls']} | {len(p['batches'])} | {p['lot'] or 'NULL'} | {p['derived']} |")
    odd = [r for r in tgt if plans[r["wo_number"]]["derived"] != "CLOSED"]
    L += ["", f"유도 상태(앱 `wo_derive_status` 와 같은 계산)가 CLOSED 가 아닌 대상: **{len(odd)}**건"
          + (" — " + ", ".join(f"{r['wo_number']}({plans[r['wo_number']]['derived']})" for r in odd) if odd else "")
          + ". (남은 수량 0 인 지시는 완성 0 이라 앱 유도값이 그대로지만 계획대로 status=CLOSED 로 쓴다.)", ""]
    L += ["## 4. 유지", "", "| 지시번호 | 품번 | 투입일 | 경과 | 상태 | 남은 | 외주중 | 재작업중 | 분류 |", "|---|---|---|---|---|---|---|---|---|"]
    L += [f"| {r['wo_number']} | {r['pn']} | {r['created']} | {r['age']} | {r['status']} | {fmt(r['remain'])} | "
          f"{fmt(r['outs'])} | {fmt(r['rewk'])} | {r['cls']} |" for r in keep]
    L += ["", "## 5. 품번별 PROD_OUTPUT 합계(완성 재고 증가 예상)", "",
          "| 품번 | 지시 수 | PROD_OUTPUT 합 | 지금 완성 재고 | 적용 뒤 예상 |", "|---|---|---|---|---|"]
    for (pn, pid), (n, s) in sorted(by_pn.items(), key=lambda x: -x[1][1]):
        cur = f(stock.get(pid, {}).get("current_stock"))
        L.append(f"| {pn} | {n} | {fmt(s)} | {fmt(cur)} | {fmt(cur + s)} |")
    nb = sum(len(p["batches"]) for p in plans.values())
    multi = [k for k, p in plans.items() if len(p["batches"]) > 1]
    L += ["", "## 6. 쓰기 계획(--apply 때) — 지시 1건", "",
          "1. `wo_tracking` 조건부 PATCH(읽은 status·투입·인수·합격·완성 값이 그대로이고 태그가 없을 때만, 1행 확인): "
          "received += 생산중, pass += 남은, output += 남은, status=CLOSED, remark += 태그.",
          "2. `wo_events` 3행: RECEIVE(생산중, 0 이면 생략) / INSPECT(qty=남은, detail pass=남은·나머지 0) / OUTPUT(남은). "
          f"detail.reason=`{TAG}`, created_by=`{WHO}`.",
          "3. `inventory_transactions` PROD_OUTPUT 1행(남은 > 0 일 때): lot·work_order·remark(태그 포함).",
          f"4. 열린 배치 → status=DONE, step_code=DONE, step_name=완성, routing_id=NULL, location=사내(앱 검사 완성 경로와 같은 값). 대상 배치 {nb}개"
          + (f", 배치가 2개 이상인 지시 {len(multi)}건({', '.join(multi[:10])}) — LOT 는 wo_number" if multi else "") + ".",
          "5. `master_change_log` 에 지시별 변경 필드(사유 `[일괄 정정 2026-10-26] …`).",
          "백업: 대상 지시 행·열린 배치 행·적용 전 `product_stock_v` → `_작업지시_일괄정리_정정전백업_20261026.json`(없을 때만).", ""]
    L += ["## 7. 확인이 필요한 점(기획 세션)", "",
          "1. **LOT 번호**: 계획서 §2 는 '배치 LOT 없으면 NULL'. 앱의 비배치 검사 완성은 `lot_number = wo_number` 로 쓴다. "
          "NULL 이면 `product_lot_stock_v`(lot_number NOT NULL 만 집계) — 출고 LOT 선입선출·LOT 실사표에 이 완성분이 안 보이고 "
          "`product_stock_v`(합계)에만 보인다. 기본값을 **wo_number** 로 두었고 `--lot-null` 로 계획서대로 바꿀 수 있다.",
          f"2. **'7일 내 투입' 기준일**: 계산을 오늘 다시 돌리면 10-23 에 '유지(최근 투입)' 였던 지시가 7일을 넘겨 종결 쪽으로 옮겨진다"
          f"(위 §2 의 유지→종결 변화). 11/1 에 적용하면 더 늘어난다. 10-23 의 유지 집합을 그대로 쓰려면 `--asof 2026-10-23`.",
          ""]
    out = os.path.join(G, f"_작업지시_일괄정리_드라이런_{dt.date.today():%Y%m%d}{md_suffix}.md")
    io.open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"열린 {len(rows)} / 종결 대상 {len(tgt)} / 유지 {len(keep)} / PROD_OUTPUT 합 {fmt(tot)} / 후보표 차이 {len(diffs)}"
          f"(종결↔유지 {len(grp_diffs)}) / 배치 {nb}")
    print("saved", out)
    return tgt, plans, stock, diffs, grp_diffs


# ─── 적용 ───
def expected_targets(path):
    """검토한 드라이런 md §3 표의 지시번호 목록."""
    txt = io.open(path, encoding="utf-8").read()
    sec = txt.split("## 3. 종결 대상", 1)[1].split("\n## ", 1)[0]
    return [ln.split("|")[2].strip() for ln in sec.splitlines()
            if ln.startswith("| ") and ln.split("|")[1].strip().isdigit()]


def apply(args, asof):
    if not args.expect:
        sys.exit("--apply 에는 --expect <검토한 드라이런 md> 가 필요하다(Data 리뷰 H1)")
    tgt, plans, stock, diffs, grp_diffs = dry_run(args, asof, "_적용시점")
    exp = expected_targets(args.expect)
    now_set = [r["wo_number"] for r in tgt]
    if not exp or sorted(exp) != sorted(now_set):
        sys.exit(f"대상이 검토한 드라이런과 다르다 — 중단. 빠짐 {sorted(set(exp) - set(now_set))} / "
                 f"추가 {sorted(set(now_set) - set(exp))}")
    if grp_diffs or len(diffs) >= 10:
        sys.exit(f"후보표 대비 종결↔유지 변화 {len(grp_diffs)} / 분류 차이 {len(diffs)} — 중단(계획서 멈춤 조건)")
    no_pid = [r["wo_number"] for r in tgt if not r["wo"].get("product_id")]
    if no_pid:
        sys.exit(f"product_id 없는 대상 {no_pid} — 중단(Data 리뷰 M3)")
    print(f"대상 확인: 검토한 {len(exp)}건과 같음")
    if os.path.exists(BACKUP):
        snap = json.load(io.open(BACKUP, encoding="utf-8"))
        bk = {w["wo_number"]: w for w in snap["wo_tracking"]}
        bk_bat = {b["batch_id"] for b in snap.get("wo_batches", [])}
        bad = []
        for r in tgt:
            b0 = bk.get(r["wo_number"])
            if b0 is None or any(str(b0.get(k)) != str(r["wo"].get(k)) for k in GUARD):
                bad.append(r["wo_number"])
        new_bat = [b["batch_id"] for p in plans.values() for b in p["batches"] if b["batch_id"] not in bk_bat]
        if bad or new_bat:
            sys.exit(f"백업 이후 바뀐 지시 {bad[:10]} / 백업에 없는 열린 배치 {new_bat[:10]} — 중단(Data 리뷰 M5)")
        print("기존 백업 사용(값 일치 확인):", BACKUP)
    else:
        snap = {"taken_at": dt.datetime.now().isoformat(), "tag": TAG, "asof": asof.isoformat(),
                "lot_null": args.lot_null,
                "wo_tracking": [r["wo"] for r in tgt],
                "wo_batches": [b for p in plans.values() for b in p["batches"]],
                "product_stock_v": list(stock.values())}
        io.open(BACKUP, "w", encoding="utf-8").write(json.dumps(snap, ensure_ascii=False, default=str, indent=1))
        try:   # 다시 읽어 건수 확인(AGENTS §5, Data 리뷰 L5)
            chk = json.load(io.open(BACKUP, encoding="utf-8"))
            assert len(chk["wo_tracking"]) == len(tgt)
            assert len(chk["wo_batches"]) == sum(len(p["batches"]) for p in plans.values())
        except Exception as e:
            sys.exit(f"백업 파일 확인 실패 — 중단: {e}")
        print(f"backup written: {BACKUP} (wo_tracking {len(chk['wo_tracking'])} · wo_batches {len(chk['wo_batches'])})")

    ok, fail = [], []
    today = dt.date.today().isoformat()
    for r in tgt:
        w, p, wo = r["wo"], plans[r["wo_number"]], r["wo_number"]
        steps = []
        try:
            n = db.update_count("wo_tracking", guard_filter(w), p["fields"], select="wo_id")
            if n != 1:
                raise RuntimeError(f"조건부 갱신 {n}행(값이 바뀌었거나 이미 처리됨)")
            steps.append("wo_tracking")
            base = {"wo_id": w["wo_id"], "wo_number": wo, "w_lot": w.get("w_lot"), "pn": r["pn"],
                    "event_date": today, "created_by": WHO}
            ev = []
            if r["prodn"] > 0:
                ev.append({**base, "event_type": "RECEIVE", "qty": r["prodn"], "detail": {"reason": TAG}})
            ev.append({**base, "event_type": "INSPECT", "qty": r["remain"],
                       "detail": {"reason": TAG, "pass": r["remain"], "rework": 0, "scrap": 0, "tokusai": 0,
                                  "return": 0, "output": r["remain"], "lot": p["lot"],
                                  "batch_no": p["batches"][0]["batch_no"] if len(p["batches"]) == 1 else None}})
            ev.append({**base, "event_type": "OUTPUT", "qty": r["remain"], "detail": {"reason": TAG, "lot": p["lot"]}})
            db.insert("wo_events", ev); steps.append(f"wo_events {len(ev)}")
            if r["remain"] > 0:
                db.insert("inventory_transactions", [{
                    "product_id": w["product_id"], "txn_type": "PROD_OUTPUT", "qty": r["remain"], "unit": "EA",
                    "lot_number": p["lot"], "work_order": wo, "txn_date": today,
                    "remark": f"일괄 정리 완성: {r['pn']} ({wo}) {D} [{TAG}]", "created_by": WHO}])
                steps.append("PROD_OUTPUT")
            for b in p["batches"]:
                nb = db.update_count("wo_batches", f"batch_id=eq.{b['batch_id']}&status=eq.OPEN",
                                     {"status": "DONE", "step_code": "DONE", "step_name": "완성", "routing_id": None,
                                      "location": "사내", "updated_at": dt.datetime.utcnow().isoformat()},
                                     select="batch_id")
                if nb != 1:
                    raise RuntimeError(f"배치 {b['batch_no']} 갱신 {nb}행")
            if p["batches"]:
                steps.append(f"wo_batches {len(p['batches'])}")
            db.insert("master_change_log", [
                {"table_name": "wo_tracking", "record_id": wo, "field_name": k,
                 "old_value": None if w.get(k) is None else str(w.get(k)),
                 "new_value": str(p["fields"][k]), "changed_by": WHO, "reason": REASON}
                for k in ("received_qty", "pass_qty", "output_qty", "status")])
            ok.append((r, p))
            journal({"op": "apply", "wo": wo, "steps": steps})
        except KeyboardInterrupt:
            journal({"op": "apply_interrupted", "wo": wo, "steps": steps})
            print("중단됨 — 진행 중이던 지시:", wo, steps)
            raise
        except Exception as e:
            fail.append((r, steps, str(e)))
            journal({"op": "apply_fail", "wo": wo, "steps": steps, "error": str(e)})
            print("FAIL", wo, steps, e)
            if len(fail) >= 5:
                print("실패 5건 — 중단(멈춤 조건)")
                break

    after = stock_snapshot([r["wo"]["product_id"] for r, _ in ok if r["wo"].get("product_id")])
    before = {s["product_id"]: s for s in snap.get("product_stock_v", [])}
    L = [f"# 열린 작업지시 일괄 정리 — 적용 결과 ({dt.datetime.now():%Y-%m-%d %H:%M})", "",
         f"| 항목 | 값 |", "|---|---|", f"| 적용 | {len(ok)} |", f"| 실패 | {len(fail)} |",
         f"| PROD_OUTPUT 합 | {fmt(sum(r['remain'] for r, _ in ok))} EA |", f"| 백업 | `{BACKUP}` |", ""]
    if fail:
        L += ["## 실패", "", "| 지시번호 | 완료된 단계 | 오류 |", "|---|---|---|"]
        L += [f"| {r['wo_number']} | {', '.join(s) or '-'} | {e} |" for r, s, e in fail] + [""]
    L += ["## product_stock_v 전후", "", "| 품번 | 전 | 후 | 차이 |", "|---|---|---|---|"]
    for pid, s in sorted(after.items(), key=lambda x: x[1].get("pn") or ""):
        b0 = f(before.get(pid, {}).get("current_stock"))
        L.append(f"| {s.get('pn')} | {fmt(b0)} | {fmt(f(s.get('current_stock')))} | {fmt(f(s.get('current_stock')) - b0)} |")
    out = os.path.join(G, f"_작업지시_일괄정리_결과_{dt.date.today():%Y%m%d}.md")
    io.open(out, "a", encoding="utf-8").write("\n".join(L) + "\n\n")
    print(f"적용 {len(ok)} / 실패 {len(fail)} → {out}")


# ─── 되돌리기 ───
def revert(only_wo=None):
    if not os.path.exists(BACKUP):
        sys.exit("백업 없음 — 되돌릴 수 없음")
    snap = json.load(io.open(BACKUP, encoding="utf-8"))
    rows = [w for w in snap["wo_tracking"] if only_wo is None or w["wo_number"] == only_wo]
    if only_wo and not rows:
        sys.exit(f"{only_wo} 는 백업 대상이 아니다")
    bats = {}
    for b in snap.get("wo_batches", []):
        bats.setdefault(b["wo_id"], []).append(b)
    res = []
    for w in rows:
        wo = w["wo_number"]
        try:
            cur = db.fetch("wo_tracking", "wo_id,remark,status", f"wo_id=eq.{w['wo_id']}", limit=1, cache=False)
            # (태그 없음 = 적용 안 됐거나 이미 되돌림)
            if not cur or TAG not in (cur[0].get("remark") or ""):
                res.append((wo, "건너뜀(태그 없음 — 적용 안 됐거나 이미 되돌림)")); continue
            # 이후 처리 확인(Data 리뷰 H3): 이 완성분 LOT 에 출고·조정 등이 붙었거나 실사 조정이 있으면 거부
            ptx = db.fetch("inventory_transactions", "txn_id,lot_number,product_id,txn_date",
                           f"work_order=eq.{db.qv(wo)}&txn_type=eq.PROD_OUTPUT&remark=like.*{TAG}*",
                           limit=10, cache=False)
            later = []
            for t in ptx:
                if t.get("lot_number"):
                    later += db.fetch("inventory_transactions", "txn_id,txn_type,qty,txn_date",
                                      f"lot_number=eq.{db.qv(t['lot_number'])}&product_id=eq.{db.qv(t['product_id'])}"
                                      "&txn_type=neq.PROD_OUTPUT", limit=50, cache=False)
                later += db.fetch("inventory_transactions", "txn_id,txn_type,qty,txn_date",
                                  f"product_id=eq.{db.qv(t['product_id'])}&txn_type=eq.ADJUSTMENT&txn_date=gte.{D}",
                                  limit=50, cache=False)
            if later and not FORCE:
                res.append((wo, f"거부: 이후 원장 {len(later)}행(출고·조정 등) — 실사·출고 확인 뒤 --force"))
                continue
            if cur[0].get("status") != "CLOSED":
                res.append((wo, f"거부: 적용 뒤 상태가 바뀜({cur[0].get('status')})"))
                continue
            # 배치 먼저 복원 — 실패하면 태그가 남아 재시도 가능(Data 리뷰 M4)
            nb = 0
            for b in bats.get(w["wo_id"], []):
                n1 = db.update_count("wo_batches", f"batch_id=eq.{b['batch_id']}&status=eq.DONE",
                                     {k: b.get(k) for k in ("status", "step_code", "step_name", "routing_id",
                                                            "location", "step_status")}, select="batch_id")
                if n1 != 1:
                    raise RuntimeError(f"배치 {b['batch_no']} 복원 {n1}행")
                nb += 1
            n_ev = db.delete("wo_events", f"wo_number=eq.{db.qv(wo)}&detail->>reason=eq.{TAG}")
            n_tx = db.delete("inventory_transactions",
                             f"work_order=eq.{db.qv(wo)}&txn_type=eq.PROD_OUTPUT&remark=like.*{TAG}*")
            fields = {k: w.get(k) for k in ("received_qty", "pass_qty", "output_qty", "status", "remark")}
            fields["updated_at"] = dt.datetime.utcnow().isoformat()
            # 적용 값 그대로(CLOSED + 태그)일 때만 복원 — 그 뒤 앱에서 바뀐 지시는 덮지 않는다
            n = db.update_count("wo_tracking", f"wo_id=eq.{w['wo_id']}&status=eq.CLOSED&remark=like.*{TAG}*",
                                fields, select="wo_id")
            if n != 1:
                raise RuntimeError(f"wo_tracking 복원 {n}행")
            db.insert("master_change_log", [{"table_name": "wo_tracking", "record_id": wo, "field_name": "status",
                                             "old_value": "CLOSED", "new_value": str(w.get("status")),
                                             "changed_by": WHO, "reason": REASON_R}])
            res.append((wo, f"복원 wo_tracking {n} · 배치 {nb} · 이벤트 삭제 {n_ev} · PROD_OUTPUT 삭제 {n_tx}"))
            journal({"op": "revert", "wo": wo, "result": res[-1][1]})
        except Exception as e:
            res.append((wo, f"실패: {e}"))
            journal({"op": "revert_fail", "wo": wo, "error": str(e)})
    out = os.path.join(G, f"_작업지시_일괄정리_결과_{dt.date.today():%Y%m%d}.md")
    L = [f"## 되돌리기 {'— ' + only_wo if only_wo else '(전체)'} ({dt.datetime.now():%Y-%m-%d %H:%M})", "",
         "| 지시번호 | 결과 |", "|---|---|"] + [f"| {a} | {b} |" for a, b in res]
    io.open(out, "a", encoding="utf-8").write("\n".join(L) + "\n\n")
    for a, b in res:
        print(a, b)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", help="기본")
    g.add_argument("--apply", action="store_true")
    g.add_argument("--revert", action="store_true")
    g.add_argument("--revert-wo", metavar="WO_NUMBER")
    ap.add_argument("--expect", help="--apply 때 검토한 드라이런 md(대상 지시번호 일치 확인)")
    ap.add_argument("--force", action="store_true", help="되돌리기: 이후 원장 행이 있어도 진행")
    ap.add_argument("--asof", help="'7일 내 투입' 판정 기준일 YYYY-MM-DD (기본 오늘)")
    ap.add_argument("--lot-null", action="store_true", help="PROD_OUTPUT lot_number 모두 NULL (제품 합계에만 반영)")
    args = ap.parse_args()
    global FORCE
    FORCE = args.force
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    asof = dt.date.fromisoformat(args.asof) if args.asof else dt.date.today()
    if args.apply:
        apply(args, asof)
    elif args.revert:
        revert()
    elif args.revert_wo:
        revert(args.revert_wo)
    else:
        dry_run(args, asof)


if __name__ == "__main__":
    main()
