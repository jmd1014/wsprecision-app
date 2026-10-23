"""운영 마이그레이션 ledger ↔ 저장소 파일 대조 (읽기 전용, 기존 파일은 절대 덮어쓰지 않음).

배경 (P1-5, 2026-10-23): 033~062 마이그레이션은 Supabase MCP 로 운영에 적용됐지만 원본
파일이 커밋되지 않았다. 운영 ledger(supabase_migrations.schema_migrations) 에서 본문을
추출해 파일로 복구했고, 이 스크립트는 그 대조를 재현한다.

ledger 는 PostgREST(anon/service_role 키)로 읽을 수 없으므로 이 스크립트는 DB 에 접속하지
않는다. 대신 두 입력 파일을 쓴다.

  1. supabase/migrations/_ledger_index.json  (필수)
     ledger 의 version / name / 저장소 파일명 / 정규화 md5 / 원문 길이 스냅샷.
     갱신 SQL (Supabase SQL Editor 또는 MCP execute_sql):
       select version, name,
              md5(btrim(regexp_replace(regexp_replace(array_to_string(statements, E'\\n'),
                                                      '--[^\\n]*', '', 'g'), '\\s+', ' ', 'g'))) md5_norm,
              length(array_to_string(statements, E'\\n')) len
         from supabase_migrations.schema_migrations order by version;

  2. --statements <json>  (선택)  [{"version":..,"name":..,"sql":..}, ...]
     ledger 본문 덤프. --write 와 함께 주면 저장소에 **없는** 파일만 복구 헤더를 붙여 만든다.
     이미 있는 파일은 어떤 경우에도 건드리지 않는다 (차이는 보고만).

정규화 규칙(양쪽 동일): `--` 줄 주석 제거 → 공백 묶음을 한 칸으로 → 앞뒤 공백 제거 → md5.
그래서 복구 헤더·적용 메모 같은 주석 차이는 무시되고, SQL 본문 차이만 잡힌다.

사용:
  python scripts/export_migration_ledger.py                 # 대조만
  python scripts/export_migration_ledger.py --statements dump.json --write   # 없는 파일 생성
종료 코드: 0 = 전부 일치, 2 = 차이/누락 있음 (보고 뒤 사람이 판단).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIG_DIR = ROOT / "supabase" / "migrations"
INDEX = MIG_DIR / "_ledger_index.json"

HEADER = (
    "-- ════════════════════════════════════════════════════════════\n"
    "-- 복구: 운영 ledger(supabase_migrations.schema_migrations) 에서 추출 {today} — 원본 파일 커밋 없음 (P1-5)\n"
    "-- version: {version}  name: {name}\n"
    "-- ════════════════════════════════════════════════════════════\n"
)


def normalize(sql: str) -> str:
    """Postgres 쪽 md5 식과 같은 정규화 (ASCII 공백 기준)."""
    s = re.sub(r"--[^\n]*", "", sql)
    s = re.sub(r"[ \t\n\r\f\v]+", " ", s)
    return s.strip(" ")


def md5_norm(sql: str) -> str:
    return hashlib.md5(normalize(sql).encode("utf-8")).hexdigest()


def load_index(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data["rows"] if isinstance(data, dict) else data
    return sorted(rows, key=lambda r: r["version"])


def load_statements(path: Path | None) -> dict[str, str]:
    if not path:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "rows" in data:
        data = data["rows"]
    return {r["version"]: r["sql"] for r in data}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--index", type=Path, default=INDEX)
    ap.add_argument("--statements", type=Path, default=None, help="ledger 본문 덤프 JSON")
    ap.add_argument("--write", action="store_true", help="없는 파일을 --statements 로 생성 (기존 파일은 불변)")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):  # Windows 콘솔 cp949 깨짐 방지
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    rows = load_index(args.index)
    stmts = load_statements(args.statements)
    today = date.today().isoformat()

    ok, diff, missing, created, no_body = [], [], [], [], []
    for r in rows:
        rel = r["file"]
        path = MIG_DIR / rel
        if path.exists():
            got = md5_norm(path.read_text(encoding="utf-8"))
            (ok if got == r["md5_norm"] else diff).append((rel, r["version"], r["md5_norm"], got))
            continue
        body = stmts.get(r["version"])
        if args.write and body is not None:
            if md5_norm(body) != r["md5_norm"]:
                no_body.append((rel, r["version"], "statements md5 ≠ index md5 — 생성 안 함"))
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(HEADER.format(today=today, version=r["version"], name=r["name"]) + body.rstrip("\n") + "\n",
                            encoding="utf-8", newline="\n")
            created.append((rel, r["version"]))
        else:
            missing.append((rel, r["version"]))

    indexed = {r["file"] for r in rows}
    repo_only = sorted(p.relative_to(MIG_DIR).as_posix() for p in MIG_DIR.rglob("*.sql") if p.relative_to(MIG_DIR).as_posix() not in indexed)

    print(f"ledger index: {len(rows)}행  ({args.index.relative_to(ROOT).as_posix()})")
    print(f"  일치      : {len(ok)}")
    print(f"  차이      : {len(diff)}")
    print(f"  누락      : {len(missing)}")
    if created:
        print(f"  생성      : {len(created)}")
    if no_body:
        print(f"  생성 거부 : {len(no_body)}")
    for rel, ver, want, got in diff:
        print(f"  [DIFF]    {rel}  version={ver}  ledger={want[:12]}  file={got[:12]}")
    for rel, ver in missing:
        print(f"  [MISSING] {rel}  version={ver}")
    for rel, ver in created:
        print(f"  [CREATED] {rel}  version={ver}")
    for rel, ver, why in no_body:
        print(f"  [REFUSED] {rel}  version={ver}  {why}")
    if repo_only:
        print(f"  ledger 기록 없음(저장소에만, SQL Editor 직접 적용 시기 추정): {len(repo_only)}")
        for rel in repo_only:
            print(f"    - {rel}")
    return 0 if not diff and not missing and not no_body else 2


if __name__ == "__main__":
    sys.exit(main())
