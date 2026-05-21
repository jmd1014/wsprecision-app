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
        ["🏠 홈", "⚙️ 마스터 관리", "🚀 BOM 빠른 정비", "📥 수주", "📊 생산 계획", "📋 발주서 작성", "📦 입출고", "🏭 생산 보고", "📊 매출/재고", "💰 원가 분석"],
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

    tab1, tab_prod, tab_mat, tab_bom, tab_excl, tab_map, tab2 = st.tabs([
        "🏢 거래처 편집", "🧱 제품 편집", "📦 자재 편집", "🔗 BOM 편집",
        "🚫 데이터 제외 규칙",
        "🔌 매입↔자재 매핑 (레거시)", "🧭 마스터/연결 점검"
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

    # ─── Tab: 제품 편집 ───
    with tab_prod:
        st.caption("📌 제품 마스터 편집. **비용 컬럼 (소재비/외주/열처리/표면) 은 "
                   "💰 원가 분석 → ✏️ 원가 편집** 에서 관리. 여기서는 "
                   "분류·재질·조달·상태 등 일반 정보만.")

        # ── 검색 / 필터 ──
        with st.expander("🔍 검색 / 필터", expanded=True):
            pfc1, pfc2, pfc3, pfc4 = st.columns(4)
            with pfc1:
                fpn = st.text_input("품번", placeholder="MRG6, 8HFDV",
                                    key="prod_f_pn")
            with pfc2:
                fcust = st.text_input("고객사", placeholder="미진, 명진, 두산",
                                      key="prod_f_cust")
            with pfc3:
                fgroup = st.text_input("제품군", placeholder="FLANGE, ADAPTER",
                                       key="prod_f_group")
            with pfc4:
                fstatus = st.selectbox("상태",
                    ["활성", "휴면", "전체"], key="prod_f_status")

            pfc5, pfc6, pfc7 = st.columns([2, 2, 1])
            with pfc5:
                fmat = st.text_input("재질/규격/자재명",
                    placeholder="STS304, 환봉, SCM440",
                    key="prod_f_mat")
            with pfc6:
                fproc = st.selectbox("조달",
                    ["전체", "도급", "사급"], key="prod_f_proc")
            with pfc7:
                plim = st.number_input("행수", 20, 1000, 100, 20,
                                       key="prod_lim")

        # ── 쿼리 빌드 ──
        parts = ["order=pn.asc"]
        if fpn:
            parts.append(f"pn=ilike.*{fpn.strip()}*")
        if fcust:
            parts.append(f"customer=ilike.*{fcust.strip()}*")
        if fgroup:
            parts.append(f"product_group=ilike.*{fgroup.strip()}*")
        if fmat:
            mq = fmat.strip()
            parts.append(
                f"or=(material.ilike.*{mq}*,raw_material_name.ilike.*{mq}*,"
                f"raw_material_spec.ilike.*{mq}*)"
            )
        if fstatus == "활성":
            parts.append("archived_at=is.null")
        elif fstatus == "휴면":
            parts.append("archived_at=not.is.null")
        if fproc != "전체":
            parts.append(f"procurement_type=eq.{fproc}")

        try:
            prows = fetch("products",
                "product_id,pn,customer,product_group,sub_class,material,"
                "raw_material_name,raw_material_spec,procurement_type,"
                "caution,active,archived_at,archive_reason,drawing_no,"
                "alias_list,updated_at",
                "&".join(parts), limit=int(plim))
        except Exception as e:
            st.error(f"조회 실패: {e}"); prows = []

        st.caption(f"검색 결과: **{len(prows)}건**")

        if prows:
            pdf = pd.DataFrame(prows)
            # 표시할 컬럼 (편집/조회용)
            show_cols = ["product_id","pn","customer","product_group","sub_class",
                         "material","raw_material_name","raw_material_spec",
                         "procurement_type","caution","active","archived_at",
                         "archive_reason","drawing_no","alias_list"]
            show_cols = [c for c in show_cols if c in pdf.columns]
            pdf = pdf[show_cols]

            edited_p = st.data_editor(
                pdf,
                column_config={
                    "product_id": st.column_config.TextColumn("PID",
                        disabled=True, width="small"),
                    "pn": st.column_config.TextColumn("품번 *", width="medium",
                        help="중복 금지 — 수정 시 매출/매입 매핑에 영향"),
                    "customer": st.column_config.TextColumn("고객사",
                        width="medium"),
                    "product_group": st.column_config.TextColumn("제품군",
                        width="small"),
                    "sub_class": st.column_config.TextColumn("하위분류",
                        width="small"),
                    "material": st.column_config.TextColumn("재질",
                        width="small"),
                    "raw_material_name": st.column_config.TextColumn(
                        "자재명", width="medium"),
                    "raw_material_spec": st.column_config.TextColumn(
                        "규격", width="small"),
                    "procurement_type": st.column_config.SelectboxColumn("조달",
                        options=["", "도급", "사급"], width="small"),
                    "caution": st.column_config.TextColumn("주의사항",
                        width="medium"),
                    "active": st.column_config.TextColumn("active",
                        width="small", help="'1'=활성, '0'=비활성"),
                    "archived_at": st.column_config.DatetimeColumn("휴면일자",
                        disabled=True, width="small"),
                    "archive_reason": st.column_config.TextColumn("휴면사유",
                        width="medium"),
                    "drawing_no": st.column_config.TextColumn("도면번호",
                        width="small"),
                    "alias_list": st.column_config.TextColumn("별칭(콤마)",
                        width="medium"),
                },
                hide_index=True, use_container_width=True,
                num_rows="fixed", key="prod_editor", height=440
            )

            psv1, psv2 = st.columns([1, 4])
            with psv1:
                save_prod = st.button("💾 변경 저장", type="primary",
                                       key="prod_save")
            with psv2:
                st.caption("⚠️ 품번(pn) 변경은 매출/매입 매핑에 영향 — "
                           "변경 시 sales_ledger / purchase_ledger 의 "
                           "관련 행 재매핑 검토 필요")

            if save_prod:
                chg = 0
                editable_keys = ("pn", "customer", "product_group", "sub_class",
                                 "material", "raw_material_name", "raw_material_spec",
                                 "procurement_type", "caution", "active",
                                 "archive_reason", "drawing_no", "alias_list")
                for orig, new in zip(prows, edited_p.to_dict("records")):
                    upd = {}
                    for k in editable_keys:
                        if k in new:
                            ov = orig.get(k)
                            nv = new.get(k)
                            if isinstance(nv, float) and pd.isna(nv):
                                nv = None
                            if nv == "":
                                nv = None
                            if ov != nv:
                                upd[k] = nv
                    if upd:
                        try:
                            if _db.update("products",
                                f"product_id=eq.{orig['product_id']}", upd):
                                chg += 1
                        except Exception:
                            pass
                if chg:
                    st.success(f"✅ {chg}건 변경 저장")
                    st.rerun()
                else:
                    st.info("변경 사항 없음")

            # ── 휴면 처리 / 휴면 해제 ──
            st.divider()
            with st.expander("🟡 휴면 처리 / 해제", expanded=False):
                ar1, ar2 = st.columns([2, 1])
                with ar1:
                    ar_pid = st.text_input(
                        "처리할 product_id (또는 pn)",
                        key="prod_arch_pid",
                        help="예: P0001 또는 품번 직접")
                with ar2:
                    ar_action = st.radio("작업",
                        ["휴면 처리", "휴면 해제"], horizontal=True,
                        key="prod_arch_action")
                ar_reason = st.text_input("휴면 사유 (휴면 처리 시)",
                    placeholder="예: 12개월 이상 거래 없음, 단종, EOS",
                    key="prod_arch_reason")
                if st.button("실행", key="prod_arch_btn"):
                    if not ar_pid:
                        st.error("product_id / pn 입력 필요")
                    else:
                        target_pid = ar_pid.strip()
                        # pn 으로 입력했으면 product_id 조회
                        if not target_pid.startswith("P"):
                            try:
                                lookup = _db.fetch_one("products",
                                    f"pn=eq.{target_pid}",
                                    "product_id")
                                if lookup:
                                    target_pid = lookup["product_id"]
                                else:
                                    st.error(f"품번 '{ar_pid}' 못 찾음"); st.stop()
                            except Exception as e:
                                st.error(f"조회 실패: {e}"); st.stop()

                        if ar_action == "휴면 처리":
                            payload = {
                                "archived_at": "now()",
                                "archive_reason": ar_reason or "운영자 수동 처리"
                            }
                        else:
                            payload = {"archived_at": None,
                                       "archive_reason": None}
                        try:
                            if _db.update("products",
                                f"product_id=eq.{target_pid}", payload):
                                st.success(
                                    f"✅ {target_pid} {ar_action} 완료")
                                st.rerun()
                            else:
                                st.error("처리 실패")
                        except Exception as e:
                            st.error(f"처리 오류: {e}")

        st.divider()
        st.markdown("##### ➕ 신규 제품 추가")
        with st.form("new_prod_form"):
            npc1, npc2, npc3 = st.columns(3)
            with npc1:
                new_pn = st.text_input("품번 * (고유)",
                    placeholder="예: MRG6-07")
            with npc2:
                new_cust = st.text_input("고객사",
                    placeholder="예: 미진정밀")
            with npc3:
                new_group = st.text_input("제품군",
                    placeholder="예: ADAPTER, FLANGE")

            npc4, npc5, npc6 = st.columns(3)
            with npc4:
                new_subclass = st.text_input("하위분류",
                    placeholder="예: M타입")
            with npc5:
                new_mat = st.text_input("재질",
                    placeholder="예: STS630, SCM440")
            with npc6:
                new_proc = st.selectbox("조달", ["", "도급", "사급"],
                    key="new_prod_proc")

            npc7, npc8 = st.columns([2, 1])
            with npc7:
                new_spec = st.text_input("자재 규격",
                    placeholder="예: ⌀25 × 400, S630")
            with npc8:
                new_drawing = st.text_input("도면번호 (선택)")

            new_caution = st.text_input("주의사항 (선택)",
                placeholder="예: 진공열처리 필수")

            if st.form_submit_button("➕ 제품 추가", type="primary"):
                if not new_pn:
                    st.error("품번은 필수입니다.")
                else:
                    # 중복 체크
                    try:
                        existing = _db.fetch_one("products",
                            f"pn=eq.{new_pn.strip()}",
                            "product_id,pn")
                    except Exception:
                        existing = None
                    if existing:
                        st.error(f"⚠️ 품번 '{new_pn}' 이 이미 존재합니다. "
                                 f"(product_id={existing['product_id']})")
                    else:
                        # 자동 product_id 생성 — P + 다음 번호
                        try:
                            latest = fetch("products", "product_id",
                                "product_id=like.P*&order=product_id.desc",
                                limit=1)
                        except Exception:
                            latest = []
                        if latest and latest[0]["product_id"].startswith("P"):
                            try:
                                next_n = int(latest[0]["product_id"][1:]) + 1
                            except Exception:
                                next_n = 9000
                        else:
                            next_n = 1
                        new_pid = f"P{next_n:04d}"

                        try:
                            _db.insert("products", [{
                                "product_id": new_pid,
                                "pn": new_pn.strip(),
                                "customer": new_cust.strip() or None,
                                "product_group": new_group.strip() or None,
                                "sub_class": new_subclass.strip() or None,
                                "material": new_mat.strip() or None,
                                "raw_material_spec": new_spec.strip() or None,
                                "procurement_type": new_proc or None,
                                "drawing_no": new_drawing.strip() or None,
                                "caution": new_caution.strip() or None,
                                "active": "1",
                            }])
                            st.success(
                                f"✅ 제품 추가: **{new_pid}** | {new_pn}. "
                                f"💰 원가 분석에서 비용 정보 입력하세요."
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(f"추가 실패: {e}")


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
        if mat_q:
            q = mat_q.strip()
            # raw_name / material_id / material_type / spec / main_supplier 모두 OR 검색
            mfq.append(
                f"or=(raw_name.ilike.*{q}*,material_id.ilike.*{q}*,"
                f"material_type.ilike.*{q}*,spec.ilike.*{q}*,"
                f"main_supplier.ilike.*{q}*)"
            )
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
        st.caption("📌 BOM = 제품-자재 + 공정 **수량 관계** 만 관리. "
                   "**qty_per_pc**=제품 1EA당 자재 EA수, **shared_factor**=분할가공 N제품 "
                   "또는 1LOT 처리수량. 단가 정보는 모두 **💰 원가 분석** 페이지에서 관리.")
        bc1, bc2 = st.columns([3, 1])
        with bc1:
            bom_q = st.text_input("제품 또는 자재 검색", placeholder="예: 8HFDV, M001")
        with bc2:
            bom_limit = st.number_input("행수", 20, 500, 100, 20, key="bom_lim")

        # ── 2단계 검색: 검색어가 있으면 먼저 products.pn 으로 product_id 후보 추출 ──
        bfq_parts = ["order=product_id.asc,bom_id.asc"]
        brows = []
        diag = {}  # 디버그용 카운트
        try:
            if bom_q:
                qq = bom_q.strip()
                # (a) products: pn / product_id / product_group / customer 매칭 (archived 포함)
                try:
                    pmatch = fetch("products", "product_id,pn,sub_class,product_group,customer,archived_at",
                        f"or=(pn.ilike.*{qq}*,product_id.ilike.*{qq}*,"
                        f"product_group.ilike.*{qq}*,customer.ilike.*{qq}*)"
                        f"&order=pn.asc",
                        limit=2000)
                except Exception as e:
                    diag["products_err"] = str(e)[:120]; pmatch = []
                diag["products_matched"] = len(pmatch)
                pid_candidates = [p['product_id'] for p in pmatch if p.get('product_id')]
                archived_n = sum(1 for p in pmatch if p.get('archived_at'))
                if archived_n:
                    diag["products_archived"] = archived_n

                # (b) materials: material_id / raw_name / type / spec
                try:
                    mmatch = fetch("materials", "material_id,raw_name",
                        f"or=(material_id.ilike.*{qq}*,raw_name.ilike.*{qq}*,"
                        f"material_type.ilike.*{qq}*,spec.ilike.*{qq}*)",
                        limit=2000)
                except Exception as e:
                    diag["materials_err"] = str(e)[:120]; mmatch = []
                diag["materials_matched"] = len(mmatch)
                mid_candidates = [m['material_id'] for m in mmatch if m.get('material_id')]

                # (c) bom: product_id IN 또는 material_id IN 또는 raw_material_name ilike
                bom_filters = []
                if pid_candidates:
                    pids_in = ",".join(f'"{p}"' for p in pid_candidates[:200])
                    bom_filters.append(f"product_id.in.({pids_in})")
                if mid_candidates:
                    mids_in = ",".join(f'"{m}"' for m in mid_candidates[:200])
                    bom_filters.append(f"material_id.in.({mids_in})")
                bom_filters.append(f"raw_material_name.ilike.*{qq}*")

                if bom_filters:
                    bfq_parts.append(f"or=({','.join(bom_filters)})")
            # 007 적용 후 사용 가능한 컬럼들 (process_type/unit_price/lot_label)
            # 마이그레이션 미적용 시 → 기존 컬럼만 fallback
            full_select = ("bom_id,product_id,material_id,raw_material_name,"
                           "qty_per_pc,shared_factor,source,verification_status,"
                           "process_type,unit_price,lot_label")
            try:
                brows = fetch("bom", full_select,
                    "&".join(bfq_parts), limit=bom_limit)
            except Exception:
                # 007 미적용 환경 fallback
                try:
                    brows = fetch("bom",
                        "bom_id,product_id,material_id,raw_material_name,"
                        "qty_per_pc,shared_factor,source,verification_status",
                        "&".join(bfq_parts), limit=bom_limit)
                    # process_type 기본값 채움
                    for b in brows:
                        b.setdefault("process_type", "MATERIAL")
                        b.setdefault("unit_price", None)
                        b.setdefault("lot_label", None)
                except Exception as e:
                    st.error(f"BOM 검색 실패: {e}"); brows = []
        except Exception as e:
            st.error(f"검색 처리 오류: {e}"); brows = []

        # 제품 정보 join (품번, 제품군)
        if brows:
            pids = list({b['product_id'] for b in brows if b.get('product_id')})
            if pids:
                pids_q = ",".join(f'"{p}"' for p in pids)
                try:
                    prows = fetch("products", "product_id,pn,sub_class,product_group",
                                  f"product_id=in.({pids_q})", limit=1500)
                except Exception: prows = []
                pmap = {p['product_id']: p for p in prows}
                for b in brows:
                    p = pmap.get(b['product_id'], {})
                    b['_pn'] = p.get('pn', '')
                    b['_group'] = p.get('product_group', '')

        st.caption(f"검색 결과: **{len(brows)}건**")

        # 검색어 입력했는데 0건이면 진단 정보 표시
        if bom_q and len(brows) == 0:
            with st.expander("🔍 검색 진단 (왜 0건일까?)", expanded=True):
                st.write(diag if diag else "(진단 정보 없음)")
                st.caption(
                    "- `products_matched=0` → 검색어가 어떤 제품과도 안 맞음 "
                    "(품번 정확히 확인. 예: MRG6-07 vs MRG607 vs mrg6-07)\n"
                    "- `products_matched>0 이지만 BOM 0건` → 해당 제품에 BOM 행이 아직 없음 "
                    "(자재행 추가 영역에서 신규 BOM 등록)\n"
                    "- `materials_matched>0 이지만 BOM 0건` → 해당 자재를 쓰는 제품이 BOM 에 없음\n"
                    "- 모두 0 이면 → 키워드를 더 짧게 / 일부만 (예: 'MRG' 'STS' '환봉')"
                )
            bdf = pd.DataFrame(brows)
            # 컬럼 순서 재배치 — process_type/unit_price/lot_label 포함
            preferred_cols = ['bom_id', 'product_id', '_pn', '_group',
                              'process_type', 'material_id', 'raw_material_name',
                              'qty_per_pc', 'shared_factor', 'unit_price', 'lot_label',
                              'source', 'verification_status']
            preferred_cols = [c for c in preferred_cols if c in bdf.columns]
            bdf = bdf[preferred_cols]
            bedited = st.data_editor(
                bdf,
                column_config={
                    "bom_id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
                    "product_id": st.column_config.TextColumn("제품ID", disabled=True, width="small"),
                    "_pn": st.column_config.TextColumn("품번", disabled=True, width="medium"),
                    "_group": st.column_config.TextColumn("제품군", disabled=True, width="small"),
                    "process_type": st.column_config.SelectboxColumn("구분",
                        options=["MATERIAL","HEAT","SURFACE","OUTSOURCE","PACKING","LABOR","OTHER"],
                        width="small",
                        help="MATERIAL=자재 / HEAT=열처리(LOT) / SURFACE=표면 / OUTSOURCE=외주 등"),
                    "material_id": st.column_config.TextColumn("자재ID", disabled=True, width="small"),
                    "raw_material_name": st.column_config.TextColumn("자재/공정명", width="large"),
                    "qty_per_pc": st.column_config.NumberColumn("자재/PC", format="%.3f",
                        help="제품 1EA당 자재 사용량. 공정행은 보통 1."),
                    "shared_factor": st.column_config.NumberColumn("분할/LOT", format="%.0f",
                        help="자재: 1자재→N제품. 공정: 1 LOT 처리수량."),
                    "unit_price": st.column_config.NumberColumn("LOT 단가 (조회)",
                        format="%.2f", disabled=True,
                        help="단가 편집은 💰 원가 분석 → 단가 관리 탭에서. "
                             "여기서는 조회만 가능."),
                    "lot_label": st.column_config.TextColumn("LOT단위", width="small",
                        help="표시용. 예: LOT, CH, BATCH"),
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
                # BOM 편집 = 수량 관계만. 단가(unit_price)는 원가 분석에서 관리.
                editable_keys = ("qty_per_pc","shared_factor","verification_status",
                                 "process_type","lot_label","raw_material_name")
                for orig, new in zip(brows, bedited.to_dict("records")):
                    upd = {}
                    for k in editable_keys:
                        if k in new and orig.get(k) != new.get(k):
                            v = new.get(k)
                            if v == "":
                                v = None
                            upd[k] = v
                    if upd:
                        if _db.update("bom", f"bom_id=eq.{orig['bom_id']}", upd):
                            chg += 1
                if chg: st.success(f"✅ {chg}건 update"); st.rerun()
                else: st.info("변경 사항 없음")

            st.divider()
            st.markdown("##### ➕ 신규 BOM 자재행 추가")
            st.caption("**제품은 품번**, **자재는 자재명**으로 검색하세요. "
                       "BOM 은 수량 정보만 관리. 가격은 매입/원가에서 자동 산정.")

            ar1, ar2 = st.columns(2)
            with ar1:
                p_search = st.text_input("🔍 제품 검색 (품번/품명/고객사)",
                    placeholder="예: MRG6-07 또는 FLANGE 또는 명진",
                    key="bom_new_p_search")
                p_pick_pid = None
                p_pick_pn = None
                if p_search:
                    qq = p_search.strip()
                    try:
                        p_found = fetch("products", "product_id,pn,customer",
                            f"or=(pn.ilike.*{qq}*,customer.ilike.*{qq}*)"
                            f"&archived_at=is.null&order=pn.asc", limit=30)
                    except Exception:
                        p_found = []
                    if p_found:
                        p_labels = [f"{p['pn']}  |  {p.get('customer','-')}" for p in p_found]
                        p_sel = st.selectbox(f"제품 선택 ({len(p_found)}건)",
                            p_labels, key="bom_new_p_pick")
                        if p_sel:
                            picked = p_found[p_labels.index(p_sel)]
                            p_pick_pid = picked["product_id"]
                            p_pick_pn = picked["pn"]
                    else:
                        st.warning("일치하는 제품 없음")

            with ar2:
                m_search = st.text_input("🔍 자재 검색 (자재명/규격/재질)",
                    placeholder="예: 환봉 또는 STS304 또는 SCM440",
                    key="bom_new_m_search")
                m_pick_mid = None
                m_pick_name = None
                if m_search:
                    qq = m_search.strip()
                    try:
                        m_found = fetch("materials",
                            "material_id,raw_name,material_type,spec",
                            f"or=(raw_name.ilike.*{qq}*,material_type.ilike.*{qq}*,"
                            f"spec.ilike.*{qq}*)&order=raw_name.asc", limit=30)
                    except Exception:
                        m_found = []
                    if m_found:
                        m_labels = [
                            f"{m['raw_name']} · {m.get('material_type','-')} · {m.get('spec','-')}"
                            for m in m_found
                        ]
                        m_sel = st.selectbox(f"자재 선택 ({len(m_found)}건)",
                            m_labels, key="bom_new_m_pick")
                        if m_sel:
                            picked_m = m_found[m_labels.index(m_sel)]
                            m_pick_mid = picked_m["material_id"]
                            m_pick_name = picked_m["raw_name"]
                    else:
                        st.warning("일치하는 자재 없음")

            ar3, ar4, ar5 = st.columns([1, 1, 2])
            with ar3:
                new_qpc = st.number_input("자재/PC (EA)", min_value=0.0,
                    value=1.0, step=0.1, key="bom_new_qpc",
                    help="제품 1EA당 자재 사용량")
            with ar4:
                new_sf = st.number_input("1자재→N제품 (분할가공)",
                    min_value=1, value=1, step=1, key="bom_new_sf",
                    help="환봉 1개에서 N제품 분할가공 시 N")
            with ar5:
                st.caption(
                    f"선택됨 → "
                    f"제품: **{p_pick_pn or '(미선택)'}** · "
                    f"자재: **{m_pick_name or '(미선택)'}**"
                )

            # 단가/원가 미리보기는 💰 원가 분석 페이지에서 확인하세요.

            if st.button("➕ 자재행 추가", key="bom_new_btn", type="primary"):
                if not p_pick_pid or not m_pick_mid:
                    st.error("제품과 자재를 모두 선택해주세요.")
                else:
                    try:
                        _db.insert("bom", [{
                            "product_id": p_pick_pid,
                            "material_id": m_pick_mid,
                            "raw_material_name": m_pick_name,
                            "qty_per_pc": new_qpc,
                            "shared_factor": new_sf,
                            "process_type": "MATERIAL",
                            "source": "MANUAL",
                            "verification_status": "확인완료",
                        }])
                        st.success(
                            f"✅ 자재행 추가: **{p_pick_pn}** ↔ **{m_pick_name}** "
                            f"(qty/PC={new_qpc}, 분할={new_sf})"
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"추가 실패: {e}")

            st.divider()
            st.markdown("##### ➕ 신규 공정행 추가 (열처리/외주/표면 등)")
            st.caption(
                "공정행 = **수량 관계** 만 입력 (어떤 공정 + LOT 처리수량). "
                "**LOT 단가는 💰 원가 분석 → 단가 관리** 에서 입력하세요. "
                "공식: per_pc = LOT단가 × qty/PC ÷ LOT처리수량 (단가 입력 후 자동 계산)."
            )

            pr1, pr2 = st.columns(2)
            with pr1:
                pp_search = st.text_input("🔍 제품 검색",
                    placeholder="예: MRG6-07",
                    key="bom_proc_p_search")
                pp_pick_pid = None
                pp_pick_pn = None
                if pp_search:
                    qq = pp_search.strip()
                    try:
                        pp_found = fetch("products", "product_id,pn,customer",
                            f"or=(pn.ilike.*{qq}*,customer.ilike.*{qq}*)"
                            f"&archived_at=is.null&order=pn.asc", limit=30)
                    except Exception:
                        pp_found = []
                    if pp_found:
                        pp_labels = [f"{p['pn']}  |  {p.get('customer','-')}" for p in pp_found]
                        pp_sel = st.selectbox(f"제품 선택 ({len(pp_found)}건)",
                            pp_labels, key="bom_proc_p_pick")
                        if pp_sel:
                            picked = pp_found[pp_labels.index(pp_sel)]
                            pp_pick_pid = picked["product_id"]
                            pp_pick_pn = picked["pn"]
                    else:
                        st.warning("일치하는 제품 없음")

            with pr2:
                proc_type = st.selectbox("공정 종류 *",
                    ["HEAT", "SURFACE", "OUTSOURCE", "PACKING", "LABOR", "OTHER"],
                    format_func=lambda v: {
                        "HEAT": "🔥 HEAT (열처리)",
                        "SURFACE": "💎 SURFACE (표면처리)",
                        "OUTSOURCE": "🏭 OUTSOURCE (외주가공)",
                        "PACKING": "📦 PACKING (포장)",
                        "LABOR": "👷 LABOR (직접노무)",
                        "OTHER": "❔ OTHER (기타)",
                    }.get(v, v),
                    key="bom_proc_type")

            pr3, pr4, pr_lbl = st.columns([1, 1, 1])
            with pr3:
                proc_qty = st.number_input("qty/PC", min_value=0.0,
                    value=1.0, step=0.1, key="bom_proc_qty",
                    help="제품 1EA당 공정 횟수. 보통 1.")
            with pr4:
                proc_lot_size = st.number_input("LOT 처리수량",
                    min_value=1, value=1, step=1, key="bom_proc_lot",
                    help="1 LOT/CH 에서 처리되는 제품 수. 예: 5000EA")
            with pr_lbl:
                proc_lot_label = st.selectbox("LOT 단위",
                    ["", "LOT", "CH", "BATCH"], key="bom_proc_label",
                    help="표시용")

            pr6, pr7 = st.columns([3, 2])
            with pr6:
                proc_name = st.text_input("공정 설명",
                    placeholder="예: 진공열처리, 무전해Ni도금, 외주황삭",
                    key="bom_proc_name")
            with pr7:
                # 공정 거래처 선택 (옵션) — vendor_group 매핑
                try:
                    proc_vendors = fetch("vendors", "vendor_id,name",
                        "vendor_group=in.(\"OUTSOURCE\",\"HEAT_TREAT\",\"SURFACE\")"
                        "&archived_at=is.null&order=name.asc", limit=200)
                except Exception:
                    proc_vendors = []
                v_labels = ["(선택 안 함)"] + [
                    f"{v['vendor_id']} | {v['name']}" for v in proc_vendors
                ]
                v_pick = st.selectbox("공정 거래처 (선택)",
                    v_labels, key="bom_proc_vendor_pick")

            if st.button("➕ 공정행 추가", key="bom_proc_btn", type="primary"):
                if not pp_pick_pid:
                    st.error("제품을 선택해주세요.")
                else:
                    record = {
                        "product_id": pp_pick_pid,
                        "material_id": None,
                        "raw_material_name": proc_name or proc_type,
                        "process_type": proc_type,
                        "qty_per_pc": proc_qty,
                        "shared_factor": proc_lot_size,
                        "lot_label": proc_lot_label or None,
                        "source": "MANUAL",
                        "verification_status": "확인완료",
                    }
                    if v_pick != "(선택 안 함)":
                        try:
                            record["process_vendor_id"] = int(v_pick.split(" | ")[0])
                        except (ValueError, IndexError):
                            pass
                    try:
                        _db.insert("bom", [record])
                        st.success(
                            f"✅ {proc_type} 공정행 추가: **{pp_pick_pn}** "
                            f"(LOT 처리 {proc_lot_size}EA). "
                            f"단가는 💰 원가 분석 → 단가 관리에서 입력하세요."
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"추가 실패: {e}")

    # ─── Tab: 데이터 제외 규칙 ───
    with tab_excl:
        st.caption(
            "특정 거래처의 특정 기간 데이터(예: 구ERP 마이그레이션 이전)를 "
            "**평균/마진 계산에서 제외**합니다. 원본은 `sales_ledger` 에 보존."
        )
        st.markdown("##### 현재 규칙")
        try:
            excl_rows = fetch("sales_data_exclusion",
                "id,customer_pattern,before_date,after_date,reason,active,created_at",
                "order=created_at.desc", limit=200)
            excl_available = True
        except Exception as e:
            excl_rows = []
            excl_available = False
            st.warning(
                f"⚠️ `sales_data_exclusion` 테이블이 없습니다. "
                f"Migration 012 적용 필요. ({str(e)[:80]})"
            )

        if excl_available:
            if not excl_rows:
                st.info("등록된 제외 규칙 없음.")
            else:
                df_e = pd.DataFrame(excl_rows)
                # PostgREST → str/None → Streamlit DateColumn 호환 형식으로 변환
                df_e["before_date"] = pd.to_datetime(
                    df_e.get("before_date"), errors="coerce"
                ).dt.date
                df_e["after_date"] = pd.to_datetime(
                    df_e.get("after_date"), errors="coerce"
                ).dt.date
                df_e["active"] = df_e["active"].astype(bool)
                df_e["id"] = pd.to_numeric(df_e["id"], errors="coerce").astype("Int64")
                df_e["customer_pattern"] = df_e["customer_pattern"].fillna("").astype(str)
                df_e["reason"] = df_e["reason"].fillna("").astype(str)

                edited_e = st.data_editor(
                    df_e[["id","customer_pattern","before_date","after_date",
                          "reason","active"]],
                    column_config={
                        "id": st.column_config.NumberColumn("ID",
                            disabled=True, width="small"),
                        "customer_pattern": st.column_config.TextColumn(
                            "거래처 패턴 (ILIKE)", width="medium",
                            help="예: %미진% 은 '미진' 포함 거래처 모두 매칭"),
                        "before_date": st.column_config.DateColumn(
                            "이 날짜 이전 제외", width="small",
                            format="YYYY-MM-DD"),
                        "after_date": st.column_config.DateColumn(
                            "이 날짜 이후 제외", width="small",
                            format="YYYY-MM-DD"),
                        "reason": st.column_config.TextColumn("사유",
                            width="large"),
                        "active": st.column_config.CheckboxColumn("활성",
                            width="small"),
                    },
                    hide_index=True, use_container_width=True,
                    num_rows="fixed", key="excl_editor"
                )
                if st.button("💾 변경 저장", type="primary", key="excl_save"):
                    import datetime as _dt
                    chg = 0
                    for o, n in zip(excl_rows, edited_e.to_dict("records")):
                        upd = {}
                        for k in ("customer_pattern","before_date","after_date",
                                  "reason","active"):
                            ov = o.get(k); nv = n.get(k)
                            # NaN / NaT 정리
                            if isinstance(nv, float) and pd.isna(nv):
                                nv = None
                            try:
                                if nv is not None and pd.isna(nv):
                                    nv = None
                            except Exception:
                                pass
                            # date 객체 → ISO 문자열
                            if isinstance(nv, (_dt.date, _dt.datetime)):
                                nv = nv.strftime("%Y-%m-%d")
                            # 원본 ov 도 같은 형식으로 정규화 비교
                            ov_norm = ov
                            if isinstance(ov, str) and "T" in ov:
                                ov_norm = ov.split("T")[0]
                            if str(ov_norm or "") != str(nv or ""):
                                upd[k] = nv
                        if upd:
                            try:
                                if _db.update("sales_data_exclusion",
                                    f"id=eq.{o['id']}", upd):
                                    chg += 1
                            except Exception as e:
                                st.warning(f"id={o['id']} 저장 실패: {e}")
                    if chg:
                        st.success(f"✅ {chg}건 변경 저장")
                        st.rerun()
                    else:
                        st.info("변경 사항 없음")

            st.divider()
            st.markdown("##### ➕ 신규 제외 규칙 추가")
            with st.form("new_excl_form"):
                nec1, nec2, nec3 = st.columns([2, 1, 1])
                with nec1:
                    new_pat = st.text_input(
                        "거래처 패턴 (ILIKE)",
                        placeholder="예: %미진% / %두산% / %HDX%",
                        help="% 는 와일드카드. '%미진%' 은 '미진' 포함 모두.")
                with nec2:
                    new_before = st.date_input("이 날짜 이전 제외",
                        value=None, key="new_excl_before")
                with nec3:
                    new_after = st.date_input("이 날짜 이후 제외",
                        value=None, key="new_excl_after")
                new_reason = st.text_input("사유",
                    placeholder="예: 구ERP 마이그레이션 전 데이터 가격 정합성 부족")
                add_btn = st.form_submit_button("➕ 규칙 추가",
                    type="primary")

                if add_btn:
                    if not new_pat:
                        st.error("거래처 패턴은 필수입니다.")
                    elif not new_before and not new_after:
                        st.error("before/after 중 하나는 반드시 지정해야 합니다.")
                    else:
                        record = {
                            "customer_pattern": new_pat,
                            "before_date": str(new_before) if new_before else None,
                            "after_date":  str(new_after)  if new_after  else None,
                            "reason": new_reason or None,
                            "active": True,
                        }
                        try:
                            _db.insert("sales_data_exclusion", [record])
                            st.success(f"✅ 규칙 추가됨: {new_pat}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"추가 실패: {e}")

            # 영향 미리보기
            if excl_rows:
                st.divider()
                st.markdown("##### 📊 제외 영향 미리보기")
                if st.button("🔍 활성 규칙 적용 시 제외되는 거래 수 계산",
                             key="excl_preview_btn"):
                    total_excluded = 0
                    breakdown = []
                    for r in excl_rows:
                        if not r.get("active"):
                            continue
                        filt = [f"customer=ilike.{r['customer_pattern']}"]
                        if r.get("before_date"):
                            filt.append(f"item_date=lt.{r['before_date']}")
                        if r.get("after_date"):
                            filt.append(f"item_date=gt.{r['after_date']}")
                        try:
                            from db import count_rows as _cnt
                            # count via Range header
                            import requests
                            url = (f"{st.secrets['supabase']['url']}/rest/v1/"
                                   f"sales_ledger?select=*&limit=1&" +
                                   "&".join(filt))
                            sr = st.secrets["supabase"]["service_role_key"]
                            rr = requests.get(url, headers={
                                "apikey": sr, "Authorization": f"Bearer {sr}",
                                "Prefer": "count=exact"}, timeout=15)
                            cr = rr.headers.get("content-range", "")
                            n = 0
                            if "/" in cr:
                                nstr = cr.split("/")[-1]
                                n = int(nstr) if nstr.isdigit() else 0
                            total_excluded += n
                            breakdown.append({
                                "패턴": r['customer_pattern'],
                                "기간": f"{r.get('before_date') or '-'} ~ {r.get('after_date') or '-'}",
                                "제외 건수": n,
                                "사유": r.get('reason') or "-"
                            })
                        except Exception as e:
                            breakdown.append({
                                "패턴": r['customer_pattern'],
                                "기간": "ERR",
                                "제외 건수": "-",
                                "사유": str(e)[:60]
                            })
                    st.metric("🎯 총 제외 거래", f"{total_excluded:,}건")
                    if breakdown:
                        st.dataframe(pd.DataFrame(breakdown),
                            use_container_width=True, hide_index=True)


    # ─── Tab: 매입↔자재 매핑 (Phase 2 스캐폴딩) ───
    with tab_map:
        st.caption(
            "📌 `purchase_ledger.matched_material_id` 를 채워서 자재별 시점 단가가 "
            "자동 계산되도록 합니다. (Migration 007 적용 필요)"
        )

        # 매핑 현황 카드
        try:
            total_pl = _db.fetch_one("purchase_ledger",
                "matched_material_id=is.null", "ledger_id")
            mapped_pl = _db.fetch_one("purchase_ledger",
                "matched_material_id=not.is.null", "ledger_id")
            map_view_ok = True
        except Exception as e:
            map_view_ok = False
            st.warning(f"⚠️ Migration 007 (`matched_material_id` 컬럼) 적용 필요: {e}")

        if map_view_ok:
            try:
                unmapped = fetch("purchase_ledger",
                    "ledger_id,trade_date,vendor,vendor_normalized,item,category,"
                    "qty,unit,unit_price,kg_price,ea_price",
                    "matched_material_id=is.null"
                    "&category=like.MAT_*"
                    "&order=trade_date.desc",
                    limit=500)
            except Exception as e:
                st.error(f"미매핑 조회 실패: {e}"); unmapped = []

            # 카테고리 필터
            cat_choices = sorted({u.get("category") or "" for u in unmapped if u.get("category")})
            mc1, mc2 = st.columns([2, 1])
            with mc1:
                cat_pick = st.selectbox("카테고리", ["전체"] + cat_choices,
                                        key="map_cat")
            with mc2:
                search_item = st.text_input("품목명 검색", key="map_search_item")

            view_rows = unmapped
            if cat_pick != "전체":
                view_rows = [r for r in view_rows if r.get("category") == cat_pick]
            if search_item:
                ssi = search_item.strip().lower()
                view_rows = [r for r in view_rows
                             if ssi in (r.get("item") or "").lower()]

            st.caption(
                f"매입 매핑 현황 — **미매핑 매입(MAT_*):** {len(unmapped):,}건 / "
                f"표시: **{len(view_rows):,}건**"
            )

            if not view_rows:
                st.info("표시할 미매핑 거래 없음. (또는 007 적용 후 데이터 없음)")
            else:
                # 동일 item 그룹핑 → 한 번 매핑 시 일괄 적용 후보
                from collections import defaultdict
                groups = defaultdict(list)
                for r in view_rows:
                    key = (r.get("item") or "", r.get("vendor_normalized") or "")
                    groups[key].append(r)

                # 상위 그룹 (거래 빈도 순)
                sorted_groups = sorted(groups.items(),
                                       key=lambda kv: -len(kv[1]))[:50]

                # 자재 목록 한 번만 로드
                try:
                    all_mats = fetch("materials",
                        "material_id,raw_name,material_type,spec",
                        "order=raw_name.asc", limit=2000)
                except Exception:
                    all_mats = []
                mat_labels = [f"{m['material_id']} | {m.get('raw_name','')}" for m in all_mats]

                st.markdown("##### 그룹별 매핑 (동일 품목 → 일괄 적용)")
                for (item, vendor), rows in sorted_groups[:20]:
                    n = len(rows)
                    avg_p = sum(float(r.get("unit_price") or 0) for r in rows) / n
                    with st.expander(
                        f"📦 **{item or '(품목명 없음)'}**  "
                        f"· {vendor or '-'}  · {n}건  · 평균 {avg_p:,.0f}원",
                        expanded=False
                    ):
                        gc1, gc2 = st.columns([3, 1])
                        with gc1:
                            sel = st.selectbox(
                                "매핑할 자재", ["(선택)"] + mat_labels,
                                key=f"map_sel_{hash((item, vendor)) & 0xFFFF}"
                            )
                        with gc2:
                            apply_btn = st.button("✅ 일괄 매핑",
                                key=f"map_btn_{hash((item, vendor)) & 0xFFFF}")
                        if apply_btn and sel != "(선택)":
                            mid = sel.split(" | ")[0]
                            ok_n, fail_n = 0, 0
                            for r in rows:
                                try:
                                    if _db.update("purchase_ledger",
                                        f"ledger_id=eq.{r['ledger_id']}",
                                        {"matched_material_id": mid,
                                         "mapping_status": "MANUAL"}):
                                        ok_n += 1
                                    else:
                                        fail_n += 1
                                except Exception:
                                    fail_n += 1
                            st.success(
                                f"✅ {ok_n}건 매핑 완료 → {mid}"
                                + (f" / 실패 {fail_n}건" if fail_n else "")
                            )
                            st.rerun()

                st.divider()
                st.markdown("##### 개별 거래 매핑 (필요 시)")
                st.caption("위 그룹에 안 묶이거나 일회성 거래만 별도 매핑.")
                st.dataframe(
                    pd.DataFrame(view_rows[:200])[[
                        "trade_date", "vendor", "item", "category",
                        "qty", "unit", "unit_price", "kg_price"
                    ]],
                    use_container_width=True, hide_index=True, height=320
                )

    # ─── Tab: 마스터/연결 점검 ───
    with tab2:
        st.caption(
            "📌 마스터 데이터·매핑 키·BOM·원가 신뢰도를 한 화면에서 점검합니다. "
            "정비 우선순위 결정에 사용."
        )

        if not st.button("🔄 진단 실행 / 새로고침", type="primary", key="diag_run"):
            st.info("위 버튼을 눌러 진단을 실행하세요.")
        else:
            with st.spinner("진단 중..."):
                # PostgREST count=exact 가 Content-Range 헤더에 / 뒤 숫자로 총수 반환
                def _cnt(table, filter_query=""):
                    try:
                        import requests
                        url = f"{st.secrets['supabase']['url']}/rest/v1/{table}?select=*&limit=1"
                        if filter_query:
                            url += f"&{filter_query}"
                        sr = st.secrets["supabase"]["service_role_key"]
                        r = requests.get(url, headers={
                            "apikey": sr, "Authorization": f"Bearer {sr}",
                            "Prefer": "count=exact"}, timeout=15)
                        if r.status_code in (200, 206):
                            cr = r.headers.get("content-range", "")
                            if "/" in cr:
                                n = cr.split("/")[-1]
                                return int(n) if n.isdigit() else 0
                        return 0
                    except Exception:
                        return -1  # err

                # ═══════════════ A. 제품 마스터 ═══════════════
                st.markdown("### 🅰 제품 마스터")
                ac1, ac2, ac3, ac4 = st.columns(4)
                total_p = _cnt("products")
                active_p = _cnt("products", "archived_at=is.null")
                arch_p = total_p - active_p if total_p >= 0 else 0
                ac1.metric("전체 제품", f"{total_p:,}")
                ac2.metric("활성 (archived_at IS NULL)",
                           f"{active_p:,}",
                           f"{active_p/total_p*100:.0f}%" if total_p else None)
                ac3.metric("휴면", f"{arch_p:,}")
                # 컬럼 보유율
                has_cost = _cnt("products",
                    "archived_at=is.null&estimated_cost_per_pc=gt.0")
                ac4.metric("estimated_cost_per_pc > 0",
                           f"{has_cost:,}",
                           f"{has_cost/active_p*100:.0f}%" if active_p else None)

                ac5, ac6, ac7, ac8 = st.columns(4)
                has_mat_unit = _cnt("products",
                    "archived_at=is.null&material_unit_price=gt.0")
                ac5.metric("material_unit_price > 0",
                           f"{has_mat_unit:,}",
                           f"{has_mat_unit/active_p*100:.0f}%" if active_p else None)
                has_heat = _cnt("products",
                    "archived_at=is.null&heat_treat_per_pc=gt.0")
                ac6.metric("heat_treat_per_pc > 0",
                           f"{has_heat:,}",
                           f"{has_heat/active_p*100:.0f}%" if active_p else None)
                has_surface = _cnt("products",
                    "archived_at=is.null&surface_per_pc=gt.0")
                ac7.metric("surface_per_pc > 0",
                           f"{has_surface:,}",
                           f"{has_surface/active_p*100:.0f}%" if active_p else None)
                has_out = _cnt("products",
                    "archived_at=is.null&outsourcing_per_pc=gt.0")
                ac8.metric("outsourcing_per_pc > 0",
                           f"{has_out:,}",
                           f"{has_out/active_p*100:.0f}%" if active_p else None)

                # 제품군 분포
                try:
                    pg_rows = fetch("products",
                        "product_group", "archived_at=is.null", limit=2000)
                    from collections import Counter
                    pg_count = Counter(p.get("product_group") or "(없음)"
                                       for p in pg_rows)
                    pg_df = pd.DataFrame(
                        pg_count.most_common(15), columns=["제품군", "건수"])
                    st.markdown("##### 제품군 분포 (상위 15)")
                    st.dataframe(pg_df, use_container_width=True,
                                 hide_index=True, height=240)
                except Exception as e:
                    st.caption(f"제품군 분포 조회 실패: {e}")

                st.divider()

                # ═══════════════ B. 자재 마스터 ═══════════════
                st.markdown("### 🅱 자재 마스터")
                bc1, bc2, bc3, bc4 = st.columns(4)
                total_m = _cnt("materials")
                m_with_type = _cnt("materials", "material_type=not.is.null")
                m_with_spec = _cnt("materials", "spec=not.is.null")
                m_with_sup = _cnt("materials", "main_supplier=not.is.null")
                bc1.metric("전체 자재", f"{total_m:,}")
                bc2.metric("material_type 보유",
                           f"{m_with_type:,}",
                           f"{m_with_type/total_m*100:.0f}%" if total_m else None)
                bc3.metric("spec 보유",
                           f"{m_with_spec:,}",
                           f"{m_with_spec/total_m*100:.0f}%" if total_m else None)
                bc4.metric("main_supplier 보유",
                           f"{m_with_sup:,}",
                           f"{m_with_sup/total_m*100:.0f}%" if total_m else None)

                # 자재 type 분포
                try:
                    mt_rows = fetch("materials", "material_type", "", limit=2000)
                    mt_count = Counter(m.get("material_type") or "(없음)"
                                       for m in mt_rows)
                    mt_df = pd.DataFrame(
                        mt_count.most_common(10), columns=["material_type", "건수"])
                    st.markdown("##### 자재 분류 분포")
                    st.dataframe(mt_df, use_container_width=True,
                                 hide_index=True, height=200)
                except Exception as e:
                    st.caption(f"자재 분류 조회 실패: {e}")

                st.divider()

                # ═══════════════ C. BOM 상태 ═══════════════
                st.markdown("### 🅒 BOM 상태")
                cc1, cc2, cc3, cc4 = st.columns(4)
                total_bom = _cnt("bom")
                # process_type 별 (007 적용 시)
                try:
                    bom_mat = _cnt("bom", "process_type=eq.MATERIAL")
                except Exception:
                    bom_mat = 0
                bom_process = total_bom - bom_mat if total_bom >= 0 else 0
                cc1.metric("BOM 행 전체", f"{total_bom:,}")
                cc2.metric("MATERIAL 행", f"{bom_mat:,}")
                cc3.metric("공정행 (HEAT/SURFACE/...)",
                           f"{bom_process:,}")
                # BOM 보유 제품 수
                try:
                    pid_rows = fetch("bom", "product_id", "", limit=10000)
                    bom_pids = {b['product_id'] for b in pid_rows if b.get('product_id')}
                    cc4.metric("BOM 보유 제품 수",
                               f"{len(bom_pids):,}",
                               f"{len(bom_pids)/active_p*100:.0f}% of 활성"
                               if active_p else None)
                except Exception:
                    cc4.metric("BOM 보유 제품 수", "?")

                cc5, cc6, cc7 = st.columns(3)
                # 분할가공 (shared_factor > 1)
                sf_gt1 = _cnt("bom", "shared_factor=gt.1")
                cc5.metric("shared_factor > 1 행",
                           f"{sf_gt1:,}",
                           "분할가공 케이스" if sf_gt1 > 0 else None)
                # verification 분포
                try:
                    vs_rows = fetch("bom", "verification_status", "", limit=10000)
                    confirmed = sum(1 for v in vs_rows
                                    if v.get("verification_status") == "확인완료")
                    cc6.metric("확인완료 행", f"{confirmed:,}",
                               f"{confirmed/total_bom*100:.0f}%"
                               if total_bom else None)
                    auto_n = sum(1 for v in vs_rows
                                 if (v.get("verification_status") or "").startswith("AUTO"))
                    cc7.metric("AUTO-* (미확인) 행", f"{auto_n:,}",
                               "검증 필요" if auto_n > 0 else None,
                               delta_color="inverse")
                except Exception:
                    pass

                # process_type 별 분포
                try:
                    pt_rows = fetch("bom", "process_type", "", limit=10000)
                    pt_count = Counter(b.get("process_type") or "(없음)"
                                       for b in pt_rows)
                    pt_df = pd.DataFrame(
                        sorted(pt_count.items(), key=lambda x: -x[1]),
                        columns=["process_type", "건수"])
                    st.markdown("##### process_type 분포")
                    st.dataframe(pt_df, use_container_width=True,
                                 hide_index=True, height=220)
                except Exception:
                    st.caption("process_type 분포: 007 마이그레이션 미적용 또는 조회 실패")

                st.divider()

                # ═══════════════ D. 거래처 ═══════════════
                st.markdown("### 🅓 거래처")
                dc1, dc2, dc3, dc4 = st.columns(4)
                total_v = _cnt("vendors")
                v_with_group = _cnt("vendors", "vendor_group=not.is.null")
                v_active = _cnt("vendors", "archived_at=is.null")
                dc1.metric("전체 거래처", f"{total_v:,}")
                dc2.metric("활성", f"{v_active:,}",
                           f"{v_active/total_v*100:.0f}%" if total_v else None)
                dc3.metric("vendor_group 보유",
                           f"{v_with_group:,}",
                           f"{v_with_group/total_v*100:.0f}%" if total_v else None)
                v_out_proc = _cnt("vendors",
                    "vendor_group=in.(\"OUTSOURCE\",\"HEAT_TREAT\",\"SURFACE\")")
                dc4.metric("공정 거래처 (외주/열처리/표면)",
                           f"{v_out_proc:,}")

                st.divider()

                # ═══════════════ E. 데이터 연결 (매핑 키) ═══════════════
                st.markdown("### 🅔 데이터 연결 상태")
                ec1, ec2, ec3, ec4 = st.columns(4)
                # 매출 ledger 매핑
                total_sl = _cnt("sales_ledger")
                sl_mapped = _cnt("sales_ledger", "product_id=not.is.null")
                ec1.metric("매출 ledger 전체", f"{total_sl:,}")
                ec2.metric("product_id 매핑",
                           f"{sl_mapped:,}",
                           f"{sl_mapped/total_sl*100:.0f}%" if total_sl else None)

                # 매입 ledger 매핑
                total_pl = _cnt("purchase_ledger")
                pl_mapped_pn = _cnt("purchase_ledger", "matched_pn=not.is.null")
                ec3.metric("매입 ledger 전체", f"{total_pl:,}")
                ec4.metric("matched_pn 매핑",
                           f"{pl_mapped_pn:,}",
                           f"{pl_mapped_pn/total_pl*100:.0f}%" if total_pl else None)

                ec5, ec6 = st.columns(2)
                # 007 컬럼 (매핑 매핑)
                try:
                    pl_mapped_mat = _cnt("purchase_ledger",
                        "matched_material_id=not.is.null")
                    ec5.metric("matched_material_id 매핑",
                               f"{pl_mapped_mat:,}",
                               f"{pl_mapped_mat/total_pl*100:.0f}%"
                               if total_pl else None,
                               help="향후 매입 입력 화면에서 자동 채움")
                except Exception:
                    ec5.metric("matched_material_id", "007 적용 필요")
                # production_log
                total_prod = _cnt("production_log")
                try:
                    prod_mapped = _cnt("production_log", "product_id=not.is.null")
                    ec6.metric(f"production_log product_id ({total_prod:,}건 중)",
                               f"{prod_mapped:,}",
                               f"{prod_mapped/total_prod*100:.0f}%"
                               if total_prod else None,
                               help="Stage 4 활성 시 채움")
                except Exception:
                    ec6.metric("production_log", "007 적용 필요")

                st.divider()

                # ═══════════════ F. 원가 신뢰도 (product_cost_full_v) ═══════════════
                st.markdown("### 🅕 원가 데이터 신뢰도")
                try:
                    cs_rows = fetch("product_cost_full_v",
                        "cost_source,total_sales_12m",
                        "archived_at=is.null", limit=5000)
                    cs_count = Counter(r.get("cost_source") or "?" for r in cs_rows)
                    fc1, fc2, fc3, fc4 = st.columns(4)
                    fc1.metric("🟢 BOM_FULL", f"{cs_count.get('BOM_FULL', 0):,}")
                    fc2.metric("🟡 BOM_PARTIAL",
                               f"{cs_count.get('BOM_PARTIAL', 0):,}")
                    fc3.metric("🟠 LEGACY_ONLY",
                               f"{cs_count.get('LEGACY_ONLY', 0):,}")
                    fc4.metric("🔴 NO_DATA",
                               f"{cs_count.get('NO_DATA', 0):,}",
                               "정비 우선순위 ↑" if cs_count.get('NO_DATA', 0) > 100
                               else None,
                               delta_color="inverse")

                    # NO_DATA 중 매출 있는 것 (진짜 정비 대상)
                    nd_with_sale = sum(
                        1 for r in cs_rows
                        if r.get("cost_source") == "NO_DATA"
                        and (r.get("total_sales_12m") or 0) > 0
                    )
                    if nd_with_sale > 0:
                        st.warning(
                            f"⚠️ **NO_DATA 중 12M 매출 있는 품목: {nd_with_sale}건** "
                            f"— 실제 거래되는데 원가 데이터 없음. 최우선 정비 대상."
                        )
                except Exception as e:
                    st.caption(f"원가 신뢰도 조회 실패 (009 적용 필요): {e}")

                st.divider()

                # ═══════════════ G. 정비 우선순위 추천 ═══════════════
                st.markdown("### 🎯 정비 우선순위 추천")
                priority = []
                try:
                    if cs_count.get('LEGACY_ONLY', 0) > 0:
                        priority.append(
                            (1, f"**LEGACY_ONLY {cs_count.get('LEGACY_ONLY',0)}건**",
                             "BOM 행 1개만 추가하면 BOM_FULL 격상. 가장 ROI 높음.",
                             "BOM 편집 → 자재행 추가"))
                    if nd_with_sale > 0:
                        priority.append(
                            (2, f"**NO_DATA 중 매출있음 {nd_with_sale}건**",
                             "실거래 품목이라 원가 부재가 마진 분석 왜곡. 시급.",
                             "원가 편집 + BOM 등록"))
                    if cs_count.get('BOM_PARTIAL', 0) > 0:
                        priority.append(
                            (3, f"**BOM_PARTIAL {cs_count.get('BOM_PARTIAL',0)}건**",
                             "BOM 있으나 자재 단가 누락. 단가 보완으로 BOM_FULL 격상.",
                             "원가 편집 → material_unit_price 갱신"))
                except NameError:
                    pass
                # BOM 미보유 활성 제품
                try:
                    no_bom = active_p - len(bom_pids)
                    if no_bom > 100:
                        priority.append(
                            (4, f"**BOM 미보유 활성 제품 {no_bom:,}건**",
                             "전체 활성 제품 중 BOM 없는 비율 큼. BOM 등록 캠페인 필요.",
                             "BOM 편집"))
                except Exception:
                    pass
                # 매입 자재 매핑
                try:
                    if pl_mapped_mat == 0:
                        priority.append(
                            (5, "**matched_material_id 매핑 0%**",
                             "향후 매입 입력 화면에서 자동 채움 — 현재 정책상 대기.",
                             "(우선순위 낮음)"))
                except Exception:
                    pass

                if priority:
                    pdf = pd.DataFrame(priority, columns=["순위", "항목", "이유", "이동"])
                    st.dataframe(pdf, use_container_width=True, hide_index=True)
                else:
                    st.info("정비 우선 항목이 없습니다. (이상적 상태 또는 진단 데이터 부족)")


elif page == "🚀 BOM 빠른 정비":
    st.subheader("🚀 BOM 빠른 정비")
    st.caption(
        "1제품의 자재·공정행을 한 화면에서 입력/수정하고, 동일 BOM 구조를 분기 제품에 일괄 복사합니다. "
        "제품 마스터 정비 속도를 크게 올려줍니다."
    )

    if not DB_AVAILABLE:
        st.error("DB 연결이 활성화되지 않았습니다."); st.stop()

    import db as _db
    import pandas as pd

    # ════════════════════════════════════════════════
    # 1. 제품 검색 + 선택
    # ════════════════════════════════════════════════
    s1, s2, s3 = st.columns([3, 1, 1])
    with s1:
        fq = st.text_input("🔍 제품 검색 (품번/품명/고객사/제품군)",
            placeholder="예: MRG6-07, FLANGE, 미진정밀",
            key="fast_search")
    with s2:
        filter_no_bom = st.checkbox("BOM 미보유만",
            value=False, key="fast_no_bom")
    with s3:
        f_limit = st.number_input("결과", 10, 200, 50, 10, key="fast_limit")

    sel_pid = None
    sel_pn = None
    sel_customer = None

    if fq:
        qq = fq.strip()
        try:
            cand = fetch("products",
                "product_id,pn,customer,product_group,sub_class,"
                "material,raw_material_name,raw_material_spec,"
                "material_unit_price,heat_treat_per_pc,surface_per_pc,outsourcing_per_pc,"
                "estimated_cost_per_pc",
                f"or=(pn.ilike.*{qq}*,customer.ilike.*{qq}*,"
                f"product_group.ilike.*{qq}*,sub_class.ilike.*{qq}*)"
                f"&archived_at=is.null&order=pn.asc",
                limit=int(f_limit))
        except Exception as e:
            st.error(f"검색 실패: {e}"); cand = []

        # BOM 미보유 필터
        if filter_no_bom and cand:
            pids = [c["product_id"] for c in cand]
            pids_q = ",".join(f'"{p}"' for p in pids)
            try:
                bp = fetch("bom", "product_id",
                    f"product_id=in.({pids_q})", limit=5000)
                has_bom = {b["product_id"] for b in bp}
                cand = [c for c in cand if c["product_id"] not in has_bom]
            except Exception:
                pass

        if not cand:
            st.info("결과 없음")
        else:
            labels = [
                f"{c['pn']}  |  {c.get('customer','-')}  |  {c.get('product_group','-')}"
                for c in cand
            ]
            sel = st.selectbox(f"제품 선택 ({len(cand)}건)",
                labels, key="fast_pick")
            if sel:
                picked = cand[labels.index(sel)]
                sel_pid = picked["product_id"]
                sel_pn = picked["pn"]
                sel_customer = picked.get("customer")

    # ════════════════════════════════════════════════
    # 2. 선택된 제품의 현재 BOM + 정비 폼
    # ════════════════════════════════════════════════
    if sel_pid:
        st.divider()
        st.markdown(f"### 🔧 {sel_pn}  ·  {sel_customer or '-'}")

        # 현재 BOM 행
        try:
            cur_bom = fetch("bom",
                "bom_id,process_type,material_id,raw_material_name,"
                "qty_per_pc,shared_factor,unit_price,lot_label,"
                "verification_status,source",
                f"product_id=eq.{sel_pid}&order=bom_id.asc", limit=100)
        except Exception as e:
            st.error(f"BOM 조회 실패: {e}"); cur_bom = []

        if cur_bom:
            st.markdown(f"##### 현재 BOM ({len(cur_bom)}행)")
            df_b = pd.DataFrame(cur_bom)
            for c in ["qty_per_pc","shared_factor","unit_price"]:
                df_b[c] = pd.to_numeric(df_b[c], errors="coerce")
            # per_pc 계산 미리보기
            def _per_pc(r):
                up = r.get("unit_price")
                qp = r.get("qty_per_pc") or 1
                sf = r.get("shared_factor") or 1
                if pd.notna(up) and up and sf:
                    return up * qp / sf
                return None
            df_b["per_pc 추정"] = df_b.apply(_per_pc, axis=1)
            df_b["per_pc 추정"] = df_b["per_pc 추정"].apply(
                lambda v: f"{v:,.2f}" if pd.notna(v) else "-")

            show_cols = ["bom_id","process_type","material_id","raw_material_name",
                         "qty_per_pc","shared_factor","unit_price","lot_label",
                         "per_pc 추정","verification_status"]
            st.dataframe(df_b[show_cols].rename(columns={
                "bom_id":"ID","process_type":"구분","material_id":"자재ID",
                "raw_material_name":"자재/공정명","qty_per_pc":"qty/PC",
                "shared_factor":"분할/LOT","unit_price":"LOT단가",
                "lot_label":"단위","verification_status":"검증"
            }), use_container_width=True, hide_index=True, height=240)

            # 삭제 (선택적 권장)
            with st.expander("⚠️ 개별 행 삭제", expanded=False):
                del_id = st.number_input("삭제할 BOM ID", min_value=0,
                    value=0, step=1, key="fast_del_id")
                if st.button("🗑 삭제", key="fast_del_btn"):
                    if del_id > 0:
                        try:
                            import requests
                            sr = st.secrets["supabase"]["service_role_key"]
                            r = requests.delete(
                                f"{st.secrets['supabase']['url']}/rest/v1/bom?"
                                f"bom_id=eq.{del_id}",
                                headers={"apikey": sr,
                                         "Authorization": f"Bearer {sr}"},
                                timeout=15)
                            if r.status_code in (200, 204):
                                st.success(f"✅ bom_id={del_id} 삭제 완료")
                                st.rerun()
                            else:
                                st.error(f"삭제 실패: {r.status_code} {r.text[:100]}")
                        except Exception as e:
                            st.error(f"삭제 오류: {e}")
        else:
            st.info("이 제품에 등록된 BOM 행이 없습니다. 아래에서 입력하세요.")

        st.divider()

        # ── 자재행 추가 ──
        st.markdown("##### 1️⃣ 자재행 추가")
        with st.form(f"fast_mat_form_{sel_pid}"):
            mc1, mc2, mc3, mc4 = st.columns([2, 1, 1, 1])
            with mc1:
                mat_q = st.text_input("자재 검색 (자재명/규격/재질)",
                    placeholder="예: 환봉 STS304, SCM440",
                    key=f"fast_mat_q_{sel_pid}")
            with mc2:
                mat_qpc = st.number_input("qty/PC", min_value=0.0,
                    value=1.0, step=0.1, key=f"fast_mat_qpc_{sel_pid}")
            with mc3:
                mat_sf = st.number_input("분할가공 N",
                    min_value=1, value=1, step=1,
                    key=f"fast_mat_sf_{sel_pid}",
                    help="환봉 1개 → N제품 분할가공 시 N. 분할 없으면 1.")
            with mc4:
                st.write(""); st.write("")
                mat_submit = st.form_submit_button("➕ 자재행 추가", type="primary")

            if mat_q:
                qq = mat_q.strip()
                try:
                    m_found = fetch("materials",
                        "material_id,raw_name,material_type,spec",
                        f"or=(raw_name.ilike.*{qq}*,material_type.ilike.*{qq}*,"
                        f"spec.ilike.*{qq}*)&order=raw_name.asc", limit=20)
                except Exception:
                    m_found = []
                if m_found:
                    m_labels = [
                        f"{m['raw_name']} · {m.get('material_type','-')} · {m.get('spec','-')}"
                        for m in m_found
                    ]
                    sel_m_label = st.selectbox(f"자재 선택 ({len(m_found)}건)",
                        m_labels, key=f"fast_mat_pick_{sel_pid}")
                else:
                    sel_m_label = None
                    st.caption("일치하는 자재 없음")
            else:
                sel_m_label = None
                m_found = []

            if mat_submit:
                if not sel_m_label:
                    st.error("자재를 선택해주세요.")
                else:
                    m = m_found[m_labels.index(sel_m_label)]
                    try:
                        _db.insert("bom", [{
                            "product_id": sel_pid,
                            "material_id": m["material_id"],
                            "raw_material_name": m["raw_name"],
                            "process_type": "MATERIAL",
                            "qty_per_pc": mat_qpc,
                            "shared_factor": mat_sf,
                            "source": "MANUAL",
                            "verification_status": "확인완료",
                        }])
                        st.success(f"✅ 자재행 추가: {m['raw_name']} "
                                   f"(qty/PC={mat_qpc}, 분할={mat_sf})")
                        st.rerun()
                    except Exception as e:
                        st.error(f"추가 실패: {e}")

        # ── 공정행 추가 ──
        st.markdown("##### 2️⃣ 공정행 추가 (열처리/외주/표면 등)")
        with st.form(f"fast_proc_form_{sel_pid}"):
            st.caption("공정행 = **수량 관계만** 등록. LOT 단가는 💰 원가 분석 → 단가 관리에서.")
            fc1, fc2, fc3 = st.columns([1, 1, 1])
            with fc1:
                pt = st.selectbox("공정", ["HEAT","SURFACE","OUTSOURCE",
                    "PACKING","LABOR","OTHER"],
                    format_func=lambda v: {
                        "HEAT":"🔥 HEAT","SURFACE":"💎 SURFACE",
                        "OUTSOURCE":"🏭 OUTSOURCE","PACKING":"📦 PACKING",
                        "LABOR":"👷 LABOR","OTHER":"❔ OTHER"
                    }[v], key=f"fast_pt_{sel_pid}")
            with fc2:
                pqpc = st.number_input("qty/PC", min_value=0.0,
                    value=1.0, step=0.1, key=f"fast_pqpc_{sel_pid}")
            with fc3:
                plot = st.number_input("LOT 처리수량",
                    min_value=1, value=1, step=1, key=f"fast_plot_{sel_pid}")

            fc5, fc6, fc7 = st.columns([2, 1, 1])
            with fc5:
                pn = st.text_input("공정 설명",
                    placeholder="예: 소재열처리, 제품열처리, 무전해Ni도금",
                    key=f"fast_pn_{sel_pid}")
            with fc6:
                plbl = st.selectbox("LOT단위", ["","LOT","CH","BATCH"],
                    key=f"fast_plbl_{sel_pid}")
            with fc7:
                st.write(""); st.write("")
                proc_submit = st.form_submit_button("➕ 공정행 추가", type="primary")

            if proc_submit:
                try:
                    _db.insert("bom", [{
                        "product_id": sel_pid,
                        "material_id": None,
                        "raw_material_name": pn or pt,
                        "process_type": pt,
                        "qty_per_pc": pqpc,
                        "shared_factor": plot,
                        "lot_label": plbl or None,
                        "source": "MANUAL",
                        "verification_status": "확인완료",
                    }])
                    st.success(
                        f"✅ {pt} 추가 (LOT 처리 {plot}EA). "
                        f"단가는 💰 원가 분석 → 단가 관리에서 입력하세요."
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"추가 실패: {e}")

        st.divider()

        # ── 분기 일괄 복사 ──
        if cur_bom:
            st.markdown("##### 3️⃣ 이 BOM을 다른 제품에 일괄 복사 (분기 적용)")
            st.caption(
                f"현재 **{sel_pn}** 의 BOM **{len(cur_bom)}행** 을 다른 제품에 그대로 복제합니다. "
                "분기 제품군(예: -A/-B/-C) 한 번에 정비할 때 유용."
            )
            cp_c1, cp_c2 = st.columns([3, 1])
            with cp_c1:
                cp_q = st.text_input("대상 제품 검색 (다중 선택)",
                    placeholder=f"예: {sel_pn[:6]} (분기 베이스로 검색)",
                    key=f"fast_cp_q_{sel_pid}")
            with cp_c2:
                cp_limit = st.number_input("결과수",
                    10, 200, 50, 10, key=f"fast_cp_lim_{sel_pid}")

            if cp_q:
                cqq = cp_q.strip()
                try:
                    cp_found = fetch("products", "product_id,pn,customer",
                        f"or=(pn.ilike.*{cqq}*,customer.ilike.*{cqq}*)"
                        f"&archived_at=is.null&product_id=neq.{sel_pid}"
                        f"&order=pn.asc", limit=int(cp_limit))
                except Exception:
                    cp_found = []
                if cp_found:
                    cp_labels = [f"{p['pn']} | {p.get('customer','-')}"
                                 for p in cp_found]
                    cp_sel = st.multiselect(
                        f"복사할 대상 제품 선택 (최대 {cp_limit}개)",
                        cp_labels, key=f"fast_cp_sel_{sel_pid}")

                    cp_opt1, cp_opt2 = st.columns([1, 3])
                    with cp_opt1:
                        cp_overwrite = st.checkbox("기존 BOM 덮어쓰기",
                            value=False, key=f"fast_cp_ow_{sel_pid}",
                            help="체크 시 대상 제품의 기존 BOM 행 모두 삭제 후 복사.")
                    if cp_sel and st.button(
                        f"📋 {len(cp_sel)}개 제품에 BOM 복사",
                        type="primary", key=f"fast_cp_btn_{sel_pid}"
                    ):
                        target_pids = [cp_found[cp_labels.index(l)]["product_id"]
                                       for l in cp_sel]
                        ok_n, fail_n = 0, 0
                        # 1) 덮어쓰기면 기존 삭제
                        if cp_overwrite:
                            for tpid in target_pids:
                                try:
                                    import requests
                                    sr = st.secrets["supabase"]["service_role_key"]
                                    r = requests.delete(
                                        f"{st.secrets['supabase']['url']}/rest/v1/bom?"
                                        f"product_id=eq.{tpid}",
                                        headers={"apikey": sr,
                                                 "Authorization": f"Bearer {sr}"},
                                        timeout=15)
                                except Exception:
                                    pass
                        # 2) 행 복제
                        for tpid in target_pids:
                            records = []
                            for b in cur_bom:
                                rec = {
                                    "product_id": tpid,
                                    "material_id": b.get("material_id"),
                                    "raw_material_name": b.get("raw_material_name"),
                                    "process_type": b.get("process_type") or "MATERIAL",
                                    "qty_per_pc": b.get("qty_per_pc"),
                                    "shared_factor": b.get("shared_factor"),
                                    "unit_price": b.get("unit_price"),
                                    "lot_label": b.get("lot_label"),
                                    "source": f"COPY_FROM:{sel_pn}",
                                    "verification_status": b.get("verification_status"),
                                }
                                records.append(rec)
                            try:
                                _db.insert("bom", records)
                                ok_n += 1
                            except Exception:
                                fail_n += 1
                        st.success(
                            f"✅ {ok_n}개 제품 복사 완료"
                            + (f" / 실패 {fail_n}개" if fail_n else "")
                            + (" (기존 BOM 덮어씀)" if cp_overwrite else "")
                        )
                        st.rerun()


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
            st.info(f"🛒 **생산 계획에서 자동 제안 받은 발주 데이터**: 거래처 '{pv}', 품목 {len(pi)}개")
            if st.button("🔄 자동 제안 + 품목표 모두 초기화"):
                st.session_state.po_prefill_vendor_name = None
                st.session_state.po_prefill_items = None
                st.session_state.po_items = []
                st.rerun()
            # 품목 prefill (현재 품목표가 비어있을 때만)
            if pi and not st.session_state.get("po_items"):
                import uuid as _uuid
                st.session_state.po_items = [
                    {**x, "_uid": str(_uuid.uuid4())[:8]} for x in pi
                ]

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

            # ─── ② 최근 발주 복사 (이 거래처의 과거 발주 5건) ───
            with st.expander("📋 최근 발주에서 복사 (이 거래처)"):
                try:
                    recent_pos = fetch("purchase_orders",
                        "po_id,po_number,po_date,total_amount",
                        f"vendor_id=eq.{vendor['vendor_id']}&order=po_date.desc",
                        limit=10)
                except Exception as e:
                    st.error(e); recent_pos = []
                if not recent_pos:
                    st.caption("이 거래처에 과거 발주가 없습니다.")
                else:
                    for po in recent_pos:
                        rc1, rc2, rc3 = st.columns([3, 2, 1])
                        rc1.write(f"**{po['po_number']}** · {po.get('po_date','')}")
                        rc2.write(f"₩{int(po.get('total_amount') or 0):,}")
                        if rc3.button("📋 복사", key=f"copy_po_{po['po_id']}"):
                            try:
                                copied = fetch("purchase_order_items",
                                    "item_name,spec,qty,unit_price,remark",
                                    f"po_id=eq.{po['po_id']}&order=line_no", limit=50)
                                import uuid as _uuid_c
                                for it in copied:
                                    st.session_state.po_items.append({
                                        "_uid": str(_uuid_c.uuid4())[:8],
                                        "product_id": None,
                                        "item_name": it.get("item_name") or "",
                                        "material": "",
                                        "spec": it.get("spec") or "",
                                        "qty": int(it.get("qty") or 0),
                                        "unit_price": int(it.get("unit_price") or 0),
                                        "memo": it.get("remark") or "",
                                    })
                                st.success(f"✅ {po['po_number']}의 {len(copied)}개 품목 복사")
                                st.rerun()
                            except Exception as e:
                                st.error(f"복사 실패: {e}")

            # ─── 거래처별 단가 자동 채움 helper ───
            @st.cache_data(ttl=60)
            def _get_vendor_recent_price(vid, item_name):
                """이 거래처에서 같은 품목 최근 발주 단가"""
                try:
                    pos = fetch("purchase_orders", "po_id",
                                f"vendor_id=eq.{vid}&order=po_date.desc", limit=20)
                    if not pos: return None
                    po_ids = ",".join(str(p["po_id"]) for p in pos)
                    items = fetch("purchase_order_items", "unit_price,po_id",
                                  f"po_id=in.({po_ids})&item_name=eq.{item_name}&order=po_id.desc",
                                  limit=1)
                    return int(items[0]["unit_price"]) if items else None
                except: return None

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
                        # 거래처별 최근 단가 우선, 없으면 마스터 단가
                        vendor_price = _get_vendor_recent_price(vendor["vendor_id"], p["pn"])
                        upd = vendor_price or int(p.get("material_unit_price") or 0)
                        if vendor_price:
                            cols[3].markdown(f"₩{upd:,} <small>(이전)</small>",
                                              unsafe_allow_html=True)
                        else:
                            cols[3].write(f"₩{upd:,}" if upd else "-")
                        if cols[4].button("➕", key=f"add_{p['product_id']}"):
                            import uuid as _uuid
                            st.session_state.po_items.append({
                                "_uid": str(_uuid.uuid4())[:8],
                                "product_id": p["product_id"], "item_name": p["pn"],
                                "material": p.get("material") or "",
                                "spec": p.get("raw_material_spec") or "",
                                "qty": 0, "unit_price": upd, "memo": "",
                            })
                            st.rerun()

            # ─── ④ 품번 일괄 추가 ───
            with st.expander("📋 품번 일괄 추가 (콤마/줄바꿈 구분)"):
                bulk_txt = st.text_area("품번 목록",
                    placeholder="8HFDV-VM-05\n4PDVN-02\nMRG6-07\n또는 콤마 구분: 8HFDV-VM-05, 4PDVN-02",
                    key="bulk_pn")
                if st.button("📋 일괄 추가", key="bulk_add_btn") and bulk_txt:
                    import re as _re_bulk, uuid as _uuid_bulk
                    pns = [x.strip() for x in _re_bulk.split(r'[,\n]+', bulk_txt) if x.strip()]
                    added = 0; notfound = []
                    for pn in pns:
                        try:
                            r = fetch("active_products",
                                "product_id,pn,raw_material_name,raw_material_spec,material,material_unit_price",
                                f"or=(pn.eq.{pn},alias_list.ilike.*{pn}*)&limit=1")
                        except: r = []
                        if not r:
                            notfound.append(pn); continue
                        p = r[0]
                        vp = _get_vendor_recent_price(vendor["vendor_id"], p["pn"])
                        upd = vp or int(p.get("material_unit_price") or 0)
                        st.session_state.po_items.append({
                            "_uid": str(_uuid_bulk.uuid4())[:8],
                            "product_id": p["product_id"], "item_name": p["pn"],
                            "material": p.get("material") or "",
                            "spec": p.get("raw_material_spec") or "",
                            "qty": 0, "unit_price": upd, "memo": "",
                        })
                        added += 1
                    msg = f"✅ {added}개 추가"
                    if notfound: msg += f"\n⚠️ 미발견: {', '.join(notfound[:10])}"
                    if added: st.success(msg); st.rerun()
                    else: st.warning(msg)

            with st.expander("✏️ 마스터에 없는 품목 즉석 추가"):
                c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
                nx = c1.text_input("품번/품명", key="nx_name")
                nm = c2.text_input("재질", key="nx_mat")
                ns = c3.text_input("규격", key="nx_spec")
                np_ = c4.number_input("단가", min_value=0, step=100, key="nx_price")
                if st.button("➕ 추가 (즉석)") and nx:
                    import uuid as _uuid
                    st.session_state.po_items.append({
                        "_uid": str(_uuid.uuid4())[:8],
                        "product_id": None, "item_name": nx, "material": nm,
                        "spec": ns, "qty": 0, "unit_price": int(np_), "memo": "",
                    })
                    st.rerun()

            st.divider()
            st.markdown("##### ③ 품목 표 (수량·단가 편집)")
            total = 0
            if not st.session_state.po_items:
                st.info("위에서 ➕ 버튼으로 품목을 추가하세요.")
            else:
                # UID 부여 (기존 데이터에 _uid 없을 수도)
                import uuid as _uuid_local
                for it in st.session_state.po_items:
                    if "_uid" not in it:
                        it["_uid"] = str(_uuid_local.uuid4())[:8]

                # 헤더 행
                hcols = st.columns([2.5, 1.2, 1.8, 1.2, 1.3, 1.3, 2, 0.5])
                hcols[0].markdown("**품명**"); hcols[1].markdown("**재질**")
                hcols[2].markdown("**규격**"); hcols[3].markdown("**수량**")
                hcols[4].markdown("**단가**"); hcols[5].markdown("**합계**")
                hcols[6].markdown("**메모**"); hcols[7].markdown("")

                for i, it in enumerate(st.session_state.po_items):
                    uid = it["_uid"]
                    cols = st.columns([2.5, 1.2, 1.8, 1.2, 1.3, 1.3, 2, 0.5])
                    cols[0].write(f"**{it['item_name']}**")
                    cols[1].write(it.get("material") or "")
                    cols[2].write(it.get("spec") or "")
                    it["qty"] = cols[3].number_input("수량", 0, value=int(it.get("qty") or 0),
                        step=10, key=f"qty_{uid}", label_visibility="collapsed")
                    it["unit_price"] = cols[4].number_input("단가", 0, value=int(it.get("unit_price") or 0),
                        step=100, key=f"up_{uid}", label_visibility="collapsed")
                    amt = it["qty"] * it["unit_price"]
                    cols[5].markdown(
                        f"<div style='text-align:right;padding-top:8px'>₩{amt:,}</div>",
                        unsafe_allow_html=True)
                    it["memo"] = cols[6].text_input("메모", value=it.get("memo") or "",
                        key=f"memo_{uid}", label_visibility="collapsed",
                        placeholder="예: 6/15 납기, 검수 후 입고")
                    if cols[7].button("🗑", key=f"del_{uid}"):
                        for k in (f"qty_{uid}", f"up_{uid}", f"memo_{uid}"):
                            if k in st.session_state: del st.session_state[k]
                        st.session_state.po_items = [
                            x for x in st.session_state.po_items if x["_uid"] != uid
                        ]
                        st.rerun()
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
                                # 메모 + 재질 합쳐 remark에 저장
                                "remark": (
                                    (it.get("memo") or "") +
                                    (" / " + it["material"] if it.get("memo") and it.get("material") else "") +
                                    (it.get("material") or "" if not it.get("memo") else "")
                                ) or None,
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


elif page == "💰 원가 분석":
    st.subheader("💰 원가 분석")
    st.caption("정적 원가 스냅샷(소재/외주/열처리/표면) + 실판매가 → 마진 분석. 생산실적 추가 시 실원가 비교 탭 확장 예정.")

    if not DB_AVAILABLE:
        st.error("DB 연결이 활성화되지 않았습니다."); st.stop()

    import db as _db
    import pandas as pd

    def _money(v):
        try:    return f"{int(v):,}"
        except: return "-"

    def _pct(v):
        try:    return f"{float(v):.1f}%"
        except: return "-"

    # ─── 데이터 소스 자동 선택 ───
    # product_cost_full_v (009) 가 있으면 사용 → BOM 변경이 즉시 반영.
    # 없으면 product_full(legacy) fallback.
    USE_V2 = True
    try:
        fetch("product_cost_full_v", "product_id", limit=1)
    except Exception:
        USE_V2 = False

    SRC_TABLE = "product_cost_full_v" if USE_V2 else "product_full"

    # 호환 alias (009 마이그레이션이 두 컬럼명 모두 제공) → 기존 필드 그대로 사용 가능
    COST_FIELDS = (
        "product_id,pn,customer,product_group,sub_class,"
        "material_kg_price,material_unit_price,outsourcing_per_pc,"
        "heat_treat_per_pc,surface_per_pc,estimated_cost_per_pc,"
        "cost_data_quality,avg_unit_price,margin_pct,abc_grade,"
        "total_sales_12m,sales_count_12m,activity_trend"
    )

    if USE_V2:
        st.success(
            "✅ `product_cost_full_v` 사용 중 — BOM 변경이 즉시 반영됩니다."
        )
    else:
        st.warning(
            "⚠️ legacy `product_full` 사용 중 — BOM 변경 자동 반영 안 됨. "
            "Migration 007/008/009 적용 후 자동 활성."
        )

    # ════════════════════════════════════════════════
    # 📊 매입 단가 조회 (페이지 공통 보조 위젯)
    # ════════════════════════════════════════════════
    with st.expander("📊 매입 단가 조회 (자재명/품번으로 최근 거래가 확인)",
                     expanded=False):
        st.caption("BOM 작성·단가 입력 전 참고. 매입 ledger 의 `item` (자재명), "
                   "`matched_pn` (제품 매칭), `remark` 를 모두 검색합니다.")

        # 데이터 상태 진단 (silent fail 방지)
        from db import count_rows as _cnt_rows
        pl_total = _cnt_rows("purchase_ledger")
        try:
            cat_rows = fetch("purchase_ledger", "category",
                "category=not.is.null&order=category.asc", limit=2000)
            all_cats = sorted({r['category'] for r in cat_rows if r.get('category')})
            cat_err = None
        except Exception as e:
            all_cats = []
            cat_err = str(e)[:120]
        mat_default = [c for c in all_cats if c.upper().startswith('MAT')]

        # 상태 헤더
        st_c1, st_c2, st_c3 = st.columns(3)
        st_c1.metric("매입 ledger 총 건수",
                     f"{pl_total:,}" if isinstance(pl_total, int) else "ERR")
        st_c2.metric("category 보유 종류",
                     f"{len(all_cats)}종",
                     "데이터 부재" if len(all_cats) == 0 else None,
                     delta_color="inverse" if len(all_cats) == 0 else "off")
        st_c3.metric("MAT_* 종", f"{len(mat_default)}종")
        if cat_err:
            st.error(f"카테고리 로드 오류: {cat_err}")
        if len(all_cats) == 0 and not cat_err:
            st.warning(
                "ℹ️ purchase_ledger.category 가 모두 NULL. "
                "카테고리 필터는 비활성. 키워드 검색만 작동합니다."
            )

        pql_c1, pql_c2 = st.columns([3, 1])
        with pql_c1:
            pl_q = st.text_input("키워드 (자재명/품번/메모)",
                placeholder="예: 환봉, STS304, SCM440, MRG6-07, 8HFDV",
                key="cost_pl_search")
        with pql_c2:
            pl_limit = st.number_input("최근 N건", 3, 50, 15, 1, key="cost_pl_limit")

        if all_cats:
            pl_cats = st.multiselect(
                f"카테고리 필터 (전체 {len(all_cats)}종, 기본=MAT_*)",
                all_cats, default=mat_default, key="cost_pl_cats")
        else:
            pl_cats = []

        if pl_q:
            qq = pl_q.strip()
            # item / matched_pn / remark 모두 검색 → 자재명/품번/메모 어느 쪽이든 매칭
            filt = [
                f"or=(item.ilike.*{qq}*,matched_pn.ilike.*{qq}*,remark.ilike.*{qq}*)",
                "order=trade_date.desc"
            ]
            if pl_cats:
                cat_in = ",".join(f'"{c}"' for c in pl_cats)
                filt.append(f"category=in.({cat_in})")
            try:
                pl_rows = fetch("purchase_ledger",
                    "ledger_id,trade_date,vendor,vendor_normalized,item,"
                    "qty,unit,unit_price,kg_price,ea_price,category,"
                    "matched_pn,remark",
                    "&".join(filt), limit=int(pl_limit))
            except Exception as e:
                st.error(f"매입 조회 실패: {e}"); pl_rows = []

            if not pl_rows:
                # 진단: 카테고리 필터를 끄면 결과가 나오는지 점검
                try:
                    raw_rows = fetch("purchase_ledger", "ledger_id",
                        f"or=(item.ilike.*{qq}*,matched_pn.ilike.*{qq}*,"
                        f"remark.ilike.*{qq}*)", limit=5)
                except Exception:
                    raw_rows = []
                if raw_rows and pl_cats:
                    st.warning(
                        f"⚠️ 카테고리 필터 때문에 0건. "
                        f"필터 없이는 **{len(raw_rows)}건 이상** 매칭 — 카테고리 해제 후 재시도."
                    )
                elif not raw_rows:
                    st.info(
                        f"'{qq}' 와 일치하는 매입 이력 없음. "
                        f"키워드를 짧게(부분)·자재명 위주로 변경해 보세요."
                    )
            else:
                prices_unit = [float(r.get("unit_price") or 0) for r in pl_rows
                               if r.get("unit_price")]
                prices_kg = [float(r.get("kg_price") or 0) for r in pl_rows
                             if r.get("kg_price")]
                prices_ea = [float(r.get("ea_price") or 0) for r in pl_rows
                             if r.get("ea_price")]
                s1, s2, s3, s4 = st.columns(4)
                s1.metric("검색결과", f"{len(pl_rows):,}건")
                if prices_unit:
                    s2.metric("평균 단가", f"{sum(prices_unit)/len(prices_unit):,.0f}",
                              f"최근 {prices_unit[0]:,.0f}")
                if prices_kg:
                    s3.metric("평균 KG단가",
                              f"{sum(prices_kg)/len(prices_kg):,.0f}")
                if prices_ea:
                    s4.metric("평균 EA단가",
                              f"{sum(prices_ea)/len(prices_ea):,.0f}")
                df_pl = pd.DataFrame(pl_rows)
                df_pl["unit_price"] = pd.to_numeric(df_pl["unit_price"], errors="coerce")
                df_pl["qty"] = pd.to_numeric(df_pl["qty"], errors="coerce")
                cols_avail = [c for c in ["trade_date","vendor","item","matched_pn",
                                          "category","qty","unit","unit_price",
                                          "kg_price","ea_price"] if c in df_pl.columns]
                show = df_pl[cols_avail].rename(
                    columns={"trade_date":"거래일","vendor":"거래처","item":"품목",
                             "matched_pn":"매칭품번",
                             "category":"분류","qty":"수량","unit":"단위",
                             "unit_price":"단가","kg_price":"KG단가","ea_price":"EA단가"})
                st.dataframe(show, use_container_width=True,
                             hide_index=True, height=280)
                if len(pl_rows) >= 3:
                    # 월별 추이 (시간순)
                    df_pl_chart = df_pl.copy()
                    df_pl_chart["trade_date"] = pd.to_datetime(
                        df_pl_chart["trade_date"], errors="coerce")
                    df_pl_chart = df_pl_chart.dropna(
                        subset=["trade_date","unit_price"])
                    df_pl_chart = df_pl_chart[df_pl_chart["unit_price"] > 0]
                    if len(df_pl_chart) >= 2:
                        df_pl_chart["월"] = df_pl_chart["trade_date"].dt.to_period("M").astype(str)
                        monthly_pl = (df_pl_chart.groupby("월")["unit_price"]
                                      .mean().sort_index())
                        if len(monthly_pl) >= 2:
                            st.markdown("##### 월별 평균 단가 추이")
                            st.line_chart(monthly_pl, height=200,
                                          use_container_width=True)

                    st.markdown("##### 거래처별 평균 단가 (상위 5)")
                    by_vendor = (df_pl.groupby("vendor_normalized")
                                 .agg(거래수=("ledger_id","count"),
                                      평균단가=("unit_price","mean"),
                                      최근거래=("trade_date","max"))
                                 .reset_index()
                                 .sort_values("거래수", ascending=False)
                                 .head(5))
                    by_vendor["평균단가"] = by_vendor["평균단가"].apply(
                        lambda v: f"{v:,.0f}" if pd.notna(v) else "-")
                    st.dataframe(by_vendor.rename(columns={
                        "vendor_normalized":"거래처(정규)"}),
                        use_container_width=True, hide_index=True)

    tabs = st.tabs(["📊 마진 대시보드", "🔍 품목 분석", "⚠️ 이상치",
                    "🧮 BOM 재산정", "✏️ 원가 편집", "🏗 통합 view (Beta)"])

    # ════════════════════════════════════════════════
    # Tab 1: 마진 대시보드
    # ════════════════════════════════════════════════
    with tabs[0]:
        st.markdown("### 핵심 지표")
        try:
            # 활성 제품 전체 (마진/원가 통계 산출 기반)
            all_rows = fetch(SRC_TABLE,
                "product_id,estimated_cost_per_pc,avg_unit_price,margin_pct,total_sales_12m",
                "archived_at=is.null", limit=5000)
        except Exception as e:
            st.error(f"데이터 로드 실패: {e}"); st.stop()

        df_all = pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
        if df_all.empty:
            st.warning("활성 제품 데이터가 없습니다."); st.stop()

        # 숫자 강제 변환
        for c in ["estimated_cost_per_pc", "avg_unit_price", "margin_pct", "total_sales_12m"]:
            df_all[c] = pd.to_numeric(df_all[c], errors="coerce")

        n_total = len(df_all)
        n_has_cost = int((df_all["estimated_cost_per_pc"].fillna(0) > 0).sum())
        n_has_sale = int((df_all["avg_unit_price"].fillna(0) > 0).sum())
        n_both = int(((df_all["estimated_cost_per_pc"].fillna(0) > 0) &
                      (df_all["avg_unit_price"].fillna(0) > 0)).sum())
        # 마진 산출 가능한 것만으로 통계
        df_m = df_all.dropna(subset=["margin_pct"])
        avg_margin = df_m["margin_pct"].mean() if not df_m.empty else None
        n_neg = int((df_m["margin_pct"] < 0).sum())
        n_low = int(((df_m["margin_pct"] >= 0) & (df_m["margin_pct"] < 10)).sum())
        n_missing = n_total - n_has_cost

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("활성 제품", f"{n_total:,}")
        k2.metric("원가 데이터 보유", f"{n_has_cost:,}", f"{n_has_cost/n_total*100:.0f}%")
        k3.metric("평균 마진율", _pct(avg_margin) if avg_margin is not None else "-")
        k4.metric("역마진 (<0%)", f"{n_neg:,}", "주의" if n_neg > 0 else "양호")
        k5.metric("저마진 (0~10%)", f"{n_low:,}")

        k6, k7, k8 = st.columns(3)
        k6.metric("원가 데이터 누락", f"{n_missing:,}", f"{n_missing/n_total*100:.0f}%")
        k7.metric("판매 실적 있음", f"{n_has_sale:,}")
        k8.metric("원가+판매 모두 보유", f"{n_both:,}", "마진 산출 가능")

        st.divider()
        st.markdown("### 마진율 분포")
        if not df_m.empty:
            # 구간화
            bins = [-9999, -10, 0, 10, 20, 30, 50, 9999]
            labels = ["역마진 (-10%↓)", "역마진 (-10~0%)", "저마진 (0~10%)",
                      "보통 (10~20%)", "양호 (20~30%)", "우수 (30~50%)", "최우수 (50%+)"]
            df_m["bucket"] = pd.cut(df_m["margin_pct"], bins=bins, labels=labels)
            dist = df_m.groupby("bucket", observed=True).size().reset_index(name="품목수")
            st.bar_chart(dist.set_index("bucket"), height=240)
        else:
            st.caption("마진 산출 가능한 품목이 없습니다.")

        st.divider()
        st.markdown("### ⛔ 저마진 BOTTOM 10 (마진율↑)")
        try:
            bottom = fetch(SRC_TABLE, COST_FIELDS,
                "archived_at=is.null&margin_pct=not.is.null&total_sales_12m=gt.0"
                "&order=margin_pct.asc", limit=10)
            if bottom:
                df_b = pd.DataFrame(bottom)
                df_b["판매가"] = df_b["avg_unit_price"].apply(_money)
                df_b["추정원가"] = df_b["estimated_cost_per_pc"].apply(_money)
                df_b["마진율"] = df_b["margin_pct"].apply(_pct)
                df_b["12M매출"] = df_b["total_sales_12m"].apply(_money)
                st.dataframe(
                    df_b[["pn", "customer", "판매가", "추정원가", "마진율",
                          "12M매출", "abc_grade", "activity_trend"]]
                    .rename(columns={"pn": "품번", "customer": "고객사",
                                     "abc_grade": "ABC", "activity_trend": "추세"}),
                    use_container_width=True, hide_index=True)
            else:
                st.caption("데이터 없음")
        except Exception as e:
            st.caption(f"조회 실패: {e}")

        st.divider()
        st.markdown("### 🏆 고마진 TOP 10 (마진율↓)")
        try:
            top = fetch(SRC_TABLE, COST_FIELDS,
                "archived_at=is.null&margin_pct=not.is.null&total_sales_12m=gt.0"
                "&order=margin_pct.desc", limit=10)
            if top:
                df_t = pd.DataFrame(top)
                df_t["판매가"] = df_t["avg_unit_price"].apply(_money)
                df_t["추정원가"] = df_t["estimated_cost_per_pc"].apply(_money)
                df_t["마진율"] = df_t["margin_pct"].apply(_pct)
                df_t["12M매출"] = df_t["total_sales_12m"].apply(_money)
                st.dataframe(
                    df_t[["pn", "customer", "판매가", "추정원가", "마진율",
                          "12M매출", "abc_grade", "activity_trend"]]
                    .rename(columns={"pn": "품번", "customer": "고객사",
                                     "abc_grade": "ABC", "activity_trend": "추세"}),
                    use_container_width=True, hide_index=True)
        except Exception as e:
            st.caption(f"조회 실패: {e}")

    # ════════════════════════════════════════════════
    # Tab 2: 품목 분석 (단일 품번 상세)
    # ════════════════════════════════════════════════
    with tabs[1]:
        st.markdown("### 품목 검색")
        c1, c2 = st.columns([3, 1])
        with c1:
            q = st.text_input("품번 / 품명 / 고객사", placeholder="예: 4S-001 또는 FLANGE 또는 명진",
                              key="cost_search")
        with c2:
            ca_limit = st.number_input("표시", 5, 100, 20, 5, key="cost_search_limit")

        if q:
            parts = [f"archived_at=is.null"]
            qq = q.strip()
            # OR 검색 (PostgREST or= 문법)
            parts.append(f"or=(pn.ilike.*{qq}*,customer.ilike.*{qq}*,product_group.ilike.*{qq}*)")
            parts.append(f"order=total_sales_12m.desc.nullslast")
            try:
                rows = fetch(SRC_TABLE, COST_FIELDS, "&".join(parts), limit=int(ca_limit))
            except Exception as e:
                st.error(f"검색 실패: {e}"); rows = []

            if not rows:
                st.info("검색 결과 없음")
            else:
                df_q = pd.DataFrame(rows)
                df_q["_label"] = df_q.apply(
                    lambda r: f"{r['pn']}  |  {r.get('customer','')}  |  마진 {r.get('margin_pct') or '-' }%",
                    axis=1
                )
                sel = st.selectbox("분석할 품목 선택", df_q["_label"].tolist(), key="cost_pick")
                row = df_q[df_q["_label"] == sel].iloc[0].to_dict() if sel else None

                if row:
                    st.divider()
                    st.markdown(f"#### 🔧 {row['pn']}  ·  {row.get('customer') or '-'}")
                    sale = float(row.get("avg_unit_price") or 0)
                    mat = float(row.get("material_unit_price") or 0)
                    out_ = float(row.get("outsourcing_per_pc") or 0)
                    heat = float(row.get("heat_treat_per_pc") or 0)
                    surf = float(row.get("surface_per_pc") or 0)
                    cost = float(row.get("estimated_cost_per_pc") or 0)
                    margin = sale - cost if (sale > 0 and cost > 0) else None
                    margin_pct = (margin / sale * 100) if (margin is not None and sale > 0) else None

                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("평균 판매가 (12M)", _money(sale))
                    m2.metric("추정 원가", _money(cost))
                    m3.metric("마진", _money(margin) if margin is not None else "-")
                    m4.metric("마진율", _pct(margin_pct) if margin_pct is not None else "-",
                              delta=("역마진" if (margin_pct is not None and margin_pct < 0)
                                     else "저마진" if (margin_pct is not None and margin_pct < 10)
                                     else None),
                              delta_color="inverse")

                    st.markdown("##### 원가 구성")
                    cc1, cc2, cc3, cc4 = st.columns(4)
                    cc1.metric("소재비/EA", _money(mat),
                               f"{(mat/cost*100):.0f}%" if cost > 0 else None)
                    cc2.metric("외주비/EA", _money(out_),
                               f"{(out_/cost*100):.0f}%" if cost > 0 else None)
                    cc3.metric("열처리비/EA", _money(heat),
                               f"{(heat/cost*100):.0f}%" if cost > 0 else None)
                    cc4.metric("표면처리비/EA", _money(surf),
                               f"{(surf/cost*100):.0f}%" if cost > 0 else None)

                    # 구성 비율 bar
                    if cost > 0:
                        comp = pd.DataFrame({
                            "항목": ["소재비", "외주비", "열처리", "표면처리", "기타"],
                            "금액": [mat, out_, heat, surf,
                                     max(cost - mat - out_ - heat - surf, 0)]
                        }).set_index("항목")
                        st.bar_chart(comp, height=200)

                    st.markdown("##### 부가 정보")
                    info_rows = [
                        ("재질", row.get("material") or row.get("raw_material_name") or "-"),
                        ("규격", row.get("raw_material_spec") or "-"),
                        ("제품군", row.get("product_group") or "-"),
                        ("ABC 등급", row.get("abc_grade") or "-"),
                        ("12M 매출액", _money(row.get("total_sales_12m"))),
                        ("12M 거래건수", row.get("sales_count_12m") or 0),
                        ("매출 추세", row.get("activity_trend") or "-"),
                        ("원가데이터 품질", row.get("cost_data_quality") or "-"),
                        ("소재 KG단가", _money(row.get("material_kg_price"))),
                    ]
                    info_df = pd.DataFrame(info_rows, columns=["항목", "값"])
                    st.dataframe(info_df, hide_index=True, use_container_width=True)

                    # ── 📈 판매가 변동 이력 ──
                    st.divider()
                    st.markdown("##### 📈 판매가 변동 이력")
                    st.caption(
                        "12M 평균에 과거 오류 거래가 섞일 수 있어 **최근 단가 / 3M / 12M** "
                        "을 비교 표시. 새 거래가 누적될수록 평균 정확도 향상."
                    )
                    try:
                        sales_rows = fetch("sales_ledger",
                            "voucher_date,item_date,customer,qty,unit,unit_price,amount,remark",
                            f"product_id=eq.{row['product_id']}"
                            f"&order=item_date.desc.nullslast",
                            limit=50)
                    except Exception as e:
                        st.error(f"매출 이력 조회 실패: {e}"); sales_rows = []

                    if not sales_rows:
                        st.info(
                            "매출 거래 이력 없음. "
                            "(sales_ledger.product_id 매핑 누락 또는 거래 없음)"
                        )
                    else:
                        df_s = pd.DataFrame(sales_rows)
                        df_s["unit_price"] = pd.to_numeric(df_s["unit_price"], errors="coerce")
                        df_s["qty"] = pd.to_numeric(df_s["qty"], errors="coerce")
                        df_s["item_date"] = pd.to_datetime(df_s["item_date"], errors="coerce")
                        df_s["amount"] = pd.to_numeric(df_s["amount"], errors="coerce")

                        # 단가/날짜 유효한 행만
                        valid = df_s.dropna(subset=["unit_price", "item_date"])
                        valid = valid[valid["unit_price"] > 0]

                        # 메트릭
                        now_ts = pd.Timestamp.now()
                        recent_price = (valid.iloc[0]["unit_price"]
                                        if len(valid) else None)
                        three_m = valid[valid["item_date"]
                                        >= now_ts - pd.Timedelta(days=90)]
                        twelve_m = valid[valid["item_date"]
                                         >= now_ts - pd.Timedelta(days=365)]
                        avg_3m = (three_m["unit_price"].mean()
                                  if len(three_m) else None)
                        avg_12m = (twelve_m["unit_price"].mean()
                                   if len(twelve_m) else None)

                        sm1, sm2, sm3, sm4 = st.columns(4)
                        sm1.metric("최근 단가", _money(recent_price))
                        sm2.metric("최근 3M 평균",
                                   _money(avg_3m) if avg_3m else "-",
                                   f"{(recent_price-avg_3m)/avg_3m*100:+.1f}% vs 3M"
                                   if (recent_price and avg_3m and avg_3m > 0)
                                   else None)
                        sm3.metric("12M 평균",
                                   _money(avg_12m) if avg_12m else "-",
                                   f"{(recent_price-avg_12m)/avg_12m*100:+.1f}% vs 12M"
                                   if (recent_price and avg_12m and avg_12m > 0)
                                   else None)
                        sm4.metric("거래 건수 (12M)",
                                   f"{len(twelve_m):,}건")

                        # 월별 평균 line chart
                        if len(valid) >= 2:
                            valid_c = valid.copy()
                            valid_c["월"] = valid_c["item_date"].dt.to_period("M").astype(str)
                            monthly = (valid_c.groupby("월")["unit_price"]
                                       .mean().sort_index())
                            if len(monthly) >= 2:
                                st.markdown("**월별 평균 단가 추이**")
                                st.line_chart(monthly, height=200,
                                              use_container_width=True)

                        # 최근 거래 표 (상위 20건)
                        st.markdown("**최근 거래 (20건)**")
                        df_show = df_s.head(20).copy()
                        df_show["item_date"] = df_show["item_date"].dt.strftime("%Y-%m-%d")
                        df_show["unit_price"] = df_show["unit_price"].apply(
                            lambda v: f"{v:,.0f}" if pd.notna(v) else "-")
                        df_show["amount"] = df_show["amount"].apply(
                            lambda v: f"{v:,.0f}" if pd.notna(v) else "-")
                        df_show["qty"] = df_show["qty"].apply(
                            lambda v: f"{v:,.0f}" if pd.notna(v) else "-")
                        st.dataframe(
                            df_show[["item_date","customer","qty","unit",
                                     "unit_price","amount","remark"]].rename(
                                columns={"item_date":"거래일","customer":"고객사",
                                         "qty":"수량","unit":"단위",
                                         "unit_price":"단가","amount":"금액",
                                         "remark":"비고"}),
                            use_container_width=True, hide_index=True, height=280
                        )

                    # ── 📋 BOM 행 + 공정행 단가 인라인 편집 ──
                    st.divider()
                    st.markdown("##### 📋 BOM 행 / 공정행 단가 편집")
                    try:
                        bom_rows = fetch("bom",
                            "bom_id,process_type,material_id,raw_material_name,"
                            "qty_per_pc,shared_factor,unit_price,lot_label,"
                            "verification_status",
                            f"product_id=eq.{row['product_id']}&order=bom_id.asc",
                            limit=50)
                    except Exception as e:
                        st.error(f"BOM 조회 실패: {e}"); bom_rows = []

                    if not bom_rows:
                        st.info("이 제품에 등록된 BOM 행이 없습니다. "
                                "🚀 BOM 빠른 정비 또는 🔗 BOM 편집에서 등록.")
                    else:
                        bom_df = pd.DataFrame(bom_rows)
                        for c in ["qty_per_pc","shared_factor","unit_price"]:
                            bom_df[c] = pd.to_numeric(bom_df[c], errors="coerce")

                        # per_pc 미리보기
                        def _calc_pp(r):
                            up = r.get("unit_price")
                            qp = r.get("qty_per_pc") or 1
                            sf = r.get("shared_factor") or 1
                            if pd.notna(up) and up and sf:
                                return up * qp / sf
                            return None
                        bom_df["per_pc"] = bom_df.apply(_calc_pp, axis=1)

                        edit_df = bom_df[["bom_id","process_type",
                                          "raw_material_name","qty_per_pc",
                                          "shared_factor","unit_price","per_pc",
                                          "lot_label"]].copy()

                        st.caption(
                            "**unit_price (LOT 단가)** 만 편집하세요. 수량 정보는 BOM 편집 화면에서. "
                            "자재행은 unit_price 비워두면 매입 평균에서 자동 산정됩니다."
                        )
                        edited_bom = st.data_editor(
                            edit_df,
                            column_config={
                                "bom_id": st.column_config.NumberColumn(
                                    "ID", disabled=True, width="small"),
                                "process_type": st.column_config.TextColumn(
                                    "구분", disabled=True, width="small"),
                                "raw_material_name": st.column_config.TextColumn(
                                    "자재/공정", disabled=True, width="large"),
                                "qty_per_pc": st.column_config.NumberColumn(
                                    "qty/PC", format="%.3f", disabled=True),
                                "shared_factor": st.column_config.NumberColumn(
                                    "분할/LOT", format="%.0f", disabled=True),
                                "unit_price": st.column_config.NumberColumn(
                                    "LOT 단가 ✏️", format="%.2f",
                                    help="여기서 편집 가능"),
                                "per_pc": st.column_config.NumberColumn(
                                    "per_pc (자동)", format="%.2f", disabled=True),
                                "lot_label": st.column_config.TextColumn(
                                    "단위", disabled=True, width="small"),
                            },
                            hide_index=True, use_container_width=True,
                            num_rows="fixed",
                            key=f"cost_bom_editor_{row['product_id']}")

                        if st.button("💾 BOM 단가 저장",
                                     type="primary",
                                     key=f"cost_bom_save_{row['product_id']}"):
                            chg = 0
                            for o, n in zip(bom_rows, edited_bom.to_dict("records")):
                                o_up = o.get("unit_price")
                                n_up = n.get("unit_price")
                                # NaN safety
                                o_v = None if (o_up is None or pd.isna(o_up)) else float(o_up)
                                n_v = None if (n_up is None or pd.isna(n_up)) else float(n_up)
                                if o_v != n_v:
                                    try:
                                        if _db.update("bom",
                                            f"bom_id=eq.{o['bom_id']}",
                                            {"unit_price": n_v}):
                                            chg += 1
                                    except Exception:
                                        pass
                            if chg:
                                st.success(f"✅ {chg}건 단가 변경 저장")
                                st.rerun()
                            else:
                                st.info("변경 사항 없음")
        else:
            st.caption("검색어를 입력하세요.")

    # ════════════════════════════════════════════════
    # Tab 3: 이상치 탐지
    # ════════════════════════════════════════════════
    with tabs[2]:
        st.markdown("### 이상치 유형 선택")
        outlier_kind = st.radio(
            "유형",
            ["역마진 (margin < 0%)",
             "저마진 (0 ≤ margin < 10%)",
             "원가 데이터 누락",
             "소재비 과다 (판매가의 50% 초과)",
             "원가 > 판매가 (적자)"],
            horizontal=True,
            key="outlier_kind"
        )

        ol_limit = st.number_input("최대 표시 행", 20, 500, 100, 20, key="ol_limit")

        try:
            if outlier_kind.startswith("역마진"):
                rows = fetch(SRC_TABLE, COST_FIELDS,
                    "archived_at=is.null&margin_pct=lt.0&order=margin_pct.asc",
                    limit=int(ol_limit))
            elif outlier_kind.startswith("저마진"):
                rows = fetch(SRC_TABLE, COST_FIELDS,
                    "archived_at=is.null&margin_pct=gte.0&margin_pct=lt.10"
                    "&order=margin_pct.asc", limit=int(ol_limit))
            elif outlier_kind.startswith("원가 데이터 누락"):
                # estimated_cost_per_pc IS NULL or = 0
                rows = fetch(SRC_TABLE, COST_FIELDS,
                    "archived_at=is.null&or=(estimated_cost_per_pc.is.null,estimated_cost_per_pc.eq.0)"
                    "&order=total_sales_12m.desc.nullslast", limit=int(ol_limit))
            elif outlier_kind.startswith("소재비 과다"):
                rows = fetch(SRC_TABLE, COST_FIELDS,
                    "archived_at=is.null&avg_unit_price=gt.0&material_unit_price=gt.0"
                    "&order=total_sales_12m.desc.nullslast", limit=2000)
                # 클라이언트 측 필터
                rows = [r for r in rows if
                        (float(r.get("material_unit_price") or 0) >
                         float(r.get("avg_unit_price") or 0) * 0.5)]
                rows = rows[:int(ol_limit)]
            else:  # 원가>판매가
                rows = fetch(SRC_TABLE, COST_FIELDS,
                    "archived_at=is.null&avg_unit_price=gt.0&estimated_cost_per_pc=gt.0"
                    "&order=total_sales_12m.desc.nullslast", limit=2000)
                rows = [r for r in rows if
                        (float(r.get("estimated_cost_per_pc") or 0) >
                         float(r.get("avg_unit_price") or 0))]
                rows = rows[:int(ol_limit)]
        except Exception as e:
            st.error(f"조회 실패: {e}"); rows = []

        st.caption(f"검출: **{len(rows):,}건**")

        if rows:
            df_o = pd.DataFrame(rows)
            for c in ["material_unit_price", "outsourcing_per_pc",
                      "heat_treat_per_pc", "surface_per_pc",
                      "estimated_cost_per_pc", "avg_unit_price",
                      "margin_pct", "total_sales_12m"]:
                if c in df_o.columns:
                    df_o[c] = pd.to_numeric(df_o[c], errors="coerce")

            df_o["판매가"] = df_o["avg_unit_price"].apply(_money)
            df_o["소재비"] = df_o["material_unit_price"].apply(_money)
            df_o["외주비"] = df_o["outsourcing_per_pc"].apply(_money)
            df_o["열처리"] = df_o["heat_treat_per_pc"].apply(_money)
            df_o["표면"] = df_o["surface_per_pc"].apply(_money)
            df_o["추정원가"] = df_o["estimated_cost_per_pc"].apply(_money)
            df_o["마진율"] = df_o["margin_pct"].apply(_pct)
            df_o["12M매출"] = df_o["total_sales_12m"].apply(_money)

            cols = ["pn", "customer", "product_group", "판매가", "소재비",
                    "외주비", "열처리", "표면", "추정원가", "마진율",
                    "12M매출", "abc_grade", "cost_data_quality"]
            show = df_o[[c for c in cols if c in df_o.columns]].rename(columns={
                "pn": "품번", "customer": "고객사", "product_group": "제품군",
                "abc_grade": "ABC", "cost_data_quality": "데이터품질"
            })
            st.dataframe(show, use_container_width=True, hide_index=True, height=520)

            csv = show.to_csv(index=False).encode("utf-8-sig")
            st.download_button("📥 CSV 다운로드", csv,
                file_name=f"cost_outliers_{outlier_kind[:6]}.csv",
                mime="text/csv", use_container_width=False)
        else:
            st.info("해당 조건의 이상치가 없습니다.")

    # ════════════════════════════════════════════════
    # Tab 4: BOM 재산정 보조 (shared_factor 적용 시뮬레이션)
    # ════════════════════════════════════════════════
    with tabs[3]:
        st.markdown("### 🧮 BOM 재산정 보조")
        st.caption(
            "원리: **실제 소재비/EA = (qty_per_pc × 자재단가) / shared_factor**. "
            "현재 `products.material_unit_price`는 shared_factor 미반영 스냅샷이라 "
            "분할가공(예: 환봉 1개 → N제품) 품목에서 과대 산정될 수 있습니다. "
            "BOM 의 shared_factor 가 적용된 재계산 값을 미리 보고 일괄/단건으로 적용하세요."
        )

        # ── 모드 선택 ──
        mode = st.radio("분석 범위", [
            "🎯 의심 품목 자동 추출 (소재비 > 판매가 × 50%)",
            "🔍 품번 검색 (단일 제품 상세)",
        ], horizontal=True, key="bom_recalc_mode")

        # ════════════════════
        # 모드 A: 의심 품목 자동 추출
        # ════════════════════
        if mode.startswith("🎯"):
            r_limit = st.number_input("최대 검토 행수", 10, 500, 50, 10,
                                       key="bom_recalc_limit")

            # 1) 의심 후보: 판매가 > 0, 소재비 > 판매가*0.5
            try:
                cand = fetch(SRC_TABLE,
                    "product_id,pn,customer,material_kg_price,material_unit_price,"
                    "outsourcing_per_pc,heat_treat_per_pc,surface_per_pc,"
                    "estimated_cost_per_pc,avg_unit_price,margin_pct,total_sales_12m",
                    "archived_at=is.null&avg_unit_price=gt.0&material_unit_price=gt.0"
                    "&order=total_sales_12m.desc.nullslast", limit=2000)
            except Exception as e:
                st.error(f"제품 조회 실패: {e}"); cand = []

            cand = [r for r in cand if
                    (float(r.get("material_unit_price") or 0) >
                     float(r.get("avg_unit_price") or 0) * 0.5)]
            cand = cand[:int(r_limit)]

            if not cand:
                st.info("의심 품목 없음. (또는 한도 내 매칭 없음)"); st.stop()

            # 2) 해당 제품들의 BOM 조회 (product_id IN)
            pids = [r["product_id"] for r in cand]
            pids_q = ",".join(f'"{p}"' for p in pids[:300])
            try:
                bom_rows = fetch("bom",
                    "bom_id,product_id,material_id,raw_material_name,"
                    "qty_per_pc,shared_factor",
                    f"product_id=in.({pids_q})&order=product_id.asc",
                    limit=5000)
            except Exception as e:
                st.error(f"BOM 조회 실패: {e}"); bom_rows = []

            # product_id → BOM 행들
            bom_by_pid = {}
            for b in bom_rows:
                bom_by_pid.setdefault(b["product_id"], []).append(b)

            # 3) 재계산 수행
            rows = []
            for c in cand:
                pid = c["product_id"]
                bs = bom_by_pid.get(pid, [])
                # 주 BOM 한 줄 기준: shared_factor의 평균 또는 최대값 사용
                # 실무: 1개 제품에 BOM 다수면 행별로 계산해야 하지만 화면 단순화 위해 합산.
                cur_mat = float(c.get("material_unit_price") or 0)
                # 단순화: shared_factor 가장 큰 것 적용 (가장 큰 분할가공)
                max_sf = max((float(b.get("shared_factor") or 1) for b in bs), default=1) if bs else 1
                # qty_per_pc 합 (자재 여러 개일 때)
                sum_qpc = sum(float(b.get("qty_per_pc") or 1) for b in bs) if bs else 1
                # 추정 재계산값: cur_mat / max_sf (가장 보수적)
                est_recalc = cur_mat / max_sf if max_sf > 0 else cur_mat
                # 더 정확한 BOM 기반: cur_mat × sum_qpc / max_sf
                est_bom = cur_mat * sum_qpc / max_sf if max_sf > 0 else cur_mat

                rows.append({
                    "product_id": pid,
                    "pn": c.get("pn"),
                    "customer": c.get("customer"),
                    "판매가": float(c.get("avg_unit_price") or 0),
                    "현재_소재비": cur_mat,
                    "소재비/판매가": (cur_mat / float(c["avg_unit_price"]) * 100)
                                       if float(c["avg_unit_price"]) > 0 else 0,
                    "BOM_행수": len(bs),
                    "qty_per_pc합": sum_qpc,
                    "shared_factor(최대)": max_sf,
                    "재산정_단순": round(est_recalc, 2),
                    "재산정_BOM": round(est_bom, 2),
                    "현재_추정원가": float(c.get("estimated_cost_per_pc") or 0),
                    "12M매출": float(c.get("total_sales_12m") or 0),
                    "마진율": c.get("margin_pct"),
                })

            df_r = pd.DataFrame(rows)
            st.caption(f"의심 후보: **{len(df_r):,}건**, 그 중 shared_factor > 1: "
                       f"**{int((df_r['shared_factor(최대)'] > 1).sum()):,}건** (재계산 효과 있음)")

            # 표시용 포맷
            disp = df_r.copy()
            for c in ["판매가", "현재_소재비", "재산정_단순", "재산정_BOM",
                      "현재_추정원가", "12M매출"]:
                disp[c] = disp[c].apply(lambda v: _money(v))
            disp["소재비/판매가"] = disp["소재비/판매가"].apply(lambda v: f"{v:.0f}%")
            disp["마진율"] = disp["마진율"].apply(_pct)

            show_cols = ["pn", "customer", "판매가", "현재_소재비",
                         "소재비/판매가", "BOM_행수", "qty_per_pc합",
                         "shared_factor(최대)", "재산정_단순", "재산정_BOM",
                         "12M매출", "마진율"]
            disp = disp.rename(columns={"pn": "품번", "customer": "고객사"})
            st.dataframe(
                disp[[("품번" if c == "pn" else "고객사" if c == "customer" else c)
                      for c in show_cols]],
                use_container_width=True, hide_index=True, height=480
            )

            st.divider()
            st.markdown("##### 🚀 일괄 적용")
            apply_col1, apply_col2, apply_col3 = st.columns([2, 2, 2])
            with apply_col1:
                apply_kind = st.selectbox("적용할 값", [
                    "재산정_단순 (현재값 ÷ shared_factor)",
                    "재산정_BOM (현재값 × qty/PC ÷ shared_factor)",
                ], key="recalc_apply_kind")
            with apply_col2:
                only_sf_gt1 = st.checkbox(
                    "shared_factor > 1 인 행만 적용 (안전)",
                    value=True, key="recalc_only_sf")
            with apply_col3:
                update_est = st.checkbox(
                    "estimated_cost_per_pc 도 동시 재계산 "
                    "(= 신_소재비 + 외주 + 열처리 + 표면)",
                    value=True, key="recalc_update_est")

            if st.button("✅ 검토 완료 — 위 추출 결과에 일괄 적용",
                          type="primary", key="recalc_apply_btn"):
                target = df_r.copy()
                if only_sf_gt1:
                    target = target[target["shared_factor(최대)"] > 1]
                if target.empty:
                    st.warning("적용 대상이 없습니다.")
                else:
                    ok_n, fail_n = 0, 0
                    for _, r in target.iterrows():
                        new_mat = (r["재산정_단순"] if apply_kind.startswith("재산정_단순")
                                   else r["재산정_BOM"])
                        payload = {"material_unit_price": float(new_mat)}
                        if update_est:
                            # 외주/열처리/표면은 별도 컬럼에서 가져와 합산
                            try:
                                src = next(c for c in cand
                                           if c["product_id"] == r["product_id"])
                                est = (float(new_mat)
                                       + float(src.get("outsourcing_per_pc") or 0)
                                       + float(src.get("heat_treat_per_pc") or 0)
                                       + float(src.get("surface_per_pc") or 0))
                                payload["estimated_cost_per_pc"] = est
                            except StopIteration:
                                pass
                        try:
                            if _db.update("products",
                                f"product_id=eq.{r['product_id']}", payload):
                                ok_n += 1
                            else:
                                fail_n += 1
                        except Exception:
                            fail_n += 1
                    st.success(
                        f"✅ 적용 완료: {ok_n}건"
                        + (f" / 실패 {fail_n}건" if fail_n else ""))
                    st.rerun()

            csv = df_r.to_csv(index=False).encode("utf-8-sig")
            st.download_button("📥 분석 결과 CSV", csv,
                file_name="bom_recalc_review.csv", mime="text/csv")

        # ════════════════════
        # 모드 B: 품번 검색 (단일)
        # ════════════════════
        else:
            sq = st.text_input("품번 / 품명 / 고객사", key="bom_recalc_search")
            if sq:
                try:
                    matches = fetch(SRC_TABLE,
                        "product_id,pn,customer,material_unit_price,outsourcing_per_pc,"
                        "heat_treat_per_pc,surface_per_pc,estimated_cost_per_pc,"
                        "avg_unit_price,margin_pct",
                        f"or=(pn.ilike.*{sq}*,customer.ilike.*{sq}*)"
                        f"&archived_at=is.null&order=pn.asc", limit=30)
                except Exception as e:
                    st.error(f"검색 실패: {e}"); matches = []

                if not matches:
                    st.info("결과 없음")
                else:
                    labels = [f"{m['pn']} | {m.get('customer','')}" for m in matches]
                    sel = st.selectbox("제품 선택", labels, key="bom_recalc_pick")
                    if sel:
                        m = matches[labels.index(sel)]
                        st.markdown(f"#### {m['pn']} · {m.get('customer') or '-'}")

                        cur_mat = float(m.get("material_unit_price") or 0)
                        sale = float(m.get("avg_unit_price") or 0)

                        # BOM rows
                        try:
                            bs = fetch("bom",
                                "bom_id,material_id,raw_material_name,qty_per_pc,"
                                "shared_factor,verification_status",
                                f"product_id=eq.{m['product_id']}&order=bom_id.asc",
                                limit=50)
                        except Exception as e:
                            st.error(f"BOM 조회 실패: {e}"); bs = []

                        if not bs:
                            st.warning("이 제품에는 BOM 행이 없습니다. BOM 편집에서 먼저 등록하세요.")
                        else:
                            st.markdown("##### BOM 행")
                            bdf = pd.DataFrame(bs)
                            st.dataframe(bdf, use_container_width=True, hide_index=True)

                            max_sf = max(float(b.get("shared_factor") or 1) for b in bs)
                            sum_qpc = sum(float(b.get("qty_per_pc") or 1) for b in bs)

                            est_simple = cur_mat / max_sf if max_sf > 0 else cur_mat
                            est_bom = cur_mat * sum_qpc / max_sf if max_sf > 0 else cur_mat

                            cc1, cc2, cc3, cc4 = st.columns(4)
                            cc1.metric("판매가", _money(sale))
                            cc2.metric("현재 소재비", _money(cur_mat),
                                       f"{cur_mat/sale*100:.0f}%" if sale > 0 else None)
                            cc3.metric("재산정_단순", _money(est_simple),
                                       f"-{(cur_mat-est_simple)/cur_mat*100:.0f}%"
                                       if cur_mat > 0 else None,
                                       delta_color="off")
                            cc4.metric("재산정_BOM", _money(est_bom),
                                       f"-{(cur_mat-est_bom)/cur_mat*100:.0f}%"
                                       if cur_mat > 0 else None,
                                       delta_color="off")

                            st.divider()
                            ac1, ac2 = st.columns([1, 3])
                            with ac1:
                                apply_pick = st.radio("적용값",
                                    ["재산정_단순", "재산정_BOM"],
                                    key="bom_recalc_single_kind")
                            with ac2:
                                if st.button("이 품목에 적용",
                                             type="primary",
                                             key="bom_recalc_single_btn"):
                                    new_mat = (est_simple if apply_pick == "재산정_단순"
                                               else est_bom)
                                    payload = {
                                        "material_unit_price": round(float(new_mat), 2),
                                        "estimated_cost_per_pc": round(
                                            float(new_mat)
                                            + float(m.get("outsourcing_per_pc") or 0)
                                            + float(m.get("heat_treat_per_pc") or 0)
                                            + float(m.get("surface_per_pc") or 0), 2)
                                    }
                                    try:
                                        if _db.update("products",
                                            f"product_id=eq.{m['product_id']}",
                                            payload):
                                            st.success(
                                                f"✅ {m['pn']} 소재비 → "
                                                f"{int(new_mat):,}원 적용 완료")
                                            st.rerun()
                                        else:
                                            st.error("적용 실패")
                                    except Exception as e:
                                        st.error(f"적용 오류: {e}")

    # ════════════════════════════════════════════════
    # Tab 5: 원가 편집 (단건 또는 다건)
    # ════════════════════════════════════════════════
    with tabs[4]:
        st.markdown("### 원가 편집")
        st.caption("⚠️ 저장 시 products 테이블이 즉시 갱신됩니다. "
                   "estimated_cost_per_pc 는 자동 재계산되지 않으므로 직접 입력해 주세요.")

        edit_mode = st.radio("편집 방식",
            ["🔧 단건 편집", "📑 다건 일괄 편집 (검색 결과)"],
            horizontal=True, key="cost_edit_mode")

        # ── 단건 편집 ──
        if edit_mode == "🔧 단건 편집":
            eq = st.text_input("품번 / 품명 / 고객사", key="cost_edit_search")
            if eq:
                try:
                    rows = fetch("products",
                        "product_id,pn,customer,material,raw_material_name,raw_material_spec,"
                        "material_kg_price,material_unit_price,outsourcing_per_pc,"
                        "heat_treat_per_pc,surface_per_pc,estimated_cost_per_pc,cost_data_quality",
                        f"or=(pn.ilike.*{eq}*,customer.ilike.*{eq}*)"
                        f"&archived_at=is.null&order=pn.asc",
                        limit=30)
                except Exception as e:
                    st.error(f"검색 실패: {e}"); rows = []

                if not rows:
                    st.info("검색 결과 없음")
                else:
                    labels = [f"{r['pn']} | {r.get('customer','')}" for r in rows]
                    pick = st.selectbox("편집할 품목", labels, key="cost_edit_pick")
                    if pick:
                        r = rows[labels.index(pick)]
                        with st.form(f"cost_edit_form_{r['product_id']}"):
                            st.markdown(f"**{r['pn']}** · {r.get('customer') or '-'}")
                            ec1, ec2, ec3 = st.columns(3)
                            with ec1:
                                v_mkg = st.number_input("소재 KG단가",
                                    value=float(r.get("material_kg_price") or 0),
                                    step=100.0, format="%.2f")
                                v_mup = st.number_input("소재 개당단가",
                                    value=float(r.get("material_unit_price") or 0),
                                    step=10.0, format="%.2f")
                            with ec2:
                                v_out = st.number_input("외주비/EA",
                                    value=float(r.get("outsourcing_per_pc") or 0),
                                    step=10.0, format="%.2f")
                                v_heat = st.number_input("열처리비/EA",
                                    value=float(r.get("heat_treat_per_pc") or 0),
                                    step=10.0, format="%.2f")
                            with ec3:
                                v_surf = st.number_input("표면처리비/EA",
                                    value=float(r.get("surface_per_pc") or 0),
                                    step=10.0, format="%.2f")
                                v_est = st.number_input("추정원가/EA (합계)",
                                    value=float(r.get("estimated_cost_per_pc") or 0),
                                    step=10.0, format="%.2f")

                            v_quality = st.selectbox("데이터 품질",
                                ["", "high", "medium", "low"],
                                index=["", "high", "medium", "low"].index(
                                    r.get("cost_data_quality") or "")
                                if (r.get("cost_data_quality") or "") in
                                   ["", "high", "medium", "low"] else 0)

                            auto_sum = st.checkbox(
                                "추정원가를 (소재+외주+열처리+표면) 합계로 자동계산",
                                value=False)

                            submit = st.form_submit_button("💾 저장",
                                use_container_width=True, type="primary")

                            if submit:
                                est_val = (v_mup + v_out + v_heat + v_surf) if auto_sum else v_est
                                payload = {
                                    "material_kg_price": v_mkg or None,
                                    "material_unit_price": v_mup or None,
                                    "outsourcing_per_pc": v_out or None,
                                    "heat_treat_per_pc": v_heat or None,
                                    "surface_per_pc": v_surf or None,
                                    "estimated_cost_per_pc": est_val or None,
                                    "cost_data_quality": v_quality or None,
                                }
                                try:
                                    ok = _db.update("products",
                                        f"product_id=eq.{r['product_id']}", payload)
                                    if ok:
                                        st.success(f"✅ {r['pn']} 원가 저장 완료")
                                        st.rerun()
                                    else:
                                        st.error("저장 실패")
                                except Exception as e:
                                    st.error(f"저장 오류: {e}")

        # ── 다건 일괄 편집 ──
        else:
            st.markdown("##### 1) 검색 → 2) 표 내 직접 수정 → 3) 저장")
            bq = st.text_input("검색 (품번/고객사/제품군) — 비우면 50건 노출",
                               key="cost_bulk_search")
            bfetch_limit = st.number_input("최대 행수", 10, 300, 50, 10,
                                           key="cost_bulk_limit")

            parts = ["archived_at=is.null", "order=pn.asc"]
            if bq:
                qq = bq.strip()
                parts.append(f"or=(pn.ilike.*{qq}*,customer.ilike.*{qq}*,product_group.ilike.*{qq}*)")
            try:
                rows = fetch("products",
                    "product_id,pn,customer,material_unit_price,outsourcing_per_pc,"
                    "heat_treat_per_pc,surface_per_pc,estimated_cost_per_pc,cost_data_quality",
                    "&".join(parts), limit=int(bfetch_limit))
            except Exception as e:
                st.error(f"검색 실패: {e}"); rows = []

            if not rows:
                st.info("검색 결과 없음")
            else:
                df_e = pd.DataFrame(rows)
                # 표시할 컬럼 정렬
                for c in ["material_unit_price", "outsourcing_per_pc",
                          "heat_treat_per_pc", "surface_per_pc",
                          "estimated_cost_per_pc"]:
                    df_e[c] = pd.to_numeric(df_e[c], errors="coerce")

                disp = df_e[["product_id", "pn", "customer",
                             "material_unit_price", "outsourcing_per_pc",
                             "heat_treat_per_pc", "surface_per_pc",
                             "estimated_cost_per_pc", "cost_data_quality"]].copy()
                disp = disp.rename(columns={
                    "pn": "품번", "customer": "고객사",
                    "material_unit_price": "소재비",
                    "outsourcing_per_pc": "외주비",
                    "heat_treat_per_pc": "열처리",
                    "surface_per_pc": "표면",
                    "estimated_cost_per_pc": "추정원가",
                    "cost_data_quality": "품질",
                })

                edited = st.data_editor(
                    disp,
                    use_container_width=True,
                    hide_index=True,
                    num_rows="fixed",
                    disabled=["product_id", "품번", "고객사"],
                    column_config={
                        "product_id": st.column_config.NumberColumn("PID", width="small"),
                        "품질": st.column_config.SelectboxColumn(
                            "품질", options=["", "high", "medium", "low"]),
                    },
                    key="cost_bulk_editor"
                )

                cc1, cc2 = st.columns([1, 4])
                with cc1:
                    auto_sum_b = st.checkbox("추정원가 자동합계",
                                             value=False, key="bulk_auto_sum")
                with cc2:
                    save_btn = st.button("💾 변경분 일괄 저장",
                                         type="primary", use_container_width=False)

                if save_btn:
                    # diff 계산
                    orig = disp.set_index("product_id")
                    new = edited.set_index("product_id")
                    changed = []
                    for pid in new.index:
                        o_row = orig.loc[pid]
                        n_row = new.loc[pid]
                        diff = {}
                        col_map = {
                            "소재비": "material_unit_price",
                            "외주비": "outsourcing_per_pc",
                            "열처리": "heat_treat_per_pc",
                            "표면": "surface_per_pc",
                            "추정원가": "estimated_cost_per_pc",
                            "품질": "cost_data_quality",
                        }
                        for k_ui, k_db in col_map.items():
                            o_v = o_row[k_ui]
                            n_v = n_row[k_ui]
                            # NaN 비교 안전
                            if pd.isna(o_v) and pd.isna(n_v):
                                continue
                            if o_v != n_v:
                                diff[k_db] = (None if (pd.isna(n_v) or n_v == "" or n_v == 0)
                                              else (n_v if isinstance(n_v, str) else float(n_v)))
                        if auto_sum_b:
                            est_sum = (
                                (float(n_row["소재비"]) if not pd.isna(n_row["소재비"]) else 0) +
                                (float(n_row["외주비"]) if not pd.isna(n_row["외주비"]) else 0) +
                                (float(n_row["열처리"]) if not pd.isna(n_row["열처리"]) else 0) +
                                (float(n_row["표면"]) if not pd.isna(n_row["표면"]) else 0)
                            )
                            diff["estimated_cost_per_pc"] = est_sum or None
                        if diff:
                            changed.append((int(pid), diff))

                    if not changed:
                        st.info("변경된 행이 없습니다.")
                    else:
                        ok_n, fail_n = 0, 0
                        for pid, payload in changed:
                            try:
                                if _db.update("products", f"product_id=eq.{pid}", payload):
                                    ok_n += 1
                                else:
                                    fail_n += 1
                            except Exception:
                                fail_n += 1
                        st.success(f"✅ 저장 완료: {ok_n}건"
                                   + (f" / 실패 {fail_n}건" if fail_n else ""))
                        st.rerun()

    # ════════════════════════════════════════════════
    # Tab 6: 통합 view (Beta) — product_cost_full_v 사용
    # ════════════════════════════════════════════════
    with tabs[5]:
        st.markdown("### 🏗 통합 원가 view (Beta)")
        st.caption(
            "Migration 007/008 적용 시 자동 활성. **BOM 기반 자동 원가 + legacy fallback + "
            "데이터 신뢰도 배지** 를 한 곳에서 확인."
        )

        cs_filter = st.multiselect(
            "신뢰도 필터",
            ["BOM_FULL", "BOM_PARTIAL", "LEGACY_ONLY", "NO_DATA"],
            default=["BOM_FULL", "BOM_PARTIAL", "LEGACY_ONLY"],
            key="cs_filter")
        cv_limit = st.number_input("최대 행수", 50, 1000, 200, 50, key="cv_limit")

        # view 조회 시도 — 미적용 시 graceful fail
        try:
            cv_rows = fetch("product_cost_full_v",
                "product_id,pn,customer,product_group,"
                "legacy_estimated_cost,bom_cost_per_pc,material_cost_per_pc,"
                "heat_cost_per_pc,surface_cost_per_pc,outsource_cost_per_pc,"
                "final_cost_per_pc,sale_price,margin_pct_calc,"
                "cost_source,bom_row_count,material_rows,process_rows,"
                "total_sales_12m,abc_grade",
                "order=total_sales_12m.desc.nullslast",
                limit=int(cv_limit))
            view_available = True
        except Exception as e:
            cv_rows = []
            view_available = False
            st.warning(
                f"⚠️ `product_cost_full_v` 가 아직 적용되지 않았습니다. "
                f"Migration 007/008 을 SQL Editor 에서 실행하세요. ({str(e)[:80]})"
            )

        if view_available and cv_rows:
            df_v = pd.DataFrame(cv_rows)
            if cs_filter:
                df_v = df_v[df_v["cost_source"].isin(cs_filter)]

            # 통계 헤더
            n_full = (df_v["cost_source"] == "BOM_FULL").sum()
            n_partial = (df_v["cost_source"] == "BOM_PARTIAL").sum()
            n_legacy = (df_v["cost_source"] == "LEGACY_ONLY").sum()
            n_none = (df_v["cost_source"] == "NO_DATA").sum()

            mk1, mk2, mk3, mk4 = st.columns(4)
            mk1.metric("🟢 BOM_FULL", f"{n_full:,}")
            mk2.metric("🟡 BOM_PARTIAL", f"{n_partial:,}")
            mk3.metric("🟠 LEGACY_ONLY", f"{n_legacy:,}")
            mk4.metric("🔴 NO_DATA", f"{n_none:,}")

            # 표시용 변환
            for c in ["legacy_estimated_cost", "bom_cost_per_pc",
                      "material_cost_per_pc", "heat_cost_per_pc",
                      "surface_cost_per_pc", "outsource_cost_per_pc",
                      "final_cost_per_pc", "sale_price", "total_sales_12m"]:
                if c in df_v.columns:
                    df_v[c] = pd.to_numeric(df_v[c], errors="coerce")

            df_v["판매가"] = df_v["sale_price"].apply(_money)
            df_v["BOM원가"] = df_v["bom_cost_per_pc"].apply(_money)
            df_v["legacy원가"] = df_v["legacy_estimated_cost"].apply(_money)
            df_v["최종원가"] = df_v["final_cost_per_pc"].apply(_money)
            df_v["소재"] = df_v["material_cost_per_pc"].apply(_money)
            df_v["열처리"] = df_v["heat_cost_per_pc"].apply(_money)
            df_v["표면"] = df_v["surface_cost_per_pc"].apply(_money)
            df_v["외주"] = df_v["outsource_cost_per_pc"].apply(_money)
            df_v["마진율(계산)"] = df_v["margin_pct_calc"].apply(_pct)
            df_v["12M매출"] = df_v["total_sales_12m"].apply(_money)

            badge_map = {"BOM_FULL": "🟢", "BOM_PARTIAL": "🟡",
                         "LEGACY_ONLY": "🟠", "NO_DATA": "🔴"}
            df_v["신뢰도"] = df_v["cost_source"].apply(
                lambda v: f"{badge_map.get(v,'?')} {v}")

            show_cols = ["pn", "customer", "신뢰도", "판매가", "최종원가",
                         "마진율(계산)", "BOM원가", "legacy원가",
                         "소재", "열처리", "표면", "외주",
                         "bom_row_count", "12M매출", "abc_grade"]
            disp_v = df_v[[c for c in show_cols if c in df_v.columns]].rename(columns={
                "pn": "품번", "customer": "고객사",
                "bom_row_count": "BOM행수", "abc_grade": "ABC"
            })
            st.dataframe(disp_v, use_container_width=True,
                         hide_index=True, height=520)

            st.caption(
                "👉 **BOM_PARTIAL** / **LEGACY_ONLY** 품목을 BOM 편집에서 보완하면 "
                "자동으로 BOM_FULL 로 격상됩니다. "
                "**BOM원가** 와 **legacy원가** 가 크게 다르면 BOM 단가 정확도 점검 필요."
            )

            csv = disp_v.to_csv(index=False).encode("utf-8-sig")
            st.download_button("📥 CSV 다운로드", csv,
                file_name="product_cost_full.csv", mime="text/csv")
        elif view_available:
            st.info("표시할 행이 없습니다.")


st.divider()
st.caption("© 2026 우성정밀 · 부산광역시 기장군 산단4로 71")
