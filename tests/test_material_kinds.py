"""
마스터 관리 › 자재 편집 — 구분별(소재 M / 소모품·포장재 C / 공구 T) 관리 (2026-09-22)

소모품·공구는 소재처럼 재질·조달·재고가 아니라 자재명·규격·구분·주공급사만
다룬다. 구분 라디오를 바꾸면 그 접두어의 자재만 조회하고 표·상세·신규 등록
폼이 그 구성으로 바뀌어야 한다. DB 는 mock.
"""
import sys, os
import importlib.util
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

streamlit_available = importlib.util.find_spec("streamlit") is not None
pytestmark = pytest.mark.skipif(
    not streamlit_available, reason="streamlit 미설치 — AppTest 불가")

APP_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "streamlit_app.py")

MATS = [
    {"material_id": "M003", "raw_name": "20AHYBV-X1413", "material_type": None,
     "spec": "주물소재", "unit": "EA", "stock_qty": 0, "main_supplier": "디와이모터스",
     "procurement_type": "도급"},
    {"material_id": "C002", "raw_name": "절삭유", "material_type": "소모품",
     "spec": "20L", "unit": "EA", "stock_qty": 0, "main_supplier": "삼경O&T",
     "procurement_type": None},
    {"material_id": "T001", "raw_name": "INSERT TIP VBMT 160404HQ PR1125",
     "material_type": "공구", "spec": None, "unit": "EA", "stock_qty": 0,
     "main_supplier": "두리T.M.S", "procurement_type": None},
]
CALLS = []


def _mock_fetch(table, select="*", filter_query="", limit=1000):
    if table == "materials":
        CALLS.append(filter_query)
        for pre in ("M", "C", "T"):
            if f"material_id=like.{pre}*" in filter_query:
                return [m for m in MATS if m["material_id"].startswith(pre)]
        return list(MATS)
    return []


@pytest.fixture()
def mocked_db(monkeypatch):
    import db
    monkeypatch.setattr(db, "fetch", _mock_fetch)
    monkeypatch.setattr(db, "fetch_one", lambda *a, **k: None)
    monkeypatch.setattr(db, "insert", lambda t, r: len(r))
    monkeypatch.setattr(db, "update", lambda *a, **k: True)
    monkeypatch.setattr(db, "health_check", lambda: {"status": "OK", "counts": {}})
    monkeypatch.setattr(db, "debug_check", lambda: {"url": "mock", "status": "mock"})
    if hasattr(db, "count_rows"):
        monkeypatch.setattr(db, "count_rows", lambda *a, **k: 0)
    if hasattr(db, "rpc"):
        monkeypatch.setattr(db, "rpc", lambda *a, **k: None)
    CALLS.clear()
    return db


def _open_master():
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    for _c in (st.cache_data, st.cache_resource):
        try:
            _c.clear()
        except Exception:
            pass
    at = AppTest.from_file(APP_FILE, default_timeout=30)
    at.secrets["supabase"] = {"url": "https://mock.supabase.local",
                              "anon_key": "mock_anon",
                              "service_role_key": "mock_service"}
    at.secrets["auth"] = {"disabled": True}
    at.run()
    at.sidebar.radio[1].set_value("마스터 관리")
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def _kind_radio(at):
    r = [x for x in at.radio if x.key == "mat_kind"]
    assert r, "자재 구분 라디오(mat_kind) 없음"
    return r[0]


def _grid_text(at):
    return "\n".join(f.value.to_string() for f in at.dataframe)


def test_default_is_stock_materials(mocked_db):
    """기본 '소재' — M 자재만 조회, 표에 재질·재고·조달 열."""
    at = _open_master()
    assert _kind_radio(at).value == "소재"
    assert any("material_id=like.M*" in c for c in CALLS)
    # AppTest 가 노출하는 표는 일괄 편집 data_editor(원본 컬럼명) — 행 구성만 검증
    txt = _grid_text(at)
    assert "M003" in txt and "C002" not in txt and "T001" not in txt
    # 소재 상세 편집 폼 — 재질 text_input · 조달 selectbox 있음
    assert any(t.key == "md_ty_M003" for t in at.text_input)
    assert any(s.key == "md_pr_M003" for s in at.selectbox)


def test_tools_view_shows_only_T_with_simple_columns(mocked_db):
    """'공구' — T 자재만, 표는 구분·자재명·규격·주공급사 (재질·재고·조달 없음)."""
    at = _open_master()
    _kind_radio(at).set_value("공구")
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert any("material_id=like.T*" in c for c in CALLS)
    txt = _grid_text(at)
    assert "T001" in txt and "M003" not in txt and "C002" not in txt
    assert "공구" in txt
    # 상세 편집 폼 — 재질·조달 입력 없음, 구분 selectbox 는 공구 고정
    keys = {t.key for t in at.text_input}
    assert "md_nm_T001" in keys and "md_sp_T001" in keys
    assert "md_ty_T001" not in keys, "비생산 자재는 재질 text_input 이 없어야 함"
    sel = [s for s in at.selectbox if s.key == "md_ty_T001"]
    assert sel and sel[0].options == ["공구"]
    assert not any(s.key == "md_pr_T001" for s in at.selectbox)
    assert "md_un_T001" in keys, "비생산 자재 상세 편집에 단위 입력이 있어야 함"
    # 신규 등록 폼 — 공구용 (자재명·규격·구분·단위·주공급사)
    assert "nm_name_T" in keys and "nm_spec_T" in keys and "nm_sup_T" in keys
    assert "nm_unit_T" in keys, "공구 등록 폼에 단위 입력이 있어야 함"
    assert "nm_type" not in keys, "공구 등록 폼에 재질 입력이 있으면 안 됨"


def test_consumables_view_has_kind_filter(mocked_db):
    """'소모품·포장재' — C 자재만, 구분 필터(전체/소모품/포장재)."""
    at = _open_master()
    _kind_radio(at).set_value("소모품·포장재")
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert any("material_id=like.C*" in c for c in CALLS)
    txt = _grid_text(at)
    assert "C002" in txt and "T001" not in txt
    f = [s for s in at.selectbox if s.key == "mat_f_kind"]
    assert f and f[0].options == ["전체", "소모품", "포장재"]
    sel = [s for s in at.selectbox if s.key == "md_ty_C002"]
    assert sel and sel[0].options == ["소모품", "포장재"] and sel[0].value == "소모품"
