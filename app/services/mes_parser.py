"""
MES 일간생산보고서 파서.

사내 MES 의 [EXCEL] 내보내기 파일 (.xls 확장자지만 실제 HTML 테이블) 을
파싱해서 공정 실적 행 리스트로 변환.

컬럼: 설비명 / 제품명 / 공정명 / 작업시간 / 작업자 / 작업지시서 / 생산수량 / 불량수량
- '소 계' / '총 합 계' 행 자동 제외
- 작업시간 "08:54 ~ 12:28" → work_start / work_end 분리
- 공정명 "CNC#10" → process_step=10 추출
- 파일명 "일간생산보고서_20260703.xls" → 생산일 추출

Streamlit 의존 없음 — 단위 테스트 가능.
"""
import re
from io import BytesIO
from datetime import date

WORK_TIME_RE = re.compile(r'(\d{1,2}:\d{2})\s*~\s*(\d{1,2}:\d{2})')
PROCESS_STEP_RE = re.compile(r'#\s*(\d+)')
FILENAME_DATE_RE = re.compile(r'(\d{8})')
SUBTOTAL_TOKENS = ('소 계', '소계', '총 합 계', '총합계', '합 계')

REQUIRED_COLS = ['설비명', '제품명', '공정명', '작업시간', '작업자',
                 '작업지시서', '생산수량', '불량수량']


def parse_date_from_filename(filename: str):
    """'일간생산보고서_20260703.xls' → date(2026,7,3). 실패 시 None."""
    m = FILENAME_DATE_RE.search(filename or "")
    if not m:
        return None
    s = m.group(1)
    try:
        return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    except ValueError:
        return None


def _num(v):
    try:
        return float(str(v).replace(',', '').strip())
    except (ValueError, TypeError):
        return 0.0


def _clean(v) -> str:
    """텍스트 정규화 — &nbsp;(\xa0) → 공백, 연속 공백 1개로.
    작업지시서는 수주 연결 키 후보라 공백 통일 필수."""
    s = str(v if v is not None else "")
    if s.lower() == 'nan':
        return ""
    return re.sub(r'\s+', ' ', s.replace('\xa0', ' ')).strip()


def _is_subtotal(text: str) -> bool:
    t = str(text or "").strip()
    return any(tok in t for tok in SUBTOTAL_TOKENS)


def parse_mes_daily_report(content: bytes) -> list:
    """MES 일간 보고서 HTML(.xls) 바이트 → 실적 행 리스트.

    반환 행: {equipment, item_name, process, process_step,
              work_start, work_end, worker, work_order, qty, defect}
    """
    import pandas as pd
    tables = pd.read_html(BytesIO(content), encoding='utf-8')
    if not tables:
        raise ValueError("테이블을 찾을 수 없습니다 — MES 엑셀 파일인지 확인하세요.")
    df = tables[0]

    # 첫 데이터 행이 헤더인 경우 처리
    first_row = [str(x).strip() for x in df.iloc[0]]
    if '설비명' in first_row:
        df.columns = first_row
        df = df.iloc[1:]
    else:
        df.columns = [str(c).strip() for c in df.columns]

    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"필수 컬럼 누락: {missing} — MES 일간 보고서 양식이 맞는지 확인하세요.")

    rows = []
    for _, r in df.iterrows():
        equip = _clean(r['설비명'])
        wt = _clean(r['작업시간'])
        # 소계/합계/빈 행 제외
        if not equip or _is_subtotal(equip) or _is_subtotal(wt):
            continue

        ws = we = None
        m = WORK_TIME_RE.search(wt)
        if m:
            ws, we = m.group(1), m.group(2)

        proc = _clean(r['공정명'])
        step = None
        ms = PROCESS_STEP_RE.search(proc)
        if ms:
            step = int(ms.group(1))

        rows.append({
            "equipment": equip,
            "item_name": _clean(r['제품명']),
            "process": proc,
            "process_step": step,
            "work_start": ws,
            "work_end": we,
            "worker": _clean(r['작업자']),
            "work_order": _clean(r['작업지시서']),
            "qty": _num(r['생산수량']),
            "defect": _num(r['불량수량']),
        })
    return rows


def match_product_pn(item_name: str, pn_set: set) -> str:
    """MES 제품명 → 제품 마스터 pn 매칭.

    1) 정확 일치
    2) '/' 앞부분 일치 (예: 'HA30-60251/SB' → 'HA30-60251')
    반환: 매칭된 pn 또는 None
    """
    if not item_name:
        return None
    name = item_name.strip()
    if name in pn_set:
        return name
    if '/' in name:
        base = name.split('/')[0].strip()
        if base in pn_set:
            return base
    return None
