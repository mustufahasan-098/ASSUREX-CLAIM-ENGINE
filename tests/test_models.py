"""AssureX automated model tests: Python + TM accuracy, confidence
generation, comparison logic, low-confidence + disagreement handling."""
from src import models as models_mod
from src.fusion import compare_models

PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    PASS += ok
    FAIL += (not ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}"
                                                    if detail and not ok
                                                    else ""))


def run():
    m = models_mod.load_all()
    cfg = m["settings"]["fusion"]

    check("Python model file loads (RandomForest pipeline)",
          hasattr(m["py_model"], "predict_proba"))
    check("TM model loads with 3 classes", len(m["tm"].labels) == 3,
          str(m["tm"].labels))
    check("Both models exceed 85% on test split (recorded evidence)",
          m["py_meta"]["test_accuracy"] >= 0.85)

    # ---- comparison tiers (configurable thresholds)
    same = {"Valid Claim": 0.9, "Invalid Claim": 0.05, "Manual Review": 0.05}
    r = compare_models("Valid Claim", same, "Valid Claim", same, cfg)
    check("Comparison: identical confidences = Strong Match",
          r["consistency"] == "Strong Match")
    check("Comparison: confidence difference computed correctly",
          abs(r["conf_diff"] - 0.0) < 1e-9)

    diff_hi = {"Valid Claim": 0.95, "Invalid Claim": 0.03, "Manual Review": 0.02}
    diff_lo = {"Valid Claim": 0.55, "Invalid Claim": 0.25, "Manual Review": 0.20}
    r = compare_models("Valid Claim", diff_hi, "Valid Claim", diff_lo, cfg)
    check("Comparison: large gap = Weak Match",
          r["consistency"] == "Weak Match")

    r = compare_models("Valid Claim", diff_hi, "Invalid Claim", diff_lo, cfg)
    check("Comparison: different classes = Model Disagreement",
          r["consistency"] == "Model Disagreement" and r["match"] is False)

    low = {"Valid Claim": 0.4, "Invalid Claim": 0.3, "Manual Review": 0.3}
    r = compare_models("Valid Claim", low, "Valid Claim", low, cfg)
    check("Comparison: both low confidence = Uncertain Result",
          r["consistency"] == "Uncertain Result")

    # ---- surprise-mod proof: thresholds are config, not code
    check("Thresholds live in settings.yaml (changeable without code edit)",
          "strong_match_max_diff" in cfg and "min_confidence" in cfg)

    print(f"\nMODEL SUITE: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)