"""발주 비즈니스 로직"""
import re
from app.repositories import purchase_repository as po_repo


def generate_po_number_safe() -> str:
    """DB 함수 호출로 동시성 안전 채번. 실패 시 Python fallback (가벼운 race risk)."""
    try:
        return po_repo.next_po_number()
    except Exception:
        # fallback: Python 측 채번 (운영 1인 환경에서는 충분)
        from datetime import date
        from app.db import supabase_rest as db
        today = date.today()
        prefix = f"PO-{today.strftime('%Y%m')}-"
        rows = db.fetch(
            "purchase_orders", "po_number",
            f"po_number=like.{prefix}*&order=po_number.desc&limit=1"
        )
        seq = int(rows[0]["po_number"].replace(prefix, "")) + 1 if rows else 1
        return f"{prefix}{seq:03d}"


PO_NUMBER_RE = re.compile(r'^PO-\d{6}-\d{3}$')


def is_valid_po_number(po_number: str) -> bool:
    """발주번호 형식 검증 (테스트용)"""
    return bool(PO_NUMBER_RE.match(po_number or ""))


def submit_purchase_order(header: dict, items: list[dict]) -> tuple[str, int]:
    """발주 생성 통합 흐름. 반환: (po_number, po_id)"""
    if not header.get("po_number"):
        header["po_number"] = generate_po_number_safe()
    po_id = po_repo.create_purchase_order(header, items)
    return header["po_number"], po_id
