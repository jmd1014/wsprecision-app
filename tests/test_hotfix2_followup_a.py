"""핫픽스 2 후속 A(2026-10-28) — 1,000행을 넘었거나 곧 넘을 5블록이 db.fetch_all 로 끝까지 읽고,
절단(truncated=True)이면 확정 숫자·확정 행동을 내지 않는지 회귀 AppTest.

목 DB(SOMock)에 server_max=1000(요청당 1,000행)을 걸고 대상 행을 1,000행 뒤에 둔다 — 예전 코드
(fetch limit 1000/2000 한 번)는 대상 행을 못 읽는다. 절단은 db.fetch_all 을 감싸 대상 테이블만
truncated=True 로 돌려 흉내 낸다(2만 행 시드 없이 앱의 절단 처리만 본다).
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

N = 1005          # 1,000행 상한 뒤에 대상 행이 오도록


def _mock():
    from tests.so_mock import SOMock
    m = SOMock()
    m.server_max = 1000
    return m


def _force_truncated(monkeypatch, table, drop=None):
    """table 의 fetch_all 결과를 truncated=True 로(drop 이 있으면 그 키의 행을 빼서 '못 읽은 행'을 흉내)."""
    import db as _dbmod
    real = _dbmod.fetch_all

    def _wrap(t, *a, **kw):
        rows, tr = real(t, *a, **kw)
        if t == table:
            if drop:
                k, v = drop
                rows = [r for r in rows if r.get(k) != v]
            return rows, True
        return rows, tr
    monkeypatch.setattr(_dbmod, "fetch_all", _wrap)


def _open(monkeypatch, m, main, sub=None):
    import db as _dbmod
    from streamlit.testing.v1 import AppTest
    from tests.conftest import goto
    from tests.test_so_close import _hook_aggrid, GRIDS
    GRIDS.clear()
    _hook_aggrid(monkeypatch)
    m.install(monkeypatch, _dbmod)
    at = AppTest.from_file(APP_FILE, default_timeout=120)
    at.secrets["supabase"] = {"url": "https://mock.local", "anon_key": "a", "service_role_key": "s"}
    at.secrets["auth"] = {"disabled": True}
    at.run()
    goto(at, main, sub)
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def _texts(at):
    out = [str(x.value) for x in at.markdown] + [str(x.value) for x in at.caption]
    out += [str(x.value) for x in at.warning] + [str(x.value) for x in at.error] + [str(x.value) for x in at.info]
    return "\n".join(out)


def _reads(m, table):
    return [fq for t, fq in m.fetch_calls if t == table]


# ── ① 구매 관리 → 입고 현황 material_stock ─────────────────────────────

def _seed_material_stock(m):
    m.tables["material_stock"] = [
        {"material_id": f"M{i:04d}", "raw_name": f"자재{i}", "material_type": "SUS304", "spec": "D10",
         "main_supplier": "공급사", "current_stock": 0, "total_received": 0, "total_consumed": 0,
         "last_txn_date": None} for i in range(N)]
    m.tables["material_stock"].append(
        {"material_id": "T621", "raw_name": "끝 공구", "material_type": None, "spec": None,
         "main_supplier": "두리", "current_stock": 7, "total_received": 7, "total_consumed": 0,
         "last_txn_date": "2026-10-27"})


def _kpi_row(at, label):
    return next((str(x.value) for x in at.markdown
                 if 'class="kpi-row"' in str(x.value) and label in str(x.value)), "")


def test_receipt_status_material_stock_reads_past_1000(monkeypatch):
    """1,006행(운영 2026-10-28) — 1,000행 뒤의 T621 까지 읽어 보유 소재 1종."""
    m = _mock()
    _seed_material_stock(m)
    at = _open(monkeypatch, m, "po", "rstat")
    assert any("offset=1000" in fq for fq in _reads(m, "material_stock")), _reads(m, "material_stock")
    kpi = _kpi_row(at, "보유 소재")
    assert ">1종<" in kpi, kpi                                   # 예전: T621 이 잘려 0종
    assert "뒤쪽은 표시되지 않습니다" not in _texts(at)


def test_receipt_status_material_stock_truncated_warns(monkeypatch):
    m = _mock()
    _seed_material_stock(m)
    _force_truncated(monkeypatch, "material_stock")
    at = _open(monkeypatch, m, "po", "rstat")
    assert any("뒤쪽은 표시되지 않습니다" in str(w.value) for w in at.warning), _texts(at)[:400]
    kpi = _kpi_row(at, "보유 소재")
    assert "미확인" in kpi and ">1종<" not in kpi, kpi


# ── ② 마스터 → 자재 실사 시트 / ③ 중복 후보 찾기 materials ─────────────────

def _seed_materials(m, dup_tail=False):
    m.tables["materials"] = [
        {"material_id": f"M{i:04d}", "raw_name": f"S304 Ø{i}", "material_type": "SUS304", "spec": f"φ{i}*{i}L",
         "unit": "EA", "main_supplier": "명진", "stock_qty": 0, "applied_pn": None, "procurement_type": "도급",
         "archived_at": None} for i in range(N)]
    if dup_tail:      # 1,000행 뒤에 같은 규격·재질 두 건(표기만 다름)
        for mid, nm, sp in (("M9998", "S304 Ø777*7", "φ777*7L"), ("M9999", "STS304환봉 777￠7ℓ", "Ø777x7")):
            m.tables["materials"].append(
                {"material_id": mid, "raw_name": nm, "material_type": "STS304", "spec": sp, "unit": "EA",
                 "main_supplier": "명진", "stock_qty": 0, "applied_pn": None, "procurement_type": "도급",
                 "archived_at": None})


def _dl_labels(at):
    return [getattr(b, "label", "") or "" for b in at.get("download_button")]


def test_count_sheet_covers_all_materials(monkeypatch):
    m = _mock()
    _seed_materials(m)
    at = _open(monkeypatch, m, "master")
    labels = [l for l in _dl_labels(at) if "소재 실사 시트" in l]
    assert labels and f"전체 {N}종" in labels[0], labels          # 예전: 1,000종에서 잘림
    assert any("offset=1000" in fq for fq in _reads(m, "materials"))


def test_count_sheet_blocked_when_truncated(monkeypatch):
    """실사 시트는 전수 전제 — 절단이면 내려받기 버튼 자체가 없고 오류 안내."""
    m = _mock()
    _seed_materials(m)
    _force_truncated(monkeypatch, "materials")
    at = _open(monkeypatch, m, "master")
    assert not [l for l in _dl_labels(at) if "소재 실사 시트" in l], _dl_labels(at)
    assert any("출력하지 않습니다" in str(e.value) for e in at.error), [str(e.value) for e in at.error]


def _scan(at):
    next(b for b in at.button if b.key == "mg_scan").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def test_duplicate_scan_reaches_tail_pair(monkeypatch):
    m = _mock()
    _seed_materials(m, dup_tail=True)
    at = _scan(_open(monkeypatch, m, "master"))
    t = _texts(at)
    assert "중복 후보 1쌍" in t and "미검사" not in t, t[-600:]       # 예전: 1,000행 뒤 쌍을 못 봄


def test_duplicate_scan_truncated_says_partial(monkeypatch):
    m = _mock()
    _seed_materials(m)
    _force_truncated(monkeypatch, "materials")
    at = _scan(_open(monkeypatch, m, "master"))
    assert any("일부 자재 미검사" in str(w.value) for w in at.warning), _texts(at)[-600:]
    assert not any("중복 자재가 없습니다" in str(s.value) for s in at.success)   # '없음' 확정 금지


# ── ④ 공정 관리 → 투입 등록 W LOT 잔여 ───────────────────────────────

def _seed_w_lots(m):
    """WTAIL 입고 10(맨 앞) … 다른 LOT 입고·투입 쌍 … WTAIL 전량 투입 −10(1,000행 뒤).
    끝까지 읽으면 WTAIL 잔여 0(목록에 없음), 1,000행에서 자르면 잔여 10 으로 보인다."""
    tx = [{"txn_id": 1, "lot_number": "WTAIL", "material_id": "M0001", "qty": 10,
           "txn_type": "RECEIPT", "ref_id": None}]
    for i in range(N // 2):
        lot = f"W{i:05d}"
        tx.append({"txn_id": 2 + 2 * i, "lot_number": lot, "material_id": "M0002", "qty": 1,
                   "txn_type": "RECEIPT", "ref_id": None})
        tx.append({"txn_id": 3 + 2 * i, "lot_number": lot, "material_id": "M0002", "qty": -1,
                   "txn_type": "PROD_INPUT", "ref_id": None})
    tx.append({"txn_id": 9999, "lot_number": "WTAIL", "material_id": "M0001", "qty": -10,
               "txn_type": "PROD_INPUT", "ref_id": None})
    tx.append({"txn_id": 10000, "lot_number": "WOPEN", "material_id": "M0003", "qty": 5,
               "txn_type": "RECEIPT", "ref_id": None})
    m.tables["inventory_transactions"] = tx


def test_input_w_lot_balance_reads_past_1000(monkeypatch):
    from tests.test_so_close import _grid_text
    m = _mock()
    _seed_w_lots(m)
    at = _open(monkeypatch, m, "proc", "in")
    assert any("offset=1000" in fq for fq in _reads(m, "inventory_transactions"))
    g = _grid_text()
    assert "WOPEN" in g and "WTAIL" not in g, g[:400]           # 예전: WTAIL 잔여 10 으로 보임


def test_input_blocked_when_w_lots_truncated(monkeypatch):
    from tests.test_so_close import _grid_text
    m = _mock()
    _seed_w_lots(m)
    _force_truncated(monkeypatch, "inventory_transactions")
    at = _open(monkeypatch, m, "proc", "in")
    assert any("투입 등록을 막았습니다" in str(e.value) for e in at.error), [str(e.value) for e in at.error]
    assert "WOPEN" not in _grid_text()                             # 잔여 LOT 선택 그리드 없음


# ── ⑤ 원가 확인 → 매입 단가 조회 구분 목록 ────────────────────────────

def _seed_ledger(m):
    m.tables["purchase_ledger"] = [{"ledger_id": i + 1, "category": "MAT_A"} for i in range(N)]
    m.tables["purchase_ledger"].append({"ledger_id": N + 1, "category": "ZZ_TAIL"})


def _cats_metric(at):
    return next((x.value for x in at.metric if x.label == "category 보유 종류"), None)


def test_cost_category_list_reads_past_1000(monkeypatch):
    m = _mock()
    _seed_ledger(m)
    at = _open(monkeypatch, m, "cost")
    assert _cats_metric(at) == "2종", _cats_metric(at)              # 예전: ZZ_TAIL 이 잘려 1종
    ms = next(x for x in at.multiselect if x.key == "cost_pl_cats")
    assert "ZZ_TAIL" in ms.options, ms.options


def test_cost_category_truncated_warns(monkeypatch):
    m = _mock()
    _seed_ledger(m)
    _force_truncated(monkeypatch, "purchase_ledger")
    at = _open(monkeypatch, m, "cost")
    assert _cats_metric(at) == "미확인", _cats_metric(at)
    assert any("구분 목록 일부 미확인" in str(w.value) for w in at.warning)


# ── ⑥ 수주 관리 → 제품 확인 필요 ───────────────────────────────────

def _seed_products(m):
    m.seed(so_id=301, so_status="CONFIRMED", lines=[(901, 10, 0, 10, "PENDING")],
           pn="TAIL-PN", product_id="PZZZ")
    tail = m.tables["products"].pop()                  # 시드 제품을 1,000행 뒤로
    m.tables["products"] = [
        {"product_id": f"P{i:05d}", "pn": f"PN{i}", "archived_at": None, "archive_reason": None,
         "sale_price": 1, "customer": "X", "item_name": "-", "material": "-"} for i in range(N)] + [tail]


def _check_card(at):
    return [x for x in at.expander if "제품 확인 필요" in str(x.label)]


def test_product_check_reads_products_past_1000(monkeypatch):
    """활성 제품이 1,000행 뒤에 있어도 '미등록'으로 띄우지 않는다(예전: 잘려서 미등록 → 신규 등록 유도)."""
    m = _mock()
    _seed_products(m)
    at = _open(monkeypatch, m, "so", "input")
    assert any("offset=1000" in fq for fq in _reads(m, "products"))
    assert not _check_card(at), [x.label for x in _check_card(at)]


def test_product_check_truncated_notes_and_skips_unknown(monkeypatch):
    """제품 조회가 잘려 못 찾은 제품은 '미등록'이 아니라 미확인 — 카드에 올리지 않고 경고."""
    m = _mock()
    _seed_products(m)
    _force_truncated(monkeypatch, "products", drop=("product_id", "PZZZ"))
    at = _open(monkeypatch, m, "so", "input")
    assert not _check_card(at), [x.label for x in _check_card(at)]
    assert "제품 확인 필요 — 수주·제품 조회가 너무 많아 일부 미확인" in _texts(at)
