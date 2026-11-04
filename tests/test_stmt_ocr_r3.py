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
    # Codex r3 HIGH: 오독 글자가 단어 끝일 때만 — 실제 괄호 설명·'ㄴ자' 는 그대로
    assert clean_item("STS316(가공) 환봉") == "STS316(가공) 환봉"
    assert clean_item("STS316[소둔] 환봉") == "STS316[소둔] 환봉"
    assert clean_item("STS316 ㄴ자 브라켓") == "STS316 ㄴ자 브라켓"
    assert clean_item("STS316(") == "STS316L", "줄 끝 오독"
    # Codex r3 2차 HIGH: 닫는 괄호가 뒤에 있으면 공백이 있어도 실제 괄호 설명
    assert clean_item("STS316( 가공 ) 환봉") == "STS316( 가공 ) 환봉"
    assert clean_item("STS316[ 소둔 ] 환봉") == "STS316[ 소둔 ] 환봉"
    assert clean_item("STS316& 환봉 (가공)") == "STS316L 환봉 (가공)", "& 는 괄호 짝 검사 대상 아님"
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


# ─────────────── O14 psm 합집합(parse_document) — 목 OCR ───────────────
def _words(texts):
    """줄 텍스트 목록 → 단어(줄마다 y 를 달리해 group_lines 가 다시 묶게)"""
    return [{"t": t, "x": j * 100, "y": i * 40, "w": 90, "h": 20, "c": 90.0}
            for i, line in enumerate(texts) for j, t in enumerate(line.split())]


def _run(monkeypatch, by_psm, biz_map, vendors=None):
    from utils import stmt_ocr as S
    monkeypatch.setattr(S, "ocr_available", lambda: True)
    monkeypatch.setattr(S, "render_pages", lambda b, n: ["IMG"])
    monkeypatch.setattr(S, "best_rotation", lambda img: 0)
    monkeypatch.setattr(S, "_image_to_words", lambda img, psm: _words(by_psm.get(psm, [])))
    return S.parse_document(b"x", "scan.pdf", biz_map, {}, vendors=vendors)[0]


_HS = {"vendor_id": 1, "name": "혜성철강(주)", "business_no": "615-81-76465"}


def test_r3_o14_totals_from_other_psm_vendor_and_date(monkeypatch):
    import datetime as dt
    day = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    a = [f"품목{i} 10 1,000 10,000" for i in range(8)]                     # 8행, 합계줄 없음
    b = ["등록번호 615-81-76465", f"일자 {day}"] + a[:3] + ["합계 80,000"]   # 3행 + 합계줄(= A 의 라인 합)
    pg = _run(monkeypatch, {6: a, 11: b, 4: []}, {"6158176465": _HS})
    assert pg["psm"] == 6 and len(pg["items"]) == 8, "items 는 채택 psm(A) 그대로"
    assert 80000 in pg["printed_totals"] and pg["sum"] == 80000 and pg["total_ok"] is True, "합계줄은 B 에서"
    assert (pg["vendor"], pg["vendor_how"]) == (_HS, "biz"), "채택 psm 에 사업자번호 없음 → 다른 psm"
    assert pg["date"] == day
    assert pg["lines"][0] == a[0], "lines 는 채택 psm 것"


def test_r3_o14_chosen_psm_first_and_biz_before_name(monkeypatch):
    import datetime as dt
    d1, d2 = (dt.date.today() - dt.timedelta(days=d) for d in (1, 2))
    other = {"vendor_id": 2, "name": "위드열처리", "business_no": "000-00-00001"}
    # 단가가 금액의 10% 가 아니게(5×2,000) — 세액 모양 우연 일치로 합계 ○ 가 되지 않게
    a = ["위드열처리 거래명세서", f"일자 {d1.isoformat()}"] + [f"품목{i} 5 2,000 10,000" for i in range(4)]
    b = ["등록번호 615-81-76465", f"일자 {d2.isoformat()}", "품목 5 2,000 10,000"]
    pg = _run(monkeypatch, {6: a, 11: b}, {"6158176465": _HS, "0000000001": other}, vendors=[_HS, other])
    assert pg["psm"] == 6 and pg["date"] == d1.isoformat(), "날짜는 채택 psm 먼저"
    assert (pg["vendor"], pg["vendor_how"]) == (_HS, "biz"), "사업자번호(어느 psm 이든)가 상호 폴백보다 먼저"
    assert pg["total_ok"] is False and pg["printed_totals"] == []
    pg = _run(monkeypatch, {6: a, 11: b[1:]}, {"6158176465": _HS, "0000000001": other}, vendors=[_HS, other])
    assert (pg["vendor"]["name"], pg["vendor_how"]) == ("위드열처리", "name"), "번호가 어디에도 없으면 상호"


def test_r3_o14_other_psm_plain_numbers_do_not_make_total_ok(monkeypatch):
    """Codex r3 2차 HIGH: 다른 psm 의 일반 숫자(단가 10,000)가 'A 라인 합 10,000 + 세액 1,000 이 본문에 있음' 을
    맞춰 행이 많은 A 가 채택되던 것 — 다른 psm 은 합계 키워드 줄만 본다."""
    a = ["품목A 5 1,000 5,000", "품목B 5 1,000 5,000"]
    b = ["품목C 10 10,000 100,000", "합계 100,000"]
    pg = _run(monkeypatch, {6: a, 11: b}, {})
    assert pg["psm"] == 11 and pg["sum"] == 100000 and pg["total_ok"] is True, "합계가 맞는 B 채택(r2 와 같음)"


def test_r3_o13_exact_length_wins_over_l_variant():
    """Codex r3 3차 HIGH: 읽은 그대로의 치수가 사전에 있으면 길이 변형(L//10) 후보는 보지 않는다."""
    both = build_known([{"vendor": "V", "item": "STS304환봉 95￠*152ℓ", "unit_price": 100},
                        {"vendor": "V", "item": "STS304환봉 95￠*15ℓ", "unit_price": 200}])["V"]
    assert match_item("STS304 환봉 95¢ +152", both, 200) == ("STS304환봉 95￠*152ℓ", 100, "dims"), "단가가 축약 쪽과 같아도"
    short = build_known([{"vendor": "V", "item": "STS304환봉 95￠*15ℓ", "unit_price": 200}])["V"]
    assert match_item("STS304 환봉 95¢ +152", short, None) == ("STS304환봉 95￠*15ℓ", 100, "dims"), "축약만 있으면 변형 후보로(O13)"
    assert ocr_dims("95¢ +152", l_variants=False) == [(95, 152)]
