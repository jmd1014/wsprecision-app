# Supabase DB 운영 가이드

## ⚠️ 가장 중요 — 운영 중 절대 실행 금지 파일

### `_INITIAL_SETUP_ONLY_schema.sql`
- **최초 1회 빈 프로젝트에 적용한 파일**
- `DROP TABLE ... CASCADE` + `CREATE TABLE` 패턴이라 **운영 중 실행하면 모든 데이터 삭제**
- 이름 앞에 `_INITIAL_SETUP_ONLY_`를 붙여 시각적으로 격리
- 새 환경에 1번만 적용 → 그 이후로는 절대 열지 않을 것

### 운영 중 DB 변경은 반드시 `migrations/` 폴더의 파일로

```
migrations/
├── 001_vendor_group.sql
├── 002_sales_orders.sql
├── 003_inventory_transactions.sql
├── 004_status_constraints.sql
├── 005_po_number_function.sql
├── 006_pending_qty_view.sql
├── 007_bom_processes_and_mapping.sql
├── 008_cost_views.sql
├── 009_cost_view_refactor.sql
├── 010_bom_process_price.sql
├── 011_sales_stats_recent_avg.sql
├── 012_data_quality_exclusion.sql
├── 013_active_master_views.sql
├── 014_material_price_status.sql
├── 015_recent_price_basis.sql
├── ...
├── 077_so_close_rounds_all.sql
├── adhoc/                      ← 번호 없이 적용된 1회성 SQL (ledger 복구)
└── _ledger_index.json          ← 운영 ledger 스냅샷 (대조용, scripts/export_migration_ledger.py)
```

모든 migration은 다음 원칙을 따름:
1. **멱등 (idempotent)** — 두 번 실행해도 안전 (`IF NOT EXISTS`, `OR REPLACE`)
2. **비파괴 (non-destructive)** — DROP TABLE 사용 금지
3. **순서 보장** — 파일명 앞 번호로 적용 순서 명확
4. **기존 데이터 보존** — ALTER TABLE ADD COLUMN 우선

---

## DB 변경 절차

상세 절차는 [/docs/db-migration-guide.md](../docs/db-migration-guide.md) 참고.

### 요약

1. 백업 (Supabase Dashboard → Database → Backups)
2. 새 migration 파일을 `supabase/migrations/NNN_xxx.sql`로 작성
3. Supabase SQL Editor에서 해당 파일 내용 실행
4. 결과 검증 (Table Editor, 쿼리)
5. `docs/db-migration-guide.md`의 적용 로그에 기록

---

## 현재 마이그레이션 적용 현황

