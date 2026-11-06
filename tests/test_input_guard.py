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

        def insert(self, table, records):
            # 운영처럼 PK 발급(wo_tracking.wo_id·wo_batches.batch_id) — 등록 뒤 연결(wo_batches.wo_id) 검증용(r2 R-3)
            pk = {"wo_tracking": "wo_id", "wo_batches": "batch_id"}.get(table)
            if pk:
                recs = []
                for r in records:
                    self._seq[table] = self._seq.get(table, 0) + 1
                    recs.append({pk: self._seq[table], **r})
                records = recs
            return super().insert(table, records)

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


# ── r2(2026-11-06): 리뷰 REQUIRED TESTS + R-1 탐침으로 찾은 선택 바뀜(D-1·D-2) ──
GONE_92 = ("앞서 고른 품번 HA80-80092 (발주 라인 기준) 이 후보에서 빠졌습니다(휴면 처리 등) — "
           "품번을 다시 확인하세요. 방금 [투입 등록] 을 눌렀다면 등록되지 않았습니다.")   # r2b 문구
WRITE_TABLES = ("wo_tracking", "wo_batches", "inventory_transactions")


def _no_input_writes(m):
    return not [w for w in m.writes if w[0] == "insert" and w[1] in WRITE_TABLES]


def _set_arch(m, pid, v):
    next(p for p in m.tables["products"] if p["product_id"] == pid)["archived_at"] = v


def _set_pend(m, pid, q):
    next(s for s in m.tables["sales_order_items"] if s["product_id"] == pid)["pending_qty"] = q


def _add_prod(m, pid, pn, pend=None):
    m.tables["products"].append({"product_id": pid, "pn": pn, "archived_at": None, "archive_reason": None})
    if pend is not None:
        m.tables["sales_order_items"].append({"soi_id": 7000 + len(m.tables["sales_order_items"]), "so_id": 702,
                                              "product_id": pid, "pending_qty": pend, "status": "PENDING"})


def _wo(at, wo):
    at.text_input(key="pe_wo_no").set_value(wo)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]


def _click(at):
    at.button(key="pe_in_submit").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]


def test_r1a_direct_input_archived_between_render_and_click(monkeypatch):
    """직접 입력: 활성 품번으로 그린 뒤 다른 세션이 휴면 처리 → 클릭 → 차단 문구·쓰기 0.
    Streamlit 1.66.1 이 비활성 위젯의 클릭 값을 서버에서 버리는 동작에 의존 — 버전을 올릴 때 이 테스트가 지킨다."""
    m = _mock()
    _set_arch(m, "P0738", None)
    _lot(m, "W3000", "M500", 50)
    at = _open(monkeypatch, m)
    at.text_input(key="pe_in_pn").set_value("HA80-80092")
    _wo(at, "20261106-011")
    assert not at.button(key="pe_in_submit").disabled
    _set_arch(m, "P0738", ARCHIVED)
    _click(at)
    assert BLOCK_92 in [str(e.value) for e in at.error], [str(e.value) for e in at.error]
    assert _no_input_writes(m), m.writes


def test_r1b_select_archived_between_render_and_click(monkeypatch):
    """선택 상자: 80092(발주 라인 기준) 기본으로 그린 뒤 휴면 → 클릭 → 그 run 은 등록 0·D-1 문구.
    다음 run: 기본 80093·휴면 안내·버튼 활성 → 클릭하면 80093 등록."""
    m = _mock()
    _set_arch(m, "P0738", None)
    _w1257(m)
    at = _open(monkeypatch, m)
    sb = _sel(at, "W1257")
    assert sb.value == "HA80-80092 (발주 라인 기준)", (sb.options, sb.value)
    _wo(at, "20261106-012")
    _set_arch(m, "P0738", ARCHIVED)
    _click(at)
    assert _no_input_writes(m), m.writes
    assert GONE_92 in [str(e.value) for e in at.error], [str(e.value) for e in at.error]
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert _sel(at, "W1257").value == "HA80-80093 ← 미납 500"
    assert NOTICE_92 in _texts(at) and not at.button(key="pe_in_submit").disabled, _texts(at)
    _click(at)
    rows = _ins(m, "wo_tracking")
    assert len(rows) == 1 and rows[0]["pn"] == "HA80-80093" and rows[0]["product_id"] == "P0883", rows


