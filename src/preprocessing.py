"""AssureX Claim Engine - feature engineering + preprocessing for the Python
classification model.

These functions are used at BOTH training time (src/train_model.py) and
prediction time (the live app), so engineered features can never drift
between the dataset and the application.

Pipeline stages (SRS Step 3 - Data Pre-Processing):
  - missing-value handling   -> derived date features become NaN and are
                                median-imputed inside the sklearn pipeline
  - date format conversion   -> src.features.parse_date (multi-format)
  - derived features         -> product age, remaining warranty, reporting
                                delay, missing-document count, coverage flags
  - categorical encoding     -> OneHotEncoder with handle_unknown='ignore'
                                (hidden claims may contain unseen brands)
  - numerical scaling        -> StandardScaler

Identifier columns (claim_id, user_id, serial_number, invoice_number) and raw
date strings are deliberately EXCLUDED: they carry no business meaning and
would invite shortcut learning instead of real warranty-claim patterns.
"""
import pandas as pd

from .features import compute_derived, to_bool

# Model-input price clamp (train/serve skew guard): the synthetic training
# dataset sampled purchase_price uniformly in [80, 3000]; live
# registrations carry realistic market prices (e.g. Rs 90,000 phones).
# Values far outside the training range make the tree ensemble hedge
# unnaturally, so the MODEL FEATURE is winsorized to the training range.
# This is a no-op for all training data (already in range) and only
# stabilizes live inference. The fraud layer reads the RAW price
# separately (realistic reference prices) - each layer gets the input
# it was designed for.
MODEL_PRICE_RANGE = (80.0, 3000.0)


def _clamp_price(value):
    if value != value:      # NaN stays NaN (imputer handles it)
        return value
    return min(max(value, MODEL_PRICE_RANGE[0]), MODEL_PRICE_RANGE[1])


NUMERIC_FEATURES = [
    "product_age_days",
    "warranty_days_remaining",
    "days_to_report",
    "missing_docs_count",
    "warranty_months",
    "extended_months",
    "purchase_price",
    "repair_count",
    "prior_claim_count",
]

BOOLEAN_FEATURES = [
    "authorized_repair",
    "serial_match",
    "duplicate_invoice",
    "replaced_before",
    "fault_covered",
    "fault_excluded",
    "has_receipt",
    "has_warranty_card",
    "has_product_image",
    "has_serial_evidence",
    "has_fault_evidence",
    "has_repair_report",
]

CATEGORICAL_FEATURES = [
    "product_category",
    "brand",
    "fault_category",
    "warranty_type",
]

ALL_FEATURES = NUMERIC_FEATURES + BOOLEAN_FEATURES + CATEGORICAL_FEATURES


def _f(value):
    """int/None -> float/NaN so the pipeline imputer can handle missing dates."""
    return float(value) if value is not None else float("nan")


def _num_or_nan(value, cast):
    if value in (None, "", "NA"):
        return float("nan")
    try:
        return float(cast(value))
    except (TypeError, ValueError):
        return float("nan")


def build_model_features(claim, policies):
    """Convert ONE raw claim (dict or pandas Series - from CSV or Firestore)
    into the model feature record. Works identically at training and serving
    time. Raises a clear error for unknown product categories."""
    category = claim.get("product_category")
    if category not in policies:
        raise ValueError(f"Unknown product category: {category!r}")
    policy = policies[category]

    derived = compute_derived(claim, policy)
    fault = claim.get("fault_category") or "unknown"

    features = {
        # ---- derived numerics (NaN when dates are missing -> imputed)
        "product_age_days": _f(derived["product_age_days"]),
        "warranty_days_remaining": _f(derived["warranty_days_remaining"]),
        "days_to_report": _f(derived["days_to_report"]),
        "missing_docs_count": float(derived["missing_docs_count"]),
        # ---- raw numerics
        "warranty_months": _num_or_nan(claim.get("warranty_months"), int),
        "extended_months": _num_or_nan(claim.get("extended_months"), int),
        "purchase_price": _clamp_price(
            _num_or_nan(claim.get("purchase_price"), float)),
        "repair_count": _num_or_nan(claim.get("repair_count"), int),
        "prior_claim_count": _num_or_nan(claim.get("prior_claim_count"), int),
        # ---- booleans as 0/1
        "authorized_repair": int(to_bool(claim.get("authorized_repair", True))),
        "serial_match": int(to_bool(claim.get("serial_match", True))),
        "duplicate_invoice": int(to_bool(claim.get("duplicate_invoice", False))),
        "replaced_before": int(to_bool(claim.get("replaced_before", False))),
        "fault_covered": int(fault in policy["covered_faults"]),
        "fault_excluded": int(fault in policy["excluded_faults"]),
        "has_receipt": int(to_bool(claim.get("has_receipt", False))),
        "has_warranty_card": int(to_bool(claim.get("has_warranty_card", False))),
        "has_product_image": int(to_bool(claim.get("has_product_image", False))),
        "has_serial_evidence": int(to_bool(claim.get("has_serial_evidence", False))),
        "has_fault_evidence": int(to_bool(claim.get("has_fault_evidence", False))),
        "has_repair_report": int(to_bool(claim.get("has_repair_report", False))),
        # ---- categoricals (encoded inside the sklearn pipeline)
        "product_category": category,
        "brand": claim.get("brand") or "Unknown",
        "fault_category": fault,
        "warranty_type": claim.get("warranty_type") or "standard",
    }
    return features


def build_feature_frame(rows, policies):
    """Build the model input DataFrame from an iterable of raw claim records.
    Row order is preserved, so predictions stay aligned with claim IDs."""
    return pd.DataFrame([build_model_features(r, policies) for r in rows])