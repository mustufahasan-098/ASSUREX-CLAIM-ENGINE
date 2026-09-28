"""Seeds demo users, products, and three demonstration claims (valid,
invalid-by-expiry, manual-review) through the FULL production pipeline.
Idempotent - safe to run repeatedly.  Run:  python -m src.seed_demo"""
from datetime import date, timedelta
from pathlib import Path

import yaml

from . import auth, claim_service as cs
from . import firebase_db as fdb
from . import models as models_mod

TODAY = date.today()
ROOT = Path(__file__).resolve().parent.parent
SETTINGS = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text())


def ensure_user(email, name, role, password):
    if fdb.get_doc("users", email):
        return False
    fdb.set_doc("users", email, {
        "name": name, "email": email, "role": role,
        "password": auth.hash_password(password), "failed_attempts": 0,
        "created_at": TODAY.isoformat()})
    fdb.log_audit("seed_user_created", email, {"role": role})
    return True


def ensure_product(pid, owner, name, category, brand, model, serial,
                   purchase, price):
    if fdb.get_doc("products", pid):
        return False
    pol = models_mod.load_all()["policies"][category]
    fdb.set_doc("products", pid, {
        "product_id": pid, "owner_email": owner, "name": name,
        "product_category": category, "brand": brand, "model": model,
        "serial_number": serial, "purchase_date": purchase.isoformat(),
        "purchase_price": price, "retailer": "Demo Electronics Store",
        "warranty_type": "standard",
        "warranty_months": pol["standard_warranty_months"],
        "extended_months": 0})
    fdb.log_audit("product_registered", owner, {"product_id": pid})
    return True


def ensure_claim(marker, claim):
    if fdb.query("claims", "seed_marker", "==", marker, limit=1):
        return False
    claim["seed_marker"] = marker
    cs.process_and_save(claim, docs=[], actor="seed")
    return True


def base_claim():
    return {"user_id": "demo@assurex.com", "warranty_type": "standard",
            "extended_months": 0, "repair_count": 0, "last_repair_date": "",
            "authorized_repair": True, "serial_match": True,
            "prior_claim_count": 0, "duplicate_invoice": False,
            "replaced_before": False, "has_receipt": True,
            "has_warranty_card": True, "has_product_image": True,
            "has_serial_evidence": True, "has_fault_evidence": True,
            "has_repair_report": False}


def main():
    a = SETTINGS["admin"]
    ensure_user(a["email"], "System Administrator", "admin", a["password"])
    ensure_user("reviewer@assurex.com", "Ayesha Reviewer", "reviewer",
                "Reviewer@123")
    ensure_user("demo@assurex.com", "Demo Customer", "customer", "Demo@123")
    ensure_user("service@assurex.com", "City Service Center",
                "service_center", "Service@123")

    ensure_product("PRD-SEED1", "demo@assurex.com", "Smartphone",
                   "Electronics", "Samsung", "Galaxy S22", "SNSEED0001",
                   TODAY - timedelta(days=200), 899.0)
    ensure_product("PRD-SEED2", "demo@assurex.com", "Refrigerator",
                   "Home Appliances", "LG", "Fridge 340L", "SNSEED0002",
                   TODAY - timedelta(days=150), 650.0)
    ensure_product("PRD-SEED3", "demo@assurex.com", "Cordless Drill",
                   "Power Tools", "Bosch", "GSR 18V", "SNSEED0003",
                   TODAY - timedelta(days=900), 180.0)

     
    c1 = {**base_claim(), "product_category": "Electronics",
          "brand": "Samsung", "model": "Galaxy S22",
          "serial_number": "SNSEED0001",
          "purchase_date": (TODAY - timedelta(days=200)).isoformat(),
          "purchase_price": 899.0, "warranty_months": 24,
          "fault_date": (TODAY - timedelta(days=9)).isoformat(),
          "claim_date": TODAY.isoformat(), "fault_category": "screen_defect",
          "invoice_number": "INV-SEED-001"}

     
    c2 = {**base_claim(), "product_category": "Power Tools",
          "brand": "Bosch", "model": "GSR 18V", "serial_number": "SNSEED0003",
          "purchase_date": (TODAY - timedelta(days=900)).isoformat(),
          "purchase_price": 180.0, "warranty_months": 18,
          "fault_date": (TODAY - timedelta(days=5)).isoformat(),
          "claim_date": TODAY.isoformat(), "fault_category": "motor_failure",
          "invoice_number": "INV-SEED-002"}

     
    c3 = {**base_claim(), "product_category": "Home Appliances",
          "brand": "LG", "model": "Fridge 340L", "serial_number": "SNSEED0002",
          "purchase_date": (TODAY - timedelta(days=150)).isoformat(),
          "purchase_price": 650.0, "warranty_months": 12,
          "fault_date": (TODAY - timedelta(days=4)).isoformat(),
          "claim_date": TODAY.isoformat(), "fault_category": "cooling_failure",
          "invoice_number": "INV-SEED-003", "has_receipt": False,
          "serial_match": False}

    r1 = ensure_claim("seed_valid", c1)
    r2 = ensure_claim("seed_invalid", c2)
    r3 = ensure_claim("seed_review", c3)

    print("SEED COMPLETE")
    print("  users    : admin / reviewer / demo customer / service center")
    print("  products : 3 registered (one with expired warranty)")
    print(f"  claims   : valid={'NEW' if r1 else 'exists'}, "
          f"invalid={'NEW' if r2 else 'exists'}, "
          f"review={'NEW' if r3 else 'exists'}")
    print("\nLogins:")
    print("  admin@assurex.com / Admin@123")
    print("  reviewer@assurex.com / Reviewer@123")
    print("  demo@assurex.com / Demo@123")
    print("  service@assurex.com / Service@123")


if __name__ == "__main__":
    main()