# -*- coding: utf-8 -*-
"""업무 루틴 전용 목 DB (계획서 §6, 2026-10-21).

- dash_ 테이블 4개 + work_calendar 를 리스트로 보유, 실제 행을 바꾼다.
- 필터 AND 파싱(id=eq. · status=eq. · completed_at=eq. · work_date=gte./lte. · shift=eq. · template_id=in. …).
- update_count 는 0/1/-1 또는 예외를 시뮬레이션할 수 있다(`update_mode`).
- rpc 목은 (template_id, work_date, shift) 충돌 판정으로 DB 함수와 같은 결과를 낸다(`rpc_raise` 로 예외).
- 쓰기(insert/update/update_count/delete/rpc)는 dash_ 테이블·dash_generate_cards 외에는 즉시 실패.
  읽기는 등록되지 않은 테이블이면 [] (홈·사이드바 등 다른 화면이 읽는 표 — 쓰기와 달리 조용히 빈 결과).
- 계정은 app_settings(auth_users·auth_secret) fetch_one 으로 로그인 경로를 그대로 탄다.
"""
import json
from urllib.parse import unquote

from utils import auth as _auth

SECRET = "d1" * 32
USERS = {
    "김민수": {"name": "김민수", "role": "admin", "pw": _auth.hash_pw("pw-admin")},
    "김준오": {"name": "김준오", "role": "worker", "pw": _auth.hash_pw("pw-day")},
    "현장": {"name": "현장", "role": "worker", "pw": _auth.hash_pw("pw-field")},
    "김만호": {"name": "김만호", "role": "worker", "pw": _auth.hash_pw("pw-night")},
}
DASH_TABLES = ("dash_parts", "dash_routine_templates", "dash_cards", "dash_card_activity")


def seed_templates():
    day = [("prod_day_%02d" % i, "day", i, t, "기준 %d" % i, ["김준오"], "always") for i, t in enumerate(
        ["야간 인수 확인", "현장 회의록 게시", "당일 출고 수량·검사 확인", "소재·공정 대기 재고 확인",
         "전일 불량 내역 등록", "출퇴근·연장근무 승인 확인", "연장·야간 편성 라인 게시"], 1)]
    night = [("prod_night_01", "night", 1, "편성 라인 가동 확인", "기준", [], "always"),
             ("prod_night_02", "night", 2, "자동화 라인 알람 기록", "기준", [], "always"),
             ("prod_night_03", "night", 3, "퇴근 전 특이사항 남기기", "기준", [], "always"),
             ("prod_night_04", "night", 4, "휴무 전 문단속·인수인계", "토요일·공휴일 전날만", [], "pre_holiday")]
    rows = []
    for i, (code, shift, seq, title, crit, ass, rule) in enumerate(day + night, 1):
        rows.append({"id": i, "code": code, "part_id": 1, "shift": shift, "seq": seq, "title": title,
                     "done_criteria": crit, "assignee_user_ids": list(ass), "active_rule": rule,
                     "active": True, "created_at": "2026-10-21T00:00:00+00:00",
                     "updated_at": "2026-10-21T00:00:00+00:00"})
    return rows


