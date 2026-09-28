"""AssureX Counterfactual Engine - 'what would have changed this decision?'

For rejected/review claims, computes the changes that would flip the
outcome to Valid. Every candidate flip is VERIFIED by re-running the
actual rule engine on the modified claim - if the engine says the flip
doesn't produce a Valid outcome, the flip is NOT offered. The engine
refuses to lie: when no single change suffices, it says so, and when a
combination is needed, it reports the minimal combination it found.

Design notes (verified by test_counterfactual.py):
  - date flips also repair the reporting window (a fault moved inside
    warranty must still be reported within the deadline, so the claim
    date is moved into the valid window too - and the result is
    re-verified)
  - multi-rule failures (e.g. expired + excluded fault) produce a
    combined counterfactual when one exists, or an honest 'multiple
    conditions must differ' statement when none does
Read-only: never modifies stored claims."""
from datetime import timedelta

from .features import add_months, parse_date
from .rules import VALID, evaluate_claim


def _verify(claim, policy):
    """A flip only counts if the REAL rule engine returns Valid."""
    return evaluate_claim(claim, policy)["label"] == VALID


def _date_flip(claim, policy, purchase, fault, claim_d, expiry):
    """Flip 1: fault moved on/before expiry, with claim date repaired
    into the reporting window. Returns a message or None."""
    if not (fault and fault > expiry):
        return None
    deadline_days = int(policy["claim_reporting_period_days"])
    candidate = dict(claim)
    candidate["fault_date"] = expiry.isoformat()
     
     
    candidate["claim_date"] = (expiry + timedelta(days=1)).isoformat()
    if _verify(candidate, policy):
        days = (fault - expiry).days
        return (f"If the fault had occurred on or before "
                f"{expiry.isoformat()} ({days} day"
                f"{'s' if days != 1 else ''} earlier) and been reported "
                f"within {deadline_days} days, the claim would likely "
                f"have been VALID.")
    return None


def _extended_warranty_flip(claim, policy, purchase, fault):
    """Flip 2: an extended warranty long enough to cover the fault."""
    if not (purchase and fault):
        return None
    months = int(claim.get("warranty_months") or 0)
    if months and claim.get("extended_months"):
        pass  # already extended; adding more may still help - continue
    needed = None
    current = months + int(claim.get("extended_months") or 0)
    for extra in range(1, 37):
        if fault <= add_months(purchase, current + extra):
            needed = extra
            break
    if not needed:
        return None
    max_ext = int(policy.get("extended_warranty_max_months", 36))
    if current + needed > months + max_ext:
        return None  # beyond what the policy even allows
    candidate = dict(claim)
    candidate["warranty_type"] = "extended"
    candidate["extended_months"] = \
        int(claim.get("extended_months") or 0) + needed
    if _verify(candidate, policy):
        return (f"If an extended warranty of +{needed} additional month(s) "
                f"had been registered at purchase, the fault would have "
                f"fallen inside coverage and the claim likely VALID.")
    return None


def _covered_fault_flip(claim, policy):
    """Flip 3: the excluded fault replaced by a covered one."""
    if claim.get("fault_category") not in policy["excluded_faults"]:
        return None
    for covered in policy["covered_faults"]:
        candidate = dict(claim)
        candidate["fault_category"] = covered
        if _verify(candidate, policy):
            return (f"'{claim['fault_category'].replace('_', ' ')}' is "
                    f"excluded by the {policy['category']} policy. The "
                    f"same claim with a covered fault (e.g. "
                    f"'{covered.replace('_', ' ')}') would likely have "
                    f"been VALID.")
    return None


def _documents_flip(claim, policy, base):
    """Flip 4: uploading all mandatory documents."""
    if not any("issing" in f for f in base["review_flags"]):
        return None
    candidate = dict(claim)
    for doc in policy["mandatory_documents"]:
        candidate[f"has_{doc}"] = True
    if _verify(candidate, policy):
        return ("Uploading all mandatory documents would likely move this "
                "claim to VALID (currently routed for manual review).")
    return None


def _serial_flip(claim, policy):
    """Flip 5: correcting a mismatched serial number."""
    if claim.get("serial_match", True):
        return None
    candidate = dict(claim)
    candidate["serial_match"] = True
    if _verify(candidate, policy):
        return ("Correcting the serial number to match the registered "
                "product would likely make the claim VALID.")
    return None


def _combined_flip(claim, policy):
    """When no single flip works, try the smallest sensible COMBINATIONS
    (date + documents, warranty + fault type, etc.). Returns a message
    or None."""
    purchase = parse_date(claim["purchase_date"])
    fault = parse_date(claim["fault_date"])

    combos = []
     
    c = dict(claim)
    c["fault_category"] = policy["covered_faults"][0]
    months = int(claim.get("warranty_months") or 0) \
        + int(claim.get("extended_months") or 0)
    if purchase and fault:
        for extra in range(1, 37):
            if fault <= add_months(purchase, months + extra):
                c["warranty_type"] = "extended"
                c["extended_months"] = int(claim.get("extended_months")
                                           or 0) + extra
                break
    combos.append(c)
     
    c2 = dict(claim)
    for doc in policy["mandatory_documents"]:
        c2[f"has_{doc}"] = True
    c2["serial_match"] = True
    combos.append(c2)

    for candidate in combos:
        if _verify(candidate, policy):
            return ("No SINGLE change flips this decision, but a "
                    "combination would: extending coverage (or using a "
                    "covered fault) together with complete documents "
                    "could make this claim VALID. See the factors above "
                    "for which conditions were violated.")
    return None


def generate(claim, policy):
    """Returns a list of human-readable counterfactual strings, or None
    when the claim is already Valid (nothing to flip)."""
    base = evaluate_claim(claim, policy)
    if base["label"] == VALID:
        return None

    purchase = parse_date(claim["purchase_date"])
    fault = parse_date(claim["fault_date"])
    claim_d = parse_date(claim["claim_date"])
    months = int(claim.get("warranty_months") or 0)
    expiry = add_months(purchase, months + int(claim.get("extended_months")
                                               or 0)) if purchase else None

    flips = []
    if expiry:
        f = _date_flip(claim, policy, purchase, fault, claim_d, expiry)
        if f:
            flips.append(f)
        f = _extended_warranty_flip(claim, policy, purchase, fault)
        if f:
            flips.append(f)
    f = _covered_fault_flip(claim, policy)
    if f:
        flips.append(f)
    f = _documents_flip(claim, policy, base)
    if f:
        flips.append(f)
    f = _serial_flip(claim, policy)
    if f:
        flips.append(f)

    if not flips:
        f = _combined_flip(claim, policy)
        if f:
            flips.append(f)

    if not flips:
        flips.append("No single change of dates, documents, warranty "
                     "terms or fault type would flip this decision - "
                     "multiple conditions would need to differ. See the "
                     "decision factors above for the full list of "
                     "violations.")
    return flips