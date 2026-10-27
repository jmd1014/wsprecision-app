"""
Supabase REST API 직접 호출 (supabase-py 대신 requests 사용)
- supabase-py의 응답 파싱 호환 이슈를 우회
- 이미 import 단계에서 검증된 방식
"""
import streamlit as st
import requests
import json
import time
import urllib.parse as _up


# ─── PostgREST 필터 값 인용 (2026-09-17 보안 점검 반영) ───
# 실측 규칙 (이 프로젝트 DB 로 확인):
#  · 최상위 `col=op.값` 은 값 전체를 그대로 받으므로 콤마·괄호는 문제없고
#    URL 을 깨는 & # % + 만 percent-encoding 하면 된다 (* 는 ilike 와일드카드).
#    큰따옴표로 감싸면 오히려 따옴표까지 문자로 비교되어 빈 결과가 난다.
#  · `or=(a.op.값,b.op.값)` / `in.(값,값)` 안에서는 콤마·괄호가 구분자라
#    큰따옴표로 감싼 뒤 percent-encoding 해야 한다 (와일드카드 * 는 따옴표
#    안에서도 동작).
def qv(v) -> str:
    """최상위 필터 값 — `f"pn=ilike.*{qv(q)}*"`, `f"customer=eq.{qv(c)}"`."""
    return _up.quote(str(v if v is not None else ""), safe="*")


def qo(v) -> str:
    """or=()/and=()/in.() 안의 값 — `f"or=(pn.eq.{qo(x)},name.ilike.{qol(x)})"`."""
    s = str(v if v is not None else "").replace("\\", "\\\\").replace('"', '\\"')
    return _up.quote('"' + s + '"', safe="")


def qol(v) -> str:
    """or=() 안의 ilike 부분일치 값 — `*값*` 를 통째로 인용."""
    return qo("*" + str(v if v is not None else "") + "*")


def _headers(role: str = "service_role"):
    if role == "service_role":
        key = st.secrets["supabase"]["service_role_key"]
    else:
        key = st.secrets["supabase"]["anon_key"]
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _url() -> str:
    return st.secrets["supabase"]["url"]


def count_rows(table: str) -> int | str:
    """단일 테이블 행수 — Range-Unit count 사용"""
    try:
        r = requests.get(
            f"{_url()}/rest/v1/{table}?select=*&limit=1",
            headers={**_headers(), "Prefer": "count=exact"},
            timeout=10,
        )
        if r.status_code not in (200, 206):
            return f"ERR{r.status_code}"
        cr = r.headers.get("content-range", "")
        if "/" in cr:
            n = cr.split("/")[-1]
            return int(n) if n.isdigit() else n
        return 0
    except Exception as e:
        return f"ERR: {str(e)[:30]}"


def health_check() -> dict:
    """모든 핵심 테이블/view의 행수 확인"""
    try:
        url = _url()
        _ = _headers()  # secrets 접근 검증
    except Exception as e:
        return {"status": "FAIL", "error": str(e)}

    tables = [
        "products", "vendors", "materials", "bom", "drawings",
        "sales_ledger", "purchase_ledger",
        "active_products", "archived_products",
    ]
    counts = {}
    for t in tables:
        counts[t] = count_rows(t)
    return {"status": "OK", "counts": counts}


def lib_versions() -> dict:
    """운영 런타임 버전 4종 (P1-4: requirements 상한 고정 근거). 실패해도 진단은 계속."""
    import sys
    from importlib import metadata
    v = {"python": sys.version.split()[0]}
    for key, dist in (("streamlit", "streamlit"), ("pandas", "pandas"), ("st_aggrid", "streamlit-aggrid")):
        try:
            v[key] = metadata.version(dist)
        except Exception as e:  # 미설치·메타데이터 없음
            v[key] = f"(확인 불가: {type(e).__name__})"
    return v


