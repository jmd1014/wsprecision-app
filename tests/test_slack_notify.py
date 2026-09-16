# -*- coding: utf-8 -*-
"""슬랙 알림 — 미설정 시 스킵, 포맷, 전송 경로 검증."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils import slack_notify as sn  # noqa: E402


def test_skip_when_not_configured(monkeypatch):
    monkeypatch.setattr(sn, "_secret_url", lambda: None)
    monkeypatch.setattr(sn, "_db_url", lambda: None)
    sn._cache.update({"url": None, "loaded": False})
    assert sn.webhook_url(force=True) is None
    assert sn.notify("x") is False


def test_rejects_non_slack_url(monkeypatch):
    monkeypatch.setattr(sn, "_secret_url", lambda: "https://evil.example/x")
    monkeypatch.setattr(sn, "_db_url", lambda: None)
    assert sn.webhook_url(force=True) is None


def test_notify_posts_when_configured(monkeypatch):
    sent = {}
    monkeypatch.setattr(sn, "_secret_url",
                        lambda: "https://hooks.slack.com/services/T/B/x")
    monkeypatch.setattr(sn, "_post", lambda u, t: sent.update(u=u, t=t) or True)
    sn.webhook_url(force=True)
    assert sn.notify("[테스트] 연결", sync=True) is True
    assert sent["t"] == "[테스트] 연결"
    sn._cache.update({"url": None, "loaded": False})


def test_formats():
    # "[태그] 내용 — 사람 · 상세" (2026-09-16 사용자 확정)
    assert sn.fmt_po("26-0915", "명진메탈", 3, 1240, "김민수") ==         "[발주 작성] 26-0915 명진메탈 · 3품목 · 1,240개 — 김민수 · 발송 요청"
    assert sn.fmt_po("26-0915", "명진메탈", 3, 1240, "염정원", sent=True) ==         "[발주 발송] 26-0915 명진메탈 · 3품목 · 1,240개 — 염정원"
    assert sn.fmt_receipt(["W1006", "W1007", "W1008"],
                          ["S304 Ø45*16", "S316 Ø125*22"], "명진메탈", "염정원") ==         "[입고] W1006~W1008 · S304 Ø45*16 외 1 — 염정원 · 명진메탈"
    assert sn.fmt_receipt([None], ["S45C Ø25"], "직접 입고", "염정원") ==         "[입고] 식별 번호 없음 · S45C Ø25 — 염정원 · 직접 입고"
    assert sn.fmt_input("HDVN-03", 500, "W1006", "김준오") ==         "[투입] HDVN-03 500 EA · 소재 W1006 — 김준오"
    assert sn.fmt_wo_event("RECEIVE", "HDVN-03", 480, "김준오", defect=20) ==         "[완료] HDVN-03 480 EA (불량 20) — 김준오"
    assert sn.fmt_wo_event("OUT_SEND", "MRG6-07", 480, "황민혁",
                           vendor="성보정밀", step="열처리") ==         "[외주 출고] MRG6-07 480 EA · 열처리 → 성보정밀 — 황민혁"
    assert sn.fmt_wo_event("OUT_RETURN", "MRG6-07", 480, "황민혁",
                           vendor="성보정밀") ==         "[외주 입고] MRG6-07 480 EA ← 성보정밀 — 황민혁"
    assert sn.fmt_wo_event("STEP_START", "X", 1, "a") is None
    assert sn.fmt_ship("SH-20260915-01", ["미진정밀", "미진정밀"], 4, 3200, "염정원") ==         "[출고] SH-20260915-01 · 미진정밀 · 4품목 3,200개 — 염정원"


def test_format_inspect():
    d = {"lot": "20260828-002-A", "pass": 7000, "tokusai": 56, "rework": 10,
         "scrap": 0, "return": 0, "output": 7056}
    assert sn.fmt_wo_event("INSPECT", "20AHYBV-03-X1413", 7066, "홍지안",
                           detail=d) ==         "[검사] 20AHYBV-03-X1413 완성 7,056 · 재작업 10 · 특채 56 EA · LOT 20260828-002-A — 홍지안"
    assert sn.fmt_wo_event("INSPECT", "X", 10, "홍지안", detail={"pass": 10}) ==         "[검사] X 완성 10 EA — 홍지안"


def test_format_cancels():
    assert sn.fmt_wo_event("STEP_CANCEL", "MRG6-07", 480, "김준오", step="CNC",
                           detail={"cancelled": "STEP_START"}) ==         "[공정 취소] MRG6-07 480 EA · CNC — 김준오 · 시작 취소"
    assert sn.fmt_cancel("투입 취소", "T16ABV", 1500, "김준오",
                         extra="소재 W1108 복원") ==         "[투입 취소] T16ABV 1,500 EA — 김준오 · 소재 W1108 복원"
