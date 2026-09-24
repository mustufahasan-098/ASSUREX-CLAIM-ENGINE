"""AssureX Claim Engine - Manual Review Queue (req xxxvi, xxxvii).

Reviewers see every claim routed to manual review (low confidence, model
disagreement, missing evidence, contradictions, rule flags) and can
approve, reject, or request more information. Overrides of the AI
recommendation are recorded and preserved in the audit history.
"""
import streamlit as st

from card_generator.generate_cards import render_card
from src import claim_service as cs
from src import firebase_db as fdb
from src import models as models_mod
from ui.components import (alert, badge, empty_state, inject_css, kv_grid,
                           page_header, stat_row, status_badge)

REVIEW_STATUSES = ("Manual Review", "Additional Information Required")


def view():
    inject_css()
    user = st.session_state["user"]
    page_header("⚖️", "Manual Review Queue",
                "Claims that the AI could not confidently auto-decide — "
                "your judgment completes the system")

    claims = [c for c in fdb.all_docs("claims")
              if c.get("status") in REVIEW_STATUSES]
    claims.sort(key=lambda c: c.get("created_at", ""))

    pending = len(claims)
    dup = sum(1 for c in claims
              if c.get("duplicates", {}).get("invoice_reused")
              or c.get("duplicates", {}).get("doc_hash_reuse")
              or c.get("duplicates", {}).get("prior_claims", 0) > 0)
    disagree = sum(1 for c in claims
                   if c.get("consistency") == "Model Disagreement")
    contra = sum(1 for c in claims
                 if c.get("rules_outcome", {}).get("contradictions"))
    stat_row([
        {"label": "Awaiting review", "value": pending, "icon": "👤",
         "tone": "review" if pending else "neutral"},
        {"label": "Model disagreements", "value": disagree, "icon": "🔀",
         "tone": "invalid" if disagree else "neutral"},
        {"label": "Duplicate indicators", "value": dup, "icon": "🕵️",
         "tone": "invalid" if dup else "neutral"},
        {"label": "Data contradictions", "value": contra, "icon": "⚠️",
         "tone": "review" if contra else "neutral"},
    ])

    if not claims:
        empty_state("🎉", "Queue is empty",
                    "Every claim has been auto-decided or reviewed — "
                    "the system is fully caught up.")
        return

    m = models_mod.load_all()
    for c in claims:
        r = c.get("rules_outcome", {})
        reasons = (r.get("contradictions", []) + r.get("hard_fails", [])
                   + r.get("review_flags", []))
        with st.expander(f"👤 {c['claim_id']} — {c.get('brand', '')} "
                         f"{c.get('model', '')} · "
                         f"{c.get('final_decision', '')}"):
            col1, col2 = st.columns([3, 2])
            with col1:
                st.markdown(status_badge(c["status"]) + " "
                            + status_badge(c.get("final_decision", "")) + " "
                            + badge(c.get("consistency", ""), "info"),
                            unsafe_allow_html=True)
                if reasons:
                    alert("Routed to review: " + " · ".join(reasons[:4]),
                          "review")
                kv_grid([
                    ("Python model", f"{c.get('python_pred', '')} "
                                     f"({c.get('py_top_conf', 0):.0%})"),
                    ("Teachable Machine", f"{c.get('tm_pred', '')} "
                                          f"({c.get('tm_top_conf', 0):.0%})"),
                    ("Prior claims", c.get("duplicates", {}).get(
                        "prior_claims", 0)),
                    ("Documents", ", ".join(
                        d["type"] for d in c.get("documents", []))
                     or "none uploaded"),
                ])
                st.markdown(c.get("summary", "")[:500]
                            + ("…" if len(c.get("summary", "")) > 500 else ""))
            with col2:
                try:
                    st.image(render_card(
                        c, m["policies"][c["product_category"]]), width=250)
                except Exception:
                    pass

            comment = st.text_area("Reviewer comment",
                                   key=f"cmt_{c['claim_id']}",
                                   placeholder="Reasoning for the decision…")
            b1, b2, b3 = st.columns(3)
            cid = c["claim_id"]

            if b1.button("✅ Approve", key=f"ap_{cid}",
                         use_container_width=True):
                _decide(c, "Approved", "approve", comment, user)
            if b2.button("⛔ Reject", key=f"rj_{cid}",
                         use_container_width=True):
                _decide(c, "Rejected", "reject", comment, user)
            if b3.button("📨 Request info", key=f"ri_{cid}",
                         use_container_width=True):
                cs.update_claim(
                    cid,
                    {"status": "Additional Information Required",
                     "reviewer": user["email"],
                     "reviewer_comment": comment},
                    event="Reviewer requested additional information",
                    actor=user["email"])
                fdb.log_audit("reviewer_decision", user["email"],
                              {"claim_id": cid, "decision": "request_info"})
                fdb.notify(c["owner_email"], cid,
                           f"Claim {cid}: additional information required — "
                           f"{comment or 'please contact support.'}")
                st.rerun()


def _decide(c, status, decision, comment, user):
    """Apply a reviewer decision, recording whether it overrode the AI."""
    ai_final = c.get("final_decision", "")
    override = (status == "Approved" and ai_final != "Likely Valid") or \
               (status == "Rejected" and ai_final != "Likely Invalid")
    cs.update_claim(
        c["claim_id"],
        {"status": status, "reviewer": user["email"],
         "reviewer_comment": comment, "reviewer_decision": decision,
         "override": override},
        event=f"Reviewer {status.lower()}"
              + (" — override of AI recommendation" if override else ""),
        actor=user["email"])
    fdb.log_audit("reviewer_decision", user["email"],
                  {"claim_id": c["claim_id"], "decision": decision,
                   "override": override})
    fdb.notify(c["owner_email"], c["claim_id"],
               f"Claim {c['claim_id']} {status.lower()} by reviewer.")
    st.rerun()