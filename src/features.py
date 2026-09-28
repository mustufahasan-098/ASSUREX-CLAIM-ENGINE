"""AssureX Claim Engine - shared feature computation.

Single source of truth for derived features, imported by:
  - the dataset generator (label derivation via the rule engine)
  - the Claim Summary Card renderer (Step 2)
  - the preprocessing pipeline for the Python model (Step 3)
  - the live application rule engine (Step 4)

Because every component imports these same functions, engineered features
can never drift between training time and prediction time.
"""
import calendar
from datetime import date, datetime, timedelta

     
     
     
DATE_FORMATS = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"]


def parse_date(value):
    """Parse a date using any supported format. Returns None for empty values
    so callers can decide how to handle missing dates."""
    if value in (None, "", "NA"):
        return None
    if isinstance(value, date):
        return value
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(str(value), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unparseable date: {value!r}")


def to_bool(value):
    """Normalise booleans that may arrive as Python bools, strings from CSV
    ("True"/"False"), or Firestore values. Prevents the classic bug where
    the string "False" is truthy."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes")


def add_months(d, months):
    """Add calendar months to a date, clipping the day to the end of the
    target month (e.g. 31 Jan + 1 month = 28/29 Feb)."""
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def warranty_expiry(claim):
    """Warranty end date, including extended months when applicable."""
    purchase = parse_date(claim["purchase_date"])
    months = int(claim.get("warranty_months") or 0)
    if str(claim.get("warranty_type", "standard")).lower() == "extended":
        months += int(claim.get("extended_months") or 0)
    return add_months(purchase, months)


def missing_documents(claim, policy):
    """Return the list of mandatory documents missing for this claim."""
    return [doc for doc in policy["mandatory_documents"]
            if not to_bool(claim.get(f"has_{doc}", False))]


def compute_derived(claim, policy):
    """All engineered features used by the model, cards, and rule engine."""
    purchase = parse_date(claim["purchase_date"])
    fault = parse_date(claim["fault_date"])
    claim_d = parse_date(claim["claim_date"])
    expiry = warranty_expiry(claim)
    grace_days = int(policy["grace_period_days"])
    missing = missing_documents(claim, policy)
    return {
        "product_age_days": (fault - purchase).days if fault and purchase else None,
        "warranty_days_remaining": (expiry - fault).days if fault else None,
        "days_to_report": (claim_d - fault).days if fault and claim_d else None,
        "missing_docs": missing,
        "missing_docs_count": len(missing),
        "warranty_expired": bool(fault and fault > expiry),
        "within_grace": bool(fault and expiry < fault <= expiry + timedelta(days=grace_days)),
    }