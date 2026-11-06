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


def test_manual_add_picker_resets_after_add(monkeypatch):
    """T1(H3): -RE-P 30 추가 뒤 같은 제품 기본 100 추가 → 2번 줄은 기본 품번(앞 선택이 남지 않음)."""
    m = _so_input_mock()
    at = _manual_pick(monkeypatch, m, "H11SDF")
    _add(at, 30, RE5)
    assert at.selectbox(key="m_cpn_pick_P0005").value == BASE5
    _add(at, 100)
    assert [(i["line_no"], i["customer_part_no"], i["qty"]) for i in at.session_state["m_so_items"]] == [
        (1, RE5, 30), (2, BASE5, 100)]


def test_manual_add_delete_and_readd(monkeypatch):
    """T2: 3줄(기본·RE·RV) 뒤 2번(RE) 삭제 → 번호 다시 매김, RE 재추가 → 3번, 합계 그대로."""
    m = _so_input_mock()
    at = _manual_pick(monkeypatch, m, "H11SDF")
    _add(at, 100)
    _add(at, 30, RE5)
    _add(at, 20, RV5)
    at.button(key="so_item_1_del").click()
    at.run()
    assert [(i["line_no"], i["customer_part_no"]) for i in at.session_state["m_so_items"]] == [
        (1, BASE5), (2, RV5)]
    _add(at, 30, RE5)
    its = at.session_state["m_so_items"]
    assert [(i["line_no"], i["customer_part_no"], i["qty"]) for i in its] == [
        (1, BASE5, 100), (2, RV5, 20), (3, RE5, 30)]
    assert sum(i["qty"] for i in its) == 150


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


# ── 매핑 등록(제품 확인 카드 신규 등록 폼): "출하 품번으로 구분" → kind (PN r2 H1·H2) ──
def _card_mock(two=False):
    from tests.test_hotfix2_followup_a import _mock, _seed_so_cards
    from tests.test_hotfix2_followup_b import _allow_product_writes
    m = _mock()
    _seed_so_cards(m)                                   # 913 = 미등록 라인(거래처 품번 CP-913)
    if two:                                             # 두 번째 미등록 그룹(CP-914, 납기 뒤)
        m.seed(so_id=404, so_status="CONFIRMED", lines=[(914, 5, 0, 5, "PENDING")],
               pn="NEW-PN2", product_id="PNEW2")
        for it in m.tables["sales_order_items"]:
            if it["soi_id"] == 914:
                it["product_id"], it["due_date"] = None, "2026-10-25"
    _allow_product_writes(m)
    return m


def _var_boxes(at):
    return [c for c in at.checkbox if str(c.key or "").startswith("sochk_var_")]


def _register(at, pn, check):
    if check:
        _var_boxes(at)[0].check()
    next(t for t in at.text_input if t.label == "품번 *").set_value(pn)
    next(b for b in at.button if "등록하고 진행" in str(b.label)).click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]


def _maps(m):
    return [w[2] for w in m.writes if w[0] == "insert" and w[1] == "customer_part_mapping"]


def test_mapping_register_default_payload_unchanged(monkeypatch):
    from tests.test_hotfix2_followup_a import _open
    m = _card_mock()
    at = _open(monkeypatch, m, "so", "input")
    assert [c.value for c in _var_boxes(at)] == [False]          # 기본 해제, 신규 등록 폼 안
    _register(at, "NEW-913", check=False)
    maps = _maps(m)
    assert len(maps) == 1 and "kind" not in maps[0], maps        # 묶음 전 payload(열 생략 = 기본 alias)
    assert maps[0]["customer_part_no"] == "CP-913"


def test_mapping_register_checked_is_variant(monkeypatch):
    from tests.test_hotfix2_followup_a import _open
    m = _card_mock()
    at = _open(monkeypatch, m, "so", "input")
    _register(at, "NEW-913", check=True)
    maps = _maps(m)
    assert len(maps) == 1 and maps[0]["kind"] == "variant", maps


def test_mapping_checkbox_not_inherited_by_next_group(monkeypatch):
    """T7(H1): 1번 그룹 체크 후 등록 → rerun 뒤 남은 그룹 체크박스는 False, 그 등록은 alias."""
    from tests.test_hotfix2_followup_a import _open
    m = _card_mock(two=True)
    at = _open(monkeypatch, m, "so", "input")
    assert len(_var_boxes(at)) == 2
    _register(at, "NEW-913", check=True)
    left = _var_boxes(at)
    assert len(left) == 1 and left[0].value is False, [(c.key, c.value) for c in left]
    _register(at, "NEW-914", check=False)
    kinds = [(mp["customer_part_no"], mp.get("kind")) for mp in _maps(m)]
    assert kinds == [("CP-913", "variant"), ("CP-914", None)], kinds


