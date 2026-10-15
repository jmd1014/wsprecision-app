# -*- coding: utf-8 -*-
"""매입내역 동기화 매칭 규칙 단위 테스트 (utils/purchase_sync.py)

2026-08-31 확정 규칙: 재질+치수+형상 완전 일치 · EA · 단가>0 만 자동
매칭. 재질 숫자(SCM440 의 440)를 지름으로 오인하지 않고, 육각/환봉을
구분한다 — 운영 반영 전 발견한 두 파서 사고의 회귀 방지.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.purchase_sync import (apply_item_map, build_key_mats, dedup_key,
                                 is_linked, item_key, match_material,
                                 merge_cutting_rows, norm_dims, norm_grade,
                                 parse_month_tab, piece_price_rows, vendor_key)

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


DIC_MATS = [
    {"material_id": "M196", "raw_name": "SCM420H Ø55*5", "material_type": "SCM420H",
     "spec": "φ55*5L", "archived_at": None},
    {"material_id": "M182", "raw_name": "SCM415 Ø32*18", "material_type": "SCM415",
     "spec": "φ32*18L", "archived_at": None},
    {"material_id": "M087", "raw_name": "S20C H38*26", "material_type": "S20C",
     "spec": "φ38*26L", "archived_at": None},
]


def _row(date, vendor, item, unit, qty, price, amt, vat=None, total=None, remark=None, weight=None):
    return {"trade_date": date, "vendor": vendor, "item": item, "unit": unit, "qty": qty,
            "weight": weight, "unit_price": price, "amount": amt, "vat": vat, "total": total,
            "remark": remark}


def test_merge_cutting_rows_hyesung_pair():
    """환봉(KG) + 절단비(EA, 부품 수) → 한 행: EA · 수량 = 부품 수 · 개당 = (환봉+절단비)÷수량 (2026-06-01 실데이터)."""
    rows = [
        _row("2026-06-01", "혜성철강(주)", "흑환봉 SCM420H 55Φx5", "KG", 150, 1650, 247500, 24750, 272250, None, 150),
        _row("2026-06-01", "혜성철강(주)", "절단비", "EA", 1000, 55, 55000, 5500, 60500),
        _row("2026-06-01", "혜성철강(주)", "흑환봉 S45C 340Φx14", "EA", 1, 90000, 90000, 9000, 99000),   # 절단비 없음
        _row("2026-06-02", "(주)명진메탈", "STS304환봉 45￠16ℓ", "EA", 100, 1500, 150000, 15000, 165000),
    ]
    out, n = merge_cutting_rows(rows)
    assert n == 1 and len(out) == 3
    m = out[0]
    assert (m["unit"], m["qty"], m["weight"]) == ("EA", 1000.0, 150)
    assert m["unit_price"] == 302 and m["amount"] == 302500 and m["vat"] == 30250 and m["total"] == 332750
    assert m["remark"] == "[+절단비 55,000원]" and m["item"] == "흑환봉 SCM420H 55Φx5"
    assert m["kg_price"] == 1650 and m["ea_price"] == 302
    assert m["_merged_from"]["item"] == "절단비"
    assert rows[0]["unit"] == "KG", "입력은 바꾸지 않는다"
    assert out[1]["item"] == "흑환봉 S45C 340Φx14" and out[1]["unit"] == "EA"
    # 합산 행은 EA·단가>0 이라 치수 매칭이 붙는다
    assert match_material(m["item"], m["unit"], m["unit_price"], build_key_mats(DIC_MATS)) == ("M196", "OK")


def test_merge_cutting_rows_guards():
    base = _row("2026-06-01", "혜성철강(주)", "흑환봉 SCM415H 32Φx18", "KG", 80, 1650, 132000, 13200, 145200)
    # 날짜가 다르면 합치지 않음
    out, n = merge_cutting_rows([base, _row("2026-06-02", "혜성철강(주)", "절단비", "EA", 400, 30, 12000)])
    assert n == 0 and len(out) == 2
    # 절단비 수량 0 이면 합치지 않음
    out, n = merge_cutting_rows([base, _row("2026-06-01", "혜성철강(주)", "절단비", "EA", 0, 30, 12000)])
    assert n == 0
    # 다른 업체의 절단비는 대상 아님
    out, n = merge_cutting_rows([base, _row("2026-06-01", "에스피열처리", "세척비 / 환봉절단한거", "EA", 1, 50000, 50000)])
    assert n == 0
    # 비고가 있으면 뒤에 덧붙임, 합계가 비어 있으면 공급가+세액
    out, n = merge_cutting_rows([{**base, "remark": "4DI0622A4-5M", "total": None},
                                 _row("2026-06-01", "혜성철강(주)", "절단비", "EA", 400, 30, 12000, 1200, None)])
    assert n == 1 and out[0]["remark"] == "4DI0622A4-5M [+절단비 12,000원]"
    assert out[0]["unit_price"] == 360 and out[0]["total"] == 158400


def test_merge_cutting_rows_idempotent_and_adjacency():
    """이미 합산된 환봉 행([+절단비 비고) 뒤에 절단비 행이 남아 있어도 다시 합치지 않는다(재실행 이중 계상 방지).
    사이에 다른 업체 행이 끼면 인접이 아니므로 합치지 않는다. 날짜가 없으면 합치지 않는다."""
    bar = _row("2026-06-01", "혜성철강(주)", "흑환봉 SCM420H 55Φx5", "KG", 150, 1650, 247500, 24750, 272250, None, 150)
    cut = _row("2026-06-01", "혜성철강(주)", "절단비", "EA", 1000, 55, 55000, 5500, 60500)
    once, n1 = merge_cutting_rows([bar, cut])
    again, n2 = merge_cutting_rows(once + [cut])
    assert n1 == 1 and n2 == 0 and again[0]["amount"] == 302500 and again[1] is cut
    other = _row("2026-06-01", "(주)명진메탈", "STS304환봉 45￠16ℓ", "EA", 100, 1500, 150000)
    out, n = merge_cutting_rows([bar, other, cut])
    assert n == 0 and len(out) == 3
    out, n = merge_cutting_rows([{**bar, "trade_date": None}, {**cut, "trade_date": None}])
    assert n == 0
    # 통봉(EA) 매입 + 절단비: 수량은 부품 수, 중량은 비어 있음, kg 단가 없음
    out, n = merge_cutting_rows([_row("2026-06-01", "혜성철강(주)", "흑환봉 S45C 340Φx14", "EA", 1, 90000, 90000, 9000, 99000), cut])
    assert n == 1 and out[0]["qty"] == 1000 and out[0]["unit_price"] == 145 and out[0].get("kg_price") is None
    # 절단비 행의 matched_pn·비고 승계 (환봉 행에 없을 때)
    out, n = merge_cutting_rows([{**bar, "matched_pn": None}, {**cut, "matched_pn": "4D917140-00", "remark": "4D917140-00"}])
    assert n == 1 and out[0]["matched_pn"] == "4D917140-00" and out[0]["remark"].startswith("4D917140-00 [+절단비")
    # 장부에 합산 저장된 행과 시트에서 합산한 행은 같은 중복 키
    db_row = {**once[0], "ledger_id": 99}
    db_row.pop("_merged_from")
    assert dedup_key(db_row) == dedup_key(once[0])


def test_grade_scm_and_carbon_variants():
    """디아이씨 소재: SCM415H↔SCM415, SCM420H, S20C 를 같은 재질로 본다. SCM440 은 종전과 같다."""
    assert norm_grade("흑환봉 SCM415H 32Φx18") == "SCM415" == norm_grade("SCM415 Ø32*18")
    assert norm_grade("흑환봉 SCM420H 55Φx5") == "SCM420" == norm_grade("SCM420H Ø55*5")
    assert norm_grade("마환봉 S20C 12Φx1000") == "S20C" and norm_grade("흑환봉 SCM440 22Φx28") == "SCM440"
    assert norm_grade("STS303 환봉 20Φ") == "303" and norm_grade("SHAFT-PTO IDLE/3037") is None
    # 종전 'in' 판정과 같아야 한다: 앞에 글자·숫자가 있어도 S45C
    assert norm_grade("SHAFT IDLER S45C") == "S45C" and norm_grade("흑환봉 SCMS45C 60Φx10.5") == "S45C"
    assert norm_grade("환봉 20Φx1000 S45C") == "S45C" and norm_grade("STS304 S20C") == "304"
    km = build_key_mats(DIC_MATS)
    assert match_material("흑환봉 SCM415H 32Φx18", "EA", 400, km) == ("M182", "OK")
    assert match_material("흑환봉 SCM415H 32Φx18", "KG", 1650, km) == (None, "KG")


def test_keys_normalize_vendor_and_item():
    assert vendor_key("(주)명진메탈") == vendor_key("주식회사 명진메탈") == "명진메탈"
    assert vendor_key("혜성철강(주)") == vendor_key("혜성철강") == "혜성철강"
    assert item_key("STS304육각 38￠*24ℓ") == item_key("STS304육각38Φ*24L") == "STS304육각38Φ*24L"
    assert item_key("흑환봉 SCM420H 55Φx5") == "흑환봉SCM420H55Φ*5"
    assert item_key("면취캇타 INSERT XDBP11T308-B EG9030") == "면취캇타INSERTXDBP11T308-BEG9030", "단어 속 X 는 보존"


def test_piece_price_rows_mijin_kg_with_count():
    """명진메탈 2026-09-16 실데이터: 수량 513개·중량 148kg·7,500원/kg·1,110,000 → 개당 2,164원, kg 단가 보존."""
    r = _row("2026-09-16", "(주)명진메탈", "STS304육각 38￠*24ℓ", "KG", 513, 7500, 1110000, 111000, 1221000, "40ABV-TW-23", 148)
    out, n = piece_price_rows([r])
    assert n == 1 and out[0]["unit"] == "EA" and out[0]["unit_price"] == 2164 and out[0]["ea_price"] == 2164
    assert out[0]["kg_price"] == 7500 and out[0]["qty"] == 513 and out[0]["weight"] == 148 and out[0]["amount"] == 1110000
    assert r["unit"] == "KG", "입력 불변"
    # 혜성 환봉(수량=중량 kg)·EA 행·금액 0·중량×단가≠금액(건수 병기 공정비) 은 대상 아님
    hy = _row("2026-06-01", "혜성철강(주)", "흑환봉 SCM420H 55Φx5", "KG", 150, 1650, 247500, weight=150)
    ea = _row("2026-06-01", "두리T.M.S", "센타드릴", "EA", 10, 4470, 44700)
    z = _row("2026-06-01", "(주)명진메탈", "STS304환봉 45￠16ℓ", "KG", 100, 5700, 0, weight=30)
    ht = _row("2026-05-21", "(주)대경열처리", "NUT HUB LOCK / 고주파 Φ68.5*12L", "KG", 22, 1050, 50000, weight=1)
    out, n = piece_price_rows([hy, ea, z, ht])
    assert n == 0 and [x["unit"] for x in out] == ["KG", "EA", "KG", "KG"]
    # 변환 뒤 EA·단가>0 이라 치수 매칭 가능
    km = build_key_mats([{"material_id": "M400", "raw_name": "S304 H38*24", "material_type": "SUS304", "spec": "φ38*24L", "archived_at": None}])
    conv = piece_price_rows([r])[0][0]
    assert match_material(conv["item"], conv["unit"], conv["unit_price"], km) == ("M400", "OK")


def test_apply_item_map_fills_only_unlinked():
    """연결 판정은 자재 또는 mapping_status — 비고 품번(matched_pn)만 있는 소재 행도 매핑되고 matched_pn 은 보존 (B1)."""
    imap = {(vendor_key("(주)명진메탈"), item_key("STS304육각 38￠*24ℓ")): {"map_id": 7, "line_type": "MATERIAL", "material_id": "M400"},
            (vendor_key("청호정밀"), item_key("A453043")): {"map_id": 8, "line_type": "PRODUCT", "product_pn": "6A453043"},
            (vendor_key("에스피열처리"), item_key("고용화 [SUS630] 다량")): {"map_id": 9, "line_type": "PROCESS", "process_type": "HEAT"}}
    rows = [{**_row("2026-09-16", "주식회사 명진메탈", "STS304육각38Φ*24L", "KG", 513, 7500, 1110000), "matched_pn": "40ABV-TW-23"},
            _row("2026-06-30", "청호정밀", "A453043", "EA", 100, 700, 70000),
            {**_row("2026-08-10", "에스피열처리", "고용화 [SUS630] 다량", "CH", None, 200000, 200000), "category": "SERVICE"},
            {**_row("2026-09-16", "(주)명진메탈", "STS304육각 38￠*24ℓ", "KG", 1, 1, 1), "matched_material_id": "M999"},
            {**_row("2026-06-30", "청호정밀", "A453043", "EA", 1, 1, 1), "matched_material_id": "M998"},
            {**_row("2026-09-16", "(주)명진메탈", "STS304육각 38￠*24ℓ", "KG", 1, 1, 1), "mapping_status": "MAP"},
            _row("2026-09-30", "두리T.M.S", "POWER SUPPLY ESF150-24", "EA", 1, 108000, 108000)]
    n = apply_item_map(rows, imap)
    assert n == 3
    assert rows[0]["matched_material_id"] == "M400" and rows[0]["mapping_status"] == "MAP" and rows[0]["map_id"] == 7
    assert rows[0]["matched_pn"] == "40ABV-TW-23" and rows[0]["category"] == "MATERIAL", "비고 품번 보존"
    assert rows[1]["matched_pn"] == "6A453043" and rows[1]["category"] == "PRODUCT"
    assert rows[2]["mapping_status"] == "MAP" and rows[2]["category"] == "SERVICE", "기존 category 는 덮지 않음"
    assert not rows[2].get("matched_material_id")
    assert "mapping_status" not in rows[3] and "mapping_status" not in rows[4], "자재가 있는 행엔 적용 안 함(PRODUCT 포함)"
    assert rows[5]["mapping_status"] == "MAP" and "map_id" not in rows[5], "이미 결정된 행"
    assert "mapping_status" not in rows[6]
    assert is_linked({"matched_pn": "X"}) is False and is_linked({"mapping_status": "MANUAL"}) is True


def test_dedup_key_normalizes_vendor_and_item():
    """시트 표기와 수기 입력(마스터명)이 같은 키 (B2); 같은 행은 같은 키, 금액 다르면 다른 키."""
    a = _row("2026-09-16", "(주)유성메탈", "STS R/B 304 40Φ*25L", "EA", 8000, 1700, 13600000)
    b = _row("2026-09-16", "주식회사유성메탈", "STS R/B 304 40 Φ * 25 L", "EA", 8000, 1700, 13600000.4)
    assert dedup_key(a) == dedup_key(b)
    assert dedup_key(a) != dedup_key({**a, "amount": 13600001})
    assert dedup_key({**a, "trade_date": "2026-09-16T00:00:00"}) == dedup_key(a)


def test_grade_and_dims_edge():
    assert norm_grade("STS630환봉 25￠400ℓ") == "630"
    assert norm_dims("S630 Ø25×20") == ("RD", 25.0, 20.0)
