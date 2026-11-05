# -*- coding: utf-8 -*-
"""납품 스케줄(so_delivery_schedule) 저장 계획 — 순수 함수 (납기 입력 안정화 묶음 후보 27, 2026-11-05).

so_delivery_schedule 은 UNIQUE(soi_id, seq). 예전 저장은 유지 회차를 행마다 `seq=새번호` 로 PATCH 한 뒤
삭제했다 — 중간 회차를 지우거나 앞 날짜를 넣어 번호가 당겨·밀리면 아직 남아 있는 다른 행과 번호가 겹쳐
409 → db.update 가 False 를 돌려주고, 코드는 보지 않아 그 회차의 번호·수량·납품완료가 **조용히 옛 값**으로
남았다(4PDVN-02 10/23 유실의 근본 원인).

계획(화면은 이 순서대로 실행만 하고, 쓰기마다 반환값을 본다):
  1. delete  — 사라지는 회차를 먼저 지워 번호 자리를 비운다
  2. phase1  — 번호가 바뀌는 유지 회차를 임시 번호로 — 임시 번호는 지금 있는 모든 번호·최종 번호보다 큰 영역
               (max(TMP_BASE, 최댓값+1) 부터 차례로)이라 남은 어떤 행과도 겹치지 않는다
  3. phase2  — 유지 회차 전부: 최종 번호 + qty·note·delivered_qty
  4. insert  — 새 회차(최종 번호)
임시 번호(TMP_BASE 이상)가 남은 상태는 다음 저장이 다시 재부여하므로 복구 가능하다 — 다음 저장의 임시 영역은
남아 있는 임시 번호보다도 위에서 시작한다(Codex 1차 H: 1000+옛 번호 방식은 중단으로 남은 1002 와 2→1002 가 겹쳤다).
"""

TMP_BASE = 1000       # 임시 번호 영역 시작(화면은 seq ≥ TMP_BASE 를 "저장 중단" 으로 표기)


def _d(v):
    return str(v)[:10]


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _note(v):
    return str(v or "").strip()


def plan_sched_writes(old_rows, keep, tmp_base=TMP_BASE):
    """old_rows: DB 회차 [{sched_id, due_date, seq, qty, note, delivered_qty, ...}].
    keep: 저장할 회차(납기순·같은 날짜 병합 뒤) [{due_date, seq(최종), qty, note, delivered_qty, ...}].
    같은 납기 날짜의 옛 회차는 sched_id 를 유지한다(확정 전표 회차 연결 shipment_allocations.sched_id 보존).
    returns {"delete": [sched_id], "phase1": [(sched_id, tmp_seq)], "phase2": [(sched_id, fields)],
             "insert": [row], "gone": [old_row], "pairs": [(old_row, keep_row)],
             "guard": {sched_id: 옛 delivered_qty}}  — guard 는 update_count 조건(동시 출고 확정 lost update 방지)
    phase2 순서(r2 ⑤): 납품완료가 늘어나는 행 → 같은 행 → 줄어드는 행 — 중간에 멈춰도 회차 납품합이 라인
    기납품 이상으로 남아 다음 저장의 승계(carry_delivered)가 깎아 복구한다. 번호·수량·비고·납품완료가 모두 같은
    유지 회차는 phase2 에서 뺀다(r2 ⑩)."""
    seqs = [int(o.get("seq") or 0) for o in old_rows] + [int(r["seq"]) for r in keep]
    tmp_next = max([tmp_base] + [x + 1 for x in seqs])
    by_date = {}
    # 같은 날짜 옛 회차가 여럿이면(예전 중복 저장) 납품된 회차를 먼저 유지 — 확정 전표 연결·납품 사실을 지키고,
    # 사라지는 쪽이 미납품 회차가 되게(r2 ⑬, 납품 회차 삭제 차단 B 에 걸리지 않게)
    for o in sorted(old_rows, key=lambda r: (-_f(r.get("delivered_qty")),
                                             int(r.get("seq") or 0), r.get("sched_id") or 0)):
        by_date.setdefault(_d(o.get("due_date")), []).append(o)
    phase1, p2, insert, kept, pairs, guard = [], [], [], set(), [], {}
    for r in keep:
        cands = by_date.get(_d(r["due_date"])) or []
        if cands:
            o = cands.pop(0)
            kept.add(o["sched_id"])
            pairs.append((o, r))
            guard[o["sched_id"]] = o.get("delivered_qty")
            moved = int(o.get("seq") or 0) != int(r["seq"])
            if moved:
                phase1.append((o["sched_id"], tmp_next))
                tmp_next += 1
            same = (not moved and abs(_f(o.get("qty")) - _f(r["qty"])) < 1e-9
                    and _note(o.get("note")) == _note(r.get("note"))
                    and abs(_f(o.get("delivered_qty")) - _f(r["delivered_qty"])) < 1e-9)
            if not same:
                delta = _f(r["delivered_qty"]) - _f(o.get("delivered_qty"))
                p2.append((0 if delta > 1e-9 else 2 if delta < -1e-9 else 1, len(p2),
                           (o["sched_id"], {"qty": r["qty"], "note": r.get("note"), "seq": r["seq"],
                                            "delivered_qty": r["delivered_qty"]})))
        else:
            insert.append(r)
    # r2 ⑥: 임시 번호는 어떤 행의 지금 번호와도 겹치지 않는다(최댓값 위 영역)
    cur = {int(o.get("seq") or 0) for o in old_rows}
    assert not any(t in cur for _, t in phase1), "임시 번호가 기존 번호와 겹침"
    gone = [o for o in old_rows if o.get("sched_id") not in kept]
    return {"delete": [o["sched_id"] for o in gone], "phase1": phase1,
            "phase2": [x[2] for x in sorted(p2, key=lambda x: (x[0], x[1]))],
            "insert": insert, "gone": gone, "pairs": pairs, "guard": guard}


