
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  
from flask_wtf.csrf import CSRFProtect, generate_csrf
from src import routing as service_routing
from src import smart_lookup
from src import product_catalog
import hashlib
import io
import secrets
import shutil
import uuid
from datetime import date
from functools import wraps
from pathlib import Path

import yaml
from flask import (Flask, Response, abort, flash, g, redirect,
                   render_template, request, send_file, session, url_for)
from werkzeug.utils import secure_filename

from card_generator.generate_cards import render_card
from PIL import Image
from src import auth, claim_service as cs
from src import firebase_db as fdb
from src import models as models_mod
from src import ocr_service
from src.features import add_months, parse_date

ROOT = Path(__file__).resolve().parent
SETTINGS = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text())
STAGING_DIR = ROOT / "uploads" / "_staging"

app = Flask(__name__)
app.secret_key = SETTINGS["session_secret"]
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True  
CSRFProtect(app)
app.config["WTF_CSRF_EXEMPT_ROUTES"] = ["chat"]

BOOT = {"models_ok": True, "fb_ok": True}
try:
    models_mod.load_all()
except Exception as e:
    BOOT.update(models_ok=False, models_err=str(e))
try:
    fdb.db()
except Exception as e:
    BOOT.update(fb_ok=False, fb_err=str(e))

CLASS_TONE = {"Valid Claim": "valid", "Invalid Claim": "invalid",
              "Manual Review": "review"}

NAV = {
    "customer": [("dashboard", "Dashboard", "🏠"),
                 ("products", "My Products", "📦"),
                 ("new_claim", "New Claim", "📝"),
                 ("claims", "My Claims", "📁")],
    "service_center": [("service_desk", "Service Desk", "🏪"),
                       ("new_claim", "New Claim", "📝"),
                       ("claims", "All Claims", "🗂️")],
    "reviewer": [("review_queue", "Review Queue", "⚖️"),
                 ("claims", "All Claims", "🗂️"),
                 ("dashboard", "Dashboard", "🏠")],
    "admin": [("admin", "Admin Analytics", "📊"),
              ("admin_approvals", "Account Approvals", "🛡️"),
              ("admin_templates", "Product Catalog", "🗃️"),
              ("entity_links", "Entity Links", "🔗"),
              ("review_queue", "Review Queue", "⚖️"),
              ("claims", "All Claims", "🗂️")],
}


@app.context_processor

def inject_globals():
    user = getattr(g, "user", None)
    return {"current_user": user,
            "nav_items": NAV.get(user["role"], []) if user else [],
            "csrf_token": generate_csrf}
   


def login_required(roles=None):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not BOOT["models_ok"] or not BOOT["fb_ok"]:
                return render_template("boot_error.html", boot=BOOT), 503
            email = session.get("user")
            if not email:
                return redirect(url_for("login"))
            user = fdb.get_doc("users", email)
            if not user:
                session.clear()
                return redirect(url_for("login"))
            if roles and user.get("role") not in roles:
                flash("You do not have access to that page.", "error")
                return redirect(url_for("home"))
            g.user = user
            return fn(*args, **kwargs)
        return wrapper
    return deco

   
@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Cache-Control"] = "no-store"   # no claim data cached
    return response
def fraud_risk(c):
    """Reads the stored 7-layer fraud analysis; falls back to the legacy
    computation for claims created before the upgrade."""
    f = c.get("fraud")
    if f:
        reasons = [s.get("reason", "") for s in f.get("signals", [])]
        return f.get("score", 0), reasons, f.get("tone", "review")
    score, reasons = 0, []
    d = c.get("duplicates", {})
    if d.get("invoice_reused"):
        score += 35
        reasons.append("Invoice number reused from another claim")
    if d.get("doc_hash_reuse"):
        score += 35
        reasons.append("Uploaded document reused from another claim")
    prior = int(d.get("prior_claims", 0) or 0)
    if prior:
        score += min(20, prior * 10)
        reasons.append(f"{prior} prior claim(s) on this serial number")
    if c.get("rules_outcome", {}).get("contradictions"):
        score += 25
        reasons.append("Contradictory claim data")
    if not c.get("serial_match", True):
        score += 15
        reasons.append("Serial number mismatch")
    if not c.get("has_receipt", False):
        score += 5
        reasons.append("No purchase receipt")
    score = min(100, score)
    tone = "valid" if score < 30 else "review" if score < 60 else "invalid"
    return score, reasons, tone


def _can_view(user, c):
    return user["role"] in ("reviewer", "admin") \
        or c.get("owner_email") == user["email"]


   
def _staging_dir():
    token = session.get("staging_token")
    if not token:
        token = secrets.token_hex(8)
        session["staging_token"] = token
    d = STAGING_DIR / token
    d.mkdir(parents=True, exist_ok=True)
    return d


def _clear_staging():
    token = session.get("staging_token")
    if token:
        shutil.rmtree(STAGING_DIR / token, ignore_errors=True)
    session.pop("staging_token", None)
    session.pop("staged_docs", None)
    session.pop("ocr_info", None)


   
