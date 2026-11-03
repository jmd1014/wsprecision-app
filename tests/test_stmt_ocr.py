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
    # r1-2(2026-11-03): today 고정 — O3 의 오늘−400 창 때문에 2027-11 이후 거짓 실패하지 않게(동작 무변화)
    _t = __import__("datetime").date(2026, 11, 3)
    assert find_date(words, today=_t) == "2026-09-30"
    assert find_date([{"t": "2006"}, {"t": "9"}, {"t": "월"}, {"t": "16"}, {"t": "일"}], today=_t).endswith("-09-16"),         "연도 오독은 올해로"


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


# ─────────────── 매입 OCR 보완 r1 (2026-11-03) — 샘플 5장 픽스처(줄 텍스트만, 정답은 구글시트 매입내역) ───────────────
import datetime as dt
import json

from utils.stmt_ocr import clean_item, normalize_tokens, vendor_unit_mode

_FIX = os.path.join(os.path.dirname(__file__), "fixtures", "stmt_ocr_20261102.json")
_TODAY = dt.date(2026, 11, 2)


def _page(no):
    """픽스처 한 장 → (줄 목록, 단어 목록, 라인 항목, 합계 검증)"""
    pg = next(p for p in json.load(open(_FIX, encoding="utf-8")) if p["page"] == no)
    lines = [_line(t) for t in pg["lines"]]
    words = [w for l in lines for w in l["words"]]
    items = parse_line_items(lines)
    return lines, words, items, find_totals(lines, items)


def _amts(items):
    return [round(i["amount"]) for i in items]


def test_r1_page1_sungbo_item_names_cleaned():
    lines, words, items, (s, cands, ok, _) = _page(1)
    assert [i["item"] for i in items] == ["BONNET", "8PDVN-02 (BONNET)"], "앞 날짜·끝 잡음 숫자 64 제거(O6)"
    assert items[0]["item_raw"] == "2026-10-28 BONNET 64", "원문은 item_raw 에 보존"
    assert s == 6120000 and ok
    assert find_date(words, today=_TODAY) == "2026-10-28"


def test_r1_page2_hyesung_unit_price_tokens_and_date():
    lines, words, items, (s, cands, ok, _) = _page(2)
    assert [(i["a"], i["price"], round(i["amount"])) for i in items] == [
        (289, 1390, 401710), (500, 105, 52500), (394, 1780, 701320), (810, 28, 22680)], "`1,390/KG` 꼴 단가(O1)"
    assert [i["unit"] for i in items] == ["KG", "EA", "KG", "EA"]
    assert items[0]["qty"] == 289, "혜성 `289 KG 289` — 뒤의 289 가 중량, 앞이 수량(O5)"
    assert items[2]["qty"] is None, "중량 왼쪽이 치수 단어(28X97)면 수량 비움"
    assert s == 1178210 and ok
    assert find_date(words, today=_TODAY) == "2026-10-19", "`202611 10g 19`(년→11 오독) — 11-10 은 미래라 제외(O3)"


def test_r1_page3_myungjin_vat_qty_unit_remark_and_dims_match():
    lines, words, items, (s, cands, ok, _) = _page(3)
    assert _amts(items) == [1315700, 191100, 112100, 1885000]
    assert (items[2]["a"], items[2]["price"], round(items[2]["amount"]), items[2]["how"]) == (19, 5900, 112100, "vat"), \
        "590(5,900 오독)×19 = 11,210(세액)을 금액으로 잡지 않고 세액 쌍으로 단가 복원(O2)"
    assert s == 3503900 and ok
    assert [i["unit"] for i in items] == ["KG"] * 4, "`Ko` 퍼지(O4)"
    assert [i["qty"] for i in items] == [100, 10, 9, 1.016] and items[3]["qty_fix"] == 1016, \
        "수량 = 중량 바로 왼쪽(O5), 1.016 은 1,016 제안값"
    assert items[0]["remark"].startswith("4S25ABV-FL-01-X1") and "4S25ABV" not in items[0]["item"], "비고 제안(O8)"
    assert items[0]["item"] == "STS304 환봉 110? +24", "515304→STS304, 끝 숫자(2) 제거(O6)"
    kb = build_known([
        {"vendor": "(주)명진메탈", "item": "STS304환봉 110￠*24ℓ", "unit_price": 5900},
        {"vendor": "(주)명진메탈", "item": "STS304환봉 125￠*16ℓ", "unit_price": 5900},
        {"vendor": "(주)명진메탈", "item": "STS316L환봉 125￠*16ℓ", "unit_price": 9100},
    ])["명진메탈"]
    assert match_item(items[0]["item"], kb, items[0]["price"])[:2] == ("STS304환봉 110￠*24ℓ", 100), \
        "`110? +24` 치수 구분자(O6) → 재질+치수 일치"
    assert find_date(words, today=_TODAY) == "2026-10-23"