def test_mapping_variant_insert_failure_warns(monkeypatch):
    """T8(H2): 체크된 매핑 insert 실패 → 라인 연결은 완료, 다음 화면에 경고 1건 + log_error."""
    import db
    from tests.test_hotfix2_followup_a import _open
    m = _card_mock()
    at = _open(monkeypatch, m, "so", "input")
    m.insert_raise_for = "customer_part_mapping"
    logged = []
    monkeypatch.setattr(db, "log_error", lambda *a, **k: logged.append((a, k)))
    _register(at, "NEW-913", check=True)
    ups = [w for w in m.writes if w[0] == "update" and w[1] == "sales_order_items"]
    assert ups and ups[0][2]["canonical_pn"] == "NEW-913"          # 라인 연결 완료
    warns = [str(w.value) for w in at.warning] + [str(x.value) for x in at.markdown]
    assert sum("출하 품번 매핑은 저장되지 않았습니다" in w for w in warns) == 1, warns
    assert any("출하 품번 매핑 저장 실패" in str(a[0][1]) for a in logged), logged


def test_mapping_checkbox_hidden_for_dormant_activation(monkeypatch):
    """H2: 휴면 해제 분기(매핑 저장 없음)에는 체크박스가 없다."""
    from tests.test_hotfix2_followup_a import _mock, _open
    from tests.test_hotfix2_followup_b import _allow_product_writes
    m = _mock()
    m.seed(so_id=501, so_status="CONFIRMED", lines=[(921, 10, 0, 10, "PENDING")], pn="DORM-PN",
           product_id="PDORM")
    next(p for p in m.tables["products"] if p["product_id"] == "PDORM")["archived_at"] = "2026-09-01"
    _allow_product_writes(m)
    at = _open(monkeypatch, m, "so", "input")
    assert any(str(b.key or "").endswith("_act") for b in at.button)
    assert not _var_boxes(at)


# ── T3 정정 이력(14): 이력엔 거래처 품번이 없어 같은 전표 라인(si_id)으로 — si_id·pn 없는 행 포함 ──
def _rev_rows():
    base = {"action": "EDIT", "qty_before": 500, "qty_after": 400, "reason": "r",
            "created_by": "t", "created_at": "2026-09-01T10:00:00"}
    return [dict(base, rev_no=0, si_id=1, pn="4PDVN-03"),
            dict(base, rev_no=0, si_id=None, pn=None),
            dict(base, rev_no=0, si_id=1, pn=None)]


def _rev_table(at):
    return next(m.value for m in at.markdown
                if '<table class="tt"' in m.value and "v1" in m.value)


def test_revision_history_variant_labels(rev_db, monkeypatch):
    rf._seed()
    rf.REVS[:] = _rev_rows()
    _with_variants(monkeypatch, [{"product_id": "P1", "customer_part_no": "4S4PDVN-03",
                                  "kind": "variant"}])
    at = rf._pick_confirmed(rf._open())
    t = _rev_table(at)
    assert t.count("4PDVN-03 (4S4PDVN-03)") == 2, t                # si_id 있음(pn 없음 = 라인 pn 폴백)
    assert ">-<" in t                                               # si_id·pn 둘 다 없음 = 묶음 전처럼 "-"


def test_revision_history_without_variants_unchanged(rev_db):
    rf._seed()
    rf.REVS[:] = _rev_rows()
    at = rf._pick_confirmed(rf._open())
    t = _rev_table(at)
    assert "(4S4PDVN-03)" not in t and t.count(">4PDVN-03<") == 2, t


# ── T4 출고 현황(25·26·27): 출하 품번 있을 때만 '품번' 열, 이력 품번 내부 앞 ──
def _dstat(monkeypatch, variant):
    from tests.test_hotfix2_followup_a import _open
    from tests.test_hotfix2_followup_bcd_r3 import _sales_mock
    m = _sales_mock()                                   # PSR · si 9101 customer_pn CP-981 · soi 981 CP-981
    m.tables["customer_part_mapping"] = [{"mapping_id": 1, "customer": "(주)디아이씨두서공장",
                                          "customer_part_no": "CP-981", "product_id": "PSR",
                                          "canonical_pn": "SR-PN",
                                          "kind": "variant" if variant else "alias"}]
    return _open(monkeypatch, m, "ship", "dstat")


def _tt(at, col):
    """toss_table(HTML) 중 헤더에 col 이 있는 표들."""
    return [m.value for m in at.markdown
            if '<table class="tt"' in m.value and f">{col}<" in m.value]