@app.route("/")
def home():
    if not session.get("user"):
        return redirect(url_for("login"))
    user = fdb.get_doc("users", session["user"]) or {}
    role = user.get("role", "customer")
    if role == "admin":
        return redirect(url_for("admin"))
    if role == "reviewer":
        return redirect(url_for("review_queue"))
    if role == "service_center":
        return redirect(url_for("service_desk"))
    return redirect(url_for("dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user, err = auth.login(request.form.get("email"),
                               request.form.get("password"))
        if err:
            flash(err, "error")
        else:
            session["user"] = user["email"]
            fdb.log_audit("user_login", user["email"])
            return redirect(url_for("home"))
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        user, err = auth.register(request.form.get("name"),
                                  request.form.get("email"),
                                  request.form.get("password"),
                                  request.form.get("role", "customer"))
        if err:
            flash(err, "error")
        else:
            session["user"] = user["email"]
            flash(f"Welcome, {user['name']}!", "success")
            return redirect(url_for("home"))
    return render_template("register.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


   
@app.route("/dashboard")
@login_required()
def dashboard():
    user = g.user
    m = models_mod.load_all()
    alert_days = m["settings"]["warranty_alert_days"]
    products = fdb.query("products", "owner_email", "==", user["email"])
    claims = fdb.query("claims", "owner_email", "==", user["email"])
    claims.sort(key=lambda c: c.get("created_at", ""), reverse=True)

    active = expiring = expired = 0
    expiring_list = []
    for p in products:
        expiry = add_months(parse_date(p["purchase_date"]),
                            int(p["warranty_months"])
                            + int(p.get("extended_months") or 0))
        left = (expiry - date.today()).days
        if left < 0:
            expired += 1
        elif left <= alert_days:
            expiring += 1
            expiring_list.append(f"{p['name']} ({p['brand']}) — {left} days")
        else:
            active += 1
    pending = sum(1 for c in claims if c.get("status") in
                  ("Manual Review", "Additional Information Required"))
    doc_count = sum(len(c.get("documents", [])) for c in claims)
    stats = [
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
                 {"label": "Saved documents", "value": doc_count, "icon": "📎",
         "tone": "neutral"},
    ]
    notes = fdb.query("notifications", "user_email", "==", user["email"])
    notes.sort(key=lambda n: str(n.get("ts", "")), reverse=True)
    notes_view = [{"ts": str(n.get("ts", ""))[:16],
                   "event": n.get("message", ""), "actor": "AssureX"}
                  for n in notes[:8]]

    return render_template("dashboard.html",
                           first_name=user["name"].split()[0],
                           role=user["role"].replace("_", " ").title(),
                           alert_days=alert_days, stats=stats,
                           expiring_list=expiring_list, expired=expired,
                           notes=notes_view, claims=claims[:6])


   
   
@app.route("/products", methods=["GET", "POST"])
@login_required()
def products():
    user = g.user
    m = models_mod.load_all()
    policies = m["policies"]
    alert_days = m["settings"]["warranty_alert_days"]
    templates = product_catalog.load_templates()

   
    tpl = product_catalog.get_template(request.values.get("t", ""))

    if request.method == "POST":
   
        owner = user["email"]
        if user["role"] in ("admin", "service_center"):
            chosen = request.form.get("owner_email", "").strip().lower()
            if chosen:
                if fdb.get_doc("users", chosen):
                    owner = chosen
                else:
                    flash(f"Owner {chosen} not found - registered to your "
                          f"account instead.", "warning")
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "")
        brand = request.form.get("brand", "").strip()
        model = request.form.get("model", "").strip()
        serial = request.form.get("serial", "").strip()
        purchase = request.form.get("purchase_date", "")
        if not all([name, brand, serial, purchase]) \
                or category not in policies:
            flash("All fields marked * are required.", "error")
        else:
            pol = policies[category]
            ext = min(int(request.form.get("extended", 0) or 0),
                      int(pol["extended_warranty_max_months"]))
            pid = f"PRD-{uuid.uuid4().hex[:6].upper()}"
            purchase_d = parse_date(purchase)
            fdb.set_doc("products", pid, {
                "product_id": pid, "owner_email": owner,
                "name": name, "product_category": category,
                "brand": brand, "model": model, "serial_number": serial,
                "purchase_date": purchase_d.isoformat(),
                "purchase_price": float(request.form.get("price", 0) or 0),
                "retailer": request.form.get("retailer", "").strip(),
                "warranty_type": "extended" if ext else "standard",
                "warranty_months": pol["standard_warranty_months"],
                "extended_months": ext,
                "registered_via": "catalog_template" if tpl else "manual"})
            fdb.log_audit("product_registered", user["email"],
                          {"product_id": pid, "owner": owner,
                           "via": "catalog_template" if tpl else "manual"})
            end = add_months(purchase_d,
                             int(pol["standard_warranty_months"]) + ext)
            flash(f"✅ Registered {name} ({pid}) for {owner}. "
                  f"Warranty until {end.isoformat()}.", "success")
            return redirect(url_for("products"))

   
    product_list = (fdb.all_docs("products", limit=500)
                    if user["role"] == "admin"
                    else fdb.query("products", "owner_email", "==",
                                   user["email"]))
    items = []
    for p in product_list:
        pol = policies[p["product_category"]]
        expiry = add_months(parse_date(p["purchase_date"]),
                            int(p["warranty_months"])
                            + int(p.get("extended_months") or 0))
        left = (expiry - date.today()).days
        from src.predictive import product_risk
        risk_level, _risk_reasons = product_risk(p)
        state = ("Expired" if left < 0 else
                 "Expiring soon" if left <= alert_days else "Active")
        items.append({"p": p, "pol": pol, "expiry": expiry, "left": left,
                            "state": state, "risk_level": risk_level})
    counts = {"total": len(items),
              "active": sum(1 for i in items if i["state"] == "Active"),
              "expiring": sum(1 for i in items
                              if i["state"] == "Expiring soon"),
              "expired": sum(1 for i in items if i["state"] == "Expired")}
    return render_template("products.html", items=items, counts=counts,
                           categories=list(policies), policies=policies,
                           templates=templates, tpl=tpl)
   
@app.route("/new_claim", methods=["GET", "POST"])
@login_required(roles=["customer", "service_center"])
def new_claim():
    if request.method == "POST":
        pid = request.form.get("product_id", "")
        if pid:
            return redirect(url_for("new_claim_form", product_id=pid))
    _clear_staging()   # starting fresh wipes any previous staging
    products = fdb.query("products", "owner_email", "==", g.user["email"])
    if not products:
        return render_template("new_claim.html", step="no_products")
    if len(products) == 1:
        return redirect(url_for("new_claim_form",
                                product_id=products[0]["product_id"]))
    m = models_mod.load_all()
    alert_days = m["settings"]["warranty_alert_days"]
    picks = []
    for p in products:
        expiry = add_months(parse_date(p["purchase_date"]),
                            int(p["warranty_months"])
                            + int(p.get("extended_months") or 0))
        left = (expiry - date.today()).days
        picks.append({"p": p, "left": left,
                      "expired": left < 0, "expiring": 0 <= left <= alert_days})
    return render_template("new_claim.html", step="select", picks=picks)


@app.route("/new-claim/form/<product_id>")
@login_required(roles=["customer", "service_center"])
def new_claim_form(product_id):
    m = models_mod.load_all()
    P = fdb.get_doc("products", product_id)
    if not P or P["owner_email"] != g.user["email"]:
        abort(404)
    policy = m["policies"][P["product_category"]]
    expiry = add_months(parse_date(P["purchase_date"]),
                        int(P["warranty_months"])
                        + int(P.get("extended_months") or 0))
    staged = session.get("staged_docs", [])
    missing = [d for d in policy["mandatory_documents"]
               if not any(s["type"] == d for s in staged)]
    acting_for = request.values.get("for", "").strip().lower()
    if acting_for and g.user["role"] == "service_center" and \
            not fdb.get_doc("users", acting_for):
        flash(f"Customer {acting_for} not found.", "error")
        acting_for = ""
    return render_template("new_claim.html", step="form", P=P,
                           acting_for=acting_for, policy=policy,
                           ocr_verify=session.get("ocr_verify"),
                           expiry=expiry,
                           left=(expiry - date.today()).days,
                           staged=staged, missing=missing,
                           ocr=session.get("ocr_info"),
                           doc_types=cs.DOC_TYPES,
                           default_invoice=f"INV-{abs(hash(P['serial_number'])) % 100000:05d}",
                           today=date.today().isoformat())


@app.route("/new-claim/stage", methods=["POST"])
@login_required(roles=["customer", "service_center"])

def new_claim_stage():
    pid = request.form.get("product_id", "")
    f = request.files.get("doc")
    dtype = request.form.get("dtype", "receipt")
    if f and f.filename:
        data = f.read()
        sha = hashlib.sha256(data).hexdigest()
        stored = f"{dtype}__{secure_filename(f.filename)}"
        (_staging_dir() / stored).write_bytes(data)
        docs = session.get("staged_docs", [])
        docs.append({"name": f.filename, "type": dtype, "sha256": sha,
                     "stored": stored, "size": len(data)})
        session["staged_docs"] = docs
        if f.filename.lower().endswith((".jpg", ".jpeg", ".png")):
            try:
                img = Image.open(io.BytesIO(data))
                if dtype == "receipt":
                    P = fdb.get_doc("products", pid)
                    info = ocr_service.extract_receipt_info(img)
                    session["ocr_info"] = info
                    session["ocr_verify"] = (
                        ocr_service.verify_against_product(info, P)
                        if P else {"verdict": "none",
                                   "summary": "Product not found."})
                else:
                    q = ocr_service.image_quality(img)
                    if not q["ok"]:
                        flash(f"⚠️ Image quality issue: "
                              f"{', '.join(q['notes'])}. Consider a clearer "
                              f"photo.", "warning")
            except Exception as e:
                session["ocr_info"] = {"available": False,
                                       "note": f"Could not process image: {e}"}
        flash(f"📎 Added {dtype.replace('_', ' ')}: {f.filename}", "success")
    return redirect(url_for("new_claim_form", product_id=pid))

@app.route("/new-claim/unstage", methods=["POST"])
@login_required(roles=["customer", "service_center"])
def new_claim_unstage():
    pid = request.form.get("product_id", "")
    idx = int(request.form.get("index", -1))
    docs = session.get("staged_docs", [])
    if 0 <= idx < len(docs):
        removed = docs.pop(idx)
        p = _staging_dir() / removed["stored"]
        if p.exists():
            p.unlink()
        session["staged_docs"] = docs
    return redirect(url_for("new_claim_form", product_id=pid))


@app.route("/new-claim/submit", methods=["POST"])
@login_required(roles=["customer", "service_center"])
def new_claim_submit():
    user = g.user
    m = models_mod.load_all()
    pid = request.form.get("product_id", "")
    P = fdb.get_doc("products", pid)
    if not P or P["owner_email"] != user["email"]:
        abort(404)

    serial = request.form.get("serial", "").strip()
    invoice = request.form.get("invoice", "").strip()
    if not serial or not invoice:
        flash("Serial number and invoice number are required.", "error")
        return redirect(url_for("new_claim_form", product_id=pid))

    repair_count = int(request.form.get("repair_count", 0) or 0)
    staged = session.get("staged_docs", [])
   
    acting_for = request.form.get("acting_for", "").strip().lower()
    owner = user["email"]
    if acting_for and user["role"] == "service_center":
        if fdb.get_doc("users", acting_for):
            owner = acting_for
        else:
            flash(f"Customer {acting_for} not found - claim filed under "
                  f"your center account.", "warning")
    claim = {
        "claim_id": "", "user_id": owner, "product_id": pid,
        "product_category": P["product_category"],
        "brand": P["brand"], "model": P["model"],
        "serial_number": serial, "purchase_date": P["purchase_date"],
        "purchase_price": P.get("purchase_price", 0),
        "warranty_type": P.get("warranty_type", "standard"),
        "warranty_months": int(P["warranty_months"]),
        "extended_months": int(P.get("extended_months") or 0),
        "fault_date": request.form.get("fault_date", ""),
        "claim_date": request.form.get("claim_date",
                                       date.today().isoformat()),
        "fault_category": request.form.get("fault_category", ""),
        "repair_count": repair_count,
        "last_repair_date": (request.form.get("repair_date", "")
                             if repair_count > 0 else ""),
   
   
   
        "authorized_repair": repair_count == 0 or "authorized" in request.form,
        "serial_match": serial == P["serial_number"],
        "invoice_number": invoice,
        "has_receipt": any(s["type"] == "receipt" for s in staged),
        "has_warranty_card": any(s["type"] == "warranty_card" for s in staged),
        "has_product_image": any(s["type"] == "product_image" for s in staged),
        "has_serial_evidence": any(s["type"] == "serial_evidence" for s in staged),
        "has_fault_evidence": any(s["type"] == "fault_evidence" for s in staged),
        "has_repair_report": any(s["type"] == "repair_report" for s in staged),
        "prior_claim_count": 0, "duplicate_invoice": False,
        "replaced_before": False,
        "description": request.form.get("description", "").strip(),
    }
    docs = []
    for meta in staged:
        p = _staging_dir() / meta["stored"]
        if p.exists():
            docs.append({"name": meta["name"], "type": meta["type"],
                         "bytes": p.read_bytes(), "sha256": meta["sha256"]})
   
   
   
    ocr_v = session.get("ocr_verify")
    if ocr_v and ocr_v.get("verdict") == "mismatch":
        claim["_dup"] = dict(claim.get("_dup") or {})
        claim["_dup"]["doc_mismatch"] = True
        claim["_dup"]["doc_mismatch_note"] = ocr_v.get("summary", "")
    claim["ocr_verification"] = session.get("ocr_verify") or {}

    try:
        result = cs.process_and_save(claim, docs, actor=user["email"])
    except Exception as e:
        flash(f"Evaluation failed: {e}", "error")
        return redirect(url_for("new_claim_form", product_id=pid))
        _clear_staging()
    from src import email_service
    email_service.send_email(
        owner,
        "AssureX claim " + result["claim_id"] + " submitted",
        "Your warranty claim " + result["claim_id"] + " has been submitted and evaluated."
        + "\nDecision: " + result["decision"]["final"]
        + "\nLog in to view the full analysis.\n\n- AssureX Claim Engine")
    return redirect(url_for("claim_detail", cid=result["claim_id"]))



   
@app.route("/claim/<cid>")
@login_required()
def claim_detail(cid):
    c = fdb.get_doc("claims", cid)
    if not c or not _can_view(g.user, c):
        abort(404)
    risk_score, risk_reasons, risk_tone = fraud_risk(c)

   
    def safe(field, default):
        v = c.get(field)
        return v if v not in (None, "") else default

    py_probs = safe("python_probs", {})
    tm_probs = safe("tm_probs", {})
    if not py_probs:   # reconstruct from stored top conf if detail missing
        py_probs = {safe("python_pred", "Manual Review"): 0.0}
    if not tm_probs:
        tm_probs = {safe("tm_pred", "Manual Review"): 0.0}
    c["python_probs"] = py_probs
    c["tm_probs"] = tm_probs
    c.setdefault("explanation", {"support": [], "oppose": [], "warnings": []})
    c.setdefault("rules_outcome", {"label": "—", "contradictions": [],
                                   "hard_fails": [], "review_flags": [],
                                   "warnings": []})
    c.setdefault("duplicates", {"prior_claims": 0, "invoice_reused": False,
                                "doc_hash_reuse": False})
    c.setdefault("documents", [])
    c.setdefault("timeline", [])
    c.setdefault("consistency", "—")
    c.setdefault("conf_diff", 0.0)
    c.setdefault("model_versions", {"python": "—", "tm": "—"})
    c.setdefault("py_top_conf", 0.0)
    c.setdefault("tm_top_conf", 0.0)
    c.setdefault("status", "Manual Review")
    c.setdefault("final_decision", "Manual Review Required")

    status_icon = {"Approved": "✅", "Rejected": "❌", "Closed": "🏁",
                   "Manual Review": "⏳",
                   "Additional Information Required": "📨"}.get(
                       c.get("status", ""), "📋")
    counterfactuals = None
    if c.get("final_decision") != "Likely Valid":
        try:
            from src.counterfactual import generate as cf_generate
            pol_cf = models_mod.load_all()["policies"][c["product_category"]]
            counterfactuals = cf_generate(c, pol_cf)
        except Exception:
            counterfactuals = None
    return render_template(
        "claim_result.html", c=c,
        py_short=safe("python_pred", "—").replace(" Claim", ""),
        tm_short=safe("tm_pred", "—").replace(" Claim", ""),
        py_tone=CLASS_TONE.get(c.get("python_pred", ""), "neutral"),
        tm_tone=CLASS_TONE.get(c.get("tm_pred", ""), "neutral"),
        risk_score=risk_score, risk_reasons=risk_reasons,
        risk_tone=risk_tone, status_icon=status_icon,
        counterfactuals=counterfactuals)


@app.route("/claim/<cid>/card.png")
@login_required()
def claim_card(cid):
    c = fdb.get_doc("claims", cid)
    if not c or not _can_view(g.user, c):
        abort(404)
    m = models_mod.load_all()
    img = render_card(c, m["policies"][c["product_category"]])
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@app.route("/claim/<cid>/report")
@login_required()
def claim_report(cid):
    c = fdb.get_doc("claims", cid)
    if not c or not _can_view(g.user, c):
        abort(404)
    return Response(cs.build_report(c), mimetype="text/markdown",
                    headers={"Content-Disposition":
                             f"attachment; filename={cid}_report.md"})


   
@app.route("/claims")
@login_required()
def claims():
    user = g.user
    all_claims = (fdb.all_docs("claims") if user["role"] in ("reviewer", "admin")
                  else fdb.query("claims", "owner_email", "==", user["email"]))
    all_claims.sort(key=lambda c: c.get("created_at", ""), reverse=True)

    status_f = request.args.get("status", "All")
    decision_f = request.args.get("decision", "All")
    cat_f = request.args.get("category", "All")
    q = request.args.get("q", "").strip().lower()

    def match(c):
        if status_f != "All" and c.get("status") != status_f:
            return False
        if decision_f != "All" and c.get("final_decision") != decision_f:
            return False
        if cat_f != "All" and c.get("product_category") != cat_f:
            return False
        if q:
            hay = f"{c.get('claim_id', '')} {c.get('serial_number', '')} " \
                  f"{c.get('invoice_number', '')}".lower()
            if q not in hay:
                return False
        return True

    shown = [c for c in all_claims if match(c)]
    return render_template("claims.html", claims=shown,
                           total=len(all_claims),
                           status_f=status_f, decision_f=decision_f,
                           cat_f=cat_f, q=q,
                           categories=list(models_mod.load_all()["policies"]),
                           statuses=["All", "Draft", "Submitted",
                                     "Under Evaluation",
                                     "Additional Information Required",
                                     "Manual Review", "Approved", "Rejected",
                                     "Closed"],
                           decisions=["All", "Likely Valid", "Likely Invalid",
                                      "Manual Review Required"])


   
@app.route("/review")
@login_required(roles=["reviewer", "admin"])
def review_queue():
    claims = [c for c in fdb.all_docs("claims")
              if c.get("status") in ("Manual Review",
                                     "Additional Information Required")]
    claims.sort(key=lambda c: c.get("created_at", ""))
    items = []
    for c in claims:
        s, r, t = fraud_risk(c)
        items.append({"c": c, "risk": s, "reasons": r, "tone": t})
    stats = [
        {"label": "Awaiting review", "value": len(items), "icon": "👤",
         "tone": "review" if items else "neutral"},
        {"label": "Model disagreements",
         "value": sum(1 for i in items
                      if i["c"].get("consistency") == "Model Disagreement"),
         "icon": "🔀", "tone": "invalid"},
        {"label": "Duplicate indicators",
         "value": sum(1 for i in items if i["c"].get("duplicates", {}).get(
             "invoice_reused") or i["c"].get("duplicates", {}).get(
             "doc_hash_reuse") or i["c"].get("duplicates", {}).get(
             "prior_claims", 0) > 0), "icon": "🕵️", "tone": "invalid"},
        {"label": "Contradictions",
         "value": sum(1 for i in items if i["c"].get("rules_outcome", {})
                      .get("contradictions")), "icon": "⚠️", "tone": "review"},
    ]
    return render_template("review_queue.html", items=items, stats=stats)


@app.route("/review/<cid>/action", methods=["POST"])
@login_required(roles=["reviewer", "admin"])
def review_action(cid):
    user = g.user
    c = fdb.get_doc("claims", cid)
    if not c:
        abort(404)
    action = request.form.get("action")
    comment = request.form.get("comment", "").strip()
    if action == "approve":
        status, decision = "Approved", "approve"
    elif action == "reject":
        status, decision = "Rejected", "reject"
    else:
        cs.update_claim(cid, {"status": "Additional Information Required",
                              "reviewer": user["email"],
                              "reviewer_comment": comment},
                        event="Reviewer requested additional information",
                        actor=user["email"])
        fdb.log_audit("reviewer_decision", user["email"],
                      {"claim_id": cid, "decision": "request_info"})
        fdb.notify(c["owner_email"], cid,
                   f"Claim {cid}: additional information required — "
                   f"{comment or 'please contact support.'}")

        from src import email_service
        email_service.notify_claim_decision(
            c.get("owner_email"), cid, "Additional information required")
        flash(f"📨 Info requested on {cid}.", "success")
        return redirect(url_for("review_queue"))

    ai_final = c.get("final_decision", "")
    override = ((status == "Approved" and ai_final != "Likely Valid")
                or (status == "Rejected" and ai_final != "Likely Invalid"))
    cs.update_claim(cid, {"status": status, "reviewer": user["email"],
                          "reviewer_comment": comment,
                          "reviewer_decision": decision,
                          "override": override,
   
   
   
                          "ai_recommendation": c.get("final_decision"),
                          "final_decision": ("Likely Valid" if status == "Approved"
                                              else "Likely Invalid")},
                    event=f"Reviewer {status.lower()}"
                          + (" — override of AI recommendation" if override
                             else ""),
                    actor=user["email"])
    fdb.log_audit("reviewer_decision", user["email"],
                  {"claim_id": cid, "decision": decision,
                   "override": override})
    fdb.notify(c["owner_email"], cid,
               f"Claim {cid} {status.lower()} by reviewer.")

    from src import email_service
    email_service.notify_claim_decision(c.get("owner_email"), cid, status)
    flash(f"{'⚠️ Override recorded — ' if override else ''}"
          f"Claim {cid} {status.lower()}.", "success")
    return redirect(url_for("review_queue"))


   
@app.route("/admin")
@login_required(roles=["admin"])
def admin():
    claims = fdb.all_docs("claims", limit=1000)
    users = fdb.all_docs("users", limit=1000)
    audit = fdb.all_docs("audit", limit=200)
    if not claims:
        return render_template("admin.html", empty=True)

    from collections import Counter
    by_final = Counter(c.get("final_decision", "?") for c in claims)
    disagreements = [c for c in claims
                     if c.get("consistency") == "Model Disagreement"]
    dupes = [c for c in claims
             if c.get("duplicates", {}).get("invoice_reused")
             or c.get("duplicates", {}).get("doc_hash_reuse")
             or c.get("duplicates", {}).get("prior_claims", 0) > 0]
    pending = sum(1 for c in claims if c.get("status") in
                  ("Manual Review", "Additional Information Required"))
    avg_py = sum(c.get("py_top_conf", 0) for c in claims) / len(claims)
    avg_tm = sum(c.get("tm_top_conf", 0) for c in claims) / len(claims)

    chart = []
    for label in ("Likely Valid", "Likely Invalid", "Manual Review Required"):
        v = by_final.get(label, 0)
        pct = round(v / max(1, len(claims)) * 100)
        chart.append((label, v, CLASS_TONE.get(
            {"Likely Valid": "Valid Claim",
             "Likely Invalid": "Invalid Claim",
             "Manual Review Required": "Manual Review"}[label], "neutral"),
            pct))

    from collections import Counter
    chart_labels = ["Likely Valid", "Likely Invalid", "Manual Review"]
    chart_values = [by_final.get(l, 0) for l in chart_labels]

    cat_counts = Counter(c.get("product_category", "Other") for c in claims)
    category_labels = list(cat_counts.keys())
    category_values = list(cat_counts.values())

    fault_counts = Counter(c.get("fault_category", "unknown").replace("_", " ")
                           for c in claims).most_common(8)
    fault_labels = [f for f, _ in fault_counts] or ["none"]
    fault_values = [n for _, n in fault_counts] or [0]

    day_counts = Counter((c.get("created_at") or "")[:10] for c in claims
                         if (c.get("created_at") or "")[:10])
    days_sorted = sorted(day_counts)
    day_labels = [d[5:] for d in days_sorted] or ["none"]
    day_values = [day_counts[d] for d in days_sorted] or [0]

    reject_reasons = Counter()
    for c in claims:
        for hf in (c.get("rules_outcome", {}).get("hard_fails") or []):
            reject_reasons[hf.split("(")[0].strip()[:38]] += 1
    reject_sorted = reject_reasons.most_common(6)
    reject_labels = [r for r, _ in reject_sorted] or ["no rejections yet"]
    reject_values = [n for _, n in reject_sorted] or [0]

    return render_template(
        "admin.html", empty=False, claims=claims, users=users, audit=audit,
        total=len(claims), by_final=by_final, pending=pending,
        disagreements=disagreements, dupes=dupes,
        avg_py=avg_py, avg_tm=avg_tm,
        chart_labels=chart_labels, chart_values=chart_values,
        category_labels=category_labels, category_values=category_values,
        fault_labels=fault_labels, fault_values=fault_values,
        day_labels=day_labels, day_values=day_values,
        reject_labels=reject_labels, reject_values=reject_values)


@app.route("/admin/export")
@login_required(roles=["admin"])
def admin_export():
    import pandas as pd
    claims = fdb.all_docs("claims", limit=1000)
    rows = [{"claim_id": c["claim_id"], "owner": c.get("owner_email"),
             "category": c.get("product_category"), "brand": c.get("brand"),
             "fault": c.get("fault_category"),
             "python_pred": c.get("python_pred"),
             "python_conf": round(c.get("py_top_conf", 0), 3),
             "tm_pred": c.get("tm_pred"),
             "tm_conf": round(c.get("tm_top_conf", 0), 3),
             "consistency": c.get("consistency"),
             "final_decision": c.get("final_decision"),
             "status": c.get("status")} for c in claims]
    csv_data = pd.DataFrame(rows).to_csv(index=False)
    return Response(csv_data, mimetype="text/csv",
                    headers={"Content-Disposition":
                             "attachment; filename=assurex_claims_export.csv"})
   
@app.route("/admin/templates", methods=["GET", "POST"])
@login_required(roles=["admin"])
def admin_templates():
    m = models_mod.load_all()
    categories = list(m["policies"])
    if request.method == "POST":
        if request.form.get("action") == "remove":
            tid = request.form.get("tid", "")
            if product_catalog.remove_template(tid):
                flash(f"🗑️ Template {tid} removed.", "success")
            else:
                flash("Template not found.", "error")
        else:
            t, err = product_catalog.add_template(
                request.form.get("name", ""), request.form.get("brand", ""),
                request.form.get("model", ""),
                request.form.get("category", ""), categories)
            flash(f"✅ Template added: {t['name']}" if not err else err,
                  "success" if not err else "error")
        return redirect(url_for("admin_templates"))
    return render_template("admin_templates.html",
                           templates=product_catalog.load_templates(),
                           categories=categories)


   
@app.route("/products/smart", methods=["GET", "POST"])
@login_required()
def smart_register():
    m = models_mod.load_all()
    categories = list(m["policies"])
    if request.method == "POST":
        query = None
        qr = request.files.get("qr")
        typed = request.form.get("query", "").strip()
        if qr and qr.filename:
            decoded = smart_lookup.decode_qr(qr.read())
            if decoded:
                query = decoded
                flash(f"📷 QR decoded: “{decoded}”", "success")
            else:
                flash("No QR code found in that image - type the product "
                      "name instead.", "warning")
        if not query and typed:
            query = typed
        if not query:
            flash("Upload a QR image or type a product name.", "error")
            return redirect(url_for("smart_register"))
        result = smart_lookup.lookup_product(query, categories)
        if not result.get("ok"):
            flash(f"ℹ️ {result.get('error')}", "warning")
        return render_template("smart_register.html", step="confirm",
                               query=query, result=result,
                               categories=categories,
                               policies=m["policies"])
    return render_template("smart_register.html", step="scan",
                           categories=categories)


@app.route("/products/smart/save", methods=["POST"])
@login_required()
def smart_register_save():
    m = models_mod.load_all()
    policies = m["policies"]
    user = g.user
    name = request.form.get("name", "").strip()
    category = request.form.get("category", "")
    brand = request.form.get("brand", "").strip()
    model = request.form.get("model", "").strip()
    serial = request.form.get("serial", "").strip()
    purchase = request.form.get("purchase_date", "")
    if not all([name, brand, serial, purchase]) \
            or category not in policies:
        flash("All fields marked * are required.", "error")
        return redirect(url_for("smart_register"))
   
    owner = user["email"]
    if user["role"] in ("admin", "service_center"):
        chosen = request.form.get("owner_email", "").strip().lower()
        if chosen:
            if fdb.get_doc("users", chosen):
                owner = chosen
            else:
                flash(f"Owner {chosen} not found - registered to your "
                      f"account instead.", "warning")
    pol = policies[category]
    ext = min(int(request.form.get("extended", 0) or 0),
              int(pol["extended_warranty_max_months"]))
    pid = f"PRD-{uuid.uuid4().hex[:6].upper()}"
    purchase_d = parse_date(purchase)
    fdb.set_doc("products", pid, {
        "product_id": pid, "owner_email": owner,
        "name": name, "product_category": category,
        "brand": brand, "model": model, "serial_number": serial,
        "purchase_date": purchase_d.isoformat(),
        "purchase_price": float(request.form.get("price", 0) or 0),
        "retailer": request.form.get("retailer", "").strip(),
        "warranty_type": "extended" if ext else "standard",
        "warranty_months": pol["standard_warranty_months"],
        "extended_months": ext,
        "registered_via": "smart_register",
        "ai_assisted": True,
        "human_verified": True})
    fdb.log_audit("product_registered_smart", user["email"],
                  {"product_id": pid, "owner": owner, "ai_assisted": True})
    end = add_months(purchase_d, int(pol["standard_warranty_months"]) + ext)
    flash(f"✅ Registered {name} ({pid}) for {owner}. "
          f"Warranty until {end.isoformat()}.", "success")
    return redirect(url_for("products"))
   

   
@app.route("/profile", methods=["GET", "POST"])
@login_required()
def profile():
    user = g.user
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        password = request.form.get("password", "")
        if not name:
            flash("Name is required.", "error")
        else:
            updates = {"name": name}
            if password:
                if len(password) < 6:
                    flash("Password must be at least 6 characters.", "error")
                    return render_template("profile.html")
                from src.auth import hash_password
                updates["password"] = hash_password(password)
            fdb.set_doc("users", user["email"], updates, merge=True)
            fdb.log_audit("profile_updated", user["email"])
            flash("✅ Profile updated.", "success")
            return redirect(url_for("profile"))
    return render_template("profile.html")


   
PROFILE_PHOTOS = ROOT / "uploads" / "_profile_photos"
ALLOWED_PHOTO_EXT = (".jpg", ".jpeg", ".png")
MAX_PHOTO_BYTES = 2 * 1024 * 1024   # 2 MB


@app.route("/profile/photo/upload", methods=["POST"])
@login_required()
def profile_photo_upload():
    user = g.user
    f = request.files.get("photo")
    if not f or not f.filename:
        flash("Choose an image file first.", "error")
        return redirect(url_for("profile"))
    if not f.filename.lower().endswith(ALLOWED_PHOTO_EXT):
        flash("Only JPG or PNG images are allowed.", "error")
        return redirect(url_for("profile"))
    data = f.read()
    if len(data) > MAX_PHOTO_BYTES:
        flash("Photo must be under 2 MB.", "error")
        return redirect(url_for("profile"))
   
    try:
        img = Image.open(io.BytesIO(data))
        img = img.convert("RGB")
        img.thumbnail((400, 400))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=88)
        data = buf.getvalue()
    except Exception:
        flash("That file is not a valid image.", "error")
        return redirect(url_for("profile"))
    PROFILE_PHOTOS.mkdir(parents=True, exist_ok=True)
    safe = secure_filename(user["email"]) + ".jpg"
    (PROFILE_PHOTOS / safe).write_bytes(data)
    fdb.set_doc("users", user["email"], {"photo": safe}, merge=True)
    fdb.log_audit("profile_photo_updated", user["email"])
    flash("📸 Profile photo updated.", "success")
    return redirect(url_for("profile"))


