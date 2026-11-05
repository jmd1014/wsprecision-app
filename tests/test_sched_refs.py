# -*- coding: utf-8 -*-
"""납기 입력 핫픽스 1(2026-11-05) — 회차 삭제 전 전표 참조 확인(_sched_refs_block) 회귀.

cccae4f 는 shipment_allocations 에서 없는 열(shipment_id)을 select → 운영에서 항상 400 → 회차 삭제가 든 저장·
전체 삭제가 모두 차단. 테스트 목이 열을 검사하지 않아 못 잡았다. 여기서는
 (1) 화면 전체 경로: 운영 컬럼만 허용하는 목(test_sched_save.SHIP_PROD_COLS)으로 참조 없는 회차 삭제가 저장되는지,
 (2) 조회 열 계약: sched_save.REFS_SELECT 의 열이 저장소 마이그레이션의 테이블 정의에 있는지,
 (3) 분류·문구 순수 함수(sched_refs_message)·조회 함수(sched_refs_block)의 경우별 결과.
"""
import os
import re
import sys
import importlib.util

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)
MIG = os.path.join(ROOT, "supabase", "migrations")

_HAS_ST = importlib.util.find_spec("streamlit") is not None


# ── (1) 화면 전체 경로 — 수정 전 코드에서 실패(재현) ──
@pytest.mark.skipif(not _HAS_ST, reason="streamlit 미설치 — AppTest 불가")
def test_hf1_delete_unreferenced_round_saves_with_prod_columns(monkeypatch):
    from tests.test_sched_save import _three, _open, _save, _errors, _sched, SOI  # noqa: F401
    m = _three()
    at = _open(monkeypatch, m)
    _save(at, m, deleted_rows=[1])
    assert not [w for w in m.writes if w[0] == "fetch_400"], [w for w in m.writes if w[0] == "fetch_400"]
    assert not any("연결된 전표를 확인하지 못했습니다" in e for e in _errors(at)), _errors(at)
    assert len(_sched(m)) == 2, _sched(m)


@pytest.mark.skipif(not _HAS_ST, reason="streamlit 미설치 — AppTest 불가")
def test_hf1_bulk_delete_enabled_without_refs_with_prod_columns(monkeypatch):
    from tests.test_sched_save import _sched_mock, _open, SOI
    m = _sched_mock([(1, "2026-11-10", 1, 100, 0)])
    at = _open(monkeypatch, m)
    b = at.button(key=f"sch_reset_{SOI}_ask")
    assert not b.disabled, b.proto.help
    assert not [w for w in m.writes if w[0] == "fetch_400"]


# ── (2) 조회 열 계약 — 마이그레이션 정의와 대조 ──
_SKIP_ITEM = re.compile(r"^(primary|unique|foreign|check|constraint|exclude)\b", re.I)


def _split_top(body):
    out, depth, cur = [], 0, ""
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return out


def _strip_comments(sql):
    return re.sub(r"--[^\n]*", "", sql)


def migration_columns(table):
    """저장소 supabase/migrations 의 CREATE TABLE + ALTER TABLE … ADD COLUMN 으로 table 의 열 집합."""
    cols = set()
    for fn in sorted(os.listdir(MIG)):
        if not fn.endswith(".sql"):
            continue
        sql = _strip_comments(open(os.path.join(MIG, fn), encoding="utf-8").read())
        for mt in re.finditer(r"create\s+table\s+(?:if\s+not\s+exists\s+)?(?:public\.)?(\w+)\s*\(", sql, re.I):
            if mt.group(1).lower() != table:
                continue
            i, depth = mt.end(), 1
            while depth and i < len(sql):
                depth += {"(": 1, ")": -1}.get(sql[i], 0)
                i += 1
            for item in _split_top(sql[mt.end():i - 1]):
                item = item.strip()
                if item and not _SKIP_ITEM.match(item):
                    cols.add(item.split()[0].strip('"').lower())
        for ma in re.finditer(r"alter\s+table\s+(?:if\s+exists\s+)?(?:only\s+)?(?:public\.)?(\w+)\b([^;]*);", sql, re.I):
            if ma.group(1).lower() != table:
                continue
            for c in re.findall(r"add\s+column\s+(?:if\s+not\s+exists\s+)?\"?(\w+)", ma.group(2), re.I):
                cols.add(c.lower())
    return cols


