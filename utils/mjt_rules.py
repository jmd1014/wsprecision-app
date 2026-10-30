# -*- coding: utf-8 -*-
"""미진 ERP·엑셀로 들어오는 엠제이티 품목 판정 규칙 (핫픽스 3 r2).

미진 ERP 파서(mijin_erp_parser)·수주 파일 파서(so_parser)·수주 업로드 화면이 같이 쓴다.
pandas 없이 표준 라이브러리만 — so_parser 가 이 모듈만 import 한다.
"""
import re

# 우성정밀이 미진 ERP 를 통해 받지만 실제 거래처가 엠제이티인 품번
# (마감내역 sales_ledger 기준 판정 — 2024-08 이후 엠제이티 전용)
MJT_ONLY_PNS = {
    "SFB-16", "SFB-24", "SFB-46", "4PDVN-02", "4PDVN-03", "8PDVN-02",
    "12HFDVN-VM-03",
}

# 엠제이티 수주 거래처 표기 — vendors 22 정식명. 예전 customer_for 의 "㈜엠제이티"
# (U+327E)는 정식명이 아니라 vendor 조회·중복 검증이 어긋난다. 운영 수주·전표는 전부 이 표기
MJT_CUSTOMER = "(주)엠제이티"

_SUFFIX_RE = re.compile(r";\s*(PM|OUP|OP)\s*$", re.I)


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
            return MJT_CUSTOMER
    return "미진정밀"
