# -*- coding: utf-8 -*-
"""투입 등록 품번 후보 순수 함수(utils/wo_input.py, 2026-11-06 재발 방지 소묶음 A).

A-T1~T3 은 대조군(이동 전 화면 동작과 같아야 한다), A-T4·T5 는 휴면 힌트.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.wo_input import pn_candidates  # noqa: E402

BOM3 = [{"product_id": "P3", "pn": "C-300"},
        {"product_id": "P1", "pn": "A-100"},
        {"product_id": "P2", "pn": "B-200"}]


def test_a_t1_no_hint_open_first():
    """힌트 없음, BOM 후보 3개 중 1개 미납 → 미납 품번이 첫 항목·기본 0·미납 라벨."""
    r = pn_candidates(BOM3, {"P2": 1500})
    assert [c["pn"] for c in r["cands"]] == ["B-200", "A-100", "C-300"]
    assert r["default"] == 0
    assert r["labels"] == ["B-200 ← 미납 1,500", "A-100", "C-300"]
    assert r["notice"] is None


def test_a_t2_active_hint_inside_bom():
    """활성 힌트가 BOM 후보 안(둘째) → 순서 그대로, 기본 = 힌트 위치, 「(발주 라인 기준)」 라벨."""
    r = pn_candidates(BOM3, {"P2": 1500}, {"pn": "A-100", "src": "발주 라인", "product_id": "P1"})
    assert [c["pn"] for c in r["cands"]] == ["B-200", "A-100", "C-300"]
    assert r["default"] == 1
    assert r["labels"][1] == "A-100 (발주 라인 기준)"
    assert r["notice"] is None


def test_a_t3_active_hint_outside_bom():
    """활성 힌트가 BOM 후보에 없음 → 맨 앞에 추가, 기본 0."""
    r = pn_candidates(BOM3, {}, {"pn": "Z-900", "src": "발주 라인", "product_id": "P9"})
    assert r["cands"][0] == {"pn": "Z-900", "product_id": "P9"}
    assert [c["pn"] for c in r["cands"][1:]] == ["A-100", "B-200", "C-300"]
    assert r["default"] == 0
    assert r["labels"][0] == "Z-900 (발주 라인 기준)"


def test_a_t3b_open_label_on_hint_and_open_pids_override():
    """미납 라벨과 힌트 라벨이 함께 붙는다 · open_pids 를 주면 그것만 미납으로 본다(화면 예외 경로 보존)."""
    r = pn_candidates(BOM3, {"P1": 10}, {"pn": "A-100", "src": "발주 라인", "product_id": "P1"})
    assert r["labels"][0] == "A-100 ← 미납 10 (발주 라인 기준)" and r["default"] == 0
    r2 = pn_candidates(BOM3, {"P1": 10}, None, open_pids=set())
    assert r2["labels"] == ["A-100", "B-200", "C-300"]


# ── 휴면 힌트(후보 49, 2026-11-05 운영 발견: 휴면 처리한 HA80-80092 가 투입 후보 맨 앞·기본값) ──
NOTICE_92 = ("발주 라인의 품번 HA80-80092 은 휴면 처리된 품번이라 후보에서 뺐습니다 — "
             "작업지시서 품번을 확인하세요.")
HINT_92 = {"pn": "HA80-80092", "src": "발주 라인", "product_id": "P0738", "archived": True}


def test_a_t4_archived_hint_dropped_bom_default():
    """휴면 힌트 + BOM 후보 1개 → 후보에 휴면 품번 없음, 기본 = BOM 후보, 안내 문구."""
    r = pn_candidates([{"product_id": "P0883", "pn": "HA80-80093"}], {"P0883": 500}, dict(HINT_92))
    assert [c["pn"] for c in r["cands"]] == ["HA80-80093"]
    assert r["default"] == 0
    assert r["labels"] == ["HA80-80093 ← 미납 500"]          # 「발주 라인 기준」 라벨 없음
    assert r["notice"] == NOTICE_92


def test_a_t5_archived_hint_no_bom_is_empty():
    """휴면 힌트 + BOM 후보 0개 → 후보 빈 목록(화면은 직접 입력), 안내 문구."""
    r = pn_candidates([], {}, dict(HINT_92))
    assert r["cands"] == [] and r["labels"] == []
    assert r["notice"] == NOTICE_92


# ── r2 D-1·D-2 · r2b D-3: 앞서 고른 선택 판정(선택 상자를 만들기 전 세션의 옛 라벨 + 직전 run 의 「라벨 → 품번」 표) ──
def _pv(prev, cands, labels, prev_map=None, lot=None):
    from utils.wo_input import prev_selection      # 함수 안 import — 수정 전 코드에서도 이 파일의 다른 테스트는 돈다
    try:
        return prev_selection(prev, cands, labels, prev_map, lot=lot)
    except TypeError:                               # 02a 재현용: r2(be25433)의 3인자 판정(라벨 꼬리 역산)으로 호출
        return prev_selection(prev, cands, labels)


def _tbl(lot, labels, pns):
    return {"lot": lot, "map": dict(zip(labels, pns))}


C2 = [{"pn": "HA80-80093", "product_id": "P0883"}, {"pn": "HA80-80099", "product_id": "P0999"}]
L_OLD = ["HA80-80093 ← 미납 500", "HA80-80099 ← 미납 300"]
T_OLD = _tbl("W1", L_OLD, ["HA80-80093", "HA80-80099"])


def test_prev_none():
    assert _pv(None, C2, ["HA80-80093 ← 미납 500", "HA80-80099"], T_OLD, "W1") == \
        {"state": "none", "pn": None, "index": None}


def test_prev_same():
    r = _pv("HA80-80099 ← 미납 300", C2, L_OLD, T_OLD, "W1")
    assert r == {"state": "same", "pn": "HA80-80099", "index": 1}, r


def test_prev_relabel_new_position():
    r = _pv("HA80-80099 ← 미납 300", C2, ["HA80-80093 ← 미납 500", "HA80-80099 ← 미납 200"], T_OLD, "W1")
    assert r == {"state": "relabel", "pn": "HA80-80099", "index": 1}, r
    t = _tbl("W1", ["HA80-80093 (발주 라인 기준)", "HA80-80099"], ["HA80-80093", "HA80-80099"])
    r = _pv("HA80-80093 (발주 라인 기준)", list(reversed(C2)), ["HA80-80099 ← 미납 5", "HA80-80093"], t, "W1")
    assert r == {"state": "relabel", "pn": "HA80-80093", "index": 1}, r


def test_prev_gone():
    t = _tbl("W1", ["HA80-80093 ← 미납 500", "HA80-80092 (발주 라인 기준)"], ["HA80-80093", "HA80-80092"])
    r = _pv("HA80-80092 (발주 라인 기준)", C2[:1], ["HA80-80093 ← 미납 500"], t, "W1")
    assert r == {"state": "gone", "pn": None, "index": None}, r
    r = _pv("HA80-80092 (발주 라인 기준)", [], [], t, "W1")      # 후보 0개 → 직접 입력 칸
    assert r["state"] == "gone", r


# ── D-3: 품번 자체가 표시 꼬리로 끝나는 경우(Codex r2 HIGH) — be25433 에서 실패해야 한다(02a) ──
XT = [{"pn": "HB10-100", "product_id": "PX"}, {"pn": "HB10-100 (발주 라인 기준)", "product_id": "PT"}]
XA = [{"pn": "HB10-100", "product_id": "PX"}, {"pn": "HB10-100 ← 미납 5", "product_id": "PA"}]


def test_d3_tail_src_pn_relabel_to_itself():
    """후보 X·「X (발주 라인 기준)」(실제 품번), 뒤쪽 선택, 그 품번 미납 0 → 200 → relabel 위치 = 뒤쪽(X 아님)."""
    old = ["HB10-100 ← 미납 500", "HB10-100 (발주 라인 기준)"]
    new = ["HB10-100 ← 미납 500", "HB10-100 (발주 라인 기준) ← 미납 200"]
    r = _pv(old[1], XT, new, _tbl("W8", old, [c["pn"] for c in XT]), "W8")
    assert r == {"state": "relabel", "pn": "HB10-100 (발주 라인 기준)", "index": 1}, r


def test_d3_tail_open_pn_relabel_to_itself():
    """후보 X·「X ← 미납 5」(실제 품번), 뒤쪽 선택(미납 0), 미납 0 → 양수 → relabel 위치 = 뒤쪽."""
    old = ["HB10-100 ← 미납 500", "HB10-100 ← 미납 5"]
    new = ["HB10-100 ← 미납 500", "HB10-100 ← 미납 5 ← 미납 30"]
    r = _pv(old[1], XA, new, _tbl("W8", old, [c["pn"] for c in XA]), "W8")
    assert r == {"state": "relabel", "pn": "HB10-100 ← 미납 5", "index": 1}, r


def test_d3_tail_pn_gone_is_not_relabelled_to_short_pn():
    """꼬리 품번이 후보에서 빠지고 X 만 남음 → gone(X 로 relabel 되지 않음)."""
    old = ["HB10-100", "HB10-100 (발주 라인 기준)"]
    r = _pv(old[1], XT[:1], ["HB10-100"], _tbl("W8", old, [c["pn"] for c in XT]), "W8")
    assert r == {"state": "gone", "pn": None, "index": None}, r


@pytest.mark.parametrize("case", ["no_table", "other_lot", "label_not_in_table"])
def test_d3_missing_or_foreign_table_is_gone(case):
    """표 없음 / 다른 LOT 의 표 / 옛 라벨이 표에 없음 → gone(fail-closed)."""
    new = ["HA80-80093 ← 미납 500", "HA80-80099 ← 미납 200"]
    if case == "no_table":
        r = _pv("HA80-80099 ← 미납 300", C2, new, None, "W1")
    elif case == "other_lot":
        r = _pv("HA80-80099 ← 미납 300", C2, new, T_OLD, "W2")
    else:
        r = _pv("HA80-80099 ← 미납 999", C2, new, T_OLD, "W1")
    assert r == {"state": "gone", "pn": None, "index": None}, r


def test_d3_same_label_now_other_pn_is_gone():
    """같은 라벨 문자열이 직전과 다른 품번을 가리키면(이론상 꼬리 품번 충돌) 같음으로 보지 않고 gone."""
    t = _tbl("W8", ["HB10-100 (발주 라인 기준)"], ["HB10-100 (발주 라인 기준)"])
    r = _pv("HB10-100 (발주 라인 기준)", XT[:1], ["HB10-100 (발주 라인 기준)"], t, "W8")
    assert r["state"] == "gone", r
