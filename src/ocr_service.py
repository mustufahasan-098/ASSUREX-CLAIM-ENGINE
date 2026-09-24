"""AssureX Document Intelligence - OCR extraction + product verification.

Tesseract-based receipt extraction (SRS req vi) with cross-verification
against the registered product (req vii, xxvii):
  - brand cross-check (keyword lexicon)     -> an iPhone receipt submitted
    for a Samsung product is detected
  - serial-number cross-check               -> req xxvii
  - purchase-date proximity check
  - image quality checks (resolution, brightness, OCR confidence)

Fully local: Tesseract engine, no external APIs (SRS 1.10.15). Every
check returns explainable reasons rendered by the UI and stored on the
claim record.
"""
import re
import shutil
from datetime import timedelta
from difflib import SequenceMatcher
from pathlib import Path

from PIL import ImageStat

from .features import parse_date

# ------------------------------------------------------------------ engine
TESSERACT_FALLBACKS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]
_PYTESSERACT = None
_ENGINE_ERR = None


def _get_pytesseract():
    global _PYTESSERACT, _ENGINE_ERR
    if _PYTESSERACT is not None or _ENGINE_ERR:
        return _PYTESSERACT, _ENGINE_ERR
    try:
        import pytesseract
    except ImportError:
        _ENGINE_ERR = "pytesseract package missing (pip install pytesseract)"
        return None, _ENGINE_ERR
    if shutil.which("tesseract"):
        _PYTESSERACT = pytesseract
        return pytesseract, None
    for path in TESSERACT_FALLBACKS:
        if Path(path).exists():
            pytesseract.pytesseract.tesseract_cmd = path
            _PYTESSERACT = pytesseract
            return pytesseract, None
    _ENGINE_ERR = ("Tesseract ENGINE not installed. Download the Windows "
                   "installer from https://github.com/UB-Mannheim/tesseract/wiki "
                   "(default options), then restart the terminal AND Flask.")
    return None, _ENGINE_ERR


# ------------------------------------------------------------ brand lexicon
BRAND_KEYWORDS = {
    "Samsung": ["samsung", "galaxy"],
    "Sony": ["sony", "bravia", "playstation"],
    "LG": ["lg"],
    "Xiaomi": ["xiaomi", "redmi", "poco"],
    "HP": ["hp", "pavilion"],
    "Apple": ["apple", "iphone", "ipad", "macbook"],
    "Dell": ["dell", "inspiron", "vostro", "xps"],
    "Lenovo": ["lenovo", "ideapad", "thinkpad"],
    "Whirlpool": ["whirlpool"],
    "Bosch": ["bosch"],
    "IFB": ["ifb"],
    "Godrej": ["godrej"],
    "DeWalt": ["dewalt"],
    "Makita": ["makita"],
    "Black+Decker": ["black\\+decker", "black and decker"],
    "Stanley": ["stanley"],
}

DATE_RE = re.compile(r"\b(\d{1,2}[./-]\d{1,2}[./-]\d{4})\b")
AMOUNT_RE = re.compile(r"(?:rs\.?|pkr|\$)\s*([\d,]{3,8}(?:\.\d{2})?)", re.I)
INVOICE_RE = re.compile(r"\b(?:inv|invoice)\s*[.:#-]*\s*([A-Za-z0-9-]{3,12})",
                        re.I)
SERIAL_RE = re.compile(
    r"\b(?:s/?n|serial(?:\s*(?:no|number))?)\s*[.:#-]*\s*([A-Za-z0-9-]{5,16})",
    re.I)


def _word_in(word, text):
    return re.search(rf"\b{re.escape(word)}\b", text) is not None


# ---------------------------------------------------------------- extract
def extract_receipt_info(image):
    """OCR a receipt image and return structured fields + quality stats."""
    pyt, err = _get_pytesseract()
    if pyt is None:
        return {"available": False, "note": err}
    try:
        img = image.convert("RGB")
        text = pyt.image_to_string(img, config="--psm 6")
        data = pyt.image_to_data(img, config="--psm 6",
                                 output_type=pyt.Output.DICT)
        confs = [float(c) for c in data["conf"] if float(c) > 0]
        words = [w for w, c in zip(data["text"], data["conf"])
                 if str(w).strip() and float(c) > 0]
    except Exception as e:
        return {"available": False, "note": f"OCR engine error: {e}"}

    low = text.lower()
    brands = [b for b, kws in BRAND_KEYWORDS.items()
              if any(_word_in(kw, low) for kw in kws)]

    dates = []
    for raw in DATE_RE.findall(text):
        try:
            dates.append(parse_date(raw.replace(".", "-")).isoformat())
        except Exception:
            continue

    return {
        "available": True,
        "brands": brands,
        "dates": dates,
        "serials": [m.upper() for m in SERIAL_RE.findall(text)][:3],
        "invoices": INVOICE_RE.findall(text)[:3],
        "amounts": AMOUNT_RE.findall(text)[:5],
        "confidence": round(sum(confs) / len(confs)) if confs else 0,
        "word_count": len(words),
        "text_preview": text.strip()[:300],
        "_text": text.lower(),
    }


