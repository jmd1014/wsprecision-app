# -*- coding: utf-8 -*-
"""취소(CANCELLED) 출고 전표는 종착 상태 — 불변식 테스트 (2026-11-06 재발 방지 소묶음 B, 후보 53).

CLAUDE.md 출고 절 "CANCELLED 는 종착 상태 — 취소 전표는 되살리지 않는다"의 테스트 짝.
납기 입력의 회차 참조 검사(utils/sched_save.sched_refs_message)는 취소 전표 라인을 차단 사유에서 뺀다
(2026-11-05 핫픽스 2). 이 전제가 깨지면(취소 → 작성중·확정으로 되돌리는 경로가 생기면) 그 검사부터 다시 봐야 한다.

- B-T3(정적, qa M-1 · r2 에서 qa M-2·Codex MEDIUM 4건 반영): 파이썬 파일(streamlit_app.py · utils/** · db.py · app/**)의
  `"shipments"` 문자열을 구문 트리(ast)로 전부 모아
  · 조회 호출의 인자 / dict 키 / 첨자면 통과, 쓰기 호출(insert·update·update_count·upsert·delete·_uc)이면 승인된 쓰기
    자리 목록(streamlit_app.py: insert 1 · update 3 · _uc 1)과 대조, 그 밖(변수 대입·비교 등)은 실패
  · 승인된 쓰기의 상태값을 해석: insert = "DRAFT" 하나, update = "CANCELLED" 만, 해석 못 하면(변수 값) 실패
  · 조건부 헬퍼 _cf_set_status_if_draft 의 실제 필터 대입문(docstring 제외)에 status=eq.DRAFT
  · "status": "CONFIRMED" dict 는 _cf_set_status_if_draft( 인자 안에만
  마이그레이션: UPDATE shipments [AS] [별칭] SET … status = X(CANCELLED 외) 는 WHERE 에 status = 'DRAFT' 필수,
  INSERT … shipments … ON CONFLICT … DO UPDATE 는 상태를 바꾸지 않아야 함.
  목표는 완벽한 정적 분석이 아니라 변이 V1~V6(검토 세션 r2 지시)을 전부 잡는 것 — test_b_t3_catches_variant 참고.
- B-T2(화면, qa M-2): 취소 전표 라인이 이미 없는 회차를 가리켜도 출고 전표 화면이 견딘다.
"""
import ast
import glob
import importlib.util
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
APP_FILE = os.path.join(ROOT, "streamlit_app.py")
MIG_DIR = os.path.join(ROOT, "supabase", "migrations")
_HAS_ST = importlib.util.find_spec("streamlit") is not None

RECHECK = ("— 새 전표 상태 쓰기 경로입니다. CLAUDE.md 출고 절 'CANCELLED 는 종착 상태' 와 "
           "utils/sched_save.sched_refs_message(취소 전표 라인 무시)를 다시 검토한 뒤 이 테스트를 고치세요.")
WRITE_METHODS = {"insert", "update", "update_count", "upsert", "delete", "_uc"}
# 승인된 shipments 쓰기 자리(파일, 메서드) — 줄 번호가 아니라 종류·개수로 고정한다
APPROVED = sorted([("streamlit_app.py", "insert"), ("streamlit_app.py", "_uc"),
                   ("streamlit_app.py", "update"), ("streamlit_app.py", "update"), ("streamlit_app.py", "update")])
HELPER = "_cf_set_status_if_draft"


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def py_sources(root=ROOT):
    """검사 대상 파이썬 파일 {상대 경로: 소스}."""
    files = [os.path.join(root, "streamlit_app.py"), os.path.join(root, "db.py")]
    for sub in ("utils", "app"):
        files += glob.glob(os.path.join(root, sub, "**", "*.py"), recursive=True)
    return {os.path.relpath(p, root).replace(os.sep, "/"): _read(p) for p in files if os.path.isfile(p)}


def sql_sources(mig_dir=MIG_DIR):
    return {os.path.basename(p): _read(p) for p in sorted(glob.glob(os.path.join(mig_dir, "*.sql")))}


def _parents(tree):
    par = {}
    for n in ast.walk(tree):
        for c in ast.iter_child_nodes(n):
            par[c] = n
    return par


def _method(call):
    f = call.func
    return f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else None)


def _is_str(n, v=None):
    return isinstance(n, ast.Constant) and isinstance(n.value, str) and (v is None or n.value == v)


