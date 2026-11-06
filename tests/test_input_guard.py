# -*- coding: utf-8 -*-
"""투입 등록(공정 관리 → 투입 등록) 품번 후보 화면 AppTest (2026-11-06 재발 방지 소묶음 A).

운영 사례(2026-11-06 검토 세션 읽기 전용 확인): 소재 LOT W1257(M191, 잔여 800)의 입고 → 발주 라인 poi 325 →
HA80-80092(P0738, 휴면 — 설계변경 HA80-80093). 같은 소재의 활성 BOM 품번은 HA80-80093(P0883).

목: SOMock + select 한 열만 돌려준다(apply_select) — `products` 조회가 archived_at 을 select 하지 않으면 그 값을
못 읽는다(핫픽스 1 교훈: 열을 빼먹은 select 가 목에서 통과하지 않게).
"""
import importlib.util
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
APP_FILE = os.path.join(ROOT, "streamlit_app.py")
streamlit_available = importlib.util.find_spec("streamlit") is not None
pytestmark = pytest.mark.skipif(not streamlit_available, reason="streamlit 미설치 — AppTest 불가")

WRITABLE_INPUT = ("wo_tracking", "wo_batches", "inventory_transactions", "wo_events")
ARCHIVED = "2026-11-05T09:00:00+00:00"


def _mock():
    from tests.so_mock import SOMock

    class _M(SOMock):
        def _assert_dash(self, op, table):
            if table not in WRITABLE_INPUT:
                raise AssertionError(f"input mock: 허용되지 않은 쓰기 ({op} {table})")

    m = _M()
    m.apply_select = True
    for t in ("inventory_transactions", "purchase_order_items", "bom", "materials", "wo_tracking",
              "wo_batches", "wo_events"):
        m.tables.setdefault(t, [])
    m.tables["materials"] += [{"material_id": "M191", "raw_name": "S45C Ø30"},
                              {"material_id": "M500", "raw_name": "SUS303 Ø12"}]
    m.tables["products"] += [
        {"product_id": "P0738", "pn": "HA80-80092", "archived_at": ARCHIVED,
         "archive_reason": "설계변경 HA80-80093"},
        {"product_id": "P0883", "pn": "HA80-80093", "archived_at": None, "archive_reason": None},
    ]
    m.tables["sales_order_items"].append({"soi_id": 7001, "so_id": 701, "product_id": "P0883",
                                          "pending_qty": 500, "status": "PENDING"})
    return m


def _lot(m, lot, mid, qty, poi=None, poi_item=None, poi_pid=None, txn_id=None):
    """잔여 소재 LOT(RECEIPT) + 그 입고가 가리키는 발주 라인."""
    m.tables["inventory_transactions"].append({
        "txn_id": txn_id or len(m.tables["inventory_transactions"]) + 1, "lot_number": lot,
        "material_id": mid, "qty": qty, "txn_type": "RECEIPT", "ref_id": poi})
    if poi is not None:
        m.tables["purchase_order_items"].append({"poi_id": poi, "item_name": poi_item, "product_id": poi_pid})


def _bom(m, pid, mid):
    m.tables["bom"].append({"bom_id": len(m.tables["bom"]) + 1, "product_id": pid, "material_id": mid,
                            "qty_per_pc": 1, "shared_factor": 1})


def _open(monkeypatch, m):
    import db as _dbmod
    from streamlit.testing.v1 import AppTest
    from tests.conftest import goto
    m.install(monkeypatch, _dbmod)
    at = AppTest.from_file(APP_FILE, default_timeout=90)
    at.secrets["supabase"] = {"url": "https://mock.local", "anon_key": "a", "service_role_key": "s"}
    at.secrets["auth"] = {"disabled": True}
    at.run()
    goto(at, "proc", "in")
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def _sel(at, lot):
    return next(s for s in at.selectbox if s.key == f"pe_in_pnsel_{lot}")


def _texts(at):
    out = [str(x.value) for x in at.warning] + [str(x.value) for x in at.error] + [str(x.value) for x in at.info]
    return "\n".join(out)


def _submit(at, wo="20261106-001"):
    at.text_input(key="pe_wo_no").set_value(wo)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    b = at.button(key="pe_in_submit")
    assert not b.disabled, _texts(at)
    b.click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]


def _ins(m, table):
    return [p for op, t, p in m.writes if op == "insert" and t == table]


# ── 대조군: 활성 힌트는 지금처럼 기본 선택으로 등록 ──
def test_a_t9_active_hint_registers_as_before(monkeypatch):
    m = _mock()
    _lot(m, "W2000", "M191", 300, poi=400, poi_item="HA80-80093", poi_pid="P0883")
    _bom(m, "P0883", "M191")
    at = _open(monkeypatch, m)
    sb = _sel(at, "W2000")
    assert sb.options == ["HA80-80093 ← 미납 500 (발주 라인 기준)"], sb.options
    assert sb.index == 0
    _submit(at)
    wo = _ins(m, "wo_tracking")
    assert len(wo) == 1 and wo[0]["product_id"] == "P0883" and wo[0]["pn"] == "HA80-80093", wo
    wb = _ins(m, "wo_batches")
    assert len(wb) == 1 and wb[0]["product_id"] == "P0883" and wb[0]["pn"] == "HA80-80093", wb
