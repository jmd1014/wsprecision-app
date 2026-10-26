"""복원 리허설 스크립트 안전장치 정적 검사 (P1-1, 2026-10-26).

scripts/restore_local.py 는 운영(Supabase REST)에 GET 만 하고, 쓰기는 로컬 wsapp_restore 에만 한다.
"""
import ast
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "restore_local.py")


def _src():
    with open(SCRIPT, encoding="utf-8") as f:
        return f.read()


def test_no_write_calls_to_production():
    tree = ast.parse(_src())
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            owner = node.func.value
            # requests.post/patch/put/delete, 앱 db 모듈 쓰기 함수
            if isinstance(owner, ast.Name) and owner.id == "requests" and node.func.attr != "get":
                bad.append((node.lineno, f"requests.{node.func.attr}"))
            if isinstance(owner, ast.Name) and owner.id == "db" and node.func.attr in (
                    "insert", "update", "update_count", "delete", "rpc"):
                bad.append((node.lineno, f"db.{node.func.attr}"))
    assert not bad, bad
    src = _src()
    assert "import db" not in src                       # 앱 db 모듈(운영 쓰기 경로)을 쓰지 않는다
    # 운영 REST 는 prod_get 한 곳에서만
    assert src.count("/rest/v1/") == 1 and "def prod_get(" in src


def test_local_only_and_fixed_target_guards():
    src = _src()
    assert 'TARGET_DB = "wsapp_restore"' in src and 'ADMIN_DB = "postgres"' in src
    assert 'LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")' in src
    assert "if host not in LOCAL_HOSTS:" in src
    assert "if db not in (ADMIN_DB, TARGET_DB):" in src
    assert "if dbname not in (ADMIN_DB, TARGET_DB):" in src     # connect() 도 다시 확인
    # DROP/CREATE DATABASE 는 TARGET_DB 상수로만
    stmts = [ln for ln in src.splitlines() if "execute(" in ln and re.search(r"(drop|create) database", ln, re.I)]
    assert len(stmts) == 2, stmts
    for stmt in stmts:
        assert "TARGET_DB" in stmt, stmt
    # DSN 은 [restore_pg] 에서만, 비밀번호는 로그에 찍지 않는다
    assert 'sec["restore_pg"]["dsn"]' in src
    assert "비밀번호 표시 안 함" in src and "password']}" not in src
