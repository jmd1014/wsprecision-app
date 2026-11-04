"""매입 OCR r2-2(2026-11-04) — 스캔 저장 성공 뒤 정정 기록 purchase_scan_log 1행(AppTest, 목 DB).

T-L1 정상 저장 → 장부 insert 뒤 기록 1행 · T-L2 셀 2개 수정 + 행 1개 삭제 · T-L2b 마지막 행 삭제 + 행 추가(숨김 idx)
T-L3 기록 insert 예외 → 장부 저장·플래시 그대로, log_error 1회 · T-L4 장부 저장 실패 → 기록 0 · T-L5 거래처·날짜 정정
"""
import os
import sys
from datetime import date

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tests.test_ocr_r1_screen import VENDOR, _click_save, _ledger_inserts, _open_pur, app_only  # noqa: E402


def _open(monkeypatch, ledger=(), pages=None):
    """log_error 호출은 m.log_errors 에 모은다 — 화면이 삼킨 기록 실패가 있으면 단언으로 잡는다(r2-4)."""
    import db
    m, at = _open_pur(monkeypatch, list(ledger), pages=pages)
    m.log_errors = []
    monkeypatch.setattr(db, "log_error", lambda kind, detail, **kw: m.log_errors.append((kind, detail, kw)) or True)
    return m, at


def _swallowed(m):
    return [e for e in m.log_errors if "스캔 정정 기록 실패" in str(e[1])]


def _logs(m):
    out = []
    for w in m.writes:
        if w[0] == "insert" and w[1] == "purchase_scan_log":
            out += w[2] if isinstance(w[2], list) else [w[2]]
    return out


def _flash(at):
    return [str(s.value) for s in at.success] + [str(t.value) for t in at.toast]


def _edit(at, **state):
    at.session_state["sc_ed_1_0"] = {"edited_rows": {}, "added_rows": [], "deleted_rows": [], **state}
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]


@app_only
def test_t_l1_save_writes_one_log_row_after_ledger(monkeypatch):
    m, at = _open(monkeypatch)
    _click_save(at)
    led, logs = _ledger_inserts(m), _logs(m)
    assert len(led) == 4 and len(logs) == 1
    assert all("idx" not in r for r in led), "idx 는 장부 payload 에 안 들어감"
    order = [w[1] for w in m.writes if w[0] == "insert"]
    assert order.index("purchase_ledger") < order.index("purchase_scan_log"), "장부 저장 성공 뒤에만"
    lg = logs[0]
    assert (lg["vendor_ocr"], lg["vendor_saved"], lg["date_ocr"], lg["date_saved"]) == \
        (VENDOR, VENDOR, "2026-10-23", "2026-10-23")
    assert (lg["n_rows_ocr"], lg["n_rows_saved"], lg["n_cells_changed"], lg["n_rows_added"],
            lg["n_rows_removed"], lg["n_head_changed"]) == (4, 4, 0, 0, 0, 0)
    assert lg["rules_version"] == "r2" and lg["file_name"] == "scan.pdf" and (lg["page"], lg["psm"]) == (3, 6)
    assert [r["idx"] for r in lg["items_saved"]] == [0, 1, 2, 3] and [r["idx"] for r in lg["items_ocr"]] == [0, 1, 2, 3]
    assert lg["items_ocr"][1]["score"] == 79 and "how" in lg["items_ocr"][0], "기본값 + 제안 점수·how"
    assert round(lg["saved_sum"]) == 3503900 and lg["total_ok"] is True
    assert any("정정 기록(셀 0·행 +0/−0)" in f for f in _flash(at)), _flash(at)
    at.run()
    assert len(_logs(m)) == 1 and len(_ledger_inserts(m)) == 4, "rerun 뒤 재저장·재기록 없음"
    assert _swallowed(m) == []


