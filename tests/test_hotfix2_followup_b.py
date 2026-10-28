"""핫픽스 2 후속 B(2026-10-28) — 납품 스케줄 전체 회차 절단 시 지연 상세·간트 합계 미확인(r3 M1), '전체' vs
기간 선택의 판정 숫자 동일, 납기 입력 절단 시 중립 정렬·선택 라인 일치(r3 REQUIRED ①~③), 그리고 후속 A r2
리뷰의 REQUIRED T1~T3(병합 확인 UI 뒤 절단 전환, 단가 변동 감지 생략·이력 유지, 절단 중 제품 조치 유지).
"""
import importlib.util
import os
import re
import sys
from datetime import timedelta

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
streamlit_available = importlib.util.find_spec("streamlit") is not None
pytestmark = pytest.mark.skipif(not streamlit_available, reason="streamlit 미설치 — AppTest 불가")

from tests.test_hotfix2_fetch_all_sites import BIG, TODAY, _mock as _sch_mock, _open, _period  # noqa: E402


def _kpi_html(at):
    return next((str(x.value) for x in at.markdown
                 if 'class="kpi-row"' in str(x.value) and "지연 회차" in str(x.value)), "")


def _late_label(at):
    return next((str(x.label) for x in at.expander if str(x.label).startswith("지연 상세")), None)


def _plan_total_caption(at):
    return next((str(x.value) for x in at.caption if "전 품목 계획 합계" in str(x.value)), "")


def _plan_rates(at):
    from tests.test_delivery_schedule_gantt import _gantt_html
    return re.findall(r"계획률 (?:\d+%|미확인)", _gantt_html(at) or "")


# ── r3 REQUIRED ① — 전체 회차 절단(_sch_unk)이면 판정 숫자 전부 미확인 ─────────────────

def _big_with_old_late_round():
    """닫힌 회차 20,100(2026-01-01) + 그보다 앞선(정렬상 먼저 읽히는) 열린 지연 회차 1개(2025-12-01).
    맨 끝(최근) 대상 회차는 잘린다."""
    m = _sch_mock(target_due=(TODAY + timedelta(days=7)).isoformat(), target_qty=777, line_pending=777,
                  filler=BIG)
    m.tables["so_delivery_schedule"].insert(0, {
        "sched_id": 0, "so_id": 102, "soi_id": 601, "due_date": "2025-12-01", "seq": 9,
        "qty": 40, "delivered_qty": 0, "note": None})
    return m


@pytest.mark.parametrize("period", ["전체", "최근 3개월부터"])
def test_truncated_rounds_show_no_firm_totals(monkeypatch, period):
    m = _big_with_old_late_round()
    at = _open(monkeypatch, m, "so", "sched")
    if period != "전체":
        _period(at, period)
    kpi = _kpi_html(at)
    assert kpi.count('<div class="v">미확인</div>') == 4, kpi[:400]          # 4카드
    assert _late_label(at) == "지연 상세 — 조회된 일부 회차 (총계 미확인)", _late_label(at)
    assert not any("상단 KPI 도 같은 기준" in str(c.value) for c in at.caption)
    cap = _plan_total_caption(at)
    assert "전 품목 계획 합계 **미확인**" in cap, cap[:200]
    assert all(r == "계획률 미확인" for r in _plan_rates(at)), _plan_rates(at)
    assert not any('class="unplan"' in str(x.value) for x in at.markdown)  # 미계획 배너 없음


# ── r3 REQUIRED ② — 절단이 없으면 '전체'와 기간 선택의 판정 숫자가 같다 ─────────────

def test_period_and_all_give_same_judgement(monkeypatch):
    """같은 라인(미납 100)의 지난 지연 회차 30(기간 밖) + 다음 주 회차 50(기간 안)."""
    m = _sch_mock(target_due=(TODAY + timedelta(days=7)).isoformat(), target_qty=50, line_pending=100,
                  filler=5)
    m.tables["so_delivery_schedule"].append({
        "sched_id": 9001, "so_id": 102, "soi_id": 601, "due_date": (TODAY - timedelta(days=200)).isoformat(),
        "seq": 2, "qty": 30, "delivered_qty": 0, "note": None})
    at = _open(monkeypatch, m, "so", "sched")
    base = (_kpi_html(at), _late_label(at), _plan_rates(at), _plan_total_caption(at).split("—")[0])
    assert base[1] and base[1].startswith("지연 상세 1건 · 잔량 30"), base[1]
    assert "미확인" not in base[0]
    _period(at, "최근 3개월부터")
    got = (_kpi_html(at), _late_label(at), _plan_rates(at), _plan_total_caption(at).split("—")[0])
    assert got[0] == base[0] and got[1] == base[1] and got[2] == base[2], (base, got)
    # 하단 캡션의 '표시 품번 합계'는 표시 범위라 달라질 수 있고, '전 품목 계획 합계'는 같다
    assert base[3].split("· 전 품목")[1] == got[3].split("· 전 품목")[1], (base[3], got[3])


