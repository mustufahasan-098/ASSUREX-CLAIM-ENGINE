from datetime import date, datetime, timezone

import streamlit as st

from src import firebase_db as fdb
from src import models as models_mod
from src.features import add_months, parse_date
from ui.components import (alert, empty_state, inject_css, kv_grid,
                           page_header, section, stat_row, status_badge,
                           timeline)


def _warranty_state(p, alert_days):
    """(days_left, status_text, tone) for one product's warranty."""
    expiry = add_months(parse_date(p["purchase_date"]),
                        int(p["warranty_months"])
                        + int(p.get("extended_months") or 0))
    left = (expiry - date.today()).days
    if left < 0:
        return left, "Expired", "invalid"
    if left <= alert_days:
        return left, "Expiring soon", "review"
    return left, "Active", "valid"


def view():
    inject_css()
    user = st.session_state["user"]
    m = models_mod.load_all()
    alert_days = m["settings"]["warranty_alert_days"]

    products = fdb.query("products", "owner_email", "==", user["email"])
    claims = fdb.query("claims", "owner_email", "==", user["email"])
    claims.sort(key=lambda c: c.get("created_at", ""), reverse=True)
    notes = fdb.query("notifications", "user_email", "==", user["email"])
    notes.sort(key=lambda n: n.get("ts")
               or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    first_name = user["name"].split()[0]
    page_header("🏠", f"Welcome back, {first_name}",
                f"{user['role'].replace('_', ' ').title()} workspace · "
                f"warranty alerts {alert_days} days before expiry")

    # ---- summary statistics
    active = expiring = expired = 0
    expiring_list = []
    for p in products:
        left, status, _ = _warranty_state(p, alert_days)
        if status == "Expired":
            expired += 1
        elif status == "Expiring soon":
            expiring += 1
            expiring_list.append(f"{p['name']} ({p['brand']} "
                                 f"{p['model']}) - {left} days left")
        else:
            active += 1
    pending = sum(1 for c in claims
                  if c["status"] in ("Manual Review",
                                     "Additional Information Required"))

    stat_row([
        {"label": "My products", "value": len(products), "icon": "📦",
         "tone": "neutral"},
        {"label": "Active warranties", "value": active, "icon": "✅",
         "tone": "valid"},
        {"label": "Expiring soon", "value": expiring, "icon": "⏰",
         "tone": "review" if expiring else "neutral"},
        {"label": "My claims", "value": len(claims), "icon": "📁",
         "tone": "neutral"},
        {"label": "Awaiting review", "value": pending, "icon": "👤",
         "tone": "review" if pending else "neutral"},
    ])

    # ---- warranty expiry alerts (req ix)
    if expiring_list:
        alert("⏰ Warranty expiring soon:  " + "  ·  ".join(expiring_list),
              "review")
    if expired:
        alert(f"{expired} product(s) have expired warranties - claims for "
              f"them will likely be invalid.", "invalid")

    # ---- notifications (req xxxix)
    if notes:
        with st.expander(f"🔔 Notifications ({len(notes)})"):
            timeline([{"ts": str(n.get("ts", ""))[:16],
                       "event": n.get("message", ""),
                       "actor": "AssureX"} for n in notes[:8]])

    # ---- recent claims
    section("📁", "Recent claims")
    if not claims:
        empty_state("🗂️", "No claims yet",
                    "Submit your first claim from the New Claim page - "
                    "both AI models will evaluate it in seconds.")
        return
    for c in claims[:6]:
        st.markdown(f"""<div class="ax-card">
  <div style="display:flex; justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap;">
    <div><b>{c['claim_id']}</b> · {c.get('brand', '')} {c.get('model', '')}
      <span style="color:#475467;">· {c.get('fault_category', '').replace('_', ' ')}</span></div>
    <div>{status_badge(c['status'])} {status_badge(c.get('final_decision', ''))}</div>
  </div>
  <div style="margin-top:8px; font-size:.88rem; color:#475467;">{c.get('summary', '')[:260]}{'…' if len(c.get('summary', '')) > 260 else ''}</div>
</div>""", unsafe_allow_html=True)