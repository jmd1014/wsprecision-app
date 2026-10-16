# -*- coding: utf-8 -*-
"""미연결 매입 행 규칙 처리 (2026-10-16, 사용자: "규칙성이 있는 건 처리하고 파악 어려운 것만 따로").
A. 업체 기본 유형(와일드카드) 추가: 현대연마 PROCESS/SURFACE, 성창테크·이노켐·해광지오메트·서진씨앤에스 SUPPLY, 대일정공·월드브라스트·라인자동화 OTHER
B. 오리엔스테크(고기호 포함): 품명 첫 토큰 = 제품 품번(정확/DIC 접두 3·4·6 제거/별칭, 후보 1개) → PRODUCT. 토큰 오타는 같은 업체가 이미
   연결한 품번과 유사도 ≥ 88 + 나머지 품명 유사도 ≥ 80 일 때만.
C. 같은 업체의 기존 매핑 품명과 유사도 ≥ 90 → 같은 매핑 적용(표기 변형).
D. 소재(명진·유성·혜성·건흥): 재질+치수가 읽히고 자재 마스터에 없으면 자재 신규 등록(M###, 명명 규칙 기존과 동일) → 치수 매칭으로 연결.
사용: python scripts/intake_rules_20261016.py [--apply]"""
import os, sys, re, json, datetime as dt
from collections import Counter, defaultdict

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.getcwd())
import db  # noqa: E402
from utils.purchase_sync import vendor_key, item_key, norm_grade, norm_dims, is_hex, build_key_mats, match_material, apply_item_map  # noqa: E402
from rapidfuzz import fuzz, process  # noqa: E402

APPLY = "--apply" in sys.argv
D = "2026-10-16"
WHO = "Claude"
REASON = f"[일괄 정정 {D}] 미연결 매입 규칙 처리"
VENDOR_DEFAULTS = {"현대연마": ("PROCESS", "SURFACE"), "성창테크": ("SUPPLY", None), "이노켐": ("SUPPLY", None),
                   "해광지오메트": ("SUPPLY", None), "서진씨앤에스": ("SUPPLY", None), "대일정공": ("OTHER", None),
                   "월드브라스트": ("OTHER", None), "라인자동화": ("OTHER", None)}
MATERIAL_VENDORS = ("명진메탈", "유성메탈", "혜성철강", "건흥금속")
GRADE_TYPE = {"304": "SUS304", "316": "SUS316", "316L": "SUS316L", "630": "SUS630", "AL6061": "AL6061", "S45C": "S45C",
              "S20C": "S20C", "SCM415": "SCM415", "SCM420": "SCM420H", "SCM440": "SCM440"}
RAW_PREFIX = {"304": "S304", "316": "S316", "316L": "S316", "630": "S630", "AL6061": "AL6061", "S45C": "S45C", "S20C": "S20C",
              "SCM415": "SCM415", "SCM420": "SCM420H", "SCM440": "SCM440"}


def pages(table, cols, filt, order):
    out, off = [], 0
    while True:
        pg = db.fetch(table, cols, (f"{filt}&" if filt else "") + f"order={order}&offset={off}", limit=1000)
        out += pg
        if len(pg) < 1000:
            return out
        off += 1000


LOOSE_RE = re.compile(r"(\d+(?:\.\d+)?)[^\d*xX×]{0,2}[*xX×]\s*(\d+(?:\.\d+)?)")   # '28Φx97', '40Μ*25' 도 허용


def loose_dims(text):
    """norm_dims 가 못 읽는 'S45C 22x15'·'BE6061T6 56*15L' 도 (지름, 길이)로. 세 숫자(t*w*L)는 norm_dims 결과."""
    d = norm_dims(text)
    if d:
        return d
    m = LOOSE_RE.search(str(text).replace("ℓ", "").replace("Ｌ", "L"))
    if m:
        return ("HX" if is_hex(text) else "RD", float(m.group(1)), float(m.group(2)))
    return None


def fmt(v):
    return str(int(v)) if float(v).is_integer() else str(v)


unl = pages("purchase_ledger", "ledger_id,vendor,item,unit,qty,unit_price,amount,remark,trade_date",
            f"matched_material_id=is.null&mapping_status=is.null&trade_date=gte.{(dt.date.today()-dt.timedelta(days=365)).isoformat()}", "ledger_id")
