"""핫픽스(2026-10-27): 출고 등록 회차 조회 상한 — limit=500 한 번 조회가 기준일 이하 회차 500행을
넘으면 납기 오름차순 끝(가장 최근 납기)의 열린 회차가 잘려 안 뜨던 결함(509행, 10/28 회차 9건).

목 DB 는 PostgREST 처럼 정렬된 행을 offset·limit 으로 자르고, 요청당 최대 1,000행만 준다.
"""
import os
import sys
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_bulk_delivery import (ship_db, _open_shipping, streamlit_available)  # noqa: E402,F401

APP_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "streamlit_app.py")
pytestmark = pytest.mark.skipif(not streamlit_available, reason="streamlit 미설치 — AppTest 불가")

SERVER_MAX = 1000          # Supabase PostgREST 기본 max rows


def _rounds(n_closed, open_due):
    """지난 날짜의 닫힌 회차 n_closed 개(납기 오름차순 앞) + 기준일의 열린 회차 1개(맨 뒤)."""
    base = date.today() - timedelta(days=400)
    rows = [{"sched_id": 10000 + i, "soi_id": 11, "so_id": 100, "seq": i + 10,
             "due_date": (base + timedelta(days=i % 380)).isoformat(),
             "qty": 10, "delivered_qty": 10} for i in range(n_closed)]
    rows.append({"sched_id": 99999, "soi_id": 12, "so_id": 101, "seq": 1,
                 "due_date": open_due, "qty": 300, "delivered_qty": 100})
    rows.sort(key=lambda r: (r["due_date"], r["seq"], r["sched_id"]))
    return rows


def _patch(monkeypatch, ship_db, rows, calls):
    real = ship_db.fetch

    def _f(table, select="*", filter_query="", limit=1000, **kw):
        if table == "so_delivery_schedule" and "due_date=" in filter_query:
            calls.append((filter_query, limit))
            off = int(filter_query.split("offset=")[1].split("&")[0]) if "offset=" in filter_query else 0
            return [dict(r) for r in rows[off:off + min(limit, SERVER_MAX)]]
        return real(table, select, filter_query, limit, **kw)
    monkeypatch.setattr(ship_db, "fetch", _f)


def _cart(at):
    return next((d.value for d in at.dataframe
                 if "잔량" in d.value.columns and "출고" in d.value.columns), None)


def test_open_round_after_509_rows_is_listed(ship_db, monkeypatch):
    """회귀: 기준일 이하 회차 510행(앞 509 닫힘) — 마지막(가장 최근 납기)의 열린 회차가 목록에 뜬다."""
    calls = []
    _patch(monkeypatch, ship_db, _rounds(509, date.today().isoformat()), calls)
    at = _open_shipping(ship_db)
    assert not at.exception, [str(e.value) for e in at.exception]
    cart = _cart(at)
    assert cart is not None and len(cart) == 1, cart
    assert float(cart.iloc[0]["잔량"]) == 200                 # 300 − 100
    assert not any("일부가 잘렸습니다" in str(w.value) for w in at.warning)
    assert len(calls) == 1 and calls[0][1] == 1000 and "sched_id.asc" in calls[0][0]


def test_pages_past_server_max_rows(ship_db, monkeypatch):
    """요청당 1,000행 상한(PostgREST)을 넘어도 offset 으로 끝까지 읽는다 — 2,500행이면 3번."""
    calls = []
    _patch(monkeypatch, ship_db, _rounds(2499, date.today().isoformat()), calls)
    at = _open_shipping(ship_db)
    assert not at.exception, [str(e.value) for e in at.exception]
    cart = _cart(at)
    assert cart is not None and len(cart) == 1
    assert [int(q.split("offset=")[1]) for q, _ in calls] == [0, 1000, 2000]


def test_safety_cap_warns_on_screen(ship_db, monkeypatch):
    """안전 상한(10,000행)에 닿으면 현장 경고 한 줄 — 관리자 화면 기록만으로 끝나지 않는다."""
    calls = []
    _patch(monkeypatch, ship_db, _rounds(10500, date.today().isoformat()), calls)
    at = _open_shipping(ship_db)
    assert not at.exception, [str(e.value) for e in at.exception]
    assert len(calls) == 11            # 페이지 10 + 남은 행 탐색 1(핫픽스 2 r2 — 딱 상한이면 절단 아님)
    assert any("회차가 너무 많아 일부가 잘렸습니다 — 기준일을 좁히세요" in str(w.value) for w in at.warning)


def test_static_no_single_500_limit_on_round_list():
    src = open(APP_FILE, encoding="utf-8").read()
    assert '_sh_flt + "&order=due_date.asc,seq.asc", limit=500)' not in src
    assert "회차가 너무 많아 일부가 잘렸습니다 — 기준일을 좁히세요" in src
