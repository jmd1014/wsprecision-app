# -*- coding: utf-8 -*-
"""수주 종결·취소·되돌리기 — RPC 래퍼 + 상태 규칙 (2026-10-22, 수주 상태 정리 r2 / 마이그레이션 076).

기준: _수주상태_검토의견_20261022.md D1~D8 + _수주상태_r1리뷰_분류_및_수정지시문_20261022.md D9~D14.

- 수주 머리글 상태는 **파생값**: 접수(DRAFT) → 부분 진행(PARTIAL) → 완납(DELIVERED)은 출고 확정·정정·되돌리기가
  `header_status()`(활성 라인만, 납품 0 = DRAFT)로 계산한다. 종결(CLOSED)·취소(CANCELLED)는 RPC 버튼 루틴만 쓴다.
- D9 원자화: 종결·취소 = `so_close_lines`, 되돌리기 = `so_reopen_lines` (076, 한 트랜잭션·서버 값·멱등).
  이 모듈은 RPC 호출 + 거부 사유 → 메시지만 담당한다. 쓰기 전 조회는 하지 않는다(TOCTOU 없음).
- D11 비활성 라인 집합 = {CLOSED, CANCELLED, REPLACED}: 출고 정정(`revise_line_fields`)·머리글 계산·뷰·069 모두 제외.
- 응답 불명(RpcTransportError)은 멱등이므로 **1회 재호출**, 그래도 실패면 "화면을 다시 열어 확인".
- 이 모듈은 Streamlit 을 모른다. db 는 rpc/fetch/update 를 가진 모듈(또는 목).
"""
from utils.shipment_adjust import line_status

SO_INACTIVE = ("CANCELLED", "CANCELED", "CLOSED")                 # 머리글 비활성 (활성 수주 집합 = 이것을 뺀 것)
SO_INACTIVE_FQ = 'status=not.in.("CANCELLED","CANCELED","CLOSED")'
LINE_INACTIVE = ("CLOSED", "CANCELLED", "REPLACED")              # 라인 비활성 (D11)
CLOSE_REASONS = ("월 변경 이월", "고객 요청 중단", "기타")
MODES = ("CLOSED", "CANCELLED")
MODE_KO = {"CLOSED": "종결", "CANCELLED": "취소"}
RPC_CLOSE = "so_close_lines"
RPC_REOPEN = "so_reopen_lines"


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def is_inactive(status) -> bool:
    return str(status or "").upper() in SO_INACTIVE


def is_line_inactive(status) -> bool:
    return str(status or "").upper() in LINE_INACTIVE


def header_status(lines, current=None) -> str:
    """수주 머리글 상태(파생값, D1·D11): 비활성 라인(CLOSED·CANCELLED·REPLACED)을 뺀 활성 라인으로 계산.

    전 라인 납품 ≥ 수량 → DELIVERED, 하나라도 납품 > 0 → PARTIAL, 아니면 DRAFT(접수).
    활성 라인이 없으면 `current`(없으면 DRAFT) — 대체·종결로만 이뤄진 수주의 상태를 덮지 않는다.
    """
    rows = [r for r in (lines or []) if not is_line_inactive(r.get("status"))]
    if not rows:
        return current or "DRAFT"
    if all(_f(r.get("received_qty")) >= _f(r.get("qty")) - 1e-9 for r in rows):
        return "DELIVERED"
    if any(_f(r.get("received_qty")) > 0 for r in rows):
        return "PARTIAL"
    return "DRAFT"


def kept_mode(lines):
    """보존 잔량(closed_qty>0) 라인들의 상태 — CLOSED / CANCELLED / None(없음) / 'MIXED'(혼재)."""
    modes = {str(l.get("status") or "").upper() for l in (lines or []) if _f(l.get("closed_qty")) > 0}
    modes &= {"CLOSED", "CANCELLED"}
    if not modes:
        return None
    return modes.pop() if len(modes) == 1 else "MIXED"


