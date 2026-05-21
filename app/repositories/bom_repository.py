"""
BOM repository (stub).

DB 접근만 담당. 비즈니스 로직 없음.
TODO: streamlit_app.py 의 BOM CRUD 를 점진 이동.
"""
from typing import Optional
from app.db import supabase_rest as db


def find_by_product(product_id: str) -> list:
    """제품의 모든 BOM 행 반환."""
    return db.fetch("bom",
        "bom_id,product_id,material_id,raw_material_name,"
        "qty_per_pc,shared_factor,process_type,unit_price,lot_label,"
        "verification_status,source,apply_start_date,apply_end_date",
        f"product_id=eq.{product_id}&order=bom_id.asc")


def insert_material_row(product_id: str, material_id: str,
                        material_name: str, qty_per_pc: float,
                        shared_factor: int) -> int:
    """BOM 자재행 추가. unit_price 는 입력하지 않음 (정책)."""
    return db.insert("bom", [{
        "product_id": product_id,
        "material_id": material_id,
        "raw_material_name": material_name,
        "qty_per_pc": qty_per_pc,
        "shared_factor": shared_factor,
        "process_type": "MATERIAL",
        "source": "MANUAL",
        "verification_status": "확인완료",
    }])


def insert_process_row(product_id: str, process_type: str,
                       process_name: str, unit_price: float,
                       qty_per_pc: float, lot_size: int,
                       lot_label: Optional[str] = None,
                       vendor_id: Optional[int] = None) -> int:
    """BOM 공정행 추가. LOT 단가 입력은 공정행만 허용."""
    record = {
        "product_id": product_id,
        "material_id": None,
        "raw_material_name": process_name or process_type,
        "process_type": process_type,
        "unit_price": unit_price,
        "qty_per_pc": qty_per_pc,
        "shared_factor": lot_size,
        "lot_label": lot_label,
        "source": "MANUAL",
        "verification_status": "확인완료",
    }
    if vendor_id is not None:
        record["process_vendor_id"] = vendor_id
    return db.insert("bom", [record])


# TODO: update_row (qty_per_pc / shared_factor / verification_status 만)
# TODO: delete_row (단건)
# TODO: copy_bom_to (분기 일괄 복사)
