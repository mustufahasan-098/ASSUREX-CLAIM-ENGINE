"""AssureX Fraud Intelligence - 7 explainable detection layers.

Layer 1  pHash image fingerprints ......... same photo re-saved/renamed
Layer 2  velocity rules ................... claim bursts, repeated faults
Layer 3  behavioral scoring ............... rejection history per user
Layer 4  price reasonableness ............. category medians from dataset
Layer 5  cross-user network ............... shared documents across customers
Layer 6  OCR verification weighting ....... mismatched/unverifiable receipts
Layer 7  combinatorial escalation ......... multiple independent signals

Every signal carries (code, points, reason) - fully auditable, stored on
each claim record, rendered as an evidence table in the UI. No external
APIs, no extra models (SRS 1.10.15).
"""
import csv
import io
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SIMILAR_THRESHOLD = 10   # max hamming distance for "same image"


# ---------------------------------------------------- layer 1: fingerprints
def dhash_from_bytes(data):
    """dHash (difference hash): 64-bit visual fingerprint. Robust to
    re-saving, re-compression and renaming - catches the copies that
    SHA-256 misses."""
    try:
        img = Image.open(io.BytesIO(data)).convert("L").resize((9, 8))
        px = np.array(img, dtype=int)
        bits = (px[:, 1:] > px[:, :-1]).flatten()
        return "".join("1" if b else "0" for b in bits)
    except Exception:
        return None


def hamming(a, b):
    if not a or not b or len(a) != len(b):
        return 64
    return sum(x != y for x, y in zip(a, b))


# ---------------------------------------------------- layer 4: price norms
_PRICE_CACHE = {}


def category_price_stats():
    """Median purchase price per category, computed from the project's own
    dataset (data/all_claims.csv) - data-driven, not hard-coded."""
    if _PRICE_CACHE:
        return _PRICE_CACHE
    path = ROOT / "data" / "all_claims.csv"
    try:
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        for cat in {r["product_category"] for r in rows}:
            prices = [float(r["purchase_price"]) for r in rows
                      if r["product_category"] == cat]
            _PRICE_CACHE[cat] = {"median": float(np.median(prices))}
    except Exception:
        pass
    return _PRICE_CACHE


def price_signal(claim):
    stats = category_price_stats()
    cat = claim.get("product_category")
    if cat not in stats:
        return []
    med = stats[cat]["median"]
    price = float(claim.get("purchase_price") or 0)
    if price and med and price >= med * 4:
        return [("price_outlier", 15,
                 f"Registered price Rs {price:,.0f} is {price / med:.1f}x "
                 f"the {cat} category median (Rs {med:,.0f})")]
    return []


# --------------------------------------------- layers 2+3: velocity/history
def _days_ago(iso_str, today):
    try:
        return (today - datetime.fromisoformat(str(iso_str)[:10]).date()).days
    except Exception:
        return 9999


def velocity_signals(owner_claims, serial_claims, today=None):
    """owner_claims / serial_claims: pre-fetched claim dicts (no direct
    Firestore access - fully unit-testable)."""
    today = today or date.today()
    signals = []
    recent = [c for c in owner_claims
              if 0 <= _days_ago(c.get("created_at", ""), today) <= 7]
    if len(recent) >= 3:
        signals.append(("velocity_burst", 20,
                        f"{len(recent)} claims submitted in the last 7 days"))
    for fault, n in Counter(c.get("fault_category")
                            for c in serial_claims).items():
        if n >= 2:
            signals.append(("repeat_fault", 15,
                            f"Fault '{fault}' claimed {n} times on this "
                            f"serial number"))
    total = len(owner_claims)
    rejected = sum(1 for c in owner_claims if c.get("status") == "Rejected")
    if total >= 4 and rejected / total >= 0.4:
        signals.append(("rejection_history", 15,
                        f"{rejected} of {total} previous claims were rejected"))
    return signals