def line_reopen_status(line) -> str:
    """되돌린 라인의 상태: 납품 > 0 → PARTIAL, 아니면 PENDING."""
    return "PARTIAL" if _f(line.get("received_qty")) > 0 else "PENDING"


def revise_line_fields(line, new_received, header_status=None) -> dict:
    """출고 정정·취소가 수주 라인에 쓸 값 (F3·D15). 활성 라인은 기존 규칙(received·pending·status).
    비활성 라인(CLOSED·CANCELLED·REPLACED)은 received 만 조정하고 pending 0·status 유지,
    CLOSED/CANCELLED 는 closed_qty = qty − received(received + pending + closed = qty 불변식 ⑤), REPLACED 는 closed_qty 0.
    **머리글이 종결·취소(header_status)면 라인 상태와 무관하게 비활성 취급**(D15, Codex r2 H1): 완납 라인(DELIVERED,
    pending 0)을 감소 정정해도 PENDING 으로 되살리지 않고 status = 머리글 모드·closed_qty = qty − received 로 보존한다
    (되돌리기로 복원). REPLACED 라인은 그대로."""
    qty = _f(line.get("qty"))
    nr = max(_f(new_received), 0.0)
    st = str(line.get("status") or "").upper()
    hdr = str(header_status or "").upper()
    if st == "REPLACED":
        return {"received_qty": nr, "pending_qty": 0, "status": st}
    if st in ("CLOSED", "CANCELLED"):
        return {"received_qty": nr, "pending_qty": 0, "status": st, "closed_qty": max(qty - nr, 0.0)}
    if hdr in ("CLOSED", "CANCELLED", "CANCELED"):
        mode = "CLOSED" if hdr == "CLOSED" else "CANCELLED"
        return {"received_qty": nr, "pending_qty": 0, "status": mode, "closed_qty": max(qty - nr, 0.0)}
    return {"received_qty": nr, "pending_qty": max(qty - nr, 0.0), "status": line_status(qty, nr)}


def recompute_header(db, so_id, force=False):
    """출고 확정·정정·대체 되돌리기 뒤 머리글 재계산 (F5). 머리글이 비활성이면 건드리지 않는다(D11).
    force=True 는 대체 되돌리기(머리글 CANCELLED 가 대체 루틴이 만든 것)에서만 — 비활성 머리글도 활성 라인으로 다시 계산.
    반환: 새 상태(str) 또는 None(비활성·조회 실패·변화 없음)."""
    hdr = db.fetch("sales_orders", "so_id,status", f"so_id=eq.{int(so_id)}", limit=1)
    cur = (hdr[0].get("status") if hdr else None) or "DRAFT"
    if is_inactive(cur) and not force:
        return None
    lines = db.fetch("sales_order_items", "qty,received_qty,status", f"so_id=eq.{int(so_id)}", limit=500)
    if len(lines) >= 500:
        _log(db, f"recompute_header: so {so_id} 라인 조회가 500 한도에 닿음 — 머리글 재계산이 일부 라인을 빼고 계산됐을 수 있다")
    new = header_status(lines, cur)
    if new == cur:
        return None
    return new if db.update("sales_orders", f"so_id=eq.{int(so_id)}", {"status": new}) else None


def replacement_revert_block(header_status_value, lines):
    """단가 변경 재발주 대체의 [되돌리기] 를 막아야 하는지 (QA B-1·M-6).
    머리글이 CLOSED(종결 루틴이 만든 것)이거나 보존 잔량(closed_qty>0) 라인이 있으면 먼저 수주 [되돌리기] 가 필요하다.
    반환: 차단 메시지(str) 또는 None. 머리글 CANCELLED + 보존 라인 없음 = 대체 루틴이 만든 취소 → 허용(되돌린 뒤 force 재계산)."""
    st = str(header_status_value or "").upper()
    kept = [l for l in (lines or []) if _f(l.get("closed_qty")) > 0]
    if st == "CLOSED" or kept:
        return ("이 수주는 종결(또는 잔량 보존) 상태입니다 — 수주 목록에서 먼저 [되돌리기] 를 한 뒤 "
                "대체를 되돌리세요")
    return None


