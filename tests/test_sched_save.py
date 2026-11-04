# -*- coding: utf-8 -*-
"""납기 입력 안정화(2026-11-05) — 납품 스케줄 저장의 회차 번호 재부여(후보 27)·납품 회차 삭제 차단(후보 26).

so_delivery_schedule 은 UNIQUE(soi_id, seq). 목이 이를 흉내 낸다: 같은 soi 에 같은 seq 가 이미 다른 행에 있으면
update 는 False(PostgREST 409 → db.update False), insert 는 예외. 화면 테스트는 SOMock + 수주 관리 › 납품 스케줄.
"""
import os
import sys
import importlib.util

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tests.conftest import goto  # noqa: E402

pytestmark = pytest.mark.skipif(importlib.util.find_spec("streamlit") is None,
                                reason="streamlit 미설치 — AppTest 불가")
APP_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "streamlit_app.py")
SOI = 11


def _sched_mock(rounds):
    """rounds: [(sched_id, due, seq, qty, delivered)]"""
    from tests.so_mock import SOMock

    class _M(SOMock):
        false_after = None          # n 번째 schedule update 부터 False(부분 실패 흉내)
        n_sched_update = 0

        def _dup(self, soi, seq, sid):
            return any(int(r["soi_id"]) == int(soi) and int(r["seq"]) == int(seq) and r["sched_id"] != sid
                       for r in self.tables["so_delivery_schedule"])

        def update(self, table, filter_query, fields):
            if table == "so_delivery_schedule":
                self.n_sched_update += 1
                if self.false_after is not None and self.n_sched_update >= self.false_after:
                    self.writes.append(("update_false", table, {"filter": filter_query, **fields}))
                    return False
                if "seq" in fields:
                    for r in self._rows(table, filter_query):
                        if self._dup(r["soi_id"], fields["seq"], r["sched_id"]):
                            self.writes.append(("update_409", table, {"filter": filter_query, **fields}))
                            return False          # UNIQUE(soi_id, seq) 위반 → PostgREST 409 → db.update False
            return super().update(table, filter_query, fields)

        def insert(self, table, records):
            if table == "so_delivery_schedule":
                for r in records:
                    if self._dup(r["soi_id"], r["seq"], None):
                        raise RuntimeError("so_delivery_schedule insert 409: duplicate key (soi_id, seq)")
                n = 0
                for r in records:
                    self._seq["so_delivery_schedule"] = max(
                        [self._seq.get("so_delivery_schedule", 0)]
                        + [int(x["sched_id"]) for x in self.tables[table]]) + 1
                    row = {"sched_id": self._seq["so_delivery_schedule"], **r}
                    self.tables[table].append(row)
                    self.writes.append(("insert", table, dict(row)))
                    n += 1
                return n
            return super().insert(table, records)

        def delete(self, table, filter_query):
            self._assert_dash("delete", table)
            rows = self._rows(table, filter_query)
            ids = {id(r) for r in rows}
            self.tables[table] = [r for r in self.tables[table] if id(r) not in ids]
            self.writes.append(("delete", table, {"filter": filter_query, "n": len(rows)}))
            return len(rows)

    m = _M()
    total = sum(q for _, _, _, q, _ in rounds)
    done = sum(d for *_, d in rounds)
    m.seed(so_id=101, so_number="PO-SCH", lines=[(SOI, total, done, total - done, "PARTIAL" if done else "PENDING")],
           rounds=[])
    m.tables["so_delivery_schedule"] = [
        {"sched_id": sid, "so_id": 101, "soi_id": SOI, "due_date": due, "seq": seq, "qty": q,
         "delivered_qty": d, "note": None} for sid, due, seq, q, d in rounds]
    return m


def _open(monkeypatch, m):
    import db as _dbmod
    from streamlit.testing.v1 import AppTest
    m.install(monkeypatch, _dbmod)
    at = AppTest.from_file(APP_FILE, default_timeout=90)
    at.secrets["supabase"] = {"url": "https://mock.local", "anon_key": "a", "service_role_key": "s"}
    at.secrets["auth"] = {"disabled": True}
    at.run()
    goto(at, "so", "sched")
    at.session_state["sch_view_next"] = "납기 입력"
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def _ed_key(m):
    rows = sorted((str(r["due_date"])[:10], float(r["qty"])) for r in m.tables["so_delivery_schedule"]
                  if int(r["soi_id"]) == SOI)
    return f"sch_ed_{SOI}_{len(rows)}_{hash(tuple(rows)) % 99999}_0"


def _save(at, m, **state):
    at.session_state[_ed_key(m)] = {"edited_rows": {}, "added_rows": [], "deleted_rows": [], **state}
    at.run()
    at.button(key=f"sch_save_{SOI}").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]


