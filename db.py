"""
Supabase REST API 직접 호출 (supabase-py 대신 requests 사용)
- supabase-py의 응답 파싱 호환 이슈를 우회
- 이미 import 단계에서 검증된 방식
"""
import streamlit as st
import requests
import json
import time


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


def debug_check() -> dict:
    """secrets 등록 상태 + 실제 API 호출 결과를 진단 (값은 마스킹)"""
    info = {}
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
        info["service_role_preview"] = (sr_key[:25] + "..." + sr_key[-10:]) if sr_key else "(없음)"
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
    for f in (_fetch_cached, _fetch_cached_tx):
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
    return r.status_code in (200, 204)


def delete(table: str, filter_query: str) -> int:
    """DELETE — 필터 없는 전체 삭제 금지. 삭제된 행 수 반환."""
    if not filter_query or not filter_query.strip():
        raise ValueError("delete: filter_query 필수 (전체 삭제 방지)")
    r = requests.delete(
        f"{_url()}/rest/v1/{table}?{filter_query}",
        headers={**_headers(), "Prefer": "return=representation"},
    )
    if r.status_code not in (200, 204):
        raise RuntimeError(f"{table} delete {r.status_code}: {r.text[:200]}")
    clear_cache()
    try:
        return len(r.json())
    except Exception:
        return 0
