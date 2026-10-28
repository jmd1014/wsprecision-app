# DATA_INTEGRITY — 정합성 불변식 v3 · 2026-10-27

v2.1 에 Codex 재리뷰(`_P2a_Codex재리뷰_v2.1_결과_20261027.md`, HIGH 1·MEDIUM 6·LOW 1)를 반영한 판. **§8 SQL 4묶음은 이 문서의 유일한 실행본**이며(v1·v2 참조 없음) §4 는 그 SQL 을 2026-10-27 저녁 운영 DB 에 읽기 전용으로 실행한 결과(지시번호 중복·취소 시각 백필 L3-D 적용 **뒤**, 예외 A·B·E·F·I·J 적용 상태)다.

## 0. v2.1 → v3 (Codex 재리뷰 반영)
| 지적 | 처리 |
|---|---|
| N1 (HIGH) 예외 J 가 거래처 제한 없이 전 전표 면제 | J = **거래처 (주)엠제이티** + 확정일(KST) 25일 이후 + 납품일 다음 달 1~5일. I17b 는 그 전표에 연결된 `ISSUE/ref_table=shipment_items/ref_id=si_id` 행만 제외. 적용 결과 2건(SH-20261001-01, SH-20261102-01) — 둘 다 월말 확정·다음 달 초 납품일, 규칙과 일치 |
| N2 I21 교체→복원→재교체 오탐 | 복원 이력은 같은 옛 라인에 **뒤 활성 REPLACE 가 없을 때만** 검사 |
| N3 I18a 지시번호 단독 합산 | `(wo_number, product_id)` 양쪽 집계 + I18c(대응 지시 없는 PROD_OUTPUT) 추가 |
| N4 I10d `updated_at` 은 전환 시각이 아님 | **정보(후보 진단)** 로 강등. 정확한 전환 시각은 P3-1 에서 `closed_at` 류 컬럼으로 |
| N5 I13c(활성 라인 closed_qty 잔존) 누락 | I13 에 복원 |
| N6 예외 I 가 ID 전체 면제 | **고정값 조건**: sched 151 은 qty 1,732·Σ충당 3,748 일 때만, si 378 은 qty 1,400·Σ충당 1,300 일 때만 제외. 값이 바뀌면 신규 위반 |
| N7 §8 실행 불가 | 4묶음 전문 수록, 모든 예외를 SQL 조건에 반영 |
| N8 문서 간 비동기 | §4 를 정정 뒤·예외 적용 뒤 결과로 전면 교체, §6 결정 확정판 |
| H3 I7d 등급 | 제품 원장 material_id 혼입은 뷰에서 빠지므로 **P0** |
| H4 I8c | 레거시 비배치 경로 범위 미확정 → **정보** |
| H7 I14a 수동 생산보고 NULL LOT | `ref_table='production_log'` 제외(현재 0행) |
| M2 자재 현재고 정의 | §2 에 "material_stock = materials.stock_qty(기준) + 원장 합" 명시 |
| M4 I12b 표본 순서 | 월 순 정렬, cnt = 행 수 |
| 최종 확인(v2.1→v3, HIGH 0/M 2/L 1) N1 잔여 | J 를 **라인 단위**로(혼합 전표는 위반), 17b 는 `txn_date = ship_date` 인 ISSUE 만 제외 |
| N6 잔여 | 예외 I 에 delivered_qty 1,732 도 고정 |
| N8 잔여 | §4 를 원시 검출 / 승인 예외 / 최종 위반으로 구분 |

## 1. 목적과 원칙
- "맞는 상태"를 SQL 로 정의한다. **불변식(0건이 정상)** 과 **[정보](건수·추세)** 를 구분한다. 각 블록은 번호·설명·건수·샘플 키 5개를 돌려준다.
- 원장(`inventory_transactions`)이 재고의 진실, 뷰는 파생. 수주 잔량의 진실은 라인 `received_qty`·`presched_qty`·`closed_qty` 와 회차 `delivered_qty`; 출고 반영 흔적은 `shipment_allocations` + ISSUE 원장(라인 `si_id` 단위); 머리글은 `shipments.status`·`rev_no`.
- 등급: **P0** = 존재 불가(3·4·9·11, 2d·7d·7e) → 즉시 보고, 정정은 L3-D. **P1** = 검토 필요. **P2** = 알려진 예외·실사 대기. [정보] = 등급 없음.
- 허용 오차: 수량 등식 1e-9, 뷰 음수·추세 0.5. 날짜는 KST.
- 예외는 §5 의 ID·고정값 조건만. 날짜·문자열 조건으로 넓히지 않는다.
- 번호 1~17 고정(로드맵·AGENTS 가 3·4·9·11 참조), 18~21 은 v2 추가.

## 2. 범위와 규약
| 흐름 | 표 | 파생 뷰 |
|---|---|---|
| 수주 | sales_orders · sales_order_items · so_delivery_schedule · so_line_replacements | sales_order_items_v · sales_order_stats |
| 발주·입고 | purchase_orders · purchase_order_items · purchase_ledger · purchase_item_map | po_item_receipt_v |
| 생산 | wo_tracking · wo_batches · wo_events · batch_links · product_routing | — |
| 재고·LOT | inventory_transactions · materials · products · bom | material_stock(= materials.stock_qty 기준재고 + 원장 합) · material_stock_by_lot · product_stock_v · product_lot_stock_v |
| 출고 | shipments · shipment_items · shipment_allocations · shipment_revisions · sales_month_close | — |

- 원장 부호: RECEIPT +, PROD_OUTPUT +, ADJUSTMENT ±, ISSUE −(취소 역분개 +), PROD_INPUT −(투입 취소 복원 +). DEFECT 미사용.
- ISSUE ref_table: shipment_items(651) / sales_order_items(8월 이관 10). RECEIPT ref 없음 110(초기 재고). 수동 생산보고 경로는 `ref_table='production_log'`(현재 0행).
- RPC 069 confirm_shipment(2026-10-13 적용): `soi_id NULL` 라인 건너뜀, `product_id NULL` 라인 ISSUE 없음, 회차 부족분은 `unallocated` 로 알리고 확정. 라인별 `ΣISSUE = −si.qty` 가 RPC 불변식.
- 상태값: sales_orders {DRAFT, CONFIRMED, IN_PROD, PARTIAL, DELIVERED, CANCELLED, CLOSED} · sales_order_items {PENDING, IN_PROD, PARTIAL, DELIVERED, CANCELLED, CLOSED, REPLACED} · purchase_orders {DRAFT, SENT, PARTIAL, RECEIVED, CANCELLED, CLOSED} · shipments {DRAFT, CONFIRMED, CANCELLED} · wo_tracking 유도값 {IN_PROD, OUTSOURCE, REWORK, INSPECT, CLOSED} + 레거시 {DONE, READY, RECEIVED, CANCELLED} · wo_batches {OPEN, DONE, SCRAP, RETURN, MERGED}.
- 라우팅 저장 = delete+insert → `wo_batches.routing_id` 고아는 정상. 기본 플로우 스텝 MAT_IN·PROD·OUT·INSPECT·DONE.
- 거래처 마감 규칙(2026-10-27 확인): (주)엠제이티는 25일 이후 납품을 차월 거래명세서로 → 납품일(ship_date)이 미래인 확정 전표가 정상 존재(§5-J).