class DashMock:
    def __init__(self, tables_missing=False):
        self.tables_missing = tables_missing
        self.tables = {
            "dash_parts": [{"id": 1, "code": "production", "name": "생산", "sort_order": 1},
                           {"id": 2, "code": "quality", "name": "품질", "sort_order": 2}],
            "dash_routine_templates": seed_templates(),
            "dash_cards": [],
            "dash_card_activity": [],
            "work_calendar": [],
        }
        self.writes = []            # (op, table, payload)
        self.rpc_calls = []
        self.fetch_calls = []
        self.update_mode = None     # None | 0 | -1 | "raise"
        self.update_false = False   # db.update 가 False 를 돌려주는 상황(PostgREST 오류) 시뮬레이션
        self.update_fail_ids = set()  # 이 id 의 갱신만 실패(-1)
        self.fetch_raise_for = None   # 이 테이블 조회는 예외
        self.insert_raise_for = None
        self.rpc_raise = None
        self.log_errors = []
        self._seq = {t: len(rows) for t, rows in self.tables.items()}

    # ── 필터 ──
    @staticmethod
    def _parse(filter_query):
        conds = []
        for part in (filter_query or "").split("&"):
            if not part or part.startswith(("order=", "select=", "limit=", "offset=")):
                continue
            col, _, rest = part.partition("=")
            op, _, val = rest.partition(".")
            conds.append((col, op, unquote(val)))
        return conds

    @staticmethod
    def _match(row, conds):
        for col, op, val in conds:
            cur = row.get(col)
            s = "" if cur is None else str(cur)
            if op == "eq":
                if val in ("true", "false"):
                    if bool(cur) != (val == "true"):
                        return False
                elif s != val:
                    return False
            elif op == "neq":
                if s == val:
                    return False
            elif op == "in":
                vals = [v.strip().strip('"') for v in val.strip("()").split(",")]
                if s not in vals:
                    return False
            elif op == "gte":
                if s < val:
                    return False
            elif op == "lte":
                if s > val:
                    return False
            elif op == "gt":
                if not s > val:
                    return False
            elif op == "lt":
                if not s < val:
                    return False
            elif op == "is":
                if (val == "null") != (cur is None):
                    return False
            else:
                raise AssertionError(f"dash_mock: 지원하지 않는 연산자 {op}")
        return True

    def _rows(self, table, filter_query):
        if table in DASH_TABLES and self.tables_missing:
            raise RuntimeError(f"{table} 404: relation does not exist (Old DB)")
        rows = self.tables.get(table)
        if rows is None:
            return None
        conds = self._parse(filter_query)
        out = [r for r in rows if self._match(r, conds)]
        if "order=seq.asc" in (filter_query or ""):
            out.sort(key=lambda r: (int(r.get("seq") or 0), int(r.get("id") or 0)))
        return out

    # ── 읽기 ──
    def fetch(self, table, select="*", filter_query="", limit=1000, cache=None):
        self.fetch_calls.append((table, filter_query or ""))
        if self.fetch_raise_for == table:
            raise RuntimeError(f"{table} 조회 실패 (시뮬레이션)")
        rows = self._rows(table, filter_query)
        if rows is None:
            return []
        return [dict(r) for r in rows[:limit]]

    def fetch_one(self, table, filter_query="", select="*"):
        if table == "app_settings":
            if "auth_users" in (filter_query or ""):
                return {"value": json.dumps(USERS, ensure_ascii=False)}
            if "auth_secret" in (filter_query or ""):
                return {"value": SECRET}
            return None
        rows = self.fetch(table, select, filter_query, 1)
        return rows[0] if rows else None

    # ── 쓰기 ──
    def _assert_dash(self, op, table):
        if table not in DASH_TABLES:
            raise AssertionError(f"dash_mock: dash_ 외 테이블 쓰기 금지 ({op} {table})")
        if self.tables_missing:
            raise RuntimeError(f"{table} 404: relation does not exist (Old DB)")

    def insert(self, table, records):
        self._assert_dash("insert", table)
        if self.insert_raise_for == table:
            raise RuntimeError(f"insert {table} 실패 (시뮬레이션)")
        for r in records:
            self._seq[table] = self._seq.get(table, 0) + 1
            row = {"id": self._seq[table], "created_at": "2026-10-21T01:00:00+00:00", **r}
            if table == "dash_routine_templates":
                for k, v in (("active", True), ("seq", 0), ("assignee_user_ids", [])):
                    row.setdefault(k, v)
            self.tables[table].append(row)
            self.writes.append(("insert", table, dict(row)))
        return len(records)

    def update(self, table, filter_query, fields):
        if self.update_false:
            self._assert_dash("update", table)
            return False
        n = self.update_count(table, filter_query, fields)
        return n >= 0

    def update_count(self, table, filter_query, fields, select="*"):
        self._assert_dash("update", table)
        if not filter_query:
            raise ValueError("update_count: filter_query 필수")
        if self.update_mode == "raise":
            raise RuntimeError("update 실패 (시뮬레이션)")
        if self.update_mode in (0, -1):
            return self.update_mode
        if any(f"id=eq.{i}&" in filter_query + "&" for i in self.update_fail_ids):
            return -1
        rows = self._rows(table, filter_query)
        for r in rows:
            r.update(fields)
            self.writes.append(("update", table, {"filter": filter_query, **fields}))
        return len(rows)

    def delete(self, table, filter_query):
        self._assert_dash("delete", table)
        raise AssertionError("dash_mock: delete 는 1단계 범위 밖")

    def rpc(self, name, params=None, timeout=None):
        self.rpc_calls.append((name, dict(params or {})))
        if name != "dash_generate_cards":
            raise AssertionError(f"dash_mock: 미등록 RPC {name}")
        if self.tables_missing:
            import db as _db
            raise _db.RpcUnavailable("dash_generate_cards: 없음 (Old DB)")
        if self.rpc_raise:
            raise self.rpc_raise
        p = params or {}
        ids = [int(i) for i in (p.get("p_template_ids") or [])]
        wd, sh = str(p.get("p_work_date")), p.get("p_shift")
        inserted = 0
        for t in self.tables["dash_routine_templates"]:
            if t["id"] not in ids or not t.get("active", True) or t.get("shift") != sh:
                continue
            if not [u for u in (t.get("assignee_user_ids") or []) if str(u or "").strip()]:
                continue          # 074: 담당자 빈 템플릿은 DB 에서도 제외
            if any(c.get("template_id") == t["id"] and str(c.get("work_date")) == wd and c.get("shift") == sh
                   for c in self.tables["dash_cards"]):
                continue
            self._seq["dash_cards"] += 1
            row = {"id": self._seq["dash_cards"], "type": "routine", "part_id": t["part_id"],
                   "template_id": t["id"], "work_date": wd, "shift": sh, "seq": t["seq"],
                   "title": t["title"], "done_criteria": t.get("done_criteria"), "status": "todo",
                   "assignee_user_ids": list(t.get("assignee_user_ids") or []),
                   "completed_by": None, "completed_at": None,
                   "created_at": "2026-10-21T01:00:00+00:00"}
            self.tables["dash_cards"].append(row)
            self.writes.append(("rpc_insert", "dash_cards", dict(row)))
            inserted += 1
        return {"inserted": inserted, "skipped": len(ids) - inserted, "requested": len(ids),
                "work_date": wd, "shift": sh}

    # ── 기타 ──
    def log_error(self, kind, detail, **kw):
        self.log_errors.append((kind, str(detail)))
        return True

    def install(self, monkeypatch, db):
        monkeypatch.setattr(db, "fetch", self.fetch)
        monkeypatch.setattr(db, "fetch_one", self.fetch_one)
        monkeypatch.setattr(db, "insert", self.insert)
        monkeypatch.setattr(db, "update", self.update)
        monkeypatch.setattr(db, "update_count", self.update_count)
        monkeypatch.setattr(db, "delete", self.delete)
        monkeypatch.setattr(db, "rpc", self.rpc)
        monkeypatch.setattr(db, "log_error", self.log_error)
        monkeypatch.setattr(db, "health_check", lambda: {"status": "OK", "counts": {}})
        monkeypatch.setattr(db, "debug_check", lambda: {"status": "mock"})
        monkeypatch.setattr(db, "count_rows", lambda t, f="": 0)
        monkeypatch.setattr(db, "clear_cache", lambda: None)
        return self

    # ── 조회 보조 ──
    def cards(self, **kw):
        return [c for c in self.tables["dash_cards"] if all(str(c.get(k)) == str(v) for k, v in kw.items())]

    def activity(self):
        return list(self.tables["dash_card_activity"])
