# -*- coding: utf-8 -*-
"""utils.line_pn — 출하 품번(variant)만 병기 (PN 묶음 r2 2026-11-02)."""
from utils.line_pn import line_pn, load_variants

BASE = "H11SDF-2C-10-01"
RE = "H11SDF-2C-10-01-RE-P"
VS = {("P0005", RE.upper())}


def test_variant_customer_first_by_default():
    assert line_pn({"customer_part_no": RE, "canonical_pn": BASE,
                    "product_id": "P0005"}, VS) == f"{RE} ({BASE})"
    assert line_pn({"customer_pn": RE, "pn": BASE, "product_id": "P0005"},
                   VS) == f"{RE} ({BASE})"


def test_variant_internal_first_and_narrow():
    si = {"customer_pn": RE, "pn": BASE, "product_id": "P0005"}
    assert line_pn(si, VS, internal_first=True) == f"{BASE} ({RE})"
    assert line_pn(si, VS, full=False) == RE
    assert line_pn(si, VS, full=False, internal_first=True) == BASE


def test_alias_shows_internal_only():
    # 미진 ERP 코드 — 글자는 달라도 variant 가 아니면 묶음 전과 같은 내부 품번 하나
    row = {"customer_part_no": "4S8HFDV-VM-05;PM", "canonical_pn": "8HFDV-VM-05",
           "product_id": "P0100"}
    assert line_pn(row, VS) == "8HFDV-VM-05"
    assert line_pn(row, VS, internal_first=True) == "8HFDV-VM-05"
    # 같은 품번이라도 다른 제품의 variant 로는 병기 안 함
    assert line_pn({"customer_pn": RE, "pn": BASE, "product_id": "P9999"}, VS) == BASE


def test_same_empty_and_missing_product():
    assert line_pn({"customer_pn": BASE, "pn": BASE, "product_id": "P0005"}, VS) == BASE
    assert line_pn({"customer_pn": "", "pn": BASE, "product_id": "P0005"}, VS) == BASE
    assert line_pn({"customer_pn": RE, "pn": None, "product_id": "P0005"}, VS) == RE
    assert line_pn({"customer_pn": RE, "pn": BASE}, VS) == BASE      # product_id 없음
    assert line_pn({}, VS) == "-"
    assert line_pn(None, VS) == "-"
    assert line_pn({"customer_pn": RE, "pn": BASE, "product_id": "P0005"},
                   frozenset()) == BASE                                 # variant 0건 = 묶음 전


def test_case_insensitive():
    assert line_pn({"customer_pn": RE.lower(), "pn": BASE, "product_id": "P0005"},
                   VS) == f"{RE.lower()} ({BASE})"
    assert line_pn({"customer_pn": BASE.lower(), "pn": BASE, "product_id": "P0005"},
                   {("P0005", BASE.upper())}) == BASE                   # 대소문자만 다름 = 같음


def test_load_variants_filters_kind():
    calls = []

    def _fetch(table, select, filt):
        calls.append((table, select, filt))
        return [{"product_id": "P0005", "customer_part_no": f" {RE.lower()} ", "kind": "variant"},
                {"product_id": "P0100", "customer_part_no": "4S8HFDV-VM-05;PM", "kind": "alias"},
                {"product_id": "P0200", "customer_part_no": "X"},          # kind 없음(옛 응답) = 제외
                {"product_id": None, "customer_part_no": "Y", "kind": "variant"},
                {"product_id": "P0300", "customer_part_no": "", "kind": "variant"}]
    assert load_variants(_fetch) == {("P0005", RE.upper())}
    assert calls == [("customer_part_mapping", "product_id,customer_part_no,kind",
                      "kind=eq.variant")]
    assert load_variants(lambda *a: None) == set()
