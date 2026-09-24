"""AssureX Claim Engine - New Claim page (demo centerpiece).

Walks the user through the full SRS claim workflow:
  1. Supporting document upload with live SHA-256 hashing (req v, xii)
  2. Optional OCR extraction + verification note (req vi, vii)
  3. Pre-submission guidance: missing docs, contradictions warnings
     (req xxxiii)
  4. Claim details form (req xi, xiii)
  5. Full dual-model evaluation with the premium result experience:
     fusion decision banner, model comparison metrics, probability bars,
     rule breakdown, Claim Summary Card, explanation factors, AI summary,
     downloadable report (req xviii-xxiv, xxxii, xxxiv, xxxv, xliv)
"""
import hashlib
import io
from datetime import date, timedelta

import streamlit as st

from card_generator.generate_cards import render_card
from src import claim_service as cs
from src import firebase_db as fdb
from src import models as models_mod
from src import ocr_service
from src.features import add_months, parse_date
from ui.components import (alert, badge, decision_banner, empty_state,
                           inject_css, kv_grid, page_header, prob_bars,
                           section, stat_row, status_badge)


def _render_result(result):
    """The full result experience after evaluation."""
    final = result["decision"]["final"]
    cmp_ = result["comparison"]
    py_p, tm_p = result["py_probs"], result["tm_probs"]

    decision_banner(
        final,
        f"Claim {result['claim_id']} · status {result['status']} · "
        f"{cmp_['consistency']} · confidence difference "
        f"{cmp_['conf_diff']:.3f}")

    # ---- headline metrics
    m = st.columns(4)
    m[0].metric("🐍 Python model", f"{result['py_probs'][result['py_pred']]:.0%}",
                result["py_pred"].replace(" Claim", ""))
    m[1].metric("🖼️ Teachable Machine",
                f"{result['tm_probs'][result['tm_pred']]:.0%}",
                result["tm_pred"].replace(" Claim", ""))
    m[2].metric("🤝 Models match", "Yes" if cmp_["match"] else "No",
                cmp_["consistency"])
    m[3].metric("⚖️ Rule engine", "Pass",
                result["rules"]["label"].replace(" Claim", ""))

    tabs = st.tabs(["🧠 Decision explanation", "🐍 Python model",
                    "🖼️ Teachable Machine", "⚖️ Rules & documents",
                    "🪪 Claim Summary Card", "📋 AI summary",
                    "⬇️ Report"])

    # ---- explanation
    with tabs[0]:
        d = result["decision"]
        ca, cb = st.columns(2)
        with ca:
            st.markdown("""<div class="ax-card">
  <h4>✅ Factors supporting the decision</h4>
</div>""", unsafe_allow_html=True)
            for f in d["support"]:
                st.markdown(f"- {f}")
            for w in d.get("warnings", []):
                st.markdown(f"- ℹ️ {w}")
        with cb:
            st.markdown("""<div class="ax-card">
  <h4>⚠️ Factors against / needing attention</h4>
</div>""", unsafe_allow_html=True)
            for f in d["oppose"]:
                st.markdown(f"- {f}")
            if not d["oppose"]:
                st.markdown("- None")

    # ---- python model
    with tabs[1]:
        st.markdown("""<div class="ax-card"><h4>Python classification model
— RandomForest (trained on 1,050 claims, 3 algorithms compared)</h4></div>""",
                    unsafe_allow_html=True)
        prob_bars(py_p)

    # ---- teachable machine
    with tabs[2]:
        c1, c2 = st.columns([1, 2])
        with c1:
            st.image(result["card"], width=290,
                     caption="The exact card classified by TM")
        with c2:
            st.markdown("""<div class="ax-card"><h4>Google Teachable
Machine model — image classification of the Claim Summary Card (2,100
training images)</h4></div>""", unsafe_allow_html=True)
            prob_bars(tm_p)

    # ---- rules & documents
    with tabs[3]:
        r = result["rules"]
        if r["contradictions"]:
            alert("Contradictions: " + " · ".join(r["contradictions"]),
                  "invalid")
        if r["hard_fails"]:
            alert("Hard-fail rules: " + " · ".join(r["hard_fails"]),
                  "invalid")
        if r["review_flags"]:
            alert("Review flags: " + " · ".join(r["review_flags"]), "review")
        if r["warnings"]:
            alert("Warnings: " + " · ".join(r["warnings"]), "info")
        if not (r["contradictions"] or r["hard_fails"] or r["review_flags"]):
            alert("All warranty rules passed with complete documentation.",
                  "valid")
        st.markdown(f"**Rule-engine label:** {r['label']}")
        dup = result.get("duplicates", {})
        kv_grid([
            ("Prior claims (same serial)", dup.get("prior_claims", 0)),
            ("Invoice reused", "Yes" if dup.get("invoice_reused") else "No"),
            ("Document reuse", "Yes" if dup.get("doc_hash_reuse")
             else "No"),
        ])
        docs = st.session_state.get("submitted_docs_info", [])
        st.markdown("**Uploaded documents:** "
                    + (", ".join(d["type"] for d in docs) or "none"))

    # ---- card
    with tabs[4]:
        c1, c2 = st.columns([1, 1.3])
        with c1:
            st.image(result["card"], width=400)
        with c2:
            st.markdown("""<div class="ax-card">
  <h4>🪪 Claim Summary Card</h4>
  <p style="font-size:.9rem; color:#475467;">Generated automatically from
  the submitted claim data (SRS Step 7). Contains factual claim
  information only — product, warranty status, fault, coverage, repair
  history, document availability, and validation-check findings.
  <b>No predictions or confidence scores appear on the card</b> (SRS
  req xx), so both models evaluate independently.</p>
</div>""", unsafe_allow_html=True)

    # ---- summary
    with tabs[5]:
        st.markdown("""<div class="ax-card">
  <h4>📋 AI-generated claim summary (template-based, no external AI
API)</h4>
</div>""", unsafe_allow_html=True)
        st.markdown(result["summary"])

    # ---- report
    with tabs[6]:
        claim = fdb.get_doc("claims", result["claim_id"])
        st.download_button(
            "⬇️ Download full claim report (.md)",
            cs.build_report(claim),
            file_name=f"{result['claim_id']}_report.md",
            mime="text/markdown", use_container_width=True)
        st.caption("Report contains: claim details, both model predictions "
                   "with all confidence scores, model versions, comparison, "
                   "rule results, duplicates, final decision, explanation "
                   "factors, AI summary, and the full timeline.")

    if st.button("➕ Submit another claim"):
        st.session_state.pop("last_result", None)
        st.rerun()


