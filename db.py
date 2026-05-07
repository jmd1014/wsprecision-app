"""
Supabase DB 연결 공통 모듈
- st.secrets에서 자격증명 로드
- service_role 사용 (관리자 작업), anon은 향후 RLS 정책 추가 시 사용
"""
import streamlit as st
from supabase import create_client, Client


@st.cache_resource
def get_client(role: str = "service_role") -> Client:
    """Supabase 클라이언트 — service_role(서버 권한) 또는 anon(공개)"""
    url = st.secrets["supabase"]["url"]
    if role == "service_role":
        key = st.secrets["supabase"]["service_role_key"]
    else:
        key = st.secrets["supabase"]["anon_key"]
    return create_client(url, key)


def health_check() -> dict:
    """DB 연결 상태 + 테이블 행 수 확인"""
    try:
        client = get_client()
        tables = ["products", "vendors", "materials", "bom", "drawings",
                  "sales_ledger", "purchase_ledger"]
        counts = {}
        for t in tables:
            try:
                r = client.table(t).select("*", count="exact").limit(1).execute()
                counts[t] = r.count if r.count is not None else 0
            except Exception as e:
                counts[t] = f"ERR: {str(e)[:40]}"
        return {"status": "OK", "counts": counts}
    except Exception as e:
        return {"status": "FAIL", "error": str(e)}
