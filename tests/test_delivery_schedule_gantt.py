"""
납품 스케줄 — 7b 회차 간트 렌더 검증 (DESIGN_HANDOFF 3-1)

운영 DB 의 실제 스케줄 데이터를 mock 으로 주입해, 간트 그리드가
  · 8열 (250px + 6주 + 이후) 정렬을 유지하는지
  · 회차 칩 / 계획률 / 주 합계 / KPI / 미계획 배너 값이 맞는지
를 헤드리스로 확인한다. (기준일 2026-07-31, 이번 주 월요일 07-27)
"""
import os
import sys
import re
import importlib.util
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

streamlit_available = importlib.util.find_spec("streamlit") is not None
pytestmark = pytest.mark.skipif(
    not streamlit_available, reason="streamlit 미설치 — AppTest 불가")

APP_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "streamlit_app.py")

# ─── 고정 데이터셋 ────────────────────────────────────
# 오늘(테스트 실행일) 기준 주차로 환산해 '지연/이번 주/다음 주/이후'
# 네 구간이 모두 생기도록 상대 오프셋으로 정의한다.
_TODAY = date.today()
_W0 = _TODAY - timedelta(days=_TODAY.weekday())   # 이번 주 월요일


def _d(offset_days):
    return (_W0 + timedelta(days=offset_days)).isoformat()


# (soi_id, so_id, 품번, 미납, 라인 납기)
LINES = [
    (1, 10, "4PDVN-02", 91648, None),      # 분납 · 계획률 낮음
    (2, 11, "4PDVN-03", 7600, None),       # 분납 · 계획률 100%
    (3, 12, "8HFDV-VM-05", 8500, None),    # 분납 · 완료 회차 포함
    (4, 13, "8PDVN-02", 3000, None),       # 분납 · 지연(지난 주)
    (5, 14, "8HFDV-15PIF-01", 10, _d(9)),  # 단발 · 예정
    (6, 15, "839-339939-001-A02", 79, _d(1)),   # 단발 · 지연
    (7, 16, "4S20AHYBV-03-X1413", 54288, None),  # 납기 미협의 (미계획)
]
# (sched_id, soi_id, so_id, seq, 납기, 수량, 납품완료)
SCHED = [
    (101, 1, 10, 1, _d(2), 2016, 0),       # 지연 (이번 주 수요일이지만 과거)
    (102, 1, 10, 2, _d(9), 1008, 0),
    (103, 1, 10, 3, _d(16), 2016, 0),
    (104, 2, 11, 1, _d(2), 1400, 0),
    (105, 2, 11, 2, _d(30), 1400, 0),
    (106, 2, 11, 3, _d(60), 4800, 0),      # '이후' 열 (6주 밖)
    (107, 3, 12, 1, _d(-5), 300, 300),     # 완료
    (108, 3, 12, 2, _d(9), 500, 0),
    (109, 4, 13, 1, _d(-5), 1500, 0),      # 지난 주 → 지연, 이번 주 칸
    (110, 4, 13, 2, _d(16), 1500, 0),
]
ORDERS = {10: ("202604080013-MJT", "㈜엠제이티"),
          11: ("202604220014-MJT", "㈜엠제이티"),
          12: ("202605120010", "미진정밀"),
          13: ("202604220013-MJT", "㈜엠제이티"),
          14: ("202607220001", "미진정밀"),
          15: ("202607010001", "미진정밀"),
          16: ("202607280011", "미진정밀")}


def _line_row(t):
    soi, so, pn, pend, due = t
    return {"soi_id": soi, "so_id": so, "canonical_pn": pn,
            "customer_part_no": pn, "qty": pend, "received_qty": 0,
            "pending_qty": pend, "due_date": due}


def _sched_row(t):
    sid, soi, so, seq, due, qty, done = t
    return {"sched_id": sid, "soi_id": soi, "so_id": so, "seq": seq,
            "due_date": due, "qty": qty, "delivered_qty": done,
            "note": None}


def _fetch(table, select="*", filter_query="", limit=1000):
    if table == "so_delivery_schedule":
        return [_sched_row(t) for t in SCHED]
    if table == "sales_order_items":
        rows = [_line_row(t) for t in LINES]
        if "pending_qty=gt.0" in filter_query:
            rows = [r for r in rows if r["pending_qty"] > 0]
        m = re.search(r"soi_id=in\.\(([^)]*)\)", filter_query)
        if m:
            want = {int(x) for x in m.group(1).split(",") if x.strip()}
            rows = [r for r in rows if r["soi_id"] in want]
        return rows
    if table == "sales_orders":
        return [{"so_id": k, "so_number": v[0], "customer": v[1],
                 "status": "CONFIRMED"} for k, v in ORDERS.items()]
    return []


@pytest.fixture()
def sched_db(monkeypatch):
    import db
    monkeypatch.setattr(db, "fetch", _fetch)
    monkeypatch.setattr(db, "fetch_one",
                        lambda t, f="", s="*": None)
    monkeypatch.setattr(db, "insert", lambda t, r: len(r))
    monkeypatch.setattr(db, "update", lambda t, f, v: True)
    monkeypatch.setattr(db, "health_check",
                        lambda: {"status": "OK", "counts": {}})
    monkeypatch.setattr(db, "debug_check", lambda: {"status": "mock"})
    if hasattr(db, "count_rows"):
        monkeypatch.setattr(db, "count_rows", lambda t, f="": 0)
    return db


def _open_schedule_tab(sched_db):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP_FILE, default_timeout=60)
    at.secrets["supabase"] = {"url": "https://mock.local",
                              "anon_key": "a", "service_role_key": "s"}
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    at.sidebar.radio[0].set_value("수주 관리")
    at.sidebar.radio[1].set_value(None)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def _gantt_html(at):
    for m in at.markdown:
        if 'class="gt"' in m.value:
            return m.value
    return None


