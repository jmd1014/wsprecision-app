# -*- coding: utf-8 -*-
"""거래명세서 스캔 판독 — 내부 OCR(Tesseract) + 장부 연관성 매칭 (2026-10-16, 매입 내재화 2단계).

사용자 결정(2026-10-15): 외부 API 대신 내부 OCR, 거래처 양식은 몇 종이므로 "내부 DB 연관성" 위주로 맞추고
입력자가 검토·수정 후 확정한다.

흐름 (parse_document):
  파일(PDF/이미지) → 페이지 렌더(300dpi, 그레이·이진화) → 방향 보정(0/90/180/270 중 OCR 신뢰도 최고)
  → 단어 OCR(kor+eng, psm 6/11/4 중 라인 수·합계 검증이 가장 좋은 것) → 줄 묶기
  → 거래처: 본문 숫자열에서 등록 사업자번호 검색(우성정밀 제외) → 거래일(후보 중 오늘−400~+7 안, '일자' 글자에 가까운 것)
  → 라인: 단어 정규화(`1,390/KG`·`150°`) → ① 수량×단가=금액(±0.1%, 세액 모양 후보 제외) ② 금액+세액(10%) 쌍에서
    수량·단가 복원 → 단위(오독 `Ko` 포함)·KG 행 수량(중량 왼쪽 숫자)·품명(첫 숫자 앞 글자, 정리본)·비고(줄 끝 `/품번`)
    (2026-11-03 매입 OCR 보완 r1 — 샘플 5장 픽스처 tests/fixtures/stmt_ocr_20261102.json)
  → 합계 검증: '합계/공급가액' 줄의 숫자 == 라인 합, 또는 라인 합과 그 10%(세액)가 본문에 함께 있음
  → 품명 제안: 그 거래처의 기존 장부 품명과 ① 재질+치수 일치(OCR 'Φ→0/?' 보정, 변형 표기는 최근 것)
    ② 단가 일치 ③ 유사도(rapidfuzz). 제안은 검토 표의 기본값일 뿐 — 저장은 입력자가 확정한 값으로.

의존: pytesseract + Tesseract 실행 파일(윈도 C:\\Program Files\\Tesseract-OCR, 리눅스 apt tesseract-ocr/-kor),
PyMuPDF(fitz), Pillow, rapidfuzz. 엔진이 없으면 ocr_available() 가 False — 화면은 안내만 한다.
이 모듈은 DB 를 모른다: vendors(사업자번호)·known(거래처별 기존 품명·단가)는 호출자가 넘긴다.
"""
import io
import os
import re
import shutil
import datetime as dt
from collections import Counter, defaultdict

from utils.purchase_sync import vendor_key, item_key, norm_grade, norm_dims

NUM_RE = re.compile(r"^[\d,]+(?:\.\d+)?\.?$")
UNITS = {"EA", "KG", "Kg", "kg", "SET", "CH", "식", "M", "본"}
DATE_RE = re.compile(r"(20\d\d)\D{0,6}(\d{1,2})\D{0,6}(\d{1,2})")
# 치수 구분자: `*`·`x`·`×` + OCR 오독 `＊#¢@?`(Φ·ℓ 자리), `110? +24` 처럼 구분자 뒤 `+` 도 (O6, 2026-11-03)
DIMS_RE = re.compile(r"(\d+(?:\.\d+)?)[^\d*xX×＊#¢@?]{0,3}(?:[*xX×＊#¢@?]\s*)+\+?\s*(\d+(?:\.\d+)?)")
_TESS_WIN = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def _tesseract_cmd():
    if shutil.which("tesseract"):
        return shutil.which("tesseract")
    if os.path.exists(_TESS_WIN):
        return _TESS_WIN
    return None


def ocr_available():
    try:
        import pytesseract  # noqa: F401
        import fitz  # noqa: F401
        import rapidfuzz  # noqa: F401
    except ImportError:
        return False
    return _tesseract_cmd() is not None


