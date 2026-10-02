"""
수주 관리 › 파일 업로드 — DIC 납품예정서등록 엑셀 (2026-10-02)

한 파일에 두 공장(= 거래처 2곳)이 섞여 있고 단가 열이 없다. 미납 조회 화면이라
같은 수주가 매번 다시 나오므로:
- 새 수주는 (거래처, 수주번호) 로 묶어 등록, 거래처별 vendor_id
- 이미 있는 수주의 새 행번은 그 수주에 라인만 추가
- 이미 있는 라인은 건드리지 않는다 (납품량은 앱 출고 확정으로만)
- 단가는 제품 마스터 판매단가로 채움, 수량은 미납품량
DB 는 mock.
"""
import io
import os
import sys
import importlib.util
from urllib.parse import unquote

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.dirname(__file__))

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("streamlit") is None,
    reason="streamlit 미설치 — AppTest 불가")

APP_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "streamlit_app.py")
DUSEO, DUDONG = "(주)디아이씨두서공장", "(주)디아이씨두동공장"
INSERTED, UPDATED = [], []


def _workbook():
    """파서 테스트의 표본 + 기존 수주(…712)의 새 행번 5 한 줄."""
    import openpyxl
    from test_so_parser_utils import _dic_workbook
    wb = openpyxl.load_workbook(io.BytesIO(_dic_workbook()))
    ws = wb.active
    row = [4, "2026-09-15", "6A503007#1", "COLLOR,SPLINE-선삭", "", "SCM415",
           "정상", "P10", "중장비공장", "EA ", "PO2609000000712", "5", 200,
           "2026-10-31", 0, 200, "통합물류창고(중장비)"]
    for j, v in enumerate(row, 1):
        ws.cell(21, j, v)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _fetch(table, select="*", filter_query="", limit=1000):
    fq = unquote(filter_query or "")
    if table == "vendors":
        if "name=like.*디아이씨*" in fq:
            return [{"name": DUSEO}, {"name": DUDONG}]
        if f'name=eq."{DUSEO}"' in fq:
            return [{"vendor_id": 15, "name": DUSEO}]
        if f'name=eq."{DUDONG}"' in fq:
            return [{"vendor_id": 14, "name": DUDONG}]
        return []
    if table == "sales_orders":
        if DUSEO in fq and "PO2609000000712" in fq:
            return [{"so_id": 500, "so_number": "PO2609000000712"}]
        return []
    if table == "sales_order_items":
        if "so_id=in.(500)" in fq:
            return [{"soi_id": 9001, "so_id": 500, "line_no": 3,
                     "customer_part_no": "6A433004#1", "qty": 400,
                     "received_qty": 300}]
        return []
    if table == "products":
        if "product_id=in." in fq:
            return [{"product_id": "P0864", "sale_price": 842},
                    {"product_id": "P0575", "sale_price": 618}]
        return [
            {"product_id": "P0857", "pn": "6A433004#1", "alias_list": None,
             "archived_at": None, "archive_reason": None},
            {"product_id": "P0864", "pn": "6A503007#1", "alias_list": None,
             "archived_at": None, "archive_reason": None},
            {"product_id": "P0575", "pn": "24315-45001",
             "alias_list": "624315-45001#1", "archived_at": None,
             "archive_reason": None},
        ]
    return []


def _fetch_one(table, filter_query="", select="*"):
    fq = unquote(filter_query or "")
    if table == "sales_orders":
        if "PO2610000000060" in fq:
            return {"so_id": 701}
        if "PO2610000000999" in fq:
            return {"so_id": 702}
    return None


@pytest.fixture()
def dic_db(monkeypatch):
    import db
    INSERTED.clear()
    UPDATED.clear()
    monkeypatch.setattr(db, "fetch", _fetch)
    monkeypatch.setattr(db, "fetch_one", _fetch_one)
    monkeypatch.setattr(db, "insert",
                        lambda t, r: (INSERTED.append((t, r)), len(r))[1])
    monkeypatch.setattr(db, "update",
                        lambda t, f, v: (UPDATED.append((t, f, v)), True)[1])
    monkeypatch.setattr(db, "health_check",
                        lambda: {"status": "OK", "counts": {}})
    monkeypatch.setattr(db, "debug_check", lambda: {"status": "mock"})
    if hasattr(db, "count_rows"):
        monkeypatch.setattr(db, "count_rows", lambda *a, **k: 0)
    if hasattr(db, "rpc"):
        monkeypatch.setattr(db, "rpc", lambda *a, **k: None)
    return db


def test_dic_upload_two_customers_append_and_price(dic_db):
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    for _c in (st.cache_data, st.cache_resource):
        try:
            _c.clear()
        except Exception:
            pass
    at = AppTest.from_file(APP_FILE, default_timeout=60)
    at.secrets["supabase"] = {"url": "https://mock.local",
                              "anon_key": "a", "service_role_key": "s"}
    at.secrets["auth"] = {"disabled": True}
    at.run()
    at.sidebar.radio[0].set_value("수주 관리")
    at.sidebar.radio[1].set_value(None)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]

    up = at.get("file_uploader")
    assert up, "파일 업로더 없음"
    up[0].upload("납품예정서등록-DIC.xls", _workbook()).run()
    assert not at.exception, [str(e.value) for e in at.exception]

    infos = " ".join(str(i.value) for i in at.info)
    assert "DIC (납품예정서등록 엑셀)" in infos
    # 기존 수주(…712): 새 행번 1개는 추가, 이미 있는 행번 3은 그대로
    assert "이미 등록된 수주 **1건**" in infos and "새 행번 1개" in infos
    assert not any("다른 라인" in (e.label or "") for e in at.expander)
    # 마스터에 없는 납품공장 경고
    assert any("신공장" in str(w.value) for w in at.warning)

    save = [b for b in at.button if b.label == "수주 DB 저장"]
    assert save
    save[0].click().run()
    assert not at.exception, [str(e.value) for e in at.exception]

    heads = [r for t, rows in INSERTED if t == "sales_orders" for r in rows]
    lines = [r for t, rows in INSERTED if t == "sales_order_items" for r in rows]
    # 헤더: 두동 신규 1건 + 모르는 공장 1건 (기존 …712 는 헤더를 만들지 않음)
    assert {h["so_number"] for h in heads} == {"PO2610000000060",
                                              "PO2610000000999"}
    dudong = next(h for h in heads if h["so_number"] == "PO2610000000060")
    assert dudong["customer"] == DUDONG and dudong["vendor_id"] == 14
    # 기존 수주에 붙은 새 라인 — 마스터 판매단가, 미납 = 수량
    app = next(x for x in lines if x["so_id"] == 500)
    assert app["line_no"] == 5 and app["customer_part_no"] == "6A503007#1"
    assert app["product_id"] == "P0864" and app["unit_price"] == 842
    assert app["amount"] == 200 * 842 and app["pending_qty"] == 200
    # 이미 있는 행번 3 은 다시 넣지도, 고치지도 않는다
    assert not any(x["so_id"] == 500 and x["line_no"] == 3 for x in lines)
    assert not any(t == "sales_order_items" for t, _f, _v in UPDATED)
    # 두동 라인 — 별칭(624315-45001#1)으로 본품 연결 + 단가
    d = next(x for x in lines if x["so_id"] == 701)
    assert d["product_id"] == "P0575" and d["unit_price"] == 618
    assert d["status"] == "PENDING"