@app_only
def test_t_l2_two_cells_changed_one_row_removed(monkeypatch):
    m, at = _open(monkeypatch)
    _edit(at, edited_rows={"0": {"단가": 6000}, "2": {"저장 품명": "STS304환봉 125￠*17ℓ"}}, deleted_rows=[1])
    _click_save(at)
    lg = _logs(m)[0]
    assert (lg["n_cells_changed"], lg["n_rows_removed"], lg["n_rows_added"]) == (2, 1, 0)
    assert [r["idx"] for r in lg["items_saved"]] == [0, 2, 3], "지운 행은 저장 목록에 없음"
    assert lg["diff"]["removed"] == [1]
    assert {(c["idx"], c["field"]) for c in lg["diff"]["changed"]} == {(0, "unit_price"), (2, "item")}
    assert len(_ledger_inserts(m)) == 3
    assert any("정정 기록(셀 2·행 +0/−1)" in f for f in _flash(at)), _flash(at)
    assert _swallowed(m) == []


@app_only
def test_t_l2b_delete_last_then_add_row_is_not_matched_to_deleted(monkeypatch):
    """편집기 index 는 마지막 행을 지우고 추가하면 지운 번호(3)를 다시 쓴다 — 숨김 idx 열로 짝지어 추가 행으로 본다."""
    m, at = _open(monkeypatch)
    _edit(at, deleted_rows=[3], added_rows=[{"저장 품명": "절단비", "단위": "EA", "수량": 1, "단가": 5000,
                                              "공급가액": 5000}])
    _click_save(at)
    lg = _logs(m)[0]
    assert lg["diff"]["removed"] == [3] and lg["diff"]["added"] == [3], lg["diff"]
    assert lg["n_cells_changed"] == 0 and lg["items_saved"][3]["idx"] is None


@app_only
@pytest.mark.parametrize("err, app_logs", [("network down", 1), ("purchase_scan_log insert 404: relation", 0)])
def test_t_l3_log_failure_keeps_ledger_save_and_flash(monkeypatch, err, app_logs):
    import db
    m, at = _open(monkeypatch)
    real, errs = db.insert, []

    def _ins(table, records, *a, **kw):
        if table == "purchase_scan_log":
            raise RuntimeError(err)
        return real(table, records, *a, **kw)
    monkeypatch.setattr(db, "insert", _ins)
    monkeypatch.setattr(db, "log_error", lambda kind, detail, **kw: errs.append((kind, detail, kw)) or True)
    _click_save(at)
    assert len(_ledger_inserts(m)) == 4 and _logs(m) == []
    fl = _flash(at)
    assert any("장부 추가 4행" in f for f in fl) and not any("정정 기록" in f for f in fl), fl
    mine = [e for e in errs if e[2].get("table_name") == "purchase_scan_log"]
    assert len(mine) == app_logs, "응답 오류(db.insert 가 이미 기록)는 화면이 다시 남기지 않음"
    if app_logs:
        assert mine[0][0] == "db_write" and "스캔 정정 기록 실패" in mine[0][1]
    assert "sc_pages" not in at.session_state
    at.run()
    assert len(_ledger_inserts(m)) == 4 and len([e for e in errs if e[2].get("table_name") == "purchase_scan_log"]) \
        == app_logs, "rerun 뒤 재저장·재기록 없음"


@app_only
def test_t_l4_ledger_failure_writes_no_log(monkeypatch):
    led = [{"ledger_id": 1, "trade_date": "2026-10-23", "vendor": VENDOR, "item": "STS304환봉 110￠*24ℓ",
            "amount": 1315700}]
    m, at = _open(monkeypatch, led)
    _click_save(at)
    assert _ledger_inserts(m) == [] and _logs(m) == []


@app_only
def test_t_l5_vendor_and_date_corrected(monkeypatch):
    m, at = _open(monkeypatch)
    m.tables["vendors"].append({"vendor_id": 9002, "name": "성보정밀", "business_no": None, "in_use": True,
                                "archived_at": None})
    at.run()
    at.selectbox(key="sc_v_1_0").set_value("성보정밀")
    at.date_input(key="sc_d_1_0").set_value(date(2026, 10, 24))
    at.run()
    _click_save(at)
    lg = _logs(m)[0]
    assert (lg["n_head_changed"], lg["n_cells_changed"]) == (2, 0)
    assert (lg["vendor_saved"], lg["date_saved"]) == ("성보정밀", "2026-10-24")
    assert {r["vendor"] for r in _ledger_inserts(m)} == {"성보정밀"}
    assert _swallowed(m) == []


