"""Product template catalog - admin-maintained list of common products.

Templates pre-fill ONLY brand/model/category at registration. The
customer always supplies their own serial number, purchase date, price
and retailer (these come from the customer's receipt, never from the
catalog - SRS req iii). Warranty months are NEVER stored on a template:
they are computed from the category policy at registration time, keeping
the AI/catalog completely outside the decision path (SRS 1.10.15).
"""
import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "config" / "product_templates.json"


def load_templates():
    if not CATALOG.exists():
        return []
    try:
        return json.loads(CATALOG.read_text(encoding="utf-8")).get(
            "templates", [])
    except Exception:
        return []


def save_templates(templates):
    CATALOG.parent.mkdir(exist_ok=True)
    CATALOG.write_text(json.dumps({"templates": templates}, indent=2),
                       encoding="utf-8")


def get_template(tid):
    for t in load_templates():
        if t["id"] == tid:
            return t
    return None


def add_template(name, brand, model, category, valid_categories):
    """Validate + persist one template. Returns (template, error)."""
    name, brand = name.strip(), brand.strip()
    if not name or not brand:
        return None, "Name and brand are required."
    if category not in valid_categories:
        return None, "Choose a valid category."
    templates = load_templates()
    if any(t["name"].lower() == name.lower()
           and t["brand"].lower() == brand.lower() for t in templates):
        return None, "A template with this name and brand already exists."
    t = {"id": f"TPL-{uuid.uuid4().hex[:4].upper()}",
         "name": name, "brand": brand, "model": model.strip(),
         "category": category}
    templates.append(t)
    save_templates(templates)
    return t, None


def remove_template(tid):
    templates = load_templates()
    remaining = [t for t in templates if t["id"] != tid]
    if len(remaining) == len(templates):
        return False
    save_templates(remaining)
    return True