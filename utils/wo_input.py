"""투입 등록 품번 후보 계산(순수 함수, 2026-11-06 재발 방지 소묶음 A).

화면(공정 관리 → 투입 등록)은 DB 조회만 하고, 후보 목록·라벨·기본 선택·안내 문구는 여기서 정한다.

- BOM 후보: 이 소재를 쓰는 활성 제품. 미납 수주가 있는 제품을 앞에, 그다음 품번 순.
- 힌트: 소재 LOT 의 입고 → 발주 라인이 가리키는 품번. 기본 선택일 뿐 강제하지 않는다
  (2026-09-16 T16ABV/20ABV 오등록 사고 — 작업지시서 품번과 대조해 고르도록 선택창을 항상 보인다).
  BOM 후보에 없으면 맨 앞에 끼워 넣는다.
- 힌트가 휴면 품번이면 힌트로 쓰지 않고 후보에서도 빼며 안내 문구를 돌려준다(2026-11-06 후보 49).
"""


def order_bom_candidates(bom_rows, open_pids):
    """미납 수주 있는 제품 우선, 그다음 품번 순."""
    return sorted(bom_rows or [], key=lambda p: (p["product_id"] not in open_pids, p["pn"]))


def pn_candidates(bom_rows, open_pend, hint=None, open_pids=None):
    """투입 등록 품번 선택 상자의 후보.

    bom_rows: [{"product_id", "pn"}] — 이 소재를 쓰는 활성 BOM 제품(정렬 무관)
    open_pend: {product_id: 미납 합}
    hint: 발주 라인 품번 {"pn", "src", "product_id", "archived"} 또는 None
    open_pids: 미납 라벨·우선 정렬 대상(기본 = open_pend 의 키)

    반환 {"cands": [{"pn", "product_id"}], "labels": [str], "default": int, "notice": str | None}
    cands 가 비면 화면은 직접 입력 칸을 보인다.
    """
    open_pend = open_pend or {}
    open_pids = set(open_pend) if open_pids is None else set(open_pids)
    hint = dict(hint or {})
    hint_pn = hint.get("pn") or ""
    hint_src = hint.get("src") or ""
    notice, dropped = None, ""
    if hint_pn and hint.get("archived"):
        # 휴면 품번은 힌트·후보·기본값에서 뺀다 — 기본값은 힌트 없는 LOT 과 같은 규칙(2026-11-06 후보 49)
        dropped, hint_pn = hint_pn, ""
        notice = (f"발주 라인의 품번 {dropped} 은 휴면 처리된 품번이라 후보에서 뺐습니다 — "
                  "작업지시서 품번을 확인하세요.")

    cands = [p for p in order_bom_candidates(bom_rows, open_pids) if not dropped or p["pn"] != dropped]
    if hint_pn and all(p["pn"] != hint_pn for p in cands):
        cands.insert(0, {"pn": hint_pn, "product_id": hint.get("product_id")})

    labels = []
    for p in cands:
        lb = p["pn"]
        if p.get("product_id") in open_pids:
            lb += f" ← 미납 {open_pend.get(p['product_id'], 0):,.0f}"
        if hint_pn and p["pn"] == hint_pn:
            lb += f" ({hint_src} 기준)"
        labels.append(lb)
    default = (next((i for i, p in enumerate(cands) if p["pn"] == hint_pn), 0)
               if hint_pn else 0)
    return {"cands": cands, "labels": labels, "default": default, "notice": notice}
