# -*- coding: utf-8 -*-
"""db.fetch 읽기 캐시·쓰기 무효화·조회 상한 감지 (2026-09-17)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import db  # noqa: E402


class _Resp:
    def __init__(self, status=204, body=None):
        self.status_code = status
        self.text = ""
        self._body = body or []

    def json(self):
        return self._body


def _patch_raw(monkeypatch, calls, rows=None):
    def raw(table, select, filter_query, limit):
        calls.append(table)
        return list(rows or [{"id": 1}])
    monkeypatch.setattr(db, "_fetch_raw", raw)
    db.clear_cache()


def _patch_write(monkeypatch):
    monkeypatch.setattr(db, "_url", lambda: "http://x")
    monkeypatch.setattr(db, "_headers", lambda role="service_role": {})
    monkeypatch.setattr(db.requests, "patch", lambda *a, **k: _Resp(204))
    monkeypatch.setattr(db.requests, "post", lambda *a, **k: _Resp(201))
    monkeypatch.setattr(db.requests, "delete", lambda *a, **k: _Resp(200, []))


def test_master_table_is_cached(monkeypatch):
    calls = []
    _patch_raw(monkeypatch, calls)
    db.fetch("products", "product_id", "is_active=eq.true", 1000)
    db.fetch("products", "product_id", "is_active=eq.true", 1000)
    assert calls.count("products") == 1
    # 다른 select/filter 는 별도 항목
    db.fetch("products", "*", "", 1000)
    assert calls.count("products") == 2


def test_tx_table_is_cached_too(monkeypatch):
    calls = []
    _patch_raw(monkeypatch, calls)
    db.fetch("wo_events", "*", "", 500)
    db.fetch("wo_events", "*", "", 500)
    assert calls.count("wo_events") == 1


def test_any_write_invalidates_everything(monkeypatch):
    calls = []
    _patch_raw(monkeypatch, calls)
    _patch_write(monkeypatch)
    db.fetch("materials", "*", "", 1000)
    db.fetch("wo_events", "*", "", 500)
    # 원장에 쓰면 마스터 캐시까지 전부 비운다 (뷰·파생 데이터 정합 보장)
    assert db.insert("inventory_transactions", [{"x": 1}]) == 1
    db.fetch("materials", "*", "", 1000)
    db.fetch("wo_events", "*", "", 500)
    assert calls.count("materials") == 2
    assert calls.count("wo_events") == 2
    assert db.update("materials", "material_id=eq.M1", {"name": "x"}) is True
    db.fetch("materials", "*", "", 1000)
    assert calls.count("materials") == 3
    db.delete("wo_events", "event_id=eq.1")
    db.fetch("wo_events", "*", "", 500)
    assert calls.count("wo_events") == 3


def test_cache_can_be_forced_off(monkeypatch):
    calls = []
    _patch_raw(monkeypatch, calls)
    db.fetch("vendors", "*", "", 1000, cache=False)
    db.fetch("vendors", "*", "", 1000, cache=False)
    assert calls.count("vendors") == 2


def test_truncation_noted(monkeypatch):
    noted = {}
    monkeypatch.setattr(db, "_note_truncation",
                        lambda t, lim, n: noted.__setitem__(t, (lim, n)))
    _patch_raw(monkeypatch, [], rows=[{"i": i} for i in range(300)])
    db.fetch("so_delivery_schedule", "*", "", 300)
    assert noted["so_delivery_schedule"] == (300, 300)


def test_filter_quoting():
    # 최상위: URL 을 깨는 문자만 인코딩, * 는 와일드카드로 유지
    assert db.qv("*A&B*") == "*A%26B*"
    assert db.qv("(주)명진") == "%28%EC%A3%BC%29%EB%AA%85%EC%A7%84"
    assert db.qv("2026-09-16T00:00:00+09:00") == "2026-09-16T00%3A00%3A00%2B09%3A00"
    assert db.qv(None) == ""
    assert db.qv(96) == "96"
    # or=()/in.() 안: 큰따옴표로 감싸 콤마·괄호를 값으로, 따옴표는 이스케이프
    assert db.qo("A,B") == "%22A%2CB%22"
    assert db.qo('x"y') == "%22x%5C%22y%22"
    # 따옴표 안의 * 도 인코딩되지만 PostgREST 는 와일드카드로 해석 (실측)
    assert db.qol("ABV") == "%22%2AABV%2A%22"


def test_truncation_rule():
    # 작은 limit(최근 N건) 은 의도된 것 — 기록 안 함, 상한 미만도 기록 안 함
    ss = {}
    import streamlit as st
    orig = st.session_state
    try:
        db.st.session_state = ss  # type: ignore[attr-defined]
        db._note_truncation("x", 20, 20)
        db._note_truncation("y", 1000, 999)
        db._note_truncation("z", 1000, 1000)
        assert ss.get("_fetch_truncated") == {"z": 1000}
    finally:
        db.st.session_state = orig  # type: ignore[attr-defined]
