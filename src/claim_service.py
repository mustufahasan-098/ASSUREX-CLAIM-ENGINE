"""AssureX Claim Engine - end-to-end claim evaluation pipeline.

Pipeline (SRS Steps 2, 6, 7, 9, 10, 11, 12):
  duplicate detection -> warranty rule engine -> Python classification
  model -> Claim Summary Card generation -> Teachable Machine
  classification -> model comparison -> fusion decision -> Firestore
  persistence + audit trail + notifications + model-version tracking.

Every claim record stores the full evidence chain (both predictions, all
confidence scores, rule outcomes, model versions) so any decision can be
reconstructed later (SRS req xlvii, xlviii).
"""
import hashlib
from datetime import datetime
from pathlib import Path

from card_generator.generate_cards import render_card
from . import firebase_db as fdb
from . import models as models_mod
from .fusion import build_summary, compare_models, decide
from .preprocessing import build_feature_frame
from .rules import evaluate_claim
from . import fraud_intel
ROOT = Path(__file__).resolve().parent.parent
UPLOADS = ROOT / "uploads"
DOC_TYPES = ["receipt", "warranty_card", "product_image",
             "serial_evidence", "fault_evidence", "repair_report"]


# ------------------------------------------------------------------ duplicates
def detect_duplicates(claim, docs):
    """Duplicate-claim and duplicate-document detection (req xxx, xxxi):
    same serial with prior claims, reused invoice numbers, and document
    hashes that already appeared in another claim (SHA-256)."""
    prior = fdb.query("claims", "serial_number", "==", claim["serial_number"])
    same_invoice = fdb.query("claims", "invoice_number", "==",
                             claim["invoice_number"])
    doc_reuse = []
    for d in docs:
        for hit in fdb.query("claims", "doc_hashes", "array_contains",
                             d["sha256"], limit=5):
            doc_reuse.append(hit["claim_id"])
    return {"prior_claims": len(prior),
            "invoice_reused": bool(same_invoice),
            "doc_hash_reuse": bool(doc_reuse),
            "reused_doc_claims": sorted(set(doc_reuse))[:5]}


# ------------------------------------------------------------------ pipeline
def process_claim(claim):
    """Runs the full dual-model evaluation for one claim dict.
    Returns every intermediate result (used by the result screen)."""
    m = models_mod.load_all()
    policy = m["policies"][claim["product_category"]]
    cfg = m["settings"]["fusion"]

    # 1. warranty rule engine (SRS step 11)
    rules = evaluate_claim(claim, policy)

    # 2. python classification model + confidence scores (SRS step 6)
    X = build_feature_frame([claim], m["policies"])
    proba = m["py_model"].predict_proba(X)[0]
    py_probs = {cls: float(p) for cls, p in zip(m["le"].classes_, proba)}
    py_pred = max(py_probs, key=py_probs.get)

    # 3. claim summary card -> teachable machine (SRS steps 7, 9)
    card = render_card(claim, policy)
    tm_probs = m["tm"].predict(card)
    tm_pred = max(tm_probs, key=tm_probs.get)

    # 4. comparison + fusion decision (SRS steps 10, 12)
    cmp = compare_models(py_pred, py_probs, tm_pred, tm_probs, cfg)
    dup = claim.get("_dup", {})
    decision = decide(rules, cmp, py_pred, tm_pred, py_probs, tm_probs,
                      cfg, dup)
    decision["_rule_out"] = rules
    summary = build_summary(claim, policy, decision, cmp)

    return {"rules": rules, "py_pred": py_pred, "py_probs": py_probs,
            "tm_pred": tm_pred, "tm_probs": tm_probs, "comparison": cmp,
            "decision": decision, "summary": summary, "card": card,
            "policy": policy}


