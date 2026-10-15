# -*- coding: utf-8 -*-
"""매입내역 구글시트 동기화 + 자재 자동 매칭 헬퍼.

시트 양식: 스프레드시트에 "YYYY년_MM월" 탭, 각 탭 컬럼
  월/일 | 업체명 | 품명 및 규격 | 단위 | 수량 | 중량 | 단가 |
  공급가액 | 세액 | 합계 | 비고
매칭 규칙(2026-08-31 확정, 원가 오염 방지를 위해 보수적):
  재질(grade) + 치수(Ø지름*길이 / t*w*L) + 형상(환봉/육각) 완전 일치,
  후보 자재가 정확히 1개, EA 단위, 단가 > 0 인 행만 자동 매칭.
  KG 단위 매입은 환산 로직 전까지 보류(행은 추가, 매칭만 비움).
혜성철강 환봉(KG 매입) + 절단비(EA, 수량 = 부품 수) 두 행은 merge_cutting_rows 로
  한 행(EA, 개당 단가 = (환봉 금액 + 절단비) ÷ 부품 수)으로 합친 뒤 매칭한다 —
  시트 시절 Apps Script PMLib.preprocessHyesungCutting 규칙을 그대로 이식 (2026-10-15).
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
    m = re.search(r"SCM(\d{3})H?", s)
    if m:                       # SCM440 / SCM415H → SCM415 / SCM420H → SCM420
        return f"SCM{m.group(1)}"
    m = re.search(r"S(\d{2})C", s)
    if m:                       # S45C / S20C / S55C — 앞 글자 무관('SHAFT IDLER S45C', 'SCMS45C' 오기 포함, 종전 'in' 과 동일)
        return f"S{m.group(1)}C"
    if re.search(r"303(?!\d)", s):   # STS303 — '3037' 같은 치수·품번 숫자는 제외
        return "303"
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


_CUT_VENDOR = "혜성"
_CUT_MAT_RE = re.compile(r"환봉|단조|육환봉")


def _n(v):
    try:
        return float(str(v).replace(",", "")) if v not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0


def merge_cutting_rows(rows):
    """혜성철강 '환봉/단조/육환봉' 행 바로 다음에 같은 날짜·같은 업체의 '절단비' 행이 오면 한 행으로 합산.
    수량 = 절단비 수량(= 부품 개수), 금액·세액·합계 = 두 행 합, 단위 EA,
    개당 단가 = (환봉 금액 + 절단비 금액) ÷ 부품 수(반올림), 비고 += '[+절단비 N원]'.
    중량(kg)은 환봉 행 값을 유지. 절단비 수량이 0 이면 합치지 않는다.
    반환: (새 행 목록, 합산 건수). 입력 dict 는 바꾸지 않는다(복사). ledger_id 등 다른 키는 환봉 행 것을 유지하고,
    합산된 절단비 행은 '_merged_from' 키로 환봉 행에 붙는다(장부 재처리용).
    멱등: 비고에 이미 '[+절단비' 가 있는 환봉 행은 다시 합치지 않는다(재처리·재실행 이중 계상 방지).
    환봉 kg 단가는 kg_price, 개당 단가는 ea_price 에도 둔다. 절단비 행의 matched_pn·비고는 환봉 행에 없을 때 승계.
    Apps Script 원본과 다른 점: 날짜 둘 다 있어야 함(원본은 Date 형만), 절단 수량 0 이면 분리(원본은 금액만 합산),
    단위 EA·중량 kg 기록(원본은 단위 불변) — 매칭·원가에 필요한 변경."""
    out, i, n = [], 0, 0
    while i < len(rows):
        r = rows[i]
        nxt = rows[i + 1] if i + 1 < len(rows) else None
        if (nxt is not None and _CUT_VENDOR in str(r.get("vendor") or "")
                and _CUT_MAT_RE.search(str(r.get("item") or ""))
                and "[+절단비" not in str(r.get("remark") or "")
                and "절단" in str(nxt.get("item") or "")
                and _CUT_VENDOR in str(nxt.get("vendor") or "")
                and r.get("trade_date") and r.get("trade_date") == nxt.get("trade_date")
                and _n(nxt.get("qty")) > 0):
            cut_qty = _n(nxt.get("qty"))
            mat_amt, cut_amt = _n(r.get("amount")), _n(nxt.get("amount"))
            mat_vat, cut_vat = _n(r.get("vat")), _n(nxt.get("vat"))
            mat_tot = _n(r.get("total")) or (mat_amt + mat_vat)
            cut_tot = _n(nxt.get("total")) or (cut_amt + cut_vat)
            m = dict(r)
            m["unit"] = "EA"
            m["qty"] = cut_qty
            if str(r.get("unit") or "").upper() == "KG":
                if m.get("weight") in (None, ""):
                    m["weight"] = r.get("qty")
                m["kg_price"] = r.get("unit_price")
            m["unit_price"] = round((mat_amt + cut_amt) / cut_qty)
            m["ea_price"] = m["unit_price"]
            m["amount"] = mat_amt + cut_amt
            m["vat"] = mat_vat + cut_vat
            m["total"] = mat_tot + cut_tot
            rk = str(r.get("remark") or "").strip() or str(nxt.get("remark") or "").strip()
            m["remark"] = (rk + " " if rk else "") + f"[+절단비 {int(round(cut_amt)):,}원]"
            if not m.get("matched_pn") and nxt.get("matched_pn"):
                m["matched_pn"] = nxt.get("matched_pn")
            m["_merged_from"] = nxt
            out.append(m)
            n += 1
            i += 2
            continue
        out.append(r)
        i += 1
    return out, n


_VENDOR_STRIP_RE = re.compile(r"\(주\)|주식회사|㈜|\s+")
_DIA_RE = re.compile("[Φφ￠Øø∅]")


def vendor_key(vendor):
    """매핑표 거래처 키 — '(주)명진메탈' / '주식회사유성메탈' / '혜성철강 (주)' 의 법인 표기·공백 제거, 대문자."""
    return _VENDOR_STRIP_RE.sub("", str(vendor or "")).upper()


def item_key(item):
    """매핑표 품명 키 — 대문자, 공백 제거, 지름 기호 통일(Φ), ℓ→L, 숫자 사이 x/×→*.
    'STS304육각 38￠*24ℓ' 와 'STS304육각38Φ*24L' 이 같은 키."""
    s = str(item or "").upper()
    s = _DIA_RE.sub("Φ", s).replace("ℓ", "L").replace("Ｌ", "L")
    s = re.sub(r"(?<=[\dΦ])\s*[X×]\s*(?=\d)", "*", s)   # 55ΦX5 · 38X24 → *, 단어 속 X(XDBP…) 보존
    return re.sub(r"\s+", "", s)


def piece_price_rows(rows):
    """KG 매입인데 수량(개)과 중량(kg)이 따로 적힌 행(명진메탈식) → 개당 기준으로.
    조건: unit KG · weight>0 · qty>0 · qty≠weight · amount>0. 변환: kg_price=원 단가, unit_price=round(amount/qty),
    ea_price=같음, unit='EA', 수량·중량·금액 유지. 혜성 환봉(수량=중량 kg)은 대상 아님(절단비 합산이 담당).
    반환 (새 행 목록, 변환 건수). 입력 불변."""
    out, n = [], 0
    for r in rows:
        unit = str(r.get("unit") or "").upper()
        qty, wt, amt, up = _n(r.get("qty")), _n(r.get("weight")), _n(r.get("amount")), _n(r.get("unit_price"))
        # 가드: 중량 × kg 단가 ≈ 금액(2%) 일 때만 — 단위 오기·건수 병기 공정비 행 차단 (Reviewer H3)
        if (unit == "KG" and wt > 0 and qty > 0 and abs(qty - wt) > 1e-9 and amt > 0
                and up > 0 and abs(wt * up - amt) <= amt * 0.02):
            m = dict(r)
            m["kg_price"] = r.get("unit_price")
            m["unit"] = "EA"
            m["unit_price"] = round(amt / qty)
            m["ea_price"] = m["unit_price"]
            out.append(m)
            n += 1
        else:
            out.append(r)
    return out, n


def is_linked(row):
    """행이 이미 연결(결정)됐는가 — 자재가 있거나 mapping_status 가 있음. 비고 첫 토큰에서 온 matched_pn
    (그 소재가 들어갈 제품 품번)은 연결 판정에 넣지 않는다 (Reviewer B1)."""
    return bool(row.get("matched_material_id") or row.get("mapping_status"))


def apply_item_map(rows, imap):
    """매핑표 적용. imap: {(vendor_key, item_key): {map_id, line_type, material_id, product_pn, process_type}}.
    is_linked 가 아닌 행만. MATERIAL/SUPPLY → matched_material_id(기존 matched_pn 보존), PRODUCT → matched_pn
    (자재가 있는 행엔 적용 안 함), PROCESS/OTHER → 상태만. 적용 행: mapping_status='MAP', map_id, category 는
    비어 있을 때만 line_type. 반환 적용 건수. 행은 제자리 수정."""
    n = 0
    for r in rows:
        if is_linked(r):
            continue
        m = imap.get((vendor_key(r.get("vendor")), item_key(r.get("item"))))
        if not m:
            continue
        lt = m.get("line_type")
        if lt in ("MATERIAL", "SUPPLY"):
            if not m.get("material_id"):
                continue
            r["matched_material_id"] = m["material_id"]
        elif lt == "PRODUCT":
            if not m.get("product_pn"):
                continue
            r["matched_pn"] = m["product_pn"]
        r["mapping_status"] = "MAP"
        if m.get("map_id"):
            r["map_id"] = m["map_id"]
        if not r.get("category"):
            r["category"] = lt
        n += 1
    return n


def dedup_key(row):
    """장부 중복 판정 키 — 날짜 + 거래처 키(법인 표기·공백 무시) + 품명 키(공백·기호 정규화) + 공급가액(반올림).
    시트 '(주)유성메탈' 와 수기 입력(마스터명 '주식회사유성메탈')이 같은 키 (Reviewer B2, 2026-10-15)."""
    try:
        amt = round(float(row.get("amount") or 0))
    except (TypeError, ValueError):
        amt = None
    return (str(row.get("trade_date") or "")[:10], vendor_key(row.get("vendor")),
            item_key(row.get("item")), amt)


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