# ─────────────── r2-4(data·qa 리뷰) ───────────────
@app_only
def test_r24_missing_page_skips_log_with_one_error(monkeypatch):
    """③ 저장 요청의 장을 못 찾으면(판독 결과가 바뀜) 장부는 저장하되 기록은 건너뛰고 log_error 1회."""
    m, at = _open(monkeypatch)
    at.session_state["sc_save_req"] = {
        "nonce": 1, "pi": 99, "date_iso": "2026-10-23", "stmt_no": "", "dup_ok": False, "vendor": VENDOR,
        "ocr_rows": [], "rows": [{"trade_date": "2026-10-23", "vendor": VENDOR, "item": "X 볼트", "unit": "EA",
                                  "qty": 1.0, "weight": None, "unit_price": 1000.0, "amount": 1000.0, "vat": 100.0,
                                  "total": 1100.0, "remark": None, "idx": 0}]}
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert len(_ledger_inserts(m)) == 1 and _logs(m) == []
    sw = _swallowed(m)
    assert len(sw) == 1 and "판독 장 99 없음" in sw[0][1]


@app_only
def test_r24_log_function_exception_is_swallowed(monkeypatch):
    """⑤-1 기록 함수 자체 예외 → 장부 저장·플래시 그대로, log_error 1회."""
    from utils import scan_log as L

    def _boom(*a, **kw):
        raise ValueError("scan_log_row 실패 (시뮬레이션)")
    monkeypatch.setattr(L, "scan_log_row", _boom)
    m, at = _open(monkeypatch)
    _click_save(at)
    assert len(_ledger_inserts(m)) == 4 and _logs(m) == [] and len(_swallowed(m)) == 1
    assert any("장부 추가 4행" in f for f in _flash(at))


@app_only
def test_r24_blank_item_is_removed_and_auto_vat_is_not_a_correction(monkeypatch):
    """⑤-2 품명을 비운 행 = 저장 안 됨 = removed, ⑤-3 세액을 비워 자동 계산(공급가액×0.1)된 값은 정정 아님."""
    m, at = _open(monkeypatch)
    _edit(at, edited_rows={"1": {"저장 품명": ""}, "0": {"세액": None}})
    _click_save(at)
    lg = _logs(m)[0]
    assert lg["diff"]["removed"] == [1] and lg["n_rows_saved"] == 3
    assert lg["n_cells_changed"] == 0, lg["diff"]["changed"]
    assert lg["items_saved"][0]["vat"] == 131570 and len(_ledger_inserts(m)) == 3
    assert _swallowed(m) == []


@app_only
def test_r24_second_page_save_logs_that_page(monkeypatch):
    """⑤-5 두 장 중 둘째 장 저장 → 기록은 둘째 장 머리, 첫 장 카드는 그대로."""
    from tests.test_ocr_r1_screen import _pages
    p0, p1 = _pages()[0], _pages()[0]
    p1.update(page=4, psm=11, rot=90)
    m, at = _open(monkeypatch, pages=[p0, p1])
    next(b for b in at.button if b.key == "sc_save_1_1").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    lg = _logs(m)[0]
    assert (lg["page"], lg["psm"], lg["rot"]) == (4, 11, 90) and len(_ledger_inserts(m)) == 4
    assert [p["_sid"] for p in at.session_state["sc_pages"]] == [0]
    assert any(b.key == "sc_save_1_0" for b in at.button) and _swallowed(m) == []


