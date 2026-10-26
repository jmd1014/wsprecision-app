# -*- coding: utf-8 -*-
"""야간 백업(JSONL) → 로컬 PostgreSQL `wsapp_restore` 복원 리허설 (P1-1, 2026-10-26).

계획: _P1종료묶음_계획서_및_지시문_20261023.md §2-2. 운영 DB 는 읽기(비교 GET)만, 쓰기는 로컬 wsapp_restore 만.

사용:
  python scripts/restore_local.py                       최신 백업 폴더로 리허설
  python scripts/restore_local.py --backup "G:\\내 드라이브\\제품관리DB\\backup\\20261026"
  python scripts/restore_local.py --no-prod-compare      운영 비교 조회 생략
되돌리기: 로컬에서 `DROP DATABASE wsapp_restore;` (운영과 무관)

안전장치(3중):
  1) DSN 은 로컬 secrets 의 [restore_pg].dsn 에서만 읽는다. 호스트가 localhost/127.0.0.1/::1 이 아니면 즉시 중단.
  2) 쓰는 DB 이름은 상수 TARGET_DB = "wsapp_restore" 로 고정. DROP/CREATE 는 관리용 postgres DB 접속에서
     그 이름에만 한다. DSN 의 DB 이름이 postgres/wsapp_restore 가 아니면 중단.
  3) 운영([supabase].url)은 비교용 GET 만 쓴다 — 이 파일에는 운영으로 가는 POST/PATCH/PUT/DELETE 가 없다
     (tests/test_restore_local_static.py 가 확인).

순서: ① DB 재생성 ② 역할 service_role·anon·authenticated(NOLOGIN) ③ _INITIAL_SETUP_ONLY_schema.sql →
migrations 001~077(+adhoc) psql -1 -v ON_ERROR_STOP=1 (파일별 소요·실패 기록) ④ 데이터 적재(FK 부모 먼저,
session_replication_role=replica, 1000행 배치) ⑤ 시퀀스 보정 ⑥ 검증.
"""
import argparse
import datetime as dt
import io
import json
import os
import subprocess
import sys
import time
import tomllib
import urllib.parse as up

import requests

ROOT = r"C:\wsapp"
SECRETS = os.path.join(ROOT, ".streamlit", "secrets.toml")
BACKUP_ROOT = r"G:\내 드라이브\제품관리DB\backup"
PSQL = r"C:\Program Files\PostgreSQL\17\bin\psql.exe"
TARGET_DB = "wsapp_restore"
ADMIN_DB = "postgres"
LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")
ROLES = ("service_role", "anon", "authenticated")
SCHEMA_FILE = os.path.join(ROOT, "supabase", "_INITIAL_SETUP_ONLY_schema.sql")
MIG_DIR = os.path.join(ROOT, "supabase", "migrations")
# 번호 없는 adhoc 은 운영 ledger 적용 순서대로 이 번호 파일 뒤에(_ledger_index.json 기준)
ADHOC_AFTER = {"adhoc/20260824_flange_ledger_price_backup.sql": "048_"}
# 운영에서 마이그레이션 파일 밖(SQL 편집기·MCP 1회성)으로 만들어졌다가 066 에서 지워진 백업 표 — 저장소에 만드는 SQL 이
# 없어 033(RLS 켜기)이 실패한다. 033 직전에 빈 스텁을 만들고 기록한다(066 이 IF EXISTS 로 지움). 2026-10-26 리허설에서 확인.
PRE_STUBS = {"033_": ("zz_bak_golive_sales_orders", "zz_bak_golive_sales_order_items", "zz_bak_golive_purchase_orders",
                      "zz_bak_golive_purchase_order_items", "zz_bak_golive_inventory_transactions",
                      "zz_bak_golive_production_log_manual", "materials_baseline_backup_0805", "flange_split_backup_0805",
                      "bom_backup_0805", "materials_name_backup_0805", "products_prefix_backup_0806",
                      "soi_prefix_backup_0806", "backfill_backup_0806")}
