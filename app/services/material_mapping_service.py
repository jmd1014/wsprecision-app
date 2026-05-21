"""
자재 매칭 도메인 서비스 (stub).

원칙:
- purchase_ledger.matched_material_id 매핑 책임.
- 자동 확정 금지 — 후보 추천 + 사용자 직접 선택.
- TODO: streamlit_app.py 의 매칭 화면 로직을 점진 이동.
"""
from typing import Optional


def confidence_label(score: int) -> str:
    """confidence_score (0~100) 를 사용자 표시 라벨로."""
    if score is None or score == 0:
        return "후보 없음"
    if score >= 100:
        return "🟢 완전일치 (100)"
    if score >= 80:
        return "🟢 높음 (80+)"
    if score >= 50:
        return "🟡 중간 (50+)"
    if score >= 30:
        return "🟠 낮음 (30+)"
    return "🔴 매우 낮음"


def normalize_item_key(item: str) -> str:
    """매입 ledger.item 의 정규화 키 (그룹핑용)."""
    if not item:
        return ""
    return item.strip().lower()


# TODO: 매핑 적용 함수 (purchase_ledger UPDATE)
# TODO: 일괄 매핑 (item_key 기준)
# TODO: 매핑 진행률 계산