def debug_check() -> dict:
    """secrets 등록 상태 + 실제 API 호출 결과를 진단 (값은 마스킹)"""
    info = {"versions": lib_versions()}   # secrets 오류로 일찍 돌아가도 버전은 보이게 맨 앞
    try:
        url = st.secrets["supabase"].get("url", "")
        info["url_set"] = bool(url)
        info["url_preview"] = url[:50] + "..." if len(url) > 50 else url
    except Exception as e:
        info["secrets_section_error"] = str(e)
        return info

    try:
        sr_key = st.secrets["supabase"].get("service_role_key", "")
        an_key = st.secrets["supabase"].get("anon_key", "")
        info["service_role_set"] = bool(sr_key)
        info["service_role_length"] = len(sr_key) if sr_key else 0
        info["service_role_preview"] = ("설정됨 (본문은 표시하지 않음)" if sr_key else "(없음)")
        info["service_role_is_jwt"] = sr_key.startswith("eyJ") if sr_key else False
        info["service_role_role_field"] = (
            "service_role" if sr_key and "service_role" in sr_key else
            ("anon" if sr_key and "anon" in sr_key else "(unknown)")
        )
        info["anon_key_set"] = bool(an_key)
    except Exception as e:
        info["key_error"] = str(e)
        return info

    # 실제 API 호출
    try:
        full_url = f"{url}/rest/v1/products?select=*&limit=1"
        info["test_url"] = full_url[:80] + "..." if len(full_url) > 80 else full_url
        r = requests.get(
            full_url,
            headers={"apikey": sr_key, "Authorization": f"Bearer {sr_key}",
                     "Prefer": "count=exact"},
            timeout=10,
        )
        info["test_status"] = r.status_code
        info["test_content_range"] = r.headers.get("content-range", "(없음)")
        info["test_response_first_300"] = r.text[:300]
    except Exception as e:
        info["test_error"] = str(e)
    return info


# ─── 읽기 캐시 (2026-09-17 성능 조치) ───
# 마스터성 테이블은 읽기가 잦고(화면당 20~60 회 왕복 × 220ms) 쓰기는 드물다.
# 프로세스 공유 캐시(st.cache_data) 로 5분 보관하고, 이 모듈을 거치는
# insert/update/delete 가 그 테이블을 건드리면 즉시 비운다. 원장·작업지시·
# 수주처럼 매 처리마다 바뀌는 테이블은 캐시하지 않는다. MCP 등 외부 SQL 로
# 마스터를 고친 경우는 TTL(5분) 후 반영 — 급하면 clear_cache().
CACHED_TABLES = frozenset({
    "products", "materials", "vendors", "bom", "product_routing",
    "product_op_std", "product_op_machine", "machines",
    "customer_part_mapping",
})
CACHE_TTL = 300
# 그 외(원장·작업지시·수주·뷰) 도 짧게 캐시한다 (2026-09-17 실측: 화면 시간의
# 95% 가 DB 왕복, 화면당 20~30회 × 240ms). 이 앱의 모든 쓰기는 이 모듈을 거치므로
# 어떤 테이블이든 쓰기가 일어나면 캐시 전체를 비워 앱 안에서는 항상 최신이다.
# 외부(MCP SQL 등) 변경만 최대 TTL 만큼 늦게 보인다.
CACHE_TTL_TX = 60

# 조회 상한 감지: limit 이상 행이 오면(= 딱 맞게 잘렸을 가능성) 세션에 기록.
# 작은 limit(최근 N건 조회) 은 의도된 것이라 제외. 화면 끝에서 관리자에게 표시.
TRUNC_MIN_LIMIT = 200


def _fetch_raw(table: str, select: str, filter_query: str, limit: int) -> list:
    url = f"{_url()}/rest/v1/{table}?select={select}&limit={limit}"
    if filter_query:
        url += f"&{filter_query}"
    r = requests.get(url, headers=_headers(), timeout=30)
    if r.status_code not in (200, 206):
        raise RuntimeError(f"{table} fetch {r.status_code}: {r.text[:200]}")
    return r.json()


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def _fetch_cached(table: str, select: str, filter_query: str, limit: int) -> list:
    return _fetch_raw(table, select, filter_query, limit)


