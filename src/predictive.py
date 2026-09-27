"""AssureX Predictive Warranty Risk - forward-looking fault risk per product.

Statistical estimate from the project's own 1,500-claim dataset: fault
propensity by category and age band, adjusted for repair history and
warranty runway. Rule/stat based - every risk level carries its
reasoning. NOT a prediction of a specific failure; a prioritisation
signal for inspection and renewal attention."""
import csv
from datetime import date
from pathlib import Path

from .features import add_months, parse_date

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "all_claims.csv"
_cache = {}


def _bucket(days):
    if days < 90:
        return "0-90d"
    if days < 365:
        return "90d-1y"
    if days < 730:
        return "1-2y"
    return "2y+"


def _stats():
    if _cache:
        return _cache
    stats = {}
    try:
        with open(DATA, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                p = parse_date(row["purchase_date"])
                fl = parse_date(row["fault_date"])
                if not p or not fl:
                    continue
                age = max(0, (fl - p).days)
                stats.setdefault(row["product_category"], {})
                b = _bucket(age)
                stats[row["product_category"]][b] = \
                    stats[row["product_category"]].get(b, 0) + 1
    except Exception:
        pass
    _cache.update(stats)
    return stats


def product_risk(product, today=None):
    """Returns (risk_level, reasons) - LOW / ELEVATED / HIGH."""
    today = today or date.today()
    stats = _stats()
    cat = product.get("product_category", "")
    purchase = parse_date(product.get("purchase_date", ""))
    if not purchase:
        return "LOW", ["Insufficient data for risk estimation."]

    age = max(0, (today - purchase).days)
    b = _bucket(age)
    cat_stats = stats.get(cat, {})
    total = sum(cat_stats.values()) or 1
    rate = cat_stats.get(b, 0) / total

    repairs = int(product.get("repair_count", 0) or 0)
    end = add_months(purchase,
                     int(product.get("warranty_months", 12) or 12)
                     + int(product.get("extended_months", 0) or 0))
    days_left = (end - today).days

    score, reasons = 0, []
    if rate >= 0.30:
        score += 1
        reasons.append(f"Age band {b} is a high-fault period for {cat} "
                       f"({rate:.0%} of that category's historical faults)")
    if repairs >= 1:
        score += 1
        reasons.append(f"{repairs} prior repair(s) - repaired products "
                       f"show elevated re-fault rates")
    if 0 <= days_left <= 90:
        score += 1
        reasons.append(f"Warranty ends in {days_left} days")

    level = "LOW" if score == 0 else ("ELEVATED" if score == 1 else "HIGH")
    if not reasons:
        reasons.append(f"Normal fault profile for {cat} at age {b}")
    return level, reasons