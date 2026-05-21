"""
진단/점검 도메인 서비스 (stub).

원칙:
- 자동 수정 금지 — 후보·작업 우선순위 리스트만 제공.
- 운영 흐름의 보조 도구.
- TODO: streamlit_app.py 의 진단/이상치 로직을 점진 이동.
"""
from typing import Optional


def completion_status_label(status: str) -> str:
    """active_bom_completion_v.completion_status 한국어 라벨."""
    return {
        "COMPLETE":   "🟢 완료",
        "UNVERIFIED": "🟡 미확인",
        "INCOMPLETE": "🟠 불완전",
        "NO_BOM":     "🔴 BOM 없음",
    }.get(status or "", "?")


def priority_label(p: int) -> str:
    """bom_cleanup_todo_v.priority 한국어 라벨."""
    return {
        1: "1️⃣ 긴급 (NO_BOM + 매출있음)",
        2: "2️⃣ 높음 (불완전 + 매출있음)",
        3: "3️⃣ 중간 (미확인 + 매출있음)",
        4: "4️⃣ 낮음 (NO_BOM)",
        5: "5️⃣ 낮음 (불완전)",
        6: "6️⃣ 낮음 (미확인)",
    }.get(p, "(미분류)")


# TODO: 단계 종료 기준 자동 점검 (master-stabilization-exit-criteria.md 기반)
# TODO: 무결성 점검 (orphan BOM / 휴면 BOM / 중복 BOM)
# TODO: 이상치 후보 (참고용 — 자동 적용 X)
