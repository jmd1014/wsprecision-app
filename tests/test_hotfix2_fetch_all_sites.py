"""핫픽스 2(2026-10-27) — so_delivery_schedule 를 넓게 읽는 6곳이 PostgREST 요청당 1,000행 상한을 넘어
끝까지 읽는지(db.fetch_all) 회귀 AppTest.

목 DB(SOMock)에 server_max=1000(요청당 1,000행)을 걸고, 닫힌 회차 2,500행 뒤(맨 끝)에 대상 회차를 둔다.
예전 코드(fetch limit 1000/2000 한 번)는 대상 회차를 못 읽는다.
"""
import importlib.util
import os
import re
import sys
from datetime import date, timedelta

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
APP_FILE = os.path.join(ROOT, "streamlit_app.py")
streamlit_available = importlib.util.find_spec("streamlit") is not None
pytestmark = pytest.mark.skipif(not streamlit_available, reason="streamlit 미설치 — AppTest 불가")

FILLER = 2500
TODAY = date.today()


def _mock(target_due, target_qty=10, target_delivered=0, line_due="2026-10-20", line_pending=10,
          tail_pn="TAIL-PN-01", filler_soi=602, filler=FILLER):
    """SO 102: 대상 라인 601 + 다 납품된 라인 602. 닫힌 회차 2,500(기본 602, filler_soi=601 이면 대상
    라인 자신) 뒤 맨 끝에 대상 라인 601 의 회차 1개."""
    from tests.so_mock import SOMock
    m = SOMock()
    m.server_max = 1000
    m.sort_orders = True          # order= 적용(PostgREST 동일) — r2 L1
    m.seed(so_id=102, so_status="CONFIRMED",
           lines=[(601, target_qty, 0, line_pending, "PENDING"), (602, filler, filler, 0, "DELIVERED")],
           pn=tail_pn, product_id="P601")
    for it in m.tables["sales_order_items"]:
        if it["soi_id"] == 601:
            it["due_date"] = line_due
    m.tables["so_delivery_schedule"] = [
        {"sched_id": i + 1, "so_id": 102, "soi_id": filler_soi, "due_date": "2026-01-01", "seq": i + 1,
         "qty": 1, "delivered_qty": 1, "note": None} for i in range(filler)]
    m.tables["so_delivery_schedule"].append(
        {"sched_id": filler + 500, "so_id": 102, "soi_id": 601, "due_date": target_due, "seq": 1,
         "qty": target_qty, "delivered_qty": target_delivered, "note": None})
    return m


def _open(monkeypatch, m, main, sub=None):
    import db as _dbmod
    from streamlit.testing.v1 import AppTest
    from tests.conftest import goto
    from tests.test_so_close import _hook_aggrid, GRIDS
    GRIDS.clear()
    _hook_aggrid(monkeypatch)
    m.install(monkeypatch, _dbmod)
    at = AppTest.from_file(APP_FILE, default_timeout=120)
    at.secrets["supabase"] = {"url": "https://mock.local", "anon_key": "a", "service_role_key": "s"}
    at.secrets["auth"] = {"disabled": True}
    at.run()
    goto(at, main, sub)
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def _late_value(at):
    for mk in at.markdown:
        hit = re.search(r'<span class="k">납기 지연</span><span class="v[^"]*">([^<]+)</span>', str(mk.value or ""))
        if hit:
            return hit.group(1)
    return None


def _sched_reads(m):
    return [fq for t, fq in m.fetch_calls if t == "so_delivery_schedule"]


def test_so_kpi_sched_soi_all_reads_past_1000(monkeypatch):
    """① 수주 KPI `_sched_soi_all`: 회차가 맨 끝에 있는 라인을 '회차 없음'으로 오판해 지연을 세지 않는다."""
    m = _mock(target_due=(TODAY + timedelta(days=60)).isoformat())     # 미래 회차 — 지연 아님
    at = _open(monkeypatch, m, "so", "input")
    assert _late_value(at) == "0건", _late_value(at)                   # 예전: 라인 경로로 1건
    assert any("offset=2000" in fq for fq in _sched_reads(m))


def test_so_kpi_late_rounds_read_past_1000(monkeypatch):
    """② 수주 KPI 납기 지연: 지난 회차 2,501행 중 맨 끝의 열린 지연 회차까지 센다."""
    # 라인 납기는 미래 → 라인 경로로는 지연이 아니다. 지연은 맨 끝 회차(2026-01-02, 열림)로만 생긴다
    m = _mock(target_due="2026-01-02", line_due=(TODAY + timedelta(days=60)).isoformat())
    at = _open(monkeypatch, m, "so", "input")
    assert _late_value(at) == "1건", _late_value(at)                   # 예전: 1,000행에서 잘려 0건


