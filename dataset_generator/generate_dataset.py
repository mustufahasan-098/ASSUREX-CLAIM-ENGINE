"""AssureX Claim Engine - Warranty Claim Dataset Generator.

Generates 1,500 unique synthetic warranty claims (500 per class) across three
product categories, labels each claim with the SAME rule engine the live
application uses (src/rules.py), and writes stratified 70/15/15
train/validation/test splits.

The 'scenario' column is deliberately EXCLUDED from the CSVs - it would leak
the label. Scenario counts are reported in dataset_stats.json only.

Reproducible: fixed seed and anchor date produce an identical dataset on
every run (important for the report and for evaluator verification).

Run from the project root:
    python -m dataset_generator.generate_dataset
"""
import csv
import json
import random
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from src.features import add_months, parse_date, warranty_expiry
from src.rules import evaluate_claim, load_policies

SEED = 42
ANCHOR = date(2025, 9, 20)        # fixed reference date -> reproducible dataset
TRAIN, VAL, TEST = 350, 75, 75    # per class: 70/15/15 of 500

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

PRODUCTS = {
    "Electronics": [
        ("Samsung", "Galaxy S22"), ("Sony", "Bravia X75"), ("LG", "OLED C3"),
        ("Xiaomi", "Redmi Note 12"), ("HP", "Pavilion 15"), ("Apple", "iPhone 13"),
        ("Dell", "Inspiron 5518"), ("Lenovo", "IdeaPad Slim 3"),
    ],
    "Home Appliances": [
        ("Whirlpool", "WM 2500"), ("LG", "Fridge 340L"), ("Bosch", "Serie 6 Washer"),
        ("IFB", "Senorita SX"), ("Samsung", "RT28 Refrigerator"), ("Godrej", "WD 700"),
    ],
    "Power Tools": [
        ("Bosch", "GSR 18V"), ("DeWalt", "DCD771"), ("Makita", "HP457"),
        ("Black+Decker", "CD701"), ("Stanley", "SXD201"),
    ],
}

# scenario name -> (label, count). Each class sums to exactly 500.
SCENARIOS = {
    "Valid Claim": [
        ("clean_active_warranty", 280),
        ("valid_with_prior_authorized_repair", 70),
        ("valid_extended_warranty", 60),
        ("boundary_fault_on_expiry_date", 45),
        ("boundary_reported_on_deadline", 45),
    ],
    "Invalid Claim": [
        ("expired_warranty_beyond_grace", 200),
        ("excluded_fault_or_damage", 140),
        ("unauthorized_repair", 60),
        ("reported_after_deadline", 80),
        ("product_already_replaced", 20),
    ],
    "Manual Review": [
        ("missing_mandatory_documents", 120),
        ("serial_number_mismatch", 80),
        ("duplicate_claim_indicators", 70),
        ("contradictory_dates", 70),
        ("fault_within_grace_period", 60),
        ("excessive_repair_history", 50),
        ("early_fault_doa_window", 50),
    ],
}


# ------------------------------------------------------------------ helpers
def base_claim(rng, category, policy, min_purchase_age_days=None):
    """Random claim skeleton. Purchase date is pushed far enough back that
    every downstream date (fault, claim) stays before the ANCHOR date, so no
    generated record is ever dated in the future."""
    brand, model = rng.choice(PRODUCTS[category])
    span_days = int(policy["standard_warranty_months"]) * 31
    need = min_purchase_age_days or (span_days + 200)
    earliest = ANCHOR - timedelta(days=2100)
    latest = ANCHOR - timedelta(days=need)
    purchase = earliest + timedelta(days=rng.randint(0, max(1, (latest - earliest).days)))
    return {
        "claim_id": "",
        "user_id": f"USR-{rng.randint(1000, 9999)}",
        "product_category": category,
        "brand": brand,
        "model": model,
        "serial_number": f"SN{rng.randint(10**7, 10**8 - 1)}",
        "purchase_date": purchase.isoformat(),
        "purchase_price": round(rng.uniform(80, 3000), 2),
        "warranty_type": "standard",
        "warranty_months": policy["standard_warranty_months"],
        "extended_months": 0,
        "fault_date": "",
        "claim_date": "",
        "fault_category": rng.choice(policy["covered_faults"]),
        "repair_count": 0,
        "last_repair_date": "",
        "authorized_repair": True,
        "serial_match": True,
        "invoice_number": f"INV-{rng.randint(10**5, 10**6 - 1)}",
        "has_receipt": True,
        "has_warranty_card": True,
        "has_product_image": True,
        "has_serial_evidence": True,
        "has_fault_evidence": True,
        "has_repair_report": False,
        "prior_claim_count": 0,
        "duplicate_invoice": False,
        "replaced_before": False,
    }


