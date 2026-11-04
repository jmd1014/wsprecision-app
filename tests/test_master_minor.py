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


# ─────────────── 후보 32 — 라우트 복사(목 DB, 상태 보존) ───────────────
class _MemDB:
    """eq·in·is.null·order 만 해석하는 작은 목. insert 는 serial id 를 붙이고, fail 표에 있으면 RuntimeError."""
    IDS = {"bom": "bom_id", "product_routing": "routing_id", "master_change_log": "log_id"}

    def __init__(self, tables):
        self.t = {k: [dict(r) for r in v] for k, v in tables.items()}
        self.seq = {"bom": 9000, "product_routing": 500, "master_change_log": 1}
        self.writes, self.fail, self.rpc_calls = [], set(), []

    @staticmethod
    def _match(row, fq):
        for part in (fq or "").split("&"):
            if "=" not in part or part.startswith(("order=", "or=", "limit=", "select=")):
                continue
            col, cond = part.split("=", 1)
            if cond.startswith("eq."):
                if str(row.get(col)) != cond[3:].strip('"'):
                    return False
            elif cond.startswith("in."):
                vals = {v.strip().strip('"') for v in cond[4:-1].split(",")}
                if str(row.get(col)) not in vals:
                    return False
            elif cond == "is.null":
                if row.get(col) is not None:
                    return False
        return True

    def fetch(self, table, select="*", filter_query="", limit=1000, **kw):
        fq = unquote(filter_query or "")
        rows = [dict(r) for r in self.t.get(table, []) if self._match(r, fq)]
        order = next((p[6:] for p in fq.split("&") if p.startswith("order=")), None)
        if order:
            col = order.split(",")[0].split(".")[0]
            rows.sort(key=lambda r: (r.get(col) is None, r.get(col)))
        return rows[:limit]

    def fetch_all(self, table, select="*", filter_query="", **kw):
        return self.fetch(table, select, filter_query, limit=10 ** 6), False

    def insert(self, table, records, *a, **k):
        if table in self.fail:
            raise RuntimeError(f"{table} insert 500: 시뮬레이션")
        idk = self.IDS.get(table)
        for r in records:
            r = dict(r)
            if idk:
                self.seq[table] += 1
                r[idk] = self.seq[table]
            self.t.setdefault(table, []).append(r)
        self.writes.append(("insert", table, [dict(r) for r in records]))
        return len(records)

    def delete(self, table, filter_query):
        fq = unquote(filter_query or "")
        keep = [r for r in self.t.get(table, []) if not self._match(r, fq)]
        n = len(self.t.get(table, [])) - len(keep)
        self.t[table] = keep
        self.writes.append(("delete", table, fq))
        return n

    def update(self, table, filter_query, fields, *a, **k):
        fq = unquote(filter_query or "")
        for r in self.t.get(table, []):
            if self._match(r, fq):
                r.update(fields)
        self.writes.append(("update", table, fq, dict(fields)))
        return True

    def rpc(self, name, params=None, timeout=None):
        """copy_product_routing 목 — 실제 SQL 은 test_copy_routing_rpc_local 이 로컬 복원 DB 에서 실행한다.
        rpc_exc 가 있으면 던지고(after 가 있으면 먼저 실행 — 응답 유실 흉내), 아니면 rpc_result."""
        self.rpc_calls.append((name, dict(params or {})))
        if getattr(self, "rpc_after", None):
            self.rpc_after(self)
        if getattr(self, "rpc_exc", None):
            raise self.rpc_exc
        return getattr(self, "rpc_result", {"proc": 2, "mat": 0, "routing": 6, "src_pn": "MM-SRC-1",
                                            "tgt_pn": "MM-TGT-1"})


def _prod(pid, pn, archived=None):
    return {"product_id": pid, "pn": pn, "item_name": f"품 {pn}", "customer": "시험고객",
            "sub_class": "시험", "archived_at": archived}


def _bomrow(bid, pid, pt, name, mid=None, vendor=None, price=None, ver="확인완료", lot=None):
    return {"bom_id": bid, "product_id": pid, "material_id": mid, "raw_material_name": name,
            "qty_per_pc": 1.0 if pt == "MATERIAL" else 0.5, "shared_factor": 1, "process_type": pt,
            "unit_price": price, "lot_label": lot, "process_vendor_id": vendor,
            "verification_status": ver, "source": "MES"}