# ── r3 REQUIRED ③ — 납기 입력 절단: 복수 라인 중립 정렬 + 첫 행 외 선택 시 같은 라인 ─────────

def test_due_input_truncated_neutral_order_and_selection(monkeypatch):
    from tests.test_so_close import SEL
    m = _sch_mock(target_due=(TODAY + timedelta(days=30)).isoformat(), filler_soi=601, filler=BIG)
    # 두 번째 미납 라인 603(미납 55, 납기 601 보다 늦음) — 절단이면 '납기 미입력' 순 정렬을 하지 않는다
    m.tables["sales_order_items"].append(dict(
        next(i for i in m.tables["sales_order_items"] if i["soi_id"] == 601),
        soi_id=603, line_no=3, customer_part_no="CP-603", qty=55, received_qty=0, pending_qty=55,
        due_date="2026-12-20"))
    at = _open(monkeypatch, m, "so", "sched")
    at.session_state["sch_view"] = "납기 입력"
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    # 현황 표(toss_table HTML) — 절단이면 회차·입력 열 없이 라인 납기순 그대로(중립, '미입력' 순 정렬 안 함)
    stat = next(str(x.value) for x in at.markdown
                if "<table" in str(x.value) and "<th>수주번호</th>" in str(x.value))
    assert "<th>회차</th>" not in stat and "납기 미입력" not in stat, stat[:300]
    assert re.findall(r'<td class="r">([\d,]+)</td>', stat) == ["10", "55"], stat[:400]
    from tests.test_so_close import GRIDS
    assert list(GRIDS["sch_line_grid"]["미납"]) == [10.0, 55.0]         # 선택 그리드도 같은 순서
    monkeypatch.setitem(SEL, "sch_line_grid", 1)                       # 테스트 끝나면 원복
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    pend = next(mt.value for mt in at.metric if mt.label == "미납 (계획 대상)")
    assert pend == "55", pend                                           # 두 번째 행 = _all_items[1] = 603


# ════════ 후속 A r2 REQUIRED T1~T3 ════════

from tests.test_hotfix2_followup_a import (  # noqa: E402
    _force_truncated, _mock as _a_mock, _open as _a_open, _scan, _seed_materials, _seed_so_cards, _texts,
)


def test_t1_merge_confirm_open_then_truncated(monkeypatch):
    """T1: 완전 조회에서 병합 확인 UI 를 연 뒤 다음 실행이 절단이면 확인 UI 가 사라지고 쓰기 0건."""
    m = _a_mock()
    _seed_materials(m, dup_tail=True)
    at = _scan(_a_open(monkeypatch, m, "master"))
    go = next(b for b in at.button if str(b.key or "").startswith("mg_go_") and not b.disabled)
    go.click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert any(b.key == f"{go.key}_cfm_ok" for b in at.button), "확인 UI 가 열리지 않음"
    _force_truncated(monkeypatch, "materials")
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert not any(b.key == f"{go.key}_cfm_ok" for b in at.button), "절단 후에도 확인 UI 가 남음"
    assert ("cfm_" + go.key) not in at.session_state
    assert not m.writes, m.writes


def _count_detect(monkeypatch):
    import utils.so_replace as _sr
    calls = []
    real = _sr.detect_groups

    def _cnt(*a, **kw):
        calls.append(1)
        return real(*a, **kw)
    monkeypatch.setattr(_sr, "detect_groups", _cnt)
    return calls


def test_t2_products_truncated_skips_detection(monkeypatch):
    """T2: products 만 절단 → 제품 확인 '(일부 미확인)', 단가 변경 카드 없음, detect_groups 호출 0건."""
    calls = _count_detect(monkeypatch)
    m = _a_mock()
    _seed_so_cards(m)
    _force_truncated(monkeypatch, "products")
    at = _a_open(monkeypatch, m, "so", "input")
    labels = [str(x.label) for x in at.expander]
    assert any(l.startswith("제품 확인 필요(일부 미확인)") for l in labels), labels
    assert not any(l.startswith("단가 변경") for l in labels), labels
    assert calls == [], calls
    assert "단가 변동 감지 미확인" in _texts(at)