def _status_in_dict(d):
    """dict 리터럴의 "status" 값들 — 문자열이 아니면 None(해석 불가)."""
    out = []
    for k, v in zip(d.keys, d.values):
        if _is_str(k, "status"):
            out.append(v.value if _is_str(v) else None)
        elif k is None:                        # {**other} — 펼친 dict 는 해석 불가
            out.append(None)
    return out


def _scope(node, par):
    while node in par:
        node = par[node]
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
            return node
    return node


def _var_status(var, call, par):
    """쓰기 호출에 넘긴 변수 payload 의 상태값 — 같은 범위에서 호출 앞(80줄 안)의 대입·update·첨자 대입을 읽는다.
    반환 (값 목록, 정의 찾음 여부). 문자열이 아닌 값은 None."""
    scope = _scope(call, par)
    lo = call.lineno - 80
    vals, found = [], False
    for n in ast.walk(scope):
        ln = getattr(n, "lineno", 0)
        if not (lo <= ln < call.lineno):
            continue
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and t.id == var:
                    found = True
                    vals += _status_in_dict(n.value) if isinstance(n.value, ast.Dict) else [None]
                elif isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id == var:
                    if _is_str(t.slice, "status") or not _is_str(t.slice):
                        vals.append(n.value.value if _is_str(n.value) else None)
        elif (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ("update", "setdefault")
              and isinstance(n.func.value, ast.Name) and n.func.value.id == var):
            for a in n.args:
                vals += _status_in_dict(a) if isinstance(a, ast.Dict) else [None]
            for kw in n.keywords:
                if kw.arg == "status" or kw.arg is None:
                    vals.append(kw.value.value if _is_str(kw.value) else None)
    return vals, found


def _helper_filter_ok(fn):
    """헬퍼의 실제 코드(docstring 제외): status=eq.DRAFT 가 든 필터 변수를 _uc(\"shipments\", 그 변수, …) 에 넘긴다."""
    flt = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Assign) and "status=eq.DRAFT" in ast.unparse(n.value):
            flt |= {t.id for t in n.targets if isinstance(t, ast.Name)}
    for n in ast.walk(fn):
        if isinstance(n, ast.Call) and _method(n) == "_uc" and len(n.args) >= 2 and _is_str(n.args[0], "shipments"):
            a1 = n.args[1]
            if (isinstance(a1, ast.Name) and a1.id in flt) or "status=eq.DRAFT" in ast.unparse(a1):
                return True
    return False


def check_py(sources):
    """위반 목록(빈 목록이면 통과). sources = {상대 경로: 소스}. 변이 확인(02b·test_b_t3_catches_variant)도 이 함수를 쓴다."""
    bad, writes = [], []
    for path, src in sorted(sources.items()):
        tree = ast.parse(src)
        par = _parents(tree)
        helper_args = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and _method(n) == HELPER:
                for a in list(n.args) + [k.value for k in n.keywords]:
                    helper_args |= set(ast.walk(a))
                    if isinstance(a, ast.Dict):
                        for v in _status_in_dict(a):
                            if v not in ("CONFIRMED", "CANCELLED"):
                                bad.append(f"{path}:{n.lineno}: 조건부 헬퍼 상태 값 {v!r}")
        for n in ast.walk(tree):                # 헬퍼 인자를 다 모은 뒤 두 번째로 훑는다
            if isinstance(n, ast.Dict) and "CONFIRMED" in _status_in_dict(n) and n not in helper_args:
                bad.append(f"{path}:{n.lineno}: \"status\": \"CONFIRMED\" 가 {HELPER}( 인자 밖 {RECHECK}")
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == HELPER and not _helper_filter_ok(n):
                bad.append(f"{path}:{n.lineno}: {HELPER} 의 실제 필터에 status=eq.DRAFT 가 없음 {RECHECK}")
            if not _is_str(n, "shipments"):
                continue
            p = par.get(n)
            if isinstance(p, ast.keyword):
                p = par.get(p)
            if isinstance(p, ast.Dict) and any(k is n for k in p.keys):
                continue                        # dict 키(PK 표·select 표)
            if isinstance(p, ast.Subscript) and p.slice is n:
                continue                        # REFS_SELECT["shipments"] 같은 첨자
            if not isinstance(p, ast.Call):
                bad.append(f"{path}:{n.lineno}: \"shipments\" 가 호출 인자가 아닌 곳({type(p).__name__})에 있음 "
                           f"— 테이블명을 변수에 담은 쓰기를 검사할 수 없음 {RECHECK}")
                continue
            meth = _method(p)
            if meth not in WRITE_METHODS:
                continue                        # 조회·로그 등
            writes.append((path, meth, p, par))
    if sorted((w[0], w[1]) for w in writes) != APPROVED:
        bad.append(f"shipments 쓰기 목록이 바뀜: {[(w[0], w[1], w[2].lineno) for w in writes]} {RECHECK}")
    for path, meth, call, par in writes:
        ln = f"{path}:{call.lineno}"
        if meth == "_uc":
            fn = _scope(call, par)
            if not (isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and fn.name == HELPER):
                bad.append(f"{ln}: 조건부 갱신(_uc)이 {HELPER} 밖에 있음 {RECHECK}")
            continue
        payload = call.args[1] if meth == "insert" and len(call.args) > 1 else (
            call.args[2] if len(call.args) > 2 else next((k.value for k in call.keywords
                                                          if k.arg in ("fields", "records", "data")), None))
        if meth == "insert":
            dicts = payload.elts if isinstance(payload, (ast.List, ast.Tuple)) else [payload]
            vals = []
            for d in dicts:
                vals += _status_in_dict(d) if isinstance(d, ast.Dict) else [None]
            if vals != ["DRAFT"]:
                bad.append(f"{ln}: shipments insert 상태는 \"DRAFT\" 하나여야 함 — {vals} {RECHECK}")
        elif meth == "update":
            if isinstance(payload, ast.Dict):
                vals = _status_in_dict(payload)
            elif isinstance(payload, ast.Name):
                vals, found = _var_status(payload.id, call, par)
                if not found:
                    bad.append(f"{ln}: payload 변수 {payload.id} 의 정의를 찾지 못함(해석 불가) {RECHECK}")
            else:
                vals = [None]
            if any(v != "CANCELLED" for v in vals):
                bad.append(f"{ln}: shipments update 상태 값 {vals} — \"CANCELLED\" 만 허용(None = 해석 불가) {RECHECK}")
        else:
            bad.append(f"{ln}: shipments {meth} 는 승인된 쓰기 종류가 아님 {RECHECK}")
    return bad


