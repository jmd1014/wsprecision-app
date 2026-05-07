"""
우성정밀 업무관리 시스템 — Streamlit 메인
v0.2 (Stage 1) — DB 연결 + 마스터 import 화면 활성화
"""
import streamlit as st

st.set_page_config(
    page_title="우성정밀 업무관리",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# DB 연결 시도
try:
    from db import get_client, health_check
    DB_AVAILABLE = True
except Exception as e:
    DB_AVAILABLE = False
    DB_ERROR = str(e)


# ─── 헤더 ───
col1, col2 = st.columns([3, 1])
with col1:
    st.title("🏭 우성정밀 업무관리 시스템")
    st.caption("v0.2 · Stage 1 (마스터 import 단계)")
with col2:
    if DB_AVAILABLE:
        st.success("✅ 시스템 활성")
    else:
        st.error("❌ DB 연결 대기")

st.divider()


# ─── 사이드바 ───
with st.sidebar:
    st.header("📋 메뉴")
    page = st.radio(
        "이동",
        ["🏠 홈", "⚙️ 마스터 관리", "📋 발주서 작성", "📦 입출고", "🏭 생산 보고", "📊 매출/재고"],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("🔧 시스템")
    if st.button("🔍 DB 상태 확인", use_container_width=True):
        if DB_AVAILABLE:
            with st.spinner("확인 중..."):
                hc = health_check()
            if hc["status"] == "OK":
                st.success("DB 연결 정상")
                st.json(hc["counts"])
            else:
                st.error(f"DB 오류: {hc.get('error', 'unknown')}")
        else:
            st.warning("Secrets 등록을 먼저 완료해주세요")


# ─── 페이지 라우팅 ───

if page == "🏠 홈":
    st.subheader("📊 마스터 데이터 현황")

    if DB_AVAILABLE:
        try:
            hc = health_check()
            counts = hc.get("counts", {})
            m1, m2, m3, m4, m5 = st.columns(5)
            with m1: st.metric("제품", counts.get("products", "-"))
            with m2: st.metric("자재", counts.get("materials", "-"))
            with m3: st.metric("BOM", counts.get("bom", "-"))
            with m4: st.metric("거래처", counts.get("vendors", "-"))
            with m5: st.metric("도면", counts.get("drawings", "-"))

            st.divider()
            st.subheader("📈 거래 데이터")
            l1, l2 = st.columns(2)
            with l1: st.metric("매출 ledger", counts.get("sales_ledger", "-"))
            with l2: st.metric("매입 ledger", counts.get("purchase_ledger", "-"))

            if all(isinstance(v, int) and v == 0 for v in [counts.get("products", 0), counts.get("vendors", 0)]):
                st.warning("⚠️ 마스터 테이블이 비어있습니다. **'⚙️ 마스터 관리'** 메뉴에서 import 실행해주세요.")
        except Exception as e:
            st.error(f"DB 연결 오류: {e}")
            st.info("좌측 사이드바 '🔍 DB 상태 확인' 버튼을 눌러 자세한 상태를 확인하세요.")
    else:
        st.warning("⚠️ Streamlit Cloud Secrets 등록이 완료되지 않았습니다.")
        st.info("**share.streamlit.io → Settings → Secrets**에 Supabase 키를 등록하면 활성화됩니다.")

    st.divider()

    # 로드맵
    st.subheader("🛣 개발 로드맵")
    roadmap = [
        ("Stage 0", "환경 구축", "🟢 완료", "GitHub + Streamlit Cloud + Supabase 세팅"),
        ("Stage 1", "마스터 import + DB 활성", "🟡 진행 중", "5개 마스터 + 거래 ledger를 Supabase로 이전"),
        ("Stage 2", "Phase 1 발주 모듈 MVP", "⚪ 대기", "거래처 선택 → 품목 선택 → PDF 생성 → 슬랙 알림"),
        ("Stage 3", "시범 운영", "⚪ 대기", "김민수·염정원 2주 사용 + 피드백"),
        ("Stage 4", "Phase 2 생산·재고 통합", "⚪ 대기", "BOM 차감, 일일 보고, 사급/도급 분기"),
        ("Stage 5", "Phase 3 매출 대조", "⚪ 대기", "고객사 ERP 자동 파싱"),
        ("Stage 6", "Phase 4 대시보드", "⚪ 대기", "마진율, 미수, ABC 등급, 이상 탐지"),
    ]
    for stage, name, status, desc in roadmap:
        with st.expander(f"{status} **{stage}** — {name}"):
            st.write(desc)


elif page == "⚙️ 마스터 관리":
    st.subheader("⚙️ 마스터 데이터 관리")

    if not DB_AVAILABLE:
        st.error("DB 연결이 활성화되지 않았습니다. Secrets 등록을 먼저 확인해주세요.")
        st.stop()

    st.markdown("""
    ### 마스터 import 안내

    이 화면에서는 로컬 엑셀 파일을 Supabase로 일괄 import 합니다.

    **import 대상:**
    1. `product_master_v11.xlsx` → products (834건, 정적 컬럼만)
    2. `거래처관리_v2.xlsx` → vendors (201건)
    3. `material_master_v3.xlsx` → materials (308건)
    4. `BOM_v8.xlsx` → bom
    5. `도면관리.xlsx` → drawings (2,777건)
    6. `매출내역_우성정밀.xlsx` → sales_ledger (11,308건)
    7. `2024/2025/2026 매입내역` → purchase_ledger (5,332건)

    ⚠️ **이 import는 클라우드 환경에서 직접 실행 불가** (로컬 엑셀 파일 접근 필요).
    클로드가 Stage 1 작업으로 별도 환경에서 실행 후, DB에 자료가 채워진 상태로 활성화됩니다.
    """)

    st.info("📌 **현재 상태**: import 스크립트 작성 완료, DB 연결 검증 후 클로드가 실행 예정.")

    # DB 상태 표시
    st.divider()
    st.subheader("현재 DB 상태")
    if st.button("🔍 새로고침", type="primary"):
        with st.spinner("..."):
            hc = health_check()
        if hc["status"] == "OK":
            st.success("DB 연결 OK")
            for table, cnt in hc["counts"].items():
                st.write(f"- **{table}**: {cnt}건")
        else:
            st.error(hc.get("error"))


elif page == "📋 발주서 작성":
    st.subheader("📋 발주서 작성")
    st.info("🚧 Stage 2에서 활성화 예정 — 마스터 import 완료 후")


elif page == "📦 입출고":
    st.subheader("📦 입출고 등록")
    st.info("🚧 Stage 4에서 활성화 예정")


elif page == "🏭 생산 보고":
    st.subheader("🏭 일일 생산 보고")
    st.info("🚧 Stage 4에서 활성화 예정 (모바일 입력 우선 최적화)")


elif page == "📊 매출/재고":
    st.subheader("📊 매출/재고 조회")
    st.info("🚧 Stage 5에서 활성화 예정")


st.divider()
st.caption("© 2026 우성정밀 · 부산광역시 기장군 산단4로 71")
