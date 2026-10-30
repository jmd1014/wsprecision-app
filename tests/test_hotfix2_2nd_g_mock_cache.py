# -*- coding: utf-8 -*-
"""핫픽스 2 후속 2차 묶음 G — 목 DB 쓰기도 실제 db 처럼 끝에 clear_cache() (2026-10-30).

실제 db.insert/update/update_count/delete/rpc 는 끝에 읽기 캐시를 비운다. 목이 안 비우면
쓰기 뒤 fetch_all 재조회가 이전 결과(전체 결과 캐시)를 읽어 화면 테스트가 거짓 통과할 수 있다.
"""
import pytest

from tests.dash_mock import DashMock


@pytest.fixture()
def mdb(monkeypatch):
    import db
    m = DashMock().install(monkeypatch, db)
    db.clear_cache()
    return m, db


def _parts(db):
    rows, tr = db.fetch_all("dash_parts", pk="id")
    assert tr is False
    return sorted((r["id"], r["name"]) for r in rows)


def test_mock_insert_then_fetch_all_reads_new_row(mdb):
    m, db = mdb
    assert _parts(db) == [(1, "생산"), (2, "품질")]                  # 결과 전체 캐시에 들어감
    db.insert("dash_parts", [{"code": "admin", "name": "관리", "sort_order": 3}])
    assert _parts(db) == [(1, "생산"), (2, "품질"), (3, "관리")]


@pytest.mark.parametrize("op", ["update", "update_count"])
def test_mock_update_then_fetch_all_reads_new_value(mdb, op):
    m, db = mdb
    assert _parts(db)[1] == (2, "품질")
    getattr(db, op)("dash_parts", "id=eq.2", {"name": "품질관리"})
    assert _parts(db)[1] == (2, "품질관리")


def test_mock_update_failure_still_clears_like_real(mdb):
    """실제 update/update_count 는 실패 응답(False·-1)에도 캐시를 비운다 — 목도 같게."""
    m, db = mdb
    _parts(db)
    m.tables["dash_parts"][1]["name"] = "밖에서 바뀜"            # 외부 변경(캐시엔 아직 옛 값)
    m.update_mode = -1
    assert db.update_count("dash_parts", "id=eq.1", {"name": "x"}) == -1
    assert _parts(db)[1] == (2, "밖에서 바뀜")


def test_mock_rpc_success_and_rejection_clear(mdb):
    m, db = mdb
    tid = next(t["id"] for t in m.tables["dash_routine_templates"] if t["assignee_user_ids"])
    seen, _ = db.fetch_all("dash_cards", pk="id")
    assert seen == []
    db.rpc("dash_generate_cards", {"p_template_ids": [tid], "p_work_date": "2026-10-30", "p_shift": "day"})
    seen, _ = db.fetch_all("dash_cards", pk="id")
    assert [c["template_id"] for c in seen] == [tid]
    # 거부(RpcRejected)도 실제 rpc 처럼 비운다
    m.tables["dash_cards"].clear()
    m.rpc_raise = db.RpcRejected("P0001", "bad", 400)
    with pytest.raises(db.RpcRejected):
        db.rpc("dash_generate_cards", {"p_template_ids": [tid], "p_work_date": "2026-10-30", "p_shift": "day"})
    seen, _ = db.fetch_all("dash_cards", pk="id")
    assert seen == []


def test_mock_rpc_unavailable_does_not_clear_like_real(mdb):
    """실제 rpc 는 PGRST202(RpcUnavailable)에서 캐시를 비우지 않는다 — 목도 같게(대조)."""
    m, db = mdb
    _parts(db)
    m.tables["dash_parts"][1]["name"] = "밖에서 바뀜"
    m.rpc_raise = db.RpcUnavailable("dash_generate_cards: 없음")
    with pytest.raises(db.RpcUnavailable):
        db.rpc("dash_generate_cards", {"p_template_ids": [], "p_work_date": "2026-10-30", "p_shift": "day"})
    assert _parts(db)[1] == (2, "품질")                          # 캐시 그대로


# ── r2-3 (Codex L1): db.py 와 다른 두 시점 맞춤 — 대조군 ─────────────────────

def test_mock_empty_insert_does_not_clear_like_real(mdb):
    """db.insert([]) 는 요청 없이 0 — 캐시를 비우지 않는다. 목도 같게."""
    m, db = mdb
    _parts(db)
    m.tables["dash_parts"][1]["name"] = "밖에서 바뀜"
    assert db.insert("dash_parts", []) == 0
    assert _parts(db)[1] == (2, "품질")                          # 캐시 그대로


def test_mock_rpc_pgrst203_rejection_does_not_clear_like_real(mdb):
    """db.rpc 의 PGRST203(오버로드 모호) 거부는 함수가 실행되지 않아 캐시를 비우지 않는다 — 목도 같게."""
    m, db = mdb
    _parts(db)
    m.tables["dash_parts"][1]["name"] = "밖에서 바뀜"
    m.rpc_raise = db.RpcRejected("PGRST203", "ambiguous", 300)
    with pytest.raises(db.RpcRejected):
        db.rpc("dash_generate_cards", {"p_template_ids": [], "p_work_date": "2026-10-30", "p_shift": "day"})
    assert _parts(db)[1] == (2, "품질")
