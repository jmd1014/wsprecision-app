# -*- coding: utf-8 -*-
"""수주·출고 라인의 표시 품번 — 거래처 품번 표시 묶음(PN 묶음 r2, 2026-11-02).

엠제이티 P0005 처럼 사내 생산·재고는 하나인데 거래처가 다른 품번(-RE-P·-RV-P)으로
따로 주문·납품받는 '출하 품번'(customer_part_mapping.kind='variant')만 라인에 병기한다.
미진 ERP 코드(4S/S/6 접두·;PM 접미 등) 같은 '별칭'(kind='alias', 기본)은 지금처럼 내부 품번
하나만 — 정규식 정규화는 쓰지 않는다(사용자 결정 11-02). variant 0건이면 묶음 전과 바이트 동일.
제품 단위 집계(간트 행 묶음·주간 계획·작업 지시·MES·공정·재고)에는 쓰지 않는다.

순서는 화면군별 고정(사용자 과정 모델 11-02):
- 거래처 앞 `customer_pn (pn)` — 수주 관리·납품 스케줄·발주 (기본값)
- 내부 앞 `pn (customer_pn)` — 출고 관리 전부·출고 리스트·일일 결산 품번 열, internal_first=True
"""


def load_variants(fetch):
    """kind='variant' 매핑 → {(product_id, 거래처 품번 upper)}. 화면 렌더당 1회(db.fetch 캐시).

    행의 kind 도 다시 확인한다 — 필터를 무시하는 목·옛 스키마 응답에서 별칭이 variant 로 새지 않게.
    """
    rows = fetch("customer_part_mapping", "product_id,customer_part_no,kind",
                 "kind=eq.variant") or []
    return {(r.get("product_id"), str(r.get("customer_part_no") or "").strip().upper())
            for r in rows
            if r.get("kind") == "variant" and r.get("product_id")
            and str(r.get("customer_part_no") or "").strip()}


def line_pn(row, variants, *, internal_first=False, full=True) -> str:
    """라인의 표시 품번. 거래처 품번이 그 제품의 출하 품번(variant)이고 내부 품번과 다를 때만 병기.

    그 외(별칭·빈값·같음·product_id 없음)는 `pn or cpn or "-"` **원문** — 묶음 전 표시와 같은 문자열
    (비교만 strip·upper, PN r2 M1).
    row: soi(customer_part_no, canonical_pn, product_id) 또는 si(customer_pn, pn, product_id) dict.
    full=False: 좁은 칸 — 병기 대상이면 앞쪽 품번만.
    """
    row = row or {}
    raw_cpn = row.get("customer_part_no") or row.get("customer_pn")
    raw_pn = row.get("canonical_pn") or row.get("pn")
    cpn = str(raw_cpn or "").strip()
    pn = str(raw_pn or "").strip()
    pid = row.get("product_id") or ""
    if (cpn and pn and cpn.upper() != pn.upper()
            and (pid, cpn.upper()) in (variants or ())):
        a, b = (pn, cpn) if internal_first else (cpn, pn)
        return f"{a} ({b})" if full else a
    return raw_pn or raw_cpn or "-"