@app.route("/profile/photo/remove", methods=["POST"])
@login_required()
def profile_photo_remove():
    user = g.user
    safe = secure_filename(user["email"]) + ".jpg"
    p = PROFILE_PHOTOS / safe
    if p.exists():
        p.unlink()
    fdb.set_doc("users", user["email"], {"photo": ""}, merge=True)
    fdb.log_audit("profile_photo_removed", user["email"])
    flash("🗑️ Photo removed.", "success")
    return redirect(url_for("profile"))


@app.route("/profile/photo/<email>")
@login_required()
def profile_photo(email):
    """Serve a user's avatar with access control (logged-in users only)."""
    doc = fdb.get_doc("users", email.strip().lower())
    name = doc.get("photo") if doc else None
    if not name:
        abort(404)
    p = PROFILE_PHOTOS / secure_filename(name)
    if not p.exists():
        abort(404)
    return send_file(p, mimetype="image/jpeg")


   
@app.route("/claim/<cid>/doc/<int:index>")
@login_required()
def claim_doc_download(cid, index):
    c = fdb.get_doc("claims", cid)
    if not c or not _can_view(g.user, c):
        abort(404)
    docs = c.get("documents", [])
    if not (0 <= index < len(docs)):
        abort(404)
    d = docs[index]
    path = ROOT / "uploads" / cid / (d["type"] + "__" + secure_filename(d["filename"]))
    if not path.exists():
        abort(404)
    return send_file(path, as_attachment=True, download_name=d["filename"])


