# -*- coding: utf-8 -*-
"""PN 묶음(거래처 품번 표시 r2, 2026-11-02) — 화면 AppTest.

출하 품번(customer_part_mapping.kind='variant')만 라인에 병기하고, variant 0건이면
묶음 전과 같은 문자열(대조군). 출고 관리 = 내부 품번 앞.
"""
import pytest

from tests import test_bulk_delivery as bd
from tests import test_shipment_revision_flow as rf
from tests.test_bulk_delivery import ship_db  # noqa: F401  (fixture)
from tests.test_shipment_revision_flow import rev_db  # noqa: F401  (fixture)

pytestmark = rf.pytestmark


def _with_variants(monkeypatch, rows):
    """현재 db.fetch 목 위에 customer_part_mapping 응답만 얹는다(kind 필터 무시하는 목 대비 kind 포함)."""
    import db
    base = db.fetch

    def _f(table, select="*", filter_query="", limit=1000, **kw):
        if table == "customer_part_mapping":
            return [dict(r) for r in rows]
        return base(table, select, filter_query, limit, **kw)
    monkeypatch.setattr(db, "fetch", _f)


def _errors(at):
    return [str(e.value) for e in at.error]


# ── ③ 출고 전표: 미납 초과 라인 — 같은 내부 품번·다른 거래처 품번 2라인이 모두 보고 (버그 21) ──
def _seed_overp():
    rf._seed()
    rf.SHIP_ITEMS.append(
        {"si_id": 3, "shipment_id": 2, "soi_id": 12, "so_id": 100,
         "sched_id": None, "product_id": "P1", "pn": "4PDVN-03",
         "customer_pn": "4PDVN-03-RE", "item_name": None,
         "customer": "㈜엠제이티", "so_number": "SO-100", "qty": 100,
         "unit": "EA", "unit_price": 1000})
    rf.LINES[11].update(received_qty=1950, pending_qty=50)          # 미납 50 < 출고 100
    rf.LINES[12] = dict(rf.LINES[11], soi_id=12, customer_part_no="4PDVN-03-RE",
                        qty=100, received_qty=50, pending_qty=50)    # 미납 50 < 출고 100


def test_slip_overpending_reports_both_lines_with_same_internal_pn(rev_db, monkeypatch):
    _seed_overp()
    _with_variants(monkeypatch, [{"product_id": "P1", "customer_part_no": "4PDVN-03-RE",
                                  "kind": "variant"}])
    at = rf._open()
    assert not at.exception, [str(e.value) for e in at.exception]
    over = [e for e in _errors(at) if "수주 미납보다 많이 담긴 라인" in e]
    assert len(over) == 1, _errors(at)
    assert over[0].count("출고 100 > 미납 50") == 2, over[0]
    assert "4PDVN-03 (4PDVN-03-RE): 출고 100" in over[0]
    assert "4PDVN-03: 출고 100" in over[0]                     # 별칭(4S4PDVN-03)은 내부 품번만
    assert at.button(key="cf_go").proto.disabled
    ed = next(d.value for d in at.dataframe if "선택" in d.value.columns)
    assert list(ed["품번"]) == ["4PDVN-03", "4PDVN-03 (4PDVN-03-RE)"]


def test_slip_overpending_without_variants_keeps_old_labels(rev_db):
    """대조군: variant 0건 — 문구는 묶음 전 품번 그대로, 그래도 두 라인 모두 보고(키 = soi_id)."""
    _seed_overp()
    at = rf._open()
    over = [e for e in _errors(at) if "수주 미납보다 많이 담긴 라인" in e]
    assert len(over) == 1 and over[0].count("4PDVN-03: 출고 100 > 미납 50") == 2, _errors(at)
    ed = next(d.value for d in at.dataframe if "선택" in d.value.columns)
    assert list(ed["품번"]) == ["4PDVN-03", "4PDVN-03"]


# ── ② 출고 등록: 검색 셀렉트박스 라벨·미납 회차 표 ──
def _search(at, q):
    at.text_input(key="ship_q").set_value(q)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return next(s for s in at.selectbox if s.key == "ship_pick")


