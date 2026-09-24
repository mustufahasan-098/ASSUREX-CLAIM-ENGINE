"""Firestore wrapper. Every database call in the app goes through this
module - one place to audit, one place to change."""
import os
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore

ROOT = Path(__file__).resolve().parent.parent
_client = None


def db():
    global _client
    if _client is None:
        path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") \
            or str(ROOT / "firebase_service_account.json")
        if not Path(path).exists():
            raise RuntimeError(
                "firebase_service_account.json not found. Download the private "
                "key from Firebase Console > Project Settings > Service "
                "accounts and save it in the project root.")
        if not firebase_admin._apps:
            firebase_admin.initialize_app(credentials.Certificate(path))
        _client = firestore.client()
    return _client


def get_doc(coll, doc_id):
    snap = db().collection(coll).document(doc_id).get()
    return snap.to_dict() if snap.exists else None


def set_doc(coll, doc_id, data, merge=False):
    db().collection(coll).document(doc_id).set(data, merge=merge)


def query(coll, field, op, value, limit=200):
    q = db().collection(coll).where(field, op, value).limit(limit)
    return [{**d.to_dict(), "_id": d.id} for d in q.stream()]


def all_docs(coll, limit=500):
    return [{**d.to_dict(), "_id": d.id}
            for d in db().collection(coll).limit(limit).stream()]


def next_claim_id():
    """Sequential readable claim IDs: CLM-A10001, CLM-A10002, ..."""
    ref = db().collection("counters").document("claims")
    n = (ref.get().to_dict() or {}).get("n", 10000) + 1
    ref.set({"n": n})
    return f"CLM-A{n}"


def log_audit(action, actor, details=None):
    db().collection("audit").add({"action": action, "actor": actor,
                                  "details": details or {},
                                  "ts": firestore.SERVER_TIMESTAMP})


def notify(user_email, claim_id, message):
    db().collection("notifications").add({"user_email": user_email,
                                          "claim_id": claim_id,
                                          "message": message, "read": False,
                                          "ts": firestore.SERVER_TIMESTAMP})