## 3. 불변식 표
| # | 이름 | 정의 (0건이 정상) | 등급 | 담당 화면 | 예외/발생원 |
|---|---|---|---|---|---|
| 1 | 수주 라인 대사 | (a) 회차 있는 라인 Σdelivered = received − presched · (b) 활성 라인 pending = greatest(qty − received, 0) | P1 | 수주 목록 · 납품 스케줄 | A. 발생원: RPC unallocated 확정(§4 soi 157) → P3-1 설계 결정 |
| 2 | 확정 전표 충당 | (a) Σ충당 > 라인 qty · (b) 회차 Σ충당 > 회차 qty · (c) Σ충당(확정) > 회차 delivered · (d) 충당 행 무효 | P1 (d P0) | 출고 등록·전표 · 납품 스케줄 | I(고정값). [정보] 2a_under 미충당, 2c_under(B) |
| 3 | 비확정 전표 흔적 | DRAFT·CANCELLED 전표 **라인별** ISSUE 순합 ≠ 0 또는 충당 잔존 | **P0** | 출고 전표 · confirm_shipment | 없음 |
| 4 | 전표 ISSUE 대사 | (a) 10-13 이후 확정, 제품·수주 연결 라인 ΣISSUE(si_id) = −qty · (b) 미연결 라인 ISSUE·제품 불일치 · (레거시) 10-13 이전 전표·제품 단위 | **P0** | 출고 전표 · confirm_shipment | 10-13 이전 라인별 불일치 6건은 정보 |
| 5 | 발주 입고 | (a)[정보] 초과 입고 · (b) DRAFT·CANCELLED 발주 입고 · (c) 순입고 음수 | P1 | 입고 처리 | C |
| 6 | 자재 LOT | (a) (자재,LOT) 잔량 < 0 · (b) PROD_INPUT LOT·자재 없음 · (c)[정보] 자재 현재고 < 0 | P1 | 투입 등록 · 자재 재고 | 실사 전 음수 정상 |
| 7 | 완성 재고 | (a)[정보] product_stock_v < 0 · (b) 제품 LOT 잔량 < 0 · (c) PROD_OUTPUT·전표 ISSUE 제품 없음 · (d) 제품 원장 material_id 혼입 · (e) 제품 LOT 뷰 중복 | P1 (d·e **P0**) | 완성 재고 · 완성 재고 조정 | D(실사 전) |
| 8 | 배치 정합 | (a) CLOSED 지시(wo_id)에 OPEN 배치 · (b) OPEN 배치 step_code 가 라우팅·기본 플로우에 없음 · (c)[정보] 활성 지시 OPEN 배치 0 · (d) 배치 소유 불일치 · (e)[P2] routing_id 고아 | P1 | 공정 처리·현황판 | H |
| 9 | 고아 참조 | 충당→전표 라인, 회차→수주 라인, BOM→제품, 원장→자재/제품, 전표 라인→전표, 배치→지시(wo_id), ISSUE ref→전표 라인, 전표 라인 soi→수주 라인, 지시→제품, (k) RECEIPT ref→발주 라인, (l) 전표 라인·회차 so_id = 수주 라인 부모 | **P0** | (구조) | 발생원: 투입 취소가 batch_links FK 로 배치 삭제 실패 |
| 10 | 상태 전이 | (a) CONFIRMED confirmed_at 없음 · (b) CANCELLED cancelled_at 없음 · (c) 수주 DELIVERED 인데 활성 미납 · (d)[정보] 비활성 수주 updated_at 뒤 확정 출고 · (d2) 비활성 라인 참조 DRAFT 전표 · (e~h) 라인·발주·DRAFT 모순 · (i) 허용 밖 상태값 · (j) 배치 상태값 | P1 | 각 화면 | E·F |
| 11 | 채번 유일 | ship_no·po_number·so_number·batch_no 중복, (d1) wo_number 중복 — 제품 다름, (d2) wo_number 중복 — 같은 제품, (f) `^W[0-9]+$` RECEIPT 중복 | **P0** | 채번 RPC 068 · 각 채번 | 없음 |
| 12 | 매입 연결 | [정보] mapping_status 분포, 미연결 월별 | 정보 | 매입 등록 › 확인 대기 | — |
| 13 | 종결·대체 라인 | CLOSED·CANCELLED(신루틴) closed_qty = greatest(qty − received, 0) · 비활성 pending = 0 · REPLACED replaced_by_soi 있음 · 활성 라인 closed_qty = 0 | P1 | 수주 목록 · so_close_lines | 없음 |
| 14 | 생산 LOT 사슬 | (a) PROD_OUTPUT LOT 없음(created_at ≥ 10-27, production_log 제외) · (b) PROD_INPUT LOT 기원(같은 자재 RECEIPT 또는 ADJUSTMENT+) · (c) 지시 w_lot 기원 | P1 | 투입 등록 · 공정 처리 | G |
| 15 | 휴면 참조 | 활성 제품 BOM 소재행 · 미입고 발주 라인 · 미종결 지시가 휴면 자재 참조 | P1 | 자재·BOM 편집 | 없음 |
| 16 | BOM 구조 | (a) 활성 제품 소재행 2개 이상(**정책: 1개, 변경은 교체**) · (b) qty_per_pc ≤ 0 / coalesce(shared_factor,1) < 1 · (c) material_id 없음 | P1 | BOM 편집 · 부족 자재 | 없음 |
| 17 | 시간 경계 | (a) 마감 월에 마감 뒤 확정·취소·정정 · (b) 원장 txn_date > KST 오늘 · (c) 확정 전표 ship_date > KST 오늘 | P1 | 출고 등록 · 월 마감 | J(엠제이티 마감 규칙) |
| 18 | 지시 누계 | (a) (지시번호,제품) output_qty 합 = PROD_OUTPUT 합 · (b) 누적 순서 · (c) 대응 지시 없는 PROD_OUTPUT | P1 | 공정 처리 | 없음 |
| 19 | 배치 계보 | (a) 배치 qty = 들어온 링크(없으면 지시 input) − 나간 SPLIT; MERGED 는 나간 MERGE 합 · (b) 지시별 비MERGED 배치 합 = input_qty | P1 | 공정 처리(분기·합류) | `_bat_take` 링크 insert try/except |
| 20 | 정정 이력 | (a) 머리글 rev_no = 이력 max · (b) 마지막 EDIT qty_after = 라인 qty · (c) 09-05 이후 취소 전표 CANCEL 이력 또는 '작성중 취소' | P1 | 출고 전표 정정·취소 | 정정 중단 탐지 |
| 21 | 대체 왕복 | 활성 REPLACE ↔ 옛 라인 REPLACED·replaced_by_soi · 복원 이력(뒤 재교체 없음)인데 REPLACED · REPLACED 라인에 활성 이력 없음 | P1 | 수주 목록(대체) | 없음 |

