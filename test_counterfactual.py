"""Counterfactual Engine + Predictive Risk self-test.

Test design lesson (documented in dev log): the engine VERIFIES every
proposed flip through the production rule engine and refuses to offer
flips that don't hold. Initial tests failed not because the engine was
wrong but because the test claims violated MULTIPLE rules
simultaneously - no single flip could fix them. Corrected tests isolate
one rule violation per claim."""
from datetime import date, timedelta

from src.counterfactual import generate
from src.predictive import product_risk
from src.rules import load_policies

TODAY = date.today()
pol = load_policies()["Electronics"]
P = 0


def check(name, ok, d=""):
    global P
    P += ok
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" - {d}" if d and not ok else ""))


# base: LONG-EXPIRED claim (warranty ended ~500 days ago)
base_expired = {
    "purchase_date": (TODAY - timedelta(days=800)).isoformat(),
    "warranty_months": 24, "warranty_type": "standard", "extended_months": 0,
    "fault_date": (TODAY - timedelta(days=10)).isoformat(),
    "claim_date": TODAY.isoformat(), "fault_category": "screen_defect",
    "repair_count": 0, "last_repair_date": "", "authorized_repair": True,
    "serial_match": True, "has_receipt": True, "has_warranty_card": True,
    "has_product_image": True, "has_serial_evidence": True,
    "has_fault_evidence": True, "has_repair_report": False,
    "prior_claim_count": 0, "duplicate_invoice": False,
    "replaced_before": False}

# base: ACTIVE-warranty claim (for single-violation tests)
base_active = {
    **base_expired,
    "purchase_date": (TODAY - timedelta(days=200)).isoformat(),
    "fault_date": (TODAY - timedelta(days=5)).isoformat()}

# ---- 1. expired claim produces counterfactuals
r = generate({**base_expired}, pol)
check("Expired claim produces counterfactuals", bool(r), str(r))

# ---- 2. date flip (v2 engine repairs the reporting window too)
check("Date flip present (or honest multi-condition note)",
      any("on or before" in f for f in r) or
      any("multiple conditions" in f for f in r), str(r))

# ---- 3. extended-warranty flip on the expired claim
check("Extended-warranty flip present",
      any("extended warranty" in f for f in r), str(r))

# ---- 4. excluded fault ISOLATED on an active warranty (single violation)
r2 = generate({**base_active, "fault_category": "liquid_damage"}, pol)
check("Excluded fault gets covered-fault flip",
      any("covered fault" in f for f in r2), str(r2))

# ---- 5. missing docs ISOLATED on an active warranty
r3 = generate({**base_active, "has_receipt": False,
               "has_warranty_card": False}, pol)
check("Missing docs gets upload flip",
      any("documents" in f for f in r3), str(r3))

# ---- 6. valid claim returns None (nothing to flip)
check("Valid claim returns None",
      generate({**base_active}, pol) is None)

# ---- 7. predictive risk computes with reasons
lvl, why = product_risk({
    "product_category": "Electronics",
    "purchase_date": (TODAY - timedelta(days=700)).isoformat(),
    "warranty_months": 24, "repair_count": 1})
check(f"Predictive risk computed: {lvl}", lvl in ("LOW", "ELEVATED", "HIGH"))
print(f"        reasons: {why}")

print(f"\nRESULT: {P}/7 passed")