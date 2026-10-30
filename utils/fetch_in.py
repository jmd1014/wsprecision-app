# -*- coding: utf-8 -*-
"""id 목록 묶음(in) 조회를 끝까지 — 핫픽스 2 후속 2차 묶음 F (2026-10-30).

`fetch(..., "col=in.(…)", limit=1000|2000)` 은 PostgREST 요청당 1,000행 상한에 조용히 잘린다
(len < limit 라 절단도 감지되지 않음). id 를 `chunk` 개씩 나눠 각 묶음을 `db.fetch_all` 로 끝까지 읽고
절단 여부를 OR 로 모아 돌려준다 — 호출자가 집계면 '미확인'·확정 차단, 목록이면 경고 1줄.
"""


def fetch_all_in(table, select, col, ids, extra="", *, quote=False, chunk=50,
                 order=None, pk=None, dedupe=True, cache=None):
    """→ (rows, truncated). ids 가 비면 ([], False) — 조회하지 않는다.

    - ids: 순서 유지 중복 제거 뒤 `chunk` 개씩. quote=True 면 값마다 큰따옴표(문자 id, 기존 호출 표기 그대로).
    - extra: in 조건 뒤에 붙는 추가 필터(`pending_qty=gt.0` 등). order= 는 넣지 말 것(order 인자로).
    - 정렬은 묶음 안에서만 결정적이다(묶음끼리 이어 붙임) — 전체 순서가 필요하면 호출자가 다시 정렬.
    - pk·dedupe·cache 는 db.fetch_all 그대로(뷰는 구조적 유일 키만, 아니면 dedupe=False).
    """
    import db                      # 호출 시점 조회 — 테스트 목(monkeypatch)을 그대로 탄다
    vals = list(dict.fromkeys(i for i in ids if i is not None))
    rows, truncated = [], False
    kw = {"order": order, "pk": pk, "dedupe": dedupe}
    if cache is not None:
        kw["cache"] = cache
    for i in range(0, len(vals), chunk):
        part = ",".join(f'"{v}"' if quote else str(v) for v in vals[i:i + chunk])
        filt = f"{col}=in.({part})" + (f"&{extra}" if extra else "")
        r, t = db.fetch_all(table, select, filt, **kw)
        rows += r
        truncated = truncated or bool(t)
    return rows, truncated