@st.cache_data(ttl=CACHE_TTL_TX, show_spinner=False)
def _fetch_cached_tx(table: str, select: str, filter_query: str, limit: int) -> list:
    return _fetch_raw(table, select, filter_query, limit)


def clear_cache():
    """읽기 캐시 전체 비우기 (이 모듈의 모든 쓰기 후 자동, 외부 변경 시 수동)."""
    for f in (_fetch_cached, _fetch_cached_tx, _fetch_all_cached):
        try:
            f.clear()
        except Exception:
            pass


def _note_truncation(table: str, limit: int, n: int):
    if limit < TRUNC_MIN_LIMIT or n < limit:
        return
    try:
        st.session_state.setdefault("_fetch_truncated", {})[table] = limit
    except Exception:
        pass


def fetch(table: str, select: str = "*", filter_query: str = "",
          limit: int = 1000, cache: bool | None = None) -> list:
    """SELECT — 페이지네이션은 호출자가 처리.

    cache: None 이면 캐시(마스터 5분, 그 외 60초), False 로 끄기.
    """
    use_cache = True if cache is None else bool(cache)
    t0 = time.perf_counter()
    if not use_cache:
        rows = _fetch_raw(table, select, filter_query, limit)
    elif table in CACHED_TABLES:
        rows = _fetch_cached(table, select, filter_query, limit)
    else:
        rows = _fetch_cached_tx(table, select, filter_query, limit)
    _note_truncation(table, limit, len(rows))
    # 런 단위 조회 프로파일 (관리자 사이드바 진단용) — (테이블, ms, 캐시여부)
    try:
        st.session_state.setdefault("_fetch_prof", []).append(
            (table, (time.perf_counter() - t0) * 1000.0, use_cache))
    except Exception:
        pass
    return rows


# 페이지 반복 조회의 결정적 정렬·중복 제거에 쓰는 테이블별 기본 키(fetch_all).
PK_OF = {
    "so_delivery_schedule": "sched_id", "sales_order_items": "soi_id", "sales_orders": "so_id",
    "inventory_transactions": "txn_id", "shipment_items": "si_id", "shipments": "shipment_id",
    "shipment_allocations": "alloc_id", "purchase_order_items": "poi_id",
    "purchase_orders": "po_id", "products": "product_id", "materials": "material_id",
}
FETCH_ALL_PAGE = 1000          # PostgREST 요청당 최대 행(Supabase 기본 db-max-rows)


def _fetch_all_raw(table: str, sel: str, base: str, page: int, max_rows: int, pk: str):
    """페이지 반복 본체 — 페이지마다 cache=False(페이지별 캐시가 서로 다른 시점을 섞지 않게).
    반환 (rows, truncated). max_rows 에 딱 닿으면 1행 탐색으로 실제 남은 행이 있는지 본다."""
    rows, seen, off = [], set(), 0
    while True:
        n = min(page, max_rows - off)
        pg = fetch(table, sel, f"{base}&offset={off}" if base else f"offset={off}",
                   limit=n, cache=False)
        for r in pg:
            k = r.get(pk)
            if k is not None:
                if k in seen:
                    continue
                seen.add(k)
            rows.append(r)
        if len(pg) < n:
            return rows, False
        off += n
        if off >= max_rows:
            probe = fetch(table, sel, f"{base}&offset={off}" if base else f"offset={off}",
                          limit=1, cache=False)
            return rows, bool(probe)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def _fetch_all_cached(table: str, sel: str, base: str, page: int, max_rows: int, pk: str):
    """fetch_all 결과 전체를 한 단위로 캐시(핫픽스 2 r2 H1) — 페이지별 캐시는 쓰지 않는다."""
    return _fetch_all_raw(table, sel, base, page, max_rows, pk)


