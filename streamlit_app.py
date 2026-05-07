"""
우성정밀 업무관리 시스템 — Streamlit 메인
v0.3 (Stage 1 완료) — Supabase 활성, 활성/휴면 분리 표시
"""
import streamlit as st

st.set_page_config(
    page_title="우성정밀 업무관리",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# DB 연결 시도 (requests 기반)
try:
    from db import health_check, fetch, debug_check
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

    if st.button("🩺 진단 (secrets 점검)", use_container_width=True):
        with st.spinner("..."):
            info = debug_check()
        st.json(info)


# ─── 페이지 라우팅 ───

if page == "🏠 홈":
    if DB_AVAILABLE:
        try:
            hc = health_check()
            counts = hc.get("counts", {})

            st.subheader("📊 마스터 데이터 현황")
            m1, m2, m3, m4, m5 = st.columns(5)
            with m1: st.metric("제품 (전체)", counts.get("products", "-"))
            with m2: st.metric("자재", counts.get("materials", "-"))
            with m3: st.metric("BOM", counts.get("bom", "-"))
            with m4: st.metric("거래처", counts.get("vendors", "-"))
            with m5: st.metric("도면", counts.get("drawings", "-"))

            st.divider()
            st.subheader("🟢 활성 vs 🟡 휴면")
            a1, a2, a3 = st.columns(3)
            with a1: st.metric("활성 제품 (12M)", counts.get("active_products", "-"))
            with a2: st.metric("휴면 제품 (3년+)", counts.get("archived_products", "-"))
            with a3:
                # 매출 1억+ A등급 카운트
                try:
                    a_grade = fetch("product_stats", "product_id",
                                    "abc_grade=eq.A", limit=200)
                    st.metric("A등급 (매출 1억+)", len(a_grade))
                except: st.metric("A등급", "-")

            st.divider()
            st.subheader("📈 거래 데이터")
            l1, l2 = st.columns(2)
            with l1: st.metric("매출 ledger", counts.get("sales_ledger", "-"))
            with l2: st.metric("매입 ledger", counts.get("purchase_ledger", "-"))

            # 매출 TOP 10
            st.divider()
            st.subheader("🏆 활성 매출 TOP 10 (12개월)")
            try:
                top = fetch("product_stats",
                            "product_id,pn,sales_count_12m,total_sales_12m,abc_grade,activity_trend,margin_pct",
                            "total_sales_12m=gt.0&order=total_sales_12m.desc",
                            limit=10)
                if top:
                    import pandas as pd
                    df = pd.DataFrame(top)
                    df = df.rename(columns={
                        'pn': '품번', 'sales_count_12m': '매출건수',
                        'total_sales_12m': '매출액', 'abc_grade': 'ABC',
                        'activity_trend': '추세', 'margin_pct': '마진율%',
                    })
                    df['매출액'] = df['매출액'].apply(lambda x: f'{int(x):,}')
                    st.dataframe(df.drop(columns=['product_id']), use_container_width=True, hide_index=True)
            except Exception as e:
                st.caption(f"TOP10 로드 실패: {e}")

            # ERR 표시
            err_keys = [k for k, v in counts.items() if isinstance(v, str) and "ERR" in v]
            if err_keys:
                st.warning(f"⚠️ 일부 테이블 조회 실패: {', '.join(err_keys)}")

        except Exception as e:
            st.error(f"DB 연결 오류: {e}")
    else:
        st.warning("⚠️ Streamlit Cloud Secrets 등록이 완료되지 않았습니다.")
        st.info("**share.streamlit.io → Settings → Secrets**에 Supabase 키를 등록하면 활성화됩니다.")

    st.divider()

    # 로드맵
    st.divider()
    st.subheader("🛣 개발 로드맵")
    roadmap = [
        ("Stage 0", "환경 구축", "🟢 완료", "GitHub + Streamlit Cloud + Supabase 세팅"),
        ("Stage 1", "마스터 import + DB 활성", "🟢 완료", "5개 마스터 + 11,307 매출 + 5,332 매입 ledger 적재, 99.9% 매칭"),
        ("Stage 2", "Phase 1 발주 모듈 MVP", "🟡 진행 중", "거래처 선택 → 품목 선택 → PDF 생성 → 슬랙 알림"),
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
