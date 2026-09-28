AssureX Firestore Database Design
Collections
users/{email}
Field	Type	Description
name	string	Full name
email	string	User ID (document key)
role	string	customer / service_center / reviewer / admin
status	string	active / pending / rejected (privileged roles start pending)
password	string	PBKDF2-SHA256 hash (salt$hash)
photo	string	Profile photo filename (optional)
failed_attempts	number	Login lockout counter (locks at 5)
created_at	string	ISO timestamp
products/{product_id}
Field	Type	Description
product_id	string	PRD-XXXXXX
owner_email	string	Owning user
name, brand, model	string	Product identity
product_category	string	Electronics / Home Appliances / Power Tools
serial_number	string	Unique serial
purchase_date	string	ISO date
purchase_price	number	
warranty_months, extended_months	number	From category policy (extended clamped to policy max)
registered_via	string	manual / catalog_template / smart_register
claims/{claim_id}
Full evidence chain per claim:

Field	Type	Description
claim_id	string	CLM-AXXXXX
owner_email, user_id	string	Owner + submitter (differ for service-desk filings)
product fields	various	Category, brand, model, serial, dates, price
documents	array	{type, filename, sha256, size}
doc_hashes, doc_phashes	array	SHA-256 + perceptual fingerprints
rules_outcome	map	Rule engine: label, contradictions, hard_fails, review_flags
python_pred, python_probs	string, map	Prediction + 3-class probabilities
tm_pred, tm_probs	string, map	Same for Teachable Machine
conf_diff, consistency	number, string	Comparison metrics
fraud	map	7-layer score, signals, escalation
duplicates	map	Invoice/doc reuse, prior claims, syndicate cluster
final_decision	string	Likely Valid / Likely Invalid / Manual Review Required
explanation	map	Support/oppose factors
derived_features	map	Pre-processing snapshot
model_versions	map	Python + TM versions used
timeline	array	Every status change with actor + timestamp
status	string	Lifecycle state
notifications/{auto}
Field	Type
user_email, claim_id, message, read, ts	
audit/{auto}
Every action: user_registered, product_registered, claim_submitted, reviewer_decision, document_removed, chatbot_query, user_approved... {action, actor, details, ts}

counters/claims
Sequential claim-ID generator.