def test_ship_register_labels_show_variant_internal_first(ship_db, monkeypatch):
    _with_variants(monkeypatch, [{"product_id": "P1", "customer_part_no": "4S4PDVN-03",
                                  "kind": "variant"}])
    at = bd._open_shipping(ship_db)
    sel = _search(at, "4PDVN")
    labels = list(sel.options)                  # AppTest 옵션 = format_func 적용 문자열
    assert any(l.startswith("4PDVN-03 (4S4PDVN-03) | SO-100 | 미납 2,000") for l in labels), labels
    assert any(l.startswith("MRG6-07 | SO-101") for l in labels), labels     # cpn 없음 = 그대로
    ed = next(d.value for d in at.dataframe
              if "잔량" in d.value.columns and "출고" in d.value.columns)
    assert set(ed["품번"]) == {"4PDVN-03 (4S4PDVN-03)", "MRG6-07"}


def test_ship_register_labels_unchanged_without_variants(ship_db):
    """대조군: 매핑이 별칭뿐(목 응답 없음) — 라벨·표가 묶음 전과 같은 문자열."""
    at = bd._open_shipping(ship_db)
    sel = _search(at, "4PDVN")
    labels = list(sel.options)                  # AppTest 옵션 = format_func 적용 문자열
    assert any(l.startswith("4PDVN-03 | SO-100 | 미납 2,000") for l in labels), labels
    ed = next(d.value for d in at.dataframe
              if "잔량" in d.value.columns and "출고" in d.value.columns)
    assert set(ed["품번"]) == {"4PDVN-03", "MRG6-07"}


def test_ship_register_payload_keeps_internal_pn(ship_db, monkeypatch):
    """표시만 바뀌고 전표 품목 payload(pn·customer_pn)는 묶음 전과 같다."""
    _with_variants(monkeypatch, [{"product_id": "P1", "customer_part_no": "4S4PDVN-03",
                                  "kind": "variant"}])
    at = bd._open_shipping(ship_db)
    bd._register(at)
    items = [r for t, recs in bd.INSERTED if t == "shipment_items" for r in recs]
    assert items and {(r["pn"], r["customer_pn"]) for r in items} == {
        ("4PDVN-03", "4S4PDVN-03"), ("MRG6-07", "MRG6-07")}


# ── ① 납품 스케줄: 납기 입력 표·편집 캡션(거래처 앞), 간트 툴팁(full=False) — 행 묶음은 제품 단위 그대로 ──
from tests import test_delivery_schedule_gantt as sg  # noqa: E402
from tests.test_delivery_schedule_gantt import sched_db  # noqa: E402,F401  (fixture)


def _sched_variant_fetch(monkeypatch, variant=True):
    """soi 1 = 출하 품번 4PDVN-02-RE(P0002), 나머지는 내부 품번과 같은 거래처 품번."""
    import db

    def _f(table, select="*", filter_query="", limit=1000, **kw):
        if table == "customer_part_mapping":
            return ([{"product_id": "P0002", "customer_part_no": "4PDVN-02-RE",
                      "kind": "variant"}] if variant else [])
        rows = sg._fetch(table, select, filter_query, limit, **kw)
        if table == "sales_order_items":
            for r in rows:
                r["product_id"] = f"P{r['soi_id']:04d}"
                if r["soi_id"] == 1:
                    r["product_id"], r["customer_part_no"] = "P0002", "4PDVN-02-RE"
        return rows
    monkeypatch.setattr(db, "fetch", _f)


def _texts(at):
    out = [m.value for m in at.markdown] + [c.value for c in at.caption]
    out += [d.value.to_string() for d in at.dataframe]
    return "\n".join(str(x) for x in out)


def test_schedule_input_shows_variant_and_edit_caption(sched_db, monkeypatch):
    _sched_variant_fetch(monkeypatch)
    at = sg._open_schedule_tab(sched_db)
    at.session_state["sch_view"] = "납기 입력"
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    t = _texts(at)
    assert "4PDVN-02-RE (4PDVN-02)" in t, t[:2000]
    assert any(c.value == "202604080013-MJT · 4PDVN-02-RE (4PDVN-02) · 미납 91,648"
               for c in at.caption), [c.value for c in at.caption]
    assert "4PDVN-03 (" not in t                                  # 같은 품번 라인은 한 번만