def fetch_all(table: str, select: str = "*", filter_query: str = "", *,
              page: int = FETCH_ALL_PAGE, max_rows: int = 20000, order: str | None = None,
              cache: bool | None = None, pk: str | None = None):
    """offset 페이지 반복으로 끝까지 읽는다 → (rows, truncated).

    PostgREST 는 요청당 최대 1,000행이라 `fetch(limit=2000)` 도 1,000 에서 잘리고 len < limit
    라 절단도 감지되지 않는다(2026-10-27 출고 등록 회차 조회 사고, 핫픽스 ab824aa).
    - 정렬: order(예 "due_date.asc,seq.asc") 뒤에 기본 키를 붙여 페이지 경계가 결정적이다.
      order 가 없으면 기본 키 오름차순. filter_query 에 order= 를 넣지 말 것(order 인자로).
    - 중복 제거: 기본 키가 select 에 없으면 붙여 읽고, 같은 키는 한 번만.
    - 캐시(r2): 페이지 조회는 항상 cache=False, 결과 전체를 한 단위로 캐시(_fetch_all_cached,
      CACHE_TTL). cache=False 면 우회. clear_cache() 가 함께 지운다.
    - **스냅샷 아님**: 페이지 사이에 행이 삽입·삭제되면 경계에서 누락이 생길 수 있다(중복은 제거).
      동시성은 P3 범위.
    - max_rows 를 넘는 행이 있으면 truncated=True(호출자가 현장 안내) + 관리자 상한 기록.
      끝까지 읽은 경우에는 페이지마다 fetch 가 남긴 상한 기록을 되돌린다.
    - 인자 검증(r2 M3·M4): 기본 키(PK_OF 또는 pk) 필수, 1 <= page <= 1000(1,000 초과는 서버 상한에
      잘려 절단 감지 불가), max_rows 양수.
    """
    if "order=" in (filter_query or ""):
        raise ValueError("fetch_all: 정렬은 order 인자로(filter_query 에 order= 금지)")
    pk = pk or PK_OF.get(table)
    if not pk:
        raise ValueError(f"fetch_all: {table} 의 기본 키를 모름 — PK_OF 에 추가하거나 pk= 로 넘길 것")
    if not isinstance(page, int) or not (1 <= page <= FETCH_ALL_PAGE):
        raise ValueError(f"fetch_all: page 는 1~{FETCH_ALL_PAGE} (받음 {page!r})")
    if not isinstance(max_rows, int) or max_rows <= 0:
        raise ValueError(f"fetch_all: max_rows 는 양수 (받음 {max_rows!r})")
    sel = select
    if select.strip() != "*" and pk not in [c.strip() for c in select.split(",")]:
        sel = f"{select},{pk}"
    ords = [o.strip() for o in (order or "").split(",") if o.strip()]
    if not any(o.split(".")[0] == pk for o in ords):
        ords.append(f"{pk}.asc")
    base = "&".join(x for x in (filter_query, f"order={','.join(ords)}") if x)
    try:
        _prev = dict(st.session_state.get("_fetch_truncated") or {})
    except Exception:
        _prev = None
    if cache is False:
        rows, truncated = _fetch_all_raw(table, sel, base, page, max_rows, pk)
    else:
        rows, truncated = _fetch_all_cached(table, sel, base, page, max_rows, pk)
    if _prev is not None:
        try:
            _ft = st.session_state.setdefault("_fetch_truncated", {})
            if truncated:
                _ft[table] = max_rows
            elif table in _prev:
                _ft[table] = _prev[table]
            else:
                _ft.pop(table, None)
        except Exception:
            pass
    return rows, truncated


def fetch_one(table: str, filter_query: str, select: str = "*"):
    rows = fetch(table, select, filter_query, limit=1)
    return rows[0] if rows else None


def insert(table: str, records: list[dict]) -> int:
    """INSERT bulk"""
    if not records: return 0
    r = requests.post(
        f"{_url()}/rest/v1/{table}",
        headers={**_headers(), "Prefer": "return=minimal"},
        data=json.dumps(records, ensure_ascii=False, default=str),
    )
    if r.status_code not in (200, 201, 204):
        log_error("db_write", f"{table} insert {r.status_code}: {r.text[:200]}",
                  table_name=table)
        raise RuntimeError(f"{table} insert {r.status_code}: {r.text[:200]}")
    clear_cache()
    return len(records)