# 운영 information_schema(2026-11-05) — 파서가 제대로 읽는지 확인용(운영 ⊆ 마이그레이션)
_PROD = {
    "shipment_allocations": {"alloc_id", "si_id", "sched_id", "qty", "created_at"},
    "shipment_items": {"si_id", "shipment_id", "soi_id", "so_id", "sched_id", "product_id", "pn", "customer_pn",
                       "item_name", "customer", "so_number", "qty", "unit", "unit_price"},
    "shipments": {"shipment_id", "ship_no", "ship_date", "status", "remark", "created_by", "created_at",
                  "confirmed_at", "rev_no", "revised_at", "cancelled_at", "cancel_reason"},
}


@pytest.mark.parametrize("table", sorted(_PROD))
def test_hf1_migration_parser_sees_prod_columns(table):
    got = migration_columns(table)
    assert _PROD[table] <= got, sorted(_PROD[table] - got)


def test_hf1_refs_select_columns_exist_in_migrations():
    from utils.sched_save import REFS_SELECT
    assert set(REFS_SELECT) == {"shipment_allocations", "shipment_items", "shipments"}
    for table, sel in REFS_SELECT.items():
        cols = {c.strip() for c in sel.split(",")}
        missing = cols - migration_columns(table)
        assert not missing, f"{table}: 마이그레이션에 없는 열 {sorted(missing)}"


def test_hf1_contract_catches_old_select():
    """계약 검사가 cccae4f 의 잘못된 select(shipment_allocations.shipment_id)를 잡는지."""
    assert "shipment_id" not in migration_columns("shipment_allocations")


# ── (3) 분류·문구 순수 함수 ──
def _ships():
    return [{"shipment_id": 70, "ship_no": "SH-20261101-01", "status": "CONFIRMED"},
            {"shipment_id": 71, "ship_no": "SH-20261105-01", "status": "DRAFT"},
            {"shipment_id": 72, "ship_no": "SH-20261020-02", "status": "CANCELLED"},
            {"shipment_id": 74, "ship_no": "SH-20261010-04", "status": "CONFIRMED"}]


def test_hf1_msg_no_refs():
    from utils.sched_save import sched_refs_message
    assert sched_refs_message([], [], [], _ships()) is None


def test_hf1_msg_confirmed_via_alloc_line():
    from utils.sched_save import sched_refs_message
    msg = sched_refs_message([{"sched_id": 2, "si_id": 800}], [],
                             [{"si_id": 800, "sched_id": None, "shipment_id": 70}], _ships())
    assert msg == "확정 전표 SH-20261101-01 에 연결된 회차라 삭제할 수 없습니다.", msg


def test_hf1_msg_draft():
    from utils.sched_save import sched_refs_message
    msg = sched_refs_message([], [{"si_id": 900, "sched_id": 2, "shipment_id": 71}], [], _ships())
    assert msg == "작성중 전표 SH-20261105-01 가 이 회차를 가리킵니다 — 전표를 먼저 정리하세요.", msg


def test_hf1_msg_other_status():
    """확정 전표 라인인데 충당 행이 없음(053 이전 등) → "전표 …" 차단."""
    from utils.sched_save import sched_refs_message
    msg = sched_refs_message([], [{"si_id": 901, "sched_id": 2, "shipment_id": 74}], [], _ships())
    assert msg == "전표 SH-20261010-04 가 이 회차를 가리킵니다.", msg