def _rt(pid, seq, code, name, kind="INHOUSE", stage="PRODUCT", bom_id=None, confirmed=True):
    return {"routing_id": 100 + seq + (1000 if pid != "PS" else 0), "product_id": pid, "seq": seq,
            "step_code": code, "step_name": name, "step_kind": kind, "stage": stage, "bom_id": bom_id,
            "default_vendor": "위드열처리" if bom_id else None, "confirmed": confirmed}


def _tables(target_bom=(), target_rt=(), src_unconfirmed=False):
    src_rt = [_rt("PS", 10, "MAT_IN", "소재입고", stage="MATERIAL"), _rt("PS", 20, "PROD", "생산"),
              _rt("PS", 30, "OUT", "침탄 열처리", "OUTSOURCE", bom_id=802),
              _rt("PS", 40, "OUT", "도금", "OUTSOURCE", bom_id=803, confirmed=not src_unconfirmed),
              _rt("PS", 50, "INSPECT", "검사"), _rt("PS", 60, "DONE", "완성")]
    return {
        "products": [_prod("PS", "MM-SRC-1"), _prod("PT", "MM-TGT-1"), _prod("PX", "MM-OLD-1", "2026-01-01"),
                     _prod("PO", "MM-OTH-1")],
        "bom": [_bomrow(801, "PS", "MATERIAL", "SCM420 Ø28*97", mid="M191"),
                _bomrow(802, "PS", "HEAT", "침탄 열처리", vendor=116, price=1000, lot="KG"),
                _bomrow(803, "PS", "SURFACE", "도금", vendor=117, price=50)] + list(target_bom),
        "product_routing": src_rt + list(target_rt)
                           + [_rt("PX", 10, "PROD", "생산"), _rt("PO", 10, "PROD", "생산")],
        "vendors": [{"vendor_id": 116, "name": "위드열처리"}, {"vendor_id": 117, "name": "도금사"}],
    }


@pytest.fixture()
def mem_db(monkeypatch):
    import db

    def make(**kw):
        m = _MemDB(_tables(**kw))
        for name in ("fetch", "fetch_all", "insert", "delete", "update"):
            monkeypatch.setattr(db, name, getattr(m, name))
        monkeypatch.setattr(db, "fetch_one", lambda *a, **k: None)
        monkeypatch.setattr(db, "health_check", lambda: {"status": "OK", "counts": {}})
        monkeypatch.setattr(db, "debug_check", lambda: {"status": "mock"})
        if hasattr(db, "count_rows"):
            monkeypatch.setattr(db, "count_rows", lambda *a, **k: 0)
        monkeypatch.setattr(db, "rpc", m.rpc)
        return m
    return make


def _open_copy(m, tgt="PT", src="PS"):
    at = _open_bom(sel_pid=tgt, q="MM-")
    sb = [s for s in at.selectbox if s.key == f"rc_src_{tgt}"]
    assert sb, "라우트 복사 원본 선택"
    if src:
        sb[0].set_value(src)
        at.run()
        assert not at.exception, [str(e.value) for e in at.exception]
    return at


def _copy_btn(at, tgt="PT"):
    return [b for b in at.button if b.key == f"rc_go_{tgt}"][0]


def _ins(m, table):
    return [r for w in m.writes if w[0] == "insert" and w[1] == table for r in w[2]]


def test_32_source_options_exclude_self_and_archived(mem_db):
    m = mem_db()
    at = _open_copy(m, src=None)
    opts = [s for s in at.selectbox if s.key == "rc_src_PT"][0].options
    assert any("MM-SRC-1" in o for o in opts) and any("MM-OTH-1" in o for o in opts)
    assert not any("MM-OLD-1" in o for o in opts), "보관 제품 제외"
    assert not any("MM-TGT-1" in o for o in opts), "자기 자신 제외"


def test_32_copy_calls_rpc_once_and_flashes(mem_db):
    m = mem_db(target_bom=[_bomrow(850, "PT", "MATERIAL", "SCM420 Ø30*99", mid="M192")])
    at = _open_copy(m)
    assert not [c for c in at.checkbox if c.key == "rc_mat_PT"], "(f) 소재행 있는 대상 → 체크박스 없음"
    assert not _copy_btn(at).disabled
    _copy_btn(at).click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert m.rpc_calls == [("copy_product_routing",
                            {"p_src": "PS", "p_tgt": "PT", "p_with_mat": False, "p_who": m.rpc_calls[0][1]["p_who"]})]
    assert m.writes == [], "쓰기는 전부 RPC 안(화면 직접 insert·delete 없음)"
    assert any("라우팅 복사: MM-TGT-1 ← MM-SRC-1 — 공정행 2·순서 6단계" in str(s.value) for s in at.success)


