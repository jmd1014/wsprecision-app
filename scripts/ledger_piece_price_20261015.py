# -*- coding: utf-8 -*-
"""L3-D: purchase_ledger KG 매입(개수 병기, 명진메탈식) → 개당 기준 재처리 + 매핑표/치수 매칭 (2026-10-15).
사용: python scripts/ledger_piece_price_20261015.py [--date YYYY-MM-DD] [--vendor 명진]
                                                   드라이런(백업 JSON 은 없을 때만 작성, 비대상 업체 행은 전체 열 출력)
      ... --apply    스냅샷 기준 가드 → update_count=1 → 이력 즉시 insert(+저널). 재실행 안전.
      ... --revert   저널의 적용값과 현재값이 같은 행만 스냅샷대로 복원(그 뒤 사람이 바꾼 행은 건너뜀).
규칙 = utils.purchase_sync.piece_price_rows (앱 동기화·수기 입력과 한 코드). 기본 대상 업체 = 명진 (--vendor 로 변경)."""
import io, json, os, sys, datetime as dt
from collections import Counter

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.getcwd())
import db  # noqa: E402
from utils.purchase_sync import piece_price_rows, apply_item_map, match_material, build_key_mats, is_linked  # noqa: E402

args = sys.argv[1:]
MODE = "apply" if "--apply" in args else ("revert" if "--revert" in args else "dry")
D = args[args.index("--date") + 1] if "--date" in args else dt.date.today().isoformat()
VENDOR = args[args.index("--vendor") + 1] if "--vendor" in args else "명진"
BACKUP = rf"G:\내 드라이브\제품관리DB\_KG개당변환_정정전백업_{D.replace('-', '')}.json"
JOURNAL = os.path.join(os.getcwd(), "scripts", f"ledger_piece_price_journal_{D.replace('-', '')}.jsonl")
REASON = f"[일괄 정정 {D}] KG 매입(개수 병기) 개당 단가 변환"
COLS = ("ledger_id,trade_date,vendor,item,unit,qty,weight,unit_price,amount,vat,total,remark,category,kg_price,ea_price,"
        "matched_pn,matched_material_id,mapping_status,map_id,source")
FIELDS = ("unit", "unit_price", "kg_price", "ea_price", "matched_material_id", "mapping_status", "map_id", "category")
GUARD = ("item", "unit", "qty", "weight", "amount", "unit_price", "trade_date")


def pages(table, cols, filt, order="ledger_id"):
    out, off = [], 0
    while True:
        pg = db.fetch(table, cols, (f"{filt}&" if filt else "") + f"order={order}&offset={off}", limit=1000)
        out += pg
        if len(pg) < 1000:
            return out
        off += 1000


def same(a, b, keys):
    def nz(v):
        if v in (None, ""):
            return ""
        try:
            return f"{float(v):.4f}"
        except (TypeError, ValueError):
            return str(v).strip()
    return all(nz(a.get(k)) == nz(b.get(k)) for k in keys)