## 4. 점검 결과 (2026-10-27 저녁, L3-D 정정 뒤·예외 적용 뒤, §8 SQL 그대로)
### 4.1 P0
3 · 4a · 4b · 4 레거시 · 2d · 7d · 7e · 9a~l · 11a~f: **전부 0건.**

### 4.2 P1
| # | 건수 | 내용 · 처리 |
|---|---|---|
| 1a | **1 — soi 157**(202605120010-MJT, 4PDVN-02) | recv 10,424 vs 회차 10,404: 10/26 SH-20261026-01 라인 719(2,016)가 회차 여유 1,996 만 충당(unallocated 20). **si 378 과 같은 유형이 재발** → 단발성 예외 아님. P3-1 설계 결정 대상(미충당분 presched 가산 또는 초과 회차 자동 생성). 그때까지 월 점검에 유지 |
| 2c_over | 원시 1(sched 151: Σ충당 3,748 > delivered 1,732) · 승인 예외 1(I 고정값) · **최종 0** | §8 은 고정값(qty·delivered·충당)으로 제외 |
| 1b·2a_over·2b·2c_over·2d·3·4·5b·5c·6a·6b·7b·7c·7d·7e·8a·8b·8d·9·10a~c·10d2·10e~j·11·13·14·15·16·17a~c·18·19·20·21 | 0 | |

### 4.3 [정보]·P2
| # | 결과 |
|---|---|
| 2a_under | 5 (si 148·176·214·215 전환기, **si 719** = 1a 와 같은 건) |
| 2c_under(B 적용) | 4 (sched 480·487·507·666 — delivered 는 찼는데 충당 0 또는 절반: 회차 재저장 `carry_delivered`·이관 라인 회차 재생성 흔적) |
| 4 레거시 라인 불일치 | 6 (si 35·37·330·331·337·340, 전표·제품 단위 0) |
| 5a 초과 입고 | 10 |
| 6c | 0 |
| 7a 완성 재고 음수 | 71 (11/2 실사 대상) |
| 8c | 0 |
| 8e | 0 |
| 10d | 0 |
| 10i 레거시 wo 상태 | DONE 1 |
| 12a | 미연결 2,071 (MANUAL 2,474 · null 1,744 · AUTO_DIMS 1,393 · MAP 923) |
| 12b | 6개월 539 (04=8 · 05=50 · 06=81 · 07=74 · 08=163 · 09=156 · 10=7) |
| J 적용 전표 | 2 (SH-20261001-01, SH-20261102-01 — 전 라인 엠제이티) · J_mixed 0 |

요약: **P0 0건. P1 최종 = soi 157/si 719 1건(미충당 유형 재발 → P3-1). 원시 검출 → 승인 예외 → 최종 위반을 구분해 기록한다.**

## 5. 예외 목록 (ID·고정값)
- **A. 이관 수주 라인**: soi 145, 149, 152, 158, 162, 163 — I1a 제외.
- **B. 충당 도입(2026-09-05 KST) 이전**: 2a_under 는 `confirmed_at ≥ 2026-09-05`, 2c_under 는 `created_at ≥ 2026-09-05` 회차만. over 계열은 예외 없음.
- **C. 초과 입고**: 정보.
- **D. 완성 재고 음수**: 11/2 실사 조정 전 P2.
- **E. cancelled_at 백필 2건**: SH-20260814-01, SH-20260817-02 — 2026-10-27 백필 완료(이제 조건 불필요, 기록용).
- **F. 076 이전 대체 취소 수주**: so 202604160011, 202606290006 — 10d 제외.
- **G. PROD_OUTPUT LOT NULL 레거시**: `created_at < 2026-10-27` 72행.
- **H. 기본 플로우 배치**: routing_id NULL 허용.
- **I. 단발성 예외(고정값)**: sched 151 — `qty=1732 and delivered=1732 and Σ충당=3748` 일 때만 2b·2c_over 제외; si 378 — `qty=1400 and Σ충당=1300` 일 때만 2a_under 제외. 값이 하나라도 바뀌면 신규 위반.
- **J. 거래처 마감 규칙(라인 단위)**: 거래처 '(주)엠제이티' **라인**이고 전표 `confirmed_at`(KST) 일자 ≥ 25, `ship_date` 가 다음 달 1~5일 — 17b 는 그 라인의 ISSUE 중 `txn_date = ship_date` 인 행만 제외, 17c 는 **모든 라인**이 이 조건인 전표만 제외(다른 거래처 라인이 섞이면 위반으로 봄, J_mixed 로 건수 표시).

## 6. 사용자 결정 (2026-10-27 확정)
1·2·6 지시번호 중복·백필 → L3-D 적용 완료. 3 SH-20261102-01 → 마감 규칙(J), 미래 납품일 금지 규칙 없음. 4 이관 6건 → A. 5 sched 151·si 378 → I(고정값). 7 BOM 소재행 1개 → 16a P1.
**추가 발견(결정 필요 없음, 기록)**: si 719/soi 157 로 미충당 유형 재발 → P3-1 범위에 "미충당 처리 규칙" 포함.

## 7. 월 점검 절차
1. 매월 1영업일, 기획 세션이 §8 4묶음을 Supabase MCP(읽기 전용)로 실행.
2. `_정합성점검_결과_YYYYMMDD.md` 에 §4 형식(번호/건수/샘플/분류/원인/방침) 기록, 전월 대비 증감. P3 항목 배포 다음 달에는 해당 불변식 먼저.
3. P0 > 0 → 즉시 보고 + 대기열 맨 앞. P1 은 분기 L3-D 묶음 후보, [정보]·P2 는 추세.
4. §5 예외는 ID·고정값 추가만, 사용자 승인·사유 기록.
5. P4-2 에서 자동화(결과 → app_errors 또는 슬랙).