def _pick_y_and_change(monkeypatch, change, lot="W6000"):
    """후보 X=HA80-80093(P0883, 미납 500), Y=HA80-80099(P0999, 미납 300) → 품번 순으로 X 가 기본. Y 를 고른 뒤 change."""
    m = _mock()
    _add_prod(m, "P0999", "HA80-80099", 300)
    _lot(m, lot, "M191", 100)
    _bom(m, "P0883", "M191")
    _bom(m, "P0999", "M191")
    at = _open(monkeypatch, m)
    sb = _sel(at, lot)
    assert sb.index == 0 and sb.options[0].startswith("HA80-80093"), sb.options
    sb.set_value(next(o for o in sb.options if o.startswith("HA80-80099")))
    at.run()
    _wo(at, "20261106-013")
    change(m)
    _click(at)
    return m, at


def _assert_y(m, at):
    assert not [str(e.value) for e in at.error], [str(e.value) for e in at.error]
    # D-2 는 index 인자로 선택을 유지한다 — 세션 상태를 직접 쓰지 않으므로 Streamlit 경고가 없어야 한다
    assert not [str(w.value) for w in at.warning if "Session State" in str(w.value)], [str(w.value) for w in at.warning]
    for t in ("wo_tracking", "wo_batches"):
        rows = _ins(m, t)
        assert len(rows) == 1 and rows[0]["pn"] == "HA80-80099" and rows[0]["product_id"] == "P0999", (t, rows)


def test_r1c_selected_label_changes_keeps_selection(monkeypatch):
    """Y 선택 → Y 미납 300 → 200 → 클릭 → Y 등록(차단·오류 없음)."""
    _assert_y(*_pick_y_and_change(monkeypatch, lambda m: _set_pend(m, "P0999", 200)))


def test_r1c2_relabel_run_without_click_keeps_selection_no_warning(monkeypatch):
    """클릭 없이 다시 그려도(라벨 변동 run) 선택이 Y 의 새 라벨로 유지되고 Streamlit 경고·오류가 없다(D-2 index 방식)."""
    m = _mock()
    _add_prod(m, "P0999", "HA80-80099", 300)
    _lot(m, "W6200", "M191", 100)
    _bom(m, "P0883", "M191")
    _bom(m, "P0999", "M191")
    at = _open(monkeypatch, m)
    _sel(at, "W6200").set_value("HA80-80099 ← 미납 300")
    at.run()
    _set_pend(m, "P0999", 200)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert _sel(at, "W6200").value == "HA80-80099 ← 미납 200", _sel(at, "W6200").value
    assert not [str(e.value) for e in at.error] and not [str(w.value) for w in at.warning
                                                          if "Session State" in str(w.value)]


def test_r1d_other_label_changes_keeps_selection(monkeypatch):
    """Y 선택 → 고르지 않은 X 의 라벨만 변동 → 클릭 → Y 등록(기존 동작 고정)."""
    _assert_y(*_pick_y_and_change(monkeypatch, lambda m: _set_pend(m, "P0883", 400)))


def test_r1e_selected_moves_position_keeps_selection(monkeypatch):
    """X 미납 0 · Y 미납 300 → Y 가 첫 항목. Y 선택 → Y 미납 0 이 되어 품번 순 [X, Y] 로 바뀜 → 클릭 → Y 등록."""
    m = _mock()
    _set_pend(m, "P0883", 0)
    _add_prod(m, "P0999", "HA80-80099", 300)
    _lot(m, "W6100", "M191", 100)
    _bom(m, "P0883", "M191")
    _bom(m, "P0999", "M191")
    at = _open(monkeypatch, m)
    sb = _sel(at, "W6100")
    assert sb.options[0].startswith("HA80-80099"), sb.options
    sb.set_value(sb.options[0])
    at.run()
    _wo(at, "20261106-014")
    _set_pend(m, "P0999", 0)
    _click(at)
    _assert_y(m, at)


