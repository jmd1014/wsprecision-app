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
        self.writes, self.fail = [], set()

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
        if hasattr(db, "rpc"):
            monkeypatch.setattr(db, "rpc", lambda *a, **k: None)
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


def test_32_copy_maps_bom_ids_and_logs(mem_db):
    m = mem_db(target_bom=[_bomrow(850, "PT", "MATERIAL", "SCM420 Ø30*99", mid="M192")])
    at = _open_copy(m)
    assert not [c for c in at.checkbox if c.key == "rc_mat_PT"], "(f) 소재행 있는 대상 → 체크박스 없음"
    assert not _copy_btn(at).disabled
    _copy_btn(at).click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    bom = _ins(m, "bom")
    assert [(b["process_type"], b["raw_material_name"]) for b in bom] == [("HEAT", "침탄 열처리"), ("SURFACE", "도금")]
    assert all(b["process_vendor_id"] is None and b["unit_price"] is None and b["material_id"] is None
               and b["source"] == "MANUAL" and b["product_id"] == "PT" for b in bom), "업체·단가 복사 안 함"
    assert bom[0]["lot_label"] == "KG" and bom[0]["verification_status"] == "확인완료"
    new_ids = {r["raw_material_name"]: r["bom_id"] for r in m.t["bom"] if r["product_id"] == "PT"
               and r["process_type"] != "MATERIAL"}
    rt = _ins(m, "product_routing")
    assert len(rt) == 6 and all(r["product_id"] == "PT" and r["confirmed"] is True and r["default_vendor"] is None
                                for r in rt)
    assert [r["bom_id"] for r in rt] == [None, None, new_ids["침탄 열처리"], new_ids["도금"], None, None], \
        "원본 bom_id → 새 id, 외주 아닌 단계는 NULL"
    lg = _ins(m, "master_change_log")
    assert len(lg) == 1 and lg[0]["table_name"] == "product_routing" and lg[0]["record_id"] == "PT" \
        and lg[0]["new_value"] == "6단계 복사 from MM-SRC-1"
    assert not [w for w in m.writes if w[0] == "update"], "소재행 복사 안 했으면 products 소재 표기 그대로"


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


def test_32_routing_failure_rolls_back_bom(mem_db):
    m = mem_db()
    m.fail.add("product_routing")
    at = _open_copy(m)
    [c for c in at.checkbox if c.key == "rc_mat_PT"][0].uncheck()
    at.run()
    _copy_btn(at).click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert len(_ins(m, "bom")) == 2
    assert [r for r in m.t["bom"] if r["product_id"] == "PT"] == [], "만든 BOM 행 삭제"
    assert any(w[0] == "delete" and w[1] == "bom" for w in m.writes)
    assert any("복사 실패" in str(e.value) for e in at.error)
    assert _ins(m, "master_change_log") == []


def test_32_empty_target_copies_material_rows(mem_db):
    m = mem_db()
    at = _open_copy(m)
    cb = [c for c in at.checkbox if c.key == "rc_mat_PT"]
    assert cb and cb[0].value is True, "(e) 빈 대상 → 소재행도 복사 체크박스(기본 켬)"
    _copy_btn(at).click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    bom = _ins(m, "bom")
    assert [b["process_type"] for b in bom] == ["MATERIAL", "HEAT", "SURFACE"]
    assert bom[0]["material_id"] == "M191" and bom[0]["verification_status"] == "AUTO-추정"
    new_proc = {r["bom_id"] for r in m.t["bom"] if r["product_id"] == "PT" and r["process_type"] != "MATERIAL"}
    assert {r["bom_id"] for r in _ins(m, "product_routing") if r["bom_id"]} == new_proc, "매핑은 공정행만"
    upd = [w for w in m.writes if w[0] == "update" and w[1] == "products"]
    assert upd and upd[0][3] == {"raw_material_name": "SCM420 Ø28*97", "bom_material_name": "SCM420 Ø28*97"}
    assert "소재행 1" in _ins(m, "master_change_log")[0]["reason"]


# ─────────────── 후보 34 — 단가 변동 감지 '단가 조정'(PRICE_ADJ) ───────────────
def _price_mock():
    from tests.so_mock import SOMock

    class _M(SOMock):
        def _assert_dash(self, op, table):     # 단가 조정은 마스터 판매 단가·변경 이력까지 쓴다
            if table not in ("products", "master_change_log"):
                super()._assert_dash(op, table)

        def insert(self, table, records):      # DashMock 은 id 를 붙인다 — 결정 이력은 repl_id 로 읽는다
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


def test_34_project_keep_unchanged_no_master_update(monkeypatch):
    m = _price_mock()
    at = _open_so_list(monkeypatch, m)
    assert at.button(key="rp_9_keep").label == "별건 (새 수주 = 프로젝트)"
    _keep(at, "프로젝트")
    assert m.line(9)["price_kind"] == "PROJECT" and m.line(1)["price_kind"] is None
    assert m.tables["products"][0]["sale_price"] == 3285 and m.tables["master_change_log"] == []
    rp = m.tables["so_line_replacements"][0]
    assert (rp["master_updated"], rp["master_old_price"], rp["tagged_kind"]) == (False, None, "PROJECT")