@app.route("/claim/<cid>/doc/<int:index>/remove", methods=["POST"])
@login_required()
def claim_doc_remove(cid, index):
    user = g.user
    c = fdb.get_doc("claims", cid)
    if not c:
        abort(404)
    if c["owner_email"] != user["email"] and user["role"] != "admin":
        abort(403)
    if c["status"] in ("Approved", "Rejected", "Closed"):
        flash("Cannot modify documents on a decided claim - the audit "
              "trail must be preserved.", "warning")
        return redirect(url_for("claim_detail", cid=cid))
    docs = c.get("documents", [])
    if not (0 <= index < len(docs)):
        abort(404)
    removed = docs.pop(index)
    path = ROOT / "uploads" / cid / (removed["type"] + "__" + secure_filename(removed["filename"]))
    if path.exists():
        path.unlink()
    c["documents"] = docs
    for dtype in ("receipt", "warranty_card", "product_image",
                  "serial_evidence", "fault_evidence", "repair_report"):
        c["has_" + dtype] = any(d["type"] == dtype for d in docs)
    c.pop("_id", None)
    fdb.set_doc("claims", cid, c)
    fdb.log_audit("document_removed", user["email"],
                  {"claim_id": cid, "file": removed["filename"]})
    flash("🗑️ Removed " + removed["filename"] + " - the claim's document "
          "flags were updated.", "success")
    return redirect(url_for("claim_detail", cid=cid))


   
