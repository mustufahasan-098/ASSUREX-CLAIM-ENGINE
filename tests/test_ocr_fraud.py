"""AssureX automated OCR + fraud-layer tests (reuses proven self-tests)."""
import io
from datetime import date, timedelta

from PIL import Image, ImageDraw
from PIL import Image, ImageDraw, ImageFont
from src import fraud_intel as fi
from src import ocr_service

PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    PASS += ok
    FAIL += (not ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}"
                                                    if detail and not ok
                                                    else ""))


def receipt(title, serial):
    img = Image.new("RGB", (640, 420), "white")
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 22)
        fb = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 26)
    except OSError:
        f = fb = ImageFont.load_default()
    lines = [("DEMO ELECTRONICS STORE", fb), ("TAX INVOICE", f),
             (f"Item: {title}", f), (f"Serial No: {serial}", f),
             (f"Date: {(date.today() - timedelta(days=200)).strftime('%d-%m-%Y')}", f),
             ("Invoice: INV-T1", f), ("Total: Rs 89,999.00", f)]
    y = 26
    for text, font in lines:
        d.text((36, y), text, font=font, fill="black")
        y += 46
    return img


def run():
    product = {"brand": "Samsung", "model": "Galaxy S22",
               "serial_number": "SNTEST0001",
               "purchase_date": (date.today() - timedelta(days=200)
                                 ).isoformat()}

    ok_receipt = receipt("Samsung Galaxy S22 Smartphone", "SNTEST0001")
    info = ocr_service.extract_receipt_info(ok_receipt)
    v = ocr_service.verify_against_product(info, product)
    check("OCR: matching receipt = verified", v["verdict"] == "verified",
          v["summary"])

    bad_receipt = receipt("Apple iPhone 14 Pro", "SNOTHER9999")
    info2 = ocr_service.extract_receipt_info(bad_receipt)
    v2 = ocr_service.verify_against_product(info2, product)
    check("OCR: wrong-brand receipt = mismatch", v2["verdict"] == "mismatch",
          v2["summary"])

    q = ocr_service.image_quality(Image.new("RGB", (100, 80), (5, 5, 5)))
    check("Quality: dark tiny image rejected", q["ok"] is False)

    # fraud layers (subset of the 12/12 suite)
    original = receipt("Samsung Galaxy S22", "SNTEST0001")
    b1, b2 = io.BytesIO(), io.BytesIO()
    original.save(b1, "PNG")
    original.save(b2, "JPEG", quality=50)
    h1 = fi.dhash_from_bytes(b1.getvalue())
    h2 = fi.dhash_from_bytes(b2.getvalue())
    check("Fraud: pHash catches re-saved same image",
          fi.hamming(h1, h2) <= fi.SIMILAR_THRESHOLD)
    check("Fraud: price outlier detection",
          bool(fi.price_signal({"product_category": "Power Tools",
                                "purchase_price": 15000.0})))

    print(f"\nOCR/FRAUD SUITE: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)