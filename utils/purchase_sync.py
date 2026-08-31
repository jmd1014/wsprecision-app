# -*- coding: utf-8 -*-
"""매입내역 구글시트 동기화 + 자재 자동 매칭 헬퍼.

시트 양식: 스프레드시트에 "YYYY년_MM월" 탭, 각 탭 컬럼
  월/일 | 업체명 | 품명 및 규격 | 단위 | 수량 | 중량 | 단가 |
  공급가액 | 세액 | 합계 | 비고
매칭 규칙(2026-08-31 확정, 원가 오염 방지를 위해 보수적):
  재질(grade) + 치수(Ø지름*길이 / t*w*L) + 형상(환봉/육각) 완전 일치,
  후보 자재가 정확히 1개, EA 단위, 단가 > 0 인 행만 자동 매칭.
  KG 단위 매입은 환산 로직 전까지 보류(행은 추가, 매칭만 비움).
"""
import re
from collections import defaultdict

NUM = r"(\d+(?:\.\d+)?)"
DIA_CH = "[Φφ￠Øø∅]"

# 기본 매입내역 시트 (2026년) — app_settings 'purchase_sheet_id' 로 교체 가능
DEFAULT_SHEET_ID = "1MJxpdXU6niYAo26HQSh6IfPJ4QfRJsl1T_DGWxnpyYU"


def norm_grade(t):
    """텍스트에서 재질 등급 추출 (없으면 None → 소재 아님으로 간주)"""
    s = str(t).upper().replace(" ", "")
    if "316/L" in s or "316L" in s:
        return "316L"
    if "316" in s:
        return "316"
    if "304" in s:
        return "304"
    if "630" in s:
        return "630"
    if "6061" in s:
        return "AL6061"
    if "SCM440" in s:
        return "SCM440"
    if "S45C" in s:
        return "S45C"
    if (re.search(r"(^|[^A-Z])BS([^A-Z]|$)", s) or "황동" in s
            or "BRASS" in s or "C3604" in s or "C3771" in s):
        return "BS"
    return None


def norm_dims(t):
    """치수 추출 — 환봉/육각 (지름, 길이) 또는 사각 (t, w, L).
    DIA 문자가 숫자 앞에 오는 표기를 먼저 시도해 SCM440 의 440 같은
    재질 숫자를 지름으로 오인하지 않는다."""
    s = (str(t).replace("×", "*").replace("x", "*").replace("X", "*")
         .replace("ℓ", "").replace("Ｌ", "L"))
    m = re.search(NUM + r"[Tt]?\s*\*\s*" + NUM + r"\s*\*\s*" + NUM, s)
    if m:
        return ("SQ", *(float(m.group(i)) for i in (1, 2, 3)))
    m = (re.search(DIA_CH + r"\s*" + NUM + r"\s*\*\s*" + NUM, s)
         or re.search(r"(?<![A-Za-z0-9.])" + NUM + r"\s*" + DIA_CH
                      + r"\s*\*?\s*" + NUM, s))
    if m:
        return ("RD", float(m.group(1)), float(m.group(2)))
    return None


def is_hex(t):
    """육각봉 여부 — 매입 품명의 '육각' 또는 자재명의 H<숫자> 표기"""
    return bool("육각" in str(t) or re.search(r"(^|\s)H\d", str(t)))


def keyize(g, d, hexed=False):
    if not g or not d:
        return None
    shape = "HX" if (d[0] == "RD" and hexed) else d[0]
    return (g,) + tuple(round(x, 1) for x in d[1:]) + (shape,)


def build_key_mats(materials):
    """활성 자재 목록 → 매칭 키 사전. spec 과 raw_name 양쪽 키 등록
    (마스터 표기 불일치 흡수)."""
    key_mats = defaultdict(list)
    for m in materials:
        if m.get("archived_at"):
            continue
        txt = ((m.get("material_type") or "") + " " + (m.get("spec") or "")
               + " " + (m.get("raw_name") or ""))
        g = norm_grade(txt)
        hexed = is_hex(txt)
        ks = set()
        for src in (m.get("spec"), m.get("raw_name")):
            if src:
                k = keyize(g, norm_dims(src), hexed)
                if k:
                    ks.add(k)
        for k in ks:
            key_mats[k].append(m["material_id"])
    return key_mats


