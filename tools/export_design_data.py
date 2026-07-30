# -*- coding: utf-8 -*-
"""디자인용 실데이터 스냅샷 추출

클로드 디자인(또는 다른 디자인 도구)은 Supabase 에 접근할 수 없으므로,
현재 운영 데이터를 화면별 구조 그대로 JSON 한 파일로 뽑아 첨부한다.

실행:  python tools/export_design_data.py
출력:  docs/design-data.json  (+ 콘솔 요약)

주의: 실데이터이므로 외부 공유 시 거래처·단가 노출을 확인할 것.
      단가·금액은 기본 제외(--with-price 로 포함).
"""
import json
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

import db  # noqa: E402

WITH_PRICE = "--with-price" in sys.argv
OUT = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "docs", "design-data.json")


def q(table, select="*", flt="", limit=1000):
    try:
        return db.fetch(table, select, flt, limit=limit)
    except Exception as e:            # 뷰 미존재 등은 빈 배열로
        print(f"  ! {table}: {e}")
        return []


def num(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


today = date.today()
mon = today - timedelta(days=today.weekday())
data = {
    "_meta": {
        "generated": today.isoformat(),
        "source": "우성정밀 업무관리 (Supabase 운영 데이터)",
        "note": "화면에 실제로 표시되는 값 구조. 디자인 시안 작성용.",
        "palette": {
            "primary": "#24406b", "bg": "#f4f5f7", "card": "#ffffff",
            "line": "#e2e5ea", "ink": "#1b2a41", "body": "#333a45",
            "dim": "#7a828d", "warn": "#e8590c", "danger": "#d9480f",
            "good": "#2f9e44", "font": "IBM Plex Sans KR",
        },
        "menu": {
            "flow": ["홈", "수주 관리", "생산 계획", "발주/입고",
                     "공정 관리", "출고 관리"],
            "admin": ["마스터 관리", "원가 확인", "생산 보고"],
        },
    }
}

# ── 수주 (공통 기반) ──
sos = q("sales_orders", "so_id,so_number,customer,so_date,due_date,status",
        'status=not.in.("CANCELLED","CANCELED")&order=so_date.desc', 500)
so_map = {s["so_id"]: s for s in sos}
items = q("sales_order_items",
          "soi_id,so_id,line_no,product_id,canonical_pn,customer_part_no,"
          "qty,received_qty,pending_qty,due_date,status", "", 1000)
items = [i for i in items if i["so_id"] in so_map]
sched = q("so_delivery_schedule",
          "sched_id,so_id,soi_id,seq,due_date,qty,delivered_qty,note",
          "order=due_date.asc", 2000)
stats = q("sales_order_stats",
          "so_id,so_number,customer,so_date,due_date,total_qty,"
          "total_received_qty,total_pending_qty,delivery_status,status",
          'status=not.in.("CANCELLED","CANCELED")&order=so_date.desc', 500)

sc_by_soi = {}
for s in sched:
    e = sc_by_soi.setdefault(s["soi_id"], {"n": 0, "q": 0.0, "d": 0.0,
                                           "next": None})
    e["n"] += 1
    e["q"] += num(s["qty"])
    e["d"] += num(s["delivered_qty"])
    if num(s["qty"]) > num(s["delivered_qty"]):
        if e["next"] is None or s["due_date"] < e["next"]:
            e["next"] = s["due_date"]

# ── 홈 ──
wo = q("wo_tracking", "*", "status=neq.CLOSED&order=created_at.desc", 300)
pstock = q("product_stock_v", "pn,current_stock",
           "current_stock=gt.0&order=current_stock.desc", 200)
rcv = q("po_item_receipt_v", "pending_qty,receipt_status", "", 300)


def wo_stage(t):
    def f(k):
        return num(t.get(k))
    rew = f("rework_qty") - f("rework_in_qty")
    return {
        "생산중": max(0.0, f("input_qty") - f("received_qty")),
        "외주중": max(0.0, f("outsource_qty") - f("outsource_in_qty")),
        "재작업중": max(0.0, rew),
        "검사대기": max(0.0, f("received_qty") + f("outsource_in_qty")
                     - f("outsource_qty") - f("pass_qty")
                     - f("scrap_qty") - f("return_qty") - rew),
    }


stock_map = {p["pn"]: num(p["current_stock"]) for p in pstock}
wip = {}
for w in wo:
    s = wo_stage(w)
    if w.get("pn"):
        wip[w["pn"]] = wip.get(w["pn"], 0) + sum(s.values())

agg = {}
for i in items:
    if num(i["pending_qty"]) <= 0:
        continue
    pn = i.get("canonical_pn") or i.get("customer_part_no") or "-"
    a = agg.setdefault(pn, {"pn": pn, "pending": 0.0, "orders": set(),
                            "customers": set(), "due": None})
    a["pending"] += num(i["pending_qty"])
    a["orders"].add(i["so_id"])
    c = so_map.get(i["so_id"], {}).get("customer")
    if c:
        a["customers"].add(c)
    d = (sc_by_soi.get(i["soi_id"], {}).get("next") or i.get("due_date"))
    if d and (a["due"] is None or d < a["due"]):
        a["due"] = d

data["home"] = {
    "kpi": {
        "미납 수주": sum(num(s["total_pending_qty"]) for s in stats),
        "진행 수주 건": sum(1 for s in stats
                        if num(s["total_pending_qty"]) > 0),
        "소재 입고 대기": sum(num(r["pending_qty"]) for r in rcv),
        "생산중": sum(wo_stage(w)["생산중"] for w in wo),
        "외주중": sum(wo_stage(w)["외주중"] for w in wo),
        "완성 재고": sum(stock_map.values()),
    },
    "by_item": sorted([{
        "품번": a["pn"],
        "거래처": (list(a["customers"])[0] if len(a["customers"]) == 1
                 else f"{len(a['customers'])}개사"),
        "납기": a["due"],
        "수주건": len(a["orders"]),
        "미납": a["pending"],
        "완성재고": stock_map.get(a["pn"], 0),
        "생산중": wip.get(a["pn"], 0),
        "부족": max(0.0, a["pending"] - stock_map.get(a["pn"], 0)
                   - wip.get(a["pn"], 0)),
    } for a in agg.values()],
        key=lambda x: (x["납기"] or "9999", -x["미납"]))[:20],
    "by_order": [{
        "수주번호": s["so_number"], "거래처": s["customer"],
        "납기": s.get("due_date"),
        "미납": num(s["total_pending_qty"]),
        "진행률": round(num(s["total_received_qty"])
                      / max(num(s["total_qty"]), 1), 3),
        "상태": s.get("delivery_status"),
    } for s in stats if num(s["total_pending_qty"]) > 0][:15],
    "완성재고": [{"품번": p["pn"], "재고": num(p["current_stock"])}
              for p in pstock[:10]],
}

# ── 납품 스케줄 (간트 + 주차별) ──
g = []
for s in sched:
    if s["so_id"] not in so_map:
        continue
    it = next((i for i in items if i["soi_id"] == s["soi_id"]), {})
    rem = num(s["qty"]) - num(s["delivered_qty"])
    g.append({
        "품번": it.get("canonical_pn") or it.get("customer_part_no") or "-",
        "거래처": so_map[s["so_id"]]["customer"],
        "수주번호": so_map[s["so_id"]]["so_number"],
        "구분": "분납", "회차": s["seq"], "납기": s["due_date"],
        "수량": num(s["qty"]), "완료": num(s["delivered_qty"]),
        "잔량": max(rem, 0),
        "상태": ("완료" if rem <= 0 else
                "지연" if s["due_date"] < today.isoformat() else "예정"),
    })
for i in items:
    if (num(i["pending_qty"]) <= 0 or not i.get("due_date")
            or i["soi_id"] in sc_by_soi):
        continue
    g.append({
        "품번": i.get("canonical_pn") or i.get("customer_part_no") or "-",
        "거래처": so_map[i["so_id"]]["customer"],
        "수주번호": so_map[i["so_id"]]["so_number"],
        "구분": "단발", "회차": 1, "납기": i["due_date"],
        "수량": num(i["qty"]), "완료": num(i["received_qty"]),
        "잔량": num(i["pending_qty"]),
        "상태": ("지연" if i["due_date"] < today.isoformat() else "예정"),
    })
g.sort(key=lambda x: x["납기"])

wk = {}
for r in g:
    if r["상태"] == "완료":
        continue
    d = date.fromisoformat(r["납기"])
    k = (d - timedelta(days=d.weekday())).isoformat()
    wk.setdefault(r["품번"], {}).setdefault(k, 0)
    wk[r["품번"]][k] += r["잔량"]

data["delivery_schedule"] = {
    "kpi": {
        "이번 주 납품": sum(r["잔량"] for r in g if r["상태"] != "완료"
                       and mon.isoformat() <= r["납기"]
                       < (mon + timedelta(days=7)).isoformat()),
        "다음 주": sum(r["잔량"] for r in g if r["상태"] != "완료"
                    and (mon + timedelta(days=7)).isoformat() <= r["납기"]
                    < (mon + timedelta(days=14)).isoformat()),
        "지연": sum(r["잔량"] for r in g if r["상태"] == "지연"),
        "전체 잔여 계획": sum(r["잔량"] for r in g if r["상태"] != "완료"),
    },
    "gantt": g[:120],
    "weekly_matrix": wk,
}

# ── 생산 계획 ──
bom = q("bom", "product_id,material_id,qty_per_pc,shared_factor",
        "material_id=not.is.null", 2000)
bom_by_pid = {}
for b in bom:
    bom_by_pid.setdefault(b["product_id"], []).append(b)
mids = list({b["material_id"] for b in bom})
mstock = {}
if mids:
    for m in q("material_stock",
               "material_id,raw_name,material_type,spec,unit,current_stock",
               "material_id=in.(" + ",".join(f'"{x}"' for x in mids) + ")",
               600):
        mstock[m["material_id"]] = m
need = {}
for i in items:
    if num(i["pending_qty"]) <= 0 or not i.get("product_id"):
        continue
    for b in bom_by_pid.get(i["product_id"], []):
        qpp = num(b.get("qty_per_pc"), 1) or 1
        sf = num(b.get("shared_factor"), 1) or 1
        need[b["material_id"]] = need.get(b["material_id"], 0) + \
            num(i["pending_qty"]) * qpp / sf
data["production_plan"] = {
    "materials": sorted([{
        "자재": mstock.get(mid, {}).get("raw_name", mid),
        "재질": mstock.get(mid, {}).get("material_type"),
        "규격": mstock.get(mid, {}).get("spec"),
        "총필요량": round(v), "소재재고": num(
            mstock.get(mid, {}).get("current_stock")),
        "발주필요량": round(v - num(
            mstock.get(mid, {}).get("current_stock"))),
    } for mid, v in need.items()],
        key=lambda x: -x["발주필요량"])[:25],
}

# ── 공정 관리 ──
data["process"] = {
    "kpi": {k: sum(wo_stage(w)[k] for w in wo)
            for k in ["생산중", "외주중", "재작업중", "검사대기"]},
    "work_orders": [{
        "작업지시": w["wo_number"], "품번": w.get("pn"),
        "소재LOT": w.get("w_lot"), "투입": num(w.get("input_qty")),
        **wo_stage(w),
        "완성": num(w.get("output_qty")), "상태": w.get("status"),
    } for w in wo[:20]],
}

# ── 발주/입고 ──
data["purchase"] = {
    "receipt_status": [{
        "PO": r.get("po_id"), "품명": r.get("item_name"),
        "발주": num(r.get("ordered_qty")), "입고": num(r.get("received_qty")),
        "미입고": num(r.get("pending_qty")), "상태": r.get("receipt_status"),
    } for r in q("po_item_receipt_v",
                 "po_id,item_name,ordered_qty,received_qty,pending_qty,"
                 "receipt_status", "order=po_id.desc", 30)],
    "material_lots": [{
        "W번호": l.get("lot_number"), "자재": l.get("material_id"),
        "수량": num(l.get("qty")), "입고일": l.get("txn_date"),
    } for l in q("inventory_transactions",
                 "lot_number,material_id,qty,txn_date",
                 "txn_type=eq.RECEIPT&lot_number=like.W*"
                 "&order=txn_id.desc", 20)],
}

# ── 마스터 요약 ──
data["master"] = {
    "products": len(q("products", "product_id", "archived_at=is.null", 2000)),
    "materials": len(q("materials", "material_id", "", 2000)),
    "bom_lines": len(bom),
    "customers": sorted({s["customer"] for s in sos if s.get("customer")}),
}

if not WITH_PRICE:
    data["_meta"]["note"] += " 단가·금액은 제외됨 (--with-price 로 포함)."

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=1)

print("OK ->", OUT)
print(f"  홈 품번 {len(data['home']['by_item'])}행 / 수주 "
      f"{len(data['home']['by_order'])}행")
print(f"  스케줄 회차 {len(data['delivery_schedule']['gantt'])} / 주차 "
      f"매트릭스 품번 {len(data['delivery_schedule']['weekly_matrix'])}")
print(f"  자재 {len(data['production_plan']['materials'])} / 작업지시 "
      f"{len(data['process']['work_orders'])}")
print(f"  파일 크기 {os.path.getsize(OUT):,} bytes")
