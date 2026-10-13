"""소재 식별 번호(W LOT) 채번 — w_lot_next / w_lot_max_used (migration 068, 2026-10-13).

RPC next_w_lot 우선, 없거나 불명이면 기존 로직(max(카운터, 원장 최대) + 1 →
카운터 갱신). 순수 함수 부분만 exec 로 떼어 db 모듈을 대역으로 검증한다
(test_wo_number_auto.py 와 같은 방식).
"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class _RpcRejected(Exception):
    """db.RpcRejected 와 같은 시그니처 — code/message 속성."""

    def __init__(self, code, message, status=400):
        super().__init__(f"{code}: {message}")
        self.code, self.message, self.status = code, message, status


class _FakeDb(types.ModuleType):
    """db 대역 — rpc 결과·카운터·원장 LOT 목록·update 기록·조회 기록."""

    RpcRejected = _RpcRejected

    class RpcUnavailable(Exception):
        pass

    class RpcTransportError(Exception):
        pass

    def __init__(self, counter="0904", ledger=("W0905",), rpc_result=None,
                 rpc_exc=None, has_rpc=True):
        super().__init__("db")
        self.counter, self.ledger = counter, list(ledger)
        self.rpc_result, self.rpc_exc = rpc_result, rpc_exc
        self.updates, self.rpc_calls, self.fetches = [], [], []
        if not has_rpc:
            # 기존 AppTest 목처럼 rpc 속성 자체가 없는 모듈
            self.__class__ = _FakeDbNoRpc

    def rpc(self, name, params=None, **kw):
        self.rpc_calls.append((name, params))
        if self.rpc_exc:
            raise self.rpc_exc
        return self.rpc_result

    def fetch_one(self, table, fq, select="*"):
        self.fetches.append((table, fq))
        assert table == "app_settings" and "w_lot_counter" in fq
        return {"value": self.counter} if self.counter is not None else None

    def fetch(self, table, select="*", fq="", limit=1000, **kw):
        self.fetches.append((table, fq, limit))
        assert table == "inventory_transactions"
        return [{"lot_number": x} for x in self.ledger[:limit]]

    def update(self, table, fq, fields):
        self.updates.append((table, fq, fields))
        return True


class _FakeDbNoRpc(_FakeDb):
    @property
    def rpc(self):
        raise AttributeError("module 'db' has no attribute 'rpc'")


def _load(fake):
    src = open(os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "streamlit_app.py"), encoding="utf-8").read()
    i = src.index("def w_lot_max_used")
    j = src.index("def w_lot_sync_counter")
    ns = {}
    saved = sys.modules.get("db")
    sys.modules["db"] = fake
    try:
        exec(src[i:j], ns)
        return ns
    finally:
        if saved is not None:
            sys.modules["db"] = saved
        else:
            sys.modules.pop("db", None)


def _run(fake, count=1, fn="w_lot_next"):
    """exec 된 함수는 호출 시점에 `import db` 를 하므로 호출 동안 대역을 꽂는다."""
    ns = _load(fake)
    saved = sys.modules.get("db")
    sys.modules["db"] = fake
    try:
        return ns[fn](count) if fn == "w_lot_next" else ns[fn]()
    finally:
        if saved is not None:
            sys.modules["db"] = saved
        else:
            sys.modules.pop("db", None)


# ─── T-B1 폴백(기존 로직) 고정 — rpc 가 None 을 돌려주는 테스트 목 상태 ───
def test_fallback_counter_behind_ledger():
    f = _FakeDb(counter="0904", ledger=["W0905"])
    assert _run(f) == ["W0906"]
    assert f.updates == [("app_settings", "key=eq.w_lot_counter", {"value": "906"})]


def test_fallback_counter_ahead_of_ledger():
    f = _FakeDb(counter="0910", ledger=["W0905"])
    assert _run(f) == ["W0911"]
    assert f.updates[-1][2] == {"value": "911"}


def test_fallback_counter_unset_or_invalid():
    assert _run(_FakeDb(counter=None)) is None
    f = _FakeDb(counter="abc")
    assert _run(f) is None
    assert f.updates == []


def test_fallback_count_zero_and_batch():
    f = _FakeDb(counter="0905", ledger=[])
    assert _run(f, 0) == []
    assert f.updates == [] and f.rpc_calls == []
    assert _run(f, 3) == ["W0906", "W0907", "W0908"]
    assert f.updates[-1][2] == {"value": "908"}


def test_fallback_parser_ignores_other_w_formats():
    """'W2608-001' 같은 다른 형식은 무시 — 종전엔 숫자만 이어붙여 2608001 로 오판."""
    f = _FakeDb(counter="0904", ledger=["W2608-001", "W0905", "W-TEST"])
    assert _run(f) == ["W0906"]


def test_fallback_parser_queries_recent_receipts_under_trunc_limit():
    """입고(RECEIPT) 행을 최근 거래순으로, 조회 절단 경고 임계(200) 미만으로 본다 —
    문자열 정렬에서 W10000 이 W1001 뒤로 밀리던 문제 (2026-10-13 Data 리뷰 H-2·M-2)."""
    f = _FakeDb(counter="0904", ledger=["W10000", "W9999"])
    assert _run(f, fn="w_lot_max_used") == 10000
    table, fq, limit = f.fetches[-1]
    assert "txn_type=eq.RECEIPT" in fq and "order=txn_id.desc" in fq
    assert limit < 200


def test_fallback_without_rpc_attribute():
    """기존 AppTest 목처럼 db 에 rpc 가 없어도 기존 로직으로 간다."""
    f = _FakeDb(counter="0904", ledger=["W0905"], has_rpc=False)
    assert _run(f) == ["W0906"]


# ─── T-B2 RPC 경로 ───
def test_rpc_result_is_used_without_counter_update_or_reads():
    f = _FakeDb(counter="0904", ledger=["W0905"], rpc_result=["W1170"])
    assert _run(f) == ["W1170"]
    assert f.updates == [], "카운터 갱신은 DB 함수 안에서 끝난다"
    assert f.fetches == [], "RPC 성공이면 카운터·원장을 읽지 않는다"
    assert f.rpc_calls == [("next_w_lot", {"p_count": 1})]


def test_rpc_batch_success_and_length_mismatch():
    f = _FakeDb(counter="0904", ledger=["W0905"], rpc_result=["W1170", "W1171"])
    assert _run(f, 2) == ["W1170", "W1171"]
    f = _FakeDb(counter="0904", ledger=["W0905"], rpc_result=["W1170"])
    assert _run(f, 2) == ["W0906", "W0907"], "길이가 다르면 폴백"


def test_rpc_unavailable_or_transport_falls_back():
    for exc in (_FakeDb.RpcUnavailable("no fn"), _FakeDb.RpcTransportError("t"),
                RuntimeError("other")):
        f = _FakeDb(counter="0904", ledger=["W0905"], rpc_exc=exc)
        assert _run(f) == ["W0906"]


def test_rpc_counter_unset_returns_none_without_fallback():
    f = _FakeDb(counter="0904", ledger=["W0905"],
                rpc_exc=_RpcRejected("P0001", "w_lot_counter_unset"))
    assert _run(f) is None
    assert f.updates == [] and f.fetches == []


def test_rpc_other_rejection_falls_back():
    f = _FakeDb(counter="0904", ledger=["W0905"],
                rpc_exc=_RpcRejected("P0001", "w_lot_count_too_large"))
    assert _run(f) == ["W0906"]