# --------------------------------------------------- layer 5: cross-user net
def network_signals(all_claims, current_owner, sha_list, phash_list,
                    current_invoice=None):
    """The same document (exact bytes OR near-identical image) used by a
    DIFFERENT customer - the strongest coordinated-fraud signal."""
    hits = []
    for c in all_claims:
        if c.get("owner_email") == current_owner:
            continue
        stored_sha = set(c.get("doc_hashes") or [])
        if any(h in stored_sha for h in sha_list):
            hits.append((c.get("owner_email"), "exact file"))
            continue
        stored_ph = [p for p in (c.get("doc_phashes") or []) if p]
        similar_img = any(p and any(hamming(p, q) <= SIMILAR_THRESHOLD
                                    for q in stored_ph) for p in phash_list)
        same_invoice = c.get("invoice_number") == current_invoice
        if similar_img and same_invoice:
            # visually identical AND same invoice number - two independent
            # confirmations, not layout coincidence
            hits.append((c.get("owner_email"), "same image + same invoice"))
    if hits:
        users = sorted({u for u, _ in hits})
        kinds = sorted({k for _, k in hits})
        return [("cross_user_doc", 40,
                 f"Document already used by another customer "
                 f"({', '.join(users[:3])}) - {'/'.join(kinds)}")]
    return []


# ------------------------------------------------------ layer 6: OCR weight
def ocr_signal(ocr_verify):
    v = (ocr_verify or {}).get("verdict")
    if v == "inconclusive":
        return [("receipt_unverified", 10,
                 "Receipt could not be fully verified by OCR (low quality "
                 "or unclear)")]
    return []


# -------------------------------------------------- base + aggregation
def base_signals(dup):
    s = []
    if dup.get("invoice_reused"):
        s.append(("invoice_reuse", 35,
                  "Invoice number reused from a previous claim"))
    if dup.get("doc_hash_reuse"):
        s.append(("doc_reuse", 35,
                  "Document file already used in another of your claims"))
    prior = int(dup.get("prior_claims", 0) or 0)
    if prior:
        s.append(("prior_claims", min(20, prior * 10),
                  f"{prior} prior claim(s) on this serial number"))
    return s


def analyze(claim, dup, owner_claims, serial_claims, all_claims,
            docs_meta, ocr_verify):
    """Aggregate all layers into one explainable score (0-100).
    Firestore data is passed in as arguments - fully unit-testable."""
    signals = base_signals(dup) + ocr_signal(ocr_verify)
    signals += velocity_signals(owner_claims, serial_claims)
    sha_list = [d["sha256"] for d in docs_meta]
    phash_list = [d.get("phash") for d in docs_meta if d.get("phash")]
    signals += network_signals(all_claims, claim.get("user_id"),
                               sha_list, phash_list,
                               claim.get("invoice_number"))
    signals += price_signal(claim)

    # receipt mismatch flagged at upload time (OCR cross-verification)
    if claim.get("_dup", {}).get("doc_mismatch"):
        signals.append(("receipt_mismatch", 25,
                        claim["_dup"].get("doc_mismatch_note",
                                          "Uploaded receipt does not match "
                                          "the registered product")))
    if not claim.get("serial_match", True):
        signals.append(("serial_mismatch", 15,
                        "Serial number does not match the registered product"))
    if not claim.get("has_receipt", True):
        signals.append(("no_receipt", 10, "No purchase receipt provided"))

    score = min(100, sum(p for _, p, _ in signals))
    families = len({c for c, _, _ in signals})

    # layer 7: several independent indicator families reinforce each other
    escalated = families >= 3 and score >= 40
    if escalated and score < 60:
        score = 60
    tone = "valid" if score < 30 else "review" if score < 60 else "invalid"
    return {"score": score, "tone": tone, "escalated": escalated,
            "families": families,
            "signals": [{"code": c, "points": p, "reason": r}
                        for c, p, r in signals]}