@pytest.mark.parametrize("case", ["target_routing", "target_proc", "src_unconfirmed"])
def test_32_blocked_cases_write_nothing(mem_db, case):
    kw = {"target_routing": {"target_rt": [_rt("PT", 10, "PROD", "생산")]},
          "target_proc": {"target_bom": [_bomrow(860, "PT", "HEAT", "기존 열처리")]},
          "src_unconfirmed": {"src_unconfirmed": True}}[case]
    m = mem_db(**kw)
    at = _open_copy(m)
    assert _copy_btn(at).disabled, case
    assert any(("덮어쓰기 없음" in str(w.value)) or ("먼저 확정" in str(w.value)) for w in at.warning)
    assert m.writes == []
    if case == "target_routing":   # 라우팅이 있는 대상도 원본 후보에서 자기 자신은 빠짐
        opts = [s for s in at.selectbox if s.key == "rc_src_PT"][0].options
        assert not any("MM-TGT-1" in o for o in opts)


def test_32_rpc_rejected_and_unavailable_messages(mem_db):
    import db
    m = mem_db()
    m.rpc_exc = db.RpcRejected("P0001", "target_has_routing", 400)
    at = _open_copy(m)
    _copy_btn(at).click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert any("대상에 이미 라우팅이 있습니다" in str(e.value) for e in at.error)
    m.rpc_exc = db.RpcUnavailable("copy_product_routing: PGRST202")
    at.session_state["_guard_rout_copy"] = 0
    _copy_btn(at).click()
    at.run()
    assert any("081 미적용" in str(e.value) for e in at.error)
    assert m.writes == [] and len(m.rpc_calls) == 2


@pytest.mark.parametrize("applied", [True, False])
def test_32_transport_error_decided_by_target_routing(mem_db, applied):
    import db
    m = mem_db()
    m.rpc_exc = db.RpcTransportError("copy_product_routing: timeout")
    if applied:       # 서버는 반영했고 응답만 잃음
        m.rpc_after = lambda mm: mm.t["product_routing"].append(_rt("PT", 10, "PROD", "생산"))
    at = _open_copy(m)
    _copy_btn(at).click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    if applied:
        assert any("응답은 없었지만 복사된 것을 확인" in str(s.value) for s in at.success)
    else:
        assert any("반영되지 않았습니다" in str(e.value) for e in at.error)
    assert len(m.rpc_calls) == 1, "자동 재시도 없음"


def test_32_empty_target_offers_material_copy(mem_db):
    m = mem_db()
    m.rpc_result = {"proc": 2, "mat": 1, "routing": 6, "src_pn": "MM-SRC-1", "tgt_pn": "MM-TGT-1"}
    at = _open_copy(m)
    cb = [c for c in at.checkbox if c.key == "rc_mat_PT"]
    assert cb and cb[0].value is True, "(e) 빈 대상 → 소재행도 복사 체크박스(기본 켬)"
    _copy_btn(at).click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert m.rpc_calls[0][1]["p_with_mat"] is True
    assert any("소재행 1" in str(s.value) for s in at.success)


# ─────────────── 후보 34 — 단가 변동 감지 '단가 조정'(PRICE_ADJ) ───────────────
def _price_mock():
    from tests.so_mock import SOMock

    class _M(SOMock):
        def _assert_dash(self, op, table):     # 단가 조정은 마스터 판매 단가·변경 이력까지 쓴다
            if table not in ("products", "master_change_log"):
                super()._assert_dash(op, table)

        false_update = ()      # (표, 필드) — db.update 가 False(PostgREST 오류·CHECK 위반)
        fail_insert = ()       # 표 — insert 예외

        def update(self, table, filter_query, fields):
            if any(table == t and f in fields for t, f in self.false_update):
                return False
            return super().update(table, filter_query, fields)

        def insert(self, table, records):      # DashMock 은 id 를 붙인다 — 결정 이력은 repl_id 로 읽는다
            if table in self.fail_insert:
                raise RuntimeError(f"{table} insert 500: 시뮬레이션")
            n = super().insert(table, records)
            if table == "so_line_replacements":
                for r in self.tables[table]:
                    r.setdefault("repl_id", r.get("id"))
                    r.setdefault("reverted_at", None)
            return n
    m = _M()
    m.tables.setdefault("master_change_log", [])
    m.seed(so_id=101, so_number="PO-OLD", lines=[(1, 400, 9, 391, "PARTIAL")], rounds=[])
    m.seed(so_id=102, so_number="PO-NEW", lines=[(9, 100, 0, 100, "PENDING")], rounds=[])
    m.line(1)["unit_price"] = 3285
    m.line(9)["unit_price"] = 3282
    m.tables["products"][0]["sale_price"] = 3285
    return m


