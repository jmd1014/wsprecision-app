# -*- coding: utf-8 -*-
"""수주 종결·취소 전용 목 DB (2026-10-22, r2) — DashMock 의 필터 파서를 재사용한다.

- 쓰기 허용 표: sales_orders · sales_order_items · so_delivery_schedule (그 외 쓰기는 즉시 실패).
- 비교 연산(gt/lt/gte/lte)은 둘 다 숫자로 읽히면 숫자 비교. `not.in.(…)` 지원(r1 Codex M1).
- `update_fail_ids` 는 `soi_id=eq.{i}&` 정확 매칭. `order=soi_id` 정렬.
- RPC `so_close_lines` / `so_reopen_lines` 를 076 과 같은 규칙으로 구현(한 번에 반영 또는 전부 거부).
  실패 주입: `rpc_fail = (code, message, hint)` → RpcRejected, `rpc_unavailable=True`,
  `rpc_transport_fail_once=True`(첫 호출만 RpcTransportError — 반영은 됐다고 가정 = 응답 유실),
  `rpc_header_fail_once=True`(첫 close/reopen 에서 라인만 쓰고 머리글은 못 쓴 '반쪽' 상태를 흉내 — H2 복구 테스트용).
- `sales_order_stats` 뷰는 076 정의(비활성 라인 pending 0, total_closed_qty, 종결/취소 납품상태)로 즉석 계산.
"""
from datetime import date as _date

from tests.dash_mock import DashMock

