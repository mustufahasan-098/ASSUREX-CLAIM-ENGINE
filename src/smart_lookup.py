"""AssureX smart product lookup - QR decode + AI detail suggestion.

Flow: user uploads a QR/barcode image (decoded locally with OpenCV) or
types a product name. The Groq API (llama-3.1-8b-instant) returns a
SUGGESTION for brand/model/category which is shown to the user for
verification - nothing is saved automatically (SRS req vii pattern).

Guardrails (see AI_USAGE.md):
  - suggestion only; human verification required before saving
  - warranty terms always come from the local category policy, never
    from the AI (decision-path isolation, SRS 1.10.15)
  - API key read from the environment, never stored in the repo
  - any failure (no key, no network, API error) degrades gracefully to
    the standard manual registration form
"""
import json
import os

import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-20b"

PROMPT = """You are a product catalog assistant. Given a product name or QR/barcode text, respond with ONLY a JSON object with these exact fields:
- "product_name": clean retail product name
- "brand": manufacturer brand
- "model": model identifier, or "" if unknown
- "category": exactly one of "Electronics", "Home Appliances", "Power Tools" - the closest match
- "typical_warranty_months": integer, typical standard manufacturer warranty for this product type
- "notes": one short sentence, or ""

Product input: {query}"""


def decode_qr(data_bytes):
    """Decode a QR code from image bytes, fully local (OpenCV)."""
    try:
        import cv2
        import numpy as np
        img = cv2.imdecode(np.frombuffer(data_bytes, np.uint8),
                           cv2.IMREAD_COLOR)
        if img is None:
            return None
        text, _, _ = cv2.QRCodeDetector().detectAndDecode(img)
        return text.strip() or None
    except Exception:
        return None


def lookup_product(query, valid_categories):
    """Ask Groq for product details. Returns dict with ok/suggestion or a
    graceful fallback. NEVER raises."""
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        return {"ok": False, "error": "GROQ_API_KEY not configured - "
                                      "using manual entry (fallback active)"}
    try:
        r = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {key}"},
                        json={"model": MODEL,
                  "temperature": 0,
                  "max_tokens": 300,
                  "messages": [{"role": "user",
                                "content": PROMPT.format(query=query)}]},
            timeout=20)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        data = json.loads(content[content.find("{"):content.rfind("}") + 1])
        category = data.get("category", "")
        if category not in valid_categories:
            data["category"] = ""
            data["notes"] = (data.get("notes", "") +
                             " (AI category not recognised - choose one)")
        return {"ok": True, "suggestion": data,
                "query": query, "model": MODEL}
    except Exception as e:
        return {"ok": False, "error": f"Lookup unavailable ({e}) - "
                                      "using manual entry"}