def _open_so_list(monkeypatch, m):
    import db as _dbmod
    from streamlit.testing.v1 import AppTest
    m.install(monkeypatch, _dbmod)
    at = AppTest.from_file(APP_FILE, default_timeout=90)
    at.secrets["supabase"] = {"url": "https://mock.local", "anon_key": "a", "service_role_key": "s"}
    at.secrets["auth"] = {"disabled": True}
    at.run()
    goto(at, "so", "list")
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def _keep(at, kind):
    [s for s in at.selectbox if s.key == "rp_9_t"][0].set_value(kind)
    at.run()
    btn = at.button(key="rp_9_keep")
    btn.click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return btn


def test_34_price_adj_keeps_old_and_updates_master_then_revert(monkeypatch):
    m = _price_mock()
    at = _open_so_list(monkeypatch, m)
    assert "단가 조정" in [s for s in at.selectbox if s.key == "rp_9_t"][0].options
    [s for s in at.selectbox if s.key == "rp_9_t"][0].set_value("단가 조정")
    at.run()
    assert at.button(key="rp_9_keep").label == "별건 (옛 수주 = 옛 단가)"
    _keep(at, "단가 조정")
    assert m.line(1)["price_kind"] == "PRICE_ADJ" and m.line(9)["price_kind"] is None, "옛 라인에 표시, 새 라인은 기준"
    assert m.tables["products"][0]["sale_price"] == 3282, "새 수주 단가 → 마스터"
    assert m.line(1)["pending_qty"] == 391 and m.line(1)["status"] == "PARTIAL", "옛 수주는 그대로 진행"
    rp = m.tables["so_line_replacements"]
    assert len(rp) == 1 and (rp[0]["action"], rp[0]["tagged_kind"], rp[0]["tagged_soi_id"],
                             rp[0]["master_updated"], rp[0]["master_old_price"]) == ("KEEP", "PRICE_ADJ", 1, True, 3285)
    lg = m.tables["master_change_log"]
    assert len(lg) == 1 and lg[0]["field_name"] == "sale_price" and "단가 조정" in lg[0]["reason"]
    assert any("단가 조정: 옛 수주 1건은 옛 단가 유지, 마스터 판매 단가 3,285 → 3,282" in str(s.value)
               for s in at.success)
    rid = rp[0].get("repl_id")
    at.button(key=f"rp_rv_{rid}").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert m.line(1)["price_kind"] is None and m.tables["products"][0]["sale_price"] == 3285, "되돌리기 → 마스터 복원"
    assert m.tables["so_line_replacements"][0]["reverted_at"]
    assert len(m.tables["master_change_log"]) == 2 and "되돌리기" in m.tables["master_change_log"][1]["reason"]


def test_34_revert_group_and_later_master_change_guard(monkeypatch):
    """Codex 34 HIGH: 옛 라인 2건 단가 조정 → 한 건만 되돌리면 마스터 그대로, 마지막 건에서 복원.
    마스터가 이후 바뀌었으면 자동 복원하지 않음."""
    m = _price_mock()
    m.tables["sales_order_items"].append(dict(m.line(1), soi_id=2, line_no=2))
    at = _open_so_list(monkeypatch, m)
    _keep(at, "단가 조정")
    rp = m.tables["so_line_replacements"]
    assert len(rp) == 2 and all(r["master_updated"] and r["master_old_price"] == 3285 for r in rp)
    assert m.tables["products"][0]["sale_price"] == 3282
    at.button(key=f"rp_rv_{rp[0]['repl_id']}").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert m.line(1)["price_kind"] is None and m.line(2)["price_kind"] == "PRICE_ADJ"
    assert m.tables["products"][0]["sale_price"] == 3282, "다른 단가 조정 이력이 남아 있으면 마스터 그대로"
    assert any("1건이 남아 있습니다" in str(s.value) for s in at.success)
    m.tables["products"][0]["sale_price"] = 3300           # 이후 다른 변경
    at.run()
    at.button(key=f"rp_rv_{rp[1]['repl_id']}").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert m.line(2)["price_kind"] is None and m.tables["products"][0]["sale_price"] == 3300, "덮어쓰지 않음"
    assert any("복원하지 않았습니다" in str(s.value) for s in at.success)
    assert all(r["reverted_at"] for r in m.tables["so_line_replacements"])