def update(table: str, filter_query: str, fields: dict) -> bool:
    r = requests.patch(
        f"{_url()}/rest/v1/{table}?{filter_query}",
        headers={**_headers(), "Prefer": "return=minimal"},
        data=json.dumps(fields, ensure_ascii=False, default=str),
    )
    clear_cache()
    if r.status_code not in (200, 204):
        log_error("db_write", f"{table} update {r.status_code}: {r.text[:200]}",
                  table_name=table)
    return r.status_code in (200, 204)


def update_count(table: str, filter_query: str, fields: dict,
                 select: str = "*") -> int:
    """UPDATE 후 실제로 바뀐 행 수. PostgREST 는 0행 매치여도 204 라 `update()` 의
    True 만으로는 "조건에 맞는 행이 있었는지"를 알 수 없다 — 상태 조건부 갱신
    (`status=eq.DRAFT`)처럼 행 수가 의미 있는 곳에서 쓴다. 실패는 -1.
    필터 없는 전체 갱신 금지. select 로 돌려받을 컬럼을 줄일 수 있다."""
    if not filter_query or not filter_query.strip():
        raise ValueError("update_count: filter_query 필수 (전체 갱신 방지)")
    r = requests.patch(
        f"{_url()}/rest/v1/{table}?{filter_query}&select={select}",
        headers={**_headers(), "Prefer": "return=representation"},
        data=json.dumps(fields, ensure_ascii=False, default=str),
        timeout=(5, 30),
    )
    clear_cache()
    if r.status_code not in (200, 204):
        log_error("db_write", f"{table} update {r.status_code}: {r.text[:200]}",
                  table_name=table)
        return -1
    try:
        return len(r.json()) if r.text else 0
    except Exception:
        return 0


def delete(table: str, filter_query: str) -> int:
    """DELETE — 필터 없는 전체 삭제 금지. 삭제된 행 수 반환."""
    if not filter_query or not filter_query.strip():
        raise ValueError("delete: filter_query 필수 (전체 삭제 방지)")
    r = requests.delete(
        f"{_url()}/rest/v1/{table}?{filter_query}",
        headers={**_headers(), "Prefer": "return=representation"},
    )
    if r.status_code not in (200, 204):
        log_error("db_write", f"{table} delete {r.status_code}: {r.text[:200]}",
                  table_name=table)
        raise RuntimeError(f"{table} delete {r.status_code}: {r.text[:200]}")
    clear_cache()
    try:
        return len(r.json())
    except Exception:
        return 0


# ═══════════════════════════════════════════════════════════════
# 오류 기록 (migration 067 app_errors) — 2026-10-13, L3-S 계획서 C 항목
# ═══════════════════════════════════════════════════════════════
# 어떤 경우에도 예외를 내지 않는다. 내부에서 insert() 를 쓰지 않고(재귀 금지)
# requests.post 를 직접, 짧은 timeout 으로 친다. 캐시는 건드리지 않는다.
# 같은 내용(detail 앞 200자)은 60초에 한 번만 — 세션이 아니라 모듈 전역이라
# 스크립트(백업·요약)에서 불러도 동작한다.
_ERR_RECENT: dict = {}
_ERR_DEDUP_SEC = 60.0
_ERR_DOWN_KEY = "__down__"      # 기록 POST 자체가 실패하면 60초 동안 전부 건너뜀
_ERR_RATE_MAX = 30              # 분당 기록 상한 (폭주 방지)
_ERR_RATE = [0.0, 0]            # [창 시작 monotonic, 건수]
_ERR_DETAIL_MAX = 500
_ERR_TB_MAX = 4000
_ERR_KINDS = ("db_write", "unhandled", "rpc_fallback", "rpc_rejected", "manual")


def _error_context() -> dict:
    """앱이 실행 시작 때 session_state['_err_ctx'] 에 둔 {page, user} — 없으면 빈 값."""
    try:
        ctx = st.session_state.get("_err_ctx") or {}
        return {"page": ctx.get("page"), "user_name": ctx.get("user")}
    except Exception:
        return {"page": None, "user_name": None}