@app.route("/claim/<cid>/close", methods=["POST"])
@login_required(roles=["reviewer", "admin"])
def claim_close(cid):
    user = g.user
    c = fdb.get_doc("claims", cid)
    if not c:
        abort(404)
    if c["status"] not in ("Approved", "Rejected"):
        flash("Only decided claims (Approved/Rejected) can be closed.",
              "warning")
        return redirect(url_for("claim_detail", cid=cid))
    cs.update_claim(cid, {"status": "Closed"},
                    event="Claim closed by " + user["role"],
                    actor=user["email"])
    fdb.log_audit("claim_closed", user["email"], {"claim_id": cid})
    fdb.notify(c["owner_email"], cid, "Claim " + cid + " has been closed.")
    flash("🔒 Claim " + cid + " closed.", "success")
    return redirect(url_for("claim_detail", cid=cid))
   
@app.route("/claim/<cid>/dispatch")
@login_required()
def claim_dispatch(cid):
    """Match an approved claim to certified repair centers."""
    c = fdb.get_doc("claims", cid)
    if not c or not _can_view(g.user, c):
        abort(404)
    if c["final_decision"] != "Likely Valid" or \
            c["status"] not in ("Approved", "Closed"):
        flash("Dispatch is available for approved claims only.", "warning")
        return redirect(url_for("claim_detail", cid=cid))
    city = c.get("service_city") or request.args.get("city", "")
    matches = service_routing.match_centers(c, city)
    return render_template("claim_dispatch.html", c=c, matches=matches,
                           city=city or None,
                           dispatch=c.get("dispatch"))


