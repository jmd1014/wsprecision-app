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


# ─── 토스 스타일 리스타일 (design/toss-restyle, 2026-08-12) ───
# 원칙: 테두리 대신 그림자+큰 라디우스, 색은 상태·버튼에만, Pretendard.
# 상태 의미는 기존 규칙 유지 — 문제=danger, 대기=warn, 완료=good, 진행=primary
st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css');
:root{
  --primary:#3182f6;--primary-hov:#1b64da;--link:#1b64da;
  --bg:#f9fafb;--card:#ffffff;
  --line:#eef1f4;--line2:#f2f4f6;--line3:#f7f8fa;
  --ink:#191f28;--body:#333d4b;--dim:#6b7684;--faint:#8b95a1;--mute:#b0b8c1;
  --warn:#dd6b02;--warn2:#f04452;--warn-bg:#fff3e0;
  --good:#01a76b;--good-bg:#e6f9f1;
  --note:#ffb331;--note-txt:#a86e00;--note-bg:#fff7e1;
  --primary-bg:#e8f3ff;--blue-bg:#e8f3ff;
  --shadow:0 1px 3px rgba(2,32,71,.05),0 5px 14px rgba(2,32,71,.06);
}
html, body, [class*="css"], font, div, span, p, label, input, textarea,
button, select {
  font-family:'Pretendard',-apple-system,sans-serif !important;
}
/* Material 아이콘은 아이콘 폰트 유지 (전역 폰트 강제의 예외) */
span[data-testid="stIconMaterial"],
[class*="material-symbols"], [class*="material-icons"]{
  font-family:'Material Symbols Rounded','Material Icons' !important;
}

/* ── 제목 위계 ── */
h1{font-size:22px !important;font-weight:800 !important;
   color:var(--ink) !important;letter-spacing:-.4px;}
h2,h3{color:var(--ink) !important;font-weight:700 !important;
   letter-spacing:-.2px;}
h5{font-size:14.5px !important;font-weight:700 !important;
   color:var(--ink) !important;}

/* ── KPI 메트릭 → 카드 (그림자 구분, 테두리 없음) ── */
div[data-testid="stMetric"]{
  background:var(--card);border:none;border-radius:16px;
  padding:18px 20px;box-shadow:var(--shadow);
}
div[data-testid="stMetricLabel"] p{
  font-size:13px !important;font-weight:500 !important;
  color:var(--faint) !important;
}
div[data-testid="stMetricValue"]{
  font-size:26px !important;font-weight:800 !important;
  color:var(--ink) !important;letter-spacing:-.6px;
}
div[data-testid="stMetricDelta"]{font-size:12.5px !important;}

/* ── 탭 ── */
div[data-testid="stTabs"] button[data-baseweb="tab"]{
  font-weight:600;color:var(--faint);font-size:14px;
}
div[data-testid="stTabs"] button[aria-selected="true"]{
  color:var(--ink);
}

/* ── expander → 카드 ── */
div[data-testid="stExpander"]{
  background:var(--card);border:none !important;
  border-radius:16px;box-shadow:var(--shadow);
}

/* ── 버튼 (보조: 테두리 없는 회색 면 — 토스 스타일) ── */
div[data-testid="stButton"] button,
div[data-testid="stDownloadButton"] button{
  border-radius:10px;font-weight:600;font-size:14px;
  border:none;background:#f2f4f6;color:var(--body);
  transition:background .15s ease;
}
div[data-testid="stButton"] button:hover,
div[data-testid="stDownloadButton"] button:hover{
  background:#e8ebee;color:var(--ink);
}
div[data-testid="stButton"] button[kind="primary"],
div[data-testid="stDownloadButton"] button[kind="primary"]{
  background:var(--primary) !important;color:#fff !important;
}
div[data-testid="stButton"] button[kind="primary"]:hover,
div[data-testid="stDownloadButton"] button[kind="primary"]:hover{
  background:var(--primary-hov) !important;
}
/* 비활성 버튼 — 회색 면 유지 + 흐린 글자 (잠긴 버튼 가독성) */
div[data-testid="stButton"] button:disabled,
div[data-testid="stDownloadButton"] button:disabled{
  background:#f2f4f6 !important;color:var(--mute) !important;
  border:none !important;cursor:not-allowed;
}
div[data-testid="stButton"] button:disabled p,
div[data-testid="stDownloadButton"] button:disabled p{
  color:var(--mute) !important;
}

/* ── 사이드바: 흰 배경, 경계는 은은하게 ── */
section[data-testid="stSidebar"]{
  background:var(--card);border-right:1px solid var(--line2);
  min-width:216px !important;max-width:246px !important;
}
section[data-testid="stSidebar"] h2{
  font-size:15px !important;color:var(--ink) !important;
}
section[data-testid="stSidebar"] div[data-testid="stCaptionContainer"] p{
  font-size:11px !important;font-weight:700 !important;
  color:var(--mute) !important;letter-spacing:.07em;
  text-transform:uppercase;
}
section[data-testid="stSidebar"] label[data-baseweb="radio"] div p{
  font-size:14px !important;color:var(--body);
}

/* ── 알림 박스 ── */
div[data-testid="stAlert"]{
  border-radius:12px;border-left-width:4px !important;
}

/* ── 데이터프레임 ── */
div[data-testid="stDataFrame"]{
  border:1px solid var(--line2);border-radius:12px;
}

