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


# ─── 2a 시안: 정밀 라이트 × IBM Plex Sans KR (DESIGN_HANDOFF.md) ───
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap');
:root{
  --primary:#24406b;--link:#3b5b8c;--bg:#f4f5f7;--card:#ffffff;
  --line:#e2e5ea;--line2:#eceef2;--line3:#f2f3f6;
  --ink:#1b2a41;--body:#333a45;--dim:#7a828d;--faint:#9aa1ab;--mute:#b6bcc4;
  --warn:#e8590c;--warn2:#d9480f;--warn-bg:#fff4e6;
  --good:#2f9e44;--good-bg:#e6f7ec;
  --note:#f0b429;--note-txt:#b08a1e;--note-bg:#fdf6e3;
  --primary-bg:#eef2f8;--blue-bg:#e7f0ff;
}
html, body, [class*="css"], font, div, span, p, label, input, textarea,
button, select {
  font-family:'IBM Plex Sans KR',sans-serif !important;
}
/* Material 아이콘은 아이콘 폰트 유지 (전역 폰트 강제의 예외) */
span[data-testid="stIconMaterial"],
[class*="material-symbols"], [class*="material-icons"]{
  font-family:'Material Symbols Rounded','Material Icons' !important;
}

/* ── 제목 위계 ── */
h1{font-size:22px !important;font-weight:700 !important;
   color:var(--ink) !important;letter-spacing:-.2px;}
h2,h3{color:var(--ink) !important;font-weight:600 !important;}
h5{font-size:14.5px !important;font-weight:600 !important;
   color:var(--ink) !important;}

/* ── KPI 메트릭 → 카드 (보더 구분, 그림자 없음) ── */
div[data-testid="stMetric"]{
  background:var(--card);border:1px solid var(--line);border-radius:6px;
  padding:14px 16px;
}
div[data-testid="stMetricLabel"] p{
  font-size:11.5px !important;font-weight:600 !important;
  color:var(--faint) !important;letter-spacing:.02em;
}
div[data-testid="stMetricValue"]{
  font-size:24px !important;font-weight:700 !important;
  color:var(--ink) !important;letter-spacing:-.3px;
}
div[data-testid="stMetricDelta"]{font-size:12px !important;}

/* ── 탭 ── */
div[data-testid="stTabs"] button[data-baseweb="tab"]{
  font-weight:600;color:var(--dim);font-size:13.5px;
}
div[data-testid="stTabs"] button[aria-selected="true"]{
  color:var(--primary);
}

/* ── expander → 카드 ── */
div[data-testid="stExpander"]{
  background:var(--card);border:1px solid var(--line) !important;
  border-radius:6px;box-shadow:none;
}

/* ── 버튼 ── */
div[data-testid="stButton"] button,
div[data-testid="stDownloadButton"] button{
  border-radius:6px;font-weight:600;font-size:13px;
  border:1px solid #d8dbe0;
}
div[data-testid="stButton"] button[kind="primary"],
div[data-testid="stDownloadButton"] button[kind="primary"]{
  background:var(--primary) !important;border-color:var(--primary) !important;
}

/* ── 사이드바: 216px 흰 배경, 우측 1px 보더 ── */
section[data-testid="stSidebar"]{
  background:var(--card);border-right:1px solid var(--line);
  min-width:216px !important;max-width:246px !important;
}
section[data-testid="stSidebar"] h2{
  font-size:15px !important;color:var(--ink) !important;
}
section[data-testid="stSidebar"] div[data-testid="stCaptionContainer"] p{
  font-size:11px !important;font-weight:600 !important;
  color:var(--faint) !important;letter-spacing:.06em;
  text-transform:uppercase;
}
section[data-testid="stSidebar"] label[data-baseweb="radio"] div p{
  font-size:13.5px !important;color:var(--body);
}

/* ── 알림 박스 ── */
div[data-testid="stAlert"]{
  border-radius:6px;border-left-width:4px !important;
}

/* ── 데이터프레임 ── */
div[data-testid="stDataFrame"]{
  border:1px solid var(--line);border-radius:6px;
}