def _cfg(psm):
    td = os.environ.get("TESSDATA_DIR") or (r"C:\Temp\tessdata" if os.path.isdir(r"C:\Temp\tessdata") else None)
    return (f"--tessdata-dir {td} " if td else "") + f"--psm {psm}"


# ─────────────────────────── 이미지·OCR ───────────────────────────
def render_pages(file_bytes, name="", dpi=300):
    """PDF 또는 이미지 바이트 → [PIL 흑백 이진 이미지]"""
    from PIL import Image, ImageOps
    imgs = []
    if (name or "").lower().endswith(".pdf") or file_bytes[:4] == b"%PDF":
        import fitz
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            imgs.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
    else:
        imgs.append(Image.open(io.BytesIO(file_bytes)).convert("RGB"))
    out = []
    for img in imgs:
        g = ImageOps.autocontrast(ImageOps.grayscale(img))
        out.append(g.point(lambda v: 255 if v > 160 else 0))
    return out


def _image_to_words(img, psm):
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd()
    d = pytesseract.image_to_data(img, lang="kor+eng", config=_cfg(psm), output_type=pytesseract.Output.DICT)
    return [{"t": t.strip(), "x": d["left"][i], "y": d["top"][i], "w": d["width"][i], "h": d["height"][i], "c": float(d["conf"][i])}
            for i, t in enumerate(d["text"]) if t.strip() and float(d["conf"][i]) >= 0]