KEY_TABLES = {   # 운영 비교 — (id 열, 합계 열)
    "sales_orders": ("so_id", "total_amount"),
    "sales_order_items": ("soi_id", "qty"),
    "inventory_transactions": ("txn_id", "qty"),
}
CHECK_VIEWS = ("sales_order_stats", "product_stock_v", "product_lot_stock_v")
CHECK_FUNCS = ("confirm_shipment", "so_close_lines", "so_reopen_lines", "dash_generate_cards")


class SafetyError(SystemExit):
    pass


# ─── 안전장치 ───
def load_dsn():
    sec = tomllib.load(open(SECRETS, "rb"))
    if "restore_pg" not in sec or not sec["restore_pg"].get("dsn"):
        raise SafetyError("secrets 에 [restore_pg] dsn 이 없다 — 사용자가 로컬 secrets.toml 에 직접 추가")
    u = up.urlparse(sec["restore_pg"]["dsn"])
    if u.scheme not in ("postgresql", "postgres"):
        raise SafetyError(f"DSN 형식 아님: {u.scheme}")
    host = (u.hostname or "").lower()
    if host not in LOCAL_HOSTS:
        raise SafetyError(f"DSN 호스트가 로컬이 아님({host}) — 중단")
    db = (u.path or "/").lstrip("/") or ADMIN_DB
    if db not in (ADMIN_DB, TARGET_DB):
        raise SafetyError(f"DSN DB 이름이 {ADMIN_DB}/{TARGET_DB} 가 아님({db}) — 중단")
    # 비밀번호에 @ # % / : 같은 문자가 있으면 URL 에서 깨지므로 [restore_pg] password 키를 따로 둘 수 있다(있으면 우선)
    pw = sec["restore_pg"].get("password")
    if pw is None:
        pw = up.unquote(u.password or "")
    return {"host": host, "port": u.port or 5432, "user": up.unquote(u.username or "postgres"),
            "password": str(pw)}, sec.get("supabase", {})


def connect(cfg, dbname):
    import psycopg2
    if dbname not in (ADMIN_DB, TARGET_DB):
        raise SafetyError(f"접속 DB 이름 위반: {dbname}")
    if cfg["host"] not in LOCAL_HOSTS:
        raise SafetyError("로컬 아님")
    try:
        return psycopg2.connect(host=cfg["host"], port=cfg["port"], user=cfg["user"], password=cfg["password"],
                                dbname=dbname)
    except UnicodeDecodeError:
        # Windows 한국어 서버의 오류문(cp949)을 psycopg2 가 못 읽는다 — psql 로 다시 시도해 메시지를 보여 준다
        env = dict(psql_env(cfg), PGDATABASE=dbname)
        r = subprocess.run([PSQL, "-X", "-c", "select 1"], env=env, capture_output=True)
        raise SafetyError("로컬 PostgreSQL 접속 실패: " + r.stderr.decode("cp949", "replace").strip())


def psql_env(cfg):
    env = dict(os.environ)
    env.update({"PGHOST": cfg["host"], "PGPORT": str(cfg["port"]), "PGUSER": cfg["user"],
                "PGPASSWORD": cfg["password"], "PGDATABASE": TARGET_DB, "PGCLIENTENCODING": "UTF8",
                # Supabase 는 UTC — 로컬(Asia/Seoul) 세션이면 마이그레이션의 'YYYY-MM-DD'::timestamptz 상수가
                # 9시간 다른 순간으로 저장된다(054 data_quality_v 실측, 2026-10-26 리허설)
                "PGTZ": "UTC"})
    return env