| # | 파일 | 적용 일자 | 비고 |
|---|---|---|---|
| 001 | vendor_group.sql | 2026-05-07 | vendors에 vendor_group 컬럼 추가 |
| 002 | sales_orders.sql | 2026-05-08 | sales_orders / sales_order_items / customer_part_mapping |
| 003 | inventory_transactions.sql | 2026-05-13 | 재고 거래 이력 + material_stock view |
| 004 | status_constraints.sql | 2026-05-13 | CHECK 제약 |
| 005 | po_number_function.sql | 2026-05-13 | 동시성 안전 채번 함수 |
| 006 | pending_qty_view.sql | 2026-05-13 | pending_qty view 계산 |
| 007 | bom_processes_and_mapping.sql | (미적용) | BOM 공정행 + 매입/생산 매핑 컬럼 |
| 008 | cost_views.sql | (미적용) | material_price_v / product_cost_full_v 등 |
| 009 | cost_view_refactor.sql | (미적용) | BOM=수량 / 가격=원가·매입 분리. 호환 alias 추가 |
| 010 | bom_process_price.sql | (미적용) | 공정행 unit_price (LOT 단가) 우선 활용 |
| 011 | sales_stats_recent_avg.sql | (미적용) | avg_unit_price=12M 필터, 3M/all/last 컬럼 추가 |
| 012 | data_quality_exclusion.sql | 2026-05-20 | sales_data_exclusion 테이블 + 미진 2023-02 이전 제외 |
| 013 | active_master_views.sql | 2026-05-21 | 활성 기준 정비 view + 매칭 view 6종 |
| 014 | material_price_status.sql | 2026-05-21 | 자재 가격 출처 view (매입/legacy/없음) |
| 015 | recent_price_basis.sql | 2026-05-21 | 최근 거래가 기준 + 사급 BOM_FULL 인정 |
| 016 | po_source_tracking.sql | 2026-06-11 | purchase_orders.remark (수주 출처 추적) |
| 017 | material_receiving.sql | 2026-07-03 | Phase A 소재 입고 — poi.material_id + po_item_receipt_v + material_stock 기초재고 반영 |
| 018 | production_report.sql | 2026-07-03 | Phase B 생산 보고 — material_id 선택화 + 제품 재고 view (product_stock_v) |
| 019 | lot_traceability.sql | 2026-07-03 | Phase C — production_log.lot_number + lot_trace_v + product_trace_v |
| 020 | mes_upload.sql | 2026-07-06 | MES 실적 업로드 (공정 실적 raw) |
| 021 | material_price_po.sql | 2026-07-15 | 자재 최근가에 앱 발주 단가 반영 (ledger name: material_price_po) |
| 022 | phase_e_foundation.sql | 2026-07-23 | Phase E 기반 — 공정 관리 (ledger name: phase_e_foundation) |
| 023 | phase_e2_process.sql | 2026-07-23 | Phase E-2 — 공정 처리 (ledger name: phase_e2_process) |
| 024 | wo_events.sql | 2026-07-23 | 공정 이벤트 이력 (ledger name: wo_events) |
| 025 | wo_return_qty.sql | 2026-07-24 | 검사 반품 수량 (ledger name: wo_return_qty) |
| 026 | product_lot_stock.sql | 2026-07-28 | 제품 LOT별 완성 재고 view (ledger name: product_lot_stock) |
| 027 | delivery_schedule.sql | 2026-07-29 | 분납 스케줄 — 수주 라인별 회차 (ledger name: delivery_schedule) |
| 028 | material_master_cleanup.sql | 2026-08-03 | 자재 마스터 선행 정리 |
| 029 | material_supplier_normalize.sql | 2026-08-03 | main_supplier 정리 |
| 030 | product_lot_stock_include_adjustment.sql | 2026-08-03 | LOT 재고에 실사 조정(ADJUSTMENT) 반영 |
| 031 | shipments.sql | 2026-08-07 | 출고 전표 |
| 032 | product_name_group_cleanup.sql | 2026-08-10 | 제품 품명(item_name) 추가 + product_group 삭제 |
| 033 | enable_rls_all_tables.sql | 2026-08-12 | RLS 전체 활성화 ※ledger 복구 |
| 034 | views_security_invoker.sql | 2026-08-12 | 뷰 security_invoker 적용 ※ledger 복구 |
| 035 | function_search_path.sql | 2026-08-12 | 함수 search_path 고정 ※ledger 복구 |
| 036 | product_routing.sql | 2026-08-12 | 제품 라우팅(공정 순서) ※ledger 복구 |
| 037 | wo_batches.sql | 2026-08-18 | 작업 배치 ※ledger 복구 |
| 038 | presched_and_data_quality.sql | 2026-08-19 | 스케줄이전 수량 + 정합 점검 뷰 data_quality_v ※ledger 복구 |
| 039 | poi_product_id.sql | 2026-08-19 | 발주 라인 제품 연결 ※ledger 복구 |
| 040 | poi_material.sql | 2026-08-19 | 발주 라인 자재 연결 ※ledger 복구 |
| 041 | po_short_close.sql | 2026-08-20 | 발주 미입고 종결 ※ledger 복구 |
| 042 | po_status_allow_closed.sql | 2026-08-20 | 발주 상태 CLOSED 허용 ※ledger 복구 |
| 043 | po_line_level_close.sql | 2026-08-20 | 발주 라인 단위 종결 ※ledger 복구 |
| 044 | dq_route_cost_link.sql | 2026-08-20 | 정합 점검 ROUTE_COST_ORPHAN ※ledger 복구 |
| 045 | routing_no_material_stage.sql | 2026-08-20 | 소재 단계 외주 개념 폐지 ※ledger 복구 |
| 046 | dq_proc_price_vendor.sql | 2026-08-21 | 정합 점검 PROC_NO_PRICE/VENDOR (자기 참조 — 047 로 수정) ※ledger 복구 |
| 047 | fix_dq_view_recursion.sql | 2026-08-21 | 046 자기 참조 수정 — 뷰 전체 재정의 ※ledger 복구 |
| 048 | dq_proc_checks_scope.sql | 2026-08-21 | PROC 검사 공정행 한정 ※ledger 복구 |
| adhoc | adhoc/20260824_flange_ledger_price_backup.sql | 2026-08-24 | 플랜지 소재단가 보정 전 백업 테이블 (번호 없는 적용) ※ledger 복구 |
| 049 | batch_step_status.sql | 2026-08-26 | 배치 공정별 WAIT/RUN ※ledger 복구 |
| 050 | product_sale_price.sql | 2026-08-31 | 제품 표준 판매 단가 + 판매가 우선순위 ※ledger 복구 |
| 051 | sale_price_no_avg.sql | 2026-08-31 | 판매가 12M 평균 fallback 제거 ※ledger 복구 |
| 052 | product_size.sql | 2026-09-03 | 제품 사이즈(완성품 치수) + 발주 품명 백필 ※ledger 복구 |
| 053 | shipment_revision.sql | 2026-09-04 | 출고 정정·취소 인프라 (충당·이력·월 마감) ※ledger 복구 |
| 054 | dq_ship_alloc_scope.sql | 2026-09-04 | SHIP_ALLOC_MISMATCH 2026-09-05 이후 한정 ※ledger 복구 |
| 055 | production_standards.sql | 2026-09-07 | 설비 마스터·공정 표준·능력 매트릭스 ※ledger 복구 |
| 056 | production_sheet_sync.sql | 2026-09-07 | 생산일정 시트 동기화 컬럼 ※ledger 복구 |
| 057 | production_schedule.sql | 2026-09-07 | 설비 스케줄 보드 1단계 ※ledger 복구 |
| 058 | op_std_active_log.sql | 2026-09-07 | 공정 표준 사용 여부 + 변경 이력 ※ledger 복구 |
| 059 | so_line_replacement.sql | 2026-09-10 | 수주 대체/별건 결정 이력 ※ledger 복구 |
| 060 | price_kind_customer_mat.sql | 2026-09-10 | 특수 단가 CUSTOMER_MAT ※ledger 복구 |
| 061 | lot_stock_material_lot_fallback.sql | 2026-09-11 | LOT 잔량 뷰 소재 LOT 폴백 ※ledger 복구 |
| 062 | poi_adhoc_once.sql | 2026-09-11 | 발주 라인 일회성 표시 ※ledger 복구 |
| 063 | vendor_short_name.sql | 2026-09-15 | 거래처 약칭 |
| 064 | po_mail_sent_info.sql | 2026-09-16 | 발주 발송 기록 |
| 065 | login_log_and_backup_rls.sql | 2026-09-17 | 로그인 기록 + 백업 테이블 RLS |
| 066 | drop_backup_tables.sql | 2026-09-17 | 공개 스키마 백업 테이블 20개 정리 |
| 067 | app_errors.sql | 2026-10-13 | 앱 오류 기록 테이블 |
| 068 | w_lot_rpc.sql | 2026-10-13 | W LOT 채번 RPC + 입고 유니크 |
| 069 | confirm_shipment_rpc.sql | 2026-10-13 | 출고 확정 트랜잭션 RPC |
| 070 | weekly_plan.sql | 2026-10-14 | 생산 계획 1차 — 주간 계획·근무 체계 |
| 071 | purchase_item_map.sql | 2026-10-15 | 매입 품명 매핑표 + 장부 출처 열 |
| 072 | item_map_vendor_default.sql | 2026-10-15 | 매핑표 업체 기본 유형(와일드카드) |
| 073 | dash_routine.sql | 2026-10-21 | 업무 루틴 dash_ 테이블 4개 + RPC |
| 074 | dash_generate_cards_assignee.sql | 2026-10-21 | dash_generate_cards 담당자 빈 템플릿 제외 |
| 075 | so_status_closed.sql | 2026-10-22 | 수주 상태 CLOSED + 라인 중단 수량 보존 |
| 076 | so_close_rpc.sql | 2026-10-22 | 수주 종결·되돌리기 RPC 원자화 |
| 077 | so_close_rounds_all.sql | 2026-10-23 | 종결 때 라인 전 회차 closed_rounds 보존 |

