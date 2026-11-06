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


# ── 휴면 품번(후보 49) — 수정 전 코드에서 실패해야 한다(02a) ──
NOTICE_92 = ("발주 라인의 품번 HA80-80092 은 휴면 처리된 품번이라 후보에서 뺐습니다 — "
             "작업지시서 품번을 확인하세요.")
BLOCK_92 = ("HA80-80092 은 휴면 처리된 품번입니다 — 투입 등록할 수 없습니다. "
            "품번을 다시 고르거나 마스터 관리에서 휴면을 해제하세요.")


def _w1257(m, poi_pid="P0738"):
    """운영 사례: W1257(M191, 잔여 800) → poi 325(HA80-80092). BOM 은 휴면·활성 둘 다 M191."""
    _lot(m, "W1257", "M191", 800, poi=325, poi_item="HA80-80092", poi_pid=poi_pid)
    _bom(m, "P0738", "M191")
    _bom(m, "P0883", "M191")


def _assert_w1257(at, m):
    sb = _sel(at, "W1257")
    assert not any("HA80-80092" in o for o in sb.options), sb.options
    assert sb.options == ["HA80-80093 ← 미납 500"] and sb.index == 0, sb.options
    assert NOTICE_92 in _texts(at), _texts(at)
    _submit(at)
    for t in ("wo_tracking", "wo_batches"):
        rows = _ins(m, t)
        assert len(rows) == 1 and rows[0]["product_id"] == "P0883" and rows[0]["pn"] == "HA80-80093", (t, rows)


def test_a_t6_archived_hint_by_product_id(monkeypatch):
    """발주 라인 product_id = 휴면 제품 → 후보에서 빠지고 활성 BOM 품번으로 등록."""
    m = _mock()
    _w1257(m)
    _assert_w1257(_open(monkeypatch, m), m)


def test_a_t7_archived_hint_by_item_name(monkeypatch):
    """발주 라인 product_id 없음 + 품명 = 휴면 품번(품명 경로) → A-T6 과 같은 결과."""
    m = _mock()
    _w1257(m, poi_pid=None)
    _assert_w1257(_open(monkeypatch, m), m)


def test_a_t8_direct_input_archived_pn_blocked(monkeypatch):
    """BOM 후보 없음 → 직접 입력 칸에 휴면 품번 → 오류 문구·버튼 비활성·쓰기 0."""
    m = _mock()
    _lot(m, "W3000", "M500", 50)
    at = _open(monkeypatch, m)
    assert not [s for s in at.selectbox if s.key == "pe_in_pnsel_W3000"]
    at.text_input(key="pe_in_pn").set_value("HA80-80092")
    at.text_input(key="pe_wo_no").set_value("20261106-002")
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert BLOCK_92 in [str(e.value) for e in at.error], [str(e.value) for e in at.error]
    assert at.button(key="pe_in_submit").disabled
    assert not [w for w in m.writes if w[0] != "fetch_400"], m.writes


def test_a_t8b_direct_input_active_pn_still_allowed(monkeypatch):
    """대조: 직접 입력 칸에 활성 품번이면 지금처럼 등록된다."""
    m = _mock()
    _lot(m, "W3000", "M500", 50)
    at = _open(monkeypatch, m)
    at.text_input(key="pe_in_pn").set_value("HA80-80093")
    at.run()
    _submit(at, "20261106-003")
    rows = _ins(m, "wo_tracking")
    assert len(rows) == 1 and rows[0]["product_id"] == "P0883", rows
