# -*- coding: utf-8 -*-
"""L3-D: purchase_ledger 혜성철강 환봉+절단비 쌍을 합산 행으로 재처리 (2026-10-15, Data Reviewer v2 반영).
사용:
  python ledger_cut_merge.py                       드라이런(읽기 전용). 백업 JSON 은 없을 때만 작성(덮어쓰지 않음).
  python ledger_cut_merge.py --apply               백업 스냅샷을 기준으로 쌍마다 가드 → 환봉 UPDATE(1행 확인) → 절단비 DELETE(1행 확인)
                                                   → 이력 2행 즉시 insert(+로컬 JSONL). 재실행 안전(합산된 쌍·잔존 절단비는 보고만).
  python ledger_cut_merge.py --revert              스냅샷대로 복원(환봉 행 필드 복원 + 절단비 행 원 ledger_id 로 재삽입) + 되돌림 이력.
규칙은 utils.purchase_sync.merge_cutting_rows 와 동일(앱 동기화와 한 코드)."""
import io, json, os, sys, datetime as dt
from collections import Counter

os.chdir(r"C:\wsapp")
sys.path.insert(0, r"C:\wsapp")
import db  # noqa: E402
from utils.purchase_sync import merge_cutting_rows, match_material, build_key_mats, dedup_key  # noqa: E402

JOURNAL_DIR = os.path.dirname(os.path.abspath(__file__))
MODE = "apply" if "--apply" in sys.argv else ("revert" if "--revert" in sys.argv else "dry")
D = "2026-10-15"
BACKUP = rf"G:\내 드라이브\제품관리DB\_혜성절단비합산_정정전백업_{D.replace('-', '')}.json"
JOURNAL = os.path.join(JOURNAL_DIR, f"ledger_cut_merge_journal_{MODE}.jsonl")
REASON = f"[일괄 정정 {D}] 혜성철강 환봉+절단비 합산(개당 단가)"
REASON_R = f"[일괄 정정 되돌림 {D}] 혜성철강 환봉+절단비 합산"
COLS = ("ledger_id,trade_date,vendor,item,unit,qty,weight,unit_price,amount,vat,total,remark,"
        "category,vendor_normalized,kg_price,ea_price,matched_pn,synced_at,matched_material_id,mapping_status")
FIELDS = ("unit", "qty", "weight", "unit_price", "amount", "vat", "total", "remark", "kg_price", "ea_price", "matched_pn")
GUARD_KEYS = ("item", "unit", "qty", "amount", "trade_date", "remark")


def fetch_pages(table, cols, filt, order="ledger_id"):
    out, off = [], 0
    while True:
        pg = db.fetch(table, cols, f"{filt}&order={order}&offset={off}", limit=1000)
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


def log_rows(rows):
    db.insert("master_change_log", rows)


HY = "vendor=ilike.*%ED%98%9C%EC%84%B1*"
live = fetch_pages("purchase_ledger", COLS, HY)
live.sort(key=lambda r: r["ledger_id"])

if MODE in ("dry", "apply") and not os.path.exists(BACKUP):
    snap_rows = live
    merged0, n0 = merge_cutting_rows(snap_rows)
    snap = {"taken_at": dt.datetime.now().isoformat(), "rule": "merge_cutting_rows", "rows_all": snap_rows,
            "pairs": [{"bar_id": m["ledger_id"], "cut_id": m["_merged_from"]["ledger_id"]} for m in merged0 if m.get("_merged_from")]}
    io.open(BACKUP, "w", encoding="utf-8").write(json.dumps(snap, ensure_ascii=False, default=str))
    print("backup written:", BACKUP)
snap = json.load(io.open(BACKUP, encoding="utf-8"))
snap_by_id = {r["ledger_id"]: r for r in snap["rows_all"]}
print(f"snapshot {snap['taken_at']} rows={len(snap['rows_all'])} pairs={len(snap['pairs'])} | live rows={len(live)}")

if MODE == "revert":
    done = skipped = failed = 0
    for p in snap["pairs"]:
        bar0, cut0 = snap_by_id[p["bar_id"]], snap_by_id[p["cut_id"]]
        db.clear_cache()
        cur = db.fetch("purchase_ledger", COLS, f"ledger_id=eq.{p['bar_id']}", limit=1)
        cut_live = db.fetch("purchase_ledger", "ledger_id", f"ledger_id=eq.{p['cut_id']}", limit=1)
        if not cur or "[+절단비" not in str(cur[0].get("remark") or "") or cut_live:
            skipped += 1
            continue
        restore = {k: bar0.get(k) for k in FIELDS + ("matched_material_id", "mapping_status")}
        if db.update_count("purchase_ledger", f"ledger_id=eq.{p['bar_id']}", restore, select="ledger_id") != 1:
            failed += 1
            print("REVERT UPDATE FAIL", p)
            continue
        ins = {k: cut0.get(k) for k in cut0 if k != "synced_at"}
        db.insert("purchase_ledger", [ins])
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        log_rows([{"table_name": "purchase_ledger", "record_id": str(p["bar_id"]), "field_name": "cut_merge", "old_value": json.dumps({k: cur[0].get(k) for k in FIELDS}, ensure_ascii=False, default=str), "new_value": json.dumps(restore, ensure_ascii=False, default=str), "changed_by": "Claude", "changed_at": now, "reason": REASON_R},
                  {"table_name": "purchase_ledger", "record_id": str(p["cut_id"]), "field_name": "restored", "old_value": None, "new_value": json.dumps(ins, ensure_ascii=False, default=str), "changed_by": "Claude", "changed_at": now, "reason": REASON_R}])
        journal({"revert": p})
        done += 1
    print(f"되돌림 완료 {done} · 건너뜀 {skipped} · 실패 {failed}")
    sys.exit(0)