# ─────────────── r2-3(후보 21 a·d) ───────────────
@app_only
def test_c21_retry_after_failure_saves_once_with_dup_ok(monkeypatch):
    """저장 실패(중복) 뒤 그대로 재클릭 → 또 실패, 의도한 중복 체크 뒤 재클릭 → 1회만 저장·기록 1행."""
    led = [{"ledger_id": 1, "trade_date": "2026-10-23", "vendor": VENDOR, "item": "STS304환봉 110￠*24ℓ",
            "amount": 1315700}]
    import time
    from tests.test_ocr_r1_screen import _md
    texts = lambda: _md(at) + "\n" + "\n".join(str(w.value) for w in at.warning)
    m, at = _open(monkeypatch, led)
    _click_save(at)
    assert "이미 장부에 같은 행이 있습니다" in texts()
    # r2-4(qa M1): 시간에 기대지 않게 가드를 직접 — 방금 누른 상태면 막히고(장부 불변), 풀면 다시 저장 시도
    at.session_state["_guard_sc_save_0"] = time.time()
    _click_save(at)
    assert "방금 같은 처리가 실행됐습니다" in texts() and _ledger_inserts(m) == []
    at.session_state["_guard_sc_save_0"] = 0
    _click_save(at)
    assert "이미 장부에 같은 행이 있습니다" in texts(), "가드를 풀면 다시 저장 시도 → 중복으로 또 실패"
    assert _ledger_inserts(m) == [] and _logs(m) == []
    at.checkbox(key="sc_dup_1_0").check()
    at.session_state["_guard_sc_save_0"] = 0
    at.run()
    _click_save(at)
    assert len(_ledger_inserts(m)) == 4 and len(_logs(m)) == 1
    at.run()
    assert len(_ledger_inserts(m)) == 4 and len(_logs(m)) == 1, "rerun 뒤 재저장 없음"


@app_only
def test_c21_old_pages_without_sid_get_stable_keys(monkeypatch):
    """_sid 없는 옛 판독 결과(r1-3 이전 세션) → 지금 위치로 한 번 고정, 앞 장을 저장해 빼도 뒤 장 key 유지."""
    from tests.test_ocr_r1_screen import _pages
    p0, p1 = _pages()[0], _pages()[0]
    p1["page"] = 4
    m, at = _open(monkeypatch, pages=[p0, p1])
    assert [p["_sid"] for p in at.session_state["sc_pages"]] == [0, 1]
    assert {b.key for b in at.button} >= {"sc_save_1_0", "sc_save_1_1"}
    _click_save(at)
    assert [p["_sid"] for p in at.session_state["sc_pages"]] == [1], "남은 장은 번호 1 그대로"
    assert any(b.key == "sc_save_1_1" for b in at.button) and not any(b.key == "sc_save_1_0" for b in at.button)
    assert _logs(m)[0]["page"] == 3


@app_only
def test_c21_p21_lookup_failure_and_p23_truncation_are_silent(monkeypatch):
    """P2-1(장부 최근 거래일) 조회 실패, P2-3(같은 날짜 장부) 절단 → 안내·경고 없이 통과(저장 버튼 그대로)."""
    import db
    from tests.test_ocr_r1_screen import _md
    real_f, real_fa = db.fetch, db.fetch_all

    def _f(t, select="*", filter_query="", *a, **kw):
        if t == "purchase_ledger" and "trade_date=not.is.null" in (filter_query or ""):
            raise RuntimeError("조회 실패 (시뮬레이션)")
        return real_f(t, select, filter_query, *a, **kw)

    def _fa(t, select="*", filter_query="", *a, **kw):
        if t == "purchase_ledger" and "trade_date=eq." in (filter_query or ""):
            return [{"vendor": VENDOR, "amount": 3503900}], True         # 합계는 같지만 절단
        return real_fa(t, select, filter_query, *a, **kw)
    monkeypatch.setattr(db, "fetch", _f)
    monkeypatch.setattr(db, "fetch_all", _fa)
    m, at = _open(monkeypatch)
    md = _md(at)
    assert "장부 최근 동기화" not in md and "이 장부에 이미 있습니다" not in md
    assert any(b.key == "sc_save_1_0" for b in at.button)
