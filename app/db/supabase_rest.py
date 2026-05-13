"""
Supabase REST API 클라이언트 (thin wrapper)
- 기존 db.py 함수를 그대로 재export
- 신규 코드는 이 모듈을 import해서 사용 (app/repositories에서)
- 향후 supabase-py로 교체 시 이 파일만 수정하면 됨
"""
import json
import requests
import streamlit as st


def _headers(role: str = "service_role") -> dict:
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


def fetch(table: str, select: str = "*", filter_query: str = "", limit: int = 1000) -> list:
    url = f"{_url()}/rest/v1/{table}?select={select}&limit={limit}"
    if filter_query:
        url += f"&{filter_query}"
    r = requests.get(url, headers=_headers(), timeout=30)
    if r.status_code not in (200, 206):
        raise RuntimeError(f"{table} fetch {r.status_code}: {r.text[:200]}")
    return r.json()


def fetch_one(table: str, filter_query: str, select: str = "*"):
    rows = fetch(table, select, filter_query, limit=1)
    return rows[0] if rows else None


def insert(table: str, records: list[dict]) -> int:
    if not records:
        return 0
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


def rpc(function_name: str, params: dict | None = None):
    """Supabase RPC 호출 (DB 함수 실행)"""
    r = requests.post(
        f"{_url()}/rest/v1/rpc/{function_name}",
        headers=_headers(),
        data=json.dumps(params or {}, default=str),
    )
    if r.status_code not in (200, 201, 204):
        raise RuntimeError(f"rpc {function_name} {r.status_code}: {r.text[:200]}")
    if r.text and r.text.strip():
        try:
            return r.json()
        except Exception:
            return r.text
    return None