def set_valid_timing(rng, claim, policy, fault=None):
    """Place the fault inside the warranty and the claim inside the
    reporting deadline (so no timing rule fires)."""
    purchase = parse_date(claim["purchase_date"])
    expiry = warranty_expiry(claim)
    if fault is None:
        span = (expiry - purchase).days
        lo = max(45, int(span * 0.10))
        hi = max(lo + 1, int(span * 0.90))
        fault = purchase + timedelta(days=rng.randint(lo, hi))
    claim["fault_date"] = fault.isoformat()
    deadline = int(policy["claim_reporting_period_days"])
    claim["claim_date"] = (fault + timedelta(days=rng.randint(1, deadline))).isoformat()
    return claim


def add_authorized_repair(rng, claim):
    """Add a plausible authorized repair between purchase and fault."""
    purchase = parse_date(claim["purchase_date"])
    fault = parse_date(claim["fault_date"])
    claim["last_repair_date"] = (
        purchase + timedelta(days=rng.randint(30, max(31, (fault - purchase).days - 1)))
    ).isoformat()
    claim["has_repair_report"] = True
    return claim


# ------------------------------------------------------- valid scenarios
def sc_clean_active_warranty(rng, cat, pol):
    return set_valid_timing(rng, base_claim(rng, cat, pol), pol)


def sc_valid_with_prior_authorized_repair(rng, cat, pol):
    c = sc_clean_active_warranty(rng, cat, pol)
    c["repair_count"] = rng.randint(1, int(pol["max_prior_repairs"]))
    c["authorized_repair"] = True
    return add_authorized_repair(rng, c)


def sc_valid_extended_warranty(rng, cat, pol):
    options = [m for m in (12, 24) if m <= int(pol["extended_warranty_max_months"])]
    ext = rng.choice(options)
    need = (int(pol["standard_warranty_months"]) + ext) * 31 + 45
    c = base_claim(rng, cat, pol, min_purchase_age_days=need)
    c["warranty_type"] = "extended"
    c["extended_months"] = ext
    purchase = parse_date(c["purchase_date"])
    standard_end = add_months(purchase, int(pol["standard_warranty_months"]))
    full_end = warranty_expiry(c)
    window = (full_end - standard_end).days
    fault = standard_end + timedelta(days=rng.randint(15, max(16, window - 15)))
    return set_valid_timing(rng, c, pol, fault=fault)


def sc_boundary_fault_on_expiry_date(rng, cat, pol):
    c = base_claim(rng, cat, pol)
    return set_valid_timing(rng, c, pol, fault=warranty_expiry(c))


def sc_boundary_reported_on_deadline(rng, cat, pol):
    c = sc_clean_active_warranty(rng, cat, pol)
    fault = parse_date(c["fault_date"])
    c["claim_date"] = (fault + timedelta(days=int(pol["claim_reporting_period_days"]))).isoformat()
    return c


# ----------------------------------------------------- invalid scenarios
def sc_expired_warranty_beyond_grace(rng, cat, pol):
    span = int(pol["standard_warranty_months"]) * 31
    need = span + int(pol["grace_period_days"]) + 440 + int(pol["claim_reporting_period_days"])
    c = base_claim(rng, cat, pol, min_purchase_age_days=need)
    expiry = warranty_expiry(c)
    fault = expiry + timedelta(days=int(pol["grace_period_days"]) + rng.randint(5, 400))
    c["fault_date"] = fault.isoformat()
    c["claim_date"] = (fault + timedelta(days=rng.randint(1, int(pol["claim_reporting_period_days"])))).isoformat()
    return c


