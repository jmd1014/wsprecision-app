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
        raise_after = None          # n 번째 schedule update 부터 예외(통신 오류 흉내)
        n_sched_update = 0
        delete_mode = None          # "short"(1건 덜 지움 — 다른 사용자가 먼저 지움) · "raise"
        insert_raise = False

        def _dup(self, soi, seq, sid):
            return any(int(r["soi_id"]) == int(soi) and int(r["seq"]) == int(seq) and r["sched_id"] != sid
                       for r in self.tables["so_delivery_schedule"])

        def update(self, table, filter_query, fields):
            if table == "so_delivery_schedule":
                self.n_sched_update += 1
                if self.raise_after is not None and self.n_sched_update >= self.raise_after:
                    self.writes.append(("update_raise", table, {"filter": filter_query, **fields}))
                    raise RuntimeError("ConnectionError: 시뮬레이션")
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
                if self.insert_raise:
                    self.writes.append(("insert_raise", table, {}))
                    raise RuntimeError("so_delivery_schedule insert 500: 시뮬레이션")
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
            if self.delete_mode == "raise":
                self.writes.append(("delete_raise", table, {"filter": filter_query}))
                raise RuntimeError("ReadTimeout: 시뮬레이션")
            rows = self._rows(table, filter_query)
            if self.delete_mode == "short":
                rows = rows[1:]
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
    assert p["phase1"] == [(1, TMP_BASE)], "번호가 바뀌는 유지 회차만 임시 번호(3 은 3 그대로)"
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
    assert len(set(tmps)) == 2 and min(tmps) > TMP_BASE + 1, "임시 영역은 남은 임시 번호보다 위"


def test_plan_codex1_interrupted_tmp_does_not_collide():
    """Codex 1차 H: A(11-10)=2·B(11-20)=1002 로 중단된 뒤 두 회차만 다시 저장 — A 2→임시 가 B 의 1002 와 겹치면 안 됨."""
    from utils.sched_save import plan_sched_writes
    old = [{"sched_id": 1, "due_date": "2026-11-10", "seq": 2}, {"sched_id": 2, "due_date": "2026-11-20", "seq": 1002}]
    keep = [{"due_date": "2026-11-10", "seq": 1, "qty": 1, "note": None, "delivered_qty": 0},
            {"due_date": "2026-11-20", "seq": 2, "qty": 1, "note": None, "delivered_qty": 0}]
    p = plan_sched_writes(old, keep)
    occupied = {1002, 2}
    for sid, t in p["phase1"]:
        assert t not in occupied, (sid, t)
        occupied.add(t)


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


def test_a_codex1_resave_after_interrupted_phase2(monkeypatch):
    """화면: 앞 날짜 삽입 저장이 2단계에서 중단(A=2·B=임시) → 새로고침 뒤 두 회차만 다시 저장해도 충돌 없이 정리."""
    m = _sched_mock([(1, "2026-11-10", 2, 100, 0), (2, "2026-11-20", 1002, 100, 0)])
    at = _open(monkeypatch, m)
    _save(at, m)
    assert not [w for w in m.writes if w[0] in ("update_409", "update_false")], m.writes
    assert [(x[1], x[2]) for x in _sched(m)] == [("2026-11-10", 1), ("2026-11-20", 2)]



# ── r2(검토 세션 2026-11-05) ③ — 단계별 실패·예외, 날짜순≠번호순, 중복 날짜 + 납품, D 무변화 ──
def _sched_writes(m):
    return [w for w in m.writes if w[1] == "so_delivery_schedule"]


def _three():
    return _sched_mock([(1, "2026-11-10", 1, 100, 0), (2, "2026-11-20", 2, 100, 0), (3, "2026-11-30", 3, 100, 0)])


def test_r2_phase2_false_stops_with_applied_list(monkeypatch):
    m = _three()
    at = _open(monkeypatch, m)
    m.false_after = 2            # 임시 번호(1건) 뒤 2단계 첫 update 가 False
    _save(at, m, deleted_rows=[1])
    e = " ".join(_errors(at))
    assert "2단계(번호·수량) 1번째 회차 저장 실패" in e and "이미 반영: 삭제 1건 · 임시 번호 1건" in e, e
    assert not any("저장 완료" in f for f in _flash(at))
    assert [w[0] for w in _sched_writes(m)][-1] == "update_false", "실패 뒤 쓰기 없음"


def test_r2_phase1_exception_reports_uncertain(monkeypatch):
    m = _three()
    at = _open(monkeypatch, m)
    m.raise_after = 1
    _save(at, m, deleted_rows=[1])
    e = " ".join(_errors(at))
    assert "1단계(임시 번호) 1번째 회차 저장 실패" in e and "반영 여부가 불확실" in e and "이미 반영: 삭제 1건" in e, e
    assert [w[0] for w in _sched_writes(m)][-1] == "update_raise"


