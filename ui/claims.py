"""AssureX Claim Engine - Claims list page.

Search & filter claims (req xlii), full claim detail with card preview,
timeline (req xxxviii), model predictions, reviewer notes, and report
download (req xliv). Customers see only their claims; reviewers/admins
see all claims.
"""
from datetime import datetime, timezone

import streamlit as st

from card_generator.generate_cards import render_card
from src import claim_service as cs
from src import firebase_db as fdb
from src import models as models_mod
from ui.components import (badge, empty_state, inject_css, kv_grid,
                           page_header, status_badge, timeline)

STATUS_OPTIONS = ["All", "Draft", "Submitted", "Under Evaluation",
                  "Additional Information Required", "Manual Review",
                  "Approved", "Rejected", "Closed"]


def view():
    inject_css()
    user = st.session_state["user"]
    role = user["role"]
    is_elevated = role in ("reviewer", "admin")
    title = "All Claims" if is_elevated else "My Claims"

    page_header("📁" if not is_elevated else "🗂️", title,
                "Search, filter, and track every claim through its "
                "lifecycle" if is_elevated else
                "Track the progress of your submitted claims")

    claims = (fdb.all_docs("claims") if is_elevated
              else fdb.query("claims", "owner_email", "==", user["email"]))
    claims.sort(key=lambda c: c.get("created_at", ""), reverse=True)
    if not claims:
        empty_state("🗂️", "No claims found",
                    "Submit a claim from the New Claim page to see it here.")
        return

    # ---- filters (req xlii)
    m = models_mod.load_all()
    with st.expander("🔎 Search & filters"):
        c1, c2, c3, c4 = st.columns(4)
        status_f = c1.selectbox("Status", STATUS_OPTIONS)
        cat_f = c2.selectbox("Category", ["All"] + list(m["policies"]))
        decision_f = c3.selectbox("AI decision", ["All", "Likely Valid",
                                                  "Likely Invalid",
                                                  "Manual Review Required"])
        search = c4.text_input("Search (ID / serial / invoice)")

    def match(c):
        if status_f != "All" and c.get("status") != status_f:
            return False
        if cat_f != "All" and c.get("product_category") != cat_f:
            return False
        if decision_f != "All" and c.get("final_decision") != decision_f:
            return False
        if search:
            s = search.lower()
            hay = (f"{c.get('claim_id', '')} {c.get('serial_number', '')} "
                   f"{c.get('invoice_number', '')} "
                   f"{c.get('owner_email', '')}").lower()
            if s not in hay:
                return False
        return True

    shown = [c for c in claims if match(c)]
    st.caption(f"Showing {len(shown)} of {len(claims)} claims")

    for c in shown:
        with st.expander(f"{_status_emoji(c['status'])} {c['claim_id']} — "
                         f"{c.get('brand', '')} {c.get('model', '')} · "
                         f"{c.get('final_decision', '')}"):
            col1, col2 = st.columns([3, 2])
            with col1:
                st.markdown(status_badge(c["status"]) + " "
                            + status_badge(c.get("final_decision", ""))
                            + " " + badge(c.get("consistency", ""), "info"),
                            unsafe_allow_html=True)
                st.markdown(c.get("summary", ""))
                kv_grid([
                    ("Python model", f"{c.get('python_pred', '')} "
                                     f"({c.get('py_top_conf', 0):.0%})"),
                    ("Teachable Machine", f"{c.get('tm_pred', '')} "
                                          f"({c.get('tm_top_conf', 0):.0%})"),
                    ("Confidence diff", f"{c.get('conf_diff', 0):.3f}"),
                    ("Model versions", c.get("model_versions", {}).get("python", "")
                     + " · " + c.get("model_versions", {}).get("tm", "")),
                ])
                if c.get("reviewer"):
                    note = (f"🧑‍⚖️ **{c['reviewer']}** — "
                            f"\"{c.get('reviewer_comment', '')}\"")
                    if c.get("override"):
                        note += " ⚠️ *(overrode the AI recommendation)*"
                    st.markdown(note)
                st.download_button("⬇️ Download report", cs.build_report(c),
                                   file_name=f"{c['claim_id']}_report.md",
                                   mime="text/markdown",
                                   key=f"rep_{c['claim_id']}")
            with col2:
                try:
                    st.image(render_card(
                        c, m["policies"][c["product_category"]]), width=270)
                except Exception:
                    st.caption("(card preview unavailable)")
            timeline(c.get("timeline", []))


def _status_emoji(status):
    return {"Approved": "✅", "Rejected": "⛔", "Manual Review": "👤",
            "Additional Information Required": "📨"}.get(status, "📄")