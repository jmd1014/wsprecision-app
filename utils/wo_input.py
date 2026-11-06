"""투입 등록 품번 후보 계산(순수 함수, 2026-11-06 재발 방지 소묶음 A).

화면(공정 관리 → 투입 등록)은 DB 조회만 하고, 후보 목록·라벨·기본 선택·안내 문구는 여기서 정한다.

- BOM 후보: 이 소재를 쓰는 활성 제품. 미납 수주가 있는 제품을 앞에, 그다음 품번 순.
- 힌트: 소재 LOT 의 입고 → 발주 라인이 가리키는 품번. 기본 선택일 뿐 강제하지 않는다
  (2026-09-16 T16ABV/20ABV 오등록 사고 — 작업지시서 품번과 대조해 고르도록 선택창을 항상 보인다).
  BOM 후보에 없으면 맨 앞에 끼워 넣는다.
- 힌트가 휴면 품번이면 힌트로 쓰지 않고 후보에서도 빼며 안내 문구를 돌려준다(2026-11-06 후보 49).
- 앞서 고른 선택이 라벨 변동으로 풀리거나 후보에서 빠졌는지 판정한다(prev_selection, 2026-11-06 r2).
"""
import re


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


# ── 앞서 고른 선택 판정 (2026-11-06 r2 D-1·D-2) ──
# 선택 상자 라벨에 미납 수량·「(발주 라인 기준)」이 들어 있어, 라벨이 바뀌면 Streamlit 은 그 선택을 못 찾고
# index(기본값)로 되돌린다 → 같은 run 의 [투입 등록] 클릭이 사용자가 본 것과 다른 품번으로 등록됐다.
# 화면은 선택 상자를 만들기 전에 세션의 옛 라벨을 읽어 이 함수로 판정한다.
_SRC_SUFFIX = re.compile(r"^(.*) \([^()]* 기준\)$")
_OPEN_SUFFIX = re.compile(r"^(.*) ← 미납 [-\d,.]+$")


def label_pn(label):
    """pn_candidates 가 만든 라벨에서 품번을 되찾는다 — 「 (… 기준)」·「 ← 미납 N」 꼬리를 뗀 나머지(정확 일치용)."""
    s = str(label or "")
    m = _SRC_SUFFIX.match(s)
    if m:
        s = m.group(1)
    m = _OPEN_SUFFIX.match(s)
    if m:
        s = m.group(1)
    return s


def prev_selection(prev_label, cands, labels):
    """옛 선택 라벨 → {"state", "pn", "index"}.

    none    : 옛 값 없음(처음 그림·LOT 바꿈)
    same    : 옛 라벨이 새 라벨에 그대로 있음
    relabel : 같은 품번이 새 후보에 있고 라벨·위치만 바뀜 → 화면은 index 로 그 위치를 넘겨 선택 유지(D-2)
    gone    : 옛 품번이 새 후보에 없음(휴면 처리 등, 후보 0개 포함) → 그 run 은 등록 차단(D-1)
    """
    if prev_label is None:
        return {"state": "none", "pn": None, "index": None}
    labels = list(labels or [])
    if prev_label in labels:
        i = labels.index(prev_label)
        return {"state": "same", "pn": cands[i]["pn"], "index": i}
    pn = label_pn(prev_label)
    i = next((k for k, c in enumerate(cands or []) if c["pn"] == pn), None)
    if i is None:
        return {"state": "gone", "pn": None, "index": None}
    return {"state": "relabel", "pn": pn, "index": i}


def gone_message(prev_label):
    return (f"앞서 고른 품번 {prev_label} 이 후보에서 빠졌습니다(휴면 처리 등) — "
            "품번을 다시 확인하세요. 이번 클릭은 등록하지 않았습니다.")
