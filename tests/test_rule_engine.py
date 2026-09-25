"""AssureX automated rule-engine + contradiction + boundary tests.
Covers SRS deliverable 8 categories: rule-engine tests, contradiction
detection, missing documents, serial mismatch, boundary dates, negative
cases. All tests run against the REAL rule engine (src/rules.py)."""
from datetime import date, timedelta

from src.rules import INVALID, REVIEW, VALID, evaluate_claim, load_policies

TODAY = date.today()
PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    PASS += ok
    FAIL += (not ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}"
                                                    if detail and not ok
                                                    else ""))


def base(policies):
    pol = policies["Electronics"]
    return pol, {
        "purchase_date": (TODAY - timedelta(days=200)).isoformat(),
        "warranty_months": pol["standard_warranty_months"],
        "warranty_type": "standard", "extended_months": 0,
        "fault_date": (TODAY - timedelta(days=10)).isoformat(),
        "claim_date": TODAY.isoformat(),
        "fault_category": "screen_defect",
        "repair_count": 0, "last_repair_date": "",
        "authorized_repair": True, "serial_match": True,
        "has_receipt": True, "has_warranty_card": True,
        "has_product_image": True, "has_serial_evidence": True,
        "has_fault_evidence": True, "has_repair_report": False,
        "prior_claim_count": 0, "duplicate_invoice": False,
        "replaced_before": False,
    }


def run():
    policies = load_policies()
    pol, claim = base(policies)

    # ---- valid path
    check("Valid: clean active-warranty claim",
          evaluate_claim(claim, pol)["label"] == VALID)

    # ---- hard fails (invalid)
    c = {**claim, "purchase_date": (TODAY - timedelta(days=800)).isoformat(),
         "fault_date": (TODAY - timedelta(days=10)).isoformat(),
         "claim_date": TODAY.isoformat()}
    out = evaluate_claim(c, pol)
    check("Invalid: expired warranty",
          out["label"] == INVALID and
          any("expired" in f.lower() for f in out["hard_fails"]),
          f"label={out['label']} hard_fails={out['hard_fails']}")

    c = {**claim, "fault_category": "liquid_damage"}
    check("Invalid: excluded fault (liquid damage)",
          evaluate_claim(c, pol)["label"] == INVALID)

    c = {**claim, "repair_count": 1, "authorized_repair": False,
         "last_repair_date": (TODAY - timedelta(days=100)).isoformat()}
    check("Invalid: unauthorized repair",
          evaluate_claim(c, pol)["label"] == INVALID)

    c = {**claim, "claim_date": (TODAY + timedelta(days=60)).isoformat()}
    check("Invalid: late fault reporting (60 days)",
          evaluate_claim(c, pol)["label"] == INVALID)

    c = {**claim, "replaced_before": True}
    check("Invalid: prior replacement",
          evaluate_claim(c, pol)["label"] == INVALID)

    # ---- manual-review triggers
    c = {**claim, "has_receipt": False}
    out = evaluate_claim(c, pol)
    check("Review: missing mandatory document",
          out["label"] == REVIEW and
          any("Missing" in f for f in out["review_flags"]))

    c = {**claim, "serial_match": False}
    check("Review: serial-number mismatch",
          evaluate_claim(c, pol)["label"] == REVIEW)

    c = {**claim, "prior_claim_count": 1}
    check("Review: duplicate-claim indicator",
          evaluate_claim(c, pol)["label"] == REVIEW)

    c = {**claim, "repair_count": 5, "authorized_repair": True,
         "last_repair_date": (TODAY - timedelta(days=100)).isoformat()}
    check("Review: excessive repair history",
          evaluate_claim(c, pol)["label"] == REVIEW)

    # ---- contradictions
    c = {**claim, "claim_date": (TODAY - timedelta(days=300)).isoformat()}
    check("Contradiction: claim before purchase",
          evaluate_claim(c, pol)["label"] == REVIEW and
          bool(evaluate_claim(c, pol)["contradictions"]))

    c = {**claim, "fault_date": (TODAY - timedelta(days=300)).isoformat()}
    check("Contradiction: fault before purchase",
          evaluate_claim(c, pol)["label"] == REVIEW)

    c = {**claim, "fault_date": (TODAY + timedelta(days=5)).isoformat()}
    check("Contradiction: fault after claim date",
          evaluate_claim(c, pol)["label"] == REVIEW)

    # ---- boundary dates (the tricky ones evaluators love)
    pol_ha = policies["Home Appliances"]
    purchase = TODAY - timedelta(days=365)           # 12-month warranty
    expiry = purchase + timedelta(days=365)
    c = {"purchase_date": purchase.isoformat(),
         "warranty_months": 12, "warranty_type": "standard",
         "extended_months": 0,
         "fault_date": expiry.isoformat(),            # fault ON expiry day
         "claim_date": (expiry + timedelta(days=2)).isoformat(),
         "fault_category": "motor_failure", "repair_count": 0,
         "last_repair_date": "", "authorized_repair": True,
         "serial_match": True, "has_receipt": True,
         "has_warranty_card": True, "has_product_image": True,
         "has_serial_evidence": True, "has_fault_evidence": True,
         "has_repair_report": False, "prior_claim_count": 0,
         "duplicate_invoice": False, "replaced_before": False}
    out = evaluate_claim(c, pol_ha)
    check("Boundary: fault exactly ON expiry date = still valid",
          out["label"] == VALID, f"got {out['label']}")

    c2 = {**c, "fault_date": (expiry + timedelta(days=1)).isoformat()}
    out = evaluate_claim(c2, pol_ha)
    check("Boundary: fault 1 day AFTER expiry = grace period review "
          f"(grace={pol_ha['grace_period_days']}d)",
          out["label"] == REVIEW if pol_ha["grace_period_days"] > 0
          else out["label"] == INVALID)

    deadline = pol["claim_reporting_period_days"]
    c3 = {**claim, "claim_date": (TODAY - timedelta(days=10 + deadline)
                                   ).isoformat() + " "}
    # claim_date = fault + exactly 'deadline' days -> on time
    c3 = {**claim,
          "fault_date": (TODAY - timedelta(days=10 + deadline)).isoformat(),
          "claim_date": (TODAY - timedelta(days=10)).isoformat()}
    check(f"Boundary: reported exactly ON {deadline}-day deadline = valid",
          evaluate_claim(c3, pol)["label"] == VALID)

    # ---- category policy differences (config-driven proof)
    check("Policies differ: grace period Electronics vs Home Appliances",
          policies["Electronics"]["grace_period_days"]
          != policies["Home Appliances"]["grace_period_days"],
          "policies unexpectedly identical")

    print(f"\nRULE ENGINE SUITE: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    ok = run()
    raise SystemExit(0 if ok else 1)