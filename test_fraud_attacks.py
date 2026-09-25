"""Fraud-intelligence self-test: simulates every attack family against the
REAL detection logic. No Firestore writes - all inputs are synthetic."""
import io
from datetime import date, datetime, timedelta

from PIL import Image, ImageDraw

from src import fraud_intel as fi

passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    passed += ok
    failed += (not ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  - {detail}"
                                                    if detail else ""))


def make_receipt(title, fmt=None, quality=95):
    img = Image.new("RGB", (640, 300), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 640, 40], fill="black")          # header band
    d.text((30, 60), title, fill="black")
    d.text((30, 120), "Total: Rs 89,999.00", fill="black")
    d.text((30, 150), "Serial No: SNTEST0001", fill="black")
    d.rectangle([30, 200, 300, 230], fill="gray")       # content block
    # the drill version gets a visually distinct layout
    if "DRILL" in title:
        img = img.rotate(4, expand=False, fillcolor="white")
    buf = io.BytesIO()
    img.save(buf, fmt or "PNG", quality=quality)
    return buf.getvalue()


# ---- layer 1: perceptual fingerprint
original = make_receipt("SAMSUNG GALAXY S22")
resaved = make_receipt("SAMSUNG GALAXY S22", "JPEG", quality=55)   # re-compressed
different = make_receipt("BOSCH GSR 18V DRILL")
h1, h2, h3 = (fi.dhash_from_bytes(x) for x in (original, resaved, different))
check("pHash: re-saved copy of same image detected",
      fi.hamming(h1, h2) <= fi.SIMILAR_THRESHOLD, f"hamming={fi.hamming(h1, h2)}")
check("pHash: different image NOT flagged",
      fi.hamming(h1, h3) > fi.SIMILAR_THRESHOLD, f"hamming={fi.hamming(h1, h3)}")

# ---- layer 4: price reasonableness
sig = fi.price_signal({"product_category": "Power Tools",
                       "purchase_price": 15000.0})
check("Price outlier: Rs 15,000 drill flagged",
      len(sig) == 1, sig[0][2] if sig else "")
check("Price normal: Rs 180 drill not flagged",
      fi.price_signal({"product_category": "Power Tools",
                       "purchase_price": 180.0}) == [])

# ---- layers 2+3: velocity + behavior
iso = lambda d: (datetime.now() - timedelta(days=d)).isoformat(timespec="seconds")
burst = [{"created_at": iso(d), "status": "Under Evaluation"}
         for d in (1, 2, 5)]
check("Velocity: 3 claims in 7 days flagged",
      any(c == "velocity_burst" for c, _, _ in fi.velocity_signals(burst, [])))
check("Velocity: calm history not flagged", fi.velocity_signals([], []) == [])
repeat = [{"fault_category": "motor_failure"}] * 2
check("Repeated fault on same serial flagged",
      any(c == "repeat_fault" for c, _, _ in fi.velocity_signals([], repeat)))

# ---- layer 5: cross-user network
others = [{"owner_email": "other@x.com", "doc_hashes": ["ABC123"]}]
sig = fi.network_signals(others, "me@x.com", ["ABC123"], [])
check("Cross-user document reuse = 40 pts",
      sig and sig[0][0] == "cross_user_doc" and sig[0][1] == 40,
      sig[0][2] if sig else "")
check("Same-user reuse NOT counted as network fraud",
      fi.network_signals(others, "other@x.com", ["ABC123"], []) == [])

# ---- layer 6: OCR weighting
check("OCR inconclusive = 10 pts",
      fi.ocr_signal({"verdict": "inconclusive"})[0][1] == 10)
check("OCR verified = no signal",
      fi.ocr_signal({"verdict": "verified"}) == [])

# ---- layer 7: combinatorial escalation
claim = {"user_id": "me@x.com", "product_category": "Power Tools",
         "purchase_price": 180.0, "serial_match": False,
         "has_receipt": False,
         "_dup": {"doc_mismatch": True,
                  "doc_mismatch_note": "receipt says Apple, product is Samsung"},
         "ocr_verification": {"verdict": "mismatch"}}
res = fi.analyze(claim, {"invoice_reused": True, "prior_claims": 1},
                 [], [], [], [], {"verdict": "mismatch"})
check("Escalation: 5 independent families -> score >= 60, escalated",
      res["score"] >= 60 and res["escalated"],
      f"score={res['score']} families={res['families']}")

print(f"\nRESULT: {passed} passed, {failed} failed")