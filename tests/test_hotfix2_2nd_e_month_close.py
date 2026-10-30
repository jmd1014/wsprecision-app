# -*- coding: utf-8 -*-
"""핫픽스 2 후속 2차 묶음 E — 영업 보고 기간 조회가 절단이 아닌 **예외**로 실패해도 절단과 같은 차단 (2026-10-30).

- 확정 전표 기간 조회(_sr_ships) 예외 / 작성중 전표 조회만 예외 → 월 마감 버튼 비활성, 확인 상태를 주입해도
  sales_month_close 쓰기 0건, '마감할 수 없습니다' 캡션, '확정 전표가 없습니다'로 안내하지 않음.
- 절단이면 기간 출력물(마감 보고서 HTML·거래내역서 HTML/xlsx) 비활성(BCD r3 RT2 — 일일 결산만 보던 것 보강).
- 대조군: 완전 조회면 출력물 활성 + 마감 확정 payload 그대로(묶음 전 커밋 7b0bd80 에서도 통과).
"""
import importlib.util
import os
import sys
from datetime import date

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests.test_hotfix2_followup_bcd_r3 import _force_fail, _sales_mock  # noqa: E402

streamlit_available = importlib.util.find_spec("streamlit") is not None
app_only = pytest.mark.skipif(not streamlit_available, reason="streamlit 미설치 — AppTest 불가")

MONTH_OUTPUTS = ("마감 보고서 인쇄", "거래내역서 인쇄", "거래내역서 엑셀")


def _fail_drafts(m):
    """작성중 전표 조회(fetch, status=eq.DRAFT)만 예외 — 확정 전표 조회는 성공."""
    real = m.fetch

    def _f(table, select="*", filter_query="", limit=1000, cache=None):
        if table == "shipments" and "status=eq.DRAFT" in (filter_query or ""):
            raise RuntimeError("shipments 작성중 조회 실패 (시뮬레이션)")
        return real(table, select, filter_query, limit, cache)
    m.fetch = _f


def _dl(at):
    return {getattr(b, "label", ""): getattr(b, "disabled", None) for b in at.get("download_button")}


@app_only
@pytest.mark.parametrize("where", ["confirmed", "drafts"])
def test_month_close_blocked_when_period_query_raises(monkeypatch, where):
    from tests.test_hotfix2_followup_a import _open
    m = _sales_mock()
    if where == "confirmed":
        _force_fail(monkeypatch, "shipments", when=lambda f: "status=eq.CONFIRMED" in f)
    else:
        _fail_drafts(m)
    at = _open(monkeypatch, m, "sales")
    btn = [b for b in at.button if b.key == "sr_mc_close"]
    assert btn and btn[0].disabled, [(b.key, b.disabled) for b in btn]
    assert any("조회 실패" in str(e.value) for e in at.error), [str(e.value) for e in at.error]
    assert any("마감할 수 없습니다" in str(c.value) for c in at.caption)
    assert not any("확정 전표가 없습니다" in str(i.value) for i in at.info), [str(i.value) for i in at.info]
    # 기간 출력물은 조회 실패면 아예 없거나(빈 결과) 비활성(부분 결과)
    assert not any(_dl(at).get(k) is False for k in MONTH_OUTPUTS), _dl(at)
    at.session_state["cfm_sr_mc_close"] = True                   # 이전 실행의 확인 상태 주입
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert not any(str(b.key or "").startswith("sr_mc_close_cfm") for b in at.button)
    assert not [w for w in m.writes if w[1] == "sales_month_close"], m.writes


@app_only
def test_month_outputs_disabled_when_truncated(monkeypatch):
    from tests.test_hotfix2_followup_a import _force_truncated, _open
    m = _sales_mock()
    _force_truncated(monkeypatch, "shipments")
    at = _open(monkeypatch, m, "sales")
    dl = _dl(at)
    assert all(dl.get(k) is True for k in MONTH_OUTPUTS), dl


@app_only
def test_daily_and_reissue_query_failure_is_not_empty_notice(monkeypatch):
    """일일 결산·재발행: 조회 실패를 '확정 전표가 없습니다'로 안내하지 않는다(출력물은 빈 결과라 없음)."""
    from tests.test_hotfix2_followup_a import _open
    m = _sales_mock()
    _force_fail(monkeypatch, "shipments", when=lambda f: "status=eq.CONFIRMED" in f)
    at = _open(monkeypatch, m, "sales")
    infos = [str(i.value) for i in at.info]
    assert not any("확정 전표가 없습니다" in t for t in infos), infos
    assert "일일 결산 리포트 인쇄" not in _dl(at)
    assert sum("조회 실패" in str(e.value) for e in at.error) >= 3, [str(e.value) for e in at.error]


@app_only
def test_complete_query_contrast_outputs_enabled_and_close_payload(monkeypatch):
    """대조군 — 완전 조회: 출력물 활성, 마감 확정 → sales_month_close 1행(ym·closed_by·note)."""
    from tests.test_hotfix2_followup_a import _open
    m = _sales_mock()
    at = _open(monkeypatch, m, "sales")
    dl = _dl(at)
    assert dl.get("일일 결산 리포트 인쇄") is False and all(dl.get(k) is False for k in MONTH_OUTPUTS), dl
    at.button(key="sr_mc_close").click()
    at.run()
    at.button(key="sr_mc_close_cfm_ok").click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    ins = [w[2] for w in m.writes if w[0] == "insert" and w[1] == "sales_month_close"]
    assert len(ins) == 1, m.writes
    assert ins[0]["ym"] == date.today().strftime("%Y-%m") and ins[0]["note"] is None, ins
