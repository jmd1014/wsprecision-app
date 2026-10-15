-- ════════════════════════════════════════════════════════════
-- Migration 071: 매입 내재화 1단계 — 매입 품명 매핑표 + 장부 출처·매핑 참조 열 (2026-10-15)
-- (계획서 docs/development/plans/20261015_L3S_매입내재화_1단계.md, Data Reviewer v2 반영)
-- ════════════════════════════════════════════════════════════
-- ① purchase_item_map   거래처 키 + 품명 키 → 자재/제품/라인 유형. 한 번 확인한 (거래처, 품명)은
--                       시트 동기화·수기 입력·(2단계) 스캔 입력에서 자동 적용. 씨앗은 장부의 기존 자재 매칭
--                       (스크립트, 같은 정규화 함수 utils/purchase_sync.vendor_key/item_key 사용).
-- ② purchase_ledger.source        입력구: SHEET(시트 동기화, 기본) / MANUAL(수기) / SCAN(2단계) / PO(발주)
-- ③ purchase_ledger.statement_no  거래명세서 번호(수기·스캔 입력, 선택)
-- ④ purchase_ledger.map_id        이 행을 연결한 매핑표 행(역추적·연결 해제용), 매핑 삭제 시 NULL
-- 운영 데이터 변경: source 를 기존 행 전부 'SHEET' 로 채움(지금까지 입력구는 시트뿐). 그 외 없음.
-- Old App + New DB: 구앱 insert 는 source 를 안 보내도 DEFAULT 'SHEET'. New App + Old DB 불가 → 배포 전 적용.
-- 되돌리기(코드 revert 뒤):
--   ALTER TABLE public.purchase_ledger DROP COLUMN IF EXISTS map_id;
--   DROP TABLE IF EXISTS public.purchase_item_map;
--   ALTER TABLE public.purchase_ledger DROP CONSTRAINT IF EXISTS purchase_ledger_source_chk;
--   ALTER TABLE public.purchase_ledger DROP COLUMN IF EXISTS source, DROP COLUMN IF EXISTS statement_no;
-- ════════════════════════════════════════════════════════════

ALTER TABLE public.purchase_ledger ADD COLUMN IF NOT EXISTS source text;
ALTER TABLE public.purchase_ledger ADD COLUMN IF NOT EXISTS statement_no text;
UPDATE public.purchase_ledger SET source = 'SHEET' WHERE source IS NULL;
ALTER TABLE public.purchase_ledger ALTER COLUMN source SET DEFAULT 'SHEET';
ALTER TABLE public.purchase_ledger DROP CONSTRAINT IF EXISTS purchase_ledger_source_chk;
ALTER TABLE public.purchase_ledger
    ADD CONSTRAINT purchase_ledger_source_chk CHECK (source IN ('SHEET','MANUAL','SCAN','PO'));
COMMENT ON COLUMN public.purchase_ledger.source IS '입력구: SHEET 시트 동기화(기본) / MANUAL 수기 / SCAN 명세서 스캔 / PO 발주 (071)';
COMMENT ON COLUMN public.purchase_ledger.statement_no IS '거래명세서 번호(수기·스캔 입력 시, 선택) (071)';

CREATE TABLE IF NOT EXISTS public.purchase_item_map (
    map_id        serial PRIMARY KEY,
    vendor_key    text NOT NULL,           -- utils/purchase_sync.vendor_key(장부 vendor)  예: '명진메탈'
    item_key      text NOT NULL,           -- utils/purchase_sync.item_key(장부 item)      예: 'STS304육각38Φ*24L'
    item_sample   text,                    -- 사람이 읽을 원문 품명 예시
    line_type     text NOT NULL CHECK (line_type IN ('MATERIAL','SUPPLY','PRODUCT','PROCESS','OTHER')),
    material_id   text REFERENCES public.materials(material_id),
    product_id    text REFERENCES public.products(product_id),
    process_type  text CHECK (process_type IS NULL OR process_type IN ('HEAT','SURFACE','OUTSOURCE','TRANSPORT','OTHER')),
    note          text,
    origin        text NOT NULL DEFAULT 'USER' CHECK (origin IN ('SEED','USER','DIMS')),
    confirmed_by  text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (vendor_key, item_key),
    -- 라인 유형과 연결 컬럼의 상호배타 (Reviewer M3)
    CHECK ((line_type IN ('MATERIAL','SUPPLY')) = (material_id IS NOT NULL)),
    CHECK ((line_type = 'PRODUCT') = (product_id IS NOT NULL)),
    CHECK (line_type = 'PROCESS' OR process_type IS NULL)
);
CREATE INDEX IF NOT EXISTS purchase_item_map_material_idx ON public.purchase_item_map(material_id);
ALTER TABLE public.purchase_item_map ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.purchase_item_map FROM anon, authenticated;
GRANT ALL ON public.purchase_item_map TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.purchase_item_map_map_id_seq TO service_role;
COMMENT ON TABLE public.purchase_item_map IS '매입 품명 매핑표 — (거래처 키, 품명 키) → 자재/제품/라인 유형. 동기화·수기·스캔 입력의 자동 연결 근거. 씨앗 = 장부 기존 자재 매칭 (071, 2026-10-15)';

ALTER TABLE public.purchase_ledger ADD COLUMN IF NOT EXISTS map_id integer
    REFERENCES public.purchase_item_map(map_id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS purchase_ledger_map_idx ON public.purchase_ledger(map_id);
COMMENT ON COLUMN public.purchase_ledger.map_id IS '이 행의 자재/제품 연결을 만든 매핑표 행 (071). 매핑 삭제 시 NULL — 연결 해제는 mapping_status/matched 와 함께 코드가 처리';