def _log(db, detail):
    """db.log_error 가 있으면 기록(실패해도 삼킨다) — 경고 1줄용."""
    fn = getattr(db, "log_error", None)
    if fn:
        try:
            fn("db_write", detail, table_name="sales_order_items")
        except Exception:
            pass


# ── RPC 래퍼 ──
def _exc(db, name):
    """RPC 예외 클래스 — 실제 db 모듈 것을 우선(목 db 가 들어와도 같은 클래스를 던진다)."""
    try:
        import db as _real
        cls = getattr(_real, name, None)
        if cls is not None:
            return cls
    except Exception:
        pass
    return getattr(db, name, None) or type(name, (Exception,), {})


def _call(db, name, params):
    """RPC 호출. 응답 불명(RpcTransportError)은 멱등이므로 1회 재호출. 반환 (body|None, kind, err)."""
    Rej, Unav, Trans = _exc(db, "RpcRejected"), _exc(db, "RpcUnavailable"), _exc(db, "RpcTransportError")
    retried = False
    for attempt in (1, 2):
        try:
            return db.rpc(name, params), "ok", None, retried
        except Rej as e:
            return None, "rejected", e, retried
        except Unav as e:
            return None, "unavailable", e, retried
        except Trans as e:
            if attempt == 1:
                retried = True
                continue
            return None, "unknown", e, retried
    return None, "unknown", None, retried      # pragma: no cover


def _rej_text(e, ko):
    m = str(getattr(e, "message", "") or str(e))
    hint = str(getattr(e, "hint", "") or "")
    if m == "blocked":
        return (f"미확정 출고 전표가 이 수주 라인을 참조합니다 — 먼저 확정하거나 삭제하세요: {hint or '-'}"), [h.strip() for h in hint.split(",") if h.strip()]
    if m == "not_found":
        return "수주를 찾을 수 없습니다 — 화면을 새로 고치세요", []
    if m == "bad_args":
        return "사유를 입력하세요", []
    code = str(getattr(e, "code", "") or "")
    if code in ("55P03", "57014", "40P01"):
        return f"다른 처리와 겹쳐 {ko}이 취소됐습니다(아무것도 반영되지 않음) — 잠시 후 다시 시도하세요", []
    return f"{ko} 거부 ({code}: {m[:80]}) — 관리자에게 확인하세요", []


