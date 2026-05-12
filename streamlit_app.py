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
        ["🏠 홈", "⚙️ 마스터 관리", "📥 수주", "📊 생산 계획", "📋 발주서 작성", "📦 입출고", "🏭 생산 보고", "📊 매출/재고"],
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
        st.error("DB 연결이 활성화되지 않았습니다."); st.stop()

    import db as _db
    import pandas as pd

    tab1, tab_mat, tab_bom, tab2 = st.tabs([
        "🏢 거래처 편집", "📦 자재 편집", "🔗 BOM 편집", "📊 DB 현황"
    ])

    # ─── Tab 1: 거래처 편집 ───
    with tab1:
        VENDOR_GROUPS = [
            "SALES_MIJIN", "SALES_HDX", "SALES_DIC", "SALES_OTHER",
            "MAT_STS", "MAT_CARBON", "MAT_FORGING", "MAT_CASTING", "MAT_OTHER",
            "MAT_CONSUMABLES",
            "OUTSOURCE", "HEAT_TREAT", "SURFACE", "TOOL",
            "INDIRECT_PROFESSIONAL", "INDIRECT_TELECOM", "INDIRECT_LEGAL",
            "INDIRECT_UTILITY", "INDIRECT_FINANCE", "INDIRECT_LOGISTICS",
            "INDIRECT_FACILITY", "INDIRECT_CONSUMABLES", "INDIRECT_OTHER",
        ]

        # ── 필터 영역 (다중 컬럼) ──
        with st.expander("🔍 상세 필터 / 정렬", expanded=True):
            r1c1, r1c2, r1c3, r1c4 = st.columns(4)
            with r1c1:
                f_name = st.text_input("거래처명", placeholder="예: 명진, 미진, 두리")
            with r1c2:
                f_biz = st.text_input("사업자번호", placeholder="예: 606-02")
            with r1c3:
                f_group = st.selectbox("그룹", ["전체"] + VENDOR_GROUPS)
            with r1c4:
                f_type = st.selectbox("거래 구분", ["전체", "매입", "매출", "혼합"])

            r2c1, r2c2, r2c3, r2c4 = st.columns(4)
            with r2c1:
                f_btype = st.text_input("업태", placeholder="예: 제조")
            with r2c2:
                f_bitem = st.text_input("종목", placeholder="예: 환봉")
            with r2c3:
                f_inuse = st.selectbox("사용여부", ["전체", "사용", "미사용"])
            with r2c4:
                f_sort = st.selectbox("정렬", [
                    "그룹 → 이름", "이름 (가나다)", "최근 등록순", "ID 순"
                ])

            r3c1, r3c2 = st.columns([3, 1])
            with r3c2:
                f_limit = st.number_input("표시 행수", 20, 500, 100, 20)

        # 정렬 매핑
        sort_map = {
            "그룹 → 이름": "vendor_group.asc,name.asc",
            "이름 (가나다)": "name.asc",
            "최근 등록순": "vendor_id.desc",
            "ID 순": "vendor_id.asc",
        }

        # ── 쿼리 빌드 ──
        fq_parts = [f"order={sort_map[f_sort]}"]
        if f_name: fq_parts.append(f"name=ilike.*{f_name}*")
        if f_biz: fq_parts.append(f"business_no=ilike.*{f_biz}*")
        if f_group != "전체": fq_parts.append(f"vendor_group=eq.{f_group}")
        if f_type != "전체": fq_parts.append(f"trade_type=eq.{f_type}")
        if f_btype: fq_parts.append(f"business_type=ilike.*{f_btype}*")
        if f_bitem: fq_parts.append(f"business_item=ilike.*{f_bitem}*")
        if f_inuse == "사용": fq_parts.append("in_use=eq.true")
        elif f_inuse == "미사용": fq_parts.append("in_use=eq.false")
        fq = "&".join(fq_parts)

        try:
            rows = fetch("vendors",
                         "vendor_id,name,vendor_group,category,trade_type,business_no,ceo_name,phone,address,business_type,business_item,payment_terms,in_use",
                         fq, limit=f_limit)
        except Exception as e:
            st.error(f"조회 실패: {e}"); rows = []

        st.caption(f"검색 결과: **{len(rows)}건** (필터 적용)")

        # ── 신규 거래처 등록 ──
        with st.expander("➕ 신규 거래처 등록"):
            ec1, ec2 = st.columns(2)
            with ec1:
                new_name = st.text_input("거래처명 *", key="m_new_name", placeholder="(주)○○산업")
                new_biz = st.text_input("사업자번호", key="m_new_biz", placeholder="000-00-00000")
                new_ceo = st.text_input("대표자명", key="m_new_ceo")
                new_phone = st.text_input("전화", key="m_new_phone")
                new_fax = st.text_input("팩스", key="m_new_fax")
            with ec2:
                new_group = st.selectbox("그룹 *", ["선택"] + VENDOR_GROUPS, key="m_new_group")
                new_type = st.selectbox("거래 구분", ["매입", "매출", "혼합"], key="m_new_type")
                new_pay = st.text_input("결제조건", key="m_new_pay", value="말일 마감 60일 현금")
                new_address = st.text_input("주소", key="m_new_addr")
                new_email = st.text_input("이메일", key="m_new_email")
            new_contact = st.text_input("담당자", key="m_new_contact")
            new_btype = st.text_input("업태", key="m_new_btype")
            new_bitem = st.text_input("종목", key="m_new_bitem")
            new_memo = st.text_input("메모", key="m_new_memo")

            # 마지막 등록 결과 표시 (rerun 후에도 보존)
            if "m_last_registered" in st.session_state:
                lr = st.session_state.m_last_registered
                st.success(f"✅ **{lr['name']}** 등록 완료 (ID: {lr['id']}, 그룹: {lr['group']})")
                st.caption("💡 위 표 새로고침하려면 필터를 한 번 변경하거나 페이지를 다시 여세요.")

            if st.button("💾 신규 등록", type="primary", key="m_new_btn"):
                if not new_name or new_group == "선택":
                    st.error("거래처명과 그룹은 필수입니다.")
                else:
                    import re as _re
                    # 거래처명 자동 정리
                    cleaned = (new_name.replace('（','(').replace('）',')').replace('㈜','(주)'))
                    cleaned = _re.sub(r'\)\s+', ')', cleaned)
                    cleaned = _re.sub(r'\s+\(', '(', cleaned)
                    cleaned = _re.sub(r'\s+', ' ', cleaned).strip()
                    norm = _re.sub(r'\s+', '', cleaned)
                    try:
                        dup = fetch("vendors", "vendor_id,name", f"normalized_name=eq.{norm}", limit=1)
                    except: dup = []
                    if dup:
                        st.error(f"⚠️ 이미 등록됨: {dup[0]['name']} (ID={dup[0]['vendor_id']})")
                    else:
                        try:
                            _db.insert("vendors", [{
                                "name": cleaned, "normalized_name": norm,
                                "business_no": new_biz or None,
                                "vendor_group": new_group,
                                "trade_type": new_type,
                                "ceo_name": new_ceo or None,
                                "phone": new_phone or None,
                                "fax": new_fax or None,
                                "address": new_address or None,
                                "email": new_email or None,
                                "contact_person": new_contact or None,
                                "business_type": new_btype or None,
                                "business_item": new_bitem or None,
                                "payment_terms": new_pay,
                                "memo": new_memo or None,
                                "verification_status": "수기등록",
                                "in_use": True,
                            }])
                            # 새로 등록된 vendor_id 조회
                            new_v = fetch("vendors", "vendor_id", f"normalized_name=eq.{norm}", limit=1)
                            new_id = new_v[0]["vendor_id"] if new_v else "?"
                            # 메시지 보존
                            st.session_state.m_last_registered = {
                                "name": cleaned, "id": new_id, "group": new_group
                            }
                            st.toast(f"✅ '{cleaned}' 등록 완료!", icon="🎉")
                            st.balloons()
                            st.rerun()
                        except Exception as e:
                            st.error(f"등록 실패: {e}")

        # ── 표 표시 + 인라인 편집 ──
        if not rows:
            st.info("필터 조건에 맞는 거래처 없음. 위에서 신규 등록하세요.")
        else:
            df = pd.DataFrame(rows)
            edited = st.data_editor(
                df,
                column_config={
                    "vendor_id": st.column_config.NumberColumn("ID", width="small", disabled=True),
                    "name": st.column_config.TextColumn("거래처명", width="medium", disabled=True),
                    "vendor_group": st.column_config.SelectboxColumn(
                        "그룹", options=[None] + VENDOR_GROUPS, width="medium"
                    ),
                    "category": st.column_config.TextColumn("카테고리(자동)", disabled=True, width="small"),
                    "trade_type": st.column_config.TextColumn("구분", width="small", disabled=True),
                    "business_no": st.column_config.TextColumn("사업자번호", disabled=True, width="small"),
                    "ceo_name": st.column_config.TextColumn("대표자"),
                    "phone": st.column_config.TextColumn("전화"),
                    "address": st.column_config.TextColumn("주소", width="medium"),
                    "business_type": st.column_config.TextColumn("업태", disabled=True),
                    "business_item": st.column_config.TextColumn("종목", disabled=True),
                    "payment_terms": st.column_config.TextColumn("결제조건"),
                    "in_use": st.column_config.CheckboxColumn("사용", width="small"),
                },
                hide_index=True,
                use_container_width=True,
                key="vendor_editor",
                num_rows="fixed",
            )

            if st.button("💾 변경 저장", type="primary"):
                changed = 0
                editable_fields = ["vendor_group", "ceo_name", "phone", "address", "payment_terms", "in_use"]
                for orig, new in zip(rows, edited.to_dict("records")):
                    updates = {}
                    for f in editable_fields:
                        if orig.get(f) != new.get(f):
                            updates[f] = new.get(f)
                    if updates:
                        if _db.update("vendors", f"vendor_id=eq.{orig['vendor_id']}", updates):
                            changed += 1
                if changed:
                    st.success(f"✅ {changed}건 업데이트")
                    st.rerun()
                else:
                    st.info("변경 사항 없음")

    # ─── Tab: 자재 편집 ───
    with tab_mat:
        st.caption("📌 모든 자재 단위는 **EA**로 통일됨 (수주·발주·생산·출고 일관성)")
        mc1, mc2, mc3 = st.columns([2, 2, 1])
        with mc1:
            mat_q = st.text_input("자재 검색", placeholder="예: STS304, 환봉, 8HFDV")
        with mc2:
            mat_type_q = st.text_input("재질 필터", placeholder="예: SUS304")
        with mc3:
            mat_limit = st.number_input("행수", 20, 500, 100, 20)

        mfq = ["order=material_id.asc"]
        if mat_q: mfq.append(f"or=(raw_name.ilike.*{mat_q}*,material_id.ilike.*{mat_q}*)")
        if mat_type_q: mfq.append(f"material_type=ilike.*{mat_type_q}*")
        try:
            mrows = fetch("materials",
                "material_id,raw_name,material_type,spec,unit,stock_qty,main_supplier,procurement_type",
                "&".join(mfq), limit=mat_limit)
        except Exception as e: st.error(e); mrows = []

        st.caption(f"검색 결과: **{len(mrows)}건**")

        if mrows:
            mdf = pd.DataFrame(mrows)
            mediated = st.data_editor(
                mdf,
                column_config={
                    "material_id": st.column_config.TextColumn("자재ID", disabled=True, width="small"),
                    "raw_name": st.column_config.TextColumn("자재명", width="large"),
                    "material_type": st.column_config.TextColumn("재질"),
                    "spec": st.column_config.TextColumn("규격"),
                    "unit": st.column_config.TextColumn("단위", disabled=True, width="small"),
                    "stock_qty": st.column_config.NumberColumn("재고 (EA)", format="%.2f"),
                    "main_supplier": st.column_config.TextColumn("주공급사", disabled=True, width="medium"),
                    "procurement_type": st.column_config.TextColumn("조달유형", width="small"),
                },
                hide_index=True, use_container_width=True,
                num_rows="fixed", key="mat_editor",
            )
            if st.button("💾 자재 변경 저장", type="primary"):
                chg = 0
                for orig, new in zip(mrows, mediated.to_dict("records")):
                    upd = {k: new[k] for k in ("raw_name","material_type","spec","stock_qty","procurement_type")
                           if orig.get(k) != new.get(k)}
                    if upd:
                        if _db.update("materials", f"material_id=eq.{orig['material_id']}", upd):
                            chg += 1
                if chg: st.success(f"✅ {chg}건 update"); st.rerun()
                else: st.info("변경 사항 없음")

    # ─── Tab: BOM 편집 ───
    with tab_bom:
        st.caption("📌 BOM = 제품-자재 매핑. **qty_per_pc**는 제품 1 EA당 자재 EA 수. "
                   "**shared_factor**는 1 자재에서 여러 제품 분할 가공 시 (예: 환봉 1개 → 3 EA → shared_factor=3)")
        bc1, bc2 = st.columns([3, 1])
        with bc1:
            bom_q = st.text_input("제품 또는 자재 검색", placeholder="예: 8HFDV, M001")
        with bc2:
            bom_limit = st.number_input("행수", 20, 500, 100, 20, key="bom_lim")

        bfq = ["order=product_id.asc,bom_id.asc"]
        if bom_q:
            bfq.append(f"or=(product_id.ilike.*{bom_q}*,material_id.ilike.*{bom_q}*,raw_material_name.ilike.*{bom_q}*)")
        try:
            brows = fetch("bom",
                "bom_id,product_id,material_id,raw_material_name,qty_per_pc,shared_factor,source,verification_status",
                "&".join(bfq), limit=bom_limit)
        except Exception as e: st.error(e); brows = []

        st.caption(f"검색 결과: **{len(brows)}건**")

        if brows:
            bdf = pd.DataFrame(brows)
            bedited = st.data_editor(
                bdf,
                column_config={
                    "bom_id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
                    "product_id": st.column_config.TextColumn("제품ID", disabled=True, width="small"),
                    "material_id": st.column_config.TextColumn("자재ID", disabled=True, width="small"),
                    "raw_material_name": st.column_config.TextColumn("자재명", width="large", disabled=True),
                    "qty_per_pc": st.column_config.NumberColumn("자재/PC (EA)", format="%.3f"),
                    "shared_factor": st.column_config.NumberColumn("1자재→N제품", format="%.0f"),
                    "source": st.column_config.TextColumn("출처", disabled=True, width="small"),
                    "verification_status": st.column_config.SelectboxColumn("검증",
                        options=["AUTO-추정", "AUTO-매입추정", "AUTO-명진추정", "확인완료", "재검토"],
                        width="small"),
                },
                hide_index=True, use_container_width=True,
                num_rows="fixed", key="bom_editor",
            )
            if st.button("💾 BOM 변경 저장", type="primary"):
                chg = 0
                for orig, new in zip(brows, bedited.to_dict("records")):
                    upd = {k: new[k] for k in ("qty_per_pc","shared_factor","verification_status")
                           if orig.get(k) != new.get(k)}
                    if upd:
                        if _db.update("bom", f"bom_id=eq.{orig['bom_id']}", upd):
                            chg += 1
                if chg: st.success(f"✅ {chg}건 update"); st.rerun()
                else: st.info("변경 사항 없음")

            st.divider()
            st.markdown("##### ➕ 신규 BOM 추가")
            nc1, nc2, nc3, nc4 = st.columns([2, 2, 1, 1])
            with nc1:
                new_pid = st.text_input("제품 ID *", placeholder="예: P0001", key="bom_new_pid")
            with nc2:
                new_mid = st.text_input("자재 ID *", placeholder="예: M001", key="bom_new_mid")
            with nc3:
                new_qpc = st.number_input("qty/PC (EA)", min_value=0.0, value=1.0, step=0.1, key="bom_new_qpc")
            with nc4:
                new_sf = st.number_input("shared_factor", min_value=1, value=1, step=1, key="bom_new_sf")
            if st.button("➕ BOM 추가", key="bom_new_btn"):
                if not new_pid or not new_mid:
                    st.error("제품 ID와 자재 ID는 필수입니다.")
                else:
                    # 자재명 자동 조회
                    mrow = _db.fetch_one("materials", f"material_id=eq.{new_mid}", "raw_name")
                    try:
                        _db.insert("bom", [{
                            "product_id": new_pid, "material_id": new_mid,
                            "raw_material_name": mrow.get("raw_name") if mrow else None,
                            "qty_per_pc": new_qpc, "shared_factor": new_sf,
                            "source": "MANUAL", "verification_status": "확인완료",
                        }])
                        st.success(f"✅ BOM 추가: {new_pid} ↔ {new_mid}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"추가 실패: {e}")

    # ─── Tab 2: DB 현황 ───
    with tab2:
        if st.button("🔍 새로고침", type="primary"):
            with st.spinner("..."):
                hc = health_check()
            if hc["status"] == "OK":
                st.success("DB 연결 OK")
                for table, cnt in hc["counts"].items():
                    st.write(f"- **{table}**: {cnt}건")
            else:
                st.error(hc.get("error"))


elif page == "📥 수주":
    st.subheader("📥 수주 관리")
    if not DB_AVAILABLE: st.error("DB 연결 필요"); st.stop()

    from datetime import date as _date, timedelta as _td
    from utils.so_parser import (parse_hdx_excel, parse_mijin_excel, parse_mjt_pdf,
                                  group_by_so_number, match_canonical_pn)
    import db as _db
    import pandas as pd
    import re as _re

    tab_input, tab_list = st.tabs(["📤 새 수주 입력", "📋 수주 목록"])

    # ════════ TAB 1: 새 수주 입력 ════════
    with tab_input:
        mode = st.radio("입력 방식", ["📁 파일 업로드 자동 파싱", "✏️ 수기 입력"],
                        horizontal=True)

        if mode == "📁 파일 업로드 자동 파싱":
            st.caption("📌 양식은 파일을 보고 자동으로 인식합니다 (HDX / 미진정밀 / 엠제이티 PDF)")
            uploaded = st.file_uploader("파일 선택",
                type=['xlsx','xls','pdf'],
                help="여러 거래처 양식 자동 인식")

            if uploaded:
                file_bytes = uploaded.read()
                filename = uploaded.name
                from utils.so_parser import detect_so_format, parse_so_auto
                with st.spinner("양식 인식 + 파싱 중..."):
                    try:
                        fmt, items = parse_so_auto(file_bytes, filename)
                    except Exception as e:
                        st.error(f"파싱 실패: {e}"); fmt = "ERR"; items = []

                fmt_labels = {
                    "HDX": "🟢 HDX (ERP 엑셀)",
                    "MIJIN": "🟢 미진정밀 (외주발주품목조회)",
                    "MJT_PDF": "🟢 (주)엠제이티 (PDF 발주서)",
                    "UNKNOWN_PDF": "⚠️ 알 수 없는 PDF — 수동 파서 선택 필요",
                    "UNKNOWN_EXCEL": "⚠️ 알 수 없는 엑셀 양식 — 수동 파서 선택 필요",
                    "UNKNOWN": "❌ 인식 실패",
                }
                st.info(f"**양식 인식**: {fmt_labels.get(fmt, fmt)}")

                # 인식 실패 → 수동 선택 fallback
                if fmt.startswith("UNKNOWN") or not items:
                    manual = st.selectbox("수동 선택 (자동 인식 실패 시)",
                        ["선택 안 함", "HDX (엑셀)", "미진정밀 (엑셀)", "엠제이티 (PDF)"])
                    if manual == "HDX (엑셀)":
                        try: items = parse_hdx_excel(file_bytes, filename)
                        except Exception as e: st.error(e); items = []
                    elif manual == "미진정밀 (엑셀)":
                        try: items = parse_mijin_excel(file_bytes, filename)
                        except Exception as e: st.error(e); items = []
                    elif manual == "엠제이티 (PDF)":
                        try: items = parse_mjt_pdf(file_bytes, filename)
                        except Exception as e: st.error(e); items = []

                if items:
                    st.success(f"✅ {len(items)}개 품목 파싱 완료")

                    # ── 중복 수주번호 검증 (DB 기존 데이터 vs 파싱 결과) ──
                    customer_name = items[0]["customer"]
                    parsed_so_set = sorted({it["so_number"] for it in items if it.get("so_number")})
                    if parsed_so_set:
                        existing_filter = (
                            f"customer=eq.{customer_name}&"
                            f"so_number=in.({','.join(parsed_so_set)})"
                        )
                        try:
                            existing = fetch("sales_orders", "so_number", existing_filter, limit=500)
                            existing_set = {e["so_number"] for e in existing}
                        except Exception:
                            existing_set = set()
                    else:
                        existing_set = set()

                    new_items = [it for it in items if it.get("so_number") not in existing_set]
                    dup_items = [it for it in items if it.get("so_number") in existing_set]
                    dup_so_nums = sorted({it["so_number"] for it in dup_items})

                    if dup_so_nums:
                        st.warning(
                            f"⚠️ 이미 등록된 수주 **{len(dup_so_nums)}건** 자동 제외:\n\n"
                            + "\n".join(f"- `{s}`" for s in dup_so_nums[:10])
                            + (f"\n... 외 {len(dup_so_nums)-10}건" if len(dup_so_nums) > 10 else "")
                        )
                    if not new_items:
                        st.error("모든 수주가 이미 등록되어 있습니다. 업로드 불필요.")
                        st.stop()
                    items = new_items  # 이후 매칭/저장은 신규만

                    # 우성정밀 품번 매칭
                    products = fetch("products", "product_id,pn,alias_list", limit=1500)
                    cm = {}
                    def _mk(s):
                        if not s: return ""
                        s = str(s).upper()
                        s = _re.sub(r'\([^)]*\)', '', s)
                        s = _re.sub(r'[\s\-_·,\.]+', '', s)
                        return s
                    for p in products:
                        cm[_mk(p['pn'])] = (p['pn'], p['product_id'])
                        if p.get('alias_list'):
                            for a in str(p['alias_list']).split(','):
                                a = a.strip()
                                if a: cm.setdefault(_mk(a), (p['pn'], p['product_id']))

                    def _strip_prefix(s):
                        """4S/S 접두어 제거 (PMLib _getBasePn)"""
                        if not s: return ""
                        p = str(s).upper().strip()
                        if p.startswith('4S') and len(p) > 2 and (p[2].isalnum()):
                            return p[2:]
                        if p.startswith('S') and len(p) > 1 and (p[1].isalnum()):
                            excluded = ('SP-','SDF','SUS','SODV','SFB','SCM','SKD','SKH',
                                        'S45','S20','S30','S304','S316','S630')
                            if not any(p.startswith(e) for e in excluded):
                                return p[1:]
                        return p

                    matched_count = 0
                    for it in items:
                        pn_hint = it.get("canonical_pn_hint") or it.get("customer_part_no") or ""
                        base = pn_hint.split(';')[0].strip() if ';' in pn_hint else pn_hint
                        # 시도 후보 4종
                        candidates = [
                            pn_hint,
                            base,
                            _strip_prefix(pn_hint),
                            _strip_prefix(base),
                        ]
                        m = None
                        for c in candidates:
                            if not c: continue
                            m = cm.get(_mk(c))
                            if m: break
                        if m:
                            it["matched_pn"] = m[0]
                            it["matched_pid"] = m[1]
                            matched_count += 1
                        else:
                            it["matched_pn"] = None
                            it["matched_pid"] = None

                    st.info(f"🎯 우성정밀 품번 매칭: **{matched_count}/{len(items)}** "
                            f"({100*matched_count/len(items):.1f}%)")

                    # 미리보기
                    df = pd.DataFrame([{
                        "수주번호": it.get("so_number"),
                        "라인": it.get("line_no"),
                        "거래처 자재": it.get("customer_part_no"),
                        "거래처 품명": (it.get("customer_item_name") or "")[:30],
                        "✅ 우성정밀 품번": it.get("matched_pn") or "❌ 미매칭",
                        "수량": int(it.get("qty") or 0),
                        "단가": int(it.get("unit_price") or 0),
                        "금액": int(it.get("amount") or 0),
                        "납기": it.get("due_date"),
                    } for it in items])
                    st.dataframe(df, use_container_width=True, hide_index=True,
                        column_config={
                            "수량": st.column_config.NumberColumn(format="%d"),
                            "단가": st.column_config.NumberColumn(format="₩%d"),
                            "금액": st.column_config.NumberColumn(format="₩%d"),
                        })

                    if matched_count < len(items):
                        st.warning(f"⚠️ 매칭 안 된 {len(items) - matched_count}개 품목은 customer_part_no만 저장됩니다. 추후 마스터 관리에서 매핑 가능.")

                    # DB 저장
                    if st.button("💾 수주 DB 저장", type="primary", use_container_width=True):
                        groups = group_by_so_number(items)

                        # 거래처 vendor_id 조회
                        cust_name = items[0]["customer"]
                        v = fetch("vendors", "vendor_id",
                                  f"name=ilike.*{cust_name}*&limit=1", limit=1)
                        vendor_id = v[0]["vendor_id"] if v else None

                        saved_so = 0; saved_items = 0
                        for g in groups:
                            try:
                                # 헤더 INSERT
                                header = g["header"]
                                header_payload = {
                                    "so_number": header["so_number"],
                                    "customer": header["customer"],
                                    "vendor_id": vendor_id,
                                    "so_date": header["so_date"].isoformat() if header["so_date"] else None,
                                    "due_date": header["due_date"].isoformat() if header["due_date"] else None,
                                    "total_amount": header["total_amount"] or 0,
                                    "vat": header["vat"] or 0,
                                    "source": header["source"],
                                    "source_file": header["source_file"],
                                    "delivery_address": header.get("delivery_address"),
                                    "status": "DRAFT",
                                    "created_by": "김민수",
                                }
                                _db.insert("sales_orders", [header_payload])
                                so_row = _db.fetch_one("sales_orders",
                                    f"so_number=eq.{header['so_number']}&customer=eq.{header['customer']}",
                                    "so_id")
                                if not so_row: continue

                                # 품목 INSERT
                                for it in g["items"]:
                                    qty = float(it.get("qty") or 0)
                                    item_payload = {
                                        "so_id": so_row["so_id"],
                                        "line_no": it.get("line_no") or 1,
                                        "customer_part_no": it.get("customer_part_no"),
                                        "customer_item_name": it.get("customer_item_name"),
                                        "product_id": it.get("matched_pid"),
                                        "canonical_pn": it.get("matched_pn"),
                                        "qty": qty,
                                        "received_qty": float(it.get("received_qty") or 0),
                                        "pending_qty": qty - float(it.get("received_qty") or 0),
                                        "unit": it.get("unit") or "EA",
                                        "unit_price": it.get("unit_price"),
                                        "amount": it.get("amount"),
                                        "vat": it.get("vat"),
                                        "total": it.get("total"),
                                        "due_date": it.get("due_date").isoformat() if it.get("due_date") else None,
                                        "mes_work_order": it.get("mes_work_order"),
                                        "remark": it.get("remark"),
                                        "status": "PENDING",
                                    }
                                    _db.insert("sales_order_items", [item_payload])
                                    saved_items += 1
                                saved_so += 1
                            except Exception as e:
                                st.warning(f"⚠️ 수주 {header['so_number']} 저장 실패: {e}")

                        st.success(f"✅ 수주 {saved_so}건 / 품목 {saved_items}개 저장 완료")
                        st.balloons()

        else:  # 수기 입력
            st.markdown("##### 수기 입력 — 단일 수주 1건")
            mc1, mc2 = st.columns(2)
            with mc1:
                m_so_no = st.text_input("거래처 발주번호 *", placeholder="예: PO-2026-001")
                m_cust = st.text_input("거래처명 *", placeholder="예: 신규 고객사")
                m_so_date = st.date_input("수주일", value=_date.today())
            with mc2:
                m_due = st.date_input("납기일", value=_date.today() + _td(days=14))
                m_addr = st.text_input("납품 주소")

            if "m_so_items" not in st.session_state:
                st.session_state.m_so_items = []

            with st.expander("➕ 품목 추가"):
                ic1, ic2, ic3, ic4 = st.columns(4)
                m_pn = ic1.text_input("품번", key="m_pn")
                m_qty = ic2.number_input("수량", 0, step=10, key="m_qty")
                m_up = ic3.number_input("단가", 0, step=100, key="m_up")
                m_due_item = ic4.date_input("품목 납기", value=_date.today() + _td(days=14), key="m_due_item")
                if st.button("➕ 추가", key="m_add_item") and m_pn and m_qty:
                    st.session_state.m_so_items.append({
                        "line_no": len(st.session_state.m_so_items) + 1,
                        "customer_part_no": m_pn, "qty": m_qty,
                        "unit_price": m_up, "amount": m_qty * m_up,
                        "due_date": m_due_item,
                    })
                    st.rerun()

            if st.session_state.m_so_items:
                df = pd.DataFrame(st.session_state.m_so_items)
                st.dataframe(df, use_container_width=True, hide_index=True)
                total = sum(it["amount"] for it in st.session_state.m_so_items)
                st.markdown(f"**총액**: ₩{total:,}")

            if st.button("💾 수주 저장", type="primary",
                         disabled=not (m_so_no and m_cust and st.session_state.m_so_items)):
                # 중복 체크
                try:
                    dup = fetch("sales_orders", "so_id,so_number",
                                f"so_number=eq.{m_so_no}&customer=eq.{m_cust}", limit=1)
                except Exception: dup = []
                if dup:
                    st.error(f"⚠️ 이미 등록됨: 수주 {m_so_no} / 거래처 {m_cust} (so_id={dup[0]['so_id']})")
                    st.stop()
                try:
                    v = fetch("vendors", "vendor_id", f"name=ilike.*{m_cust}*&limit=1", limit=1)
                    vendor_id = v[0]["vendor_id"] if v else None
                    _db.insert("sales_orders", [{
                        "so_number": m_so_no, "customer": m_cust, "vendor_id": vendor_id,
                        "so_date": m_so_date.isoformat(), "due_date": m_due.isoformat(),
                        "total_amount": total, "vat": int(total * 0.1),
                        "source": "MANUAL", "delivery_address": m_addr,
                        "status": "DRAFT", "created_by": "김민수",
                    }])
                    so_row = _db.fetch_one("sales_orders",
                        f"so_number=eq.{m_so_no}&customer=eq.{m_cust}", "so_id")
                    if so_row:
                        for it in st.session_state.m_so_items:
                            _db.insert("sales_order_items", [{
                                "so_id": so_row["so_id"], "line_no": it["line_no"],
                                "customer_part_no": it["customer_part_no"],
                                "qty": it["qty"], "unit": "EA",
                                "unit_price": it["unit_price"], "amount": it["amount"],
                                "due_date": it["due_date"].isoformat() if it.get("due_date") else None,
                                "status": "PENDING",
                            }])
                    st.success(f"✅ 수주 '{m_so_no}' 저장 완료")
                    st.session_state.m_so_items = []
                    st.balloons()
                except Exception as e:
                    st.error(f"저장 실패: {e}")

    # ════════ TAB 2: 수주 목록 (다중 뷰) ════════
    with tab_list:
        view_mode = st.radio("뷰",
            ["📋 수주별 (헤더)", "📦 품목별", "🏢 거래처별", "📅 납기 임박순", "❌ 매칭 안된 품목"],
            horizontal=True)

        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            sl_period = st.selectbox("기간", ["이번달", "최근 3개월", "올해", "전체"], index=2)
        with fc2:
            sl_cust = st.text_input("거래처", placeholder="예: HDX, 미진")
        with fc3:
            sl_status = st.selectbox("상태",
                ["전체", "DRAFT", "CONFIRMED", "IN_PROD", "PARTIAL", "DELIVERED", "CANCELLED"])

        today = _date.today()
        common_fq = []
        if sl_period == "이번달":
            common_fq.append(f"so_date=gte.{today.replace(day=1).isoformat()}")
        elif sl_period == "최근 3개월":
            common_fq.append(f"so_date=gte.{(today - _td(days=90)).isoformat()}")
        elif sl_period == "올해":
            common_fq.append(f"so_date=gte.{today.year}-01-01")
        if sl_cust: common_fq.append(f"customer=ilike.*{sl_cust}*")
        if sl_status != "전체": common_fq.append(f"status=eq.{sl_status}")

        # ── 뷰 1: 수주별 ──
        if view_mode == "📋 수주별 (헤더)":
            fq = ["order=so_date.desc"] + common_fq
            try: sos = fetch("sales_order_stats", "*", "&".join(fq), limit=300)
            except Exception as e: st.error(e); sos = []

            if sos:
                sc1, sc2, sc3, sc4 = st.columns(4)
                sc1.metric("수주 건수", len(sos))
                sc2.metric("총 수주액", f"₩{sum(int(s.get('total_amount') or 0) for s in sos):,}")
                sc3.metric("거래처 수", len({s["customer"] for s in sos}))
                avg_match = sum(s.get("match_rate_pct") or 0 for s in sos) / len(sos)
                sc4.metric("평균 매칭률", f"{avg_match:.1f}%")
                st.divider()
                df = pd.DataFrame([{
                    "수주번호": s["so_number"], "거래처": s["customer"],
                    "수주일": s.get("so_date"), "납기": s.get("due_date"),
                    "품목수": s.get("item_count"),
                    "총수량": int(s.get("total_qty") or 0),
                    "납품": int(s.get("total_received_qty") or 0),
                    "미납": int(s.get("total_pending_qty") or 0),
                    "납품상태": s.get("delivery_status"),
                    "총액": int(s.get("total_amount") or 0),
                    "매칭률": f"{s.get('match_rate_pct') or 0:.0f}%",
                    "상태": s["status"],
                } for s in sos])
                st.dataframe(df, use_container_width=True, hide_index=True,
                    column_config={"총액": st.column_config.NumberColumn(format="₩%d")})

                st.divider()
                st.markdown("##### 🔍 수주 상세")
                opts = {f"{s['so_number']} | {s['customer']} | ₩{int(s.get('total_amount') or 0):,}": s
                        for s in sos}
                sel_so = st.selectbox("선택", list(opts.keys()))
                if sel_so:
                    so = opts[sel_so]
                    sitems = fetch("sales_order_items", "*",
                                   f"so_id=eq.{so['so_id']}&order=line_no", limit=200)
                    idf = pd.DataFrame([{
                        "라인": i["line_no"], "거래처 자재": i.get("customer_part_no"),
                        "우성 품번": i.get("canonical_pn") or "❌",
                        "수량": int(i.get("qty") or 0),
                        "납품": int(i.get("received_qty") or 0),
                        "미납": int(i.get("pending_qty") or 0),
                        "단가": int(i.get("unit_price") or 0),
                        "금액": int(i.get("amount") or 0),
                        "납기": i.get("due_date"),
                        "상태": i.get("status"),
                    } for i in sitems])
                    if not idf.empty:
                        st.dataframe(idf, use_container_width=True, hide_index=True,
                            column_config={
                                "단가": st.column_config.NumberColumn(format="₩%d"),
                                "금액": st.column_config.NumberColumn(format="₩%d"),
                            })
                    rc1, rc2 = st.columns(2)
                    statuses = ["DRAFT","CONFIRMED","IN_PROD","PARTIAL","DELIVERED","CANCELLED"]
                    new_st = rc1.selectbox("상태 변경", statuses,
                        index=statuses.index(so["status"]) if so["status"] in statuses else 0)
                    if rc2.button("💾 상태 저장"):
                        if _db.update("sales_orders", f"so_id=eq.{so['so_id']}", {"status": new_st}):
                            st.success(f"상태 변경: {new_st}"); st.rerun()
            else:
                st.info("결과 없음")

        # ── 뷰 2: 품목별 ──
        elif view_mode == "📦 품목별":
            fq = ["order=so_date.desc"] + common_fq
            try: sos = fetch("sales_orders", "so_id,so_number,customer,so_date,status",
                              "&".join(fq), limit=500)
            except Exception as e: st.error(e); sos = []
            so_map = {s["so_id"]: s for s in sos}

            if so_map:
                ids_str = ",".join(str(x) for x in so_map.keys())
                p_search = st.text_input("품목 검색", placeholder="품번 또는 자재명")
                item_filter = f"so_id=in.({ids_str})&order=due_date.asc.nullslast"
                if p_search:
                    item_filter += f"&or=(canonical_pn.ilike.*{p_search}*,customer_part_no.ilike.*{p_search}*,customer_item_name.ilike.*{p_search}*)"
                try: sitems = fetch("sales_order_items", "*", item_filter, limit=1000)
                except Exception as e: st.error(e); sitems = []

                if sitems:
                    st.metric("품목 건수", len(sitems))
                    df = pd.DataFrame([{
                        "수주번호": so_map.get(i["so_id"], {}).get("so_number"),
                        "거래처": so_map.get(i["so_id"], {}).get("customer"),
                        "수주일": so_map.get(i["so_id"], {}).get("so_date"),
                        "라인": i["line_no"],
                        "거래처 자재": i.get("customer_part_no"),
                        "우성 품번": i.get("canonical_pn") or "❌",
                        "수량": int(i.get("qty") or 0),
                        "미납": int(i.get("pending_qty") or 0),
                        "단가": int(i.get("unit_price") or 0),
                        "금액": int(i.get("amount") or 0),
                        "납기": i.get("due_date"),
                        "상태": i.get("status"),
                    } for i in sitems])
                    st.dataframe(df, use_container_width=True, hide_index=True,
                        column_config={
                            "단가": st.column_config.NumberColumn(format="₩%d"),
                            "금액": st.column_config.NumberColumn(format="₩%d"),
                        })
                else:
                    st.info("결과 없음")
            else:
                st.info("수주 데이터 없음")

        # ── 뷰 3: 거래처별 ──
        elif view_mode == "🏢 거래처별":
            fq = ["order=customer.asc"] + common_fq
            try: sos = fetch("sales_order_stats", "*", "&".join(fq), limit=500)
            except Exception as e: st.error(e); sos = []

            if sos:
                from collections import defaultdict as _dd
                agg = _dd(lambda: {"수주건수": 0, "품목수": 0, "총수량": 0, "납품": 0,
                                    "미납": 0, "총액": 0, "_ms": 0, "_mn": 0})
                for s in sos:
                    a = agg[s["customer"]]
                    a["수주건수"] += 1
                    a["품목수"] += int(s.get("item_count") or 0)
                    a["총수량"] += int(s.get("total_qty") or 0)
                    a["납품"] += int(s.get("total_received_qty") or 0)
                    a["미납"] += int(s.get("total_pending_qty") or 0)
                    a["총액"] += int(s.get("total_amount") or 0)
                    if s.get("match_rate_pct") is not None:
                        a["_ms"] += s["match_rate_pct"]; a["_mn"] += 1

                rows = [{
                    "거래처": cust, "수주건수": a["수주건수"], "품목수": a["품목수"],
                    "총수량": a["총수량"], "납품": a["납품"], "미납": a["미납"],
                    "납품률": f"{100*a['납품']/a['총수량']:.1f}%" if a["총수량"] else "-",
                    "총액": a["총액"],
                    "평균매칭률": f"{(a['_ms']/a['_mn'] if a['_mn'] else 0):.1f}%",
                } for cust, a in sorted(agg.items(), key=lambda x: -x[1]["총액"])]
                df = pd.DataFrame(rows)
                st.dataframe(df, use_container_width=True, hide_index=True,
                    column_config={"총액": st.column_config.NumberColumn(format="₩%d")})
            else:
                st.info("결과 없음")

        # ── 뷰 4: 납기 임박순 ──
        elif view_mode == "📅 납기 임박순":
            fq = ["order=so_date.desc"] + common_fq
            try: sos = fetch("sales_orders", "so_id,so_number,customer,so_date,status",
                              "&".join(fq), limit=500)
            except Exception as e: st.error(e); sos = []
            so_map = {s["so_id"]: s for s in sos}

            if so_map:
                ids_str = ",".join(str(x) for x in so_map.keys())
                item_filter = f"so_id=in.({ids_str})&pending_qty=gt.0&due_date=not.is.null&order=due_date.asc"
                try: sitems = fetch("sales_order_items", "*", item_filter, limit=500)
                except Exception as e: st.error(e); sitems = []

                if sitems:
                    from datetime import datetime as _dt
                    rows = []
                    for i in sitems:
                        so = so_map.get(i["so_id"], {})
                        due_raw = i.get("due_date")
                        days_left = None
                        if due_raw:
                            try:
                                due_d = _dt.strptime(due_raw, "%Y-%m-%d").date() if isinstance(due_raw, str) else due_raw
                                days_left = (due_d - today).days
                            except: pass
                        emoji = ("🔴" if days_left is not None and days_left < 0 else
                                 "🟠" if days_left is not None and days_left <= 7 else
                                 "🟡" if days_left is not None and days_left <= 30 else "🟢")
                        rows.append({
                            "🔥": emoji,
                            "수주번호": so.get("so_number"),
                            "거래처": so.get("customer"),
                            "납기": due_raw, "D-day": days_left,
                            "거래처 자재": i.get("customer_part_no"),
                            "우성 품번": i.get("canonical_pn") or "❌",
                            "수량": int(i.get("qty") or 0),
                            "미납": int(i.get("pending_qty") or 0),
                        })
                    df = pd.DataFrame(rows)
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.info("미납 품목 없음")
            else:
                st.info("결과 없음")

        # ── 뷰 5: 매칭 안된 품목 ──
        elif view_mode == "❌ 매칭 안된 품목":
            fq = ["order=so_date.desc"] + common_fq
            try: sos = fetch("sales_orders", "so_id,so_number,customer,so_date",
                              "&".join(fq), limit=500)
            except Exception as e: st.error(e); sos = []
            so_map = {s["so_id"]: s for s in sos}

            if so_map:
                ids_str = ",".join(str(x) for x in so_map.keys())
                item_filter = f"so_id=in.({ids_str})&product_id=is.null&order=so_id.desc"
                try: sitems = fetch("sales_order_items", "*", item_filter, limit=500)
                except Exception as e: st.error(e); sitems = []

                if sitems:
                    st.warning(f"⚠️ 우성정밀 품번 매칭 안된 품목 **{len(sitems)}건**")
                    df = pd.DataFrame([{
                        "수주번호": so_map.get(i["so_id"], {}).get("so_number"),
                        "거래처": so_map.get(i["so_id"], {}).get("customer"),
                        "거래처 자재": i.get("customer_part_no"),
                        "거래처 품명": (i.get("customer_item_name") or "")[:40],
                        "수량": int(i.get("qty") or 0),
                        "수주일": so_map.get(i["so_id"], {}).get("so_date"),
                    } for i in sitems])
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    st.caption("💡 거래처 자재코드 → 우성정밀 품번 매핑은 마스터 관리에서 추가 가능 (다음 push)")
                else:
                    st.success("✅ 모든 품목이 매칭되었습니다")
            else:
                st.info("결과 없음")


elif page == "📊 생산 계획":
    st.subheader("📊 생산 계획 — 자재 필요량 자동 산출")
    if not DB_AVAILABLE: st.error("DB 연결 필요"); st.stop()

    import db as _db
    import pandas as pd
    from collections import defaultdict as _dd
    from datetime import date as _d2

    st.caption("📌 활성 수주(미납 품목)의 BOM을 조회해 자재 필요량을 산출합니다. "
               "**모든 단위 EA 통일** — 제품 EA × BOM.qty_per_pc (자재 EA/PC) ÷ shared_factor")

    # ── 1) 미납 수주 품목 조회 ──
    with st.spinner("미납 수주 조회 중..."):
        try:
            # 미납수량 > 0 이고 product_id 매칭된 것만
            sois = fetch("sales_order_items", "*",
                         "pending_qty=gt.0&product_id=not.is.null&order=due_date.asc.nullslast",
                         limit=1000)
        except Exception as e:
            st.error(f"수주 조회 실패: {e}"); sois = []

    if not sois:
        st.info("미납 수주 품목이 없습니다. 모든 수주가 완납되었거나 미납 품목이 매칭 안된 상태입니다.")
        st.stop()

    # ── 2) so_id 매핑 (수주 헤더 정보) ──
    so_ids = list({i["so_id"] for i in sois})
    ids_str = ",".join(str(x) for x in so_ids)
    so_rows = fetch("sales_orders", "so_id,so_number,customer,so_date,due_date,status",
                     f"so_id=in.({ids_str})", limit=500)
    so_map = {s["so_id"]: s for s in so_rows}

    # ── 3) BOM 조회 (제품별 자재 매핑) ──
    pids = list({i["product_id"] for i in sois if i.get("product_id")})
    if not pids:
        st.warning("매칭된 product_id가 없습니다. 수주 → ❌ 매칭 안된 품목에서 매핑 필요.")
        st.stop()

    pids_str = ",".join(f'"{p}"' for p in pids)
    bom_rows = fetch("bom", "product_id,material_id,raw_material_name,qty_per_pc,shared_factor",
                     f"product_id=in.({pids_str})", limit=2000)
    bom_by_pid = _dd(list)
    for b in bom_rows:
        bom_by_pid[b["product_id"]].append(b)

    # ── 4) 자재 마스터 조회 ──
    mids = list({b["material_id"] for b in bom_rows if b.get("material_id")})
    if mids:
        mids_str = ",".join(f'"{m}"' for m in mids)
        mat_rows = fetch("materials", "material_id,raw_name,material_type,spec,unit,stock_qty,main_supplier",
                          f"material_id=in.({mids_str})", limit=500)
        mat_map = {m["material_id"]: m for m in mat_rows}
    else:
        mat_map = {}

    # ── 5) 자재 필요량 계산 ──
    # material_id → {required, by_pid: {pid: req}, by_so: {so_id: req}}
    mat_req = _dd(lambda: {
        "required": 0.0, "by_pid": _dd(float), "by_so": _dd(float),
        "items_count": 0, "no_bom_pids": set(),
    })
    items_with_bom = 0
    items_no_bom = []

    for soi in sois:
        pid = soi["product_id"]
        pending = float(soi.get("pending_qty") or 0)
        boms = bom_by_pid.get(pid, [])
        if not boms:
            items_no_bom.append({
                "so_id": soi["so_id"], "product_id": pid,
                "canonical_pn": soi.get("canonical_pn"),
                "pending_qty": pending,
            })
            continue
        items_with_bom += 1
        for b in boms:
            mid = b.get("material_id")
            if not mid: continue
            qpp = float(b.get("qty_per_pc") or 1)
            sf = float(b.get("shared_factor") or 1) or 1
            need = pending * qpp / sf
            mat_req[mid]["required"] += need
            mat_req[mid]["by_pid"][pid] += need
            mat_req[mid]["by_so"][soi["so_id"]] += need
            mat_req[mid]["items_count"] += 1

    # ── 6) 상단 통계 ──
    sc1, sc2, sc3, sc4 = st.columns(4)
    sc1.metric("미납 수주 품목", len(sois))
    sc2.metric("BOM 매핑된 품목", items_with_bom)
    sc3.metric("필요 자재 종류", len(mat_req))
    shortage_count = sum(1 for mid, info in mat_req.items()
                          if info["required"] - (mat_map.get(mid, {}).get("stock_qty") or 0) > 0)
    sc4.metric("🔴 자재 부족", shortage_count, delta_color="inverse")

    if items_no_bom:
        with st.expander(f"⚠️ BOM 미등록 품목 {len(items_no_bom)}건 — 마스터에서 BOM 등록 필요"):
            df_no = pd.DataFrame(items_no_bom)
            st.dataframe(df_no, use_container_width=True, hide_index=True)

    st.divider()

    # ── 7) 탭 구조 ──
    tab_mat, tab_so, tab_po = st.tabs(["📦 자재별 필요량", "📋 수주별 BOM 전개", "🛒 발주 자동 제안"])

    # ─── 탭 1: 자재별 ───
    with tab_mat:
        rows = []
        for mid, info in mat_req.items():
            mat = mat_map.get(mid, {})
            req = info["required"]
            stock = float(mat.get("stock_qty") or 0)
            shortage = req - stock
            rows.append({
                "자재ID": mid,
                "자재명": mat.get("raw_name") or "-",
                "재질": mat.get("material_type") or "-",
                "규격": mat.get("spec") or "-",
                "단위": mat.get("unit") or "-",
                "필요량": round(req, 2),
                "현재재고": round(stock, 2),
                "부족분": round(shortage, 2),
                "주공급사": (mat.get("main_supplier") or "-")[:30],
                "사용 제품수": len(info["by_pid"]),
                "수주 건수": len(info["by_so"]),
            })
        # 부족분 큰 순
        rows.sort(key=lambda x: -x["부족분"])
        df = pd.DataFrame(rows)

        if not df.empty:
            # 행별 색상 (부족분 > 0: 빨간 표시는 dataframe에서 직접 안 됨 → 정보로)
            st.dataframe(df, use_container_width=True, hide_index=True)

            shortage_rows = [r for r in rows if r["부족분"] > 0]
            if shortage_rows:
                st.warning(f"🔴 자재 부족 {len(shortage_rows)}건 — '🛒 발주 자동 제안' 탭에서 발주서 생성 가능")

    # ─── 탭 2: 수주별 BOM 전개 ───
    with tab_so:
        # so별 그룹화
        by_so = _dd(list)
        for soi in sois:
            by_so[soi["so_id"]].append(soi)

        for so_id, items in list(by_so.items())[:30]:  # 최대 30개 수주
            so = so_map.get(so_id, {})
            so_label = f"📋 {so.get('so_number')} | {so.get('customer')} | 납기: {so.get('due_date') or '-'}"
            with st.expander(so_label):
                so_rows = []
                for soi in items:
                    pid = soi["product_id"]
                    pending = float(soi.get("pending_qty") or 0)
                    boms = bom_by_pid.get(pid, [])
                    if not boms:
                        so_rows.append({
                            "라인": soi["line_no"],
                            "품번": soi.get("canonical_pn"),
                            "미납수량": pending,
                            "자재": "❌ BOM 미등록",
                            "필요량": 0, "단위": "-", "재고": 0, "부족분": 0,
                        })
                        continue
                    for b in boms:
                        mid = b.get("material_id")
                        mat = mat_map.get(mid, {})
                        qpp = float(b.get("qty_per_pc") or 1)
                        sf = float(b.get("shared_factor") or 1) or 1
                        need = pending * qpp / sf
                        stock = float(mat.get("stock_qty") or 0)
                        so_rows.append({
                            "라인": soi["line_no"],
                            "품번": soi.get("canonical_pn"),
                            "미납수량": pending,
                            "자재": mat.get("raw_name") or "-",
                            "필요량": round(need, 2),
                            "단위": mat.get("unit") or "-",
                            "재고": round(stock, 2),
                            "부족분": round(max(0, need - stock), 2),
                        })
                st.dataframe(pd.DataFrame(so_rows), use_container_width=True, hide_index=True)

    # ─── 탭 3: 발주 자동 제안 ───
    with tab_po:
        # 부족분 > 0인 자재만 + 거래처별 묶음
        shortage_list = []
        for mid, info in mat_req.items():
            mat = mat_map.get(mid, {})
            req = info["required"]
            stock = float(mat.get("stock_qty") or 0)
            shortage = req - stock
            if shortage > 0:
                # 주공급사 파싱 ("(주)명진메탈(967건)" → "(주)명진메탈")
                sup_raw = (mat.get("main_supplier") or "").split("(")[0].strip()
                # 또는 "(주)명진메탈(967건)" 같은 형식 처리
                import re as _re3
                sup_match = _re3.match(r'^([^(]+(?:\([^)]+\)[^(]*)?)', mat.get("main_supplier") or "")
                supplier_name = sup_match.group(1).strip() if sup_match else sup_raw
                supplier_name = supplier_name.split(",")[0].strip() if "," in supplier_name else supplier_name
                # 공급사명에서 빈도수 표기 제거
                supplier_name = _re3.sub(r'\(\d+건?\)$', '', supplier_name).strip()

                shortage_list.append({
                    "material_id": mid,
                    "name": mat.get("raw_name") or "",
                    "material_type": mat.get("material_type"),
                    "spec": mat.get("spec"),
                    "unit": mat.get("unit") or "EA",
                    "required": req, "stock": stock, "shortage": shortage,
                    "supplier": supplier_name or "(미정)",
                })

        if not shortage_list:
            st.success("✅ 자재 부족 없음 — 발주 제안 사항 없습니다.")
        else:
            # 거래처별 묶음
            by_supplier = _dd(list)
            for s in shortage_list:
                by_supplier[s["supplier"]].append(s)

            for supplier, mats in sorted(by_supplier.items(), key=lambda x: -sum(m["shortage"] for m in x[1])):
                total_short = sum(m["shortage"] for m in mats)
                with st.expander(f"🛒 **{supplier}** — {len(mats)}개 자재 부족 (합 {total_short:.1f})",
                                 expanded=True):
                    pdf = pd.DataFrame([{
                        "자재명": m["name"][:30],
                        "재질": m["material_type"] or "-",
                        "규격": m["spec"] or "-",
                        "필요량": round(m["required"], 2),
                        "재고": round(m["stock"], 2),
                        "부족분 (발주 권장)": round(m["shortage"], 2),
                        "단위": m["unit"],
                    } for m in mats])
                    st.dataframe(pdf, use_container_width=True, hide_index=True)

                    if st.button(f"➕ 발주서 작성 화면으로 (이 {len(mats)}건)",
                                 key=f"go_po_{supplier}"):
                        # session_state로 발주 화면에 미리 채울 데이터 전달
                        st.session_state["po_prefill_vendor_name"] = supplier
                        st.session_state["po_prefill_items"] = [{
                            "product_id": None,  # 자재 행이므로 product_id 없음
                            "item_name": m["name"],
                            "material": m["material_type"] or "",
                            "spec": m["spec"] or "",
                            "qty": int(m["shortage"]) if m["unit"] == "EA" else round(m["shortage"], 2),
                            "unit_price": 0,
                        } for m in mats]
                        st.success(f"✅ '{supplier}'의 {len(mats)}개 품목이 발주서 작성에 임시 저장됨. "
                                   f"좌측 '📋 발주서 작성' 메뉴로 이동해서 검토하세요.")


elif page == "📋 발주서 작성":
    st.subheader("📋 발주 관리")
    if not DB_AVAILABLE:
        st.error("DB 연결 필요"); st.stop()

    from datetime import date as _date, timedelta as _td
    from utils.po_generator import generate_po_number, fill_po_template
    import db as _db
    import pandas as pd

    PURCHASE_GROUPS = {
        "MAT_STS": "🟦 소재 STS (명진/유성)",
        "MAT_CARBON": "🟦 소재 탄소강 (혜성)",
        "MAT_FORGING": "🟦 단조품",
        "MAT_CASTING": "🟦 주조품",
        "MAT_OTHER": "🟦 기타 소재",
        "MAT_CONSUMABLES": "🟨 유류·소모성 자재",
        "OUTSOURCE": "🟩 외주 (가공·연마·전조)",
        "HEAT_TREAT": "🟩 열처리",
        "SURFACE": "🟩 표면처리",
        "TOOL": "🟨 공구·소모품",
    }

    tab_new, tab_hist = st.tabs(["✏️ 새 발주서 작성", "📜 발주 이력"])

    # ════════════ TAB 1: 새 발주서 작성 ════════════
    with tab_new:
        # 생산 계획에서 prefill된 경우 안내
        if st.session_state.get("po_prefill_vendor_name") or st.session_state.get("po_prefill_items"):
            pv = st.session_state.get("po_prefill_vendor_name", "")
            pi = st.session_state.get("po_prefill_items", [])
            st.info(f"🛒 **생산 계획에서 자동 제안 받은 발주 데이터**: 거래처 '{pv}', 품목 {len(pi)}개. "
                    f"아래에서 거래처 선택 + 품목 확인 후 발주서 생성.")
            if st.button("🔄 자동 제안 데이터 초기화"):
                st.session_state.po_prefill_vendor_name = None
                st.session_state.po_prefill_items = None
                st.rerun()
            # 품목 prefill
            if pi and not st.session_state.get("po_items"):
                st.session_state.po_items = list(pi)

        st.markdown("##### ① 거래처 선택")
        group_options = ["전체 (매입)"] + list(PURCHASE_GROUPS.values())
        sel_group_label = st.selectbox("발주 그룹", group_options, index=0)
        selected_groups = list(PURCHASE_GROUPS.keys()) if sel_group_label == "전체 (매입)" else \
            [k for k, v in PURCHASE_GROUPS.items() if v == sel_group_label]
        groups_str = ",".join(selected_groups)
        fq = f"vendor_group=in.({groups_str})&in_use=eq.true&order=name"
        try:
            vendors = fetch("vendors",
                            "vendor_id,name,vendor_group,category,business_no,ceo_name,phone,fax,address,email,payment_terms,contact_person,contact_phone",
                            filter_query=fq, limit=300)
        except Exception as e:
            st.error(f"거래처 로드 실패: {e}"); vendors = []

        if not vendors:
            st.warning("해당 그룹에 거래처가 없습니다. 아래에서 신규 등록하세요.")

        # 신규 거래처 등록 (검색 결과 부족 시 사용)
        with st.expander("➕ 신규 거래처 등록 (수기 입력)"):
            ec1, ec2 = st.columns(2)
            with ec1:
                nv_name = st.text_input("거래처명 *", key="nv_name", placeholder="(주)○○산업")
                nv_biz = st.text_input("사업자번호", key="nv_biz", placeholder="000-00-00000")
                nv_ceo = st.text_input("대표자명", key="nv_ceo")
                nv_phone = st.text_input("전화", key="nv_phone")
            with ec2:
                nv_group = st.selectbox("그룹 *", options=["선택"] + list(PURCHASE_GROUPS.keys()),
                                        key="nv_group")
                nv_pay = st.text_input("결제조건", key="nv_pay",
                                       value="말일 마감 60일 현금")
                nv_address = st.text_input("주소", key="nv_addr")
                nv_email = st.text_input("이메일", key="nv_mail")
            nv_contact = st.text_input("담당자", key="nv_contact")
            nv_btype = st.text_input("업태", key="nv_btype")
            nv_bitem = st.text_input("종목", key="nv_bitem")
            nv_memo = st.text_input("메모", key="nv_memo")

            # 마지막 등록 결과 표시
            if "po_last_registered" in st.session_state:
                lr = st.session_state.po_last_registered
                st.success(f"✅ **{lr['name']}** 등록 완료 (ID: {lr['id']}, 그룹: {lr['group']})")

            if st.button("💾 신규 거래처 저장", type="primary"):
                if not nv_name or nv_group == "선택":
                    st.error("거래처명과 그룹은 필수입니다.")
                else:
                    import re as _re
                    cleaned = (nv_name.replace('（','(').replace('）',')').replace('㈜','(주)'))
                    cleaned = _re.sub(r'\)\s+', ')', cleaned)
                    cleaned = _re.sub(r'\s+\(', '(', cleaned)
                    cleaned = _re.sub(r'\s+', ' ', cleaned).strip()
                    norm = _re.sub(r'\s+', '', cleaned)
                    nv_name = cleaned
                    # 중복 체크
                    dup_q = f"normalized_name=eq.{norm}"
                    try:
                        dup = fetch("vendors", "vendor_id,name", dup_q, limit=1)
                    except Exception: dup = []
                    if dup:
                        st.error(f"⚠️ 이미 등록됨: {dup[0]['name']} (vendor_id={dup[0]['vendor_id']})")
                    else:
                        try:
                            payload = {
                                "name": nv_name,
                                "normalized_name": norm,
                                "business_no": nv_biz or None,
                                "vendor_group": nv_group,
                                "trade_type": "매입",
                                "ceo_name": nv_ceo or None,
                                "phone": nv_phone or None,
                                "address": nv_address or None,
                                "email": nv_email or None,
                                "contact_person": nv_contact or None,
                                "business_type": nv_btype or None,
                                "business_item": nv_bitem or None,
                                "payment_terms": nv_pay,
                                "memo": nv_memo or None,
                                "verification_status": "수기등록",
                                "in_use": True,
                            }
                            _db.insert("vendors", [payload])
                            new_v = fetch("vendors", "vendor_id", f"normalized_name=eq.{norm}", limit=1)
                            new_id = new_v[0]["vendor_id"] if new_v else "?"
                            st.session_state.po_last_registered = {
                                "name": cleaned, "id": new_id, "group": nv_group
                            }
                            st.toast(f"✅ '{cleaned}' 등록 완료!", icon="🎉")
                            st.balloons()
                            st.rerun()
                        except Exception as e:
                            st.error(f"등록 실패: {e}")

        if vendors:
            vendor_options = {f"{v['name']} ({v.get('vendor_group') or '-'})": v for v in vendors}
            sel = st.selectbox(f"거래처 선택 ({len(vendors)}개)", list(vendor_options.keys()))
            vendor = vendor_options[sel]

            with st.expander("선택한 거래처 정보"):
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**사업자번호**: {vendor.get('business_no') or '-'}")
                    st.write(f"**결제조건**: {vendor.get('payment_terms') or '-'}")
                with c2:
                    st.write(f"**주소**: {vendor.get('address') or '-'}")
                    st.write(f"**담당자**: {vendor.get('contact_person') or '-'}")

            st.divider()
            st.markdown("##### ② 품목 추가")
            if "po_items" not in st.session_state:
                st.session_state.po_items = []

            search_q = st.text_input("품번 검색", placeholder="예: 8HFDV, 4PDVN")
            if search_q and len(search_q) >= 2:
                try:
                    res = fetch("active_products",
                                "product_id,pn,raw_material_name,raw_material_spec,material,bom_material_name,material_unit_price",
                                f"or=(pn.ilike.*{search_q}*,alias_list.ilike.*{search_q}*,bom_material_name.ilike.*{search_q}*)&limit=20")
                except Exception as e:
                    st.error(f"검색 실패: {e}"); res = []
                for p in res[:10]:
                    with st.container(border=True):
                        cols = st.columns([3, 2, 2, 2, 1])
                        cols[0].write(f"**{p['pn']}**")
                        cols[1].write(p.get("material") or "-")
                        cols[2].write(p.get("raw_material_spec") or p.get("bom_material_name") or "-")
                        upd = int(p.get("material_unit_price") or 0)
                        cols[3].write(f"₩{upd:,}" if upd else "-")
                        if cols[4].button("➕", key=f"add_{p['product_id']}"):
                            st.session_state.po_items.append({
                                "product_id": p["product_id"], "item_name": p["pn"],
                                "material": p.get("material") or "",
                                "spec": p.get("raw_material_spec") or "",
                                "qty": 0, "unit_price": upd,
                            })
                            st.rerun()

            with st.expander("✏️ 마스터에 없는 품목 즉석 추가"):
                c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
                nx = c1.text_input("품번/품명", key="nx_name")
                nm = c2.text_input("재질", key="nx_mat")
                ns = c3.text_input("규격", key="nx_spec")
                np_ = c4.number_input("단가", min_value=0, step=100, key="nx_price")
                if st.button("➕ 추가 (즉석)") and nx:
                    st.session_state.po_items.append({
                        "product_id": None, "item_name": nx, "material": nm,
                        "spec": ns, "qty": 0, "unit_price": int(np_),
                    })
                    st.rerun()

            st.divider()
            st.markdown("##### ③ 품목 표 (수량·단가 편집)")
            total = 0
            if not st.session_state.po_items:
                st.info("위에서 ➕ 버튼으로 품목을 추가하세요.")
            else:
                for i, it in enumerate(st.session_state.po_items):
                    with st.container(border=True):
                        cols = st.columns([3, 1.5, 2, 1.5, 1.5, 1.5, 0.5])
                        cols[0].write(f"**{it['item_name']}**")
                        cols[1].write(it.get("material") or "")
                        cols[2].write(it.get("spec") or "")
                        it["qty"] = cols[3].number_input("수량", 0, value=int(it.get("qty") or 0),
                            step=10, key=f"qty_{i}", label_visibility="collapsed")
                        it["unit_price"] = cols[4].number_input("단가", 0, value=int(it.get("unit_price") or 0),
                            step=100, key=f"up_{i}", label_visibility="collapsed")
                        amt = it["qty"] * it["unit_price"]
                        cols[5].markdown(f"<div style='text-align:right;padding-top:8px'>₩{amt:,}</div>",
                                         unsafe_allow_html=True)
                        if cols[6].button("🗑", key=f"del_{i}"):
                            st.session_state.po_items.pop(i); st.rerun()
                total = sum(it["qty"] * it["unit_price"] for it in st.session_state.po_items)
                st.markdown(f"### 합계: ₩{total:,} (VAT 별도)")

            st.divider()
            st.markdown("##### ④ 발주 정보")
            fc1, fc2 = st.columns(2)
            with fc1:
                po_date = st.date_input("발주일", value=_date.today())
                delivery_date = st.text_input("납기", placeholder="예: 14일 이내")
            with fc2:
                payment_terms = st.text_input("지불조건",
                    value=vendor.get("payment_terms") or "말일 마감 60일 현금")
                contact_person = st.text_input("담당자", value="김민수 과장 / 010-3881-1165")
            delivery_address = st.text_input("배송지", value="부산광역시 기장군 산단4로 71")

            st.divider()

            if st.button("📄 발주서 xlsx 생성", type="primary", use_container_width=True,
                         disabled=not st.session_state.po_items):
                try:
                    po_no = generate_po_number(_db)
                except Exception:
                    po_no = f"PO-{_date.today().strftime('%Y%m')}-001"
                po_data = {"po_number": po_no, "po_date": po_date,
                           "vendor_name": vendor["name"],
                           "delivery_date": delivery_date,
                           "payment_terms": payment_terms,
                           "delivery_address": delivery_address,
                           "contact_person": contact_person}
                vendor_info = {
                    "biz_no": vendor.get("business_no"),
                    "ceo": vendor.get("ceo_name"),
                    "address": vendor.get("address"),
                    "phone": vendor.get("phone"),
                }
                try:
                    xlsx_bytes = fill_po_template(po_data, st.session_state.po_items, vendor_info)
                    st.success(f"✅ 발주서 생성 완료: **{po_no}**")
                    st.download_button("⬇ 다운로드", data=xlsx_bytes,
                        file_name=f"{po_no}_{vendor['name']}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True)
                    try:
                        _db.insert("purchase_orders", [{
                            "po_number": po_no, "vendor_id": vendor["vendor_id"],
                            "po_date": po_date.isoformat(),
                            "delivery_date": delivery_date or None,
                            "total_amount": total, "vat": int(total * 0.1),
                            "payment_terms": payment_terms,
                            "delivery_address": delivery_address,
                            "contact_person": contact_person,
                            "status": "DRAFT", "created_by": "김민수",
                        }])
                        po_row = _db.fetch_one("purchase_orders", f"po_number=eq.{po_no}", "po_id")
                        if po_row:
                            _db.insert("purchase_order_items", [{
                                "po_id": po_row["po_id"], "line_no": i + 1,
                                "item_name": it["item_name"], "spec": it.get("spec") or None,
                                "qty": it["qty"], "unit": "EA",
                                "unit_price": it["unit_price"],
                                "amount": it["qty"] * it["unit_price"],
                                "remark": it.get("material") or None,
                            } for i, it in enumerate(st.session_state.po_items)])
                            st.info(f"💾 발주 이력 저장 (po_id={po_row['po_id']})")
                    except Exception as e:
                        st.warning(f"⚠️ DB 저장 실패 (xlsx는 정상): {e}")
                    if st.button("🔄 새 발주서 시작"):
                        st.session_state.po_items = []; st.rerun()
                except Exception as e:
                    st.error(f"발주서 생성 실패: {e}")

    # ════════════ TAB 2: 발주 이력 ════════════
    with tab_hist:
        c1, c2, c3 = st.columns(3)
        with c1:
            period = st.selectbox("기간", ["이번달", "최근 3개월", "올해", "전체"], index=0)
        with c2:
            status_f = st.selectbox("상태", ["전체", "DRAFT", "SENT", "RECEIVED", "CANCELLED"])
        with c3:
            v_search = st.text_input("거래처", placeholder="이름 검색")

        # 쿼리 빌드
        today = _date.today()
        fq_parts = ["order=po_date.desc"]
        if period == "이번달":
            fq_parts.append(f"po_date=gte.{today.replace(day=1).isoformat()}")
        elif period == "최근 3개월":
            fq_parts.append(f"po_date=gte.{(today - _td(days=90)).isoformat()}")
        elif period == "올해":
            fq_parts.append(f"po_date=gte.{today.year}-01-01")
        if status_f != "전체":
            fq_parts.append(f"status=eq.{status_f}")
        fq_h = "&".join(fq_parts)

        try:
            history = fetch("purchase_orders",
                            "po_id,po_number,vendor_id,po_date,delivery_date,total_amount,vat,status,contact_person",
                            fq_h, limit=500)
        except Exception as e:
            st.error(f"발주 이력 조회 실패: {e}"); history = []

        if not history:
            st.info("이 조건의 발주 이력이 없습니다.")
        else:
            # 거래처명 매핑
            vid_set = list({r["vendor_id"] for r in history if r.get("vendor_id")})
            v_map = {}
            if vid_set:
                vid_str = ",".join(str(x) for x in vid_set)
                vs = fetch("vendors", "vendor_id,name,vendor_group", f"vendor_id=in.({vid_str})", limit=500)
                v_map = {v["vendor_id"]: v for v in vs}
            for r in history:
                vinfo = v_map.get(r.get("vendor_id"), {})
                r["_vname"] = vinfo.get("name", "?")
                r["_vgroup"] = vinfo.get("vendor_group", "")

            # 거래처 필터
            if v_search:
                history = [r for r in history if v_search.lower() in (r["_vname"] or "").lower()]

            # 통계
            stat_cols = st.columns(3)
            stat_cols[0].metric("발주 건수", len(history))
            stat_cols[1].metric("총 발주액",
                f"₩{sum(int(r.get('total_amount') or 0) for r in history):,}")
            stat_cols[2].metric("거래처 수",
                len({r["_vname"] for r in history}))

            st.divider()

            df = pd.DataFrame([{
                "발주번호": r["po_number"],
                "거래처": r["_vname"],
                "그룹": r["_vgroup"],
                "발주일": r["po_date"],
                "납기": r.get("delivery_date") or "-",
                "총액": int(r.get("total_amount") or 0),
                "VAT": int(r.get("vat") or 0),
                "상태": r["status"],
            } for r in history])
            st.dataframe(
                df, use_container_width=True, hide_index=True,
                column_config={
                    "총액": st.column_config.NumberColumn(format="₩%d"),
                    "VAT": st.column_config.NumberColumn(format="₩%d"),
                }
            )

            st.divider()
            st.markdown("##### 🔍 발주서 상세 / 재발급")
            opts = {f"{r['po_number']} | {r['_vname']} | ₩{int(r.get('total_amount') or 0):,}": r
                    for r in history}
            sel_po = st.selectbox("선택", list(opts.keys()))
            if sel_po:
                po = opts[sel_po]
                items = fetch("purchase_order_items", "*",
                              f"po_id=eq.{po['po_id']}&order=line_no", limit=50)
                item_df = pd.DataFrame([{
                    "NO": i.get("line_no"),
                    "품명": i.get("item_name"),
                    "규격": i.get("spec") or "-",
                    "수량": i.get("qty"),
                    "단가": int(i.get("unit_price") or 0),
                    "공급가액": int(i.get("amount") or 0),
                    "비고": i.get("remark") or "-",
                } for i in items])
                if not item_df.empty:
                    st.dataframe(item_df, use_container_width=True, hide_index=True,
                                 column_config={
                                    "단가": st.column_config.NumberColumn(format="₩%d"),
                                    "공급가액": st.column_config.NumberColumn(format="₩%d"),
                                 })

                rc1, rc2 = st.columns(2)
                if rc1.button("📄 xlsx 재발급", use_container_width=True):
                    # 재발급 시 거래처 상세 다시 조회
                    full_vendor = _db.fetch_one(
                        "vendors",
                        f"vendor_id=eq.{po['vendor_id']}",
                        "business_no,ceo_name,address,phone"
                    ) or {}
                    re_po_data = {
                        "po_number": po["po_number"],
                        "po_date": po["po_date"],
                        "vendor_name": po["_vname"],
                        "delivery_date": po.get("delivery_date"),
                        "payment_terms": po.get("payment_terms") or "",
                        "delivery_address": "부산광역시 기장군 산단4로 71",
                        "contact_person": po.get("contact_person") or "김민수 과장",
                    }
                    re_vendor_info = {
                        "biz_no": full_vendor.get("business_no"),
                        "ceo": full_vendor.get("ceo_name"),
                        "address": full_vendor.get("address"),
                        "phone": full_vendor.get("phone"),
                    }
                    try:
                        xb = fill_po_template(re_po_data, [{
                            "item_name": i.get("item_name"),
                            "material": i.get("remark") or "",
                            "spec": i.get("spec") or "",
                            "qty": int(i.get("qty") or 0),
                            "unit_price": int(i.get("unit_price") or 0),
                        } for i in items], re_vendor_info)
                        st.download_button("⬇ 다운로드", data=xb,
                            file_name=f"{po['po_number']}_{po['_vname']}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True)
                    except Exception as e:
                        st.error(f"재발급 실패: {e}")

                new_status = rc2.selectbox(
                    "상태 변경",
                    ["DRAFT", "SENT", "RECEIVED", "CANCELLED"],
                    index=["DRAFT", "SENT", "RECEIVED", "CANCELLED"].index(po["status"])
                          if po["status"] in ["DRAFT","SENT","RECEIVED","CANCELLED"] else 0
                )
                if rc2.button("💾 상태 저장", use_container_width=True):
                    if _db.update("purchase_orders", f"po_id=eq.{po['po_id']}",
                                  {"status": new_status}):
                        st.success(f"상태를 {new_status}로 변경"); st.rerun()


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