def _sched(m):
    return sorted(((r["sched_id"], str(r["due_date"])[:10], int(r["seq"]), float(r["qty"]),
                    float(r.get("delivered_qty") or 0)) for r in m.tables["so_delivery_schedule"]
                   if int(r["soi_id"]) == SOI), key=lambda x: x[2])


def _flash(at):
    return [str(s.value) for s in at.success] + [str(t.value) for t in at.toast]


def _errors(at):
    return [str(e.value) for e in at.error]


# ── A(후보 27) 재현: 중간 회차 삭제 → 뒤 회차 번호가 앞으로 당겨질 때 UNIQUE 충돌 ──
def test_a_delete_middle_round_renumbers_and_saves_qty(monkeypatch):
    m = _sched_mock([(1, "2026-11-10", 1, 100, 0), (2, "2026-11-20", 2, 100, 0), (3, "2026-11-30", 3, 100, 0)])
    at = _open(monkeypatch, m)
    _save(at, m, deleted_rows=[1], edited_rows={2: {"수량": 150}})
    assert _sched(m) == [(1, "2026-11-10", 1, 100.0, 0.0), (3, "2026-11-30", 2, 150.0, 0.0)], \
        "11-30 회차가 2번·수량 150 으로 저장(sched_id 3 유지)"
    assert not [w for w in m.writes if w[0] in ("update_409", "update_false")]


def test_a_insert_earlier_date_shifts_all_and_keeps_ids(monkeypatch):
    m = _sched_mock([(1, "2026-11-10", 1, 100, 0), (2, "2026-11-20", 2, 100, 0)])
    at = _open(monkeypatch, m)
    _save(at, m, added_rows=[{"납기": "2026-11-05", "수량": 50}])
    s = _sched(m)
    assert [(x[1], x[2], x[3]) for x in s] == [("2026-11-05", 1, 50.0), ("2026-11-10", 2, 100.0),
                                              ("2026-11-20", 3, 100.0)]
    assert [x[0] for x in s][1:] == [1, 2], "같은 날짜 회차는 sched_id 유지(전표 회차 연결 보존)"
    assert not [w for w in m.writes if w[0] in ("update_409", "update_false")]
    assert any("저장 완료 — 3개 회차" in f for f in _flash(at))


def test_a_same_date_merge_keeps_id_and_delivered(monkeypatch):
    m = _sched_mock([(1, "2026-11-10", 1, 100, 100), (2, "2026-11-20", 2, 100, 0)])
    at = _open(monkeypatch, m)
    _save(at, m, added_rows=[{"납기": "2026-11-10", "수량": 30}])
    assert _sched(m) == [(1, "2026-11-10", 1, 130.0, 100.0), (2, "2026-11-20", 2, 100.0, 0.0)], \
        "같은 납기 병합 — sched_id 1 유지, 납품완료 승계"


def test_a_partial_failure_stops_without_flash(monkeypatch):
    m = _sched_mock([(1, "2026-11-10", 1, 100, 0), (2, "2026-11-20", 2, 100, 0), (3, "2026-11-30", 3, 100, 0)])
    at = _open(monkeypatch, m)
    m.false_after = 2            # 첫 schedule update 만 성공, 두 번째부터 False
    _save(at, m, added_rows=[{"납기": "2026-11-05", "수량": 50}])
    errs = _errors(at)
    assert any("저장 중단" in e and "1단계(임시 번호) 2번째" in e and "이미 반영: 임시 번호 1건" in e
               for e in errs), errs
    assert not any("저장 완료" in f for f in _flash(at)), "플래시 없음"
    assert not [w for w in m.writes if w[0] == "insert"], "이후 쓰기 없음(새 회차 insert 안 함)"
    n_false = len([w for w in m.writes if w[0] == "update_false"])
    assert n_false == 1, "실패 뒤 더 시도하지 않음"
    m.false_after = None         # 다시 저장하면 임시 번호까지 정리
    m.n_sched_update = 0
    at.session_state["sch_ed_nonce"] = 0
    _save(at, m, added_rows=[{"납기": "2026-11-05", "수량": 50}])
    assert [(x[1], x[2]) for x in _sched(m)] == [("2026-11-05", 1), ("2026-11-10", 2), ("2026-11-20", 3),
                                                ("2026-11-30", 4)]


def test_a_no_edit_save_writes_no_seq_moves(monkeypatch):
    m = _sched_mock([(1, "2026-11-10", 1, 100, 0), (2, "2026-11-20", 2, 100, 0)])
    at = _open(monkeypatch, m)
    _save(at, m)
    assert not [w for w in m.writes if w[0] == "update" and w[2].get("seq", 0) >= 1000], "번호가 그대로면 임시 번호 없음"
    assert _sched(m) == [(1, "2026-11-10", 1, 100.0, 0.0), (2, "2026-11-20", 2, 100.0, 0.0)]


