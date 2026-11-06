# -*- coding: utf-8 -*-
"""확정 출고 전표의 정정(EDIT)·취소(CANCEL) — 서버 함수 `revise_shipment`(082)의 순수 모델 + 화면 payload 조립.

P3-1a (2026-11-06, 계획서 v3 — §18 이 본문보다 우선). 이 모듈은 DB 를 모른다.

- `plan_revision(state, request, today, now)` — 082 `revise_shipment` 와 **같은 규칙**의 파이썬 모델.
  입력 state = 표 이름 → 행 목록(ship_mock 세계와 같은 모양), 출력 = (결과 dict, 새 state).
  CI 는 이것을 가짜 RPC 로 쓰고, 로컬 복원 DB 시험(L1)은 같은 골든 벡터로 실제 SQL 과 대조한다.
- `build_payload(state, shipment_id, new_qtys, reason, who, allow_over, today)` — 화면이 보낼 payload.
  감소는 서버가 계산하므로 lines 만, 증가는 확정(069)처럼 화면이 회차·충당·LOT 를 계획한다(감소 반영 뒤 기준).
- `request_md5(request)` — 재실행 내용 대조용 정규화 해시(§18 A5). who 제외.

규칙 출처: 계획서 §4-3(처리 순서)·§4-4(거부 코드)·§4-5(데이터 사유)·§18 A1~A11.
"""
import copy
import hashlib
import re
from decimal import Decimal

from utils.delivery_alloc import allocate_rounds
from utils.shipment_adjust import net_issued_by_lot, split_round_alloc
from utils.so_close import LINE_INACTIVE, header_status, revise_line_fields

EPS = 1e-9
SO_INACTIVE_HDR = ("CLOSED", "CANCELLED", "CANCELED")
# 충당 저장(2026-09-05) 전 옛 전표 라인 — 「충당 기록 없음 + 회차 있음」(계획서 §4-5 유형 A, 운영 13라인 · 전표 10장)
LEGACY_NO_ALLOC_SI = frozenset({4, 10, 16, 17, 23, 36, 48, 60, 63, 78, 99, 148, 176})
DATA_REASONS = ("legacy_no_alloc", "issue_mismatch", "round_short", "recv_underflow")


class Reject(Exception):
    """P0001 거부 — 쓰기 없음. code 는 계획서 §4-4 의 코드(`stock:P1` 처럼 꼬리 포함 가능)."""

    def __init__(self, code, hint=None):
        super().__init__(code)
        self.code = code
        self.hint = hint


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _num(v):
    """정규화 숫자 표기 — SQL `trim_scale(round(x::numeric, 6))::text` 와 같은 글자(500.0 → '500', 12.50 → '12.5')."""
    d = Decimal(repr(round(_f(v), 6))).normalize()
    s = format(d, "f")
    return "0" if s in ("-0", "0") else s


# ── 재실행 내용 대조(§18 A5) ──
def request_md5(req):
    """action · reason · allow_over · lines(si 오름차순) · inc(배열 정렬)의 정규화 문자열 md5. who 는 제외.

    082 `revise_shipment` 가 같은 문자열을 만든다(정렬은 숫자 순, 문자열은 C 정렬):
      a=<action>|r=<reason>|o=<1|0>|l=<si:전:후;…>|e=<soi:납품;…>|s=<sched:soi:delta;…>|c=<si:sched:qty;…>
      |t=<si:product:qty:unit:lot:work_order;…>
    """
    inc = req.get("inc") or {}
    lines = sorted((int(l["si_id"]), _f(l.get("qty_before")), _f(l.get("qty_after")))
                   for l in (req.get("lines") or []))
    exp = sorted((int(e["soi_id"]), _f(e.get("received"))) for e in (inc.get("expected_received_before") or []))
    sch = sorted((int(s["sched_id"]), int(s["soi_id"]), _f(s.get("delta"))) for s in (inc.get("scheds") or []))
    alc = sorted((int(a["si_id"]), int(a["sched_id"]), _f(a.get("qty"))) for a in (inc.get("allocs") or []))
    txs = sorted((int(t["si_id"]), str(t.get("product_id") or ""), _f(t.get("qty")), str(t.get("unit") or ""),
                  str(t.get("lot_number") or ""), str(t.get("work_order") or "")) for t in (inc.get("txns") or []))
    s = "|".join([
        "a=" + str(req.get("action") or ""),
        "r=" + str(req.get("reason") or "").strip(),
        "o=" + ("1" if req.get("allow_over") else "0"),
        "l=" + ";".join(f"{a}:{_num(b)}:{_num(c)}" for a, b, c in lines),
        "e=" + ";".join(f"{a}:{_num(b)}" for a, b in exp),
        "s=" + ";".join(f"{a}:{b}:{_num(c)}" for a, b, c in sch),
        "c=" + ";".join(f"{a}:{b}:{_num(c)}" for a, b, c in alc),
        "t=" + ";".join(f"{a}:{b}:{_num(c)}:{d}:{e}:{g}" for a, b, c, d, e, g in txs),
    ])
    return hashlib.md5(s.encode("utf-8")).hexdigest()


_UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def _is_uuid(v):
    return isinstance(v, str) and bool(_UUID_RE.fullmatch(v))


def tag(action, ship_no, so_number, reason):
    """원장 remark — 옛 엔진(streamlit_app 11036)과 글자 단위로 같다(§18 A10)."""
    return "{} {}: {} ({})".format("출고 취소" if action == "CANCEL" else "출고 정정",
                                   ship_no, so_number or "-", reason or "-")


# ── 조회 보조 ──
def _by(rows, key):
    return {r[key]: r for r in rows}


def _round_due(r):
    return str((r or {}).get("due_date") or "")


