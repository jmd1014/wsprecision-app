# -*- coding: utf-8 -*-
"""매입내역 동기화 매칭 규칙 단위 테스트 (utils/purchase_sync.py)

2026-08-31 확정 규칙: 재질+치수+형상 완전 일치 · EA · 단가>0 만 자동
매칭. 재질 숫자(SCM440 의 440)를 지름으로 오인하지 않고, 육각/환봉을
구분한다 — 운영 반영 전 발견한 두 파서 사고의 회귀 방지.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.purchase_sync import (build_key_mats, dedup_key, match_material,
                                 norm_dims, norm_grade, parse_month_tab)

MATS = [
    {"material_id": "M113", "raw_name": "S304 Ø40*25",
     "material_type": "SUS304", "spec": "φ40*25L", "archived_at": None},
    {"material_id": "M129", "raw_name": "S316 Ø105*14",
     "material_type": "SUS316", "spec": "φ105*14L", "archived_at": None},
    {"material_id": "M199", "raw_name": "SCM440 Ø22*26",
     "material_type": "SCM440", "spec": "φ22*26L", "archived_at": None},
    {"material_id": "M200", "raw_name": "SCM440 Ø22*28",
     "material_type": "SCM440", "spec": "φ22*28L", "archived_at": None},
    {"material_id": "M101", "raw_name": "S304 H50*11.5",
     "material_type": "SUS304", "spec": "φ50*11.5L", "archived_at": None},
    {"material_id": "M039", "raw_name": "AL6061 20*25*79",
     "material_type": "AL6061", "spec": "φ20*25L", "archived_at": None},
]
KM = build_key_mats(MATS)


def test_basic_round_bar_match():
    mid, why = match_material("STS R/B 304 40Φ*25L", "EA", 1640, KM)
    assert (mid, why) == ("M113", "OK")


def test_316L_relaxed_to_316():
    # 장부 316/L 표기 ↔ 마스터 SUS316 (치수 유일 시 허용)
    mid, why = match_material("STS R/B 316/L 105Φ*14L", "EA", 10900, KM)
    assert (mid, why) == ("M129", "OK")


def test_scm440_grade_digits_not_diameter():
    # 440을 지름으로 읽으면 M199/M200 이 한 키로 뭉쳐 DUP 가 됐다
    mid, why = match_material("흑환봉 SCM440 22Φx26", "EA", 500, KM)
    assert (mid, why) == ("M199", "OK")
    mid2, _ = match_material("흑환봉 SCM440 ø22X28", "EA", 500, KM)
    assert mid2 == "M200"


def test_hex_vs_round_distinguished():
    # 육각(M101)과 같은 치수 환봉이 있어도 형상으로 구분
    mid, why = match_material("STS304육각 50￠*11.5ℓ", "EA", 900, KM)
    assert (mid, why) == ("M101", "OK")
    # 환봉 표기는 육각 자재에 붙지 않는다
    mid2, why2 = match_material("STS304환봉 50￠*11.5ℓ", "EA", 900, KM)
    assert mid2 is None and why2 == "NOMAT"


def test_square_bar_via_raw_name_key():
    # 마스터 spec 이 φ 표기로 잘못돼 있어도 raw_name 사각 키로 매칭
    mid, why = match_material("AL 사각 6061 20t*25*79", "EA", 880, KM)
    assert (mid, why) == ("M039", "OK")


def test_kg_and_zero_price_held():
    assert match_material("STS R/B 304 40Φ*25L", "KG", 5700, KM) \
        == (None, "KG")
    assert match_material("STS R/B 304 40Φ*25L", "EA", 0, KM) \
        == (None, "ZERO")


def test_non_material_is_etc():
    assert match_material("절단비", "EA", 50, KM) == (None, "ETC")


def test_parse_month_tab_and_dedup():
    rows = parse_month_tab("2026년_08월", [
        ["월/일", "업체명", "품명 및 규격", "단위", "수량", "중량",
         "단가", "공급가액", "세액", "합계", "비고"],
        ["8월 3일", "(주)명진메탈", "STS304환봉 45￠16ℓ", "EA",
         2289, None, 1500, 3433500, 343350, 3776850, "8HFDV-VM-05"],
        [0, 0, None, None, None, None, None, None, None, None, None],
    ])
    assert len(rows) == 1
    r = rows[0]
    assert r["trade_date"] == "2026-08-03"
    assert r["unit_price"] == 1500
    assert r["remark"] == "8HFDV-VM-05"
    # 같은 행은 같은 키 (공백 차이 무시)
    assert dedup_key(r) == dedup_key({**r, "item": "STS304환봉 45￠16ℓ "})


def test_date_carry_forward():
    # 시트 관행: 같은 날 연속 행은 날짜를 첫 행에만 기재
    rows = parse_month_tab("2026년_06월", [
        ["월/일", "업체명", "품명", "단위", "수량", "중량", "단가",
         "공급가액", "세액", "합계", "비고"],
        ["6월 30일", "청호정밀", "A453043", "EA", 100, None, 700,
         70000, 7000, 77000, None],
        [None, "청호정밀", "A433004", "EA", 749, None, 500,
         374500, 37450, 411950, None],
    ])
    assert [r["trade_date"] for r in rows] \
        == ["2026-06-30", "2026-06-30"]


def test_grade_and_dims_edge():
    assert norm_grade("STS630환봉 25￠400ℓ") == "630"
    assert norm_dims("S630 Ø25×20") == ("RD", 25.0, 20.0)