@app.route("/claim/<cid>/dispatch/confirm", methods=["POST"])
@login_required()
def claim_dispatch_confirm(cid):
    """Confirm dispatch to the chosen center - records the assignment,
    updates the claim status, notifies, and logs the audit trail."""
    user = g.user
    c = fdb.get_doc("claims", cid)
    if not c:
        abort(404)
    if c.get("owner_email") != user["email"] and user["role"] not in \
            ("admin", "service_center"):
        abort(403)
    center_id = request.form.get("center_id", "")
    cfg = service_routing.load_centers()
    center = next((x for x in cfg["centers"] if x["id"] == center_id), None)
    if not center:
        flash("Choose a valid service center.", "error")
        return redirect(url_for("claim_dispatch", cid=cid))
    if center["id"] not in center["categories"] and \
            c["product_category"] not in center["categories"]:
        flash("That center is not certified for this product category.",
              "error")
        return redirect(url_for("claim_dispatch", cid=cid))

    deadline = service_routing.sla_deadline(center["sla_days"])
    dispatch = {"center_id": center["id"], "center_name": center["name"],
                "center_city": center["city"], "center_phone": center["phone"],
                "sla_days": center["sla_days"], "deadline": deadline,
                "assigned_at": date.today().isoformat(),
                "assigned_by": user["email"], "status": "Repair Scheduled"}
    cs.update_claim(cid, {"dispatch": dispatch, "status": "Under Evaluation"},
                    event=f"Dispatched to {center['name']} - SLA deadline "
                          f"{deadline} (repair scheduled)",
                    actor=user["email"])
    fdb.log_audit("claim_dispatched", user["email"],
                  {"claim_id": cid, "center": center["id"],
                   "sla": center["sla_days"]})
    fdb.notify(c["owner_email"], cid,
               f"Claim {cid}: repair scheduled at {center['name']} - "
               f"expected by {deadline}. Contact: {center['phone']}")

    from src import email_service
    email_service.send_email(
        c.get("owner_email"),
        "AssureX claim " + cid + ": repair scheduled",
        "Your approved claim " + cid + " has been scheduled for repair at "
        + center["name"] + " (" + center["city"] + ")."
        + "\nExpected completion by: " + deadline
        + "\nContact: " + center["phone"] + "\n\n- AssureX Claim Engine")
    flash(f"🔧 Repair scheduled at {center['name']} — SLA deadline "
          f"{deadline}.", "success")
    return redirect(url_for("claim_detail", cid=cid))


   
