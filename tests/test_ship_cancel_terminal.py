# -*- coding: utf-8 -*-
"""취소(CANCELLED) 출고 전표는 종착 상태 — 불변식 테스트 (2026-11-06 재발 방지 소묶음 B, 후보 53).

CLAUDE.md 출고 절 "CANCELLED 는 종착 상태 — 취소 전표는 되살리지 않는다"의 테스트 짝.
납기 입력의 회차 참조 검사(utils/sched_save.sched_refs_message)는 취소 전표 라인을 차단 사유에서 뺀다
(2026-11-05 핫픽스 2). 이 전제가 깨지면(취소 → 작성중·확정으로 되돌리는 경로가 생기면) 그 검사부터 다시 봐야 한다.

- B-T3(정적, qa M-1): streamlit_app.py 의 shipments 상태 쓰기 목록이 고정돼 있고, CONFIRMED 는 status=eq.DRAFT 조건부
  헬퍼(_cf_set_status_if_draft) 인자로만, DRAFT 는 새 전표 insert 1곳만, 마이그레이션의 CONFIRMED UPDATE 는 모두
  AND status = 'DRAFT'.
- B-T2(화면, qa M-2): 취소 전표 라인이 이미 없는 회차를 가리켜도 출고 전표 화면이 견딘다.
"""
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


def _src(path=None):
    with open(path or APP_FILE, encoding="utf-8") as f:
        return f.read()


def _call_text(src, start):
    """src[start] 부터 첫 '(' 의 짝 ')' 까지(문자열 안 괄호는 대충 무시 — 이 파일의 쓰기 호출엔 충분)."""
    i = src.index("(", start)
    depth, j = 0, i
    in_str = None
    while j < len(src):
        c = src[j]
        if in_str:
            if c == "\\":
                j += 2
                continue
            if c == in_str:
                in_str = None
        elif c in "\"'":
            in_str = c
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return src[start:j + 1]
        j += 1
    raise AssertionError(f"괄호 짝 없음: {src[start:start + 80]!r}")


WRITE_RE = re.compile(r'(_db\.insert|_db\.update_count|_db\.update|_uc)\(\s*"shipments"')
STATUS_RE = re.compile(r'"status"\s*:\s*"([A-Z_]+)"')


def _ship_writes(src):
    return [(m.group(1), m.start(), _call_text(src, m.start())) for m in WRITE_RE.finditer(src)]


def _line(src, pos):
    return src.count("\n", 0, pos) + 1


def _var_status_values(src, pos, var):
    """쓰기 호출 직전(60줄 안)에서 변수 var 를 만들거나 고치는 문장의 "status": "X" 값."""
    lines = src[:pos].split("\n")[-60:]
    seg = "\n".join(lines)
    vals = []
    for m in re.finditer(rf'\b{re.escape(var)}\s*(=\s*\{{|\.update\(\s*\{{)', seg):
        body = seg[m.start():seg.find("}", m.end()) + 1]
        vals += STATUS_RE.findall(body)
    return vals


