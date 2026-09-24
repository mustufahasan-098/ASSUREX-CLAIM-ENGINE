"""AssureX Claim Engine - configurable warranty rule engine.

Policies are loaded from JSON files in /policies (never hard-coded), and this
same engine is used by BOTH the dataset generator (to derive training labels)
and the live application (to validate real claims). One engine means training
labels and business rules can never drift apart.

Decision priority:
  1. Contradictions  -> Manual Review (unreliable data cannot be auto-decided)
  2. Hard-fail rules -> Invalid Claim
  3. Review rules    -> Manual Review
  4. Otherwise       -> Valid Claim

Warning rules are informational only - they never change the label.
"""
import json
import pathlib

from .features import compute_derived, parse_date, to_bool

POLICY_DIR = pathlib.Path(__file__).resolve().parent.parent / "policies"

VALID, INVALID, REVIEW = "Valid Claim", "Invalid Claim", "Manual Review"


def load_policies():
    """Load every policy JSON in /policies, keyed by category name."""
    return {p["category"]: p for p in
            (json.loads(f.read_text(encoding="utf-8"))
             for f in sorted(POLICY_DIR.glob("*.json")))}


def evaluate_claim(claim, policy):
    """Evaluate one claim against its category policy.
    Returns the label plus fully explainable rule outcomes (the UI, the
    decision-explanation screen, and the audit trail all render these)."""
    purchase = parse_date(claim["purchase_date"])
    fault = parse_date(claim["fault_date"])
    claim_d = parse_date(claim["claim_date"])
    repair = parse_date(claim.get("last_repair_date"))
    d = compute_derived(claim, policy)

    out = {"label": None, "contradictions": [], "hard_fails": [],
           "review_flags": [], "warnings": [], "reasons": []}

    # 1 ---- contradictions -> manual review (checked first: unreliable data
    # cannot be trusted to auto-decide anything, even an invalid-looking claim)
    if claim_d and purchase and claim_d < purchase:
        out["contradictions"].append("Claim submitted before purchase date")
    if fault and purchase and fault < purchase:
        out["contradictions"].append("Fault occurred before purchase date")
    if repair and purchase and repair < purchase:
        out["contradictions"].append("Repair recorded before purchase date")
    if fault and claim_d and fault > claim_d:
        out["contradictions"].append("Fault date is after claim submission date")
    if out["contradictions"]:
        out["label"] = REVIEW
        out["reasons"] = ["Contradictory claim data requires human verification"] + out["contradictions"]
        return out

    # 2 ---- hard failures -> invalid
    if d["warranty_expired"] and not d["within_grace"]:
        out["hard_fails"].append("Warranty expired before the fault date")
    if claim.get("fault_category") in policy["excluded_faults"]:
        out["hard_fails"].append(
            f"Fault type '{claim['fault_category']}' is excluded by the {policy['category']} policy")
    if (int(claim.get("repair_count") or 0) > 0
            and not to_bool(claim.get("authorized_repair", True))
            and policy.get("authorized_service_required", True)):
        out["hard_fails"].append("Warranty voided by repair at an unauthorized service centre")
    if d["days_to_report"] is not None and \
            d["days_to_report"] > int(policy["claim_reporting_period_days"]):
        out["hard_fails"].append(
            f"Fault reported {d['days_to_report']} days after occurrence "
            f"(limit: {policy['claim_reporting_period_days']})")
    if to_bool(claim.get("replaced_before", False)):
        out["hard_fails"].append("Product was already replaced once under warranty")
    if out["hard_fails"]:
        out["label"] = INVALID
        out["reasons"] = ["One or more hard-fail warranty rules were violated"] + out["hard_fails"]
        return out

    # 2.5 ---- informational warnings (never change the label)
    price = float(claim.get("purchase_price") or 0)
    if price >= int(policy.get("expensive_item_threshold", 10**9)):
        out["warnings"].append("High-value item - extra documentation check advised")
    if d["warranty_days_remaining"] is not None and d["warranty_days_remaining"] <= 60:
        out["warnings"].append("Fault occurred near the end of the warranty period")

    # 3 ---- manual-review triggers
    if d["within_grace"]:
        out["review_flags"].append("Fault occurred after expiry but inside the grace period")
    if not to_bool(claim.get("serial_match", True)):
        out["review_flags"].append("Serial number does not match purchase records")
    if d["missing_docs_count"] > 0:
        out["review_flags"].append("Missing mandatory documents: " + ", ".join(d["missing_docs"]))
    if int(claim.get("prior_claim_count") or 0) > 0 or to_bool(claim.get("duplicate_invoice", False)):
        out["review_flags"].append("Possible duplicate claim detected")
    if int(claim.get("repair_count") or 0) > int(policy["max_prior_repairs"]):
        out["review_flags"].append("Excessive repair history - replacement decision needed")
    if d["product_age_days"] is not None and \
            d["product_age_days"] <= int(policy["early_fault_review_days"]):
        out["review_flags"].append("Fault within early-life window - possible dead-on-arrival")
    if out["review_flags"]:
        out["label"] = REVIEW
        out["reasons"] = ["Claim requires manual verification"] + out["review_flags"]
        return out

    # 4 ---- all rules passed
    out["label"] = VALID
    out["reasons"] = ["All warranty rules passed with complete documentation"]
    return out