# ─── 1. 그리드 구조 ────────────────────────────────────

def test_gantt_grid_is_eight_columns(sched_db):
    """헤더·본문·합계가 같은 grid 의 자식 → 열 수가 8의 배수여야 한다."""
    html = _gantt_html(_open_schedule_tab(sched_db))
    assert html, "간트 그리드가 렌더되지 않음"
    inner = html.split('<div class="gt">', 1)[1]
    depth, cells = 0, 0
    for tag in re.findall(r"<div\b|</div>", inner):
        if tag == "</div>":
            depth -= 1
            if depth < 0:      # .gt 닫힘
                break
        else:
            if depth == 0:
                cells += 1
            depth += 1
    assert cells % 8 == 0, f"grid 직계 자식 {cells}개 — 8열 배수가 아님"
    # 헤더 1행 + 품번 6행(미계획 전용 품번 제외) + 합계 1행
    assert cells == 8 * 8, f"예상 8행 × 8열, 실제 {cells}칸"


def test_gantt_header_marks_current_week(sched_db):
    html = _gantt_html(_open_schedule_tab(sched_db))
    assert html.count('class="gh now"') == 1, "이번 주 헤더 강조 1칸이어야 함"
    assert html.count('class="cell now"') == 6, "이번 주 본문 칸 = 품번 수"
    assert '<div class="gh">이후</div>' in html


# ─── 2. 회차 칩 ────────────────────────────────────────

def test_chip_classes_cover_all_states(sched_db):
    html = _gantt_html(_open_schedule_tab(sched_db))
    assert 'class="gc plan"' in html      # 예정 (분납)
    assert 'class="gc late"' in html      # 지연 (분납)
    assert 'class="gc one"' in html       # 단발 예정
    assert 'class="gc one late"' in html  # 단발 지연
    # 완료 회차는 기본 필터(완료 숨기기)로 제외
    assert 'class="gc done"' not in html


def test_overdue_chips_fold_into_current_week(sched_db):
    """지난 주 납기(sched 109)도 이번 주 칸에 붉은 칩으로 나타난다."""
    html = _gantt_html(_open_schedule_tab(sched_db))
    first_cell = html.split('<div class="cell now">')[1].split("</div></div>")[0]
    assert "gc late" in html
    assert "8PDVN-02" in html


# ─── 3. 계산값 ─────────────────────────────────────────

def test_plan_rate_thresholds(sched_db):
    """계획률 = 계획 합계 ÷ 미납 — 색 임계값까지 확인."""
    html = _gantt_html(_open_schedule_tab(sched_db))
    rates = re.findall(r'color:(#[0-9a-f]{6})">계획률 (\d+)%', html)
    by_color = {}
    for color, pct in rates:
        by_color.setdefault(color, set()).add(int(pct))
    # 4PDVN-02 5,040/91,648 = 5% · 8HFDV-VM-05 500/8,500 = 6% → 30% 미만
    assert by_color.get("#d9480f") == {5, 6}, rates
    # 4PDVN-03·8PDVN-02·단발 2건 = 100% → 70% 초과
    assert by_color.get("#2f9e44") == {100}, rates
    assert "#e8590c" not in by_color  # 30~70% 구간 데이터 없음


def test_week_totals_match_chip_sums(sched_db):
    """주 합계 행 = 각 칸 잔량의 합 (표시 품번 기준)."""
    html = _gantt_html(_open_schedule_tab(sched_db))
    sums = [int(s.replace(",", "")) for s in re.findall(
        r'<div class="gsum">([\d,]+)</div>', html)]
    # 이번 주(지연 포함) 2016+1400+1500 = 4916, +단발 79 = 4995
    assert sums[0] == 4995, sums
    # 2주 뒤: 1008+500+10(단발) = 1518
    assert sums[1] == 1518, sums
    # '이후' 열: 4800
    assert sums[-1] == 4800, sums
    assert sum(sums) == 4995 + 1518 + 3516 + 1400 + 4800


def test_unplanned_banner_and_metrics(sched_db):
    at = _open_schedule_tab(sched_db)
    banner = next((m.value for m in at.markdown
                   if 'class="unplan"' in m.value), None)
    assert banner, "미계획 배너가 없음"
    # 4S20AHYBV(54,288 전량) + 4PDVN-02(91,648-5,040) + 8HFDV(8,500-500)
    # + 8PDVN(3,000-3,000=0) + 4PDVN-03(7,600-7,600=0)
    assert "54,288" in banner or "4S20AHYBV-03-X1413" in banner
    kpi = next((m.value for m in at.markdown
                if 'class="kpi-row"' in m.value), None)
    assert kpi, "KPI 카드가 없음"
    assert "지연 회차" in kpi and "전체 잔여 계획" in kpi


# ─── 4. 뷰 전환 ────────────────────────────────────────

def test_view_toggle_defaults_to_gantt(sched_db):
    at = _open_schedule_tab(sched_db)
    assert at.session_state["sch_view"] == "회차 간트"


@pytest.mark.parametrize("view,want_gantt,min_df", [
    ("주차별 물량", False, 1),   # 주차 피벗 1개
    ("납기 입력", False, 1),     # 라인 현황 표
    ("회차 간트", True, 0),
])
def test_each_view_renders(sched_db, view, want_gantt, min_df):
    at = _open_schedule_tab(sched_db)
    at.session_state["sch_view"] = view
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert bool(_gantt_html(at)) is want_gantt
    assert len(at.dataframe) >= min_df
