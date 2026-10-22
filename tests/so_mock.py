# -*- coding: utf-8 -*-
"""수주 종결·취소 전용 목 DB (2026-10-22) — DashMock 의 필터 파서를 재사용한다.

- 쓰기 허용 표: sales_orders · sales_order_items · so_delivery_schedule (그 외 쓰기는 즉시 실패).
- 비교 연산(gt/lt/gte/lte)은 둘 다 숫자로 읽히면 숫자 비교(`pending_qty=gt.0` 가 "0.0" 에 걸리지 않게).
- `sales_order_stats` 뷰는 sales_orders + sales_order_items 로 즉석 계산한다(006 정의와 같은 열).
"""
from tests.dash_mock import DashMock

WRITABLE = ("sales_orders", "sales_order_items", "so_delivery_schedule")


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
        })
        self._seq.update({t: 0 for t in ("sales_orders", "sales_order_items", "so_delivery_schedule")})

    # ── 시드 ──
    def seed(self, *, so_status="DRAFT", lines=None, rounds=None, drafts=(), so_id=101):
        """lines: [(soi_id, qty, received, pending, status)], rounds: [(sched_id, soi_id, qty, delivered)],
        drafts: [(shipment_id, ship_no, status, [soi_id,...])]"""
        self.tables["sales_orders"] = [{
            "so_id": so_id, "so_number": f"PO-{so_id}", "customer": "(주)디아이씨두서공장",
            "so_date": "2026-10-01", "due_date": None, "status": so_status, "total_amount": 1000,
            "remark": None, "created_by": "테스트"}]
        self.tables["sales_order_items"] = [{
            "soi_id": sid, "so_id": so_id, "line_no": i, "customer_part_no": f"CP-{sid}",
            "customer_item_name": None, "product_id": "P1", "canonical_pn": "4DI0622A4-5M-1",
            "qty": q, "received_qty": r, "pending_qty": p, "unit_price": 100, "amount": q * 100,
            "due_date": "2026-10-20", "status": st, "remark": None, "price_kind": None,
            "closed_qty": 0, "close_reason": None, "presched_qty": 0}
            for i, (sid, q, r, p, st) in enumerate(lines or [], 1)]
        self.tables["so_delivery_schedule"] = [{
            "sched_id": sc, "soi_id": soi, "due_date": "2026-10-20", "seq": 1, "qty": q,
            "delivered_qty": d, "note": None} for sc, soi, q, d in (rounds or [])]
        self.tables["shipments"] = [{"shipment_id": sh, "ship_no": no, "ship_date": "2026-10-21",
                                     "status": st} for sh, no, st, _ in drafts]
        self.tables["shipment_items"] = [{"si_id": 1000 + sh * 10 + k, "shipment_id": sh, "soi_id": soi,
                                          "so_id": so_id, "qty": 1}
                                         for sh, _, _, sois in drafts for k, soi in enumerate(sois)]
        self.tables["products"] = [{"product_id": "P1", "pn": "4DI0622A4-5M-1", "archived_at": None,
                                    "archive_reason": None, "sale_price": 100,
                                    "customer": "(주)디아이씨두서공장", "item_name": "BUSHING", "material": "SCM415"}]
        return self

    # ── 필터: 숫자 비교 ──
    @staticmethod
    def _match(row, conds):
        for col, op, val in conds:
            cur = row.get(col)
            a, b = _num(cur), _num(val)
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

    # ── 뷰 ──
    def fetch(self, table, select="*", filter_query="", limit=1000, cache=None):
        if table == "sales_order_stats":
            rows = []
            for so in self.tables["sales_orders"]:
                its = [i for i in self.tables["sales_order_items"] if i["so_id"] == so["so_id"]]
                rcv = sum(float(i.get("received_qty") or 0) for i in its)
                pend = sum(max(float(i.get("qty") or 0) - float(i.get("received_qty") or 0), 0) for i in its)
                rows.append({**so, "item_count": len(its), "total_qty": sum(float(i["qty"]) for i in its),
                             "total_received_qty": rcv, "total_pending_qty": pend,
                             "delivery_status": "미납" if rcv == 0 else ("완납" if pend == 0 else "부분납"),
                             "match_rate_pct": 100.0})
            conds = self._parse(filter_query)
            self.fetch_calls.append((table, filter_query or ""))
            return [dict(r) for r in rows if self._match(r, conds)][:limit]
        return super().fetch(table, select, filter_query, limit, cache)

    # ── 쓰기 범위 ──
    def _assert_dash(self, op, table):
        if table not in WRITABLE:
            raise AssertionError(f"so_mock: 허용되지 않은 쓰기 ({op} {table})")

    def rpc(self, name, params=None, timeout=None):
        raise AssertionError(f"so_mock: RPC 호출 없음이어야 함 ({name})")

    # ── 조회 보조 ──
    def line(self, soi_id):
        return next(l for l in self.tables["sales_order_items"] if l["soi_id"] == soi_id)

    def header(self, so_id=101):
        return next(s for s in self.tables["sales_orders"] if s["so_id"] == so_id)

    def round(self, sched_id):
        return next(r for r in self.tables["so_delivery_schedule"] if r["sched_id"] == sched_id)