def test_r1f_only_candidate_archived_switches_to_direct_input(monkeypatch):
    """후보 1개(발주 라인 힌트만, BOM 없음) 선택 → 휴면 → 클릭 → 직접 입력 칸, D-1 문구, 쓰기 0."""
    m = _mock()
    _set_arch(m, "P0738", None)
    _lot(m, "W7000", "M500", 30, poi=326, poi_item="HA80-80092", poi_pid="P0738")
    at = _open(monkeypatch, m)
    assert _sel(at, "W7000").options == ["HA80-80092 (발주 라인 기준)"]
    _wo(at, "20261106-015")
    _set_arch(m, "P0738", ARCHIVED)
    _click(at)
    assert _no_input_writes(m), m.writes
    assert not [s for s in at.selectbox if s.key == "pe_in_pnsel_W7000"]
    assert [t for t in at.text_input if t.key == "pe_in_pn"], "직접 입력 칸"
    assert GONE_92 in [str(e.value) for e in at.error], [str(e.value) for e in at.error]
    assert NOTICE_92 in _texts(at)
    # r2b: 다음 run — 선택 상자가 그려지지 않은 run 뒤 세션의 선택 값이 지워져 gone 문구·차단이 풀린다(영구 차단 아님)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert "pe_in_pnsel_W7000" not in at.session_state
    assert not any("앞서 고른 품번" in str(e.value) for e in at.error), [str(e.value) for e in at.error]
    at.text_input(key="pe_in_pn").set_value("HA80-80093")
    at.run()
    assert not at.button(key="pe_in_submit").disabled, [str(e.value) for e in at.error]
    _click(at)
    rows = _ins(m, "wo_tracking")
    assert len(rows) == 1 and rows[0]["pn"] == "HA80-80093", rows


# ── r2b D-3: 품번 자체가 표시 꼬리로 끝나는 경우(Codex r2 HIGH) — 직전 run 의 「라벨 → 품번」 표로 찾는다 ──
def _tail_pick(monkeypatch):
    """후보 X=HB10-100(미납 500, 기본), T=「HB10-100 (발주 라인 기준)」(실제 품번, 미납 0). T 를 고른 뒤 T 미납 0 → 200."""
    m = _mock()
    _add_prod(m, "PX", "HB10-100", 500)
    _add_prod(m, "PT", "HB10-100 (발주 라인 기준)", 0)
    _lot(m, "W8000", "M191", 100)
    _bom(m, "PX", "M191")
    _bom(m, "PT", "M191")
    at = _open(monkeypatch, m)
    sb = _sel(at, "W8000")
    assert sb.options == ["HB10-100 ← 미납 500", "HB10-100 (발주 라인 기준)"] and sb.index == 0, sb.options
    sb.set_value("HB10-100 (발주 라인 기준)")
    at.run()
    _wo(at, "20261106-021")
    _set_pend(m, "PT", 200)
    return m, at


def test_d3_tail_pn_kept_on_rerun(monkeypatch):
    m, at = _tail_pick(monkeypatch)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert _sel(at, "W8000").value == "HB10-100 (발주 라인 기준) ← 미납 200", _sel(at, "W8000").value
    assert not [str(e.value) for e in at.error]


def test_d3_tail_pn_registered_on_click(monkeypatch):
    m, at = _tail_pick(monkeypatch)
    _click(at)
    assert not [str(e.value) for e in at.error], [str(e.value) for e in at.error]
    for t in ("wo_tracking", "wo_batches"):
        rows = _ins(m, t)
        assert len(rows) == 1 and rows[0]["pn"] == "HB10-100 (발주 라인 기준)" and rows[0]["product_id"] == "PT", (t, rows)


