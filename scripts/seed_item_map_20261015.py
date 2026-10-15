# -*- coding: utf-8 -*-
"""매핑표 씨앗 (2026-10-15, 매입 내재화 1단계): purchase_ledger 의 기존 자재 매칭(matched_material_id)에서
(vendor_key, item_key) → 자재 를 뽑아 purchase_item_map 에 넣는다. 키당 자재가 1개인 것만(충돌 건너뜀), 휴면 자재 제외.
PRODUCT(비고 품번만 있는 키)는 1단계 씨앗에서 제외 — 소재 품명에 제품 품번이 붙은 경우가 섞여 있어(Reviewer B1) 확인 대기에서 사람이 연결.
사용: python scripts/seed_item_map_20261015.py [--apply]   (기본 드라이런)"""
import os, sys
from collections import defaultdict, Counter

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.getcwd())
import db  # noqa: E402
from utils.purchase_sync import vendor_key, item_key  # noqa: E402

APPLY = "--apply" in sys.argv


def pages(table, cols, filt, order):
    out, off = [], 0
    while True:
        pg = db.fetch(table, cols, (f"{filt}&" if filt else "") + f"order={order}&offset={off}", limit=1000)
        out += pg
        if len(pg) < 1000:
            return out
        off += 1000


rows = pages("purchase_ledger", "ledger_id,vendor,item,matched_material_id,mapping_status,trade_date",
             "matched_material_id=not.is.null", "ledger_id")
mats = {m["material_id"]: m for m in pages("materials", "material_id,archived_at", "", "material_id")}
existing = {(m["vendor_key"], m["item_key"]) for m in pages("purchase_item_map", "vendor_key,item_key", "", "map_id")}
print(f"matched ledger rows {len(rows)} · materials {len(mats)} · map existing {len(existing)}")

grp = defaultdict(lambda: {"mats": Counter(), "sample": None, "last": ""})
for r in rows:
    k = (vendor_key(r["vendor"]), item_key(r["item"]))
    g = grp[k]
    g["mats"][r["matched_material_id"]] += 1
    if not g["sample"] or str(r.get("trade_date")) > g["last"]:
        g["sample"], g["last"] = r["item"], str(r.get("trade_date"))

seed, skipped = [], Counter()
for (vk, ik), g in grp.items():
    if (vk, ik) in existing:
        skipped["exists"] += 1
        continue
    if not vk or not ik:
        skipped["empty_key"] += 1
        continue
    if len(g["mats"]) > 1:
        skipped["material_conflict"] += 1
        continue
    mid = next(iter(g["mats"]))
    m = mats.get(mid)
    if not m:
        skipped["material_missing"] += 1
        continue
    if m.get("archived_at"):
        skipped["material_archived"] += 1
        continue
    lt = "SUPPLY" if mid[:1] in ("C", "T") else "MATERIAL"
    seed.append({"vendor_key": vk, "item_key": ik, "item_sample": g["sample"], "line_type": lt,
                 "material_id": mid, "origin": "SEED", "confirmed_by": "seed"})
print("seed rows:", len(seed), "| by type:", dict(Counter(s["line_type"] for s in seed)), "| skipped:", dict(skipped))
print("examples:", [(s["vendor_key"], s["item_key"], s["material_id"]) for s in seed[:8]])
if APPLY:
    n = 0
    for i in range(0, len(seed), 200):
        n += db.insert("purchase_item_map", seed[i:i + 200])
    print("inserted", n)
else:
    print("dry-run (--apply to insert)")
