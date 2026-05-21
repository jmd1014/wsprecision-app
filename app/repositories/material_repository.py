"""
Material repository (stub).

자재 마스터 + 매핑 관련 DB 접근.
TODO: streamlit_app.py 의 자재 검색/매칭 로직을 점진 이동.
"""
from typing import Optional
from app.db import supabase_rest as db


def search(keyword: str, limit: int = 20) -> list:
    """자재 검색 (자재명 / 재질 / 규격)."""
    if not keyword:
        return []
    kw = keyword.strip()
    return db.fetch("materials",
        "material_id,raw_name,material_type,spec,unit,main_supplier",
        f"or=(material_id.eq.{kw},raw_name.ilike.*{kw}*,"
        f"material_type.ilike.*{kw}*,spec.ilike.*{kw}*)"
        f"&order=raw_name.asc", limit=limit)


def get_unresolved_groups(min_count: int = 1, item_keyword: Optional[str] = None,
                          limit: int = 100) -> list:
    """미매핑 매입 그룹 (013 view 사용)."""
    parts = [f"purchase_count=gte.{int(min_count)}",
             "order=purchase_count.desc,total_amount.desc.nullslast"]
    if item_keyword:
        parts.append(f"item=ilike.*{item_keyword.strip()}*")
    return db.fetch("unresolved_purchase_materials",
        "item_key,item,vendor_normalized,category,purchase_count,"
        "avg_unit_price,last_purchase_date,total_amount,vendors_text",
        "&".join(parts), limit=limit)


def get_candidates_for_item(item_key: str, limit: int = 5) -> list:
    """미매핑 그룹에 대한 자재 후보."""
    if not item_key:
        return []
    safe_key = item_key.replace(",", "%2C")
    return db.fetch("material_mapping_candidates",
        "material_id,raw_name,material_type,spec,unit,"
        "main_supplier,confidence_score",
        f"item_key=eq.{safe_key}"
        f"&order=confidence_score.desc,material_id.asc",
        limit=limit)


def apply_mapping(item: str, material_id: str) -> bool:
    """item 키 같은 모든 미매핑 매입행을 material_id 로 매핑."""
    return db.update("purchase_ledger",
        f"item=eq.{item}&matched_material_id=is.null",
        {"matched_material_id": material_id,
         "mapping_status": "MANUAL"})


def get_match_progress() -> Optional[dict]:
    """매핑 진행률 (013 view 사용)."""
    return db.fetch_one("purchase_material_match_progress", "", "*")


# TODO: 자재 마스터 CRUD (add / update / archive)
# TODO: material_price_v 조회 헬퍼
