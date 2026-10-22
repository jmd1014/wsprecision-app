# -*- coding: utf-8 -*-
"""수주 종결·취소·되돌리기 루틴 (2026-10-22, 수주 상태 정리 L3-S).

기준: _수주상태_검토의견_20261022.md §2 D1~D8 / 마이그레이션 075.

- 수주 머리글 상태는 **파생값**이다: 접수(DRAFT) → 부분 진행(PARTIAL) → 완납(DELIVERED)은 출고 확정이
  `header_status()` 로 바꾸고, 종결(CLOSED)·취소(CANCELLED)는 `close_sales_order()` 버튼 루틴만 쓴다.
  수동 selectbox 로 상태를 고르는 경로는 없다(취소를 고르면 잔량이 남아 자재 소요·계획률을 오염시켰다).
- 종결과 취소는 **같은 루틴**(mode 만 다름): 미확정 출고 전표 검사 → 미납 라인마다 잔량 보존(closed_qty)·
  pending_qty 0·상태 mode → 납품 회차 qty=delivered_qty(재발주 대체와 같은 방식) → 전 라인 pending 0 이면 머리글 mode.
- 되돌리기는 예외 경로: 잔량 복원·라인 상태 재계산·머리글 재계산. 닫힌 회차는 복원하지 않고 안내만.
- 이 모듈은 Streamlit 을 모른다. db 는 fetch/update_count/update 를 가진 모듈(또는 목).
"""
from datetime import date as _date

SO_INACTIVE = ("CANCELLED", "CANCELED", "CLOSED")
SO_INACTIVE_FQ = 'status=not.in.("CANCELLED","CANCELED","CLOSED")'
CLOSE_REASONS = ("월 변경 이월", "고객 요청 중단", "기타")
MODES = ("CLOSED", "CANCELLED")
MODE_KO = {"CLOSED": "종결", "CANCELLED": "취소"}


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def is_inactive(status) -> bool:
    return str(status or "").upper() in SO_INACTIVE


def header_status(lines) -> str:
    """출고 확정·되돌리기 뒤 수주 머리글 상태(파생값, D1).

    전 라인 납품 ≥ 수량 → DELIVERED, 하나라도 납품 > 0 → PARTIAL, 아니면 DRAFT(접수).
    라인이 없으면 DRAFT. (이전에는 납품 0 을 CONFIRMED 로 썼다 — 작성과 구분 안 됨)
    """
    rows = list(lines or [])
    if not rows:
        return "DRAFT"
    if all(_f(r.get("received_qty")) >= _f(r.get("qty")) - 1e-9 for r in rows):
        return "DELIVERED"
    if any(_f(r.get("received_qty")) > 0 for r in rows):
        return "PARTIAL"
    return "DRAFT"


def line_reopen_status(line) -> str:
    """되돌린 라인의 상태: 납품 > 0 → PARTIAL, 아니면 PENDING."""
    return "PARTIAL" if _f(line.get("received_qty")) > 0 else "PENDING"


def _append_remark(old, text):
    old = (old or "").strip()
    return (old + " · " if old else "") + text


def open_shipments_for(db, soi_ids):
    """이 라인들을 참조하는 **미확정(DRAFT)** 출고 전표 번호 목록. 종결 전 차단 검사(검토 ⑨)."""
    ids = [int(i) for i in soi_ids if i is not None]
    if not ids:
        return []
    items = []
    for i0 in range(0, len(ids), 100):
        items += db.fetch("shipment_items", "shipment_id,soi_id",
                          "soi_id=in.({})".format(",".join(str(i) for i in ids[i0:i0 + 100])),
                          limit=1000)
    sids = sorted({int(x["shipment_id"]) for x in items if x.get("shipment_id") is not None})
    if not sids:
        return []
    drafts = []
    for i0 in range(0, len(sids), 100):
        drafts += db.fetch("shipments", "shipment_id,ship_no,status",
                           "status=eq.DRAFT&shipment_id=in.({})".format(
                               ",".join(str(s) for s in sids[i0:i0 + 100])), limit=200)
    return sorted({str(d.get("ship_no") or d.get("shipment_id")) for d in drafts})