maps = pages("purchase_item_map", "map_id,vendor_key,item_key,item_sample,line_type,material_id,product_id,process_type,origin", "", "map_id")
products = pages("products", "product_id,pn,alias_list,archived_at", "archived_at=is.null", "product_id")
materials = pages("materials", "material_id,raw_name,material_type,spec,archived_at,main_supplier", "archived_at=is.null", "material_id")
pn_by_id = {p["product_id"]: p["pn"] for p in products}
print(f"미연결 {len(unl)}행 · 매핑표 {len(maps)} · 제품 {len(products)} · 자재 {len(materials)}")

actions = []          # (kind, rows[ledger_id], map_row(dict) or material(dict), note)
done_ids = set()
by_vendor = defaultdict(list)
for r in unl:
    by_vendor[vendor_key(r["vendor"])].append(r)

# ── A. 업체 기본 ──
existing_wild = {m["vendor_key"] for m in maps if m["item_key"] == "*"}
for vk, (lt, proc) in VENDOR_DEFAULTS.items():
    rows = by_vendor.get(vk, [])
    if vk in existing_wild or not rows:
        continue
    actions.append(("A", [r["ledger_id"] for r in rows], {"vendor_key": vk, "item_key": "*", "item_sample": f"{rows[0]['vendor']} 업체 기본",
                    "line_type": lt, "process_type": proc, "origin": "USER", "confirmed_by": WHO}, f"{rows[0]['vendor']} → {lt}"))
    done_ids.update(r["ledger_id"] for r in rows)

# ── B. 오리엔스테크 토큰 → 제품 ──
def product_candidates(tok):
    t = tok.upper()
    c = set()
    for p in products:
        pn = p["pn"].upper()
        if pn == t or re.sub(r"^[346]", "", pn) == t:
            c.add(p["product_id"])
        elif p.get("alias_list") and t in [a.strip().upper() for a in re.split(r"[,;]", p["alias_list"])]:
            c.add(p["product_id"])
    return sorted(c)


vend_product_maps = defaultdict(list)   # vendor_key → [(token, rest_key, product_id)]
for m in maps:
    if m["line_type"] == "PRODUCT" and m.get("product_id") and m["item_key"] != "*":
        toks = (m.get("item_sample") or "").split()
        if toks:
            vend_product_maps[m["vendor_key"]].append((toks[0].upper(), item_key(" ".join(toks[1:])), m["product_id"]))
for vk in ("오리엔스테크", "오리엔스테크고기호", "오리엔스테크", "오리엔스테크고기호"):   # 2회: 1회차 매핑을 2회차 오타 보정에 활용
    groups = defaultdict(list)
    for r in by_vendor.get(vk, []):
        if r["ledger_id"] in done_ids:
            continue
        groups[(r["item"].split() or [""])[0].upper(), item_key(r["item"])].append(r)
    for (tok, ik), rows in groups.items():
        pid, how = None, None
        cands = product_candidates(tok)
        if len(cands) == 1:
            pid, how = cands[0], "토큰=품번"
        else:
            rest = item_key(" ".join(rows[0]["item"].split()[1:]))
            best = None
            for pk in ("오리엔스테크", "오리엔스테크고기호"):
                for t2, rest2, pid2 in vend_product_maps.get(pk, []):
                    sc = fuzz.ratio(tok, t2)
                    if sc >= 92 and len(tok) != len(t2) and fuzz.ratio(rest, rest2) >= 80 and (best is None or sc > best[0]):
                        best = (sc, pid2, t2)
            if best:
                pid, how = best[1], f"오타 보정({tok}≈{best[2]})"
        if pid:
            actions.append(("B", [r["ledger_id"] for r in rows], {"vendor_key": vk, "item_key": ik, "item_sample": rows[0]["item"],
                            "line_type": "PRODUCT", "product_id": pid, "origin": "USER", "confirmed_by": WHO}, f"{rows[0]['item']} → {pn_by_id[pid]} ({how})"))
            done_ids.update(r["ledger_id"] for r in rows)
            vend_product_maps[vk].append((tok, item_key(" ".join(rows[0]["item"].split()[1:])), pid))

