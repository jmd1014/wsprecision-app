# -*- coding: utf-8 -*-
"""매입 OCR r3(2026-11-04) — 판독 규칙 O12(등급 복원 확장)·O13(치수 변형 후보) 테스트.
픽스처 tests/fixtures/stmt_ocr_20261104.json: 11/04 스캔 4장(명진 3장 — 직원 체크표시 ✓ 있음, 위드 1장)의 줄 텍스트만.
사전은 명진 장부 품명 최소본(기대표의 품명만, 단가는 장부 최근 개당 단가)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.stmt_ocr import (MATCH_AUTO_MIN, OCR_RULES_VERSION, build_known, clean_item, match_item, ocr_dims,
                            parse_line_items)

_FIX = os.path.join(os.path.dirname(__file__), "fixtures", "stmt_ocr_20261104.json")
_MJ = [("STS304육각 46￠12ℓ", 1912), ("STS316L환봉 100￠*16ℓ", 12350), ("STS304환봉 100￠*15ℓ", 7505),
       ("STS304환봉 135￠*18ℓ", 16140), ("STS630환봉 25￠*407ℓ", 15981), ("STS304환봉 140￠*18ℓ", 17080),
       ("STS316L환봉 156￠18ℓ", 33120), ("STS316L환봉 95￠*14ℓ", 10010), ("STS316L환봉 95￠*19ℓ", 12740),
       ("STS304육각 30￠*17ℓ", 1006)]
_KB = build_known([{"vendor": "(주)명진메탈", "item": i, "unit_price": p} for i, p in _MJ])["명진메탈"]


def _line(text):
    words = [{"t": t, "x": i * 100, "y": 0, "w": 90, "h": 20, "c": 90.0} for i, t in enumerate(text.split())]
    return {"yc": 10, "h": 20, "words": words, "text": text}


def _items(no):
    pg = next(p for p in json.load(open(_FIX, encoding="utf-8")) if p["page"] == no)
    return parse_line_items([_line(t) for t in pg["lines"]])


# 장 → 행별 (기대 제안, 기대 방식) — None 이면 점수 < 80(제안 없음, 담당자 정정)
_EXPECT = {
    1: [("STS304육각 46￠12ℓ", "fuzzy"),          # 515904 육각 4644121 (3→9)
        (None, None),                              # 환봉
        (None, None),                              # STS316[ 환봉 100? £ a — 길이 미판독
        ("STS316L환봉 100￠*16ℓ", "dims"),         # 818316( 환봉 100? +16
        ("STS304환봉 100￠*15ℓ", "dims"),          # STS304H 100¢ +152 (ℓ→2)
        (None, None),                              # STS304
        ("STS304환봉 135￠*18ℓ", "dims"),          # STS304 2 135 ¢ +18
        ("STS304환봉 135￠*18ℓ", "dims")],         # STS304 135? +182 (ℓ→2)
    2: [("STS630환봉 25￠*407ℓ", "dims"),          # STS630 환봉 25 ¢ «407 (＊→«)
        ("STS304환봉 140￠*18ℓ", "dims"),          # +184 (ℓ→4)
        ("STS304환봉 140￠*18ℓ", "dims"),          # STS304t = 140 ¢ «18 £
        ("STS304환봉 140￠*18ℓ", "dims"),          # STS304 환봉 140? +18
        (None, None),                              # sTS3teLE — 무리하게 고치지 않음
        ("STS316L환봉 156￠18ℓ", "dims"),          # 515916 ㄴ 환봉 -156? +184
        ("STS316L환봉 95￠*14ℓ", "dims"),          # STS316L& = 95¢ +144
        ("STS316L환봉 95￠*19ℓ", "dims")],         # STS316( 환봉 95¢ +192
    3: [("STS304육각 30￠*17ℓ", "dims"),           # Vv STS3045 24 30¢+17¢ (체크표시)
        (None, None)],                             # Vv |5[5304 육각 30? * 1787 1,040 — 길이 1787
}


def test_r3_rules_version():
    assert OCR_RULES_VERSION == "r3"


def test_r3_1104_myungjin_suggestions_13_of_18():
    hits = 0
    for no, exp in _EXPECT.items():
        items = _items(no)
        assert len(items) == len(exp), f"{no}장 라인 수"
        for it, (want, how) in zip(items, exp):
            raw, sc, mhow = match_item(it["item"], _KB, it["price"])
            if want is None:
                assert sc < MATCH_AUTO_MIN, f"{no}장 {it['item_raw']!r} → {raw} {sc}"
                continue
            hits += 1
            assert (raw, mhow) == (want, how) and sc >= MATCH_AUTO_MIN, f"{no}장 {it['item_raw']!r} → {raw} {sc} {mhow}"
    assert hits == 13


def test_r3_1104_item_names_after_o12():
    assert [i["item"] for i in _items(1)][:5] == [
        "STS304 육각 4644121", "환봉", "STS316L 환봉 100? £ a", "STS316L 환봉 100? +16", "STS304H 100¢ +152"]
    assert [i["item"] for i in _items(2)][4:6] == ["sTS3teLE 156 ¢ 23", "STS316L 환봉 -156? +184"]
    assert [i["item"] for i in _items(3)] == ["STS3045 24 30¢+17¢", "STS304 육각 30? * 1787 1,040"], "체크표시 Vv 떼기"


def test_r3_1104_amounts_unchanged():
    assert [round(i["amount"]) for i in _items(3)] == [1450400, 1036000]
    assert [round(i["amount"]) for i in _items(4)] == [234000]


def test_r3_clean_item_grade_variants():
    assert clean_item("515904 육각") == "STS304 육각", "3→9 오독, 치환 뒤 STS9xx → STS3xx"
    assert clean_item("818316( 환봉") == "STS316L 환봉"
    assert clean_item("815304 환봉") == "STS304 환봉"
    assert clean_item("Vv |5[5304 육각") == "STS304 육각", "체크표시 잡토큰 단어 + 첫 글자 `|`"
    r = clean_item("/| 515310( 환봉")
    assert r.startswith("STS310") and "310L" not in r, "L 변형은 316 만"
    assert clean_item("-| STS316[ 환봉") == "STS316L 환봉"
    assert clean_item("515916 ㄴ 환봉") == "STS316L 환봉"
    assert clean_item("STS316& 환봉") == "STS316L 환봉"
    assert clean_item("STS304( 환봉") == "STS304( 환봉", "304 는 L 변형이 없음"
    # 기존 규칙 유지
    assert clean_item("STS3048 환봉") == "STS304 환봉"
    assert clean_item("6515304 환봉") == "STS304 환봉"
    assert clean_item("STS304환봉") == "STS304환봉", "체크 없는 정상 표기 무변화"
    assert clean_item("sTS3teLE 156 ¢ 23") == "sTS3teLE 156 ¢ 23", "글자 섞인 변형은 고치지 않음"
    assert clean_item("VALVE 25A") == "VALVE 25A", "잡토큰은 그 글자들만으로 된 1~3자 단어"


def test_r3_ocr_dims_l_variants_and_guillemet():
    d = ocr_dims("STS304H 100¢ +152")
    assert {(100, 152), (100, 15), (10, 152), (10, 15)} <= set(d), "ℓ→2 후보 + 기존 d/10 후보"
    assert ocr_dims("STS630 환봉 25 ¢ «407") == [(25, 407)], "끝자리 7 → 길이 변형 없음"
    assert ocr_dims("STS304 환봉 140¢ +18") == [(140, 18), (14, 18)], "2자리 길이 → 길이 변형 없음(d/10 은 기존 규칙)"
    assert (140, 18) in ocr_dims("STS304 환봉 140? +184")
    assert (140, 18) in ocr_dims("STS304t = 140 ¢ «18 £"), "`«` 구분자"
    assert (95, 14) in ocr_dims("STS316L& = 95¢ +144")
    assert ocr_dims("95¢ +153") == [(95, 153)], "끝자리 3 은 변형 없음"