def _lines(db, so_id):
    return db.fetch("sales_order_items",
                    "soi_id,so_id,qty,received_qty,pending_qty,status,remark,closed_qty,close_reason",
                    f"so_id=eq.{int(so_id)}&order=soi_id", limit=500)


def close_sales_order(db, so_id, mode, reason, who, today=None):
    """수주 종결(CLOSED) 또는 취소(CANCELLED). 반환 dict:
    ok, blocked(list[ship_no]), closed(n), failed(list[soi_id]), rounds(n), header(bool|None), msg.

    - 미확정 출고 전표가 라인을 참조하면 아무것도 쓰지 않고 blocked 로 돌려준다.
    - 라인 갱신은 `pending_qty=gt.0` 조건부 update_count — 두 번 실행돼도 두 번째는 0행.
    - 전 라인 pending 0 이 됐을 때만 머리글 상태를 바꾼다. 일부 실패면 header=None 으로 명시.
    """
    mode = str(mode or "").upper()
    if mode not in MODES:
        raise ValueError(f"close_sales_order: mode 는 {MODES} 중 하나 ({mode})")
    reason = (reason or "").strip()
    if not reason:
        return {"ok": False, "blocked": [], "closed": 0, "failed": [], "rounds": 0,
                "header": None, "msg": "사유를 입력하세요"}
    d = (today or _date.today()).isoformat() if not isinstance(today, str) else today
    who = who or "-"
    ko = MODE_KO[mode]
    lines = _lines(db, so_id)
    open_lines = [l for l in lines if _f(l.get("pending_qty")) > 0]
    blocked = open_shipments_for(db, [l["soi_id"] for l in open_lines])
    if blocked:
        return {"ok": False, "blocked": blocked, "closed": 0, "failed": [], "rounds": 0,
                "header": None,
                "msg": f"미확정 출고 전표가 이 수주 라인을 참조합니다 — 먼저 확정하거나 삭제하세요: {', '.join(blocked)}"}
    tag = f"{ko}({reason}) {d} {who}"
    closed, failed, rounds = 0, [], 0
    for l in open_lines:
        pend = _f(l.get("pending_qty"))
        try:
            n = db.update_count(
                "sales_order_items", f"soi_id=eq.{int(l['soi_id'])}&pending_qty=gt.0",
                {"closed_qty": pend, "pending_qty": 0, "status": mode, "close_reason": reason,
                 "remark": _append_remark(l.get("remark"), tag)})
        except Exception as e:
            _log(db, f"sales_order_items {ko} 실패(soi {l['soi_id']}): {e}")
            n = -1
        if n != 1:
            failed.append(l["soi_id"])
            continue
        closed += 1
        # 납품 회차: 미충당분 닫기 (qty = delivered_qty) — 재발주 대체와 동일
        try:
            for r in db.fetch("so_delivery_schedule", "sched_id,qty,delivered_qty",
                              f"soi_id=eq.{int(l['soi_id'])}", limit=200):
                if _f(r.get("qty")) - _f(r.get("delivered_qty")) > 1e-9:
                    if db.update("so_delivery_schedule", f"sched_id=eq.{int(r['sched_id'])}",
                                 {"qty": _f(r.get("delivered_qty"))}):
                        rounds += 1
        except Exception as e:
            _log(db, f"so_delivery_schedule 회차 닫기 실패(soi {l['soi_id']}): {e}")
    header = None
    after = _lines(db, so_id)
    if closed and not failed and after and all(_f(l.get("pending_qty")) <= 0 for l in after):
        hdr = db.fetch("sales_orders", "so_id,status,remark", f"so_id=eq.{int(so_id)}", limit=1)
        hdr = hdr[0] if hdr else {}
        try:
            header = bool(db.update("sales_orders", f"so_id=eq.{int(so_id)}",
                                    {"status": mode,
                                     "remark": _append_remark(hdr.get("remark"), tag)}))
        except Exception as e:
            _log(db, f"sales_orders {ko} 머리글 갱신 실패(so {so_id}): {e}")
            header = False
    if failed:
        msg = (f"{ko} 일부만 반영 — 라인 {closed}/{len(open_lines)} (실패 soi {', '.join(map(str, failed))}). "
               "머리글은 바꾸지 않았습니다. 화면을 다시 열어 확인하세요")
    elif header is False:
        msg = f"{ko} — 라인 {closed}줄은 반영됐으나 머리글 상태 저장에 실패했습니다. 다시 시도하세요"
    elif not open_lines:
        msg = f"미납 라인이 없어 {ko}할 잔량이 없습니다"
    else:
        msg = f"{ko} — 라인 {closed}줄 잔량 보존, 회차 {rounds}건 닫음" + ("" if header else " (머리글 유지)")
    return {"ok": not failed and header is not False, "blocked": [], "closed": closed,
            "failed": failed, "rounds": rounds, "header": header, "msg": msg}