def test_hf1_msg_mixed_and_dedup():
    from utils.sched_save import sched_refs_message
    allocs = [{"sched_id": 2, "si_id": 800}, {"sched_id": 3, "si_id": 800}]
    items = [{"si_id": 800, "sched_id": 2, "shipment_id": 70},       # 충당된 확정 라인 — 확정에만
             {"si_id": 900, "sched_id": 3, "shipment_id": 71},
             {"si_id": 901, "sched_id": 3, "shipment_id": 74},
             {"si_id": 902, "sched_id": 3, "shipment_id": 72}]       # 취소 — 언급 안 함
    msg = sched_refs_message(allocs, items, [], _ships())
    assert msg == ("확정 전표 SH-20261101-01 에 연결된 회차라 삭제할 수 없습니다 · "
                   "작성중 전표 SH-20261105-01 가 이 회차를 가리킵니다 — 전표를 먼저 정리하세요 · "
                   "전표 SH-20261010-04 가 이 회차를 가리킵니다."), msg


def test_hf1_msg_alloc_line_missing_still_blocks():
    from utils.sched_save import sched_refs_message
    msg = sched_refs_message([{"sched_id": 2, "si_id": 999}], [], [], _ships())
    assert msg and "확정 전표 미상(전표 라인 999)" in msg, msg


def test_hf1_msg_shipment_row_missing_uses_id():
    from utils.sched_save import sched_refs_message
    msg = sched_refs_message([{"sched_id": 2, "si_id": 800}], [],
                             [{"si_id": 800, "sched_id": None, "shipment_id": 77}], _ships())
    assert msg == "확정 전표 77 에 연결된 회차라 삭제할 수 없습니다.", msg


# ── (3b) 조회 함수 — 운영 컬럼만 허용하는 가짜 fetch 로 전체 경로 ──
class _FakeFetch:
    def __init__(self, tables, limit_hit=None, raise_for=None, raise_if=None, limit_if=None):
        self.tables, self.calls, self.limit_hit, self.raise_for = tables, [], limit_hit, raise_for
        self.raise_if, self.limit_if = raise_if, limit_if

    def __call__(self, table, select="*", filter_query="", limit=1000, cache=None):
        self.calls.append((table, select, filter_query, limit, cache))
        if table == self.raise_for or (self.raise_if and self.raise_if(table, filter_query)):
            raise RuntimeError("ReadTimeout 시뮬레이션")
        want = [c.strip() for c in select.split(",")]
        bad = [c for c in want if c not in _PROD[table]]
        if bad:
            raise RuntimeError(f"{table} fetch 400: column {table}.{bad[0]} does not exist")
        m = re.match(r"(\w+)=in\.\(([^)]*)\)$", filter_query)
        col, vals = m.group(1), {int(x) for x in m.group(2).split(",")}
        rows = [{c: r.get(c) for c in want} for r in self.tables.get(table, []) if r.get(col) in vals]
        if self.limit_hit == table or (self.limit_if and self.limit_if(table, filter_query)):
            rows = (rows * limit)[:limit] if rows else [{c: None for c in want}] * limit
        return rows[:limit]


def _db():
    return {"shipment_allocations": [{"alloc_id": 1, "si_id": 800, "sched_id": 2, "qty": 5}],
            "shipment_items": [{"si_id": 800, "shipment_id": 70, "sched_id": None},
                               {"si_id": 900, "shipment_id": 71, "sched_id": 3}],
            "shipments": _ships()}


def test_hf1_block_no_ids_no_calls():
    from utils.sched_save import sched_refs_block
    f = _FakeFetch(_db())
    assert sched_refs_block([None], f) is None and not f.calls


def test_hf1_block_unreferenced_passes():
    from utils.sched_save import sched_refs_block
    f = _FakeFetch(_db())
    assert sched_refs_block([5, 6], f) is None
    assert all(c[4] is False for c in f.calls), "cache=False"


def test_hf1_block_alloc_resolves_ship_via_line():
    from utils.sched_save import sched_refs_block
    f = _FakeFetch(_db())
    msg = sched_refs_block([2], f)
    assert msg == "확정 전표 SH-20261101-01 에 연결된 회차라 삭제할 수 없습니다.", msg
    assert ("shipment_items", "si_id,sched_id,shipment_id", "si_id=in.(800)", 200, False) in f.calls