@app.route("/desk")
@login_required(roles=["service_center"])
def service_desk():
    user = g.user
    claims = fdb.all_docs("claims", limit=500)
    filed = [c for c in claims
             if any(t.get("actor") == user["email"]
                    for t in c.get("timeline", []))][-15:]
    filed.sort(key=lambda c: c.get("created_at", ""), reverse=True)
    products = fdb.all_docs("products", limit=500)
    registered_by_us = [p for p in products
                         if p.get("registered_by") == user["email"]][-10:]
    return render_template("service_desk.html", claims=filed,
                           products=registered_by_us)


   
@app.route("/admin/approvals")
@login_required(roles=["admin"])
def admin_approvals():
    all_users = fdb.all_docs("users", limit=500)
    pending_users = [u for u in all_users if u.get("status") == "pending"]
    stats = [
        {"label": "Pending approvals", "value": len(pending_users),
         "icon": "⏳", "tone": "review" if pending_users else "neutral"},
        {"label": "Active users",
         "value": sum(1 for u in all_users
                      if u.get("status", "active") == "active"),
         "icon": "✅", "tone": "valid"},
    ]
    return render_template("admin_approvals.html", users=pending_users,
                           stats=stats)


@app.route("/admin/approvals/<email>/action", methods=["POST"])
@login_required(roles=["admin"])
def admin_approval_action(email):
    action = request.form.get("action")
    doc = fdb.get_doc("users", email)
    if not doc:
        abort(404)
    if action == "approve":
        fdb.set_doc("users", email, {"status": "active"}, merge=True)
        fdb.log_audit("user_approved", g.user["email"], {"user": email})
        fdb.notify(email, None, "Your AssureX account has been approved - "
                   "you can now log in.")
        from src import email_service
        ok, err = email_service.notify_account_approved(
            email, doc.get("name", ""), doc.get("role", ""))
        if ok:
            flash(f"✅ Approved {email} - notification email sent.",
                  "success")
        else:
            flash(f"✅ Approved {email} - in-app notification sent "
                  f"(email: {err}).", "success")
    elif action == "reject":
        fdb.set_doc("users", email, {"status": "rejected"}, merge=True)
        fdb.log_audit("user_rejected", g.user["email"], {"user": email})
        flash(f"⛔ Rejected {email}.", "warning")
    return redirect(url_for("admin_approvals"))


   