/* ── 헤더 ── */
.ws-hdr{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:4px}
.ws-hdr .t{font-size:22px;color:var(--ink);font-weight:800;letter-spacing:-.4px}
.ws-hdr .t .co{color:var(--primary)}
.ws-hdr .sub{color:var(--dim);font-size:13.5px}
.ws-hdr-meta{margin-left:auto;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.ws-chip{background:#f2f4f6;border:none;border-radius:20px;
  padding:6px 13px;font-size:12px;color:var(--dim);
  display:inline-flex;gap:6px;align-items:center}
.ws-chip b{font-weight:700}
.ws-chip.ok b{color:var(--good)}
.ws-chip.err b{color:var(--warn2)}

/* ── 홈 KPI 카드 (상태는 숫자 색으로 — 스트라이프 없음) ── */
.kpi-row{display:flex;gap:14px;flex-wrap:wrap;margin:4px 0 12px}
.kpi{flex:1;min-width:150px;background:var(--card);
  border:none;border-radius:16px;padding:18px 20px;
  box-shadow:var(--shadow)}
.kpi .k{font-size:13px;font-weight:500;color:var(--faint);
  margin-bottom:7px}
.kpi .v{font-size:28px;font-weight:800;color:var(--ink);
  letter-spacing:-.6px;line-height:1.1}
.kpi .s{font-size:12.5px;color:var(--faint);margin-top:5px}
.kpi.warn .v{color:var(--warn)}
.kpi.danger .v{color:var(--warn2)}
.kpi.good .v{color:var(--good)}
.kpi.zero .v{color:var(--mute)}

/* ── 공정 스테퍼 (투입→생산→외주→검사→완성) — 필 세그먼트 ── */
.stepper{display:flex;gap:8px;margin:6px 0 10px}
.step{flex:1;text-align:center;font-size:12.5px;font-weight:600;
  padding:9px 4px;border:none;border-radius:10px;
  color:var(--mute);background:#f2f4f6}
.step.on{background:var(--primary);color:#fff}
.step.done{background:var(--good-bg);color:var(--good)}
.step.warn{background:var(--warn-bg);color:var(--warn)}

/* ── 납품 스케줄 회차 간트 (7b) ── */
.gt{display:grid;grid-template-columns:250px repeat(6,1fr) 96px;
  background:var(--card);border:none;border-radius:16px;
  box-shadow:var(--shadow);
  margin:6px 0 4px}  /* overflow hidden 금지 — 호버 메모가 잘린다 */
.gt>div{padding:9px 10px;border-bottom:1px solid var(--line3);
  border-right:1px solid var(--line3);min-width:0}
.gt>div:nth-child(8n){border-right:none}
.gt>div:nth-child(8n+1){border-right:1px solid var(--line2)}
.gt .gh{font-size:12px;font-weight:600;color:var(--faint);
  border-bottom:1px solid var(--line2)}
.gt .gh.now{color:var(--primary);font-weight:700;background:#f5f9ff}
.gt .cell.now{background:#fafcff}
.gt .gpn{font-size:13px;font-weight:700;color:var(--ink);
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.gt .gsub{font-size:11.5px;color:var(--dim);margin-top:2px}
.gt .grate{font-size:11px;font-weight:600;margin-top:3px}
.gt .gsum{background:var(--line3);border-bottom:none;font-size:12.5px;
  font-weight:700;color:var(--ink);text-align:right}
.gt .gsum.l{font-size:11.5px;font-weight:600;color:var(--faint);
  letter-spacing:.02em;text-align:left}
.gc{display:flex;justify-content:space-between;align-items:center;
  gap:8px;padding:5px 10px;border-radius:12px;margin-bottom:5px;
  position:relative;cursor:default}
.gc:last-child{margin-bottom:0}
/* 회차 칩 호버 메모 — 마우스를 올리면 세부 내역 */
.gc .tip{display:none;position:absolute;z-index:60;left:0;top:100%;
  margin-top:5px;background:var(--ink);color:#fff;
  font-size:11.5px;font-weight:400;line-height:1.8;
  padding:10px 13px;border-radius:10px;white-space:nowrap;
  box-shadow:0 6px 18px rgba(25,31,40,.28);text-align:left}
.gc .tip b{font-weight:600;color:#fff}
.gc .tip .warn{color:#ffb4a0;font-weight:600}
.gc:hover .tip{display:block}
/* 마지막 품번 행·합계 행의 칩은 메모를 위로 띄움 (화면 밖 방지) */
.gt > div:nth-last-child(-n+16) .gc .tip{top:auto;bottom:100%;
  margin-top:0;margin-bottom:5px}
.gc .gd{font-size:11px;white-space:nowrap}
.gc .gq{font-size:11.5px;font-weight:700;color:var(--ink)}
.gc.late{background:#fef1f1;border:none;
  border-left:3px solid var(--warn2)}
.gc.late .gd{color:var(--warn2);font-weight:700}
.gc.plan{background:var(--primary-bg);border:none;
  border-left:3px solid var(--primary)}
.gc.plan .gd{color:var(--link);font-weight:600}
.gc.done{background:var(--line3);border:none;
  border-left:3px solid var(--good)}
.gc.done .gd{color:var(--faint);font-weight:600}
.gc.done .gq{color:var(--faint)}
.gc.one{background:var(--line3);border:none;
  border-left:3px solid var(--dim);border-radius:8px}
.gc.one .gd{color:#4e5968;font-weight:600}
.gc.one.late{border-left-color:var(--warn2)}
.gc.one.late .gd{color:var(--warn2);font-weight:700}
/* '이후' 열 — 회차 나열 대신 총량 요약 (행 높이 고정) */
.gc.after{display:block;text-align:right;padding:6px 10px;
  background:var(--card);border:1px dashed #c7ddfb;
  border-left:3px solid var(--link);border-radius:12px}
.gc.after .tip{left:auto;right:0;text-align:left}
.gc.after .gq{display:block;font-size:12.5px}
.gc.after .gd{display:block;color:var(--dim);font-weight:600;
  margin-top:1px}

/* ── 토스 스타일 HTML 테이블 (toss_table 헬퍼) ── */
.tt-wrap{background:var(--card);border-radius:16px;box-shadow:var(--shadow);
  overflow-x:auto;margin:6px 0 10px}
.tt-wrap.scroll{max-height:560px;overflow-y:auto}
.tt{width:100%;border-collapse:collapse;font-size:13.5px}
.tt th{position:sticky;top:0;background:var(--card);z-index:2;
  font-size:12.5px;font-weight:600;color:var(--faint);text-align:left;
  padding:12px 16px;border-bottom:1px solid var(--line2);white-space:nowrap}
.tt td{padding:12px 16px;border-bottom:1px solid var(--line3);
  color:var(--body);white-space:nowrap}
.tt tbody tr:last-child td{border-bottom:none}
.tt tbody tr{transition:background .12s}
.tt tbody tr:hover{background:#fafbfc}
.tt th.r,.tt td.r{text-align:right;font-variant-numeric:tabular-nums}
.tt td b{font-weight:700;color:var(--ink)}
.tt .neg{color:var(--warn2);font-weight:700}
.tt .dim{color:var(--mute)}
.tt tr.hl td{background:#fef1f1}
.tt .late{color:var(--warn2);font-weight:700}
.tt .badge{display:inline-block;font-size:12px;font-weight:600;
  padding:4px 10px;border-radius:7px;line-height:1.3}
.tt .b-red{background:#fdecec;color:var(--warn2)}
.tt .b-green{background:var(--good-bg);color:var(--good)}
.tt .b-amber{background:var(--warn-bg);color:var(--warn)}
.tt .b-blue{background:var(--primary-bg);color:#1b64da}
.tt .b-gray{background:#f2f4f6;color:var(--faint)}

/* ── 미계획 물량 경고 카드 ── */
.unplan{background:var(--warn-bg);border:none;
  border-left:4px solid var(--warn);border-radius:12px;
  padding:15px 18px;margin:12px 0 6px}
.unplan .t{font-size:14.5px;font-weight:700;color:var(--warn)}
.unplan .d{font-size:12.5px;color:var(--body);margin-top:7px;
  line-height:1.75}
.unplan .d b{font-weight:600;color:var(--ink)}
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


# ─── 로그인 (계정별 접근 · 2026-08-04) ───────────────────
from utils import auth as _auth  # noqa: E402

# Streamlit Cloud 는 재배포 시 프로세스를 유지한 채 코드만 바꾸는 경우가
# 있어, 이미 import 된 모듈이 옛 버전으로 남는다 (sys.modules 캐시).
# 최신 버전에만 있는 속성이 없으면 강제 reload (2026-08-05 실장애)
if not hasattr(_auth, "PW_RULES"):
    import importlib as _il
    _auth = _il.reload(_auth)


def current_user() -> dict:
    return st.session_state.get("auth_user") or {}


def current_user_name() -> str:
    """원장·이력의 created_by — 로그인 사용자 실명"""
    return current_user().get("name") or "시스템"


def click_guard(name, ttl=5.0):
    """이중 클릭 가드 — 같은 처리의 재진입을 ttl초 동안 막는다.

    Streamlit 은 클릭 즉시 버튼을 잠글 수 없어(서버 rerun 모델)
    빠른 두 번째 클릭이 큐잉되어 순서대로 실행된다 — 2026-08-18
    SH-20260817-01/-02 동일 전표 2건(1.4초 간격) 사고의 원인.
    쓰기 버튼의 클릭 핸들러 첫 줄에서 호출해 True 일 때만 처리:

        if st.button(...):
            if click_guard("ship_reg"):
                ... insert ...

    런은 세션 안에서 직렬 실행되므로 두 번째 런은 첫 런이 남긴
    타임스탬프를 보고 중단된다 (멱등성 키의 로컬 구현).
    """
    import time
    k = f"_guard_{name}"
    now = time.time()
    if now - float(st.session_state.get(k) or 0) < ttl:
        st.warning("방금 같은 처리가 실행됐습니다 — 버튼이 두 번 "
                   "눌린 경우입니다. 화면의 결과를 확인하세요.")
        return False
    st.session_state[k] = now
    return True


def _cookie_js(script: str):
    """쿠키 기록·삭제용 JS 실행.

    components.html 의 iframe(srcdoc)은 앱과 같은 origin 이라
    document.cookie 가 앱 도메인에 그대로 적용된다. 단, 같은 런에서
    st.rerun() 을 부르면 컴포넌트가 마운트되기 전에 화면이 교체되어
    쿠키가 저장되지 않는다 — 반드시 rerun 없는 안정 런에서 호출할 것
    (2026-08-07 자동 로그인 미동작 원인)."""
    try:
        from streamlit.components.v1 import html as _html_js
        _html_js(f"<script>{script}</script>", height=0)
    except Exception:
        pass


def _cookie_read(name: str):
    """st.context 로 쿠키 읽기 — 컴포넌트 왕복 없이 첫 런에서 확정."""
    try:
        return st.context.cookies.get(name)
    except Exception:
        return None


# 테스트 하네스(AppTest)는 secrets 로 로그인을 끈다 — 운영 배포에는
# 이 키가 없으므로 항상 로그인 필요
try:
    _AUTH_OFF = bool(st.secrets.get("auth", {}).get("disabled"))
except Exception:
    _AUTH_OFF = False
if _AUTH_OFF and not st.session_state.get("auth_user"):
    st.session_state["auth_user"] = {
        "username": "test", "name": "테스트", "role": "admin"}

if DB_AVAILABLE and not st.session_state.get("auth_user"):
    import db as _adb
    import base64 as _b64

    _users = _auth.load_users(_adb)
    _secret = _auth.load_secret(_adb)

    # 1) 쿠키 자동 로그인 — st.context (동기 읽기, 로그아웃 직후 제외)
    if _users and _secret and not st.session_state.get("auth_skip_cookie"):
        _tok_b64 = _cookie_read("ws_auth")
        _tok = None
        if _tok_b64:
            try:
                # 한글 아이디 → 쿠키는 ASCII 만 안전하므로 base64 저장
                _tok = _b64.urlsafe_b64decode(
                    _tok_b64.encode()).decode("utf-8")
            except Exception:
                _tok = None
        _uid = _auth.parse_token(_tok, _secret) if _tok else None
        if _uid and _uid in _users:
            # rerun 불필요 — 같은 런에서 세션만 채우고 아래로 통과
            st.session_state["auth_user"] = {
                "username": _uid,
                "name": _users[_uid].get("name") or _uid,
                "role": _users[_uid].get("role") or "worker"}

    # 2) 로그인 폼
    if not st.session_state.get("auth_user"):
        # 로그아웃 직후 예약된 쿠키 삭제 실행 (rerun 없는 런)
        if st.session_state.pop("auth_cookie_clear", None):
            _cookie_js("document.cookie='ws_auth=; path=/; max-age=0';")
        _lc1, _lc2, _lc3 = st.columns([1, 1.2, 1])
        with _lc2:
            if not _users:
                st.error("계정 정보가 없습니다 — 관리자에게 문의하세요. "
                         "(app_settings.auth_users 미설정)")
                st.stop()
            with st.form("ws_login"):
                st.markdown("#### 로그인")
                _li_id = st.text_input("아이디")
                _li_pw = st.text_input("비밀번호", type="password")
                _li_keep = st.checkbox("이 기기에서 자동 로그인 (14일)",
                                       value=True)
                _li_go = st.form_submit_button("로그인", type="primary",
                                               use_container_width=True)
            if _li_go:
                _u = _users.get((_li_id or "").strip())
                if _u and _auth.verify_pw(_li_pw, _u.get("pw", "")):
                    st.session_state["auth_user"] = {
                        "username": (_li_id or "").strip(),
                        "name": _u.get("name") or _li_id,
                        "role": _u.get("role") or "worker"}
                    st.session_state.pop("auth_skip_cookie", None)
                    if _li_keep and _secret:
                        # 여기서 바로 쓰면 rerun 에 잘려 저장 안 됨 —
                        # 인증 후 안정 런에 예약
                        st.session_state["auth_cookie_write"] = (
                            _b64.urlsafe_b64encode(_auth.make_token(
                                st.session_state["auth_user"]["username"],
                                _secret).encode("utf-8")).decode())
                    st.rerun()
                else:
                    st.error("아이디 또는 비밀번호가 맞지 않습니다.")
            st.stop()

# 로그인 시 예약한 자동 로그인 쿠키 기록 — 인증 후 첫 안정 런에서 실행
_pend_ck = st.session_state.pop("auth_cookie_write", None)
if _pend_ck:
    _cookie_js(
        "document.cookie='ws_auth={}; path=/; max-age=1209600; "
        "SameSite=Lax';".format(_pend_ck))


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
#   진한 주황 #f04452 = 문제(지연·불합격·폐기·부족) / 주황 #dd6b02 =
#   진행 대기(부분·외주·재작업) / 초록 #01a76b = 완료·합격 /
#   주색 #3182f6 = 생산중·활성 — 전 페이지 동일 규칙.
_ST_RED = ("지연", "불합", "폐기", "취소", "부족")
_ST_GREEN = ("완납", "입고완료", "합격", "완료", "전량", "종결", "완성")
_ST_AMBER = ("대기", "부분", "외주", "재작업", "미납")
_ST_BLUE = ("생산중", "확정", "발송")


def status_style(df, cols=("상태",)):
    """상태 컬럼에 의미 색 적용한 Styler 반환 (색 규칙 참조)"""
    def _c(v):
        s = str(v)
        if any(k in s for k in _ST_RED):
            return "color:#f04452;font-weight:700"
        if any(k in s for k in _ST_GREEN):
            return "color:#01a76b;font-weight:600"
        if any(k in s for k in _ST_AMBER):
            return "color:#dd6b02;font-weight:600"
        if any(k in s for k in _ST_BLUE):
            return "color:#3182f6;font-weight:600"
        return "color:#6b7684"
    _sub = [c for c in cols if c in df.columns]
    if not _sub:
        return df
    try:
        return df.style.map(_c, subset=_sub)
    except AttributeError:          # pandas < 2.1
        return df.style.applymap(_c, subset=_sub)


def _badge_class(v):
    """상태 텍스트 → 배지 색 클래스 (status_style 과 같은 색 규칙)"""
    s = str(v)
    if any(k in s for k in _ST_RED):
        return "b-red"
    if any(k in s for k in _ST_GREEN):
        return "b-green"
    if any(k in s for k in _ST_AMBER):
        return "b-amber"
    if any(k in s for k in _ST_BLUE):
        return "b-blue"
    return "b-gray"


def toss_table(rows, columns=None, *, badge_cols=(), num_cols=(),
               strong_cols=(), raw_cols=(), hl_rows=(), scroll=False):
    """읽기 전용 표를 토스 스타일 HTML 테이블로 렌더 (.tt CSS).

    st.dataframe(글라이드 그리드)은 CSS 커스텀이 안 되므로, 배지·강조가
    중요한 표는 이 헬퍼로 그린다. 편집이 필요한 표는 계속 data_editor.

    rows: list[dict] 또는 DataFrame. columns: 표시 순서(생략 시 첫 행 키).
    badge_cols: 상태 배지로 그릴 컬럼 / num_cols: 우측 정렬+콤마 /
    strong_cols: 굵게(품번 등) / raw_cols: 호출부가 만든 HTML 그대로
    (반드시 호출부에서 escape 책임) / hl_rows: 위험 행 인덱스(연빨강 배경).
    """
    import html as _h
    if hasattr(rows, "to_dict"):
        rows = rows.to_dict("records")
    if not rows:
        return
    cols = list(columns) if columns else list(rows[0].keys())

    def _fmt(c, v):
        if c in raw_cols:
            return "" if v is None else str(v)
        if v is None or v == "":
            return '<span class="dim">-</span>'
        if c in badge_cols:
            return (f'<span class="badge {_badge_class(v)}">'
                    f"{_h.escape(str(v))}</span>")
        if c in num_cols and isinstance(v, (int, float)):
            txt = (f"{v:,.0f}" if float(v).is_integer() else f"{v:,.2f}")
            return f'<span class="neg">{txt}</span>' if v < 0 else txt
        out = _h.escape(str(v))
        return f"<b>{out}</b>" if c in strong_cols else out

    _r = ' class="r"'
    _hl = ' class="hl"'
    head = "".join(
        f"<th{_r if c in num_cols else ''}>{_h.escape(str(c))}</th>"
        for c in cols)
    body = []
    for i, r in enumerate(rows):
        tds = "".join(
            f"<td{_r if c in num_cols else ''}>{_fmt(c, r.get(c))}</td>"
            for c in cols)
        body.append(f"<tr{_hl if i in hl_rows else ''}>{tds}</tr>")
    st.markdown(
        f'<div class="tt-wrap{" scroll" if scroll else ""}">'
        f'<table class="tt"><thead><tr>{head}</tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table></div>',
        unsafe_allow_html=True)


# ─── 공정 라우팅 (Migration 036, 2026-08-12) ───
# 라우팅 = 제품별 공정 '순서' 마스터. 공정 '원가'는 BOM(process_type 행).
# 라우팅 행이 없는 제품은 기본 플로우로 동작한다.
ROUTING_DEFAULT = [
    # 기본 플로우는 외주 없이 소재입고→생산→검사→완성 (2026-08-12
    # 사용자 확정 — 25ABV 등 외주 없는 제품이 대부분). 외주가 실제로
    # 발생한 작업지시는 공정 처리 스테퍼가 외주 칸을 동적으로 붙인다.
    {"routing_id": None, "seq": 1, "step_code": "MAT_IN",
     "step_name": "소재입고", "step_kind": "INHOUSE", "stage": "MATERIAL"},
    {"routing_id": None, "seq": 10, "step_code": "PROD",
     "step_name": "생산", "step_kind": "INHOUSE", "stage": "PRODUCT"},
    {"routing_id": None, "seq": 50, "step_code": "INSPECT",
     "step_name": "검사", "step_kind": "INHOUSE", "stage": "PRODUCT"},
    {"routing_id": None, "seq": 60, "step_code": "DONE",
     "step_name": "완성", "step_kind": "INHOUSE", "stage": "PRODUCT"},
]


def get_routing(product_id):
    """제품 라우팅 조회 — 없으면 기본 플로우 반환 (routing_id=None)"""
    if product_id:
        try:
            rows = fetch("product_routing", "*",
                         f"product_id=eq.{product_id}&order=seq", limit=50)
            if rows:
                return rows
        except Exception:
            pass
    return [dict(s) for s in ROUTING_DEFAULT]


def routing_out_steps(routing, stage="PRODUCT"):
    """라우팅의 외주 스텝만 (기본: 제품 단계)"""
    return [s for s in routing
            if s.get("step_kind") == "OUTSOURCE" and s.get("stage") == stage]


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
    "INPUT_CANCEL": "투입 취소",
    "MAT_OUT_SEND": "소재 외주 출고", "MAT_OUT_RETURN": "소재 외주 회수",
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


def w_lot_max_used():
    """원장에서 실제 사용 중인 최대 식별 번호 (없으면 0).

    수기 수정·취소 등 인위적 개입이 있어도 채번이 스스로 최신
    번호를 찾는 근거 — 카운터가 어긋나도 원장이 정본.
    """
    try:
        import db as _dbw
        rows = _dbw.fetch("inventory_transactions", "lot_number",
                          "lot_number=like.W*"
                          "&order=lot_number.desc", limit=20)
        nums = []
        for r in rows:
            _d = "".join(ch for ch in str(r.get("lot_number") or "")
                         if ch.isdigit())
            if _d:
                nums.append(int(_d))
        return max(nums) if nums else 0
    except Exception:
        return 0


def w_lot_next(count=1):
    """소재 LOT (식별 번호) 채번 — max(카운터, 원장 최대 번호) + 1.

    카운터는 앱 도입 전 실물 이력의 기준점(설정 후 발급 시 갱신),
    원장 최대 번호는 실사용 정본. 둘 중 큰 값 다음부터 발급하므로
    수기 수정으로 카운터가 어긋나도 중복 발급이 없다.
    반환: ["W0905", ...] count개. 카운터 미설정 시 None (입고는 식별
    번호 없이 진행 가능, 입고 처리 탭 하단에서 시작 번호 등록 안내).
    """
    if count <= 0:
        return []
    try:
        import db as _dbw
        row = _dbw.fetch_one("app_settings", "key=eq.w_lot_counter", "value")
        val = str((row or {}).get("value") or "").strip()
        if not val.isdigit():
            return None
        base = max(int(val), w_lot_max_used())
        nums = [base + i + 1 for i in range(count)]
        _dbw.update("app_settings", "key=eq.w_lot_counter",
                    {"value": str(nums[-1])})
        return [f"W{n:04d}" for n in nums]
    except Exception:
        return None


def w_lot_sync_counter():
    """수기 수정·입고 취소 후 카운터를 원장 실사용 최대 번호로 동기화.

    최신 번호를 지우거나 아래로 고치면 카운터가 따라 내려가 다음
    입고가 그 번호를 다시 받고, 위로 고치면 따라 올라가 중복이 없다.
    원장이 비면(전량 취소) 실물 기준점 보존을 위해 손대지 않는다.
    반환: 동기화 후 카운터 값 (미설정·원장 비면 None).
    """
    try:
        import db as _dbw
        mx = w_lot_max_used()
        if mx <= 0:
            return None
        row = _dbw.fetch_one("app_settings", "key=eq.w_lot_counter", "value")
        val = str((row or {}).get("value") or "").strip()
        if not val.isdigit():
            return None
        if int(val) != mx:
            _dbw.update("app_settings", "key=eq.w_lot_counter",
                        {"value": str(mx)})
        return mx
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
        "영업 보고",
    ]
    ALL_MENU = MENU_FLOW + MENU_ADMIN

    # 두 그룹 radio — 한쪽 선택 시 다른 쪽 해제 (page 는 하나만)
    def _nav_pick_flow():
        st.session_state["nav_admin"] = None

    def _nav_pick_admin():
        st.session_state["nav_flow"] = None

    _is_admin = current_user().get("role", "admin") == "admin"

    st.header("업무 진행")
    nav_flow = st.radio("업무", MENU_FLOW, key="nav_flow",
                        on_change=_nav_pick_flow,
                        label_visibility="collapsed")
    if _is_admin:
        st.divider()
        st.caption("관리자")
        nav_admin = st.radio("관리자", MENU_ADMIN, key="nav_admin",
                             index=None, on_change=_nav_pick_admin,
                             label_visibility="collapsed")
    else:
        # 작업자 계정 — 관리자 메뉴(마스터·원가·생산 보고) 숨김
        nav_admin = None
    page = nav_admin or nav_flow or "홈"
    if not _is_admin and page in MENU_ADMIN:
        page = "홈"

    # ── 계정 ──
    if current_user():
        st.divider()
        st.caption("계정")
        st.markdown(
            '<span class="ws-chip"><b>{}</b> · {}</span>'.format(
                current_user_name(),
                "관리자" if _is_admin else "작업자"),
            unsafe_allow_html=True)
        if st.button("로그아웃", use_container_width=True, key="auth_out"):
            st.session_state.pop("auth_user", None)
            # 쿠키 삭제는 다음 런(로그인 화면)에서 실행 — 같은 런에서
            # 지우고 rerun 하면 컴포넌트가 잘려 삭제되지 않는다
            st.session_state["auth_cookie_clear"] = True
            # st.context 쿠키는 새로고침 전까지 옛 값을 주므로 세션 차단
            st.session_state["auth_skip_cookie"] = True
            st.rerun()
        with st.expander("비밀번호 변경"):
            # form 필수 — 일반 버튼은 입력 중(포커스 유지) 값을 못 읽어
            # "6자 이상" 오류가 나는 경합이 있었음 (2026-08-05)
            with st.form("pc_form", clear_on_submit=True):
                st.caption(_auth.PW_RULES)
                _pc_old = st.text_input("현재 비밀번호", type="password")
                _pc_new = st.text_input("새 비밀번호", type="password")
                _pc_new2 = st.text_input("새 비밀번호 확인", type="password")
                _pc_go = st.form_submit_button("변경",
                                               use_container_width=True)
            if _pc_go:
                import db as _pdb
                _pu = _auth.load_users(_pdb)
                _me = current_user().get("username")
                _bad = _auth.check_password(_pc_new, _me)
                if _me not in _pu or not _auth.verify_pw(
                        _pc_old, _pu[_me].get("pw", "")):
                    st.error("현재 비밀번호가 맞지 않습니다.")
                elif _bad:
                    st.error(f"새 비밀번호: {_bad}")
                elif _pc_new != _pc_new2:
                    st.error("새 비밀번호 확인이 서로 다릅니다.")
                else:
                    _pu[_me]["pw"] = _auth.hash_pw(_pc_new)
                    if _auth.save_users(_pdb, _pu):
                        st.success("변경 완료 — 다음 로그인부터 적용")
                    else:
                        st.error("저장 실패 — 다시 시도하세요.")

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
            "so_id,so_number,customer,so_date,due_date,total_qty,"
            "total_received_qty,total_pending_qty,delivery_status",
            'status=not.in.("CANCELLED","CANCELED")&order=so_date.desc',
            limit=500)
    except Exception:
        _h_so = []
    # 수주별 대표 품번 + 분납 스케줄 납기 (미납 라인 기준)
    _h_pn, _h_sched, _h_lines = {}, {}, []
    _open_ids = [s["so_id"] for s in _h_so
                 if float(s.get("total_pending_qty") or 0) > 0][:120]
    if _open_ids:
        _ids = ",".join(str(i) for i in _open_ids)
        try:
            _h_lines = fetch("sales_order_items",
                "so_id,soi_id,product_id,canonical_pn,customer_part_no,"
                "qty,received_qty,pending_qty,due_date",
                f"so_id=in.({_ids})&pending_qty=gt.0"
                "&order=pending_qty.desc", limit=800)
            for _l in _h_lines:      # pending desc → 첫 라인이 대표
                _e = _h_pn.setdefault(_l["so_id"],
                                      {"top": None, "n": 0})
                if _e["top"] is None:
                    _e["top"] = (_l.get("canonical_pn")
                                 or _l.get("customer_part_no") or "-")
                _e["n"] += 1
        except Exception:
            _h_lines = []
        _h_sched_line = {}
        try:
            for _sc in fetch("so_delivery_schedule",
                "so_id,soi_id,due_date,qty,delivered_qty",
                f"so_id=in.({_ids})&order=due_date.asc", limit=800):
                if (float(_sc.get("qty") or 0)
                        - float(_sc.get("delivered_qty") or 0)) > 0:
                    _h_sched.setdefault(_sc["so_id"], _sc["due_date"])
                    _h_sched_line.setdefault(_sc["soi_id"],
                                             _sc["due_date"])
        except Exception:
            _h_sched_line = {}
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
        # 품번별 = 생산 일정 관리 단위 (같은 품번에 수주가 계속
        # 추가되므로 실무 기본값). 수주별은 문서 단위 확인용.
        _h_view = st.radio("수주 진행 보기", ["품번별", "수주별"],
                           horizontal=True, key="home_so_view",
                           label_visibility="collapsed")
        st.markdown(f"##### 수주 진행 ({_h_view} · 미납 · 납기순)")

    if _h_view == "품번별":
        with hc1:
            if not _h_lines:
                st.info("미납 수주 없음 — 수주 관리에서 업로드하면 "
                        "표시됩니다.")
            else:
                _so_cust = {s["so_id"]: s.get("customer")
                            for s in _h_so}
                _stock_map = {p["pn"]: float(p.get("current_stock") or 0)
                              for p in _h_ps}
                _wip_map = {}
                for _w in _h_wo:
                    _q = wo_stage_qty(_w)
                    _k = _w.get("pn")
                    if _k:
                        _wip_map[_k] = (_wip_map.get(_k, 0)
                                        + _q["생산중"] + _q["외주중"]
                                        + _q["재작업중"] + _q["검사대기"])
                _agg = {}
                for _l in _h_lines:
                    _pn = (_l.get("canonical_pn")
                           or _l.get("customer_part_no") or "-")
                    _a = _agg.setdefault(_pn, {
                        "pn": _pn, "pend": 0.0, "qty": 0.0, "rcv": 0.0,
                        "n_so": set(), "custs": set(), "due": None})
                    _a["pend"] += float(_l.get("pending_qty") or 0)
                    _a["qty"] += float(_l.get("qty") or 0)
                    _a["rcv"] += float(_l.get("received_qty") or 0)
                    _a["n_so"].add(_l["so_id"])
                    _c = _so_cust.get(_l["so_id"])
                    if _c:
                        _a["custs"].add(_c)
                    _d = (_h_sched_line.get(_l["soi_id"])
                          or _l.get("due_date")
                          or _h_sched.get(_l["so_id"]))
                    if _d and (_a["due"] is None or _d < _a["due"]):
                        _a["due"] = _d
                _rows_pn = sorted(_agg.values(),
                                  key=lambda a: (a["due"] or "9999-12-31",
                                                 -a["pend"]))
                _n_late_pn = sum(1 for a in _rows_pn if a["due"]
                                 and a["due"] < _hd.today().isoformat())

                def _dd_pn(d):
                    if not d:
                        return "-"
                    n = (_hd.fromisoformat(d) - _hd.today()).days
                    return (f"지연 {-n}일" if n < 0
                            else "오늘" if n == 0 else f"D-{n}")

                if len(_rows_pn) > 15:
                    _cu = ["전체 거래처"] + sorted(
                        {c for a in _rows_pn for c in a["custs"]})
                    _cf = st.selectbox("거래처", _cu, key="home_pn_cust",
                                       label_visibility="collapsed")
                    if _cf != "전체 거래처":
                        _rows_pn = [a for a in _rows_pn
                                    if _cf in a["custs"]]
                _cut_pn = len(_rows_pn) - 15
                _pndf = pd.DataFrame([{
                    "품번": a["pn"],
                    "거래처": (next(iter(a["custs"])) if len(a["custs"]) == 1
                             else f"{len(a['custs'])}개사"),
                    "납기": _dd_pn(a["due"]),
                    "수주": a["n_so"].__len__(),
                    "미납": a["pend"],
                    "완성재고": _stock_map.get(a["pn"], 0.0),
                    "생산중": _wip_map.get(a["pn"], 0.0),
                    "부족": max(0.0, a["pend"] - _stock_map.get(a["pn"], 0.0)
                               - _wip_map.get(a["pn"], 0.0)),
                } for a in _rows_pn[:15]])
                st.dataframe(
                    _pndf.style.apply(
                        lambda r: ["color:#f04452;font-weight:700"
                                   if str(r["납기"]).startswith("지연")
                                   else ""] * len(r), axis=1),
                    use_container_width=True, hide_index=True,
                    height=min(430, 60 + len(_pndf) * 35),
                    column_config={
                        "수주": st.column_config.NumberColumn(
                            "수주건", width="small"),
                        **{c: st.column_config.NumberColumn(
                            format="localized", width="small")
                           for c in ["미납", "완성재고", "생산중", "부족"]},
                    })
                _cap_pn = [f"품목 {len(_agg)}종"]
                if _n_late_pn:
                    _cap_pn.append(f"납기 지연 {_n_late_pn}종")
                if _cut_pn > 0:
                    _cap_pn.append(f"외 {_cut_pn:,}종은 수주 관리 → "
                                   "품목별에서 확인")
                st.caption(" · ".join(_cap_pn)
                           + " — 부족 = 미납 − 완성재고 − 생산중(진행 "
                             "작업지시)")

    with hc1:
        _open_so = [s for s in _h_so
                    if float(s.get("total_pending_qty") or 0) > 0]
        if _h_view != "수주별":
            pass
        elif not _open_so:
            st.info("미납 수주 없음 — 수주 관리에서 업로드하면 표시됩니다.")
        else:
            # 납기 = 분납 스케줄의 가장 빠른 미완료 회차 > 수주 납기
            for _s in _open_so:
                _s["_due"] = (_h_sched.get(_s.get("so_id"))
                              or _s.get("due_date"))
                _s["_sched"] = bool(_h_sched.get(_s.get("so_id")))
            # 납기 임박·지연이 항상 위로 — 수주 많아져도 볼 것부터 보이게
            _open_so.sort(key=lambda s: s.get("_due") or "9999-12-31")

            def _h_dday(d):
                if not d:
                    return "-"
                _dd = (_hd.fromisoformat(d) - _hd.today()).days
                if _dd < 0:
                    return f"지연 {-_dd}일"
                return "오늘" if _dd == 0 else f"D-{_dd}"

            _n_late = sum(1 for s in _open_so
                          if s.get("_due")
                          and s["_due"] < _hd.today().isoformat())
            if len(_open_so) > 15:
                _hc_opts = ["전체 거래처"] + sorted(
                    {s["customer"] for s in _open_so if s.get("customer")})
                _hcf = st.selectbox("거래처", _hc_opts, key="home_so_cust",
                                    label_visibility="collapsed")
                if _hcf != "전체 거래처":
                    _open_so = [s for s in _open_so
                                if s["customer"] == _hcf]
            _so_cut = len(_open_so) - 15

            def _h_item(s):
                e = _h_pn.get(s.get("so_id")) or {}
                pn = e.get("top") or "-"
                return (f"{pn} 외 {e['n'] - 1}종" if e.get("n", 0) > 1
                        else pn)

            _h_sodf = pd.DataFrame([{
                "수주번호": s["so_number"], "거래처": s["customer"],
                "품번": _h_item(s),
                "납기": (_h_dday(s.get("_due"))
                        + (" ⟳" if s.get("_sched") else "")),
                "미납": float(s.get("total_pending_qty") or 0),
                "진행률": (float(s.get("total_received_qty") or 0)
                          / float(s.get("total_qty") or 1)),
                "상태": status_ko(s.get("delivery_status")),
            } for s in _open_so[:15]])
            st.dataframe(
                _h_sodf.style.apply(
                    lambda row: ["color: #f04452; font-weight: 700"
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

    # 개발기 정비용 탭(데이터 제외 규칙·매입↔자재 매핑·마스터/연결
    # 점검)은 2026-08-05 제거 — 제외 규칙 자체는 DB 뷰에 내장되어
    # 계속 적용된다. 중복 자재 병합 도구는 자재 편집 하단으로 이동.
    (tab_fit, tab1, tab_prod, tab_mat, tab_bom, tab_rout,
     tab_acct, tab_dsn) = st.tabs([
        "품번별 맞추기",
        "거래처 편집", "제품 편집", "자재 편집", "BOM 편집", "공정 라우팅",
        "계정 관리", "디자인 데이터 내보내기"
    ])

    # ─── Tab: 공정 라우팅 (Migration 036, 2026-08-12) ───
    # 라우팅 = 제품별 공정 '순서'. 공정 '원가'는 BOM(process_type 행)이
    # 담당하고, 외주 스텝은 bom_id 로 원가 행과 연결된다.
    with tab_rout:
        st.markdown("**제품별 공정 순서(라우팅)를 정의합니다** — "
                    "공정 관리의 스테퍼·외주 공정 선택이 이 순서를 따릅니다.")
        st.caption(
            "라우팅이 없는 제품은 기본 플로우(소재입고 → 생산 → 외주 → "
            "검사 → 완성)로 동작하므로, 외주 공정이 있는 제품만 정의하면 "
            "됩니다. **단계=소재**는 투입 전 외주(소재열처리 등), "
            "**단계=제품**은 가공 후 외주입니다.")

        # 순서 확정 대기 (BOM 공정에서 자동 생성된 라우팅)
        try:
            _unconf = fetch("product_routing", "product_id",
                            "confirmed=eq.false", limit=500)
        except Exception:
            _unconf = []
        _unids = sorted({r["product_id"] for r in _unconf})
        if _unids:
            _ustr = ",".join(f'"{p}"' for p in _unids)
            try:
                _upn = fetch("products", "product_id,pn",
                             f"product_id=in.({_ustr})", limit=100)
            except Exception:
                _upn = []
            st.warning(
                "**순서 확정 필요**: "
                + " · ".join(p["pn"] for p in _upn)
                + " — BOM 공정 행에서 자동 생성된 라우팅입니다. 외주 "
                "공정의 단계(소재/제품)와 순서를 확인하고 저장하세요.")

        _rq = st.text_input("제품 검색 (품번/품명)", key="rout_q",
                            placeholder="예: MRG6-07")
        if (_rq or "").strip():
            _kw = _rq.strip()
            try:
                _rcand = fetch("products", "product_id,pn,item_name",
                    f"or=(pn.ilike.*{_kw}*,item_name.ilike.*{_kw}*)"
                    "&archived_at=is.null&order=pn", limit=30)
            except Exception as e:
                st.error(e); _rcand = []
            if not _rcand:
                st.info("검색 결과 없음")
            else:
                _rp_lbl = [p["pn"] + (f" | {p['item_name']}"
                                      if p.get("item_name") else "")
                           for p in _rcand]
                _rp_pick = st.selectbox("제품 선택", _rp_lbl,
                                        key="rout_pick")
                _rp_id = _rcand[_rp_lbl.index(_rp_pick)]["product_id"]

                _cur = get_routing(_rp_id)
                _has_custom = any(s.get("routing_id") for s in _cur)
                if not _has_custom:
                    st.caption("정의된 라우팅 없음 — 기본 플로우입니다. "
                               "수정 후 저장하면 이 제품 전용 라우팅이 "
                               "생성됩니다.")

                # 이 제품의 BOM 전체 행 — 소재(MATERIAL)는 소재입고
                # 스텝에, 공정(HEAT/SURFACE 등)은 외주 스텝에 연결해
                # '라우팅 = BOM 정보가 공정 순서 위에 완성된 그림'이 되게
                try:
                    _pbom = fetch("bom",
                        "bom_id,process_type,raw_material_name,unit_price",
                        f"product_id=eq.{_rp_id}", limit=50)
                except Exception:
                    _pbom = []
                _pbom.sort(key=lambda b: (
                    (b.get("process_type") or "MATERIAL") != "MATERIAL",
                    b["bom_id"]))

                def _bom_lbl(b):
                    _is_mat = ((b.get("process_type") or "MATERIAL")
                               == "MATERIAL")
                    return (f"#{b['bom_id']} "
                            f"{b.get('raw_material_name') or b['process_type']}"
                            + (" (소재)" if _is_mat else " (외주)")
                            + (f" ₩{int(float(b['unit_price'])):,}"
                               if b.get("unit_price") else ""))

                _bom_opts = ["(연결 안 함)"] + [_bom_lbl(b) for b in _pbom]
                _bom_by_lbl = {_bom_opts[i + 1]: _pbom[i]["bom_id"]
                               for i in range(len(_pbom))}
                _lbl_by_bom = {v: k for k, v in _bom_by_lbl.items()}
                _mat_bom = next(
                    (b for b in _pbom
                     if (b.get("process_type") or "MATERIAL")
                     == "MATERIAL"), None)

                # 외주 거래처 고정 후보 — PPAP 개념: 공정은 검증된 업체만.
                # 여기서 고정하면 공정 처리에서 변경 불가(마스터 전용)
                try:
                    _rvend = fetch("vendors", "name",
                                   "in_use=eq.true&order=name", limit=300)
                except Exception:
                    _rvend = []
                _vend_opts = ["(미지정)"] + [v["name"] for v in _rvend]

                _kind_lbl = {"INHOUSE": "사내", "OUTSOURCE": "외주"}
                _stage_lbl = {"MATERIAL": "소재", "PRODUCT": "제품"}

                def _link_lbl(s):
                    """스텝의 BOM 연결 표시 — 소재입고는 소재 행 자동 제안"""
                    _l = _lbl_by_bom.get(s.get("bom_id"))
                    if _l:
                        return _l
                    if s.get("step_code") == "MAT_IN" and _mat_bom:
                        return _lbl_by_bom.get(_mat_bom["bom_id"],
                                               "(연결 안 함)")
                    return "(연결 안 함)"

                _red = st.data_editor(
                    pd.DataFrame([{
                        "순서": s["seq"],
                        "공정명": s["step_name"],
                        "구분": _kind_lbl.get(s.get("step_kind"), "사내"),
                        "단계": _stage_lbl.get(s.get("stage"), "제품"),
                        "BOM 연결": _link_lbl(s),
                        "외주 거래처": (s.get("default_vendor")
                                        or "(미지정)"),
                    } for s in _cur]),
                    hide_index=True, num_rows="dynamic",
                    use_container_width=True,
                    column_config={
                        "순서": st.column_config.NumberColumn(
                            required=True, step=1,
                            help="이 숫자 순으로 정렬됩니다"),
                        "공정명": st.column_config.TextColumn(
                            required=True),
                        "구분": st.column_config.SelectboxColumn(
                            options=["사내", "외주"], required=True),
                        "단계": st.column_config.SelectboxColumn(
                            options=["소재", "제품"], required=True,
                            help="소재 = 투입 전 / 제품 = 가공 후"),
                        "BOM 연결": st.column_config.SelectboxColumn(
                            options=_bom_opts,
                            help="외주 공정의 원가 행(BOM) 연결"),
                        "외주 거래처": st.column_config.SelectboxColumn(
                            options=_vend_opts,
                            help="PPAP 승인 업체 고정 — 지정하면 공정 "
                                 "처리에서 변경 불가 (품질 유지)"),
                    }, key=f"rout_ed_{_rp_id}")

                # BOM 연결 완성도 — 라우팅이 BOM 정보를 다 덮었는지 표시
                _linked_ids = {_bom_by_lbl.get(r.get("BOM 연결"))
                               for r in _red.to_dict("records")}
                _unlinked = [b for b in _pbom
                             if b["bom_id"] not in _linked_ids]
                if _pbom and _unlinked:
                    st.caption(
                        f"BOM 연결 {len(_pbom) - len(_unlinked)}"
                        f"/{len(_pbom)} — 미연결: "
                        + ", ".join(_bom_lbl(b) for b in _unlinked))
                elif _pbom:
                    st.caption(f"BOM 연결 {len(_pbom)}/{len(_pbom)} — "
                               "모든 BOM 행이 라우팅에 연결되었습니다.")

                _CODE_BY_NAME = {"소재입고": "MAT_IN", "생산": "PROD",
                                 "검사": "INSPECT", "완성": "DONE"}
                rc1, rc2 = st.columns([1, 1])
                if rc1.button("라우팅 저장", type="primary",
                              key="rout_save"):
                    _rows = [r for r in _red.to_dict("records")
                             if (str(r.get("공정명") or "")).strip()]
                    if not _rows:
                        st.error("공정이 없습니다.")
                    else:
                        _rows.sort(key=lambda r: float(r.get("순서") or 0))
                        _ins = []
                        for _i, r in enumerate(_rows):
                            _nm = str(r["공정명"]).strip()
                            _kind = ("OUTSOURCE" if r.get("구분") == "외주"
                                     else "INHOUSE")
                            _vend_pick = (r.get("외주 거래처") or "").strip()
                            _ins.append({
                                "product_id": _rp_id,
                                "seq": (_i + 1) * 10,
                                "step_code": ("OUT" if _kind == "OUTSOURCE"
                                              else _CODE_BY_NAME.get(
                                                  _nm, "STEP")),
                                "step_name": _nm,
                                "step_kind": _kind,
                                "stage": ("MATERIAL"
                                          if r.get("단계") == "소재"
                                          else "PRODUCT"),
                                "bom_id": _bom_by_lbl.get(
                                    r.get("BOM 연결")),
                                "default_vendor": (
                                    _vend_pick
                                    if _kind == "OUTSOURCE"
                                    and _vend_pick not in ("", "(미지정)")
                                    else None),
                                "confirmed": True,
                            })
                        try:
                            _db.delete("product_routing",
                                       f"product_id=eq.{_rp_id}")
                            _db.insert("product_routing", _ins)
                            st.success(f"라우팅 저장: {_rp_pick} — "
                                       f"{len(_ins)}개 공정")
                            st.rerun()
                        except Exception as e:
                            st.error(f"저장 실패: {e}")
                if _has_custom and rc2.button(
                        "기본 플로우로 되돌리기 (라우팅 삭제)",
                        key="rout_reset"):
                    try:
                        _db.delete("product_routing",
                                   f"product_id=eq.{_rp_id}")
                        st.success("라우팅 삭제 — 기본 플로우로 동작합니다.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"삭제 실패: {e}")

    # ─── Tab: 품번별 맞추기 (2026-07-31) ───
    # 발주서 없이 소재를 먼저 입고하고, 완성재고를 출하 시점에 실사로
    # 맞춰가는 도구. 과거 매입내역을 일괄 매핑하는 대신 실제 물건이
    # 움직일 때마다 표본을 쌓아 정합을 올리는 방식.
    with tab_fit:
        from datetime import date as _ft_date
        st.markdown("**품번 하나를 골라 소재·완성재고·BOM 을 그 자리에서 맞춥니다**")
        st.caption(
            "발주서 없이 소재를 먼저 입고하고, 출하 시점에 완성재고를 "
            "실사 수량으로 맞출 수 있습니다. 모든 기록은 재고 원장에 "
            "남아 LOT 추적이 이어집니다.")

        # ── Day 0 실사 시트 (2026-08-07 금요일 실사 기준일) ──
        with st.expander("실사 시트 내려받기 (Day 0 준비)"):
            st.caption(
                "휴면 제외 전체 자재 목록입니다 (장부는 8/5 전량 0으로 "
                "리셋됨 — 실물 수량이 새 기준이 됩니다). 출력해서 실물을 "
                "세고, 자재 편집에서 실사 수량을 입력하세요. BOM 에 "
                "연결된 자재가 위쪽에 옵니다. 실사 이후의 입출고는 전부 "
                "앱에만 입력합니다.")
            try:
                _inv_rows = _db.fetch(
                    "materials",
                    "material_id,raw_name,material_type,spec,unit,"
                    "main_supplier,stock_qty,applied_pn",
                    "archived_at=is.null&order=material_id", limit=1000)
                # 사용 품번 — BOM 연결 제품으로 현장에서 소재를 빨리 식별
                _pn_map = {}
                try:
                    _bl = _db.fetch("bom", "material_id,product_id",
                                    "material_id=not.is.null", limit=2000)
                    _pids = {b["product_id"] for b in _bl}
                    _pm = {}
                    if _pids:
                        _pm = {p["product_id"]: p["pn"] for p in _db.fetch(
                            "products", "product_id,pn",
                            "product_id=in.({})".format(",".join(
                                f'"{i}"' for i in _pids)), limit=2000)}
                    for b in _bl:
                        _p = _pm.get(b["product_id"])
                        if _p:
                            _pn_map.setdefault(
                                b["material_id"], []).append(_p)
                except Exception:
                    pass

                def _pn_label(r):
                    _l = sorted(set(_pn_map.get(r["material_id"], [])))
                    if not _l and r.get("applied_pn"):
                        return r["applied_pn"]        # BOM 미연결 → 참고 품번
                    if len(_l) > 3:
                        return ", ".join(_l[:3]) + f" 외 {len(_l) - 3}"
                    return ", ".join(_l)

                _inv_rows.sort(key=lambda r: (
                    r["material_id"] not in _pn_map,
                    str(r.get("material_type") or "ZZZ"),
                    str(r.get("raw_name") or "")))
                if _inv_rows:
                    import csv as _csv
                    import io as _io
                    _buf = _io.StringIO()
                    _wcsv = _csv.writer(_buf)
                    _wcsv.writerow(["자재ID", "자재명", "재질", "규격",
                                    "단위", "공급사", "사용 품번",
                                    "장부수량", "실사수량", "차이/비고"])
                    for r in _inv_rows:
                        _wcsv.writerow([
                            r["material_id"], r.get("raw_name") or "",
                            r.get("material_type") or "",
                            r.get("spec") or "", r.get("unit") or "EA",
                            r.get("main_supplier") or "",
                            _pn_label(r),
                            f"{float(r.get('stock_qty') or 0):g}",
                            "", ""])
                    _n_bom = sum(1 for r in _inv_rows
                                 if r["material_id"] in _pn_map)
                    st.download_button(
                        "소재 실사 시트 (CSV · 전체 {}종 · BOM 연결 {}종)"
                        .format(len(_inv_rows), _n_bom),
                        # BOM(utf-8-sig) — 엑셀에서 한글이 깨지지 않게
                        _buf.getvalue().encode("utf-8-sig"),
                        file_name="소재실사시트_{:%Y%m%d}.csv".format(
                            _ft_date.today()),
                        mime="text/csv", key="ft_inv_dl")
                else:
                    st.info("활성 자재가 없습니다.")
            except Exception as e:
                st.error(f"실사 시트 생성 실패: {e}")

        # ── 품번 선택 ──
        _ft_q = st.text_input("품번 · 품명 검색", key="ft_q",
                              placeholder="예: 4PDVN, MRG6, GLAND NUT")
        try:
            _ft_flt = ["archived_at=is.null", "order=pn"]
            if _ft_q.strip():
                _qq = _ft_q.strip()
                _ft_flt.append(f"or=(pn.ilike.*{_qq}*,"
                               f"item_name.ilike.*{_qq}*)")
            _ft_prods = _db.fetch("products",
                                  "product_id,pn,item_name,customer",
                                  "&".join(_ft_flt), limit=300)
        except Exception as e:
            st.error(f"제품 조회 실패: {e}"); _ft_prods = []

        if not _ft_prods:
            st.info("검색 결과가 없습니다 — 품번 일부만 입력해 보세요.")
            _ft_p = None
        else:
            if len(_ft_prods) > 200:
                st.caption(f"{len(_ft_prods)}건 — 검색어로 좁히면 찾기 쉽습니다.")
            _ft_p = st.selectbox(
                "품번", _ft_prods,
                format_func=lambda r: " · ".join(
                    x for x in (r["pn"], r.get("item_name"),
                                r.get("customer") or "-") if x),
                key="ft_pick")

        if _ft_p:
            _pid = _ft_p["product_id"]
            _pn = _ft_p["pn"]
            _unit = "EA"   # products 에 제품 단위 컬럼 없음 — 전 품목 EA

            # ── 현황 집계 ──
            def _ft_load():
                out = {"pend": 0.0, "so_n": 0, "stock": 0.0, "wip": 0.0,
                       "lots": [], "bom": [], "txns": []}
                try:
                    _lis = _db.fetch("sales_order_items",
                        "soi_id,so_id,pending_qty,due_date",
                        f"product_id=eq.{_pid}&pending_qty=gt.0", limit=200)
                    _sids = {l["so_id"] for l in _lis}
                    _dead = set()
                    if _sids:
                        _dead = {s["so_id"] for s in _db.fetch(
                            "sales_orders", "so_id,status",
                            "so_id=in.({})".format(
                                ",".join(map(str, _sids))), limit=300)
                            if (s.get("status") or "") in
                            ("CANCELLED", "CANCELED")}
                    _lis = [l for l in _lis if l["so_id"] not in _dead]
                    out["pend"] = sum(float(l.get("pending_qty") or 0)
                                      for l in _lis)
                    out["so_n"] = len(_lis)
                except Exception:
                    pass
                try:
                    _ps = _db.fetch_one("product_stock_v",
                                        f"product_id=eq.{_pid}",
                                        "current_stock")
                    out["stock"] = float((_ps or {}).get("current_stock") or 0)
                except Exception:
                    pass
                try:
                    out["lots"] = [l for l in _db.fetch(
                        "product_lot_stock_v",
                        "lot_number,produced_qty,adjust_qty,issued_qty,"
                        "remain_qty,first_output_date,material_lot",
                        f"product_id=eq.{_pid}&order=first_output_date",
                        limit=100) if float(l.get("remain_qty") or 0) != 0]
                except Exception:
                    pass
                try:
                    out["wip"] = sum(
                        max(float(t.get("input_qty") or 0)
                            - float(t.get("output_qty") or 0), 0)
                        for t in _db.fetch("wo_tracking",
                            "wo_number,input_qty,output_qty,status",
                            f"product_id=eq.{_pid}&status=neq.CLOSED",
                            limit=100))
                except Exception:
                    pass
                try:
                    _bl = _db.fetch("bom",
                        "bom_id,material_id,raw_material_name,qty_per_pc,"
                        "shared_factor,process_type",
                        f"product_id=eq.{_pid}&material_id=not.is.null",
                        limit=50)
                    _mids = [b["material_id"] for b in _bl]
                    _mm = {}
                    if _mids:
                        _mm = {m["material_id"]: m for m in _db.fetch(
                            "material_stock",
                            "material_id,raw_name,material_type,spec,unit,"
                            "current_stock,main_supplier",
                            "material_id=in.({})".format(
                                ",".join(_mids)), limit=100)}
                    for b in _bl:
                        b["_m"] = _mm.get(b["material_id"], {})
                    out["bom"] = _bl
                except Exception:
                    pass
                try:
                    out["txns"] = _db.fetch("inventory_transactions",
                        "txn_id,txn_type,qty,unit,lot_number,txn_date,remark,"
                        "material_id,product_id",
                        f"product_id=eq.{_pid}&order=txn_id.desc", limit=15)
                except Exception:
                    pass
                return out

            _ft = _ft_load()
            _short = max(_ft["pend"] - _ft["stock"] - _ft["wip"], 0)
            st.markdown(
                '<div class="kpi-row">'
                '<div class="kpi {c1}"><div class="k">미납 수주</div>'
                '<div class="v">{p:,.0f}</div><div class="s">{n}개 라인</div></div>'
                '<div class="kpi {c2}"><div class="k">완성 재고</div>'
                '<div class="v">{s:,.0f}</div><div class="s">LOT {l}개</div></div>'
                '<div class="kpi {c3}"><div class="k">생산중</div>'
                '<div class="v">{w:,.0f}</div><div class="s">진행 작업지시</div></div>'
                '<div class="kpi {c4}"><div class="k">부족</div>'
                '<div class="v">{d:,.0f}</div>'
                '<div class="s">미납 − 완성 − 생산중</div></div>'
                '</div>'.format(
                    p=_ft["pend"], n=_ft["so_n"], s=_ft["stock"],
                    l=len(_ft["lots"]), w=_ft["wip"], d=_short,
                    c1="warn" if _ft["pend"] else "zero",
                    c2="good" if _ft["stock"] else "zero",
                    c3="" if _ft["wip"] else "zero",
                    c4="danger" if _short else "good"),
                unsafe_allow_html=True)

            st.divider()

            # ══ 1) BOM & 소재 ══
            st.markdown("##### 1. 소재 (BOM)")
            if not _ft["bom"]:
                st.warning(
                    "이 품번에 BOM 이 없습니다 — 소재를 연결해야 필요량 "
                    "산출과 투입 자동 매핑이 동작합니다. 아래에서 등록하세요.")
            else:
                _brows = []
                for b in _ft["bom"]:
                    _m = b["_m"]
                    _per = (float(b.get("qty_per_pc") or 1)
                            / max(float(b.get("shared_factor") or 1), 1))
                    _need = _ft["pend"] * _per
                    _have = float(_m.get("current_stock") or 0)
                    _brows.append({
                        "자재": _m.get("raw_name") or b["material_id"],
                        "재질": _m.get("material_type") or "-",
                        "규격": _m.get("spec") or "-",
                        "공급사": _m.get("main_supplier") or "-",
                        "1개당": _per,
                        "필요량": _need,
                        "현재고": _have,
                        "부족": max(_need - _have, 0),
                    })
                _bdf = pd.DataFrame(_brows)
                st.dataframe(
                    _bdf.style.format({
                        "1개당": "{:,.3f}", "필요량": "{:,.0f}",
                        "현재고": "{:,.0f}", "부족": "{:,.0f}"}).map(
                        lambda v: ("color:#f04452;font-weight:600"
                                   if isinstance(v, (int, float)) and v > 0
                                   else "color:#b0b8c1"), subset=["부족"]),
                    use_container_width=True, hide_index=True)

            with st.expander("BOM 소재 추가 / 수정", expanded=not _ft["bom"]):
                _mq = st.text_input("자재 검색", key="ft_mq",
                                    placeholder="예: S304, Ø45, 명진")
                _mcand = []
                if _mq.strip():
                    try:
                        _s = _mq.strip()
                        _mcand = _db.fetch("materials",
                            "material_id,raw_name,material_type,spec,"
                            "main_supplier,procurement_type",
                            f"archived_at=is.null&or=(raw_name.ilike.*{_s}*,"
                            f"spec.ilike.*{_s}*,material_type.ilike.*{_s}*,"
                            f"main_supplier.ilike.*{_s}*)&order=raw_name",
                            limit=40)
                    except Exception as e:
                        st.error(f"자재 조회 실패: {e}")
                if _mcand:
                    _mpick = st.selectbox(
                        "자재", _mcand,
                        format_func=lambda m: "{} · {} · {}".format(
                            m["raw_name"], m.get("spec") or "-",
                            m.get("main_supplier") or "공급사 미정"),
                        key="ft_mpick")
                    bc1, bc2, bc3 = st.columns([1, 1, 1])
                    _qpp = bc1.number_input("제품 1개당 소요", 0.0, 100.0,
                                            1.0, 0.1, key="ft_qpp")
                    _shf = bc2.number_input("분할 계수 (1소재 n제품)", 1, 50,
                                            1, 1, key="ft_shf",
                                            help="소재 1개로 제품 n개를 뽑으면 n")
                    _ptp = bc3.text_input("공정 구분 (선택)", key="ft_ptp",
                                          placeholder="예: 선삭, 밀링")
                    if st.button("BOM 저장", type="primary", key="ft_bom_save"):
                        try:
                            _ex = _db.fetch_one("bom",
                                f"product_id=eq.{_pid}&material_id=eq."
                                f"{_mpick['material_id']}", "bom_id")
                            _pay = {"qty_per_pc": float(_qpp),
                                    "shared_factor": int(_shf),
                                    "raw_material_name": _mpick["raw_name"],
                                    "process_type": _ptp or None,
                                    "source": "품번별 맞추기",
                                    "verification_status": "CONFIRMED"}
                            if _ex:
                                _db.update("bom", f"bom_id=eq.{_ex['bom_id']}",
                                           _pay)
                                st.success("BOM 수정 완료")
                            else:
                                _db.insert("bom", [{
                                    **_pay, "product_id": _pid,
                                    "material_id": _mpick["material_id"]}])
                                st.success("BOM 등록 완료")
                            st.rerun()
                        except Exception as e:
                            st.error(f"저장 실패: {e}")
                elif _mq.strip():
                    st.caption("일치하는 자재가 없습니다 — 자재 편집에서 "
                               "먼저 등록하세요.")

            st.divider()

            # ══ 2) 소재 즉시 입고 (발주 없이) ══
            st.markdown("##### 2. 소재 입고 (발주서 없이)")
            st.caption(
                "실물이 들어온 시점에 바로 기록합니다. 식별 번호가 부여되어 "
                "투입·완성·출고까지 LOT 이 이어집니다.")
            _rcv_opts = [{"material_id": b["material_id"],
                          "raw_name": (b["_m"].get("raw_name")
                                       or b["material_id"]),
                          "spec": b["_m"].get("spec"),
                          "material_type": b["_m"].get("material_type"),
                          "unit": b["_m"].get("unit") or "EA",
                          "main_supplier": b["_m"].get("main_supplier")}
                         for b in _ft["bom"]]
            if not _rcv_opts:
                st.info("BOM 소재를 먼저 등록하면 여기서 바로 입고할 수 "
                        "있습니다. (발주/입고 → 직접 입고 도 사용 가능)")
            else:
                rc1, rc2, rc3 = st.columns([2, 1, 1])
                _rpick = rc1.selectbox(
                    "입고 자재", _rcv_opts,
                    format_func=lambda m: "{} · {}".format(
                        m["raw_name"], m.get("spec") or "-"),
                    key="ft_rpick")
                _rqty = rc2.number_input("수량", 0.0, 1_000_000.0, 0.0, 10.0,
                                         key="ft_rqty")
                _rdate = rc3.date_input("입고일", _ft_date.today(),
                                        key="ft_rdate")
                rc4, rc5 = st.columns([2, 1])
                _rsrc = rc4.text_input(
                    "공급처", key="ft_rsrc",
                    value=_rpick.get("main_supplier") or "",
                    placeholder="예: (주)명진메탈, 미진정밀 사급")
                _rfree = rc5.checkbox("사급 (무상 지급)", key="ft_rfree")
                if st.button(f"입고 등록 ({_rqty:,.0f})", type="primary",
                             disabled=_rqty <= 0, key="ft_rcv_go"):
                    _w = (w_lot_next(1) or [None])[0]
                    try:
                        _db.insert("inventory_transactions", [{
                            "material_id": _rpick["material_id"],
                            "txn_type": "RECEIPT",
                            "qty": float(_rqty),
                            "unit": _rpick.get("unit") or "EA",
                            "lot_number": _w,
                            "ref_table": None, "ref_id": None,
                            "txn_date": _rdate.isoformat(),
                            "remark": "발주 없이 직접 입고 · {}{} · {}".format(
                                _pn, " · 사급" if _rfree else "",
                                _rsrc or "출처 미기재"),
                            "created_by": current_user_name(),
                        }])
                        st.session_state["ft_label"] = {
                            "w_lot": _w or "(식별 번호 없음)", "pn": _pn,
                            "material_name": _rpick.get("material_type")
                            or _rpick["raw_name"],
                            "spec": _rpick.get("spec") or "-",
                            "qty": float(_rqty),
                            "unit": _rpick.get("unit") or "EA",
                            "po_number": "직접 입고",
                            "vendor": _rsrc or "-",
                            "date": _rdate.isoformat()}
                        st.success(
                            "입고 완료 — {} {:,.0f}{}".format(
                                _rpick["raw_name"], _rqty,
                                f" · 소재 LOT {_w}" if _w else
                                " (식별 번호 카운터 미설정)"))
                        st.rerun()
                    except Exception as e:
                        st.error(f"입고 실패: {e}")
                if st.session_state.get("ft_label"):
                    try:
                        from utils.label_generator import receipt_labels
                        st.download_button(
                            "방금 입고 라벨 내려받기",
                            receipt_labels([st.session_state["ft_label"]]),
                            file_name="소재입고라벨_{}.html".format(
                                st.session_state["ft_label"]["w_lot"]),
                            mime="text/html", key="ft_label_dl")
                    except Exception:
                        pass

            st.divider()

            # ══ 3) 완성재고 맞추기 ══
            st.markdown("##### 3. 완성 재고 맞추기 (출하 시점 실사)")
            st.caption(
                "장부 재고와 실제 창고 수량이 다를 때 실사 수량을 넣으면 "
                "차이만큼 조정 기록이 남습니다. 조정분에도 LOT 이 붙어 "
                "출고 선입선출에 그대로 쓰입니다.")
            if _ft["lots"]:
                st.dataframe(
                    pd.DataFrame([{
                        "완성 LOT": l["lot_number"],
                        "소재 LOT": l.get("material_lot") or "-",
                        "생산": float(l.get("produced_qty") or 0),
                        "조정": float(l.get("adjust_qty") or 0),
                        "출고": float(l.get("issued_qty") or 0),
                        "잔여": float(l.get("remain_qty") or 0),
                        "완성일": l.get("first_output_date") or "-",
                    } for l in _ft["lots"]]),
                    use_container_width=True, hide_index=True)

            ac1, ac2, ac3 = st.columns([1, 1, 1])
            ac1.metric("장부 완성재고", f"{_ft['stock']:,.0f}")
            # 장부가 음수인 품목도 열리도록 초기값은 0 미만 방지
            # (음수 장부 = 미기록 생산분 — 실사값 입력으로 바로잡는 대상)
            _real = ac2.number_input("실사 수량", 0.0, 1_000_000.0,
                                     max(0.0, float(_ft["stock"])), 1.0,
                                     key="ft_real")
            _diff = float(_real) - _ft["stock"]
            ac3.metric("조정될 차이", f"{_diff:+,.0f}",
                       delta=None if _diff == 0 else
                       ("과잉 — 재고를 늘립니다" if _diff > 0
                        else "부족 — 재고를 줄입니다"),
                       delta_color="off")
            _amemo = st.text_input(
                "조정 사유", key="ft_amemo",
                placeholder="예: 8/1 창고 실사, 미기록 완성분 반영")
            if st.button("완성재고 조정", type="primary",
                         disabled=(_diff == 0), key="ft_adj_go"):
                if not _amemo.strip():
                    st.error("조정 사유는 반드시 남겨야 합니다 — 나중에 "
                             "왜 숫자가 바뀌었는지 추적할 수 없습니다.")
                else:
                    _alot = "ADJ-{:%Y%m%d}".format(_ft_date.today())
                    try:
                        _db.insert("inventory_transactions", [{
                            "material_id": None,
                            "product_id": _pid,
                            "txn_type": "ADJUSTMENT",
                            "qty": float(_diff),
                            "unit": _unit,
                            "lot_number": _alot if _diff > 0 else None,
                            "ref_table": None, "ref_id": None,
                            "txn_date": _ft_date.today().isoformat(),
                            "remark": f"실사 조정 · {_amemo.strip()}",
                            "created_by": current_user_name(),
                        }])
                        st.success(
                            "조정 완료 — {:+,.0f} (완성재고 {:,.0f} → "
                            "{:,.0f})".format(_diff, _ft["stock"], _real))
                        st.rerun()
                    except Exception as e:
                        st.error(f"조정 실패: {e}")
            if _diff < 0 and _ft["lots"]:
                st.caption(
                    "감소 조정은 LOT 없이 기록되어 전체 재고에서만 "
                    "빠집니다. 특정 LOT 을 줄여야 하면 사유에 LOT 번호를 "
                    "적어 두세요.")

            # ══ 4) 최근 원장 ══
            with st.expander("이 품번의 최근 재고 원장 15건"):
                if _ft["txns"]:
                    st.dataframe(pd.DataFrame([{
                        "일자": t.get("txn_date"),
                        "유형": t.get("txn_type"),
                        "수량": float(t.get("qty") or 0),
                        "LOT": t.get("lot_number") or "-",
                        "비고": t.get("remark") or "-",
                    } for t in _ft["txns"]]),
                        use_container_width=True, hide_index=True)
                else:
                    st.caption("아직 원장 기록이 없습니다.")

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
                fname = st.text_input("품명",
                                      placeholder="GLAND NUT, FLANGE",
                                      key="prod_f_name")
            with pfc3:
                fcust = st.text_input("고객사", placeholder="미진, 명진, 두산",
                                      key="prod_f_cust")
            with pfc4:
                fgroup = st.text_input("제품군", placeholder="YPBV, LJF, ABV",
                                       key="prod_f_group")

            pfc5, pfc6, pfc7, pfc8 = st.columns([1, 2, 2, 1])
            with pfc5:
                fstatus = st.selectbox("상태",
                    ["활성", "휴면", "전체"], key="prod_f_status")
            with pfc6:
                fmat = st.text_input("재질/규격/자재명",
                    placeholder="STS304, 환봉, SCM440",
                    key="prod_f_mat")
            with pfc7:
                fproc = st.selectbox("조달",
                    ["전체", "도급", "사급"], key="prod_f_proc")
            with pfc8:
                plim = st.number_input("행수", 20, 1000, 100, 20,
                                       key="prod_lim")

        # ── 쿼리 빌드 ──
        parts = ["order=pn.asc"]
        if fpn:
            parts.append(f"pn=ilike.*{fpn.strip()}*")
        if fname:
            parts.append(f"item_name=ilike.*{fname.strip()}*")
        if fcust:
            parts.append(f"customer=ilike.*{fcust.strip()}*")
        if fgroup:
            # 제품군 = sub_class (032: product_group 삭제, 라벨만 교체)
            parts.append(f"sub_class=ilike.*{fgroup.strip()}*")
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
                "product_id,pn,item_name,customer,sub_class,material,"
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
            show_cols = ["product_id","pn","item_name","customer","sub_class",
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
                    "item_name": st.column_config.TextColumn("품명",
                        width="medium",
                        help="유사 품번 착오 방지 — 출고 리스트에 "
                             "품번 옆에 표시됨"),
                    "customer": st.column_config.TextColumn("고객사",
                        width="medium"),
                    "sub_class": st.column_config.TextColumn("제품군",
                        width="small",
                        help="구 하위분류 — YPBV, LJF, ABV-FL 등 "
                             "제품 계열"),
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
                editable_keys = ("pn", "item_name", "customer", "sub_class",
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
                new_iname = st.text_input("품명",
                    placeholder="예: 40A BELLOWS VALVE GLAND NUT")

            npc4, npc5, npc6 = st.columns(3)
            with npc4:
                new_subclass = st.text_input("제품군",
                    placeholder="예: YPBV, LJF, ABV")
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
                                "item_name": new_iname.strip() or None,
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

        # ── 중복 자재 병합 (2026-07-31) ──
        st.divider()
        st.markdown("##### 중복 자재 병합")
        st.caption(
            "같은 소재가 표기만 달라 두 번 등록된 경우 — 예: "
            "`S304 Ø45*16` 과 `STS304환봉 45￠16ℓ`. BOM·재고 원장·매입 "
            "매핑을 남길 자재로 옮기고, 흡수된 쪽은 휴면 처리합니다.")

        def _mkey(m):
            """규격·재질 정규화 키 — 표기 차이를 흡수 (φØ￠Φ, *xL, 316L→316).

            형상은 흡수하지 않는다: 육각(H)과 환봉(Ø)은 다른 소재
            (2026-08-04 사용자 확정) — 자재명에서 형상을 읽어 키에 포함."""
            import re as _re
            s = _re.sub(r"[ *xXL×ℓ]", "",
                        _re.sub(r"[φØ￠Φ]", "D", (m.get("spec") or "").upper()))
            t = _re.sub(r"(L|H)$", "",
                        _re.sub(r"^STS", "SUS", (m.get("material_type")
                                                 or "").upper()))
            _nm = m.get("raw_name") or ""
            shape = "HEX" if _re.search(r"\bH\d|육각", _nm) else "RND"
            return (s, t, shape) if s and t else None

        if st.button("중복 후보 찾기", key="mg_scan"):
            st.session_state["mg_scan_on"] = True
        if st.session_state.get("mg_scan_on"):
            try:
                _all_m = _db.fetch("materials",
                    "material_id,raw_name,material_type,spec,stock_qty,"
                    "main_supplier,procurement_type",
                    "archived_at=is.null&order=material_id", limit=1000)
            except Exception as e:
                st.error(f"자재 조회 실패: {e}"); _all_m = []
            _grp = {}
            for m in _all_m:
                k = _mkey(m)
                if k:
                    _grp.setdefault(k, []).append(m)
            _dups = {k: v for k, v in _grp.items() if len(v) > 1}
            if not _dups:
                st.success("동일 규격·재질의 중복 자재가 없습니다.")
            else:
                # 참조 건수 — 어느 쪽을 남길지 판단 근거
                _ids = [m["material_id"] for v in _dups.values() for m in v]
                _bcnt, _tcnt = {}, {}
                try:
                    for b in _db.fetch("bom", "material_id",
                            "material_id=in.({})".format(",".join(_ids)),
                            limit=2000):
                        _bcnt[b["material_id"]] = _bcnt.get(
                            b["material_id"], 0) + 1
                    for t in _db.fetch("inventory_transactions", "material_id",
                            "material_id=in.({})".format(",".join(_ids)),
                            limit=2000):
                        _tcnt[t["material_id"]] = _tcnt.get(
                            t["material_id"], 0) + 1
                except Exception:
                    pass
                st.caption(f"중복 후보 {len(_dups)}쌍 — 한 쌍씩 확인하고 "
                           "병합하세요.")
                for _k, _v in sorted(_dups.items()):
                    _lab = "{} · {} · {}".format(
                        _k[1], _k[0], "육각" if _k[2] == "HEX" else "환봉")
                    with st.expander("{}  ({}건)".format(_lab, len(_v))):
                        st.dataframe(pd.DataFrame([{
                            "ID": m["material_id"], "자재명": m["raw_name"],
                            "재질": m.get("material_type") or "-",
                            "규격": m.get("spec") or "-",
                            "공급사": m.get("main_supplier") or "-",
                            "재고": float(m.get("stock_qty") or 0),
                            "BOM": _bcnt.get(m["material_id"], 0),
                            "원장": _tcnt.get(m["material_id"], 0),
                        } for m in _v]), use_container_width=True,
                            hide_index=True)
                        _kk = "_".join(_k)
                        _keep = st.selectbox(
                            "남길 자재", _v, key=f"mg_keep_{_kk}",
                            format_func=lambda m: "{} ({})".format(
                                m["raw_name"], m["material_id"]))
                        _drop = [m for m in _v
                                 if m["material_id"] != _keep["material_id"]]
                        st.caption("흡수될 자재: " + ", ".join(
                            "{} ({})".format(m["raw_name"], m["material_id"])
                            for m in _drop))
                        if st.button("병합 실행", type="primary",
                                     key=f"mg_go_{_kk}"):
                            from datetime import date as _mg_date
                            _kid = _keep["material_id"]
                            _today = _mg_date.today().isoformat()
                            _nbom = 0
                            try:
                                for m in _drop:
                                    _did = m["material_id"]
                                    # BOM — 남길 자재에 이미 있는 제품이면
                                    # 중복이 되므로 옮기지 않고 지운다
                                    _keep_pids = {b["product_id"] for b in
                                        _db.fetch("bom", "product_id",
                                            f"material_id=eq.{_kid}",
                                            limit=500)}
                                    for b in _db.fetch("bom",
                                            "bom_id,product_id",
                                            f"material_id=eq.{_did}",
                                            limit=500):
                                        if b["product_id"] in _keep_pids:
                                            _db.delete(
                                                "bom",
                                                f"bom_id=eq.{b['bom_id']}")
                                        else:
                                            _db.update(
                                                "bom",
                                                f"bom_id=eq.{b['bom_id']}",
                                                {"material_id": _kid,
                                                 "raw_material_name":
                                                 _keep["raw_name"]})
                                            _nbom += 1
                                    # 원장·발주라인·매입매핑을 남길 자재로
                                    _db.update("inventory_transactions",
                                               f"material_id=eq.{_did}",
                                               {"material_id": _kid})
                                    _db.update("purchase_order_items",
                                               f"material_id=eq.{_did}",
                                               {"material_id": _kid})
                                    _db.update("purchase_ledger",
                                               f"matched_material_id=eq.{_did}",
                                               {"matched_material_id": _kid})
                                    # 재고 baseline 합산 후 원본은 휴면
                                    _ds = float(m.get("stock_qty") or 0)
                                    if _ds:
                                        _ks = float(_keep.get("stock_qty") or 0)
                                        _db.update(
                                            "materials",
                                            f"material_id=eq.{_kid}",
                                            {"stock_qty": _ks + _ds})
                                        _keep["stock_qty"] = _ks + _ds
                                    _db.update(
                                        "materials", f"material_id=eq.{_did}",
                                        {"archived_at": _today,
                                         "stock_qty": 0, "in_use": False,
                                         "remark": f"{_kid} 로 병합 ({_today})"})
                                st.success(
                                    "병합 완료 — {} 로 통합 · BOM {}건 이동"
                                    .format(_kid, _nbom))
                                st.rerun()
                            except Exception as e:
                                st.error(f"병합 실패: {e}")


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
                # (a) products: pn / product_id / 품명 / customer 매칭 (archived 포함)
                try:
                    pmatch = fetch("products", "product_id,pn,sub_class,item_name,customer,archived_at",
                        f"or=(pn.ilike.*{qq}*,product_id.ilike.*{qq}*,"
                        f"item_name.ilike.*{qq}*,customer.ilike.*{qq}*)"
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
                    prows = fetch("products", "product_id,pn,sub_class",
                                  f"product_id=in.({pids_q})", limit=1500)
                except Exception: prows = []
                pmap = {p['product_id']: p for p in prows}
                for b in brows:
                    p = pmap.get(b['product_id'], {})
                    b['_pn'] = p.get('pn', '')
                    b['_group'] = p.get('sub_class', '')

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
                            f"or=(pn.ilike.*{qq}*,item_name.ilike.*{qq}*,"
                            f"customer.ilike.*{qq}*)"
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

    # ─── Tab: 계정 관리 (2026-08-05) ───
    with tab_acct:
        st.markdown("**로그인 계정 추가·역할 변경·비밀번호 초기화**")
        st.caption("비밀번호 규칙: " + _auth.PW_RULES + " — 계정은 "
                   "app_settings 에 저장되며 배포 없이 즉시 적용됩니다.")

        _ac_users = _auth.load_users(_db)
        if not _ac_users:
            st.error("계정 정보를 불러오지 못했습니다.")
        else:
            _ROLE_KO = {"admin": "관리자", "worker": "작업자"}
            _ROLE_EN = {v: k for k, v in _ROLE_KO.items()}
            _admins = [u for u, v in _ac_users.items()
                       if v.get("role") == "admin"]
            st.dataframe(pd.DataFrame([{
                "아이디": u, "이름": v.get("name") or u,
                "역할": _ROLE_KO.get(v.get("role"), v.get("role")),
            } for u, v in sorted(_ac_users.items())]),
                use_container_width=True, hide_index=True)

            ac_new, ac_edit = st.columns(2)

            # ── 신규 계정 ──
            with ac_new:
                st.markdown("##### 신규 계정")
                with st.form("acct_new", clear_on_submit=True):
                    _an_id = st.text_input("아이디 (로그인용)")
                    _an_name = st.text_input(
                        "이름 (기록에 남는 실명)",
                        help="입고·조정·출고 이력의 처리자로 표시됩니다")
                    _an_role = st.radio("역할", ["작업자", "관리자"],
                                        horizontal=True)
                    _an_pw = st.text_input("초기 비밀번호", type="password")
                    _an_go = st.form_submit_button("계정 추가",
                                                   type="primary",
                                                   use_container_width=True)
                if _an_go:
                    _an_id = (_an_id or "").strip()
                    _bad = (_auth.check_username(_an_id)
                            or _auth.check_password(_an_pw, _an_id))
                    if _bad:
                        st.error(_bad)
                    elif _an_id in _ac_users:
                        st.error(f"이미 있는 아이디입니다: {_an_id}")
                    else:
                        _ac_users[_an_id] = {
                            "name": (_an_name or "").strip() or _an_id,
                            "role": _ROLE_EN[_an_role],
                            "pw": _auth.hash_pw(_an_pw)}
                        if _auth.save_users(_db, _ac_users):
                            st.success(f"추가 완료 — {_an_id} "
                                       f"({_an_role}). 초기 비밀번호를 "
                                       "본인에게 전달하고, 첫 로그인 후 "
                                       "변경하도록 안내하세요.")
                            st.rerun()
                        else:
                            st.error("저장 실패 — 다시 시도하세요.")

            # ── 기존 계정 관리 ──
            with ac_edit:
                st.markdown("##### 기존 계정")
                _ae_id = st.selectbox(
                    "대상 계정", sorted(_ac_users),
                    format_func=lambda u: "{} · {} ({})".format(
                        u, _ac_users[u].get("name") or u,
                        _ROLE_KO.get(_ac_users[u].get("role"), "-")),
                    key="acct_pick")
                _ae = _ac_users[_ae_id]
                _is_last_admin = (_ae.get("role") == "admin"
                                  and len(_admins) <= 1)
                _is_me = _ae_id == current_user().get("username")

                with st.form("acct_edit"):
                    _ae_role = st.radio(
                        "역할", ["작업자", "관리자"], horizontal=True,
                        index=1 if _ae.get("role") == "admin" else 0)
                    _ae_pw = st.text_input(
                        "비밀번호 초기화 (바꿀 때만 입력)",
                        type="password")
                    _ae_go = st.form_submit_button("저장",
                                                   use_container_width=True)
                if _ae_go:
                    _new_role = _ROLE_EN[_ae_role]
                    if (_is_last_admin and _new_role != "admin"):
                        st.error("마지막 관리자는 작업자로 바꿀 수 "
                                 "없습니다 — 다른 관리자를 먼저 만드세요.")
                    else:
                        _bad = (_auth.check_password(_ae_pw, _ae_id)
                                if _ae_pw else None)
                        if _bad:
                            st.error(f"비밀번호: {_bad}")
                        else:
                            _ae["role"] = _new_role
                            if _ae_pw:
                                _ae["pw"] = _auth.hash_pw(_ae_pw)
                            if _auth.save_users(_db, _ac_users):
                                st.success("저장 완료"
                                           + (" — 새 비밀번호를 본인에게 "
                                              "전달하세요." if _ae_pw else ""))
                                st.rerun()
                            else:
                                st.error("저장 실패 — 다시 시도하세요.")

                if st.button("계정 삭제", key="acct_del",
                             disabled=_is_me or _is_last_admin,
                             use_container_width=True):
                    _ac_users.pop(_ae_id, None)
                    if _auth.save_users(_db, _ac_users):
                        st.success(f"삭제 완료 — {_ae_id}")
                        st.rerun()
                    else:
                        st.error("저장 실패 — 다시 시도하세요.")
                if _is_me:
                    st.caption("본인 계정은 삭제할 수 없습니다.")
                elif _is_last_admin:
                    st.caption("마지막 관리자 계정은 삭제할 수 없습니다.")

    # ─── Tab: 디자인 데이터 내보내기 ───
    with tab_dsn:
        st.markdown("**화면 설계용 실데이터 스냅샷**")
        st.caption(
            "클로드 디자인 등 외부 도구는 Supabase 에 직접 접근할 수 없습니다. "
            "지금 DB 에 들어있는 실제 값을 JSON 한 장으로 받아서 첨부하세요. "
            "단가·금액 항목은 자동으로 제외됩니다.")

        # 단가/금액 계열 컬럼은 외부 도구로 나가지 않도록 제거
        _PRICE_HINT = ("price", "amount", "cost", "margin", "vat",
                       "단가", "금액", "원가")

        def _dsn_clean(rows):
            out = []
            for r in (rows or []):
                out.append({k: v for k, v in r.items()
                            if not any(h in k.lower() for h in _PRICE_HINT)})
            return out

        # (라벨, 테이블/뷰, 정렬, 건수)
        _DSN_SRC = [
            ("제품", "products", "order=pn", 60),
            ("자재", "materials", "order=material_id", 60),
            ("BOM", "bom", "", 80),
            ("수주", "sales_orders", "order=order_date.desc", 40),
            ("수주 라인", "sales_order_items", "", 120),
            ("납품 스케줄", "so_delivery_schedule", "order=due_date", 200),
            ("스케줄 요약", "so_schedule_summary_v", "", 120),
            ("소재 재고", "material_stock", "", 60),
            ("완성 재고", "product_stock_v", "", 60),
            ("완성 LOT 재고", "product_lot_stock_v", "", 60),
            ("작업지시", "wo_tracking", "order=wo_id.desc", 40),
            ("발주", "purchase_orders", "order=po_date.desc", 30),
            ("발주 라인", "purchase_order_items", "", 60),
            ("재고 원장", "inventory_transactions", "order=txn_id.desc", 120),
        ]

        _dsn_n = st.columns(2)
        with _dsn_n[0]:
            _dsn_go = st.button("스냅샷 만들기", type="primary",
                                use_container_width=True)
        if _dsn_go:
            import json as _json
            from datetime import date as _dt_date
            snap = {
                "_meta": {
                    "생성일": str(_dt_date.today()),
                    "출처": "우성정밀 업무관리 시스템 — Supabase 운영 데이터",
                    "용도": "화면 디자인 참고용 실데이터. 단가·금액 제외.",
                    "업무 흐름": "수주 → 소재 → 생산 → 외주 → 완성 → 출고",
                    "메뉴": ["홈", "수주 관리", "생산 계획", "발주/입고",
                             "공정 관리", "출고 관리", "마스터 관리",
                             "원가 확인", "생산 보고"],
                    "디자인 토큰": {
                        "font": "Pretendard",
                        "primary": "#3182f6", "bg": "#f9fafb",
                        "card": "#ffffff", "line": "#eef1f4",
                        "ink": "#191f28", "dim": "#6b7684",
                        "warn": "#dd6b02", "danger": "#f04452",
                        "good": "#01a76b",
                        "규칙": "이모지 미사용. 상태는 색으로만 구분 — "
                                "문제=danger, 대기=warn, 완료=good, 진행=primary.",
                    },
                },
            }
            _bar = st.progress(0.0)
            _fail = []
            for _i, (_label, _tbl, _ord, _lim) in enumerate(_DSN_SRC):
                try:
                    _rows = _db.fetch(_tbl, "*", _ord, limit=_lim)
                    snap[_label] = _dsn_clean(_rows)
                except Exception as e:  # 뷰 미존재 등은 건너뜀
                    _fail.append(f"{_label}({type(e).__name__})")
                _bar.progress((_i + 1) / len(_DSN_SRC))
            _bar.empty()

            _txt = _json.dumps(snap, ensure_ascii=False, indent=1, default=str)
            _cnt = sum(len(v) for k, v in snap.items() if k != "_meta")
            st.success(f"{len(_DSN_SRC) - len(_fail)}개 영역 · {_cnt:,}행 · "
                       f"{len(_txt)/1024:,.0f}KB")
            if _fail:
                st.caption("건너뜀: " + ", ".join(_fail))
            st.download_button(
                "design-data.json 내려받기", _txt,
                file_name=f"design-data_{_dt_date.today():%Y%m%d}.json",
                mime="application/json", use_container_width=True)
            with st.expander("미리보기 (앞부분)"):
                st.code(_txt[:2000], language="json")


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
            "so_id,total_pending_qty,due_date,so_date",
            'status=not.in.("CANCELLED","CANCELED")', limit=500)
    except Exception:
        _so_kpi = []
    _sk_pend = sum(float(s.get("total_pending_qty") or 0) for s in _so_kpi)
    _sk_open = sum(1 for s in _so_kpi
                   if float(s.get("total_pending_qty") or 0) > 0)
    _sk_month = sum(1 for s in _so_kpi
                    if str(s.get("so_date") or "")[:7]
                    == _date.today().isoformat()[:7])
    # 납기 지연 = 납품 스케줄 기준 (간트와 동일 정의):
    # 지난 회차의 미납 잔량 + 회차 없는 라인의 지난 납기 잔량.
    # (수주 헤더의 협의 납기 기준으로 세면 캘린더와 숫자가 어긋난다
    #  — 2026-08-06 확인)
    _sk_alive = {s["so_id"] for s in _so_kpi}
    _sk_late_n, _sk_late_qty = 0, 0.0
    try:
        for _r in fetch("so_delivery_schedule",
                "so_id,qty,delivered_qty",
                f"due_date=lt.{_date.today().isoformat()}", limit=1000):
            if _r["so_id"] in _sk_alive and (
                    float(_r.get("qty") or 0)
                    - float(_r.get("delivered_qty") or 0)) > 0:
                _sk_late_n += 1
                _sk_late_qty += (float(_r.get("qty") or 0)
                                 - float(_r.get("delivered_qty") or 0))
        _sched_soi_all = {r["soi_id"] for r in fetch(
            "so_delivery_schedule", "soi_id", "", limit=2000)}
        for _r in fetch("sales_order_items",
                "so_id,soi_id,pending_qty",
                f"pending_qty=gt.0&due_date=lt.{_date.today().isoformat()}",
                limit=1000):
            if (_r["so_id"] in _sk_alive
                    and _r["soi_id"] not in _sched_soi_all):
                _sk_late_n += 1
                _sk_late_qty += float(_r.get("pending_qty") or 0)
    except Exception:
        pass
    sk1, sk2, sk3, sk4 = st.columns(4)
    sk1.metric("미납 수량", f"{_sk_pend:,.0f}")
    sk2.metric("진행 수주", f"{_sk_open:,}건")
    sk3.metric("납기 지연", f"{_sk_late_n:,}건",
               delta=f"-{_sk_late_qty:,.0f}" if _sk_late_qty else None,
               delta_color="inverse" if _sk_late_qty else "off",
               help="납품 스케줄 기준 — 지난 회차·지난 납기의 미납 잔량. "
                    "부분 납품도 잔량이 남으면 지연으로 셉니다. "
                    "상세는 납품 스케줄 탭의 지연 상세.")
    sk4.metric("이번 달 수주", f"{_sk_month:,}건")
    st.divider()

    tab_input, tab_list, tab_sched = st.tabs(
        ["새 수주 입력", "수주 목록", "납품 스케줄"])

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
                                    "created_by": current_user_name(),
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
                            f"alias_list.ilike.*{m_pn_q.strip()}*,"
                            f"item_name.ilike.*{m_pn_q.strip()}*)"
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
                        "status": "DRAFT", "created_by": current_user_name(),
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
                toss_table([{
                    "수주번호": s["so_number"], "거래처": s["customer"],
                    "수주일": s.get("so_date"), "납기": s.get("due_date"),
                    "품목수": s.get("item_count"),
                    "총수량": int(s.get("total_qty") or 0),
                    "납품": int(s.get("total_received_qty") or 0),
                    "미납": int(s.get("total_pending_qty") or 0),
                    "납품상태": status_ko(s.get("delivery_status")),
                    "총액 (원)": int(s.get("total_amount") or 0),
                    "매칭률": f"{s.get('match_rate_pct') or 0:.0f}%",
                    "상태": status_ko(s["status"]),
                } for s in sos],
                    badge_cols=("납품상태", "상태"),
                    num_cols=("품목수", "총수량", "납품", "미납",
                              "총액 (원)", "매칭률"),
                    strong_cols=("수주번호",),
                    scroll=len(sos) > 15)

                st.divider()
                st.markdown("##### 🔍 수주 상세")
                # 리스트에서 행 선택 → 상세 (스크롤 선택 대체)
                _so_ev = st.dataframe(
                    pd.DataFrame([{
                        "수주번호": s["so_number"],
                        "거래처": s["customer"],
                        "미납": int(s.get("total_pending_qty") or 0),
                        "총액 (원)": int(s.get("total_amount") or 0),
                        "상태": status_ko(s["status"]),
                    } for s in sos]),
                    hide_index=True, use_container_width=True,
                    on_select="rerun", selection_mode="single-row",
                    key="so_detail_list",
                    column_config={c: st.column_config.NumberColumn(
                        format="localized")
                        for c in ("미납", "총액 (원)")})
                _so_rows = (getattr(getattr(_so_ev, "selection", None),
                                    "rows", None) or [])
                if not _so_rows:
                    _so_rows = [0]
                    if len(sos) > 1:
                        st.caption("행을 체크하면 그 수주의 상세가 "
                                   "열립니다 — 지금은 첫 수주 표시 중.")
                so = sos[min(_so_rows[0], len(sos) - 1)]
                if so:
                    sitems = fetch("sales_order_items", "*",
                                   f"so_id=eq.{so['so_id']}&order=line_no", limit=200)
                    if sitems:
                        toss_table([{
                            "라인": i["line_no"],
                            "거래처 자재": i.get("customer_part_no"),
                            "우성 품번": i.get("canonical_pn") or "미매칭",
                            "수량": int(i.get("qty") or 0),
                            "납품": int(i.get("received_qty") or 0),
                            "미납": int(i.get("pending_qty") or 0),
                            "단가 (원)": int(i.get("unit_price") or 0),
                            "금액 (원)": int(i.get("amount") or 0),
                            "납기": i.get("due_date"),
                            "상태": status_ko(i.get("status")),
                        } for i in sitems],
                            badge_cols=("상태",),
                            num_cols=("수량", "납품", "미납",
                                      "단가 (원)", "금액 (원)"),
                            strong_cols=("우성 품번",))
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
                    st.caption("납기 입력·수정은 납품 스케줄 탭에서 "
                               "일괄 처리합니다.")
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
                                    "미납": 0, "총액": 0, "_ms": 0, "_mn": 0,
                                    "미납건": 0, "부분납건": 0, "완납건": 0})
                for s in sos:
                    a = agg[s["customer"]]
                    a["수주건수"] += 1
                    a["품목수"] += int(s.get("item_count") or 0)
                    a["총수량"] += int(s.get("total_qty") or 0)
                    a["납품"] += int(s.get("total_received_qty") or 0)
                    a["미납"] += int(s.get("total_pending_qty") or 0)
                    a["총액"] += int(s.get("total_amount") or 0)
                    # 수주 상태 분포 (delivery_status 기준)
                    _ds0 = s.get("delivery_status")
                    if _ds0 == "미납":
                        a["미납건"] += 1
                    elif _ds0 == "부분납":
                        a["부분납건"] += 1
                    elif _ds0 == "완납":
                        a["완납건"] += 1
                    if s.get("match_rate_pct") is not None:
                        a["_ms"] += s["match_rate_pct"]; a["_mn"] += 1

                rows = [{
                    "거래처": cust, "수주건수": a["수주건수"], "품목수": a["품목수"],
                    "상태 (미납/부분/완납)":
                        f"{a['미납건']} / {a['부분납건']} / {a['완납건']}",
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
                    import html as _h

                    def _due_html(due_raw, days_left):
                        """`08-14 (D-2)` 표기 — 지남·임박(7일)은 빨강"""
                        if not due_raw:
                            return '<span class="dim">-</span>'
                        txt = _h.escape(str(due_raw)[5:]
                                        if len(str(due_raw)) == 10
                                        else str(due_raw))
                        if days_left is None:
                            return txt
                        if days_left < 0:
                            return (f'<span class="late">{txt} '
                                    f"(D+{-days_left})</span>")
                        if days_left <= 7:
                            return (f'<span class="late">{txt} '
                                    f"(D-{days_left})</span>")
                        return f"{txt} (D-{days_left})"

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
                        rows.append({
                            "수주번호": so.get("so_number"),
                            "거래처": so.get("customer"),
                            "납기": _due_html(due_raw, days_left),
                            "거래처 자재": i.get("customer_part_no"),
                            "우성 품번": i.get("canonical_pn") or "미매칭",
                            "수량": int(i.get("qty") or 0),
                            "미납": int(i.get("pending_qty") or 0),
                            "상태": status_ko(i.get("status")),
                            "_late": (days_left is not None
                                      and days_left < 0),
                        })
                    toss_table(rows,
                        columns=("수주번호", "거래처", "납기",
                                 "거래처 자재", "우성 품번", "수량",
                                 "미납", "상태"),
                        badge_cols=("상태",),
                        num_cols=("수량", "미납"),
                        strong_cols=("우성 품번",),
                        raw_cols=("납기",),
                        hl_rows={n for n, r in enumerate(rows)
                                 if r["_late"]},
                        scroll=len(rows) > 15)
                else:
                    st.info("미납 품목 없음")
            else:
                st.info("결과 없음")

        # ── 뷰 5: 매칭 안된 품목 ──
        elif view_mode == "❌ 매칭 안된 품목":
            fq = ["order=so_date.desc"] + common_fq
            try: sos = fetch("sales_orders", "so_id,so_number,customer,so_date,status",
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
                        "수주 상태": status_ko(
                            so_map.get(i["so_id"], {}).get("status")),
                    } for i in sitems])
                    st.dataframe(status_style(df, cols=("수주 상태",)),
                                 use_container_width=True, hide_index=True)
                    st.caption("💡 거래처 자재코드 → 우성정밀 품번 매핑은 마스터 관리에서 추가 가능 (다음 push)")
                else:
                    st.success("✅ 모든 품목이 매칭되었습니다")
            else:
                st.info("결과 없음")

    # ════════ TAB 3: 납품 스케줄 (7b 회차 간트, 2026-07-31) ════════
    with tab_sched:
        st.caption(
            "품목별 납품 회차를 주차 그리드에 배치해 전체 납품 일정을 "
            "한 화면에서 봅니다. 회차는 자유롭게 추가·수정·삭제할 수 "
            "있고, 화면의 납기는 **가장 빠른 미완료 회차**로 표시됩니다.")

        # ── 1) 데이터 적재 ──
        try:
            _all_sc = fetch("so_delivery_schedule",
                "sched_id,so_id,soi_id,seq,due_date,qty,delivered_qty,note",
                "order=due_date.asc", limit=2000)
        except Exception as e:
            st.error(f"스케줄 조회 실패 (Migration 027 필요): {e}")
            _all_sc = []
        try:  # 미납이 남은 전 라인 — 계획률·미계획 물량 산출 기준
            _open_li = fetch("sales_order_items",
                "soi_id,so_id,canonical_pn,customer_part_no,qty,"
                "received_qty,pending_qty,due_date",
                "pending_qty=gt.0", limit=2000)
        except Exception:
            _open_li = []

        _so_ids = ({r["so_id"] for r in _all_sc}
                   | {l["so_id"] for l in _open_li}) or {0}
        _soi_more = ({r["soi_id"] for r in _all_sc}
                     - {l["soi_id"] for l in _open_li})
        try:
            _sc_som = {s["so_id"]: s for s in fetch("sales_orders",
                "so_id,so_number,customer,status",
                "so_id=in.({})".format(",".join(map(str, _so_ids))),
                limit=1000)}
        except Exception:
            _sc_som = {}
        _li_by_soi = {l["soi_id"]: l for l in _open_li}
        if _soi_more:  # 납품이 끝난 라인의 회차도 품번 표시가 필요
            try:
                for l in fetch("sales_order_items",
                        "soi_id,so_id,canonical_pn,customer_part_no,qty,"
                        "received_qty,pending_qty,due_date",
                        "soi_id=in.({})".format(
                            ",".join(map(str, _soi_more))), limit=1000):
                    _li_by_soi.setdefault(l["soi_id"], l)
            except Exception:
                pass

        _dead = {k for k, v in _sc_som.items()
                 if (v.get("status") or "") in ("CANCELLED", "CANCELED")}
        _today_s = _date.today()
        _wk0 = _today_s - _td(days=_today_s.weekday())
        _wk1, _wk2 = _wk0 + _td(days=7), _wk0 + _td(days=14)

        def _pn_of(_l):
            return ((_l or {}).get("canonical_pn")
                    or (_l or {}).get("customer_part_no") or "-")

        # ── 2) 회차 칩 목록 (분납 = 스케줄 행, 단발 = 스케줄 없는 라인) ──
        _sched_soi = {r["soi_id"] for r in _all_sc}
        _g = []
        for r in _all_sc:
            if r["so_id"] in _dead:
                continue
            _l = _li_by_soi.get(r["soi_id"], {})
            _q = float(r.get("qty") or 0)
            _dq = float(r.get("delivered_qty") or 0)
            _rem = _q - _dq
            _due = _date.fromisoformat(str(r["due_date"])[:10])
            _g.append({
                "품번": _pn_of(_l),
                "거래처": _sc_som.get(r["so_id"], {}).get("customer", "-"),
                "수주번호": _sc_som.get(r["so_id"], {}).get("so_number", "-"),
                "구분": "분납", "회차": int(r.get("seq") or 0),
                "납기": _due, "수량": _q, "완료": _dq,
                "잔량": max(_rem, 0.0),
                "상태": ("완료" if _rem <= 0 else
                        "지연" if _due < _today_s else "예정"),
            })
        for l in _open_li:
            # 납기 미협의 라인은 간트에 나타나지 않음 → 미계획 배너로 노출
            if (l["so_id"] in _dead or l["soi_id"] in _sched_soi
                    or not l.get("due_date")):
                continue
            _rem = float(l.get("pending_qty") or 0)
            _due = _date.fromisoformat(str(l["due_date"])[:10])
            _g.append({
                "품번": _pn_of(l),
                "거래처": _sc_som.get(l["so_id"], {}).get("customer", "-"),
                "수주번호": _sc_som.get(l["so_id"], {}).get("so_number", "-"),
                "구분": "단발", "회차": 1,
                "납기": _due, "수량": float(l.get("qty") or 0),
                "완료": float(l.get("received_qty") or 0),
                "잔량": max(_rem, 0.0),
                "상태": ("완료" if _rem <= 0 else
                        "지연" if _due < _today_s else "예정"),
            })

        # ── 3) 품번별 미납 / 계획 / 미계획 ──
        _pend_pn, _cust_pn = {}, {}
        for l in _open_li:
            if l["so_id"] in _dead:
                continue
            _p = _pn_of(l)
            _pend_pn[_p] = _pend_pn.get(_p, 0.0) + float(
                l.get("pending_qty") or 0)
            _cust_pn.setdefault(
                _p, _sc_som.get(l["so_id"], {}).get("customer", "-"))
        _plan_pn = {}
        for c in _g:
            if c["상태"] == "완료":
                continue
            _plan_pn[c["품번"]] = _plan_pn.get(c["품번"], 0.0) + c["잔량"]
            _cust_pn.setdefault(c["품번"], c["거래처"])

        _unplan = [(p, _pd - _plan_pn.get(p, 0.0))
                   for p, _pd in _pend_pn.items()
                   if _pd - _plan_pn.get(p, 0.0) > 0.5]
        _unplan.sort(key=lambda x: -x[1])
        _unplan_qty = sum(u for _, u in _unplan)

        # ── 4) 상단 KPI 4카드 (border-top 3px) ──
        _live = [c for c in _g if c["상태"] != "완료"]
        if _g:
            def _agg(rows):
                return (sum(c["잔량"] for c in rows), len(rows),
                        len({c["품번"] for c in rows}))
            _kpi = [
                ("지연 회차",
                 _agg([c for c in _live if c["상태"] == "지연"]), "danger"),
                ("이번 주 납품",
                 _agg([c for c in _live if _wk0 <= c["납기"] < _wk1]), "warn"),
                ("다음 주",
                 _agg([c for c in _live if _wk1 <= c["납기"] < _wk2]), ""),
                ("전체 잔여 계획", _agg(_live), ""),
            ]
            st.markdown(
                '<div class="kpi-row">' + "".join(
                    '<div class="kpi {c}"><div class="k">{k}</div>'
                    '<div class="v">{v:,.0f}</div>'
                    '<div class="s">{n}회차 · {p}품번</div></div>'.format(
                        c=(cls if v[0] else "zero"), k=k,
                        v=v[0], n=v[1], p=v[2])
                    for k, v, cls in _kpi) + "</div>",
                unsafe_allow_html=True)

            # ── 지연 상세 (부분 납품 포함 — 잔량이 남으면 지연) ──
            _late_rows = sorted(
                [c for c in _live if c["상태"] == "지연"],
                key=lambda c: c["납기"])
            if _late_rows:
                with st.expander(
                        "지연 상세 {}건 · 잔량 {:,.0f} — 품번·회차·경과일"
                        .format(len(_late_rows),
                                sum(c["잔량"] for c in _late_rows))):
                    _ldf = pd.DataFrame([{
                        "품번": c["품번"], "거래처": c["거래처"],
                        "수주번호": c["수주번호"],
                        "회차": "{} {}".format(c["구분"], c["회차"]),
                        "납기": c["납기"].isoformat(),
                        "경과": "D+{}".format(
                            (_today_s - c["납기"]).days),
                        "회차수량": c["수량"], "납품": c["완료"],
                        "잔량": c["잔량"],
                    } for c in _late_rows])
                    st.dataframe(
                        _ldf.style.map(
                            lambda v: "color:#f04452;font-weight:600",
                            subset=["경과", "잔량"]),
                        use_container_width=True, hide_index=True,
                        column_config={c: st.column_config.NumberColumn(
                            format="localized")
                            for c in ("회차수량", "납품", "잔량")})
                    st.caption(
                        "부분 납품이라도 잔량이 남으면 지연으로 셉니다. "
                        "수주 관리 상단 KPI 도 같은 기준입니다.")
        else:
            st.info("등록된 납품 회차가 없습니다 — 아래 **납기 입력**에서 "
                    "수주 라인을 골라 회차를 만들면 여기에 표시됩니다.")

        # ── 5) 뷰 토글 (회차 간트가 기본) ──
        _VIEWS = ["회차 간트", "주차별 물량", "납기 입력"]
        # 다른 위젯이 요청한 뷰 전환은 위젯 생성 '전에' 반영해야 한다
        # (생성 후 session_state 수정은 StreamlitAPIException)
        _nx = st.session_state.pop("sch_view_next", None)
        if _nx in _VIEWS:
            st.session_state["sch_view"] = _nx
        if hasattr(st, "segmented_control"):
            _sv = st.segmented_control(
                "보기", _VIEWS, default="회차 간트", key="sch_view",
                label_visibility="collapsed") or "회차 간트"
        else:
            _sv = st.radio("보기", _VIEWS, horizontal=True, key="sch_view",
                           label_visibility="collapsed")

        if _sv in ("회차 간트", "주차별 물량"):
            fg1, fg2, _fg3 = st.columns([1.2, 1, 2])
            _f_cust = fg1.selectbox(
                "거래처", ["전체"] + sorted({c["거래처"] for c in _g} - {"-"}),
                key="gantt_cust")
            _f_hide_done = fg2.checkbox("완료 회차 숨기기", value=True,
                                        key="gantt_hide_done")
            _chips = [c for c in _g
                      if (_f_cust == "전체" or c["거래처"] == _f_cust)
                      and not (_f_hide_done and c["상태"] == "완료")]
        else:
            _chips = []

        # ════ 뷰 A: 회차 간트 ════
        if _sv == "회차 간트":
            _WEEKS = 6
            _wstart = [_wk0 + _td(days=7 * i) for i in range(_WEEKS)]
            _wend = _wk0 + _td(days=7 * _WEEKS)

            def _bucket(d):
                """지연(이번 주 이전) 회차는 이번 주 칸으로 모아 표시"""
                if d < _wstart[0]:
                    return 0
                return _WEEKS if d >= _wend else (d - _wstart[0]).days // 7

            _cellmap, _pn_first = {}, {}
            for c in _chips:
                _cellmap.setdefault((c["품번"], _bucket(c["납기"])),
                                    []).append(c)
                if c["상태"] != "완료":
                    _pn_first[c["품번"]] = min(
                        _pn_first.get(c["품번"], c["납기"]), c["납기"])
            _pns = sorted({c["품번"] for c in _chips},
                          key=lambda p: (_pn_first.get(p, _date(2999, 1, 1)),
                                         -_pend_pn.get(p, 0)))

            if not _pns:
                st.info("표시할 납품 회차가 없습니다 — 필터를 조정하거나 "
                        "납기 입력에서 회차를 만드세요.")
            else:
                _WD = ("월", "화", "수", "목", "금", "토", "일")
                _h = ['<div class="gt">',
                      '<div class="gh">품번 / 거래처 · 미납</div>']
                for _i, _w in enumerate(_wstart):
                    _h.append('<div class="gh{n}">{d:%m/%d} 주{t}</div>'
                              .format(n=" now" if _i == 0 else "", d=_w,
                                      t=" · 이번 주" if _i == 0 else ""))
                _h.append('<div class="gh">이후</div>')

                _sums = [0.0] * (_WEEKS + 1)
                for _p in _pns:
                    _pd0 = _pend_pn.get(_p, 0.0)
                    if _pd0 > 0:
                        _rt = _plan_pn.get(_p, 0.0) / _pd0
                        _rc = ("#f04452" if _rt < 0.3 else
                               "#dd6b02" if _rt < 0.7 else "#01a76b")
                        _rtxt = ('<div class="grate" style="color:{c}">'
                                 '계획률 {r:.0%}</div>'.format(c=_rc, r=_rt))
                    else:
                        _rtxt = ('<div class="grate" style="color:#8b95a1">'
                                 '미납 없음</div>')
                    _h.append('<div><div class="gpn">{p}</div>'
                              '<div class="gsub">{c} · 미납 {q:,.0f}</div>'
                              '{r}</div>'.format(
                                  p=_p, c=_cust_pn.get(_p, "-"),
                                  q=_pd0, r=_rtxt))
                    for _b in range(_WEEKS + 1):
                        _cs = sorted(_cellmap.get((_p, _b), []),
                                     key=lambda x: x["납기"])
                        _sums[_b] += sum(c["잔량"] for c in _cs
                                         if c["상태"] != "완료")
                        if _b == _WEEKS and _cs:
                            # '이후' 열은 회차를 나열하지 않고 총량만 —
                            # 장기 스케줄이 행 높이를 늘리는 것을 막는다
                            _inner = ['<div class="gc after">'
                                      '<span class="gq">{q:,.0f}</span>'
                                      '<span class="gd">{n}회 · {f:%m/%d}{e}'
                                      '</span><span class="tip"><b>{pn}</b> '
                                      '이후 회차 요약<br>{f2:%Y-%m-%d} ~ '
                                      '{l:%Y-%m-%d} · {n}회차<br>잔량 합계 '
                                      '<b>{q:,.0f}</b></span></div>'.format(
                                          q=sum(c["잔량"] for c in _cs
                                                if c["상태"] != "완료"),
                                          n=len(_cs), f=_cs[0]["납기"],
                                          f2=_cs[0]["납기"],
                                          l=_cs[-1]["납기"], pn=_p,
                                          e="~" if len(_cs) > 1 else "")]
                        else:
                            _inner = []
                            for c in _cs:
                                _cls = ("done" if c["상태"] == "완료" else
                                        "one late" if c["구분"] == "단발"
                                        and c["상태"] == "지연" else
                                        "one" if c["구분"] == "단발" else
                                        "late" if c["상태"] == "지연"
                                        else "plan")
                                # 호버 메모 — 마우스를 올리면 세부 내역
                                _ld = (_today_s - c["납기"]).days
                                _tip = (
                                    "<b>{pn}</b> · {cu}<br>"
                                    "{so} · {kind} {seq}회차<br>"
                                    "납기 {due:%Y-%m-%d} ({dd})<br>"
                                    "회차 {q:,.0f} · 납품 {dv:,.0f} · "
                                    "잔량 <b>{rem:,.0f}</b>{w}").format(
                                    pn=c["품번"], cu=c["거래처"],
                                    so=c["수주번호"], kind=c["구분"],
                                    seq=c["회차"], due=c["납기"],
                                    dd=("D+{}".format(_ld) if _ld > 0
                                        else "오늘" if _ld == 0
                                        else "D-{}".format(-_ld)),
                                    q=c["수량"], dv=c["완료"],
                                    rem=c["잔량"],
                                    w=('<br><span class="warn">지연 '
                                       '{}일째 — 잔량 미납</span>'
                                       .format(_ld)
                                       if c["상태"] == "지연" else ""))
                                _inner.append(
                                    '<div class="gc {cl}">'
                                    '<span class="gd">{d}</span>'
                                    '<span class="gq">{q:,.0f}</span>'
                                    '<span class="tip">{tip}</span></div>'
                                    .format(
                                        cl=_cls,
                                        q=(c["잔량"] if c["상태"] != "완료"
                                           else c["수량"]),
                                        d="{} {}".format(
                                            _WD[c["납기"].weekday()],
                                            c["납기"].day),
                                        tip=_tip))
                        _h.append('<div class="cell{n}">{v}</div>'.format(
                            n=" now" if _b == 0 else "", v="".join(_inner)))
                _h.append('<div class="gsum l">주 합계</div>')
                for _b in range(_WEEKS + 1):
                    _h.append('<div class="gsum">{}</div>'.format(
                        "{:,.0f}".format(_sums[_b]) if _sums[_b]
                        else '<span style="color:#b0b8c1">0</span>'))
                _h.append("</div>")
                st.markdown("".join(_h), unsafe_allow_html=True)
                st.caption(
                    "표시 품번 {n}종 합계 **{s:,.0f}** · 전 품목 계획 합계 "
                    "**{t:,.0f}** — 지연 회차는 이번 주 칸에 붉은 칩으로 "
                    "모으고, **6주 밖 회차는 '이후' 열에 총량으로만** "
                    "표시합니다(칩에 마우스를 올리면 기간). 둥근 칩 = "
                    "반복(분납) · 각진 칩 = 단발.".format(
                        n=len(_pns), s=sum(_sums),
                        t=sum(c["잔량"] for c in _live)))

        # ════ 뷰 B: 주차별 물량 ════
        elif _sv == "주차별 물량":
            if not _chips:
                st.info("표시할 납품 회차가 없습니다 — 필터를 조정하세요.")
            else:
                _pv = pd.DataFrame(_chips)
                _pv["주"] = pd.to_datetime(_pv["납기"]).dt.to_period(
                    "W-SUN").apply(lambda p: p.start_time.strftime("%m/%d"))
                _piv = _pv.pivot_table(index="품번", columns="주",
                                       values="잔량", aggfunc="sum",
                                       fill_value=0)
                _ordp = (_pv.groupby("품번")["납기"].min()
                         .sort_values().index.tolist())
                _piv = _piv.reindex([p for p in _ordp if p in _piv.index])
                _piv["합계"] = _piv.sum(axis=1)
                _wk_cols = [c for c in _piv.columns if c != "합계"]
                _vmax = (float(_piv[_wk_cols].to_numpy().max())
                         if _wk_cols else 0.0)

                def _heat(v):
                    try:
                        v = float(v)
                    except (TypeError, ValueError):
                        return ""
                    if v <= 0 or _vmax <= 0:
                        return "color:#b0b8c1"
                    _t = min(v / _vmax, 1.0)
                    _bg = (f"background-color: rgba(36,64,107,"
                           f"{0.06 + 0.5 * _t:.2f})")
                    return (_bg + ";color:#fff;font-weight:600"
                            if _t > 0.55 else _bg)
                st.dataframe(
                    _piv.style.format("{:,.0f}").map(_heat, subset=_wk_cols),
                    use_container_width=True,
                    height=min(460, 60 + len(_piv) * 35))
                st.caption("열 = 주 시작일(월요일) · 값 = 그 주 납품 예정 "
                           "잔량 · 생산 계획 수립에 사용하세요.")

        # ── 미계획 물량 배너 (간트·주차 뷰에 상시 노출) ──
        if _sv != "납기 입력" and _unplan:
            _pend_all = sum(_pend_pn.values()) or 1
            st.markdown(
                '<div class="unplan"><div class="t">납기 미협의 물량 '
                '{q:,.0f}개 ({r:.0%})</div><div class="d">'
                '계획이 없는 품번 <b>{n}종</b> — 간트에 나타나지 않으므로 '
                '납기 입력에서 회차를 잡아야 합니다.<br>상위 3품번: '
                '<b>{t}</b></div></div>'.format(
                    q=_unplan_qty, r=_unplan_qty / _pend_all,
                    n=len(_unplan),
                    t=" · ".join("{} {:,.0f}".format(p, q)
                                 for p, q in _unplan[:3])),
                unsafe_allow_html=True)
            ub1, ub2, _ub3 = st.columns([1, 1, 2])
            if ub1.button("미계획 품번 보기", use_container_width=True,
                          key="sch_unplan_btn"):
                st.session_state["sch_unplan_open"] = not st.session_state.get(
                    "sch_unplan_open", False)
            if ub2.button("납기 입력으로 이동", type="primary",
                          use_container_width=True, key="sch_goto_input"):
                st.session_state["sch_view_next"] = "납기 입력"
                st.rerun()
            if st.session_state.get("sch_unplan_open"):
                st.dataframe(
                    pd.DataFrame([{"품번": p, "거래처": _cust_pn.get(p, "-"),
                                   "미납": _pend_pn.get(p, 0.0),
                                   "계획됨": _plan_pn.get(p, 0.0),
                                   "미계획": q} for p, q in _unplan]),
                    use_container_width=True, hide_index=True,
                    height=min(420, 60 + len(_unplan) * 35))

        # ════ 뷰 C: 납기 입력 ════
        if _sv == "납기 입력":
            st.caption(
                "품번 또는 수주번호로 찾아 대상 라인을 고르고, **한 번에"
                "(단발)** 또는 **나눠서(반복)** 로 납기를 만듭니다. "
                "단발 납기도 1회차로 저장되어 회차 간트에 함께 표시됩니다.")

            # ── 통합 검색 (품번 / 수주번호 / 거래처) ──
            sc1, sc2 = st.columns([3, 1])
            _sq = sc1.text_input("품번 · 품명 · 수주번호 · 거래처 검색",
                                 key="sch_q",
                                 placeholder="예: 4PDVN, GLAND, 202607, 미진")
            _sc_only_open = sc2.checkbox("미납만", value=True,
                                         key="sch_open_only")

            # 품번 검색은 라인에서, 수주번호·거래처는 헤더에서 → so_id 합집합
            _hit_soi, _hit_so = None, None
            if _sq:
                _q = _sq.strip()
                try:
                    _by_pn = fetch("sales_order_items", "soi_id,so_id",
                        f"or=(canonical_pn.ilike.*{_q}*,"
                        f"customer_part_no.ilike.*{_q}*,"
                        f"customer_item_name.ilike.*{_q}*)", limit=500)
                    _hit_soi = {r["soi_id"] for r in _by_pn}
                    _hit_so = {r["so_id"] for r in _by_pn}
                except Exception:
                    _hit_soi, _hit_so = set(), set()
                try:
                    _by_so = fetch("sales_orders", "so_id",
                        f"or=(so_number.ilike.*{_q}*,customer.ilike.*{_q}*)",
                        limit=300)
                    _hit_so |= {r["so_id"] for r in _by_so}
                except Exception:
                    pass

            _sf = ['status=not.in.("CANCELLED","CANCELED")',
                   "order=so_date.desc"]
            if _sq:
                if not _hit_so:
                    _sf.append("so_id=eq.-1")     # 결과 없음
                else:
                    _sf.append("so_id=in.("
                               + ",".join(str(i) for i in _hit_so) + ")")
            try:
                _s_sos = fetch("sales_orders",
                    "so_id,so_number,customer,so_date,due_date",
                    "&".join(_sf), limit=200)
            except Exception as e:
                st.error(f"수주 조회 실패: {e}"); _s_sos = []

            if not _s_sos:
                st.info("검색 결과 없음 — 품번 일부(예: 4PDVN)나 수주번호로 "
                        "다시 찾아보세요.")
            else:
                _so_ids_f = ",".join(str(s["so_id"]) for s in _s_sos)
                try:
                    _all_items = fetch("sales_order_items",
                        "soi_id,so_id,line_no,product_id,canonical_pn,"
                        "customer_part_no,qty,received_qty,pending_qty,"
                        "due_date",
                        f"so_id=in.({_so_ids_f})"
                        + ("&pending_qty=gt.0" if _sc_only_open else "")
                        + "&order=due_date.asc.nullslast,soi_id.asc",
                        limit=500)
                except Exception as e:
                    st.error(f"라인 조회 실패: {e}"); _all_items = []
                if _sq and _hit_soi:
                    # 품번으로 찾은 경우 그 품번 라인만 (수주번호 검색은 전체)
                    _pn_only = [i for i in _all_items
                                if i["soi_id"] in _hit_soi]
                    if _pn_only:
                        _all_items = _pn_only

                if not _all_items:
                    st.info("표시할 라인 없음 (미납만 보기 해제 시 전체 표시).")
                else:
                    _so_lbl = {s["so_id"]: s for s in _s_sos}
                    _sc_cnt = {}
                    try:
                        for _r in fetch("so_delivery_schedule",
                            "soi_id,qty,delivered_qty",
                            "soi_id=in.("
                            + ",".join(str(i["soi_id"]) for i in _all_items)
                            + ")", limit=1000):
                            _e = _sc_cnt.setdefault(_r["soi_id"],
                                                    {"n": 0, "q": 0.0,
                                                     "d": 0.0})
                            _e["n"] += 1
                            _e["q"] += float(_r.get("qty") or 0)
                            _e["d"] += float(_r.get("delivered_qty") or 0)
                    except Exception:
                        pass

                    # 납기 미입력 수량 = 미납 − (계획 − 납품완료)
                    def _unplanned(it):
                        _c = _sc_cnt.get(it["soi_id"], {})
                        _planned = max(0.0, float(_c.get("q", 0))
                                       - float(_c.get("d", 0)))
                        return max(0.0, float(it.get("pending_qty") or 0)
                                   - _planned)

                    _tot_pend = sum(float(i.get("pending_qty") or 0)
                                    for i in _all_items)
                    _tot_un = sum(_unplanned(i) for i in _all_items)
                    sm1, sm2, sm3, sm4 = st.columns(4)
                    sm1.metric("조회 라인", f"{len(_all_items):,}건")
                    sm2.metric("미납 합계", f"{_tot_pend:,.0f}")
                    sm3.metric("납기 입력됨", f"{_tot_pend - _tot_un:,.0f}")
                    sm4.metric("납기 미입력", f"{_tot_un:,.0f}",
                               help="이 수량만큼 일정을 더 넣어야 합니다")

                    # 라인별 계획 현황 (어디에 일정을 넣어야 하는지)
                    _st_rows = [{
                        "수주번호": _so_lbl.get(i["so_id"], {}).get(
                            "so_number", "-"),
                        "품번": (i.get("canonical_pn")
                                or i.get("customer_part_no") or "-"),
                        "미납": float(i.get("pending_qty") or 0),
                        "회차": _sc_cnt.get(i["soi_id"], {}).get("n", 0),
                        "납기 입력됨": float(i.get("pending_qty") or 0)
                                     - _unplanned(i),
                        "납기 미입력": _unplanned(i),
                    } for i in _all_items]
                    _st_df = pd.DataFrame(_st_rows).sort_values(
                        "납기 미입력", ascending=False)
                    st.dataframe(
                        _st_df.style.map(
                            lambda v: ("color:#f04452;font-weight:700"
                                       if isinstance(v, (int, float))
                                       and v > 0 else "color:#8b95a1"),
                            subset=["납기 미입력"]).format(
                            {c: "{:,.0f}" for c in
                             ["미납", "납기 입력됨", "납기 미입력"]}),
                        use_container_width=True, hide_index=True,
                        height=min(320, 60 + len(_st_df) * 35))

                    # ── 대상 라인 선택 (단발·반복 공통) ──
                    st.divider()
                    st.markdown("##### 납기 만들기")
                    _li_map = {}
                    for i in _all_items:
                        _c = _sc_cnt.get(i["soi_id"], {})
                        _li_map[
                            f"{_so_lbl.get(i['so_id'], {}).get('so_number','-')}"
                            f" · {i.get('canonical_pn') or i.get('customer_part_no') or '-'}"
                            f" | 미납 {float(i.get('pending_qty') or 0):,.0f}"
                            + (f" · 회차 {_c['n']}개" if _c.get("n")
                               else " · 회차 없음")] = i
                    _li_pick = st.selectbox(
                        f"대상 라인 ({len(_li_map)}건)", list(_li_map.keys()),
                        key="sch_line_pick")
                    _li = _li_map[_li_pick]
                    _s_so = _so_lbl.get(_li["so_id"], {"so_id": _li["so_id"]})
                    _li_qty = float(_li.get("qty") or 0)
                    _li_rcv = float(_li.get("received_qty") or 0)
                    _li_pend = float(_li.get("pending_qty") or 0)
                    # 계획 기준은 항상 '미납' — 수주 총량과 혼동 방지
                    # (예: 수주 16,600 중 8,252 납품 완료 → 미납 8,348 이
                    #  계획 대상. 총량과 비교하면 계획이 모자란 것처럼 보임)
                    _li_planned = max(0.0, float(
                        _sc_cnt.get(_li["soi_id"], {}).get("q", 0))
                        - float(_sc_cnt.get(_li["soi_id"], {}).get("d", 0)))
                    _li_unplan = max(0.0, _li_pend - _li_planned)
                    lm1, lm2, lm3, lm4 = st.columns(4)
                    lm1.metric("미납 (계획 대상)", f"{_li_pend:,.0f}",
                               help=f"수주 {_li_qty:,.0f} − 기납품 "
                                    f"{_li_rcv:,.0f}")
                    lm2.metric("납기 입력됨", f"{_li_planned:,.0f}")
                    lm3.metric("납기 미입력", f"{_li_unplan:,.0f}")
                    lm4.metric("수주 / 기납품",
                               f"{_li_qty:,.0f} / {_li_rcv:,.0f}")

                    # ── 기존 스케줄 조회 ──
                    try:
                        _rows = fetch("so_delivery_schedule",
                            "sched_id,seq,due_date,qty,delivered_qty,note",
                            f"soi_id=eq.{_li['soi_id']}&order=seq.asc",
                            limit=200)
                    except Exception as e:
                        st.error(f"스케줄 조회 실패 (Migration 027 필요): {e}")
                        _rows = []

                    # ── 회차 생성 (요일 패턴 + 미납 소진까지 자동) ──
                    # 실사용 패턴 분석(2026-07-28): 수/금 주2회, 월수금 주3회,
                    # 주1회 — 모두 요일 기반이고 합계는 미납과 정확히 일치.
                    # → 요일 + 회차당 수량만 주면 나머지는 자동 생성.
                    from datetime import timedelta as _td2
                    _WD = ["월", "화", "수", "목", "금", "토", "일"]
                    _sched_done = sum(float(r.get("delivered_qty") or 0)
                                      for r in _rows)
                    _sched_plan = sum(float(r.get("qty") or 0) for r in _rows)
                    _remain_to_plan = max(0.0, _li_pend - (_sched_plan
                                                          - _sched_done))

                    # 같은 품번의 최근 스케줄에서 패턴 추론 (이어받기)
                    _prev = {}
                    try:
                        _sib = fetch("sales_order_items", "soi_id",
                            f"product_id=eq.{_li.get('product_id')}"
                            f"&soi_id=neq.{_li['soi_id']}", limit=50) \
                            if _li.get("product_id") else []
                        _sib_ids = [str(x["soi_id"]) for x in _sib]
                        _pool = []
                        if _sib_ids:
                            _pool = fetch("so_delivery_schedule",
                                "soi_id,due_date,qty",
                                f"soi_id=in.({','.join(_sib_ids)})"
                                "&order=due_date.desc", limit=100)
                        _src_rows = _rows or _pool
                        if _src_rows:
                            _sr = sorted(_src_rows,
                                         key=lambda x: x["due_date"])
                            _ds = [r["due_date"] for r in _sr]
                            # 요일별 수량 추론 — 마지막 회차는 잔량이라 제외
                            _body = _sr[:-1] if len(_sr) > 1 else _sr
                            _wq = {}
                            for r in _body:
                                _w = _date.fromisoformat(r["due_date"]).weekday()
                                _wq.setdefault(_w, []).append(float(r["qty"]))
                            _wd_qty = {w: max(set(v), key=v.count)
                                       for w, v in _wq.items()}
                            # 마지막 회차가 그 요일 정상 수량보다 적으면
                            # 부족분을 다음 스케줄 첫 회차로 승계 (연속성)
                            _lastr = _sr[-1]
                            _lw = _date.fromisoformat(
                                _lastr["due_date"]).weekday()
                            _lnorm = _wd_qty.get(_lw)
                            _carry = 0.0
                            if _lnorm and float(_lastr["qty"]) < _lnorm:
                                _carry = _lnorm - float(_lastr["qty"])
                            _prev = {"wd": sorted(_wd_qty.keys()),
                                     "wd_qty": _wd_qty,
                                     "last": max(_ds),
                                     "last_qty": float(_lastr["qty"]),
                                     "last_norm": _lnorm,
                                     "carry": _carry,
                                     "src": ("이 라인" if _rows
                                             else "같은 품번 이전 수주")}
                    except Exception:
                        _prev = {}

                    # ── 패턴으로 행 채우기 (2026-08-08 재설계) ──
                    # 단발/분납 구분 제거 — 회차가 1개면 그게 단발이다.
                    # 표(회차 편집)가 1차 입력 수단이고, 패턴 도구는 표를
                    # 빨리 채워줄 뿐이다. 여기서 만든 행은 DB 에 바로
                    # 저장되지 않고 표에 올라간 뒤 '스케줄 저장' 시점에
                    # 반영된다 — 저장 전에 표에서 자유롭게 고칠 수 있다.
                    _pend_key = f"sch_pend_{_li['soi_id']}"
                    _pending = st.session_state.setdefault(_pend_key, [])
                    _pending_sum = sum(float(p["qty"]) for p in _pending)
                    _fill_target = max(0.0, _remain_to_plan - _pending_sum)
                    with st.expander(
                            "패턴으로 행 채우기 — 요일 반복을 표에 자동 "
                            "추가"
                            + (f" (미저장 {len(_pending)}행 · "
                               f"{_pending_sum:,.0f})" if _pending else ""),
                            expanded=not _rows and not _pending):
                        _pv_wq = _prev.get("wd_qty") or {}
                        if _prev:
                            st.caption(
                                f"이전 패턴 감지 ({_prev['src']}): "
                                + " · ".join(
                                    f"{_WD[w]} {q:,.0f}"
                                    for w, q in sorted(_pv_wq.items()))
                                + f" · 마지막 납기 {_prev['last']} → 아래 "
                                  "기본값에 반영했습니다.")
                        _def_wd = [_WD[w] for w in _prev.get("wd", [2, 4])
                                   if w < 7] or ["수", "금"]
                        _def_start = (
                            _date.fromisoformat(_prev["last"]) + _td(days=1)
                            if _prev.get("last")
                            and _date.fromisoformat(_prev["last"])
                            >= _date.today()
                            else _date.today() + _td(days=1))
                        g1, g2 = st.columns([2, 1])
                        _g_wd = g1.multiselect(
                            "납품 요일", _WD, default=_def_wd,
                            key=f"sch_wd_{_li['soi_id']}",
                            help="여러 개 선택 — 요일마다 수량을 다르게 "
                                 "지정할 수 있습니다. 1회짜리(단발)는 "
                                 "이 도구 없이 표에 행 하나만 추가하면 "
                                 "됩니다.")
                        _g_start = g2.date_input(
                            "시작일", value=_def_start,
                            key=f"sch_st_{_li['soi_id']}",
                            help="이 날짜 이후 첫 해당 요일부터 생성")
                        _wd_amt = {}
                        if _g_wd:
                            st.caption("요일별 수량 — 요일마다 다르면 각각 "
                                       "입력하세요.")
                            _wcols = st.columns(len(_g_wd))
                            for _wi, _wname in enumerate(_g_wd):
                                _widx = _WD.index(_wname)
                                _dflt = float(
                                    _pv_wq.get(_widx)
                                    or (list(_pv_wq.values())[0]
                                        if _pv_wq else 0)
                                    or (round(_fill_target / 4)
                                        if _fill_target else 0))
                                _wd_amt[_widx] = _wcols[_wi].number_input(
                                    f"{_wname}요일", min_value=0.0,
                                    value=_dflt, step=1.0,
                                    key=f"sch_wq_{_li['soi_id']}_{_widx}")
                        _week_sum = sum(_wd_amt.values())
                        _g_target = st.number_input(
                            "총 배분 수량", min_value=0.0,
                            value=float(_fill_target), step=1.0,
                            key=f"sch_t_{_li['soi_id']}",
                            help="기본값 = 납기 미입력 잔량(미저장 행 "
                                 "제외). 이 수량이 소진될 때까지 행을 "
                                 "만듭니다.")
                        _carry0 = float(_prev.get("carry") or 0)
                        _use_carry = False
                        if _carry0 > 0:
                            _use_carry = st.checkbox(
                                f"{_prev['last']} 잔여 {_carry0:,.0f} 먼저 "
                                f"채우기 (그날 {_prev['last_qty']:,.0f} / "
                                f"정상 {_prev['last_norm']:,.0f})",
                                value=True, key=f"sch_cr_{_li['soi_id']}")
                        if _g_target > 0 and _week_sum > 0 and _g_wd:
                            st.caption(
                                f"주당 {_week_sum:,.0f} → 약 "
                                f"{_g_target / _week_sum:.1f}주 · 총 "
                                f"{_g_target:,.0f} (마지막 행에서 잔량 "
                                "조정)")
                        fb1, fb2 = st.columns([1, 1])
                        if fb1.button(
                                "표에 채우기", type="primary",
                                disabled=not (_week_sum > 0
                                              and _g_target > 0 and _g_wd),
                                key=f"sch_mk_{_li['soi_id']}",
                                use_container_width=True):
                            _cur = _g_start
                            _left = float(_g_target)
                            _new, _guard = [], 0
                            if _use_carry and _carry0 > 0:
                                _cq = min(_carry0, _left)
                                _new.append({
                                    "due_date": _prev["last"],
                                    "qty": float(_cq),
                                    "note": "이전 회차 잔여 보충"})
                                _left -= _cq
                            while _left > 0.5 and _guard < 500:
                                _guard += 1
                                _wq = _wd_amt.get(_cur.weekday())
                                if _wq and _wq > 0:
                                    _q = min(_wq, _left)
                                    _new.append({
                                        "due_date": _cur.isoformat(),
                                        "qty": float(_q), "note": None})
                                    _left -= _q
                                _cur += _td2(days=1)
                            if _new:
                                _pending.extend(_new)
                                st.rerun()
                        if _pending and fb2.button(
                                "미저장 행 비우기",
                                key=f"sch_pclr_{_li['soi_id']}",
                                use_container_width=True):
                            st.session_state[_pend_key] = []
                            st.rerun()

                    # ── 일괄 조정 (협의 변경 대응) ──
                    if _rows:
                        _cur_plan = sum(float(r.get("qty") or 0)
                                        for r in _rows)
                        _cur_done = sum(float(r.get("delivered_qty") or 0)
                                        for r in _rows)
                        with st.expander("일괄 조정 (총량 변경·날짜 이동)"):
                            st.caption(
                                "고객사 협의로 물량이나 일정이 통째로 바뀔 때 "
                                "사용합니다. 이미 납품된 회차는 건드리지 "
                                "않습니다.")
                            b1, b2 = st.columns(2)
                            with b1:
                                st.markdown("**총량 재배분**")
                                _new_tot = st.number_input(
                                    "새 총 계획 수량", min_value=0.0,
                                    value=float(_cur_plan), step=1.0,
                                    key=f"sch_bt_{_li['soi_id']}",
                                    help="기존 회차 비율을 유지하며 수량을 "
                                         "다시 나눕니다 (납품 완료분 이상은 "
                                         "유지)")
                                if st.button("총량 적용", type="primary",
                                             use_container_width=True,
                                             disabled=_new_tot <= 0,
                                             key=f"sch_bta_{_li['soi_id']}"):
                                    try:
                                        _open = [r for r in _rows
                                                 if float(r.get("qty") or 0)
                                                 > float(r.get(
                                                     "delivered_qty") or 0)]
                                        _open_now = sum(
                                            float(r["qty"]) for r in _open)
                                        _tgt = _new_tot - _cur_done
                                        if _open_now <= 0 or _tgt <= 0:
                                            st.warning("조정할 미납 회차가 "
                                                       "없습니다.")
                                        else:
                                            _ratio = _tgt / _open_now
                                            _acc = 0.0
                                            for _k, _r in enumerate(_open):
                                                _q = (round(float(_r["qty"])
                                                            * _ratio)
                                                      if _k < len(_open) - 1
                                                      else _tgt - _acc)
                                                _q = max(
                                                    float(_r.get(
                                                        "delivered_qty")
                                                        or 0), _q)
                                                _acc += _q
                                                _db.update(
                                                    "so_delivery_schedule",
                                                    f"sched_id=eq.{_r['sched_id']}",
                                                    {"qty": float(_q)})
                                            st.success(
                                                f"총량 {_new_tot:,.0f} 로 "
                                                "재배분 완료")
                                            st.rerun()
                                    except Exception as e:
                                        st.error(f"조정 실패: {e}")
                            with b2:
                                st.markdown("**납기 일괄 이동**")
                                _shift = st.number_input(
                                    "이동 일수 (+뒤로 / −앞으로)",
                                    value=0, step=1,
                                    key=f"sch_bs_{_li['soi_id']}")
                                _shift_open = st.checkbox(
                                    "미납 회차만 이동", value=True,
                                    key=f"sch_bso_{_li['soi_id']}")
                                if st.button("날짜 적용",
                                             use_container_width=True,
                                             disabled=_shift == 0,
                                             key=f"sch_bsa_{_li['soi_id']}"):
                                    try:
                                        _n = 0
                                        for _r in _rows:
                                            if _shift_open and float(
                                                    _r.get("qty") or 0) <= \
                                                    float(_r.get(
                                                        "delivered_qty")
                                                        or 0):
                                                continue
                                            _nd = (_date.fromisoformat(
                                                str(_r["due_date"])[:10])
                                                + _td(days=int(_shift)))
                                            _db.update(
                                                "so_delivery_schedule",
                                                f"sched_id=eq.{_r['sched_id']}",
                                                {"due_date":
                                                 _nd.isoformat()})
                                            _n += 1
                                        st.success(f"{_n}개 회차 "
                                                   f"{_shift:+d}일 이동")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"이동 실패: {e}")

                    # ── 자유 편집 (data_editor) ──
                    # 회차 번호는 저장 시 납기순 자동 부여 → 표에서 제외
                    st.markdown("##### 회차 편집")
                    st.caption("납기·수량을 직접 고치거나, 표 아래 ＋ 로 회차를 "
                               "추가하고 휴지통으로 삭제합니다. 회차 번호는 "
                               "저장할 때 납기순으로 자동 부여됩니다. "
                               "납품 완료 수량은 출고 등록 시 자동 반영.")
                    # 표 = DB 회차 + 패턴으로 채운 미저장 행 (납기순)
                    # 빈 표에서도 컬럼 타입이 정해져야 data_editor 가
                    # column_config 와 충돌하지 않는다 (astype 필수)
                    _tbl_rows = sorted(
                        [{"due_date": str(r["due_date"])[:10],
                          "qty": float(r.get("qty") or 0),
                          "delivered_qty":
                              float(r.get("delivered_qty") or 0),
                          "note": r.get("note")} for r in _rows]
                        + [{"due_date": str(p["due_date"])[:10],
                            "qty": float(p.get("qty") or 0),
                            "delivered_qty": 0.0,
                            "note": p.get("note")} for p in _pending],
                        key=lambda x: x["due_date"])
                    if _tbl_rows:
                        _b = pd.DataFrame(_tbl_rows)
                        _ed_src = pd.DataFrame({
                            "납기": pd.to_datetime(_b["due_date"],
                                                  errors="coerce"),
                            "수량": pd.to_numeric(_b["qty"],
                                                 errors="coerce").astype(float),
                            "납품완료": pd.to_numeric(
                                _b["delivered_qty"],
                                errors="coerce").fillna(0).astype(float),
                            "비고": _b["note"].astype("string"),
                        }).reset_index(drop=True)
                    else:
                        _ed_src = pd.DataFrame({
                            "납기": pd.Series([], dtype="datetime64[ns]"),
                            "수량": pd.Series([], dtype="float64"),
                            "납품완료": pd.Series([], dtype="float64"),
                            "비고": pd.Series([], dtype="string"),
                        })
                    if _pending:
                        st.caption(
                            f"패턴으로 채운 미저장 행 {len(_pending)}개가 "
                            "표에 포함되어 있습니다 — 확인·수정 후 "
                            "**스케줄 저장**을 눌러야 반영됩니다.")
                    # key 에 데이터 시그니처를 포함 — 같은 key 면 Streamlit 이
                    # 이전 위젯 상태(편집 전 표)를 재사용해 행 추가 직후
                    # 표가 갱신되지 않는다 (2026-07-28 사용자 보고)
                    _ed_sig = f"{len(_tbl_rows)}_{hash(tuple(sorted((r['due_date'], r['qty']) for r in _tbl_rows))) % 99999}"
                    _ed = st.data_editor(
                        _ed_src, num_rows="dynamic", use_container_width=True,
                        hide_index=True,
                        key=f"sch_ed_{_li['soi_id']}_{_ed_sig}",
                        column_config={
                            "납기": st.column_config.DateColumn(
                                format="YYYY-MM-DD"),
                            "수량": st.column_config.NumberColumn(
                                format="localized", step=1),
                            "납품완료": st.column_config.NumberColumn(
                                format="localized", disabled=True),
                        })
                    _plan = float(pd.to_numeric(
                        _ed["수량"], errors="coerce").fillna(0).sum())
                    _done = float(pd.to_numeric(
                        _ed["납품완료"], errors="coerce").fillna(0).sum())
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("라인 수주", f"{_li_qty:,.0f}")
                    m2.metric("계획 합계", f"{_plan:,.0f}")
                    m3.metric("납품 완료", f"{_done:,.0f}")
                    m4.metric("계획 잔량", f"{_plan - _done:,.0f}")
                    # 비교는 '계획 잔량'(합계 − 납품완료) 기준 — 계획
                    # 합계에는 이미 납품된 회차가 포함되므로 미납과 직접
                    # 비교하면 기납품만큼 어긋나 보인다 (2026-08-06 확인)
                    if abs((_plan - _done) - _li_pend) > 0.5 and _rows:
                        st.warning(
                            f"계획 잔량 {_plan - _done:,.0f} 가 라인 미납 "
                            f"{_li_pend:,.0f} 와 다릅니다 — 협의 변경이면 "
                            "그대로 두셔도 되고, 맞추려면 수량을 조정하세요.")

                    sv1, sv2 = st.columns([1, 1])
                    _do_save = sv1.button("스케줄 저장", type="primary",
                                          use_container_width=True,
                                          key=f"sch_save_{_li['soi_id']}")
                    # 전체 삭제 — 2단계 확인 (오조작 방지)
                    _rk = f"sch_reset_{_li['soi_id']}"
                    if _rows:
                        if st.session_state.get(_rk):
                            sv2.warning("이 라인의 회차를 전부 지웁니다.")
                            rc1, rc2 = sv2.columns(2)
                            if rc1.button("삭제 확정", type="primary",
                                          use_container_width=True,
                                          key=f"{_rk}_ok"):
                                try:
                                    _db.delete("so_delivery_schedule",
                                               f"soi_id=eq.{_li['soi_id']}")
                                    st.session_state[_rk] = False
                                    st.session_state[_pend_key] = []
                                    st.success("전체 삭제 완료")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"삭제 실패: {e}")
                            if rc2.button("취소", use_container_width=True,
                                          key=f"{_rk}_no"):
                                st.session_state[_rk] = False
                                st.rerun()
                        else:
                            sv2.button(
                                f"전체 삭제 ({len(_rows)}회차)",
                                use_container_width=True,
                                key=f"{_rk}_ask",
                                on_click=lambda k=_rk:
                                    st.session_state.update({k: True}))

                    if _do_save:
                        try:
                            _keep = []
                            for _k, _r in _ed.iterrows():
                                _due = _r.get("납기")
                                _q = float(pd.to_numeric(_r.get("수량"),
                                                         errors="coerce") or 0)
                                if pd.isna(_due) or _q <= 0:
                                    continue
                                _keep.append({
                                    "due_date": str(_due)[:10],
                                    "qty": _q,
                                    "note": (None if pd.isna(_r.get("비고"))
                                             else str(_r.get("비고") or "")
                                             or None),
                                })
                            # 회차 번호는 납기순 자동 부여 (사용자 입력 없음)
                            _keep.sort(key=lambda x: x["due_date"])
                            # 같은 납기는 한 회차로 병합 — 납기당 1회차.
                            # 중복 날짜가 저장되면 한 번의 납품이 두 행에
                            # 나뉘어 보이는 왜곡 (2026-08-13, 4PDVN-02)
                            from utils.delivery_alloc import (
                                carry_delivered, merge_same_date)
                            _n_before = len(_keep)
                            _keep = merge_same_date(_keep)
                            if len(_keep) < _n_before:
                                st.info("같은 납기 {}건을 한 회차로 "
                                        "병합했습니다 (납기당 1회차 · "
                                        "수량 합산).".format(
                                            _n_before - len(_keep)))
                            for _i2, _r2 in enumerate(_keep, 1):
                                _r2["seq"] = _i2
                            # 납품완료 승계 — 납기 '날짜' 기준.
                            # 순번(위치) 승계는 중간 회차를 지우면 납품이
                            # 다음 날짜로 밀림 (8/3 삭제 → 8/5 실적이
                            # 8/7 로 이동하던 버그, 2026-08-06)
                            _done_new, _done_lost = carry_delivered(
                                _rows, _keep)
                            if _done_lost > 0.5:
                                st.warning(
                                    f"납품완료 {_done_lost:,.0f}개는 새 "
                                    "회차 총량보다 커서 회차에 싣지 "
                                    "못했습니다 — 라인 기납품에는 그대로 "
                                    "남습니다. 회차 수량을 확인하세요.")
                            for _i3, _r3 in enumerate(_keep):
                                _r3["delivered_qty"] = _done_new[_i3]
                                _r3["so_id"] = _s_so["so_id"]
                                _r3["soi_id"] = _li["soi_id"]
                                _r3["created_by"] = current_user_name()
                                # PostgREST 배열 insert 는 키가 모두 같아야
                                # 한다 (PGRST102 All object keys must match)
                                _r3.setdefault("note", None)
                            _db.delete("so_delivery_schedule",
                                       f"soi_id=eq.{_li['soi_id']}")
                            if _keep:
                                _db.insert("so_delivery_schedule", _keep)
                                # 라인 납기 = 첫 회차 (화면 납기 표시 기준)
                                try:
                                    _db.update("sales_order_items",
                                        f"soi_id=eq.{_li['soi_id']}",
                                        {"due_date":
                                         _keep[0]["due_date"]})
                                except Exception:
                                    pass
                            st.session_state[_pend_key] = []
                            st.success(f"저장 완료 — {len(_keep)}개 회차")
                            st.rerun()
                        except Exception as e:
                            st.error(f"저장 실패: {e}")


elif page == "출고 관리":
    st.subheader("출고 관리")
    if not DB_AVAILABLE:
        st.error("DB 연결이 활성화되지 않았습니다."); st.stop()

    import db as _db
    import pandas as pd

    tab_deliver, tab_ship, tab_dstat = st.tabs(["출고 등록", "출고 전표", "출고 현황"])

    # ════════ TAB 1: 납품 등록 ════════
    with tab_deliver:
        # ══ ① 출고 등록 — 장바구니식 리스트 구성 → 전표 생성 ══
        # 흐름: 담기(스케줄 자동 + 품번 검색) → [출고 등록] = 전표
        # 생성(DRAFT) → 출고 전표 탭에서 확인용 리스트 인쇄·현장 확인
        # → 정정 반영 → [출고 확정] = 수주 반영·재고 차감·명세서 발행
        from datetime import date as _sh_dt
        st.caption(
            "스케줄이 출고 예정 품목을 자동으로 담고, 스케줄에 없는 "
            "품목은 품번 검색으로 추가합니다. **출고 등록**을 누르면 "
            "전표(DRAFT)가 만들어지고, 인쇄·현장 확인·정정·확정은 "
            "**출고 전표 탭**에서 이어집니다. 재고 차감과 거래명세서는 "
            "확정 시점에 이루어집니다.")

        st.markdown("##### 출고 리스트 담기")
        shc1, shc2, shc3 = st.columns([1, 1, 2])
        _sh_d = shc1.date_input("납품일", _sh_dt.today(), key="bk_date")
        _sh_late = shc2.checkbox("지연 회차 포함", value=True, key="bk_late",
                                 help="선택일 이전에 밀린 회차 잔량도 "
                                      "리스트에 올립니다")

        # 작성중(DRAFT) 전표에 이미 담긴 라인은 중복 등록 방지를 위해
        # 담기 목록에서 제외한다 (2026-08-08 사용자 확정 — 두 전표를
        # 모두 확정하면 이중 출고가 되므로). 전표를 취소하면 다시 뜬다.
        _draft_sois = {}
        try:
            _open_drafts = fetch("shipments", "shipment_id,ship_no",
                                 "status=eq.DRAFT", limit=50)
            if _open_drafts:
                _d_ids = ",".join(str(s["shipment_id"])
                                  for s in _open_drafts)
                _d_no = {s["shipment_id"]: s["ship_no"]
                         for s in _open_drafts}
                for x in fetch("shipment_items", "soi_id,shipment_id",
                               f"shipment_id=in.({_d_ids})", limit=1000):
                    if x.get("soi_id") is not None:
                        _draft_sois.setdefault(
                            x["soi_id"], _d_no.get(x["shipment_id"], "-"))
        except Exception:
            _draft_sois = {}

        # 스케줄 자동 리스트업
        _sh_flt = ("due_date=lte." if _sh_late
                   else "due_date=eq.") + _sh_d.isoformat()
        try:
            _sh_rounds_all = [r for r in fetch("so_delivery_schedule",
                "sched_id,soi_id,so_id,seq,due_date,qty,delivered_qty",
                _sh_flt + "&order=due_date.asc,seq.asc", limit=500)
                if (float(r.get("qty") or 0)
                    - float(r.get("delivered_qty") or 0)) > 0]
            _sh_rounds = [r for r in _sh_rounds_all
                          if r["soi_id"] not in _draft_sois]
            _sh_held = {r["soi_id"]: _draft_sois[r["soi_id"]]
                        for r in _sh_rounds_all
                        if r["soi_id"] in _draft_sois}
            if _sh_held:
                st.info("작성중 전표에 이미 담긴 {}개 라인은 목록에서 "
                        "제외했습니다 ({}) — 수정은 출고 전표 탭에서, "
                        "다시 담으려면 해당 전표를 취소하세요.".format(
                            len(_sh_held),
                            ", ".join(sorted(set(_sh_held.values())))))
        except Exception as e:
            st.error(f"회차 조회 실패: {e}")
            _sh_rounds = []

        # 품번 검색 → 리스트 추가
        _sh_manual = st.session_state.setdefault("ship_manual", [])
        sq1, sq2 = st.columns([3, 1])
        _sh_q = sq1.text_input(
            "품번 · 품명 · 수주번호 검색 후 리스트에 추가", key="ship_q",
            placeholder="예: 8HFDV, GLAND NUT, 202607")
        _sh_cand = []
        if _sh_q.strip():
            _qq2 = _sh_q.strip()
            try:
                _sh_cand = fetch("sales_order_items",
                    "soi_id,so_id,canonical_pn,customer_part_no,"
                    "pending_qty,due_date",
                    f"pending_qty=gt.0&or=(canonical_pn.ilike.*{_qq2}*,"
                    f"customer_part_no.ilike.*{_qq2}*,"
                    f"customer_item_name.ilike.*{_qq2}*)",
                    limit=30)
                if not _sh_cand:
                    _hit_so2 = [s["so_id"] for s in fetch("sales_orders",
                        "so_id", f"so_number=ilike.*{_qq2}*", limit=20)]
                    if _hit_so2:
                        _sh_cand = fetch("sales_order_items",
                            "soi_id,so_id,canonical_pn,customer_part_no,"
                            "pending_qty,due_date",
                            "pending_qty=gt.0&so_id=in.({})".format(
                                ",".join(map(str, _hit_so2))), limit=30)
            except Exception:
                _sh_cand = []
        if _sh_cand:
            _cand_so = {s["so_id"]: s for s in fetch("sales_orders",
                "so_id,so_number,customer,status",
                "so_id=in.({})".format(
                    ",".join(str(c["so_id"]) for c in _sh_cand)),
                limit=100)}
            _sh_cand = [c for c in _sh_cand
                        if (_cand_so.get(c["so_id"], {}).get("status")
                            or "") not in ("CANCELLED", "CANCELED")]
            if _sh_cand:
                _sh_pick2 = sq1.selectbox(
                    "추가할 수주 라인", _sh_cand,
                    format_func=lambda c: "{} | {} | 미납 {:,.0f}".format(
                        c.get("canonical_pn")
                        or c.get("customer_part_no") or "-",
                        _cand_so.get(c["so_id"], {}).get("so_number", "-"),
                        float(c.get("pending_qty") or 0)),
                    key="ship_pick", label_visibility="collapsed")
                if sq2.button("리스트에 추가", key="ship_add",
                              use_container_width=True):
                    if _sh_pick2["soi_id"] in _draft_sois:
                        st.warning("작성중 전표 {} 에 이미 담긴 "
                                   "라인입니다 — 수정은 출고 전표 "
                                   "탭에서 하세요.".format(
                                       _draft_sois[_sh_pick2["soi_id"]]))
                    elif any(m["soi_id"] == _sh_pick2["soi_id"]
                             for m in _sh_manual):
                        st.toast("이미 리스트에 있는 라인입니다.")
                    else:
                        _sh_manual.append({
                            "soi_id": _sh_pick2["soi_id"],
                            "so_id": _sh_pick2["so_id"]})
                        st.rerun()
            else:
                sq1.caption("미납 라인이 없습니다.")
        elif _sh_q.strip():
            sq1.caption("검색 결과가 없습니다 — 품번 일부로 검색하세요.")

        # ── 리스트 행 구성 (스케줄 + 추가분 조인) ──
        _sh_soids = ({r["so_id"] for r in _sh_rounds}
                     | {m["so_id"] for m in _sh_manual})
        _sh_sois = ({r["soi_id"] for r in _sh_rounds}
                    | {m["soi_id"] for m in _sh_manual})
        _sh_som, _sh_lim = {}, {}
        if _sh_soids:
            try:
                _sh_som = {s["so_id"]: s for s in fetch("sales_orders",
                    "so_id,so_number,customer,status",
                    "so_id=in.({})".format(
                        ",".join(map(str, _sh_soids))), limit=300)
                    if (s.get("status") or "") not in
                    ("CANCELLED", "CANCELED")}
                _sh_lim = {l["soi_id"]: l for l in fetch(
                    "sales_order_items",
                    "soi_id,so_id,canonical_pn,customer_part_no,"
                    "customer_item_name,product_id,qty,received_qty,"
                    "pending_qty,unit,unit_price,due_date",
                    "soi_id=in.({})".format(
                        ",".join(map(str, _sh_sois))), limit=500)}
            except Exception as e:
                st.error(f"수주 조회 실패: {e}")

        _sh_items = []
        for r in _sh_rounds:
            _so = _sh_som.get(r["so_id"])
            _li2 = _sh_lim.get(r["soi_id"])
            if not _so or not _li2:
                continue
            _pend2 = float(_li2.get("pending_qty") or 0)
            _rem2 = (float(r.get("qty") or 0)
                     - float(r.get("delivered_qty") or 0))
            if _pend2 <= 0 or _rem2 <= 0:
                continue
            _sh_items.append({
                "src": "스케줄", "r": r, "li": _li2, "so": _so,
                "pn": (_li2.get("canonical_pn")
                       or _li2.get("customer_part_no") or "-"),
                "due": str(r["due_date"])[:10],
                "cap": min(_rem2, _pend2),
            })
        _sh_auto_soi = {it["li"]["soi_id"] for it in _sh_items}
        for m in _sh_manual:
            if m["soi_id"] in _sh_auto_soi or m["soi_id"] in _draft_sois:
                continue      # 작성중 전표에 담긴 라인은 재등록 금지
            _li2 = _sh_lim.get(m["soi_id"])
            _so = _sh_som.get(m["so_id"])
            if not _so or not _li2:
                continue
            _pend2 = float(_li2.get("pending_qty") or 0)
            if _pend2 <= 0:
                continue
            _sh_items.append({
                "src": "추가", "r": None, "li": _li2, "so": _so,
                "pn": (_li2.get("canonical_pn")
                       or _li2.get("customer_part_no") or "-"),
                "due": str(_li2.get("due_date") or "")[:10] or "-",
                "cap": _pend2,
            })

        if not _sh_items:
            st.info("출고 리스트가 비어 있습니다 — 스케줄 회차가 없으면 "
                    "품번 검색으로 추가하세요.")
        else:
            import pandas as _sh_pd

            # 행이 늘어나도 편집값(선택·출고 수량) 유지 (2026-08-07)
            _sh_edits = st.session_state.setdefault("ship_edits", {})

            def _sh_rowkey(it):
                return "{}:{}".format(
                    it["li"]["soi_id"],
                    it["r"]["sched_id"] if it.get("r") else "M")

            _sh_df = _sh_pd.DataFrame([{
                "선택": bool(_sh_edits.get(_sh_rowkey(it), {})
                            .get("선택", True)),
                "구분": it["src"],
                "품번": it["pn"],
                "거래처": it["so"].get("customer") or "-",
                "수주번호": it["so"].get("so_number") or "-",
                "납기": it["due"],
                "잔량": float(it["cap"]),
                "출고": min(float(_sh_edits.get(_sh_rowkey(it), {})
                               .get("출고", it["cap"])),
                           float(it["cap"])),
            } for it in _sh_items])
            _sh_sig = "{}_{}_{}_{}".format(_sh_d, _sh_late,
                                           len(_sh_items),
                                           len(_sh_manual))
            _sh_ed = st.data_editor(
                _sh_df, hide_index=True, use_container_width=True,
                key=f"bk_ed_{_sh_sig}",
                column_config={
                    "선택": st.column_config.CheckboxColumn(
                        "선택", width="small"),
                    "출고": st.column_config.NumberColumn(
                        "출고 수량", min_value=0, step=1),
                    **{c: st.column_config.Column(disabled=True)
                       for c in ("구분", "품번", "거래처", "수주번호",
                                  "납기")},
                    **{c: st.column_config.NumberColumn(
                        format="localized", disabled=True)
                       for c in ("잔량",)},
                })
            _sh_sel = []
            for _bi, _brow in _sh_ed.iterrows():
                _it = _sh_items[int(_bi)]
                _bq = float(_sh_pd.to_numeric(
                    _brow.get("출고"), errors="coerce") or 0)
                _sh_edits[_sh_rowkey(_it)] = {
                    "선택": bool(_brow.get("선택")), "출고": _bq}
                if not bool(_brow.get("선택")) or _bq <= 0:
                    continue
                _sh_sel.append((_it, min(_bq, _it["cap"])))
            _sh_total = sum(q for _, q in _sh_sel)

            _rg1, _rg2 = st.columns([1, 1])
            if _rg1.button(
                    f"출고 등록 — 전표 생성 ({_sh_total:,.0f} · "
                    f"{len(_sh_sel)}건)",
                    type="primary", key="ship_reg",
                    use_container_width=True,
                    disabled=_sh_total <= 0):
                _sd = _sh_d.isoformat()
                # 이중 클릭 가드 — 화면 구성 시점의 제외 목록은 클릭
                # 1.4초 간격의 두 번째 실행을 못 거른다 (2026-08-18
                # SH-20260817-01/-02 동일 전표 2건 사례). ① 시간 가드
                # ② insert 직전 라이브 재확인의 이중 방어.
                _dup_guard = not click_guard("ship_reg")
                try:
                    _g_drafts = fetch("shipments", "shipment_id,ship_no",
                                      "status=eq.DRAFT", limit=50)
                    if _g_drafts:
                        _g_ids = ",".join(str(d["shipment_id"])
                                          for d in _g_drafts)
                        _g_sois = {x["soi_id"] for x in fetch(
                            "shipment_items", "soi_id,shipment_id",
                            f"shipment_id=in.({_g_ids})", limit=1000)}
                        _new_sois = {it["li"]["soi_id"]
                                     for it, _ in _sh_sel}
                        _hit_g = _new_sois & _g_sois
                        if _hit_g:
                            _dup_guard = True
                            st.warning(
                                "등록 중단 — 방금 만든 작성중 전표에 "
                                "같은 라인이 이미 담겨 있습니다 "
                                "(버튼이 두 번 눌린 경우). 출고 전표 "
                                "탭에서 기존 전표를 확인하세요.")
                except Exception:
                    pass
                if not _dup_guard:
                    try:
                        _cnt = len(fetch("shipments", "shipment_id",
                                         f"ship_date=eq.{_sd}",
                                         limit=100))
                    except Exception:
                        _cnt = 0
                    _ship_no = "SH-{}-{:02d}".format(
                        _sd.replace("-", ""), _cnt + 1)
                    try:
                        _db.insert("shipments", [{
                            "ship_no": _ship_no, "ship_date": _sd,
                            "status": "DRAFT",
                            "created_by": current_user_name()}])
                        _srow = _db.fetch_one("shipments",
                                              f"ship_no=eq.{_ship_no}",
                                              "shipment_id")
                        _db.insert("shipment_items", [{
                            "shipment_id": _srow["shipment_id"],
                            "soi_id": it["li"]["soi_id"],
                            "so_id": it["so"]["so_id"],
                            "sched_id": (it["r"]["sched_id"]
                                         if it.get("r") else None),
                            "product_id": it["li"].get("product_id"),
                            "pn": it["pn"],
                            "customer_pn":
                                it["li"].get("customer_part_no")
                                or it["pn"],
                            "item_name":
                                it["li"].get("customer_item_name"),
                            "customer": it["so"].get("customer") or "-",
                            "so_number":
                                it["so"].get("so_number") or "-",
                            "qty": _q9,
                            "unit": it["li"].get("unit") or "EA",
                            "unit_price": it["li"].get("unit_price"),
                        } for it, _q9 in _sh_sel])
                        st.session_state["ship_manual"] = []
                        st.session_state["ship_edits"] = {}
                        st.session_state["ship_open_no"] = _ship_no
                        st.success(f"출고 전표 {_ship_no} 등록 — 출고 "
                                   "전표 탭에서 확인용 리스트 인쇄·정정·"
                                   "확정을 진행하세요.")
                    except Exception as e:
                        st.error(f"전표 등록 실패: {e}")
            _rg2.caption("등록 시점에는 아무것도 차감되지 않습니다 — "
                         "확정(출고 전표 탭)에서 수주 반영·재고 차감·"
                         "거래명세서 발행이 이루어집니다.")

    # ════════ TAB 2: 출고 전표 (확인 → 정정 → 확정 → 재발행) ════════
    with tab_ship:
        from datetime import date as _cf_dt
        from utils.delivery_alloc import allocate_rounds as _cf_alloc
        from utils.statement_generator import (
            delivery_list_html as _cf_list,
            transaction_statements_html as _cf_stmt)
        st.caption(
            "등록된 전표를 열어 **확인용 리스트 인쇄 → 현장 확인 → "
            "정정 저장 → 출고 확정** 순서로 진행합니다. 확정된 전표는 "
            "언제든 출고 리스트·거래명세서를 다시 발행할 수 있습니다.")

        _cf_filter = st.radio("전표 상태", ["작성중", "확정", "전체"],
                              horizontal=True, key="cf_filter",
                              label_visibility="collapsed")
        _cf_q = {"작성중": "status=eq.DRAFT", "확정": "status=eq.CONFIRMED",
                 "전체": 'status=neq.CANCELLED'}[_cf_filter]
        try:
            _cf_ships = fetch("shipments",
                "shipment_id,ship_no,ship_date,status,created_by,"
                "confirmed_at",
                _cf_q + "&order=shipment_id.desc", limit=30)
        except Exception as e:
            st.error(f"전표 조회 실패: {e}")
            _cf_ships = []
        if not _cf_ships:
            st.info("전표가 없습니다 — 출고 등록 탭에서 리스트를 담아 "
                    "등록하세요.")
        else:
            _cf_stko = {"DRAFT": "작성중", "CONFIRMED": "확정",
                        "CANCELLED": "취소"}
            _open_no = st.session_state.pop("ship_open_no", None)
            _cf_idx = 0
            if _open_no:
                for _i9, _s9 in enumerate(_cf_ships):
                    if _s9["ship_no"] == _open_no:
                        _cf_idx = _i9
                        break
            _cf_pick = st.selectbox(
                "전표 선택", _cf_ships, index=_cf_idx,
                format_func=lambda s: "{} | {} | {} | {}".format(
                    s["ship_no"], s.get("ship_date"),
                    _cf_stko.get(s.get("status"), s.get("status")),
                    s.get("created_by") or "-"),
                key="cf_pick")
            try:
                _cf_items = fetch("shipment_items",
                    "si_id,soi_id,so_id,sched_id,product_id,pn,"
                    "customer_pn,item_name,customer,so_number,qty,unit,"
                    "unit_price",
                    f"shipment_id=eq.{_cf_pick['shipment_id']}"
                    "&order=si_id.asc", limit=200)
            except Exception as e:
                st.error(f"전표 품목 조회 실패: {e}")
                _cf_items = []

            # 품명(유사 품번 착오 방지) + LOT — 확정은 원장 실적,
            # 작성중은 FIFO 예정 배분 (2026-08-10 출고 리스트 개편)
            from utils.ship_lots import names_and_lots as _cf_nl
            _cf_names, _cf_lotmap = _cf_nl(
                fetch, _cf_items,
                confirmed=(_cf_pick.get("status") == "CONFIRMED"))

            def _cf_batch(items):
                return {"date": str(_cf_pick.get("ship_date")),
                        "rows": [{
                            "pn": x.get("pn"),
                            "customer_pn": x.get("customer_pn"),
                            "item_name": x.get("item_name"),
                            "disp_name": _cf_names.get(x.get("si_id")),
                            "lots": _cf_lotmap.get(x.get("si_id")),
                            "customer": x.get("customer"),
                            "so_number": x.get("so_number"),
                            "qty": float(x.get("qty") or 0),
                            "unit": x.get("unit") or "EA",
                            "unit_price": x.get("unit_price"),
                            "date": str(_cf_pick.get("ship_date")),
                        } for x in items]}

            def _cf_vmap(items):
                out = {}
                for _cu in {x.get("customer") for x in items
                            if x.get("customer")}:
                    _term = (_cu.replace("㈜", "")
                             .replace("(주)", "").strip())
                    try:
                        _vs = fetch("vendors",
                            "name,business_no,ceo_name,phone,address,"
                            "business_type,business_item",
                            f"name=ilike.*{_term}*", limit=5)
                        if _vs:
                            out[_cu] = _vs[0]
                    except Exception:
                        pass
                return out

            if not _cf_items:
                st.info("전표에 품목이 없습니다.")
            elif _cf_pick.get("status") == "CONFIRMED":
                import pandas as _cf_pd
                st.dataframe(_cf_pd.DataFrame([{
                    "품번": x.get("pn"),
                    "품명": _cf_names.get(x.get("si_id")) or "-",
                    "LOT": _cf_lotmap.get(x.get("si_id")) or "-",
                    "거래처": x.get("customer"),
                    "수량": float(x.get("qty") or 0),
                    "단가": x.get("unit_price"),
                } for x in _cf_items]), use_container_width=True,
                    hide_index=True,
                    column_config={c: st.column_config.NumberColumn(
                        format="localized")
                        for c in ("수량", "단가")})
                st.caption("확정 {} · 처리 {}".format(
                    str(_cf_pick.get("confirmed_at") or "")[:16],
                    _cf_pick.get("created_by") or "-"))
                pr1, pr2 = st.columns(2)
                pr1.download_button(
                    "출고 리스트 재발행", _cf_list(_cf_batch(_cf_items)),
                    file_name=f"출고리스트_{_cf_pick['ship_no']}.html",
                    mime="text/html", key="cf_dl_list",
                    use_container_width=True)
                pr2.download_button(
                    "거래명세서 재발행",
                    _cf_stmt(_cf_batch(_cf_items), _cf_vmap(_cf_items)),
                    file_name=f"거래명세서_{_cf_pick['ship_no']}.html",
                    mime="text/html", key="cf_dl_stmt", type="primary",
                    use_container_width=True)
            else:
                # ── DRAFT: 확인용 인쇄 → 정정 저장 → 확정 ──
                import pandas as _cf_pd
                _cf_df = _cf_pd.DataFrame([{
                    "선택": True, "품번": x.get("pn"),
                    "품명": _cf_names.get(x.get("si_id")) or "-",
                    "거래처": x.get("customer"),
                    "수량": float(x.get("qty") or 0),
                } for x in _cf_items])
                _cf_ed = st.data_editor(
                    _cf_df, hide_index=True, use_container_width=True,
                    key="cf_ed_{}_{}".format(_cf_pick["shipment_id"],
                                             len(_cf_items)),
                    column_config={
                        "선택": st.column_config.CheckboxColumn(
                            "선택", width="small"),
                        "수량": st.column_config.NumberColumn(
                            "수량 (정정)", min_value=0, step=1),
                        **{c: st.column_config.Column(disabled=True)
                           for c in ("품번", "품명", "거래처")},
                    })
                ac1, ac2, ac3 = st.columns([1, 1, 1])
                ac1.download_button(
                    "확인용 리스트 인쇄",
                    _cf_list(_cf_batch(_cf_items), draft=True),
                    file_name="출고리스트_확인용_{}.html".format(
                        _cf_pick["ship_no"]),
                    mime="text/html", key="cf_dl_draft",
                    use_container_width=True)
                if ac2.button("정정 저장", key="cf_save",
                              use_container_width=True):
                    _n_upd, _n_del = 0, 0
                    for _bi, _brow in _cf_ed.iterrows():
                        _x = _cf_items[int(_bi)]
                        if not bool(_brow.get("선택")):
                            try:
                                _db.delete("shipment_items",
                                           f"si_id=eq.{_x['si_id']}")
                                _n_del += 1
                            except Exception:
                                pass
                            continue
                        _nq = float(_cf_pd.to_numeric(
                            _brow.get("수량"), errors="coerce") or 0)
                        if abs(_nq - float(_x.get("qty") or 0)) > 1e-9:
                            try:
                                _db.update("shipment_items",
                                           f"si_id=eq.{_x['si_id']}",
                                           {"qty": _nq})
                                _n_upd += 1
                            except Exception:
                                pass
                    st.success(f"정정 저장 — 수정 {_n_upd} · 제외 {_n_del}")
                    st.rerun()
                _cf_over = ac3.checkbox("재고 없이 출고 허용",
                                        value=False, key="cf_over",
                                        help="ERP 이관 전 생산분 등 — "
                                             "완성 재고와 무관하게 확정")

                # ── 확정: 수주 반영 + 회차 충당 + 재고 차감 + 명세서 ──
                _cf_rows = [( _x, float(_x.get("qty") or 0))
                            for _x in _cf_items
                            if float(_x.get("qty") or 0) > 0]
                _cf_total = sum(q for _, q in _cf_rows)
                _cf_pids = {x.get("product_id") for x, _ in _cf_rows
                            if x.get("product_id")}
                _cf_stock, _cf_lots = {}, {}
                if _cf_pids:
                    _cf_pstr = ",".join(f'"{p}"' for p in _cf_pids)
                    try:
                        _cf_stock = {s["product_id"]:
                                     float(s.get("current_stock") or 0)
                                     for s in fetch("product_stock_v",
                                         "product_id,current_stock",
                                         f"product_id=in.({_cf_pstr})",
                                         limit=300)}
                        for _l in fetch("product_lot_stock_v",
                                "product_id,lot_number,remain_qty",
                                f"product_id=in.({_cf_pstr})"
                                "&remain_qty=gt.0"
                                "&order=first_output_date.asc,"
                                "lot_number.asc", limit=500):
                            _cf_lots.setdefault(
                                _l["product_id"], []).append(_l)
                    except Exception:
                        pass
                _cf_short = {}
                if not _cf_over:
                    _byp = {}
                    for _x, _q in _cf_rows:
                        if _x.get("product_id"):
                            _byp[_x["product_id"]] = (
                                _byp.get(_x["product_id"], 0) + _q)
                    _pid_pn2 = {x.get("product_id"): x.get("pn")
                                for x, _ in _cf_rows}
                    _cf_short = {(_pid_pn2.get(p) or p):
                                 (q, _cf_stock.get(p, 0))
                                 for p, q in _byp.items()
                                 if q > _cf_stock.get(p, 0) + 1e-9}
                if _cf_short:
                    st.error("완성 재고 부족 — " + ", ".join(
                        f"{p}: 출고 {q:,.0f} > 재고 {s:,.0f}"
                        for p, (q, s) in _cf_short.items())
                        + ". 수량을 정정하거나 '재고 없이 출고 허용'을 "
                          "체크하세요.")
                if st.button(
                        f"출고 확정 ({_cf_total:,.0f} · "
                        f"{len(_cf_rows)}건) — 수주 반영·재고 차감·"
                        "명세서 발행",
                        type="primary", key="cf_go",
                        disabled=(_cf_total <= 0 or bool(_cf_short))
                        ) and click_guard("cf_go"):
                    _cf_date = str(_cf_pick.get("ship_date"))
                    # 라인 단위 합산
                    _by_soi = {}
                    for _x, _q in _cf_rows:
                        _e = _by_soi.setdefault(_x["soi_id"],
                                                {"x": _x, "q": 0.0})
                        _e["q"] += _q
                    _sois_str = ",".join(str(s) for s in _by_soi)
                    _fresh = {l["soi_id"]: l for l in fetch(
                        "sales_order_items",
                        "soi_id,so_id,qty,received_qty,pending_qty,unit",
                        f"soi_id=in.({_sois_str})", limit=200)}
                    _cf_ok, _cf_txns = 0, []
                    _lot_used = {}
                    for _soi5, _e in _by_soi.items():
                        _x5 = _e["x"]
                        _li5 = _fresh.get(_soi5)
                        if not _li5:
                            continue
                        _q5 = min(_e["q"],
                                  float(_li5.get("pending_qty") or 0))
                        if _q5 <= 0:
                            continue
                        _qty5 = float(_li5.get("qty") or 0)
                        _nr = float(_li5.get("received_qty") or 0) + _q5
                        _np = max(_qty5 - _nr, 0)
                        _ns = ("DELIVERED" if _nr >= _qty5
                               else "PARTIAL" if _nr > 0 else "PENDING")
                        try:
                            if not _db.update("sales_order_items",
                                    f"soi_id=eq.{_soi5}",
                                    {"received_qty": _nr,
                                     "pending_qty": _np, "status": _ns}):
                                continue
                        except Exception as e:
                            st.warning(f"{_x5.get('pn')} 반영 실패: {e}")
                            continue
                        _cf_ok += 1
                        try:
                            _rr = fetch("so_delivery_schedule",
                                "sched_id,due_date,qty,delivered_qty",
                                f"soi_id=eq.{_soi5}"
                                "&order=due_date.asc,seq.asc", limit=100)
                            for _sid6, _nd in _cf_alloc(
                                    _rr, _q5, _cf_date).items():
                                _db.update("so_delivery_schedule",
                                           f"sched_id=eq.{_sid6}",
                                           {"delivered_qty": _nd})
                        except Exception:
                            pass
                        _pid5 = _x5.get("product_id")
                        if _pid5:
                            _left5 = _q5
                            for _lot5 in _cf_lots.get(_pid5, []):
                                if _left5 <= 0:
                                    break
                                _lr = (float(_lot5.get("remain_qty") or 0)
                                       - _lot_used.get(
                                           (_pid5, _lot5["lot_number"]),
                                           0))
                                _tk = min(_left5, max(_lr, 0))
                                if _tk <= 0:
                                    continue
                                _lot_used[(_pid5,
                                           _lot5["lot_number"])] = \
                                    _lot_used.get(
                                        (_pid5, _lot5["lot_number"]),
                                        0) + _tk
                                _cf_txns.append({
                                    "material_id": None,
                                    "product_id": _pid5,
                                    "txn_type": "ISSUE", "qty": -_tk,
                                    "unit": _li5.get("unit") or "EA",
                                    "lot_number": _lot5["lot_number"],
                                    "work_order": _lot5["lot_number"],
                                    "ref_table": "shipment_items",
                                    "ref_id": _x5["si_id"],
                                    "txn_date": _cf_date,
                                    "remark": "출고 {}: {}".format(
                                        _cf_pick["ship_no"],
                                        _x5.get("so_number") or "-"),
                                    "created_by": current_user_name(),
                                })
                                _left5 -= _tk
                            if _left5 > 1e-9:
                                _cf_txns.append({
                                    "material_id": None,
                                    "product_id": _pid5,
                                    "txn_type": "ISSUE", "qty": -_left5,
                                    "unit": _li5.get("unit") or "EA",
                                    "lot_number": None,
                                    "work_order": None,
                                    "ref_table": "shipment_items",
                                    "ref_id": _x5["si_id"],
                                    "txn_date": _cf_date,
                                    "remark": "출고 {}: {} (LOT 미지정)"
                                    .format(_cf_pick["ship_no"],
                                            _x5.get("so_number") or "-"),
                                    "created_by": current_user_name(),
                                })
                    if _cf_txns:
                        try:
                            _db.insert("inventory_transactions",
                                       _cf_txns)
                        except Exception as e:
                            st.warning(
                                f"재고 차감 기록 실패 (납품은 정상): {e}")
                    for _sid7 in {e["x"]["so_id"]
                                  for e in _by_soi.values()
                                  if e["x"].get("so_id")}:
                        try:
                            _fr = fetch("sales_order_items",
                                        "qty,received_qty",
                                        f"so_id=eq.{_sid7}", limit=100)
                            _all7 = all(
                                float(x.get("received_qty") or 0)
                                >= float(x.get("qty") or 0)
                                for x in _fr) if _fr else False
                            _any7 = any(
                                float(x.get("received_qty") or 0) > 0
                                for x in _fr) if _fr else False
                            _db.update("sales_orders",
                                       f"so_id=eq.{_sid7}",
                                       {"status": "DELIVERED" if _all7
                                        else "PARTIAL" if _any7
                                        else "CONFIRMED"})
                        except Exception:
                            pass
                    if _cf_ok:
                        from datetime import datetime as _cf_now
                        try:
                            _db.update("shipments",
                                "shipment_id=eq.{}".format(
                                    _cf_pick["shipment_id"]),
                                {"status": "CONFIRMED",
                                 "confirmed_at":
                                 _cf_now.now().isoformat()})
                        except Exception:
                            pass
                        st.session_state["ship_open_no"] = \
                            _cf_pick["ship_no"]
                        st.success(
                            f"출고 확정 — {_cf_ok}개 라인 · "
                            f"{_cf_total:,.0f}개. 아래에서 거래명세서를 "
                            "발행하세요.")
                        st.rerun()
                if st.button("전표 취소", key="cf_cancel"):
                    try:
                        _db.update("shipments",
                                   "shipment_id=eq.{}".format(
                                       _cf_pick["shipment_id"]),
                                   {"status": "CANCELLED"})
                        st.success("전표 취소됨")
                        st.rerun()
                    except Exception as e:
                        st.error(f"취소 실패: {e}")

    # ════════ TAB 3: 출고 현황 (확정 전표 기준 품목별 조회) ════════
    with tab_dstat:
        st.caption(
            "**확정 전표 기준 출고 조회** — 품목별 집계·출고 이력·수주별 "
            "대사(전표 외 기납품 구분)까지 확인합니다. 수주 진행 KPI 는 "
            "홈·수주 관리에서.")

        from datetime import date as _dv_dt, timedelta as _dv_td
        from utils.ship_lots import issued_lots as _dv_lots_fn

        _dv_preset = st.radio(
            "기간", ["최근 7일", "최근 30일", "이번 달", "전체"],
            index=1, horizontal=True, key="dstat_range",
            label_visibility="collapsed")
        _dv_today = _dv_dt.today()
        _dv_from = {
            "최근 7일": (_dv_today - _dv_td(days=6)).isoformat(),
            "최근 30일": (_dv_today - _dv_td(days=29)).isoformat(),
            "이번 달": _dv_today.replace(day=1).isoformat(),
            "전체": None,
        }[_dv_preset]

        try:
            _dv_cond = "status=eq.CONFIRMED"
            if _dv_from:
                _dv_cond += f"&ship_date=gte.{_dv_from}"
            _dv_ships = fetch(
                "shipments", "shipment_id,ship_no,ship_date,created_by",
                _dv_cond + "&order=ship_date.desc,shipment_id.desc",
                limit=300)
        except Exception as e:
            st.error(f"출고 조회 실패: {e}"); _dv_ships = []

        if not _dv_ships:
            st.info("기간 내 확정 전표 없음 — 기간을 넓히거나 출고 전표 "
                    "탭에서 확정하세요.")
        else:
            _dv_smap = {s["shipment_id"]: s for s in _dv_ships}
            _dv_rows = []
            _dv_ids = list(_dv_smap)
            for _i0 in range(0, len(_dv_ids), 50):
                _ck = ",".join(str(x) for x in _dv_ids[_i0:_i0 + 50])
                try:
                    for x in fetch(
                            "shipment_items",
                            "si_id,shipment_id,soi_id,product_id,pn,"
                            "item_name,customer,so_number,qty",
                            f"shipment_id=in.({_ck})&order=si_id.desc",
                            limit=2000):
                        _s0 = _dv_smap.get(x["shipment_id"]) or {}
                        x["ship_no"] = _s0.get("ship_no")
                        x["ship_date"] = _s0.get("ship_date")
                        x["by"] = _s0.get("created_by")
                        _dv_rows.append(x)
                except Exception:
                    pass

            # 품명 (사내 정본 우선) · LOT (원장 ISSUE 실적)
            _dv_pn_nm = {}
            try:
                _dv_pns = sorted({r["pn"] for r in _dv_rows if r.get("pn")})
                for _i0 in range(0, len(_dv_pns), 80):
                    _dv_pn_nm.update({
                        p["pn"]: (p.get("item_name")
                                  or p.get("sub_class"))
                        for p in fetch(
                            "products", "pn,item_name,sub_class",
                            "pn=in.({})".format(",".join(
                                f'"{x}"' for x in _dv_pns[_i0:_i0 + 80])),
                            limit=300)})
            except Exception:
                pass

            def _dv_name(r):
                return (_dv_pn_nm.get(r.get("pn"))
                        or r.get("item_name") or "-")

            _dv_lot_map = {}
            try:
                _si_ids = [r["si_id"] for r in _dv_rows]
                _tx0 = []
                for _i0 in range(0, len(_si_ids), 80):
                    _tx0 += fetch(
                        "inventory_transactions", "ref_id,lot_number,qty",
                        "ref_table=eq.shipment_items&txn_type=eq.ISSUE"
                        "&ref_id=in.({})".format(",".join(
                            str(x) for x in _si_ids[_i0:_i0 + 80])),
                        limit=2000)
                _dv_lot_map = _dv_lots_fn(_tx0)
            except Exception:
                pass

            _dv_q = st.text_input(
                "출고 검색", key="dstat_q", label_visibility="collapsed",
                placeholder="검색 — 품번 · 품명 · 거래처 · 수주번호 · 전표")
            if (_dv_q or "").strip():
                _q0 = _dv_q.strip().lower()
                _dv_rows = [r for r in _dv_rows if any(
                    _q0 in str(v).lower() for v in (
                        r.get("pn"), _dv_name(r), r.get("customer"),
                        r.get("so_number"), r.get("ship_no")))]

            _dv_sum = sum(float(r.get("qty") or 0) for r in _dv_rows)
            _dv_nship = len({r["shipment_id"] for r in _dv_rows})
            _dv_npn = len({r.get("pn") for r in _dv_rows})
            _dv_ncust = len({r.get("customer") for r in _dv_rows
                             if r.get("customer")})

            def _dv_kpi(label, value, sub="", tone="primary"):
                _v = (value if isinstance(value, str)
                      else f"{value:,.0f}")
                _z = (not isinstance(value, str)) and value <= 0
                cls = "zero" if _z else tone
                return (f'<div class="kpi {cls}"><div class="k">{label}'
                        f'</div><div class="v">{_v}</div>'
                        + (f'<div class="s">{sub}</div>' if sub else "")
                        + "</div>")

            st.markdown(
                '<div class="kpi-row">'
                + _dv_kpi("출고 수량", _dv_sum, _dv_preset, "good")
                + _dv_kpi("전표", f"{_dv_nship}건")
                + _dv_kpi("품목", f"{_dv_npn}종")
                + _dv_kpi("거래처", f"{_dv_ncust}곳")
                + "</div>", unsafe_allow_html=True)

            _dv_view = st.radio(
                "보기", ["품목별", "출고 이력"], horizontal=True,
                key="dstat_view", label_visibility="collapsed")

            if _dv_view == "품목별":
                # ── 품목별 집계 ──
                _dv_agg = {}
                for r in _dv_rows:
                    _a = _dv_agg.setdefault(r.get("pn") or "-", {
                        "qty": 0.0, "n": 0, "last": "",
                        "cust": set()})
                    _a["qty"] += float(r.get("qty") or 0)
                    _a["n"] += 1
                    _a["last"] = max(_a["last"],
                                     str(r.get("ship_date") or ""))
                    if r.get("customer"):
                        _a["cust"].add(r["customer"])
                st.dataframe(pd.DataFrame([{
                    "품번": pn,
                    "품명": _dv_pn_nm.get(pn) or "-",
                    "거래처": ", ".join(sorted(a["cust"])) or "-",
                    "출고 수량": a["qty"],
                    "횟수": a["n"],
                    "최근 출고일": a["last"] or "-",
                } for pn, a in sorted(_dv_agg.items(),
                                      key=lambda kv: -kv[1]["qty"])]),
                    use_container_width=True, hide_index=True,
                    height=min(400, 60 + len(_dv_agg) * 35),
                    column_config={
                        "출고 수량": st.column_config.NumberColumn(
                            format="localized"),
                        "횟수": st.column_config.NumberColumn(
                            width="small")})

                # ── 품번 상세: 출고 라인 + 수주별 대사 ──
                _dv_pick = st.selectbox(
                    "품번 상세", sorted(_dv_agg),
                    format_func=lambda p: "{} · {}".format(
                        p, _dv_pn_nm.get(p) or "-"),
                    key="dstat_pick")
                if _dv_pick:
                    _dv_det = [r for r in _dv_rows
                               if r.get("pn") == _dv_pick]
                    st.markdown("**출고 라인 (기간 내)**")
                    st.dataframe(pd.DataFrame([{
                        "출고일": r.get("ship_date"),
                        "전표": r.get("ship_no"),
                        "수주번호": r.get("so_number") or "-",
                        "수량": float(r.get("qty") or 0),
                        "LOT": _dv_lot_map.get(r["si_id"]) or "-",
                        "처리자": r.get("by") or "-",
                    } for r in _dv_det]), use_container_width=True,
                        hide_index=True,
                        column_config={
                            "수량": st.column_config.NumberColumn(
                                format="localized")})

                    # 수주별 대사 — 기납품 중 전표 출고와 전표 외
                    # (런칭 전 소급·업로드) 를 구분해 표시
                    st.markdown("**수주별 대사 (누적 기준)**")
                    try:
                        _dv_sois = fetch(
                            "sales_order_items",
                            "soi_id,so_id,qty,received_qty,pending_qty",
                            f"canonical_pn=eq.{_dv_pick}"
                            "&order=soi_id.asc", limit=100)
                    except Exception:
                        _dv_sois = []
                    if not _dv_sois:
                        st.caption("이 품번의 수주 라인 없음.")
                    else:
                        _dv_so_nm = {}
                        try:
                            _so_ids = {s["so_id"] for s in _dv_sois}
                            _dv_so_nm = {
                                s["so_id"]:
                                    (s.get("so_number"),
                                     s.get("customer"))
                                for s in fetch(
                                    "sales_orders",
                                    "so_id,so_number,customer",
                                    "so_id=in.({})".format(",".join(
                                        str(i) for i in _so_ids)),
                                    limit=200)}
                        except Exception:
                            pass
                        # 전표 출고 누적 (기간 무관 — 전체 확정 전표)
                        _dv_ship_sum = {}
                        try:
                            _soi_str = ",".join(
                                str(s["soi_id"]) for s in _dv_sois)
                            _all_li = fetch(
                                "shipment_items",
                                "soi_id,shipment_id,qty",
                                f"soi_id=in.({_soi_str})", limit=1000)
                            _sh_st = {}
                            _sh_ids2 = {x["shipment_id"]
                                        for x in _all_li}
                            if _sh_ids2:
                                _sh_st = {s["shipment_id"]: s["status"]
                                          for s in fetch(
                                        "shipments",
                                        "shipment_id,status",
                                        "shipment_id=in.({})".format(
                                            ",".join(str(i) for i in
                                                     _sh_ids2)),
                                        limit=300)}
                            for x in _all_li:
                                if _sh_st.get(
                                        x["shipment_id"]) == "CONFIRMED":
                                    _dv_ship_sum[x["soi_id"]] = (
                                        _dv_ship_sum.get(x["soi_id"], 0)
                                        + float(x.get("qty") or 0))
                        except Exception:
                            pass
                        _dv_rc = []
                        for s in _dv_sois:
                            _rcv = float(s.get("received_qty") or 0)
                            _shp = _dv_ship_sum.get(s["soi_id"], 0.0)
                            _no, _cu = _dv_so_nm.get(
                                s["so_id"], ("-", "-"))
                            _dv_rc.append({
                                "수주번호": _no, "거래처": _cu,
                                "수주": float(s.get("qty") or 0),
                                "기납품": _rcv,
                                "전표 출고": _shp,
                                "전표 외 기납품": max(_rcv - _shp, 0),
                                "미납": float(
                                    s.get("pending_qty") or 0),
                            })
                        st.dataframe(pd.DataFrame(_dv_rc),
                            use_container_width=True, hide_index=True,
                            column_config={c:
                                st.column_config.NumberColumn(
                                    format="localized", width="small")
                                for c in ("수주", "기납품", "전표 출고",
                                          "전표 외 기납품", "미납")})
                        if any(r["전표 외 기납품"] > 0 for r in _dv_rc):
                            st.caption(
                                "**전표 외 기납품** = 런칭 전 실적 "
                                "(수주 업로드 스냅샷·기납품 소급) — "
                                "앱 전표 없이 기납품에만 반영된 물량. "
                                "회차 표의 납품완료가 전표보다 많아 "
                                "보이는 이유입니다.")
            else:
                # ── 출고 이력 (라인 단위 시간순) ──
                st.dataframe(pd.DataFrame([{
                    "출고일": r.get("ship_date"),
                    "전표": r.get("ship_no"),
                    "품번": r.get("pn"),
                    "품명": _dv_name(r),
                    "거래처": r.get("customer") or "-",
                    "수주번호": r.get("so_number") or "-",
                    "수량": float(r.get("qty") or 0),
                    "LOT": _dv_lot_map.get(r["si_id"]) or "-",
                    "처리자": r.get("by") or "-",
                } for r in _dv_rows]), use_container_width=True,
                    hide_index=True,
                    height=min(500, 60 + len(_dv_rows) * 35),
                    column_config={
                        "수량": st.column_config.NumberColumn(
                            format="localized")})

        # ── 완성 LOT별 재고 (출고 순서) ──
        with st.expander("완성 LOT별 재고 (출고 순서 · FIFO)",
                         expanded=False):
            st.caption("출고는 완성일이 빠른 LOT부터 자동 배분됩니다. "
                       "LOT = 작업지시 번호이며, 소재 식별 번호까지 "
                       "연결되어 클레임 시 역추적이 가능합니다.")
            try:
                _ls = fetch("product_lot_stock_v",
                    "pn,lot_number,produced_qty,issued_qty,remain_qty,"
                    "first_output_date,tokusai_qty,material_lot",
                    "remain_qty=gt.0&order=pn.asc,first_output_date.asc",
                    limit=300)
            except Exception:
                _ls = []
            if not _ls:
                st.caption("출고 가능한 완성 LOT 없음.")
            else:
                st.dataframe(pd.DataFrame([{
                    "품번": l["pn"],
                    "완성 LOT (작업지시)": l["lot_number"],
                    "소재 LOT": l.get("material_lot") or "-",
                    "완성일": l.get("first_output_date") or "-",
                    "완성": float(l.get("produced_qty") or 0),
                    "출고": float(l.get("issued_qty") or 0),
                    "잔여": float(l.get("remain_qty") or 0),
                    "특채": float(l.get("tokusai_qty") or 0),
                } for l in _ls]), use_container_width=True,
                    hide_index=True,
                    height=min(400, 60 + len(_ls) * 35),
                    column_config={c: st.column_config.NumberColumn(
                        format="localized", width="small")
                        for c in ["완성", "출고", "잔여", "특채"]})


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
    total_mat_cover = sum(
        min(info["required"],
            float(mat_map.get(mid, {}).get("stock_qty") or 0))
        for mid, info in mat_req.items())
    shortage_count = sum(1 for mid, info in mat_req.items()
                          if info["required"] - (mat_map.get(mid, {}).get("stock_qty") or 0) > 0)
    sc1, sc2, sc3, sc4, sc5, sc6 = st.columns(6)
    sc1.metric("미납 수주 품목", len(sois))
    sc2.metric("BOM 매핑된 품목", items_with_bom)
    sc3.metric("완성 재고 충당",
               f"{total_prod_stock_used:,.0f}",
               help="제품 완성 재고(product_stock_v)로 생산 없이 출고 "
                    "가능한 수량 — 자재 필요량 계산에서 제외됨")
    sc4.metric("소재 재고 충당", f"{total_mat_cover:,.0f}",
               help="자재 실재고(material_stock)로 충당되는 필요량 — "
                    "발주 필요량 = 총필요량 − 소재 재고")
    sc5.metric("필요 자재 종류", len(mat_req))
    sc6.metric("🔴 자재 부족", shortage_count, delta_color="inverse")
    st.caption(
        "ℹ️ 총필요량 = **순생산필요** (미납수량 − 제품 완성 재고) × BOM → "
        "**발주 필요량 = 총필요량 − 소재 실재고** (원장 material_stock). "
        "완성 재고와 소재 재고가 모두 차감된 값이 발주 기준입니다.")

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
                "총필요량": round(req, 2),
                "소재 재고": round(stock, 2),
                "재고 충당": round(min(req, max(stock, 0)), 2),
                "발주 필요량": round(shortage, 2),
                "주공급사": (mat.get("main_supplier") or "-")[:30],
                "사용 제품수": len(info["by_pid"]),
                "수주 건수": len(info["by_so"]),
            })
        # 발주 필요량 큰 순
        rows.sort(key=lambda x: -x["발주 필요량"])
        df = pd.DataFrame(rows)

        if not df.empty:
            # 예외 중심 강조 — 부족 행은 옅은 붉은 배경, 발주 필요량은 진한 빨강
            def _hl_short(row):
                css = ("background-color:#fef1f1"
                       if row["발주 필요량"] > 0 else "")
                return [css] * len(row)
            _styled = (df.style
                       .apply(_hl_short, axis=1)
                       .map(lambda v: "color:#f04452;font-weight:700"
                            if isinstance(v, (int, float)) and v > 0 else "color:#8b95a1",
                            subset=["발주 필요량"])
                       .format({"총필요량": "{:,.0f}", "소재 재고": "{:,.0f}",
                                "재고 충당": "{:,.0f}",
                                "발주 필요량": "{:,.0f}"}))
            st.dataframe(_styled, use_container_width=True, hide_index=True)

            shortage_rows = [r for r in rows if r["발주 필요량"] > 0]
            if shortage_rows:
                st.warning(f"🔴 자재 부족 {len(shortage_rows)}건 — '발주 자동 제안' 탭에서 발주서 생성 가능")
            else:
                st.success("✅ 전 자재 소재 재고로 충당 가능 — 발주 필요 "
                           "없음.")

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
            # 최근 발주 이력에서 자재별 실제 거래처 역산 (2026-07-28)
            # — materials.main_supplier 는 대부분 비어 있어(308중 88)
            #   자동 제안이 전부 '(미정)' 으로 뭉치는 문제가 있었다.
            _mid_vendor = {}
            try:
                _po_hist = fetch("purchase_order_items",
                    "material_id,po_id",
                    "material_id=not.is.null&order=poi_id.desc", limit=1000)
                _po_ids = list({x["po_id"] for x in _po_hist
                                if x.get("po_id")})
                if _po_ids:
                    _pv = {p["po_id"]: p.get("vendor_id") for p in fetch(
                        "purchase_orders", "po_id,vendor_id",
                        "po_id=in.(" + ",".join(str(i) for i in _po_ids)
                        + ")", limit=500)}
                    _vids = list({v for v in _pv.values() if v})
                    _vn = {}
                    if _vids:
                        _vn = {v["vendor_id"]: v["name"] for v in fetch(
                            "vendors", "vendor_id,name",
                            "vendor_id=in.("
                            + ",".join(str(i) for i in _vids) + ")",
                            limit=500)}
                    for x in _po_hist:   # poi_id desc → 최신이 먼저
                        m = x["material_id"]
                        if m not in _mid_vendor:
                            nm = _vn.get(_pv.get(x.get("po_id")))
                            if nm:
                                _mid_vendor[m] = nm
            except Exception:
                pass
            for s in shortage_list:
                if s["supplier"] in ("(미정)", ""):
                    hit = _mid_vendor.get(s["material_id"])
                    if hit:
                        s["supplier"] = hit
                        s["supplier_src"] = "발주 이력"

            # 거래처별 묶음
            by_supplier = _dd(list)
            for s in shortage_list:
                by_supplier[s["supplier"]].append(s)

            _n_undef = len(by_supplier.get("(미정)", []))
            if _n_undef:
                st.info(
                    f"거래처 미지정 자재 {_n_undef}건 — 마스터에 주공급사가 "
                    "없고 발주 이력도 없는 자재입니다. 아래에서 거래처를 "
                    "직접 고르면 그대로 발주서에 담깁니다. (자주 쓰는 "
                    "자재는 마스터 관리 → 자재 편집에서 주공급사를 "
                    "등록해 두세요.)")

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

                    # 거래처 미지정이면 직접 고를 수 있게 (발주 불가 방지)
                    _target = supplier
                    if supplier == "(미정)":
                        try:
                            _vopts = [v["name"] for v in fetch(
                                "vendors", "name",
                                "in_use=eq.true&vendor_group=like.MAT*"
                                "&order=name", limit=300)]
                        except Exception:
                            _vopts = []
                        if not _vopts:
                            try:
                                _vopts = [v["name"] for v in fetch(
                                    "vendors", "name",
                                    "in_use=eq.true&order=name", limit=300)]
                            except Exception:
                                _vopts = []
                        _target = st.selectbox(
                            "발주할 거래처 선택", ["(선택하세요)"] + _vopts,
                            key=f"po_vsel_{supplier}")

                    if st.button(f"➕ 발주서 작성 화면으로 (이 {len(mats)}건)",
                                 key=f"go_po_{supplier}",
                                 disabled=_target in ("(선택하세요)",
                                                      "(미정)")):
                        # session_state로 발주 화면에 미리 채울 데이터 전달
                        st.session_state["po_prefill_vendor_name"] = _target
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
                        st.success(f"✅ '{_target}'의 {len(mats)}개 품목이 발주서 작성에 임시 저장됨. "
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

    # ════════════ TAB 3: 입고 현황 (입고일 기준 보유 자재) ════════════
    with tab_rstat:
        st.caption(
            "**입고된 자재를 입고일 기준으로 확인합니다.** 리스트에서 "
            "라벨 재발행·입고 취소까지 처리하고, 투입은 공정 관리 → "
            "투입 등록에서 진행합니다.")

        # ── 데이터 로드 ──
        from datetime import date as _rs_dt, timedelta as _rs_td
        try:
            _rs = fetch("po_item_receipt_v",
                "po_id,po_number,line_no,item_name,ordered_qty,"
                "received_qty,pending_qty,receipt_status",
                "order=po_id.desc,line_no.asc", limit=300)
        except Exception as e:
            st.error(f"입고 현황 조회 실패: {e}"); _rs = []
        try:
            _ms = fetch("material_stock",
                "material_id,raw_name,main_supplier,current_stock,"
                "total_received,total_consumed,last_txn_date",
                "order=material_id", limit=1000)
        except Exception:
            _ms = []
        try:
            _lots = fetch("material_stock_by_lot",
                          "material_id,lot_number,lot_balance,last_date",
                          "order=lot_number.desc", limit=1000)
        except Exception:
            _lots = []
        try:
            _rcpts = fetch("inventory_transactions",
                "txn_id,material_id,qty,unit,lot_number,ref_id,txn_date,"
                "remark",
                "txn_type=eq.RECEIPT&material_id=not.is.null"
                "&order=txn_date.desc,txn_id.desc", limit=300)
        except Exception:
            _rcpts = []
        _wk_from = (_rs_dt.today() - _rs_td(days=6)).isoformat()

        _wait_rows = [r for r in _rs
                      if r.get("receipt_status") != "RECEIVED"
                      and float(r.get("pending_qty") or 0) > 0]
        _q_pend = sum(float(r.get("pending_qty") or 0) for r in _wait_rows)
        _hold = [m for m in _ms
                 if abs(float(m.get("current_stock") or 0)) > 1e-9]
        _hold_pos = [m for m in _hold if float(m["current_stock"]) > 0]
        _wk_sum = sum(float(r.get("qty") or 0) for r in _rcpts
                      if str(r.get("txn_date") or "") >= _wk_from)
        _lots_w = [l for l in _lots
                   if str(l.get("lot_number") or "").startswith("W")]
        _lot_bal = {l["lot_number"]: float(l.get("lot_balance") or 0)
                    for l in _lots_w}
        _lots_open = [l for l in _lots_w
                      if float(l.get("lot_balance") or 0) > 0]
        _m_name = {m["material_id"]: m.get("raw_name") for m in _ms}

        def _rk(label, value, sub="", tone="primary"):
            _v = value if isinstance(value, str) else f"{value:,.0f}"
            _z = (not isinstance(value, str)) and value <= 0
            cls = "zero" if _z else tone
            return (f'<div class="kpi {cls}"><div class="k">{label}</div>'
                    f'<div class="v">{_v}</div>'
                    + (f'<div class="s">{sub}</div>' if sub else "")
                    + "</div>")

        st.markdown(
            '<div class="kpi-row">'
            + _rk("입고 대기", _q_pend,
                  f"{len(_wait_rows)}개 라인 — 입고 처리 탭", "warn")
            + _rk("최근 7일 입고", _wk_sum)
            + _rk("보유 소재", f"{len(_hold_pos)}종",
                  "총 {:,.0f}".format(sum(
                      float(m["current_stock"]) for m in _hold_pos)), "good")
            + _rk("투입 대기 LOT", f"{len(_lots_open)}건",
                  "공정 관리 → 투입 등록")
            + "</div>", unsafe_allow_html=True)

        # ── 보유 자재 (입고일 기준) — 라벨 재발행·입고 취소 ──
        st.markdown("##### 보유 자재 (입고일 기준)")
        if not _rcpts:
            st.info("입고 이력 없음 — [입고 처리] 탭에서 입고하면 "
                    "여기에 입고일 순으로 쌓입니다.")
        else:
            # 발주 라인(품명·규격)·헤더(발주번호·거래처) 역조인
            _poi_m, _po_hdr9, _v_nm9 = {}, {}, {}
            try:
                _poi_ids9 = {r["ref_id"] for r in _rcpts if r.get("ref_id")}
                if _poi_ids9:
                    _poi_m = {p["poi_id"]: p for p in fetch(
                        "purchase_order_items",
                        "poi_id,item_name,spec,po_id",
                        "poi_id=in.({})".format(
                            ",".join(str(i) for i in _poi_ids9)),
                        limit=500)}
                _po_ids9 = {p["po_id"] for p in _poi_m.values()}
                if _po_ids9:
                    _po_hdr9 = {p["po_id"]: p for p in fetch(
                        "purchase_orders", "po_id,po_number,vendor_id",
                        "po_id=in.({})".format(
                            ",".join(str(i) for i in _po_ids9)),
                        limit=500)}
                _v_ids9 = {p.get("vendor_id") for p in _po_hdr9.values()
                           if p.get("vendor_id")}
                if _v_ids9:
                    _v_nm9 = {v["vendor_id"]: v["name"] for v in fetch(
                        "vendors", "vendor_id,name",
                        "vendor_id=in.({})".format(
                            ",".join(str(i) for i in _v_ids9)),
                        limit=500)}
            except Exception:
                pass
            # 공정 투입 현황 (wo_tracking)
            _wo_by_lot = {}
            try:
                _wl_ids = sorted({r["lot_number"] for r in _rcpts
                                  if str(r.get("lot_number") or ""
                                         ).startswith("W")})
                for _i0 in range(0, len(_wl_ids), 50):
                    for w in fetch("wo_tracking", "w_lot,pn,status",
                            "w_lot=in.({})".format(",".join(
                                f'"{x}"' for x in _wl_ids[_i0:_i0 + 50])),
                            limit=500):
                        _wo_by_lot.setdefault(w["w_lot"], []).append(
                            f"{w.get('pn') or '-'}"
                            f"({status_ko(w.get('status'))})")
            except Exception:
                pass

            _bq = st.text_input(
                "보유 자재 검색", key="rcv_recv_q",
                label_visibility="collapsed",
                placeholder="검색 — 자재 · 식별 번호 · 품명 · 발주번호")
            _pairs = []
            for r in _rcpts:
                _ln = r.get("lot_number")
                _is_w = str(_ln or "").startswith("W")
                _qty9 = float(r.get("qty") or 0)
                _bal9 = _lot_bal.get(_ln) if _is_w else None
                if not _is_w:
                    _stat9 = "번호 미부여"
                elif _bal9 is None or _bal9 + 1e-9 >= _qty9:
                    _stat9 = "투입 대기"
                elif _bal9 <= 0:
                    _stat9 = "전량 투입"
                else:
                    _stat9 = "일부 투입"
                _poi9 = _poi_m.get(r.get("ref_id"), {})
                _po9 = _po_hdr9.get(_poi9.get("po_id"), {})
                _pairs.append((r, {
                    "선택": False,
                    "입고일": r.get("txn_date"),
                    "식별 번호": _ln if _is_w else "(미부여)",
                    "자재": _m_name.get(r["material_id"])
                            or r["material_id"],
                    "발주 품명": _poi9.get("item_name") or "-",
                    "입고": _qty9,
                    "잔량": _bal9 if _bal9 is not None else None,
                    "상태": _stat9,
                    "공정 투입": ", ".join(
                        _wo_by_lot.get(_ln, [])) or "-",
                    "발주": _po9.get("po_number") or "-",
                }))
            if (_bq or "").strip():
                _q1 = _bq.strip().lower()
                _pairs = [t for t in _pairs if any(
                    _q1 in str(t[1][k]).lower()
                    for k in ("자재", "식별 번호", "발주 품명", "발주"))]
            if not _pairs:
                st.info("검색 결과 없음.")
            else:
                _ed9 = st.data_editor(
                    pd.DataFrame([d for _, d in _pairs]),
                    hide_index=True, use_container_width=True,
                    key="rcv_recv_ed_{}_{}".format(
                        len(_pairs), (_bq or "").strip()),
                    height=min(430, 60 + len(_pairs) * 35),
                    column_config={
                        "선택": st.column_config.CheckboxColumn(
                            "선택", width="small"),
                        "식별 번호": st.column_config.TextColumn(
                            "식별 번호", width="small",
                            help="공정 진행 전에만 수정 가능 — 고쳐 쓰고 "
                                 "아래 변경 저장. 예: 1010 또는 W1010"),
                        **{c: st.column_config.Column(disabled=True)
                           for c in ("입고일", "자재", "발주 품명",
                                     "상태", "공정 투입", "발주")},
                        **{c: st.column_config.NumberColumn(
                            format="localized", width="small",
                            disabled=True) for c in ("입고", "잔량")},
                    })
                _sel9 = [t for t, (_, er) in zip(_pairs, _ed9.iterrows())
                         if bool(er.get("선택"))]
                st.caption("상태: 투입 대기 → 일부 투입 → 전량 투입. "
                           "**공정 진행 전 LOT 은 식별 번호를 표에서 고쳐 "
                           "저장할 수 있습니다.** 잘못 입고한 라인은 선택 "
                           "후 입고 취소 — 투입이 시작된 LOT 은 취소·수정 "
                           "불가 (공정 쪽 정리 먼저). 취소하면 발주 "
                           "미입고가 되살아나 입고 처리 탭에 다시 뜹니다.")

                # 식별 번호 변경 감지 → 저장 (공정 진행 전 한정)
                _rn9 = []
                for (r, d), (_, er) in zip(_pairs, _ed9.iterrows()):
                    _nv = str(er.get("식별 번호") or "").strip()
                    if _nv != str(d["식별 번호"]):
                        _rn9.append((r, d, _nv))
                if _rn9:
                    if st.button(f"식별 번호 변경 저장 ({len(_rn9)}건)",
                                 type="primary", key="rcv_wid_save"):
                        _errs9, _okr9 = [], 0
                        _batch9 = set()
                        for r, d, _nv in _rn9:
                            _lbl0 = d["식별 번호"]
                            if d["상태"] not in ("투입 대기", "번호 미부여"):
                                _errs9.append(f"{_lbl0}: 공정 진행 중 — "
                                              "변경 불가")
                                continue
                            _dg = "".join(ch for ch in _nv
                                          if ch.isdigit())
                            if not _dg:
                                _errs9.append(f"{_lbl0}: 새 번호를 숫자로 "
                                              "입력하세요 (예: 1010)")
                                continue
                            _nw = f"W{int(_dg):04d}"
                            if _nw == r.get("lot_number"):
                                continue
                            if _nw in _batch9:
                                _errs9.append(f"{_nw}: 같은 저장에서 중복")
                                continue
                            try:
                                _dupx = fetch("inventory_transactions",
                                              "txn_id",
                                              f"lot_number=eq.{_nw}",
                                              limit=1)
                            except Exception:
                                _dupx = [1]
                            if _dupx:
                                _errs9.append(f"{_nw}: 이미 사용 중 — "
                                              "다른 번호를 쓰세요")
                                continue
                            try:
                                _db.update("inventory_transactions",
                                           f"txn_id=eq.{r['txn_id']}",
                                           {"lot_number": _nw})
                                _batch9.add(_nw)
                                _okr9 += 1
                            except Exception as e:
                                _errs9.append(f"{_nw}: {e}")
                        # 카운터를 원장 최대 번호로 동기화 — 위로
                        # 고치면 상향, 최신 번호를 아래로 고치면 복귀
                        if _okr9:
                            w_lot_sync_counter()
                        for _e9 in _errs9:
                            st.warning(_e9)
                        if _okr9:
                            st.success(f"식별 번호 변경 {_okr9}건 — "
                                       "라벨은 선택 후 재발행으로 "
                                       "출력하세요.")
                            st.rerun()
                if _sel9:
                    from utils.label_generator import receipt_labels

                    def _lbl9(r):
                        _poi = _poi_m.get(r.get("ref_id"), {})
                        _po = _po_hdr9.get(_poi.get("po_id"), {})
                        return {
                            "w_lot": r.get("lot_number") or "(식별 번호 없음)",
                            "pn": _poi.get("item_name") or "-",
                            "material_name":
                                _m_name.get(r.get("material_id"))
                                or r.get("material_id") or "-",
                            "spec": _poi.get("spec") or "-",
                            "qty": float(r.get("qty") or 0),
                            "unit": r.get("unit") or "EA",
                            "po_number": _po.get("po_number") or "-",
                            "vendor": _v_nm9.get(
                                _po.get("vendor_id")) or "-",
                            "date": r.get("txn_date") or "",
                        }

                    _items9 = [_lbl9(r) for r, _ in _sel9]
                    ab1, ab2, ab3 = st.columns(3)
                    ab1.download_button(
                        f"라벨 재발행 · 단표 ({len(_sel9)})",
                        data=receipt_labels(_items9, mode="label"),
                        file_name=("입고라벨_재발행_"
                                   f"{_items9[0]['w_lot']}.html"),
                        mime="text/html", use_container_width=True,
                        key="rcv_recv_dl1")
                    ab2.download_button(
                        "A4 배치",
                        data=receipt_labels(_items9, mode="a4"),
                        file_name=("입고라벨_재발행_A4_"
                                   f"{_items9[0]['w_lot']}.html"),
                        mime="text/html", use_container_width=True,
                        key="rcv_recv_dl2")
                    if ab3.button(f"입고 취소 ({len(_sel9)})",
                                  key="rcv_recv_cancel",
                                  use_container_width=True):
                        _blocked, _done9, _aff9 = [], 0, set()
                        for r, d in _sel9:
                            _ln = r.get("lot_number")
                            _is_w = str(_ln or "").startswith("W")
                            _used = (_is_w and (
                                _wo_by_lot.get(_ln)
                                or _lot_bal.get(
                                    _ln, float(r.get("qty") or 0))
                                < float(r.get("qty") or 0) - 1e-9))
                            if _used:
                                _blocked.append(_ln or "-")
                                continue
                            try:
                                _db.delete("inventory_transactions",
                                           f"txn_id=eq.{r['txn_id']}")
                                _poi9 = _poi_m.get(r.get("ref_id"), {})
                                if _poi9.get("po_id"):
                                    _aff9.add(_poi9["po_id"])
                                _done9 += 1
                            except Exception as e:
                                st.warning(f"{_ln or r['txn_id']} 취소 "
                                           f"실패: {e}")
                        # 발주 헤더 상태 재계산 (취소로 되돌아간 발주)
                        for _pid9 in _aff9:
                            try:
                                _fr9 = fetch("po_item_receipt_v",
                                             "receipt_status",
                                             f"po_id=eq.{_pid9}", limit=50)
                                _st9 = [f["receipt_status"] for f in _fr9]
                                if _st9 and all(s == "RECEIVED"
                                                for s in _st9):
                                    _h9 = "RECEIVED"
                                elif any(s in ("PARTIAL", "RECEIVED")
                                         for s in _st9):
                                    _h9 = "PARTIAL"
                                else:
                                    _h9 = "SENT"
                                _db.update("purchase_orders",
                                           f"po_id=eq.{_pid9}",
                                           {"status": _h9})
                            except Exception:
                                pass
                        # 카운터를 원장 최대 번호로 동기화 — 최신 번호
                        # 취소 시 다음 입고가 그 번호를 다시 받는다
                        _mx9c = w_lot_sync_counter() if _done9 else None
                        if _blocked:
                            st.warning("투입이 시작된 LOT 은 취소 불가: "
                                       + ", ".join(_blocked))
                        if _done9:
                            st.success(
                                f"입고 취소 {_done9}건 — 발주 미입고가 "
                                "복구되었습니다."
                                + (f" 다음 입고는 W{_mx9c + 1:04d} 부터 "
                                   "발급됩니다."
                                   if _mx9c is not None else ""))
                            st.rerun()

        # ── 자재별 현재고 요약 ──
        with st.expander("자재별 현재고 요약", expanded=False):
            if not _hold:
                st.caption("보유 소재 없음 — 입고 처리하면 집계됩니다. "
                           "(기초재고는 Day 0 실사 기준 0에서 시작)")
            else:
                _use_pn = {}
                try:
                    _mb_ids = [m["material_id"] for m in _hold]
                    _bom0 = []
                    for _i0 in range(0, len(_mb_ids), 50):
                        _bom0 += fetch("bom", "material_id,product_id",
                            "material_id=in.({})".format(
                                ",".join(_mb_ids[_i0:_i0 + 50])),
                            limit=2000)
                    _bp_ids = sorted({b["product_id"] for b in _bom0
                                      if b.get("product_id")})
                    _bp_nm = {}
                    for _i0 in range(0, len(_bp_ids), 100):
                        _bp_nm.update({p["product_id"]: p["pn"]
                                       for p in fetch(
                            "products", "product_id,pn",
                            "product_id=in.({})".format(",".join(
                                f'"{x}"' for x in
                                _bp_ids[_i0:_i0 + 100])), limit=300)})
                    for b in _bom0:
                        _pn0 = _bp_nm.get(b.get("product_id"))
                        if _pn0:
                            _use_pn.setdefault(
                                b["material_id"], []).append(_pn0)
                except Exception:
                    pass
                _ht = []
                for m in sorted(_hold,
                                key=lambda x: -float(x["current_stock"])):
                    _pns = sorted(set(_use_pn.get(m["material_id"], [])))
                    _cs = float(m["current_stock"])
                    _ht.append({
                        "자재": m.get("raw_name") or m["material_id"],
                        "현재고": _cs,
                        "누적 입고": float(m.get("total_received") or 0),
                        "누적 투입": float(m.get("total_consumed") or 0),
                        "최근 이동": m.get("last_txn_date") or "-",
                        "주공급처": m.get("main_supplier") or "-",
                        "사용 품번": (", ".join(_pns[:3])
                                    + (f" 외 {len(_pns) - 3}"
                                       if len(_pns) > 3 else ""))
                                   if _pns else "-",
                        "비고": ("⚠ 음수 — 입고 미기록분 확인"
                                 if _cs < 0 else ""),
                    })
                st.dataframe(pd.DataFrame(_ht), use_container_width=True,
                    hide_index=True,
                    height=min(420, 60 + len(_ht) * 35),
                    column_config={c: st.column_config.NumberColumn(
                        format="localized", width="small")
                        for c in ("현재고", "누적 입고", "누적 투입")})

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
                                f"or=(pn.ilike.*{search_q}*,alias_list.ilike.*{search_q}*,item_name.ilike.*{search_q}*,bom_material_name.ilike.*{search_q}*)&limit=20")
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
                            "status": "DRAFT", "created_by": current_user_name(),
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
            # 리스트에서 행 선택 → 상세/재발급 (스크롤 선택 대체)
            _po_ev = st.dataframe(
                pd.DataFrame([{
                    "발주번호": r["po_number"],
                    "거래처": r["_vname"],
                    "총액 (원)": int(r.get("total_amount") or 0),
                    "상태": status_ko(r.get("status")),
                } for r in history]),
                hide_index=True, use_container_width=True,
                on_select="rerun", selection_mode="single-row",
                key="po_hist_list",
                column_config={"총액 (원)": st.column_config.NumberColumn(
                    format="localized")})
            _po_rows = (getattr(getattr(_po_ev, "selection", None),
                                "rows", None) or [])
            if not _po_rows:
                _po_rows = [0]
                if len(history) > 1:
                    st.caption("행을 체크하면 그 발주서의 상세가 열립니다 "
                               "— 지금은 첫 발주서 표시 중.")
            po = history[min(_po_rows[0], len(history) - 1)]
            if po:
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
            "**입고 대기 리스트에서 바로 처리합니다** — 도착한 라인에 "
            "수량을 적거나 '전량'을 체크하고 [입고 처리]를 누르세요. "
            "식별 번호 채번 → 실재고 반영 → 입고 라벨까지 자동입니다. "
            "발주 없이 들어온 소재는 아래 직접 입고.")

        try:
            _rw = fetch("po_item_receipt_v",
                "poi_id,po_id,po_number,line_no,item_name,spec,ordered_qty,"
                "unit,material_id,material_name,received_qty,pending_qty",
                "pending_qty=gt.0&order=po_id.desc,line_no.asc", limit=300)
        except Exception as e:
            st.error(f"입고 대기 조회 실패: {e}"); _rw = []

        if not _rw:
            st.success("입고 대기 라인 없음 — 발주된 소재가 모두 "
                       "입고됐습니다. 새 발주는 [새 발주서 작성] 탭에서.")
        else:
            # 발주 헤더 (거래처·입고 예정일)
            _po_h, _po_v = {}, {}
            try:
                _po_ids8 = {r["po_id"] for r in _rw}
                _po_h = {p["po_id"]: p for p in fetch(
                    "purchase_orders",
                    "po_id,po_number,po_date,delivery_date,vendor_id",
                    "po_id=in.({})".format(
                        ",".join(str(i) for i in _po_ids8)), limit=300)}
                _v_ids8 = {p.get("vendor_id") for p in _po_h.values()
                           if p.get("vendor_id")}
                if _v_ids8:
                    _po_v = {v["vendor_id"]: v["name"] for v in fetch(
                        "vendors", "vendor_id,name",
                        "vendor_id=in.({})".format(
                            ",".join(str(i) for i in _v_ids8)), limit=300)}
            except Exception:
                pass

            _rq = st.text_input(
                "입고 대기 검색", key="rcvp_q",
                label_visibility="collapsed",
                placeholder="검색 — 발주번호 · 거래처 · 품명 · 자재")
            from datetime import date as _rp_dt
            _tdy = _rp_dt.today().isoformat()
            _rows = []
            for r in _rw:
                _h = _po_h.get(r["po_id"], {})
                _due = _h.get("delivery_date")
                _rows.append((r, {
                    "전량": False,
                    "이번 입고": 0.0,
                    "발주": r.get("po_number") or str(r["po_id"]),
                    "거래처": _po_v.get(_h.get("vendor_id")) or "-",
                    "예정": ((str(_due) + " ⚠")
                             if _due and str(_due) < _tdy
                             else (_due or "-")),
                    "품명": r.get("item_name") or "-",
                    "자재": r.get("material_name")
                            or ("미매핑" if not r.get("material_id")
                                else r["material_id"]),
                    "발주수량": float(r.get("ordered_qty") or 0),
                    "기입고": float(r.get("received_qty") or 0),
                    "미입고": float(r.get("pending_qty") or 0),
                }))
            if (_rq or "").strip():
                _q2 = _rq.strip().lower()
                _rows = [t for t in _rows if any(
                    _q2 in str(t[1][k]).lower()
                    for k in ("발주", "거래처", "품명", "자재"))]
            if not _rows:
                st.info("검색 결과 없음 — 검색어를 줄여보세요.")
            else:
                _ed = st.data_editor(
                    pd.DataFrame([d for _, d in _rows]),
                    hide_index=True, use_container_width=True,
                    key="rcvp_ed_{}_{}".format(
                        len(_rows), (_rq or "").strip()),
                    height=min(430, 60 + len(_rows) * 35),
                    column_config={
                        "전량": st.column_config.CheckboxColumn(
                            "전량", width="small",
                            help="체크하면 미입고 전량 입고"),
                        "이번 입고": st.column_config.NumberColumn(
                            "이번 입고", min_value=0, step=1,
                            help="실입고 수량 — 발주 초과 입력 가능 "
                                 "(잔재 협의 등)"),
                        **{c: st.column_config.Column(disabled=True)
                           for c in ("발주", "거래처", "예정", "품명",
                                     "자재", "발주수량", "기입고",
                                     "미입고")},
                    })

                # 처리 대상 계산 — 전량 체크 또는 수량 입력
                _todo = []
                for (_r, _), (_bi, _brow) in zip(_rows, _ed.iterrows()):
                    _q3 = float(pd.to_numeric(
                        _brow.get("이번 입고"), errors="coerce") or 0)
                    if bool(_brow.get("전량")):
                        _q3 = max(_q3, float(_r.get("pending_qty") or 0))
                    if _q3 > 0:
                        _todo.append((_r, _q3))

                # 미매핑 자재 — 처음 입고하는 품목만 1회 지정 (재사용)
                _map_pick = {}
                _need_map = [(_r, q) for _r, q in _todo
                             if not _r.get("material_id")]
                for _r, _q4 in _need_map:
                    st.markdown(f"**자재 매핑 — {_r.get('item_name')}** "
                                "(최초 1회, 이후 재사용)")
                    _bm = None
                    try:
                        _ph = fetch("products", "product_id",
                            f"pn=eq.{_r.get('item_name', '')}", limit=1)
                        if _ph:
                            _bh = fetch("bom", "material_id",
                                f"product_id=eq.{_ph[0]['product_id']}"
                                "&material_id=not.is.null", limit=1)
                            if _bh:
                                _bm = _bh[0]["material_id"]
                    except Exception:
                        pass
                    _mk = st.text_input(
                        "자재 검색", key=f"rcvp_mq_{_r['poi_id']}",
                        label_visibility="collapsed",
                        placeholder=("비우면 BOM 매핑 자재 자동 추천"
                                     if _bm else "자재명 / 재질 / 규격"))
                    _mc = []
                    if not (_mk or "").strip() and _bm:
                        try:
                            _mc = fetch("materials",
                                "material_id,raw_name,spec",
                                f"material_id=eq.{_bm}", limit=1)
                        except Exception:
                            _mc = []
                    elif (_mk or "").strip():
                        _kw4 = _mk.strip()
                        try:
                            _mc = fetch("materials",
                                "material_id,raw_name,spec",
                                f"or=(raw_name.ilike.*{_kw4}*,"
                                f"material_type.ilike.*{_kw4}*,"
                                f"spec.ilike.*{_kw4}*)&order=raw_name",
                                limit=15)
                        except Exception:
                            _mc = []
                    if _mc:
                        _ml = [f"{m['material_id']} | {m['raw_name']} "
                               f"({m.get('spec') or '-'})" for m in _mc]
                        _mp = st.selectbox(
                            "자재 선택", _ml,
                            key=f"rcvp_mp_{_r['poi_id']}")
                        _map_pick[_r["poi_id"]] = \
                            _mc[_ml.index(_mp)]["material_id"]
                    else:
                        st.caption("일치 자재 없음 — 다른 키워드를 넣거나 "
                                   "마스터 관리 → 자재 편집에서 등록하세요.")

                # 발주 초과 경고 (차단 없음 — 실입고 그대로 기록)
                _over = [(r, q) for r, q in _todo
                         if q > float(r.get("pending_qty") or 0) + 1e-9]
                if _over:
                    st.warning("발주 초과 입고 {}건 — {} (잔재 협의 등, "
                               "실입고 그대로 기록되고 원장에 초과분 "
                               "표시)".format(
                        len(_over), ", ".join(
                            "{} +{:,.0f}".format(
                                r.get("item_name") or "-",
                                q - float(r.get("pending_qty") or 0))
                            for r, q in _over[:5])))

                _tot = sum(q for _, q in _todo)
                _unmapped = [r for r, q in _todo
                             if not r.get("material_id")
                             and r["poi_id"] not in _map_pick]
                if _unmapped:
                    st.warning("자재 미매핑 {}건 — 위에서 자재를 선택해야 "
                               "입고할 수 있습니다.".format(len(_unmapped)))
                if st.button(
                        f"입고 처리 ({_tot:,.0f} · {len(_todo)}개 라인)",
                        type="primary", key="rcvp_go",
                        disabled=(_tot <= 0 or bool(_unmapped))
                        ) and click_guard("rcvp_go"):
                    from datetime import date as _rcv_date
                    _wls = w_lot_next(len(_todo))
                    if _wls is None:
                        st.warning(
                            "⚠️ 식별 번호 카운터 미설정 — 이번 입고는 식별 번호 "
                            "없이 기록됩니다. 아래 채번 설정을 먼저 "
                            "저장하세요.")
                    _lbl, _okn, _failn, _aff_po = [], 0, 0, set()
                    for _wi, (_r, _q5) in enumerate(_todo):
                        _mid = (_r.get("material_id")
                                or _map_pick.get(_r["poi_id"]))
                        _w = _wls[_wi] if _wls else None
                        _pend5 = float(_r.get("pending_qty") or 0)
                        _rmk = "발주 입고: {}".format(
                            _r.get("po_number") or _r["po_id"])
                        if _q5 > _pend5:
                            _rmk += f" · 발주 초과 +{_q5 - _pend5:,.0f}"
                        try:
                            _db.insert("inventory_transactions", [{
                                "material_id": _mid,
                                "txn_type": "RECEIPT",
                                "qty": _q5,
                                "unit": _r.get("unit") or "EA",
                                "lot_number": _w,
                                "ref_table": "purchase_order_items",
                                "ref_id": _r["poi_id"],
                                "txn_date":
                                    _rcv_date.today().isoformat(),
                                "remark": _rmk,
                                "created_by": current_user_name(),
                            }])
                            if not _r.get("material_id") and _mid:
                                _db.update("purchase_order_items",
                                           f"poi_id=eq.{_r['poi_id']}",
                                           {"material_id": _mid})
                            _h5 = _po_h.get(_r["po_id"], {})
                            _lbl.append({
                                "w_lot": _w or "(식별 번호 없음)",
                                "pn": _r.get("item_name") or "-",
                                "material_name":
                                    _r.get("material_name") or _mid,
                                "spec": _r.get("spec") or "-",
                                "qty": _q5,
                                "unit": _r.get("unit") or "EA",
                                "po_number": _r.get("po_number") or "-",
                                "vendor": _po_v.get(
                                    _h5.get("vendor_id")) or "-",
                                "date": _rcv_date.today().isoformat(),
                            })
                            _aff_po.add(_r["po_id"])
                            _okn += 1
                        except Exception as e:
                            _failn += 1
                            st.warning("{} 입고 실패: {}".format(
                                _r.get("item_name") or _r["poi_id"], e))
                    # 발주 헤더 상태 자동 갱신 (영향 발주만)
                    for _pid5 in _aff_po:
                        try:
                            _fr5 = fetch("po_item_receipt_v",
                                         "receipt_status",
                                         f"po_id=eq.{_pid5}", limit=50)
                            _sts5 = [f["receipt_status"] for f in _fr5]
                            if _sts5 and all(s == "RECEIVED"
                                             for s in _sts5):
                                _hdr5 = "RECEIVED"
                            elif any(s in ("PARTIAL", "RECEIVED")
                                     for s in _sts5):
                                _hdr5 = "PARTIAL"
                            else:
                                _hdr5 = None
                            if _hdr5:
                                _db.update("purchase_orders",
                                           f"po_id=eq.{_pid5}",
                                           {"status": _hdr5})
                        except Exception:
                            pass
                    if _okn:
                        st.session_state["rcv_labels"] = _lbl
                        st.success(
                            f"✅ 입고 처리 완료 — {_okn}개 라인 · "
                            f"{_tot:,.0f}개 (실재고 자동 반영)"
                            + (f" / 실패 {_failn}" if _failn else ""))
                        st.rerun()

        if st.session_state.get("rcv_labels"):
            from utils.label_generator import receipt_labels
            _lbs = st.session_state["rcv_labels"]
            st.info(
                f"방금 입고한 {len(_lbs)}건의 소재 입고 라벨 — "
                "다운로드 후 열면 인쇄 창이 자동으로 뜹니다. "
                "라벨을 소재에 부착하고, MES 소재 등록 시 라벨의 "
                "식별 번호를 그대로 입력하세요.")
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
                     key="dr_submit") and click_guard("dr_submit"):
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
                    "created_by": current_user_name(),
                }])
                st.session_state["rcv_labels"] = [{
                    "w_lot": _dw or "(식별 번호 없음)",
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
                           + (f"(소재 LOT {_dw})" if _dw else "(식별 번호 없음)"))
                st.rerun()
            except Exception as e:
                st.error(f"직접 입고 실패: {e}")

        # 식별 번호 채번 카운터 — 미설정일 때만 노출되는 최초 셋업 (설정되면
        # 화면에서 사라짐. 상시 도구는 사용자 확정으로 제거, 2026-08-12)
        try:
            _wc0 = _db.fetch_one("app_settings",
                                 "key=eq.w_lot_counter", "value")
        except Exception:
            _wc0 = {"value": "?"}
        if not (_wc0 or {}).get("value"):
            st.divider()
            st.warning("식별 번호 채번 카운터가 아직 없습니다 — 현장에서 "
                       "마지막으로 사용한 번호를 저장해야 입고 시 "
                       "식별 번호가 자동 발급됩니다. (최초 1회)")
            _wcx1, _wcx2 = st.columns([1, 2])
            _wc_new0 = _wcx1.number_input("마지막 사용 번호", 0, 9999,
                                          904, 1, key="pe_wc_new")
            _wcx2.write("")
            if _wcx2.button("카운터 저장", key="pe_wc_save"):
                try:
                    _db.insert("app_settings", [{
                        "key": "w_lot_counter",
                        "value": str(int(_wc_new0))}])
                    st.success(f"저장 — 다음 입고부터 "
                               f"W{int(_wc_new0) + 1:04d}")
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
            "MES 작업지시서 발행 직후, 지시서의 **작업지시 NO + 소재 식별 번호 + "
            "투입 수량**을 등록합니다 → 소재 재고 차감 + '생산중' 진입. "
            "(하루 발행분 기준 건당 30초)")

        # ── 잔여 있는 소재 식별 번호 목록 (RECEIPT − PROD_INPUT) ──
        try:
            _wtx = fetch("inventory_transactions",
                "lot_number,material_id,qty,txn_type,ref_id",
                "lot_number=like.W*&txn_type=in.(RECEIPT,PROD_INPUT)",
                limit=2000)
        except Exception as e:
            st.error(f"소재 LOT 조회 실패: {e}"); _wtx = []

        if not _wtx:
            st.info("잔여 소재 LOT(식별 번호)가 없습니다 — 발주/입고 → "
                    "입고 처리에서 입고하면 식별 번호가 발급됩니다.")
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

                # 잔여 소재 LOT 리스트 — 행을 선택(체크)해 투입 진행
                # (스크롤 선택 대체, 2026-08-12)
                _bal = _bal.reset_index(drop=True)
                _w_df = pd.DataFrame([{
                    "식별 번호": b.lot_number,
                    "자재": _mn_map.get(b.material_id, b.material_id),
                    "잔여": float(b.qty),
                } for b in _bal.itertuples()])
                _w_ev = st.dataframe(
                    _w_df, hide_index=True, use_container_width=True,
                    on_select="rerun", selection_mode="single-row",
                    key="pe_w_list",
                    column_config={"잔여": st.column_config.NumberColumn(
                        format="localized")})
                _w_rows = (getattr(getattr(_w_ev, "selection", None),
                                   "rows", None) or [])
                if not _w_rows:
                    _w_rows = [0]     # 미선택 시 첫 LOT 표시
                    if len(_bal) > 1:
                        st.caption("리스트에서 행을 체크하면 그 소재로 "
                                   "투입을 진행합니다 — 지금은 첫 번째 "
                                   "LOT 이 선택되어 있습니다.")
                _sel = _bal.iloc[min(_w_rows[0], len(_bal) - 1)]
                _sel_lot, _sel_mid = _sel["lot_number"], _sel["material_id"]
                _sel_bal = float(_sel["qty"])
                st.caption(f"선택: **{_sel_lot}** · "
                           f"{_mn_map.get(_sel_mid, _sel_mid)} · "
                           f"잔여 {_sel_bal:,.0f}")

                # 품번 자동 매핑 (2026-07-27 개선) —
                #  ① 발주 라인명이 제품 품번이면 그대로 (품목 발주 경로)
                #  ② 아니면 소재 → BOM 역조회로 이 소재를 쓰는 제품 후보
                #     (자재 발주·사급·직접 입고 경로). 미납 수주 있는
                #     제품을 우선 제시.
                _pn_hint, _pn_src = "", ""
                _ref_poi = _lot_ref.get(_sel_lot)
                if _ref_poi:
                    try:
                        _poi_row = _db.fetch_one("purchase_order_items",
                            f"poi_id=eq.{_ref_poi}", "item_name")
                        _cand_pn = (_poi_row or {}).get("item_name") or ""
                        if _cand_pn and _db.fetch_one(
                                "products", f"pn=eq.{_cand_pn}",
                                "product_id"):
                            _pn_hint, _pn_src = _cand_pn, "발주 라인"
                    except Exception:
                        pass

                _bom_pns = []
                if not _pn_hint:
                    try:
                        _bp = fetch("bom", "product_id",
                            f"material_id=eq.{_sel_mid}", limit=50)
                        _bp_ids = list({b["product_id"] for b in _bp
                                        if b.get("product_id")})
                        if _bp_ids:
                            _bp_str = ",".join(f'"{p}"' for p in _bp_ids)
                            _bp_rows = fetch("products", "product_id,pn",
                                f"product_id=in.({_bp_str})"
                                "&archived_at=is.null&order=pn", limit=50)
                            # 미납 수주가 있는 제품 우선 정렬
                            _open_pids = set()
                            try:
                                _open_pids = {
                                    s["product_id"] for s in fetch(
                                        "sales_order_items", "product_id",
                                        f"product_id=in.({_bp_str})"
                                        "&pending_qty=gt.0", limit=200)
                                    if s.get("product_id")}
                            except Exception:
                                pass
                            _bom_pns = sorted(
                                _bp_rows,
                                key=lambda p: (
                                    p["product_id"] not in _open_pids,
                                    p["pn"]))
                    except Exception:
                        _bom_pns = []

                if _pn_hint:
                    _in_pn = _pn_hint
                    st.caption(f"품번 **{_in_pn}** ({_pn_src}에서 자동 "
                               "매핑)")
                elif _bom_pns:
                    _pn_labels = [
                        (f"{p['pn']} ← 미납 수주 있음"
                         if p["product_id"] in _open_pids else p["pn"])
                        for p in _bom_pns]
                    _pn_sel = st.selectbox(
                        f"품번 (이 소재의 BOM 제품 {len(_bom_pns)}건)",
                        _pn_labels, key=f"pe_in_pnsel_{_sel_lot}",
                        help="소재→BOM 역조회 자동 후보. 미납 수주가 "
                             "있는 제품이 위에 표시됩니다.")
                    _in_pn = _bom_pns[_pn_labels.index(_pn_sel)]["pn"]
                else:
                    _in_pn = st.text_input(
                        "품번 (BOM 연결 없음 — 직접 입력)",
                        key="pe_in_pn",
                        help="이 소재를 쓰는 제품이 BOM 에 없습니다. "
                             "마스터 관리 → BOM 편집에서 등록하면 "
                             "다음부터 자동 제안됩니다.")

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

                # 라우팅 선행 공정 확인 — 소재 단계 외주(소재열처리 등)가
                # 정의된 제품은 회수 이력이 있어야 투입 가능 (순차 강제,
                # 관리자만 우회). 처리 UI 를 이 자리에 승격 표시.
                _mat_ok, _mat_override = True, False
                _has_routed_mat = False
                if _prod0:
                    _rt_in = get_routing(_prod0.get("product_id"))
                    _mat_steps = routing_out_steps(_rt_in, stage="MATERIAL")
                    _has_routed_mat = bool(_mat_steps)
                    if _mat_steps:
                        try:
                            _mev2 = fetch("wo_events",
                                "event_type,qty,routing_id",
                                f"w_lot=eq.{_sel_lot}"
                                "&event_type=in.(MAT_OUT_SEND,"
                                "MAT_OUT_RETURN)", limit=100)
                        except Exception:
                            _mev2 = []

                        def _mat_done(s):
                            return any(
                                e["event_type"] == "MAT_OUT_RETURN"
                                and (e.get("routing_id")
                                     == s.get("routing_id")
                                     or e.get("routing_id") is None)
                                for e in _mev2)

                        _pend_mat = next((s for s in _mat_steps
                                          if not _mat_done(s)), None)
                        if _pend_mat is None:
                            st.caption(
                                "선행 소재 외주("
                                + " · ".join(s["step_name"]
                                             for s in _mat_steps)
                                + ") 회수 이력 확인됨 — 투입 가능합니다.")
                        else:
                            _mat_ok = False
                            st.error(
                                "선행 공정 미완료 — "
                                f"**{_pend_mat['step_name']} (소재 외주)** "
                                "출고·회수를 기록해야 투입할 수 있습니다.")
                            # 방금 발행한 의뢰서 (rerun 후 다운로드 유지)
                            if st.session_state.get("mo_doc"):
                                _mdoc = st.session_state["mo_doc"]
                                mdc1, mdc2 = st.columns([3, 1])
                                mdc1.download_button(
                                    _mdoc["title"], data=_mdoc["html"],
                                    file_name=_mdoc["fn"],
                                    mime="text/html", key="mo_doc_dl",
                                    use_container_width=True)
                                if mdc2.button("닫기", key="mo_doc_x",
                                               use_container_width=True):
                                    del st.session_state["mo_doc"]
                                    st.rerun()
                            _mo2_open = (
                                sum(float(e.get("qty") or 0)
                                    for e in _mev2
                                    if e["event_type"] == "MAT_OUT_SEND")
                                - sum(float(e.get("qty") or 0)
                                      for e in _mev2
                                      if e["event_type"]
                                      == "MAT_OUT_RETURN"))
                            if _mo2_open > 0:
                                st.caption(f"현재 외주 중: "
                                           f"{_mo2_open:,.0f} — 돌아오면 "
                                           "회수 기록을 누르세요.")
                            _mo_fixv = (_pend_mat.get("default_vendor")
                                        or "").strip()
                            mo1, mo2 = st.columns(2)
                            with mo1:
                                st.text_input("공정 (라우팅 자동)",
                                    value=_pend_mat["step_name"],
                                    disabled=True,
                                    key=f"mo2_p_{_sel_lot}")
                                if _mo_fixv:
                                    _mo2_vendor = _mo_fixv
                                    st.text_input(
                                        "외주 거래처 (마스터 고정 — "
                                        "승인 업체)",
                                        value=_mo2_vendor, disabled=True,
                                        key=f"mo2_v_{_sel_lot}")
                                else:
                                    try:
                                        _mov2 = fetch("vendors", "name",
                                            "in_use=eq.true&order=name",
                                            limit=300)
                                    except Exception:
                                        _mov2 = []
                                    _mo2_vendor = st.selectbox(
                                        "외주 거래처",
                                        [v["name"] for v in _mov2]
                                        or ["(거래처 없음)"],
                                        key=f"mo2_vs_{_sel_lot}")
                                    st.caption("마스터 관리 → 공정 "
                                               "라우팅에서 승인 업체를 "
                                               "고정할 수 있습니다.")
                            with mo2:
                                _mo2_qty = st.number_input("수량",
                                    min_value=0.0,
                                    value=float(_sel_bal), step=1.0,
                                    key=f"mo2_q_{_sel_lot}")
                                _mo2_due = st.date_input("납기 요청일",
                                    key=f"mo2_d_{_sel_lot}")

                            def _mo2_log(ev_type):
                                try:
                                    _db.insert("wo_events", [{
                                        "wo_number": _sel_lot,
                                        "w_lot": _sel_lot,
                                        "pn": (_in_pn or "").strip()
                                              or None,
                                        "event_type": ev_type,
                                        "qty": _mo2_qty,
                                        "routing_id":
                                            _pend_mat.get("routing_id"),
                                        "step_name":
                                            _pend_mat["step_name"],
                                        "detail": {
                                            "vendor": _mo2_vendor,
                                            "due": str(_mo2_due),
                                            "material_id": _sel_mid},
                                        "event_date":
                                            _pe_date.today().isoformat(),
                                        "created_by":
                                            current_user_name()}])
                                    return True
                                except Exception as e:
                                    st.error(f"기록 실패: {e}")
                                    return False

                            bb1, bb2 = st.columns(2)
                            if bb1.button(
                                    f"외주 출고 기록 + 의뢰서 "
                                    f"({_mo2_qty:,.0f})", type="primary",
                                    disabled=_mo2_qty <= 0,
                                    key=f"mo2_send_{_sel_lot}"):
                                from utils.label_generator import (
                                    outsource_request_html)
                                _mdoc_html = outsource_request_html({
                                    "vendor": _mo2_vendor,
                                    "process": _pend_mat["step_name"],
                                    "due_date": str(_mo2_due),
                                    "issue_date":
                                        _pe_date.today().isoformat(),
                                    "items": [{
                                        "pn": (_in_pn or "").strip()
                                              or "-",
                                        "wo_number": "-",
                                        "w_lot": _sel_lot,
                                        "qty": _mo2_qty,
                                        "note": _pend_mat["step_name"]}],
                                    "remark": "소재 외주 (투입 전)"})
                                if _mo2_log("MAT_OUT_SEND"):
                                    st.session_state["mo_doc"] = {
                                        "title": "소재 외주 의뢰서 — "
                                                 f"{_mo2_vendor} "
                                                 f"({_pend_mat['step_name']}"
                                                 f" {_mo2_qty:,.0f})",
                                        "fn": f"소재외주의뢰서_{_sel_lot}"
                                              f"_{_mo2_vendor}.html",
                                        "html": _mdoc_html}
                                    st.rerun()
                            if bb2.button(f"회수 기록 ({_mo2_qty:,.0f})",
                                          disabled=not (_mo2_qty > 0
                                                        and _mo2_open > 0),
                                          key=f"mo2_ret_{_sel_lot}"):
                                if _mo2_log("MAT_OUT_RETURN"):
                                    st.success("회수 기록 완료 — 투입이 "
                                               "열립니다.")
                                    st.rerun()
                            if current_user().get("role") == "admin":
                                _mat_override = st.checkbox(
                                    "관리자 우회 — 소재 외주 이력 없이 "
                                    "투입 진행", key=f"mo2_ov_{_sel_lot}")

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
                                      and _in_prod_qty > 0
                                      and (_mat_ok or _mat_override)),
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
                            "created_by": current_user_name(),
                        }])
                        # 초기 배치 생성 (Phase A — 지시번호-A, 계보 뿌리)
                        _new_batch_id = None
                        try:
                            _nwo = _db.fetch_one("wo_tracking",
                                f"wo_number=eq.{_wo}&w_lot=eq.{_sel_lot}",
                                "wo_id")
                            _db.insert("wo_batches", [{
                                "batch_no": f"{_wo}-A",
                                "wo_id": (_nwo or {}).get("wo_id"),
                                "wo_number": _wo,
                                "product_id":
                                    (_prod0 or {}).get("product_id"),
                                "pn": _pn_clean or None,
                                "w_lot": _sel_lot,
                                "qty": _in_prod_qty,
                                "step_code": "PROD",
                                "step_name": "생산",
                                "location": "사내",
                                "created_by": current_user_name()}])
                            _nb = _db.fetch_one("wo_batches",
                                f"batch_no=eq.{_wo}-A", "batch_id")
                            _new_batch_id = (_nb or {}).get("batch_id")
                        except Exception:
                            pass   # 배치는 병행 기록 — 실패해도 투입 진행
                        _db.insert("inventory_transactions", [{
                            "material_id": _sel_mid,
                            "txn_type": "PROD_INPUT",
                            "qty": -_in_qty,
                            "unit": "EA",
                            "lot_number": _sel_lot,
                            "work_order": _wo,
                            "txn_date": _pe_date.today().isoformat(),
                            "remark": f"생산 투입: {_pn_clean or '-'} ({_wo})",
                            "created_by": current_user_name(),
                        }])
                        try:
                            _db.insert("wo_events", [{
                                "wo_number": _wo, "w_lot": _sel_lot,
                                "pn": _pn_clean or None,
                                "event_type": "INPUT",
                                "qty": _in_prod_qty,
                                "batch_id": _new_batch_id,
                                "detail": {"material_qty": _in_qty,
                                           "batch_no": f"{_wo}-A"},
                                "event_date":
                                    _pe_date.today().isoformat(),
                                "created_by": current_user_name()}])
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

                # ── 소재 외주 처리 (수동 기록 — 라우팅 미정의 제품용) ──
                # 라우팅에 소재 외주가 정의된 제품은 위 승격 배너에서
                # 처리하므로 중복 노출하지 않는다. 재고 수량은 바뀌지
                # 않고(소유권 유지) 이벤트 이력만 남는다.
                _mev = []
                try:
                    _mev = fetch("wo_events",
                        "event_id,event_type,qty,step_name,detail,"
                        "event_date,created_by",
                        f"w_lot=eq.{_sel_lot}"
                        "&event_type=in.(MAT_OUT_SEND,MAT_OUT_RETURN)"
                        "&order=event_id", limit=100)
                except Exception:
                    pass
                if not _has_routed_mat:
                    _m_open = (sum(float(e.get("qty") or 0) for e in _mev
                                   if e["event_type"] == "MAT_OUT_SEND")
                               - sum(float(e.get("qty") or 0) for e in _mev
                                     if e["event_type"] == "MAT_OUT_RETURN"))
                    with st.expander(
                            "소재 외주 처리 (소재열처리 등 — 투입 전 외주)"
                            + (f" — 외주 중 {_m_open:,.0f}"
                               if _m_open > 0 else ""),
                            expanded=_m_open > 0):
                        st.caption(
                            f"**{_sel_lot}** 소재를 투입 전에 외주(소재열처리 "
                            "등) 보내고 회수하는 기록입니다. 장부 재고는 "
                            "바뀌지 않고 이력만 남아, 투입 시 선행 공정 "
                            "확인에 사용됩니다.")
                        try:
                            _mov = fetch("vendors", "name",
                                "in_use=eq.true&order=name", limit=300)
                        except Exception:
                            _mov = []
                        mo1, mo2, mo3 = st.columns(3)
                        with mo1:
                            _mo_proc = st.text_input("공정명",
                                placeholder="예: 고용화, 소재열처리",
                                key=f"mo_proc_{_sel_lot}")
                        with mo2:
                            _mo_vendor = st.selectbox("외주 거래처",
                                [v["name"] for v in _mov] or ["(거래처 없음)"],
                                key=f"mo_vendor_{_sel_lot}")
                        with mo3:
                            _mo_qty = st.number_input("수량",
                                min_value=0.0, value=float(_sel_bal), step=1.0,
                                key=f"mo_qty_{_sel_lot}")
    
                        def _mo_log(ev_type, done_msg):
                            try:
                                _db.insert("wo_events", [{
                                    "wo_number": _sel_lot,  # WO 생성 전 — LOT 로 기록
                                    "w_lot": _sel_lot,
                                    "event_type": ev_type,
                                    "qty": _mo_qty,
                                    "step_name": (_mo_proc or "").strip() or None,
                                    "detail": {"vendor": _mo_vendor,
                                               "material_id": _sel_mid},
                                    "event_date": _pe_date.today().isoformat(),
                                    "created_by": current_user_name()}])
                                st.success(done_msg)
                                st.rerun()
                            except Exception as e:
                                st.error(f"기록 실패: {e}")
    
                        mb1, mb2 = st.columns(2)
                        if mb1.button(f"외주 출고 기록 ({_mo_qty:,.0f})",
                                      disabled=not (_mo_qty > 0 and
                                                    (_mo_proc or "").strip()),
                                      key=f"mo_send_{_sel_lot}"):
                            _mo_log("MAT_OUT_SEND",
                                    f"소재 외주 출고 기록: {_sel_lot} "
                                    f"{_mo_qty:,.0f} → {_mo_vendor}")
                        if mb2.button(f"회수 기록 ({_mo_qty:,.0f})",
                                      type="primary",
                                      disabled=not (_mo_qty > 0
                                                    and _m_open > 0),
                                      key=f"mo_ret_{_sel_lot}"):
                            _mo_log("MAT_OUT_RETURN",
                                    f"소재 외주 회수 기록: {_sel_lot} "
                                    f"{_mo_qty:,.0f} ← {_mo_vendor}")
                        if _mev:
                            toss_table([{
                                "일자": e.get("event_date"),
                                "구분": ("출고" if e["event_type"]
                                         == "MAT_OUT_SEND" else "회수"),
                                "공정": e.get("step_name"),
                                "거래처": (e.get("detail") or {}).get("vendor"),
                                "수량": float(e.get("qty") or 0),
                                "처리자": e.get("created_by"),
                            } for e in _mev],
                                num_cols=("수량",), badge_cols=("구분",))

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
            # 작업지시 상태 리스트 — 전체 진행 상황을 보면서 행을
            # 선택(체크)해 바로 처리한다 (스크롤 선택 대체, 2026-08-12)
            def _next_hint(t1):
                q1 = wo_stage_qty(t1)
                if q1["생산중"] > 0:
                    return "완료 인수"
                if q1["외주중"] > 0:
                    return "외주 입고"
                if q1["재작업중"] > 0:
                    return "재작업 복귀"
                if q1["검사대기"] > 0:
                    return "검사 / 외주"
                if q1["완성"] > 0:
                    return "완성 확정"
                return "-"

            _p_df = pd.DataFrame([{
                "지시번호": t1["wo_number"],
                "품번": t1.get("pn") or "-",
                "소재 LOT": t1.get("w_lot") or "-",
                "생산중": float(wo_stage_qty(t1)["생산중"]),
                "외주중": float(wo_stage_qty(t1)["외주중"]),
                "검사대기": float(wo_stage_qty(t1)["검사대기"]),
                "완성": float(wo_stage_qty(t1)["완성"]),
                "상태": status_ko(wo_derive_status(t1)),
                "다음 처리": _next_hint(t1),
            } for t1 in _pe_pool])
            _p_ev = st.dataframe(
                _p_df, hide_index=True, use_container_width=True,
                on_select="rerun", selection_mode="single-row",
                key="pe_proc_list",
                column_config={c: st.column_config.NumberColumn(
                    format="localized") for c in
                    ("생산중", "외주중", "검사대기", "완성")})
            _p_rows = (getattr(getattr(_p_ev, "selection", None),
                               "rows", None) or [])
            if not _p_rows:
                _p_rows = [0]     # 미선택 시 첫 지시 표시
                if len(_pe_pool) > 1:
                    st.caption("리스트에서 행을 체크하면 그 작업지시가 "
                               "아래에 열립니다 — 지금은 첫 번째 지시가 "
                               "표시되고 있습니다.")
            _t = _pe_pool[min(_p_rows[0], len(_pe_pool) - 1)]
            _q = wo_stage_qty(_t)

            # 라우팅 기반 동적 스테퍼 — 제품의 공정 순서대로 칸 구성,
            # 진행 칸만 상태색 (Migration 036). 라우팅 없으면 기본 4칸,
            # 외주 실적이 있는 지시만 표시용 외주 칸을 동적으로 추가.
            _rt = list(get_routing(_t.get("product_id")))
            _routed = any(s.get("routing_id") for s in _rt
                          if s.get("step_kind") == "OUTSOURCE")
            if not _routed and (float(_t.get("outsource_qty") or 0) > 0
                                or _q["외주중"] > 0):
                _ins_at = next((i for i, s in enumerate(_rt)
                                if s["step_code"] == "INSPECT"), len(_rt))
                _rt.insert(_ins_at, {
                    "routing_id": None, "seq": 30, "step_code": "OUT",
                    "step_name": "외주", "step_kind": "OUTSOURCE",
                    "stage": "PRODUCT"})
            _out_steps = routing_out_steps(_rt)
            try:
                _rt_evs = fetch("wo_events", "event_type,qty,routing_id",
                    f"wo_id=eq.{_t['wo_id']}"
                    "&event_type=in.(OUT_SEND,OUT_RETURN)", limit=300)
            except Exception:
                _rt_evs = []
            _mat_evs = []
            if _t.get("w_lot") and routing_out_steps(_rt, stage="MATERIAL"):
                try:
                    _mat_evs = fetch("wo_events", "event_type,qty",
                        f"w_lot=eq.{_t['w_lot']}"
                        "&event_type=in.(MAT_OUT_SEND,MAT_OUT_RETURN)",
                        limit=100)
                except Exception:
                    pass
            # 스텝별 출고/회수 '누계' — 수량 분기(부분 출고·부분 회수)가
            # 일어나도 스텝 단위로 얼마나 통과했는지 추적한다.
            # routing 지정 없는 옛 이벤트는 첫 외주 스텝으로 귀속.
            _osent, _oret = {}, {}
            for _e in _rt_evs:
                _k = _e.get("routing_id")
                _qv = float(_e.get("qty") or 0)
                if _e["event_type"] == "OUT_SEND":
                    _osent[_k] = _osent.get(_k, 0) + _qv
                else:
                    _oret[_k] = _oret.get(_k, 0) + _qv
            if _out_steps:
                _k0 = _out_steps[0].get("routing_id")
                if _k0 is not None:
                    if None in _osent:
                        _osent[_k0] = (_osent.get(_k0, 0)
                                       + _osent.pop(None))
                    if None in _oret:
                        _oret[_k0] = _oret.get(_k0, 0) + _oret.pop(None)
                if not _rt_evs:
                    # 이벤트가 없는 옛 지시 — 집계 수량으로 보정
                    _osent[_k0] = float(_t.get("outsource_qty") or 0)
                    _oret[_k0] = float(_t.get("outsource_in_qty") or 0)
            _ob = {k: _osent.get(k, 0) - _oret.get(k, 0)
                   for k in set(_osent) | set(_oret)}
            _rcv_cum = float(_t.get("received_qty") or 0)

            def _step_sent(s):
                return float(_osent.get(s.get("routing_id"), 0))

            def _step_ret(s):
                return float(_oret.get(s.get("routing_id"), 0))

            def _step_cls(active, done):
                return "on" if active else ("done" if done else "")

            _stp = []
            for _s in _rt:
                _sc = _s["step_code"]
                if _sc == "MAT_IN":
                    _cls = _step_cls(False,
                                     float(_t.get("input_qty") or 0) > 0)
                elif (_s.get("stage") == "MATERIAL"
                      and _s.get("step_kind") == "OUTSOURCE"):
                    _ms = sum(float(e.get("qty") or 0) for e in _mat_evs
                              if e["event_type"] == "MAT_OUT_SEND")
                    _mr = sum(float(e.get("qty") or 0) for e in _mat_evs
                              if e["event_type"] == "MAT_OUT_RETURN")
                    _cls = _step_cls(_ms > _mr, _mr > 0)
                elif _sc == "PROD":
                    _cls = _step_cls(_q["생산중"] > 0,
                                     float(_t.get("received_qty") or 0) > 0)
                elif _s.get("step_kind") == "OUTSOURCE":
                    # 완료 = 인수 누계 전량이 이 공정을 통과(회수)했을 때.
                    # 부분 출고·부분 회수(수량 분기) 중에는 진행 표시.
                    _sv, _rv = _step_sent(_s), _step_ret(_s)
                    _cls = _step_cls(_sv > _rv,
                                     _rcv_cum > 0 and _rv >= _rcv_cum)
                elif _sc == "INSPECT":
                    _cls = _step_cls(_q["검사대기"] > 0
                                     or _q["재작업중"] > 0,
                                     float(_t.get("pass_qty") or 0) > 0
                                     or float(_t.get("scrap_qty") or 0) > 0)
                elif _sc == "DONE":
                    _cls = _step_cls(False, _q["완성"] > 0)
                else:  # 사용자 정의 사내 공정 — 수량 추적 없음 (2단계 예정)
                    _cls = ""
                _stp.append((_s["step_name"], _cls))
            st.markdown('<div class="stepper">' + "".join(
                f'<div class="step {c}">{n}</div>' for n, c in _stp)
                + "</div>", unsafe_allow_html=True)
            # 다음 공정 안내 — 진행 중이면 그 공정, 아니면 첫 미완료 공정
            _going = [n for n, c in _stp if c == "on"]
            _next = [n for n, c in _stp if c == ""]
            if _going:
                st.caption(f"진행 중: **{' · '.join(_going)}**"
                           + (f" — 다음 공정: {_next[0]}" if _next else ""))
            elif _next:
                st.caption(f"다음 공정: **{_next[0]}**")

            # 외주 공정별 수량 추적 (분기 대비) — 출고·회수 누계와
            # 인수 대비 미처리 수량을 스텝 단위로 보여준다
            if _routed and _rcv_cum > 0:
                toss_table([{
                    "외주 공정": s["step_name"],
                    "출고 누계": _step_sent(s),
                    "회수 누계": _step_ret(s),
                    "외주 중": max(0.0, _step_sent(s) - _step_ret(s)),
                    "미처리": max(0.0, _rcv_cum - _step_ret(s)),
                } for s in _out_steps],
                    num_cols=("출고 누계", "회수 누계", "외주 중",
                              "미처리"))


            pm = st.columns(6)
            for _pi, _pk in enumerate(
                    ["생산중", "외주중", "재작업중", "검사대기",
                     "완성", "반품"]):
                pm[_pi].metric(_pk if _pk != "검사대기" else "검사 대기",
                               f"{_q[_pk]:,.0f}")

            def _wo_apply(fields, ledger=None, docs=None, msg="",
                          event=None):
                """수량 누적 갱신 + 상태 자동 유도 + 원장/문서/이벤트 기록"""
                if not click_guard("wo_apply", ttl=3.0):
                    return
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
                            "created_by": current_user_name(), **event}])
                    except Exception as e:
                        st.warning(f"⚠️ 이력 기록 실패 (처리는 정상): {e}")
                if docs:
                    st.session_state["pe_docs"] = docs
                st.success(msg)
                st.rerun()

            # ═══ 배치 단위 처리 (Phase B) — 분기·합류가 처리의 기본 ═══
            # 배치가 있는 지시는 배치 리스트에서 행을 선택해 처리한다.
            # 부분 수량 = 자동 분기(SPLIT), 합치기 = 같은 지시 내 합류.
            # 완성 LOT 번호 = 배치번호 → 회차별 완성 추적이 이어진다.
            try:
                _bat_all = fetch("wo_batches", "*",
                    f"wo_number=eq.{_t['wo_number']}&order=batch_no",
                    limit=200)
            except Exception:
                _bat_all = []
            _bat_open = [b for b in _bat_all if b.get("status") == "OPEN"]

            _flow = [s for s in _rt
                     if s.get("stage") != "MATERIAL"
                     and s["step_code"] in ("PROD", "OUT",
                                            "INSPECT", "DONE")]

            def _bpos(b):
                """배치의 현재 위치 → _flow 인덱스"""
                if b["step_code"] == "OUT":
                    for _i, s in enumerate(_flow):
                        if (s["step_code"] == "OUT"
                                and s.get("routing_id")
                                == b.get("routing_id")):
                            return _i
                    return max(0, next(
                        (_i for _i, s in enumerate(_flow)
                         if s["step_code"] == "INSPECT"), 1) - 1)
                return next((_i for _i, s in enumerate(_flow)
                             if s["step_code"] == b["step_code"]), 0)

            def _bnext(b):
                _i = _bpos(b)
                return _flow[_i + 1] if _i + 1 < len(_flow) else None

            def _b_action(b):
                """배치 위치 → 가능한 처리 (위치가 액션을 결정)"""
                if b["step_code"] == "PROD":
                    return "완료 인수"
                if b["step_code"] == "OUT":
                    return ("외주 입고"
                            if (b.get("location") or "사내")
                            not in ("사내", "재작업") else "외주 출고")
                if b["step_code"] == "INSPECT":
                    return ("재작업 복귀"
                            if b.get("location") == "재작업" else "검사")
                return "-"

            def _b_suffix():
                """다음 가지 문자 (A~Z, AA~) — 지시 내 유일"""
                import string as _bs
                _used = {b["batch_no"].rsplit("-", 1)[-1]
                         for b in _bat_all}
                for _c in list(_bs.ascii_uppercase) + [
                        a + b2 for a in _bs.ascii_uppercase
                        for b2 in _bs.ascii_uppercase]:
                    if _c not in _used:
                        return _c
                return f"X{len(_bat_all)}"

            def _bat_update(bid, fields):
                fields = dict(fields)
                fields["updated_at"] = _pe_dt.utcnow().isoformat()
                _db.update("wo_batches", f"batch_id=eq.{bid}", fields)

            def _bat_take(b, qty, new_fields):
                """배치에서 qty 를 떼어 새 상태로. 전량이면 배치 이동,
                부분이면 자동 분기(SPLIT 계보 기록). (번호, id) 반환"""
                if qty >= float(b["qty"]) - 1e-9:
                    _bat_update(b["batch_id"], new_fields)
                    return b["batch_no"], b["batch_id"]
                _new_no = f"{_t['wo_number']}-{_b_suffix()}"
                _db.insert("wo_batches", [{
                    "batch_no": _new_no, "wo_id": _t["wo_id"],
                    "wo_number": _t["wo_number"],
                    "product_id": _t.get("product_id"),
                    "pn": _t.get("pn"), "w_lot": _t.get("w_lot"),
                    "qty": qty, **new_fields,
                    "created_by": current_user_name()}])
                _nb = _db.fetch_one("wo_batches",
                                    f"batch_no=eq.{_new_no}", "batch_id")
                _bat_update(b["batch_id"],
                            {"qty": float(b["qty"]) - qty})
                if _nb:
                    try:
                        _db.insert("batch_links", [{
                            "parent_batch_id": b["batch_id"],
                            "child_batch_id": _nb["batch_id"],
                            "qty": qty, "link_type": "SPLIT"}])
                    except Exception:
                        pass
                _bat_all.append({"batch_no": _new_no})  # suffix 중복 방지
                return _new_no, (_nb or {}).get("batch_id")

            if _bat_open:
                st.markdown("##### 배치 처리")
                st.caption("행을 선택해 진행합니다 — 부분 수량은 자동으로 "
                           "분기(새 가지 번호)되고, 계보가 기록되어 "
                           "회차·LOT 추적이 유지됩니다.")
                _bt_ev = st.dataframe(
                    pd.DataFrame([{
                        "배치": b["batch_no"],
                        "수량": float(b.get("qty") or 0),
                        "공정": b.get("step_name") or "-",
                        "위치": b.get("location") or "사내",
                        "다음 처리": _b_action(b),
                    } for b in _bat_open]),
                    hide_index=True, use_container_width=True,
                    on_select="rerun", selection_mode="single-row",
                    key=f"bt_list_{_t['wo_id']}",
                    column_config={"수량": st.column_config.NumberColumn(
                        format="localized")})
                _bt_rows = (getattr(getattr(_bt_ev, "selection", None),
                                    "rows", None) or [])
                if not _bt_rows:
                    _bt_rows = [0]
                    if len(_bat_open) > 1:
                        st.caption("행을 체크하면 그 배치를 처리합니다 — "
                                   "지금은 첫 배치가 선택되어 있습니다.")
                _sb = _bat_open[min(_bt_rows[0], len(_bat_open) - 1)]
                _sb_qty = float(_sb.get("qty") or 0)
                _sb_act = _b_action(_sb)
                st.markdown(
                    f"**{_sb['batch_no']}** · {_sb_qty:,.0f} EA · "
                    f"{_sb.get('step_name') or '-'} · "
                    f"{_sb.get('location') or '사내'} → **{_sb_act}**")

                # ── 완료 인수 (배치: 생산 → 다음 공정 대기) ──
                if _sb_act == "완료 인수":
                    _bq = st.number_input("인수 수량", 0.0, _sb_qty,
                        _sb_qty, 1.0, key=f"bt_rq_{_sb['batch_id']}")
                    if st.button(f"인수 등록 ({_bq:,.0f})",
                                 type="primary", disabled=_bq <= 0,
                                 key=f"bt_rq_btn_{_sb['batch_id']}"):
                        _nx = _bnext(_sb)
                        _no, _nid = _bat_take(_sb, _bq, {
                            "step_code": _nx["step_code"],
                            "step_name": _nx["step_name"],
                            "routing_id": _nx.get("routing_id"),
                            "location": "사내"})
                        _wo_apply(
                            {"received_qty":
                             float(_t.get("received_qty") or 0) + _bq},
                            event={"event_type": "RECEIVE", "qty": _bq,
                                   "batch_id": _nid,
                                   "detail": {"batch_no": _no}},
                            msg=f"✅ {_no} 인수 {_bq:,.0f} EA → "
                                f"{_nx['step_name']} 대기")

                # ── 외주 출고 (배치: 공정 대기 → 거래처) ──
                elif _sb_act == "외주 출고":
                    _stp_r = next(
                        (s for s in _out_steps
                         if s.get("routing_id") == _sb.get("routing_id")),
                        None)
                    _fxv = ((_stp_r or {}).get("default_vendor")
                            or "").strip()
                    bc1, bc2 = st.columns(2)
                    with bc1:
                        st.text_input("가공 공정 (배치 위치 — 자동)",
                            value=_sb.get("step_name") or "외주",
                            disabled=True,
                            key=f"bt_p_{_sb['batch_id']}")
                        if _fxv:
                            _bv = _fxv
                            st.text_input(
                                "외주 거래처 (마스터 고정 — 승인 업체)",
                                value=_bv, disabled=True,
                                key=f"bt_v_{_sb['batch_id']}")
                        else:
                            try:
                                _bov = fetch("vendors", "name",
                                    "in_use=eq.true&order=name",
                                    limit=300)
                            except Exception:
                                _bov = []
                            _bv = st.selectbox("외주 거래처",
                                [v["name"] for v in _bov]
                                or ["(거래처 없음)"],
                                key=f"bt_vs_{_sb['batch_id']}")
                            st.caption("마스터 관리 → 공정 라우팅에서 "
                                       "승인 업체를 고정할 수 있습니다.")
                    with bc2:
                        _bq = st.number_input("출고 수량", 0.0, _sb_qty,
                            _sb_qty, 1.0,
                            key=f"bt_oq_{_sb['batch_id']}")
                        _bd = st.date_input("납기 요청일",
                            key=f"bt_od_{_sb['batch_id']}")
                    if st.button(
                            f"외주 출고 ({_bq:,.0f}) + 의뢰서 발행",
                            type="primary", disabled=_bq <= 0,
                            key=f"bt_o_btn_{_sb['batch_id']}"):
                        from utils.label_generator import (
                            outsource_request_html)
                        _no, _nid = _bat_take(_sb, _bq,
                                              {"location": _bv})
                        _doc = outsource_request_html({
                            "vendor": _bv,
                            "process": _sb.get("step_name") or "외주",
                            "due_date": str(_bd),
                            "issue_date": _pe_date.today().isoformat(),
                            "items": [{"pn": _t.get("pn"),
                                       "wo_number": _no,
                                       "w_lot": _t.get("w_lot"),
                                       "qty": _bq,
                                       "note": _sb.get("step_name")
                                               or "외주"}],
                            "remark": f"배치 {_no}",
                        })
                        _wo_apply(
                            {"outsource_qty":
                             float(_t.get("outsource_qty") or 0) + _bq},
                            event={"event_type": "OUT_SEND", "qty": _bq,
                                   "routing_id": _sb.get("routing_id"),
                                   "step_name": _sb.get("step_name"),
                                   "batch_id": _nid,
                                   "detail": {"vendor": _bv,
                                              "due": str(_bd),
                                              "batch_no": _no}},
                            docs={"title": f"외주 의뢰서 — {_bv} "
                                           f"({_sb.get('step_name')} "
                                           f"{_bq:,.0f} EA · {_no})",
                                  "files": [("외주 의뢰서 (A4)",
                                             f"외주의뢰서_{_no}_{_bv}"
                                             ".html", _doc)]},
                            msg=f"{_no} 외주 출고 {_bq:,.0f} EA → {_bv}")

                # ── 외주 입고 (배치: 거래처 → 다음 공정 대기) ──
                elif _sb_act == "외주 입고":
                    st.caption(f"{_sb.get('location')} 에서 "
                               f"{_sb.get('step_name')} 완료분을 "
                               "회수합니다 — 부분 입고 시 잔량은 외주에 "
                               "남습니다.")
                    _bq = st.number_input("입고 수량", 0.0, _sb_qty,
                        _sb_qty, 1.0, key=f"bt_iq_{_sb['batch_id']}")
                    if st.button(f"외주 입고 ({_bq:,.0f})",
                                 type="primary", disabled=_bq <= 0,
                                 key=f"bt_i_btn_{_sb['batch_id']}"):
                        _nx = _bnext(_sb)
                        _no, _nid = _bat_take(_sb, _bq, {
                            "step_code": _nx["step_code"],
                            "step_name": _nx["step_name"],
                            "routing_id": _nx.get("routing_id"),
                            "location": "사내"})
                        _wo_apply(
                            {"outsource_in_qty":
                             float(_t.get("outsource_in_qty") or 0)
                             + _bq},
                            event={"event_type": "OUT_RETURN",
                                   "qty": _bq,
                                   "routing_id": _sb.get("routing_id"),
                                   "step_name": _sb.get("step_name"),
                                   "batch_id": _nid,
                                   "detail": {"batch_no": _no}},
                            msg=f"{_no} 외주 입고 {_bq:,.0f} EA → "
                                f"{_nx['step_name']} 대기")

                # ── 검사 (배치 판정 — 완성 LOT = 배치번호) ──
                elif _sb_act == "검사":
                    st.caption("이 배치를 판정합니다 — 완성(합격+특채)은 "
                               "즉시 완성 재고로 확정되고 **완성 LOT "
                               "번호 = 배치번호**로 발행됩니다.")
                    qc1, qc2, qc3, qc4, qc5 = st.columns(5)
                    _i_pass = qc1.number_input("완성 (합격)", 0.0,
                        _sb_qty, _sb_qty, 1.0,
                        key=f"bt_ip_{_sb['batch_id']}")
                    _i_rework = qc2.number_input("재작업", 0.0, _sb_qty,
                        0.0, 1.0, key=f"bt_ir_{_sb['batch_id']}")
                    _i_scrap = qc3.number_input("폐기", 0.0, _sb_qty,
                        0.0, 1.0, key=f"bt_is_{_sb['batch_id']}")
                    _i_tok = qc4.number_input("특채", 0.0, _sb_qty,
                        0.0, 1.0, key=f"bt_it_{_sb['batch_id']}")
                    _i_ret = qc5.number_input("반품", 0.0, _sb_qty,
                        0.0, 1.0, key=f"bt_ib_{_sb['batch_id']}")
                    _i_done = _i_pass + _i_tok
                    _i_sum = (_i_pass + _i_rework + _i_scrap
                              + _i_tok + _i_ret)
                    if _i_sum > _sb_qty:
                        st.error(f"판정 합계 {_i_sum:,.0f}가 배치 수량 "
                                 f"{_sb_qty:,.0f}를 초과합니다.")
                    _f_pid = _t.get("product_id")
                    if not _f_pid and _t.get("pn"):
                        try:
                            _f_pid = (_db.fetch_one("products",
                                f"pn=eq.{_t['pn']}", "product_id")
                                or {}).get("product_id")
                        except Exception:
                            pass
                    if _i_done > 0 and not _f_pid:
                        st.error("품번이 제품 마스터와 연결되지 않아 "
                                 "완성 재고 등록이 불가합니다.")
                    if st.button(f"검사 등록 (판정 {_i_sum:,.0f} · "
                                 f"완성 {_i_done:,.0f})", type="primary",
                                 disabled=not (0 < _i_sum <= _sb_qty
                                               and (_i_done <= 0
                                                    or bool(_f_pid))),
                                 key=f"bt_i_go_{_sb['batch_id']}"):
                        from utils.label_generator import (
                            inspection_labels, finished_labels)
                        _today = _pe_date.today().isoformat()
                        # 판정별 분기 — 부모 잔량을 추적하며 순서대로
                        _par = dict(_sb)

                        def _take2(q, fields):
                            _no2, _id2 = _bat_take(_par, q, fields)
                            _par["qty"] = max(
                                0.0, float(_par["qty"]) - q)
                            if _par["qty"] <= 1e-9:
                                _par["batch_no"] = _no2
                            return _no2, _id2

                        _fin_no = None
                        if _i_done > 0:
                            _fin_no, _fin_id = _take2(_i_done, {
                                "step_code": "DONE",
                                "step_name": "완성",
                                "routing_id": None,
                                "location": "사내",
                                "status": "DONE"})
                        if _i_rework > 0 and _par["qty"] > 0:
                            _take2(_i_rework, {"location": "재작업"})
                        if _i_scrap > 0 and _par["qty"] > 0:
                            _take2(_i_scrap, {"status": "SCRAP",
                                              "location": "사내"})
                        if _i_ret > 0 and _par["qty"] > 0:
                            _take2(_i_ret, {"status": "RETURN",
                                            "location": "사내"})
                        _lot_no = _fin_no or _t["wo_number"]
                        _base = {"pn": _t.get("pn"),
                                 "wo_number": _t["wo_number"],
                                 "w_lot": _t.get("w_lot"),
                                 "lot": _lot_no, "date": _today}
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
                                 f"완성라벨_{_lot_no}.html",
                                 finished_labels(_fin, mode="label")),
                                ("완성 라벨 A4",
                                 f"완성라벨_A4_{_lot_no}.html",
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
                                         + _i_pass,
                             "tokusai_qty":
                             float(_t.get("tokusai_qty") or 0) + _i_tok,
                             "rework_qty":
                             float(_t.get("rework_qty") or 0)
                             + _i_rework,
                             "scrap_qty":
                             float(_t.get("scrap_qty") or 0) + _i_scrap,
                             "return_qty":
                             float(_t.get("return_qty") or 0) + _i_ret,
                             "output_qty":
                             float(_t.get("output_qty") or 0) + _i_done},
                            event={"event_type": "INSPECT",
                                   "qty": _i_sum,
                                   "batch_id": _sb["batch_id"],
                                   "detail": {"pass": _i_pass,
                                              "rework": _i_rework,
                                              "scrap": _i_scrap,
                                              "tokusai": _i_tok,
                                              "return": _i_ret,
                                              "output": _i_done,
                                              "batch_no":
                                                  _sb["batch_no"],
                                              "lot": _fin_no}},
                            ledger=({
                                "product_id": _f_pid,
                                "txn_type": "PROD_OUTPUT",
                                "qty": _i_done, "unit": "EA",
                                "lot_number": _lot_no,
                                "work_order": _t["wo_number"],
                                "txn_date": _today,
                                "remark": "검사 완성: "
                                          f"{_t.get('pn') or '-'} "
                                          f"(배치 {_lot_no} · 소재 "
                                          f"{_t.get('w_lot') or '-'})",
                                "created_by": current_user_name(),
                            } if _i_done > 0 else None),
                            docs=({"title": "검사 판정 문서",
                                   "files": _files} if _files else None),
                            msg=f"검사 등록 — 완성 {_i_done:,.0f} "
                                f"(LOT {_fin_no or '-'}) · 재작업 "
                                f"{_i_rework:,.0f} · 폐기 "
                                f"{_i_scrap:,.0f}")

                # ── 재작업 복귀 (배치: 재작업 → 검사 대기) ──
                elif _sb_act == "재작업 복귀":
                    _bq = st.number_input("복귀 수량", 0.0, _sb_qty,
                        _sb_qty, 1.0, key=f"bt_rw_{_sb['batch_id']}")
                    if st.button(f"재작업 복귀 ({_bq:,.0f})",
                                 type="primary", disabled=_bq <= 0,
                                 key=f"bt_rw_btn_{_sb['batch_id']}"):
                        _no, _nid = _bat_take(_sb, _bq,
                                              {"location": "사내"})
                        _wo_apply(
                            {"rework_in_qty":
                             float(_t.get("rework_in_qty") or 0) + _bq},
                            event={"event_type": "REWORK_BACK",
                                   "qty": _bq, "batch_id": _nid,
                                   "detail": {"batch_no": _no}},
                            msg=f"{_no} 재작업 복귀 {_bq:,.0f} EA → "
                                "재검사 대기")

                # ── 배치 합치기 (같은 지시 · 같은 공정·위치만) ──
                _mg_pool = [b for b in _bat_open
                            if (b["step_code"], b.get("routing_id"),
                                b.get("location") or "사내")
                            == (_sb["step_code"], _sb.get("routing_id"),
                                _sb.get("location") or "사내")]
                if len(_mg_pool) >= 2:
                    with st.expander(
                            f"배치 합치기 — {_sb.get('step_name')} · "
                            f"{_sb.get('location') or '사내'} 위치 "
                            f"{len(_mg_pool)}개"):
                        st.caption("같은 공정·위치의 배치만 합칠 수 "
                                   "있습니다. 계보(MERGE)가 남아 원천 "
                                   "추적은 유지되지만, 리콜 시 합쳐진 "
                                   "전체가 범위가 됩니다.")
                        _mg_pick = st.multiselect("합칠 배치",
                            [b["batch_no"] for b in _mg_pool],
                            default=[b["batch_no"] for b in _mg_pool],
                            key=f"bt_mg_{_sb['batch_id']}")
                        _mg_sel = [b for b in _mg_pool
                                   if b["batch_no"] in _mg_pick]
                        _mg_qty = sum(float(b["qty"]) for b in _mg_sel)
                        if st.button(
                                f"합치기 ({len(_mg_sel)}개 → "
                                f"{_mg_qty:,.0f} EA)",
                                disabled=len(_mg_sel) < 2,
                                key=f"bt_mg_btn_{_sb['batch_id']}"):
                            try:
                                _mg_no = (f"{_t['wo_number']}-"
                                          f"{_b_suffix()}")
                                _db.insert("wo_batches", [{
                                    "batch_no": _mg_no,
                                    "wo_id": _t["wo_id"],
                                    "wo_number": _t["wo_number"],
                                    "product_id": _t.get("product_id"),
                                    "pn": _t.get("pn"),
                                    "w_lot": _t.get("w_lot"),
                                    "qty": _mg_qty,
                                    "step_code": _sb["step_code"],
                                    "step_name": _sb.get("step_name"),
                                    "routing_id": _sb.get("routing_id"),
                                    "location": _sb.get("location")
                                                or "사내",
                                    "created_by": current_user_name()}])
                                _mg_new = _db.fetch_one("wo_batches",
                                    f"batch_no=eq.{_mg_no}", "batch_id")
                                for b in _mg_sel:
                                    _bat_update(b["batch_id"],
                                                {"status": "MERGED"})
                                    if _mg_new:
                                        _db.insert("batch_links", [{
                                            "parent_batch_id":
                                                b["batch_id"],
                                            "child_batch_id":
                                                _mg_new["batch_id"],
                                            "qty": float(b["qty"]),
                                            "link_type": "MERGE"}])
                                st.success(f"합치기 완료 → {_mg_no} "
                                           f"({_mg_qty:,.0f} EA)")
                                st.rerun()
                            except Exception as e:
                                st.error(f"합치기 실패: {e}")

            # ── 레거시 경로: 배치가 없는 옛 지시만 수량 풀 방식 유지 ──
            _acts = []
            if not _bat_open and _q["생산중"] > 0:
                _acts.append("완료 인수")
            # 라우팅이 정의된 제품은 공정 순차 강제 — 인수 누계 전량이
            # 각 외주 공정을 순서대로 통과해야 검사가 열린다. 수량 분기
            # (나눠서 출고·회수)는 허용하되 스텝별 누계로 추적하므로
            # 안 거친 수량이 검사로 새지 않는다. 기본 플로우 제품은 자유.
            _pending_out, _pending_cap = None, 0.0
            if _routed:
                _avail = _rcv_cum      # 이 스텝에 도달한 수량
                for _s2 in _out_steps:
                    _rv2 = _step_ret(_s2)
                    if _rv2 < _rcv_cum:
                        _pending_out = _s2
                        _pending_cap = max(0.0,
                                           _avail - _step_sent(_s2))
                        break
                    _avail = min(_rv2, _rcv_cum)
            if not _bat_open and _q["검사대기"] > 0:
                if _routed:
                    if _pending_out is not None:
                        if _pending_cap > 0:
                            _acts.append("외주 출고")
                        st.caption(
                            "라우팅 순서상 다음 공정: "
                            f"**{_pending_out['step_name']} (외주)** — "
                            f"출고 가능 {_pending_cap:,.0f}"
                            + ("" if _pending_cap > 0
                               else " (이전 공정 회수 대기)")
                            + ". 인수 수량 전량이 통과해야 검사가 "
                            "열립니다.")
                    else:
                        _acts.append("검사")
                else:
                    _acts += ["검사", "외주 출고"]
            if not _bat_open and _q["외주중"] > 0:
                _acts.append("외주 입고")
            if not _bat_open and _q["재작업중"] > 0:
                _acts.append("재작업 복귀")
            # 오입력 정리 — 후속 처리(인수·외주·검사)가 없는 투입만 취소
            # 가능. 관리자 전용.
            _dnstream = sum(float(_t.get(k) or 0) for k in
                            ("received_qty", "outsource_qty", "pass_qty",
                             "tokusai_qty", "scrap_qty", "rework_qty",
                             "output_qty", "return_qty"))
            if (float(_t.get("input_qty") or 0) > 0 and _dnstream == 0
                    and current_user().get("role") == "admin"):
                _acts.append("투입 취소")

            if not _acts and not _bat_open:
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
                        # 외주 거래처 — 라우팅에 고정 업체(PPAP 승인)가
                        # 있으면 변경 불가, 마스터 관리에서만 수정 가능
                        _fx_vendor = ""
                        if _routed and _pending_out is not None:
                            _fx_vendor = (_pending_out.get("default_vendor")
                                          or "").strip()
                        if _fx_vendor:
                            _o_vendor = _fx_vendor
                            st.text_input(
                                "외주 거래처 (마스터 고정 — 승인 업체)",
                                value=_o_vendor, disabled=True,
                                key="pe_o_vendor_fixed")
                        else:
                            _o_vendor = st.selectbox("외주 거래처",
                                [v["name"] for v in _ov]
                                or ["(거래처 없음)"],
                                key="pe_o_vendor")
                            if _routed and _pending_out is not None:
                                st.caption("마스터 관리 → 공정 라우팅에서 "
                                           "이 공정의 승인 업체를 고정할 "
                                           "수 있습니다.")
                        # 라우팅이 정의된 제품은 다음 외주 공정으로 고정
                        # (순차 강제), 기본 플로우 제품은 자유 입력
                        _o_rid = None
                        if _routed and _pending_out is not None:
                            _o_proc = _pending_out["step_name"]
                            _o_rid = _pending_out.get("routing_id")
                            st.text_input(
                                "가공 공정 (라우팅 순서 — 자동 지정)",
                                value=_o_proc, disabled=True,
                                key="pe_o_proc_fixed")
                        else:
                            _o_proc = st.text_input("가공 공정",
                                placeholder="예: 열처리, 도금, 연마",
                                key="pe_o_proc")
                    with oc2:
                        # 라우팅 제품은 이전 공정 회수분까지만 출고 가능
                        # (수량 분기 추적 — 안 거친 수량이 넘어가지 않게)
                        _o_max = (min(_q["검사대기"], _pending_cap)
                                  if _routed and _pending_out is not None
                                  else _q["검사대기"])
                        _o_qty = st.number_input("출고 수량", 0.0,
                            _o_max, _o_max, 1.0,
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
                                   "routing_id": _o_rid,
                                   "step_name": _o_proc,
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
                    # 라우팅 기준 나가 있는 공정 목록 — 어느 공정에서
                    # 돌아오는지 선택 (외주 공정이 여럿인 제품 대비)
                    _oi_rid, _oi_step = None, None
                    _rid_name = {s.get("routing_id"): s["step_name"]
                                 for s in _out_steps}
                    _open_out = [(k, v) for k, v in _ob.items() if v > 0]
                    if _open_out:
                        _oi_opts = [
                            f"{_rid_name.get(k, '외주(공정 미지정)')} — "
                            f"잔량 {v:,.0f}" for k, v in _open_out]
                        _oi_pick = st.selectbox("입고 공정", _oi_opts,
                                                key="pe_oi_step")
                        _oi_k = _open_out[_oi_opts.index(_oi_pick)][0]
                        _oi_rid = _oi_k
                        _oi_step = _rid_name.get(_oi_k)
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
                                   "qty": _oi_qty,
                                   "routing_id": _oi_rid,
                                   "step_name": _oi_step},
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
                                "created_by": current_user_name(),
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

                # ── 6. 투입 취소 (오입력 정리 — 관리자 전용) ──
                elif _act == "투입 취소":
                    st.caption(
                        "잘못 등록한 투입을 취소합니다 — **작업지시가 "
                        "삭제되고 소재 LOT 잔량이 복원**됩니다. 후속 "
                        "처리(인수·외주·검사)가 시작된 지시는 취소할 수 "
                        "없습니다. 취소 이력은 남습니다.")
                    _cx_ok = st.checkbox(
                        f"{_t['wo_number']} · {_t.get('pn') or '-'} · "
                        f"소재 {_t.get('w_lot') or '-'} 투입을 "
                        "취소합니다", key="pe_cx_ok")
                    if st.button("투입 취소 실행", type="primary",
                                 disabled=not _cx_ok, key="pe_cx_btn"):
                        try:
                            # 원래 투입한 소재 수량 — 원장에서 역산
                            _otx = fetch("inventory_transactions", "qty",
                                f"work_order=eq.{_t['wo_number']}"
                                f"&lot_number=eq.{_t.get('w_lot')}"
                                "&txn_type=eq.PROD_INPUT", limit=20)
                            _back = sum(-float(x.get("qty") or 0)
                                        for x in _otx)
                            if _back > 0:
                                _db.insert("inventory_transactions", [{
                                    "material_id": _t.get("material_id"),
                                    "txn_type": "PROD_INPUT",
                                    "qty": _back, "unit": "EA",
                                    "lot_number": _t.get("w_lot"),
                                    "work_order": _t["wo_number"],
                                    "txn_date":
                                        _pe_date.today().isoformat(),
                                    "remark": "투입 취소 복원: "
                                              f"{_t.get('pn') or '-'} "
                                              f"({_t['wo_number']})",
                                    "created_by": current_user_name()}])
                            _db.insert("wo_events", [{
                                "wo_number": _t["wo_number"],
                                "w_lot": _t.get("w_lot"),
                                "pn": _t.get("pn"),
                                "event_type": "INPUT_CANCEL",
                                "qty": float(_t.get("input_qty") or 0),
                                "detail": {"restored_material": _back},
                                "event_date":
                                    _pe_date.today().isoformat(),
                                "created_by": current_user_name()}])
                            try:   # 배치도 함께 정리 (Phase A 병행 기록)
                                _db.delete(
                                    "wo_batches",
                                    f"wo_number=eq.{_t['wo_number']}")
                            except Exception:
                                pass
                            _db.delete("wo_tracking",
                                       f"wo_id=eq.{_t['wo_id']}")
                            st.success(
                                f"투입 취소 완료 — {_t['wo_number']} 삭제, "
                                f"소재 {_back:,.0f} 복원 "
                                f"({_t.get('w_lot') or '-'})")
                            st.rerun()
                        except Exception as e:
                            st.error(f"취소 실패: {e}")

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
                                     range=["#1b64da", "#f04452"])
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
                "제품 검색 (품번/품명/고객사)",
                placeholder="예: 8HFDV-VM-05, MRG6, 미진",
                key="pb_prod_q")
        with pc2:
            st.write("")

        sel_prod = None
        if prod_q:
            qq = prod_q.strip()
            try:
                p_cands = fetch("products",
                    "product_id,pn,customer",
                    f"or=(pn.ilike.*{qq}*,item_name.ilike.*{qq}*,"
                    f"customer.ilike.*{qq}*)"
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
                            "created_by": current_user_name(),
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
                            "created_by": current_user_name(),
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


elif page == "영업 보고":
    st.subheader("영업 보고")
    st.caption(
        "**출고 확정된 전표만** 집계합니다 — 작성중 전표는 확정 전까지 "
        "매출로 잡히지 않습니다. 월 마감 잠금(마감 후 수정 차단)은 "
        "v2 예정.")

    if not DB_AVAILABLE:
        st.error("DB 연결이 활성화되지 않았습니다."); st.stop()

    import pandas as _sr_pd
    from datetime import date as _sr_date
    import utils.sales_report as _sr
    if not hasattr(_sr, "monthly_report_html"):
        import importlib as _sr_il
        _sr = _sr_il.reload(_sr)  # Cloud 재배포 시 sys.modules 캐시 가드
    from utils.statement_generator import (
        delivery_list_html as _sr_list,
        transaction_statements_html as _sr_stmt)

    def _sr_ships(cond):
        return fetch(
            "shipments",
            "shipment_id,ship_no,ship_date,status,created_by,confirmed_at",
            cond + "&order=ship_date.asc,shipment_id.asc", limit=1000)

    def _sr_items(ships):
        """전표 라인 조회 + ship_no/ship_date(=date) 부착."""
        smap = {s["shipment_id"]: s for s in ships}
        ids, out = list(smap), []
        for _i in range(0, len(ids), 50):
            _ck = ",".join(str(x) for x in ids[_i:_i + 50])
            for x in fetch(
                    "shipment_items",
                    "si_id,shipment_id,soi_id,product_id,pn,customer_pn,"
                    "item_name,customer,so_number,qty,unit,unit_price",
                    f"shipment_id=in.({_ck})&order=si_id.asc", limit=2000):
                _s = smap.get(x["shipment_id"]) or {}
                x["ship_no"] = _s.get("ship_no")
                x["date"] = _s.get("ship_date")
                out.append(x)
        return out

    def _sr_kpi(label, value, sub="", tone="primary"):
        _v = value if isinstance(value, str) else f"{value:,.0f}"
        _z = (not isinstance(value, str)) and value <= 0
        cls = "zero" if _z else tone
        return (f'<div class="kpi {cls}"><div class="k">{label}</div>'
                f'<div class="v">{_v}</div>'
                + (f'<div class="s">{sub}</div>' if sub else "") + "</div>")

    def _sr_missing_note(agg):
        if agg["all"]["missing"]:
            st.warning(
                "단가 미입력 {}건 (수량 {:,.0f}) 은 금액 집계에서 제외 "
                "— 수주 관리에서 단가를 채우면 반영됩니다.".format(
                    agg["all"]["missing"], agg["all"]["missing_qty"]))

    def _sr_cust_df(agg):
        _rows = [{"거래처": c, "품목수": s["lines"], "수량": s["qty"],
                  "공급가액": s["supply"], "세액": s["vat"],
                  "합계": s["total"]}
                 for c, s in sorted(agg["by_customer"].items(),
                                    key=lambda kv: -kv[1]["total"])]
        return _sr_pd.DataFrame(_rows)

    _NUMCOL = {c: st.column_config.NumberColumn(format="localized")
               for c in ("수량", "단가", "공급가액", "세액", "합계",
                         "합계(VAT포함)")}

    t_day, t_month, t_re = st.tabs(["일일 결산", "월 마감", "명세서 재발행"])

    # ════════ TAB 1: 일일 결산 ════════
    with t_day:
        _d_pick = st.date_input("결산일", _sr_date.today(), key="sr_day")
        _d_iso = _d_pick.isoformat()
        try:
            _d_ships = _sr_ships(
                f"status=eq.CONFIRMED&ship_date=eq.{_d_iso}")
            _d_drafts = fetch("shipments", "shipment_id,ship_no",
                              f"status=eq.DRAFT&ship_date=eq.{_d_iso}",
                              limit=50)
        except Exception as e:
            st.error(f"조회 실패: {e}")
            _d_ships, _d_drafts = [], []
        if _d_drafts:
            st.warning(
                "이 날짜의 작성중 전표 {}건({})은 집계에 포함되지 "
                "않았습니다 — 출고 관리 → 출고 전표에서 확정하세요.".format(
                    len(_d_drafts),
                    ", ".join(d["ship_no"] for d in _d_drafts)))
        if not _d_ships:
            st.info(f"{_d_iso} 확정 전표가 없습니다.")
        else:
            _d_rows = _sr_items(_d_ships)
            _d_agg = _sr.aggregate(_d_rows)
            _da = _d_agg["all"]
            st.markdown(
                '<div class="kpi-row">'
                + _sr_kpi("전표", f"{len(_d_ships)}건")
                + _sr_kpi("거래처", f"{len(_d_agg['customers'])}곳")
                + _sr_kpi("총 수량", _da["qty"])
                + _sr_kpi("공급가액", _da["supply"], tone="good")
                + _sr_kpi("합계 (VAT포함)", _da["total"], tone="good")
                + "</div>", unsafe_allow_html=True)
            _sr_missing_note(_d_agg)

            st.markdown("##### 거래처별 합계")
            st.dataframe(_sr_cust_df(_d_agg), use_container_width=True,
                         hide_index=True, column_config=_NUMCOL)

            st.markdown("##### 품목 상세")
            _d_det = []
            for x in _d_rows:
                _amt = _sr.line_amounts(x)
                _d_det.append({
                    "전표": x.get("ship_no"), "거래처": x.get("customer"),
                    "품번": x.get("pn"),
                    "거래처 표기": x.get("customer_pn"),
                    "수량": float(x.get("qty") or 0),
                    "단가": x.get("unit_price"),
                    "공급가액": _amt[0] if _amt else None})
            st.dataframe(_sr_pd.DataFrame(_d_det),
                         use_container_width=True, hide_index=True,
                         column_config=_NUMCOL)
            st.download_button(
                "일일 결산 리포트 인쇄", _sr.daily_report_html(
                    _d_iso, _d_rows, current_user_name()),
                file_name=f"일일결산_{_d_iso}.html", mime="text/html",
                key="sr_dl_day", type="primary")

    # ════════ TAB 2: 월 마감 ════════
    with t_month:
        try:
            _m_all = _sr_ships("status=eq.CONFIRMED")
        except Exception as e:
            st.error(f"조회 실패: {e}")
            _m_all = []
        _m_months = sorted({str(s["ship_date"])[:7] for s in _m_all
                            if s.get("ship_date")}, reverse=True)
        if not _m_months:
            st.info("확정 전표가 아직 없습니다 — 출고 확정 후 월 마감을 "
                    "쓸 수 있습니다.")
        else:
            _m_pick = st.selectbox("마감 월", _m_months, key="sr_month")
            _m_ships = [s for s in _m_all
                        if str(s["ship_date"])[:7] == _m_pick]
            _m_rows = _sr_items(_m_ships)
            _m_agg = _sr.aggregate(_m_rows)
            _ma = _m_agg["all"]
            st.markdown(
                '<div class="kpi-row">'
                + _sr_kpi("전표", f"{len(_m_ships)}건")
                + _sr_kpi("출고일수", f"{len(_m_agg['by_date'])}일")
                + _sr_kpi("거래처", f"{len(_m_agg['customers'])}곳")
                + _sr_kpi("총 수량", _ma["qty"])
                + _sr_kpi("공급가액", _ma["supply"], tone="good")
                + _sr_kpi("합계 (VAT포함)", _ma["total"], tone="good")
                + "</div>", unsafe_allow_html=True)
            _sr_missing_note(_m_agg)

            _mc1, _mc2 = st.columns(2)
            with _mc1:
                st.markdown("##### 거래처별 합계")
                st.dataframe(_sr_cust_df(_m_agg),
                             use_container_width=True, hide_index=True,
                             column_config=_NUMCOL)
            with _mc2:
                st.markdown("##### 일자별 합계")
                _m_dt = [{"출고일": d, "수량": s["qty"],
                          "공급가액": s["supply"], "합계": s["total"]}
                         for d, s in sorted(_m_agg["by_date"].items())]
                st.dataframe(_sr_pd.DataFrame(_m_dt),
                             use_container_width=True, hide_index=True,
                             column_config=_NUMCOL)

            st.markdown("##### 품번별 합계 (금액순)")
            _m_pn = [{"품번": pn, "거래처": cu, "라인": s["lines"],
                      "수량": s["qty"], "합계(VAT포함)": s["total"]}
                     for (pn, cu), s in sorted(
                         _m_agg["by_pn"].items(),
                         key=lambda kv: (-kv[1]["total"], -kv[1]["qty"]))]
            st.dataframe(_sr_pd.DataFrame(_m_pn),
                         use_container_width=True, hide_index=True,
                         column_config=_NUMCOL)
            st.download_button(
                "월 마감 보고서 인쇄", _sr.monthly_report_html(
                    _m_pick, _m_rows, current_user_name()),
                file_name=f"월마감_{_m_pick}.html", mime="text/html",
                key="sr_dl_month", type="primary")
            st.caption("마감 잠금(마감 후 해당 월 전표 수정 차단)은 "
                       "v2 에서 추가 예정입니다.")

    # ════════ TAB 3: 명세서 재발행 ════════
    with t_re:
        st.caption("확정 전표를 기간으로 찾아 출고 리스트·거래명세서를 "
                   "다시 발행합니다. 전표 하나를 바로 열려면 출고 관리 → "
                   "출고 전표에서도 가능합니다.")
        _rc1, _rc2 = st.columns(2)
        _r_from = _rc1.date_input(
            "시작일", _sr_date.today().replace(day=1), key="sr_re_from")
        _r_to = _rc2.date_input("종료일", _sr_date.today(), key="sr_re_to")
        try:
            _r_ships = _sr_ships(
                "status=eq.CONFIRMED"
                f"&ship_date=gte.{_r_from.isoformat()}"
                f"&ship_date=lte.{_r_to.isoformat()}")
        except Exception as e:
            st.error(f"조회 실패: {e}")
            _r_ships = []
        if not _r_ships:
            st.info("기간 내 확정 전표가 없습니다.")
        else:
            _r_rows = _sr_items(_r_ships)
            _r_bysh = {}
            for x in _r_rows:
                _r_bysh.setdefault(x["shipment_id"], []).append(x)

            _r_custs = sorted({x.get("customer") or "-" for x in _r_rows})
            _r_cu = st.selectbox("거래처", ["전체"] + _r_custs,
                                 key="sr_re_cust")
            _r_view = [s for s in _r_ships
                       if _r_cu == "전체" or any(
                           (x.get("customer") or "-") == _r_cu
                           for x in _r_bysh.get(s["shipment_id"], []))]

            _r_sum = []
            for s in _r_view:
                _xs = _r_bysh.get(s["shipment_id"], [])
                _ag = _sr.aggregate(_xs)
                _r_sum.append({
                    "전표": s["ship_no"], "출고일": s["ship_date"],
                    "거래처": ", ".join(sorted(_ag["customers"])),
                    "품목수": _ag["all"]["lines"],
                    "수량": _ag["all"]["qty"],
                    "합계": _ag["all"]["total"]})
            st.dataframe(_sr_pd.DataFrame(_r_sum),
                         use_container_width=True, hide_index=True,
                         column_config=_NUMCOL)

            _r_pick = st.selectbox(
                "재발행할 전표", _r_view,
                format_func=lambda s: "{} | {} | {}".format(
                    s["ship_no"], s.get("ship_date"),
                    ", ".join(sorted({
                        x.get("customer") or "-"
                        for x in _r_bysh.get(s["shipment_id"], [])}))),
                key="sr_re_pick")
            _r_items = _r_bysh.get(_r_pick["shipment_id"], [])
            from utils.ship_lots import names_and_lots as _sr_nl
            _r_names, _r_lots = _sr_nl(fetch, _r_items, confirmed=True)

            def _sr_batch(items, ship):
                return {"date": str(ship.get("ship_date")),
                        "rows": [{
                            "pn": x.get("pn"),
                            "customer_pn": x.get("customer_pn"),
                            "item_name": x.get("item_name"),
                            "disp_name": _r_names.get(x.get("si_id")),
                            "lots": _r_lots.get(x.get("si_id")),
                            "customer": x.get("customer"),
                            "so_number": x.get("so_number"),
                            "qty": float(x.get("qty") or 0),
                            "unit": x.get("unit") or "EA",
                            "unit_price": x.get("unit_price"),
                            "date": str(ship.get("ship_date")),
                        } for x in items]}

            def _sr_vmap(items):
                out = {}
                for _cu in {x.get("customer") for x in items
                            if x.get("customer")}:
                    _term = (_cu.replace("㈜", "")
                             .replace("(주)", "").strip())
                    try:
                        _vs = fetch("vendors",
                                    "name,business_no,ceo_name,phone,"
                                    "address,business_type,business_item",
                                    f"name=ilike.*{_term}*", limit=5)
                        if _vs:
                            out[_cu] = _vs[0]
                    except Exception:
                        pass
                return out

            _rb1, _rb2 = st.columns(2)
            _rb1.download_button(
                "출고 리스트 재발행",
                _sr_list(_sr_batch(_r_items, _r_pick)),
                file_name=f"출고리스트_{_r_pick['ship_no']}.html",
                mime="text/html", key="sr_re_list",
                use_container_width=True)
            _rb2.download_button(
                "거래명세서 재발행",
                _sr_stmt(_sr_batch(_r_items, _r_pick),
                         _sr_vmap(_r_items)),
                file_name=f"거래명세서_{_r_pick['ship_no']}.html",
                mime="text/html", key="sr_re_stmt", type="primary",
                use_container_width=True)

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
        "product_id,pn,item_name,customer,sub_class,"
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
            # OR 검색 (PostgREST or= 문법) — 품명·제품군(sub_class) 포함
            parts.append(f"or=(pn.ilike.*{qq}*,customer.ilike.*{qq}*,"
                         f"item_name.ilike.*{qq}*,sub_class.ilike.*{qq}*)")
            parts.append(f"order=total_sales_12m.desc.nullslast")
            try:
                rows = fetch(SRC_TABLE, COST_FIELDS, "&".join(parts), limit=int(ca_limit))
            except Exception as e:
                st.error(f"검색 실패: {e}"); rows = []

            if not rows:
                st.info("검색 결과 없음")
            else:
                # 리스트에서 행 선택 → 분석 (스크롤 선택 대체)
                _cq_ev = st.dataframe(
                    pd.DataFrame([{
                        "품번": r.get("pn"),
                        "고객사": r.get("customer") or "-",
                        "제품군": r.get("sub_class") or "-",
                        "판매가": float(r.get("avg_unit_price") or 0),
                        "추정원가": float(r.get("estimated_cost_per_pc")
                                          or 0),
                        "마진율(%)": float(r.get("margin_pct") or 0),
                    } for r in rows]),
                    hide_index=True, use_container_width=True,
                    on_select="rerun", selection_mode="single-row",
                    key="cost_pick_list",
                    column_config={c: st.column_config.NumberColumn(
                        format="localized")
                        for c in ("판매가", "추정원가")})
                _cq_rows = (getattr(getattr(_cq_ev, "selection", None),
                                    "rows", None) or [])
                if not _cq_rows:
                    _cq_rows = [0]
                    if len(rows) > 1:
                        st.caption("행을 체크하면 그 품목의 원가 분석이 "
                                   "열립니다 — 지금은 첫 품목 표시 중.")
                row = dict(rows[min(_cq_rows[0], len(rows) - 1)])

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
                        ("품명", row.get("item_name") or "-"),
                        ("재질", row.get("material") or row.get("raw_material_name") or "-"),
                        ("규격", row.get("raw_material_spec") or "-"),
                        ("제품군", row.get("sub_class") or "-"),
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

            import html as _h

            def _pct_html(v):
                """마진율 — 음수(역마진)는 빨강"""
                try:
                    f = float(v)
                except (TypeError, ValueError):
                    return '<span class="dim">-</span>'
                return (f'<span class="neg">{f:.1f}%</span>' if f < 0
                        else f"{f:.1f}%")

            def _q_html(v):
                """cost_data_quality 배지 — 검증=초록, 중간·부분=노랑,
                낮음=주황, 없음=빨강 (products 실데이터 값 기준)"""
                if not v:
                    return '<span class="dim">-</span>'
                s = str(v)
                cls = ("b-green" if "검증" in s else
                       "b-red" if "없음" in s else
                       "b-amber" if ("낮음" in s or "중간" in s
                                     or "부분" in s) else "b-gray")
                return (f'<span class="badge {cls}">'
                        f"{_h.escape(s)}</span>")

            _recs = df_o.to_dict("records")
            toss_table([{
                "품번": r.get("pn"), "고객사": r.get("customer"),
                "제품군": r.get("sub_class"),
                "판매가": _money(r.get("avg_unit_price")),
                "소재비": _money(r.get("material_unit_price")),
                "외주비": _money(r.get("outsourcing_per_pc")),
                "열처리": _money(r.get("heat_treat_per_pc")),
                "표면": _money(r.get("surface_per_pc")),
                "추정원가": _money(r.get("estimated_cost_per_pc")),
                "마진율": _pct_html(r.get("margin_pct")),
                "12M매출": _money(r.get("total_sales_12m")),
                "ABC": r.get("abc_grade"),
                "데이터품질": _q_html(r.get("cost_data_quality")),
            } for r in _recs],
                num_cols=("판매가", "소재비", "외주비", "열처리", "표면",
                          "추정원가", "마진율", "12M매출"),
                strong_cols=("품번",),
                raw_cols=("마진율", "데이터품질"),
                hl_rows={n for n, r in enumerate(_recs)
                         if (r.get("margin_pct") or 0) < 0},
                scroll=True)

            # CSV 다운로드용 텍스트 표 (기존 컬럼 구성 유지)
            df_o["판매가"] = df_o["avg_unit_price"].apply(_money)
            df_o["소재비"] = df_o["material_unit_price"].apply(_money)
            df_o["외주비"] = df_o["outsourcing_per_pc"].apply(_money)
            df_o["열처리"] = df_o["heat_treat_per_pc"].apply(_money)
            df_o["표면"] = df_o["surface_per_pc"].apply(_money)
            df_o["추정원가"] = df_o["estimated_cost_per_pc"].apply(_money)
            df_o["마진율"] = df_o["margin_pct"].apply(_pct)
            df_o["12M매출"] = df_o["total_sales_12m"].apply(_money)

            cols = ["pn", "customer", "sub_class", "판매가", "소재비",
                    "외주비", "열처리", "표면", "추정원가", "마진율",
                    "12M매출", "abc_grade", "cost_data_quality"]
            show = df_o[[c for c in cols if c in df_o.columns]].rename(columns={
                "pn": "품번", "customer": "고객사", "sub_class": "제품군",
                "abc_grade": "ABC", "cost_data_quality": "데이터품질"
            })

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
                        f"or=(pn.ilike.*{sq}*,item_name.ilike.*{sq}*,"
                        f"customer.ilike.*{sq}*)"
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
                parts.append(f"or=(pn.ilike.*{qq}*,customer.ilike.*{qq}*,"
                             f"item_name.ilike.*{qq}*,sub_class.ilike.*{qq}*)")
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
                "product_id,pn,customer,"
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