def test_schedule_gantt_shows_round_past_1000(monkeypatch):
    """③ 납품 스케줄 전체: 최근 납기 회차(맨 끝)가 간트 칩으로 보인다."""
    from tests.test_delivery_schedule_gantt import _gantt_html
    m = _mock(target_due=(TODAY + timedelta(days=7)).isoformat(), target_qty=777, line_pending=777)
    m.tables["so_delivery_schedule"][-1]["qty"] = 333      # 회차 333(분납) ≠ 라인 미납 777(단발이면 777 칩)
    at = _open(monkeypatch, m, "so", "sched")
    html = _gantt_html(at) or ""
    assert "TAIL-PN-01" in html and '<span class="gq">333</span>' in html, html[:400]
    # 회차를 읽었으면 미계획은 나머지 444(=777−333) — 예전에는 회차가 잘려 777 전량 미계획
    banner = next((str(x.value) for x in at.markdown if 'class="unplan"' in str(x.value)), "")
    assert "TAIL-PN-01 777" not in banner, banner[:300]
    assert not any("일부만 표시" in str(w.value) for w in at.warning)


def test_home_kpi_next_due_from_round_past_1000(monkeypatch):
    """④ 홈: 수주별 열린 회차 납기(so_id=in)가 맨 끝 회차까지 읽혀 다음 납기로 쓰인다.
    r2 L1: 1,000행 뒤 열린 회차 2개를 납기 역순(D-10 먼저 저장, D-3 나중)으로 둔다 — 가장 이른 D-3 이어야."""
    m = _mock(target_due=(TODAY + timedelta(days=10)).isoformat(), target_qty=5)   # 라인 납기는 지난 2026-10-20
    m.tables["so_delivery_schedule"].append(
        {"sched_id": FILLER + 600, "so_id": 102, "soi_id": 601, "due_date": (TODAY + timedelta(days=3)).isoformat(),
         "seq": 2, "qty": 5, "delivered_qty": 0, "note": None})
    at = _open(monkeypatch, m, "home")
    reads = [fq for fq in _sched_reads(m) if "so_id=in." in fq]
    assert reads and any("offset=2000" in fq for fq in reads), reads
    texts = [str(x.value) for x in at.markdown] + [d.value.to_string() for d in at.dataframe]
    from tests.test_so_close import _grid_text
    texts.append(_grid_text())
    assert any("D-3" in t for t in texts), "다음 납기 = 가장 이른 열린 회차(D-3) — 예전: 라인 납기로 '지연 n일'"
    assert not any("D-10" in t for t in texts)                    # 저장 순서(D-10 먼저)가 아니라 납기순
    assert not any("회차 일부 미확인" in str(x.value) for x in at.markdown)


def test_schedule_due_input_round_count_past_1000(monkeypatch):
    """⑤ 납품 스케줄 › 납기 입력 회차 집계(soi_id=in): 미납 라인 601 의 회차 2,501개를 끝까지 센다."""
    m = _mock(target_due=(TODAY + timedelta(days=30)).isoformat(), filler_soi=601)
    at = _open(monkeypatch, m, "so", "sched")
    at.session_state["sch_view"] = "납기 입력"
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    reads = [fq for fq in _sched_reads(m) if "soi_id=in.(601)" in fq]
    assert reads and any("offset=2000" in fq for fq in reads), reads
    from tests.test_so_close import _grid_text
    texts = [d.value.to_string() for d in at.dataframe] + [_grid_text()] + [str(x.value) for x in at.markdown]
    assert any("2501" in t or "2,501" in t for t in texts)          # 예전: 1,000


def test_plan_board_rounds_past_1000(monkeypatch):
    """⑥ 생산 계획 설비 스케줄: 라인 묶음(soi_id=in) 회차를 끝까지 읽어 큐 계산에 넘긴다."""
    import utils.schedule as _sch_mod
    seen = {}
    real = _sch_mod.build_queue

    def _spy(lines, rounds, *a, **k):
        seen["rounds"] = list(rounds)
        return real(lines, rounds, *a, **k)
    monkeypatch.setattr(_sch_mod, "build_queue", _spy)
    _due = (TODAY + timedelta(days=14)).isoformat()
    m = _mock(target_due=_due, filler_soi=601)          # 미납 라인 601 자신에 회차 2,501개
    _open(monkeypatch, m, "plan", "sb")
    reads = [fq for fq in _sched_reads(m) if "soi_id=in." in fq]
    assert reads and any("offset=2000" in fq for fq in reads), reads     # r2 L1: 조건부 skip 제거
    got = seen.get("rounds", [])
    assert any(r.get("soi_id") == 601 and str(r.get("due_date")) == _due for r in got), len(got)


