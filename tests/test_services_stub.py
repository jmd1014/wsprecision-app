"""신규 서비스 stub 단위 테스트 — 핵심 공식/분류 검증"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.services import bom_service, cost_service, material_mapping_service, diagnostics_service


def test_bom_calc_per_pc():
    # MRG6-07 소재열처리: LOT 200,000원 / 5,000EA × 1 = 40원/EA
    assert bom_service.calc_per_pc(200000, 1, 5000) == 40.0
    # 제품열처리: LOT 200,000원 / 2,000EA × 1 = 100원/EA
    assert bom_service.calc_per_pc(200000, 1, 2000) == 100.0
    # qty_per_pc > 1
    assert bom_service.calc_per_pc(1000, 2, 1) == 2000.0
    # shared_factor 0 → 0 (안전)
    assert bom_service.calc_per_pc(1000, 1, 0) == 0.0


def test_bom_row_type():
    assert bom_service.is_material_row(None) is True       # 기본값 MATERIAL
    assert bom_service.is_material_row("MATERIAL") is True
    assert bom_service.is_material_row("HEAT") is False
    assert bom_service.is_process_row("HEAT") is True
    assert bom_service.is_process_row("MATERIAL") is False
    assert bom_service.is_process_row(None) is False


def test_cost_margin():
    # 판매가 1,000 - 원가 700 = 마진 300 → 30%
    assert cost_service.calc_margin(1000, 700) == 30.0
    # 판매가 1,840 - 원가 408 = 마진 1,432 → 77.8%
    assert cost_service.calc_margin(1840, 408) == 77.8
    # 역마진
    assert cost_service.calc_margin(100, 150) == -50.0
    # 판매가 0 → None
    assert cost_service.calc_margin(0, 100) is None
    # 원가 None → None
    assert cost_service.calc_margin(1000, None) is None


def test_cost_classify():
    assert cost_service.classify_margin(None) == "UNKNOWN"
    assert cost_service.classify_margin(-5) == "NEGATIVE"
    assert cost_service.classify_margin(5) == "LOW"
    assert cost_service.classify_margin(20) == "NORMAL"
    assert cost_service.classify_margin(40) == "GOOD"
    assert cost_service.classify_margin(60) == "VERY_HIGH"


def test_cost_source_label():
    assert "BOM_FULL" in cost_service.cost_source_label("BOM_FULL")
    assert "?" == cost_service.cost_source_label("UNKNOWN_VALUE")


def test_material_normalize():
    assert material_mapping_service.normalize_item_key("  ABC ") == "abc"
    assert material_mapping_service.normalize_item_key("환봉 STS304") == "환봉 sts304"
    assert material_mapping_service.normalize_item_key(None) == ""
    assert material_mapping_service.normalize_item_key("") == ""


def test_material_confidence_label():
    assert "완전일치" in material_mapping_service.confidence_label(100)
    assert "높음" in material_mapping_service.confidence_label(85)
    assert "중간" in material_mapping_service.confidence_label(60)
    assert "낮음" in material_mapping_service.confidence_label(35)
    assert "후보 없음" in material_mapping_service.confidence_label(0)


def test_diagnostics_labels():
    assert "🟢" in diagnostics_service.completion_status_label("COMPLETE")
    assert "🔴" in diagnostics_service.completion_status_label("NO_BOM")
    assert "?" == diagnostics_service.completion_status_label("UNKNOWN")
    assert "긴급" in diagnostics_service.priority_label(1)
    assert "낮음" in diagnostics_service.priority_label(4)
