"""수주 비즈니스 로직"""
from app.repositories import sales_order_repository as so_repo


def filter_new_so_items(items: list[dict]) -> tuple[list[dict], list[str]]:
    """
    파싱된 items 중 DB에 이미 등록된 so_number를 제외.
    반환: (신규 items, 중복 so_numbers 정렬 리스트)
    """
    if not items:
        return [], []
    customer = items[0].get("customer", "")
    parsed = sorted({it["so_number"] for it in items if it.get("so_number")})
    existing = so_repo.find_existing_so_numbers(customer, parsed)
    new_items = [it for it in items if it.get("so_number") not in existing]
    dups = sorted(existing)
    return new_items, dups


def save_sales_order_group(header: dict, items: list[dict]) -> int:
    """수주 1건 저장. 호출자가 헤더·품목 준비 후 전달."""
    return so_repo.create_sales_order(header, items)


# pending_qty 계산은 repository에 위임 (테스트 편의)
calc_pending_qty = so_repo.calc_pending_qty
derive_item_status = so_repo.derive_item_status