def test_r2_insert_exception_stops_without_flash(monkeypatch):
    m = _sched_mock([(1, "2026-11-10", 1, 100, 0)])
    at = _open(monkeypatch, m)
    m.insert_raise = True
    _save(at, m, added_rows=[{"납기": "2026-11-20", "수량": 50}])
    e = " ".join(_errors(at))
    assert "새 회차 1건 추가 실패" in e and "이미 반영: 회차 1 저장" in e, e
    assert not any("저장 완료" in f for f in _flash(at))


@pytest.mark.parametrize("mode", ["short", "raise"])
def test_r2_delete_partial_or_exception_stops_before_updates(monkeypatch, mode):
    m = _three()
    at = _open(monkeypatch, m)
    m.delete_mode = mode
    _save(at, m, deleted_rows=[1])
    e = " ".join(_errors(at))
    if mode == "short":
        assert "회차 삭제 1건 중 0건 반영(다른 사용자가 먼저 지웠을 수 있음)" in e and "아무것도 바뀌지 않았습니다" in e, e
    else:
        assert "회차 삭제 실패" in e and "반영 여부가 불확실" in e, e
    assert not [w for w in _sched_writes(m) if w[0].startswith("update") or w[0].startswith("insert")], \
        "삭제 실패 뒤 update·insert 0"
    assert not any("저장 완료" in f for f in _flash(at))


def test_r2_date_order_differs_from_seq_order(monkeypatch):
    m = _sched_mock([(1, "2026-11-10", 2, 100, 0), (2, "2026-11-20", 1, 100, 0)])
    at = _open(monkeypatch, m)
    _save(at, m)
    assert not [w for w in m.writes if w[0] in ("update_409", "update_false")]
    assert [(x[0], x[1], x[2]) for x in _sched(m)] == [(1, "2026-11-10", 1), (2, "2026-11-20", 2)]


def test_r2_duplicate_date_keeps_delivered_round(monkeypatch):
    """예전 중복 저장(같은 날짜 2행) — 납품된 행(seq 2)을 유지하고 미납품 행을 지운다(B 에 걸리지 않음)."""
    m = _sched_mock([(1, "2026-11-10", 1, 50, 0), (2, "2026-11-10", 2, 50, 50), (3, "2026-11-20", 3, 100, 0)])
    at = _open(monkeypatch, m)
    _save(at, m)
    assert not _errors(at), _errors(at)
    s = _sched(m)
    assert [(x[0], x[1], x[2], x[3], x[4]) for x in s] == [(2, "2026-11-10", 1, 100.0, 50.0),
                                                           (3, "2026-11-20", 2, 100.0, 0.0)]


def test_r2_duplicate_date_both_delivered_blocked(monkeypatch):
    m = _sched_mock([(1, "2026-11-10", 1, 50, 30), (2, "2026-11-10", 2, 50, 20)])
    at = _open(monkeypatch, m)
    _save(at, m)
    assert any("납품된 회차(2026-11-10 기납품 20개)는 삭제할 수 없습니다" in e for e in _errors(at)), _errors(at)
    assert not _sched_writes(m), "쓰기 전 차단"


def test_r2_d_no_ship_no_html_identical_to_previous_version():
    """D: ship_no 가 없으면 이전 버전(5410711)과 같은 HTML. 옛 커밋이 없는 얕은 클론(CI)에서는 건너뜀."""
    import subprocess
    import types
    root = os.path.dirname(os.path.dirname(__file__))
    try:
        src = subprocess.run(["git", "show", "5410711:utils/statement_generator.py"], cwd=root,
                             capture_output=True, check=True).stdout.decode("utf-8")
    except Exception:
        pytest.skip("옛 커밋 없음(얕은 클론)")
    old = types.ModuleType("old_statement_generator")
    old.__file__ = os.path.join(root, "utils", "statement_generator.py")   # 로고 경로 등
    exec(compile(src, "old_statement_generator", "exec"), old.__dict__)
    from utils import statement_generator as new
    from tests.test_statement_generator import BATCH, VMAP
    assert new.transaction_statements_html(BATCH, VMAP) == old.transaction_statements_html(BATCH, VMAP)
    assert new.transaction_statements_html(BATCH, VMAP, rev_label="정정본 v2") == \
        old.transaction_statements_html(BATCH, VMAP, rev_label="정정본 v2")
    assert new.delivery_list_html(BATCH, draft=True) == old.delivery_list_html(BATCH, draft=True)
