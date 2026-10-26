# 복원 리허설 기록 (P1-1)

야간 백업(JSONL)만으로 DB 를 처음부터 다시 세울 수 있는지 확인한다. 운영 DB 는 비교 조회만 하고, 쓰기는 개발 PC 의 로컬 PostgreSQL `wsapp_restore` 에만 한다. 주기: **분기 1회**(점검표 A1).

## 1. 2026-10-26 결과

| 항목 | 값 |
|---|---|
| 로컬 PostgreSQL | 17.11 (Windows, 서비스 `postgresql-x64-17`) — 운영 Supabase 17.6 과 같은 메이저 |
| 백업 | `G:\내 드라이브\제품관리DB\backup\20261026` (02:30 야간 백업, 47테이블, 36,177행) |
| 스키마 | `_INITIAL_SETUP_ONLY_schema.sql` + `migrations/001~077` + adhoc 1 = **79파일, 실패 0** (5.1초) |
| 데이터 | **47테이블 전부 행 수 = manifest** (2.0초), 시퀀스 35개 보정(0.1초) |
| 핵심 3테이블(운영 비교, id ≤ 백업 최대 id) | `sales_orders` 82행·합 5,004,382,143 / `sales_order_items` 345행·qty 합 841,932 / `inventory_transactions` 1,032행·qty 합 −136,418 — **모두 일치** |
| 뷰·함수 | `sales_order_stats`·`product_stock_v`·`product_lot_stock_v` 조회 성공, `confirm_shipment`·`so_close_lines`·`so_reopen_lines`·`dash_generate_cards` 존재 (검증 2.5초) |
| 스키마 일치(운영 카탈로그 대조) | 열 1,162 · 제약 152 · 인덱스 137 · 함수 서명 8 · 뷰 옵션 29 · **RLS 플래그 76 · 뷰 정의 29 모두 해시 일치**. 함수 본문 8 개는 **주석만 다름**(주석·공백 제거 뒤 일치) |
| 전체 소요 | 약 10초(+ 운영 비교 조회) |
| 결과 JSON | `G:\내 드라이브\제품관리DB\_복원리허설_결과_20261026.json` |

운영 현재 `inventory_transactions` 는 1,113행 — 백업(02:30) 뒤 작업지시 일괄 정리(72행) 등이 더해진 것이라 비교는 "백업 최대 id 이하"로 맞췄다.

## 2. 리허설이 드러낸 차이와 처리

| # | 차이 | 원인 | 처리 |
|---|---|---|---|
| 1 | 033(RLS 켜기)이 `zz_bak_golive_sales_orders` 없음으로 실패 | 033 이 RLS 를 켜는 백업 표 13개(`zz_bak_golive_*` 6, `*_backup_0805/0806` 7)는 운영에서 **마이그레이션 파일 밖**(SQL 편집기·MCP 1회성)으로 만들어졌고 066 에서 지워졌다. 저장소에 만드는 SQL 이 없다 | 복원 스크립트가 033 직전에 빈 스텁 13개를 만들고 기록(`PRE_STUBS`). 066 이 그대로 지운다. 033 파일은 운영 ledger 그대로라 수정하지 않음 |
| 2 | 로컬 19개 표가 RLS 꺼짐(운영은 전부 켜짐) | Supabase 대시보드에서 만든 표는 처음부터 RLS 가 켜진다 — 초기 스키마 파일에 `ENABLE ROW LEVEL SECURITY` 가 없다 | 스크립트가 스키마 적용 뒤 public 의 모든 표 RLS ON(Supabase 기본값 재현) |
| 3 | `data_quality_v` 정의가 다름 — `confirmed_at >= '2026-09-05 00:00:00+09'` vs 운영 `+00` | 054 의 `'2026-09-05'::timestamptz` 상수가 **세션 시간대**로 해석된다. 로컬 서버는 Asia/Seoul, Supabase 는 UTC → 9시간 다른 순간으로 저장 | 복원 DB `timezone = UTC` + psql `PGTZ=UTC`. 교훈: 마이그레이션에 시간대 없는 timestamptz 상수를 쓰지 말 것(`'…+00'` 명시) |
| 4 | `dash_parts`·`dash_routine_templates`·`sales_data_exclusion`·`shift_profiles` 중복 키 | 마이그레이션(012·070·073)이 시드 행을 넣는다 | 적재 전 그 표를 비우고 백업 값으로 채움(시드 행 교체 기록) |
| 5 | 함수 본문 8개 해시 다름 | 저장소 파일의 함수 본문 안 주석이 MCP 로 적용된 운영 본문에는 없다 | 의미 차이 없음(주석·공백 제거 뒤 해시 일치) — 기록만 |

P1-5 복구 파일(033~062 + adhoc) 검증: **전부 무오류 적용**, 위 #1 은 파일 결함이 아니라 마이그레이션 밖 이력이다.

## 3. 다시 하는 법

1. 로컬 secrets(`.streamlit/secrets.toml`, git 제외)에 `[restore_pg] dsn = "postgresql://postgres:<비밀번호>@localhost:5432/postgres"` — 비밀번호에 `@ # % / :` 가 있으면 `password = "…"` 키를 따로(우선 적용).
2. `pip install -r requirements-dev.txt` (psycopg2, 개발 PC 전용).
3. `python scripts/restore_local.py` (최신 백업) 또는 `--backup <폴더>`, 운영 비교 생략은 `--no-prod-compare`.
4. 스키마 일치까지 보려면 같은 카탈로그 서명 SQL(열·제약·인덱스·함수·RLS·뷰 정의를 범주별 md5)을 운영(MCP 읽기)과 로컬에서 돌려 비교.

안전장치: DSN 호스트가 localhost/127.0.0.1/::1 이 아니면 중단, 쓰는 DB 이름은 `wsapp_restore` 고정(관리 접속은 `postgres`), 운영은 GET 비교만(정적 테스트 `tests/test_restore_local_static.py`).

되돌리기: 로컬에서 `DROP DATABASE wsapp_restore;` (운영 무관). 리허설 뒤 DB 는 남겨 둬도 되고 서비스는 꺼도 된다.