# ── C. 같은 업체 기존 매핑과 유사 표기 ──
for vk, rows in by_vendor.items():
    cand_maps = [m for m in maps if m["vendor_key"] == vk and m["item_key"] != "*"]
    if not cand_maps:
        continue
    keys = {m["item_key"]: m for m in cand_maps}
    groups = defaultdict(list)
    for r in rows:
        if r["ledger_id"] not in done_ids:
            groups[item_key(r["item"])].append(r)
    for ik, grp in groups.items():
        m = process.extractOne(ik, list(keys), scorer=fuzz.ratio)
        if m and m[1] >= 90:
            tgt = keys[m[0]]
            if tgt["line_type"] in ("MATERIAL", "SUPPLY"):
                d1, d2 = loose_dims(grp[0]["item"]), loose_dims(tgt.get("item_sample") or "")
                if not d1 or not d2 or d1 != d2:
                    continue          # 치수가 다르면 다른 자재 (340×15 ≠ 340×14)
            actions.append(("C", [r["ledger_id"] for r in grp], {"vendor_key": vk, "item_key": ik, "item_sample": grp[0]["item"],
                            "line_type": tgt["line_type"], "material_id": tgt.get("material_id"), "product_id": tgt.get("product_id"),
                            "process_type": tgt.get("process_type"), "origin": "USER", "confirmed_by": WHO},
                            f"{grp[0]['item']} ≈ {tgt['item_sample']} ({m[1]:.0f}) → {tgt['line_type']} {tgt.get('material_id') or pn_by_id.get(tgt.get('product_id') or '', '')}"))
            done_ids.update(r["ledger_id"] for r in grp)

# ── D. 소재 자재 신규 등록 ──
km = build_key_mats(materials)
new_mats, mat_actions = [], []
next_no = max(int(m["material_id"][1:]) for m in materials if re.match(r"^M\d+$", m["material_id"])) + 1
seen_specs = {}
for vk in MATERIAL_VENDORS:
    groups = defaultdict(list)
    for r in by_vendor.get(vk, []):
        if r["ledger_id"] in done_ids:
            continue
        groups[item_key(r["item"])].append(r)
    for ik, grp in groups.items():
        item = grp[0]["item"]
        if re.search(r"임가공|반품|절단비|불량", item):
            continue
        g, d = norm_grade(item), loose_dims(item)
        if not g or not d or g not in GRADE_TYPE:
            continue
        if d[0] != "SQ" and (d[1] > 400 or d[2] > 3000):
            continue              # 'Ø1440' 같은 오타 — 사람 확인
        hexed = is_hex(item) or d[0] == "HX"
        # 이미 있는 자재(치수 키)면 매칭 규칙이 붙여야 했음 — 단가 0 등으로 못 붙은 경우: 바로 연결
        from utils.purchase_sync import keyize
        k = keyize(g, d, hexed)
        mids = km.get(k, [])
        if len(mids) == 1:
            actions.append(("D-link", [r["ledger_id"] for r in grp], {"material_id": mids[0]}, f"{item} → 기존 자재 {mids[0]}"))
            done_ids.update(r["ledger_id"] for r in grp)
            continue
        if len(mids) > 1:
            continue
        spec_key = (g, d, hexed)
        if spec_key in seen_specs:
            mid = seen_specs[spec_key]
        else:
            mid = f"M{next_no:03d}"; next_no += 1
            if d[0] == "SQ":
                dims_s = f"{fmt(d[1])}*{fmt(d[2])}*{fmt(d[3])}"
                raw, spec = f"{RAW_PREFIX[g]} {dims_s}", dims_s
            else:
                shape = "H" if hexed else "Ø"
                raw, spec = f"{RAW_PREFIX[g]} {shape}{fmt(d[1])}*{fmt(d[2])}", f"φ{fmt(d[1])}*{fmt(d[2])}L"
            new_mats.append({"material_id": mid, "raw_name": raw, "material_type": GRADE_TYPE[g], "spec": spec, "unit": "EA",
                             "procurement_type": "도급", "main_supplier": grp[0]["vendor"], "in_use": True,
                             "remark": f"[자동 등록 {D}] 매입 품명 '{item}'"})
            seen_specs[spec_key] = mid
        actions.append(("D-new", [r["ledger_id"] for r in grp], {"material_id": mid}, f"{item} → 신규 자재 {mid} {new_mats[-1]['raw_name'] if new_mats and new_mats[-1]['material_id']==mid else mid}"))
        done_ids.update(r["ledger_id"] for r in grp)