def test_hf1_block_draft_and_alloc():
    from utils.sched_save import sched_refs_block
    msg = sched_refs_block([2, 3], _FakeFetch(_db()))
    assert "확정 전표 SH-20261101-01" in msg and "작성중 전표 SH-20261105-01" in msg, msg


@pytest.mark.parametrize("table", ["shipment_allocations", "shipment_items", "shipments"])
def test_hf1_block_lookup_fail_closed(table):
    from utils.sched_save import sched_refs_block
    msg = sched_refs_block([2, 3], _FakeFetch(_db(), raise_for=table))
    assert msg and msg.startswith("연결된 전표를 확인하지 못했습니다"), msg


@pytest.mark.parametrize("table", ["shipment_allocations", "shipment_items"])
def test_hf1_block_limit_reached_blocks(table):
    from utils.sched_save import sched_refs_block, REFS_LIMIT
    msg = sched_refs_block([2, 3], _FakeFetch(_db(), limit_hit=table))
    assert msg and f"{REFS_LIMIT}행" in msg, msg


# ── 핫픽스 2(2026-11-05): 취소(CANCELLED) 전표 라인 참조는 차단 사유가 아니다 ──
def test_hf2_msg_cancelled_only_is_none():
    from utils.sched_save import sched_refs_message
    items = [{"si_id": 902, "sched_id": 2, "shipment_id": 72}]
    assert sched_refs_message([], items, [], _ships()) is None


def test_hf2_msg_cancelled_plus_draft_mentions_draft_only():
    from utils.sched_save import sched_refs_message
    items = [{"si_id": 902, "sched_id": 2, "shipment_id": 72}, {"si_id": 900, "sched_id": 2, "shipment_id": 71}]
    msg = sched_refs_message([], items, [], _ships())
    assert msg == "작성중 전표 SH-20261105-01 가 이 회차를 가리킵니다 — 전표를 먼저 정리하세요.", msg


def test_hf2_msg_cancelled_plus_alloc_blocks_confirmed():
    from utils.sched_save import sched_refs_message
    items = [{"si_id": 902, "sched_id": 2, "shipment_id": 72}]
    msg = sched_refs_message([{"sched_id": 2, "si_id": 800}], items,
                             [{"si_id": 800, "sched_id": None, "shipment_id": 70}], _ships())
    assert msg == "확정 전표 SH-20261101-01 에 연결된 회차라 삭제할 수 없습니다.", msg


def test_hf2_msg_cancelled_plus_confirmed_without_alloc_blocks():
    from utils.sched_save import sched_refs_message
    items = [{"si_id": 902, "sched_id": 2, "shipment_id": 72}, {"si_id": 901, "sched_id": 2, "shipment_id": 74}]
    msg = sched_refs_message([], items, [], _ships())
    assert msg == "전표 SH-20261010-04 가 이 회차를 가리킵니다.", msg


def test_hf2_msg_alloc_on_cancelled_shipment_still_blocks():
    """충당 행이 있으면 전표 상태와 무관하게 보수적으로 차단(운영엔 취소 전표 충당 0 — 지시문 A)."""
    from utils.sched_save import sched_refs_message
    msg = sched_refs_message([{"sched_id": 2, "si_id": 902}], [],
                             [{"si_id": 902, "sched_id": None, "shipment_id": 72}], _ships())
    assert msg == "확정 전표 SH-20261020-02 에 연결된 회차라 삭제할 수 없습니다.", msg


def test_hf2_msg_alloc_line_loaded_via_items_keeps_label():
    """충당 행의 라인이 sched_id 조회(items)로만 들어온 취소 전표 라인이어도 라벨은 전표번호(미상 아님)."""
    from utils.sched_save import sched_refs_message
    msg = sched_refs_message([{"sched_id": 2, "si_id": 902}], [{"si_id": 902, "sched_id": 2, "shipment_id": 72}],
                             [], _ships())
    assert msg == "확정 전표 SH-20261020-02 에 연결된 회차라 삭제할 수 없습니다.", msg


