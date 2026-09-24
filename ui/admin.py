"""AssureX Claim Engine - Administrator Analytics (req xli, xliii, xlv).

Fleet-wide view: totals, model performance, disagreements, duplicate
alerts, trends, and CSV export. Monitoring hooks for repeated failures
and low-confidence predictions (req l).
"""
from collections import Counter
from datetime import datetime

import pandas as pd
import streamlit as st

from src import firebase_db as fdb
from ui.components import (empty_state, inject_css, page_header, section,
                           stat_row)

FINAL_OPTIONS = ["Likely Valid", "Likely Invalid", "Manual Review Required"]


def view():
    inject_css()
    page_header("📊", "Administrator Analytics",
                "Fleet-wide claim intelligence — outcomes, model behavior, "
                "duplicates, and trends")

    claims = fdb.all_docs("claims", limit=1000)
    users = fdb.all_docs("users", limit=1000)
    audit = fdb.all_docs("audit", limit=200)

    if not claims:
        empty_state("📭", "No claims in the system yet",
                    "Analytics populate as claims are submitted.")
        return

    by_final = Counter(c.get("final_decision", "?") for c in claims)
    pending = sum(1 for c in claims
                  if c.get("status") in ("Manual Review",
                                         "Additional Information Required"))
    disagreements = [c for c in claims
                     if c.get("consistency") == "Model Disagreement"]
    low_conf = [c for c in claims
                if min(c.get("py_top_conf", 1), c.get("tm_top_conf", 1)) < 0.6]
    dupes = [c for c in claims
             if c.get("duplicates", {}).get("invoice_reused")
             or c.get("duplicates", {}).get("doc_hash_reuse")
             or c.get("duplicates", {}).get("prior_claims", 0) > 0]
    avg_py = sum(c.get("py_top_conf", 0) for c in claims) / len(claims)
    avg_tm = sum(c.get("tm_top_conf", 0) for c in claims) / len(claims)

    stat_row([
        {"label": "Total claims", "value": len(claims), "icon": "📁",
         "tone": "neutral"},
        {"label": "Likely valid", "value": by_final.get("Likely Valid", 0),
         "icon": "✅", "tone": "valid"},
        {"label": "Likely invalid", "value": by_final.get("Likely Invalid", 0),
         "icon": "⛔", "tone": "invalid"},
        {"label": "Manual review", "value": pending, "icon": "👤",
         "tone": "review"},
        {"label": "Disagreements", "value": len(disagreements), "icon": "🔀",
         "tone": "invalid" if disagreements else "neutral"},
    ])

    m = st.columns(4)
    m[0].metric("Avg Python confidence", f"{avg_py:.0%}")
    m[1].metric("Avg TM confidence", f"{avg_tm:.0%}")
    m[2].metric("Low-confidence claims", len(low_conf))
    m[3].metric("Duplicate alerts", len(dupes))

    c1, c2 = st.columns(2)
    with c1:
        section("🥧", "Final decisions")
        pie = Counter({k: by_final.get(k, 0) for k in FINAL_OPTIONS})
        st.bar_chart(dict(pie))
    with c2:
        section("📈", "Claims by day")
        days = Counter((c.get("created_at") or "")[:10] for c in claims)
        st.bar_chart({k: v for k, v in sorted(days.items()) if k})

    section("🔀", "Model disagreement monitor (req l)")
    if disagreements:
        st.dataframe([{"claim_id": c["claim_id"],
                       "python": c.get("python_pred"),
                       "tm": c.get("tm_pred"),
                       "conf_diff": round(c.get("conf_diff", 0), 3),
                       "status": c.get("status")} for c in disagreements],
                     use_container_width=True)
    else:
        st.caption("No disagreements — both models agree on every claim so far.")

    section("🕵️", "Duplicate & fraud indicators")
    if dupes:
        st.dataframe([{"claim_id": c["claim_id"],
                       "indicators": str(c.get("duplicates", {}))}
                      for c in dupes], use_container_width=True)
    else:
        st.caption("No duplicate indicators detected.")

    section("👥", "Users")
    st.dataframe([{"name": u.get("name"), "email": u.get("email"),
                   "role": u.get("role")} for u in users],
                 use_container_width=True)

    section("🧾", "Audit trail (latest 200 actions)")
    st.dataframe([{"ts": str(a.get("ts", ""))[:19],
                   "actor": a.get("actor"),
                   "action": a.get("action"),
                   "details": str(a.get("details", {}))[:80]}
                  for a in reversed(audit)], use_container_width=True)

    section("⬇️", "Data export (req xlv)")
    rows = [{"claim_id": c["claim_id"], "owner": c.get("owner_email"),
             "category": c.get("product_category"),
             "brand": c.get("brand"), "fault": c.get("fault_category"),
             "python_pred": c.get("python_pred"),
             "python_conf": round(c.get("py_top_conf", 0), 3),
             "tm_pred": c.get("tm_pred"),
             "tm_conf": round(c.get("tm_top_conf", 0), 3),
             "consistency": c.get("consistency"),
             "final_decision": c.get("final_decision"),
             "status": c.get("status")} for c in claims]
    st.download_button("⬇️ Export all claims (CSV)",
                       pd.DataFrame(rows).to_csv(index=False),
                       file_name="assurex_claims_export.csv",
                       mime="text/csv", use_container_width=True)