def test_r2_archived_by_product_id_with_active_item_name(monkeypatch):
    """poi product_id = 휴면 P0738, item_name = 활성 HA80-80093 → 품명 경로로 넘어가지 않음:
    옵션은 활성 BOM 품번만, 「(발주 라인 기준)」 없음, 휴면 안내."""
    m = _mock()
    _lot(m, "W1257", "M191", 800, poi=325, poi_item="HA80-80093", poi_pid="P0738")
    _bom(m, "P0738", "M191")
    _bom(m, "P0883", "M191")
    at = _open(monkeypatch, m)
    assert _sel(at, "W1257").options == ["HA80-80093 ← 미납 500"]
    assert NOTICE_92 in _texts(at), _texts(at)


def test_r3_registration_rows_and_batch_link(monkeypatch):
    """A-T6 보강: PROD 라우팅, 투입 800, BOM 1:1 → PROD_INPUT·wo_tracking·wo_batches 값과 wo_batches.wo_id 연결."""
    m = _mock()
    _w1257(m)
    m.tables["product_routing"] = [
        {"routing_id": 81, "product_id": "P0883", "seq": 10, "step_code": "PROD", "step_name": "생산",
         "step_kind": "INHOUSE", "stage": "PRODUCT", "bom_id": None, "confirmed": True},
        {"routing_id": 82, "product_id": "P0883", "seq": 50, "step_code": "INSPECT", "step_name": "검사",
         "step_kind": "INHOUSE", "stage": "PRODUCT", "bom_id": None, "confirmed": True}]
    at = _open(monkeypatch, m)
    _submit(at, "20261106-001")
    wo = _ins(m, "wo_tracking")
    assert len(wo) == 1, wo
    w = wo[0]
    assert (w["pn"], w["product_id"], w["material_id"], w["w_lot"]) == ("HA80-80093", "P0883", "M191", "W1257"), w
    assert (float(w["input_qty"]), float(w["received_qty"]), w["status"]) == (800.0, 0.0, "IN_PROD"), w
    wb = _ins(m, "wo_batches")
    assert len(wb) == 1, wb
    b = wb[0]
    assert (b["batch_no"], float(b["qty"]), b["step_code"], b["routing_id"]) == ("20261106-001-A", 800.0, "PROD", 81), b
    assert b["wo_id"] is not None and b["wo_id"] == w["wo_id"], (b, w)
    tx = _ins(m, "inventory_transactions")
    assert len(tx) == 1, tx
    t = tx[0]
    assert (t["txn_type"], t["material_id"], float(t["qty"]), t["lot_number"], t["work_order"]) == \
        ("PROD_INPUT", "M191", -800.0, "W1257", "20261106-001"), t


def test_r4_archived_hint_two_active_bom(monkeypatch):
    """휴면 힌트 + 활성 BOM 2개(미납 500 / 0) → 미납 품번 첫 항목·기본 0·휴면 없음."""
    m = _mock()
    _add_prod(m, "P0999", "HA80-80099", 0)
    _w1257(m)
    _bom(m, "P0999", "M191")
    at = _open(monkeypatch, m)
    sb = _sel(at, "W1257")
    assert sb.options == ["HA80-80093 ← 미납 500", "HA80-80099"] and sb.index == 0, sb.options
    assert NOTICE_92 in _texts(at)


def test_r_ws_direct_input_archived_with_spaces_blocked(monkeypatch):
    """직접 입력에 앞뒤 공백 붙은 휴면 품번 → 차단 문구·버튼 비활성·쓰기 0."""
    m = _mock()
    _lot(m, "W3000", "M500", 50)
    at = _open(monkeypatch, m)
    at.text_input(key="pe_in_pn").set_value("  HA80-80092  ")
    _wo(at, "20261106-016")
    assert BLOCK_92 in [str(e.value) for e in at.error], [str(e.value) for e in at.error]
    assert at.button(key="pe_in_submit").disabled
    assert not [w for w in m.writes if w[0] != "fetch_400"], m.writes