WRITABLE = ("sales_orders", "sales_order_items", "so_delivery_schedule", "so_line_replacements")   # 마지막은 _rp_revert 실제 흐름용
LINE_INACTIVE = ("CLOSED", "CANCELLED", "REPLACED")


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class SOMock(DashMock):
    def __init__(self):
        super().__init__()
        self.tables.update({
            "sales_orders": [], "sales_order_items": [], "so_delivery_schedule": [],
            "shipments": [], "shipment_items": [], "products": [], "so_line_replacements": [],
            "product_stock_v": [],
        })
        self._seq.update({t: 0 for t in ("sales_orders", "sales_order_items", "so_delivery_schedule")})
        self.rpc_fail = None                 # (code, message, hint)
        self.rpc_unavailable = False
        self.rpc_transport_fail_once = False
        self.rpc_header_fail_once = False
        self.today = "2026-10-22"

    # ── 시드 ──
    def seed(self, *, so_status="DRAFT", lines=None, rounds=None, drafts=(), so_id=101, customer="(주)디아이씨두서공장",
             so_number=None, pn="4DI0622A4-5M-1", product_id="P1"):
        """lines: [(soi_id, qty, received, pending, status)] 또는 (…, status, closed_qty),
        rounds: [(sched_id, soi_id, qty, delivered)], drafts: [(shipment_id, ship_no, status, [soi_id,...])]"""
        self.tables["sales_orders"].append({
            "so_id": so_id, "so_number": so_number or f"PO-{so_id}", "customer": customer,
            "so_date": "2026-10-01", "due_date": None, "status": so_status, "total_amount": 1000,
            "remark": None, "created_by": "테스트"})
        for i, l in enumerate(lines or [], 1):
            sid, q, r, p, st = l[:5]
            cq = l[5] if len(l) > 5 else 0
            self.tables["sales_order_items"].append({
                "soi_id": sid, "so_id": so_id, "line_no": i, "customer_part_no": f"CP-{sid}",
                "customer_item_name": None, "product_id": product_id, "canonical_pn": pn,
                "qty": q, "received_qty": r, "pending_qty": p, "unit_price": 100, "amount": q * 100,
                "due_date": "2026-10-20", "status": st, "remark": None, "price_kind": None,
                "closed_qty": cq, "close_reason": None, "closed_rounds": None, "presched_qty": 0, "unit": "EA"})
        for sc, soi, q, d in (rounds or []):
            self.tables["so_delivery_schedule"].append({
                "sched_id": sc, "so_id": so_id, "soi_id": soi, "due_date": "2026-10-20", "seq": 1, "qty": q,
                "delivered_qty": d, "note": None})
        for sh, no, st, sois in drafts:
            self.tables["shipments"].append({"shipment_id": sh, "ship_no": no, "ship_date": "2026-10-21", "status": st})
            for k, soi in enumerate(sois):
                self.tables["shipment_items"].append({"si_id": 1000 + sh * 10 + k, "shipment_id": sh, "soi_id": soi,
                                                      "so_id": so_id, "qty": 1})
        if not any(p["product_id"] == product_id for p in self.tables["products"]):
            self.tables["products"].append({"product_id": product_id, "pn": pn, "archived_at": None,
                                            "archive_reason": None, "sale_price": 100, "customer": customer,
                                            "item_name": "BUSHING", "material": "SCM415"})
            self.tables["product_stock_v"].append({"product_id": product_id, "pn": pn, "customer": customer,
                                                   "current_stock": 10, "last_txn_date": "2026-10-20"})
        return self

    # ── 필터: 숫자 비교 + not.in ──
    @staticmethod
    def _match(row, conds):
        for col, op, val in conds:
            cur = row.get(col)
            if op == "not":
                sub, _, v2 = val.partition(".")
                if sub == "in":
                    vals = [x.strip().strip('"') for x in v2.strip("()").split(",")]
                    if ("" if cur is None else str(cur)) in vals:
                        return False
                    continue
                if sub == "is":
                    if (v2 == "null") == (cur is None):
                        return False
                    continue
                raise AssertionError(f"so_mock: 지원하지 않는 연산자 not.{sub}")
            a, b = _num(cur), _num(val)
            if op == "eq" and a is not None and b is not None and val not in ("true", "false"):
                if abs(a - b) > 1e-9:
                    return False
                continue
            if op in ("gt", "lt", "gte", "lte") and a is not None and b is not None:
                if op == "gt" and not a > b:
                    return False
                if op == "lt" and not a < b:
                    return False
                if op == "gte" and not a >= b:
                    return False
                if op == "lte" and not a <= b:
                    return False
                continue
            if not DashMock._match(row, [(col, op, val)]):
                return False
        return True

    def _rows(self, table, filter_query):
        out = super()._rows(table, filter_query)
        if out is not None and "order=soi_id" in (filter_query or ""):
            out.sort(key=lambda r: int(r.get("soi_id") or 0))
        return out

    def update_count(self, table, filter_query, fields, select="*"):
        if any(f"soi_id=eq.{i}&" in filter_query + "&" for i in self.update_fail_ids):
            self._assert_dash("update", table)
            return -1
        saved, self.update_fail_ids = self.update_fail_ids, set()
        try:
            return super().update_count(table, filter_query, fields, select)
        finally:
            self.update_fail_ids = saved

    # ── 뷰 ──
    def stats_rows(self):
        rows = []
        for so in self.tables["sales_orders"]:
            its = [i for i in self.tables["sales_order_items"] if i["so_id"] == so["so_id"]]
            rcv = sum(float(i.get("received_qty") or 0) for i in its)
            pend = sum(0 if str(i.get("status") or "").upper() in LINE_INACTIVE else float(i.get("pending_qty") or 0)
                       for i in its)
            closed = sum(float(i.get("closed_qty") or 0) for i in its)
            ds = ("종결" if so["status"] == "CLOSED" else "취소" if so["status"] == "CANCELLED"
                  else "미납" if rcv == 0 else "완납" if pend == 0 else "부분납")
            rows.append({**so, "item_count": len(its), "total_qty": sum(float(i["qty"]) for i in its),
                         "total_received_qty": rcv, "total_pending_qty": pend, "delivery_status": ds,
                         "match_rate_pct": 100.0, "total_closed_qty": closed})
        return rows

    def fetch(self, table, select="*", filter_query="", limit=1000, cache=None):
        if table == "sales_order_stats":
            self.fetch_calls.append((table, filter_query or ""))
            conds = self._parse(filter_query)
            return [dict(r) for r in self.stats_rows() if self._match(r, conds)][:limit]
        return super().fetch(table, select, filter_query, limit, cache)

    # ── 쓰기 범위 ──
    def _assert_dash(self, op, table):
        if table not in WRITABLE:
            raise AssertionError(f"so_mock: 허용되지 않은 쓰기 ({op} {table})")

    # ── RPC (076 규칙) ──
    def rpc(self, name, params=None, timeout=None):
        import db as _db
        self.rpc_calls.append((name, dict(params or {})))
        if name not in ("so_close_lines", "so_reopen_lines"):
            raise AssertionError(f"so_mock: 미등록 RPC {name}")
        if self.rpc_unavailable:
            raise _db.RpcUnavailable(f"{name}: PGRST202")
        if self.rpc_fail:
            code, msg, hint = self.rpc_fail
            raise _db.RpcRejected(code, msg, 400, hint=hint)
        out = self._close(params) if name == "so_close_lines" else self._reopen(params)
        if self.rpc_transport_fail_once:
            self.rpc_transport_fail_once = False          # 반영은 됐고 응답만 잃음
            raise _db.RpcTransportError(f"{name}: timeout")
        return out

    def _hdr(self, so_id):
        return next((s for s in self.tables["sales_orders"] if int(s["so_id"]) == int(so_id)), None)

    def _lines_of(self, so_id):
        return sorted([l for l in self.tables["sales_order_items"] if int(l["so_id"]) == int(so_id)],
                      key=lambda l: int(l["soi_id"]))

    @staticmethod
    def _tag_append(old, tag):
        return tag if not (old or "").strip() else f"{old} · {tag}"

    def _close(self, p):
        import db as _db
        so_id, mode, reason, who = int(p["p_so_id"]), p.get("p_mode"), (p.get("p_reason") or "").strip(), p.get("p_who") or "-"
        if mode not in ("CLOSED", "CANCELLED") or not reason:
            raise _db.RpcRejected("P0001", "bad_args", 400, hint="mode CLOSED|CANCELLED, reason required")
        hdr = self._hdr(so_id)
        if hdr is None:
            raise _db.RpcRejected("P0001", "not_found", 400)
        lines = self._lines_of(so_id)
        open_ids = {l["soi_id"] for l in lines if float(l.get("pending_qty") or 0) > 0}
        drafts = sorted({s["ship_no"] for si in self.tables["shipment_items"] if si["soi_id"] in open_ids
                         for s in self.tables["shipments"] if s["shipment_id"] == si["shipment_id"] and s["status"] == "DRAFT"})
        if drafts:
            raise _db.RpcRejected("P0001", "blocked", 400, hint=", ".join(drafts))
        ko = "종결" if mode == "CLOSED" else "취소"
        tag = f"{ko}({reason}) {self.today} {who}"
        closed = rounds = 0
        for l in lines:
            if float(l.get("pending_qty") or 0) <= 0 or str(l.get("status") or "").upper() in LINE_INACTIVE:
                continue
            rs_all = [r for r in self.tables["so_delivery_schedule"] if r["soi_id"] == l["soi_id"]]
            rs = [r for r in rs_all if float(r.get("qty") or 0) > float(r.get("delivered_qty") or 0) + 1e-9]
            # 077(D17): 전 회차 보존 — 완납 회차도 qty_before 를 남긴다(종결 중 과거 출고 취소 뒤 복원용)
            l["closed_rounds"] = [{"sched_id": r["sched_id"], "qty_before": float(r["qty"]),
                                   "delivered": float(r.get("delivered_qty") or 0)} for r in sorted(rs_all, key=lambda r: r["sched_id"])]
            l.update({"closed_qty": float(l["pending_qty"]), "pending_qty": 0, "status": mode, "close_reason": reason,
                      "remark": self._tag_append(l.get("remark"), tag)})
            self.writes.append(("rpc_update", "sales_order_items", {"soi_id": l["soi_id"], "status": mode}))
            for r in rs:
                r["qty"] = float(r.get("delivered_qty") or 0)
                self.writes.append(("rpc_update", "so_delivery_schedule", {"sched_id": r["sched_id"], "qty": r["qty"]}))
                rounds += 1
            closed += 1
        active_pend = sum(float(l.get("pending_qty") or 0) for l in lines if str(l.get("status") or "").upper() not in LINE_INACTIVE)
        has_closed = any(str(l.get("status") or "").upper() in ("CLOSED", "CANCELLED") for l in lines)
        mode_mix = any(str(l.get("status") or "").upper() in ("CLOSED", "CANCELLED") and str(l.get("status") or "").upper() != mode
                       for l in lines)
        if closed == 0 and has_closed and hdr["status"] not in ("CLOSED", "CANCELLED") and mode_mix:
            raise _db.RpcRejected("P0001", "bad_args", 400, hint="mode mismatch: closed lines have another mode")
        header = False
        if active_pend <= 1e-9 and (closed > 0 or (has_closed and hdr["status"] not in ("CLOSED", "CANCELLED"))):
            if self.rpc_header_fail_once:
                self.rpc_header_fail_once = False          # 반쪽 상태 흉내(운영에선 트랜잭션이라 불가능, 복구 경로 검증용)
            else:
                hdr["status"], hdr["remark"] = mode, self._tag_append(hdr.get("remark"), tag)
                self.writes.append(("rpc_update", "sales_orders", {"so_id": so_id, "status": mode}))
                header = True
        return {"closed": closed, "rounds": rounds, "header": header, "header_status": hdr["status"]}

    def _reopen(self, p):
        import db as _db
        so_id, who = int(p["p_so_id"]), p.get("p_who") or "-"
        hdr = self._hdr(so_id)
        if hdr is None:
            raise _db.RpcRejected("P0001", "not_found", 400)
        tag = f"되돌림 {self.today} {who}"
        lines = self._lines_of(so_id)
        n = restored = skipped = 0
        for l in lines:
            if float(l.get("closed_qty") or 0) <= 0 or str(l.get("status") or "").upper() not in ("CLOSED", "CANCELLED"):
                continue
            l.update({"pending_qty": float(l["closed_qty"]), "closed_qty": 0,
                      "status": "PARTIAL" if float(l.get("received_qty") or 0) > 0 else "PENDING",
                      "close_reason": None, "remark": self._tag_append(l.get("remark"), tag)})
            for cr in (l.get("closed_rounds") or []):
                r = next((x for x in self.tables["so_delivery_schedule"] if x["sched_id"] == cr["sched_id"] and x["soi_id"] == l["soi_id"]), None)
                if r is not None and abs(float(r.get("qty") or 0) - float(r.get("delivered_qty") or 0)) <= 1e-9:
                    r["qty"] = max(float(cr["qty_before"]), float(r.get("delivered_qty") or 0))   # 아직 닫힌 회차만 (QA H-2)
                    restored += 1
                else:
                    skipped += 1
            l["closed_rounds"] = None
            self.writes.append(("rpc_update", "sales_order_items", {"soi_id": l["soi_id"], "status": l["status"]}))
            n += 1
        header = None
        left = any(float(l.get("closed_qty") or 0) > 0 for l in lines)
        active_open = any(str(l.get("status") or "").upper() not in LINE_INACTIVE and float(l.get("pending_qty") or 0) > 0
                          for l in lines)
        if n > 0 or (hdr["status"] in ("CLOSED", "CANCELLED") and not left and active_open):   # 거울상 = 불변식 ③ 위반만 (QA H-1)
            act = [l for l in lines if str(l.get("status") or "").upper() not in LINE_INACTIVE]
            if not act:
                new = hdr["status"]
            elif all(float(l.get("received_qty") or 0) >= float(l["qty"]) for l in act):
                new = "DELIVERED"
            elif any(float(l.get("received_qty") or 0) > 0 for l in act):
                new = "PARTIAL"
            else:
                new = "DRAFT"
            if self.rpc_header_fail_once:
                self.rpc_header_fail_once = False
            else:
                if new != hdr["status"] or n > 0:
                    hdr["status"] = new
                    if n > 0:
                        hdr["remark"] = self._tag_append(hdr.get("remark"), tag)
                    self.writes.append(("rpc_update", "sales_orders", {"so_id": so_id, "status": new}))
                header = new
        return {"reopened": n, "rounds_restored": restored, "rounds_skipped": skipped, "header": header,
                "header_status": hdr["status"]}

    # ── 조회 보조 ──
    def line(self, soi_id):
        return next(l for l in self.tables["sales_order_items"] if l["soi_id"] == soi_id)

    def header(self, so_id=101):
        return self._hdr(so_id)

    def round(self, sched_id):
        return next(r for r in self.tables["so_delivery_schedule"] if r["sched_id"] == sched_id)

    def stats(self, so_id=101):
        return next(r for r in self.stats_rows() if r["so_id"] == so_id)