def best_rotation(img):
    small = img.resize((max(1, img.width // 3), max(1, img.height // 3)))
    best = (0, -1.0)
    for rot in (0, 90, 180, 270):
        words = _image_to_words(small.rotate(rot, expand=True), 11)
        confs = [w["c"] for w in words]
        score = (sum(confs) / len(confs) if confs else 0) * min(len(confs), 60)
        if score > best[1]:
            best = (rot, score)
    return best[0]


def group_lines(words):
    """y 중심이 가까운 단어를 한 줄로 묶고 x 순 정렬."""
    words = sorted(words, key=lambda w: (w["y"] + w["h"] / 2))
    lines = []
    for w in words:
        yc = w["y"] + w["h"] / 2
        for ln in lines:
            if abs(ln["yc"] - yc) <= max(min(ln["h"], w["h"]) * 0.5, 8):
                ln["words"].append(w)
                ln["yc"] = (ln["yc"] * (len(ln["words"]) - 1) + yc) / len(ln["words"])
                ln["h"] = max(ln["h"], w["h"])
                break
        else:
            lines.append({"yc": yc, "h": w["h"], "words": [w]})
    for ln in lines:
        ln["words"].sort(key=lambda w: w["x"])
        ln["text"] = " ".join(w["t"] for w in ln["words"])
    lines.sort(key=lambda l: l["yc"])
    return lines


# ─────────────────────────── 해석 (순수 함수, 테스트 대상) ───────────────────────────
def to_num(t):
    t = str(t).replace(",", "").replace("O", "0").replace("o", "0").rstrip(".")
    try:
        return float(t)
    except ValueError:
        return None


_NUM_UNIT_RE = re.compile(r"^(\d[\d,.]*)/(KG|EA|M|SET|본)$", re.I)
_NUM_TAIL_RE = re.compile(r"[°'\"·,@:]+$")
_DOTS_MULTI_RE = re.compile(r"^\d{1,3}(?:\.\d{3}){2,}$")      # 1.214.400 — 소수일 수 없는 꼴
_DOTS_ONE_RE = re.compile(r"^\d{1,3}\.\d{3}$")                 # 155.100 — 소수(1.016)와 겹쳐 금액·단가 자리만 2차 해석


def normalize_tokens(toks):
    """O1(2026-11-03): 단가 칸 `1,390/KG`·`105/EA` → 숫자 + 단위 두 단어, 숫자 끝의 `°'"·,@:` 떼기(`150°`·`300,000:`),
    점 여러 개 천단위 `1.214.400` → `1,214,400`. 같은 입력을 두 번 넣어도 결과가 같다(line_nums 가 안에서 다시 불러도
    번호가 어긋나지 않게)."""
    out = []
    for w in toks:
        t = str(w["t"])
        m = _NUM_UNIT_RE.match(t)
        if m:
            out += [{**w, "t": m.group(1)}, {**w, "t": m.group(2).upper()}]
            continue
        s = _NUM_TAIL_RE.sub("", t)
        if _DOTS_MULTI_RE.match(s):
            s = s.replace(".", ",")
        out.append({**w, "t": s} if (s != t and s and NUM_RE.match(s.replace("O", "0"))) else w)
    return out


def line_nums(toks):
    toks = normalize_tokens(toks)
    out = []
    for i, w in enumerate(toks):
        if NUM_RE.match(w["t"].replace("O", "0")):
            v = to_num(w["t"])
            if v is not None:
                out.append((i, v))
    return out


def _near(x, y, tol=0.002):
    return abs(x - y) <= max(1.0, abs(y) * tol)


_UNIT_FUZZY = ((re.compile(r"^\[?k[goa9]\]?$", re.I), "KG"), (re.compile(r"^\[?ea\]?$", re.I), "EA"),
               (re.compile(r"^\[?set\]?$", re.I), "SET"))


def _unit_of(t, fuzzy=False):
    """단위 단어 → 'KG'·'EA'… (아니면 None). fuzzy: O4 — `Ko`·`Ka`·`K9`·`[kg]`·`[ea]` 오독까지."""
    if t in UNITS:
        return t.upper()
    if fuzzy:
        for rx, u in _UNIT_FUZZY:
            if rx.match(t):
                return u
    return None


_TOTAL_KW = ("합계", "공급가액", "공급가", "명세합계", "총액", "소계", "부가세", "잔액", "미수")


def _is_total_line(text):
    t = str(text or "").replace(" ", "")
    return any(k in t for k in _TOTAL_KW)


def _solve(nums):
    """① a×b=c ② c+세액 쌍 → ((qi,q),(pi,p),(ci,c)), how — 못 찾으면 (None, None)."""
    # O2(2026-11-03): 금액 후보 c 의 바로 왼쪽 숫자가 ≈10×c 면 c 는 세액 → 후보에서 뺀다(명진 `112,100 11,210` 에서
    # 19×590(5,900 오독)=11,210 이 우연히 맞아 세액을 금액으로 잡던 것). 오른쪽 이웃이 ≈0.1×c(세액)인 후보를 먼저 본다.
    for ci in _amount_cands(nums):
        c = nums[ci][1]
        # 맞는 쌍(왼쪽=수량·중량, 오른쪽=단가) 중 금액에 가장 가까운 것 — 혜성 `289 KG 289 1,390` 은 뒤의 289(중량)
        pairs = [(ai, bi) for ai in range(ci) for bi in range(ai + 1, ci)
                 if nums[ai][1] > 0 and nums[bi][1] > 0 and abs(nums[ai][1] * nums[bi][1] - c) <= max(1.0, c * 0.001)]
        if pairs:
            ai, bi = max(pairs)
            return (nums[ai], nums[bi], nums[ci]), "mul"
    for ci in range(len(nums) - 1):
        c, v = nums[ci][1], nums[ci + 1][1]
        if c >= 100 and abs(c * 0.1 - v) <= max(1.0, c * 0.001):
            before = [n for n in nums[:ci] if n[1] > 0]
            if len(before) >= 2:
                a_i, p_i = before[-2], before[-1]
                price = c / a_i[1]
                if abs(price - p_i[1]) / max(price, 1) <= 0.15 or abs(price - round(price)) < 0.01:
                    return (a_i, (p_i[0], round(price)), nums[ci]), "vat"
            break
    return None, None


def _amount_cands(nums):
    cis = [ci for ci in range(len(nums) - 1, -1, -1)
           if nums[ci][1] >= 100 and not (ci > 0 and _near(nums[ci - 1][1], nums[ci][1] * 10))]
    cis.sort(key=lambda ci: not (ci + 1 < len(nums) and _near(nums[ci + 1][1], nums[ci][1] * 0.1)))
    return cis


def _one_digit_off(x, y):
    sx, sy = str(int(x)), str(int(y))
    return len(sx) == len(sy) and sum(a != b for a, b in zip(sx, sy)) == 1


def _fix_one_digit(nums):
    """O9(2026-11-03): 금액 c 왼쪽 두 숫자 a·b 중 하나가 한 자리 오독 — c/b 가 정수이고 a 와 한 자리만 다르면 a := c/b,
    대칭으로 b := c/a. 두리 `30 7,870 221,100` → 7,370 · 중앙연마 `209 300 89,700` → 299. 원래 값은 fixed_from."""
    for ci in _amount_cands(nums):
        if ci < 2:
            continue
        (ia, a), (ib, b), c = nums[ci - 2], nums[ci - 1], nums[ci][1]
        if min(a, b) <= 0 or any(v != int(v) for v in (a, b, c)):
            continue
        if c % b == 0 and _one_digit_off(c // b, a):
            return ((ia, float(c // b)), (ib, b), nums[ci]), "fix1", {"a": a}
        if c % a == 0 and _one_digit_off(c // a, b):
            return ((ia, a), (ib, float(c // a)), nums[ci]), "fix1", {"price": b}
    return None, None, None


def parse_line_items(lines):
    """줄 목록 → 라인 항목. ① a×b=c(±0.1%, c 는 오른쪽·≥100) ② c 와 세액(c×0.1) 쌍 → 앞의 두 숫자로 수량·단가.
    항목: item(정리본)·item_raw·unit(None 이면 화면이 거래처 최빈 단위)·a·price·amount·other_nums·how·line
    ·qty(KG 행의 수량 후보, 없으면 None)·qty_fix(`1.016`→1016 제안, 자동 치환 안 함)·remark(비고 제안)."""
    items = []
    for ln in lines:
        toks = normalize_tokens(ln["words"])
        # O6 보강: 첫 단어가 1~2자리 숫자이고 다음 단어가 숫자·단위가 아니면 줄번호 — 계산·품명에서 뺀다
        row_no = (len(toks) >= 3 and re.fullmatch(r"\d{1,2}", toks[0]["t"]) is not None
                  and not NUM_RE.match(toks[1]["t"]) and not _unit_of(toks[1]["t"], fuzzy=True))
        nums = [n for n in line_nums(toks) if not (row_no and n[0] == 0)]
        if len(nums) < 2:
            continue
        fixed_from = None
        found, how = _solve(nums)
        if not found:
            # O1 보강: 금액·단가 자리(오른쪽 두 숫자)의 `155.100` 은 천단위 점으로 다시 읽어 본다(중량 1.016 은 그대로)
            alt = [(i, float(toks[i]["t"].replace(".", "")) if (k >= len(nums) - 2 and _DOTS_ONE_RE.match(toks[i]["t"])) else v)
                   for k, (i, v) in enumerate(nums)]
            if alt != nums:
                found, how = _solve(alt)
                nums = alt if found else nums
        if not found and not _is_total_line(ln["text"]):
            found, how, fixed_from = _fix_one_digit(nums)
        if not found and not _is_total_line(ln["text"]) and len(nums) == 2                 and nums[0][1] >= 100 and _near(nums[0][1], nums[1][1], 0):
            # O10: 숫자가 단가·금액 둘뿐이고 같으면 수량 1 (수량 칸 `1` 을 `아`·`ｌ` 로 읽음)
            found, how = ((nums[0][0], 1.0), nums[0], nums[1]), "qty1"
        if not found:
            continue
        (qi, q), (pi, p), (ci, c) = found
        first = min(qi, pi, ci)
        # 단위: 정확한 표기는 줄 어디서든(기존), 퍼지(O4)는 숫자 칸(첫 숫자 이후)에서만 —
        # 위드열처리 품명 `HA50-80210 [KG]` 의 [KG] 는 품명 일부라 단위로 보지 않는다(시트 관행 EA, D4)
        unit = next((u for u in (_unit_of(w["t"]) for w in toks) if u), None) or \
            next((u for u in (_unit_of(w["t"], fuzzy=True) for w in toks[first:]) if u), None)
        # O5: KG 행 수량 = 중량(a) 바로 왼쪽 숫자. 단위·글자 단어는 건너뛰고, 숫자가 섞인 치수 단어(`28X97`·`700@×16`)를
        # 만나면 멈춘다(품명 속 숫자를 수량으로 잡지 않게). `1.016` 꼴(소수 셋째 자리, 정수부 1~9)은 천 단위 오독 제안값 qty_fix.
        qty = qty_i = qty_fix = None
        for j in range(qi - 1, -1, -1):
            t = toks[j]["t"]
            if NUM_RE.match(t.replace("O", "0")):
                qty, qty_i = to_num(t), j
                if re.match(r"^[1-9]\.\d{3}$", t):
                    qty_fix = round(qty * 1000)
                break
            if _unit_of(t, fuzzy=True) or not re.search(r"\d", t):
                continue
            break
        cut = min(first, qty_i) if (unit == "KG" and qty_i is not None) else first
        text_words = [w["t"] for w in toks[(1 if row_no else 0):cut]
                      if w["t"] not in UNITS and not re.match(r"^\d{2}/\d{2}$", w["t"])]
        other = [v for i, v in nums if i not in (qi, pi, ci) and i < ci]
        raw = " ".join(text_words).strip()
        # O8: 줄 끝 `/4S25ABV-FL-01-X156`(소재가 쓰일 제품 품번) → 비고 제안
        rm = _REMARK_RE.match(toks[-1]["t"]) if toks else None
        items.append({"item": clean_item(raw), "item_raw": raw, "unit": unit, "a": q,
                      "price": float(p), "amount": c, "other_nums": other, "how": how, "line": ln["text"],
                      "qty": qty, "qty_fix": qty_fix, "remark": rm.group(1) if rm else None,
                      "fixed_from": fixed_from})
    return items


def find_totals(lines, items):
    s = round(sum(i["amount"] for i in items))
    cands, all_nums = [], set()
    for ln in lines:
        txt = ln["text"].replace(" ", "")
        toks = normalize_tokens(ln["words"])
        nums = [round(v) for _, v in line_nums(toks) if v >= 1000]
        # 천단위 점 한 개(`117.600`)도 합계 대조용으로는 함께 본다(O1 보강)
        nums += [int(w["t"].replace(".", "")) for w in toks if _DOTS_ONE_RE.match(w["t"])]
        all_nums.update(nums)
        if any(k in txt for k in ("합계", "공급가액", "공급가", "명세합계", "총액", "소계", "부가세")):
            cands += nums
    vat_seen = round(s * 0.1) in all_nums
    return s, sorted(set(cands)), (s in cands) or (s in all_nums and vat_seen), vat_seen


def _name_key(name):
    return re.sub(r"[()\[\]]", "", vendor_key(name))


def find_vendor(words, biz_map, our_biz="6060214529", names=None):
    """본문 숫자열에 등록 사업자번호(10자리)가 들어 있으면 그 거래처.
    O11(2026-11-03): 번호로 못 찾고 names(거래처 dict 목록)를 주면, 본문을 공백 없이 이어 붙인 글자에 상호 키(법인 표기·
    공백·괄호 제거, 3자 이상)가 **하나만** 들어 있을 때 그 거래처(둘 이상이면 None). 우성정밀(우리) 번호의 거래처는 제외."""
    digits = re.sub(r"\D", "", "".join(w["t"] for w in words))
    for b, v in biz_map.items():
        if b != our_biz and len(b) == 10 and b in digits:
            return v
    if not names:
        return None
    text = _name_key("".join(w["t"] for w in words))
    hits, seen = [], set()
    for v in names:
        k = _name_key(v.get("name"))
        if len(k) >= 3 and k in text and k != "우성정밀" and re.sub(r"\D", "", str(v.get("business_no") or "")) != our_biz                 and k not in seen:
            seen.add(k)
            hits.append(v)
    return hits[0] if len(hits) == 1 else None


_DATE_NEN_RE = re.compile(r"(?<!\d)(20\d\d)\d{1,2}\s+(\d{1,2})\D{0,3}?\s*(\d{1,2})(?!\d)")
_DATE_MD_RE = re.compile(r"(?<!\d)(\d{1,2})\s*[월%]\s*(\d{1,2})(?!\d)")    # O3b: `10월 28일`·`10% 28 일`
_DATE_KW = ("거래일", "일자", "Date", "DATE", "년")


def find_date(words, today=None):
    """거래일. O3(2026-11-03): 후보를 전부 모아 오늘+7 초과·오늘−400 미만을 빼고, '일자·Date·년·거래일' 글자에
    가장 가까운 후보(없으면 첫 후보). 남는 후보가 없으면 None(화면은 오늘 기본 + '날짜 미식별').
    후보: ① 숫자열 이어 붙인 본문의 20xx 년·월·일 ② '2026년' 의 년을 숫자로 읽은 꼴(`202611 10g 19` → 10-19)
    ③ O3b 월·일(`10% 28 일`, '월' 을 %로 읽음) + 가장 가까운 20xx 연도(`20269` 는 2026, 없으면 올해).
    연·월·일 사이에 구분 글자가 있는 후보(`2026/10/23`·③)가 숫자가 붙은 후보(`2026910` → 9-10)보다 먼저.
    연도 오독(2020 이전)은 올해로 — 단 '월' 이 함께 있는 꼴만(`2006 9 월 16 일`, 금액 속 2000 은 제외), 미래가 되면 작년."""
    today = today or dt.date.today()
    lo, hi = today - dt.timedelta(days=400), today + dt.timedelta(days=7)
    text = "".join(w["t"] for w in words)
    spaced = " ".join(w["t"] for w in words)
    cands = []                                   # (본문 위치, 날짜, 구분 글자 있음)

    def _add(pos, y, mo, d, misread_ok, strong=True):
        if not (1 <= mo <= 12 and 1 <= d <= 31):
            return
        if y < 2020:
            if not misread_ok:
                return
            y = today.year if dt.date(today.year, mo, min(d, 28)) <= hi else today.year - 1
        try:
            cands.append((pos, dt.date(y, mo, d), strong))
        except ValueError:
            pass

    for s in re.finditer(r"(?=20\d\d)", text):
        m = DATE_RE.match(text, s.start())
        if m:
            _add(m.start(), int(m.group(1)), int(m.group(2)), int(m.group(3)), "월" in m.group(0),
                 m.start(2) > m.end(1) and m.start(3) > m.end(2))
    for m in _DATE_NEN_RE.finditer(spaced):
        _add(len(spaced[:m.start()].replace(" ", "")), int(m.group(1)), int(m.group(2)), int(m.group(3)), False)
    years = [(m.start(), int(m.group(1))) for m in re.finditer(r"(?<!\d)(20\d\d)", spaced)]
    for m in _DATE_MD_RE.finditer(spaced):
        y = min(years, key=lambda t: abs(t[0] - m.start()))[1] if years else 0    # 0 → 올해(미래면 작년)
        _add(len(spaced[:m.start()].replace(" ", "")), y, int(m.group(1)), int(m.group(2)), True)
    cands = [c for c in cands if lo <= c[1] <= hi]
    if any(c[2] for c in cands):
        cands = [c for c in cands if c[2]]
    if not cands:
        return None
    kws = [i for k in _DATE_KW for i in [m.start() for m in re.finditer(re.escape(k), text)]]
    if kws:
        return min(cands, key=lambda c: (min(abs(c[0] - k) for k in kws), c[0]))[1].isoformat()
    return min(cands, key=lambda c: c[0])[1].isoformat()


_LEAD_DATE_RE = re.compile(r"^(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2})\s+")
_STS_OCR_RE = re.compile(r"^[56]?[5S][1Il\[][5S](?=3\d\d|4\d\d|630)")   # 515304·6515304·5[5316 → STS304·STS316
_REMARK_RE = re.compile(r"^/([A-Z0-9-]{4,})$")


def clean_item(text):
    """O6(2026-11-03) 품명 정리 — 앞의 날짜(`2026-10-28`·`10/14`), 끝의 외톨이 숫자(1~3자리)·기호 단어 떼기,
    재질 오독 `515304`→`STS304`·`STS3048`→`STS304`, `환 봉`·`육 각` 붙이기. 결과가 비면 원문."""
    s = _LEAD_DATE_RE.sub("", str(text or "").strip())
    s = _STS_OCR_RE.sub("STS", s)
    s = re.sub(r"STS3048(?!\d)", "STS304", s)
    s = s.replace("환 봉", "환봉").replace("육 각", "육각")
    toks = s.split()
    # 치수 구분자 바로 뒤 숫자(`140? ＊ 19` 의 19)는 치수라 남긴다
    while len(toks) > 1 and re.fullmatch(r"\d{1,3}|[/&=|_.,~-]", toks[-1]) and \
            not (toks[-1][0].isdigit() and re.search(r"[*xX×＊#¢@?+]$", toks[-2])):
        toks.pop()
    return " ".join(toks) or str(text or "").strip()


def ocr_dims(text):
    out = []
    for m in DIMS_RE.finditer(text):
        d, L = float(m.group(1)), float(m.group(2))
        out.append((d, L))
        if d >= 100 and d % 10 == 0:
            out.append((d / 10, L))
    return out


def match_item(ocr_text, known, price=None):
    """known: {item_key: (원문, 최근 단가)} (최근 것이 뒤). 반환 (원문, 점수, 방식) 또는 (None, 0, None)."""
    if not known:
        return None, 0, None
    from rapidfuzz import fuzz, process
    g = norm_grade(ocr_text)
    dims = ocr_dims(ocr_text)
    if g and dims:
        same = [k for k, (raw, _) in known.items()
                if norm_grade(raw) == g and norm_dims(raw) and any(norm_dims(raw)[1:] == d for d in dims)]
        if len(same) == 1:
            return known[same[0]][0], 100, "dims"
        if len(same) > 1:
            sp = [k for k in same if price and known[k][1] and abs(known[k][1] - price) < 1]
            if len(sp) == 1:
                return known[sp[0]][0], 100, "dims+price"
            return known[same[-1]][0], 95, "dims(variants)"
    k = item_key(ocr_text)
    keys = list(known)
    m = process.extractOne(k, keys, scorer=fuzz.token_set_ratio)
    m2 = process.extractOne(k, keys, scorer=fuzz.ratio)
    best = max([x for x in (m, m2) if x], key=lambda x: x[1], default=None)
    if not best:
        return None, 0, None
    sc = best[1]
    if price and known[best[0]][1] and abs(known[best[0]][1] - price) < 1:
        sc = min(100, sc + 15)
    return known[best[0]][0], round(sc), "fuzzy"


def build_known(ledger_rows):
    """장부 행(vendor, item, unit_price; ledger_id 순) → {vendor_key: {item_key: (원문, 최근 단가)}}"""
    out = defaultdict(dict)
    for r in ledger_rows:
        out[vendor_key(r.get("vendor"))][item_key(r.get("item"))] = (r.get("item"), float(r.get("unit_price") or 0))
    return out


MATCH_AUTO_MIN = 80     # O7: 제안 점수가 이 값 이상일 때만 저장 품명 기본값으로


def ocr_row_defaults(it, unit_mode=None):
    """O7·O4·O5(2026-11-03) 검토 표 한 줄의 기본값 — 순수 함수.
    저장 품명: 제안 점수 ≥ 80 이면 제안, 아니면 OCR 품명(정리본). 단위: 판독 단위 → 거래처 최빈 단위 → EA.
    KG 행: 수량 = qty(없으면 None = 빈칸), 중량 = a. 그 외: 수량 = a. note: 수량 `1.016` 꼴이면 1,016 오독 안내 한 줄."""
    unit = (it.get("unit") or unit_mode or "EA").upper()
    kg = unit == "KG"
    sc = it.get("match_score") or 0
    q = it.get("qty") if kg else it["a"]
    note = None
    if kg and it.get("qty_fix") and q is not None:
        note = f"수량 {q:g} 은 {it['qty_fix']:,} 오독일 수 있습니다(소수점)"
    return {"save_item": it["match"] if (it.get("match") and sc >= MATCH_AUTO_MIN) else it["item"],
            "ocr_item": it["item"], "score": sc, "unit": unit,
            "qty": (float(q) if q is not None else None), "weight": (float(it["a"]) if kg else None),
            "price": float(it["price"]), "amount": float(it["amount"]), "vat": float(round(it["amount"] * 0.1)),
            "remark": it.get("remark") or "", "note": note}


def vendor_unit_mode(ledger_rows):
    """O4(2026-11-03): 장부 행(vendor, unit) → {vendor_key: 가장 많이 쓴 단위}. 판독 줄에 단위가 안 읽히면
    검토 표 단위 기본값으로 쓴다(명진=KG, 성보=EA). 같은 횟수면 먼저 나온 단위."""
    cnt = defaultdict(Counter)
    for r in ledger_rows:
        u = str(r.get("unit") or "").strip().upper()
        if u:
            cnt[vendor_key(r.get("vendor"))][u] += 1
    return {k: c.most_common(1)[0][0] for k, c in cnt.items()}


# ─────────────────────────── 문서 한 건 ───────────────────────────
def parse_document(file_bytes, name, biz_map, known_by_vendor, psms=(6, 11, 4), vendors=None):
    """→ [{page, vendor(dict|None), vendor_how('biz'|'name'|None), date, items[{item, unit, a, price, amount, how, match}],
           sum, printed_totals, total_ok, vat_seen, rot, psm}]. OCR 엔진이 없으면 RuntimeError.
    vendors: 상호 폴백(O11)용 거래처 목록 — 없으면 biz_map 의 거래처들."""
    if not ocr_available():
        raise RuntimeError("OCR 엔진(Tesseract)이 없습니다")
    pages = []
    for pno, img in enumerate(render_pages(file_bytes, name), 1):
        rot = best_rotation(img)
        if rot:
            img = img.rotate(rot, expand=True)
        best = None
        for psm in psms:
            words = _image_to_words(img, psm)
            lines = group_lines(words)
            items = parse_line_items(lines)
            s, cands, ok, vat_seen = find_totals(lines, items)
            score = (ok, len(items))
            if best is None or score > best[0]:
                best = (score, psm, words, lines, items, s, cands, ok, vat_seen)
        _, psm, words, lines, items, s, cands, ok, vat_seen = best
        vend = find_vendor(words, biz_map)
        vhow = "biz" if vend else None
        if not vend:
            vend = find_vendor(words, {}, names=vendors if vendors is not None else list(biz_map.values()))
            vhow = "name" if vend else None
        known = known_by_vendor.get(vendor_key(vend["name"]), {}) if vend else {}
        for it in items:
            raw, sc, how = match_item(it["item"], known, it["price"])
            it["match"] = raw
            it["match_score"] = sc
            it["match_how"] = how
        pages.append({"page": pno, "rot": rot, "psm": psm, "vendor": vend, "vendor_how": vhow,
                      "date": find_date(words), "items": items,
                      "sum": s, "printed_totals": cands, "total_ok": ok, "vat_seen": vat_seen,
                      "lines": [l["text"] for l in lines]})
    return pages