def sc_excluded_fault_or_damage(rng, cat, pol):
    c = sc_clean_active_warranty(rng, cat, pol)
    c["fault_category"] = rng.choice(pol["excluded_faults"])
    return c


def sc_unauthorized_repair(rng, cat, pol):
    c = sc_clean_active_warranty(rng, cat, pol)
    c["repair_count"] = rng.randint(1, int(pol["max_prior_repairs"]))
    c["authorized_repair"] = False
    return add_authorized_repair(rng, c)


def sc_reported_after_deadline(rng, cat, pol):
    c = sc_clean_active_warranty(rng, cat, pol)
    fault = parse_date(c["fault_date"])
    c["claim_date"] = (fault + timedelta(
        days=int(pol["claim_reporting_period_days"]) + rng.randint(5, 150))).isoformat()
    return c


def sc_product_already_replaced(rng, cat, pol):
    c = sc_clean_active_warranty(rng, cat, pol)
    c["replaced_before"] = True
    return c


# ------------------------------------------------- manual-review scenarios
def sc_missing_mandatory_documents(rng, cat, pol):
    c = sc_clean_active_warranty(rng, cat, pol)
    docs = pol["mandatory_documents"]
    for doc in rng.sample(docs, k=min(rng.randint(1, 2), len(docs))):
        c[f"has_{doc}"] = False
    return c


def sc_serial_number_mismatch(rng, cat, pol):
    c = sc_clean_active_warranty(rng, cat, pol)
    c["serial_match"] = False
    return c


def sc_duplicate_claim_indicators(rng, cat, pol):
    c = sc_clean_active_warranty(rng, cat, pol)
    c["prior_claim_count"] = rng.randint(1, 2)
    if rng.random() < 0.5:
        c["duplicate_invoice"] = True
    return c


def sc_contradictory_dates(rng, cat, pol):
    c = sc_clean_active_warranty(rng, cat, pol)
    purchase = parse_date(c["purchase_date"])
    fault = parse_date(c["fault_date"])
    kind = rng.choice(["claim_before_purchase", "fault_before_purchase",
                       "fault_after_claim", "repair_before_purchase"])
    if kind == "claim_before_purchase":
        c["claim_date"] = (purchase - timedelta(days=rng.randint(1, 60))).isoformat()
    elif kind == "fault_before_purchase":
        c["fault_date"] = (purchase - timedelta(days=rng.randint(1, 120))).isoformat()
    elif kind == "fault_after_claim":
        c["claim_date"] = (fault - timedelta(days=rng.randint(1, 30))).isoformat()
    else:
        c["repair_count"] = 1
        c["has_repair_report"] = True
        c["last_repair_date"] = (purchase - timedelta(days=rng.randint(1, 200))).isoformat()
    return c


def sc_fault_within_grace_period(rng, cat, pol):
    span = int(pol["standard_warranty_months"]) * 31
    need = span + int(pol["grace_period_days"]) + int(pol["claim_reporting_period_days"]) + 40
    c = base_claim(rng, cat, pol, min_purchase_age_days=need)
    expiry = warranty_expiry(c)
    fault = expiry + timedelta(days=rng.randint(1, max(1, int(pol["grace_period_days"]))))
    c["fault_date"] = fault.isoformat()
    c["claim_date"] = (fault + timedelta(days=rng.randint(1, int(pol["claim_reporting_period_days"])))).isoformat()
    return c


def sc_excessive_repair_history(rng, cat, pol):
    c = sc_clean_active_warranty(rng, cat, pol)
    c["repair_count"] = rng.randint(int(pol["max_prior_repairs"]) + 1,
                                    int(pol["max_prior_repairs"]) + 3)
    c["authorized_repair"] = True
    return add_authorized_repair(rng, c)