def factual_flags(claim, policy):
    """Factual validation findings for one claim, for the Claim Summary Card.

    Each finding is tagged with the severity category defined by the policy
    rule lists: 'hard_fail' (rule violation that voids the warranty),
    'review' (condition requiring manual verification) or 'conflict'
    (contradictory data - review-level, mirroring evaluate_claim's priority).

    The card renders these as large status pills coloured by severity:
    hard-fail = red, review/conflict = amber, no findings = green.
    Conditions intentionally mirror evaluate_claim; the card generator's
    self-test (label 'Valid Claim' <=> zero flags) guards against drift.
    """
    purchase = parse_date(claim["purchase_date"])
    fault = parse_date(claim["fault_date"])
    claim_d = parse_date(claim["claim_date"])
    repair = parse_date(claim.get("last_repair_date") or "")
    d = compute_derived(claim, policy)

    conflicts = []
    if claim_d and purchase and claim_d < purchase:
        conflicts.append("claim before purchase")
    if fault and purchase and fault < purchase:
        conflicts.append("fault before purchase")
    if repair and purchase and repair < purchase:
        conflicts.append("repair before purchase")
    if fault and claim_d and fault > claim_d:
        conflicts.append("fault after claim date")

    flags = []
    if conflicts:
        flags.append(("conflict", "DATE CONTRADICTION"))
    if d["warranty_expired"] and not d["within_grace"]:
        flags.append(("hard_fail", "WARRANTY EXPIRED"))
    if claim.get("fault_category") in policy["excluded_faults"]:
        flags.append(("hard_fail", "FAULT EXCLUDED"))
    if (int(claim.get("repair_count") or 0) > 0
            and not to_bool(claim.get("authorized_repair", True))
            and policy.get("authorized_service_required", True)):
        flags.append(("hard_fail", "UNAUTHORIZED REPAIR"))
    if d["days_to_report"] is not None and \
            d["days_to_report"] > int(policy["claim_reporting_period_days"]):
        flags.append(("hard_fail", "LATE FAULT REPORTING"))
    if to_bool(claim.get("replaced_before", False)):
        flags.append(("hard_fail", "PRIOR REPLACEMENT"))
    if d["within_grace"]:
        flags.append(("review", "GRACE PERIOD CLAIM"))
    if not to_bool(claim.get("serial_match", True)):
        flags.append(("review", "SERIAL NUMBER MISMATCH"))
    for doc in d["missing_docs"]:
        flags.append(("review", f"MISSING: {doc.replace('_', ' ').upper()}"))
    if int(claim.get("prior_claim_count") or 0) > 0 or \
            to_bool(claim.get("duplicate_invoice", False)):
        flags.append(("review", "DUPLICATE CLAIM INDICATOR"))
    if int(claim.get("repair_count") or 0) > int(policy["max_prior_repairs"]):
        flags.append(("review", "EXCESSIVE REPAIR HISTORY"))
    if d["product_age_days"] is not None and \
            d["product_age_days"] <= int(policy["early_fault_review_days"]):
        flags.append(("review", "EARLY-LIFE FAULT"))
    return flags