"""AssureX Claim Engine - model comparison + fusion decision engine.

Implements SRS Steps 10-12: compares the Python classification model with
the Google Teachable Machine model, combines both with the warranty rule
engine, and produces the final three-way decision with a full explanation
(req xxii-xxv, xxxiv, xxxv).

Design principles:
  - All thresholds come from config/settings.yaml (never hard-coded), so
    fusion behaviour can be changed during the surprise-modification round
    by editing one YAML file - no code changes.
  - Rules outrank models: an optimistic model can never override a violated
    warranty rule.
  - Everything uncertain routes to Manual Review - the system never
    auto-decides a claim it is not confident about.
"""
from .features import missing_documents, parse_date, warranty_expiry


def compare_models(py_pred, py_probs, tm_pred, tm_probs, cfg):
    """SRS Step 10 (req xxii-xxiv): predicted-class match, top-class
    confidence difference, and the consistency status."""
    py_top, tm_top = py_probs[py_pred], tm_probs[tm_pred]
    diff = abs(py_top - tm_top)
    if py_pred != tm_pred:
        status = "Model Disagreement"
    elif py_top < cfg["min_confidence"] and tm_top < cfg["min_confidence"]:
        status = "Uncertain Result"
    elif diff <= cfg["strong_match_max_diff"]:
        status = "Strong Match"
    elif diff <= cfg["acceptable_match_max_diff"]:
        status = "Acceptable Match"
    else:
        status = "Weak Match"
    return {"match": py_pred == tm_pred, "conf_diff": round(diff, 4),
            "consistency": status}


def decide(rule_out, cmp, py_pred, tm_pred, py_probs, tm_probs, cfg, dup):
    """SRS Step 12 (req xxxiv-xxxv): final decision by combining the rule
    outcome, both model predictions, the confidence comparison and
    duplicate indicators. Returns the decision plus supporting/opposing
    factors that power the explanation screen."""
    hard, contra, flags = (rule_out["hard_fails"],
                           rule_out["contradictions"],
                           rule_out["review_flags"])
    support, oppose = [], []
    py_top, tm_top = py_probs[py_pred], tm_probs[tm_pred]

    if not hard and not contra:
        support.append("No hard-fail warranty rules triggered")

    # ---- priority 1: contradictory data cannot be auto-decided
    if contra:
        final = "Manual Review Required"
        oppose.append("Contradictory claim data detected - cannot be auto-decided:")
        oppose += contra
    # ---- priority 2: hard rule violations
    elif hard:
        final = "Likely Invalid"
        oppose.append("Warranty rule violations:")
        oppose += hard
    # ---- priority 3: review-level conditions
    elif flags:
        final = "Manual Review Required"
        oppose.append("Conditions require manual verification:")
        oppose += flags
    # ---- priority 4: models + rules both clean -> decide by agreement
    else:
        if (cmp["match"] and py_pred == "Valid Claim"
                and cmp["consistency"] in ("Strong Match", "Acceptable Match")):
            final = "Likely Valid"
            support.append(f"Both models agree: Valid Claim "
                           f"(confidence difference {cmp['conf_diff']:.2f})")
            support.append("All mandatory documents present")
            support.append("All warranty rules passed")
        elif cmp["match"] and py_pred == "Invalid Claim":
            final = "Likely Invalid"
            oppose.append(f"Both models agree the claim is Invalid "
                          f"({cmp['consistency']})")
        else:
            final = "Manual Review Required"
            if not cmp["match"]:
                oppose.append(f"Model disagreement: Python model says "
                              f"'{py_pred}' but Teachable Machine says "
                              f"'{tm_pred}'")
            elif py_pred == "Valid Claim":
                oppose.append(f"Models agree on Valid but consistency is "
                              f"'{cmp['consistency']}' "
                              f"(difference {cmp['conf_diff']:.2f})")
            else:
                oppose.append(f"Models agree on '{py_pred}' while all rules "
                              f"passed - human confirmation advised")

    # ---- duplicate indicators can only downgrade, never upgrade
    if dup.get("invoice_reused"):
        oppose.append("Invoice number already used in a previous claim")
        if final == "Likely Valid":
            final = "Manual Review Required"
    if dup.get("doc_hash_reuse"):
        oppose.append("An uploaded document was already used in another claim "
                      f"({', '.join(dup.get('reused_doc_claims', [])[:3])})")
        if final == "Likely Valid":
            final = "Manual Review Required"
    if dup.get("doc_mismatch"):
        oppose.append("Receipt verification failed: "
                      + str(dup.get("doc_mismatch_note",
                                    "uploaded receipt does not match the "
                                    "registered product")))
    fs = int(dup.get("fraud_score", 0) or 0)
    if fs >= 60:
        oppose.append(f"High fraud risk ({fs}/100) - multiple independent "
                      f"risk indicators; routed for manual verification")
        if final in ("Likely Valid", "Likely Invalid"):
            final = "Manual Review Required"
        if final == "Likely Valid":
            final = "Manual Review Required"
    # ---- confidence annotations (never change the decision, only explain)
    if cmp["match"] and cmp["conf_diff"] > cfg["acceptable_match_max_diff"]:
        oppose.append(f"Large confidence difference between models "
                      f"({cmp['conf_diff']:.2f})")
    if py_top < cfg["min_confidence"]:
        oppose.append(f"Python model confidence below threshold "
                      f"({py_top:.2f} < {cfg['min_confidence']})")
    if tm_top < cfg["min_confidence"]:
        oppose.append(f"Teachable Machine confidence below threshold "
                      f"({tm_top:.2f} < {cfg['min_confidence']})")

    return {"final": final, "support": support, "oppose": oppose,
            "warnings": rule_out.get("warnings", [])}


def build_summary(claim, policy, decision, cmp):
    """AI-generated claim summary (req xxxii). Template/rule-based by
    design - NO external generative-AI API is involved in any decision or
    summary text (SRS 1.10.15)."""
    expiry = warranty_expiry(claim)
    fault = parse_date(claim["fault_date"])
    missing = missing_documents(claim, policy)
    p = [f"**Claim {claim['claim_id']}** covers a {claim['brand']} "
         f"{claim['model']} ({claim['product_category']}) purchased on "
         f"{claim['purchase_date']}.",
         f"The customer reports a **{claim['fault_category'].replace('_', ' ')}"
         f"** fault on {claim['fault_date']}, submitted on {claim['claim_date']}."]
    if fault and expiry:
        state = "expired" if fault > expiry else "active"
        p.append(f"Warranty runs to {expiry.isoformat()} and was **{state}** "
                 f"at the fault date.")
    if missing:
        p.append(f"Missing mandatory documents: {', '.join(missing)}.")
    rules = decision.get("_rule_out", {})
    if rules.get("contradictions"):
        p.append("Data contradictions detected: "
                 + "; ".join(rules["contradictions"]) + ".")
    if rules.get("hard_fails"):
        p.append("Rule violations: " + "; ".join(rules["hard_fails"]) + ".")
    elif rules.get("review_flags"):
        p.append("Items needing verification: "
                 + "; ".join(rules["review_flags"]) + ".")
    else:
        p.append("All warranty checks passed with complete documentation.")
    p.append(f"The Python model and the Teachable Machine model "
             f"{'agree' if cmp['match'] else 'disagree'} on this claim "
             f"({cmp['consistency']}, confidence difference "
             f"{cmp['conf_diff']:.2f}).")
    p.append(f"**Final recommendation: {decision['final']}.**")
    return " ".join(p)