# ─── ① ② DB·역할 ───
def recreate_db(cfg):
    c = connect(cfg, ADMIN_DB)
    c.autocommit = True
    cur = c.cursor()
    cur.execute("select pg_terminate_backend(pid) from pg_stat_activity where datname = %s and pid <> pg_backend_pid()",
                (TARGET_DB,))
    cur.execute(f'drop database if exists "{TARGET_DB}"')
    cur.execute(f"create database \"{TARGET_DB}\" encoding 'UTF8' template template0")
    cur.execute(f"alter database \"{TARGET_DB}\" set timezone to 'UTC'")   # Supabase 와 같게
    for r in ROLES:
        cur.execute("select 1 from pg_roles where rolname = %s", (r,))
        if not cur.fetchone():
            cur.execute(f'create role "{r}" nologin')
    cur.execute("select version()")
    ver = cur.fetchone()[0]
    c.close()
    return ver


# ─── ③ 스키마 ───
def schema_files():
    nums = sorted(f for f in os.listdir(MIG_DIR) if f.endswith(".sql") and f[:3].isdigit())
    out = [SCHEMA_FILE]
    for f in nums:
        out.append(os.path.join(MIG_DIR, f))
        for adh, after in ADHOC_AFTER.items():
            if f.startswith(after):
                out.append(os.path.join(MIG_DIR, *adh.split("/")))
    return out


