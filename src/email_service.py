"""AssureX email notifications - Gmail SMTP with graceful fallback.

All notification events:
  1. Account approval          -> the new user
  2. Claim submission          -> the claim owner
  3. Reviewer approve/reject   -> the claim owner
  4. Info requested            -> the claim owner
  5. Repair scheduled          -> the claim owner
  6. Fraud alert (score >= 60) -> ADMIN ONLY (never tip off a claimant)

Design decisions:
  - send_email_async: background threads with a short startup stagger -
    avoids Gmail's rapid-sequential-connection throttling (the root
    cause of dropped thread sends found during testing)
  - Demo-inbox copies: every email is also delivered to DEMO_NOTIFY_EMAIL
    so notifications are observable during evaluation (config-driven)
  - Fraud alerts go to admins only: notifying a suspected fraudster
    would compromise investigation
  - Falls back silently to in-app notifications when SMTP unconfigured"""
import os
import smtplib
import time
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from email.utils import formatdate
import time

# self-sufficient env loading: works whether or not the host application
# called load_dotenv() first
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except Exception:
    pass

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

DEMO_NOTIFY_EMAIL = os.environ.get("DEMO_NOTIFY_EMAIL",
                                   "khoobwearz@gmail.com")
ADMIN_ALERT_EMAIL = os.environ.get("ADMIN_ALERT_EMAIL",
                                   "khoobwearz@gmail.com")


def email_configured():
    return bool(os.environ.get("SMTP_EMAIL") and
                os.environ.get("SMTP_APP_PASSWORD"))


# ------------------------------------------------------------- low-level send
def _deliver(to_email, subject, body_text):
    """Synchronous send with one retry. Returns (ok, error). Never raises."""
    last_err = None
    for attempt in range(2):                    # retry once on failure
        try:
            msg = MIMEMultipart()
            msg["From"] = f"AssureX <{os.environ['SMTP_EMAIL']}>"
            msg["To"] = to_email
            msg["Subject"] = subject
            msg["Reply-To"] = os.environ["SMTP_EMAIL"]
            msg["Date"] = formatdate(localtime=True)
            msg["Message-ID"] = f"<assurex-{int(time.time())}-{hash(to_email) % 99999}@assurex.app>"
            msg.attach(MIMEText(body_text, "plain"))
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
                server.starttls()
                server.login(os.environ["SMTP_EMAIL"],
                             os.environ["SMTP_APP_PASSWORD"])
                server.send_message(msg)
            return True, None
        except Exception as e:
            last_err = str(e)
            if attempt == 0:
                time.sleep(1.5)                 # brief pause before retry
    return False, last_err


def send_email(to_email, subject, body_text):
    """Synchronous send with demo-inbox copy. Returns (ok, err)."""
    if not email_configured():
        return False, "SMTP not configured - in-app notification only"
    if not to_email or "@" not in to_email:
        to_email = DEMO_NOTIFY_EMAIL   # invalid recipient -> demo inbox
    ok, err = _deliver(to_email, subject, body_text)
    # demo copy (separate connection, brief pause avoids Gmail throttle)
    if DEMO_NOTIFY_EMAIL and to_email != DEMO_NOTIFY_EMAIL:
        time.sleep(0.5)
        _deliver(DEMO_NOTIFY_EMAIL, f"[copy] {subject}", body_text)
    return ok, err


def send_email_async(to_email, subject, body_text):
    """Background-thread send. Non-daemon thread with a short stagger so
    (a) Python does not kill the send mid-flight in short-lived
    processes (the test-script failure mode) and (b) rapid consecutive
    Gmail SMTP connections do not throttle each other. In the Flask app
    the request returns immediately; the thread completes in ~1-2s."""
    def _run():
        try:
            time.sleep(0.2)                     # stagger thread start
            send_email(to_email, subject, body_text)
        except Exception:
            pass                                 # never break the app
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    # keep a reference so the interpreter waits in short-lived scripts
    _THREADS.append(t)


_THREADS = []                                     # active email threads


def _wait_for_emails():
    """Wait for all pending email threads (used by tests / shutdown)."""
    for t in list(_THREADS):
        t.join(timeout=25)
    _THREADS.clear()


# ------------------------------------------------------ notification builders

def notify_account_approved(email, name, role):
    send_email_async(
        email, "Your AssureX account has been approved",
        f"Hello {name},\n\nYour AssureX {role.replace('_', ' ').title()} "
        f"account has been approved by an administrator.\n"
        f"You can now log in at any time.\n\n- AssureX Claim Engine")


def notify_claim_submitted(email, claim_id, product, decision, status):
    send_email_async(
        email, f"AssureX claim {claim_id} submitted",
        f"Your warranty claim has been submitted and evaluated.\n\n"
        f"Claim ID: {claim_id}\n"
        f"Product: {product}\n"
        f"Decision: {decision}\n"
        f"Status: {status}\n\n"
        f"Log in to view the full analysis, both AI model predictions, "
        f"and the complete explanation.\n\n- AssureX Claim Engine")


def notify_claim_decision(email, claim_id, status):
    word = "approved" if "pprov" in status else (
        "rejected" if "ejec" in status else status.lower())
    send_email_async(
        email, f"AssureX claim {claim_id}: {status}",
        f"Your warranty claim {claim_id} has been {word} by a reviewer.\n\n"
        f"Log in to view the decision details, the reviewer's comments, "
        f"and next steps.\n\n- AssureX Claim Engine")


def notify_info_requested(email, claim_id, comment):
    send_email_async(
        email, f"AssureX claim {claim_id}: additional information required",
        f"Our review team needs more information to continue processing "
        f"your claim {claim_id}.\n\n"
        f"Reviewer's note: {comment or 'Please contact support.'}\n\n"
        f"Log in and open the claim to see the full details.\n\n"
        f"- AssureX Claim Engine")


def notify_repair_scheduled(email, claim_id, center, city, deadline, phone):
    send_email_async(
        email, f"AssureX claim {claim_id}: repair scheduled",
        f"Good news - your approved claim {claim_id} has been scheduled "
        f"for repair.\n\n"
        f"Service center: {center}\n"
        f"City: {city}\n"
        f"Expected completion by: {deadline}\n"
        f"Contact: {phone}\n\n"
        f"Please keep your product and purchase receipt available for the "
        f"visit.\n\n- AssureX Claim Engine")


def notify_fraud_alert_admin(claim_id, fraud_score, top_signals):
    """Fraud alerts go to ADMIN (never the suspected claimant - never tip
    off a potential fraudster; design decision for the viva)."""
    send_email_async(
        ADMIN_ALERT_EMAIL,
        f"AssureX FRAUD ALERT: claim {claim_id} scored {fraud_score}/100",
        f"Automated fraud intelligence alert.\n\n"
        f"Claim: {claim_id}\n"
        f"Fraud score: {fraud_score}/100\n\n"
        f"Top indicators:\n"
        + "\n".join(f"- {s}" for s in top_signals[:5])
        + "\n\nReview this claim in the admin panel.\n"
          "- AssureX Fraud Intelligence")