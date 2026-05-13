-- 마이그레이션 #1: vendor_group 컬럼 추가
-- 사용자가 Supabase SQL Editor에 1번만 실행

ALTER TABLE vendors ADD COLUMN IF NOT EXISTS vendor_group TEXT;
CREATE INDEX IF NOT EXISTS idx_vendors_group ON vendors(vendor_group);

-- 검증: 다음 쿼리로 컬럼 확인 가능
-- SELECT column_name FROM information_schema.columns WHERE table_name='vendors' AND column_name='vendor_group';