def apply_schema(cfg, log):
    res = []
    env = psql_env(cfg)
    for path in schema_files():
        base = os.path.basename(path)
        for pre, names in PRE_STUBS.items():
            if base.startswith(pre):
                sql = ";".join(f'create table if not exists public."{n}" ()' for n in names)
                st = subprocess.run([PSQL, "-X", "-q", "-v", "ON_ERROR_STOP=1", "-c", sql], env=env,
                                    capture_output=True, text=True, encoding="utf-8", errors="replace")
                res.append({"file": f"(스텁 {len(names)}개 — {base} 전)", "ok": st.returncode == 0, "sec": 0,
                            "error": None if st.returncode == 0 else st.stderr[-300:], "stubs": list(names)})
                log(f"  STUB {len(names)}개 (마이그레이션 밖에서 만들어진 백업 표) → {base} 전")
        t0 = time.perf_counter()
        p = subprocess.run([PSQL, "-X", "-q", "-1", "-v", "ON_ERROR_STOP=1", "-f", path],
                           env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
        sec = time.perf_counter() - t0
        rel = os.path.relpath(path, os.path.join(ROOT, "supabase")).replace("\\", "/")
        err = (p.stderr or "").strip()
        ok = p.returncode == 0
        res.append({"file": rel, "ok": ok, "sec": round(sec, 2),
                    "error": None if ok else err[-600:],
                    "notices": len([l for l in err.splitlines() if "NOTICE" in l or "WARNING" in l]) if ok else None})
        log(f"  {'OK  ' if ok else 'FAIL'} {rel} {sec:.2f}s" + ("" if ok else f" — {err.splitlines()[-1] if err else ''}"))
        if sum(1 for r in res if not r["ok"]) >= 5:
            log("  스키마 적용 실패 5개 — 중단(멈춤 조건)")
            break
    return res


def enable_rls_all(cfg):
    c = connect(cfg, TARGET_DB)
    cur = c.cursor()
    cur.execute("""select c.relname from pg_class c join pg_namespace n on n.oid=c.relnamespace
                   where n.nspname='public' and c.relkind in ('r','p') and not c.relrowsecurity order by 1""")
    names = [r[0] for r in cur.fetchall()]
    for t in names:
        cur.execute(f'alter table public."{t}" enable row level security')
    c.commit()
    c.close()
    return names


# ─── ④ 데이터 ───
def table_meta(cur):
    cur.execute("""select c.relname, c.relkind from pg_class c join pg_namespace n on n.oid=c.relnamespace
                   where n.nspname='public' and c.relkind in ('r','v','m','p')""")
    kinds = dict(cur.fetchall())
    cur.execute("""select table_name, column_name, data_type, is_generated, identity_generation
                   from information_schema.columns where table_schema='public' order by table_name, ordinal_position""")
    cols = {}
    for t, c, typ, gen, ident in cur.fetchall():
        cols.setdefault(t, []).append({"name": c, "type": typ, "generated": gen == "ALWAYS", "identity": ident})
    cur.execute("""select tc.relname child, tp.relname parent from pg_constraint k
                   join pg_class tc on tc.oid=k.conrelid join pg_class tp on tp.oid=k.confrelid
                   join pg_namespace n on n.oid=tc.relnamespace
                   where k.contype='f' and n.nspname='public' and tc.relname <> tp.relname""")
    fks = cur.fetchall()
    return kinds, cols, fks


def topo_order(tables, fks):
    deps = {t: set() for t in tables}
    for child, parent in fks:
        if child in deps and parent in deps:
            deps[child].add(parent)
    out, seen = [], set()

    def visit(t, stack=()):
        if t in seen or t in stack:
            return
        for p in sorted(deps[t]):
            visit(p, stack + (t,))
        seen.add(t)
        out.append(t)
    for t in sorted(tables):
        visit(t)
    return out


def load_data(cfg, bdir, manifest, log):
    from psycopg2.extras import Json, execute_values
    c = connect(cfg, TARGET_DB)
    cur = c.cursor()
    kinds, cols, fks = table_meta(cur)
    mtabs = list(manifest["tables"])
    missing = [t for t in mtabs if t not in kinds]
    views = [t for t in mtabs if kinds.get(t) in ("v", "m")]
    base = [t for t in mtabs if kinds.get(t) in ("r", "p")]
    order = topo_order(base, fks)
    cur.execute("set session_replication_role = replica")
    res = []
    for t in order:
        t0 = time.perf_counter()
        tc = {x["name"]: x for x in cols.get(t, [])}
        path = os.path.join(bdir, f"{t}.jsonl")
        rows = [json.loads(l) for l in io.open(path, encoding="utf-8") if l.strip()] if os.path.exists(path) else []
        keys = []
        for r in rows:
            for k in r:
                if k not in keys:
                    keys.append(k)
        use = [k for k in keys if k in tc and not tc[k]["generated"]]
        extra = [k for k in keys if k not in tc]
        gen_skipped = [k for k in keys if k in tc and tc[k]["generated"]]
        ident = any(tc[k]["identity"] == "ALWAYS" for k in use)
        err = None
        seeded = 0
        try:
            # 마이그레이션 시드가 먼저 들어간 표(dash_parts·shift_profiles 등)는 비우고 백업 값으로 채운다
            cur.execute(f'select count(*) from public."{t}"')
            seeded = cur.fetchone()[0]
            if seeded:
                cur.execute(f'delete from public."{t}"')
            if rows and use:
                def conv(k, v):
                    if v is None:
                        return None
                    typ = tc[k]["type"]
                    if typ in ("json", "jsonb"):
                        return Json(v)
                    return v
                vals = [tuple(conv(k, r.get(k)) for k in use) for r in rows]
                collist = ",".join(f'"{k}"' for k in use)
                ov = " overriding system value" if ident else ""
                for i in range(0, len(vals), 1000):
                    execute_values(cur, f'insert into public."{t}" ({collist}){ov} values %s', vals[i:i + 1000],
                                   page_size=1000)
            c.commit()
        except Exception as e:
            c.rollback()
            cur.execute("set session_replication_role = replica")
            err = str(e).strip().splitlines()[0][:300]
        cur.execute(f'select count(*) from public."{t}"')
        n = cur.fetchone()[0]
        want = manifest["tables"][t]["rows"]
        res.append({"table": t, "manifest": want, "restored": n, "ok": n == want and err is None,
                    "seed_rows_replaced": seeded if err is None else None,
                    "sec": round(time.perf_counter() - t0, 2), "error": err,
                    "extra_cols": extra, "generated_skipped": gen_skipped})
        log(f"  {'OK  ' if n == want and not err else 'DIFF'} {t}: {n}/{want}" + (f" — {err}" if err else "")
            + (f" (시드 {seeded}행 교체)" if seeded and not err else "")
            + (f" (백업에만 있는 열 {extra})" if extra else ""))
    cur.execute("set session_replication_role = origin")
    c.commit()
    c.close()
    return res, order, missing, views


# ─── ⑤ 시퀀스 ───
def fix_sequences(cfg):
    c = connect(cfg, TARGET_DB)
    cur = c.cursor()
    cur.execute("""select c.relname, a.attname, pg_get_serial_sequence(format('public.%I', c.relname), a.attname)
                   from pg_attribute a join pg_class c on c.oid=a.attrelid join pg_namespace n on n.oid=c.relnamespace
                   where n.nspname='public' and c.relkind='r' and a.attnum>0 and not a.attisdropped
                   and pg_get_serial_sequence(format('public.%I', c.relname), a.attname) is not null""")
    out = []
    for t, col, seq in cur.fetchall():
        cur.execute(f'select max("{col}") from public."{t}"')
        mx = cur.fetchone()[0]
        if mx is not None:
            cur.execute("select setval(%s, %s, true)", (seq, mx))
            out.append((t, col, int(mx)))
    c.commit()
    c.close()
    return out


# ─── ⑥ 검증 ───
def prod_get(sb, table, select, extra, order):
    """운영 읽기 전용 GET (비교용). 쓰기 메서드는 이 파일에 없다."""
    base = sb["url"].rstrip("/") + "/rest/v1/" + table
    key = sb["service_role_key"]
    h = {"apikey": key, "Authorization": "Bearer " + key}
    rows, off = [], 0
    while True:
        r = requests.get(base, headers=h, params={"select": select, "order": order, "limit": 1000, "offset": off,
                                                   **extra}, timeout=60)
        r.raise_for_status()
        b = r.json()
        rows += b
        if len(b) < 1000:
            return rows
        off += 1000


def verify(cfg, sb, prod_compare, log):
    c = connect(cfg, TARGET_DB)
    cur = c.cursor()
    key = []
    for t, (idc, sumc) in KEY_TABLES.items():
        cur.execute(f'select count(*), coalesce(max("{idc}"),0), coalesce(sum("{sumc}"),0) from public."{t}"')
        n, mx, s = cur.fetchone()
        rec = {"table": t, "restored_count": n, "restored_max_id": int(mx), "restored_sum": float(s)}
        if prod_compare:
            pr = prod_get(sb, t, f"{idc},{sumc}", {idc: f"lte.{int(mx)}"}, f"{idc}.asc")
            rec.update({"prod_count_le_max": len(pr), "prod_max_id_le": max((int(r[idc]) for r in pr), default=0),
                        "prod_sum_le_max": float(sum(float(r.get(sumc) or 0) for r in pr))})
            rec["match"] = (rec["prod_count_le_max"] == n and rec["prod_max_id_le"] == int(mx)
                            and abs(rec["prod_sum_le_max"] - float(s)) < 0.5)
            allp = prod_get(sb, t, idc, {}, f"{idc}.asc")
            rec["prod_count_now"] = len(allp)
        key.append(rec)
        log(f"  {t}: 복원 {n}행 max {int(mx)} 합 {float(s):,.2f}"
            + (f" / 운영(id≤max) {rec['prod_count_le_max']}행 합 {rec['prod_sum_le_max']:,.2f} → "
               f"{'일치' if rec['match'] else '불일치'} (운영 현재 {rec['prod_count_now']}행)" if prod_compare else ""))
    views = []
    for v in CHECK_VIEWS:
        try:
            cur.execute(f'select count(*) from public."{v}"')
            views.append((v, True, cur.fetchone()[0]))
        except Exception as e:
            c.rollback()
            views.append((v, False, str(e).splitlines()[0][:200]))
    cur.execute("select proname from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public'")
    have = {r[0] for r in cur.fetchall()}
    funcs = [(f, f in have) for f in CHECK_FUNCS]
    c.close()
    return key, views, funcs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backup", help="백업 폴더(기본: 최신 YYYYMMDD)")
    ap.add_argument("--no-prod-compare", action="store_true")
    ap.add_argument("--out", default=None, help="결과 JSON 경로(기본: 백업 폴더 밖 scratch 아님 — 저장소 밖 G: 리허설 폴더)")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cfg, sb = load_dsn()                     # 안전장치 1·2 (실패하면 여기서 끝)
    bdir = args.backup or os.path.join(BACKUP_ROOT, sorted(d for d in os.listdir(BACKUP_ROOT)
                                                           if d.isdigit() and len(d) == 8)[-1])
    manifest = json.load(io.open(os.path.join(bdir, "_manifest.json"), encoding="utf-8"))
    lines = []

    def log(s):
        print(s)
        lines.append(s)
    log(f"대상: postgresql://{cfg['user']}@{cfg['host']}:{cfg['port']}/{TARGET_DB} (비밀번호 표시 안 함)")
    log(f"백업: {bdir} (started {manifest.get('started_at')}, {len(manifest['tables'])}테이블, {manifest.get('total_rows')}행)")
    T = {}
    t0 = time.perf_counter(); ver = recreate_db(cfg); T["db"] = time.perf_counter() - t0
    log(f"① DB 재생성·② 역할 — {ver.split(',')[0]}")
    t0 = time.perf_counter(); sch = apply_schema(cfg, log); T["schema"] = time.perf_counter() - t0
    # Supabase 기본값 재현: 대시보드에서 만든 표는 RLS 가 처음부터 켜져 있다(SQL 파일에 없음). 운영은 public 의 모든 표 RLS ON.
    rls = enable_rls_all(cfg)
    log(f"  RLS 켬 {len(rls)}표 (Supabase 기본값 재현 — 파일에 ENABLE 이 없던 표)")
    fails = [s for s in sch if not s["ok"]]
    log(f"③ 스키마 {len(sch)}파일, 실패 {len(fails)} — {T['schema']:.1f}s")
    if len(fails) >= 5:
        res = {"stopped": "schema_failures", "schema": sch}
    else:
        t0 = time.perf_counter(); data, order, missing, views = load_data(cfg, bdir, manifest, log)
        T["data"] = time.perf_counter() - t0
        log(f"④ 데이터 {len(data)}테이블 — {T['data']:.1f}s (스키마에 없음 {missing}, 뷰라 건너뜀 {views})")
        t0 = time.perf_counter(); seqs = fix_sequences(cfg); T["seq"] = time.perf_counter() - t0
        log(f"⑤ 시퀀스 {len(seqs)}개 보정")
        t0 = time.perf_counter(); key, vchk, fchk = verify(cfg, sb, not args.no_prod_compare, log)
        T["verify"] = time.perf_counter() - t0
        log(f"⑥ 뷰 {vchk} / 함수 {fchk} — {T['verify']:.1f}s")
        res = {"schema": sch, "rls_enabled_after_schema": rls, "data": data, "order": order, "missing_tables": missing, "skipped_views": views,
               "sequences": seqs, "key_tables": key, "views": vchk, "functions": fchk}
    res.update({"postgres": ver, "backup": bdir, "manifest_started": manifest.get("started_at"),
                "seconds": {k: round(v, 1) for k, v in T.items()}, "at": dt.datetime.now().isoformat()})
    out = args.out or os.path.join(os.path.dirname(BACKUP_ROOT), f"_복원리허설_결과_{dt.date.today():%Y%m%d}.json")
    io.open(out, "w", encoding="utf-8").write(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    log(f"결과 → {out}")


if __name__ == "__main__":
    main()