def test_schedule_gantt_tooltip_variant_rows_unchanged(sched_db, monkeypatch):
    _sched_variant_fetch(monkeypatch)
    at = sg._open_schedule_tab(sched_db)
    html = sg._gantt_html(at)
    assert html and "<b>4PDVN-02-RE</b>" in html                  # 툴팁 = 출하 품번(좁은 칸)
    assert ">4PDVN-02<" in html or "4PDVN-02</" in html           # 행 라벨 = 내부 품번(제품 단위 묶음)


def test_schedule_without_variants_is_unchanged(sched_db, monkeypatch):
    """대조군: variant 0건 — 캡션·표·간트가 내부 품번 하나(묶음 전 문자열)."""
    _sched_variant_fetch(monkeypatch, variant=False)
    at = sg._open_schedule_tab(sched_db)
    html = sg._gantt_html(at)
    assert "<b>4PDVN-02</b>" in html and "4PDVN-02-RE" not in html
    at.session_state["sch_view"] = "납기 입력"
    at.run()
    assert any(c.value == "202604080013-MJT · 4PDVN-02 · 미납 91,648" for c in at.caption)
    assert "4PDVN-02-RE (4PDVN-02)" not in _texts(at)     # 원문 거래처 품번은 기존 '제품 확인' 카드에만


# ── ④ 수주 입력 수동 추가: 거래처 품번(출하 품번) 셀렉트박스 (31) ──
import re as _re  # noqa: E402

BASE5, RE5, RV5 = "H11SDF-2C-10-01", "H11SDF-2C-10-01-RE-P", "H11SDF-3C-10-01-RV-P"


def _so_input_mock(variants=True):
    from tests.test_uiux_u1b import _ManualSOMock
    m = _ManualSOMock()
    m.tables["products"] = [
        {"product_id": "P0005", "pn": BASE5, "alias_list": None, "archived_at": None,
         "item_name": "SEAT", "sale_price": None},
        {"product_id": "P0100", "pn": "8HFDV-VM-05", "alias_list": "4S8HFDV-VM-05;PM",
         "archived_at": None, "item_name": "VALVE", "sale_price": None}]
    kind = "variant" if variants else "alias"
    m.tables["customer_part_mapping"] = [
        {"mapping_id": 14, "customer": "엠제이티", "customer_part_no": RE5, "product_id": "P0005",
         "canonical_pn": BASE5, "kind": kind},
        {"mapping_id": 15, "customer": "엠제이티", "customer_part_no": RV5, "product_id": "P0005",
         "canonical_pn": BASE5, "kind": kind},
        {"mapping_id": 16, "customer": "(주)엠제이티", "customer_part_no": RE5, "product_id": "P0005",
         "canonical_pn": BASE5, "kind": kind},                         # 거래처 표기만 다른 중복
        {"mapping_id": 30, "customer": "미진정밀", "customer_part_no": "4S8HFDV-VM-05;PM",
         "product_id": "P0100", "canonical_pn": "8HFDV-VM-05", "kind": "alias"}]
    orig = m.fetch

    def _f(table, select="*", filter_query="", limit=1000, cache=None):
        if table == "products" and "or=(" in (filter_query or ""):     # 목은 or=(…ilike…) 미지원 → 검색만 흉내
            from urllib.parse import unquote
            tok = _re.search(r"pn\.ilike\.\"?\*?([^*\",)]+)",
                             unquote(filter_query)).group(1).upper()
            return [dict(p) for p in m.tables["products"]
                    if tok in p["pn"].upper() or tok in str(p.get("alias_list") or "").upper()]
        return orig(table, select, filter_query, limit, cache)
    m.fetch = _f
    return m


def _manual_pick(monkeypatch, m, q):
    from tests.test_uiux_u1b import _manual_open
    at = _manual_open(monkeypatch, m, items=[])
    at.text_input(key="m_pn_q").set_value(q)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def _add(at, qty, cpn=None, key="m_cpn_pick_P0005"):
    if cpn is not None:
        at.selectbox(key=key).set_value(cpn)
    at.number_input(key="m_qty").set_value(qty)
    at.run()
    at.button(key="m_add_item").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]


