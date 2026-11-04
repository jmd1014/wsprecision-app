# -*- coding: utf-8 -*-
"""마스터 관리 소수정 묶음(2026-11-04) — 후보 31(탭·선택 유지) · 32(라우트 복사) · 34(단가 조정 별건).
DB 는 mock. 탭 유지(st.tabs key)는 AppTest 로 볼 수 없어 로컬 앱 확인으로 대신한다(보고서)."""
import os
import sys
import importlib.util
from urllib.parse import unquote

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tests.conftest import goto  # noqa: E402

pytestmark = pytest.mark.skipif(importlib.util.find_spec("streamlit") is None,
                                reason="streamlit 미설치 — AppTest 불가")

APP_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "streamlit_app.py")

# ─────────────── 후보 31 — BOM 편집 선택 유지 ───────────────
PRODS = [{"product_id": f"P90{i}", "pn": f"MM-TEST-{i}", "item_name": f"시험품 {i}",
          "customer": "시험고객", "sub_class": "시험"} for i in (1, 2, 3)]
BOMS = {p["product_id"]: [{"bom_id": 7000 + k, "product_id": p["product_id"], "material_id": "M001",
                            "raw_material_name": f"S304 Ø{20 + k}*30", "qty_per_pc": 1.0, "shared_factor": 1,
                            "process_type": "MATERIAL", "unit_price": None, "lot_label": None,
                            "process_vendor_id": None, "verification_status": "확인완료", "source": "MES"}]
        for k, p in enumerate(PRODS)}


class _BomDB:
    def __init__(self):
        self.updates = []

    def fetch(self, table, select="*", filter_query="", limit=1000, **kw):
        fq = unquote(filter_query or "")
        if table == "products" and ("MM-TEST" in fq or "archived_at=is.null&order=pn" == fq):
            return [dict(p) for p in PRODS]
        if table == "bom":
            for pid, rows in BOMS.items():
                if f"product_id=eq.{pid}" in fq:
                    return [dict(r) for r in rows]
            if "product_id=in." in fq:
                return [dict(r) for rows in BOMS.values() for r in rows]
        return []


@pytest.fixture()
def bom_db(monkeypatch):
    import db
    m = _BomDB()
    monkeypatch.setattr(db, "fetch", m.fetch)
    monkeypatch.setattr(db, "fetch_one", lambda *a, **k: None)
    monkeypatch.setattr(db, "insert", lambda t, r, *a, **k: pytest.fail(f"insert {t} — 31 은 쓰기 없음"))
    monkeypatch.setattr(db, "update", lambda t, f, v, *a, **k: (m.updates.append((t, f, v)), True)[1])
    monkeypatch.setattr(db, "health_check", lambda: {"status": "OK", "counts": {}})
    monkeypatch.setattr(db, "debug_check", lambda: {"status": "mock"})
    if hasattr(db, "count_rows"):
        monkeypatch.setattr(db, "count_rows", lambda *a, **k: 0)
    if hasattr(db, "rpc"):
        monkeypatch.setattr(db, "rpc", lambda *a, **k: None)
    return m


def _open_bom(sel_pid=None, q="MM-TEST"):
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    for _c in (st.cache_data, st.cache_resource):
        try:
            _c.clear()
        except Exception:
            pass
    at = AppTest.from_file(APP_FILE, default_timeout=90)
    at.secrets["supabase"] = {"url": "https://mock.local", "anon_key": "a", "service_role_key": "s"}
    at.secrets["auth"] = {"disabled": True}
    at.run()
    if sel_pid:
        at.session_state["bom_sel_pid"] = sel_pid
    goto(at, "master")
    [t for t in at.text_input if t.key == "bom_pq"][0].set_value(q)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def _bom_head(at):
    return [str(m.value) for m in at.markdown if "BOM 전개" in str(m.value)]


def test_31_tabs_have_key():
    src = open(APP_FILE, encoding="utf-8").read()
    i = src.index('"정합 점검", "계정 관리", "디자인 데이터 내보내기", "이력 조회"')
    assert 'key="mm_tabs"' in src[i:i + 200], "마스터 관리 탭 key — 저장 뒤 rerun 에도 같은 탭"


def test_31_bom_remembered_product_is_selected(bom_db):
    at = _open_bom(sel_pid="P903")
    assert any("MM-TEST-3 — BOM 전개" in h for h in _bom_head(at)), _bom_head(at)
    assert at.session_state["bom_sel_pid"] == "P903"


def test_31_bom_default_first_row_and_unknown_memory(bom_db):
    at = _open_bom()
    assert any("MM-TEST-1 — BOM 전개" in h for h in _bom_head(at))
    assert at.session_state["bom_sel_pid"] == "P901", "선택을 기억"
    at = _open_bom(sel_pid="P999")
    assert any("MM-TEST-1 — BOM 전개" in h for h in _bom_head(at)), "목록에 없는 기억은 무시(기존 동작: 첫 행)"
    assert at.session_state["bom_sel_pid"] == "P901"


def test_31_bom_save_rerun_keeps_product(bom_db):
    at = _open_bom(sel_pid="P902")
    assert any("MM-TEST-2 — BOM 전개" in h for h in _bom_head(at))
    [n for n in at.number_input if n.key == "bomf_qpc_7001"][0].set_value(2.0)
    [b for b in at.button if b.label == "변경 저장"][0].click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert bom_db.updates and bom_db.updates[0][0] == "bom" and bom_db.updates[0][2] == {"qty_per_pc": 2.0}
    assert any("MM-TEST-2 — BOM 전개" in h for h in _bom_head(at)), "저장 → st.rerun 뒤에도 같은 제품"
    assert at.session_state["bom_sel_pid"] == "P902"