def log_error(kind: str, detail, *, page=None, user_name=None,
              table_name=None, tb=None) -> bool:
    """오류 한 건을 app_errors 에 남긴다. 기록 성공이면 True, 아니면 False.

    kind: db_write | unhandled | rpc_fallback | rpc_rejected | manual
    detail 은 500자, tb 는 4000자로 자른다. 헤더·키·URL 은 넣지 않는다.
    """
    try:
        d = str(detail if detail is not None else "")[:_ERR_DETAIL_MAX]
        key = d[:200]
        now = time.monotonic()
        down = _ERR_RECENT.get(_ERR_DOWN_KEY)
        if down is not None and now - down < _ERR_DEDUP_SEC:
            return False               # 기록 서버가 안 받는 중 — 지연 증폭 방지
        last = _ERR_RECENT.get(key)
        if last is not None and now - last < _ERR_DEDUP_SEC:
            return False
        if now - _ERR_RATE[0] >= 60.0:
            _ERR_RATE[0], _ERR_RATE[1] = now, 0
        if _ERR_RATE[1] >= _ERR_RATE_MAX:
            return False
        _ERR_RATE[1] += 1
        _ERR_RECENT[key] = now
        if len(_ERR_RECENT) > 500:
            for k, _ in sorted(list(_ERR_RECENT.items()),
                               key=lambda kv: kv[1])[:250]:
                _ERR_RECENT.pop(k, None)
        ctx = _error_context()
        rec = {
            "kind": kind if kind in _ERR_KINDS else "manual",
            "detail": d,
            "page": page or ctx.get("page"),
            "user_name": user_name or ctx.get("user_name"),
            "table_name": table_name,
            "traceback": (str(tb)[:_ERR_TB_MAX] if tb else None),
        }
        try:
            r = requests.post(
                f"{_url()}/rest/v1/app_errors",
                headers={**_headers(), "Prefer": "return=minimal"},
                data=json.dumps([rec], ensure_ascii=False, default=str),
                timeout=(2, 3),
            )
            ok = r.status_code in (200, 201, 204)
        except Exception:
            ok = False
        if not ok:
            _ERR_RECENT[_ERR_DOWN_KEY] = now
        return ok
    except Exception:
        return False


_HOOK_INSTALLED = False


def install_uncaught_hook() -> bool:
    """미처리 예외 기록 — Streamlit 이 사용자 스크립트 예외를 처리할 때 남기는
    로그('streamlit.error_util' 로거, exc_info 포함)에 핸들러를 붙인다.
    페이지 라우팅 전체를 try 로 감싸지 않아도 되고(17,000줄 재들여쓰기 회피),
    st.rerun/st.stop 은 예외 처리 경로를 타지 않아 기록되지 않는다.
    logger.enableRich 가 켜져 있으면 Streamlit 이 로그 대신 rich 로 출력해 이
    훅이 비고, logger.level 을 error 보다 높이면 기록이 꺼진다 — 이 앱은 둘 다
    기본값이다. 로거 이름은 Streamlit 내부라 버전 업 때 CI 의
    test_db_log_error.py 훅 테스트가 게이트다. 한 프로세스에 한 번만 붙는다."""
    global _HOOK_INSTALLED
    if _HOOK_INSTALLED:
        return True
    try:
        import logging
        import traceback as _tb

        class _AppErrorHandler(logging.Handler):
            def emit(self, record):
                try:
                    ei = record.exc_info
                    if not ei or not ei[1]:
                        return
                    ex = ei[1]
                    log_error("unhandled",
                              f"{type(ex).__name__}: {str(ex)[:300]}",
                              tb="".join(_tb.format_exception(*ei)))
                except Exception:
                    pass

        h = _AppErrorHandler(level=logging.ERROR)
        h.set_name("wsapp_app_errors")
        lg = logging.getLogger("streamlit.error_util")
        if not any(getattr(x, "name", "") == "wsapp_app_errors"
                   for x in lg.handlers):
            lg.addHandler(h)
        _HOOK_INSTALLED = True
        return True
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════
# RPC (PostgREST /rpc) — L3-S 계획서 공통 전제, 2026-10-13
# ═══════════════════════════════════════════════════════════════
class RpcUnavailable(Exception):
    """서버가 함수를 실행하지 않았음이 확실 — HTTP 404 + PGRST202
    (함수 없음 또는 파라미터 이름 불일치). 호출부는 기존 경로로 폴백하고,
    여기서 log_error('rpc_fallback') 로 남긴다."""


