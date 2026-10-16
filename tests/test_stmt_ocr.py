# -*- coding: utf-8 -*-
"""거래명세서 OCR 해석(utils/stmt_ocr.py) 순수 함수 테스트 — Tesseract 없이 OCR 단어 구조를 흉내 낸다.
실데이터(2026-09-16 명진·유성, 09-30 두리 스캔 3장)에서 관찰된 OCR 오독('Φ'→'0'/'®'/'?', '9,390'→'9.300')을 고정."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.stmt_ocr import (build_known, find_date, find_totals, find_vendor, match_item,
                            ocr_dims, parse_line_items)


def _line(text):
    """공백으로 쪼갠 단어들을 한 줄로 (x 는 순서, y 고정)"""
    words = [{"t": t, "x": i * 100, "y": 0, "w": 90, "h": 20, "c": 90.0} for i, t in enumerate(text.split())]
    return {"yc": 10, "h": 20, "words": words, "text": text}


def test_parse_line_items_mul_and_vat_recovery():
    lines = [
        _line("09/16 STS 8/8 304 400*25Ｌ EA 8,000.0 1,700 13,600,000 1,360,000"),      # 수량×단가=금액
        _line("09/16 STS R/B 304 100®*21L EA 1,500.0 9.300 14,085,000 1,408,500"),      # 단가 오독 → 세액으로 복원
        _line("4% 513 중량 148.0 7,500 1,110,000 세액 111,000"),                          # 명진: 중량×단가
        _line("상호 ( 주 ) 유 성 메탈 606-86-12439"),                                     # 숫자 2개뿐·산술 불성립
    ]
    items = parse_line_items(lines)
    assert [(i["a"], i["price"], i["amount"], i["how"]) for i in items] == [
        (8000.0, 1700.0, 13600000.0, "mul"), (1500.0, 9390.0, 14085000.0, "vat"), (148.0, 7500.0, 1110000.0, "mul")]
    assert items[0]["item"] == "STS 8/8 304 400*25Ｌ" and items[0]["unit"] == "EA", "날짜 토큰·단위는 품명에서 제외"
    assert items[2]["other_nums"] == [513.0], "명진 수량(개)은 보조 숫자로 남긴다"


def test_find_totals_by_keyword_or_vat():
    items = [{"amount": 13600000}, {"amount": 3426000}, {"amount": 7110000}, {"amount": 14085000}]
    ok_lines = [_line("2g 38,221,000 3,822,100 42,043, 100g")]                       # 합계 줄 키워드 없음 → 세액으로
    s, cands, ok, vat = find_totals(ok_lines, items)
    assert s == 38221000 and ok and vat
    kw_lines = [_line("명 세 합 계 273,440")]
    s2, cands2, ok2, _ = find_totals(kw_lines, [{"amount": 108000}, {"amount": 80000}, {"amount": 40740}, {"amount": 44700}])
    assert s2 == 273440 and 273440 in cands2 and ok2
    bad_lines = [_line("명 세 합 계 713,440")]                                        # 합계 오독 → 검증 실패(검토 필요)
    assert find_totals(bad_lines, [{"amount": 273440}])[2] is False


def test_find_vendor_by_business_number_and_date():
    words = [{"t": t} for t in "606—-37—-55556 «Sm 2026 년 09 월 30 일 60602-14529".split()]
    biz = {"6063755556": {"name": "두리T.M.S"}, "6060214529": {"name": "우성정밀"}}
    assert find_vendor(words, biz)["name"] == "두리T.M.S", "대시 오독·우성 번호 무시"
    assert find_date(words) == "2026-09-30"
    assert find_date([{"t": "2006"}, {"t": "9"}, {"t": "월"}, {"t": "16"}, {"t": "일"}]).endswith("-09-16"), "연도 오독은 올해로"


def test_ocr_dims_and_match_item_relations():
    assert (40.0, 25.0) in ocr_dims("STS 8/8 304 400*25Ｌ") and (38.0, 24.0) in ocr_dims("515304 육 각 38? x24 2 513")
    known = build_known([
        {"vendor": "(주)명진메탈", "item": "STS304육각 38￠24ℓ", "unit_price": 2030},
        {"vendor": "(주)명진메탈", "item": "STS304육각 38￠*24ℓ", "unit_price": 2164},
        {"vendor": "(주)유성메탈", "item": "STS R/B 304 40Φ*25L", "unit_price": 1700},
        {"vendor": "(주)유성메탈", "item": "STS R/B 304 45Φ*28L", "unit_price": 2370},
        {"vendor": "두리T.M.S", "item": "센타드릴 1.5*5.0*60도 DV301015", "unit_price": 4470},
    ])["명진메탈" and "유성메탈"]  # 키 확인용 — 아래에서 거래처별로 다시 꺼냄
    kb = build_known([
        {"vendor": "(주)명진메탈", "item": "STS304육각 38￠24ℓ", "unit_price": 2030},
        {"vendor": "(주)명진메탈", "item": "STS304육각 38￠*24ℓ", "unit_price": 2164},
        {"vendor": "(주)유성메탈", "item": "STS R/B 304 40Φ*25L", "unit_price": 1700},
        {"vendor": "(주)유성메탈", "item": "STS R/B 304 45Φ*28L", "unit_price": 2370},
        {"vendor": "두리T.M.S", "item": "센타드릴 1.5*5.0*60도 DV301015", "unit_price": 4470},
    ])
    assert match_item("STS 8/8 304 400*25Ｌ", kb["유성메탈"], 1700) == ("STS R/B 304 40Φ*25L", 100, "dims")
    assert match_item("STS R/B 304 450 *28L", kb["유성메탈"], 2370)[0] == "STS R/B 304 45Φ*28L"
    raw, sc, how = match_item("515304 육 각 38? x24 2 513", kb["명진메탈"], 7500)
    assert raw == "STS304육각 38￠*24ℓ" and how == "dims(variants)", "같은 치수 표기 변형은 최근 것"
    raw, sc, how = match_item("센 타 드릴 1.5*%5.0*60 도 DV301015", kb["두리T.M.S"], 4470)
    assert raw == "센타드릴 1.5*5.0*60도 DV301015" and sc >= 90
    assert match_item("아무거나", {}, None) == (None, 0, None)
