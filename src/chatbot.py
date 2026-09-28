"""AssureX Help Assistant - AI-powered guidance, NOT decision-making.

CRITICAL COMPLIANCE (SRS 1.10.15): This chatbot NEVER makes, predicts,
or influences claim decisions. It answers usage questions and PRESENTS
stored claim information (the deterministic explanations already computed
by the rule engine, fusion, and reviewers). The AI rephrases delivery;
the CONTENT comes from the evaluation system's stored outputs.

When a user asks 'why did my claim fail', the chatbot fetches their
actual claims from Firestore, includes the STORED explanations as read-
only context, and the AI presents those factors conversationally. No new
reasoning is generated about any claim."""
import json
import os

import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-20b"


def _get_user_claims_context(email, fdb):
    """Fetch the user's recent claims with their STORED explanations."""
    claims = fdb.query("claims", "owner_email", "==", email)
    claims.sort(key=lambda c: c.get("created_at", ""), reverse=True)
    if not claims:
        return "User has no claims yet."

    context_parts = []
    for c in claims[:5]:  # last 5 claims
        ex = c.get("explanation", {})
        r = c.get("rules_outcome", {})
        parts = [
            f"Claim {c['claim_id']}: {c.get('brand','')} {c.get('model','')}",
            f"  Status: {c.get('status','')} | Decision: {c.get('final_decision','')}",
        ]
        if r.get("hard_fails"):
            parts.append(f"  Stored reason (rule engine): {'; '.join(r['hard_fails'][:2])}")
        if r.get("review_flags"):
            parts.append(f"  Stored reason (review flags): {'; '.join(r['review_flags'][:2])}")
        if ex.get("oppose"):
            parts.append(f"  Stored factors against: {'; '.join(ex['oppose'][:2])}")
        context_parts.append("\n".join(parts))

    return "\n\n".join(context_parts)


def _build_system_prompt(claims_context):
    return f"""You are the AssureX Help Assistant. Your job is to help users navigate the AssureX warranty claim application.

CRITICAL RULES (you MUST follow these):
1. You NEVER make, predict, or influence claim decisions. Decisions are made exclusively by the AssureX dual-model evaluation system (Python ML + Teachable Machine) and human reviewers.
2. When asked about a claim's status or outcome, present ONLY the stored information provided in the context below. Do NOT add your own reasoning about why a claim was approved/rejected.
3. If asked "will my claim be approved?" or similar, respond: "Claim decisions are made by our AI evaluation system and human reviewers. I can show you your claim's current status and the stored explanation."
4. Be helpful, concise, and friendly. Use short paragraphs.

APPLICATION GUIDE (use this to answer "how to" questions):

HOW TO ADD A PRODUCT:
1. Go to My Products → Register a Product
2. Three options: pick from the catalog, use Smart Register (scan QR / type name — AI suggests, you verify), or fill the form manually
3. Enter serial number, purchase date, and price from your receipt
4. Warranty is automatically calculated from the category policy (Electronics: 24 months, Home Appliances: 12 months, Power Tools: 18 months)

HOW TO SUBMIT A CLAIM:
1. Go to New Claim → select your product
2. Upload supporting documents (receipt, warranty card, fault evidence)
3. Fill in fault details (type, date, description)
4. Click "Evaluate & Submit" — the system runs both AI models and the rule engine
5. You'll see the result immediately with full explanation

HOW TO CHECK CLAIM STATUS:
1. Go to My Claims → click any claim to see full details
2. The claim page shows: status, decision, explanation factors, repair booking
3. You'll also receive email notifications at every stage

DOCUMENTS NEEDED:
- Electronics: receipt, warranty card, fault evidence
- Home Appliances: receipt, warranty card, product image, fault evidence
- Power Tools: receipt, serial evidence, fault evidence

WHY CLAIMS GO TO MANUAL REVIEW:
- Missing mandatory documents
- Serial number mismatch
- Contradictory dates (e.g., claim date before purchase date)
- Possible duplicate claims
- Low AI model confidence

USER'S RECENT CLAIMS (stored data — present this when asked about their claims):
{claims_context}

Remember: you are a guide. The system decides. You explain what already happened."""


def chat(user_email, message, fdb, history=None):
    """Process a chat message. Returns assistant response text."""
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        return ("I'm currently offline. For help, check the claim page's "
                "explanation section or contact support. Claim decisions "
                "are always made by the evaluation system, not by me.")

    claims_context = _get_user_claims_context(user_email, fdb)
    system_prompt = _build_system_prompt(claims_context)

    messages = [{"role": "system", "content": system_prompt}]
     
    if history:
        for h in history[-8:]:
            if isinstance(h, dict) and h.get("role") and h.get("content"):
                messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": message})

    try:
        r = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": MODEL,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 400,
            },
            timeout=20,
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        return content.strip()
    except Exception as e:
        return (f"I'm having trouble connecting right now. Your claims and "
                f"their explanations are always available on the My Claims "
                f"page. (Technical note: {str(e)[:80]})")