def test_r1_page4_myungjin_units_by_vendor_mode_and_amounts():
    lines, words, items, (s, cands, ok, _) = _page(4)
    assert _amts(items) == [276000, 1237600, 746200, 9972800, 206500, 170800]
    mode = vendor_unit_mode([{"vendor": "(주)명진메탈", "unit": "KG"}, {"vendor": "(주)명진메탈", "unit": "kg"},
                             {"vendor": "(주)명진메탈", "unit": "EA"}, {"vendor": "성보정밀", "unit": "EA"}])
    assert mode == {"명진메탈": "KG", "성보정밀": "EA"}
    assert [i["unit"] or mode["명진메탈"] for i in items] == ["KG"] * 6, "단위 글자 없는 줄은 거래처 최빈 단위"
    assert [i["qty"] for i in items] == [10, 65, 40, 250, 17, 10]
    assert ok and find_date(words, today=_TODAY) == "2026-10-16"


def test_r1_page5_with_no_false_lines_and_no_future_date():
    lines, words, items, (s, cands, ok, _) = _page(5)
    truth = [125000, 267450, 112000]
    assert _amts(items) == [267450, 112000], "`150°` 도 기호(O1) — `0 so`(500) 줄은 못 읽음"
    assert all(a in truth for a in _amts(items)), "거짓 라인 0"
    assert ok is False, "3라인 중 2라인 — 합계 검증은 × 로 남아 검토를 부른다"
    assert items[0]["item"] == "HA50-80210 [KG]" and items[0]["unit"] is None, "품명 속 [KG] 는 단위로 보지 않음"
    assert find_date(words, today=_TODAY) != "2026-11-20", "금액 112000 속 2000 + 11,20 → 미래 날짜 아님"


def test_r1_helpers_normalize_clean_and_date_window():
    toks = normalize_tokens([{"t": "1,390/KG"}, {"t": "150°"}, {"t": "267450,"}, {"t": "700@×16"}, {"t": "Ko"}])
    assert [t["t"] for t in toks] == ["1,390", "KG", "150", "267450", "700@×16", "Ko"]
    assert normalize_tokens(toks) == toks, "두 번 적용해도 같음"
    assert clean_item("2026-10-28 BONNET 64") == "BONNET"
    assert clean_item("10/14 HA50-80210 [KG]") == "HA50-80210 [KG]"
    assert clean_item("6515304 환 봉 125 ?* 167 17") == "STS304 환봉 125 ?* 167"
    assert clean_item("STS3048HE 140¢ +184") == "STS304HE 140¢ +184"
    assert clean_item("515316 ㄴ 환 봉 140? ＊ 19 /") == "STS316 ㄴ 환봉 140? ＊ 19", "구분자 뒤 숫자는 치수라 남김"
    assert clean_item("64") == "64", "숫자뿐이면 그대로"
    assert (110.0, 24.0) in ocr_dims("STS304 환봉 110? +24") and (156.0, 23.0) in ocr_dims("156 ¢ #23")
    w = lambda s: [{"t": t} for t in s.split()]
    assert find_date(w("일자 2026-11-20"), today=_TODAY) is None, "오늘+7 초과 제외"
    assert find_date(w("일자 2026-11-09"), today=_TODAY) == "2026-11-09", "오늘+7 까지는 허용"
    assert find_date(w("2025-09-27 일자 2026-10-01"), today=_TODAY) == "2026-10-01"
    assert find_date(w("발행 2025-09-27"), today=_TODAY) is None, "오늘−400 미만 제외"
    assert find_date(w("2026-10-01 거래일 2026-10-20"), today=_TODAY) == "2026-10-20", "키워드에 가까운 후보"
    assert find_date(w("2006 12 월 28 일"), today=dt.date(2027, 1, 3)) == "2026-12-28", "연도 오독이 미래면 작년"


