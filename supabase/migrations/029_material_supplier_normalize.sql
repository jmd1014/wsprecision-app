-- 029_material_supplier_normalize.sql
-- main_supplier 정리 (2026-07-31)
--
-- 028 로 조달유형을 정리하고 보니 main_supplier 자체도 오염돼 있었다.
--   "(주)명진메탈 / 발주서 시트: FLANGE"   ← 엑셀 시트명이 붙음
--   "(주)명진메탈(3)", "혜성철강(주)(3)"   ← 꼬리 일련번호
-- 거래처명만 남기고 잘라낸다. 결과: 10개 공급사로 수렴.

ALTER TABLE materials_cleanup_backup_028
  ADD COLUMN IF NOT EXISTS supplier_before_029 text;
UPDATE materials_cleanup_backup_028 b
   SET supplier_before_029 = m.main_supplier
  FROM materials m WHERE m.material_id = b.material_id;

UPDATE materials SET main_supplier = btrim(
  regexp_replace(regexp_replace(main_supplier,
    '\s*/\s*발주서\s*시트:.*$', ''), '\(\d+\)\s*$', ''))
WHERE main_supplier IS NOT NULL;

-- 같은 거래처 표기 통합
UPDATE materials SET main_supplier = '진광단조' WHERE main_supplier = '진광';

UPDATE materials SET main_supplier = NULL
WHERE btrim(COALESCE(main_supplier, '')) = '';