## 8. SQL 전문 (실행본, 읽기 전용)
### 묶음 1 — 수주·출고 (1~4, 20, 21)
```sql
select 'I1a' inv, '회차 있는 라인: Σdelivered ≠ received−presched (예외 A 제외)' sub, count(*) cnt, string_agg(k, ',') filter (where rn<=5) samples from (select i.soi_id::text k, row_number() over (order by i.soi_id) rn from sales_order_items i join (select soi_id, sum(coalesce(delivered_qty,0)) d from so_delivery_schedule group by soi_id) t on t.soi_id=i.soi_id where abs(t.d-(coalesce(i.received_qty,0)-coalesce(i.presched_qty,0)))>1e-9 and i.soi_id not in (145,149,152,158,162,163)) x
union all select 'I1b', '활성 라인 pending ≠ greatest(qty−received,0)', count(*), string_agg(k, ',') filter (where rn<=5) from (select soi_id::text k, row_number() over (order by soi_id) rn from sales_order_items where coalesce(status,'') not in ('CLOSED','CANCELLED','REPLACED') and abs(coalesce(pending_qty,0)-greatest(coalesce(qty,0)-coalesce(received_qty,0),0))>1e-9) x
union all select 'I2a_over', '확정 라인 Σ충당 > qty', count(*), string_agg(k, ',') filter (where rn<=5) from (select si.si_id::text k, row_number() over (order by si.si_id) rn from shipment_items si join shipments s on s.shipment_id=si.shipment_id left join (select si_id, sum(qty) q from shipment_allocations group by si_id) a on a.si_id=si.si_id where s.status='CONFIRMED' and coalesce(a.q,0)>si.qty+1e-9) x
union all select 'I2b', '회차 Σ충당 > 회차 qty (예외 I 고정값)', count(*), string_agg(k, ',') filter (where rn<=5) from (select d.sched_id::text k, row_number() over (order by d.sched_id) rn from so_delivery_schedule d join (select sched_id, sum(qty) q from shipment_allocations group by sched_id) a on a.sched_id=d.sched_id where a.q>d.qty+1e-9 and not (d.sched_id=151 and d.qty=1732 and coalesce(d.delivered_qty,0)=1732 and a.q=3748)) x
union all select 'I2c_over', 'Σ충당(확정) > 회차 delivered (예외 I 고정값)', count(*), string_agg(k, ',') filter (where rn<=5) from (select d.sched_id::text k, row_number() over (order by d.sched_id) rn from so_delivery_schedule d join (select a.sched_id, sum(a.qty) q from shipment_allocations a join shipment_items si on si.si_id=a.si_id join shipments s on s.shipment_id=si.shipment_id where s.status='CONFIRMED' group by a.sched_id) a on a.sched_id=d.sched_id where a.q>coalesce(d.delivered_qty,0)+1e-9 and not (d.sched_id=151 and d.qty=1732 and coalesce(d.delivered_qty,0)=1732 and a.q=3748)) x
union all select 'I2d', '충당 행 무효', count(*), string_agg(k, ',') filter (where rn<=5) from (select a.alloc_id::text k, row_number() over (order by a.alloc_id) rn from shipment_allocations a left join shipment_items si on si.si_id=a.si_id left join so_delivery_schedule d on d.sched_id=a.sched_id where a.qty<=0 or si.si_id is null or d.sched_id is null or d.soi_id is distinct from si.soi_id) x
union all select 'I2a_under[정보]', '확정 라인 qty > Σ충당 (B; 예외 I 고정값)', count(*), string_agg(k, ',') filter (where rn<=5) from (select si.si_id::text k, row_number() over (order by si.si_id) rn from shipment_items si join shipments s on s.shipment_id=si.shipment_id left join (select si_id, sum(qty) q from shipment_allocations group by si_id) a on a.si_id=si.si_id where s.status='CONFIRMED' and s.confirmed_at>='2026-09-05 00:00:00+09' and si.soi_id is not null and si.qty>coalesce(a.q,0)+1e-9 and not (si.si_id=378 and si.qty=1400 and coalesce(a.q,0)=1300)) x
union all select 'I2c_under[정보]', '회차 delivered > Σ충당(확정) (B)', count(*), string_agg(k, ',') filter (where rn<=5) from (select d.sched_id::text k, row_number() over (order by d.sched_id) rn from so_delivery_schedule d left join (select a.sched_id, sum(a.qty) q from shipment_allocations a join shipment_items si on si.si_id=a.si_id join shipments s on s.shipment_id=si.shipment_id where s.status='CONFIRMED' group by a.sched_id) a on a.sched_id=d.sched_id where d.created_at>='2026-09-05 00:00:00+09' and coalesce(d.delivered_qty,0)>coalesce(a.q,0)+1e-9) x
union all select 'I3', '비확정 전표 라인별 ISSUE 순합≠0 또는 충당 잔존', count(*), string_agg(k, ',') filter (where rn<=5) from (select k, row_number() over () rn from (select si.si_id::text k from shipments s join shipment_items si on si.shipment_id=s.shipment_id left join inventory_transactions t on t.ref_table='shipment_items' and t.ref_id=si.si_id and t.txn_type='ISSUE' where s.status in ('DRAFT','CANCELLED') group by si.si_id having abs(coalesce(sum(t.qty),0))>1e-9 union select si.si_id::text from shipments s join shipment_items si on si.shipment_id=s.shipment_id where s.status in ('DRAFT','CANCELLED') and exists (select 1 from shipment_allocations a where a.si_id=si.si_id)) y) x
union all select 'I4a', '확정 라인별 ΣISSUE ≠ −qty (10-13 이후, 제품·수주 연결)', count(*), string_agg(k, ',') filter (where rn<=5) from (select si.si_id::text k, row_number() over (order by si.si_id) rn from shipment_items si join shipments s on s.shipment_id=si.shipment_id left join (select ref_id, sum(qty) tq from inventory_transactions where ref_table='shipment_items' and txn_type='ISSUE' group by ref_id) t on t.ref_id=si.si_id where s.status='CONFIRMED' and s.confirmed_at>='2026-10-13 00:00:00+09' and si.soi_id is not null and si.product_id is not null and abs(coalesce(t.tq,0)+si.qty)>1e-9) x
union all select 'I4b', '미연결 라인에 ISSUE 또는 product_id 불일치', count(*), string_agg(k, ',') filter (where rn<=5) from (select t.txn_id::text k, row_number() over (order by t.txn_id) rn from inventory_transactions t join shipment_items si on si.si_id=t.ref_id where t.ref_table='shipment_items' and t.txn_type='ISSUE' and (si.soi_id is null or si.product_id is null or si.product_id is distinct from t.product_id)) x
union all select 'I4_legacy', '[레거시] 전표·제품 단위 ΣISSUE ≠ −Σqty (10-13 이전)', count(*), string_agg(k, ',') filter (where rn<=5) from (select s.ship_no||'/'||si.product_id k, row_number() over (order by s.shipment_id) rn from shipments s join shipment_items si on si.shipment_id=s.shipment_id left join (select ref_id, sum(qty) tq from inventory_transactions where ref_table='shipment_items' and txn_type='ISSUE' group by ref_id) t on t.ref_id=si.si_id where s.status='CONFIRMED' and s.confirmed_at<'2026-10-13 00:00:00+09' and si.soi_id is not null and si.product_id is not null group by s.ship_no, s.shipment_id, si.product_id having abs(coalesce(sum(t.tq),0)+sum(si.qty))>1e-9) x
union all select 'I20a', '머리글 rev_no ≠ 이력 max', count(*), string_agg(k, ',') filter (where rn<=5) from (select s.ship_no k, row_number() over (order by s.shipment_id) rn from shipments s where coalesce(s.rev_no,0)<>coalesce((select max(rev_no) from shipment_revisions r where r.shipment_id=s.shipment_id),0)) x
union all select 'I20b', '마지막 EDIT qty_after ≠ 라인 qty', count(*), string_agg(k, ',') filter (where rn<=5) from (select si.si_id::text k, row_number() over (order by si.si_id) rn from shipment_items si join shipments s on s.shipment_id=si.shipment_id join lateral (select qty_after from shipment_revisions v where v.si_id=si.si_id and v.action='EDIT' order by v.rev_no desc, v.rev_id desc limit 1) v on true where s.status='CONFIRMED' and abs(v.qty_after-si.qty)>1e-9) x
union all select 'I20c', '09-05 이후 취소 전표 CANCEL 이력·사유 없음', count(*), string_agg(k, ',') filter (where rn<=5) from (select s.ship_no k, row_number() over (order by s.shipment_id) rn from shipments s where s.status='CANCELLED' and s.cancelled_at>='2026-09-05 00:00:00+09' and coalesce(s.cancel_reason,'') not like '작성중 취소%' and not exists (select 1 from shipment_revisions r where r.shipment_id=s.shipment_id and r.action='CANCEL')) x
union all select 'I21', '대체 왕복 불일치', count(*), string_agg(k, ',') filter (where rn<=5) from (select k, row_number() over () rn from (select 'repl:'||r.repl_id k from so_line_replacements r join sales_order_items o on o.soi_id=r.old_soi_id where r.action='REPLACE' and r.reverted_at is null and (o.status<>'REPLACED' or o.replaced_by_soi is distinct from r.new_soi_id) union all select 'reverted:'||r.repl_id from so_line_replacements r join sales_order_items o on o.soi_id=r.old_soi_id where r.action='REPLACE' and r.reverted_at is not null and o.status='REPLACED' and not exists (select 1 from so_line_replacements r2 where r2.old_soi_id=r.old_soi_id and r2.action='REPLACE' and r2.reverted_at is null) union all select 'soi:'||i.soi_id from sales_order_items i where i.status='REPLACED' and not exists (select 1 from so_line_replacements r where r.old_soi_id=i.soi_id and r.action='REPLACE' and r.reverted_at is null)) y) x;
```
### 묶음 2 — 발주·재고·배치·생산 (5~8, 18, 19)
```sql
select 'I5a[정보]' inv, '초과 입고' sub, count(*) cnt, string_agg(k, ',') filter (where rn<=5) samples from (select po_number||'#'||line_no k, row_number() over (order by poi_id) rn from po_item_receipt_v where received_qty>ordered_qty+0.5) x
union all select 'I5b', 'DRAFT·CANCELLED 발주에 입고', count(*), string_agg(k, ',') filter (where rn<=5) from (select po_number||'#'||line_no k, row_number() over (order by poi_id) rn from po_item_receipt_v where po_status in ('DRAFT','CANCELLED') and received_qty>0) x
union all select 'I5c', '순입고 음수', count(*), string_agg(k, ',') filter (where rn<=5) from (select po_number||'#'||line_no k, row_number() over (order by poi_id) rn from po_item_receipt_v where received_qty < -1e-9) x
union all select 'I6a', '자재 LOT 잔량 음수', count(*), string_agg(k, ',') filter (where rn<=5) from (select material_id||'/'||lot_number k, row_number() over (order by material_id, lot_number) rn from (select material_id, lot_number from inventory_transactions where material_id is not null and lot_number is not null group by 1,2 having sum(qty) < -0.5) y) x
union all select 'I6b', 'PROD_INPUT LOT·자재 없음 (production_log 제외)', count(*), string_agg(k, ',') filter (where rn<=5) from (select txn_id::text k, row_number() over (order by txn_id) rn from inventory_transactions where txn_type='PROD_INPUT' and coalesce(ref_table,'')<>'production_log' and (lot_number is null or material_id is null)) x
union all select 'I6c[정보]', '자재 현재고 음수(stock_qty+원장)', count(*), string_agg(k, ',') filter (where rn<=5) from (select material_id k, row_number() over (order by current_stock) rn from material_stock where current_stock < -0.5) x
union all select 'I7a[정보]', '완성 재고 음수', count(*), string_agg(k, ',') filter (where rn<=5) from (select pn k, row_number() over (order by current_stock) rn from product_stock_v where current_stock < -0.5) x
union all select 'I7b', '제품 LOT 잔량 음수', count(*), string_agg(k, ',') filter (where rn<=5) from (select pn||'/'||lot_number k, row_number() over (order by remain_qty) rn from product_lot_stock_v where remain_qty < -0.5) x
union all select 'I7c', 'PROD_OUTPUT·전표 ISSUE 에 제품 없음', count(*), string_agg(k, ',') filter (where rn<=5) from (select txn_id::text k, row_number() over (order by txn_id) rn from inventory_transactions where product_id is null and (txn_type='PROD_OUTPUT' or (txn_type='ISSUE' and ref_table='shipment_items'))) x
union all select 'I7d', '제품 원장에 material_id 혼입(뷰 제외)', count(*), string_agg(k, ',') filter (where rn<=5) from (select txn_id::text k, row_number() over (order by txn_id) rn from inventory_transactions where txn_type in ('PROD_OUTPUT','ISSUE') and product_id is not null and material_id is not null) x
union all select 'I7e', '제품 LOT 뷰 (product_id, lot_number) 중복', count(*), string_agg(k, ',') filter (where rn<=5) from (select product_id||'/'||lot_number k, row_number() over () rn from product_lot_stock_v group by product_id, lot_number having count(*)>1) x
union all select 'I8a', 'CLOSED 지시(wo_id)에 OPEN 배치', count(*), string_agg(k, ',') filter (where rn<=5) from (select b.batch_no k, row_number() over (order by b.batch_id) rn from wo_batches b join wo_tracking w on w.wo_id=b.wo_id where b.status='OPEN' and w.status='CLOSED') x
union all select 'I8b', 'OPEN 배치 step_code 가 제품 라우팅·기본 플로우에 없음', count(*), string_agg(k, ',') filter (where rn<=5) from (select b.batch_no k, row_number() over (order by b.batch_id) rn from wo_batches b where b.status='OPEN' and b.step_code not in ('MAT_IN','PROD','OUT','INSPECT','DONE') and not exists (select 1 from product_routing r where r.product_id=b.product_id and r.step_code=b.step_code)) x
union all select 'I8c[정보]', '활성 지시에 OPEN 배치 0개', count(*), string_agg(k, ',') filter (where rn<=5) from (select w.wo_number k, row_number() over (order by w.wo_id) rn from wo_tracking w where w.status not in ('CLOSED','DONE') and not exists (select 1 from wo_batches b where b.wo_id=w.wo_id and b.status='OPEN')) x
union all select 'I8d', '배치 소유 불일치 / wo_id 없음', count(*), string_agg(k, ',') filter (where rn<=5) from (select b.batch_no k, row_number() over (order by b.batch_id) rn from wo_batches b left join wo_tracking w on w.wo_id=b.wo_id where b.wo_id is null or w.wo_id is null or b.wo_number is distinct from w.wo_number or b.product_id is distinct from w.product_id or b.w_lot is distinct from w.w_lot) x
union all select 'I8e[P2]', 'OPEN 배치 routing_id 고아', count(*), string_agg(k, ',') filter (where rn<=5) from (select b.batch_no k, row_number() over (order by b.batch_id) rn from wo_batches b where b.status='OPEN' and b.routing_id is not null and not exists (select 1 from product_routing r where r.routing_id=b.routing_id)) x
union all select 'I18a', '(지시번호,제품) output_qty 합 ≠ PROD_OUTPUT 합', count(*), string_agg(k, ',') filter (where rn<=5) from (select w.wo_number||'/'||w.product_id k, row_number() over (order by w.wo_number) rn from (select wo_number, product_id, sum(coalesce(output_qty,0)) o from wo_tracking group by 1,2) w left join (select work_order, product_id, sum(qty) q from inventory_transactions where txn_type='PROD_OUTPUT' and work_order is not null group by 1,2) t on t.work_order=w.wo_number and t.product_id=w.product_id where abs(w.o-coalesce(t.q,0))>1e-9) x
union all select 'I18c', 'PROD_OUTPUT work_order 에 대응 지시(번호+제품) 없음', count(*), string_agg(k, ',') filter (where rn<=5) from (select txn_id::text k, row_number() over (order by txn_id) rn from inventory_transactions t where t.txn_type='PROD_OUTPUT' and t.work_order is not null and not exists (select 1 from wo_tracking w where w.wo_number=t.work_order and w.product_id=t.product_id)) x
union all select 'I18b', '누적 필드 순서 위반', count(*), string_agg(k, ',') filter (where rn<=5) from (select wo_number k, row_number() over (order by wo_id) rn from wo_tracking where coalesce(pass_qty,0)<coalesce(output_qty,0)-1e-9 or coalesce(tokusai_qty,0)>coalesce(pass_qty,0)+1e-9 or coalesce(rework_in_qty,0)>coalesce(rework_qty,0)+1e-9 or coalesce(outsource_in_qty,0)>coalesce(outsource_qty,0)+1e-9) x
union all select 'I19a', '배치 계보 수량 보존 위반', count(*), string_agg(k, ',') filter (where rn<=5) from (select b.batch_no k, row_number() over (order by b.batch_id) rn from wo_batches b join wo_tracking w on w.wo_id=b.wo_id left join (select child_batch_id, sum(qty) q from batch_links group by 1) i on i.child_batch_id=b.batch_id left join (select parent_batch_id, sum(qty) q from batch_links where link_type='SPLIT' group by 1) o on o.parent_batch_id=b.batch_id left join (select parent_batch_id, sum(qty) q from batch_links where link_type='MERGE' group by 1) m on m.parent_batch_id=b.batch_id where (b.status<>'MERGED' and abs(b.qty-(coalesce(i.q,w.input_qty)-coalesce(o.q,0)))>1e-9) or (b.status='MERGED' and abs(b.qty-coalesce(m.q,0))>1e-9)) x
union all select 'I19b', '지시별 비MERGED 배치 합 ≠ input_qty', count(*), string_agg(k, ',') filter (where rn<=5) from (select w.wo_number k, row_number() over (order by w.wo_id) rn from wo_tracking w join (select wo_id, sum(qty) q from wo_batches where status<>'MERGED' group by 1) b on b.wo_id=w.wo_id where abs(b.q-coalesce(w.input_qty,0))>1e-9) x;
```
### 묶음 3 — 고아·상태·채번 (9~11)
```sql
select 'I9a-j' inv, '고아 참조 10종' sub, count(*) cnt, string_agg(k, ',') filter (where rn<=5) samples from (select k, row_number() over () rn from (
 select 'alloc:'||alloc_id k from shipment_allocations a where not exists (select 1 from shipment_items si where si.si_id=a.si_id)
 union all select 'sched:'||sched_id from so_delivery_schedule d where not exists (select 1 from sales_order_items i where i.soi_id=d.soi_id)
 union all select 'bom:'||bom_id from bom b where not exists (select 1 from products p where p.product_id=b.product_id)
 union all select 'txn_mat:'||txn_id from inventory_transactions t where t.material_id is not null and not exists (select 1 from materials m where m.material_id=t.material_id)
 union all select 'txn_prod:'||txn_id from inventory_transactions t where t.product_id is not null and not exists (select 1 from products p where p.product_id=t.product_id)
 union all select 'si:'||si_id from shipment_items si where not exists (select 1 from shipments s where s.shipment_id=si.shipment_id)
 union all select 'batch:'||batch_no from wo_batches b where not exists (select 1 from wo_tracking w where w.wo_id=b.wo_id)
 union all select 'issue_ref:'||txn_id from inventory_transactions t where t.txn_type='ISSUE' and t.ref_table='shipment_items' and not exists (select 1 from shipment_items si where si.si_id=t.ref_id)
 union all select 'si_soi:'||si_id from shipment_items si where si.soi_id is not null and not exists (select 1 from sales_order_items i where i.soi_id=si.soi_id)
 union all select 'wo_prod:'||wo_number from wo_tracking w where w.product_id is not null and not exists (select 1 from products p where p.product_id=w.product_id)) y) x
union all select 'I9k', 'RECEIPT ref → 발주 라인 없음', count(*), string_agg(k, ',') filter (where rn<=5) from (select txn_id::text k, row_number() over (order by txn_id) rn from inventory_transactions t where t.txn_type='RECEIPT' and t.ref_table='purchase_order_items' and not exists (select 1 from purchase_order_items p where p.poi_id=t.ref_id)) x
union all select 'I9l', '전표 라인·회차 so_id ≠ 수주 라인 부모', count(*), string_agg(k, ',') filter (where rn<=5) from (select k, row_number() over () rn from (select 'si:'||si.si_id k from shipment_items si join sales_order_items i on i.soi_id=si.soi_id where si.so_id is distinct from i.so_id union all select 'sched:'||d.sched_id from so_delivery_schedule d join sales_order_items i on i.soi_id=d.soi_id where d.so_id is distinct from i.so_id) y) x
union all select 'I10a', 'CONFIRMED confirmed_at 없음', count(*), string_agg(k, ',') filter (where rn<=5) from (select ship_no k, row_number() over (order by shipment_id) rn from shipments where status='CONFIRMED' and confirmed_at is null) x
union all select 'I10b', 'CANCELLED cancelled_at 없음', count(*), string_agg(k, ',') filter (where rn<=5) from (select ship_no k, row_number() over (order by shipment_id) rn from shipments where status='CANCELLED' and cancelled_at is null) x
union all select 'I10c', '수주 DELIVERED 인데 활성 라인 미납', count(*), string_agg(k, ',') filter (where rn<=5) from (select o.so_number k, row_number() over (order by o.so_id) rn from sales_orders o where o.status='DELIVERED' and exists (select 1 from sales_order_items_v v where v.so_id=o.so_id and v.pending_qty_calc>0.5)) x
union all select 'I10d[정보]', '비활성 수주 updated_at 뒤 확정 출고 (후보 진단; F 제외)', count(*), string_agg(k, ',') filter (where rn<=5) from (select o.so_number k, row_number() over (order by o.so_id) rn from sales_orders o where o.status in ('CANCELLED','CLOSED') and o.updated_at is not null and o.so_number not in ('202604160011','202606290006') and exists (select 1 from shipment_items si join shipments s on s.shipment_id=si.shipment_id where si.so_id=o.so_id and s.status='CONFIRMED' and si.qty>0 and s.confirmed_at>o.updated_at)) x
union all select 'I10d2', '비활성 라인 참조 DRAFT 전표', count(*), string_agg(k, ',') filter (where rn<=5) from (select distinct s.ship_no k, row_number() over (order by s.ship_no) rn from shipments s join shipment_items si on si.shipment_id=s.shipment_id join sales_order_items i on i.soi_id=si.soi_id where s.status='DRAFT' and i.status in ('CLOSED','CANCELLED','REPLACED')) x
union all select 'I10e-h', '라인·발주·DRAFT 상태 모순 4종', count(*), string_agg(k, ',') filter (where rn<=5) from (select k, row_number() over () rn from (select 'soi_dlv:'||soi_id k from sales_order_items where status='DELIVERED' and coalesce(received_qty,0)<qty-1e-9 union all select 'soi_pend:'||soi_id from sales_order_items where status='PENDING' and coalesce(received_qty,0)>1e-9 union all select 'po_rcv:'||po_number from (select distinct po_number from po_item_receipt_v where po_status='RECEIVED' and pending_qty>0.5) y union all select 'so_draft:'||o.so_number from sales_orders o where o.status='DRAFT' and exists (select 1 from sales_order_items i where i.so_id=o.so_id and coalesce(i.received_qty,0)>1e-9)) z) x
union all select 'I10i', '허용 밖 상태값', count(*), string_agg(k, ',') filter (where rn<=5) from (select k, row_number() over () rn from (select 'so:'||coalesce(status,'null') k from sales_orders where coalesce(status,'') not in ('DRAFT','CONFIRMED','IN_PROD','PARTIAL','DELIVERED','CANCELLED','CLOSED') union all select 'soi:'||coalesce(status,'null') from sales_order_items where coalesce(status,'') not in ('PENDING','IN_PROD','PARTIAL','DELIVERED','CANCELLED','CLOSED','REPLACED') union all select 'po:'||coalesce(status,'null') from purchase_orders where coalesce(status,'') not in ('DRAFT','SENT','PARTIAL','RECEIVED','CANCELLED','CLOSED') union all select 'ship:'||coalesce(status,'null') from shipments where coalesce(status,'') not in ('DRAFT','CONFIRMED','CANCELLED') union all select 'wo:'||coalesce(status,'null') from wo_tracking where coalesce(status,'') not in ('IN_PROD','OUTSOURCE','REWORK','INSPECT','CLOSED','DONE','READY','RECEIVED','CANCELLED')) y) x
union all select 'I10i_legacy[정보]', 'wo 레거시 상태값 건수', count(*), string_agg(k, ',') filter (where rn<=5) from (select status||'='||count(*) k, row_number() over () rn from wo_tracking where status in ('DONE','READY','RECEIVED','CANCELLED') group by status) x
union all select 'I10j', '배치 허용 밖 상태값', count(*), string_agg(k, ',') filter (where rn<=5) from (select 'batch:'||coalesce(status,'null') k, row_number() over () rn from wo_batches where coalesce(status,'') not in ('OPEN','DONE','SCRAP','RETURN','MERGED')) x
union all select 'I11a-c,e', 'ship_no·po_number·so_number·batch_no 중복', count(*), string_agg(k, ',') filter (where rn<=5) from (select k, row_number() over () rn from (select 'ship:'||ship_no k from shipments group by ship_no having count(*)>1 union all select 'po:'||po_number from purchase_orders group by po_number having count(*)>1 union all select 'so:'||so_number from sales_orders group by so_number having count(*)>1 union all select 'batch:'||batch_no from wo_batches group by batch_no having count(*)>1) y) x
union all select 'I11d1', 'wo_number 중복 — 제품 다름', count(*), string_agg(k, ',') filter (where rn<=5) from (select wo_number k, row_number() over () rn from wo_tracking group by wo_number having count(distinct coalesce(product_id,''))>1) x
union all select 'I11d2', 'wo_number 중복 — 같은 제품', count(*), string_agg(k, ',') filter (where rn<=5) from (select wo_number k, row_number() over () rn from wo_tracking group by wo_number having count(*)>1 and count(distinct coalesce(product_id,''))=1) x
union all select 'I11f', 'W LOT RECEIPT 중복', count(*), string_agg(k, ',') filter (where rn<=5) from (select lot_number k, row_number() over () rn from inventory_transactions where txn_type='RECEIPT' and lot_number ~ '^W[0-9]+$' group by lot_number having count(*)>1) x;
```
### 묶음 4 — 매입·종결·LOT 사슬·휴면·BOM·시간 (12~17)
```sql
with jl as (select si.si_id, s.shipment_id, s.ship_date from shipment_items si join shipments s on s.shipment_id=si.shipment_id where s.status='CONFIRMED' and si.customer='(주)엠제이티' and extract(day from (s.confirmed_at at time zone 'Asia/Seoul'))>=25 and s.ship_date>=(date_trunc('month',(s.confirmed_at at time zone 'Asia/Seoul')::date)+interval '1 month')::date and s.ship_date<=(date_trunc('month',(s.confirmed_at at time zone 'Asia/Seoul')::date)+interval '1 month'+interval '4 days')::date),
js as (select shipment_id from shipments s where s.status='CONFIRMED' and exists (select 1 from jl where jl.shipment_id=s.shipment_id) and not exists (select 1 from shipment_items si where si.shipment_id=s.shipment_id and si.si_id not in (select si_id from jl)))
select 'I12a[정보]' inv, 'mapping_status 분포 (cnt=미연결 행)' sub, (select count(*) from purchase_ledger where matched_material_id is null and matched_pn is null) cnt, (select string_agg(coalesce(mapping_status,'null')||'='||c, ',') from (select mapping_status, count(*) c from purchase_ledger group by 1 order by 2 desc) y) samples
union all select 'I12b[정보]', '미연결 최근 6개월 월별 (cnt=행 수)', sum(c), string_agg(m||'='||c, ',' order by m) from (select to_char(trade_date,'YYYY-MM') m, count(*) c from purchase_ledger where matched_material_id is null and matched_pn is null and trade_date>=current_date-interval '6 months' group by 1) x
union all select 'I13', '종결·취소 closed_qty / 비활성 pending / REPLACED 연결 / 활성 closed_qty 잔존', count(*), string_agg(k, ',') filter (where rn<=5) from (select soi_id::text k, row_number() over (order by soi_id) rn from sales_order_items where (status in ('CLOSED','CANCELLED') and close_reason is not null and abs(greatest(coalesce(qty,0)-coalesce(received_qty,0),0)-coalesce(closed_qty,0))>1e-9) or (status in ('CLOSED','CANCELLED','REPLACED') and abs(coalesce(pending_qty,0))>1e-9) or (status='REPLACED' and replaced_by_soi is null) or (coalesce(status,'') not in ('CLOSED','CANCELLED','REPLACED') and coalesce(closed_qty,0)>1e-9)) x
union all select 'I14a', 'PROD_OUTPUT 제품 LOT 없음 (created_at ≥ 10-27, production_log 제외)', count(*), string_agg(k, ',') filter (where rn<=5) from (select txn_id::text k, row_number() over (order by txn_id) rn from inventory_transactions where txn_type='PROD_OUTPUT' and lot_number is null and coalesce(ref_table,'')<>'production_log' and created_at>='2026-10-27 00:00:00+09') x
union all select 'I14b', 'PROD_INPUT LOT 기원 없음', count(*), string_agg(k, ',') filter (where rn<=5) from (select txn_id::text||'/'||lot_number k, row_number() over (order by txn_id) rn from inventory_transactions t where t.txn_type='PROD_INPUT' and t.lot_number is not null and coalesce(t.ref_table,'')<>'production_log' and not exists (select 1 from inventory_transactions r where r.lot_number=t.lot_number and r.material_id=t.material_id and (r.txn_type='RECEIPT' or (r.txn_type='ADJUSTMENT' and r.qty>0)))) x
union all select 'I14c', '지시 w_lot 기원 없음(같은 자재)', count(*), string_agg(k, ',') filter (where rn<=5) from (select wo_number||'/'||w_lot k, row_number() over (order by wo_id) rn from wo_tracking w where nullif(btrim(w.w_lot),'') is not null and not exists (select 1 from inventory_transactions r where r.lot_number=w.w_lot and r.material_id=w.material_id and (r.txn_type='RECEIPT' or (r.txn_type='ADJUSTMENT' and r.qty>0)))) x
union all select 'I15', '휴면 자재 참조 3종', count(*), string_agg(k, ',') filter (where rn<=5) from (select k, row_number() over () rn from (select 'bom:'||p.pn k from bom b join products p on p.product_id=b.product_id join materials m on m.material_id=b.material_id where p.archived_at is null and coalesce(b.process_type,'MATERIAL')='MATERIAL' and m.archived_at is not null union all select 'po:'||v.po_number||'#'||v.line_no from po_item_receipt_v v join materials m on m.material_id=v.material_id where v.pending_qty>0.5 and m.archived_at is not null union all select 'wo:'||w.wo_number from wo_tracking w join materials m on m.material_id=w.material_id where w.status<>'CLOSED' and m.archived_at is not null) y) x
union all select 'I16a', '활성 제품 소재행 2개 이상 (정책: 1개)', count(*), string_agg(k, ',') filter (where rn<=5) from (select p.pn k, row_number() over (order by p.pn) rn from products p join bom b on b.product_id=p.product_id and coalesce(b.process_type,'MATERIAL')='MATERIAL' where p.archived_at is null group by p.pn having count(*)>1) x
union all select 'I16b-c', '소재행 qty_per_pc≤0 / shared_factor<1 / material_id 없음', count(*), string_agg(k, ',') filter (where rn<=5) from (select p.pn k, row_number() over (order by b.bom_id) rn from bom b join products p on p.product_id=b.product_id where p.archived_at is null and coalesce(b.process_type,'MATERIAL')='MATERIAL' and (b.qty_per_pc<=0 or coalesce(b.shared_factor,1)<1 or b.material_id is null)) x
union all select 'I17a', '마감 월에 마감 뒤 확정·취소·정정', count(*), string_agg(k, ',') filter (where rn<=5) from (select s.ship_no k, row_number() over (order by s.shipment_id) rn from shipments s join sales_month_close c on c.ym=to_char(s.ship_date,'YYYY-MM') where greatest(coalesce(s.confirmed_at,'1900-01-01'),coalesce(s.cancelled_at,'1900-01-01'),coalesce(s.revised_at,'1900-01-01'))>c.closed_at) x
union all select 'I17b', '원장 txn_date > KST 오늘 (J: 엠제이티 라인 ISSUE 이고 txn_date = 전표 납품일인 행만 제외)', count(*), string_agg(k, ',') filter (where rn<=5) from (select t.txn_id::text k, row_number() over (order by t.txn_id) rn from inventory_transactions t where t.txn_date>(current_timestamp at time zone 'Asia/Seoul')::date and not (t.txn_type='ISSUE' and t.ref_table='shipment_items' and exists (select 1 from jl where jl.si_id=t.ref_id and jl.ship_date=t.txn_date))) x
union all select 'I17c', '확정 전표 ship_date > KST 오늘 (J: 모든 라인이 엠제이티 규칙에 맞는 전표만 제외)', count(*), string_agg(k, ',') filter (where rn<=5) from (select s.ship_no k, row_number() over (order by s.shipment_id) rn from shipments s where s.status='CONFIRMED' and s.ship_date>(current_timestamp at time zone 'Asia/Seoul')::date and s.shipment_id not in (select shipment_id from js)) x
union all select 'J[정보]', '예외 J 적용 전표(전 라인 엠제이티)', count(*), string_agg(k, ',') filter (where rn<=5) from (select s.ship_no k, row_number() over (order by s.shipment_id) rn from shipments s join js on js.shipment_id=s.shipment_id) x
union all select 'J_mixed[정보]', 'J 라인이 있으나 다른 거래처 라인이 섞인 전표', count(*), string_agg(k, ',') filter (where rn<=5) from (select distinct s.ship_no k, row_number() over (order by s.ship_no) rn from shipments s join jl on jl.shipment_id=s.shipment_id where s.shipment_id not in (select shipment_id from js)) x;
```

## 9. 리뷰·정정 기록
- 2026-10-27 Data Reviewer(v1) HIGH 7/M 10/L 6, Codex(v1) HIGH 10/M 5/L 2 → v2. Codex 재리뷰(v2.1 diff) HIGH 1/M 6/L 1 → v3. Codex 최종 확인(v2.1→v3 diff) **HIGH 0/M 2/L 1 → 커밋 권고**, 잔여 3건 반영(§0 끝). 남은 의견 차이 없음.
- 2026-10-27 L3-D: 지시번호 중복 2쌍(20260818-001→-003 분리, 20260901-001→-002 분리)·cancelled_at 백필 2건 적용(`_지시번호중복_취소시각백필_L3D_계획서_20261027.md`).
- 2026-10-27 MRG7-07 소재 정정(M180→M370, W1133→M179, M180 휴면).

## 10. 이력
- v1 10-27 초안(17) → v2 리뷰 반영(21) → v2.1 사용자 결정 7건 → **v3 재리뷰 반영·실행본·정정 뒤 점검 결과**.
