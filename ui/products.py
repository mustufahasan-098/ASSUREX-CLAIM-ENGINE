import uuid
from datetime import date

import streamlit as st

from src import firebase_db as fdb
from src import models as models_mod
from src.features import add_months, parse_date
from ui.components import (badge, empty_state, inject_css, kv_grid,
                           page_header, section, stat_row, status_badge)


def view():
    inject_css()
    user = st.session_state["user"]
    m = models_mod.load_all()
    policies = m["policies"]
    alert_days = m["settings"]["warranty_alert_days"]
    products = fdb.query("products", "owner_email", "==", user["email"])

    page_header("📦", "My Products & Warranties",
                "Register products, track coverage, and see the exact "
                "policy rules that will evaluate your claims")

    # ---- summary
    active = expiring = expired = 0
    for p in products:
        expiry = add_months(parse_date(p["purchase_date"]),
                            int(p["warranty_months"])
                            + int(p.get("extended_months") or 0))
        left = (expiry - date.today()).days
        if left < 0:
            expired += 1
        elif left <= alert_days:
            expiring += 1
        else:
            active += 1
    stat_row([
        {"label": "Products", "value": len(products), "icon": "📦",
         "tone": "neutral"},
        {"label": "Active warranties", "value": active, "icon": "✅",
         "tone": "valid"},
        {"label": "Expiring soon", "value": expiring, "icon": "⏰",
         "tone": "review" if expiring else "neutral"},
        {"label": "Expired", "value": expired, "icon": "⛔",
         "tone": "invalid" if expired else "neutral"},
    ])

    # ---- registration form (req iii)
    with st.expander("➕ Register a new product", expanded=not products):
        with st.form("product_form", border=False):
            c1, c2 = st.columns(2)
            name = c1.text_input("Product name *", placeholder="e.g. Smartphone")
            category = c2.selectbox("Category *", list(policies))
            brand = c1.text_input("Brand *", placeholder="e.g. Samsung")
            model = c2.text_input("Model *", placeholder="e.g. Galaxy S22")
            serial = c1.text_input("Serial number *",
                                   placeholder="e.g. SN12345678")
            purchase = c2.date_input(
                "Purchase date *",
                value=date(date.today().year - 1, 1, 1),
                max_value=date.today())
            price = c1.number_input("Purchase price", 0.0, 1_000_000.0,
                                    500.0, 50.0)
            retailer = c2.text_input("Retailer",
                                     placeholder="e.g. Demo Electronics")
            pol = policies[category]
            ext_options = [0] + [x for x in (12, 24)
                                 if x <= int(pol["extended_warranty_max_months"])]
            extended = st.selectbox(
                "Extended warranty (months)",
                ext_options,
                format_func=lambda x: "Standard warranty only"
                if x == 0 else f"+{x} months extended")
            if st.form_submit_button("Register product", type="primary",
                                     use_container_width=True):
                if not all([name, brand, model, serial]):
                    st.error("Fields marked * are required.")
                else:
                    pid = f"PRD-{uuid.uuid4().hex[:6].upper()}"
                    fdb.set_doc("products", pid, {
                        "product_id": pid, "owner_email": user["email"],
                        "name": name, "product_category": category,
                        "brand": brand, "model": model,
                        "serial_number": serial,
                        "purchase_date": purchase.isoformat(),
                        "purchase_price": float(price), "retailer": retailer,
                        "warranty_type": "extended" if extended else "standard",
                        "warranty_months": pol["standard_warranty_months"],
                        "extended_months": int(extended)})
                    fdb.log_audit("product_registered", user["email"],
                                  {"product_id": pid})
                    end = add_months(purchase,
                                     int(pol["standard_warranty_months"])
                                     + int(extended))
                    st.success(f"✅ Registered {name} ({pid}). "
                               f"Warranty active until {end.isoformat()}.")
                    st.rerun()

    # ---- product cards with live policy rules (req iv, xxvi)
    section("📋", "Registered products")
    if not products:
        empty_state("📦", "No products registered yet",
                    "Register a product above to start tracking its "
                    "warranty and submitting claims.")
        return
    for p in products:
        expiry = add_months(parse_date(p["purchase_date"]),
                            int(p["warranty_months"])
                            + int(p.get("extended_months") or 0))
        left = (expiry - date.today()).days
        if left < 0:
            state, tone, emoji = "Expired", "invalid", "⛔"
        elif left <= alert_days:
            state, tone, emoji = "Expiring soon", "review", "⏰"
        else:
            state, tone, emoji = "Active", "valid", "✅"
        pol = policies[p["product_category"]]
        with st.expander(f"{emoji} {p['name']} — {p['brand']} {p['model']}"
                         f"  ({p['product_id']})"):
            st.markdown(status_badge(f"Warranty {state} · {left} days left"),
                        unsafe_allow_html=True)
            kv_grid([
                ("Category", p["product_category"]),
                ("Serial number", p["serial_number"]),
                ("Purchased", f"{p['purchase_date']} · "
                              f"{p.get('retailer') or '-'} · "
                              f"Rs {p.get('purchase_price', 0):,.0f}"),
                ("Warranty", f"{p['warranty_months']} months standard"
                             + (f" + {p.get('extended_months')} extended"
                                if p.get("extended_months") else "")
                             + f" · ends {expiry.isoformat()}"),
            ])
            st.markdown(
                f"""<div style="margin-top:6px;">
  {badge('Covered: ' + ', '.join(pol['covered_faults'][:4])
         + ('…' if len(pol['covered_faults']) > 4 else ''), 'valid')}
  {badge('Excluded: ' + ', '.join(pol['excluded_faults'][:3]), 'invalid')}
  {badge('Report within ' + str(pol['claim_reporting_period_days'])
         + ' days', 'info')}
  {badge('Required docs: ' + ', '.join(pol['mandatory_documents']), 'neutral')}
</div>""", unsafe_allow_html=True)