def test_hf2_msg_unknown_shipment_row_blocks():
    """전표 행을 못 찾음(상태 미상) → 차단 유지."""
    from utils.sched_save import sched_refs_message
    msg = sched_refs_message([], [{"si_id": 903, "sched_id": 2, "shipment_id": 99}], [], _ships())
    assert msg == "전표 99 가 이 회차를 가리킵니다.", msg


def test_hf2_block_cancelled_only_passes_via_fetch():
    from utils.sched_save import sched_refs_block
    db = _db()
    db["shipment_items"].append({"si_id": 902, "shipment_id": 72, "sched_id": 5})
    assert sched_refs_block([5], _FakeFetch(db)) is None


# ── 핫픽스 1 Codex REQUIRED TESTS ──
def test_hf2_block_supplement_lookup_only_fails_closed():
    """첫 shipment_items(sched_id) 조회는 성공, 보충 조회(si_id)만 예외 → 차단 문구."""
    from utils.sched_save import sched_refs_block
    f = _FakeFetch(_db(), raise_if=lambda t, q: t == "shipment_items" and q.startswith("si_id="))
    msg = sched_refs_block([2], f)
    assert msg and msg.startswith("연결된 전표를 확인하지 못했습니다"), msg
    assert any(c[0] == "shipment_items" and c[2].startswith("sched_id=") for c in f.calls), "첫 조회는 성공"


@pytest.mark.parametrize("which", ["supplement", "shipments"])
def test_hf2_block_supplement_or_shipments_limit_blocks(which):
    from utils.sched_save import sched_refs_block, REFS_LIMIT
    pred = ((lambda t, q: t == "shipment_items" and q.startswith("si_id=")) if which == "supplement"
            else (lambda t, q: t == "shipments"))
    msg = sched_refs_block([2], _FakeFetch(_db(), limit_if=pred))
    assert msg and f"{REFS_LIMIT}행" in msg, msg


# ── 화면 경로(운영 컬럼 목) ──
def _cancel_ref(m, sched_id):
    from tests.test_sched_save import SOI
    m.tables["shipment_items"].append({"si_id": 950, "shipment_id": 75, "soi_id": SOI, "so_id": 101,
                                       "sched_id": sched_id, "qty": 5})
    m.tables["shipments"].append({"shipment_id": 75, "ship_no": "SH-20261105-09", "ship_date": "2026-11-05",
                                  "status": "CANCELLED"})


@pytest.mark.skipif(not _HAS_ST, reason="streamlit 미설치 — AppTest 불가")
def test_hf2_screen_delete_round_referenced_only_by_cancelled_saves(monkeypatch):
    from tests.test_sched_save import _three, _open, _save, _errors, _sched
    m = _three()
    _cancel_ref(m, 2)
    at = _open(monkeypatch, m)
    _save(at, m, deleted_rows=[1])
    assert not any("SH-20261105-09" in e for e in _errors(at)), _errors(at)
    assert len(_sched(m)) == 2 and 2 not in [x[0] for x in _sched(m)], _sched(m)
    assert [r["sched_id"] for r in m.tables["shipment_items"] if r["si_id"] == 950] == [2], "취소 전표 라인 무변경"


@pytest.mark.skipif(not _HAS_ST, reason="streamlit 미설치 — AppTest 불가")
def test_hf2_screen_bulk_delete_enabled_with_cancelled_ref_only(monkeypatch):
    from tests.test_sched_save import _sched_mock, _open, SOI
    m = _sched_mock([(1, "2026-11-10", 1, 100, 0)])
    _cancel_ref(m, 1)
    at = _open(monkeypatch, m)
    b = at.button(key=f"sch_reset_{SOI}_ask")
    assert not b.disabled, b.proto.help