# ── 납기 입력 핫픽스 1(2026-11-05): 회차 삭제 전 전표 참조 확인 ──
# cccae4f 는 shipment_allocations 에서 없는 열(shipment_id)을 골라 운영에서 항상 400 → 회차 삭제 저장 전부 차단.
# 충당 행(shipment_allocations)에는 전표 id 가 없다 — si_id 로 전표 라인(shipment_items)을 거쳐 전표를 찾는다.
# 테이블별 select 열은 여기 한 곳(tests/test_sched_refs.py 가 마이그레이션 테이블 정의와 대조).
REFS_SELECT = {
    "shipment_allocations": "sched_id,si_id",
    "shipment_items": "si_id,sched_id,shipment_id",
    "shipments": "shipment_id,ship_no,status",
}
REFS_LIMIT = 200


def sched_refs_message(allocs, items, alloc_lines, ships):
    """회차 참조 분류·문구(순수 함수). 문구 또는 None.
    allocs = 지울 회차의 충당 행(sched_id, si_id) · items = 지울 회차를 가리키는 전표 라인(sched_id 기준) ·
    alloc_lines = 충당 행의 si_id 로 찾은 전표 라인 · ships = 관련 전표(shipment_id, ship_no, status).
    충당 행 → 확정 전표, 라인 중 DRAFT 전표 → 작성중, 그 밖 → 전표. 충당 행의 라인을 못 찾으면 "미상" 으로 차단 유지."""
    allocs, items = list(allocs or []), list(items or [])
    if not allocs and not items:
        return None
    sh = {r.get("shipment_id"): r for r in ships or []}
    line_ship = {r.get("si_id"): r.get("shipment_id") for r in list(alloc_lines or []) + items}

    def _label(shid):
        return (sh.get(shid) or {}).get("ship_no") or str(shid)

    conf = set()
    for a in allocs:
        shid = line_ship.get(a.get("si_id"))
        conf.add(_label(shid) if shid is not None else f"미상(전표 라인 {a.get('si_id')})")
    draft = {_label(r.get("shipment_id")) for r in items
             if (sh.get(r.get("shipment_id")) or {}).get("status") == "DRAFT"}
    other = {_label(r.get("shipment_id")) for r in items} - draft - conf
    parts = []
    if conf:
        parts.append(f"확정 전표 {', '.join(sorted(conf))} 에 연결된 회차라 삭제할 수 없습니다")
    if draft:
        parts.append(f"작성중 전표 {', '.join(sorted(draft))} 가 이 회차를 가리킵니다 — 전표를 먼저 정리하세요")
    if other:
        parts.append(f"전표 {', '.join(sorted(other))} 가 이 회차를 가리킵니다")
    return " · ".join(parts) + "."


def sched_refs_block(sched_ids, fetch):
    """지울 회차 id 들을 전표가 가리키면 사유 문구(없으면 None). fetch = db.fetch 형태.
    어느 조회든 실패하면 차단 문구(fail-closed), 반환이 상한(REFS_LIMIT)에 닿으면 잘렸을 수 있어 차단."""
    ids = [str(i) for i in sched_ids if i is not None]
    if not ids:
        return None
    lim = REFS_LIMIT
    inn = ",".join(ids)
    try:
        al = fetch("shipment_allocations", REFS_SELECT["shipment_allocations"],
                   f"sched_id=in.({inn})", limit=lim, cache=False) or []
        si = fetch("shipment_items", REFS_SELECT["shipment_items"],
                   f"sched_id=in.({inn})", limit=lim, cache=False) or []
        need = sorted({a.get("si_id") for a in al if a.get("si_id") is not None}
                      - {r.get("si_id") for r in si})
        al_lines = (fetch("shipment_items", REFS_SELECT["shipment_items"],
                          "si_id=in.(" + ",".join(str(x) for x in need) + ")", limit=lim, cache=False) or []
                    if need else [])
        sh_ids = sorted({r.get("shipment_id") for r in list(si) + list(al_lines) if r.get("shipment_id") is not None})
        ships = (fetch("shipments", REFS_SELECT["shipments"],
                       "shipment_id=in.(" + ",".join(str(x) for x in sh_ids) + ")", limit=lim, cache=False) or []
                 if sh_ids else [])
    except Exception as e:
        return f"연결된 전표를 확인하지 못했습니다({e}) — 새로고침 뒤 다시 시도하세요."
    if any(len(x) >= lim for x in (al, si, al_lines, ships)):
        return (f"연결된 전표 기록이 많아({lim}행 이상) 전부 확인하지 못했습니다 — "
                "회차를 나눠 지우거나 관리자에게 문의하세요.")
    return sched_refs_message(al, si, al_lines, ships)
