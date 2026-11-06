# -*- coding: utf-8 -*-
"""투입 등록 품번 후보 순수 함수(utils/wo_input.py, 2026-11-06 재발 방지 소묶음 A).

A-T1~T3 은 대조군(이동 전 화면 동작과 같아야 한다), A-T4·T5 는 휴면 힌트.
"""
import os
import sys

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
