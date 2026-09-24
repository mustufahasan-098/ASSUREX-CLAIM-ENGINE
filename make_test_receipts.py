"""Self-test: generates a matching receipt and a wrong-brand receipt,
then runs the real OCR + verification pipeline on both."""
from datetime import date, timedelta

from PIL import Image, ImageDraw, ImageFont

from src import ocr_service


def make_receipt(item_line, serial, out):
    img = Image.new("RGB", (640, 420), "white")
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 22)
        fb = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 26)
    except OSError:
        f = fb = ImageFont.load_default()
    lines = [("DEMO ELECTRONICS STORE", fb), ("TAX INVOICE", f),
             (f"Item: {item_line}", f), (f"Serial No: {serial}", f),
             (f"Date: {(date.today() - timedelta(days=200)).strftime('%d-%m-%Y')}", f),
             ("Invoice: INV-TEST-001", f), ("Total: Rs 89,999.00", f)]
    y = 26
    for text, font in lines:
        d.text((36, y), text, font=font, fill="black")
        y += 46
    img.save(out)
    return img


product = {"brand": "Samsung", "model": "Galaxy S22",
           "serial_number": "SNTEST0001",
           "purchase_date": (date.today() - timedelta(days=200)).isoformat()}

ok = make_receipt("Samsung Galaxy S22 Smartphone", "SNTEST0001",
                  "test_receipt_samsung.png")
bad = make_receipt("Apple iPhone 14 Pro", "SNOTHER9999",
                   "test_receipt_apple.png")

for name, img in [("SAMSUNG receipt (expect: verified)", ok),
                  ("APPLE receipt (expect: mismatch)", bad)]:
    info = ocr_service.extract_receipt_info(img)
    v = ocr_service.verify_against_product(info, product)
    print(f"\n=== {name} ===")
    print("  brands:", info.get("brands"), "| serials:", info.get("serials"),
          "| dates:", info.get("dates"), "| conf:", info.get("confidence"))
    print("  verdict:", v["verdict"], "-", v["summary"])