_UPD = re.compile(r"UPDATE\s+(?:ONLY\s+)?(?:public\.)?shipments\b(?:\s+(?:AS\s+)?(?!SET\b)(\w+))?\s+SET\s+(.*?);",
                  re.I | re.S)


def check_sql(sources):
    bad = []
    for fn, sql in sorted(sources.items()):
        sql = re.sub(r"--[^\n]*", "", sql)
        for m in _UPD.finditer(sql):
            parts = re.split(r"\bWHERE\b", m.group(2), maxsplit=1, flags=re.I)
            set_part, where = parts[0], (parts[1] if len(parts) > 1 else "")
            for sv in re.findall(r"(?:\b\w+\.)?\bstatus\s*=\s*([^,\s]+)", set_part, re.I):
                if sv.upper() == "'CANCELLED'":
                    continue
                if not re.search(r"(?:\b\w+\.)?\bstatus\s*=\s*'DRAFT'", where, re.I):
                    bad.append(f"{fn}: UPDATE shipments SET status = {sv} 에 WHERE status = 'DRAFT' 없음 {RECHECK}")
        for m in re.finditer(r"INSERT\s+INTO\s+(?:public\.)?shipments\b.*?;", sql, re.I | re.S):
            if re.search(r"ON\s+CONFLICT.*DO\s+UPDATE.*\bstatus\b", m.group(0), re.I | re.S):
                bad.append(f"{fn}: INSERT … shipments … ON CONFLICT DO UPDATE 가 status 를 바꿈 {RECHECK}")
    return bad


def _n_confirm_updates(sources):
    return sum(len([m for m in _UPD.finditer(re.sub(r"--[^\n]*", "", s)) if "CONFIRMED" in m.group(2).upper()])
               for s in sources.values())


def test_b_t3_ship_status_writes_keep_cancelled_terminal():
    src = py_sources()
    assert "streamlit_app.py" in src and any(p.startswith("utils/") for p in src) and "db.py" in src, sorted(src)[:5]
    bad = check_py(src)
    assert not bad, "\n".join(bad)


def test_b_t3_migrations_confirm_only_from_draft():
    sql = sql_sources()
    bad = check_sql(sql)
    assert not bad, "\n".join(bad)
    assert _n_confirm_updates(sql) >= 2, _n_confirm_updates(sql)      # 069·076 — 아무것도 안 보는 상태가 아님


# ── 검사기 자체 대조: 변이 V1~V6(검토 세션 r2 지시) + r1 변이 ① — 사본(메모리)에만 넣는다 ──
def _inject_before(src, anchor, line, indent=24):
    i = src.index(anchor)
    return src[:i] + line + "\n" + " " * indent + src[i:]