def process_and_save(claim, docs, actor):
    """Full pipeline + persistence: assigns the Claim ID, detects
    duplicates, evaluates, saves documents, writes the claim record with
    the complete evidence chain, and logs audit + notification."""
    m = models_mod.load_all()
    claim["claim_id"] = fdb.next_claim_id()

        # ---- duplicate detection + 7-layer fraud intelligence
    incoming = claim.pop("_dup", {}) or {}
    dup = detect_duplicates(claim, docs)
    # preserve receipt-mismatch flags computed at upload time (app.py)
    for k, v in incoming.items():
        if k.startswith("doc_mismatch"):
            dup[k] = v
    for d in docs:
        d["phash"] = fraud_intel.dhash_from_bytes(d["bytes"])
    owner_claims = fdb.query("claims", "owner_email", "==", claim["user_id"])
    serial_claims = fdb.query("claims", "serial_number", "==",
                              claim["serial_number"])
    all_claims = fdb.all_docs("claims", limit=500)
    fraud = fraud_intel.analyze(claim, dup, owner_claims, serial_claims,
                                all_claims, docs,
                                claim.get("ocr_verification"))
    dup["fraud_score"] = fraud["score"]
    dup["fraud_escalated"] = fraud["escalated"]
    claim["prior_claim_count"] = dup["prior_claims"]
    claim["duplicate_invoice"] = dup["invoice_reused"]
    claim["_dup"] = dup

    res = process_claim(claim)
        # derived-feature snapshot (SRS Step 3 - displayed on the result page)
    from .features import compute_derived
    derived = compute_derived(claim, res["policy"])
    derived = {k: (v if not isinstance(v, list) else ", ".join(map(str, v)))
               for k, v in derived.items()}
    final = res["decision"]["final"]

    # map the fusion decision onto the claim-status workflow (req xxxviii)
    if final == "Likely Valid":
        status = "Approved"
    elif final == "Likely Invalid" and res["comparison"]["match"]:
        status = "Rejected"
    else:
        status = "Manual Review"

    # store uploaded files on disk, metadata (incl. sha256) in the record
    folder = UPLOADS / claim["claim_id"]
    folder.mkdir(parents=True, exist_ok=True)
    doc_meta, hashes = [], []
    for d in docs:
        safe = d["name"].replace("/", "_").replace("\\", "_")
        (folder / f"{d['type']}__{safe}").write_bytes(d["bytes"])
        doc_meta.append({"type": d["type"], "filename": d["name"],
                         "sha256": d["sha256"], "size": len(d["bytes"])})
        hashes.append(d["sha256"])

    now = datetime.now().isoformat(timespec="seconds")
    record = {k: v for k, v in claim.items() if not k.startswith("_")}
    record.update({
        "owner_email": claim["user_id"], "documents": doc_meta,
        "doc_hashes": hashes, "duplicates": dup,
        "doc_phashes": [d["phash"] for d in docs if d.get("phash")],
        "fraud": fraud,
        "rules_outcome": res["rules"],
        "derived_features": derived,
        "python_pred": res["py_pred"], "python_probs": res["py_probs"],
        "tm_pred": res["tm_pred"], "tm_probs": res["tm_probs"],
        "conf_diff": res["comparison"]["conf_diff"],
        "consistency": res["comparison"]["consistency"],
        "py_top_conf": res["py_probs"][res["py_pred"]],
        "tm_top_conf": res["tm_probs"][res["tm_pred"]],
        "final_decision": final, "explanation": res["decision"],
        "summary": res["summary"], "status": status,
        "created_at": now,
        "model_versions": {
            "python": f"{m['py_meta']['model_version']} "
                      f"({m['py_meta']['algorithm']})",
            "tm": m["tm_version"]},
        "timeline": [{"ts": now, "actor": actor,
                      "event": f"Claim submitted - evaluated as '{final}' "
                               f"-> status '{status}'"}],
    })
    fdb.set_doc("claims", claim["claim_id"], record)
    fdb.log_audit("claim_submitted", actor,
                  {"claim_id": claim["claim_id"], "final": final,
                   "status": status})
    fdb.notify(claim["user_id"], claim["claim_id"],
               f"Claim {claim['claim_id']} submitted - status: {status}")
    return {**res, "claim_id": claim["claim_id"], "status": status,
            "duplicates": dup}