def test_dstat_detail_columns_only_with_variant(monkeypatch):
    at = _dstat(monkeypatch, True)
    lines, recon = _tt(at, "LOT"), _tt(at, "전표 외 기납품")
    assert lines and ">품번<" in lines[0] and "SR-PN (CP-981)" in lines[0], lines
    assert recon and ">품번<" in recon[0] and "SR-PN (CP-981)" in recon[0], recon
    at.radio(key="dstat_view").set_value("출고 이력")
    at.run()
    hist = _tt(at, "품명")
    assert hist and "SR-PN (CP-981)" in hist[0], hist


def test_dstat_without_variant_has_no_new_columns(monkeypatch):
    at = _dstat(monkeypatch, False)
    lines, recon = _tt(at, "LOT"), _tt(at, "전표 외 기납품")
    assert lines and recon
    assert ">품번<" not in lines[0] and ">품번<" not in recon[0]       # 묶음 전 표(열 없음)
    at.radio(key="dstat_view").set_value("출고 이력")
    at.run()
    hist = _tt(at, "품명")
    assert hist and "SR-PN" in hist[0] and "(CP-981)" not in hist[0]


# ── T5 확정 계획 오류(22)·정정 경고(24): 문구 품번 ──
def _plan_err_texts(at):
    at.button(key="cf_go").click().run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return [str(e.value) for e in at.error]


def test_confirm_plan_error_label(rev_db, monkeypatch):
    rf._seed()
    rf.SHIP_ITEMS[1]["soi_id"] = 99                     # 작성중 라인의 수주 라인이 없음
    _with_variants(monkeypatch, [{"product_id": "P1", "customer_part_no": "4S4PDVN-03",
                                  "kind": "variant"}])
    errs = _plan_err_texts(rf._open())
    assert any("4PDVN-03 (4S4PDVN-03): 수주 라인 없음" in e for e in errs), errs


def test_confirm_plan_error_label_without_variants(rev_db):
    rf._seed()
    rf.SHIP_ITEMS[1]["soi_id"] = 99
    errs = _plan_err_texts(rf._open())
    assert any("4PDVN-03: 수주 라인 없음" in e for e in errs), errs


# ── T6 variant 조회 실패(열 없음 모사) → 묶음 전 표시, 예외 없음 ──
def test_variant_fetch_failure_falls_back(ship_db, monkeypatch):
    import db
    base = db.fetch

    def _f(table, select="*", filter_query="", limit=1000, **kw):
        if table == "customer_part_mapping":
            raise RuntimeError("400 column customer_part_mapping.kind does not exist")
        return base(table, select, filter_query, limit, **kw)
    monkeypatch.setattr(db, "fetch", _f)
    at = bd._open_shipping(ship_db)
    sel = _search(at, "4PDVN")
    assert any(l.startswith("4PDVN-03 | SO-100 | 미납 2,000") for l in sel.options), list(sel.options)
    ed = next(d.value for d in at.dataframe
              if "잔량" in d.value.columns and "출고" in d.value.columns)
    assert set(ed["품번"]) == {"4PDVN-03", "MRG6-07"}


# ── T4(28) 발주 소요량 › 미납 수주 라인: 출하 품번 있을 때만 '품번' 열(거래처 앞) ──
def _po_req(monkeypatch, kind):
    from tests.test_hotfix2_followup_a import _mock, _open
    m = _mock()
    m.seed(so_id=901, so_status="CONFIRMED", lines=[(991, 10, 0, 10, "PENDING")], pn="MR-PN",
           product_id="PMR")                                     # customer_part_no CP-991
    m.tables["bom"] = [{"bom_id": 1, "product_id": "PMR", "material_id": "M1",
                        "raw_material_name": "SUS", "qty_per_pc": 1, "shared_factor": 1,
                        "process_type": "MATERIAL"}]
    m.tables["customer_part_mapping"] = [{"mapping_id": 1, "customer": "x", "customer_part_no": "CP-991",
                                          "product_id": "PMR", "canonical_pn": "MR-PN", "kind": kind}]
    at = _open(monkeypatch, m, "po", "new")
    return next(v for v in (x.value for x in at.markdown)
                if '<table class="tt"' in v and ">순생산<" in v)


def test_po_requirement_pending_lines_variant_column(monkeypatch):
    t = _po_req(monkeypatch, "variant")
    assert ">품번<" in t and "<td>CP-991 (MR-PN)</td>" in t, t


def test_po_requirement_pending_lines_without_variant_unchanged(monkeypatch):
    t = _po_req(monkeypatch, "alias")
    assert ">품번<" not in t and "CP-991" not in t, t                # 묶음 전 표(열 없음)


# P3-1a(2026-11-06): 취소 경고(「원장에 차감 기록이 없는」)의 출하 품번 표기 테스트 2건은 새 경로로 이식 —
#   차감 기록 없는 라인은 issue_mismatch 로 사전 잠금되고 안내에 같은 표기(line_pn)가 쓰인다:
#   tests/test_revise_screen.py::test_blocked_notice_uses_variant_label[True|False]