def journal(rec):
    with io.open(JOURNAL, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")


def is_target(r):
    return ((r.get("weight") or 0) > 0 and (r.get("qty") or 0) > 0 and abs(float(r["qty"]) - float(r["weight"])) > 1e-9
            and (r.get("amount") or 0) > 0)


kg_all = [r for r in pages("purchase_ledger", COLS, "unit=eq.KG") if is_target(r)]
others = [r for r in kg_all if VENDOR not in str(r.get("vendor") or "")]
live = [r for r in kg_all if VENDOR in str(r.get("vendor") or "")]
print(f"KG 개수 병기 행 {len(kg_all)} → 대상 업체 '{VENDOR}' {len(live)} · 비대상 {len(others)}")
for r in others:
    print("  비대상(건너뜀):", {k: r.get(k) for k in ("ledger_id", "trade_date", "vendor", "item", "qty", "weight", "unit_price", "amount")})

if MODE != "revert" and not os.path.exists(BACKUP):
    io.open(BACKUP, "w", encoding="utf-8").write(json.dumps(
        {"taken_at": dt.datetime.now().isoformat(), "rule": "piece_price_rows", "vendor": VENDOR, "rows": live}, ensure_ascii=False, default=str))
    print("backup written:", BACKUP)
snap = json.load(io.open(BACKUP, encoding="utf-8"))
snap_by = {r["ledger_id"]: r for r in snap["rows"]}
print("snapshot", snap["taken_at"], "rows", len(snap_by))

if MODE == "revert":
    applied = {}
    if os.path.exists(JOURNAL):
        for line in io.open(JOURNAL, encoding="utf-8"):
            rec = json.loads(line)
            if "lid" in rec:
                applied[rec["lid"]] = rec["new"]
    done = skipped = 0
    for lid, r0 in snap_by.items():
        new = applied.get(lid)
        if not new:
            skipped += 1
            continue
        db.clear_cache()
        cur = db.fetch("purchase_ledger", COLS, f"ledger_id=eq.{lid}", limit=1)
        if not cur or not same(cur[0], new, tuple(new.keys())):
            skipped += 1   # 적용 뒤 사람이 바꾼 행은 건드리지 않음
            continue
        restore = {k: r0.get(k) for k in FIELDS}
        if db.update_count("purchase_ledger", f"ledger_id=eq.{lid}", restore, select="ledger_id") == 1:
            db.insert("master_change_log", [{"table_name": "purchase_ledger", "record_id": str(lid), "field_name": "piece_price",
                                             "old_value": json.dumps({k: cur[0].get(k) for k in FIELDS}, ensure_ascii=False, default=str),
                                             "new_value": json.dumps(restore, ensure_ascii=False, default=str), "changed_by": "Claude",
                                             "changed_at": dt.datetime.now(dt.timezone.utc).isoformat(), "reason": f"[일괄 정정 되돌림 {D}] KG 개당 변환"}])
            journal({"revert": lid}); done += 1
    print(f"되돌림 {done} · 건너뜀 {skipped}")
    sys.exit(0)

conv, n = piece_price_rows(list(snap_by.values()))
conv = [r for r in conv if r.get("kg_price") is not None and r["unit"] == "EA"]
print(f"변환 가능 {n} / 스냅샷 {len(snap_by)} (가드 미통과 {len(snap_by) - n})")
imap = {}
pids = {}
for m in pages("purchase_item_map", "map_id,vendor_key,item_key,line_type,material_id,product_id,process_type", "", "map_id"):
    imap[(m["vendor_key"], m["item_key"])] = m
    if m.get("product_id"):
        pids[m["product_id"]] = None
if pids:
    for p in pages("products", "product_id,pn", "", "product_id"):
        if p["product_id"] in pids:
            pids[p["product_id"]] = p["pn"]
    for m in imap.values():
        if m.get("product_id"):
            m["product_pn"] = pids.get(m["product_id"])
km = build_key_mats(pages("materials", "material_id,raw_name,material_type,spec,archived_at", "archived_at=is.null", "material_id"))
live_by = {r["ledger_id"]: r for r in live}
plan, rep = [], Counter()
for m in conv:
    lid = m["ledger_id"]
    b = live_by.get(lid)
    if b is None:
        db.clear_cache()
        cur = db.fetch("purchase_ledger", COLS, f"ledger_id=eq.{lid}", limit=1)
        rep["already_converted" if cur and cur[0].get("unit") == "EA" else "missing"] += 1
        continue
    if not same(b, snap_by[lid], GUARD):
        rep["changed_since_snapshot"] += 1
        continue
    new = {k: m.get(k) for k in ("unit", "unit_price", "kg_price", "ea_price")}
    if not is_linked(b):
        one = [dict(m)]
        if apply_item_map(one, imap):
            new.update({k: one[0].get(k) for k in ("matched_material_id", "mapping_status", "map_id", "category") if one[0].get(k) is not None})
            rep["match:MAP"] += 1
        else:
            mid, why = match_material(m["item"], "EA", m["unit_price"], km)
            if mid:
                new.update({"matched_material_id": mid, "mapping_status": "AUTO_DIMS"})
                rep["match:DIMS"] += 1
            else:
                rep["match:" + why] += 1
    else:
        rep["already_linked"] += 1
    plan.append((lid, new, b))
ups = sorted(p[1]["unit_price"] for p in plan) or [0]
print("분류:", dict(rep))
print(f"대상 {len(plan)} · 개당 단가 min {ups[0]} median {ups[len(ups)//2]} max {ups[-1]} · matched_pn 보유 {sum(1 for p in plan if p[2].get('matched_pn'))}")
print("예시:", [(p[0], p[2]["item"], p[2]["qty"], p[2]["weight"], p[2]["unit_price"], "→", p[1]["unit_price"], p[1].get("matched_material_id")) for p in plan[-5:]])
if MODE == "dry":
    print("드라이런 종료 (--apply 로 실행, 예상 소요 약", round(len(plan) * 0.8 / 60), "분)"); sys.exit(0)

done = failed = 0
try:
    for lid, new, b in plan:
        db.clear_cache()
        cur = db.fetch("purchase_ledger", COLS, f"ledger_id=eq.{lid}", limit=1)
        if not cur or not same(cur[0], b, GUARD):
            failed += 1; print("GUARD FAIL", lid); journal({"guard_fail": lid}); continue
        if db.update_count("purchase_ledger", f"ledger_id=eq.{lid}", new, select="ledger_id") != 1:
            failed += 1; print("UPDATE FAIL", lid); journal({"update_fail": lid}); continue
        journal({"lid": lid, "new": new})
        try:
            db.insert("master_change_log", [{"table_name": "purchase_ledger", "record_id": str(lid), "field_name": "piece_price",
                                             "old_value": json.dumps({k: b.get(k) for k in FIELDS}, ensure_ascii=False, default=str),
                                             "new_value": json.dumps(new, ensure_ascii=False, default=str), "changed_by": "Claude",
                                             "changed_at": dt.datetime.now(dt.timezone.utc).isoformat(), "reason": REASON}])
        except Exception as e:
            print("LOG FAIL", lid, e); journal({"log_fail": lid, "err": str(e)})
        done += 1
finally:
    print(f"완료 {done} · 실패 {failed} · 대상 {len(plan)} · 저널 {JOURNAL}")