def data_reasons(state, shipment_id, target_si, dec_by_si):
    """데이터 사유(§4-5 · §18 A2·A8) → [(코드, [근거 id])] (비면 통과). revise_shipment_check 와 공용.

    target_si: 판정 대상 전표 라인(EDIT = 바뀌는 라인, CANCEL = 수량 > 0 전 라인).
    dec_by_si: 이번 요청이 각 라인에서 줄이는 수량(recv_underflow 용, 사전 점검이면 {}).
    """
    items = _by([x for x in state["shipment_items"] if x["shipment_id"] == shipment_id], "si_id")
    allocs = state["shipment_allocations"]
    rounds = _by(state["so_delivery_schedule"], "sched_id")
    lines = _by(state["sales_order_items"], "soi_id")
    out = []
    # legacy_no_alloc: 고정 목록 + Σ충당 < 라인 수량
    bad = [si for si in target_si if si in LEGACY_NO_ALLOC_SI
           and sum(_f(a["qty"]) for a in allocs if a["si_id"] == si) < _f(items[si]["qty"]) - EPS]
    if bad:
        out.append(("legacy_no_alloc", sorted(bad)))
    # issue_mismatch: 제품 연결 라인 ISSUE 순합 ≠ −수량 / LOT 별 과복원 / 제품 불일치 / 자재 행
    bad = []
    for si in target_si:
        x = items[si]
        tx = [t for t in state["inventory_transactions"] if t.get("ref_table") == "shipment_items"
              and t.get("txn_type") == "ISSUE" and t.get("ref_id") == si]
        net = {}
        for t in tx:
            net[t.get("lot_number")] = net.get(t.get("lot_number"), 0.0) + _f(t["qty"])
        wrong = (any(t.get("product_id") != x.get("product_id") for t in tx)
                 or any(t.get("material_id") is not None for t in tx)
                 or any(v > EPS for v in net.values()))
        if x.get("product_id"):
            wrong = wrong or abs(sum(_f(t["qty"]) for t in tx) + _f(x["qty"])) > EPS
        if wrong:
            bad.append(si)
    if bad:
        out.append(("issue_mismatch", sorted(bad)))
    # round_short: 대상 라인 충당이 가리키는 회차마다 Σ(그 회차 전체 충당) > delivered
    scheds = sorted({a["sched_id"] for a in allocs if a["si_id"] in target_si})
    bad = [s for s in scheds if s in rounds and sum(_f(a["qty"]) for a in allocs if a["sched_id"] == s)
           > _f(rounds[s].get("delivered_qty")) + EPS]
    if bad:
        out.append(("round_short", bad))
    # recv_underflow: 수주 라인별 요청 전체 감소 합 > received
    need = {}
    for si, q in dec_by_si.items():
        soi = items[si].get("soi_id")
        if soi is not None:
            need[soi] = need.get(soi, 0.0) + q
    bad = [soi for soi, q in sorted(need.items())
           if soi in lines and q > _f(lines[soi].get("received_qty")) + EPS]
    if bad:
        out.append(("recv_underflow", bad))
    return out


def check(state, shipment_id):
    """revise_shipment_check 모델(§18 A9): 고정 데이터 사유만 라인별로 — {'ok', 'month_closed', 'partial_cancel_legacy',
    'lines': {si_id: [코드]}}. 요청별 사유(recv_underflow 등)는 실행 때만."""
    sh = next((s for s in state["shipments"] if s["shipment_id"] == shipment_id), None)
    if sh is None:
        return {"ok": False, "error": "not_found"}
    month = str(sh.get("ship_date") or "")[:7]
    closed = any(m.get("ym") == month for m in state.get("sales_month_close", []))
    partial = sh.get("status") == "CONFIRMED" and any(
        r.get("shipment_id") == shipment_id and r.get("action") == "CANCEL" for r in state["shipment_revisions"])
    live = [x["si_id"] for x in state["shipment_items"] if x["shipment_id"] == shipment_id and _f(x["qty"]) > EPS]
    per = {}
    for code, ids in data_reasons(state, shipment_id, live, {}):
        if code == "round_short":
            ids = sorted({a["si_id"] for a in state["shipment_allocations"] if a["sched_id"] in ids
                          and a["si_id"] in live})
        for si in ids:
            per.setdefault(si, []).append(code)
    return {"ok": True, "status": sh.get("status"), "month_closed": closed, "partial_cancel_legacy": partial,
            "lines": per}


# ── 서버 모델 ──
def plan_revision(state, request, today, now="<NOW>"):
    """082 revise_shipment 모델 → (결과, 새 state). 거부면 ({'ok': False, 'error', 'hint'}, 원래 state)."""
    st = copy.deepcopy(state)
    try:
        res = _apply(st, request, today, now)
    except Reject as e:
        return {"ok": False, "error": e.code, "hint": e.hint}, state
    return res, st


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_opt_str(v):
    return v is None or isinstance(v, str)


SHAPE = {   # 배열 원소 형식(082 0단계와 같은 규칙): 키 → 'int' | 'num' | 'str?'
    "lines": {"si_id": "int", "qty_before": "num", "qty_after": "num"},
    "expected_received_before": {"soi_id": "int", "received": "num"},
    "scheds": {"sched_id": "int", "soi_id": "int", "delta": "num"},
    "allocs": {"si_id": "int", "sched_id": "int", "qty": "num"},
    "txns": {"si_id": "int", "qty": "num", "product_id": "str?", "unit": "str?", "lot_number": "str?",
             "work_order": "str?"},
}


def shape_ok(req):
    """payload 배열 원소의 형식 — 숫자 자리에 숫자가 아니면 bad_version(SQL 이 캐스트 오류 22P02 를 내지 않게)."""
    if req.get("allow_over") is not None and not isinstance(req.get("allow_over"), bool):
        return False
    inc = req.get("inc") or {}
    if not isinstance(req.get("lines") or [], list) or not isinstance(inc, dict):
        return False
    for key, spec in SHAPE.items():
        arr = (req.get("lines") if key == "lines" else inc.get(key)) or []
        if not isinstance(arr, list):
            return False
        for e in arr:
            if not isinstance(e, dict):
                return False
            for k, kind in spec.items():
                v = e.get(k)
                ok = (_is_int(v) if kind == "int" else _is_num(v) if kind == "num" else _is_opt_str(v))
                if not ok:
                    return False
    return True


