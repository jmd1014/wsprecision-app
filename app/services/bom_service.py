"""
BOM 도메인 서비스 (stub).

원칙:
- BOM 은 "구조와 수량" 만 다룬다.
- 가격/원가는 cost_service 에서.
- Streamlit UI 의존성 없음 — 순수 비즈니스 로직.
- TODO: streamlit_app.py 의 BOM 관련 로직을 점진 이동.
"""
from typing import Optional


def calc_per_pc(unit_price: float, qty_per_pc: float, shared_factor: float) -> float:
    """공통 공식: per_pc = unit_price × qty_per_pc / shared_factor.

    공정행 단가 계산 / BOM 자재 단가 환산 모두에 사용.
    """
    if not shared_factor:
        return 0.0
    return float(unit_price or 0) * float(qty_per_pc or 1) / float(shared_factor)


def is_material_row(process_type: Optional[str]) -> bool:
    """BOM 행이 자재 행인지 판정 (process_type 미설정 시 MATERIAL 로 간주)."""
    return (process_type or "MATERIAL") == "MATERIAL"


def is_process_row(process_type: Optional[str]) -> bool:
    """BOM 행이 공정행인지 판정."""
    return process_type is not None and process_type != "MATERIAL"


# TODO: BOM CRUD (자재행 추가, 공정행 추가, 검색)
# TODO: BOM 분기 복사 로직
# TODO: BOM 완성도 검증 (active_bom_completion_v 와 동기)