def test_34_project_keep_unchanged_no_master_update(monkeypatch):
    m = _price_mock()
    at = _open_so_list(monkeypatch, m)
    assert at.button(key="rp_9_keep").label == "별건 (새 수주 = 프로젝트)"
    _keep(at, "프로젝트")
    assert m.line(9)["price_kind"] == "PROJECT" and m.line(1)["price_kind"] is None
    assert m.tables["products"][0]["sale_price"] == 3285 and m.tables["master_change_log"] == []
    rp = m.tables["so_line_replacements"][0]
    assert (rp["master_updated"], rp["master_old_price"], rp["tagged_kind"]) == (False, None, "PROJECT")


# ─────────────── r2(검토 세션 2026-11-05) — 34 쓰기 순서·반환값 검사·회귀 ───────────────
def _texts(at):
    return [str(x.value) for x in list(at.success) + list(at.error) + list(at.warning)]


def test_r2_9_two_olds_revert_reapply_same_price_keeps_master(monkeypatch):
    m = _price_mock()
    m.tables["sales_order_items"].append(dict(m.line(1), soi_id=2, line_no=2))
    at = _open_so_list(monkeypatch, m)
    _keep(at, "단가 조정")
    rp = m.tables["so_line_replacements"]
    at.button(key=f"rp_rv_{rp[0]['repl_id']}").click()
    at.run()
    assert m.tables["products"][0]["sale_price"] == 3282 and m.line(1)["price_kind"] is None
    _keep(at, "단가 조정")                       # 되돌린 옛 라인 1 다시 단가 조정 — 마스터는 이미 새 단가
    new = [r for r in m.tables["so_line_replacements"] if r["old_soi_id"] == 1 and not r.get("reverted_at")]
    assert len(new) == 1 and new[0]["master_updated"] is False and new[0]["master_old_price"] is None, \
        "같은 값이면 마스터 갱신·로그 생략(r2 ⑥)"
    assert any("그대로(이미 3,282)" in t for t in _texts(at))
    n_log = len(m.tables["master_change_log"])
    at.button(key=f"rp_rv_{new[0]['repl_id']}").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert m.tables["products"][0]["sale_price"] == 3282 and len(m.tables["master_change_log"]) == n_log


def test_r2_10_history_insert_failure_keeps_master_and_untags(monkeypatch):
    m = _price_mock()
    m.fail_insert = ("so_line_replacements",)
    at = _open_so_list(monkeypatch, m)
    _keep(at, "단가 조정")
    assert m.tables["products"][0]["sale_price"] == 3285 and m.tables["master_change_log"] == []
    assert m.line(1)["price_kind"] is None, "표시는 되돌림"
    assert any("결정 이력을 저장하지 못했습니다" in t and "바꾸지 않았습니다" in t for t in _texts(at))


def test_r2_11_master_update_false_marks_history_not_updated(monkeypatch):
    m = _price_mock()
    m.false_update = (("products", "sale_price"),)
    at = _open_so_list(monkeypatch, m)
    _keep(at, "단가 조정")
    rp = m.tables["so_line_replacements"]
    assert len(rp) == 1 and rp[0]["master_updated"] is False and rp[0]["master_old_price"] is None
    assert m.tables["products"][0]["sale_price"] == 3285 and m.tables["master_change_log"] == []
    assert m.line(1)["price_kind"] == "PRICE_ADJ"
    assert any("마스터 판매 단가를 갱신하지 못했습니다" in t for t in _texts(at))


def test_r2_12_price_kind_update_false_stops_before_master(monkeypatch):
    m = _price_mock()
    m.false_update = (("sales_order_items", "price_kind"),)
    at = _open_so_list(monkeypatch, m)
    _keep(at, "단가 조정")
    assert m.tables["so_line_replacements"] == [] and m.tables["master_change_log"] == []
    assert m.tables["products"][0]["sale_price"] == 3285
    assert any("080 미적용" in t for t in _texts(at))