def update_claim(cid, updates, event=None, actor="system"):
    """Partial claim update with an automatic timeline entry."""
    doc = fdb.get_doc("claims", cid)
    if not doc:
        return
    doc.update(updates)
    if event:
        doc.setdefault("timeline", []).append(
            {"ts": datetime.now().isoformat(timespec="seconds"),
             "actor": actor, "event": event})
    doc.pop("_id", None)
    fdb.set_doc("claims", cid, doc)


# ------------------------------------------------------------------ reporting
def build_report(claim):
    """Downloadable per-claim report (req xliv): every prediction,
    confidence score, rule result, contradiction and reviewer action."""
    r = claim.get("rules_outcome", {})
    ex = claim.get("explanation", {})
    lines = [
        f"# AssureX Claim Report - {claim['claim_id']}",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Claim details",
        f"- Product: {claim.get('brand', '')} {claim.get('model', '')} "
        f"({claim.get('product_category', '')})",
        f"- Serial: {claim.get('serial_number', '')} | "
        f"Invoice: {claim.get('invoice_number', '')}",
        f"- Purchase: {claim.get('purchase_date', '')} | "
        f"Fault: {claim.get('fault_date', '')} "
        f"({claim.get('fault_category', '')})",
        f"- Claim date: {claim.get('claim_date', '')}",
        "- Documents: "
        + (", ".join(d["type"] for d in claim.get("documents", []))
           or "none uploaded"),
        "",
        "## Python classification model",
        f"- Predicted: {claim.get('python_pred', '')} "
        f"({claim.get('py_top_conf', 0):.1%})",
        "- Probabilities: " + ", ".join(
            f"{k}={v:.1%}" for k, v in claim.get("python_probs", {}).items()),
        f"- Model version: {claim.get('model_versions', {}).get('python', '')}",
        "",
        "## Google Teachable Machine model",
        f"- Predicted: {claim.get('tm_pred', '')} "
        f"({claim.get('tm_top_conf', 0):.1%})",
        "- Probabilities: " + ", ".join(
            f"{k}={v:.1%}" for k, v in claim.get("tm_probs", {}).items()),
        f"- Model version: {claim.get('model_versions', {}).get('tm', '')}",
        "",
        "## Model comparison",
        f"- Consistency: {claim.get('consistency', '')}",
        f"- Top-class confidence difference: {claim.get('conf_diff', 0):.3f}",
        "",
        "## Warranty rule validation",
        f"- Rule-engine label: {r.get('label', '')}",
        f"- Contradictions: {r.get('contradictions') or 'none'}",
        f"- Hard-fail rules: {r.get('hard_fails') or 'none'}",
        f"- Review flags: {r.get('review_flags') or 'none'}",
        f"- Warnings: {r.get('warnings') or 'none'}",
        f"- Duplicate indicators: {claim.get('duplicates', {})}",
        "",
        "## Final decision",
        f"**{claim.get('final_decision', '')}** "
        f"(status: {claim.get('status', '')})",
        "",
        "Factors supporting: " + "; ".join(ex.get("support", [])),
        "Factors against: " + "; ".join(ex.get("oppose", [])),
        "",
        "## AI-generated summary",
        claim.get("summary", ""),
        "",
        "## Reviewer",
        f"- Reviewer: {claim.get('reviewer', '') or '-'}",
        f"- Comment: {claim.get('reviewer_comment', '') or '-'}",
        f"- Overrode AI recommendation: "
        f"{'Yes' if claim.get('override') else 'No'}",
        "",
        "## Timeline",
    ] + [f"- {t.get('ts', '')}: {t.get('event', '')} "
         f"({t.get('actor', '')})"
         for t in claim.get("timeline", [])]
    return "\n".join(lines)