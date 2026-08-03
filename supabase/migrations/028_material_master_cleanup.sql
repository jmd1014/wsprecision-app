-- 028_material_master_cleanup.sql
-- 자재 마스터 선행 정리 (2026-07-31)
--
-- 배경: procurement_type(조달유형) 칸에 세 가지가 섞여 들어가 있었다.
--   ① 정상 조달유형 + 공급사   "도급소재(명진메탈)" 90건 / "사급단조(세원금속)" 40건
--   ② 그 소재를 쓰는 제품 품번  "THNV-4MCT20-08", "T32HYPBV-08/실린더"  130건
--   ③ 자유 메모                 "테스트입니다", "사용금지(Ø175*20 으로 사용)"
-- ②③은 버릴 정보가 아니라 칸을 잘못 쓴 것이므로 전용 컬럼으로 옮긴다.
-- 조달유형은 입고 처리의 분기 기준이므로 표준 4값(도급/사급/구매/외주)으로 고정한다.
--
-- 원본은 materials_cleanup_backup_028 에 통째로 보존 — 되돌릴 수 있다.

-- ── 1. 원본 백업 ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS materials_cleanup_backup_028 AS
SELECT material_id, raw_name, material_type, spec,
       procurement_type, main_supplier, now() AS backed_up_at
FROM materials;

COMMENT ON TABLE materials_cleanup_backup_028 IS
  'Migration 028 실행 직전 materials 스냅샷 — 정리 결과가 잘못됐을 때 복원용';

-- ── 2. 컬럼 추가 ────────────────────────────────────────
ALTER TABLE materials ADD COLUMN IF NOT EXISTS applied_pn  text;
ALTER TABLE materials ADD COLUMN IF NOT EXISTS remark      text;

COMMENT ON COLUMN materials.applied_pn IS
  '이 소재를 쓰는 대표 제품 품번 — 참고용. 정식 연결은 bom 테이블';
COMMENT ON COLUMN materials.remark IS '자유 메모 (정리 전 조달유형 칸의 원본 값 포함)';
COMMENT ON COLUMN materials.procurement_type IS
  '조달유형 표준 4값: 도급 / 사급 / 구매 / 외주 (공급사는 main_supplier)';

-- ── 3. ②③ — 품번·메모가 들어간 138건을 옮긴다 ──────────
UPDATE materials SET
  remark = COALESCE(remark, procurement_type),
  applied_pn = COALESCE(
    applied_pn,
    -- "T32HYPBV-08/실린더" → 슬래시 앞을 먼저 자르고, 남은 것이
    -- 영숫자로 시작하고 한글이 없으면 품번으로 본다
    (SELECT h FROM (
       SELECT split_part(regexp_replace(procurement_type,
                                        '\s*\(.*\)\s*$', ''), '/', 1) AS h) s
     WHERE s.h ~ '^[A-Za-z0-9]' AND s.h !~ '[가-힣]' AND length(s.h) >= 4)),
  procurement_type = NULL
WHERE procurement_type IS NOT NULL
  AND procurement_type !~ '(도급|사급|구매|매입|외주)';

-- ── 4. ① — 조달유형 표준화 + 괄호 안 공급사 분리 ────────
UPDATE materials SET
  -- 기존 main_supplier 가 있으면 건드리지 않는다
  main_supplier = COALESCE(
    main_supplier,
    (SELECT v FROM (
       SELECT (regexp_match(procurement_type, '\(([^)]*)\)'))[1] AS v) s
     -- "매입추정", "57 EA", "Ø175*20 으로 사용" 같은 비-공급사 값은 제외
     WHERE s.v IS NOT NULL AND s.v ~ '[가-힣]'
       AND s.v !~ '(추정|사용|[0-9]\s*(ea|EA))')),
  remark = COALESCE(remark, procurement_type),
  procurement_type = CASE
    WHEN procurement_type ~ '도급'      THEN '도급'
    WHEN procurement_type ~ '사급'      THEN '사급'
    WHEN procurement_type ~ '외주'      THEN '외주'
    WHEN procurement_type ~ '(구매|매입)' THEN '구매'
    ELSE procurement_type END
WHERE procurement_type IS NOT NULL;

-- ── 5. 표준값 강제 ──────────────────────────────────────
ALTER TABLE materials DROP CONSTRAINT IF EXISTS materials_procurement_type_chk;
ALTER TABLE materials ADD CONSTRAINT materials_procurement_type_chk
  CHECK (procurement_type IS NULL
         OR procurement_type IN ('도급', '사급', '구매', '외주'));

-- ── 6. 조회용 인덱스 ────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_materials_applied_pn
  ON materials (applied_pn) WHERE applied_pn IS NOT NULL;