def _apply(st, req, today, now):
    # 0. 형식
    if not isinstance(req, dict) or str(req.get("v")) != "1" or req.get("action") not in ("EDIT", "CANCEL"):
        raise Reject("bad_version")
    if not shape_ok(req):
        raise Reject("bad_version", "shape")
    if not _is_uuid(req.get("request_id")):
        raise Reject("bad_version", "request_id")
    if req.get("expected_rev_no") is None or not re.fullmatch(r"-?\d+", str(req.get("expected_rev_no"))):
        raise Reject("bad_version", "expected_rev_no")
    action = req["action"]
    sid = int(req["shipment_id"])
    # ① 전표 + 재실행 판정(상태 검사보다 앞)
    sh = next((s for s in st["shipments"] if s["shipment_id"] == sid), None)
    if sh is None:
        raise Reject("not_found")
    md5 = request_md5(req)
    prev = [r for r in st["shipment_revisions"] if r.get("shipment_id") == sid
            and r.get("request_id") == str(req["request_id"])]
    if prev:
        info = prev[0].get("info") or {}
        if info.get("payload_md5") != md5:
            raise Reject("request_conflict")
        return {"ok": True, "replayed": True, "action": prev[0].get("action"), "rev_no": prev[0].get("rev_no"),
                "info": info.get("info") or []}
    # ③ 전제 검사
    if sh.get("status") != "CONFIRMED":
        raise Reject("not_confirmed:{}".format(sh.get("status")))
    if int(sh.get("rev_no") or 0) != int(req["expected_rev_no"]):
        raise Reject("stale_rev")
    reason = str(req.get("reason") or "").strip()
    if not reason:
        raise Reject("reason_required")
    if any(m.get("ym") == str(sh.get("ship_date") or "")[:7] for m in st.get("sales_month_close", [])):
        raise Reject("month_closed")
    if any(r.get("shipment_id") == sid and r.get("action") == "CANCEL" for r in st["shipment_revisions"]):
        raise Reject("partial_cancel_legacy")
    items = sorted([x for x in st["shipment_items"] if x["shipment_id"] == sid], key=lambda x: x["si_id"])
    item_by = _by(items, "si_id")
    if action == "EDIT":
        lines = req.get("lines") or []
        if not lines:
            raise Reject("nothing_to_apply")
        sis = [int(l.get("si_id")) for l in lines]
        if len(sis) != len(set(sis)) or any(s not in item_by for s in sis):
            raise Reject("line_mismatch")
        chg = {}
        for l in lines:
            si = int(l["si_id"])
            b, a = l.get("qty_before"), l.get("qty_after")
            if b is None or a is None or _f(a) < 0:
                raise Reject("line_mismatch", f"si {si}")
            if abs(_f(b) - _f(item_by[si]["qty"])) > EPS:
                raise Reject("stale_line", f"si {si}")
            if abs(_f(a) - _f(b)) <= EPS:
                raise Reject("line_mismatch", f"si {si}: no change")
            chg[si] = (_f(b), _f(a))
        live = [x["si_id"] for x in items if _f(x["qty"]) > EPS]
        if live and all(si in chg and chg[si][1] <= EPS for si in live):
            raise Reject("use_cancel")
        target = sorted(chg)
    else:
        if req.get("lines"):
            raise Reject("bad_version", "lines")
        chg = {x["si_id"]: (_f(x["qty"]), 0.0) for x in items if _f(x["qty"]) > EPS}
        target = sorted(chg)
    dec = {si: b - a for si, (b, a) in chg.items() if a < b - EPS}
    inc_q = {si: a - b for si, (b, a) in chg.items() if a > b + EPS}
    for code, ids in data_reasons(st, sid, target, dec):
        raise Reject(code, ",".join(str(i) for i in ids))
    # 증가분 형식 검사(값 검사는 감소 적용 뒤)
    inc = req.get("inc") or {}
    if inc_q:
        for si in inc_q:
            x = item_by[si]
            if x.get("soi_id") is None or not x.get("product_id"):
                raise Reject("line_unlinked", f"si {si}")
        exp = inc.get("expected_received_before") or []
        need_soi = sorted({item_by[si]["soi_id"] for si in inc_q})
        got = [int(e["soi_id"]) for e in exp]
        if sorted(got) != need_soi or len(got) != len(set(got)):
            raise Reject("bad_version", "expected_received_before")
    elif inc and any(inc.get(k) for k in ("expected_received_before", "scheds", "allocs", "txns")):
        raise Reject("bad_version", "inc without increase")

    lines_by = _by(st["sales_order_items"], "soi_id")
    hdr_by = _by(st["sales_orders"], "so_id")
    rounds = st["so_delivery_schedule"]
    recv_before = {soi: _f(lines_by[soi].get("received_qty")) for soi in lines_by}   # ② 잠금 직후 값
    ship_no = sh.get("ship_no")
    who = req.get("who")
    restored, released, info = 0, 0, []
    changed_soi = set()
    restored_by_pid = {}

    # ④ 감소분 — si 오름차순, 한 줄씩
    for si in sorted(dec):
        x, q = item_by[si], dec[si]
        soi = x.get("soi_id")
        li = lines_by.get(soi) if soi is not None else None
        if li is not None:
            hs = (hdr_by.get(li.get("so_id")) or {}).get("status")
            was_active = str(li.get("status") or "").upper() not in LINE_INACTIVE
            lf = revise_line_fields(li, _f(li.get("received_qty")) - q, hs)
            if lf.get("status") in LINE_INACTIVE and was_active and not li.get("closed_rounds"):
                lf["closed_rounds"] = [{"sched_id": r["sched_id"], "qty_before": _f(r.get("qty")),
                                        "delivered": _f(r.get("delivered_qty"))}
                                       for r in sorted((r for r in rounds if r["soi_id"] == soi),
                                                       key=lambda r: r["sched_id"])]
                lf["close_reason"] = f"출고 정정 {ship_no}"
            li.update(lf)
            changed_soi.add(soi)
            # 회차 환원: 충당 행을 회차 납기 최근순(동률 alloc_id 오름차순)으로
            rby = _by(rounds, "sched_id")
            mine = sorted((a for a in st["shipment_allocations"] if a["si_id"] == si),
                          key=lambda a: (_round_due(rby.get(a["sched_id"])), -a["alloc_id"]), reverse=True)
            left = q
            for a in mine:
                if left <= EPS:
                    break
                take = min(_f(a["qty"]), left)
                if take <= EPS:
                    continue
                r = rby[a["sched_id"]]
                r["delivered_qty"] = _f(r.get("delivered_qty")) - take
                a["qty"] = _f(a["qty"]) - take
                left -= take
                released += 1
            st["shipment_allocations"] = [a for a in st["shipment_allocations"]
                                          if a["si_id"] != si or _f(a["qty"]) > EPS]
            if left > EPS:
                info.append({"si_id": si, "kind": "unallocated", "qty": left})
            if li.get("status") in LINE_INACTIVE:                 # 닫힌 채 남는 라인: 열린 회차를 닫는다(077)
                for r in rounds:
                    if r["soi_id"] == soi and _f(r.get("qty")) > _f(r.get("delivered_qty")) + EPS:
                        r["qty"] = _f(r.get("delivered_qty"))
        # LOT 복원 — LOT 별 최초 차감 txn_id 의 역순(§18 A4)
        if x.get("product_id"):
            tx = [t for t in st["inventory_transactions"] if t.get("ref_table") == "shipment_items"
                  and t.get("txn_type") == "ISSUE" and t.get("ref_id") == si]
            left = q
            unit = (li or {}).get("unit") or x.get("unit") or "EA"
            for lot, n in reversed(net_issued_by_lot(tx)):
                if left <= EPS:
                    break
                take = min(n, left)
                _txn(st, x["product_id"], take, unit, lot, si, today,
                     tag(action, ship_no, x.get("so_number"), reason), who)
                restored += 1
                restored_by_pid[x["product_id"]] = restored_by_pid.get(x["product_id"], 0.0) + take
                left -= take

    # ⑤ 증가분 — 감소 적용 뒤 상태 기준 검증
    n_inc_alloc = n_inc_txn = 0
    if inc_q:
        exp = {int(e["soi_id"]): _f(e.get("received")) for e in inc.get("expected_received_before") or []}
        for soi, v in exp.items():
            if abs(recv_before.get(soi, -1.0) - v) > EPS:
                raise Reject("stale", f"soi {soi}")
        need = {}
        for si, q in inc_q.items():
            need[item_by[si]["soi_id"]] = need.get(item_by[si]["soi_id"], 0.0) + q
        for soi in sorted(need):
            li = lines_by[soi]
            hs = (hdr_by.get(li.get("so_id")) or {}).get("status")
            if str(li.get("status") or "").upper() in LINE_INACTIVE or str(hs or "").upper() in SO_INACTIVE_HDR:
                raise Reject("line_closed", f"soi {soi}")
            if _f(li.get("received_qty")) + need[soi] > _f(li.get("qty")) + EPS:
                raise Reject("over_pending", f"soi {soi}")
        scheds, allocs, txns = inc.get("scheds") or [], inc.get("allocs") or [], inc.get("txns") or []
        rby = _by(rounds, "sched_id")
        sum_d, sum_a = {}, {}
        for s in scheds:
            r = rby.get(int(s["sched_id"]))
            if (r is None or s.get("soi_id") is None or r["soi_id"] != int(s["soi_id"])
                    or _f(s.get("delta")) < 0 or int(s["soi_id"]) not in need):
                raise Reject("sched_mismatch")
            sum_d[r["sched_id"]] = sum_d.get(r["sched_id"], 0.0) + _f(s.get("delta"))
        tots = {soi: sum(_f(s.get("delta")) for s in scheds if int(s["soi_id"]) == soi) for soi in need}
        if any(tots[soi] > need[soi] + EPS for soi in need):
            raise Reject("sched_mismatch", "per soi")
        for soi in sorted(need):
            if tots[soi] < need[soi] - EPS:
                info.append({"soi_id": soi, "kind": "unallocated", "qty": need[soi] - tots[soi]})
        si_alloc = {}
        for a in allocs:
            si = int(a.get("si_id")) if a.get("si_id") is not None else None
            r = rby.get(int(a["sched_id"])) if a.get("sched_id") is not None else None
            if (si not in inc_q or r is None or _f(a.get("qty")) <= EPS
                    or r["soi_id"] != item_by[si]["soi_id"]):
                raise Reject("alloc_mismatch")
            sum_a[r["sched_id"]] = sum_a.get(r["sched_id"], 0.0) + _f(a["qty"])
            si_alloc[si] = si_alloc.get(si, 0.0) + _f(a["qty"])
        if any(abs(sum_d.get(k, 0.0) - sum_a.get(k, 0.0)) > EPS for k in set(sum_d) | set(sum_a)):
            raise Reject("alloc_mismatch", "per sched")
        if any(v > inc_q[si] + EPS for si, v in si_alloc.items()):
            raise Reject("alloc_mismatch", "si over qty")
        si_tx = {}
        for t in txns:
            si = int(t.get("si_id")) if t.get("si_id") is not None else None
            if si not in inc_q or _f(t.get("qty")) >= 0 or t.get("product_id") != item_by[si].get("product_id"):
                raise Reject("txn_mismatch")
            si_tx[si] = si_tx.get(si, 0.0) + _f(t["qty"])
        if any(abs(si_tx.get(si, 0.0) + q) > EPS for si, q in inc_q.items()):
            raise Reject("txn_mismatch")
        # 적용: 수주 라인 → 회차(초과 금지) → 충당 → (재고 검사) → ISSUE
        for soi in sorted(need):
            li = lines_by[soi]
            nr = _f(li.get("received_qty")) + need[soi]
            li.update({"received_qty": nr, "pending_qty": max(_f(li.get("qty")) - nr, 0.0),
                       "status": "DELIVERED" if nr >= _f(li.get("qty")) - EPS else "PARTIAL" if nr > 0 else "PENDING"})
            changed_soi.add(soi)
        for sc in sorted(sum_d):
            if sum_d[sc] <= EPS:
                continue
            r = rby[sc]
            if _f(r.get("delivered_qty")) + sum_d[sc] > _f(r.get("qty")) + EPS:
                raise Reject("sched_over", f"sched {sc}")
            r["delivered_qty"] = _f(r.get("delivered_qty")) + sum_d[sc]
        for a in allocs:
            st["shipment_allocations"].append({"alloc_id": _next(st, "shipment_allocations", "alloc_id"),
                                               "si_id": int(a["si_id"]), "sched_id": int(a["sched_id"]),
                                               "qty": _f(a["qty"])})
            n_inc_alloc += 1
        if not req.get("allow_over"):
            for pid in sorted({t["product_id"] for t in txns}):
                issue = -sum(_f(t["qty"]) for t in txns if t["product_id"] == pid)
                stock = _f(next((p.get("current_stock") for p in st.get("product_stock_v", [])
                                 if p["product_id"] == pid), 0)) + restored_by_pid.get(pid, 0.0)
                if stock + EPS < issue:
                    raise Reject(f"stock:{pid}")
        for t in txns:
            si = int(t["si_id"])
            x = item_by[si]
            rm = tag(action, ship_no, x.get("so_number"), reason)
            _txn(st, t["product_id"], _f(t["qty"]), t.get("unit") or "EA", t.get("lot_number"), si, today,
                 rm if t.get("lot_number") else rm + " (LOT 미지정)", who, work_order=t.get("work_order"))
            n_inc_txn += 1

    # ⑥ 전표 라인 수량 · ⑦ 이력
    rev = int(sh.get("rev_no") or 0) + 1
    meta = {"payload_md5": md5, "info": info}
    if action == "EDIT":
        for si in sorted(chg):
            item_by[si]["qty"] = chg[si][1]
    rows = [(si, item_by[si].get("pn"), chg[si][0], chg[si][1]) for si in sorted(chg)]
    if action == "CANCEL" and not rows:
        rows = [(None, None, 0.0, 0.0)]                       # 머리글 이력(전 라인 0 인 전표의 취소)
    for si, pn, b, a in rows:
        st["shipment_revisions"].append({
            "rev_id": _next(st, "shipment_revisions", "rev_id"), "shipment_id": sid, "rev_no": rev,
            "action": action, "si_id": si, "pn": pn, "qty_before": b, "qty_after": a, "reason": reason,
            "created_by": who, "request_id": str(req["request_id"]), "info": copy.deepcopy(meta)})
    # ⑧ 수주 머리글 — 활성 라인만, 비활성 머리글 무접촉
    so_ids = sorted({lines_by[s]["so_id"] for s in changed_soi})
    for so in so_ids:
        h = hdr_by.get(so)
        if h is None or str(h.get("status") or "").upper() in SO_INACTIVE_HDR:
            continue
        h["status"] = header_status([l for l in st["sales_order_items"] if l["so_id"] == so], h.get("status"))
    # ⑨ 전표 머리글
    sh.update({"rev_no": rev, "revised_at": now})
    if action == "CANCEL":
        sh.update({"status": "CANCELLED", "cancelled_at": now, "cancel_reason": reason})
    # ⑩ 사후 조건(§18 A1)
    _postconditions(st, sid, action, changed_soi)
    return {"ok": True, "replayed": False, "action": action, "rev_no": rev, "lines": len(chg),
            "restored_txns": restored, "released_allocs": released, "inc_allocs": n_inc_alloc,
            "inc_txns": n_inc_txn, "so_ids": so_ids, "info": info}


