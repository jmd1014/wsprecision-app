-- ════════════════════════════════════════════════════════════
-- Migration 027: 분납 스케줄 (수주 라인별 회차 납품 계획)
-- ════════════════════════════════════════════════════════════
-- 배경 (2026-07-28):
--   미진 ERP 발주에는 납기일이 97% 비어 있고(1,073/1,102), 실무는
--   "수주 후 분납 스케줄을 만들거나 납기일을 협의"하는 방식.
--   주당 납품 계획이 있는 분납을 관리하려면 수주 라인 아래에
--   회차별 예정일·수량이 필요하다.
--
-- 설계:
--   - 수주 라인(soi_id) 아래 회차(seq) 단위. 총량은 라인이 갖고,
--     스케줄은 "언제 얼마씩" 만 정의 → 스케줄 없는 수주는 기존처럼
--     단일 납기로 동작 (하위 호환).
--   - 납기 표시/정렬은 '가장 빠른 미완료 회차'(qty > delivered_qty).
--   - 출고 시 회차 충당은 앱에서 처리 (오래된 회차부터).
--   - 회차는 자유롭게 추가·삭제·수정 (실무 협의 변경 대응).
--
-- 비파괴 / 멱등.
-- ════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS so_delivery_schedule (
  sched_id      SERIAL PRIMARY KEY,
  so_id         INTEGER NOT NULL,
  soi_id        INTEGER NOT NULL,
  seq           INTEGER NOT NULL DEFAULT 1,
  due_date      DATE NOT NULL,
  qty           NUMERIC NOT NULL DEFAULT 0,
  delivered_qty NUMERIC NOT NULL DEFAULT 0,
  note          TEXT,
  created_by    TEXT,
  created_at    TIMESTAMPTZ DEFAULT now(),
  updated_at    TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sds_soi ON so_delivery_schedule(soi_id);
CREATE INDEX IF NOT EXISTS idx_sds_so ON so_delivery_schedule(so_id);
CREATE INDEX IF NOT EXISTS idx_sds_due ON so_delivery_schedule(due_date);
CREATE UNIQUE INDEX IF NOT EXISTS idx_sds_soi_seq
  ON so_delivery_schedule(soi_id, seq);

COMMENT ON TABLE so_delivery_schedule IS
  '수주 라인별 분납 스케줄 — 회차(seq)별 예정일/수량. 스케줄이 없는 '
  '수주는 라인 납기로 동작. 납기 표시는 가장 빠른 미완료 회차 기준';

-- 라인별 스케줄 요약 (다음 납기 / 총 계획 / 잔여)
CREATE OR REPLACE VIEW so_schedule_summary_v AS
SELECT
  s.soi_id,
  s.so_id,
  COUNT(*)                                   AS seq_count,
  SUM(s.qty)                                 AS planned_qty,
  SUM(s.delivered_qty)                       AS delivered_qty,
  SUM(GREATEST(s.qty - s.delivered_qty, 0))  AS remain_qty,
  MIN(s.due_date) FILTER (WHERE s.qty > s.delivered_qty) AS next_due,
  MIN(s.due_date)                            AS first_due,
  MAX(s.due_date)                            AS last_due
FROM so_delivery_schedule s
GROUP BY s.soi_id, s.so_id;

COMMENT ON VIEW so_schedule_summary_v IS
  '수주 라인별 분납 요약 — next_due 가 화면에 표시되는 납기';
