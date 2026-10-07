"""운영 DB 야간 백업 — Supabase PostgREST 로 public 테이블 전체를 JSON Lines 로 받아 저장.

실행:  C:\\Python311\\python.exe C:\\wsapp\\scripts\\backup_tables.py
등록:  schtasks /Create /TN "wsapp-backup" /SC DAILY /ST 02:30 /TR "..." /F  (매일 02:30)
저장:  G:\\내 드라이브\\제품관리DB\\backup\\YYYYMMDD\\<table>.jsonl + _manifest.json
보존:  30일. 더 오래된 날짜 폴더는 삭제한다.

- 읽기 전용(GET)만 한다. 운영 DB 에 쓰지 않는다.
- 테이블 목록: PostgREST OpenAPI(definitions) 에서 뽑고, 알려진 뷰와 `_v` 로 끝나는 이름은 뺀다.
  OpenAPI 를 못 받으면 KNOWN_TABLES(2026-10-07 스냅샷) 로 폴백.
- 페이징: 기본키 정렬 + limit/offset 1000행. 기본키를 모르는 새 테이블은 첫 컬럼 정렬.
- 어느 테이블이든 실패하면 끝까지 돌고 종료 코드 1 (manifest 에 오류 기록).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
import time
import tomllib

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRETS = os.path.join(ROOT, ".streamlit", "secrets.toml")
BACKUP_ROOT = r"G:\내 드라이브\제품관리DB\backup"
KEEP_DAYS = 30
PAGE = 1000
TIMEOUT = 60

# 2026-10-07 information_schema 스냅샷 — 테이블명: 기본키
KNOWN_TABLES = {
    "app_settings": "key", "app_users": "user_id", "batch_links": "link_id", "bom": "bom_id",
    "customer_part_mapping": "mapping_id", "drawings": "drawing_id",
    "inventory_transactions": "txn_id", "login_log": "log_id", "machines": "machine_id",
    "master_change_log": "log_id", "materials": "material_id", "product_op_machine": "pom_id",
    "product_op_std": "op_id", "product_op_std_log": "log_id", "product_routing": "routing_id",
    "production_log": "log_id", "production_plan": "plan_id", "production_schedule": "sched_id",
    "products": "product_id", "purchase_ledger": "ledger_id", "purchase_order_items": "poi_id",
    "purchase_orders": "po_id", "sales_data_exclusion": "id", "sales_ledger": "ledger_id",
    "sales_month_close": "ym", "sales_order_items": "soi_id", "sales_orders": "so_id",
    "shipment_allocations": "alloc_id", "shipment_items": "si_id", "shipment_revisions": "rev_id",
    "shipments": "shipment_id", "so_delivery_schedule": "sched_id",
    "so_line_replacements": "repl_id", "sync_log": "sync_id", "vendors": "vendor_id",
    "wo_batches": "batch_id", "wo_events": "event_id", "wo_tracking": "wo_id",
}
# 뷰 — 백업 대상 아님 (원본 테이블에서 재계산됨)
KNOWN_VIEWS = {
    "active_bom_completion_v", "active_products", "archived_products", "bom_cleanup_todo_v",
    "bom_missing_active_products_v", "data_quality_v", "lot_trace_v",
    "material_mapping_candidates", "material_price_coverage_v", "material_price_v",
    "material_stats", "material_stock", "material_stock_by_lot", "po_item_receipt_v",
    "product_actual_cost_v", "product_bom_cost_v", "product_cost_full_v", "product_full",
    "product_lot_stock_v", "product_material_price_status_v", "product_stats",
    "product_stock_v", "product_trace_v", "purchase_material_match_progress",
    "sales_order_items_v", "sales_order_stats", "so_schedule_summary_v",
    "unresolved_purchase_materials", "vendor_stats",
}


def log(msg: str) -> None:
    print(f"[{dt.datetime.now():%H:%M:%S}] {msg}", flush=True)


def load_conn() -> tuple[str, dict]:
    with open(SECRETS, "rb") as f:
        s = tomllib.load(f)["supabase"]
    key = s["service_role_key"]
    return s["url"].rstrip("/") + "/rest/v1", {"apikey": key, "Authorization": f"Bearer {key}"}


def list_tables(base: str, headers: dict) -> tuple[dict[str, str | None], str]:
    """{table: pk_or_None}, 출처 설명"""
    try:
        r = requests.get(base + "/", headers=headers, timeout=TIMEOUT)
        r.raise_for_status()
        defs = r.json().get("definitions", {})
        names = [n for n in defs if n not in KNOWN_VIEWS and not n.endswith("_v")]
        if not names:
            raise RuntimeError("definitions 비어 있음")
        return {n: KNOWN_TABLES.get(n) for n in sorted(names)}, "openapi"
    except Exception as e:  # noqa: BLE001
        log(f"OpenAPI 목록 실패 → KNOWN_TABLES 폴백: {e}")
        return dict(KNOWN_TABLES), "fallback"


def dump_table(base: str, headers: dict, table: str, pk: str | None, path: str) -> dict:
    t0 = time.time()
    n = 0
    offset = 0
    order = pk
    with open(path, "w", encoding="utf-8") as f:
        while True:
            params = {"select": "*", "limit": PAGE, "offset": offset}
            if order:
                params["order"] = f"{order}.asc"
            r = requests.get(f"{base}/{table}", headers=headers, params=params, timeout=TIMEOUT)
            if r.status_code >= 400 and order and offset == 0:
                # 기본키 추정이 틀린 새 테이블 → 정렬 없이 재시도
                order = None
                continue
            r.raise_for_status()
            rows = r.json()
            if not rows:
                break
            if order is None and n == 0 and rows and isinstance(rows[0], dict):
                order = next(iter(rows[0].keys()))  # 첫 컬럼으로라도 정렬해 페이지 안정화
                # 정렬 없이 받은 첫 페이지는 버리고 정렬 기준으로 다시 시작
                continue
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
            n += len(rows)
            if len(rows) < PAGE:
                break
            offset += PAGE
    return {"rows": n, "seconds": round(time.time() - t0, 2), "order": order}


def prune_old(root: str, keep_days: int) -> list[str]:
    removed = []
    cutoff = dt.date.today() - dt.timedelta(days=keep_days)
    if not os.path.isdir(root):
        return removed
    for name in os.listdir(root):
        p = os.path.join(root, name)
        if not (os.path.isdir(p) and len(name) == 8 and name.isdigit()):
            continue
        try:
            d = dt.datetime.strptime(name, "%Y%m%d").date()
        except ValueError:
            continue
        if d < cutoff:
            shutil.rmtree(p, ignore_errors=True)
            removed.append(name)
    return removed


def main() -> int:
    started = dt.datetime.now()
    base, headers = load_conn()
    tables, source = list_tables(base, headers)
    out_dir = os.path.join(BACKUP_ROOT, started.strftime("%Y%m%d"))
    os.makedirs(out_dir, exist_ok=True)
    log(f"백업 시작 → {out_dir} (테이블 {len(tables)}개, 목록 출처 {source})")

    manifest = {"started_at": started.isoformat(timespec="seconds"), "table_source": source,
                "tables": {}, "errors": {}}
    for table, pk in tables.items():
        path = os.path.join(out_dir, f"{table}.jsonl")
        try:
            info = dump_table(base, headers, table, pk, path)
            manifest["tables"][table] = info
            log(f"  {table:32s} {info['rows']:>7,} rows  {info['seconds']:>6.1f}s")
        except Exception as e:  # noqa: BLE001
            manifest["errors"][table] = str(e)
            log(f"  {table:32s} 실패: {e}")

    manifest["removed_old"] = prune_old(BACKUP_ROOT, KEEP_DAYS)
    manifest["finished_at"] = dt.datetime.now().isoformat(timespec="seconds")
    manifest["total_rows"] = sum(v["rows"] for v in manifest["tables"].values())
    manifest["ok"] = not manifest["errors"]
    with open(os.path.join(out_dir, "_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    log(f"완료: {len(manifest['tables'])}개 테이블 {manifest['total_rows']:,}행, "
        f"오류 {len(manifest['errors'])}건, 오래된 폴더 삭제 {len(manifest['removed_old'])}개")
    return 0 if manifest["ok"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        log(f"백업 중단: {e}")
        sys.exit(2)
