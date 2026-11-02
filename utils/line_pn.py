# -*- coding: utf-8 -*-
"""수주·출고 라인의 표시 품번 — 거래처 품번 표시 묶음(PN 묶음, 2026-11-02).

엠제이티처럼 내부 제품은 하나(P0005 H11SDF-2C-10-01)인데 출하 품번이 다른 라인
(-RE-P·-RV-P)이 화면에서 똑같이 보이지 않게, 라인 단위 화면은 거래처 품번을 함께 보인다.
제품 단위 집계(간트 행 묶음·주간 계획·작업 지시·MES·공정·재고)에는 쓰지 않는다.

순서는 화면군별 고정(사용자 과정 모델 11-02):
- 거래처 앞 `customer_pn (pn)` — 수주 관리·납품 스케줄·영업 보고·발주 (기본값)
- 내부 앞 `pn (customer_pn)` — 출고 관리 전부(출고 등록·전표·현황·출고 리스트), internal_first=True
"""


def line_pn(row, *, full=True, internal_first=False) -> str:
    """라인의 표시 품번. 두 품번이 같거나 한쪽이 비면 한 번만(묶음 전과 같은 문자열).

    row: soi(customer_part_no, canonical_pn) 또는 si(customer_pn, pn) dict.
    full=False: 좁은 칸 — 다를 때 앞쪽 품번만(거래처 앞이면 거래처 품번).
    """
    row = row or {}
    cpn = str(row.get("customer_part_no") or row.get("customer_pn") or "").strip()
    pn = str(row.get("canonical_pn") or row.get("pn") or "").strip()
    if cpn and pn and cpn != pn:
        first, second = (pn, cpn) if internal_first else (cpn, pn)
        return f"{first} ({second})" if full else first
    return cpn or pn or "-"
