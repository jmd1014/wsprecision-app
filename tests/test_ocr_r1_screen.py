"""매입 OCR 보완 r1-2(2026-11-03) — 매입 등록 스캔 판독 검토 표 화면(AppTest).

OCR 엔진은 없으므로 ocr_available 을 켜고, 판독 결과(sc_pages)는 픽스처 3쪽(명진 10/23)을 해석해 넣는다.
- O7·O4·O5: 검토 표 기본값(저장 품명·단위·수량·중량·비고), 수량 1.016 안내 한 줄
- P2-1: 장부 마지막 거래일이 오늘−7 보다 오래되면 동기화 안내 / P2-2: 머리글 숫자 / P2-3: 같은 거래처·날짜·합계 경고
"""
import importlib.util
import json
import os
import sys
from datetime import date, timedelta

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

streamlit_available = importlib.util.find_spec("streamlit") is not None
app_only = pytest.mark.skipif(not streamlit_available, reason="streamlit 미설치 — AppTest 불가")

VENDOR = "(주)명진메탈"


def _pages(total_ok=True):
    from tests.test_stmt_ocr import _line
    from utils import stmt_ocr as S
    fx = json.load(open(os.path.join(ROOT, "tests", "fixtures", "stmt_ocr_20261102.json"), encoding="utf-8"))
    lines = [_line(t) for t in next(p for p in fx if p["page"] == 3)["lines"]]
    items = S.parse_line_items(lines)
    s, cands, ok, vat = S.find_totals(lines, items)
    for it, (m, sc) in zip(items, [("STS304환봉 110￠*24ℓ", 100), ("STS316L환봉 125￠*16ℓ", 79),
                                    ("STS304환봉 125￠*16ℓ", 91), ("STS304환봉 40￠*27ℓ", 84)]):
        it.update(match=m, match_score=sc, match_how="fuzzy")
    if not total_ok:
        items[3]["unit"] = None         # 단위 못 읽은 줄 → 거래처 최빈 단위
    return [{"page": 3, "rot": 0, "psm": 6, "vendor": {"name": VENDOR}, "date": "2026-10-23", "items": items,
             "sum": s, "printed_totals": ([13870890, 12609900] if not total_ok else cands),
             "total_ok": ok and total_ok, "vat_seen": vat, "lines": [], "file": "scan.pdf",
             "unit_mode": "KG"}]


def _open_pur(monkeypatch, ledger, total_ok=True):
    import streamlit
    from utils import stmt_ocr as S
    from tests.test_hotfix2_followup_a import _mock, _open
    from tests.test_hotfix2_followup_bcd_r2 import _allow
    monkeypatch.setattr(S, "ocr_available", lambda: True)
    _real_up = streamlit.file_uploader

    def _up(label, *a, **kw):          # 판독 파일이 올라와 있는 상태(P2-1 안내는 파일이 있을 때만)
        if kw.get("key") == "sc_files":
            return [type("F", (), {"name": "scan.pdf", "getvalue": lambda self: b""})()]
        return _real_up(label, *a, **kw)
    monkeypatch.setattr(streamlit, "file_uploader", _up)
    m = _mock()
    _allow(m, "purchase_ledger", "purchase_item_map", "materials")
    m.tables["purchase_ledger"] = list(ledger)
    m.tables.setdefault("vendors", []).append({"vendor_id": 9001, "name": VENDOR, "business_no": "606-81-89947",
                                               "in_use": True, "archived_at": None})
    at = _open(monkeypatch, m, "po", "pur")
    at.session_state["sc_pages"] = _pages(total_ok)
    at.session_state["sc_nonce"] = 1
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return m, at


def _md(at):
    return "\n".join(str(x.value) for x in at.markdown)


@app_only
def test_r1_screen_defaults_and_notes(monkeypatch):
    old = (date.today() - timedelta(days=20)).isoformat()
    m, at = _open_pur(monkeypatch, [{"ledger_id": 1, "trade_date": old, "vendor": VENDOR, "item": "X", "amount": 1}])
    md = _md(at)
    assert f"장부 최근 동기화 {old}" in md, "P2-1"
    assert "합계 검증 ○ · 라인 합 3,503,900" in md, "P2-2 ○ 면 라인 합만"
    assert "4행 수량 1.016 은 1,016 오독일 수 있습니다(소수점)" in md, "O5 qty_fix 안내"
    assert "이 장부에 이미 있습니다" not in md, "같은 날짜 장부 없음 → P2-3 경고 없음"
    df = _editor(at)
    assert list(df["저장 품명"]) == ["STS304환봉 110￠*24ℓ", "STS316[ 환봉 125? +16", "STS304환봉 125￠*16ℓ",
                                    "STS304환봉 40￠*27ℓ"], "점수 79 는 OCR 품명(O7)"
    assert list(df["단위"]) == ["KG"] * 4
    assert list(df["수량"]) == [100, 10, 9, 1.016], "KG 행 수량 = 중량 왼쪽 숫자(O5) — 예전 other_nums[0](515304) 아님"
    assert list(df["중량(kg)"]) == [223, 21, 19, 325]
    assert list(df["비고"])[:2] == ["4S25ABV-FL-01-X1", "S2SRFF-P"], "비고 제안(O8)"
    assert [round(x) for x in df["공급가액"]] == [1315700, 191100, 112100, 1885000]


def _editor(at):
    return next(d.value for d in at.dataframe if "저장 품명" in list(d.value.columns))


@app_only
def test_r1_screen_total_mismatch_header_unit_mode_and_duplicate_warning(monkeypatch):
    led = [{"ledger_id": 1, "trade_date": "2026-10-23", "vendor": VENDOR, "item": "A", "amount": 1315700},
           {"ledger_id": 2, "trade_date": "2026-10-23", "vendor": "명진메탈", "item": "B", "amount": 2188200},
           {"ledger_id": 3, "trade_date": "2026-10-23", "vendor": "성보정밀", "item": "C", "amount": 999}]
    m, at = _open_pur(monkeypatch, led, total_ok=False)
    md = _md(at)
    assert "합계 검증 × (검토 필요) · 인쇄 합계 13,870,890 · 라인 합 3,503,900" in md, "P2-2"
    assert "같은 거래처·날짜·합계 3,503,900 이 장부에 이미 있습니다 — 중복이면 추가하지 마세요" in md, \
        "P2-3 — 거래처 표기('(주)' 유무)는 vendor_key 로 묶고 다른 거래처는 빼고 합산"
    assert "4행 수량 1.016" in md, "단위 None 이어도 거래처 최빈 단위 KG 로 KG 행 처리"
    assert list(_editor(at)["단위"]) == ["KG"] * 4


@app_only
def test_r1_screen_ledger_lookup_failures_are_silent(monkeypatch):
    """P2-1·P2-3 조회 실패는 판독·저장을 막지 않는다."""
    import db
    real = db.fetch_all

    def _boom(t, select="*", filter_query="", *a, **kw):
        if t == "purchase_ledger" and "trade_date=eq." in (filter_query or ""):
            raise RuntimeError("조회 실패 (시뮬레이션)")
        return real(t, select, filter_query, *a, **kw)
    monkeypatch.setattr(db, "fetch_all", _boom)
    m, at = _open_pur(monkeypatch, [])
    md = _md(at)
    assert "장부 최근 동기화" not in md and "이 장부에 이미 있습니다" not in md
    assert any(b.key == "sc_save_1_0" for b in at.button)
