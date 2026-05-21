"""
원가/가격 도메인 서비스 (stub).

원칙:
- 가격/원가/마진 계산만 다룬다.
- BOM 구조는 bom_service 에서.
- 자동 overwrite 금지 — 후보 → 사용자 선택 → 반영.
- TODO: streamlit_app.py 의 원가 분석 로직을 점진 이동.
"""
from typing import Optional


def calc_margin(sale_price: float, cost: float) -> Optional[float]:
    """마진율(%) 계산. 판매가/원가 미정 시 None."""
    if not sale_price or sale_price <= 0:
        return None
    if cost is None:
        return None
    return round((sale_price - cost) / sale_price * 100, 1)


def classify_margin(margin_pct: Optional[float]) -> str:
    """마진율 분류 — 정비 우선순위 결정용."""
    if margin_pct is None:
        return "UNKNOWN"
    if margin_pct < 0:
        return "NEGATIVE"
    if margin_pct < 10:
        return "LOW"
    if margin_pct < 25:
        return "NORMAL"
    if margin_pct < 50:
        return "GOOD"
    return "VERY_HIGH"  # 비현실적 가능성


def cost_source_label(cost_source: str) -> str:
    """product_cost_full_v.cost_source 한국어 라벨."""
    return {
        "BOM_FULL":     "🟢 BOM_FULL (완전)",
        "BOM_PARTIAL":  "🟡 BOM_PARTIAL (부분)",
        "LEGACY_ONLY":  "🟠 LEGACY_ONLY (정적)",
        "NO_DATA":      "🔴 NO_DATA (부재)",
    }.get(cost_source or "", "?")


# TODO: 단가 fallback chain 계산 (mp.price_3m → 12m → legacy → 0)
# TODO: 원가 비교 (BOM 자동 vs legacy 스냅샷)
# TODO: 판매가 변동 이력 (sales_ledger 기반)
