# -*- coding: utf-8 -*-
"""확정 출고 전표 정정·취소 시험용 상태 목 DB (2026-11-06 P3-1a).

SOMock(DashMock 필터 파서 — eq·in·is·gt·like·not, 숫자 비교, order= 정렬)을 확장해 출고 쪽 표를 상태로 갖는다.
- 쓰기 허용: 출고 정정·취소가 건드리는 8개 표(+ shipment_revisions). insert 는 표별 PK 를 발급, delete 는 실제로 지운다.
- 읽기 뷰 `product_stock_v`·`product_lot_stock_v` 는 시드 그대로(정정 엔진은 읽기만 한다).
- `snapshot()` 은 비교용 상태(표별 PK 정렬) — 골든 파일의 before·after.
"""
import copy

from tests.so_mock import SOMock

TABLES = ("shipments", "shipment_items", "shipment_allocations", "inventory_transactions", "shipment_revisions",
          "sales_order_items", "sales_orders", "so_delivery_schedule", "products", "product_stock_v",
          "product_lot_stock_v", "sales_month_close")
WRITABLE_SHIP = ("shipments", "shipment_items", "shipment_allocations", "inventory_transactions",
                 "shipment_revisions", "sales_order_items", "sales_orders", "so_delivery_schedule")
PK = {"shipments": "shipment_id", "shipment_items": "si_id", "shipment_allocations": "alloc_id",
      "inventory_transactions": "txn_id", "shipment_revisions": "rev_id", "sales_order_items": "soi_id",
      "sales_orders": "so_id", "so_delivery_schedule": "sched_id", "products": "product_id",
      "product_stock_v": "product_id", "product_lot_stock_v": "lot_number", "sales_month_close": "ym"}
SNAP_TABLES = ("shipments", "shipment_items", "shipment_allocations", "inventory_transactions",
               "shipment_revisions", "sales_order_items", "sales_orders", "so_delivery_schedule")


class ShipMock(SOMock):
    def __init__(self, world=None):
        super().__init__()
        self.sort_orders = True
        for t in TABLES:
            self.tables[t] = []
        for t, rows in (world or {}).items():
            self.tables[t] = [dict(r) for r in rows]
        self._seq = {t: max([0] + [int(r[PK[t]]) for r in self.tables.get(t, [])
                                   if isinstance(r.get(PK[t]), int)])
                     for t in PK}

    # ── 쓰기 범위 ──
    def _assert_dash(self, op, table):
        if table not in WRITABLE_SHIP:
            raise AssertionError(f"ship_mock: 허용되지 않은 쓰기 ({op} {table})")

    def insert(self, table, records):
        self._assert_dash("insert", table)
        if self.insert_raise_for == table:
            raise RuntimeError(f"insert {table} 실패 (시뮬레이션)")
        pk = PK.get(table)
        for r in records:
            row = dict(r)
            if pk and row.get(pk) is None:
                self._seq[table] = self._seq.get(table, 0) + 1
                row[pk] = self._seq[table]
            self.tables[table].append(row)
            self.writes.append(("insert", table, dict(row)))
        return len(records)

    def delete(self, table, filter_query):
        self._assert_dash("delete", table)
        rows = self._rows(table, filter_query)
        ids = {id(r) for r in rows}
        self.tables[table] = [r for r in self.tables[table] if id(r) not in ids]
        self.writes.append(("delete", table, {"filter": filter_query, "n": len(rows)}))
        return len(rows)

    def update_count(self, table, filter_query, fields, select="*"):
        self._assert_dash("update", table)
        if not filter_query:
            raise ValueError("update_count: filter_query 필수")
        rows = self._rows(table, filter_query)
        for r in rows:
            r.update(copy.deepcopy(fields))
        self.writes.append(("update", table, {"filter": filter_query, "n": len(rows), **copy.deepcopy(fields)}))
        return len(rows)

    def update(self, table, filter_query, fields):
        return self.update_count(table, filter_query, fields) >= 0

    def rpc(self, name, params=None, timeout=None):
        self.rpc_calls.append((name, dict(params or {})))
        raise AssertionError(f"ship_mock: 미등록 RPC {name}")

    # ── 비교용 ──
    def state(self):
        return {t: copy.deepcopy(self.tables.get(t, [])) for t in TABLES}

    def snapshot(self, tables=SNAP_TABLES):
        out = {}
        for t in tables:
            pk = PK[t]
            out[t] = sorted((copy.deepcopy(r) for r in self.tables.get(t, [])),
                            key=lambda r, pk=pk: (str(type(r.get(pk))), r.get(pk) if r.get(pk) is not None else 0))
        return out


class ReviseMock(ShipMock):
    """082 revise_shipment·revise_shipment_check 의 가짜 RPC — 파이썬 모델(plan_revision)을 목의 상태에 적용한다.

    faults: 호출마다 하나씩 소비 —
      "transport_after"  반영한 뒤 응답 유실(RpcTransportError)
      "transport_before" 반영 없이 응답 유실
      "na:<code>"        미반영 확정(RpcRejected 40P01·55P03·57014)
      "abnormal"         반영 없이 비정상 본문({})
      "unavailable"      함수 없음(RpcUnavailable)
      "hold"             계산은 하되 커밋 보류(응답 유실) — commit_held() 로 나중에 반영(지연 커밋)
    check_fail: revise_shipment_check 가 예외(조회 실패) / check_unavailable: 함수 없음.
    """

    def __init__(self, world=None):
        super().__init__(world)
        self.faults = []
        self.check_fail = False
        self.check_unavailable = False
        self.held = None
        self.applied = 0

    def _today(self):
        import datetime as _dt
        return (_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(hours=9)).date().isoformat()

    def _set_state(self, st):
        for t in WRITABLE_SHIP:
            if t in st:
                self.tables[t] = st[t]

    def commit_held(self):
        st, self.held = self.held, None
        self._set_state(st)
        self.applied += 1

    def rpc(self, name, params=None, timeout=None):
        import db as _db
        from utils.shipment_revise import plan_revision, check
        self.rpc_calls.append((name, copy.deepcopy(dict(params or {}))))
        p = dict(params or {})
        if name == "revise_shipment_check":
            if self.check_unavailable:
                raise _db.RpcUnavailable(name)
            if self.check_fail:
                raise _db.RpcTransportError(f"{name}: timeout")
            r = check(self.state(), p["p_shipment_id"])
            if r.get("ok"):
                r["lines"] = {str(k): v for k, v in r["lines"].items()}
            return r
        if name != "revise_shipment":
            raise AssertionError(f"ReviseMock: 미등록 RPC {name}")
        fault = self.faults.pop(0) if self.faults else None
        if fault == "unavailable":
            raise _db.RpcUnavailable(name)
        if fault and fault.startswith("na:"):
            raise _db.RpcRejected(fault[3:], "canceling statement due to lock timeout", 500)
        if fault in ("transport_before", "abnormal"):
            if fault == "abnormal":
                return {}
            raise _db.RpcTransportError(f"{name}: ReadTimeout")
        req = dict(p["p_payload"], shipment_id=p["p_shipment_id"])
        res, st = plan_revision(self.state(), req, self._today(), now="2026-11-06T07:00:00+00:00")
        if not res.get("ok"):
            raise _db.RpcRejected("P0001", res["error"], 400, hint=str(res.get("hint") or ""))
        if fault == "hold":
            self.held = st
            raise _db.RpcTransportError(f"{name}: ReadTimeout")
        if not res.get("replayed"):
            self._set_state(st)
            self.applied += 1
        if fault == "transport_after":
            raise _db.RpcTransportError(f"{name}: ReadTimeout")
        return res