def test_t2_cards_then_truncated_and_history_kept(monkeypatch):
    """T2: 완전 조회에서 단가 변경 카드가 보이던 화면이 다음 실행에서 절단되면 카드·버튼이 사라지고, 결정 이력
    (수주 목록의 '대체·별건 결정 이력')은 그대로 보인다."""
    calls = _count_detect(monkeypatch)
    m = _a_mock()
    _seed_so_cards(m)
    m.tables["so_line_replacements"] = [{
        "repl_id": 1, "old_soi_id": 911, "new_soi_id": 912, "action": "KEEP", "old_price": 100,
        "new_price": 120, "closed_pending_qty": 0, "closed_rounds": None, "moved_rounds": None,
        "master_updated": False, "master_old_price": None, "old_so_status": None, "old_line_status": None,
        "created_by": "테스트", "created_at": "2026-10-27T01:00:00+00:00", "reverted_at": None,
        "tagged_soi_id": 912, "tagged_kind": "KEEP"}]
    # 결정 이력이 있으면 911→912 는 다시 묻지 않는다 → 감지 대상이 되도록 새 라인 914(130원) 추가
    m.seed(so_id=404, so_status="CONFIRMED", lines=[(914, 10, 0, 10, "PENDING")], pn="RP-PN", product_id="PRP")
    for it in m.tables["sales_order_items"]:
        if it["soi_id"] == 914:
            it["unit_price"] = 130
    at = _a_open(monkeypatch, m, "so", "list")
    assert any(str(x.label).startswith("단가 변경") for x in at.expander), [x.label for x in at.expander]
    assert any(str(x.label).startswith("대체·별건 결정 이력 1건") for x in at.expander)
    n = len(calls)
    assert n >= 1
    _force_truncated(monkeypatch, "sales_order_items")
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    labels = [str(x.label) for x in at.expander]
    assert not any(l.startswith("단가 변경") for l in labels), labels
    assert not any(str(b.key or "").startswith("rp_9") for b in at.button)
    assert any(l.startswith("대체·별건 결정 이력 1건") for l in labels), labels
    assert any(b.key == "rp_rv_1" for b in at.button)                    # 되돌리기는 그대로
    assert len(calls) == n, calls                                       # 절단 실행에서는 감지 안 함
    assert not [w for w in m.writes if w[1] == "so_line_replacements"]


def _allow_product_writes(m):
    from tests import so_mock as _sm
    m.tables.setdefault("master_change_log", [])
    m.tables.setdefault("customer_part_mapping", [])
    allowed = set(_sm.WRITABLE) | {"products", "master_change_log", "customer_part_mapping"}

    def _guard(op, table):
        if table not in allowed:
            raise AssertionError(f"허용되지 않은 쓰기 ({op} {table})")
    m._assert_dash = _guard


def test_t3_dormant_activation_kept_when_truncated(monkeypatch):
    """T3: 절단 중에도 휴면 제품 '활성화하고 진행'은 유지(제품 단위 결정) — products update 1건."""
    m = _a_mock()
    m.seed(so_id=501, so_status="CONFIRMED", lines=[(921, 10, 0, 10, "PENDING")], pn="DORM-PN",
           product_id="PDORM")
    next(p for p in m.tables["products"] if p["product_id"] == "PDORM")["archived_at"] = "2026-09-01"
    _allow_product_writes(m)
    _force_truncated(monkeypatch, "sales_order_items")
    at = _a_open(monkeypatch, m, "so", "input")
    assert "· 미납 미확인 ·" in _texts(at)
    act = next(b for b in at.button if str(b.key or "").endswith("_act"))
    act.click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    ups = [w for w in m.writes if w[0] == "update" and w[1] == "products"]
    assert len(ups) == 1, m.writes
    assert next(p for p in m.tables["products"] if p["product_id"] == "PDORM")["archived_at"] is None


def test_t3_register_duplicate_pn_blocked_when_truncated(monkeypatch):
    """T3: 절단 중 미등록 '등록하고 진행'도 유지되지만, 같은 pn 이 서버에 이미 있으면(단건 fetch_one) insert 0건."""
    m = _a_mock()
    _seed_so_cards(m)                                   # 913 = 미등록 라인(제안 품번 CP-913)
    m.tables["products"].append({"product_id": "P7777", "pn": "CP-913", "archived_at": None,
                                 "archive_reason": None, "sale_price": 1, "customer": "X",
                                 "item_name": "-", "material": "-"})
    _allow_product_writes(m)
    _force_truncated(monkeypatch, "sales_order_items")
    at = _a_open(monkeypatch, m, "so", "input")
    next(t for t in at.text_input if t.label == "품번 *").set_value("CP-913")
    sub = next(b for b in at.button if "등록하고 진행" in str(b.label))
    sub.click()
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert any("이미 있습니다" in str(e.value) for e in at.error), [str(e.value) for e in at.error]
    assert not [w for w in m.writes if w[0] == "insert" and w[1] == "products"], m.writes
