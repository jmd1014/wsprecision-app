"""db.fetch_all — PostgREST 요청당 1,000행 상한을 넘어 끝까지 읽는 페이지 헬퍼(핫픽스 2, 2026-10-27).

목 `_fetch_raw` 는 PostgREST 처럼 order·offset·limit 을 적용하고 요청당 최대 1,000행만 준다.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db  # noqa: E402

SERVER_MAX = 1000


class Raw:
    """정렬된 행 + offset·limit 자르기 + 요청당 1,000행. calls 에 (select, filter, limit) 기록."""

    def __init__(self, rows, pk="sched_id", dup_shift=0):
        self.rows = sorted(rows, key=lambda r: r[pk])
        self.calls = []
        self.dup_shift = dup_shift       # 다음 페이지 시작을 앞당겨 경계 행이 두 번 오게(동시 삽입 모사)

    def __call__(self, table, select, filter_query, limit):
        self.calls.append((select, filter_query, limit))
        off = 0
        for part in filter_query.split("&"):
            if part.startswith("offset="):
                off = int(part[7:])
        if off and self.dup_shift:
            off = max(0, off - self.dup_shift)
        return [dict(r) for r in self.rows[off:off + min(limit, SERVER_MAX)]]


def _rows(n):
    return [{"sched_id": i + 1, "soi_id": (i % 7) + 1, "qty": 1} for i in range(n)]


@pytest.fixture()
def raw(monkeypatch):
    def _install(rows, **kw):
        r = Raw(rows, **kw)
        monkeypatch.setattr(db, "_fetch_raw", r)
        return r
    return _install


@pytest.mark.parametrize("n,pages", [(0, 1), (999, 1), (1000, 2), (2500, 3)])
def test_reads_to_the_end_in_1000_row_pages(raw, n, pages):
    r = raw(_rows(n))
    rows, truncated = db.fetch_all("so_delivery_schedule", "soi_id,qty", "", cache=False)
    assert len(rows) == n and not truncated
    assert len(r.calls) == pages                      # 1,000행 정확히면 두 번째(빈) 페이지로 끝을 확인
    assert [int(f.split("offset=")[1]) for _, f, _ in r.calls] == [i * 1000 for i in range(pages)]
    assert all(lim == 1000 for _, _, lim in r.calls)


def test_max_rows_truncates_and_flags(raw):
    r = raw(_rows(25000))
    rows, truncated = db.fetch_all("so_delivery_schedule", "soi_id", "", cache=False)
    assert truncated and len(rows) == 20000 and len(r.calls) == 20      # 페이지 수 ≤ 20
    rows2, tr2 = db.fetch_all("so_delivery_schedule", "soi_id", "", cache=False, max_rows=3000)
    assert tr2 and len(rows2) == 3000


def test_duplicate_rows_across_pages_removed_by_pk(raw):
    raw(_rows(2500), dup_shift=3)      # 페이지 경계마다 앞 페이지 끝 3행이 다시 온다
    rows, truncated = db.fetch_all("so_delivery_schedule", "soi_id,qty", "", cache=False)
    ids = [x["sched_id"] for x in rows]
    assert len(ids) == len(set(ids))
    assert set(ids) <= set(range(1, 2501))


def test_order_is_deterministic_and_pk_added_to_select(raw):
    r = raw(_rows(10))
    db.fetch_all("so_delivery_schedule", "soi_id,qty", "due_date=lt.2026-10-27",
                 order="due_date.asc,seq.asc", cache=False)
    sel, fq, _ = r.calls[0]
    assert sel == "soi_id,qty,sched_id"                                  # 중복 제거용 기본 키
    assert "order=due_date.asc,seq.asc,sched_id.asc" in fq               # 기본 키로 동순위 결정
    assert fq.startswith("due_date=lt.2026-10-27&")
    r2 = raw(_rows(10))
    db.fetch_all("so_delivery_schedule", "*", "", cache=False)
    assert r2.calls[0][0] == "*" and "order=sched_id.asc" in r2.calls[0][1]
    with pytest.raises(AssertionError):
        db.fetch_all("so_delivery_schedule", "soi_id", "order=due_date.asc", cache=False)


def test_truncation_note_only_when_truncated(raw, monkeypatch):
    """끝까지 읽으면 페이지마다 fetch 가 남긴 관리자 상한 기록을 되돌린다 — 실제 절단 때만 남긴다."""
    import streamlit as st
    store = {}

    class _SS(dict):
        pass
    ss = _SS()
    monkeypatch.setattr(st, "session_state", ss, raising=False)
    raw(_rows(2500))
    db.fetch_all("so_delivery_schedule", "soi_id", "", cache=False)
    assert "so_delivery_schedule" not in ss.get("_fetch_truncated", {})
    raw(_rows(25000))
    db.fetch_all("so_delivery_schedule", "soi_id", "", cache=False)
    assert ss["_fetch_truncated"]["so_delivery_schedule"] == 20000
    assert store == {}