def _next(st, table, pk):
    return max([0] + [int(r[pk]) for r in st[table] if r.get(pk) is not None]) + 1


def _txn(st, pid, qty, unit, lot, si, today, remark, who, work_order="__lot__"):
    st["inventory_transactions"].append({
        "txn_id": _next(st, "inventory_transactions", "txn_id"), "material_id": None, "product_id": pid,
        "txn_type": "ISSUE", "qty": qty, "unit": unit, "lot_number": lot,
        "work_order": lot if work_order == "__lot__" else work_order,
        "ref_table": "shipment_items", "ref_id": si, "txn_date": today, "remark": remark, "created_by": who})


def _postconditions(st, sid, action, changed_soi):
    sis = {x["si_id"] for x in st["shipment_items"] if x["shipment_id"] == sid}
    if action == "CANCEL":
        if any(a["si_id"] in sis for a in st["shipment_allocations"]):
            raise Reject("postcondition:alloc_left")
        for si in sis:
            if abs(sum(_f(t["qty"]) for t in st["inventory_transactions"] if t.get("ref_table") == "shipment_items"
                       and t.get("txn_type") == "ISSUE" and t.get("ref_id") == si)) > EPS:
                raise Reject("postcondition:issue_left")
    lines_by = _by(st["sales_order_items"], "soi_id")
    for soi in changed_soi:
        li = lines_by[soi]
        qty, recv, st_ = _f(li.get("qty")), _f(li.get("received_qty")), str(li.get("status") or "").upper()
        if recv < -EPS:
            raise Reject("postcondition:received_negative")
        if st_ in ("CLOSED", "CANCELLED"):
            ok = _f(li.get("pending_qty")) <= EPS and abs(_f(li.get("closed_qty")) - max(qty - recv, 0)) <= EPS
        elif st_ == "REPLACED":
            ok = _f(li.get("pending_qty")) <= EPS
        else:
            ok = (abs(_f(li.get("pending_qty")) - max(qty - recv, 0)) <= EPS and _f(li.get("closed_qty")) <= EPS)
        if not ok:
            raise Reject(f"postcondition:line_state:{soi}")


