# -*- coding: utf-8 -*-
"""거래명세서 스캔 판독 — 내부 OCR(Tesseract) + 장부 연관성 매칭 (2026-10-16, 매입 내재화 2단계).

사용자 결정(2026-10-15): 외부 API 대신 내부 OCR, 거래처 양식은 몇 종이므로 "내부 DB 연관성" 위주로 맞추고
입력자가 검토·수정 후 확정한다.

흐름 (parse_document):
  파일(PDF/이미지) → 페이지 렌더(300dpi, 그레이·이진화) → 방향 보정(0/90/180/270 중 OCR 신뢰도 최고)
  → 단어 OCR(kor+eng, psm 6/11/4 중 라인 수·합계 검증이 가장 좋은 것) → 줄 묶기
  → 거래처: 본문 숫자열에서 등록 사업자번호 검색(우성정밀 제외) → 거래일(첫 20xx 날짜, 2020 이전이면 올해)
  → 라인: ① 수량×단가=금액(±0.1%) ② 금액+세액(10%) 쌍에서 수량·단가 복원 → 품명 = 첫 숫자 앞 글자
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
from collections import defaultdict

from utils.purchase_sync import vendor_key, item_key, norm_grade, norm_dims

NUM_RE = re.compile(r"^[\d,]+(?:\.\d+)?\.?$")
UNITS = {"EA", "KG", "Kg", "kg", "SET", "CH", "식", "M", "본"}
DATE_RE = re.compile(r"(20\d\d)\D{0,6}(\d{1,2})\D{0,6}(\d{1,2})")
DIMS_RE = re.compile(r"(\d+(?:\.\d+)?)[^\dxX×*]{0,3}[*xX×]\s*(\d+(?:\.\d+)?)")
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


def line_nums(toks):
    out = []
    for i, w in enumerate(toks):
        if NUM_RE.match(w["t"].replace("O", "0")):
            v = to_num(w["t"])
            if v is not None:
                out.append((i, v))
    return out


def parse_line_items(lines):
    """줄 목록 → 라인 항목. ① a×b=c(±0.1%, c 는 오른쪽·≥100) ② c 와 세액(c×0.1) 쌍 → 앞의 두 숫자로 수량·단가."""
    items = []
    for ln in lines:
        toks = ln["words"]
        nums = line_nums(toks)
        if len(nums) < 2:
            continue
        found, how = None, None
        for ci in range(len(nums) - 1, -1, -1):
            c = nums[ci][1]
            if c < 100:
                continue
            for ai in range(ci):
                for bi in range(ci):
                    if ai != bi and nums[ai][1] > 0 and nums[bi][1] > 0 and abs(nums[ai][1] * nums[bi][1] - c) <= max(1.0, c * 0.001):
                        found, how = (nums[ai], nums[bi], nums[ci]), "mul"
                        break
                if found:
                    break
            if found:
                break
        if not found:
            for ci in range(len(nums) - 1):
                c, v = nums[ci][1], nums[ci + 1][1]
                if c >= 100 and abs(c * 0.1 - v) <= max(1.0, c * 0.001):
                    before = [n for n in nums[:ci] if n[1] > 0]
                    if len(before) >= 2:
                        a_i, p_i = before[-2], before[-1]
                        price = c / a_i[1]
                        if abs(price - p_i[1]) / max(price, 1) <= 0.15 or abs(price - round(price)) < 0.01:
                            found, how = (a_i, (p_i[0], round(price)), nums[ci]), "vat"
                    break
        if not found:
            continue
        (qi, q), (pi, p), (ci, c) = found
        first = min(qi, pi, ci)
        unit = next((w["t"] for w in toks if w["t"] in UNITS), None)
        text_words = [w["t"] for w in toks[:first] if w["t"] not in UNITS and not re.match(r"^\d{2}/\d{2}$", w["t"])]
        other = [v for i, v in nums if i not in (qi, pi, ci) and i < ci]
        items.append({"item": " ".join(text_words).strip(), "unit": (unit.upper() if unit else None), "a": q,
                      "price": float(p), "amount": c, "other_nums": other, "how": how, "line": ln["text"]})
    return items


def find_totals(lines, items):
    s = round(sum(i["amount"] for i in items))
    cands, all_nums = [], set()
    for ln in lines:
        txt = ln["text"].replace(" ", "")
        nums = [round(v) for _, v in line_nums(ln["words"]) if v >= 1000]
        all_nums.update(nums)
        if any(k in txt for k in ("합계", "공급가액", "공급가", "명세합계", "총액", "소계")):
            cands += nums
    vat_seen = round(s * 0.1) in all_nums
    return s, sorted(set(cands)), (s in cands) or (s in all_nums and vat_seen), vat_seen


def find_vendor(words, biz_map, our_biz="6060214529"):
    """본문 숫자열에 등록 사업자번호(10자리)가 들어 있으면 그 거래처."""
    digits = re.sub(r"\D", "", "".join(w["t"] for w in words))
    for b, v in biz_map.items():
        if b != our_biz and len(b) == 10 and b in digits:
            return v
    return None


def find_date(words):
    text = "".join(w["t"] for w in words)
    for m in DATE_RE.finditer(text):
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            if y < 2020:
                y = dt.date.today().year
            try:
                return dt.date(y, mo, d).isoformat()
            except ValueError:
                continue
    return None


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


# ─────────────────────────── 문서 한 건 ───────────────────────────
def parse_document(file_bytes, name, biz_map, known_by_vendor, psms=(6, 11, 4)):
    """→ [{page, vendor(dict|None), date, items[{item, unit, a, price, amount, how, match}], sum, printed_totals,
           total_ok, vat_seen, rot, psm}]. OCR 엔진이 없으면 RuntimeError."""
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
        known = known_by_vendor.get(vendor_key(vend["name"]), {}) if vend else {}
        for it in items:
            raw, sc, how = match_item(it["item"], known, it["price"])
            it["match"] = raw
            it["match_score"] = sc
            it["match_how"] = how
        pages.append({"page": pno, "rot": rot, "psm": psm, "vendor": vend, "date": find_date(words), "items": items,
                      "sum": s, "printed_totals": cands, "total_ok": ok, "vat_seen": vat_seen,
                      "lines": [l["text"] for l in lines]})
    return pages