class RpcRejected(Exception):
    """함수가 RAISE 로 거부 — 미반영 확정, 재시도 가능. code/message 보존."""

    def __init__(self, code: str, message: str, status: int = 400, hint: str = ""):
        super().__init__(f"{code}: {message}")
        self.code, self.message, self.status = code, message, status
        self.hint = hint or ""     # RAISE … USING HINT (예: 076 blocked → 전표 번호 목록)


class RpcTransportError(Exception):
    """Timeout/ConnectionError/5xx/본문 없음 — 반영 여부 불명. 자동 재시도 금지."""


def rpc(name: str, params=None, timeout=(5, 30)):
    """POST /rest/v1/rpc/<name>. 성공은 JSON 본문이 있을 때만(dict/list 반환).

    예외: RpcUnavailable / RpcRejected / RpcTransportError (위 docstring).
    성공·거부 뒤에는 clear_cache() — 거부 원인이 오래된 화면인 경우가 많다.
    """
    try:
        r = requests.post(
            f"{_url()}/rest/v1/rpc/{name}",
            headers=_headers(),
            data=json.dumps(params or {}, ensure_ascii=False, default=str),
            timeout=timeout,
        )
    except Exception as e:   # Timeout, ConnectionError, …
        clear_cache()        # 반영됐을 수 있다 — 호출부의 재검사가 캐시를 읽지 않게
        raise RpcTransportError(f"{name}: {type(e).__name__}") from e
    body = None
    try:
        body = r.json() if r.text else None
    except Exception:
        body = None
    is_dict = isinstance(body, dict)
    code0 = str(body.get("code") or "") if is_dict else ""
    if r.status_code == 404 and code0.startswith("PGRST202"):
        log_error("rpc_fallback", f"{name}: {str(body.get('message'))[:200]}")
        raise RpcUnavailable(f"{name}: {body.get('message')}")
    if code0.startswith("PGRST203"):
        # 오버로드 모호(HTTP 300) — 함수는 실행되지 않았고 설정 오류. 거부로.
        log_error("rpc_rejected", f"{name}: {code0} {str(body.get('message'))[:200]}")
        raise RpcRejected(code0, str(body.get("message") or ""), r.status_code)
    if code0 in ("55P03", "57014", "40P01"):
        # 잠금 대기 초과·문장 취소·교착 — PostgREST 는 500 으로 보내지만 함수는
        # 롤백된 것이 확실하다(미반영 확정, 재시도 가능) (2026-10-13 Data 리뷰)
        clear_cache()
        log_error("rpc_rejected", f"{name}: {code0} {str(body.get('message'))[:200]}")
        raise RpcRejected(code0, str(body.get("message") or ""), r.status_code)
    if r.status_code >= 500 or r.status_code == 408 \
            or (r.status_code == 404 and not is_dict) \
            or 300 <= r.status_code < 400:
        clear_cache()
        raise RpcTransportError(f"{name}: HTTP {r.status_code}")
    if r.status_code >= 400:
        clear_cache()
        code = str(body.get("code") or r.status_code) if is_dict else str(r.status_code)
        msg = str(body.get("message") or r.text[:200]) if is_dict else r.text[:200]
        extra = " | ".join(str(body.get(k)) for k in ("hint", "details")
                           if is_dict and body.get(k))
        log_error("rpc_rejected", f"{name}: {code} {msg[:200]}"
                  + (f" | {extra[:200]}" if extra else ""))
        raise RpcRejected(code, msg, r.status_code,
                          hint=str(body.get("hint") or "") if is_dict else "")
    if body is None or not (200 <= r.status_code < 300):
        clear_cache()
        raise RpcTransportError(f"{name}: 응답 본문 없음 (HTTP {r.status_code})")
    clear_cache()
    return body
