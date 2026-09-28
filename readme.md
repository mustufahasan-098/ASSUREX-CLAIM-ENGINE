🛡️ AssureX Claim Engine
AI-Powered Warranty Claim Validation SystemTECHVIZ 7 World Tech Championship | Category: NextWave AI and MLTeam: TECHVIZ Group — Mustufa (Lead), Ayesha Siddiqui, Aliyan, Asharib Atif

1. Project Overview
1.1 What Is AssureX?
AssureX is an AI-powered, web-based warranty claim validation application that helps manufacturers and service centers evaluate claims accurately and efficiently. Every submitted claim is independently evaluated by two AI models — a Python classification model (RandomForest, 95.1% accuracy) and a Google Teachable Machine image classifier (100% val/test accuracy) — combined with a configurable warranty rule engine, a 7-layer fraud intelligence system, and entity-link fraud-ring detection.

The system produces one of three explainable outcomes for every claim:

✅ Likely Valid — auto-approved with full supporting evidence
⛔ Likely Invalid — rejected with the exact rule violations listed
👤 Manual Review Required — escalated to a human reviewer with the complete evidence chain
1.1.1 Key Performance Metrics
Metric	Value	SRS Requirement
Python model test accuracy	95.1%	≥85% ✅
Teachable Machine val + test accuracy	100%	≥85% ✅
Dual-model prediction speed	0.098s	<5s ✅
SRS functional requirements implemented	50/50	All ✅
SRS non-functional requirements	5/5	All ✅
Automated tests passing	74/74	—
30-claim comparison report	96.7% / 100%, 0 disagreements	≥30 claims ✅
1.2 The Problem We Solve
Traditional warranty claim evaluation requires employees to manually examine purchase details, product age, fault descriptions, repair history, supporting documents, and warranty conditions. This process is slow, error-prone, inconsistent, vulnerable to duplicate and coordinated fraud, and causes delayed approvals that frustrate customers.

1.2.1 How AssureX Solves It
Dual-model verification: two independently trained AI models must agree (or their disagreement triggers human review)
Configurable rules: warranty policies live in JSON files, not code — new exclusions and thresholds are one-file edits
Fraud intelligence: 7 detection layers including perceptual document fingerprinting, velocity analysis, cross-user networks, and price reasonableness
Entity link analysis: claims are not evaluated in isolation — shared-entity clustering reveals coordinated fraud rings
Counterfactual explanations: for every rejected claim, the system computes exactly what would have changed the decision
Full audit trail: every action, prediction, override, and status change is recorded with actor and timestamp
2. Live Demo & Accounts
2.1 Deployed Application
URL: TODO-RENDER-URL (first load may take ~30 seconds — free-tier wake-up)

2.1.1 Demo Accounts
Role	Email	Password	Access
Admin	admin@assurex.com	Admin@123	Analytics, approvals, catalog, entity links, audit
Reviewer	reviewer@assurex.com	Reviewer@123	Claim evaluation queue, overrides
Customer	demo@assurex.com	Demo@123	Products, claims, repair booking
Service Center	service@assurex.com	Service@123	Dedicated service desk, on-behalf filing
Note: Privileged roles (reviewer, service center) require administrator approval after registration — register one to see the workflow, then approve it as admin.

3. How It Works
3.1 Claim Evaluation Pipeline
Every claim runs through twelve stages in under one second:

flowchart TD    A[User submits claim + documents] --> B[Document Intake: SHA-256 + pHash]    B --> C[OCR Extraction + Cross-Verification]    C --> D[Duplicate Detection: invoice / doc hash / serial]    D --> E[Fraud Intelligence: 7 layers, 0-100 score]    E --> F{Rule Engine}    F -->|Contradictions| R[Manual Review]    F -->|Hard-fail rules| I[Likely Invalid]    F -->|Clean| G[Python Model: 3-class probabilities]    G --> H[Claim Summary Card: facts only]    H --> K[Teachable Machine: 3-class probabilities]    K --> L{Fusion Comparison}    L -->|Both agree Valid + confident| V[Likely Valid]    L -->|Disagreement / low confidence| R    V --> M[(Firestore: full evidence chain)]    I --> M    R --> M    M --> N[Email + in-app notifications]
3.1.1 Stage Descriptions
Document intake — every uploaded file is SHA-256 hashed and perceptually fingerprinted (catches re-saved copies)
OCR cross-verification — receipts read by Tesseract; brand, serial, and dates cross-checked against the registered product
Duplicate detection — invoice reuse, document hash reuse, prior claims on the same serial
Fraud intelligence — 7 layers: pHash, duplicates, velocity, behavioral, price, cross-user networks, escalation
Rule engine — contradictions first, then hard-fail rules, then review flags
Python model — RandomForest with full three-class probability output
Claim Summary Card — visual card with facts ONLY (no predictions — SRS req xx), so the second model evaluates independently
Teachable Machine — classifies the card via offline TFLite inference
Fusion comparison — class match, confidence difference, five consistency tiers
Decision — Likely Valid / Likely Invalid / Manual Review with full evidence
Persistence — complete evidence chain stored per claim
Notifications — email + in-app; fraud alerts to admins only
3.2 Reviewer Workflow
flowchart TD    A[Claim enters Review Queue] --> B[Reviewer sees: both models, rules, fraud table, counterfactuals]    B --> C{Decision}    C -->|Approve| D[Approved]    C -->|Reject| E[Rejected]    C -->|Request info| F[Info Required]    D --> G{AI agreed?}    E --> G    G -->|No| H[Override FLAGGED - original AI results preserved]    G -->|Yes| I[Standard]    H --> J[Customer emailed]    I --> J    D --> K[Repair Dispatch: city / category / SLA match]    K --> L[Repair Scheduled + SLA email]    L --> M[Claim Closed]
3.2.1 Fraud Ring Detection
flowchart LR    A[(All claims)] --> B[Entity Extraction: invoices, hashes, serials]    B --> C[Link Building: shared by 2+ claims]    C --> D[Union-Find Clustering]    D --> E{Syndicate cluster?}    E -->|3+ claims, 2+ owners, 2+ entity types| F[Potential Fraud Ring]    E -->|No| G[Normal evaluation]    F --> H[Fraud score 85+, priority review]    F --> I[Admin email alert]    F --> J[Red-glow cluster in d3 graph]
4. Installation
4.1 Prerequisites
Python 3.10 or higher
~2 GB free disk space
A Firebase project (free tier)
Tesseract OCR engine (optional — app degrades gracefully)
Groq API key (optional — Smart Register AI suggestions)
4.1.1 Setup Steps
# 1. Clone the repositorygit clone https://github.com/YOURUSERNAME/assurex.gitcd assurex# 2. Create virtual environmentpython -m venv venvvenv\Scripts\activate          # Windowssource venv/bin/activate      # Linux/Mac# 3. Install dependenciespip install -r requirements.txt# 4. Firebase credentials#    Firebase Console > Project Settings > Service Accounts >#    Generate new private key > save as firebase_service_account.json#    in the project root#    Then: Firestore Database > Create database (production mode)# 5. Optional .env file (create in project root)#    GROQ_API_KEY=gsk_...#    SMTP_EMAIL=your@gmail.com#    SMTP_APP_PASSWORD=yourapppassword#    DEMO_NOTIFY_EMAIL=your@gmail.com# 6. Optional: Tesseract OCR#    Windows: https://github.com/UB-Mannheim/tesseract/wiki# 7. Seed demo datapython -m src.seed_demo# 8. Runpython app.py# -> http://localhost:5000
4.2 Troubleshooting
Problem	Solution
ModuleNotFoundError	(venv) must appear in prompt — re-run activation
Firebase connection error	firebase_service_account.json missing in root
"database (default) does not exist"	Firebase Console > Firestore > Create
OCR not installed	Install Tesseract engine, restart terminal + Flask
Models fail to load	Verify model/python/*.joblib and model/tm/model.tflite exist
5. Usage Guide
5.1 Getting Started
Log in with a demo account (Section 2.1.1) or register a new one
Register a product — manual form, admin catalog, or Smart Register (QR + AI suggestion + your verification)
Warranty tracking starts automatically
5.1.1 Submitting a Claim
New Claim → select your product
Upload documents — every file hashed for duplicate detection
Review the OCR extraction and verification verdict
Fill fault details — covered and excluded faults are visually separated
Click Evaluate & Submit — animated overlay walks the pipeline
5.2 Understanding Results
Decision banner — outcome with consistency tier and confidence difference
Both models — full three-class probability bars
Why this decision — supporting and opposing factors with evidence
Counterfactuals — exactly what would have changed the decision
Repair booking — certified centers matched by city, category, SLA
5.2.1 Running the Evidence Suite
python -m tests.run_tests                              # 31 checkspython test_counterfactual.py                          # 7 checkspython test_entity_links.py                            # 9 checkspython final_system_test.py                            # 24 checkspython test_fraud_attacks.py                           # 12 fraud simulationspython demo_valid_claim.py                             # end-to-end valid claimpython -m reports_generator.generate_comparison_report # 30-claim report
6. Architecture
6.1 System Design
flowchart TB    subgraph BROWSER["Browser"]        UI[Aurora Glass UI - role-tiered views]        CHAT[Help Chatbot]        OVL[Evaluation Overlay]        GRAPH[d3 Entity Graph]    end    subgraph FLASK["Flask Application"]        AUTH[Auth: PBKDF2 + CSRF + RBAC]        ROUTES[30+ routes]    end    subgraph ENGINES["Evaluation Engines"]        RULES[Rule Engine - JSON policies]        PY[RandomForest 95.1%]        CARD[Card Generator]        TM[TM TFLite 100% offline]        FUSION[Fusion + Counterfactuals]        FRAUD[Fraud Intel - 7 layers]        LINKS[Entity Links]        OCR[OCR + Verification]    end    subgraph DATA["Data Layer"]        FS[(Firestore)]        MAIL[SMTP async]    end    BROWSER --> FLASK    ROUTES --> RULES & OCR & FRAUD & LINKS    RULES --> PY --> CARD --> TM    PY & TM --> FUSION    ROUTES --> FS & MAIL
6.1.1 Core Design Principle
The same rule engine that labels the training data evaluates live claims — training and production can never drift. Three train/serve mismatches were found and fixed during testing (price winsorization, threshold calibration, authorized-repair normalization), all documented in the development log.

7. Security & Privacy
7.1 Security Measures
PBKDF2-SHA256 password hashing (240,000 iterations, per-user salt)
5-attempt login lockout
Role-based access control on every route
CSRF protection on all POST forms
Security headers (nosniff, frame-options, referrer-policy, no-store)
Privileged-role registration requires admin approval
7.1.1 AI Compliance (SRS 1.10.15)
No external AI generates or influences claim decisions. Decisions come exclusively from the local Python model, local TFLite model, rule engine, and fusion logic. Groq API is used only for product suggestions (with human verification) and navigation help — declared in AI_USAGE.md.

7.2 Privacy
Entity analysis uses stored claim data only — no EXIF/GPS/device fingerprinting
Fraud alert emails go to administrators only
Service account and API keys are environment-injected, never committed
8. Key Numbers
Metric	Value
Dataset	1,500 claims · 17 scenarios · 70/15/15 stratified · zero leakage
Training images	2,100 (2 variations × 1,050 claims)
Python model	RandomForest · 95.1% test · 3 algorithms compared
TM model	100% val + test · offline TFLite inference
30-claim comparison	Python 96.7% · TM 100% · 0 disagreements
Speed	0.098s dual-model (SRS budget: 5s)
Tests	74 automated checks, all passing
Notifications	6 email event types, background-threaded
9. Repository Structure
assurex/├── app.py                     # Flask application (30+ routes)├── policies/                  # 3 configurable warranty policies (JSON)├── config/                    # settings.yaml, service centers, templates├── src/                       # engines + services├── card_generator/            # Claim Summary Card generator + TM evaluation├── dataset_generator/         # 1,500-claim dataset generator├── reports_generator/         # 30-claim comparison report├── model/python/  model/tm/   # trained models + metadata├── data/                      # CSV splits + stats├── templates/  static/        # pages + Aurora Glass design system├── tests/                     # automated test suites├── reports/                   # generated evidence reports├── documentation/             # report, test cases, limitations├── sample_claims/             # 6-scenario demonstration guide├── database/                  # Firestore schema├── screenshots/               # application screenshots└── README.md  AI_USAGE.md  LICENSE  TEAM_CONTRIBUTIONS.md
10. Links
Resource	URL
Deployed application	TODO
Demonstration video	TODO
Technical blog	TODO
Project report	documentation/
Model comparison report	reports/model_comparison_report.md
11. License
MIT — see LICENSE.

12. Team
TECHVIZ Group — Mustufa (Team Lead, Full-Stack & ML), Ayesha Siddiqui (Documentation), Aliyan (Research & Validation), Asharib Atif (Deployment & QA)

See TEAM_CONTRIBUTIONS.md for the complete contribution record.