def test_manual_add_variant_lines_saved_with_customer_pn(monkeypatch):
    m = _so_input_mock()
    at = _manual_pick(monkeypatch, m, "H11SDF")
    sel = at.selectbox(key="m_cpn_pick_P0005")
    assert list(sel.options) == [BASE5, RE5, RV5]                  # 기본 + variant(중복 제거)
    assert sel.value == BASE5
    _add(at, 100)                                                  # 기본 품번
    _add(at, 30, RE5)
    _add(at, 20, RV5)
    its = at.session_state["m_so_items"]
    assert [(i["customer_part_no"], i["canonical_pn"], i["product_id"]) for i in its] == [
        (BASE5, BASE5, "P0005"), (RE5, BASE5, "P0005"), (RV5, BASE5, "P0005")]
    rows = "\n".join(str(x.value) for x in at.markdown if "so-item-row" in str(x.value))
    assert f"2. {RE5} ({BASE5})" in rows and f"1. {BASE5}</b>" in rows
    from tests.test_uiux_u1b import _save
    _save(at)
    lines = sorted(m.tables["sales_order_items"], key=lambda r: r["line_no"])
    assert [(r["customer_part_no"], r["canonical_pn"], r["product_id"], r["qty"]) for r in lines] == [
        (BASE5, BASE5, "P0005", 100), (RE5, BASE5, "P0005", 30), (RV5, BASE5, "P0005", 20)]


def test_manual_add_without_variant_has_no_picker(monkeypatch):
    """대조군: 별칭만 있는 제품(P0100) — 셀렉트박스 없음, customer_part_no = 제품 pn(묶음 전과 같음)."""
    m = _so_input_mock()
    at = _manual_pick(monkeypatch, m, "8HFDV")
    assert not [s for s in at.selectbox if str(s.key or "").startswith("m_cpn_pick")]
    _add(at, 5)
    assert [(i["customer_part_no"], i["canonical_pn"]) for i in at.session_state["m_so_items"]] == [
        ("8HFDV-VM-05", "8HFDV-VM-05")]


def test_manual_add_p0005_without_variant_kind_has_no_picker(monkeypatch):
    """대조군: 매핑이 모두 alias(마이그레이션 직후·UPDATE 전) — P0005 도 셀렉트박스 없음."""
    m = _so_input_mock(variants=False)
    at = _manual_pick(monkeypatch, m, "H11SDF")
    assert not [s for s in at.selectbox if str(s.key or "").startswith("m_cpn_pick")]


# ── 매핑 등록(제품 확인 카드): "출하 품번으로 구분" 체크박스 → kind ──
def _register_card(monkeypatch, check):
    from tests.test_hotfix2_followup_a import _mock, _open, _seed_so_cards
    from tests.test_hotfix2_followup_b import _allow_product_writes
    m = _mock()
    _seed_so_cards(m)                                   # 913 = 미등록 라인(거래처 품번 CP-913)
    _allow_product_writes(m)
    at = _open(monkeypatch, m, "so", "input")
    cb = next(c for c in at.checkbox if str(c.key or "").endswith("_variant"))
    assert cb.value is False                            # 기본 해제
    if check:
        cb.check()
        at.run()
    next(t for t in at.text_input if t.label == "품번 *").set_value("NEW-913")
    next(b for b in at.button if "등록하고 진행" in str(b.label)).click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return [w[2] for w in m.writes if w[0] == "insert" and w[1] == "customer_part_mapping"]


def test_mapping_register_default_payload_unchanged(monkeypatch):
    maps = _register_card(monkeypatch, check=False)
    assert len(maps) == 1 and "kind" not in maps[0], maps            # 묶음 전 payload(열 생략 = 기본 alias)
    assert maps[0]["customer_part_no"] == "CP-913"


def test_mapping_register_checked_is_variant(monkeypatch):
    maps = _register_card(monkeypatch, check=True)
    assert len(maps) == 1 and maps[0]["kind"] == "variant", maps