def _variant(name):
    py, sql = py_sources(), dict(sql_sources())
    app = py["streamlit_app.py"]
    ins_anchor = '_db.insert("shipments", [{'
    if name == "r1_confirm":
        py["streamlit_app.py"] = _inject_before(app, ins_anchor,
                                                '_db.update("shipments", "shipment_id=eq.1", {"status": "CONFIRMED"})')
    elif name == "V1_alias":
        py["streamlit_app.py"] = _inject_before(app, ins_anchor,
                                                '_dbw.update("shipments", "shipment_id=eq.1", {"status": "DRAFT"})')
    elif name == "V2_table_var":
        py["streamlit_app.py"] = _inject_before(app, ins_anchor,
                                                '_t9 = "shipments"; _db.update(_t9, "shipment_id=eq.1", {"status": "DRAFT"})')
    elif name == "V3_utils":
        py["utils/_v3_mut.py"] = ('import db as _db\n\n\ndef revive(sid):\n'
                                  '    return _db.update("shipments", f"shipment_id=eq.{sid}", {"status": "DRAFT"})\n')
    elif name == "V4_var_status":
        a = '                _hdr_ok9 = False\n                for _try9 in range(3):\n'
        assert app.count(a) == 1, app.count(a)
        py["streamlit_app.py"] = app.replace(a, '                _hdr["status"] = _next_status\n' + a)
    elif name == "V5_helper_filter":
        a = '_flt = f"shipment_id=eq.{_fq(shipment_id)}&status=eq.DRAFT"'
        assert app.count(a) == 1
        py["streamlit_app.py"] = app.replace(a, '_flt = f"shipment_id=eq.{_fq(shipment_id)}"')
    elif name == "V6_sql_alias":
        sql["999_v6_mut.sql"] = "UPDATE shipments AS s SET status = 'CONFIRMED' WHERE s.shipment_id = 1;\n"
    else:
        raise AssertionError(name)
    return check_py(py) + check_sql(sql)


@pytest.mark.parametrize("name", ["r1_confirm", "V1_alias", "V2_table_var", "V3_utils", "V4_var_status",
                                  "V5_helper_filter", "V6_sql_alias"])
def test_b_t3_catches_variant(name):
    bad = _variant(name)
    assert bad, f"변이 {name} 를 놓침"


def test_b_t3_v5_docstring_still_has_draft():
    """V5 는 docstring 의 status=eq.DRAFT 문자열이 남아 있어도 잡아야 한다(Codex r1 MEDIUM)."""
    app = py_sources()["streamlit_app.py"]
    i = app.index(f"def {HELPER}(")
    assert "status=eq.DRAFT" in app[i:app.index("_flt =", i)], "docstring 에 문자열이 있는 상태가 전제"


# ── B-T2(qa M-2): 취소 전표 라인이 없는 회차를 가리켜도 출고 전표 화면이 견딘다 ──
from tests.test_shipment_revision_flow import (  # noqa: E402,F401  (fixture·시드 재사용)
    rev_db, _seed, _open, SHIPMENTS, SHIP_ITEMS, ALLOCS, ROUNDS, INSERTED, UPDATED, DELETED)


@pytest.mark.skipif(not _HAS_ST, reason="streamlit 미설치 — AppTest 불가")
def test_b_t2_cancelled_slip_with_dangling_sched_renders(rev_db):
    _seed()
    SHIPMENTS[0].update({"status": "CANCELLED", "cancelled_at": "2026-09-03T09:00:00",
                         "cancel_reason": "거래처 착오", "rev_no": 1})
    SHIP_ITEMS[0]["sched_id"] = 999                        # 이미 지워진 회차
    assert all(r["sched_id"] != 999 for r in ROUNDS)
    ALLOCS[:] = []                                         # 취소 전표엔 충당 행이 없다(운영 559행 전부 CONFIRMED)
    at = _open()
    next(r for r in at.radio if r.key == "cf_filter").set_value("취소")
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    md = "\n".join(str(x.value) for x in at.markdown)
    tr = [t for t in re.findall(r"<tr[^>]*>.*?</tr>", md, re.S) if "4PDVN-03" in t]
    assert len(tr) == 1, tr
    cells = [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<td[^>]*>.*?</td>", tr[0], re.S)]
    assert "500" in cells, cells                            # r2(qa L-7): 그 행의 수량 칸
    caps = [str(c.value) for c in at.caption]
    assert any("확정 후 취소" in c for c in caps), caps
    assert not INSERTED and not UPDATED and not DELETED, (INSERTED, UPDATED, DELETED)
