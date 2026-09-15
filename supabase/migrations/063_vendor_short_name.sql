-- Migration 063: 거래처 약칭 (short_name) — 2026-09-15
-- name = 사업자등록 정식 명칭 (거래명세서·세금 서류 기준)
-- short_name = 약칭 (업로드 파일의 거래처 표기 인식·검색·화면 축약)
-- 사례: 현대제뉴인(주) → 사명 변경 '에이치디현대사이트솔루션(주)'(약칭 HDX)
--       사업자등록 명칭 변경 전까지 정식명 유지, HDX 는 약칭으로 연결
ALTER TABLE vendors ADD COLUMN IF NOT EXISTS short_name TEXT;
COMMENT ON COLUMN vendors.short_name IS
  '약칭 — 업로드 파일 거래처 표기 인식·검색·화면 축약용. name 은 사업자등록 정식 명칭';
CREATE UNIQUE INDEX IF NOT EXISTS ux_vendors_short_name
  ON vendors (short_name) WHERE short_name IS NOT NULL;

UPDATE vendors
SET short_name = 'HDX',
    memo = CASE WHEN COALESCE(memo, '') = '' THEN '' ELSE memo || ' · ' END
           || '사명 변경: 에이치디현대사이트솔루션(주), 약칭 HDX — 사업자등록 '
           || '명칭 변경 전까지 정식명 현대제뉴인(주) 유지 (2026-09-15)'
WHERE vendor_id = 188;
