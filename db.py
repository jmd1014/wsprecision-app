"""
Supabase REST API 직접 호출 (supabase-py 대신 requests 사용)
- supabase-py의 응답 파싱 호환 이슈를 우회
- 이미 import 단계에서 검증된 방식
"""
import streamlit as st
import requests
import json


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
        if r.status_code != 200:
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


def fetch(table: str, select: str = "*", filter_query: str = "", limit: int = 1000) -> list:
    """SELECT — 페이지네이션은 호출자가 처리"""
    url = f"{_url()}/rest/v1/{table}?select={select}&limit={limit}"
    if filter_query:
        url += f"&{filter_query}"
    r = requests.get(url, headers=_headers(), timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"{table} fetch {r.status_code}: {r.text[:200]}")
    return r.json()


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
    return len(records)


def update(table: str, filter_query: str, fields: dict) -> bool:
    r = requests.patch(
        f"{_url()}/rest/v1/{table}?{filter_query}",
        headers={**_headers(), "Prefer": "return=minimal"},
        data=json.dumps(fields, ensure_ascii=False, default=str),
    )
    return r.status_code in (200, 204)