/* ── 헤더 ── */
.ws-hdr{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:4px}
.ws-hdr .t{font-size:22px;color:var(--ink);font-weight:700;letter-spacing:-.2px}
.ws-hdr .t .co{color:var(--primary)}
.ws-hdr .sub{color:var(--dim);font-size:13.5px}
.ws-hdr-meta{margin-left:auto;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.ws-chip{background:var(--card);border:1px solid var(--line);border-radius:15px;
  padding:5px 12px;font-size:12px;color:var(--dim);
  display:inline-flex;gap:6px;align-items:center}
.ws-chip b{font-weight:600}
.ws-chip.ok b{color:var(--good)}
.ws-chip.err b{color:var(--warn2)}

/* ── 홈 KPI 카드 (border-top 상태색) ── */
.kpi-row{display:flex;gap:14px;flex-wrap:wrap;margin:4px 0 10px}
.kpi{flex:1;min-width:150px;background:var(--card);
  border:1px solid var(--line);border-top:3px solid var(--primary);
  border-radius:6px;padding:14px 16px}
.kpi .k{font-size:11.5px;font-weight:600;color:var(--faint);
  letter-spacing:.02em;margin-bottom:6px}
.kpi .v{font-size:27px;font-weight:700;color:var(--ink);
  letter-spacing:-.3px;line-height:1.1}
.kpi .s{font-size:12px;color:var(--dim);margin-top:4px}
.kpi.warn{border-top-color:var(--warn)}
.kpi.good{border-top-color:var(--good)}
.kpi.zero{border-top-color:var(--line)}
.kpi.zero .v{color:var(--mute)}

/* ── 공정 스테퍼 (투입→생산→외주→검사→완성) ── */
.stepper{display:flex;gap:6px;margin:6px 0 10px}
.step{flex:1;text-align:center;font-size:12px;font-weight:600;
  padding:7px 4px;border:1px solid var(--line);border-radius:4px;
  color:var(--faint);background:var(--card)}
.step.on{background:var(--blue-bg);color:var(--primary);
  border-color:var(--primary)}
.step.done{background:var(--good-bg);color:var(--good);
  border-color:var(--good)}
.step.warn{background:var(--warn-bg);color:var(--warn2);
  border-color:var(--warn2)}
</style>
""", unsafe_allow_html=True)

# ─── 헤더 (회사명 강조 + 연동 상태 pill) ───
_db_chip = ('<span class="ws-chip ok">연동 <b>LIVE</b></span>' if DB_AVAILABLE
            else '<span class="ws-chip err">연동 <b>연결 대기</b></span>')
st.markdown(f"""
<div class="ws-hdr">
  <span class="t"><span class="co">우성정밀</span> 업무관리 시스템</span>
  <span class="sub">수주 · 발주 · 원가 · 생산 계획 — Supabase 실시간 연동</span>
  <div class="ws-hdr-meta">{_db_chip}</div>
</div>
""", unsafe_allow_html=True)

st.divider()


# ─── 상태 표기 (영문 코드 → 한글 배지) ───
STATUS_KO = {
    "PENDING": "대기", "PARTIAL": "부분 진행", "DELIVERED": "완납",
    "DRAFT": "작성", "CONFIRMED": "확정", "IN_PROD": "생산중",
    "SENT": "발송", "RECEIVED": "입고완료",
    "CANCELED": "취소", "CANCELLED": "취소", "CLOSED": "종결",
    "OUTSOURCE": "외주중", "INSPECT": "검사 대기",
    "REWORK": "재작업중", "READY": "완성 대기",
}
def status_ko(s):
    """DB 상태 코드 → 한글 배지 (미정의 코드는 원문 유지)"""
    return STATUS_KO.get(str(s or "").upper(), s or "-")


# 상태 색 규칙 (2a 시안 DESIGN_HANDOFF) — 색 = 의미 고정:
#   진한 주황 #d9480f = 문제(지연·불합격·폐기·부족) / 주황 #e8590c =
#   진행 대기(부분·외주·재작업) / 초록 #2f9e44 = 완료·합격 /
#   주색 #24406b = 생산중·활성 — 전 페이지 동일 규칙.
_ST_RED = ("지연", "불합", "폐기", "취소", "부족")
_ST_GREEN = ("완납", "입고완료", "합격", "완료", "전량", "종결", "완성")
_ST_AMBER = ("대기", "부분", "외주", "재작업", "미납")
_ST_BLUE = ("생산중", "확정", "발송")


def status_style(df, cols=("상태",)):
    """상태 컬럼에 의미 색 적용한 Styler 반환 (색 규칙 참조)"""
    def _c(v):
        s = str(v)
        if any(k in s for k in _ST_RED):
            return "color:#d9480f;font-weight:700"
        if any(k in s for k in _ST_GREEN):
            return "color:#2f9e44;font-weight:600"
        if any(k in s for k in _ST_AMBER):
            return "color:#e8590c;font-weight:600"
        if any(k in s for k in _ST_BLUE):
            return "color:#24406b;font-weight:600"
        return "color:#7a828d"
    _sub = [c for c in cols if c in df.columns]
    if not _sub:
        return df
    try:
        return df.style.map(_c, subset=_sub)
    except AttributeError:          # pandas < 2.1
        return df.style.applymap(_c, subset=_sub)


def wo_stage_qty(t):
    """wo_tracking 행 → 단계별 수량. 상태는 행위의 부산물 원칙 —
    모든 단계 수량은 누적 필드에서 유도 (직접 저장 없음)."""
    def f(k):
        return float(t.get(k) or 0)
    rew = f("rework_qty") - f("rework_in_qty")
    return {
        "생산중": max(0.0, f("input_qty") - f("received_qty")),
        "외주중": max(0.0, f("outsource_qty") - f("outsource_in_qty")),
        "재작업중": max(0.0, rew),
        "검사대기": max(0.0, f("received_qty") + f("outsource_in_qty")
                     - f("outsource_qty") - f("pass_qty")
                     - f("scrap_qty") - f("return_qty") - rew),
        "완성": f("output_qty"),
        "반품": f("return_qty"),
    }


EVENT_KO = {
    "INPUT": "투입", "RECEIVE": "완료 인수",
    "OUT_SEND": "외주 출고", "OUT_RETURN": "외주 입고",
    "INSPECT": "검사", "REWORK_BACK": "재작업 복귀",
    "OUTPUT": "완성 확정",
}


def wo_derive_status(t):
    """단계 수량 → 상태 자동 유도 (앞 단계 우선)"""
    q = wo_stage_qty(t)
    if q["생산중"] > 0:
        return "IN_PROD"
    if q["외주중"] > 0:
        return "OUTSOURCE"
    if q["재작업중"] > 0:
        return "REWORK"
    if q["검사대기"] > 0:
        return "INSPECT"
    if (q["완성"] > 0 or q["반품"] > 0
            or float(t.get("scrap_qty") or 0) > 0):
        return "CLOSED"
    return t.get("status") or "IN_PROD"

def n_fmt(v):
    """KPI 숫자 천단위 콤마 (숫자가 아니면 그대로)"""
    try:
        return f"{int(v):,}" if float(v) == int(float(v)) else f"{float(v):,.1f}"
    except (TypeError, ValueError):
        return v if v is not None else "-"


def w_lot_next(count=1):
    """소재 LOT (W번호) 채번 — app_settings.w_lot_counter 기반.

    반환: ["W0905", ...] count개. 카운터 미설정 시 None (입고는 W번호
    없이 진행 가능, 공정 관리 → 설정에서 시작 번호 등록 안내).
    """
    if count <= 0:
        return []
    try:
        import db as _dbw
        row = _dbw.fetch_one("app_settings", "key=eq.w_lot_counter", "value")
        val = str((row or {}).get("value") or "").strip()
        if not val.isdigit():
            return None
        cur = int(val)
        nums = [cur + i + 1 for i in range(count)]
        _dbw.update("app_settings", "key=eq.w_lot_counter",
                    {"value": str(nums[-1])})
        return [f"W{n:04d}" for n in nums]
    except Exception:
        return None


# ─── 사이드바 — 업무 진행 순서(수주→출고) + 관리자 영역 분리 ───
with st.sidebar:
    # 정비용 페이지 (TOP 정비 등 5종) 는 마스터 안정화 완료 후 코드 제거됨.
    # 필요 시 git 이력 (8421f1e 이전) 에서 복원 가능.
    MENU_FLOW = [
        "홈",
        "수주 관리",
        "생산 계획",
        "발주/입고",
        "공정 관리",
        "출고 관리",
    ]
    MENU_ADMIN = [
        "마스터 관리",
        "원가 확인",
        "생산 보고",
    ]
    ALL_MENU = MENU_FLOW + MENU_ADMIN

    # 두 그룹 radio — 한쪽 선택 시 다른 쪽 해제 (page 는 하나만)
    def _nav_pick_flow():
        st.session_state["nav_admin"] = None

    def _nav_pick_admin():
        st.session_state["nav_flow"] = None

    st.header("업무 진행")
    nav_flow = st.radio("업무", MENU_FLOW, key="nav_flow",
                        on_change=_nav_pick_flow,
                        label_visibility="collapsed")
    st.divider()
    st.caption("관리자")
    nav_admin = st.radio("관리자", MENU_ADMIN, key="nav_admin",
                         index=None, on_change=_nav_pick_admin,
                         label_visibility="collapsed")
    page = nav_admin or nav_flow or "홈"
    st.divider()
    st.caption("시스템")
    if st.button("DB 상태 확인", use_container_width=True):
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

    if st.button("진단 (secrets 점검)", use_container_width=True):
        with st.spinner("..."):
            info = debug_check()
        st.json(info)


# ─── 페이지 라우팅 ───

if page == "홈":
    # ── 업무 진행 대시보드 (2026-07-24 개편) — 수주→출고 전 단계 요약 ──
    if not DB_AVAILABLE:
        st.warning("⚠️ Streamlit Cloud Secrets 등록이 완료되지 않았습니다.")
        st.info("**share.streamlit.io → Settings → Secrets**에 Supabase 키를 "
                "등록하면 활성화됩니다.")
        st.stop()

    import pandas as pd
    from datetime import date as _hd

    st.subheader("업무 진행 현황")
    st.caption("수주 → 소재 → 생산 → 외주 → 완성 → 출고 — 전 단계 실시간 요약. "
               "각 단계의 상세·처리는 좌측 메뉴를 진행 순서대로 이용하세요.")

    try:
        _h_so = fetch("sales_order_stats",
            "so_number,customer,so_date,due_date,total_qty,"
            "total_received_qty,total_pending_qty,delivery_status",
            'status=not.in.("CANCELLED","CANCELED")&order=so_date.desc',
            limit=500)
    except Exception:
        _h_so = []
    try:
        _h_rcv = fetch("po_item_receipt_v",
            "pending_qty,receipt_status", "", limit=300)
    except Exception:
        _h_rcv = []
    try:
        _h_wo = fetch("wo_tracking",
            "wo_number,pn,w_lot,input_qty,received_qty,outsource_qty,"
            "outsource_in_qty,pass_qty,tokusai_qty,rework_qty,"
            "rework_in_qty,scrap_qty,output_qty,status",
            "status=neq.CLOSED&order=created_at.desc", limit=300)
    except Exception:
        _h_wo = []
    try:
        _h_ps = fetch("product_stock_v", "pn,current_stock",
            "current_stock=gt.0&order=current_stock.desc", limit=500)
    except Exception:
        _h_ps = []
    try:
        _h_mes = fetch("production_log", "total_qty",
            f"log_date=eq.{_hd.today().isoformat()}&source=eq.MES_UPLOAD",
            limit=2000)
        _mes_today = sum(float(x.get("total_qty") or 0) for x in _h_mes)
    except Exception:
        _mes_today = 0

    _so_pend = sum(float(s.get("total_pending_qty") or 0) for s in _h_so)
    _so_open = sum(1 for s in _h_so
                   if float(s.get("total_pending_qty") or 0) > 0)
    _rcv_wait = sum(float(r.get("pending_qty") or 0) for r in _h_rcv)
    _in_prod = sum(max(0.0, float(w.get("input_qty") or 0)
                        - float(w.get("received_qty") or 0)) for w in _h_wo)
    _out_wip = sum(max(0.0, float(w.get("outsource_qty") or 0)
                        - float(w.get("outsource_in_qty") or 0))
                   for w in _h_wo)
    _fin_stock = sum(float(p.get("current_stock") or 0) for p in _h_ps)

    # 5단계 KPI 카드 — border-top 상태색, 0은 회색 톤 다운 (2a 시안)
    def _kpi(label, value, sub="", tone="primary"):
        cls = "zero" if value <= 0 else tone
        return (f'<div class="kpi {cls}"><div class="k">{label}</div>'
                f'<div class="v">{value:,.0f}</div>'
                + (f'<div class="s">{sub}</div>' if sub else "")
                + '</div>')

    st.markdown('<div class="kpi-row">'
                + _kpi("미납 수주", _so_pend, f"{_so_open}건 진행", "warn")
                + _kpi("소재 입고 대기", _rcv_wait, tone="warn")
                + _kpi("생산중 (투입)", _in_prod)
                + _kpi("외주중", _out_wip, tone="warn")
                + _kpi("완성 재고", _fin_stock, tone="good")
                + "</div>", unsafe_allow_html=True)
    if _mes_today:
        st.caption(f"오늘 MES 생산 실적: {_mes_today:,.0f} EA "
                   "(상세는 생산 보고)")

    st.divider()
    hc1, hc2 = st.columns(2)

    with hc1:
        st.markdown("##### 수주 진행 (미납 · 납기순)")
        _open_so = [s for s in _h_so
                    if float(s.get("total_pending_qty") or 0) > 0]
        if not _open_so:
            st.info("미납 수주 없음 — 수주 관리에서 업로드하면 표시됩니다.")
        else:
            # 납기 임박·지연이 항상 위로 — 수주 많아져도 볼 것부터 보이게
            _open_so.sort(key=lambda s: s.get("due_date") or "9999-12-31")

            def _h_dday(d):
                if not d:
                    return "-"
                _dd = (_hd.fromisoformat(d) - _hd.today()).days
                if _dd < 0:
                    return f"지연 {-_dd}일"
                return "오늘" if _dd == 0 else f"D-{_dd}"

            _n_late = sum(1 for s in _open_so
                          if s.get("due_date")
                          and s["due_date"] < _hd.today().isoformat())
            if len(_open_so) > 15:
                _hc_opts = ["전체 거래처"] + sorted(
                    {s["customer"] for s in _open_so if s.get("customer")})
                _hcf = st.selectbox("거래처", _hc_opts, key="home_so_cust",
                                    label_visibility="collapsed")
                if _hcf != "전체 거래처":
                    _open_so = [s for s in _open_so
                                if s["customer"] == _hcf]
            _so_cut = len(_open_so) - 15
            _h_sodf = pd.DataFrame([{
                "수주번호": s["so_number"], "거래처": s["customer"],
                "납기": _h_dday(s.get("due_date")),
                "미납": float(s.get("total_pending_qty") or 0),
                "진행률": (float(s.get("total_received_qty") or 0)
                          / float(s.get("total_qty") or 1)),
                "상태": status_ko(s.get("delivery_status")),
            } for s in _open_so[:15]])
            st.dataframe(
                _h_sodf.style.apply(
                    lambda row: ["color: #d9480f; font-weight: 700"
                                 if "지연" in str(row["납기"])
                                 else ""] * len(row), axis=1),
                use_container_width=True, hide_index=True,
                height=min(400, 60 + len(_h_sodf) * 35),
                column_config={
                    "미납": st.column_config.NumberColumn(
                        format="localized", width="small"),
                    "진행률": st.column_config.ProgressColumn(
                        "진행률", min_value=0, max_value=1),
                })
            _so_cap = []
            if _n_late:
                _so_cap.append(f"납기 지연 {_n_late}건")
            if _so_cut > 0:
                _so_cap.append(f"납기순 15건 표시 — 외 {_so_cut:,}건은 "
                               "수주 관리에서 검색")
            if _so_cap:
                st.caption(" · ".join(_so_cap))

    with hc2:
        st.markdown("##### 공정 진행 (작업지시)")
        if not _h_wo:
            st.info("진행 중인 작업지시 없음 — 공정 관리에서 투입 등록으로 "
                    "시작합니다.")
        else:
            st.dataframe(status_style(pd.DataFrame([{
                "작업지시": w["wo_number"], "품번": w.get("pn") or "-",
                "생산중": max(0.0, float(w.get("input_qty") or 0)
                             - float(w.get("received_qty") or 0)),
                "외주중": max(0.0, float(w.get("outsource_qty") or 0)
                             - float(w.get("outsource_in_qty") or 0)),
                "합격": float(w.get("pass_qty") or 0),
                "상태": status_ko(wo_derive_status(w)),
            } for w in _h_wo[:15]])), use_container_width=True,
                hide_index=True,
                height=min(400, 60 + min(len(_h_wo), 15) * 35),
                column_config={c: st.column_config.NumberColumn(
                    format="localized", width="small")
                    for c in ["생산중", "외주중", "합격"]})
            if len(_h_wo) > 15:
                st.caption(f"최근 15건 표시 — 외 {len(_h_wo) - 15:,}건은 "
                           "공정 관리 → 공정 현황판에서 확인")

    # 완성 재고 상위
    if _h_ps:
        st.divider()
        st.markdown("##### 완성 재고 보유 품목")
        st.dataframe(pd.DataFrame([{
            "품번": p["pn"], "재고": float(p.get("current_stock") or 0),
        } for p in _h_ps[:10]]), use_container_width=True, hide_index=True,
            column_config={"재고": st.column_config.NumberColumn(
                format="localized", width="small")})
        if len(_h_ps) > 10:
            st.caption(f"재고 상위 10품목 표시 — 외 {len(_h_ps) - 10:,}품목은 "
                       "출고 관리 → 납품 등록에서 검색")


elif page == "마스터 관리":
    st.subheader("⚙️ 마스터 데이터 관리")

    if not DB_AVAILABLE:
        st.error("DB 연결이 활성화되지 않았습니다."); st.stop()

    import db as _db
    import pandas as pd

    tab1, tab_prod, tab_mat, tab_bom, tab_excl, tab_map, tab2 = st.tabs([
        "거래처 편집", "제품 편집", "자재 편집", "BOM 편집",
        "데이터 제외 규칙",
        "매입↔자재 매핑 (레거시)", "마스터/연결 점검"
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
        with st.expander("신규 거래처 등록"):
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

        if brows:
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
                        help="단가 편집은 원가 확인 → 단가 관리 탭에서. "
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
            sc1, sc2 = st.columns([1, 4])
            with sc1:
                save_clicked = st.button("💾 BOM 변경 저장", type="primary")
            with sc2:
                show_debug = st.checkbox("🔍 변경 내역 확인",
                    value=False, key="bom_save_debug",
                    help="저장 전에 변경 내역을 미리 확인합니다.")

            # Streamlit data_editor 의 edited_rows API 로 정확한 변경 감지
            # (PostgREST 의 NUMERIC 문자열 ↔ data_editor float 비교 회피)
            editor_state = st.session_state.get("bom_editor", {})
            edited_rows = editor_state.get("edited_rows", {}) if isinstance(editor_state, dict) else {}

            # 편집 가능 컬럼 (자재행 unit_price 는 무시)
            editable_keys = {"qty_per_pc", "shared_factor", "verification_status",
                             "process_type", "lot_label", "raw_material_name",
                             "unit_price"}

            if show_debug and edited_rows:
                st.caption(f"🔍 감지된 변경: {len(edited_rows)} 행")
                for row_idx, changes in edited_rows.items():
                    try:
                        orig_row = brows[int(row_idx)]
                        bom_id = orig_row.get("bom_id")
                        pn = orig_row.get("_pn") or "?"
                        st.caption(f"  • BOM #{bom_id} ({pn}): {changes}")
                    except Exception:
                        st.caption(f"  • row_idx={row_idx}: {changes}")

            if save_clicked:
                if not edited_rows:
                    st.info("변경된 셀이 없습니다. data_editor 셀 수정 후 다른 곳 클릭 → 저장 버튼.")
                else:
                    chg = 0
                    fail = 0
                    ignored_mat_unit_price = 0
                    for row_idx, changes in edited_rows.items():
                        try:
                            orig_row = brows[int(row_idx)]
                        except Exception:
                            fail += 1; continue
                        bom_id = orig_row.get("bom_id")
                        if not bom_id:
                            fail += 1; continue

                        # MATERIAL 행 unit_price 무시
                        is_material = (
                            changes.get("process_type")
                            or orig_row.get("process_type")
                            or "MATERIAL"
                        ) == "MATERIAL"

                        upd = {}
                        for k, v in changes.items():
                            if k not in editable_keys:
                                continue
                            if k == "unit_price" and is_material:
                                ignored_mat_unit_price += 1
                                continue
                            if isinstance(v, str) and v.strip() == "":
                                v = None
                            upd[k] = v

                        if not upd:
                            continue

                        try:
                            if _db.update("bom",
                                f"bom_id=eq.{bom_id}", upd):
                                chg += 1
                            else:
                                fail += 1
                                st.warning(f"BOM #{bom_id} 저장 실패: {upd}")
                        except Exception as e:
                            fail += 1
                            st.warning(f"BOM #{bom_id} 저장 오류: {e}")

                    if chg:
                        msg = f"✅ {chg}건 저장 완료"
                        if fail:
                            msg += f" / 실패 {fail}건"
                        if ignored_mat_unit_price:
                            msg += f" / 자재행 단가 무시 {ignored_mat_unit_price}건"
                        st.success(msg)
                        st.rerun()
                    elif fail:
                        st.error(f"❌ 모든 변경 저장 실패 ({fail}건). "
                                 "로그 확인 필요.")
                    else:
                        st.info("변경 사항 없음 (편집 가능 컬럼 외 수정만 시도됨)")

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
                "**LOT 단가는 원가 확인 → 단가 관리** 에서 입력하세요. "
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
                            f"단가는 원가 확인 → 단가 관리에서 입력하세요."
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
                df_e["active"] = df_e["active"].fillna(False).astype(bool)
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


elif page == "수주 관리":
    st.subheader("수주 관리")
    if not DB_AVAILABLE: st.error("DB 연결 필요"); st.stop()

    from datetime import date as _date, timedelta as _td
    from utils.so_parser import (parse_hdx_excel, parse_mijin_excel, parse_mjt_pdf,
                                  group_by_so_number, match_canonical_pn)
    import db as _db
    import pandas as pd
    import re as _re

    # 상단 KPI — 페이지 골격 통일 (요약 → 처리 → 현황)
    try:
        _so_kpi = fetch("sales_order_stats",
            "total_pending_qty,due_date,so_date",
            'status=not.in.("CANCELLED","CANCELED")', limit=500)
    except Exception:
        _so_kpi = []
    _sk_pend = sum(float(s.get("total_pending_qty") or 0) for s in _so_kpi)
    _sk_open = sum(1 for s in _so_kpi
                   if float(s.get("total_pending_qty") or 0) > 0)
    _sk_late = sum(1 for s in _so_kpi
                   if float(s.get("total_pending_qty") or 0) > 0
                   and s.get("due_date")
                   and s["due_date"] < _date.today().isoformat())
    _sk_month = sum(1 for s in _so_kpi
                    if str(s.get("so_date") or "")[:7]
                    == _date.today().isoformat()[:7])
    sk1, sk2, sk3, sk4 = st.columns(4)
    sk1.metric("미납 수량", f"{_sk_pend:,.0f}")
    sk2.metric("진행 수주", f"{_sk_open:,}건")
    sk3.metric("납기 지연", f"{_sk_late:,}건")
    sk4.metric("이번 달 수주", f"{_sk_month:,}건")
    st.divider()

    tab_input, tab_list = st.tabs(
        ["새 수주 입력", "수주 목록"])

    # ════════ TAB 1: 새 수주 입력 ════════
    with tab_input:
        mode = st.radio("입력 방식", ["파일 업로드 자동 파싱", "수기 입력"],
                        horizontal=True)

        if mode == "파일 업로드 자동 파싱":
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

                    # ── 파일 내 중복 라인 감지 ──
                    # 실사례: G264220260 에 동일 라인 4종이 이중 등록됨 (import 중복).
                    # 수주번호+품번+수량+단가+납기가 완전히 같으면 중복으로 판단.
                    from collections import Counter as _Counter
                    def _line_key(it):
                        return (it.get("so_number"),
                                str(it.get("customer_part_no")
                                    or it.get("canonical_pn_hint") or ""),
                                str(it.get("qty")), str(it.get("unit_price")),
                                str(it.get("due_date")))
                    _key_counts = _Counter(_line_key(it) for it in items)
                    _dup_keys = {k for k, c in _key_counts.items() if c > 1}
                    if _dup_keys:
                        n_extra = sum(_key_counts[k] - 1 for k in _dup_keys)
                        st.warning(
                            f"⚠️ **파일 내 동일 라인 중복 {len(_dup_keys)}종 "
                            f"(초과 {n_extra}행)** — 수주번호·품번·수량·단가·납기가 "
                            "완전히 같은 행입니다. 기본으로 1행만 저장합니다.")
                        _dup_prev = [{"수주번호": k[0], "품번": k[1], "수량": k[2],
                                      "단가": k[3], "납기": k[4],
                                      "중복 행수": _key_counts[k]}
                                     for k in sorted(_dup_keys)]
                        st.dataframe(pd.DataFrame(_dup_prev),
                                     use_container_width=True, hide_index=True)
                        keep_dups = st.checkbox(
                            "중복 행을 그대로 모두 저장 (실제로 같은 품목을 "
                            "여러 라인으로 발주한 경우만 체크)",
                            value=False, key="so_up_keep_dups")
                        if not keep_dups:
                            _seen_keys = set()
                            _deduped = []
                            for it in items:
                                k = _line_key(it)
                                if k in _dup_keys and k in _seen_keys:
                                    continue
                                _seen_keys.add(k)
                                _deduped.append(it)
                            items = _deduped
                            st.caption(f"→ 중복 {n_extra}행 제외, "
                                       f"**{len(items)}행** 저장 예정.")

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

            with st.expander("➕ 품목 추가", expanded=True):
                # 수주는 등록된 품목만 가능 (2026-07-24 확정) — 오타
                # 품번이 수주에 들어와 재고/산출 연동이 끊기는 것 방지.
                # 미등록 품번은 아래 '신규 품목 등록'으로 먼저 추가.
                _seed = st.session_state.pop("m_pn_q_seed", None)
                if _seed is not None:
                    st.session_state["m_pn_q"] = _seed
                m_pn_q = st.text_input("품번 검색 (마스터)", key="m_pn_q",
                    placeholder="품번 일부 입력 — 예: MRG4, 8HFDV")
                _m_cands = []
                if (m_pn_q or "").strip():
                    try:
                        _m_cands = fetch("products",
                            "product_id,pn,alias_list",
                            f"or=(pn.ilike.*{m_pn_q.strip()}*,"
                            f"alias_list.ilike.*{m_pn_q.strip()}*)"
                            "&archived_at=is.null&order=pn", limit=30)
                    except Exception:
                        _m_cands = []
                _m_prod = None
                if _m_cands:
                    m_pick = st.selectbox(
                        f"품목 선택 ({len(_m_cands)}건 일치)",
                        [p["pn"] for p in _m_cands], key="m_pn_pick")
                    _m_prod = next(
                        (p for p in _m_cands if p["pn"] == m_pick), None)
                elif (m_pn_q or "").strip():
                    st.warning("일치하는 등록 품목 없음 — 수주는 등록된 "
                               "품목만 입력할 수 있습니다. 아래 '신규 "
                               "품목 등록'으로 마스터에 추가 후 "
                               "선택하세요.")
                ic2, ic3, ic4 = st.columns(3)
                m_qty = ic2.number_input("수량", 0, step=10, key="m_qty")
                m_up = ic3.number_input("단가", 0, step=100, key="m_up")
                m_due_item = ic4.date_input("품목 납기", value=_date.today() + _td(days=14), key="m_due_item")
                if st.button("➕ 추가", key="m_add_item",
                             disabled=not (_m_prod and m_qty)):
                    st.session_state.m_so_items.append({
                        "line_no": len(st.session_state.m_so_items) + 1,
                        "customer_part_no": _m_prod["pn"], "qty": m_qty,
                        "unit_price": m_up, "amount": m_qty * m_up,
                        "due_date": m_due_item,
                        "product_id": _m_prod["product_id"],
                        "canonical_pn": _m_prod["pn"],
                    })
                    st.rerun()

            with st.expander("신규 품목 등록 (마스터 미등록 품번)"):
                st.caption("여기서 마스터에 등록하면 위 검색에서 바로 "
                           "선택할 수 있습니다. BOM·원가 등 상세는 "
                           "마스터 관리 → 제품 편집에서 보완하세요.")
                nq1, nq2 = st.columns(2)
                mq_pn = nq1.text_input("품번 *", key="mq_pn",
                    placeholder="예: 4PDVN-02")
                mq_mat = nq2.text_input("재질", key="mq_mat",
                    placeholder="예: STS630, SCM440")
                nq3, nq4 = st.columns(2)
                mq_spec = nq3.text_input("자재 규격", key="mq_spec",
                    placeholder="예: ⌀25 × 400")
                mq_cust2 = nq4.text_input("거래처", key="mq_cust2",
                    placeholder="비우면 위 거래처명 사용")
                if st.button("품목 등록", key="mq_add",
                             disabled=not (mq_pn or "").strip()):
                    _mq_pn = mq_pn.strip()
                    try:
                        _mq_dup = _db.fetch_one("products",
                            f"pn=eq.{_mq_pn}", "product_id,archived_at")
                    except Exception:
                        _mq_dup = None
                    if _mq_dup:
                        st.error(f"품번 '{_mq_pn}' 이미 존재"
                                 + (" (휴면 — 마스터 관리에서 활성 복귀)"
                                    if _mq_dup.get("archived_at") else "")
                                 + f" — product_id "
                                 f"{_mq_dup['product_id']}")
                    else:
                        try:
                            _mq_latest = fetch("products", "product_id",
                                "product_id=like.P*"
                                "&order=product_id.desc", limit=1)
                            _mq_n = (int(_mq_latest[0]["product_id"][1:])
                                     + 1) if _mq_latest else 1
                        except Exception:
                            _mq_n = 9000
                        _mq_pid = f"P{_mq_n:04d}"
                        try:
                            _db.insert("products", [{
                                "product_id": _mq_pid, "pn": _mq_pn,
                                "customer": (mq_cust2 or m_cust
                                             or "").strip() or None,
                                "material": (mq_mat or "").strip()
                                            or None,
                                "raw_material_spec":
                                    (mq_spec or "").strip() or None,
                                "active": "1",
                            }])
                            st.session_state["m_pn_q_seed"] = _mq_pn
                            st.success(f"✅ 품목 등록: {_mq_pid} | "
                                       f"{_mq_pn} — 위 검색에서 "
                                       "선택하세요.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"등록 실패: {e}")

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
                                "product_id": it.get("product_id"),
                                "canonical_pn": it.get("canonical_pn"),
                                "qty": it["qty"], "unit": "EA",
                                "received_qty": 0,
                                "pending_qty": it["qty"],
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

        fc1, fc2 = st.columns(2)
        with fc1:
            sl_period = st.selectbox("기간", ["이번달", "최근 3개월", "올해", "전체"], index=2)
        with fc2:
            sl_cust = st.text_input("거래처", placeholder="예: HDX, 미진")
        # 상태 필터 칩 (2a 시안 — pills, 구버전은 radio 폴백)
        _sl_opts = ["전체", "DRAFT", "CONFIRMED", "IN_PROD", "PARTIAL",
                    "DELIVERED", "CANCELLED"]
        _sl_fmt = lambda s: "전체" if s == "전체" else status_ko(s)
        if hasattr(st, "pills"):
            sl_status = st.pills("상태", _sl_opts, default="전체",
                                 format_func=_sl_fmt,
                                 key="so_status_pills") or "전체"
        else:
            sl_status = st.radio("상태", _sl_opts, format_func=_sl_fmt,
                                 horizontal=True, key="so_status_radio")

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
                    "납품상태": status_ko(s.get("delivery_status")),
                    "총액": int(s.get("total_amount") or 0),
                    "매칭률": f"{s.get('match_rate_pct') or 0:.0f}%",
                    "상태": status_ko(s["status"]),
                } for s in sos])
                st.dataframe(df, use_container_width=True, hide_index=True,
                    column_config={
                        "총수량": st.column_config.NumberColumn(format="localized"),
                        "납품": st.column_config.NumberColumn(format="localized"),
                        "미납": st.column_config.NumberColumn(format="localized"),
                        "총액": st.column_config.NumberColumn("총액 (원)", format="localized"),
                    })

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
                        "상태": status_ko(i.get("status")),
                    } for i in sitems])
                    if not idf.empty:
                        st.dataframe(idf, use_container_width=True, hide_index=True,
                            column_config={
                                "수량": st.column_config.NumberColumn(format="localized"),
                                "납품": st.column_config.NumberColumn(format="localized"),
                                "미납": st.column_config.NumberColumn(format="localized"),
                                "단가": st.column_config.NumberColumn("단가 (원)", format="localized"),
                                "금액": st.column_config.NumberColumn("금액 (원)", format="localized"),
                            })
                    rc1, rc2 = st.columns(2)
                    statuses = ["DRAFT","CONFIRMED","IN_PROD","PARTIAL","DELIVERED","CANCELLED"]
                    new_st = rc1.selectbox("상태 변경", statuses,
                        format_func=status_ko,
                        index=statuses.index(so["status"]) if so["status"] in statuses else 0)
                    if rc2.button("💾 상태 저장"):
                        if _db.update("sales_orders", f"so_id=eq.{so['so_id']}", {"status": new_st}):
                            st.success(f"상태 변경: {status_ko(new_st)}"); st.rerun()
            else:
                st.info("조건에 맞는 수주가 없습니다 — 기간·상태 필터를 '전체'로 "
                        "바꾸거나, 새 수주 입력 탭에서 업로드하세요.")

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
                        "상태": status_ko(i.get("status")),
                    } for i in sitems])
                    st.dataframe(df, use_container_width=True, hide_index=True,
                        column_config={
                            "수량": st.column_config.NumberColumn(format="localized"),
                            "미납": st.column_config.NumberColumn(format="localized"),
                            "단가": st.column_config.NumberColumn("단가 (원)", format="localized"),
                            "금액": st.column_config.NumberColumn("금액 (원)", format="localized"),
                        })
                else:
                    st.info("검색 결과 없음 — 검색어를 지우거나 필터를 넓혀보세요.")
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

elif page == "출고 관리":
    st.subheader("출고 관리")
    if not DB_AVAILABLE:
        st.error("DB 연결이 활성화되지 않았습니다."); st.stop()

    import db as _db
    import pandas as pd

    tab_deliver, tab_dstat = st.tabs(["납품 등록", "납품 현황"])

    # ════════ TAB 1: 납품 등록 ════════
    with tab_deliver:
        st.caption(
            "수주 라인에 납품 수량을 기록합니다 — received_qty 누적 + "
            "상태 자동 전환 + 제품 완성 재고 차감 (ISSUE 원장). "
            "출고 LOT 를 입력하면 소재→생산→납품 역추적이 연결됩니다."
        )

        # ── 1) 미납 수주 조회 ──
        dc1, dc2 = st.columns([3, 1])
        with dc1:
            dq = st.text_input("수주번호 / 거래처 검색",
                placeholder="예: 202605, G264, 미진",
                key="deliver_search")
        with dc2:
            d_limit = st.number_input("표시", 5, 50, 10, 5, key="deliver_limit")

        d_filter = ["status=not.in.(\"DELIVERED\",\"CANCELLED\",\"CANCELED\")",
                    "order=so_date.desc"]
        if dq:
            qq = dq.strip()
            d_filter.append(f"or=(so_number.ilike.*{qq}*,customer.ilike.*{qq}*)")
        try:
            d_sos = fetch("sales_orders",
                "so_id,so_number,customer,so_date,due_date,status",
                "&".join(d_filter), limit=int(d_limit))
        except Exception as e:
            st.error(f"수주 조회 실패: {e}"); d_sos = []

        if not d_sos:
            st.info("미납 수주 없음 (또는 검색 결과 없음).")
        else:
            d_labels = [
                f"{s['so_number']} | {s.get('customer','-')} | "
                f"수주일 {s.get('so_date','-')} | {status_ko(s.get('status'))}"
                for s in d_sos
            ]
            d_pick = st.selectbox("수주 선택", d_labels, key="deliver_so_pick")
            d_so = d_sos[d_labels.index(d_pick)]

            # ── 2) 수주 라인 조회 ──
            try:
                d_items = fetch("sales_order_items",
                    "soi_id,line_no,customer_part_no,customer_item_name,"
                    "canonical_pn,product_id,qty,received_qty,unit,status",
                    f"so_id=eq.{d_so['so_id']}&order=line_no.asc", limit=100)
            except Exception as e:
                st.error(f"라인 조회 실패: {e}"); d_items = []

            if not d_items:
                st.info("수주 라인 없음.")
            else:
                st.markdown(f"##### 📋 {d_so['so_number']} 라인 "
                            f"({len(d_items)}개)")

                # 완성 재고 조회 — 출고는 재고 기반 (2026-07-23 확정)
                _pids = [it["product_id"] for it in d_items
                         if it.get("product_id")]
                _stock_map = {}
                if _pids:
                    try:
                        _pids_str = ",".join(f'"{p}"' for p in set(_pids))
                        _stock_map = {
                            s["product_id"]:
                            float(s.get("current_stock") or 0)
                            for s in fetch("product_stock_v",
                                "product_id,current_stock",
                                f"product_id=in.({_pids_str})",
                                limit=200)}
                    except Exception as e:
                        st.warning(f"완성 재고 조회 실패: {e}")
                _allow_over = st.checkbox(
                    "⚠️ 재고 없이 출고 허용 (ERP 이관 전 생산분 등 — "
                    "완성 재고와 무관하게 출고)",
                    value=False, key="dlv_allow_over")

                # 납품 입력 — 라인별 number_input + 일괄 처리 버튼
                deliver_inputs = {}
                for it in d_items:
                    qty = float(it.get("qty") or 0)
                    rcv = float(it.get("received_qty") or 0)
                    pending = max(qty - rcv, 0)
                    _stock = _stock_map.get(it.get("product_id"), 0.0)
                    _cap = pending if _allow_over \
                        else min(pending, max(_stock, 0.0))
                    pn_label = (it.get("canonical_pn")
                                or it.get("customer_part_no") or "-")
                    lc = st.columns([3, 1, 1, 1, 2])
                    with lc[0]:
                        st.markdown(
                            f"**L{it.get('line_no','-')}** {pn_label}  \n"
                            f"<small>{(it.get('customer_item_name') or '')[:40]}</small>",
                            unsafe_allow_html=True)
                    with lc[1]:
                        st.metric("수주", f"{qty:,.0f}",
                                  label_visibility="collapsed",
                                  help="수주 수량")
                        st.caption(f"수주 {qty:,.0f}")
                    with lc[2]:
                        st.caption(f"기납품 {rcv:,.0f}")
                        st.caption(f"미납 **{pending:,.0f}**")
                        if it.get("product_id"):
                            st.caption(f"완성 재고 {_stock:,.0f}")
                        else:
                            st.caption("재고 확인 불가 (품번 미매칭)")
                    with lc[3]:
                        if pending <= 0:
                            st.success("완납")
                        elif _cap <= 0:
                            st.warning("재고 없음")
                        else:
                            # '전량' 버튼이 예약한 값을 위젯 생성 전에 적용
                            # (렌더된 위젯 키 직접 수정은 StreamlitAPIException)
                            _pend_key = f"dlv_pend_{it['soi_id']}"
                            if _pend_key in st.session_state:
                                st.session_state[f"dlv_{it['soi_id']}"] = \
                                    min(float(_cap),
                                        st.session_state.pop(_pend_key))
                            deliver_inputs[it["soi_id"]] = st.number_input(
                                "납품", min_value=0.0, max_value=float(_cap),
                                value=0.0, step=1.0,
                                key=f"dlv_{it['soi_id']}",
                                label_visibility="collapsed",
                                help="이번 납품 수량 (완성 재고 한도)")
                    with lc[4]:
                        if pending > 0 and _cap <= 0:
                            st.caption("공정 관리 → 완성 확정 후 "
                                       "출고 가능")
                        elif pending > 0:
                            _full_label = (f"전량 ({pending:,.0f})"
                                           if _cap >= pending
                                           else f"재고 한도 ({_cap:,.0f})")
                            if st.button(_full_label,
                                          key=f"dlv_full_{it['soi_id']}",
                                          help="가능한 최대 수량 입력"):
                                st.session_state[f"dlv_pend_{it['soi_id']}"] = float(_cap)
                                st.rerun()

                st.divider()
                total_to_deliver = sum(v for v in deliver_inputs.values() if v > 0)

                # Phase C — 출고 LOT (역추적 연결, 선택)
                dlv_lot = st.text_input(
                    "출고 LOT (선택 — 생산 LOT 와 연결하면 역추적 가능)",
                    placeholder="예: LOT-260703-8HFDV-VM-0",
                    key="deliver_lot",
                    help="생산 보고에 기록한 LOT 번호를 입력하면 "
                         "자재 입고→생산→납품 전 과정 역추적이 연결됩니다.")

                bc1, bc2 = st.columns([1, 3])
                with bc1:
                    do_deliver = st.button(
                        f"📦 납품 처리 ({total_to_deliver:,.0f})",
                        type="primary",
                        disabled=total_to_deliver <= 0,
                        key="deliver_submit")
                with bc2:
                    st.caption(
                        "received_qty 누적 + 상태 자동 전환 + "
                        "제품 재고 차감 (ISSUE 원장, product_id 매핑 라인)."
                    )

                # 재고 재검증 — 같은 제품 여러 라인 합산이 재고 초과인지
                _stock_ok = True
                if do_deliver and total_to_deliver > 0 and not _allow_over:
                    _by_pid = {}
                    for soi_id, dlv_qty in deliver_inputs.items():
                        if dlv_qty <= 0:
                            continue
                        _pid = next(x for x in d_items
                                    if x["soi_id"] == soi_id
                                    ).get("product_id")
                        if _pid:
                            _by_pid[_pid] = _by_pid.get(_pid, 0) + dlv_qty
                    _over = {p: q for p, q in _by_pid.items()
                             if q > _stock_map.get(p, 0) + 1e-9}
                    if _over:
                        st.error("❌ 완성 재고 부족 — " + ", ".join(
                            f"{p}: 출고 {q:,.0f} > 재고 "
                            f"{_stock_map.get(p, 0):,.0f}"
                            for p, q in _over.items())
                            + ". 공정 관리에서 완성 확정 후 출고하거나 "
                              "'재고 없이 출고 허용'을 체크하세요.")
                        _stock_ok = False

                if do_deliver and total_to_deliver > 0 and _stock_ok:
                    from datetime import date as _dlv_date
                    ok_n, fail_n = 0, 0
                    issue_txns = []
                    for soi_id, dlv_qty in deliver_inputs.items():
                        if dlv_qty <= 0:
                            continue
                        it = next(x for x in d_items if x["soi_id"] == soi_id)
                        qty = float(it.get("qty") or 0)
                        new_rcv = float(it.get("received_qty") or 0) + dlv_qty
                        new_pending = max(qty - new_rcv, 0)
                        new_status = ("DELIVERED" if new_rcv >= qty
                                      else "PARTIAL" if new_rcv > 0
                                      else "PENDING")
                        try:
                            if _db.update("sales_order_items",
                                f"soi_id=eq.{soi_id}",
                                {"received_qty": new_rcv,
                                 "pending_qty": new_pending,
                                 "status": new_status}):
                                ok_n += 1
                                # Phase C: 제품 재고 차감 (product_id 매핑 라인만)
                                if it.get("product_id"):
                                    issue_txns.append({
                                        "material_id": None,
                                        "txn_type": "ISSUE",
                                        "qty": -dlv_qty,
                                        "unit": it.get("unit") or "EA",
                                        "ref_table": "sales_order_items",
                                        "ref_id": soi_id,
                                        "product_id": it["product_id"],
                                        "lot_number": (dlv_lot or "").strip() or None,
                                        "txn_date": _dlv_date.today().isoformat(),
                                        "remark": f"납품 출고: {d_so['so_number']}",
                                        "created_by": "김민수",
                                    })
                            else:
                                fail_n += 1
                        except Exception as e:
                            fail_n += 1
                            st.warning(f"라인 {soi_id} 실패: {e}")

                    # 제품 재고 차감 원장 (실패해도 납품 자체는 유지)
                    if issue_txns:
                        try:
                            _db.insert("inventory_transactions", issue_txns)
                        except Exception as e:
                            st.warning(f"⚠️ 제품 재고 차감 기록 실패 (납품은 정상): {e}")

                    # 수주 헤더 상태 자동 갱신
                    if ok_n:
                        try:
                            fresh = fetch("sales_order_items",
                                "qty,received_qty",
                                f"so_id=eq.{d_so['so_id']}", limit=100)
                            all_done = all(
                                float(x.get("received_qty") or 0)
                                >= float(x.get("qty") or 0)
                                for x in fresh) if fresh else False
                            any_rcv = any(
                                float(x.get("received_qty") or 0) > 0
                                for x in fresh) if fresh else False
                            hdr_status = ("DELIVERED" if all_done
                                          else "PARTIAL" if any_rcv
                                          else d_so.get("status") or "CONFIRMED")
                            _db.update("sales_orders",
                                f"so_id=eq.{d_so['so_id']}",
                                {"status": hdr_status})
                        except Exception:
                            pass
                        st.success(
                            f"✅ 납품 처리 완료: {ok_n}개 라인"
                            + (f" / 실패 {fail_n}" if fail_n else "")
                        )
                        st.rerun()
                    elif fail_n:
                        st.error(f"납품 처리 실패 ({fail_n}건)")

    # ════════ TAB 2: 납품 현황 ════════
    with tab_dstat:
        # 수주별 납품 진행
        try:
            _ds = fetch("sales_order_stats",
                "so_number,customer,so_date,total_qty,total_received_qty,"
                "total_pending_qty,delivery_status",
                'status=not.in.("CANCELLED","CANCELED")&order=so_date.desc',
            limit=500)
        except Exception as e:
            st.error(f"납품 현황 조회 실패: {e}"); _ds = []
        if not _ds:
            st.info("수주 데이터 없음 — 수주 관리에서 업로드 후 표시됩니다.")
        else:
            _t_qty = sum(float(s.get("total_qty") or 0) for s in _ds)
            _t_rcv = sum(float(s.get("total_received_qty") or 0) for s in _ds)
            _t_pend = sum(float(s.get("total_pending_qty") or 0) for s in _ds)
            dm1, dm2, dm3, dm4 = st.columns(4)
            dm1.metric("수주 수량", f"{_t_qty:,.0f}")
            dm2.metric("납품 완료", f"{_t_rcv:,.0f}")
            dm3.metric("미납", f"{_t_pend:,.0f}")
            dm4.metric("납품률",
                f"{_t_rcv / _t_qty * 100:.1f}%" if _t_qty else "-")
            dsc1, dsc2 = st.columns([2, 1])
            _ds_q = dsc1.text_input("검색", key="dstat_q",
                placeholder="수주번호 / 거래처 검색",
                label_visibility="collapsed")
            _ds_open = dsc2.checkbox("미납만 보기", value=True,
                                     key="dstat_open_only")
            _ds_show = [s for s in _ds
                        if (not _ds_open
                            or float(s.get("total_pending_qty") or 0) > 0)
                        and (not _ds_q
                             or _ds_q.lower() in (s["so_number"] or "").lower()
                             or _ds_q.lower() in (s["customer"] or "").lower())]
            _ds_cut = len(_ds_show) - 50
            _ds_show = _ds_show[:50]
            if not _ds_show:
                st.success("✅ 조건에 맞는 수주 없음 — 미납만 보기 상태면 "
                           "전부 납품 완료입니다. 체크 해제로 전체 확인.")
                _ddf = None
            else:
                _ddf = pd.DataFrame([{
                    "수주번호": s["so_number"], "거래처": s["customer"],
                    "수주일": s.get("so_date"),
                    "수주": float(s.get("total_qty") or 0),
                    "납품": float(s.get("total_received_qty") or 0),
                    "미납": float(s.get("total_pending_qty") or 0),
                    "진행률": (float(s.get("total_received_qty") or 0)
                              / float(s.get("total_qty") or 1)),
                    "상태": status_ko(s.get("delivery_status")),
                } for s in _ds_show])
            if _ddf is not None:
                st.dataframe(status_style(_ddf),
                    use_container_width=True, hide_index=True,
                    height=min(500, 60 + len(_ddf) * 35),
                    column_config={
                        "수주": st.column_config.NumberColumn(
                            format="localized"),
                        "납품": st.column_config.NumberColumn(
                            format="localized"),
                        "미납": st.column_config.NumberColumn(
                            format="localized"),
                        "진행률": st.column_config.ProgressColumn(
                            "진행률", min_value=0, max_value=1),
                    })
                if _ds_cut > 0:
                    st.caption(f"최근 50건 표시 — 외 {_ds_cut:,}건은 "
                               "검색으로 좁혀서 확인하세요.")

        # 최근 출고 이력 (ISSUE 원장)
        st.divider()
        st.markdown("##### 최근 출고 이력")
        try:
            _iss = fetch("inventory_transactions",
                "txn_date,product_id,qty,lot_number,remark",
                "txn_type=eq.ISSUE&order=txn_id.desc", limit=20)
        except Exception:
            _iss = []
        if _iss:
            st.dataframe(pd.DataFrame([{
                "출고일": i.get("txn_date"),
                "제품": i.get("product_id"),
                "수량": -float(i.get("qty") or 0),
                "출고 LOT": i.get("lot_number") or "-",
                "비고": i.get("remark") or "-",
            } for i in _iss]), use_container_width=True, hide_index=True,
                column_config={"수량": st.column_config.NumberColumn(
                    format="localized")})
        else:
            st.caption("출고 이력 없음.")


elif page == "생산 계획":
    st.subheader("생산 계획 — 자재 필요량 자동 산출")
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

    # 취소 수주 제외 — 헤더 상태 기준 (라인 pending 은 남아있을 수 있음)
    sois = [i for i in sois
            if (so_map.get(i["so_id"], {}).get("status") or "")
            not in ("CANCELLED", "CANCELED")]
    if not sois:
        st.info("미납 수주 품목이 없습니다 (취소 수주 제외).")
        st.stop()

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

    # ── 4) 자재 실재고 조회 (Phase A: material_stock = 기초 + 입고/차감 누적) ──
    mids = list({b["material_id"] for b in bom_rows if b.get("material_id")})
    if mids:
        mids_str = ",".join(f'"{m}"' for m in mids)
        try:
            # stock_qty:current_stock alias → 기존 코드 키 그대로 사용
            mat_rows = fetch("material_stock",
                "material_id,raw_name,material_type,spec,unit,stock_qty:current_stock,main_supplier",
                f"material_id=in.({mids_str})", limit=500)
        except Exception:
            # 017 미적용 환경 fallback (정적 스냅샷)
            mat_rows = fetch("materials",
                "material_id,raw_name,material_type,spec,unit,stock_qty,main_supplier",
                f"material_id=in.({mids_str})", limit=500)
        mat_map = {m["material_id"]: m for m in mat_rows}
    else:
        mat_map = {}

    # ── 4.5) 제품 완성 재고 조회 (product_stock_v — 원장 누적) ──
    # 완성 재고가 있으면 그만큼은 생산 없이 출고 가능 → 자재 필요량에서 제외
    try:
        _ps_rows = fetch("product_stock_v", "product_id,current_stock",
            f"product_id=in.({pids_str})", limit=500)
        prod_stock_left = {p["product_id"]: max(0.0, float(p.get("current_stock") or 0))
                           for p in _ps_rows}
    except Exception:
        prod_stock_left = {}
    total_prod_stock_used = 0.0

    # ── 5) 자재 필요량 계산 (순생산필요 = 미납 − 제품 완성 재고) ──
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
        # 제품 재고 선착순 배분 (수주 라인 순서대로 소진)
        avail = prod_stock_left.get(pid, 0.0)
        use = min(avail, pending)
        prod_stock_left[pid] = avail - use
        total_prod_stock_used += use
        net = pending - use
        soi["prod_stock_used"] = use
        soi["net_pending"] = net
        boms = bom_by_pid.get(pid, [])
        if not boms:
            items_no_bom.append({
                "so_id": soi["so_id"], "product_id": pid,
                "canonical_pn": soi.get("canonical_pn"),
                "pending_qty": pending,
            })
            continue
        items_with_bom += 1
        if net <= 0:
            continue   # 완성 재고로 전량 충당 — 자재 불필요
        for b in boms:
            mid = b.get("material_id")
            if not mid: continue
            qpp = float(b.get("qty_per_pc") or 1)
            sf = float(b.get("shared_factor") or 1) or 1
            need = net * qpp / sf
            mat_req[mid]["required"] += need
            mat_req[mid]["by_pid"][pid] += need
            mat_req[mid]["by_so"][soi["so_id"]] += need
            mat_req[mid]["items_count"] += 1

    # ── 6) 상단 통계 ──
    sc1, sc2, sc3, sc4, sc5 = st.columns(5)
    sc1.metric("미납 수주 품목", len(sois))
    sc2.metric("BOM 매핑된 품목", items_with_bom)
    sc3.metric("📦 완성 재고 충당",
               f"{total_prod_stock_used:,.0f}",
               help="제품 완성 재고(product_stock_v)로 생산 없이 출고 "
                    "가능한 수량 — 자재 필요량 계산에서 제외됨")
    sc4.metric("필요 자재 종류", len(mat_req))
    shortage_count = sum(1 for mid, info in mat_req.items()
                          if info["required"] - (mat_map.get(mid, {}).get("stock_qty") or 0) > 0)
    sc5.metric("🔴 자재 부족", shortage_count, delta_color="inverse")
    st.caption(
        "ℹ️ 필요량 = **순생산필요** (미납수량 − 제품 완성 재고) × BOM. "
        "자재 재고는 원장 실재고(material_stock) 기준.")

    if items_no_bom:
        with st.expander(f"⚠️ BOM 미등록 품목 {len(items_no_bom)}건 — 마스터에서 BOM 등록 필요"):
            df_no = pd.DataFrame(items_no_bom)
            st.dataframe(df_no, use_container_width=True, hide_index=True)

    st.divider()

    # ── 7) 탭 구조 ──
    tab_mat, tab_so, tab_po = st.tabs(["자재별 필요량", "수주별 BOM 전개", "발주 자동 제안"])

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
            # 예외 중심 강조 — 부족 행은 옅은 붉은 배경, 부족분 숫자는 진한 빨강
            def _hl_short(row):
                css = "background-color:#fff5f5" if row["부족분"] > 0 else ""
                return [css] * len(row)
            _styled = (df.style
                       .apply(_hl_short, axis=1)
                       .map(lambda v: "color:#d9480f;font-weight:700"
                            if isinstance(v, (int, float)) and v > 0 else "color:#9aa1ab",
                            subset=["부족분"])
                       .format({"필요량": "{:,.0f}", "현재재고": "{:,.0f}",
                                "부족분": "{:,.0f}"}))
            st.dataframe(_styled, use_container_width=True, hide_index=True)

            shortage_rows = [r for r in rows if r["부족분"] > 0]
            if shortage_rows:
                st.warning(f"🔴 자재 부족 {len(shortage_rows)}건 — '발주 자동 제안' 탭에서 발주서 생성 가능")

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
                    ps_used = float(soi.get("prod_stock_used") or 0)
                    net = float(soi.get("net_pending") if soi.get("net_pending") is not None else pending)
                    boms = bom_by_pid.get(pid, [])
                    if not boms:
                        so_rows.append({
                            "라인": soi["line_no"],
                            "품번": soi.get("canonical_pn"),
                            "미납수량": pending,
                            "완성재고 충당": ps_used,
                            "순생산필요": net,
                            "자재": "❌ BOM 미등록",
                            "필요량": 0, "단위": "-", "재고": 0, "부족분": 0,
                        })
                        continue
                    for b in boms:
                        mid = b.get("material_id")
                        mat = mat_map.get(mid, {})
                        qpp = float(b.get("qty_per_pc") or 1)
                        sf = float(b.get("shared_factor") or 1) or 1
                        need = net * qpp / sf
                        stock = float(mat.get("stock_qty") or 0)
                        so_rows.append({
                            "라인": soi["line_no"],
                            "품번": soi.get("canonical_pn"),
                            "미납수량": pending,
                            "완성재고 충당": ps_used,
                            "순생산필요": net,
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
                with st.expander(f"**{supplier}** — {len(mats)}개 자재 부족 (합 {total_short:.1f})",
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
                        # 수주 출처 추적 — 이 자재들이 어느 수주에서 필요해졌는지
                        src_so_ids = set()
                        for m in mats:
                            src_so_ids.update(
                                mat_req.get(m["material_id"], {}).get("by_so", {}).keys())
                        src_so_numbers = sorted({
                            so_map.get(sid, {}).get("so_number") or str(sid)
                            for sid in src_so_ids
                        })
                        st.session_state["po_prefill_source_so"] = ", ".join(src_so_numbers[:10])
                        st.success(f"✅ '{supplier}'의 {len(mats)}개 품목이 발주서 작성에 임시 저장됨. "
                                   f"좌측 **발주/입고** 메뉴로 이동해서 검토하세요. "
                                   f"(출처 수주: {len(src_so_numbers)}건)")


elif page == "발주/입고":
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

    tab_new, tab_hist, tab_rcv_proc, tab_rstat = st.tabs(
        ["새 발주서 작성", "발주 이력", "입고 처리", "입고 현황"])

    # ════════════ TAB 3: 입고 현황 (소재 입고 상황) ════════════
    with tab_rstat:
        st.caption(
            "발주 라인별 입고 진행 + 소재 LOT(W번호) 잔여 현황 — "
            "입고 처리는 [입고 처리] 탭에서, 투입은 공정 관리에서.")
        # 발주 라인 입고 상태 (미완료 우선)
        try:
            _rs = fetch("po_item_receipt_v",
                "po_id,line_no,item_name,spec,ordered_qty,material_id,"
                "material_name,received_qty,pending_qty,receipt_status,"
                "last_receipt_date",
                "order=po_id.desc,line_no.asc", limit=200)
        except Exception as e:
            st.error(f"입고 현황 조회 실패: {e}"); _rs = []
        if not _rs:
            st.info("발주 라인 없음 — ✏️ 새 발주서 작성에서 시작합니다.")
        else:
            _n_wait = sum(1 for r in _rs
                          if r.get("receipt_status") not in ("RECEIVED",))
            _q_pend = sum(float(r.get("pending_qty") or 0) for r in _rs)
            rs1, rs2, rs3 = st.columns(3)
            rs1.metric("발주 라인", f"{len(_rs):,}건")
            rs2.metric("입고 대기 라인", f"{_n_wait:,}건")
            rs3.metric("미입고 수량", f"{_q_pend:,.0f}")
            _rs_only_wait = st.checkbox("입고 대기만 보기", value=True,
                                        key="rcv_stat_wait_only")
            _rs_show = [r for r in _rs
                        if not _rs_only_wait
                        or r.get("receipt_status") != "RECEIVED"]
            if not _rs_show:
                st.success("✅ 입고 대기 라인 없음 — 전 라인 입고 완료. "
                           "전체 이력은 체크를 해제하세요.")
            else:
                st.dataframe(status_style(pd.DataFrame([{
                    "PO": r.get("po_id"), "라인": r.get("line_no"),
                    "품명": r.get("item_name"), "규격": r.get("spec") or "-",
                    "자재": r.get("material_name") or r.get("material_id")
                            or "미매핑",
                    "발주": float(r.get("ordered_qty") or 0),
                    "입고": float(r.get("received_qty") or 0),
                    "미입고": float(r.get("pending_qty") or 0),
                    "상태": status_ko(r.get("receipt_status")),
                    "최근 입고": r.get("last_receipt_date") or "-",
                } for r in _rs_show])), use_container_width=True,
                    hide_index=True,
                    height=min(400, 60 + len(_rs_show) * 35),
                    column_config={c: st.column_config.NumberColumn(
                        format="localized", width="small")
                        for c in ["발주", "입고", "미입고"]})

        # 소재 LOT (W번호) 잔여 현황
        st.divider()
        st.markdown("##### 소재 LOT (W번호) 현황")
        try:
            _wl = fetch("inventory_transactions",
                "lot_number,material_id,qty,txn_type,txn_date",
                "lot_number=like.W*&txn_type=in.(RECEIPT,PROD_INPUT)",
                limit=2000)
        except Exception:
            _wl = []
        if not _wl:
            st.caption("W번호 발급 이력 없음.")
        else:
            _wdf2 = pd.DataFrame(_wl)
            _wdf2["qty"] = pd.to_numeric(_wdf2["qty"], errors="coerce").fillna(0)
            _wb = (_wdf2.groupby(["lot_number", "material_id"], as_index=False)
                   .agg(잔여=("qty", "sum"),
                        입고일=("txn_date", "min")))
            _wb = _wb.sort_values("lot_number", ascending=False)
            _wb["상태"] = _wb["잔여"].apply(
                lambda v: "투입 대기" if v > 0 else "전량 투입")
            st.dataframe(status_style(_wb.rename(columns={
                "lot_number": "W번호", "material_id": "자재"})),
                use_container_width=True, hide_index=True,
                height=min(350, 60 + len(_wb) * 35),
                column_config={"잔여": st.column_config.NumberColumn(
                    format="localized", width="small")})

        # ── 입고 라벨 재발행 (분실·훼손 대비) ──
        st.divider()
        st.markdown("##### 입고 라벨 재발행")
        st.caption("입고 처리 때 발행한 소재 입고 라벨을 다시 출력합니다. "
                   "W번호로 선택 — 여러 장 동시 출력 가능.")
        try:
            _rl = fetch("inventory_transactions",
                "txn_id,lot_number,material_id,qty,unit,ref_id,txn_date",
                "txn_type=eq.RECEIPT&lot_number=like.W*"
                "&order=txn_date.desc,txn_id.desc", limit=300)
        except Exception:
            _rl = []
        if not _rl:
            st.caption("재발행할 입고 라벨 없음 — W번호 입고 이력이 "
                       "생기면 여기서 재출력할 수 있습니다.")
        else:
            # 발주 라인→헤더→거래처, 자재명 역조인으로 라벨 데이터 재구성
            _poi_map, _po_map, _v_map, _m_map = {}, {}, {}, {}
            try:
                _poi_ids = {r["ref_id"] for r in _rl if r.get("ref_id")}
                if _poi_ids:
                    _poi_map = {p["poi_id"]: p for p in fetch(
                        "purchase_order_items", "poi_id,item_name,spec,po_id",
                        f"poi_id=in.({','.join(str(i) for i in _poi_ids)})",
                        limit=500)}
                _po_ids = {p["po_id"] for p in _poi_map.values()}
                if _po_ids:
                    _po_map = {p["po_id"]: p for p in fetch(
                        "purchase_orders", "po_id,po_number,vendor_id",
                        f"po_id=in.({','.join(str(i) for i in _po_ids)})",
                        limit=500)}
                _v_ids = {p.get("vendor_id") for p in _po_map.values()
                          if p.get("vendor_id")}
                if _v_ids:
                    _v_map = {v["vendor_id"]: v["name"] for v in fetch(
                        "vendors", "vendor_id,name",
                        f"vendor_id=in.({','.join(str(i) for i in _v_ids)})",
                        limit=500)}
                _m_ids = {r["material_id"] for r in _rl
                          if r.get("material_id")}
                if _m_ids:
                    _m_map = {m["material_id"]: m.get("raw_name") for m in
                        fetch("materials", "material_id,raw_name",
                              f"material_id=in.({','.join(_m_ids)})",
                              limit=500)}
            except Exception as e:
                st.warning(f"라벨 정보 일부 조회 실패: {e}")

            def _relabel_item(r):
                poi = _poi_map.get(r.get("ref_id"), {})
                po = _po_map.get(poi.get("po_id"), {})
                return {
                    "w_lot": r.get("lot_number"),
                    "pn": poi.get("item_name") or "-",
                    "material_name": _m_map.get(r.get("material_id"))
                                     or r.get("material_id") or "-",
                    "spec": poi.get("spec") or "-",
                    "qty": float(r.get("qty") or 0),
                    "unit": r.get("unit") or "EA",
                    "po_number": po.get("po_number") or "-",
                    "vendor": _v_map.get(po.get("vendor_id")) or "-",
                    "date": r.get("txn_date") or "",
                }

            _rl_opts = {}
            for r in _rl:
                _poi = _poi_map.get(r.get("ref_id"), {})
                _key = (f"{r['lot_number']} | "
                        f"{_poi.get('item_name') or r.get('material_id')} | "
                        f"{r.get('txn_date')}")
                _rl_opts.setdefault(_key, r)
            _sel_rl = st.multiselect(
                "재발행할 W번호 선택", list(_rl_opts.keys()),
                key="rcv_relabel_sel",
                placeholder="W번호 | 품명 | 입고일")
            if _sel_rl:
                from utils.label_generator import receipt_labels
                _re_items = [_relabel_item(_rl_opts[k]) for k in _sel_rl]
                rl1, rl2 = st.columns(2)
                rl1.download_button(
                    "라벨 프린터용 (단표)",
                    data=receipt_labels(_re_items, mode="label"),
                    file_name=f"입고라벨_재발행_{_re_items[0]['w_lot']}.html",
                    mime="text/html", use_container_width=True,
                    key="rcv_relabel_dl1")
                rl2.download_button(
                    "A4 배치 (예비)",
                    data=receipt_labels(_re_items, mode="a4"),
                    file_name=(
                        f"입고라벨_재발행_A4_{_re_items[0]['w_lot']}.html"),
                    mime="text/html", use_container_width=True,
                    key="rcv_relabel_dl2")

    # ════════════ TAB 1: 새 발주서 작성 ════════════
    with tab_new:
        # 생산 계획에서 prefill된 경우 안내
        if st.session_state.get("po_prefill_vendor_name") or st.session_state.get("po_prefill_items"):
            pv = st.session_state.get("po_prefill_vendor_name", "")
            pi = st.session_state.get("po_prefill_items", [])
            src_so = st.session_state.get("po_prefill_source_so", "")
            st.info(
                f"**생산 계획에서 자동 제안 받은 발주 데이터**: 거래처 '{pv}', 품목 {len(pi)}개"
                + (f" · 출처 수주: {src_so}" if src_so else "")
            )
            if st.button("🔄 자동 제안 + 품목표 모두 초기화"):
                st.session_state.po_prefill_vendor_name = None
                st.session_state.po_prefill_items = None
                st.session_state.po_prefill_source_so = None
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
        with st.expander("신규 거래처 등록 (수기 입력)"):
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
            option_keys = list(vendor_options.keys())
            # 생산 계획 prefill 거래처 자동 선택 (이름 부분 매칭)
            default_idx = 0
            pv_name = (st.session_state.get("po_prefill_vendor_name") or "").strip()
            if pv_name:
                for i, k in enumerate(option_keys):
                    vn = vendor_options[k]["name"]
                    if pv_name in vn or vn in pv_name:
                        default_idx = i
                        break
            sel = st.selectbox(f"거래처 선택 ({len(vendors)}개)",
                               option_keys, index=default_idx)
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

            # 검색 범위 — 기본은 이 거래처와 거래한 품번 (2026-07-24)
            _vh_pns = set()
            try:
                _vh_pos = fetch("purchase_orders", "po_id",
                    f"vendor_id=eq.{vendor['vendor_id']}", limit=300)
                if _vh_pos:
                    _vh_items = fetch("purchase_order_items", "item_name",
                        "po_id=in.("
                        + ",".join(str(p["po_id"]) for p in _vh_pos)
                        + ")", limit=2000)
                    _vh_pns = {i["item_name"] for i in _vh_items
                               if i.get("item_name")}
            except Exception:
                pass
            sq1, sq2 = st.columns([3, 1])
            search_q = sq1.text_input("품번 검색",
                                      placeholder="예: 8HFDV, 4PDVN")
            _vh_only = sq2.checkbox(
                f"이 거래처 이력만 ({len(_vh_pns)}종)",
                value=bool(_vh_pns), key="po_vh_only",
                help="이 거래처와 거래한 품번 안에서만 검색 — "
                     "해제하면 전체 품목에서 검색")
            if search_q and len(search_q) >= 2:
                try:
                    res = fetch("active_products",
                                "product_id,pn,raw_material_name,raw_material_spec,material,bom_material_name,material_unit_price",
                                f"or=(pn.ilike.*{search_q}*,alias_list.ilike.*{search_q}*,bom_material_name.ilike.*{search_q}*)&limit=20")
                except Exception as e:
                    st.error(f"검색 실패: {e}"); res = []
                if _vh_only and _vh_pns:
                    _res_all_n = len(res)
                    res = [p for p in res if p["pn"] in _vh_pns]
                    if not res and _res_all_n:
                        st.info(f"이 거래처 이력에 없는 품번 — 전체 품목 "
                                f"{_res_all_n}건 일치. '이 거래처 이력만' "
                                "체크를 해제하면 표시됩니다.")
                if not res:
                    # 활성 품목 0건 — 휴면 품목과 일치하면 원인 안내 (침묵 방지)
                    try:
                        arch = fetch("products", "pn",
                            f"pn=ilike.*{search_q}*&archived_at=not.is.null",
                            limit=5)
                    except Exception:
                        arch = []
                    if arch:
                        st.warning(
                            f"⚠️ 활성 품목 중 검색 결과 없음 — **휴면 처리된 "
                            f"품목 {len(arch)}건**이 일치합니다: "
                            f"{', '.join(a['pn'] for a in arch)}. "
                            "발주하려면 마스터 관리에서 활성 복귀하세요.")
                    else:
                        st.info("일치하는 품목 없음 — 아래 '마스터에 없는 품목 "
                                "즉석 추가'를 이용하세요.")
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
                        # 수주 출처 추적 (생산 계획 → 발주 흐름인 경우)
                        _src_so = st.session_state.get("po_prefill_source_so") or None
                        _po_record = {
                            "po_number": po_no, "vendor_id": vendor["vendor_id"],
                            "po_date": po_date.isoformat(),
                            "delivery_date": delivery_date or None,
                            "total_amount": total, "vat": int(total * 0.1),
                            "payment_terms": payment_terms,
                            "delivery_address": delivery_address,
                            "contact_person": contact_person,
                            "status": "DRAFT", "created_by": "김민수",
                        }
                        if _src_so:
                            _po_record["remark"] = f"출처 수주: {_src_so}"
                        try:
                            _db.insert("purchase_orders", [_po_record])
                        except Exception:
                            # remark 컬럼 미적용 (Migration 016 전) fallback
                            _po_record.pop("remark", None)
                            _db.insert("purchase_orders", [_po_record])
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
                    # on_click 콜백 필수 — 이 버튼은 생성 직후 run 에만
                    # 렌더되는 조건부 버튼이라 if st.button() 방식으로는
                    # 클릭 처리가 실행되지 않음 (품목 표 리셋 누락 버그)
                    st.button("🔄 새 발주서 시작",
                        on_click=lambda: st.session_state.update(po_items=[]))
                except Exception as e:
                    st.error(f"발주서 생성 실패: {e}")

    # ════════════ TAB 2: 발주 이력 ════════════
    with tab_hist:
        c1, c2, c3 = st.columns(3)
        with c1:
            period = st.selectbox("기간", ["이번달", "최근 3개월", "올해", "전체"], index=1)
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
                "상태": status_ko(r["status"]),
            } for r in history])
            st.dataframe(
                df, use_container_width=True, hide_index=True,
                column_config={
                    "총액": st.column_config.NumberColumn("총액 (원)", format="localized"),
                    "VAT": st.column_config.NumberColumn("VAT (원)", format="localized"),
                }
            )

            st.divider()
            st.markdown("##### 🔍 발주서 상세 / 재발급")
            opts = {f"{r['po_number']} | {r['_vname']} | ₩{int(r.get('total_amount') or 0):,}": r
                    for r in history}
            # 입고 처리 후 rerun 되어도 같은 발주 유지 (예약 키 복원)
            _po_opts = list(opts.keys())
            if "po_hist_keep" in st.session_state:
                _keep = st.session_state.pop("po_hist_keep")
                if _keep in _po_opts:
                    st.session_state["po_hist_sel"] = _keep
            sel_po = st.selectbox("선택", _po_opts, key="po_hist_sel")
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
                                    "수량": st.column_config.NumberColumn(format="localized"),
                                    "단가": st.column_config.NumberColumn("단가 (원)", format="localized"),
                                    "공급가액": st.column_config.NumberColumn("공급가액 (원)", format="localized"),
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
                    format_func=status_ko,
                    index=["DRAFT", "SENT", "RECEIVED", "CANCELLED"].index(po["status"])
                          if po["status"] in ["DRAFT","SENT","RECEIVED","CANCELLED"] else 0
                )
                if rc2.button("💾 상태 저장", use_container_width=True):
                    if _db.update("purchase_orders", f"po_id=eq.{po['po_id']}",
                                  {"status": new_status}):
                        st.success(f"상태를 {new_status}로 변경"); st.rerun()

                st.divider()
                st.caption("입고 처리는 [입고 처리] 탭에서 진행합니다 (2026-07-23 분리).")


# ════════════════════════════════════════════════════════════════
# 공정 관리 — Phase E (투입→외주→검사→완성, 실물 라벨 연동)

    # ════════════ TAB: 입고 처리 (발주 기반 + 직접 입고) ════════════
    with tab_rcv_proc:
        st.caption(
            "소재 입고 전용 — 발주 기반 입고 + 발주 무관 직접 입고"
            "(신규/사급자재). RECEIPT 원장 + W번호 채번 + 입고 라벨.")
        st.markdown("##### 발주 기반 입고")
        try:
            _rp_pos = fetch("purchase_orders",
                "po_id,po_number,vendor_id,po_date,status",
                'status=not.in.("RECEIVED","CANCELLED")&order=po_date.desc',
                limit=200)
        except Exception as e:
            st.error(f"발주 조회 실패: {e}"); _rp_pos = []
        if not _rp_pos:
            st.info("입고 대기 발주 없음 — 발주 없이 들어온 소재는 아래 "
                    "직접 입고를 이용하세요.")
        else:
            _rp_vids = list({r["vendor_id"] for r in _rp_pos
                             if r.get("vendor_id")})
            _rp_vmap = {}
            if _rp_vids:
                try:
                    _rp_vmap = {v["vendor_id"]: v["name"] for v in fetch(
                        "vendors", "vendor_id,name",
                        "vendor_id=in.("
                        + ",".join(str(x) for x in _rp_vids) + ")",
                        limit=300)}
                except Exception:
                    pass
            for _r0 in _rp_pos:
                _r0["_vname"] = _rp_vmap.get(_r0.get("vendor_id"), "?")
            _rp_opts = {
                f"{r['po_number']} | {r['_vname']} | {r.get('po_date')} | "
                f"{status_ko(r['status'])}": r for r in _rp_pos}
            _rp_keys = list(_rp_opts.keys())
            if "po_rcv_keep" in st.session_state:
                _rk = st.session_state.pop("po_rcv_keep")
                if _rk in _rp_keys:
                    st.session_state["po_rcv_sel"] = _rk
            sel_rp = st.selectbox("입고할 발주 선택", _rp_keys,
                                  key="po_rcv_sel")
            if sel_rp:
                po = _rp_opts[sel_rp]
                # ════════ 📦 입고 처리 (Phase A) ════════
                st.divider()
                st.markdown("##### 📦 입고 처리")
                st.caption(
                    "라인별 입고 수량 기록 → `inventory_transactions` (RECEIPT) 원장 저장 "
                    "→ 실재고(material_stock) 자동 반영. "
                    "자재 매핑은 최초 1회만 지정하면 재사용."
                )

                # 입고 현황 조회 (원장 집계 view)
                try:
                    receipt_rows = fetch("po_item_receipt_v",
                        "poi_id,line_no,item_name,spec,ordered_qty,unit,"
                        "material_id,material_name,received_qty,pending_qty,"
                        "receipt_status,last_receipt_date",
                        f"po_id=eq.{po['po_id']}&order=line_no.asc", limit=50)
                except Exception as e:
                    st.warning(f"입고 현황 조회 실패 (Migration 017 필요): {e}")
                    receipt_rows = []

                if receipt_rows:
                    # 요약 메트릭
                    n_total = len(receipt_rows)
                    n_done = sum(1 for r in receipt_rows
                                 if r["receipt_status"] == "RECEIVED")
                    n_partial = sum(1 for r in receipt_rows
                                    if r["receipt_status"] == "PARTIAL")
                    rm1, rm2, rm3 = st.columns(3)
                    rm1.metric("발주 라인", n_total)
                    rm2.metric("✅ 입고 완료", n_done)
                    rm3.metric("🟡 부분 입고", n_partial)

                    # 발주 라인 비고(재질) — 자재 자동 추천 키워드로 사용
                    try:
                        _poi_rm_rows = fetch("purchase_order_items",
                            "poi_id,remark",
                            f"po_id=eq.{po['po_id']}", limit=50)
                        poi_remarks = {x["poi_id"]: (x.get("remark") or "").strip()
                                       for x in _poi_rm_rows}
                    except Exception:
                        poi_remarks = {}

                    receive_inputs = {}   # poi_id → (qty, material_id)
                    for r in receipt_rows:
                        poi_id = r["poi_id"]
                        ordered = float(r.get("ordered_qty") or 0)
                        received = float(r.get("received_qty") or 0)
                        pending = float(r.get("pending_qty") or 0)
                        st.markdown(
                            f"**L{r.get('line_no','-')} {r.get('item_name','-')}** "
                            f"({r.get('spec') or '-'}) — "
                            f"발주 {ordered:,.0f} / 기입고 {received:,.0f} / "
                            f"미입고 **{pending:,.0f}** {r.get('unit') or 'EA'}"
                        )
                        if pending <= 0:
                            st.success(f"✅ 입고 완료 (최근 {r.get('last_receipt_date') or '-'})")
                            st.divider()
                            continue

                        rl1, rl2, rl3 = st.columns([3, 1, 1])
                        with rl1:
                            # 자재 매핑 — 이미 매핑되어 있으면 표시만
                            if r.get("material_id"):
                                st.caption(
                                    f"🔗 자재: **{r['material_id']}** "
                                    f"({r.get('material_name') or '-'})"
                                )
                                sel_mid = r["material_id"]
                            else:
                                # ① BOM 매핑 최우선 — 발주 품명이 제품 품번이면
                                #    그 제품 BOM 의 자재가 정답 (재질+규격 일치).
                                #    비고(재질) 검색은 규격이 다른 자재를 추천할
                                #    수 있어 fallback 으로만 사용.
                                _bom_mat = None
                                try:
                                    _p_hit = fetch("products", "product_id",
                                        f"pn=eq.{r.get('item_name', '')}", limit=1)
                                    if _p_hit:
                                        _b_hit = fetch("bom", "material_id",
                                            f"product_id=eq.{_p_hit[0]['product_id']}"
                                            "&process_type=eq.MATERIAL"
                                            "&material_id=not.is.null", limit=1)
                                        if _b_hit:
                                            _bom_mat = _b_hit[0]["material_id"]
                                except Exception:
                                    pass
                                _auto_kw = poi_remarks.get(poi_id, "")
                                m_kw = st.text_input(
                                    "자재 검색 (최초 1회 매핑)",
                                    placeholder=(
                                        "비우면 BOM 매핑 자재 자동 추천"
                                        if _bom_mat else
                                        (f"비우면 발주 비고 '{_auto_kw}' 자동 추천"
                                         if _auto_kw else "자재명/재질/규격")),
                                    key=f"rcv_mq_{poi_id}")
                                sel_mid = None
                                # 수동 입력 > BOM 매핑 > 비고 키워드
                                _search_kw = m_kw.strip() if m_kw else _auto_kw
                                m_cands = []
                                if not m_kw and _bom_mat:
                                    try:
                                        m_cands = fetch("materials",
                                            "material_id,raw_name,material_type,spec",
                                            f"material_id=eq.{_bom_mat}", limit=1)
                                    except Exception:
                                        m_cands = []
                                if not m_cands and _search_kw:
                                    try:
                                        m_cands = fetch("materials",
                                            "material_id,raw_name,material_type,spec",
                                            f"or=(raw_name.ilike.*{_search_kw}*,"
                                            f"material_type.ilike.*{_search_kw}*,"
                                            f"spec.ilike.*{_search_kw}*)"
                                            f"&order=raw_name.asc", limit=15)
                                    except Exception:
                                        m_cands = []
                                if True:
                                    if m_cands:
                                        _src = ("검색" if m_kw else
                                                ("BOM 매핑" if _bom_mat and not m_kw
                                                 else "자동 추천 (비고)"))
                                        m_labels = [
                                            f"{m['material_id']} | {m['raw_name']} "
                                            f"({m.get('spec') or '-'})"
                                            for m in m_cands]
                                        m_pick = st.selectbox(
                                            f"자재 선택 — {_src} ({len(m_cands)}건)",
                                            m_labels, key=f"rcv_mp_{poi_id}")
                                        if m_pick:
                                            sel_mid = m_cands[
                                                m_labels.index(m_pick)]["material_id"]
                                    else:
                                        st.caption(
                                            f"'{_search_kw}' 일치 자재 없음 — "
                                            "다른 키워드 입력 또는 마스터 관리 → 자재 편집에서 등록")
                        with rl2:
                            # '전량' 버튼 예약값을 위젯 생성 전에 적용
                            _rcv_pend_key = f"rcv_pend_{poi_id}"
                            if _rcv_pend_key in st.session_state:
                                st.session_state[f"rcv_q_{poi_id}"] = \
                                    st.session_state.pop(_rcv_pend_key)
                            rcv_qty = st.number_input(
                                "입고 수량", min_value=0.0,
                                max_value=float(pending), value=0.0, step=1.0,
                                key=f"rcv_q_{poi_id}",
                                label_visibility="collapsed",
                                help="이번 입고 수량")
                        with rl3:
                            if st.button(f"전량 ({pending:,.0f})",
                                          key=f"rcv_full_{poi_id}"):
                                st.session_state[f"rcv_pend_{poi_id}"] = float(pending)
                                st.rerun()
                        if rcv_qty > 0:
                            receive_inputs[poi_id] = (rcv_qty, sel_mid, r)
                        st.divider()

                    total_rcv = sum(v[0] for v in receive_inputs.values())
                    missing_map = [
                        r_[2].get("item_name") for r_ in receive_inputs.values()
                        if not r_[1]
                    ]
                    bc1, bc2 = st.columns([1, 3])
                    with bc1:
                        do_receive = st.button(
                            f"📦 입고 처리 ({total_rcv:,.0f})",
                            type="primary",
                            disabled=(total_rcv <= 0 or bool(missing_map)),
                            key=f"rcv_submit_{po['po_id']}")
                    with bc2:
                        if missing_map:
                            st.warning(
                                f"⚠️ 자재 미매핑 라인: {', '.join(missing_map[:3])} "
                                "— 자재 선택 후 입고 가능")
                        else:
                            st.caption(
                                "RECEIPT 원장 기록 + PO 상태 자동 갱신 "
                                "(전 라인 완입고 → RECEIVED)")

                    if do_receive and total_rcv > 0 and not missing_map:
                        from datetime import date as _rcv_date
                        ok_n, fail_n = 0, 0
                        # 소재 LOT (W번호) 라인별 채번 — Phase E
                        _w_lots = w_lot_next(len(receive_inputs))
                        if _w_lots is None:
                            st.warning(
                                "⚠️ W번호 카운터 미설정 — 이번 입고는 W번호 "
                                "없이 기록됩니다. 아래 채번 설정에서 "
                                "시작 번호를 등록하세요.")
                        _label_items = []
                        for _wi, (poi_id, (rq, mid, r)) in enumerate(
                                receive_inputs.items()):
                            _w = _w_lots[_wi] if _w_lots else None
                            try:
                                # 1) 원장 기록 (lot_number = W번호)
                                _db.insert("inventory_transactions", [{
                                    "material_id": mid,
                                    "txn_type": "RECEIPT",
                                    "qty": rq,
                                    "unit": r.get("unit") or "EA",
                                    "lot_number": _w,
                                    "ref_table": "purchase_order_items",
                                    "ref_id": poi_id,
                                    "txn_date": _rcv_date.today().isoformat(),
                                    "remark": f"발주 입고: {po['po_number']}",
                                    "created_by": "김민수",
                                }])
                                _label_items.append({
                                    "w_lot": _w or "(W번호 없음)",
                                    "pn": r.get("item_name") or "-",
                                    "material_name": r.get("material_name") or mid,
                                    "spec": r.get("spec") or "-",
                                    "qty": rq,
                                    "unit": r.get("unit") or "EA",
                                    "po_number": po["po_number"],
                                    "vendor": po.get("_vname") or "-",
                                    "date": _rcv_date.today().isoformat(),
                                })
                                # 2) 최초 매핑 저장 (재사용)
                                if not r.get("material_id"):
                                    _db.update("purchase_order_items",
                                        f"poi_id=eq.{poi_id}",
                                        {"material_id": mid})
                                ok_n += 1
                            except Exception as e:
                                fail_n += 1
                                st.warning(f"라인 {poi_id} 입고 실패: {e}")

                        # 3) PO 헤더 상태 자동 갱신
                        if ok_n:
                            try:
                                fresh = fetch("po_item_receipt_v",
                                    "receipt_status",
                                    f"po_id=eq.{po['po_id']}", limit=50)
                                statuses = [f["receipt_status"] for f in fresh]
                                if statuses and all(s == "RECEIVED" for s in statuses):
                                    hdr = "RECEIVED"
                                elif any(s in ("PARTIAL", "RECEIVED") for s in statuses):
                                    hdr = "PARTIAL"
                                else:
                                    hdr = po["status"]
                                if hdr != po["status"]:
                                    _db.update("purchase_orders",
                                        f"po_id=eq.{po['po_id']}",
                                        {"status": hdr})
                            except Exception:
                                pass
                            st.success(
                                f"✅ 입고 처리 완료: {ok_n}개 라인 "
                                f"(실재고 자동 반영)"
                                + (f" / 실패 {fail_n}" if fail_n else ""))
                            # 입고 라벨 데이터 보관 → rerun 후 다운로드 표시
                            if _label_items:
                                st.session_state["rcv_labels"] = _label_items
                            # rerun 후에도 같은 발주 유지
                            st.session_state["po_rcv_keep"] = sel_rp
                            st.rerun()
                        elif fail_n:
                            st.error(f"입고 처리 실패 ({fail_n}건)")


        # ── 방금 입고분 라벨 출력 (Phase E — 소재 부착용) ──
        if st.session_state.get("rcv_labels"):
            from utils.label_generator import receipt_labels
            _lbs = st.session_state["rcv_labels"]
            st.info(
                f"방금 입고한 {len(_lbs)}건의 소재 입고 라벨 — "
                "다운로드 후 열면 인쇄 창이 자동으로 뜹니다. "
                "라벨을 소재에 부착하고, MES 소재 등록 시 라벨의 "
                "W번호를 그대로 입력하세요.")
            lc1, lc2, lc3 = st.columns([1, 1, 1])
            with lc1:
                st.download_button(
                    "라벨 프린터용 (단표)",
                    data=receipt_labels(_lbs, mode="label"),
                    file_name=f"입고라벨_{_lbs[0]['w_lot']}.html",
                    mime="text/html", use_container_width=True)
            with lc2:
                st.download_button(
                    "A4 배치 (예비)",
                    data=receipt_labels(_lbs, mode="a4"),
                    file_name=f"입고라벨_A4_{_lbs[0]['w_lot']}.html",
                    mime="text/html", use_container_width=True)
            with lc3:
                if st.button("닫기", use_container_width=True,
                             key="rcv_labels_close"):
                    del st.session_state["rcv_labels"]
                    st.rerun()

        # ── 직접 입고 (발주 무관 — 신규 자재/사급자재) ──
        st.divider()
        st.markdown("##### 직접 입고 (발주 무관 — 신규/사급자재)")
        st.caption("고객 사급자재나 발주 없이 들어온 소재를 입고합니다. "
                   "발주 라인 연결 없이 RECEIPT 원장에 기록됩니다.")
        dr1, dr2 = st.columns([2, 1])
        with dr1:
            _dr_kw = st.text_input("자재 검색", key="dr_mq",
                placeholder="자재명 / 재질 / 규격 — 예: S45C, Ø25")
            _dr_cands = []
            if (_dr_kw or "").strip():
                try:
                    _dr_cands = fetch("materials",
                        "material_id,raw_name,material_type,spec,unit",
                        f"or=(raw_name.ilike.*{_dr_kw.strip()}*,"
                        f"material_type.ilike.*{_dr_kw.strip()}*,"
                        f"spec.ilike.*{_dr_kw.strip()}*)&order=raw_name",
                        limit=15)
                except Exception:
                    _dr_cands = []
            _dr_pick = None
            if _dr_cands:
                _dr_labels = [
                    f"{m['material_id']} | {m['raw_name']} "
                    f"({m.get('spec') or '-'})" for m in _dr_cands]
                _dr_sel = st.selectbox(
                    f"자재 선택 ({len(_dr_cands)}건)", _dr_labels,
                    key="dr_mp")
                _dr_pick = _dr_cands[_dr_labels.index(_dr_sel)]
            elif (_dr_kw or "").strip():
                st.warning("일치 자재 없음 — 신규 자재는 마스터 관리 → "
                           "자재 편집에서 먼저 등록하세요.")
        with dr2:
            _dr_qty = st.number_input("입고 수량", min_value=0.0,
                step=1.0, key="dr_qty")
            _dr_sagup = st.checkbox("사급자재 (고객 지급 — 매입 아님)",
                                    key="dr_sagup")
        dc1, dc2 = st.columns(2)
        _dr_pn = dc1.text_input("사용 품번 (선택 — 라벨 표기)",
                                key="dr_pn")
        _dr_src = dc2.text_input("공급처/출처 (선택)", key="dr_src",
            placeholder="예: 미진정밀 사급, OO상사")
        if st.button(f"직접 입고 ({_dr_qty:,.0f})", type="primary",
                     disabled=not (_dr_pick and _dr_qty > 0),
                     key="dr_submit"):
            from datetime import date as _dr_date
            _dw = (w_lot_next(1) or [None])[0]
            try:
                _db.insert("inventory_transactions", [{
                    "material_id": _dr_pick["material_id"],
                    "txn_type": "RECEIPT",
                    "qty": _dr_qty,
                    "unit": _dr_pick.get("unit") or "EA",
                    "lot_number": _dw,
                    "txn_date": _dr_date.today().isoformat(),
                    "remark": ("사급 입고" if _dr_sagup else "직접 입고")
                              + (f": {_dr_src}" if _dr_src else ""),
                    "created_by": "김민수",
                }])
                st.session_state["rcv_labels"] = [{
                    "w_lot": _dw or "(W번호 없음)",
                    "pn": _dr_pn or "-",
                    "material_name": _dr_pick.get("raw_name"),
                    "spec": _dr_pick.get("spec") or "-",
                    "qty": _dr_qty,
                    "unit": _dr_pick.get("unit") or "EA",
                    "po_number": "직접 입고"
                                 + (" (사급)" if _dr_sagup else ""),
                    "vendor": _dr_src or "-",
                    "date": _dr_date.today().isoformat(),
                }]
                st.success(f"직접 입고 완료: "
                           f"{_dr_pick['material_id']} {_dr_qty:,.0f} "
                           + (f"(소재 LOT {_dw})" if _dw else "(W번호 없음)"))
                st.rerun()
            except Exception as e:
                st.error(f"직접 입고 실패: {e}")

        # ── W번호 채번 설정 (2026-07-23 공정 관리에서 이동) ──
        st.divider()
        st.markdown("##### W번호 채번 설정")
        st.caption(
            "소재 입고 시 자동 발급되는 W번호(소재 LOT)의 카운터입니다. "
            "**현장에서 마지막으로 사용한 번호**를 등록하면 다음 입고부터 "
            "+1 로 채번됩니다. 예: 904 등록 → 다음 입고 W0905.")
        try:
            _wc_row = _db.fetch_one("app_settings",
                "key=eq.w_lot_counter", "value,updated_at")
        except Exception:
            _wc_row = None
        _wc_cur = (_wc_row or {}).get("value")
        if _wc_cur:
            st.info(f"현재 카운터: **W{int(_wc_cur):04d}** (다음 채번 "
                    f"W{int(_wc_cur) + 1:04d})")
        else:
            st.warning("⚠️ 카운터 미설정 — 설정 전 입고는 W번호 없이 기록됩니다.")
        sc1, sc2 = st.columns([1, 2])
        with sc1:
            _wc_new = st.number_input("마지막 사용 번호", min_value=0,
                max_value=9999, value=int(_wc_cur) if _wc_cur else 904,
                step=1, key="pe_wc_new")
        with sc2:
            st.write("")
            st.write("")
            if st.button("💾 카운터 저장", key="pe_wc_save"):
                try:
                    if _wc_row is not None:
                        _db.update("app_settings", "key=eq.w_lot_counter",
                                   {"value": str(int(_wc_new))})
                    else:
                        _db.insert("app_settings", [{
                            "key": "w_lot_counter",
                            "value": str(int(_wc_new))}])
                    st.success(f"저장 — 다음 입고부터 W{int(_wc_new)+1:04d}")
                    st.rerun()
                except Exception as e:
                    st.error(f"저장 실패: {e}")

# ════════════════════════════════════════════════════════════════
elif page == "공정 관리":
    st.subheader("공정 관리")
    st.caption(
        "생산 앞뒤 실물 흐름 — **투입(작업지시) → 외주 → 검사 → 완성**. "
        "상태는 행위의 부산물로 자동 전환 (직접 변경 없음). "
        "공정별 생산 실적은 MES → 생산 보고에서 확인.")

    if not DB_AVAILABLE:
        st.error("DB 연결이 활성화되지 않았습니다."); st.stop()

    import db as _db
    import pandas as pd
    import re as _pe_re
    from datetime import date as _pe_date, datetime as _pe_dt

    # 진행 중 작업지시 1회 조회 — KPI/처리/현황판 공용
    try:
        _pe_all = fetch("wo_tracking", "*",
            "status=neq.CLOSED&order=created_at.desc", limit=300)
    except Exception as e:
        st.error(f"작업지시 조회 실패: {e}"); _pe_all = []

    _pe_sum = {"생산중": 0.0, "외주중": 0.0, "재작업중": 0.0,
               "검사대기": 0.0, "완성": 0.0}
    for _t0 in _pe_all:
        _q0 = wo_stage_qty(_t0)
        for _k0 in _pe_sum:
            _pe_sum[_k0] += _q0[_k0]
    pk1, pk2, pk3, pk4, pk5 = st.columns(5)
    pk1.metric("생산중", f"{_pe_sum['생산중']:,.0f}")
    pk2.metric("외주중", f"{_pe_sum['외주중']:,.0f}")
    pk3.metric("재작업중", f"{_pe_sum['재작업중']:,.0f}")
    pk4.metric("검사 대기", f"{_pe_sum['검사대기']:,.0f}")
    pk5.metric("완성 (진행 작지)", f"{_pe_sum['완성']:,.0f}")
    st.divider()

    pe_tab_in, pe_tab_proc, pe_tab_board = st.tabs(
        ["투입 등록", "공정 처리", "공정 현황판"])

    # ════════ TAB 1: 투입 등록 ════════
    with pe_tab_in:
        st.caption(
            "MES 작업지시서 발행 직후, 지시서의 **작업지시 NO + 소재 W번호 + "
            "투입 수량**을 등록합니다 → 소재 재고 차감 + '생산중' 진입. "
            "(하루 발행분 기준 건당 30초)")

        # ── 잔여 있는 소재 W번호 목록 (RECEIPT − PROD_INPUT) ──
        try:
            _wtx = fetch("inventory_transactions",
                "lot_number,material_id,qty,txn_type,ref_id",
                "lot_number=like.W*&txn_type=in.(RECEIPT,PROD_INPUT)",
                limit=2000)
        except Exception as e:
            st.error(f"소재 LOT 조회 실패: {e}"); _wtx = []

        if not _wtx:
            st.info("잔여 소재 LOT(W번호)가 없습니다 — 발주/입고 → 발주 이력 "
                    "→ 입고 처리에서 입고하면 W번호가 발급됩니다.")
        else:
            _wdf = pd.DataFrame(_wtx)
            _wdf["qty"] = pd.to_numeric(_wdf["qty"], errors="coerce").fillna(0)
            _bal = (_wdf.groupby(["lot_number", "material_id"], as_index=False)
                    ["qty"].sum())
            _bal = _bal[_bal["qty"] > 0].sort_values("lot_number",
                                                     ascending=False)
            if _bal.empty:
                st.info("모든 소재 LOT 이 투입 완료 상태입니다.")
            else:
                # 자재명 매핑
                _mids = list(_bal["material_id"].dropna().unique())
                _mn_map = {}
                if _mids:
                    _mids_str = ",".join(f'"{m}"' for m in _mids)
                    try:
                        _mrows = fetch("materials", "material_id,raw_name",
                            f"material_id=in.({_mids_str})", limit=200)
                        _mn_map = {m["material_id"]: m["raw_name"]
                                   for m in _mrows}
                    except Exception:
                        pass
                # RECEIPT ref → 발주 라인 품번 제안
                _rcpt = _wdf[_wdf["txn_type"] == "RECEIPT"]
                _lot_ref = dict(zip(_rcpt["lot_number"], _rcpt["ref_id"]))

                _w_labels = [
                    f"{b.lot_number} | "
                    f"{_mn_map.get(b.material_id, b.material_id)} | "
                    f"잔여 {b.qty:,.0f}"
                    for b in _bal.itertuples()]
                iw1, iw2 = st.columns([2, 1])
                with iw1:
                    _w_pick = st.selectbox(
                        f"소재 W번호 ({len(_w_labels)}건 잔여)",
                        _w_labels, key="pe_w_pick")
                _sel = _bal.iloc[_w_labels.index(_w_pick)]
                _sel_lot, _sel_mid = _sel["lot_number"], _sel["material_id"]
                _sel_bal = float(_sel["qty"])

                # 품번 자동 제안 (발주 라인 item_name)
                _pn_hint = ""
                _ref_poi = _lot_ref.get(_sel_lot)
                if _ref_poi:
                    try:
                        _poi_row = _db.fetch_one("purchase_order_items",
                            f"poi_id=eq.{_ref_poi}", "item_name")
                        _pn_hint = (_poi_row or {}).get("item_name") or ""
                    except Exception:
                        pass

                # 품번 자동 매핑 — 입고 근거(발주 라인)에서 결정.
                # 발주 연결이 없는 소재(직접 입고)만 직접 입력.
                if _pn_hint:
                    _in_pn = _pn_hint
                    st.caption(f"품번 **{_in_pn}** (발주 라인에서 자동 "
                               "매핑)")
                else:
                    _in_pn = st.text_input(
                        "품번 (발주 연결 없음 — 직접 입력)",
                        key="pe_in_pn")

                # BOM 분할 환산 — 소재 수량 → 예상 생산 수량 (제품 EA)
                _prod0, _cvt = None, None
                if (_in_pn or "").strip():
                    try:
                        _prod0 = _db.fetch_one("products",
                            f"pn=eq.{_in_pn.strip()}", "product_id")
                        if _prod0:
                            _b0 = fetch("bom", "qty_per_pc,shared_factor",
                                f"product_id=eq.{_prod0['product_id']}"
                                f"&material_id=eq.{_sel_mid}", limit=1)
                            if _b0:
                                _qpp = float(_b0[0].get("qty_per_pc")
                                             or 0)
                                _sf = float(_b0[0].get("shared_factor")
                                            or 1) or 1
                                if _qpp > 0:
                                    _cvt = _sf / _qpp
                    except Exception:
                        pass

                ic1, ic2, ic3 = st.columns(3)
                with ic1:
                    _wo_no = st.text_input("작업지시 NO",
                        placeholder="예: 20260723-001", key="pe_wo_no",
                        help="MES 작업지시서의 번호 — MES 실적과 자동 연결되는 키")
                with ic2:
                    _in_qty = st.number_input("소재 투입 수량",
                        min_value=0.0, max_value=_sel_bal,
                        value=_sel_bal, step=1.0, key="pe_in_qty")
                with ic3:
                    _exp_qty = float(round(_in_qty * _cvt)) \
                        if _cvt else _in_qty
                    _in_prod_qty = st.number_input(
                        "예상 생산 수량 (제품)", min_value=0.0,
                        value=_exp_qty, step=1.0,
                        key=f"pe_in_pq_{_sel_lot}_{int(_in_qty)}",
                        help="BOM 환산 자동 제안 — 수정 가능. 공정 "
                             "현황판의 생산중 수량 기준.")
                if _cvt:
                    st.caption(f"BOM 환산: 소재 1EA → 제품 {_cvt:,.2f}개 "
                               f"(소재 {_in_qty:,.0f} → 제품 "
                               f"{_exp_qty:,.0f})")
                elif (_in_pn or "").strip():
                    st.caption("BOM 환산 정보 없음 — 소재:제품 1:1 로 "
                               "제안. 다르면 예상 생산 수량을 수정하세요.")

                _wo_ok = bool(_pe_re.fullmatch(r"\d{8}-\d{3}",
                                              (_wo_no or "").strip()))
                if _wo_no and not _wo_ok:
                    st.error("작업지시 NO 형식이 다릅니다 — YYYYMMDD-NNN "
                             "(예: 20260723-001)")

                if st.button(
                        f"투입 등록 (소재 {_in_qty:,.0f} → 제품 "
                        f"{_in_prod_qty:,.0f})", type="primary",
                        disabled=not (_wo_ok and _in_qty > 0
                                      and _in_prod_qty > 0),
                        key="pe_in_submit"):
                    try:
                        _wo = _wo_no.strip()
                        _pn_clean = (_in_pn or "").strip()
                        _db.insert("wo_tracking", [{
                            "wo_number": _wo,
                            "pn": _pn_clean or None,
                            "product_id": (_prod0 or {}).get("product_id"),
                            "material_id": _sel_mid,
                            "w_lot": _sel_lot,
                            "input_qty": _in_prod_qty,
                            "status": "IN_PROD",
                            "created_by": "김민수",
                        }])
                        _db.insert("inventory_transactions", [{
                            "material_id": _sel_mid,
                            "txn_type": "PROD_INPUT",
                            "qty": -_in_qty,
                            "unit": "EA",
                            "lot_number": _sel_lot,
                            "work_order": _wo,
                            "txn_date": _pe_date.today().isoformat(),
                            "remark": f"생산 투입: {_pn_clean or '-'} ({_wo})",
                            "created_by": "김민수",
                        }])
                        try:
                            _db.insert("wo_events", [{
                                "wo_number": _wo, "w_lot": _sel_lot,
                                "pn": _pn_clean or None,
                                "event_type": "INPUT",
                                "qty": _in_prod_qty,
                                "detail": {"material_qty": _in_qty},
                                "event_date":
                                    _pe_date.today().isoformat(),
                                "created_by": "김민수"}])
                        except Exception:
                            pass
                        st.success(
                            f"✅ 투입 등록: {_wo} · {_sel_lot} · 소재 "
                            f"{_in_qty:,.0f} → 제품 {_in_prod_qty:,.0f}"
                            "EA → 생산중")
                        st.rerun()
                    except Exception as e:
                        if "duplicate" in str(e).lower() or "23505" in str(e):
                            st.error(f"❌ 이미 등록된 조합입니다: {_wo_no} + "
                                     f"{_sel_lot} — 공정 현황판에서 확인하세요.")
                        else:
                            st.error(f"등록 실패: {e}")

        # 최근 투입 목록
        st.divider()
        st.markdown("##### 최근 투입 등록")
        try:
            _recent = fetch("wo_tracking",
                "wo_number,pn,w_lot,input_qty,status,created_at",
                "order=created_at.desc", limit=15)
        except Exception:
            _recent = []
        if _recent:
            st.dataframe(status_style(pd.DataFrame([{
                "작업지시": t["wo_number"], "품번": t.get("pn") or "-",
                "소재 LOT": t.get("w_lot") or "-",
                "투입": float(t.get("input_qty") or 0),
                "상태": status_ko(t.get("status")),
                "등록": str(t.get("created_at") or "")[:16].replace("T", " "),
            } for t in _recent])), use_container_width=True, hide_index=True,
                column_config={"투입": st.column_config.NumberColumn(
                    format="localized")})
        else:
            st.caption("투입 등록 없음.")

    # ════════ TAB 2: 공정 처리 (Phase E-2) ════════
    with pe_tab_proc:
        st.caption(
            "작업지시를 선택해 **완료 인수 → 외주 → 검사 → 완성 확정**을 "
            "처리합니다. 수량은 부분 처리 가능 — 상태는 자동 전환. "
            "검사 불합격은 재작업/폐기/특채로 구분.")

        # ── 방금 발행한 문서 (라벨/의뢰서) — rerun 후 다운로드 유지 ──
        if st.session_state.get("pe_docs"):
            _pdoc = st.session_state["pe_docs"]
            st.info(f"{_pdoc['title']} — 다운로드 후 열면 인쇄 창이 "
                    "자동으로 뜹니다.")
            _dcols = st.columns(len(_pdoc["files"]) + 1)
            for _di, (_dlabel, _dfn, _dhtml) in enumerate(_pdoc["files"]):
                _dcols[_di].download_button(
                    _dlabel, data=_dhtml, file_name=_dfn,
                    mime="text/html", use_container_width=True,
                    key=f"pe_doc_dl{_di}")
            if _dcols[-1].button("닫기", use_container_width=True,
                                 key="pe_docs_close"):
                del st.session_state["pe_docs"]
                st.rerun()
            st.divider()

        _inc_closed = st.checkbox(
            "종결된 작업지시 포함 (이력 조회·라벨 재발행)",
            value=False, key="pe_inc_closed")
        _pe_pool = _pe_all
        if _inc_closed:
            try:
                _pe_pool = fetch("wo_tracking", "*",
                    "order=created_at.desc", limit=300)
            except Exception as e:
                st.error(f"작업지시 조회 실패: {e}")

        if not _pe_pool:
            st.info("작업지시가 없습니다 — 투입 등록에서 시작합니다.")
        else:
            _p_opts = {}
            for _t1 in _pe_pool:
                _p_opts[f"{_t1['wo_number']} | {_t1.get('pn') or '-'} | "
                        f"{_t1.get('w_lot') or '-'} | "
                        f"{status_ko(wo_derive_status(_t1))}"] = _t1
            _p_key = st.selectbox(
                f"작업지시 선택 ({len(_p_opts)}건)",
                list(_p_opts.keys()), key="pe_proc_pick")
            _t = _p_opts[_p_key]
            _q = wo_stage_qty(_t)

            # 5칸 스테퍼 — 진행 칸만 상태색 (2a 시안)
            def _step_cls(active, done):
                return "on" if active else ("done" if done else "")
            _stp = [
                ("투입", _step_cls(False, float(_t.get("input_qty")
                                                or 0) > 0)),
                ("생산", _step_cls(_q["생산중"] > 0,
                                  float(_t.get("received_qty") or 0) > 0)),
                ("외주", _step_cls(_q["외주중"] > 0,
                                  float(_t.get("outsource_in_qty")
                                        or 0) > 0)),
                ("검사", _step_cls(_q["검사대기"] > 0
                                  or _q["재작업중"] > 0,
                                  float(_t.get("pass_qty") or 0) > 0
                                  or float(_t.get("scrap_qty") or 0) > 0)),
                ("완성", _step_cls(False, _q["완성"] > 0)),
            ]
            st.markdown('<div class="stepper">' + "".join(
                f'<div class="step {c}">{n}</div>' for n, c in _stp)
                + "</div>", unsafe_allow_html=True)

            pm = st.columns(6)
            for _pi, _pk in enumerate(
                    ["생산중", "외주중", "재작업중", "검사대기",
                     "완성", "반품"]):
                pm[_pi].metric(_pk if _pk != "검사대기" else "검사 대기",
                               f"{_q[_pk]:,.0f}")

            def _wo_apply(fields, ledger=None, docs=None, msg="",
                          event=None):
                """수량 누적 갱신 + 상태 자동 유도 + 원장/문서/이벤트 기록"""
                fields["status"] = wo_derive_status({**_t, **fields})
                fields["updated_at"] = _pe_dt.utcnow().isoformat()
                _db.update("wo_tracking", f"wo_id=eq.{_t['wo_id']}", fields)
                if ledger:
                    _db.insert("inventory_transactions", [ledger])
                if event:
                    try:
                        _db.insert("wo_events", [{
                            "wo_id": _t["wo_id"],
                            "wo_number": _t["wo_number"],
                            "w_lot": _t.get("w_lot"),
                            "pn": _t.get("pn"),
                            "event_date": _pe_date.today().isoformat(),
                            "created_by": "김민수", **event}])
                    except Exception as e:
                        st.warning(f"⚠️ 이력 기록 실패 (처리는 정상): {e}")
                if docs:
                    st.session_state["pe_docs"] = docs
                st.success(msg)
                st.rerun()

            _acts = []
            if _q["생산중"] > 0:
                _acts.append("완료 인수")
            if _q["검사대기"] > 0:
                _acts += ["검사", "외주 출고"]
            if _q["외주중"] > 0:
                _acts.append("외주 입고")
            if _q["재작업중"] > 0:
                _acts.append("재작업 복귀")

            if not _acts:
                st.success("✅ 이 작업지시는 모든 수량이 처리되었습니다.")
            else:
                st.divider()
                _act = st.radio("처리 선택", _acts, horizontal=True,
                                key=f"pe_act_{_t['wo_id']}")

                # ── 1. 완료 인수 (생산분, 부분 가능) ──
                if _act == "완료 인수":
                    st.caption("MES 생산 완료분을 인수합니다 — 인수분은 "
                               "검사 대기로 이동. 부분 인수 가능.")
                    _rq = st.number_input("인수 수량", 0.0, _q["생산중"],
                                          _q["생산중"], 1.0, key="pe_rq")
                    if st.button(f"인수 등록 ({_rq:,.0f})",
                                 type="primary", disabled=_rq <= 0,
                                 key="pe_rq_btn"):
                        _wo_apply(
                            {"received_qty":
                             float(_t.get("received_qty") or 0) + _rq},
                            event={"event_type": "RECEIVE", "qty": _rq},
                            msg=f"✅ 인수 {_rq:,.0f} EA → 검사 대기")

                # ── 2. 외주 출고 (+의뢰서) ──
                elif _act == "외주 출고":
                    st.caption("검사 대기 수량 중 외주 가공분을 출고합니다 "
                               "— 외주 의뢰서가 발행됩니다.")
                    try:
                        _ov = fetch("vendors", "name",
                            "in_use=eq.true&order=name", limit=300)
                    except Exception:
                        _ov = []
                    oc1, oc2 = st.columns(2)
                    with oc1:
                        _o_vendor = st.selectbox("외주 거래처",
                            [v["name"] for v in _ov] or ["(거래처 없음)"],
                            key="pe_o_vendor")
                        _o_proc = st.text_input("가공 공정",
                            placeholder="예: 열처리, 도금, 연마",
                            key="pe_o_proc")
                    with oc2:
                        _o_qty = st.number_input("출고 수량", 0.0,
                            _q["검사대기"], _q["검사대기"], 1.0,
                            key="pe_o_qty")
                        _o_due = st.date_input("납기 요청일",
                                               key="pe_o_due")
                    _o_note = st.text_input("특기사항 (선택)",
                                            key="pe_o_note")
                    if st.button(f"외주 출고 ({_o_qty:,.0f}) + 의뢰서 발행",
                                 type="primary",
                                 disabled=not (_o_qty > 0 and _o_proc),
                                 key="pe_o_btn"):
                        from utils.label_generator import (
                            outsource_request_html)
                        _doc = outsource_request_html({
                            "vendor": _o_vendor, "process": _o_proc,
                            "due_date": str(_o_due),
                            "issue_date": _pe_date.today().isoformat(),
                            "items": [{"pn": _t.get("pn"),
                                       "wo_number": _t["wo_number"],
                                       "w_lot": _t.get("w_lot"),
                                       "qty": _o_qty, "note": _o_proc}],
                            "remark": _o_note,
                        })
                        _wo_apply(
                            {"outsource_qty":
                             float(_t.get("outsource_qty") or 0) + _o_qty},
                            event={"event_type": "OUT_SEND", "qty": _o_qty,
                                   "detail": {"vendor": _o_vendor,
                                              "process": _o_proc,
                                              "due": str(_o_due),
                                              "note": _o_note}},
                            docs={"title": f"외주 의뢰서 — {_o_vendor} "
                                           f"({_o_proc} {_o_qty:,.0f} EA)",
                                  "files": [("외주 의뢰서 (A4)",
                                             f"외주의뢰서_{_t['wo_number']}"
                                             f"_{_o_vendor}.html", _doc)]},
                            msg=f"외주 출고 {_o_qty:,.0f} EA → "
                                f"{_o_vendor} ({_o_proc})")

                # ── 3. 외주 입고 ──
                elif _act == "외주 입고":
                    st.caption("외주 가공 완료분 입고 — 입고분은 검사 "
                               "대기로 복귀합니다.")
                    _oi_qty = st.number_input("입고 수량", 0.0,
                        _q["외주중"], _q["외주중"], 1.0, key="pe_oi_qty")
                    if st.button(f"외주 입고 ({_oi_qty:,.0f})",
                                 type="primary", disabled=_oi_qty <= 0,
                                 key="pe_oi_btn"):
                        _wo_apply(
                            {"outsource_in_qty":
                             float(_t.get("outsource_in_qty") or 0)
                             + _oi_qty},
                            event={"event_type": "OUT_RETURN",
                                   "qty": _oi_qty},
                            msg=f"외주 입고 {_oi_qty:,.0f} EA → "
                                "검사 대기")

                # ── 4. 검사 (합격/재작업/폐기/특채 + 라벨) ──
                elif _act == "검사":
                    st.caption("검사 대기 수량을 판정합니다 — **완성(합격)"
                               "은 즉시 완성 재고로 확정** + 완성 라벨. "
                               "불합격은 재작업/폐기/특채/반품 구분 — "
                               "재작업분만 작업지시에 남아 복귀 후 "
                               "재검사합니다.")
                    qc1, qc2, qc3, qc4, qc5 = st.columns(5)
                    _i_pass = qc1.number_input("완성 (합격)", 0.0,
                        _q["검사대기"], _q["검사대기"], 1.0,
                        key="pe_i_pass")
                    _i_rework = qc2.number_input("재작업", 0.0,
                        _q["검사대기"], 0.0, 1.0, key="pe_i_rework")
                    _i_scrap = qc3.number_input("폐기", 0.0,
                        _q["검사대기"], 0.0, 1.0, key="pe_i_scrap")
                    _i_tok = qc4.number_input("특채", 0.0,
                        _q["검사대기"], 0.0, 1.0, key="pe_i_tok")
                    _i_ret = qc5.number_input("반품", 0.0,
                        _q["검사대기"], 0.0, 1.0, key="pe_i_ret")
                    _i_done = _i_pass + _i_tok
                    _i_sum = (_i_pass + _i_rework + _i_scrap
                              + _i_tok + _i_ret)
                    if _i_sum > _q["검사대기"]:
                        st.error(f"판정 합계 {_i_sum:,.0f}가 검사 대기 "
                                 f"{_q['검사대기']:,.0f}를 초과합니다.")
                    _f_pid = _t.get("product_id")
                    if not _f_pid and _t.get("pn"):
                        try:
                            _f_pid = (_db.fetch_one("products",
                                f"pn=eq.{_t['pn']}", "product_id")
                                or {}).get("product_id")
                        except Exception:
                            pass
                    if _i_done > 0 and not _f_pid:
                        st.error("품번이 제품 마스터와 연결되지 않아 완성 "
                                 "재고 등록이 불가합니다 — 마스터 관리에서 "
                                 f"품번 '{_t.get('pn') or '?'}' 확인 후 "
                                 "다시 시도하세요.")
                    if st.button(f"검사 등록 (판정 {_i_sum:,.0f} · "
                                 f"완성 {_i_done:,.0f})",
                                 type="primary",
                                 disabled=not (
                                     0 < _i_sum <= _q["검사대기"]
                                     and (_i_done <= 0 or bool(_f_pid))),
                                 key="pe_i_btn"):
                        from utils.label_generator import (
                            inspection_labels, finished_labels)
                        _today = _pe_date.today().isoformat()
                        _base = {"pn": _t.get("pn"),
                                 "wo_number": _t["wo_number"],
                                 "w_lot": _t.get("w_lot"),
                                 "date": _today}
                        _ng_items = []
                        if _i_tok:
                            _ng_items.append({**_base, "verdict": "특채",
                                              "qty": _i_tok})
                        if _i_rework:
                            _ng_items.append({**_base,
                                              "verdict": "불합격",
                                              "qty": _i_rework,
                                              "note": "재작업"})
                        if _i_scrap:
                            _ng_items.append({**_base,
                                              "verdict": "불합격",
                                              "qty": _i_scrap,
                                              "note": "폐기"})
                        if _i_ret:
                            _ng_items.append({**_base, "verdict": "반품",
                                              "qty": _i_ret,
                                              "note": "공급처 반품"})
                        _files = []
                        if _i_done > 0:
                            _fin = [{**_base, "qty": _i_done,
                                     "tokusai": _i_tok}]
                            _files += [
                                ("완성 라벨 (단표)",
                                 f"완성라벨_{_t['wo_number']}.html",
                                 finished_labels(_fin, mode="label")),
                                ("완성 라벨 A4",
                                 f"완성라벨_A4_{_t['wo_number']}.html",
                                 finished_labels(_fin, mode="a4"))]
                        if _ng_items:
                            _files += [
                                ("판정 라벨 (단표)",
                                 f"검사라벨_{_t['wo_number']}.html",
                                 inspection_labels(_ng_items,
                                                   mode="label")),
                                ("판정 라벨 A4",
                                 f"검사라벨_A4_{_t['wo_number']}.html",
                                 inspection_labels(_ng_items,
                                                   mode="a4"))]
                        _wo_apply(
                            {"pass_qty": float(_t.get("pass_qty") or 0)
                                         + _i_done,
                             "tokusai_qty":
                             float(_t.get("tokusai_qty") or 0) + _i_tok,
                             "rework_qty":
                             float(_t.get("rework_qty") or 0) + _i_rework,
                             "scrap_qty":
                             float(_t.get("scrap_qty") or 0) + _i_scrap,
                             "return_qty":
                             float(_t.get("return_qty") or 0) + _i_ret,
                             "output_qty":
                             float(_t.get("output_qty") or 0) + _i_done},
                            event={"event_type": "INSPECT",
                                   "qty": _i_sum,
                                   "detail": {"pass": _i_pass,
                                              "rework": _i_rework,
                                              "scrap": _i_scrap,
                                              "tokusai": _i_tok,
                                              "return": _i_ret,
                                              "output": _i_done}},
                            ledger=({
                                "product_id": _f_pid,
                                "txn_type": "PROD_OUTPUT",
                                "qty": _i_done, "unit": "EA",
                                "lot_number": _t["wo_number"],
                                "work_order": _t["wo_number"],
                                "txn_date": _today,
                                "remark": "검사 완성: "
                                          f"{_t.get('pn') or '-'} (소재 "
                                          f"{_t.get('w_lot') or '-'})",
                                "created_by": "김민수",
                            } if _i_done > 0 else None),
                            docs=({"title": "검사 판정 문서",
                                   "files": _files} if _files else None),
                            msg=f"검사 등록 — 완성 {_i_done:,.0f} · "
                                f"재작업 {_i_rework:,.0f} · 폐기 "
                                f"{_i_scrap:,.0f} · 반품 {_i_ret:,.0f}")
                # ── 5. 재작업 복귀 ──
                elif _act == "재작업 복귀":
                    st.caption("재작업 완료분을 검사 대기로 되돌립니다 — "
                               "재검사 후 다시 판정하세요.")
                    _rw_qty = st.number_input("복귀 수량", 0.0,
                        _q["재작업중"], _q["재작업중"], 1.0,
                        key="pe_rw_qty")
                    if st.button(f"재작업 복귀 ({_rw_qty:,.0f})",
                                 type="primary", disabled=_rw_qty <= 0,
                                 key="pe_rw_btn"):
                        _wo_apply(
                            {"rework_in_qty":
                             float(_t.get("rework_in_qty") or 0)
                             + _rw_qty},
                            event={"event_type": "REWORK_BACK",
                                   "qty": _rw_qty},
                            msg=f"재작업 복귀 {_rw_qty:,.0f} EA → "
                                "검사 대기 (재검사)")

            # ── 공정 이력 (스텝별 타임라인) + 문서 재발행 ──
            st.divider()
            st.markdown("##### 공정 이력")
            try:
                _evs = fetch("wo_events",
                    "event_id,event_type,qty,detail,event_date,created_at",
                    f"wo_number=eq.{_t['wo_number']}&order=event_id.asc",
                    limit=200)
            except Exception:
                _evs = []
            if not _evs:
                st.caption("기록된 이력 없음 — 처리하면 자동으로 쌓입니다.")
            else:
                def _ev_detail(e):
                    d = e.get("detail") or {}
                    if e["event_type"] == "OUT_SEND":
                        return (f"{d.get('vendor', '-')} · "
                                f"{d.get('process', '-')} · "
                                f"납기 {d.get('due', '-')}")
                    if e["event_type"] == "INSPECT":
                        _s = (f"완성 {float(d.get('pass') or 0):,.0f} · "
                              f"재작업 {float(d.get('rework') or 0):,.0f}"
                              f" · 폐기 {float(d.get('scrap') or 0):,.0f}"
                              f" · 특채 "
                              f"{float(d.get('tokusai') or 0):,.0f}")
                        if d.get("return"):
                            _s += f" · 반품 {float(d['return']):,.0f}"
                        return _s
                    if e["event_type"] == "OUTPUT" and d.get("tokusai"):
                        return f"특채 포함 {float(d['tokusai']):,.0f}"
                    return "-"
                st.dataframe(pd.DataFrame([{
                    "일자": e.get("event_date"),
                    "처리": EVENT_KO.get(e["event_type"],
                                        e["event_type"]),
                    "수량": float(e.get("qty") or 0),
                    "상세": _ev_detail(e),
                    "기록": str(e.get("created_at") or "")[:16]
                            .replace("T", " "),
                } for e in _evs]), use_container_width=True,
                    hide_index=True,
                    height=min(400, 60 + len(_evs) * 35),
                    column_config={"수량": st.column_config.NumberColumn(
                        format="localized", width="small")})

                _re_evs = [e for e in _evs if e["event_type"]
                           in ("OUT_SEND", "INSPECT", "OUTPUT")]
                if _re_evs:
                    st.markdown("##### 라벨·의뢰서 재발행")
                    st.caption("발행했던 문서를 이력에서 다시 출력합니다. "
                               "소재 입고 라벨은 발주/입고 → 입고 "
                               "현황에서 재발행.")
                    _re_opts = {
                        f"{e.get('event_date')} | "
                        f"{EVENT_KO.get(e['event_type'])} | "
                        f"{float(e.get('qty') or 0):,.0f} EA "
                        f"(#{e['event_id']})": e
                        for e in _re_evs}
                    _re_pick = st.selectbox("재발행할 이력 선택",
                        list(_re_opts.keys()), key="pe_re_pick")
                    _re = _re_opts[_re_pick]
                    _red = _re.get("detail") or {}
                    _re_date = _re.get("event_date") or ""
                    _re_qty = float(_re.get("qty") or 0)
                    from utils.label_generator import (
                        outsource_request_html, inspection_labels,
                        finished_labels)
                    _re_files = []
                    if _re["event_type"] == "OUT_SEND":
                        _re_files = [("외주 의뢰서 (A4)",
                            f"외주의뢰서_재발행_{_t['wo_number']}.html",
                            outsource_request_html({
                                "vendor": _red.get("vendor", "-"),
                                "process": _red.get("process", "-"),
                                "due_date": _red.get("due", "-"),
                                "issue_date": _re_date,
                                "items": [{"pn": _t.get("pn"),
                                           "wo_number": _t["wo_number"],
                                           "w_lot": _t.get("w_lot"),
                                           "qty": _re_qty,
                                           "note": _red.get("process",
                                                            "")}],
                                "remark": _red.get("note", ""),
                            }))]
                    elif _re["event_type"] == "INSPECT":
                        _base = {"pn": _t.get("pn"),
                                 "wo_number": _t["wo_number"],
                                 "w_lot": _t.get("w_lot"),
                                 "date": _re_date}
                        _items = []
                        if float(_red.get("pass") or 0):
                            _items.append({**_base, "verdict": "합격",
                                           "qty": float(_red["pass"])})
                        if float(_red.get("tokusai") or 0):
                            _items.append({**_base, "verdict": "특채",
                                           "qty":
                                           float(_red["tokusai"])})
                        if float(_red.get("rework") or 0):
                            _items.append({**_base, "verdict": "불합격",
                                           "qty": float(_red["rework"]),
                                           "note": "재작업"})
                        if float(_red.get("scrap") or 0):
                            _items.append({**_base, "verdict": "불합격",
                                           "qty": float(_red["scrap"]),
                                           "note": "폐기"})
                        if float(_red.get("return") or 0):
                            _items.append({**_base, "verdict": "반품",
                                           "qty": float(_red["return"]),
                                           "note": "공급처 반품"})
                        if float(_red.get("output") or 0):
                            _re_files += [
                                ("완성 라벨 (단표)",
                                 f"완성라벨_재발행_{_t['wo_number']}"
                                 ".html",
                                 finished_labels([{**_base,
                                     "qty": float(_red["output"]),
                                     "tokusai":
                                     float(_red.get("tokusai") or 0)}],
                                     mode="label"))]
                        if _items:
                            _re_files += [
                                ("판정 라벨 (단표)",
                                 f"검사라벨_재발행_{_t['wo_number']}"
                                 ".html",
                                 inspection_labels(_items, mode="label")),
                                ("A4 배치 (예비)",
                                 f"검사라벨_재발행_A4_{_t['wo_number']}"
                                 ".html",
                                 inspection_labels(_items, mode="a4"))]
                    elif _re["event_type"] == "OUTPUT":
                        _f_items = [{"pn": _t.get("pn"),
                                     "wo_number": _t["wo_number"],
                                     "w_lot": _t.get("w_lot"),
                                     "qty": _re_qty, "date": _re_date,
                                     "tokusai": float(_red.get("tokusai")
                                                      or 0)}]
                        _re_files = [
                            ("완성 라벨 (단표)",
                             f"완성라벨_재발행_{_t['wo_number']}.html",
                             finished_labels(_f_items, mode="label")),
                            ("A4 배치 (예비)",
                             f"완성라벨_재발행_A4_{_t['wo_number']}"
                             ".html",
                             finished_labels(_f_items, mode="a4"))]
                    if _re_files:
                        _rc = st.columns(max(2, len(_re_files)))
                        for _ri, (_rl, _rf, _rh) in enumerate(_re_files):
                            _rc[_ri].download_button(_rl, data=_rh,
                                file_name=_rf, mime="text/html",
                                use_container_width=True,
                                key=f"pe_re_dl{_ri}")

    # ════════ TAB 3: 공정 현황판 ════════
    with pe_tab_board:
        _b_closed = st.checkbox("종결 포함 보기", value=False,
                                key="pe_board_closed")
        _wos = _pe_all
        if _b_closed:
            try:
                _wos = fetch("wo_tracking", "*",
                    "order=created_at.desc", limit=300)
            except Exception as e:
                st.error(f"현황 조회 실패: {e}")

        if not _wos:
            st.info("진행 중인 작업지시가 없습니다 — 투입 등록에서 시작합니다.")
        else:
            _bdf = pd.DataFrame(_wos)
            for c in ["input_qty", "received_qty", "outsource_qty",
                      "outsource_in_qty", "pass_qty", "tokusai_qty",
                      "rework_qty", "rework_in_qty", "scrap_qty",
                      "return_qty", "output_qty"]:
                if c not in _bdf.columns:
                    _bdf[c] = 0
                _bdf[c] = pd.to_numeric(_bdf[c], errors="coerce").fillna(0)
            _bdf["생산중"] = _bdf["input_qty"] - _bdf["received_qty"]
            _bdf["외주중"] = _bdf["outsource_qty"] - _bdf["outsource_in_qty"]
            _bdf["재작업중"] = _bdf["rework_qty"] - _bdf["rework_in_qty"]
            _bdf["검사대기"] = (_bdf["received_qty"] + _bdf["outsource_in_qty"]
                              - _bdf["outsource_qty"] - _bdf["pass_qty"]
                              - _bdf["scrap_qty"] - _bdf["return_qty"]
                              - _bdf["재작업중"])
            _bdf["상태"] = [status_ko(wo_derive_status(t)) for t in _wos]

            # MES 실적 연계 — 작업지시별 최종공정 누적 (참고)
            _wo_nums = list(_bdf["wo_number"].unique())
            _mes_map = {}
            if _wo_nums:
                try:
                    _pl = fetch("production_log",
                        "work_order,process_step,total_qty",
                        "source=eq.MES_UPLOAD&work_order=not.is.null",
                        limit=5000)
                    if _pl:
                        _pldf = pd.DataFrame(_pl)
                        _pldf["wo"] = (_pldf["work_order"].astype(str)
                                       .str.split(" ").str[0])
                        _pldf = _pldf[_pldf["wo"].isin(_wo_nums)]
                        _pldf["total_qty"] = pd.to_numeric(
                            _pldf["total_qty"], errors="coerce").fillna(0)
                        _pldf["process_step"] = pd.to_numeric(
                            _pldf["process_step"], errors="coerce")
                        for wo, g in _pldf.groupby("wo"):
                            _last = g[g["process_step"] == g["process_step"].max()]
                            _mes_map[wo] = float(_last["total_qty"].sum())
                except Exception:
                    pass
            _bdf["MES최종공정"] = _bdf["wo_number"].map(_mes_map)

            b1, b2, b3, b4 = st.columns(4)
            b1.metric("진행 작업지시", f"{len(_bdf):,}건")
            b2.metric("생산중", f"{_bdf['생산중'].clip(lower=0).sum():,.0f}")
            b3.metric("외주중", f"{_bdf['외주중'].clip(lower=0).sum():,.0f}")
            b4.metric("완성 확정", f"{_bdf['output_qty'].sum():,.0f}")

            _board_df = pd.DataFrame({
                "작업지시": _bdf["wo_number"],
                "품번": _bdf["pn"].fillna("-"),
                "소재 LOT": _bdf["w_lot"].fillna("-"),
                "투입": _bdf["input_qty"],
                "생산중": _bdf["생산중"],
                "MES 최종공정": _bdf["MES최종공정"],
                "외주중": _bdf["외주중"],
                "재작업중": _bdf["재작업중"],
                "검사대기": _bdf["검사대기"].clip(lower=0),
                "특채": _bdf["tokusai_qty"],
                "폐기": _bdf["scrap_qty"],
                "반품": _bdf["return_qty"],
                "완성": _bdf["output_qty"],
                "상태": _bdf["상태"],
            })
            st.dataframe(status_style(_board_df),
                use_container_width=True, hide_index=True,
                height=min(500, 60 + len(_bdf) * 35),
                column_config={c: st.column_config.NumberColumn(
                    format="localized", width="small")
                    for c in ["투입", "생산중", "MES 최종공정", "외주중",
                              "재작업중", "검사대기", "특채",
                              "폐기", "반품", "완성"]})
            st.caption(
                "MES 최종공정 = 업로드된 MES 실적 중 해당 작업지시의 최대 "
                "공정번호 누적 수량 (사내 공정 진행 참고). "
                "처리(인수/외주/검사/완성)는 공정 처리 탭에서.")



# ════════════════════════════════════════════════════════════════
# 생산 보고 — Phase B (production_log + BOM 자재 자동 차감)
# ════════════════════════════════════════════════════════════════
elif page == "생산 보고":
    st.subheader("생산 보고")
    st.caption(
        "생산 완료 보고 → `production_log` 기록 + BOM 기준 자재 자동 차감 "
        "(PROD_INPUT) + 제품 완성 재고 (PROD_OUTPUT). 모두 원장 기반."
    )

    if not DB_AVAILABLE:
        st.error("DB 연결이 활성화되지 않았습니다."); st.stop()

    import db as _db
    import pandas as pd
    from datetime import date as _pb_date

    tab_dash, tab_report, tab_mes, tab_history, tab_trace = st.tabs(
        ["대시보드", "생산 보고 입력", "MES 업로드",
         "생산 이력", "역추적 (LOT/제품)"])

    # ════════ TAB 0: 생산 대시보드 (시트 웹앱 대시보드 이관 1차) ════════
    with tab_dash:
        import altair as alt
        from datetime import timedelta as _td

        fc1, fc2, fc3 = st.columns([1.4, 1, 1])
        with fc1:
            d_preset = st.selectbox("기간",
                ["최근 7일", "오늘", "이번 달", "직접 지정"],
                key="dash_preset")
        with fc2:
            d_shift = st.selectbox("교대", ["전체", "주간", "야간"],
                key="dash_shift")
        with fc3:
            d_src = st.selectbox("소스", ["전체", "📥 MES", "📝 수기"],
                key="dash_src")

        _today = _pb_date.today()
        if d_preset == "오늘":
            d_from, d_to = _today, _today
        elif d_preset == "이번 달":
            d_from, d_to = _today.replace(day=1), _today
        elif d_preset == "직접 지정":
            dr1, dr2 = st.columns(2)
            with dr1:
                d_from = st.date_input("시작일", _today - _td(days=7),
                    key="dash_from")
            with dr2:
                d_to = st.date_input("종료일", _today, key="dash_to")
        else:
            d_from, d_to = _today - _td(days=6), _today

        q = [f"log_date=gte.{d_from.isoformat()}",
             f"log_date=lte.{d_to.isoformat()}"]
        if d_shift != "전체":
            q.append(f"shift=eq.{d_shift}")
        if d_src == "📥 MES":
            q.append("source=eq.MES_UPLOAD")
        elif d_src == "📝 수기":
            q.append("source=eq.MANUAL")
        try:
            d_rows = fetch("production_log",
                "log_date,shift,machine,worker,process,process_step,pn,"
                "total_qty,defect_qty,work_order,work_start,work_end,source",
                "&".join(q) + "&order=log_date.asc", limit=5000)
        except Exception as e:
            st.error(f"대시보드 조회 실패: {e}"); d_rows = []

        if not d_rows:
            st.info(f"{d_from} ~ {d_to} 생산 실적 없음. "
                    "MES 업로드 또는 생산 보고 입력 후 표시됩니다.")
        else:
            ddf = pd.DataFrame(d_rows)
            ddf["total_qty"] = pd.to_numeric(ddf["total_qty"],
                errors="coerce").fillna(0)
            ddf["defect_qty"] = pd.to_numeric(ddf["defect_qty"],
                errors="coerce").fillna(0)
            ddf["shift"] = ddf["shift"].fillna("-")
            ddf["machine"] = ddf["machine"].fillna("-")
            ddf["worker"] = ddf["worker"].fillna("-")
            ddf["process"] = ddf["process"].fillna("-")
            # 작업지시 번호 (식별표 제외 앞부분)
            ddf["wo"] = (ddf["work_order"].fillna("")
                         .astype(str).str.split(" ").str[0])

            t_qty = ddf["total_qty"].sum()
            t_def = ddf["defect_qty"].sum()
            # 전일 대비 추세 (기간 내 2일 이상일 때)
            _day_tot = ddf.groupby("log_date")["total_qty"].sum().sort_index()
            _delta = None
            if len(_day_tot) >= 2 and _day_tot.iloc[-2] > 0:
                _pct = (_day_tot.iloc[-1] - _day_tot.iloc[-2]) / _day_tot.iloc[-2] * 100
                _delta = f"{_pct:+.1f}% 전일 대비"
            k1, k2, k3, k4, k5 = st.columns(5)
            k1.metric("총 생산량", f"{t_qty:,.0f}", _delta)
            k2.metric("총 불량", f"{t_def:,.0f}")
            k3.metric("불량률",
                f"{t_def / t_qty * 100:.2f}%" if t_qty else "-")
            k4.metric("가동 설비",
                f"{ddf.loc[ddf['machine'] != '-', 'machine'].nunique()}대")
            k5.metric("작업지시",
                f"{ddf.loc[ddf['wo'] != '', 'wo'].nunique()}건")

            st.caption(
                "ℹ️ 가동률은 현재 작업시간 기반 근사 — 품번·공정 C.T./UPH 마스터 "
                "도입 후 시트와 같은 UPH 기준으로 전환 예정 (이관 2차). "
                "정지사유도 이관 2차에서 통합.")
            st.divider()

            # ── 일자별 생산량 + 가동률 (시트 주간요약 2개 차트 이관) ──
            def _hhmm_min(t):
                try:
                    h_, m_ = str(t).split(":")
                    return int(h_) * 60 + int(m_)
                except Exception:
                    return None

            def _calc_daily_util(df_):
                """설비별 작업시간 구간 병합 → 교대 기준 9h 대비 시간 가동률.
                시작=종료(스캔형 등록) 행은 구간 정보 없음 → 제외."""
                recs = []
                for (d_, s_, m_), g in df_.groupby(
                        ["log_date", "shift", "machine"]):
                    ivs = []
                    for _, r_ in g.iterrows():
                        a = _hhmm_min(r_.get("work_start"))
                        b = _hhmm_min(r_.get("work_end"))
                        if a is None or b is None or a == b:
                            continue
                        # 야간의 자정 이후 시각은 +24h 로 이어붙임
                        if s_ == "야간" and a < 360:
                            a += 1440
                        if s_ == "야간" and b < 360:
                            b += 1440
                        if b < a:
                            b += 1440
                        ivs.append((a, b))
                    if not ivs:
                        continue
                    ivs.sort()
                    tot, (cs, ce) = 0, ivs[0]
                    for a, b in ivs[1:]:
                        if a <= ce:
                            ce = max(ce, b)
                        else:
                            tot += ce - cs
                            cs, ce = a, b
                    tot += ce - cs
                    recs.append({"log_date": d_, "shift": s_,
                                 "util": min(1.0, tot / 60.0 / 9.0)})
                if not recs:
                    return pd.DataFrame()
                return (pd.DataFrame(recs)
                        .groupby(["log_date", "shift"], as_index=False)
                        ["util"].mean())

            _shift_scale = alt.Scale(domain=["주간", "야간"],
                                     range=["#3b5b8c", "#d9480f"])
            _num_col = st.column_config.NumberColumn
            ch1, ch2 = st.columns([2, 1])
            with ch1:
                st.markdown("##### 📈 일자별 생산량 (교대별)")
                daily = ddf.groupby(["log_date", "shift"],
                    as_index=False)["total_qty"].sum()
                ch_daily = alt.Chart(daily).mark_bar().encode(
                    x=alt.X("log_date:N", title=None,
                            axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("total_qty:Q", title="생산량 (EA)"),
                    color=alt.Color("shift:N", title="교대",
                                    scale=_shift_scale),
                    xOffset="shift:N",
                    tooltip=[alt.Tooltip("log_date:N", title="일자"),
                             alt.Tooltip("shift:N", title="교대"),
                             alt.Tooltip("total_qty:Q", title="생산량",
                                         format=",.0f")],
                ).properties(height=300)
                st.altair_chart(ch_daily, use_container_width=True)
            with ch2:
                st.markdown("##### ⏱️ 가동률 추이 (근사)")
                util = _calc_daily_util(ddf)
                if util.empty:
                    st.info("작업시간 구간 데이터가 없어 가동률을 계산할 수 "
                            "없습니다.")
                else:
                    ch_util = alt.Chart(util).mark_line(
                        point=True, strokeWidth=3).encode(
                        x=alt.X("log_date:N", title=None,
                                axis=alt.Axis(labelAngle=0)),
                        y=alt.Y("util:Q", title=None,
                                axis=alt.Axis(format=".0%"),
                                scale=alt.Scale(domain=[0, 1])),
                        color=alt.Color("shift:N", title="교대",
                                        scale=_shift_scale),
                        tooltip=[alt.Tooltip("log_date:N", title="일자"),
                                 alt.Tooltip("shift:N", title="교대"),
                                 alt.Tooltip("util:Q", title="가동률",
                                             format=".1%")],
                    ).properties(height=300)
                    st.altair_chart(ch_util, use_container_width=True)
                st.caption(
                    "설비별 작업구간 병합 ÷ 교대 9h 의 설비 평균. "
                    "스캔형(시작=종료) 실적 제외 — 시트 실가동율(UPH 기준)과 "
                    "정의가 다름. C.T. 마스터 도입 시 UPH 기준으로 전환.")

            st.divider()

            # ── 설비별 요약 (텍스트) ──
            st.markdown("##### 🏭 설비별 요약")
            by_m = (ddf.groupby(["machine", "pn", "process"], as_index=False)
                    .agg(생산=("total_qty", "sum"),
                         불량=("defect_qty", "sum"),
                         작업자=("worker", lambda s: ", ".join(
                             sorted({w for w in s if w and w != "-"})))))
            by_m = by_m.sort_values(["machine", "process"]).rename(
                columns={"machine": "설비", "pn": "품번", "process": "공정"})
            st.dataframe(by_m[["설비", "품번", "공정", "생산", "불량", "작업자"]],
                         use_container_width=True, hide_index=True,
                         height=min(420, 60 + len(by_m) * 35),
                         column_config={
                             "설비": st.column_config.TextColumn("설비", width="small"),
                             "공정": st.column_config.TextColumn("공정", width="small"),
                             "생산": _num_col("생산", format="localized", width="small"),
                             "불량": _num_col("불량", format="localized", width="small"),
                             "작업자": st.column_config.TextColumn("작업자", width="large"),
                         })

            st.divider()

            # ── 품번·공정별 / 작업자별 요약 ──
            tc1, tc2 = st.columns(2)
            with tc1:
                st.markdown("##### 🔩 품번·공정별 생산량")
                st.caption("품번 순 정렬 · 품번↔공정 연결 방침 확정 전 — 공정별 분리 집계.")
                by_p = (ddf.groupby(["pn", "process"], as_index=False)
                        .agg(생산=("total_qty", "sum"),
                             불량=("defect_qty", "sum"))
                        .sort_values(["pn", "process"])
                        .rename(columns={"pn": "품번", "process": "공정"}))
                by_p["불량률"] = by_p.apply(
                    lambda r: r["불량"] / r["생산"] if r["생산"] else None, axis=1)
                st.dataframe(by_p, use_container_width=True, hide_index=True,
                             height=min(420, 60 + len(by_p) * 35),
                             column_config={
                                 "공정": st.column_config.TextColumn("공정", width="small"),
                                 "생산": _num_col("생산", format="localized", width="small"),
                                 "불량": _num_col("불량", format="localized", width="small"),
                                 "불량률": _num_col("불량률", format="percent", width="small"),
                             })
            with tc2:
                st.markdown("##### 👷 작업자별 요약")
                st.caption("생산량 순 · 제품 특성이 달라 절대 비교보다 담당 현황 참고용.")
                by_w = (ddf[ddf["worker"] != "-"]
                        .groupby("worker", as_index=False)
                        .agg(생산=("total_qty", "sum"),
                             불량=("defect_qty", "sum"),
                             설비=("machine", lambda s: ", ".join(
                                 sorted(set(s))[:6])))
                        .sort_values("생산", ascending=False)
                        .rename(columns={"worker": "작업자"}))
                st.dataframe(by_w, use_container_width=True, hide_index=True,
                             height=min(420, 60 + len(by_w) * 35),
                             column_config={
                                 "작업자": st.column_config.TextColumn("작업자", width="small"),
                                 "생산": _num_col("생산", format="localized", width="small"),
                                 "불량": _num_col("불량", format="localized", width="small"),
                                 "설비": st.column_config.TextColumn("설비", width="large"),
                             })

            st.divider()

            # ── 작업지시서별 공정 진행 현황 ──
            st.markdown("##### 📋 작업지시서별 공정 진행 현황")
            st.caption(
                "기간 내 MES 실적 누적 (작업지시 번호 = 소재 입고 기반 발행). "
                "MES 작지 화면에 export 가 없어 앱에서 실적 기준으로 집계 — "
                "추후 완성 확정 연결 후보 키.")
            wo_src = ddf[ddf["wo"] != ""]
            if wo_src.empty:
                st.caption("작업지시서 정보 없음.")
            else:
                wo_agg = (wo_src.groupby(["wo", "pn", "process"],
                                         as_index=False)
                          .agg(qty=("total_qty", "sum")))
                wo_p = wo_agg.pivot_table(index=["wo", "pn"],
                    columns="process", values="qty",
                    aggfunc="sum", fill_value=0)
                wo_p["불량계"] = wo_src.groupby(["wo", "pn"])["defect_qty"].sum()
                wo_p = (wo_p.reset_index()
                        .rename(columns={"wo": "작업지시", "pn": "품번"})
                        .sort_values("작업지시", ascending=False))
                wo_p.columns.name = None
                st.dataframe(wo_p, use_container_width=True, hide_index=True,
                             height=min(420, 60 + len(wo_p) * 35))

            st.divider()

            # ── 불량 발생 상세 ──
            def_rows = ddf[ddf["defect_qty"] > 0]
            st.markdown(f"##### 🚨 불량 발생 상세 ({len(def_rows)}건)")
            if def_rows.empty:
                st.caption("기간 내 불량 없음 🎉")
            else:
                st.dataframe(
                    def_rows[["log_date", "shift", "machine", "pn",
                              "process", "worker", "total_qty",
                              "defect_qty"]].rename(columns={
                        "log_date": "일자", "shift": "교대",
                        "machine": "설비", "pn": "품번",
                        "process": "공정", "worker": "작업자",
                        "total_qty": "생산", "defect_qty": "불량"}),
                    use_container_width=True, hide_index=True,
                    height=min(300, 60 + len(def_rows) * 35))

    # ════════ TAB 1: 생산 보고 입력 ════════
    with tab_report:
        # ── 1) 제품 선택 ──
        pc1, pc2 = st.columns([3, 1])
        with pc1:
            prod_q = st.text_input(
                "제품 검색 (품번/고객사)",
                placeholder="예: 8HFDV-VM-05, MRG6, 미진",
                key="pb_prod_q")
        with pc2:
            st.write("")

        sel_prod = None
        if prod_q:
            qq = prod_q.strip()
            try:
                p_cands = fetch("products",
                    "product_id,pn,customer,product_group",
                    f"or=(pn.ilike.*{qq}*,customer.ilike.*{qq}*)"
                    f"&archived_at=is.null&order=pn.asc", limit=20)
            except Exception as e:
                st.error(f"제품 검색 실패: {e}"); p_cands = []
            if p_cands:
                p_labels = [f"{p['pn']} | {p.get('customer') or '-'}"
                            for p in p_cands]
                p_pick = st.selectbox(
                    f"제품 선택 ({len(p_cands)}건)",
                    p_labels, key="pb_prod_pick")
                if p_pick:
                    sel_prod = p_cands[p_labels.index(p_pick)]
            else:
                st.info("일치하는 활성 제품 없음.")

        if sel_prod:
            st.divider()
            st.markdown(f"##### 🔧 {sel_prod['pn']} · {sel_prod.get('customer') or '-'}")

            # ── 2) 생산 정보 입력 ──
            ic1, ic2, ic3, ic4 = st.columns(4)
            with ic1:
                pb_qty = st.number_input("생산 수량 (양품)", min_value=0.0,
                    value=0.0, step=1.0, key="pb_qty")
            with ic2:
                pb_defect = st.number_input("불량 수량", min_value=0.0,
                    value=0.0, step=1.0, key="pb_defect")
            with ic3:
                pb_date = st.date_input("생산일", value=_pb_date.today(),
                    key="pb_date")
            with ic4:
                pb_shift = st.selectbox("교대", ["주간", "야간"], key="pb_shift")
            lc1, lc2 = st.columns(2)
            with lc1:
                # LOT 번호 — 역추적 키 (기본 자동 제안)
                # 제품/생산일이 바뀌면 기본값 갱신 (session_state 가 이전
                # 제품의 LOT 을 유지해 다른 제품에 저장되는 것 방지)
                _lot_default = f"LOT-{pb_date.strftime('%y%m%d')}-{sel_prod['pn'][:10]}"
                if st.session_state.get("pb_lot_seed") != _lot_default:
                    st.session_state["pb_lot_seed"] = _lot_default
                    st.session_state["pb_lot"] = _lot_default
                pb_lot = st.text_input("생산 LOT 번호",
                    value=_lot_default, key="pb_lot",
                    help="자재 투입~완성~납품까지 역추적하는 키. 자동 제안값 수정 가능.")
            with lc2:
                pb_remark = st.text_input("비고 (선택)",
                    placeholder="예: 설비 M03",
                    key="pb_remark")

            total_produced = pb_qty + pb_defect

            # ── 3) BOM 자재 차감 미리보기 ──
            try:
                pb_bom = fetch("bom",
                    "bom_id,material_id,raw_material_name,qty_per_pc,shared_factor",
                    f"product_id=eq.{sel_prod['product_id']}"
                    f"&process_type=eq.MATERIAL", limit=20)
            except Exception:
                pb_bom = []
            pb_mat_rows = [b for b in pb_bom if b.get("material_id")]

            consumption = []   # (material_id, 자재명, 소요량, 현재고)
            if pb_mat_rows and total_produced > 0:
                mids = [b["material_id"] for b in pb_mat_rows]
                mids_str = ",".join(f'"{m}"' for m in mids)
                try:
                    stock_rows = fetch("material_stock",
                        "material_id,raw_name,current_stock",
                        f"material_id=in.({mids_str})", limit=50)
                    stock_map = {s["material_id"]: s for s in stock_rows}
                except Exception:
                    stock_map = {}
                for b in pb_mat_rows:
                    qpp = float(b.get("qty_per_pc") or 1)
                    sf = float(b.get("shared_factor") or 1) or 1
                    need = total_produced * qpp / sf
                    stk = stock_map.get(b["material_id"], {})
                    consumption.append({
                        "material_id": b["material_id"],
                        "name": stk.get("raw_name") or b.get("raw_material_name") or "-",
                        "need": need,
                        "stock": float(stk.get("current_stock") or 0),
                    })

            st.markdown("##### 📦 자재 차감 미리보기")
            if not pb_mat_rows:
                st.warning(
                    "⚠️ 이 제품의 BOM 자재행이 없거나 material_id 미매핑 — "
                    "**자재 차감 없이** 생산 기록만 저장됩니다. "
                    "(마스터 관리 → BOM 편집에서 보완 가능)")
            elif total_produced <= 0:
                st.caption("생산/불량 수량 입력 시 차감량이 계산됩니다.")
            else:
                cdf = pd.DataFrame([{
                    "자재ID": c["material_id"],
                    "자재명": c["name"],
                    "차감량": round(c["need"], 2),
                    "현재고": round(c["stock"], 2),
                    "차감 후": round(c["stock"] - c["need"], 2),
                } for c in consumption])
                st.dataframe(cdf, use_container_width=True, hide_index=True)
                short = [c for c in consumption if c["stock"] < c["need"]]
                if short:
                    st.warning(
                        f"⚠️ 재고 부족 자재 {len(short)}건 — 차감 시 음수 재고 발생. "
                        "그래도 기록은 가능 (실사 후 ADJUSTMENT 로 보정).")

            # ── 4) 저장 ──
            st.divider()
            sc1, sc2 = st.columns([1, 3])
            with sc1:
                do_report = st.button(
                    f"생산 보고 저장 ({total_produced:,.0f})",
                    type="primary",
                    disabled=total_produced <= 0,
                    key="pb_submit")
            with sc2:
                st.caption(
                    "production_log 기록 + 자재 PROD_INPUT 차감 + "
                    "제품 PROD_OUTPUT 재고 (모두 원장)")

            if do_report and total_produced > 0:
                try:
                    _lot = (pb_lot or "").strip() or None
                    # 1) 생산 이력
                    _db.insert("production_log", [{
                        "log_date": pb_date.isoformat(),
                        "shift": pb_shift,
                        "pn": sel_prod["pn"],
                        "product_id": sel_prod["product_id"],
                        "total_qty": total_produced,
                        "defect_qty": pb_defect,
                        "lot_number": _lot,
                        "remark": pb_remark or None,
                    }])
                    # 2) 자재 차감 (BOM 기준) — LOT 연결
                    txns = []
                    for c in consumption:
                        txns.append({
                            "material_id": c["material_id"],
                            "txn_type": "PROD_INPUT",
                            "qty": -c["need"],
                            "unit": "EA",
                            "ref_table": "production_log",
                            "product_id": sel_prod["product_id"],
                            "lot_number": _lot,
                            "txn_date": pb_date.isoformat(),
                            "remark": f"생산 투입: {sel_prod['pn']} {total_produced:,.0f}EA",
                            "created_by": "김민수",
                        })
                    # 3) 제품 완성 재고 (양품만) — LOT 연결
                    if pb_qty > 0:
                        txns.append({
                            "material_id": None,
                            "txn_type": "PROD_OUTPUT",
                            "qty": pb_qty,
                            "unit": "EA",
                            "ref_table": "production_log",
                            "product_id": sel_prod["product_id"],
                            "lot_number": _lot,
                            "txn_date": pb_date.isoformat(),
                            "remark": f"생산 완성: {sel_prod['pn']}",
                            "created_by": "김민수",
                        })
                    if txns:
                        _db.insert("inventory_transactions", txns)
                    st.success(
                        f"✅ 생산 보고 저장: {sel_prod['pn']} "
                        f"양품 {pb_qty:,.0f} / 불량 {pb_defect:,.0f}"
                        + (f" · 자재 {len(consumption)}종 차감" if consumption else
                           " · 자재 차감 없음 (BOM 미매핑)")
                    )
                except Exception as e:
                    st.error(f"저장 실패: {e}")

    # ════════ TAB 2: MES 업로드 ════════
    with tab_mes:
        st.caption(
            "사내 MES 일간 생산보고서 엑셀을 업로드 → 검수 → **공정 실적**으로 저장 "
            "(`production_log`, source=MES_UPLOAD). "
            "⚠️ **재고 연동 없음** — 공정별 실적 raw 기록 전용. "
            "완성 재고 반영(PROD_OUTPUT)은 연결 방식 확정 전까지 "
            "📝 생산 보고 입력으로 별도 진행.")

        from app.services.mes_parser import (
            parse_mes_daily_report, parse_date_from_filename,
            match_product_pn, guess_shift, PROCESS_STEP_RE)

        mes_file = st.file_uploader(
            "MES 일간 생산보고서 (.xls)", type=["xls", "html", "htm"],
            key="mes_file",
            help="MES [EXCEL] 버튼으로 내려받은 파일 그대로 업로드 "
                 "(내부적으로 HTML 테이블 형식)")

        if mes_file is not None:
            try:
                mes_rows = parse_mes_daily_report(mes_file.getvalue())
            except Exception as e:
                st.error(f"파싱 실패: {e}"); mes_rows = []

            if mes_rows:
                # ── 1) 생산일 (교대는 행 단위 자동 분류) ──
                f_date = parse_date_from_filename(mes_file.name)
                # 다른 파일로 바뀌면 날짜를 파일명 기준으로 리셋
                # (session_state 가 이전 파일 날짜를 유지하는 것 방지)
                if st.session_state.get("mes_file_seen") != mes_file.name:
                    st.session_state["mes_file_seen"] = mes_file.name
                    if f_date:
                        st.session_state["mes_date"] = f_date
                mc1, mc2 = st.columns([1, 3])
                with mc1:
                    mes_date = st.date_input(
                        "생산일", value=f_date or _pb_date.today(),
                        key="mes_date",
                        help="파일명의 날짜를 자동 인식. 필요 시 수정.")
                with mc2:
                    if f_date is None:
                        st.warning("파일명에서 날짜 인식 실패 — 직접 확인하세요.")
                    st.caption(
                        "교대는 작업 **시작시각** 기준 자동 분류 "
                        "(06:00~17:30 주간 / 그 외 야간) — 그리드에서 수정 가능. "
                        "MES 파일이 교대별이든 하루 통합이든 그대로 업로드하면 됩니다.")

                # ── 2) 제품 마스터 매칭 ──
                try:
                    all_prods = fetch("products", "product_id,pn",
                        "archived_at=is.null", limit=3000)
                except Exception as e:
                    st.error(f"제품 마스터 조회 실패: {e}"); all_prods = []
                pn_map = {p["pn"]: p["product_id"] for p in all_prods}
                pn_set = set(pn_map)

                # ── 3) 기존 저장분과 행 단위 중복 감지 ──
                # 같은 날짜의 MES 행과 (설비/공정/지시서/시간/수량) 동일하면 중복.
                # 교대별 파일을 나눠 올려도, 하루 통합 파일을 다시 올려도 안전.
                try:
                    exist = fetch("production_log",
                        "log_id,shift,machine,process,work_order,"
                        "work_start,work_end,total_qty,defect_qty",
                        f"log_date=eq.{mes_date.isoformat()}"
                        f"&source=eq.MES_UPLOAD", limit=2000)
                except Exception:
                    exist = []
                exist_keys = {
                    (e.get("machine") or "", e.get("process") or "",
                     e.get("work_order") or "", e.get("work_start") or "",
                     e.get("work_end") or "",
                     float(e.get("total_qty") or 0),
                     float(e.get("defect_qty") or 0))
                    for e in exist}

                review = []
                for r in mes_rows:
                    mpn = match_product_pn(r["item_name"], pn_set)
                    is_dup = (
                        (r["equipment"], r["process"], r["work_order"],
                         r["work_start"] or "", r["work_end"] or "",
                         float(r["qty"]), float(r["defect"])) in exist_keys)
                    review.append({
                        "포함": not is_dup,
                        "교대": guess_shift(r["work_start"]),
                        "상태": "🔁 기존" if is_dup else "신규",
                        "설비": r["equipment"],
                        "MES 품명": r["item_name"],
                        "매칭 품번": mpn or "",
                        "공정": r["process"],
                        "작업시간": f"{r['work_start'] or '-'}~{r['work_end'] or '-'}",
                        "작업자": r["worker"],
                        "작업지시서": r["work_order"],
                        "생산": r["qty"],
                        "불량": r["defect"],
                    })
                n_matched = sum(1 for v in review if v["매칭 품번"])
                n_dup = sum(1 for v in review if v["상태"] == "🔁 기존")
                n_day = sum(1 for v in review if v["교대"] == "주간")

                mm1, mm2, mm3, mm4, mm5 = st.columns(5)
                mm1.metric("상세 행", len(review))
                mm2.metric("총 생산",
                    f"{sum(v['생산'] for v in review):,.0f}")
                mm3.metric("총 불량",
                    f"{sum(v['불량'] for v in review):,.0f}")
                mm4.metric("주간/야간", f"{n_day}/{len(review) - n_day}")
                mm5.metric("품번 매칭", f"{n_matched}/{len(review)}",
                    "미매칭 있음" if n_matched < len(review) else None,
                    delta_color="inverse" if n_matched < len(review) else "off")
                if n_matched < len(review):
                    st.warning(
                        "⚠️ 미매칭 행은 품번 없이(raw 품명 그대로) 저장됩니다. "
                        "'매칭 품번' 칸에 직접 입력하거나, 제외하려면 '포함' 해제.")
                if n_dup:
                    st.info(
                        f"🔁 이미 저장된 것과 동일한 행 **{n_dup}건**은 "
                        "'포함'이 자동 해제되어 있습니다 (이중 등록 방지).")

                # ── 4) 검수 그리드 ──
                st.markdown("##### 🔍 검수 (수정 가능: 포함 / 교대 / 매칭 품번 / 생산 / 불량)")
                edited = st.data_editor(
                    pd.DataFrame(review),
                    use_container_width=True, hide_index=True, height=420,
                    key="mes_editor",
                    column_config={
                        "포함": st.column_config.CheckboxColumn("포함", width="small"),
                        "교대": st.column_config.SelectboxColumn("교대",
                            options=["주간", "야간"], required=True,
                            width="small"),
                        "생산": st.column_config.NumberColumn("생산", min_value=0),
                        "불량": st.column_config.NumberColumn("불량", min_value=0),
                    },
                    disabled=["상태", "설비", "MES 품명", "공정", "작업시간",
                              "작업자", "작업지시서"])

                inc = edited[edited["포함"]].copy()
                # data_editor 에서 비운 셀은 NaN → 문자열/숫자 정규화
                inc["매칭 품번"] = (inc["매칭 품번"].fillna("")
                                  .astype(str).str.strip()
                                  .replace("nan", ""))
                inc["교대"] = inc["교대"].fillna("주간")
                inc["생산"] = pd.to_numeric(inc["생산"], errors="coerce").fillna(0)
                inc["불량"] = pd.to_numeric(inc["불량"], errors="coerce").fillna(0)
                bad_pn = [p for p in inc["매칭 품번"].tolist()
                          if p and p not in pn_set]
                if bad_pn:
                    st.error(
                        f"❌ 마스터에 없는 품번 {len(bad_pn)}건: "
                        f"{', '.join(sorted(set(bad_pn))[:5])} — 수정 후 저장하세요.")

                # ── 5) 저장 방식 (기존 행이 있을 때만) ──
                dup_mode = "추가"
                if exist:
                    ex_day = sum(1 for e in exist if e.get("shift") == "주간")
                    ex_night = len(exist) - ex_day
                    st.warning(
                        f"⚠️ {mes_date} MES 실적이 이미 있습니다 — "
                        f"주간 {ex_day}행 / 야간 {ex_night}행.")
                    up_shifts = sorted(set(inc["교대"])) if len(inc) else []
                    del_cnt = sum(1 for e in exist
                                  if e.get("shift") in up_shifts)
                    dup_mode = st.radio("저장 방식",
                        ["추가 (권장 — 동일 행은 위에서 자동 제외됨)",
                         f"교체 (이번 업로드의 교대 {'/'.join(up_shifts) or '-'} "
                         f"기존 {del_cnt}행 삭제 후 저장)"],
                        horizontal=True, key="mes_dup_mode")
                    if dup_mode.startswith("교체"):
                        st.caption(
                            "수정된 파일을 다시 올릴 때 사용하세요. "
                            "업로드에 없는 교대의 기존 행은 유지됩니다.")

                # ── 5) 저장 ──
                st.divider()
                sv1, sv2 = st.columns([1, 3])
                with sv1:
                    do_mes_save = st.button(
                        f"📥 MES 실적 저장 ({len(inc)}행)",
                        type="primary",
                        disabled=len(inc) == 0 or bool(bad_pn),
                        key="mes_submit")
                with sv2:
                    st.caption(
                        "production_log 에 source=MES_UPLOAD 로 저장 — "
                        "**재고 원장에는 반영되지 않습니다.**")

                if do_mes_save and len(inc) > 0 and not bad_pn:
                    try:
                        if exist and dup_mode.startswith("교체"):
                            for _sh in sorted(set(inc["교대"])):
                                n_del = _db.delete("production_log",
                                    f"log_date=eq.{mes_date.isoformat()}"
                                    f"&shift=eq.{_sh}&source=eq.MES_UPLOAD")
                                if n_del:
                                    st.info(f"기존 {_sh} {n_del}행 삭제 (교체)")
                        recs = []
                        for _, v in inc.iterrows():
                            mpn = v["매칭 품번"] or None
                            ws_, _, we_ = str(v["작업시간"] or "").partition("~")
                            _step_m = PROCESS_STEP_RE.search(v["공정"] or "")
                            recs.append({
                                "log_date": mes_date.isoformat(),
                                "shift": v["교대"],
                                "machine": v["설비"],
                                "worker": v["작업자"] or None,
                                "process": v["공정"] or None,
                                "process_step": (int(_step_m.group(1))
                                                 if _step_m else None),
                                "pn": mpn or v["MES 품명"],
                                "product_id": pn_map.get(mpn),
                                "total_qty": float(v["생산"] or 0),
                                "defect_qty": float(v["불량"] or 0),
                                "work_order": v["작업지시서"] or None,
                                "work_start": ws_.strip() if ws_.strip() != "-" else None,
                                "work_end": we_.strip() if we_.strip() != "-" else None,
                                "source": "MES_UPLOAD",
                                "remark": (None if mpn else
                                           f"품번 미매칭 (MES 품명: {v['MES 품명']})"),
                            })
                        _db.insert("production_log", recs)
                        _d = sum(1 for r in recs if r["shift"] == "주간")
                        st.success(
                            f"✅ MES 실적 {len(recs)}행 저장 — {mes_date} · "
                            f"주간 {_d} / 야간 {len(recs) - _d} · "
                            f"생산 {sum(r['total_qty'] for r in recs):,.0f} / "
                            f"불량 {sum(r['defect_qty'] for r in recs):,.0f} "
                            f"(재고 미반영)")
                    except Exception as e:
                        st.error(f"저장 실패: {e}")

    # ════════ TAB 3: 생산 이력 ════════
    with tab_history:
        hc1, hc2, hc3 = st.columns([2, 1, 1])
        with hc1:
            h_q = st.text_input("품번 검색", placeholder="예: 8HFDV",
                key="pb_hist_q")
        with hc2:
            h_src = st.selectbox("입력 소스",
                ["전체", "📝 수기 보고", "📥 MES 업로드"],
                key="pb_hist_src")
        with hc3:
            h_limit = st.number_input("표시", 10, 500, 50, 10, key="pb_hist_limit")

        h_filter = ["order=log_date.desc,log_id.desc"]
        if h_q:
            h_filter.append(f"pn=ilike.*{h_q.strip()}*")
        if h_src == "📝 수기 보고":
            h_filter.append("source=eq.MANUAL")
        elif h_src == "📥 MES 업로드":
            h_filter.append("source=eq.MES_UPLOAD")
        try:
            logs = fetch("production_log",
                "log_id,log_date,shift,pn,product_id,total_qty,defect_qty,"
                "machine,process,worker,work_order,source,remark",
                "&".join(h_filter), limit=int(h_limit))
        except Exception as e:
            st.error(f"이력 조회 실패: {e}"); logs = []

        if not logs:
            st.info("생산 이력 없음.")
        else:
            total_q = sum(float(l.get("total_qty") or 0) for l in logs)
            total_d = sum(float(l.get("defect_qty") or 0) for l in logs)
            n_mes = sum(1 for l in logs if l.get("source") == "MES_UPLOAD")
            hm1, hm2, hm3, hm4 = st.columns(4)
            hm1.metric("보고 건수", len(logs))
            hm2.metric("총 생산량", f"{total_q:,.0f}")
            hm3.metric("총 불량", f"{total_d:,.0f}",
                       f"{total_d/total_q*100:.1f}%" if total_q else None,
                       delta_color="inverse")
            hm4.metric("MES 행", f"{n_mes}/{len(logs)}")

            ldf = pd.DataFrame([{
                "일자": l.get("log_date"),
                "교대": l.get("shift") or "-",
                "소스": "MES" if l.get("source") == "MES_UPLOAD" else "수기",
                "설비": l.get("machine") or "-",
                "품번": l.get("pn"),
                "공정": l.get("process") or "-",
                "생산": float(l.get("total_qty") or 0),
                "불량": float(l.get("defect_qty") or 0),
                "작업자": l.get("worker") or "-",
                "작업지시서": l.get("work_order") or "-",
                "비고": l.get("remark") or "-",
            } for l in logs])
            st.dataframe(ldf, use_container_width=True, hide_index=True,
                         height=400)

            # 일간 보고서 집계 (MES 소계 대체) — 조회 결과 기준
            with st.expander("📊 집계 보기 (설비별 / 품번·공정별)", expanded=False):
                ag1, ag2 = st.columns(2)
                with ag1:
                    st.markdown("**설비별**")
                    eq_agg = ldf.groupby("설비", as_index=False).agg(
                        생산=("생산", "sum"), 불량=("불량", "sum"),
                        행수=("품번", "count")).sort_values("생산", ascending=False)
                    st.dataframe(eq_agg, use_container_width=True, hide_index=True)
                with ag2:
                    st.markdown("**품번·공정별**")
                    pn_agg = ldf.groupby(["품번", "공정"], as_index=False).agg(
                        생산=("생산", "sum"), 불량=("불량", "sum")).sort_values(
                        "생산", ascending=False)
                    st.dataframe(pn_agg, use_container_width=True, hide_index=True)

        # 제품 완성 재고 현황
        st.divider()
        st.markdown("##### 📦 제품 완성 재고 (product_stock_v)")
        try:
            pstock = fetch("product_stock_v",
                "pn,customer,produced_qty,issued_qty,current_stock,last_txn_date",
                "order=current_stock.desc", limit=50)
        except Exception as e:
            st.caption(f"조회 실패 (Migration 018 필요): {e}"); pstock = []
        if pstock:
            psdf = pd.DataFrame(pstock).rename(columns={
                "pn": "품번", "customer": "고객사",
                "produced_qty": "생산 누적", "issued_qty": "출고 누적",
                "current_stock": "현재고", "last_txn_date": "최근 거래"})
            st.dataframe(psdf, use_container_width=True, hide_index=True)
        else:
            st.caption("제품 재고 거래 없음 (생산 보고 저장 시 자동 생성).")

    # ════════ TAB 3: 역추적 (LOT/제품) ════════
    with tab_trace:
        st.caption(
            "LOT 번호 또는 제품으로 **자재 입고 → 생산 투입 → 생산 완성 → 납품 출고** "
            "전 과정을 원장 기준으로 역추적합니다."
        )

        trace_mode = st.radio("추적 기준",
            ["LOT 번호", "제품 (품번)"],
            horizontal=True, key="trace_mode")

        if trace_mode == "LOT 번호":
            # LOT 목록 자동 제안
            try:
                lot_list = fetch("lot_trace_v", "lot_number",
                    "order=created_at.desc", limit=200)
                lots = sorted({l["lot_number"] for l in lot_list
                               if l.get("lot_number")}, reverse=True)
            except Exception as e:
                st.error(f"LOT 조회 실패 (Migration 019 필요): {e}"); lots = []

            if not lots:
                st.info("기록된 LOT 없음. 생산 보고 시 LOT 번호가 자동 기록됩니다.")
            else:
                sel_lot = st.selectbox(f"LOT 선택 ({len(lots)}개)",
                    lots, key="trace_lot_pick")
                if sel_lot:
                    try:
                        trace_rows = fetch("lot_trace_v",
                            "txn_date,step_label,txn_type,material_id,"
                            "material_name,pn,qty,unit,ref_table,ref_id,"
                            "remark,created_at",
                            f"lot_number=eq.{sel_lot}"
                            f"&order=created_at.asc", limit=100)
                    except Exception as e:
                        st.error(f"추적 실패: {e}"); trace_rows = []

                    if trace_rows:
                        st.markdown(f"##### 🔎 {sel_lot} — {len(trace_rows)}건")
                        tdf = pd.DataFrame([{
                            "일자": t.get("txn_date"),
                            "단계": t.get("step_label"),
                            "자재/제품": t.get("material_name") or t.get("pn") or "-",
                            "수량": float(t.get("qty") or 0),
                            "참조": f"{t.get('ref_table') or '-'}#{t.get('ref_id') or ''}",
                            "비고": t.get("remark") or "-",
                        } for t in trace_rows])
                        st.dataframe(tdf, use_container_width=True,
                                     hide_index=True)
                        # 요약: 투입/완성/출고 밸런스
                        t_in = sum(-float(t["qty"]) for t in trace_rows
                                   if t["txn_type"] == "PROD_INPUT")
                        t_out = sum(float(t["qty"]) for t in trace_rows
                                    if t["txn_type"] == "PROD_OUTPUT")
                        t_issue = sum(-float(t["qty"]) for t in trace_rows
                                      if t["txn_type"] == "ISSUE")
                        tm1, tm2, tm3, tm4 = st.columns(4)
                        tm1.metric("자재 투입", f"{t_in:,.0f}")
                        tm2.metric("생산 완성", f"{t_out:,.0f}")
                        tm3.metric("납품 출고", f"{t_issue:,.0f}")
                        tm4.metric("LOT 잔량", f"{t_out - t_issue:,.0f}")

        else:  # 제품 기준
            tp_q = st.text_input("제품 검색 (품번)",
                placeholder="예: 8HFDV-VM-05",
                key="trace_prod_q")
            if tp_q:
                qq = tp_q.strip()
                try:
                    trace_rows = fetch("product_trace_v",
                        "pn,txn_date,step_label,txn_type,material_id,"
                        "material_name,qty,unit,lot_number,ref_table,ref_id,"
                        "remark,created_at",
                        f"pn=ilike.*{qq}*&order=created_at.asc", limit=200)
                except Exception as e:
                    st.error(f"추적 실패: {e}"); trace_rows = []

                if not trace_rows:
                    st.info("해당 제품의 원장 거래 없음.")
                else:
                    st.markdown(f"##### 🔎 제품 이력 — {len(trace_rows)}건")
                    tdf = pd.DataFrame([{
                        "일자": t.get("txn_date"),
                        "품번": t.get("pn"),
                        "단계": t.get("step_label"),
                        "자재": t.get("material_name") or "-",
                        "수량": float(t.get("qty") or 0),
                        "LOT": t.get("lot_number") or "-",
                        "참조": f"{t.get('ref_table') or '-'}#{t.get('ref_id') or ''}",
                        "비고": t.get("remark") or "-",
                    } for t in trace_rows])
                    st.dataframe(tdf, use_container_width=True,
                                 hide_index=True, height=400)


elif page == "원가 확인":
    st.subheader("원가 확인")
    st.caption(
        "**가격·원가·마진만 다루는 화면**. BOM 구조 편집은 마스터 관리 → BOM 편집 에서. "
        "**자동 반영 / 자동 overwrite 없음** — 후보 확인 → 사용자 직접 반영."
    )

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

    # ⚠️ / 🧮 는 참고용 진단 탭
    tabs = st.tabs(["마진 대시보드", "품목 분석",
                    "이상치 (참고)", "BOM 재산정 (참고)",
                    "원가 편집", "통합 view"])

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

                    # ── 📊 BOM 자재의 매입 단가 변동 추이 ──
                    try:
                        prod_bom = fetch("bom",
                            "bom_id,material_id,raw_material_name,process_type",
                            f"product_id=eq.{row['product_id']}"
                            f"&process_type=eq.MATERIAL", limit=10)
                    except Exception:
                        prod_bom = []
                    prod_mat_rows = [b for b in prod_bom
                                     if (b.get('process_type') or 'MATERIAL') == 'MATERIAL']
                    if prod_mat_rows:
                        st.divider()
                        st.markdown("##### 📊 BOM 자재 매입 단가 변동 추이")
                        st.caption(
                            "각 자재의 매입 거래 (자재명/규격 기준 검색). "
                            "matched_material_id 가 없어도 item 키워드로 시계열 산출."
                        )

                        for mat_row in prod_mat_rows:
                            mat_name = (mat_row.get('raw_material_name') or
                                        '').strip()
                            mat_id = mat_row.get('material_id')
                            if not mat_name:
                                continue

                            # 1) matched_material_id 기준 우선 검색
                            mp_rows = []
                            if mat_id:
                                try:
                                    mp_rows = fetch("purchase_ledger",
                                        "trade_date,vendor,item,qty,unit_price,kg_price,ea_price",
                                        f"matched_material_id=eq.{mat_id}"
                                        f"&order=trade_date.desc",
                                        limit=300)
                                except Exception:
                                    mp_rows = []

                            # 2) item 키워드로 fallback 검색
                            if not mp_rows:
                                # 자재명에서 핵심 키워드 추출 (첫 단어 또는 재질명)
                                kw = mat_name.split()[0] if mat_name else mat_name
                                try:
                                    mp_rows = fetch("purchase_ledger",
                                        "trade_date,vendor,item,qty,unit_price,kg_price,ea_price",
                                        f"item=ilike.*{kw}*"
                                        f"&order=trade_date.desc",
                                        limit=300)
                                except Exception:
                                    mp_rows = []
                                # 추가 필터: 자재명 다른 단어도 매칭 (정확도 향상)
                                if mp_rows and len(mat_name.split()) > 1:
                                    tokens = [t for t in mat_name.split()
                                              if len(t) >= 2]
                                    if len(tokens) >= 2:
                                        mp_rows = [
                                            r for r in mp_rows
                                            if all(t.lower() in (r.get('item') or '').lower()
                                                   for t in tokens)
                                        ]

                            with st.expander(
                                f"🔧 {mat_name} (BOM #{mat_row['bom_id']}, "
                                f"{mat_id or '-'}) — 매입 {len(mp_rows)}건",
                                expanded=False):
                                if not mp_rows:
                                    st.info(
                                        f"'{mat_name}' 키워드로 매입 이력 없음. "
                                        "매입 단가 조회 위젯에서 다른 키워드 시도 가능."
                                    )
                                    continue

                                df_mp = pd.DataFrame(mp_rows)
                                df_mp["unit_price"] = pd.to_numeric(
                                    df_mp["unit_price"], errors="coerce")
                                df_mp["trade_date"] = pd.to_datetime(
                                    df_mp["trade_date"], errors="coerce")
                                valid_mp = df_mp.dropna(
                                    subset=["trade_date", "unit_price"])
                                valid_mp = valid_mp[valid_mp["unit_price"] > 0]

                                if len(valid_mp) >= 1:
                                    recent_mp = valid_mp.iloc[0]["unit_price"]
                                    avg_mp = valid_mp["unit_price"].mean()
                                    min_mp = valid_mp["unit_price"].min()
                                    max_mp = valid_mp["unit_price"].max()
                                    last_d = valid_mp.iloc[0]["trade_date"]

                                    mm1, mm2, mm3, mm4, mm5 = st.columns(5)
                                    mm1.metric("최근 단가", _money(recent_mp))
                                    mm2.metric("평균 단가", _money(avg_mp))
                                    mm3.metric("최저", _money(min_mp))
                                    mm4.metric("최고", _money(max_mp))
                                    mm5.metric("최근 거래",
                                        last_d.strftime("%Y-%m-%d")
                                        if pd.notna(last_d) else "-")

                                    # 월별 평균 차트
                                    if len(valid_mp) >= 2:
                                        vc = valid_mp.copy()
                                        vc["월"] = (vc["trade_date"]
                                            .dt.to_period("M").astype(str))
                                        monthly = (vc.groupby("월")["unit_price"]
                                                   .mean().sort_index())
                                        if len(monthly) >= 2:
                                            st.line_chart(monthly, height=180,
                                                use_container_width=True)

                                    # 최근 거래 표
                                    df_show = df_mp.head(20).copy()
                                    df_show["trade_date"] = (
                                        df_show["trade_date"]
                                        .dt.strftime("%Y-%m-%d")
                                        if pd.api.types.is_datetime64_any_dtype(
                                            df_show["trade_date"])
                                        else df_show["trade_date"]
                                    )
                                    df_show["unit_price"] = df_show["unit_price"].apply(
                                        lambda v: f"{v:,.0f}"
                                        if pd.notna(v) else "-")
                                    st.dataframe(
                                        df_show[["trade_date","vendor","item",
                                                 "qty","unit_price"]].rename(
                                            columns={"trade_date":"거래일",
                                                     "vendor":"거래처",
                                                     "item":"품목",
                                                     "qty":"수량",
                                                     "unit_price":"단가"}),
                                        use_container_width=True,
                                        hide_index=True, height=200)
                                else:
                                    st.caption("유효한 단가 데이터 없음.")

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
                                "🚀 BOM 빠른 정비 또는 BOM 편집에서 등록.")
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

                cc1, cc2, cc3 = st.columns([1, 1, 3])
                with cc1:
                    auto_sum_b = st.checkbox("추정원가 자동합계",
                                             value=False, key="bulk_auto_sum",
                                             help="기본 OFF. 체크 시 estimated_cost_per_pc = "
                                                  "소재+외주+열처리+표면 자동 덮어쓰기.")
                with cc2:
                    confirm_save = st.checkbox("⚠️ 일괄 저장 확인",
                                                value=False, key="bulk_confirm",
                                                help="2단계 확인. 체크해야 저장 버튼 활성화.")
                with cc3:
                    save_btn = st.button("💾 변경분 일괄 저장",
                                         type="primary", use_container_width=False,
                                         disabled=not confirm_save)

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