# ---------------------------------------------------------------- quality
def image_quality(image):
    """Basic evidence-quality gate for uploaded photos (resolution +
    exposure). Catches dark/tiny/overexposed evidence before review."""
    w, h = image.size
    mean = ImageStat.Stat(image.convert("L")).mean[0]
    notes = []
    ok = True
    if w < 400 or h < 300:
        notes.append(f"low resolution ({w}x{h})")
        ok = False
    if mean < 40:
        notes.append("image too dark")
        ok = False
    elif mean > 235:
        notes.append("image overexposed")
        ok = False
    return {"ok": ok, "notes": notes, "size": f"{w}x{h}"}


# ---------------------------------------------------------------- verify
def verify_against_product(info, product):
    """Cross-check extracted receipt fields against the registered product
    (SRS req vii + xxvii). Verdict: verified | mismatch | inconclusive."""
    if not info or not info.get("available"):
        return {"verdict": "none",
                "summary": "No OCR data available to verify."}

    notes, mismatches = [], []
    p_brand = (product.get("brand") or "").strip()
    p_model = (product.get("model") or "").strip().lower()
    p_serial = (product.get("serial_number") or "").strip().upper()
    p_date = parse_date(product.get("purchase_date") or "")

    low = info.get("_text", "")

    # ---- 1. brand cross-check (the iPhone-for-Samsung detector)
    found = info.get("brands") or []
    brand_match = False
    if found:
        if p_brand.lower() in [b.lower() for b in found]:
            brand_match = True
            notes.append(f"Brand matches receipt ({found[0]})")
        else:
            mismatches.append(f"Receipt mentions {', '.join(found)} but the "
                              f"registered product is a {p_brand}")
    elif p_brand and _word_in(p_brand.lower(), low):
        brand_match = True
        notes.append(f"Brand '{p_brand}' found on receipt")

    # ---- 2. model mention
    if p_model and p_model in low:
        notes.append(f"Model '{product.get('model')}' appears on receipt")

    # ---- 3. serial cross-check (req xxvii)
    serial_match = False
    serials = info.get("serials") or []
    if p_serial and serials:
        def serial_close(a, b):
            # OCR confuses O/0, I/1, S/5, B/8 - compare with a normalised
            # alphabet and a similarity threshold instead of exact equality.
            norm = lambda s: s.upper().replace("O", "0").replace("I", "1") \
                              .replace("S", "5").replace("B", "8")
            if norm(a) == norm(b):
                return True
            return SequenceMatcher(None, norm(a), norm(b)).ratio() >= 0.85
        if any(serial_close(p_serial, s) for s in serials):
            serial_match = True
            notes.append("Serial number matches the registered product")
        else:
            mismatches.append("Serial on receipt does not match the "
                              "registered product serial")

    # ---- 4. purchase-date proximity
    if p_date:
        best = None
        for d in info.get("dates", []):
            dd = parse_date(d)
            if dd:
                dist = abs((dd - p_date).days)
                best = dist if best is None else min(best, dist)
        if best is not None:
            if best <= 45:
                notes.append("Receipt date consistent with purchase date")
            elif best > 365:
                notes.append("Receipt date is far from the registered "
                             "purchase date")

    # ---- quality annotation
    if info.get("word_count", 0) < 8:
        notes.append("Very little text detected - receipt may be "
                     "low quality or not a receipt")

        # a serial-only mismatch with matching brand is suspicious but not
    # conclusive - route it to review rather than failing outright
    soft_serial = (len(mismatches) == 1
                   and mismatches[0].startswith("Serial on receipt")
                   and (brand_match or serial_match))
    if mismatches and not soft_serial:
        return {"verdict": "mismatch",
                "summary": "; ".join(mismatches + notes)}
    if mismatches and soft_serial:
        return {"verdict": "inconclusive",
                "summary": "; ".join(mismatches + notes)}
    if brand_match or serial_match:
        return {"verdict": "verified", "summary": "; ".join(notes)}
    return {"verdict": "inconclusive",
            "summary": "; ".join(notes) or
            "Could not read enough information to verify the receipt"}