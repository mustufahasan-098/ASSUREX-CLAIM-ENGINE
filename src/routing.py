"""AssureX Intelligent Claim Routing - service-center matching.

Matches approved claims to certified repair centers by product category
and customer city, with SLA windows and a ranked recommendation list.
Purely additive: runs AFTER the claim decision; never touches the rule
engine, models, or fusion logic.

Config-driven (config/service_centers.json) - centers, SLAs and the
city-proximity map are data, not code, so evaluators can add or modify
centers without touching the application (surprise-modification ready).
"""
import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "service_centers.json"


def load_centers():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def match_centers(claim, city=None, limit=3):
    """Rank certified centers for a claim.

    Ranking: (1) same city + category match, (2) nearby city + category,
    (3) any city + category - sorted by SLA then rating.
    Returns list of {center, eta, reason} dicts.
    """
    cfg = load_centers()
    city = (city or cfg.get("default_city", "")).strip().title()
    nearby_city = cfg.get("nearby", {}).get(city)
    cat = claim.get("product_category")

    def eligible(c):
        return cat in c["categories"]

    candidates = [c for c in cfg["centers"] if eligible(c)]
    if not candidates:
        return []

    def rank(c):
        if c["city"] == city:
            tier = 0
        elif nearby_city and c["city"] == nearby_city:
            tier = 1
        else:
            tier = 2
        return (tier, c["sla_days"], -c["rating"])

    results = []
    for c in sorted(candidates, key=rank)[:limit]:
        eta = date.today() + timedelta(days=c["sla_days"])
        if c["city"] == city:
            reason = f"In your city - certified for {cat}"
        elif nearby_city and c["city"] == nearby_city:
            reason = f"Nearest certified city ({c['city']}) for {cat}"
        else:
            reason = f"Certified for {cat} (ships to {c['city']})"
        results.append({"center": c, "eta": eta.isoformat(), "reason": reason})
    return results


def sla_deadline(sla_days):
    return (date.today() + timedelta(days=sla_days)).isoformat()