@app.route("/admin/links")
@login_required(roles=["admin", "reviewer"])
def entity_links():
    from src import entity_links as el
    claims = fdb.all_docs("claims", limit=1000)
    links = el.build_links(claims)
    try:
        min_c = int(models_mod.load_all()["settings"]
                    .get("syndicate_min_cluster", 3))
    except Exception:
        min_c = 3
    clusters = el.build_clusters(claims, min_cluster=min_c,
                                  min_link_types=2)
    cluster_ids = {cid for cl in clusters
                   for cid in cl["members"]}
   
    nodes, edges, seen = [], [], set()
    for c in claims:
        cid = c.get("claim_id")
        if not cid:
            continue
        cluster_ids = {x for cl in clusters for x in cl["members"]}
        tone = ("invalid" if cid in cluster_ids else
                "valid" if c.get("status") == "Approved" else "review")
        nodes.append({"id": cid, "label": cid, "type": "claim",
                      "tone": tone,
                      "owner": c.get("owner_email", ""),
                      "status": c.get("status", "")})
        seen.add(cid)
    ent_id = 0
    for ent, ids in links.items():
        ent_id += 1
        eid = f"e{ent_id}"
        nodes.append({"id": eid,
                      "label": f"{ent[0]}: {ent[1][:16]}",
                      "type": "entity", "tone": "info"})
        for cid in ids:
            edges.append({"source": eid, "target": cid})

    import json as _json
   
    nodes, edges, seen = [], [], set()
    for c in claims:
        cid = c.get("claim_id")
        if not cid:
            continue
        cluster_ids = {x for cl in clusters for x in cl["members"]}
        tone = ("invalid" if cid in cluster_ids else
                "valid" if c.get("status") == "Approved" else "review")
        nodes.append({"id": cid, "label": cid, "type": "claim",
                      "tone": tone,
                      "owner": c.get("owner_email", ""),
                      "status": c.get("status", "")})
        seen.add(cid)
    ent_id = 0
    for ent, ids in links.items():
        ent_id += 1
        eid = f"e{ent_id}"
        nodes.append({"id": eid,
                      "label": f"{ent[0]}: {ent[1][:16]}",
                      "type": "entity", "tone": "info"})
        for cid in ids:
            edges.append({"source": eid, "target": cid})

    import json as _json
   
    nodes, edges, seen = [], [], set()
    for c in claims:
        cid = c.get("claim_id")
        if not cid:
            continue
        cluster_ids = {x for cl in clusters for x in cl["members"]}
        tone = ("invalid" if cid in cluster_ids else
                "valid" if c.get("status") == "Approved" else "review")
        nodes.append({"id": cid, "label": cid, "type": "claim",
                      "tone": tone,
                      "owner": c.get("owner_email", ""),
                      "status": c.get("status", "")})
        seen.add(cid)
    ent_id = 0
    for ent, ids in links.items():
        ent_id += 1
        eid = f"e{ent_id}"
        nodes.append({"id": eid,
                      "label": f"{ent[0]}: {ent[1][:16]}",
                      "type": "entity", "tone": "info"})
        for cid in ids:
            edges.append({"source": eid, "target": cid})

    import json as _json
   
    nodes, edges, seen = [], [], set()
    for c in claims:
        cid = c.get("claim_id")
        if not cid:
            continue
        cluster_ids = {x for cl in clusters for x in cl["members"]}
        tone = ("invalid" if cid in cluster_ids else
                "valid" if c.get("status") == "Approved" else "review")
        nodes.append({"id": cid, "label": cid, "type": "claim",
                      "tone": tone,
                      "owner": c.get("owner_email", ""),
                      "status": c.get("status", "")})
        seen.add(cid)
    ent_id = 0
    for ent, ids in links.items():
        ent_id += 1
        eid = f"e{ent_id}"
        nodes.append({"id": eid,
                      "label": f"{ent[0]}: {ent[1][:16]}",
                      "type": "entity", "tone": "info"})
        for cid in ids:
            edges.append({"source": eid, "target": cid})

    import json as _json
    return render_template("entity_links.html",
                           total_claims=len(claims), links=links,
                           clusters=clusters,
                           cluster_claims=len(cluster_ids),
                           graph_json=_json.dumps({"nodes": nodes,
                                                   "edges": edges}))
   
@app.route("/chat", methods=["POST"])
@login_required()
def chat():
    """Help assistant - guidance only, NEVER makes claim decisions.
    Groq AI rephrases stored explanations; the evaluation system's
    outputs are the single source of decision content."""
    from src import chatbot
    message = request.form.get("message", "").strip()
    if not message:
        return {"response": "Please type a question."}

    history = session.get("chat_history", [])
    response = chatbot.chat(g.user["email"], message, fdb, history)

   
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": response})
    session["chat_history"] = history[-8:]

    fdb.log_audit("chatbot_query", g.user["email"],
                  {"message_length": len(message)})
    return {"response": response}
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)