def test_r1_vat_not_taken_as_amount_regression():
    it = parse_line_items([_line("515304 환 봉 125? 4 9 19.00 590 Ko 112,100 11,210 /4S25L0F-W")])
    assert len(it) == 1 and round(it[0]["amount"]) == 112100 and it[0]["price"] == 5900


# ─────────────── r1-2 화면 기본값(T8) — 순수 함수 ocr_row_defaults ───────────────
from utils.stmt_ocr import MATCH_AUTO_MIN, ocr_row_defaults


def _it(**kw):
    base = {"item": "STS304 환봉 110? +24", "unit": "KG", "a": 223.0, "price": 5900.0, "amount": 1315700.0,
            "qty": 100.0, "qty_fix": None, "remark": "4S25ABV-FL-01-X156", "match": "STS304환봉 110￠*24ℓ",
            "match_score": 100}
    base.update(kw)
    return base


def test_r1_t8_save_item_threshold_79_80():
    assert MATCH_AUTO_MIN == 80
    assert ocr_row_defaults(_it(match_score=80))["save_item"] == "STS304환봉 110￠*24ℓ", "80 이상은 제안"
    d = ocr_row_defaults(_it(match="8PDVN-02 (BONNET)", match_score=79, item="BONNET"))
    assert d["save_item"] == "BONNET" and d["ocr_item"] == "BONNET" and d["score"] == 79, "80 미만은 OCR 품명(O7)"
    assert ocr_row_defaults(_it(match=None, match_score=0))["save_item"] == "STS304 환봉 110? +24"


def test_r1_t8_kg_qty_weight_unit_and_notes():
    d = ocr_row_defaults(_it())
    assert (d["unit"], d["qty"], d["weight"], d["vat"], d["remark"]) == ("KG", 100.0, 223.0, 131570.0, "4S25ABV-FL-01-X156")
    d = ocr_row_defaults(_it(qty=None))
    assert d["qty"] is None and d["weight"] == 223.0, "KG 행 수량 못 찾으면 빈칸(other_nums[0] 폐기)"
    d = ocr_row_defaults(_it(unit=None), "KG")
    assert d["unit"] == "KG" and d["qty"] == 100.0, "단위 못 읽으면 거래처 최빈 단위(O4)"
    d = ocr_row_defaults(_it(unit=None, qty=64.0, a=5400.0, price=800.0, amount=4320000.0), None)
    assert (d["unit"], d["qty"], d["weight"]) == ("EA", 5400.0, None), "단위·최빈 단위 다 없으면 EA, 수량 = a"
    d = ocr_row_defaults(_it(qty=1.016, qty_fix=1016, a=325.0))
    assert d["qty"] == 1.016 and d["note"] == "수량 1.016 은 1,016 오독일 수 있습니다(소수점)", "자동 치환 없이 안내"
    assert ocr_row_defaults(_it(unit="EA", qty=1.016, qty_fix=1016))["note"] is None, "EA 행은 수량 = a"
    assert ocr_row_defaults(_it(remark=None))["remark"] == ""
    assert ocr_row_defaults(_it(qty=1.016, qty_fix=1016, a=325.0, remark="8PSF-C-03"))["remark"] ==         "8PSF-C-03 · OCR 확인: 수량 1.016→1,016?"


def test_r1b_t8_correction_remarks():
    d = ocr_row_defaults(_it(unit="EA", a=30.0, price=7370.0, amount=221100.0, how="fix1",
                             fixed_from={"price": 7870.0}, remark=None))
    assert d["remark"] == "OCR 보정: 7,870→7,370" and d["price"] == 7370
    d = ocr_row_defaults(_it(unit=None, a=299.0, price=300.0, amount=89700.0, how="fix1", fixed_from={"a": 209.0},
                             remark=None), "EA")
    assert d["remark"] == "OCR 보정: 209→299" and d["qty"] == 299
    d = ocr_row_defaults(_it(unit="EA", a=1.0, price=7000.0, amount=7000.0, how="qty1", remark=None))
    assert d["remark"] == "OCR 보정: 수량 1(판독 안 됨)" and d["qty"] == 1


