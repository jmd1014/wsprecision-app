"""
우성정밀 업무관리 시스템 — Streamlit 메인 엔트리
v0.1 (Stage 0) — 환경 구축 단계, DB 연결 전 placeholder
"""
import streamlit as st

st.set_page_config(
    page_title="우성정밀 업무관리",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── 헤더 ───
col1, col2 = st.columns([3, 1])
with col1:
    st.title("🏭 우성정밀 업무관리 시스템")
    st.caption("v0.1 · Stage 0 (환경 구축)")
with col2:
    st.metric("배포 상태", "✅ 활성")

st.divider()

# ─── 현재 상태 안내 ───
st.info(
    "🚧 **현재 단계: 환경 구축 완료, 데이터베이스 연결 대기 중**\n\n"
    "다음 단계: Supabase 가입 → 키 등록 → 마스터 데이터 import → 발주 모듈 활성화"
)

# ─── 사이드바 ───
with st.sidebar:
    st.header("📋 메뉴")
    st.caption("회색 항목은 다음 단계에서 활성화됩니다")
    st.button("📋 발주서 작성", disabled=True, use_container_width=True)
    st.button("📦 입출고 등록", disabled=True, use_container_width=True)
    st.button("🏭 생산 보고", disabled=True, use_container_width=True)
    st.button("📊 매출/재고 조회", disabled=True, use_container_width=True)
    st.button("💰 원가 분석", disabled=True, use_container_width=True)
    st.button("⚙️ 마스터 관리", disabled=True, use_container_width=True)

    st.divider()
    st.caption("🔧 시스템")
    st.button("📥 데이터 동기화", disabled=True, use_container_width=True)
    st.button("☁️ 백업 실행", disabled=True, use_container_width=True)

# ─── 메인 콘텐츠: 마스터 현황 미리보기 ───
st.subheader("📊 마스터 데이터 현황")
m1, m2, m3, m4, m5 = st.columns(5)
with m1: st.metric("제품", "834", "alias 166")
with m2: st.metric("자재", "308", "정규화 완료")
with m3: st.metric("BOM 매핑", "97.1%", "활성 매출 기준")
with m4: st.metric("거래처", "201", "카테고리 태깅")
with m5: st.metric("도면", "2,778", "리비전 추적")

st.divider()

# ─── 개발 로드맵 ───
st.subheader("🛣 개발 로드맵")
roadmap = [
    ("Stage 0", "환경 구축", "🟢 진행 중", "GitHub + Streamlit Cloud + Supabase 세팅"),
    ("Stage 1", "마스터 import + PMLib", "⚪ 대기", "Supabase에 마스터 5종 + 정규화 라이브러리 이전"),
    ("Stage 2", "Phase 1 발주 모듈 MVP", "⚪ 대기", "거래처 선택 → 품목 선택 → PDF 생성 → 슬랙 알림"),
    ("Stage 3", "시범 운영", "⚪ 대기", "김민수·염정원 2주 사용 + 피드백"),
    ("Stage 4", "Phase 2 생산·재고 통합", "⚪ 대기", "BOM 차감, 일일 보고, 사급/도급 분기"),
    ("Stage 5", "Phase 3 매출 대조", "⚪ 대기", "고객사 ERP 자동 파싱"),
    ("Stage 6", "Phase 4 대시보드", "⚪ 대기", "마진율, 미수, ABC 등급, 이상 탐지"),
]
for stage, name, status, desc in roadmap:
    with st.expander(f"{status} **{stage}** — {name}"):
        st.write(desc)

st.divider()
st.caption("© 2026 우성정밀 · 부산광역시 기장군 산단4로 71")
