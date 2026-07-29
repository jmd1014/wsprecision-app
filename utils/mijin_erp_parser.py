# -*- coding: utf-8 -*-
"""미진정밀 ERP 외주발주/납품 조회 파서

미진정밀은 우성정밀에 '외주발주'를 내고 '외주납품'을 받는다 →
우성정밀 입장에서 외주발주 = 수주, 외주납품 = 출고.

특징 (2026-07-28 실데이터 2년치 분석):
- 품번에 공정 접미사가 붙는다 (`;PM` `;OUP` `;OP`). 같은 base 에
  접미사가 2종 이상인 경우는 0건 → 접미사는 떼고 매칭해도 안전.
- 제품번호 == 외주품번호 (1,102건 전부 동일).
- 납기일은 97% 비어 있다 (미진 ERP 가 발주에 납기를 안 넣음).
- 한 발주번호에 평균 4.8 라인, 최대 22 라인.
- 4S / S 접두사는 미진 ERP 의 재질 표기 규칙 — 우성 마스터에는
  alias_list 로 등록되어 있다. 자동 추론하지 말고 alias 로만 매칭.
"""
import re

import pandas as pd

# 우성정밀이 미진 ERP 를 통해 받지만 실제 거래처가 엠제이티인 품번
# (마감내역 sales_ledger 기준 판정 — 2024-08 이후 엠제이티 전용)
MJT_ONLY_PNS = {
    "SFB-16", "SFB-24", "SFB-46", "4PDVN-02", "4PDVN-03", "8PDVN-02",
    "12HFDVN-VM-03",
}

_SUFFIX_RE = re.compile(r";\s*(PM|OUP|OP)\s*$", re.I)
_SKIP_PNS = {"-3%(외주반품)", "차액분", "외주반품"}


def strip_suffix(pn):
    """`4S4PDVN-02;OUP` → `4S4PDVN-02`"""
    if pn is None:
        return ""
    return _SUFFIX_RE.sub("", str(pn).strip()).strip()


def customer_for(canonical_pn, erp_pn=None):
    """실제 거래처 판정 — 마스터 품번(canonical) 기준.

    미진 ERP 품번은 4S/S 재질 접두사가 붙어 있어(`4S4PDVN-02`)
    ERP 품번만으로는 엠제이티 품목을 가려낼 수 없다. 마스터 매칭
    결과(canonical_pn)로 판정해야 정확하다.
    """
    for pn in (canonical_pn, strip_suffix(erp_pn) if erp_pn else None):
        if pn and str(pn).strip().upper() in {
                p.upper() for p in MJT_ONLY_PNS}:
            return "㈜엠제이티"
    return "미진정밀"


def _num(v, default=0.0):
    try:
        f = float(v)
        return default if pd.isna(f) else f
    except (TypeError, ValueError):
        return default


def _date(v):
    try:
        d = pd.to_datetime(v, errors="coerce")
        return None if pd.isna(d) else d.date().isoformat()
    except Exception:
        return None


def parse_orders(path_or_buf, open_only=True):
    """외주발주품목조회 → 수주 라인 목록.

    open_only=True 면 미납(진행/작성) 건만. 반환 항목:
      so_number(외주발주번호), so_date, due_date, erp_pn, base_pn,
      wo_number(작업지시번호), qty, delivered_qty, pending_qty,
      unit_price, amount, status_raw, customer_hint
    """
    df = pd.read_excel(path_or_buf, header=1)
    # 2행은 TOTAL 집계행
    df = df[df["외주발주번호"].astype(str).str.match(r"^\d{8,}$", na=False)]

    rows = []
    for _, r in df.iterrows():
        erp_pn = str(r.get("외주품번호") or r.get("제품번호") or "").strip()
        base = strip_suffix(erp_pn)
        if not base or base in _SKIP_PNS:
            continue
        pend = _num(r.get("미납수량"))
        st = str(r.get("진행상태") or "").strip()
        if open_only and (pend <= 0 or st in ("완료", "중단", "진행중단")):
            continue
        rows.append({
            "so_number": str(r["외주발주번호"]).strip(),
            "so_date": _date(r.get("외주발주일")),
            "due_date": _date(r.get("납기일")),
            "erp_pn": erp_pn,
            "base_pn": base,
            "wo_number": (str(r.get("작업지시번호")).strip()
                          if pd.notna(r.get("작업지시번호")) else None),
            "qty": _num(r.get("발주수량")),
            "delivered_qty": _num(r.get("납품수량")),
            "pending_qty": pend,
            "unit_price": _num(r.get("단가")),
            "amount": _num(r.get("금액")),
            "status_raw": st,
            # 잠정 판정 — 마스터 매칭 후 customer_for(canonical_pn)
            # 으로 재판정해야 4S/S 재질 접두사 품번까지 정확하다.
            "customer_hint": customer_for(base),
        })
    return rows


def parse_deliveries(path_or_buf):
    """외주납품품목조회 → 납품(출고) 실적 목록. 대사(對査)용."""
    df = pd.read_excel(path_or_buf, header=1)
    df = df[df["외주납품번호"].astype(str).str.match(r"^\d{8,}$", na=False)]

    rows = []
    for _, r in df.iterrows():
        erp_pn = str(r.get("외주품번호") or "").strip()
        base = strip_suffix(erp_pn)
        if not base or base in _SKIP_PNS:
            continue
        rows.append({
            "delivery_no": str(r["외주납품번호"]).strip(),
            "delivery_date": _date(r.get("외주납품일")),
            "erp_pn": erp_pn,
            "base_pn": base,
            "wo_number": (str(r.get("작업지시번호")).strip()
                          if pd.notna(r.get("작업지시번호")) else None),
            "qty": _num(r.get("납품수량")),
            "unit_price": _num(r.get("단가")),
            "customer_lot": (str(r.get("LotNo")).strip()
                             if pd.notna(r.get("LotNo")) else None),
            # 잠정 판정 — 마스터 매칭 후 customer_for(canonical_pn)
            # 으로 재판정해야 4S/S 재질 접두사 품번까지 정확하다.
            "customer_hint": customer_for(base),
        })
    return rows


def group_by_order(rows):
    """수주 라인 → 발주번호 단위 헤더 + 라인 묶음.

    한 발주번호에 미진·엠제이티 품목이 섞이면 거래처별로 수주를
    분리한다 (수주번호에 -MJT 접미). 라인의 customer_hint 는 마스터
    매칭 후 customer_for() 로 갱신돼 있어야 정확하다.
    """
    out = {}
    for r in rows:
        cust = r.get("customer_hint") or "미진정밀"
        key = (r["so_number"], cust)
        h = out.setdefault(key, {
            "so_number": (r["so_number"] if cust == "미진정밀"
                          else f"{r['so_number']}-MJT"),
            "erp_order_no": r["so_number"],
            "so_date": r["so_date"],
            "customer": cust,
            "items": [],
        })
        h["items"].append(r)
    for h in out.values():
        h["total_amount"] = sum(i["amount"] for i in h["items"])
        h["due_date"] = next((i["due_date"] for i in h["items"]
                              if i["due_date"]), None)
    return list(out.values())