적용 일자는 운영 ledger(`supabase_migrations.schema_migrations`)의 version(UTC) 기준. 033~062 와 adhoc 1건은 원본 파일이 커밋되지 않아 2026-10-23 ledger 본문을 그대로 추출해 복구했다(파일 머리 "복구:" 주석). 001~012·016 은 ledger 에 기록이 없다(SQL Editor 직접 적용 시기).

### ledger 대조

`supabase/migrations/_ledger_index.json`(ledger 스냅샷: version·name·정규화 md5)과 저장소 파일을 `python scripts/export_migration_ledger.py` 로 대조한다(주석 제거·공백 정규화 뒤 md5, DB 접속 없음, 기존 파일 불변). 새 마이그레이션을 적용하면 스냅샷 행을 추가한다(SQL 은 스크립트 docstring).

2026-10-23 대조 결과: 65행 중 57 일치, 8 차이(파일은 그대로 두고 기록만). 모두 SQL 의미 차이는 아니다.
- 013·014·015: 뷰 본문이 괄호 앞뒤 공백만 다름(`SUM( CASE` vs `SUM(CASE` 류). 013(6개)·014(2개)·019(2개)의 `COMMENT ON VIEW` 는 파일에만 있고 운영에는 적용되지 않음.
- 026·027: COMMENT 문자열이 파일에서는 두 리터럴 이어붙임(`'…' '…'`), 운영은 한 리터럴 — 내용 동일.
- 031: 운영에만 `COMMENT ON TABLE shipments / shipment_items` 2문 있음(파일 누락).
- 071: `purchase_ledger.map_id` COMMENT 가 파일에서 적용 뒤 더 길어짐(문장 추가). 운영 코멘트는 짧은 쪽.