def sc_early_fault_doa_window(rng, cat, pol):
    c = base_claim(rng, cat, pol)
    purchase = parse_date(c["purchase_date"])
    fault = purchase + timedelta(days=rng.randint(1, int(pol["early_fault_review_days"])))
    return set_valid_timing(rng, c, pol, fault=fault)


SCENARIO_FN = {name: globals()[f"sc_{name}"]
               for label in SCENARIOS for name, _ in SCENARIOS[label]}


# ------------------------------------------------------------------ main
def generate():
    rng = random.Random(SEED)
    policies = load_policies()
    grace_ok = [c for c, p in policies.items() if int(p["grace_period_days"]) >= 1]
    print(f"Policies loaded: {', '.join(policies)}")

    all_rows, mismatches = [], []
    for label, scen_list in SCENARIOS.items():
        for scen_name, count in scen_list:
            for _ in range(count):
                # grace-period scenario only makes sense where a grace period exists
                cat = rng.choice(grace_ok) if scen_name == "fault_within_grace_period" \
                    else rng.choice(list(policies))
                claim = SCENARIO_FN[scen_name](rng, cat, policies[cat])
                got = evaluate_claim(claim, policies[cat])["label"]
                if got != label:
                    mismatches.append((scen_name, label, got, claim))
                claim["label"] = label
                claim["scenario"] = scen_name
                all_rows.append(claim)

    if mismatches:
        print(f"\n!! {len(mismatches)} LABEL MISMATCHES - DO NOT PROCEED. First 5:")
        for m in mismatches[:5]:
            print(f"   scenario={m[0]} intended={m[1]} got={m[2]}")
        raise SystemExit(1)
    print(f"Label check: {len(all_rows)}/{len(all_rows)} OK "
          f"(rule engine agrees with intended labels)")

    rng.shuffle(all_rows)
    for i, row in enumerate(all_rows, 1):
        row["claim_id"] = f"CLM-{i:06d}"

    splits = {"train": [], "val": [], "test": []}
    by_label = {}
    for row in all_rows:
        by_label.setdefault(row["label"], []).append(row)
    for rows in by_label.values():          # rows already in random order
        splits["train"] += rows[:TRAIN]
        splits["val"] += rows[TRAIN:TRAIN + VAL]
        splits["test"] += rows[TRAIN + VAL:]

    DATA_DIR.mkdir(exist_ok=True)
    cols = [k for k in all_rows[0] if k != "scenario"]   # never leak the scenario!
    for split, rows in splits.items():
        rng.shuffle(rows)
        with open(DATA_DIR / f"{split}_claims.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for r in rows:
                w.writerow({k: r[k] for k in cols})
        print(f"Wrote data/{split}_claims.csv  ({len(rows)} rows: "
              f"{dict(sorted(Counter(r['label'] for r in rows).items()))})")

    with open(DATA_DIR / "all_claims.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in all_rows:
            w.writerow({k: r[k] for k in cols})

    with open(DATA_DIR / "claim_image_mapping.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["claim_id", "label", "split"])
        for split, rows in splits.items():
            for r in rows:
                w.writerow([r["claim_id"], r["label"], split])

    stats = {
        "seed": SEED, "anchor_date": ANCHOR.isoformat(), "total_claims": len(all_rows),
        "per_class": dict(sorted(Counter(r["label"] for r in all_rows).items())),
        "splits": {s: {"total": len(rows),
                       "by_label": dict(sorted(Counter(r["label"] for r in rows).items()))}
                   for s, rows in splits.items()},
        "scenarios": {label: dict(counts) for label, counts in SCENARIOS.items()},
    }
    (DATA_DIR / "dataset_stats.json").write_text(json.dumps(stats, indent=2))
    print("Wrote data/all_claims.csv, data/claim_image_mapping.csv, data/dataset_stats.json")
    print("\nSTEP 1 COMPLETE [OK]")


if __name__ == "__main__":
    generate()