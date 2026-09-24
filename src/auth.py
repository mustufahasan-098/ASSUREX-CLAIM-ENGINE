"""Registration/login with PBKDF2-HMAC-SHA256 password hashing (240,000
iterations, per-user random salt - stdlib, zero external dependencies).
Roles: customer, service_center, reviewer, admin (admin is seed-only).
Includes failed-attempt lockout (5 tries) per SRS security expectations."""
import hashlib
import os
from datetime import datetime

from . import firebase_db as fdb

ITERATIONS = 240_000
ROLES = ("customer", "service_center", "reviewer", "admin")


def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, ITERATIONS)
    return f"{salt.hex()}${dk.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        salt_hex, dk_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", pw.encode(),
                                 bytes.fromhex(salt_hex), ITERATIONS)
        return dk.hex() == dk_hex
    except ValueError:
        return False


def register(name, email, password, role):
    email = (email or "").strip().lower()
    if role == "admin":
        return None, "Admin accounts are created only via the seed script."
    if not name or not email or not password:
        return None, "All fields are required."
    if len(password) < 6:
        return None, "Password must be at least 6 characters."
    if "@" not in email:
        return None, "Please enter a valid email address."
    if fdb.get_doc("users", email):
        return None, "An account with this email already exists."
    user = {"name": name.strip(), "email": email, "role": role,
            "password": hash_password(password), "failed_attempts": 0,
            "created_at": datetime.now().isoformat(timespec="seconds")}
    fdb.set_doc("users", email, user)
    fdb.log_audit("user_registered", email, {"role": role})
    return {k: v for k, v in user.items() if k != "password"}, None


def login(email, password):
    email = (email or "").strip().lower()
    doc = fdb.get_doc("users", email)
    if not doc:
        return None, "No account with this email."
    if doc.get("failed_attempts", 0) >= 5:
        return None, "Account locked after 5 failed attempts. Contact admin."
    if not verify_password(password, doc["password"]):
        fdb.set_doc("users", email,
                    {"failed_attempts": doc.get("failed_attempts", 0) + 1},
                    merge=True)
        return None, "Incorrect password."
    fdb.set_doc("users", email, {"failed_attempts": 0}, merge=True)
    return {k: v for k, v in doc.items() if k != "password"}, None