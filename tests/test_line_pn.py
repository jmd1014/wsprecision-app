# -*- coding: utf-8 -*-
"""utils.line_pn — 거래처 품번 표시 헬퍼 (PN 묶음 2026-11-02)."""
from utils.line_pn import line_pn

BASE = "H11SDF-2C-10-01"
RE = "H11SDF-2C-10-01-RE-P"


def test_same_pn_shown_once():
    assert line_pn({"customer_part_no": BASE, "canonical_pn": BASE}) == BASE
    assert line_pn({"customer_pn": BASE, "pn": BASE}) == BASE


def test_different_customer_first_by_default():
    assert line_pn({"customer_part_no": RE, "canonical_pn": BASE}) == f"{RE} ({BASE})"
    assert line_pn({"customer_pn": RE, "pn": BASE}) == f"{RE} ({BASE})"


def test_internal_first():
    assert line_pn({"customer_pn": RE, "pn": BASE},
                   internal_first=True) == f"{BASE} ({RE})"
    # 같으면 순서 인자와 무관하게 한 번만
    assert line_pn({"customer_pn": BASE, "pn": BASE}, internal_first=True) == BASE


def test_narrow_full_false():
    assert line_pn({"customer_pn": RE, "pn": BASE}, full=False) == RE
    assert line_pn({"customer_pn": RE, "pn": BASE}, full=False,
                   internal_first=True) == BASE
    assert line_pn({"customer_pn": BASE, "pn": BASE}, full=False) == BASE


def test_empty_values():
    assert line_pn({"customer_part_no": "", "canonical_pn": BASE}) == BASE
    assert line_pn({"customer_pn": None, "pn": BASE}, internal_first=True) == BASE
    assert line_pn({"customer_pn": RE, "pn": None}) == RE
    assert line_pn({}) == "-"
    assert line_pn(None) == "-"


def test_mixed_soi_si_keys_and_strip():
    # soi 키가 우선, 없으면 si 키
    assert line_pn({"customer_part_no": RE, "pn": BASE}) == f"{RE} ({BASE})"
    assert line_pn({"customer_pn": RE, "canonical_pn": BASE}) == f"{RE} ({BASE})"
    # 앞뒤 공백 때문에 같은 품번을 다르다고 보지 않음
    assert line_pn({"customer_pn": f" {BASE} ", "pn": BASE}) == BASE