# ── 드라이런/실행 공통: 스냅샷 기준 쌍, 현재 상태 분류 ──
merged, n = merge_cutting_rows(snap["rows_all"])
pairs = [m for m in merged if m.get("_merged_from")]
assert len(pairs) == len(snap["pairs"]) == n, (len(pairs), len(snap["pairs"]), n)
live_by_id = {r["ledger_id"]: r for r in live}
live_keys = Counter(dedup_key(r) for r in live)
mats = fetch_pages("materials", "material_id,raw_name,material_type,spec,archived_at", "archived_at=is.null", order="material_id")
km = build_key_mats(mats)

plan, report = [], Counter()
for m in pairs:
    bar_id, cut = m["ledger_id"], m["_merged_from"]
    cut_id = cut["ledger_id"]
    b, c = live_by_id.get(bar_id), live_by_id.get(cut_id)
    if cut_id != bar_id + 1:
        report["non_adjacent"] += 1
        continue
    if b is None:
        report["bar_missing"] += 1
        continue
    if c is None:
        report["already_merged" if "[+절단비" in str(b.get("remark") or "") else "cut_missing_bar_raw"] += 1
        continue
    if "[+절단비" in str(b.get("remark") or ""):
        report["MERGED_BUT_CUT_REMAINS(manual)"] += 1
        print("  !! 환봉은 합산됐는데 절단비 행 잔존 — 수동 확인:", bar_id, cut_id)
        continue
    if not same(b, snap_by_id[bar_id], GUARD_KEYS) or not same(c, snap_by_id[cut_id], GUARD_KEYS):
        report["changed_since_snapshot"] += 1
        continue
    mk = dedup_key(m)
    if live_keys.get(mk, 0) > 0:
        report["merged_key_already_in_db(dup from sync?)"] += 1
        print("  !! 합산 키가 이미 장부에 있음:", bar_id, mk)
        continue
    new_fields = {k: m.get(k) for k in FIELDS}
    mid = None
    if not b.get("matched_material_id"):
        mid, why = match_material(m["item"], m["unit"], m["unit_price"], km)
        report["match:" + (mid if mid else why)] += 1
        if mid:
            new_fields.update({"matched_material_id": mid, "mapping_status": "AUTO_DIMS"})
    else:
        report["already_matched:" + b["matched_material_id"]] += 1
    plan.append((bar_id, cut_id, new_fields, b, c))
    report["ready"] += 1

ups = sorted(p[2]["unit_price"] for p in plan) or [0]
print("분류:", dict(report))
print(f"실행 대상 {len(plan)} · 개당 단가 min {ups[0]} median {ups[len(ups)//2]} max {ups[-1]} · 이상치(<20 or >30000):",
      [(p[0], p[2]['unit_price']) for p in plan if p[2]['unit_price'] < 20 or p[2]['unit_price'] > 30000][:10])
print("예시:", [(p[0], p[3]["trade_date"], p[3]["item"], p[2]["qty"], p[2]["unit_price"], p[2]["remark"]) for p in plan[-4:]])

if MODE == "dry":
    print("드라이런 종료 (--apply 로 실행)")
    sys.exit(0)

done = failed = 0
try:
    for bar_id, cut_id, new_fields, b, c in plan:
        db.clear_cache()
        cur_b = db.fetch("purchase_ledger", COLS, f"ledger_id=eq.{bar_id}", limit=1)
        cur_c = db.fetch("purchase_ledger", COLS, f"ledger_id=eq.{cut_id}", limit=1)
        if not cur_b or not cur_c or not same(cur_b[0], b, GUARD_KEYS) or not same(cur_c[0], c, GUARD_KEYS):
            failed += 1
            print("GUARD FAIL (live changed)", bar_id, cut_id)
            journal({"guard_fail": [bar_id, cut_id]})
            continue
        nu = db.update_count("purchase_ledger", f"ledger_id=eq.{bar_id}", new_fields, select="ledger_id")
        if nu != 1:
            failed += 1
            print("UPDATE FAIL", bar_id, nu)
            journal({"update_fail": bar_id, "count": nu})
            continue
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        rows = [{"table_name": "purchase_ledger", "record_id": str(bar_id), "field_name": "cut_merge",
                 "old_value": json.dumps({k: b.get(k) for k in FIELDS + ("matched_material_id", "mapping_status")}, ensure_ascii=False, default=str),
                 "new_value": json.dumps(new_fields, ensure_ascii=False, default=str),
                 "changed_by": "Claude", "changed_at": now, "reason": f"{REASON} ← 절단비 행 {cut_id}"}]
        nd = db.delete("purchase_ledger", f"ledger_id=eq.{cut_id}")
        if nd == 1:
            rows.append({"table_name": "purchase_ledger", "record_id": str(cut_id), "field_name": "deleted",
                         "old_value": json.dumps({k: c.get(k) for k in COLS.split(",") if k != "synced_at"}, ensure_ascii=False, default=str),
                         "new_value": None, "changed_by": "Claude", "changed_at": now, "reason": f"{REASON} → 환봉 행 {bar_id} 에 합산"})
        else:
            failed += 1
            print("DELETE FAIL (환봉은 합산됨 — 절단비 행 수동 삭제 필요)", bar_id, cut_id, nd)
            rows[0]["reason"] += " [절단비 행 삭제 실패 — 잔존]"
        log_rows(rows)
        journal({"bar": bar_id, "cut": cut_id, "new": new_fields, "deleted": nd == 1})
        if nd == 1:
            done += 1
finally:
    print(f"완료 {done} · 실패 {failed} · 대상 {len(plan)} · 저널 {JOURNAL}")