def check_ship_status_writes(src):
    """위반 목록(빈 목록이면 통과). 변이 확인(02b)에서도 같은 함수를 쓴다."""
    bad = []
    writes = _ship_writes(src)
    kinds = sorted(k for k, _, _ in writes)
    if kinds != ["_db.insert", "_db.update", "_db.update", "_db.update", "_uc"]:
        bad.append(f"shipments 쓰기 목록이 바뀜: {[(k, _line(src, p)) for k, p, _ in writes]} {RECHECK}")
    for kind, pos, text in writes:
        vals = STATUS_RE.findall(text)
        ln = _line(src, pos)
        if kind == "_db.insert":
            if vals != ["DRAFT"]:
                bad.append(f"{ln}: shipments insert 상태는 DRAFT 하나여야 함 — {vals}")
        elif kind == "_uc":
            head = src[src.rfind("def _cf_set_status_if_draft", 0, pos):pos]
            if "def _cf_set_status_if_draft" not in head or "status=eq.DRAFT" not in head:
                bad.append(f"{ln}: 조건부 갱신(_uc)이 _cf_set_status_if_draft(status=eq.DRAFT) 밖에 있음")
        else:   # _db.update — 취소만 허용
            if "DRAFT" in text or "CONFIRMED" in text:
                bad.append(f"{ln}: shipments update 에 DRAFT/CONFIRMED")
            args = [a.strip() for a in text[text.index("(") + 1:-1].rsplit(",", 1)]
            fields = args[-1]
            if re.fullmatch(r"[A-Za-z_]\w*", fields):
                vals = _var_status_values(src, pos, fields)
            if any(v != "CANCELLED" for v in vals):
                bad.append(f"{ln}: shipments update 상태 값 {vals} — CANCELLED 만 허용")
    helper_spans = []
    for m in re.finditer(r"_cf_set_status_if_draft\(", src):
        if src[max(0, m.start() - 4):m.start()] == "def ":
            continue
        text = _call_text(src, m.start())
        helper_spans.append((m.start(), m.start() + len(text)))
        for v in STATUS_RE.findall(text):
            if v not in ("CONFIRMED", "CANCELLED"):
                bad.append(f"{_line(src, m.start())}: 조건부 헬퍼 상태 값 {v}")
    for m in re.finditer(r'"status"\s*:\s*"CONFIRMED"', src):
        if not any(a <= m.start() < b for a, b in helper_spans):
            bad.append(f"{_line(src, m.start())}: \"status\": \"CONFIRMED\" 가 _cf_set_status_if_draft( 인자 밖 {RECHECK}")
    return bad


def check_migrations(mig_dir=MIG_DIR):
    bad = []
    for fn in sorted(os.listdir(mig_dir)):
        if not fn.endswith(".sql"):
            continue
        sql = _src(os.path.join(mig_dir, fn))
        sql = re.sub(r"--[^\n]*", "", sql)
        for m in re.finditer(r"UPDATE\s+(?:public\.)?shipments\s+SET\s+(.*?);", sql, re.I | re.S):
            body = m.group(1)
            st = re.search(r"\bstatus\s*=\s*'([A-Z_]+)'", body, re.I)
            if not st or st.group(1).upper() == "CANCELLED":
                continue
            if not re.search(r"\bAND\s+status\s*=\s*'DRAFT'", body, re.I):
                bad.append(f"{fn}: UPDATE shipments SET status = '{st.group(1)}' 에 AND status = 'DRAFT' 없음")
    return bad


def test_b_t3_ship_status_writes_keep_cancelled_terminal():
    bad = check_ship_status_writes(_src())
    assert not bad, "\n".join(bad)


def test_b_t3_migrations_confirm_only_from_draft():
    bad = check_migrations()
    assert not bad, "\n".join(bad)
    n = sum(len(re.findall(r"UPDATE\s+shipments\s+SET\s+status\s*=\s*'CONFIRMED'", _src(os.path.join(MIG_DIR, f)), re.I))
            for f in os.listdir(MIG_DIR) if f.endswith(".sql"))
    assert n >= 2, n                     # 069·076 — 검사가 아무것도 안 보는 상태가 아님


def test_b_t3_checker_catches_injected_confirm():
    """검사기 자체 대조: 가짜 CONFIRMED 쓰기 한 줄을 넣은 사본은 걸린다(02b 변이 ①과 같은 모양)."""
    src = _src()
    anchor = src.index('_db.insert("shipments"')
    inj = ('_db.update("shipments", "shipment_id=eq.1", {"status": "CONFIRMED"})\n'
           + " " * 24)
    bad = check_ship_status_writes(src[:anchor] + inj + src[anchor:])
    assert any("CONFIRMED" in b for b in bad) and any("목록이 바뀜" in b for b in bad), bad


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
    assert md.count("4PDVN-03") >= 1 and "500" in md, md[-1500:]
    tr = [t for t in re.findall(r"<tr[^>]*>.*?</tr>", md, re.S) if "4PDVN-03" in t]
    assert len(tr) == 1, tr
    caps = [str(c.value) for c in at.caption]
    assert any("확정 후 취소" in c for c in caps), caps
    assert not INSERTED and not UPDATED and not DELETED, (INSERTED, UPDATED, DELETED)
