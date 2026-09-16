# -*- coding: utf-8 -*-
"""앱 업무 분기점 → 슬랙 알림 (Incoming Webhook, docs/slack-notify-plan.md).

원칙
- 전송 실패가 업무 처리를 막으면 안 된다: 백그라운드 스레드 + 짧은
  타임아웃 + 실패는 조용히 무시. 호출 측은 DB 반영이 끝난 뒤,
  st.rerun() 직전에 호출한다 (fire-and-forget).
- 웹훅 URL 은 st.secrets["slack"]["webhook_url"] → 없으면 DB
  app_settings(key=slack_webhook_url) 순으로 찾고, 둘 다 없으면 스킵
  (로컬·테스트 환경에서 에러 금지).
- 메시지는 봇 명의로 게시되므로 처리자 실명(로그인 사용자)을 본문에
  적는다 — 원장 created_by 와 같은 값.
"""
import json
import threading
import urllib.request

_TIMEOUT = 3.0
_cache = {"url": None, "loaded": False}


def _secret_url():
    try:
        import streamlit as st
        return (st.secrets.get("slack", {}) or {}).get("webhook_url") or None
    except Exception:
        return None


def _db_url():
    try:
        import db as _db
        row = _db.fetch_one("app_settings", "key=eq.slack_webhook_url", "value")
        return (row or {}).get("value") or None
    except Exception:
        return None


def webhook_url(force=False):
    """설정된 웹훅 URL (없으면 None). 세션 프로세스 내 1회 조회 후 캐시."""
    if _cache["loaded"] and not force:
        return _cache["url"]
    url = _secret_url() or _db_url()
    _cache["url"] = url if (url and str(url).startswith("https://hooks.slack.com/")) else None
    _cache["loaded"] = True
    return _cache["url"]


def _post(url, text):
    try:
        body = json.dumps({"text": text}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"},
            method="POST")
        urllib.request.urlopen(req, timeout=_TIMEOUT).read()
        return True
    except Exception:
        return False


def notify(text, sync=False):
    """슬랙에 한 줄 알림. 설정 없으면 False 반환하고 아무것도 안 한다.

    sync=True 는 연결 테스트용 — 결과(True/False)를 기다려 돌려준다.
    """
    url = webhook_url()
    if not url or not text:
        return False
    if sync:
        return _post(url, text)
    threading.Thread(target=_post, args=(url, text), daemon=True).start()
    return True


# ─── 메시지 포맷 — "[태그] 내용 — 사람 · 상세" (2026-09-16 사용자: 무슨 일인지
# 먼저, 누가 했는지는 뒤에. 입고는 "— 이름 · 거래처") ───

def _n(v):
    try:
        return f"{float(v):,.0f}"
    except (TypeError, ValueError):
        return str(v or "-")


def fmt_po(po_number, vendor, n_items, total_qty, who, sent=False):
    tag = "발주 발송" if sent else "발주 작성"
    tail = "" if sent else " · 발송 요청"
    return (f"[{tag}] {po_number} {vendor} · {n_items}품목 · "
            f"{_n(total_qty)}개 — {who}{tail}")


def fmt_receipt(lots, materials, vendor, who, qty=None):
    """lots: [W번호…], materials: [자재명…] — 처리 1회당 1건."""
    lots = [l for l in lots if l]
    if len(lots) >= 2:
        lot_s = f"{lots[0]}~{lots[-1]}"
    elif lots:
        lot_s = lots[0]
    else:
        lot_s = "식별 번호 없음"
    mats = [m for m in materials if m]
    mat_s = (mats[0] + (f" 외 {len(mats) - 1}" if len(mats) > 1 else "")) if mats else "-"
    q_s = f" {_n(qty)} EA" if qty else ""
    return f"[입고] {lot_s} · {mat_s}{q_s} — {who} · {vendor}"


def fmt_input(pn, qty, w_lot, who):
    return f"[투입] {pn or '-'} {_n(qty)} EA · 소재 {w_lot or '-'} — {who}"


def fmt_wo_event(event_type, pn, qty, who, vendor=None, step=None, defect=None,
                 detail=None):
    if event_type == "INSPECT":
        # 검사 판정 (2026-09-16 추가): 완성(합격+특채) · 불합격 내역 · LOT
        d = detail or {}
        done = float(d.get("output") or 0) or (
            float(d.get("pass") or 0) + float(d.get("tokusai") or 0))
        parts = [f"완성 {_n(done)}"]
        for k, lbl in (("rework", "재작업"), ("tokusai", "특채"),
                       ("return", "반품"), ("scrap", "기타")):
            if float(d.get(k) or 0) > 0:
                parts.append(f"{lbl} {_n(d.get(k))}")
        lot = f" · LOT {d['lot']}" if d.get("lot") else ""
        return f"[검사] {pn or '-'} {' · '.join(parts)} EA{lot} — {who}"
    if event_type == "RECEIVE":
        d = f" (불량 {_n(defect)})" if defect else ""
        return f"[완료] {pn or '-'} {_n(qty)} EA{d} — {who}"
    if event_type == "OUT_SEND":
        s = f" · {step}" if step else ""
        return f"[외주 출고] {pn or '-'} {_n(qty)} EA{s} → {vendor or '-'} — {who}"
    if event_type == "OUT_RETURN":
        return f"[외주 입고] {pn or '-'} {_n(qty)} EA ← {vendor or '-'} — {who}"
    if event_type == "STEP_CANCEL":
        # 공정 취소 (2026-09-16 추가) — 되돌린 처리를 상세에
        d = detail or {}
        back = {"STEP_START": "시작 취소", "OUT_SEND": "외주 출고 취소"}.get(
            d.get("cancelled"), "취소")
        s = f" · {step}" if step else ""
        return f"[공정 취소] {pn or '-'} {_n(qty)} EA{s} — {who} · {back}"
    return None


def fmt_cancel(tag, pn, qty, who, extra=None):
    """투입 취소 등 되돌리기 알림 — "[태그] 내용 — 사람 · 상세" """
    tail = f" · {extra}" if extra else ""
    return f"[{tag}] {pn or '-'} {_n(qty)} EA — {who}{tail}"


def fmt_ship(ship_no, customers, n_items, total_qty, who):
    cust = ", ".join(sorted(c for c in set(customers) if c)) or "-"
    return f"[출고] {ship_no} · {cust} · {n_items}품목 {_n(total_qty)}개 — {who}"