def test_r2_13_zero_new_price_disables_price_adj(monkeypatch):
    m = _price_mock()
    m.line(9)["unit_price"] = 0
    at = _open_so_list(monkeypatch, m)
    assert not at.button(key="rp_9_keep").disabled, "프로젝트 별건은 그대로 가능"
    [s for s in at.selectbox if s.key == "rp_9_t"][0].set_value("단가 조정")
    at.run()
    assert at.button(key="rp_9_keep").disabled


def test_r2_14_revert_master_update_false_does_not_mark_reverted(monkeypatch):
    m = _price_mock()
    at = _open_so_list(monkeypatch, m)
    _keep(at, "단가 조정")
    m.false_update = (("products", "sale_price"),)
    rp = m.tables["so_line_replacements"][0]
    at.button(key=f"rp_rv_{rp['repl_id']}").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert rp["reverted_at"] is None and m.line(1)["price_kind"] == "PRICE_ADJ"
    assert m.tables["products"][0]["sale_price"] == 3282
    assert any("복원 실패" in t for t in _texts(at))


def test_r2_15_replace_regression_update_and_revert(monkeypatch):
    m = _price_mock()
    at = _open_so_list(monkeypatch, m)
    at.button(key="rp_9_go").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert m.tables["products"][0]["sale_price"] == 3282
    lg = m.tables["master_change_log"]
    assert len(lg) == 1 and "단가 변경 (구 PO-OLD 3,285 → 3,282)" in lg[0]["reason"]
    rp = m.tables["so_line_replacements"][0]
    assert (rp["action"], rp["master_updated"], rp["master_old_price"]) == ("REPLACE", True, 3285)
    assert m.line(1)["status"] == "REPLACED" and m.line(1)["pending_qty"] == 0
    at.button(key=f"rp_rv_{rp['repl_id']}").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert m.tables["products"][0]["sale_price"] == 3285 and rp["reverted_at"]
    assert m.line(1)["status"] == "PARTIAL" and m.line(1)["pending_qty"] == 391


# ─────────────── r2 qa 17 — 제품·자재 편집: 기억 행 선택·저장 뒤 같은 행(쓰기 1건) ───────────────
def _form_btn(at, form):
    return next(b for b in at.button if b.label == "변경 저장" and getattr(b.proto, "form_id", "") == form)


def _open_master(m, **sel):
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
    for k, v in sel.items():
        at.session_state[k] = v
    goto(at, "master")
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def _md_heads(at):
    return [str(x.value) for x in at.markdown if "상세 편집" in str(x.value)]


def test_r2_17_product_edit_remembered_row_and_save(mem_db):
    m = mem_db()
    at = _open_master(m, prod_sel_pid="PT")
    assert any(h.startswith("##### MM-TGT-1 — 상세 편집") for h in _md_heads(at)), _md_heads(at)
    [t for t in at.text_input if t.key == "pd_ct_PT"][0].set_value("시험 주의")
    _form_btn(at, "pd_form_PT").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    ups = [w for w in m.writes if w[0] == "update" and w[1] == "products"]
    assert len(ups) == 1 and "PT" in ups[0][2] and ups[0][3].get("caution") == "시험 주의"
    assert any(h.startswith("##### MM-TGT-1 — 상세 편집") for h in _md_heads(at)), "저장 뒤 같은 제품"
    assert at.session_state["prod_sel_pid"] == "PT"


def test_r2_17_material_edit_remembered_row_and_save(mem_db):
    m = mem_db()
    m.t["materials"] = [{"material_id": f"M90{i}", "raw_name": f"시험 소재 {i}", "material_type": "SUS304",
                         "spec": f"Ø{i}0", "unit": "KG", "stock_qty": 0, "main_supplier": None,
                         "procurement_type": None} for i in (1, 2, 3)]
    at = _open_master(m, mat_sel_mid="M903")
    assert any("(M903) — 상세 편집" in h for h in _md_heads(at)), _md_heads(at)
    [t for t in at.text_input if t.key == "md_su_M903"][0].set_value("시험 공급사")
    _form_btn(at, "md_form_M903").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    ups = [w for w in m.writes if w[0] == "update" and w[1] == "materials"]
    assert len(ups) == 1 and "M903" in ups[0][2] and ups[0][3].get("main_supplier") == "시험 공급사"
    assert any("(M903) — 상세 편집" in h for h in _md_heads(at)), "저장 뒤 같은 자재"
    assert at.session_state["mat_sel_mid"] == "M903"