# ─────────────── 추록 1(2026-11-03) — 샘플 6장(두리·에스피열처리·중앙연마), 정답은 검토 세션이 원본 대조 ───────────────
from utils.stmt_ocr import find_vendor as _find_vendor

_FIX2 = os.path.join(os.path.dirname(__file__), "fixtures", "stmt_ocr_20261103.json")
_TODAY2 = dt.date(2026, 11, 3)
_TRUTH2 = {   # 쪽: [(품명, 단가)] — 장부(시트) 표기, 제안 대조용
    "두리T.M.S": [("INSERT TIP VBMT 160404-PS AH8015", 7370), ("INSERT TIP VBMT 160402-PS AH8015", 7370),
                 ("INSERT TIP GVR 185A PR930", 22750), ("INSERT TIP CCMT 09T308-C25 PC9030", 5170),
                 ("INSERT TIP CCMT 09T302-HMP PC9030", 5170), ("플러그 4P 20A 25V", 7000),
                 ("초경드릴(팡팡드릴) 8.5D*50*84*SH9 (DPPA01085)", 37650), ("코발트 드릴(나찌) 1.5D*20*65 HSS-CO", 1950)],
    "에스피열처리": [("진공(에이징처리) [SUS630]", 200000)],
    "중앙연마": [("PISTON/Φ45", 300), ("유성축/25.42*95", 350)],
}
_KB2 = build_known([{"vendor": v, "item": i, "unit_price": p} for v, xs in _TRUTH2.items() for i, p in xs])


def _page2(no, key="lines"):
    pg = next(p for p in json.load(open(_FIX2, encoding="utf-8")) if p["page"] == no)
    lines = [_line(t) for t in pg[key]]
    words = [w for l in [_line(t) for t in pg["lines"]] for w in l["words"]]
    items = parse_line_items(lines)
    return pg, words, items, find_totals(lines, items)


def _sug(vendor, it):
    return match_item(it["item"], _KB2[vendor], it["price"])


def test_r1b_t9_duri_fix1_dots_qty1_and_month_day_date():
    pg, words, items, (s, cands, ok, _) = _page2(1)
    assert [(i["a"], i["price"], round(i["amount"]), i["how"]) for i in items] == [
        (30, 7370, 221100, "mul"), (30, 7370, 221100, "fix1"), (20, 22750, 455000, "mul"),
        (30, 5170, 155100, "mul"), (30, 5170, 155100, "mul"), (1, 7000, 7000, "qty1")]
    assert items[1]["fixed_from"] == {"price": 7870}, "단가 7,870 → 7,370 한 자리 복원(O9), 원래 값 보존"
    assert items[4]["amount"] == 155100, "`155.100` 천단위 점 — 금액 자리 2차 해석(O1 보강)"
    assert s == 1214400 and ok, "인쇄 합계 `1.214.400`(점 여러 개) — 부가세 줄"
    assert find_date(words, today=_TODAY2) == "2026-10-28", "`20269 10% 28 일` 월·일 패턴(O3b)"
    sugs = [_sug("두리T.M.S", i) for i in items]
    assert [x[1] >= 80 for x in sugs] == [True] * 6
    assert sugs[1][0] == "INSERT TIP VBMT 160402-PS AH8015" and sugs[4][0] == "INSERT TIP CCMT 09T302-HMP PC9030"
    assert not items[1]["item"].startswith("2 "), "줄번호 2 는 품명에서 뗌(O6 보강)"


def test_r1b_t10_duri_two_lines_no_date():
    pg, words, items, (s, cands, ok, _) = _page2(2)
    assert [round(i["amount"]) for i in items] == [112950, 19500] and s == 132450 and ok
    assert find_date(words, today=_TODAY2) is None, "날짜 줄 자체가 판독 안 됨 → None(화면은 오늘 기본)"


