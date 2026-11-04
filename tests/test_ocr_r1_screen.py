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


def _open_pur(monkeypatch, ledger, total_ok=True, pages=None):
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
    _allow(m, "purchase_ledger", "purchase_item_map", "materials", "purchase_scan_log")   # 기록 표(OCR r2)
    m.tables["purchase_ledger"] = list(ledger)
    m.tables.setdefault("vendors", []).append({"vendor_id": 9001, "name": VENDOR, "business_no": "606-81-89947",
                                               "in_use": True, "archived_at": None})
    at = _open(monkeypatch, m, "po", "pur")
    at.session_state["sc_pages"] = pages if pages is not None else _pages(total_ok)
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


@app_only
def test_r1b_screen_name_fallback_note_and_correction_remarks(monkeypatch):
    """추록 1: 상호로 찾은 거래처 안내 + fix1·qty1 행 비고에 보정 내역."""
    from tests.test_stmt_ocr import _line
    from utils import stmt_ocr as S
    fx = json.load(open(os.path.join(ROOT, "tests", "fixtures", "stmt_ocr_20261103.json"), encoding="utf-8"))
    lines = [_line(t) for t in next(p for p in fx if p["page"] == 1)["lines"]]
    items = S.parse_line_items(lines)
    s, cands, ok, vat = S.find_totals(lines, items)
    pg = {"page": 1, "rot": 0, "psm": 6, "vendor": {"name": VENDOR}, "vendor_how": "name", "date": "2026-10-28",
          "items": items, "sum": s, "printed_totals": cands, "total_ok": ok, "vat_seen": vat, "lines": [],
          "file": "scan.pdf", "unit_mode": "EA"}
    m, at = _open_pur(monkeypatch, [], pages=[pg])
    assert "사업자번호 미판독 — 상호로 추정" in _md(at)
    df = _editor(at)
    assert list(df["비고"]) == ["", "OCR 보정: 7,870→7,370", "", "", "", "OCR 보정: 수량 1(판독 안 됨)"]
    assert list(df["단가"])[1] == 7370 and list(df["수량"])[5] == 1


# ─────────────── r1-3(2026-11-03) — 스캔 저장 요청을 _mi_save_rows 정의 뒤에서 처리(기존 NameError) ───────────────
def _ledger_inserts(m):
    out = []
    for w in m.writes:
        if w[0] == "insert" and w[1] == "purchase_ledger":
            out += w[2] if isinstance(w[2], list) else [w[2]]
    return out


def _click_save(at):
    next(b for b in at.button if b.key == "sc_save_1_0").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]


@app_only
def test_r1_3_scan_save_success_inserts_once_and_removes_card(monkeypatch):
    import db
    m, at = _open_pur(monkeypatch, [])
    calls, real = [], db.insert

    def _count(table, records, *a, **kw):
        calls.append(table)
        return real(table, records, *a, **kw)
    monkeypatch.setattr(db, "insert", _count)
    _click_save(at)
    rows = _ledger_inserts(m)
    assert calls.count("purchase_ledger") == 1, "insert 호출 1회(4행)"
    assert calls.count("purchase_scan_log") == 1, "정정 기록 1회(OCR r2) — 쓰기 가드가 막아 삼켜지지 않음"
    assert len(rows) == 4 and {r["source"] for r in rows} == {"SCAN"} and rows[0]["trade_date"] == "2026-10-23"
    assert [round(r["amount"]) for r in rows] == [1315700, 191100, 112100, 1885000]
    assert "sc_pages" not in at.session_state and "sc_save_req" not in at.session_state, "남은 장 0 → 판독 결과 비움"
    assert not any(b.key == "sc_save_1_0" for b in at.button)
    at.run()
    assert len(_ledger_inserts(m)) == 4, "다시 실행해도 재저장 없음"


@app_only
def test_r1_3_scan_save_duplicate_fails_with_note_once(monkeypatch):
    led = [{"ledger_id": 1, "trade_date": "2026-10-23", "vendor": VENDOR, "item": "STS304환봉 110￠*24ℓ",
            "amount": 1315700}]
    m, at = _open_pur(monkeypatch, led)
    _click_save(at)
    assert _ledger_inserts(m) == [], "중복이면 저장 안 함(_mi_save_rows dedup 그대로)"
    md = _md(at)
    assert "이미 장부에 같은 행이 있습니다" in md and "sc_pages" in at.session_state, "실패 사유는 카드에 경고로"
    at.run()
    assert "이미 장부에 같은 행이 있습니다" not in _md(at), "한 번만"


@app_only
def test_r1_3_scan_save_missing_amount_fails(monkeypatch):
    pages = _pages()
    pages[0]["items"] = pages[0]["items"][:1]
    m, at = _open_pur(monkeypatch, [], pages=pages)
    at.session_state["sc_ed_1_0"] = {"edited_rows": {"0": {"공급가액": None, "단가": None}},
                                      "added_rows": [], "deleted_rows": []}
    at.run()
    _click_save(at)
    assert _ledger_inserts(m) == []
    assert "금액을 계산할 수 없는 행 1건" in _md(at)


@app_only
def test_r1_3_stale_request_from_previous_read_is_ignored(monkeypatch):
    m, at = _open_pur(monkeypatch, [])
    at.session_state["sc_save_req"] = {"nonce": 0, "pi": 0, "rows": [{"item": "X", "amount": 1}],
                                       "date_iso": "2026-10-23", "stmt_no": "", "dup_ok": False}
    at.run()
    assert _ledger_inserts(m) == [] and "sc_save_req" not in at.session_state


def test_r1_3_scan_card_does_not_call_save_helper_directly():
    """정적 검사: 스캔 카드(판독 결과 표 ~ '판독 결과 비우기') 안에서 _mi_save_rows( 를 직접 부르지 않는다."""
    src = open(os.path.join(ROOT, "streamlit_app.py"), encoding="utf-8").read()
    a = src.index('_sc_pages = st.session_state.get("sc_pages") or []')
    b = src.index('st.button("판독 결과 비우기"')
    assert "_mi_save_rows(" not in src[a:b]
    assert src.index("def _mi_save_rows(") < src.index('st.session_state.pop("sc_save_req"'), "처리부는 정의 뒤"