def test_static_sites_use_fetch_all():
    src = open(APP_FILE, encoding="utf-8").read()
    assert '"so_delivery_schedule", "soi_id", "", limit=2000' not in src
    assert '"order=due_date.asc", limit=2000)' not in src
    for frag in ('fetch_all("so_delivery_schedule", "soi_id", "")',
                 'f"so_id=in.({_ids})", order="due_date.asc,seq.asc")\n',
                 '"회차가 2만 행을 넘어 뒤쪽(최근 납기)은 표시되지 않습니다',
                 '"미확인" if _sk_late_unk'):
        assert frag in src, frag
    # r2 M2: so_delivery_schedule fetch_all 결과에서 truncated 를 버리는([0]) 곳이 없어야
    assert not re.search(r'fetch_all\("so_delivery_schedule"[^)]*\)\)?\[0\]', src)


# ── r2: 안전 상한(2만 행) 초과 — truncated 처리(M1·M2, REQUIRED) ──
BIG = 20100


def test_so_kpi_late_unknown_when_over_20000(monkeypatch):
    m = _mock(target_due="2026-01-02", line_due=(TODAY + timedelta(days=60)).isoformat(), filler=BIG)
    at = _open(monkeypatch, m, "so", "input")
    assert _late_value(at) == "미확인", _late_value(at)


def test_schedule_warns_over_20000_and_period_filter_recovers(monkeypatch):
    from tests.test_delivery_schedule_gantt import _gantt_html
    m = _mock(target_due=(TODAY + timedelta(days=7)).isoformat(), target_qty=777, line_pending=777, filler=BIG)
    m.tables["so_delivery_schedule"][-1]["qty"] = 333      # 회차 333 ≠ 라인 미납 777(회차를 못 읽으면 단발 777 칩)
    at = _open(monkeypatch, m, "so", "sched")
    assert any("2만 행을 넘어" in str(w.value) for w in at.warning), [str(w.value) for w in at.warning]
    assert '<span class="gq">333</span>' not in (_gantt_html(at) or "")   # 맨 끝(최근) 회차가 잘렸다
    # 복구: 회차 기간(서버 조건 due_date=gte) — 지난 회차 2만 행이 서버에서 빠진다
    m.fetch_calls.clear()
    at.selectbox(key="sch_period").set_value("최근 3개월부터").run()
    assert not at.exception, [str(e.value) for e in at.exception]
    since = (TODAY - timedelta(days=91)).isoformat()
    assert any(fq.startswith(f"due_date=gte.{since}&") for fq in _sched_reads(m)), _sched_reads(m)[:3]
    assert not any("2만 행을 넘어" in str(w.value) for w in at.warning)
    assert '<span class="gq">333</span>' in (_gantt_html(at) or "")


def test_home_note_when_rounds_over_20000(monkeypatch):
    m = _mock(target_due=(TODAY + timedelta(days=3)).isoformat(), filler=BIG)
    at = _open(monkeypatch, m, "home")
    assert any("회차 일부 미확인" in str(x.value) for x in at.markdown)


def test_due_input_hides_counts_when_over_20000(monkeypatch):
    m = _mock(target_due=(TODAY + timedelta(days=30)).isoformat(), filler_soi=601, filler=BIG)
    at = _open(monkeypatch, m, "so", "sched")
    at.session_state["sch_view"] = "납기 입력"
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert any("일부만 집계" in str(w.value) for w in at.warning), [str(w.value) for w in at.warning]
    vals = {mt.label: mt.value for mt in at.metric}
    assert vals.get("납기 입력됨") == "미확인" and vals.get("납기 미입력") == "미확인", vals
    for d in at.dataframe:
        assert "납기 미입력" not in list(d.value.columns), list(d.value.columns)


def test_plan_board_warns_when_rounds_over_20000(monkeypatch):
    m = _mock(target_due=(TODAY + timedelta(days=14)).isoformat(), filler_soi=601, filler=BIG)
    at = _open(monkeypatch, m, "plan", "sb")
    assert any("일부 회차를 읽지 못했습니다" in str(w.value) for w in at.warning), [str(w.value) for w in at.warning]