def match_material(item, unit, price, key_mats):
    """(material_id | None, 사유). 사유: 'OK' | 'KG' | 'DUP' | 'NOMAT'
    | 'ZERO' | 'ETC'(소재 아님)."""
    g = norm_grade(item or "")
    k = keyize(g, norm_dims(item or ""), is_hex(item or ""))
    if not k:
        return None, "ETC"
    cands = key_mats.get(k, [])
    if not cands and k[0] in ("316", "316L"):
        # 발주서 SUS316 ↔ 장부 316/L 표기 차이 흡수 (치수 유일 시)
        pool = {m for kk in (("316",) + k[1:], ("316L",) + k[1:])
                for m in key_mats.get(kk, [])}
        cands = sorted(pool)
    if len(cands) > 1:
        return None, "DUP"
    if not cands:
        return None, "NOMAT"
    if (unit or "EA").upper() != "EA":
        return None, "KG"
    try:
        p = float(str(price or 0).replace(",", ""))
    except (TypeError, ValueError):
        p = 0
    if p <= 0:
        return None, "ZERO"
    return cands[0], "OK"


def _numv(v):
    if v in (None, ""):
        return None
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def parse_month_tab(title, values):
    """탭 제목 'YYYY년_MM월' + 행 리스트 → 장부 행 dict 리스트"""
    m = re.match(r"(\d{4})년_(\d+)월", str(title))
    if not m:
        return []
    year = int(m.group(1))
    rows = []
    prev_day = None
    for raw in values[1:]:  # 헤더 제외
        raw = list(raw) + [None] * (11 - len(raw))
        (dt, vendor, item, unit, qty, wt, price,
         supply, vat, tot, rmk) = raw[:11]
        if not vendor and not item:
            continue
        if str(vendor).strip() in ("", "0") or str(item).strip() in ("", "0"):
            continue
        day = None
        if isinstance(dt, str):
            dm = re.match(r"(\d+)월\s*(\d+)일", dt.strip())
            if dm:
                day = (f"{year}-{int(dm.group(1)):02d}"
                       f"-{int(dm.group(2)):02d}")
        elif hasattr(dt, "strftime"):
            day = dt.strftime(f"{year}-%m-%d")
        if day is None:
            # 시트 관행: 같은 날 연속 행은 날짜를 첫 행에만 기재
            day = prev_day
        else:
            prev_day = day
        rows.append({
            "trade_date": day, "vendor": str(vendor).strip(),
            "item": str(item).strip(),
            "unit": (str(unit).strip() if unit not in (None, "", 0)
                     else None),
            "qty": _numv(qty), "weight": _numv(wt),
            "unit_price": _numv(price), "amount": _numv(supply),
            "vat": _numv(vat), "total": _numv(tot),
            "remark": (str(rmk).strip() if rmk not in (None, "", 0)
                       else None),
        })
    return rows


def dedup_key(row):
    """장부 중복 판정 키 — 날짜+업체+품명(공백 무시)+공급가액(반올림)"""
    try:
        amt = round(float(row.get("amount") or 0))
    except (TypeError, ValueError):
        amt = None
    return (row.get("trade_date"), str(row.get("vendor") or "").strip(),
            re.sub(r"\s+", "", str(row.get("item") or "")), amt)


def download_sheet_xlsx(sheet_id, timeout=30):
    """공개(링크 공유) 시트를 xlsx 로 다운로드. 실패 시 RuntimeError."""
    import requests
    url = (f"https://docs.google.com/spreadsheets/d/{sheet_id}"
           f"/export?format=xlsx")
    r = requests.get(url, timeout=timeout)
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or "spreadsheetml" not in ctype:
        raise RuntimeError(
            "시트 다운로드 실패 — 스프레드시트가 '링크가 있는 모든 사용자"
            "(뷰어)' 로 공유되어 있어야 합니다. "
            f"(status {r.status_code})")
    return r.content


def load_sheet_tabs(sheet_id):
    """시트 전체 탭 → [(탭제목, 값 행렬)]. 공개 링크 export 사용."""
    import io as _io

    import openpyxl
    wb = openpyxl.load_workbook(
        _io.BytesIO(download_sheet_xlsx(sheet_id)), data_only=True)
    return [(ws.title, [list(r) for r in ws.iter_rows(values_only=True)])
            for ws in wb.worksheets]
