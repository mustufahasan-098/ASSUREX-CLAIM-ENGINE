"""finalfix.py - applies ALL FIX5 + profile-photo changes to app.py.

Installs (idempotent - safe to run repeatedly):
  1. Profile page route (req ii) + profile photo upload/remove/serve
  2. Document download + remove routes with access control (req xiv)
  3. Claim Close lifecycle route (req xxxviii)

Templates (profile.html) are written directly - no anchors needed.
Does NOT touch: claim_service.py, claim_result.html, dashboard stats,
base.html (those are separate small pastes - listed at the end).

Safety: backup -> anchor-match -> patch -> py_compile -> rollback on error.
"""
import py_compile
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = ROOT / "app.py"
MAIN_ANCHOR = 'if __name__ == "__main__":'

# ---------------------------------------------------------------- profile
PROFILE_HTML = '''{% extends "base.html" %}
{% import "macros.html" as ui %}
{% block title %}My Profile — AssureX{% endblock %}
{% block content %}
{{ ui.hero("🧑", "My Profile", "View and update your account details") }}
<div class="ax-grid-2">
  <div class="ax-form-card">
    <h4>✏️ Update profile</h4>
    <form method="post">
      <div class="ax-field"><label>Full name *</label>
        <input class="ax-input" name="name" required value="{{ current_user.name }}"></div>
      <div class="ax-field"><label>Email (User ID — read-only)</label>
        <input class="ax-input" value="{{ current_user.email }}" disabled></div>
      <div class="ax-field"><label>Role</label>
        <input class="ax-input" value="{{ current_user.role.replace('_',' ')|title }}" disabled></div>
      <div class="ax-field"><label>New password (leave empty to keep current)</label>
        <input class="ax-input" type="password" name="password" minlength="6" placeholder="min 6 characters"></div>
      <button class="ax-btn ax-btn--primary" type="submit">💾 Save changes</button>
    </form>
  </div>
  <div>
    <div class="ax-card" style="text-align:center;">
      <h4>📸 Profile photo</h4>
      {% if current_user.photo %}
        <img src="{{ url_for('profile_photo', email=current_user.email) }}" alt="profile photo"
             style="width:120px; height:120px; border-radius:50%; object-fit:cover;
                    border:3px solid var(--acc); box-shadow:var(--sh-2); margin:10px 0;">
      {% else %}
        <div style="width:120px; height:120px; border-radius:50%; margin:10px auto;
                    display:flex; align-items:center; justify-content:center;
                    font-size:2.6rem; font-weight:800;
                    background:var(--acc-tint); color:var(--acc-hi); border:3px solid var(--acc);">
          {{ current_user.name[:1]|upper }}
        </div>
      {% endif %}
      <form method="post" action="{{ url_for('profile_photo_upload') }}" enctype="multipart/form-data" style="margin-top:10px;">
        <div class="ax-field" style="text-align:left;">
          <label>Upload photo (JPG/PNG, max 2 MB)</label>
          <input class="ax-input" type="file" name="photo" accept=".jpg,.jpeg,.png" required>
        </div>
        <button class="ax-btn ax-btn--primary ax-btn--block" type="submit">📤 Upload photo</button>
      </form>
      {% if current_user.photo %}
      <form method="post" action="{{ url_for('profile_photo_remove') }}" style="margin-top:8px;">
        <button class="ax-btn ax-btn--danger ax-btn--block" type="submit">🗑️ Remove photo</button>
      </form>
      {% endif %}
    </div>
    <div class="ax-card">
      <h4>🔒 Account security</h4>
      {{ ui.kv_grid([
        ("User ID (email)", current_user.email),
        ("Role", current_user.role),
        ("Member since", current_user.get("created_at", "—")),
        ("Failed login attempts", current_user.get("failed_attempts", 0) ~ " (locks at 5)")
      ]) }}
      {{ ui.alert("Photos are validated as real images (Pillow), capped at 2 MB, stored server-side, and served with access control.", "info") }}
    </div>
  </div>
</div>
{% endblock %}
'''

ROUTES = '''

# ------------------------------------------------------------- profile
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


# ----------------------------------------------------- profile photos
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
    # security: verify it is a REAL image, then normalise to a safe JPEG
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


# ----------------------------------------------------- document actions
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


# ------------------------------------------------- claim close lifecycle
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

'''

# fixes: profile.html references profile_photo_upload (not profile/photo)
# route name must match: url_for('profile_photo_upload') -> we named the
# route function profile_photo_upload with URL /profile/photo/upload. OK.


def ok(msg):
    print(f"  [OK]      {msg}")


def skip(msg):
    print(f"  [SKIP]    {msg} (already present)")


def main():
    print("=" * 64)
    print("FINALFIX - FIX5 + profile photos")
    print("=" * 64)

    if not APP.exists():
        sys.exit("app.py not found.")

    # ---- 1. profile.html (direct write - no anchors needed)
    p = ROOT / "templates" / "profile.html"
    if p.exists() and "profile_photo_upload" in p.read_text(encoding="utf-8"):
        skip("templates/profile.html")
    else:
        p.write_text(PROFILE_HTML, encoding="utf-8")
        ok("templates/profile.html written")

    # ---- 2. app.py routes
    content = APP.read_text(encoding="utf-8")
    changed = False

    markers = {
        "profile route": "def profile(",
        "profile photo routes": "def profile_photo_upload(",
        "document download route": "def claim_doc_download(",
        "document remove route": "def claim_doc_remove(",
        "claim close route": "def claim_close(",
    }
    missing = [name for name, marker in markers.items()
               if marker not in content]
    if not missing:
        skip("all app.py routes")
    else:
        n = content.count(MAIN_ANCHOR)
        if n != 1:
            sys.exit(f"[ABORT] {n} occurrences of __main__ anchor "
                     f"(expected 1). Nothing changed.")
        backup = ROOT / "app.py.bak2"
        shutil.copy(APP, backup)
        content = content.replace(MAIN_ANCHOR, ROUTES + MAIN_ANCHOR, 1)
        APP.write_text(content, encoding="utf-8")
        try:
            py_compile.compile(str(APP), doraise=True)
            ok(f"routes inserted ({', '.join(missing)}) - syntax OK "
               f"(backup: app.py.bak2)")
        except py_compile.PyCompileError as e:
            shutil.copy(backup, APP)
            sys.exit(f"[ABORT] syntax check failed - backup restored.\n{e}")

    print("\n" + "=" * 64)
    print("DONE - app.py fully patched.")
    print("=" * 64)


if __name__ == "__main__":
    main()