def test_r1b_t11_sp_heat_colon_amount():
    pg, words, items, (s, cands, ok, _) = _page2(3)
    assert [(i["a"], i["price"], round(i["amount"]), i["unit"]) for i in items] == [(1.5, 200000, 300000, "CH")], \
        "`300,000:` 끝 콜론(O1 보강)"
    assert find_date(words, today=_TODAY2) == "2026-10-22"
    assert _sug("에스피열처리", items[0])[1] >= 80


def test_r1b_t12_vendor_name_fallback():
    pg, words, items, _ = _page2(4)
    biz = {"5981900019": {"name": "에스피열처리", "business_no": "598-19-00019"}}
    assert _find_vendor(words, biz) is None, "사업자번호 줄 오독"
    names = [{"name": "에스피열처리"}, {"name": "(주)명진메탈"}, {"name": "나우"}, {"name": "우성정밀"}]
    assert _find_vendor(words, biz, names=names)["name"] == "에스피열처리", "상호 폴백(O11)"
    assert _find_vendor(words, biz, names=names + [{"name": "주식회사 에스피열처리"}])["name"] == "에스피열처리", \
        "같은 상호 키는 하나로"
    assert _find_vendor(words, biz, names=names + [{"name": "BNK부산은행"}]) is None, "둘 이상 들어 있으면 None"
    assert len(items) == 1 and items[0]["amount"] == 300000


def test_r1b_t13_jungang_psm11_line_fix1():
    _, _, items6, (s6, _, ok6, _) = _page2(5)
    assert items6 == [] and not ok6, "psm 6 줄에는 품목 줄이 없음 — 거짓 라인 0"
    pg, words, items, (s, cands, ok, _) = _page2(5, "lines_psm11")
    assert [(i["a"], i["price"], round(i["amount"]), i["how"]) for i in items] == [(299, 300, 89700, "fix1")]
    assert items[0]["fixed_from"] == {"a": 209}
    assert ok and (ok, len(items)) > (ok6, len(items6)), "psm 점수(합계 검증, 라인 수) 로 psm 11 이 채택될 조건"
    assert _sug("중앙연마", items[0])[:2] == ("PISTON/Φ45", 100)


def test_r1b_t14_jungang_plain_line():
    pg, words, items, (s, cands, ok, _) = _page2(6)
    assert [(i["a"], i["price"], round(i["amount"])) for i in items] == [(336, 350, 117600)] and ok
    assert _sug("중앙연마", items[0])[:2] == ("유성축/25.42*95", 100)
    assert find_date(words, today=_TODAY2) == "2026-10-16"


def test_r1b_fallback_guards():
    one = lambda t: parse_line_items([_line(t)])
    assert one("합 계 7,000 7,000") == [] and one("공급가액 30 7,870 221,100") == [], "합계 줄에는 O9·O10 안 씀"
    assert one("BOLT 30 7,870 230,000") == [], "c/a·c/b 가 한 자리 차이가 아니면 복원 안 함"
    assert one("BOLT 30 7,870 221,100")[0]["how"] == "fix1"
    it = one("6 플러그 EA 7,000 7,000")[0]
    assert (it["a"], it["how"], it["item"]) == (1, "qty1", "플러그"), "줄번호 6 은 숫자 후보에서도 뺌"
    it = one("10 EA 500 5,000")
    assert it and it[0]["a"] == 10, "첫 숫자 다음이 단위면 줄번호가 아니라 수량"
    assert normalize_tokens([{"t": "300,000:"}, {"t": "1.214.400"}, {"t": "155.100"}, {"t": "1.016"}]) == [
        {"t": "300,000"}, {"t": "1,214,400"}, {"t": "155.100"}, {"t": "1.016"}], "점 하나는 1차에서 그대로"
    w = lambda s: [{"t": t} for t in s.split()]
    assert find_date(w("거래일 20269 10% 28 일"), today=_TODAY2) == "2026-10-28"
    assert find_date(w("12 월 28 일"), today=dt.date(2027, 1, 3)) == "2026-12-28", "연도 없는 월일 — 미래면 작년"