# ── 화면 payload 조립 ──
def build_payload(state, shipment_id, new_qtys, reason, who, allow_over, request_id, today, action="EDIT"):
    """화면이 보낼 payload. 증가분은 확정과 같은 규칙으로 화면이 계획한다 — 감소 반영 뒤 회차 여유 기준
    (지정 회차 여유 → 납품일 회차 → 오래된 회차, allocate_rounds), LOT 선입선출(product_lot_stock_v 순서,
    부족분은 LOT 미지정). 감소 전부를 먼저 반영한 회차 상태로 계획하므로 같은 수주 라인의 증감 혼합도 실린다.
    LOT 후보에는 같은 요청의 복원량을 더한다 — 뷰 LOT 은 위치 유지, 뷰에 없던 복원 LOT 은 뒤에(LOT NULL 제외)."""
    sh = next(s for s in state["shipments"] if s["shipment_id"] == shipment_id)
    items = sorted([x for x in state["shipment_items"] if x["shipment_id"] == shipment_id],
                   key=lambda x: x["si_id"])
    req = {"v": "1", "action": action, "shipment_id": shipment_id, "request_id": str(request_id),
           "expected_rev_no": int(sh.get("rev_no") or 0), "reason": (reason or "").strip(), "who": who,
           "allow_over": bool(allow_over)}
    if action == "CANCEL":
        return req
    chg = [(x, _f(x["qty"]), _f(new_qtys[x["si_id"]])) for x in items
           if x["si_id"] in new_qtys and abs(_f(new_qtys[x["si_id"]]) - _f(x["qty"])) > EPS]
    req["lines"] = [{"si_id": x["si_id"], "qty_before": b, "qty_after": a} for x, b, a in chg]
    inc = [(x, a - b) for x, b, a in chg if a > b + EPS]
    if not inc:
        return req
    # 감소 반영 뒤 회차 상태(서버와 같은 환원 순서) + 같은 요청의 LOT 복원량
    sim = copy.deepcopy(state)
    rby = _by(sim["so_delivery_schedule"], "sched_id")
    restored = {}                                   # (pid, lot) → 복원 수량 (LOT NULL 제외)
    for x, b, a in chg:
        if a < b - EPS and x.get("product_id"):
            tx = [t for t in state["inventory_transactions"] if t.get("ref_table") == "shipment_items"
                  and t.get("txn_type") == "ISSUE" and t.get("ref_id") == x["si_id"]]
            left = b - a
            for lot, n in reversed(net_issued_by_lot(tx)):
                if left <= EPS:
                    break
                take = min(n, left)
                if lot is not None:
                    k = (x["product_id"], lot)
                    restored[k] = restored.get(k, 0.0) + take
                left -= take
    for x, b, a in chg:
        if a < b - EPS:
            left = b - a
            mine = sorted((al for al in sim["shipment_allocations"] if al["si_id"] == x["si_id"]),
                          key=lambda al: (_round_due(rby.get(al["sched_id"])), -al["alloc_id"]), reverse=True)
            for al in mine:
                if left <= EPS:
                    break
                take = min(_f(al["qty"]), left)
                rby[al["sched_id"]]["delivered_qty"] = _f(rby[al["sched_id"]].get("delivered_qty")) - take
                al["qty"] = _f(al["qty"]) - take
                left -= take
    exp, scheds, allocs, txns = {}, [], [], []
    lines_by = _by(state["sales_order_items"], "soi_id")
    ship_date = str(sh.get("ship_date") or "")[:10]
    used = {}
    # 증가 LOT 후보(검토 세션 결정 2026-11-06 15:3x): 뷰 순서(first_output_date, lot_number) 그대로, 뷰 LOT 은
    # 잔량에 같은 요청의 복원량을 더하고(위치 유지), 뷰에 없던 복원 LOT 은 뒤에 lot_number 오름차순. LOT NULL 제외
    lots = {}
    for l in sorted(state.get("product_lot_stock_v", []),
                    key=lambda l: (str(l.get("first_output_date") or ""), str(l.get("lot_number") or ""))):
        rem = _f(l.get("remain_qty")) + restored.get((l["product_id"], l.get("lot_number")), 0.0)
        if rem > EPS:
            lots.setdefault(l["product_id"], []).append({"lot_number": l["lot_number"], "remain_qty": rem})
    in_view = {(l["product_id"], l.get("lot_number")) for l in state.get("product_lot_stock_v", [])}
    for (pid, lot), q in sorted(restored.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
        if (pid, lot) not in in_view and q > EPS:
            lots.setdefault(pid, []).append({"lot_number": lot, "remain_qty": q})
    for x, d in inc:
        soi = x.get("soi_id")
        if soi is not None:
            exp[soi] = _f((lines_by.get(soi) or {}).get("received_qty"))
            rr = sorted((r for r in sim["so_delivery_schedule"] if r["soi_id"] == soi),
                        key=lambda r: (str(r.get("due_date") or ""), int(r.get("seq") or 0)))
            al, left = {}, d
            own = next((r for r in rr if r["sched_id"] == x.get("sched_id")), None)
            if own:
                tk = min(max(_f(own.get("qty")) - _f(own.get("delivered_qty")), 0), left)
                if tk > 0:
                    al[own["sched_id"]] = tk
                    own["delivered_qty"] = _f(own.get("delivered_qty")) + tk
                    left -= tk
            if left > EPS:
                prev = {r["sched_id"]: _f(r.get("delivered_qty")) for r in rr}
                for s2, v2 in allocate_rounds(rr, left, ship_date).items():
                    al[s2] = al.get(s2, 0.0) + (v2 - prev[s2])
                    rby[s2]["delivered_qty"] = v2
            for s2, dq in sorted(al.items()):
                if dq > EPS:
                    scheds.append({"sched_id": s2, "soi_id": soi, "delta": dq})
            for si2, s2, q2 in split_round_alloc([(x["si_id"], d, x.get("sched_id"))], al):
                allocs.append({"si_id": si2, "sched_id": s2, "qty": q2})
        pid = x.get("product_id")
        if pid:
            unit = (lines_by.get(soi) or {}).get("unit") or x.get("unit") or "EA"
            left = d
            for l in lots.get(pid, []):
                if left <= EPS:
                    break
                k = (pid, l["lot_number"])
                tk = min(left, max(_f(l.get("remain_qty")) - used.get(k, 0.0), 0))
                if tk <= 0:
                    continue
                used[k] = used.get(k, 0.0) + tk
                txns.append({"si_id": x["si_id"], "product_id": pid, "qty": -tk, "unit": unit,
                             "lot_number": l["lot_number"], "work_order": l["lot_number"]})
                left -= tk
            if left > EPS:
                txns.append({"si_id": x["si_id"], "product_id": pid, "qty": -left, "unit": unit,
                             "lot_number": None, "work_order": None})
    req["inc"] = {"expected_received_before": [{"soi_id": s, "received": v} for s, v in sorted(exp.items())],
                  "scheds": scheds, "allocs": allocs, "txns": txns}
    return req


# ── 호출 상태 기계(§4-6 · §18 A6) ──
import time as _time

_clock = _time.monotonic                 # 테스트가 바꿔 끼운다(10초 규칙)
NOT_APPLIED = ("40P01", "55P03", "57014")  # 교착·잠금 대기 초과·문장 시간 초과 — 함수는 롤백됨(미반영 확정)
NOT_APPLIED_RETRIES = 2
UNKNOWN_RETRIES = 1
PENDING_SEC = 10.0                       # 서버 문장 제한 8초 + 여유


class _LookupFailed:
    """requery() 가 이력을 조회하지 못했다(통신·서버 오류) — 「기록 없음」과 다르다(r1 Codex H1·QA H1).
    조회 실패는 반영 여부를 모르는 것이므로 시간이 지나도 미반영으로 확정하지 않는다."""
    __slots__ = ()

    def __bool__(self):
        return False

    def __repr__(self):
        return "LOOKUP_FAILED"


LOOKUP_FAILED = _LookupFailed()


def run_call(call, requery, sleep, clock=None, wait=2.0):
    """revise_shipment 한 번의 요청(같은 request_id)을 끝까지.

    call(): RPC 1회 — dict 반환 또는 db.RpcUnavailable / db.RpcRejected / 그 밖의 예외.
    requery(): 이력에서 같은 request_id 를 캐시 없이 찾기 → {rev_no, action, info} · None(조회 성공·없음)
      · LOOKUP_FAILED(조회 실패 — 결과는 pending, lookup_failed=True).
    반환 {"state": ok|rejected|not_applied|pending|unavailable, "res", "code", "unknown", "via", "started_at"}
      - 성공(ok) / 거부(P0001 — 쓰기 없음 확정) / 미반영 확정(자동 재시도 뒤에도) / 함수 없음
      - 불명(전송 오류·비정상 본문)이 한 번이라도 있었으면 최종 판정은 재조회로만 — 없으면 pending(확인 대기)
    """
    import db as _db
    clock = clock or _clock
    unknown = False
    n_na = n_unk = 0
    started = clock()
    while True:
        started = clock()
        try:
            r = call()
        except _db.RpcUnavailable:
            if unknown:
                break
            return {"state": "unavailable", "unknown": False, "started_at": started}
        except _db.RpcRejected as e:
            code = str(getattr(e, "code", "") or "")
            if code in NOT_APPLIED:
                if n_na < NOT_APPLIED_RETRIES:
                    n_na += 1
                    sleep(wait)
                    continue
                if unknown:
                    break
                return {"state": "not_applied", "code": code, "unknown": False, "started_at": started}
            if unknown:
                break
            return {"state": "rejected", "code": str(getattr(e, "message", "") or e), "unknown": False,
                    "started_at": started}
        except Exception:                                    # 전송 오류 — 반영 여부 불명
            unknown = True
            if n_unk < UNKNOWN_RETRIES:
                n_unk += 1
                sleep(wait)
                continue
            break
        else:
            if isinstance(r, dict) and r.get("ok") is True:
                return {"state": "ok", "res": r, "unknown": unknown, "via": "call", "started_at": started}
            unknown = True                                   # None·{}·{"ok": false}·목록 — 비정상 본문
            if n_unk < UNKNOWN_RETRIES:
                n_unk += 1
                sleep(wait)
                continue
            break
    found = requery()
    if found is not LOOKUP_FAILED and found:
        return {"state": "ok", "res": dict(found, ok=True, replayed=True), "unknown": True, "via": "requery",
                "started_at": started}
    return {"state": "pending", "unknown": True, "started_at": started, "lookup_failed": found is LOOKUP_FAILED}


def recheck(requery, started_at, now=None):
    """확인 대기 중 [결과 다시 확인]: 이력에 있으면 성공, 조회 성공·기록 없음이고 마지막 호출 시작 뒤 10초가 지났으면
    미반영 확정. 조회 실패(LOOKUP_FAILED)는 시간과 무관하게 계속 대기(기록·잠금 유지)."""
    now = _clock() if now is None else now
    found = requery()
    if found is LOOKUP_FAILED:
        return {"state": "pending", "lookup_failed": True}
    if found:
        return {"state": "ok", "res": dict(found, ok=True, replayed=True)}
    if now - float(started_at) >= PENDING_SEC:
        return {"state": "not_applied"}
    return {"state": "pending", "lookup_failed": False}


# ── 화면 문구 ──
NOTHING = "아무것도 바뀌지 않았습니다."
REASON_TEXT = {
    "legacy_no_alloc": "회차 충당 기록이 없는 옛 전표 라인",
    "issue_mismatch": "출고 재고 차감 기록이 라인 수량과 맞지 않음",
    "round_short": "납품 회차의 납품완료보다 충당 기록이 많음",
    "recv_underflow": "수주 납품량이 줄일 수량보다 적음",
}
_REJECT = {
    "bad_version": "요청 형식이 맞지 않습니다 — 화면을 새로 고친 뒤 다시 시도하세요.",
    "not_found": "전표를 찾지 못했습니다 — 화면을 새로 고치세요.",
    "not_confirmed": "이 전표는 이미 취소됐거나 확정 전표가 아닙니다 — 화면을 새로 고쳐 상태를 확인하세요.",
    "stale_rev": "다른 사용자가 먼저 이 전표를 정정·취소했습니다 — 화면을 새로 고쳐 확인한 뒤 다시 하세요.",
    "stale_line": "전표 라인 수량이 그 사이 바뀌었습니다 — 화면을 새로 고치세요.",
    "stale": "그 사이 수주 납품량이 바뀌었습니다 — 화면을 새로 고친 뒤 다시 정정하세요.",
    "request_conflict": "같은 요청 번호로 다른 내용이 들어왔습니다 — 화면을 새로 고친 뒤 다시 하세요.",
    "month_closed": "마감된 달의 전표입니다 — 정정·취소하려면 영업 보고 > 마감 조회에서 마감을 해제하세요(관리자).",
    "partial_cancel_legacy": "예전에 일부 라인만 취소된 전표입니다 — 관리자에게 알려 주세요.",
    "use_cancel": "모든 라인을 0 으로 하려면 [전표 취소] 를 쓰세요.",
    "reason_required": "사유를 입력하세요.",
    "nothing_to_apply": "바꾼 수량이 없습니다.",
    "line_mismatch": "정정 라인이 이 전표와 맞지 않습니다 — 화면을 새로 고치세요.",
    "line_unlinked": "수주 또는 제품이 연결되지 않은 라인은 수량을 늘릴 수 없습니다.",
    "line_closed": "종결·취소·대체된 수주 라인은 수량을 늘릴 수 없습니다 — 수주 목록에서 되돌린 뒤 정정하세요.",
    "over_pending": "수주 미납보다 많이 늘릴 수 없습니다.",
    "sched_mismatch": "회차 계획이 맞지 않습니다 — 화면을 새로 고친 뒤 다시 하세요.",
    "sched_over": "납품 회차 수량을 넘습니다 — 화면을 새로 고친 뒤 다시 하세요.",
    "alloc_mismatch": "회차 충당 계획이 맞지 않습니다 — 화면을 새로 고친 뒤 다시 하세요.",
    "txn_mismatch": "재고 차감 계획이 맞지 않습니다 — 화면을 새로 고친 뒤 다시 하세요.",
}


def reject_text(code):
    c = str(code or "")
    base, _, tail = c.partition(":")
    if base in REASON_TEXT:
        t = f"기록이 불완전한 라인이 있어 정정·취소할 수 없습니다 — {REASON_TEXT[base]}. 관리자에게 알려 주세요."
    elif base == "stock":
        t = f"완성 재고 부족 — {tail}. [재고 없이 증가 허용] 을 확인하거나 재고를 확인하세요."
    elif base == "postcondition":
        t = f"서버 검증에 걸려 중단했습니다({tail}) — 관리자에게 알려 주세요."
    else:
        t = _REJECT.get(base, f"정정·취소가 거부됐습니다({c}).")
    return f"{t} {NOTHING}"


NOT_APPLIED_TEXT = "다른 처리와 겹쳐 반영되지 않았습니다 — 잠시 후 다시 시도하세요."
PENDING_TEXT = ("반영 여부를 확인하지 못했습니다 — 잠시 뒤 [결과 다시 확인] 을 누르세요. "
                "확인될 때까지 모든 전표의 정정·취소를 잠급니다.")
LOOKUP_FAILED_TEXT = "정정·취소 기록을 조회하지 못했습니다(통신·서버 오류) — 잠시 뒤 다시 누르세요. 확인 대기는 그대로 둡니다."
UNAVAILABLE_TEXT = "정정·취소 기능(서버 함수)을 쓸 수 없습니다 — 관리자에게 알려 주세요. " + NOTHING


def blocked_notice(ship_no, items, lines_map, label=None):
    """revise_shipment_check 의 라인별 사유 → 안내(한 라인의 사유는 전부). label(라인) = 화면의 품번 표기
    (출하 품번 병기 line_pn) — 없으면 내부 품번."""
    by = {str(x["si_id"]): x for x in items}
    rows = []
    for si, codes in sorted((lines_map or {}).items(), key=lambda kv: int(kv[0])):
        x = by.get(str(si), {})
        rows.append("- {} · 수주 {} · {:,.0f}개: {}".format(
            (label(x) if (label and x) else x.get("pn")) or "-", x.get("so_number") or "-", _f(x.get("qty")),
            " / ".join(REASON_TEXT.get(c, c) for c in codes)))
    return ("전표 {} 의 아래 라인은 기록이 불완전해 정정·취소할 수 없습니다(아무것도 바뀌지 않았습니다).\n{}\n"
            "다른 라인의 정정은 할 수 있습니다. 필요하면 관리자에게 전표번호·원하는 결과·사유를 전달하세요."
            .format(ship_no, "\n".join(rows)))


def info_text(info, items, label=None):
    """안내(info) → 품번으로 풀어 쓴 문구(감소 = si_id, 증가 미충당 = soi_id). label = 화면의 품번 표기."""
    out = []
    for e in info or []:
        if e.get("kind") != "unallocated":
            continue
        if e.get("si_id") is not None:
            x = next((i for i in items if i.get("si_id") == e["si_id"]), {})
        else:
            x = next((i for i in items if i.get("soi_id") == e.get("soi_id")), {})
        out.append("{}: 회차에 싣지 않은 {:,.0f}개 — 납품 스케줄을 확인하세요".format(
            (label(x) if (label and x) else x.get("pn")) or "-", _f(e.get("qty"))))
    return " · ".join(out)