def reopen_sales_order(db, so_id, who, today=None):
    """종결·취소 되돌리기: closed_qty → pending_qty, 라인 상태 재계산, 머리글 재계산.
    닫힌 회차는 복원하지 않는다(안내만). 반환 dict: ok, reopened(n), failed(list), header(str|None), msg."""
    d = (today or _date.today()).isoformat() if not isinstance(today, str) else today
    who = who or "-"
    lines = _lines(db, so_id)
    targets = [l for l in lines if _f(l.get("closed_qty")) > 0 and str(l.get("status") or "").upper() in SO_INACTIVE]
    reopened, failed = 0, []
    for l in targets:
        cq = _f(l.get("closed_qty"))
        try:
            n = db.update_count(
                "sales_order_items", f"soi_id=eq.{int(l['soi_id'])}&closed_qty=gt.0",
                {"pending_qty": cq, "closed_qty": 0, "status": line_reopen_status(l),
                 "close_reason": None,
                 "remark": _append_remark(l.get("remark"), f"되돌림 {d} {who}")})
        except Exception as e:
            _log(db, f"sales_order_items 되돌리기 실패(soi {l['soi_id']}): {e}")
            n = -1
        if n == 1:
            reopened += 1
        else:
            failed.append(l["soi_id"])
    header = None
    if targets and not failed:
        after = _lines(db, so_id)
        new_st = header_status(after)
        hdr = db.fetch("sales_orders", "so_id,status,remark", f"so_id=eq.{int(so_id)}", limit=1)
        hdr = hdr[0] if hdr else {}
        try:
            if db.update("sales_orders", f"so_id=eq.{int(so_id)}",
                         {"status": new_st,
                          "remark": _append_remark(hdr.get("remark"), f"되돌림 {d} {who}")}):
                header = new_st
        except Exception as e:
            _log(db, f"sales_orders 되돌리기 머리글 갱신 실패(so {so_id}): {e}")
    if not targets:
        msg = "되돌릴 잔량이 없습니다(종결·취소된 라인 없음)"
    elif failed:
        msg = (f"되돌리기 일부만 반영 — 라인 {reopened}/{len(targets)} (실패 soi {', '.join(map(str, failed))}). "
               "머리글은 바꾸지 않았습니다")
    elif header is None:
        msg = f"라인 {reopened}줄 잔량 복원됐으나 머리글 상태 저장에 실패했습니다"
    else:
        msg = (f"되돌리기 — 라인 {reopened}줄 잔량 복원, 머리글 {header}. "
               "닫힌 납품 회차는 복원하지 않았습니다 — 필요하면 납품 스케줄에서 다시 잡으세요")
    return {"ok": bool(targets) and not failed and header is not None,
            "reopened": reopened, "failed": failed, "header": header, "msg": msg}


def _log(db, detail):
    fn = getattr(db, "log_error", None)
    if fn:
        try:
            fn("db_write", detail, table_name="sales_orders")
        except Exception:
            pass