def view():
    inject_css()
    user = st.session_state["user"]
    m = models_mod.load_all()
    policies = m["policies"]

    page_header("📝", "New Warranty Claim",
                "Upload evidence → describe the fault → both AI models "
                "evaluate your claim in seconds")

    products = fdb.query("products", "owner_email", "==", user["email"])
    if not products:
        empty_state("📦", "No products registered",
                    "Register a product first on the My Products page — "
                    "claims are always linked to a registered product.")
        return
    labels = {f"{p['name']} — {p['brand']} {p['model']}  ({p['product_id']})":
              p for p in products}
    P = labels[st.selectbox("Select product", list(labels))]
    policy = policies[P["product_category"]]

    expiry = add_months(parse_date(P["purchase_date"]),
                        int(P["warranty_months"])
                        + int(P.get("extended_months") or 0))
    left = (expiry - date.today()).days
    w_state = "⛔ EXPIRED" if left < 0 else "✅ Active"
    st.markdown(
        f"""<div class="ax-card">
  <h4>Selected product &amp; warranty {status_badge(w_state if left >= 0 else "Expired")}</h4>
  <div class="ax-kv" style="margin-top:8px;">
    <div><div class="ax-kv-label">Warranty ends</div><div class="ax-kv-value">{expiry.isoformat()} ({left} days)</div></div>
    <div><div class="ax-kv-label">Covered faults</div><div class="ax-kv-value">{', '.join(policy['covered_faults'][:3])}…</div></div>
    <div><div class="ax-kv-label">Excluded</div><div class="ax-kv-value">{', '.join(policy['excluded_faults'][:3])}…</div></div>
    <div><div class="ax-kv-label">Report within</div><div class="ax-kv-value">{policy['claim_reporting_period_days']} days of the fault</div></div>
  </div>
</div>""", unsafe_allow_html=True)

    # ================================================ 1 · documents
    section("📎", "1 · Supporting documents")
    docs = st.session_state.get("claim_docs", [])
    c1, c2 = st.columns([3, 1.4])
    f = c1.file_uploader("Upload a document", type=["pdf", "jpg", "jpeg", "png"],
                         label_visibility="collapsed")
    dtype = c2.selectbox("Type", cs.DOC_TYPES, index=0)
    if st.button("➕ Add document",
                 disabled=f is None) and f is not None:
        docs.append({"name": f.name, "type": dtype, "bytes": f.getvalue(),
                     "sha256": hashlib.sha256(f.getvalue()).hexdigest()})
        st.session_state["claim_docs"] = docs
        st.rerun()
    if docs:
        st.markdown("""<div class="ax-card"><h4>Attached documents
(SHA-256 hashes power duplicate-document detection)</h4></div>""",
                    unsafe_allow_html=True)
        for i, d in enumerate(docs):
            cc1, cc2 = st.columns([5, 1])
            cc1.markdown(
                f"📎 **{d['type'].replace('_', ' ').title()}** — {d['name']} "
                f"· `{d['sha256'][:16]}…` · {len(d['bytes'])/1024:.0f} KB")
            if cc2.button("✕ Remove", key=f"rm{i}"):
                docs.pop(i)
                st.session_state["claim_docs"] = docs
                st.rerun()
        # OCR preview on the receipt (req vi, vii)
        receipt = next((d for d in docs if d["type"] == "receipt"), None)
        if receipt and receipt["name"].lower().endswith((".jpg", ".jpeg", ".png")):
            try:
                from PIL import Image
                info = ocr_service.extract_receipt_info(
                    Image.open(io.BytesIO(receipt["bytes"])))
                if info.get("available"):
                    st.markdown(
                        f"""<div class="ax-alert ax-alert--info">🔍 <b>OCR
extraction preview</b> — dates: {info['dates']} · invoices:
{info['invoice_numbers']} · serials: {info['serial_numbers']} · amounts:
{info['amounts']}. <b>Verify these values against the form below before
submitting (req vii).</b></div>""", unsafe_allow_html=True)
                else:
                    st.caption(info["note"])
            except Exception:
                st.caption("Receipt could not be opened for OCR preview.")
    # pre-submission guidance (req xxxiii)
    missing = [d for d in policy["mandatory_documents"]
               if not any(doc["type"] == d for doc in docs)]
    if missing:
        alert("Missing mandatory documents: "
              + ", ".join(missing)
              + ". The claim will be routed to manual review without them.",
              "review")

    # ================================================ 2 · details
    section("✍️", "2 · Claim details")
    with st.form("claim_form", border=False):
        c1, c2 = st.columns(2)
        fault_options = policy["covered_faults"] + policy["excluded_faults"]
        covered_set = set(policy["covered_faults"])
        fault_category = c1.selectbox(
            "Fault type", fault_options, index=0,
            format_func=lambda f_: ("✅ " if f_ in covered_set
                                    else "⛔ EXCLUDED · ") + f_.replace("_", " "),
            help="Faults marked ⛔ are excluded by the policy — selecting "
                 "one demonstrates an invalid-claim evaluation.")
        fault_date = c2.date_input("Fault date",
                                   value=date.today() - timedelta(days=7),
                                   max_value=date.today() + timedelta(days=1))
        claim_date = c1.date_input("Claim date", value=date.today())
        serial = c2.text_input("Serial number on the product *",
                               value=P["serial_number"],
                               help="If this doesn't match the registered "
                                    "serial, the claim routes to manual "
                                    "review (req xxvii).")
        description = st.text_area(
            "Fault description", placeholder="Describe what happened…",
            height=80)
        c3, c4, c5 = st.columns(3)
        repair_count = c3.number_input("Previous repairs", 0, 10, 0)
        authorized = c4.checkbox("Repairs at authorized center", value=True,
                                 disabled=repair_count == 0)
        repair_date = c5.date_input("Last repair date",
                                    value=date.today() - timedelta(days=60))
        invoice = st.text_input(
            "Invoice number *",
            value=f"INV-{abs(hash(P['serial_number'])) % 100000:05d}",
            help="Reusing an invoice from a previous claim triggers "
                 "duplicate detection.")
        st.markdown(
            f"""<div class="ax-alert ax-alert--info">💡 <b>Live checks:</b>
date contradictions (claim before purchase, fault after claim, repair
before purchase) are detected automatically, and the serial number is
compared with the registered product record.</div>""",
            unsafe_allow_html=True)
        submitted = st.form_submit_button("🚀 Evaluate & Submit Claim",
                                          type="primary",
                                          use_container_width=True)

    if submitted:
        if not serial or not invoice:
            st.error("Serial number and invoice number are required.")
            return
        claim = {
            "claim_id": "", "user_id": user["email"],
            "product_id": P["product_id"],
            "product_category": P["product_category"],
            "brand": P["brand"], "model": P["model"],
            "serial_number": serial,
            "purchase_date": P["purchase_date"],
            "purchase_price": P.get("purchase_price", 0),
            "warranty_type": P.get("warranty_type", "standard"),
            "warranty_months": int(P["warranty_months"]),
            "extended_months": int(P.get("extended_months") or 0),
            "fault_date": fault_date.isoformat(),
            "claim_date": claim_date.isoformat(),
            "fault_category": fault_category,
            "repair_count": int(repair_count),
            "last_repair_date": (repair_date.isoformat()
                                 if repair_count > 0 else ""),
            "authorized_repair": bool(authorized),
            "serial_match": serial == P["serial_number"],
            "invoice_number": invoice,
            "has_receipt": any(d["type"] == "receipt" for d in docs),
            "has_warranty_card": any(d["type"] == "warranty_card"
                                     for d in docs),
            "has_product_image": any(d["type"] == "product_image"
                                     for d in docs),
            "has_serial_evidence": any(d["type"] == "serial_evidence"
                                       for d in docs),
            "has_fault_evidence": any(d["type"] == "fault_evidence"
                                      for d in docs),
            "has_repair_report": any(d["type"] == "repair_report"
                                     for d in docs),
            "prior_claim_count": 0, "duplicate_invoice": False,
            "replaced_before": False, "description": description,
        }
        with st.spinner("Evaluating: rule engine → Python model → Claim "
                        "Summary Card → Teachable Machine → fusion…"):
            try:
                result = cs.process_and_save(claim, docs,
                                             actor=user["email"])
            except Exception as e:
                st.error(f"Evaluation failed: {e}")
                return
        st.session_state["last_result"] = result
        st.session_state["submitted_docs_info"] = [
            {"type": d["type"], "name": d["name"]} for d in docs]
        st.session_state["claim_docs"] = []
        st.rerun()

    if "last_result" in st.session_state:
        _render_result(st.session_state["last_result"])