# ── 보고 ──
print("\n[A] 업체 기본:", [a[3] + f" ({len(a[1])}행)" for a in actions if a[0] == "A"])
print("\n[B] 오리엔스테크 제품:")
for a in actions:
    if a[0] == "B":
        print("   ", a[3], f"({len(a[1])}행)")
print("\n[C] 유사 표기:")
for a in actions:
    if a[0] == "C":
        print("   ", a[3], f"({len(a[1])}행)")
print("\n[D] 소재: 신규 자재", len(new_mats))
for m in new_mats:
    print("   ", m["material_id"], m["material_type"], m["raw_name"], "|", m["spec"], "|", m["main_supplier"])
for a in actions:
    if a[0].startswith("D"):
        print("   ", a[0], a[3], f"({len(a[1])}행)")
rest = [r for r in unl if r["ledger_id"] not in done_ids]
print(f"\n처리 {len(done_ids)}행 / 남는 미연결 {len(rest)}행:")
for r in rest:
    print("   ", r["ledger_id"], r["vendor"], "[", r["item"], "]", r.get("remark") or "")

if not APPLY:
    print("\n드라이런 (--apply 로 실행)"); sys.exit(0)

# ── 실행 ──
logs, n_rows = [], 0
now = dt.datetime.now(dt.timezone.utc).isoformat()
if new_mats:
    db.insert("materials", new_mats)
    for m in new_mats:
        logs.append({"table_name": "materials", "record_id": m["material_id"], "field_name": "created", "old_value": None,
                     "new_value": json.dumps(m, ensure_ascii=False), "changed_by": WHO, "changed_at": now, "reason": REASON + " — 매입 품명에서 자재 신규 등록"})
for kind, ids, obj, note in actions:
    fields = None
    if kind in ("A", "B", "C"):
        db.clear_cache()
        ex = db.fetch("purchase_item_map", "map_id", f"vendor_key=eq.{db.qv(obj['vendor_key'])}&item_key=eq.{db.qv(obj['item_key'])}", limit=1)
        if ex:
            map_id = ex[0]["map_id"]
        else:
            db.insert("purchase_item_map", [{k: v for k, v in obj.items() if v is not None}])
            db.clear_cache()
            map_id = db.fetch("purchase_item_map", "map_id", f"vendor_key=eq.{db.qv(obj['vendor_key'])}&item_key=eq.{db.qv(obj['item_key'])}", limit=1)[0]["map_id"]
        fields = {"mapping_status": "MAP", "map_id": map_id}
        if obj.get("material_id"):
            fields["matched_material_id"] = obj["material_id"]
        if obj.get("product_id"):
            fields["matched_pn"] = pn_by_id[obj["product_id"]]
        cat = obj["line_type"]
    else:
        fields = {"matched_material_id": obj["material_id"], "mapping_status": "AUTO_DIMS"}
        cat = "MATERIAL"
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        flt = "ledger_id=in.(" + ",".join(map(str, chunk)) + ")"
        if db.update("purchase_ledger", flt, fields):
            db.update("purchase_ledger", flt + "&category=is.null", {"category": cat})
            n_rows += len(chunk)
            for lid in chunk:
                logs.append({"table_name": "purchase_ledger", "record_id": str(lid), "field_name": "rule_link", "old_value": None,
                             "new_value": json.dumps(fields, ensure_ascii=False), "changed_by": WHO, "changed_at": now, "reason": f"{REASON} [{kind}] {note}"})
        else:
            print("UPDATE FAIL", kind, chunk)
for i in range(0, len(logs), 200):
    db.insert("master_change_log", logs[i:i + 200])
print(f"\n적용: 장부 {n_rows}행, 신규 자재 {len(new_mats)}, 이력 {len(logs)}")