def close_sales_order(db, so_id, mode, reason, who, today=None):
    """수주 종결(CLOSED) 또는 취소(CANCELLED) — RPC so_close_lines 한 번. 반환 dict:
    ok, blocked(list[ship_no]), closed(n), rounds(n), header(bool|None), header_status, retried, msg."""
    mode = str(mode or "").upper()
    if mode not in MODES:
        raise ValueError(f"close_sales_order: mode 는 {MODES} 중 하나 ({mode})")
    ko = MODE_KO[mode]
    base = {"ok": False, "blocked": [], "closed": 0, "rounds": 0, "header": None, "header_status": None,
            "retried": False, "msg": ""}
    reason = (reason or "").strip()
    if not reason:
        return {**base, "msg": "사유를 입력하세요"}
    body, kind, err, retried = _call(db, RPC_CLOSE, {"p_so_id": int(so_id), "p_mode": mode,
                                                     "p_reason": reason, "p_who": who or "-"})
    base["retried"] = retried
    if kind == "rejected":
        msg, ships = _rej_text(err, ko)
        if str(getattr(err, "message", "") or "") == "bad_args" and "mode mismatch" in str(getattr(err, "hint", "") or ""):
            msg = f"닫힌 라인의 상태와 다른 방식으로 마무리할 수 없습니다 — 라인이 종결이면 [종결 마무리], 취소면 [수주 취소]로"
        return {**base, "blocked": ships, "msg": msg}
    if kind == "unavailable":
        return {**base, "msg": f"{ko} 기능(076)이 서버에 없습니다 — 관리자에게 확인하세요"}
    if kind == "unknown":
        return {**base, "msg": f"{ko} 응답 불명 — 반영됐을 수 있습니다. 화면을 다시 열어 확인하세요"}
    b = body if isinstance(body, dict) else {}
    closed, rounds, header = int(b.get("closed") or 0), int(b.get("rounds") or 0), bool(b.get("header"))
    hst = b.get("header_status")
    if retried and closed == 0 and not header:
        msg = f"응답 지연으로 재호출 — 첫 호출이 반영된 것으로 보입니다. 현재 머리글 {hst or '-'} — 화면을 확인하세요"
    elif closed == 0 and not header:
        msg = f"미납 라인이 없어 {ko}할 잔량이 없습니다" + (f" (현재 {hst})" if hst else "")
    elif closed == 0 and header:
        msg = f"{ko} 마무리 — 닫힌 라인만 남아 있어 머리글을 {ko} 상태로 맞췄습니다"
    else:
        msg = f"{ko} — 라인 {closed}줄 잔량 보존, 회차 {rounds}건 닫음"
        if retried:
            msg += " · 응답 지연으로 1회 재호출"
    return {**base, "ok": True, "closed": closed, "rounds": rounds, "header": header, "header_status": hst, "msg": msg}


def reopen_sales_order(db, so_id, who, today=None):
    """종결·취소 되돌리기 — RPC so_reopen_lines 한 번. 반환 dict:
    ok, reopened(n), rounds_restored, rounds_skipped, header(str|None), header_status, retried, msg."""
    base = {"ok": False, "reopened": 0, "rounds_restored": 0, "rounds_skipped": 0, "header": None,
            "header_status": None, "retried": False, "msg": ""}
    body, kind, err, retried = _call(db, RPC_REOPEN, {"p_so_id": int(so_id), "p_who": who or "-"})
    base["retried"] = retried
    if kind == "rejected":
        msg, _ = _rej_text(err, "되돌리기")
        return {**base, "msg": msg}
    if kind == "unavailable":
        return {**base, "msg": "되돌리기 기능(076)이 서버에 없습니다 — 관리자에게 확인하세요"}
    if kind == "unknown":
        return {**base, "msg": "되돌리기 응답 불명 — 반영됐을 수 있습니다. 화면을 다시 열어 확인하세요"}
    b = body if isinstance(body, dict) else {}
    n, rr, rs = int(b.get("reopened") or 0), int(b.get("rounds_restored") or 0), int(b.get("rounds_skipped") or 0)
    header, hst = b.get("header"), b.get("header_status")
    if retried and n == 0 and header is None:
        msg = f"응답 지연으로 재호출 — 첫 호출이 반영된 것으로 보입니다. 현재 머리글 {hst or '-'} — 화면을 확인하세요"
    elif n == 0 and header is None:
        msg = "되돌릴 잔량이 없습니다(종결·취소된 라인 없음)"
    elif n == 0:
        msg = f"보존 잔량 라인이 없어 머리글만 다시 계산했습니다 — {header}"
    else:
        msg = f"되돌리기 — 라인 {n}줄 잔량 복원, 회차 {rr}건 복원" + (f" · {rs}건 미복원(회차가 이미 열려 있음 — 납품 스케줄에서 확인)" if rs else "") + f", 머리글 {header}"
        if retried:
            msg += " · 응답 지연으로 1회 재호출"
    return {**base, "ok": n > 0 or header is not None or retried, "reopened": n, "rounds_restored": rr, "rounds_skipped": rs,
            "header": header, "header_status": hst, "retried": retried, "msg": msg}
