"""db.fetch_all — PostgREST 요청당 1,000행 상한을 넘어 끝까지 읽는 페이지 헬퍼(핫픽스 2, r2 2026-10-27).

목 `_fetch_raw` 는 PostgREST 처럼 select·order·offset·limit 을 적용하고 요청당 최대 1,000행만 준다.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db  # noqa: E402

SERVER_MAX = 1000


class Raw:
    """PostgREST 모사: select 열만, order(열.asc|desc 여러 개) 정렬, offset·limit, 요청당 1,000행.
    calls 에 (select, filter, limit) 기록. dup_shift = 다음 페이지 시작을 앞당겨 경계 행 중복(삽입 모사)."""

    def __init__(self, rows, dup_shift=0):
        self.rows = rows
        self.calls = []
        self.dup_shift = dup_shift

    def __call__(self, table, select, filter_query, limit):
        self.calls.append((select, filter_query, limit))
        parts = dict(p.split("=", 1) for p in filter_query.split("&") if "=" in p)
        rows = list(self.rows)
        for key in reversed([k for k in parts.get("order", "").split(",") if k]):
            col, _, d = key.partition(".")
            rows.sort(key=lambda r: (r.get(col) is None, r.get(col) if r.get(col) is not None else 0),
                      reverse=(d == "desc"))      # NULL 은 뒤로(후속 C 복합키 뷰)
        off = int(parts.get("offset", 0))
        if off and self.dup_shift:
            off = max(0, off - self.dup_shift)
        cols = None if select.strip() == "*" else [c.strip() for c in select.split(",")]
        out = rows[off:off + min(limit, SERVER_MAX)]
        return [dict(r) if cols is None else {c: r.get(c) for c in cols} for r in out]


def _rows(n):
    # sched_id 를 역순으로 넣어 목이 정렬하지 않으면 페이지가 엇갈리게
    return [{"sched_id": n - i, "soi_id": (i % 7) + 1, "qty": 1, "due_date": f"2026-{(i % 12) + 1:02d}-01"}
            for i in range(n)]


@pytest.fixture()
def raw(monkeypatch):
    def _install(rows, **kw):
        r = Raw(rows, **kw)
        monkeypatch.setattr(db, "_fetch_raw", r)
        return r
    return _install


@pytest.mark.parametrize("n,limits", [(0, [1000]), (999, [1000]), (1000, [1000, 1000]),
                                      (2500, [1000, 1000, 1000])])
def test_reads_to_the_end_in_1000_row_pages(raw, n, limits):
    r = raw(_rows(n))
    rows, truncated = db.fetch_all("so_delivery_schedule", "soi_id,qty", "", cache=False)
    assert not truncated
    assert sorted(x["sched_id"] for x in rows) == list(range(1, n + 1))
    assert [x["sched_id"] for x in rows] == sorted(x["sched_id"] for x in rows)   # 정렬 = 기본 키 오름차순
    assert [lim for _, _, lim in r.calls] == limits
    assert [int(f.split("offset=")[1]) for _, f, _ in r.calls] == [i * 1000 for i in range(len(limits))]


def test_max_rows_exact_vs_exceeded_uses_probe(raw):
    r = raw(_rows(20000))
    rows, truncated = db.fetch_all("so_delivery_schedule", "soi_id", "", cache=False)
    assert len(rows) == 20000 and not truncated                   # 딱 2만 행 = 절단 아님(1행 탐색 빈 응답)
    assert len(r.calls) == 21 and r.calls[-1][2] == 1
    r = raw(_rows(25000))
    rows, truncated = db.fetch_all("so_delivery_schedule", "soi_id", "", cache=False)
    assert truncated and len(rows) == 20000 and len(r.calls) == 21   # 페이지 20 + 탐색 1


def test_max_rows_not_multiple_of_page(raw):
    r = raw(_rows(5000))
    rows, truncated = db.fetch_all("so_delivery_schedule", "soi_id", "", cache=False, max_rows=2500)
    assert truncated and len(rows) == 2500
    assert [lim for _, _, lim in r.calls] == [1000, 1000, 500, 1]      # 마지막 요청 = 남은 수만
    r = raw(_rows(300))
    rows, truncated = db.fetch_all("so_delivery_schedule", "soi_id", "", cache=False, page=100, max_rows=250)
    assert truncated and len(rows) == 250
    assert [lim for _, _, lim in r.calls] == [100, 100, 50, 1]


@pytest.mark.parametrize("kw", [{"page": 0}, {"page": 2000}, {"page": 1.5}, {"max_rows": 0}, {"max_rows": -1}])
def test_argument_validation(raw, kw):
    raw(_rows(10))
    with pytest.raises(ValueError):
        db.fetch_all("so_delivery_schedule", "soi_id", "", cache=False, **kw)


def test_unknown_table_without_pk_and_order_in_filter_raise(raw):
    raw(_rows(10))
    with pytest.raises(ValueError):
        db.fetch_all("no_such_table", "x", "", cache=False)
    with pytest.raises(ValueError):
        db.fetch_all("so_delivery_schedule", "soi_id", "order=due_date.asc", cache=False)
    rows, _ = db.fetch_all("no_such_table", "x", "", cache=False, pk="sched_id")   # pk 를 주면 된다
    assert len(rows) == 10


def test_duplicate_rows_across_pages_removed_exactly(raw):
    raw(_rows(2500), dup_shift=3)      # 페이지 경계마다 앞 페이지 끝 3행이 다시 온다
    rows, truncated = db.fetch_all("so_delivery_schedule", "soi_id,qty", "", cache=False)
    ids = [x["sched_id"] for x in rows]
    assert ids == list(range(1, 2501))           # 정확한 집합·순서(중복 0, 누락 0)


def test_order_is_deterministic_and_pk_added_to_select(raw):
    r = raw(_rows(10))
    rows, _ = db.fetch_all("so_delivery_schedule", "soi_id,due_date", "due_date=lt.2026-10-27",
                           order="due_date.asc", cache=False)
    sel, fq, _ = r.calls[0]
    assert sel == "soi_id,due_date,sched_id"                             # 중복 제거용 기본 키
    assert "order=due_date.asc,sched_id.asc" in fq                       # 기본 키로 동순위 결정
    assert fq.startswith("due_date=lt.2026-10-27&")
    assert [(x["due_date"], x["sched_id"]) for x in rows] == sorted((x["due_date"], x["sched_id"]) for x in rows)
    r2 = raw(_rows(10))
    db.fetch_all("so_delivery_schedule", "*", "", cache=False)
    assert r2.calls[0][0] == "*" and "order=sched_id.asc" in r2.calls[0][1]


def test_pages_never_use_page_cache_and_result_cached_once(raw, monkeypatch):
    """r2 H1: 페이지 조회는 항상 cache=False, 결과 전체를 한 단위로 캐시 — 두 번째 호출은 DB 0회,
    clear_cache 뒤에는 다시 읽는다."""
    r = raw(_rows(2500))
    seen_cache = []
    real_fetch = db.fetch

    def _spy(*a, **k):
        seen_cache.append(k.get("cache"))
        return real_fetch(*a, **k)
    monkeypatch.setattr(db, "fetch", _spy)
    db.clear_cache()
    rows1, _ = db.fetch_all("so_delivery_schedule", "soi_id", "")      # cache 기본(None) = 전체 캐시
    n1 = len(r.calls)
    rows2, _ = db.fetch_all("so_delivery_schedule", "soi_id", "")
    assert n1 == 3 and len(r.calls) == n1 and rows1 == rows2          # 두 번째는 캐시(DB 0회)
    assert seen_cache and all(c is False for c in seen_cache)           # 페이지별 캐시 미사용
    db.clear_cache()
    db.fetch_all("so_delivery_schedule", "soi_id", "")
    assert len(r.calls) == n1 * 2                                       # clear_cache 뒤 재조회
    db.fetch_all("so_delivery_schedule", "soi_id", "", cache=False)
    assert len(r.calls) == n1 * 3                                       # cache=False 는 우회


def test_same_due_and_seq_across_page_boundary_exact(raw):
    """r3 L1: 정렬 열(납기·seq)이 모두 같은 2,500행이 페이지 경계를 가로질러도 기본 키로 결정 — 정확한 집합·순서."""
    rows = [{"sched_id": 2500 - i, "soi_id": 1, "due_date": "2026-11-01", "seq": 1, "qty": 1} for i in range(2500)]
    r = raw(rows, dup_shift=2)
    got, truncated = db.fetch_all("so_delivery_schedule", "soi_id,due_date,seq", "", order="due_date.asc,seq.asc",
                                  cache=False)
    assert not truncated
    assert [x["sched_id"] for x in got] == list(range(1, 2501))
    assert all("order=due_date.asc,seq.asc,sched_id.asc" in fq for _, fq, _ in r.calls)


def test_cache_key_covers_all_seven_arguments(raw):
    """r3 L1: 전체 결과 캐시 키 = table·select·filter·page·max_rows·order·pk — 하나만 바꿔도 다시 읽고,
    같은 인자 재호출은 DB 0회."""
    r = raw(_rows(30))
    db.clear_cache()
    # B(r3 L1): 기준 호출에도 pk 를 명시 — table 만 바꿔 키가 갈리는지 따로 본다
    base = dict(table="so_delivery_schedule", select="soi_id", filter_query="", page=1000, max_rows=20000,
                order=None, pk="sched_id")

    def call(**over):
        a = {**base, **over}
        return db.fetch_all(a.pop("table"), a.pop("select"), a.pop("filter_query"), **a)

    call()
    n = len(r.calls)
    call()
    assert len(r.calls) == n                                  # 적중
    for over in ({"table": "no_such_table"}, {"select": "soi_id,qty"},
                 {"filter_query": "qty=gt.0"}, {"page": 500}, {"max_rows": 10000},
                 {"order": "due_date.asc"}, {"pk": "soi_id"}):
        call(**over)
        assert len(r.calls) > n, over                         # 이 인자로 키가 갈린다
        n = len(r.calls)
        call(**over)
        assert len(r.calls) == n, over                        # 같은 인자 재호출은 적중


def test_cache_branch_master_vs_tx(raw, monkeypatch):
    """r3: 마스터 표(CACHED_TABLES)는 _fetch_all_cached, 그 외(회차 등)는 _fetch_all_cached_tx 로 간다(분기만 —
    실제 TTL 값은 test_fetch_all_cache_ttl_values)."""
    raw(_rows(5))
    used = []
    monkeypatch.setattr(db, "_fetch_all_cached", lambda *a: used.append("master") or ([], False))
    monkeypatch.setattr(db, "_fetch_all_cached_tx", lambda *a: used.append("tx") or ([], False))
    db.fetch_all("so_delivery_schedule", "soi_id", "")
    db.fetch_all("products", "pn", "", pk="product_id")
    assert used == ["tx", "master"]


def test_cache_hit_restores_truncation_note(raw, monkeypatch):
    """r3 L1: 캐시 적중 때도 절단 기록을 만들고(절단), 같은 테이블 기존 기록을 되돌리며(비절단), 다른 테이블 기록은 둔다."""
    import streamlit as st
    db.clear_cache()
    r = raw(_rows(25000))
    ss = {"_fetch_truncated": {}}
    monkeypatch.setattr(st, "session_state", ss, raising=False)
    db.fetch_all("so_delivery_schedule", "soi_id", "")               # 채움(절단)
    n = len(r.calls)
    ss["_fetch_truncated"] = {"products": 1000}                       # 다른 실행(새 세션 상태)
    rows, truncated = db.fetch_all("so_delivery_schedule", "soi_id", "")
    assert len(r.calls) == n and truncated                            # 적중
    assert ss["_fetch_truncated"] == {"products": 1000, "so_delivery_schedule": 20000}
    # 비절단 결과의 적중 — 같은 테이블의 기존(일반 fetch 상한) 기록은 그대로, 다른 테이블도 그대로
    raw(_rows(10))
    db.fetch_all("so_delivery_schedule", "qty", "")                   # 채움
    ss["_fetch_truncated"] = {"products": 1000, "so_delivery_schedule": 1000}
    _, truncated = db.fetch_all("so_delivery_schedule", "qty", "")    # 적중
    assert not truncated
    assert ss["_fetch_truncated"] == {"products": 1000, "so_delivery_schedule": 1000}
    ss["_fetch_truncated"] = {"products": 1000}
    db.fetch_all("so_delivery_schedule", "qty", "")                   # 적중, 기존 기록 없음 → 만들지 않는다
    assert ss["_fetch_truncated"] == {"products": 1000}


def test_truncation_note_only_when_truncated_and_other_tables_kept(raw, monkeypatch):
    """끝까지 읽으면 페이지마다 fetch 가 남긴 관리자 상한 기록을 되돌린다 — 실제 절단 때만, 다른 테이블 기록은 유지."""
    import streamlit as st
    ss = {"_fetch_truncated": {"products": 1000}}
    monkeypatch.setattr(st, "session_state", ss, raising=False)
    raw(_rows(2500))
    db.fetch_all("so_delivery_schedule", "soi_id", "", cache=False)
    assert "so_delivery_schedule" not in ss["_fetch_truncated"]
    assert ss["_fetch_truncated"]["products"] == 1000
    raw(_rows(25000))
    db.fetch_all("so_delivery_schedule", "soi_id", "", cache=False)
    assert ss["_fetch_truncated"]["so_delivery_schedule"] == 20000
    assert ss["_fetch_truncated"]["products"] == 1000


def test_fetch_all_cache_ttl_values():
    """B(r3-2 LOW): 실제 데코레이터 TTL — 마스터 300초·그 외 60초, fetch 의 CACHE_TTL·CACHE_TTL_TX 와 같다.
    시간 제어로 만료를 기다리는 대신 st.cache_data 가 가진 설정값(_info.ttl)을 읽는다(내부 속성이라 없으면
    상수 검증만)."""
    assert db.FETCH_ALL_TTL == db.CACHE_TTL == 300
    assert db.FETCH_ALL_TTL_TX == db.CACHE_TTL_TX == 60
    for f, want in ((db._fetch_all_cached, 300), (db._fetch_all_cached_tx, 60)):
        info = getattr(f, "_info", None)
        if info is not None and hasattr(info, "ttl"):
            assert info.ttl == want, (f, info.ttl)


class _Http:
    """requests 대역 — PostgREST 의 GET(select·order·offset·limit, 요청당 1,000행)·POST(삽입)만.
    db 모듈의 HTTP 만 바꾸고 db.fetch_all·db.insert·clear_cache 는 진짜를 쓴다."""

    def __init__(self, rows):
        self.rows = rows
        self.gets = 0

    class _R:
        def __init__(self, code, body=None):
            self.status_code, self._b, self.text = code, body, ""

        def json(self):
            return self._b

    def get(self, url, headers=None, timeout=None):
        from urllib.parse import urlsplit, parse_qsl
        self.gets += 1
        q = dict(parse_qsl(urlsplit(url).query, keep_blank_values=True))
        rows = list(self.rows)
        for key in reversed([k for k in q.get("order", "").split(",") if k]):
            col, _, d = key.partition(".")
            rows.sort(key=lambda r: (r.get(col) is None, r.get(col) if r.get(col) is not None else 0),
                      reverse=(d == "desc"))      # NULL 은 뒤로(후속 C 복합키 뷰)
        off, lim = int(q.get("offset", 0)), min(int(q.get("limit", 1000)), SERVER_MAX)
        cols = [c for c in q.get("select", "*").split(",")]
        out = rows[off:off + lim]
        return self._R(200, [dict(r) if cols == ["*"] else {c: r.get(c) for c in cols} for r in out])

    def post(self, url, headers=None, data=None, timeout=None):
        import json as _json
        self.rows.extend(_json.loads(data))
        return self._R(201)


def test_real_insert_invalidates_fetch_all_cache(monkeypatch):
    """B(r3-2 REQUIRED ⑥): 회차 캐시를 채운 뒤 진짜 db.insert(HTTP 만 대역)로 회차를 추가하면, 수동
    clear_cache() 없이 다음 fetch_all 이 새 행을 읽는다(쓰기 → 캐시 무효화 연결)."""
    http = _Http(_rows(1500))
    monkeypatch.setattr(db, "requests", http)
    monkeypatch.setattr(db, "_url", lambda: "https://mock.local")
    monkeypatch.setattr(db, "_headers", lambda role="service_role": {})
    db.clear_cache()
    rows, tr = db.fetch_all("so_delivery_schedule", "sched_id,qty", "")
    assert len(rows) == 1500 and not tr
    n = http.gets
    db.fetch_all("so_delivery_schedule", "sched_id,qty", "")
    assert http.gets == n                                         # 캐시 적중(HTTP 0회)
    db.insert("so_delivery_schedule", [{"sched_id": 99999, "soi_id": 1, "qty": 7, "due_date": "2026-12-01"}])
    rows2, _ = db.fetch_all("so_delivery_schedule", "sched_id,qty", "")
    assert http.gets > n and len(rows2) == 1501
    assert any(r["sched_id"] == 99999 and r["qty"] == 7 for r in rows2)