# ── 순수 함수 ──
def test_plan_sched_writes_order_and_tmp():
    from utils.sched_save import plan_sched_writes, TMP_BASE
    old = [{"sched_id": 1, "due_date": "2026-11-10", "seq": 1}, {"sched_id": 2, "due_date": "2026-11-20", "seq": 2},
           {"sched_id": 3, "due_date": "2026-11-30", "seq": 3}]
    keep = [{"due_date": "2026-11-05", "seq": 1, "qty": 5, "note": None, "delivered_qty": 0},
            {"due_date": "2026-11-10", "seq": 2, "qty": 10, "note": "a", "delivered_qty": 0},
            {"due_date": "2026-11-30", "seq": 3, "qty": 30, "note": None, "delivered_qty": 7}]
    p = plan_sched_writes(old, keep)
    assert p["delete"] == [2] and [g["sched_id"] for g in p["gone"]] == [2]
    assert p["phase1"] == [(1, TMP_BASE + 1)], "번호가 바뀌는 유지 회차만 임시 번호(3 은 3 그대로)"
    assert p["phase2"] == [(1, {"qty": 10, "note": "a", "seq": 2, "delivered_qty": 0}),
                           (3, {"qty": 30, "note": None, "seq": 3, "delivered_qty": 7})]
    assert [r["due_date"] for r in p["insert"]] == ["2026-11-05"]


def test_plan_sched_writes_recovers_from_tmp_numbers():
    """중단돼 임시 번호(1000+)가 남은 회차도 다음 저장이 최종 번호로 — 임시끼리 겹치지 않는다."""
    from utils.sched_save import plan_sched_writes, TMP_BASE
    old = [{"sched_id": 1, "due_date": "2026-11-10", "seq": TMP_BASE + 1},
           {"sched_id": 2, "due_date": "2026-11-20", "seq": 1}]
    keep = [{"due_date": "2026-11-10", "seq": 1, "qty": 1, "note": None, "delivered_qty": 0},
            {"due_date": "2026-11-20", "seq": 2, "qty": 1, "note": None, "delivered_qty": 0}]
    p = plan_sched_writes(old, keep)
    tmps = [t for _, t in p["phase1"]]
    assert sorted(tmps) == [TMP_BASE + 1, TMP_BASE + TMP_BASE + 1] and len(set(tmps)) == 2


# ── B(후보 26) 납품된 회차 삭제 차단 ──
def test_b_delete_delivered_round_blocked_before_writes(monkeypatch):
    m = _sched_mock([(1, "2026-11-10", 1, 100, 60), (2, "2026-11-20", 2, 100, 0)])
    at = _open(monkeypatch, m)
    before = _sched(m)
    _save(at, m, deleted_rows=[0])
    assert any("납품된 회차(2026-11-10 기납품 60개)는 삭제할 수 없습니다" in e for e in _errors(at)), _errors(at)
    assert _sched(m) == before and not [w for w in m.writes if w[1] == "so_delivery_schedule"], "쓰기 0"
    assert not any("저장 완료" in f for f in _flash(at))


def test_b_date_change_of_delivered_round_blocked(monkeypatch):
    m = _sched_mock([(1, "2026-11-10", 1, 100, 60), (2, "2026-11-20", 2, 100, 0)])
    at = _open(monkeypatch, m)
    _save(at, m, edited_rows={0: {"납기": "2026-11-12"}})
    assert any("날짜를 바꾸려면" in e for e in _errors(at))
    assert not [w for w in m.writes if w[1] == "so_delivery_schedule"]


def test_b_reduce_delivered_round_to_delivered_qty_allowed(monkeypatch):
    m = _sched_mock([(1, "2026-11-10", 1, 100, 60), (2, "2026-11-20", 2, 100, 0)])
    at = _open(monkeypatch, m)
    _save(at, m, edited_rows={0: {"수량": 60}})
    assert _sched(m) == [(1, "2026-11-10", 1, 60.0, 60.0), (2, "2026-11-20", 2, 100.0, 0.0)]
    assert any("저장 완료" in f for f in _flash(at))


# ── C(후보 28) 전표 정정 표 수주번호 열 ──
from tests.test_shipment_revision_flow import rev_db  # noqa: E402,F401  (fixture 재사용)


def test_c_revision_table_shows_so_number(rev_db, monkeypatch):
    from tests import test_shipment_revision_flow as RV
    from tests.test_so_close_revision import _seed_two_lines, _patch_header
    _seed_two_lines()
    _patch_header(monkeypatch, "PARTIAL")
    at = RV._pick_confirmed(RV._open())
    df = next(d.value for d in at.dataframe if "정정 수량" in list(d.value.columns))
    assert list(df.columns)[:2] == ["품번", "수주번호"]
    assert "SO-100" in list(df["수주번호"])
