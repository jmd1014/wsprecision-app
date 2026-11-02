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
