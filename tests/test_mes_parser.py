"""MES 일간 보고서 파서 단위 테스트"""
import sys, os
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.services.mes_parser import (
    parse_mes_daily_report, parse_date_from_filename, match_product_pn)

# 실제 MES export 구조 축소 재현 (HTML table, .xls 위장)
FIXTURE = """
<table border="1">
<tr><td>설비명</td><td>제품명</td><td>공정명</td><td>작업시간</td><td>작업자</td><td>작업지시서</td><td>생산수량</td><td>불량수량</td></tr>
<tr><td>CNC01</td><td>4HDV-VM-04</td><td>CNC#10</td><td>09:27  ~  12:28</td><td>유근식</td><td>20260702-002&nbsp;&nbsp;&nbsp;[001]</td><td>70</td><td>0</td></tr>
<tr><td>CNC01</td><td>4HDV-VM-04</td><td>CNC#10</td><td>12:28 ~ 17:28</td><td>유근식</td><td>20260702-002 [001]</td><td>79</td><td>1</td></tr>
<tr><td>CNC01</td><td>4HDV-VM-04</td><td>CNC#10</td><td>소 계</td><td>소 계</td><td>소 계</td><td>149</td><td>1</td></tr>
<tr><td>MCT13</td><td>HA30-60251/SB</td><td>MCT#20</td><td>16:22 ~ 17:25</td><td>첸드수렌</td><td>20260630-003 [012]</td><td>62</td><td>0</td></tr>
<tr><td>MCT13</td><td>HA30-60251/SB</td><td>MCT#20</td><td>소 계</td><td>소 계</td><td>소 계</td><td>62</td><td>0</td></tr>
<tr><td>총 합 계</td><td>총 합 계</td><td>총 합 계</td><td>총 합 계</td><td>총 합 계</td><td>총 합 계</td><td>211</td><td>1</td></tr>
</table>
""".encode("utf-8")


def test_parse_detail_rows_only():
    rows = parse_mes_daily_report(FIXTURE)
    # 소계 2행 + 총합계 1행 제외 → 상세 3행
    assert len(rows) == 3
    assert all(r["equipment"] in ("CNC01", "MCT13") for r in rows)


def test_parse_fields():
    rows = parse_mes_daily_report(FIXTURE)
    r0 = rows[0]
    assert r0["item_name"] == "4HDV-VM-04"
    assert r0["process"] == "CNC#10"
    assert r0["process_step"] == 10
    assert r0["work_start"] == "09:27"
    assert r0["work_end"] == "12:28"
    assert r0["worker"] == "유근식"
    # &nbsp; 3개 → 공백 1개 정규화 (작업지시서 = 수주 연결 키 후보)
    assert r0["work_order"] == "20260702-002 [001]"
    assert r0["qty"] == 70.0
    assert r0["defect"] == 0.0
    # 불량 있는 행
    assert rows[1]["defect"] == 1.0


def test_parse_process_step_variants():
    rows = parse_mes_daily_report(FIXTURE)
    mct = [r for r in rows if r["equipment"] == "MCT13"][0]
    assert mct["process_step"] == 20
    assert mct["item_name"] == "HA30-60251/SB"


def test_date_from_filename():
    assert parse_date_from_filename("일간생산보고서_20260703.xls") == date(2026, 7, 3)
    assert parse_date_from_filename("일간생산보고서_20261231.xls") == date(2026, 12, 31)
    assert parse_date_from_filename("보고서.xls") is None


def test_match_product_pn():
    pns = {"4HDV-VM-04", "HA30-60251", "MRG6-07", "8HFDV-VM-05/BONNET"}
    # 정확 일치
    assert match_product_pn("4HDV-VM-04", pns) == "4HDV-VM-04"
    # 슬래시 있는 이름이 마스터에 그대로 존재
    assert match_product_pn("8HFDV-VM-05/BONNET", pns) == "8HFDV-VM-05/BONNET"
    # 슬래시 앞부분 fallback
    assert match_product_pn("HA30-60251/SB", pns) == "HA30-60251"
    # 미매칭
    assert match_product_pn("UNKNOWN-99", pns) is None
    assert match_product_pn("", pns) is None
