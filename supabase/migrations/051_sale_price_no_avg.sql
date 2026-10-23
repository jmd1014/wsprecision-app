-- ════════════════════════════════════════════════════════════
-- 복구: 운영 ledger(supabase_migrations.schema_migrations) 에서 추출 2026-10-23 — 원본 파일 커밋 없음 (P1-5)
-- version: 20260831071705  name: 051_sale_price_no_avg
-- ════════════════════════════════════════════════════════════
-- 051: 판매가·마진에서 12M 평균 fallback 제거 (2026-08-31 사용자 확정:
-- 단가는 특정 시기에 바뀌므로 변동 내역이 중요하고 평균은 무의미)
-- 판매가 = 마스터 sale_price → 최근 출고가. 평균은 참고 컬럼
-- (avg_unit_price_12m/_3m)으로만 유지. 뷰 재정의는 전체 정의 명시.

create or replace view product_cost_full_v as
 SELECT p.product_id,
    p.pn,
    p.item_name,
    p.customer,
    p.sub_class,
    p.archived_at,
    p.material,
    p.raw_material_name,
    p.raw_material_spec,
    p.cost_data_quality,
    p.material_unit_price AS legacy_material_per_pc,
    p.outsourcing_per_pc AS legacy_outsource_per_pc,
    p.heat_treat_per_pc AS legacy_heat_per_pc,
    p.surface_per_pc AS legacy_surface_per_pc,
    p.estimated_cost_per_pc AS legacy_estimated_cost,
    bc.bom_cost_per_pc,
    bc.material_cost_per_pc,
    bc.heat_cost_per_pc,
    bc.surface_cost_per_pc,
    bc.outsource_cost_per_pc,
    bc.other_cost_per_pc,
    bc.bom_row_count,
    bc.material_rows,
    bc.process_rows,
    bc.rows_with_explicit_price,
    bc.rows_using_3m_avg,
    bc.rows_with_no_price,
    ac.avg_cycle_time_sec,
    ac.defect_rate,
    ac.avg_efficiency_pct,
    ac.labor_cost_per_pc_est,
    ac.log_count_6m,
    COALESCE(p.sale_price, NULLIF(ps.last_unit_price, (0)::numeric)) AS sale_price,
    COALESCE(p.sale_price, NULLIF(ps.last_unit_price, (0)::numeric)) AS avg_unit_price,
    ps.last_unit_price AS recent_price,
    ps.avg_unit_price AS avg_unit_price_12m,
    ps.avg_unit_price_3m,
    ps.total_sales_12m,
    ps.sales_count_12m,
    ps.abc_grade,
    ps.activity_trend,
    COALESCE(NULLIF(bc.bom_cost_per_pc, (0)::numeric), p.estimated_cost_per_pc) AS final_cost_per_pc,
    COALESCE(NULLIF(bc.bom_cost_per_pc, (0)::numeric), p.estimated_cost_per_pc) AS estimated_cost_per_pc,
    COALESCE(NULLIF(bc.material_cost_per_pc, (0)::numeric), p.material_unit_price) AS material_unit_price,
    COALESCE(NULLIF(bc.outsource_cost_per_pc, (0)::numeric), p.outsourcing_per_pc) AS outsourcing_per_pc,
    COALESCE(NULLIF(bc.heat_cost_per_pc, (0)::numeric), p.heat_treat_per_pc) AS heat_treat_per_pc,
    COALESCE(NULLIF(bc.surface_cost_per_pc, (0)::numeric), p.surface_per_pc) AS surface_per_pc,
    p.material_kg_price,
        CASE
            WHEN ((COALESCE(p.sale_price, NULLIF(ps.last_unit_price, (0)::numeric)) > (0)::numeric) AND (COALESCE(NULLIF(bc.bom_cost_per_pc, (0)::numeric), p.estimated_cost_per_pc) > (0)::numeric)) THEN round((((COALESCE(p.sale_price, NULLIF(ps.last_unit_price, (0)::numeric)) - COALESCE(NULLIF(bc.bom_cost_per_pc, (0)::numeric), p.estimated_cost_per_pc)) / COALESCE(p.sale_price, NULLIF(ps.last_unit_price, (0)::numeric))) * (100)::numeric), 1)
            ELSE NULL::numeric
        END AS margin_pct_calc,
        CASE
            WHEN ((COALESCE(p.sale_price, NULLIF(ps.last_unit_price, (0)::numeric)) > (0)::numeric) AND (COALESCE(NULLIF(bc.bom_cost_per_pc, (0)::numeric), p.estimated_cost_per_pc) > (0)::numeric)) THEN round((((COALESCE(p.sale_price, NULLIF(ps.last_unit_price, (0)::numeric)) - COALESCE(NULLIF(bc.bom_cost_per_pc, (0)::numeric), p.estimated_cost_per_pc)) / COALESCE(p.sale_price, NULLIF(ps.last_unit_price, (0)::numeric))) * (100)::numeric), 1)
            ELSE NULL::numeric
        END AS margin_pct,
        CASE
            WHEN ((bc.bom_row_count > 0) AND (bc.material_rows > 0) AND ((bc.rows_with_no_price = 0) OR (p.procurement_type = '사급'::text))) THEN 'BOM_FULL'::text
            WHEN ((bc.bom_row_count > 0) AND (bc.material_rows > 0)) THEN 'BOM_PARTIAL'::text
            WHEN (p.estimated_cost_per_pc > (0)::numeric) THEN 'LEGACY_ONLY'::text
            ELSE 'NO_DATA'::text
        END AS cost_source
   FROM (((products p
     LEFT JOIN product_bom_cost_v bc ON ((bc.product_id = p.product_id)))
     LEFT JOIN product_actual_cost_v ac ON ((ac.product_id = p.product_id)))
     LEFT JOIN product_stats ps ON ((ps.product_id = p.product_id)));

alter view product_cost_full_v set (security_invoker = true);
