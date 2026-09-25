# AssureX - Model Prediction & Confidence Comparison Report

**Generated:** 2026-09-25T01:20:53+00:00  
**Claims:** 30 unseen test claims (10 per class, stratified, seed 2026 - never used in training)  
**Models:** Python RandomForest (PY-1.0) · Teachable Machine (TM-1.0, TFLite, local inference)

## 1. Overall summary

| Metric | Value |
|---|---|
| Python model accuracy (30 claims) | 29/30 (96.7%) |
| Teachable Machine accuracy (30 claims) | 30/30 (100.0%) |
| Both models correct | 29/30 (96.7%) |
| Fusion decision consistent with actual class | 30/30 (100.0%) |
| Model agreement rate | 29/30 |

**Consistency distribution:** Acceptable Match: 8, Model Disagreement: 1, Strong Match: 20, Weak Match: 1

**Final decisions:** Likely Invalid: 10, Likely Valid: 9, Manual Review Required: 11

## 2. Full comparison table (SRS deliverable 6 format)

| Claim | Actual | Python pred | Py conf (V/I/R) | TM pred | TM conf (V/I/R) | Match | Δconf | Consistency | Final decision |
|---|---|---|---|---|---|---|---|---|---|
| CLM-001300 | Valid | Valid | 0.89/0.06/0.05 | Valid | 1.00/0.00/0.00 | ✓ | 0.110 | Strong Match | Likely Valid |
| CLM-001455 | Valid | Valid | 0.94/0.02/0.04 | Valid | 1.00/0.00/0.00 | ✓ | 0.064 | Strong Match | Likely Valid |
| CLM-001486 | Valid | Valid | 0.63/0.11/0.26 | Valid | 1.00/0.00/0.00 | ✓ | 0.368 | Weak Match | Manual Review Required |
| CLM-001453 | Valid | Valid | 0.77/0.08/0.14 | Valid | 1.00/0.00/0.00 | ✓ | 0.228 | Acceptable Match | Likely Valid |
| CLM-001417 | Valid | Valid | 0.95/0.02/0.02 | Valid | 1.00/0.00/0.00 | ✓ | 0.047 | Strong Match | Likely Valid |
| CLM-001494 | Valid | Valid | 0.92/0.04/0.04 | Valid | 1.00/0.00/0.00 | ✓ | 0.077 | Strong Match | Likely Valid |
| CLM-001313 | Valid | Valid | 0.70/0.10/0.20 | Valid | 1.00/0.00/0.00 | ✓ | 0.303 | Acceptable Match | Likely Valid |
| CLM-001473 | Valid | Valid | 0.81/0.05/0.14 | Valid | 1.00/0.00/0.00 | ✓ | 0.195 | Acceptable Match | Likely Valid |
| CLM-001298 | Valid | Valid | 0.73/0.08/0.19 | Valid | 1.00/0.00/0.00 | ✓ | 0.266 | Acceptable Match | Likely Valid |
| CLM-001310 | Valid | Valid | 0.98/0.02/0.01 | Valid | 1.00/0.00/0.00 | ✓ | 0.024 | Strong Match | Likely Valid |
| CLM-001363 | Invalid | Invalid | 0.16/0.77/0.07 | Invalid | 0.00/1.00/0.00 | ✓ | 0.228 | Acceptable Match | Likely Invalid |
| CLM-001301 | Invalid | Invalid | 0.02/0.95/0.02 | Invalid | 0.00/1.00/0.00 | ✓ | 0.045 | Strong Match | Likely Invalid |
| CLM-001367 | Invalid | Invalid | 0.00/1.00/0.00 | Invalid | 0.00/1.00/0.00 | ✓ | 0.003 | Strong Match | Likely Invalid |
| CLM-001439 | Invalid | Invalid | 0.04/0.96/0.00 | Invalid | 0.00/1.00/0.00 | ✓ | 0.043 | Strong Match | Likely Invalid |
| CLM-001478 | Invalid | Invalid | 0.02/0.95/0.03 | Invalid | 0.00/1.00/0.00 | ✓ | 0.052 | Strong Match | Likely Invalid |
| CLM-001433 | Invalid | Invalid | 0.03/0.95/0.02 | Invalid | 0.00/1.00/0.00 | ✓ | 0.046 | Strong Match | Likely Invalid |
| CLM-001284 | Invalid | Invalid | 0.00/1.00/0.00 | Invalid | 0.00/1.00/0.00 | ✓ | 0.002 | Strong Match | Likely Invalid |
| CLM-001402 | Invalid | Invalid | 0.03/0.93/0.03 | Invalid | 0.00/1.00/0.00 | ✓ | 0.067 | Strong Match | Likely Invalid |
| CLM-001385 | Invalid | Invalid | 0.01/0.99/0.00 | Invalid | 0.00/1.00/0.00 | ✓ | 0.007 | Strong Match | Likely Invalid |
| CLM-001293 | Invalid | Invalid | 0.04/0.90/0.05 | Invalid | 0.00/1.00/0.00 | ✓ | 0.095 | Strong Match | Likely Invalid |
| CLM-001369 | Manual Review | Manual Review | 0.08/0.01/0.91 | Manual Review | 0.00/0.00/1.00 | ✓ | 0.089 | Strong Match | Manual Review Required |
| CLM-001273 | Manual Review | Manual Review | 0.12/0.01/0.87 | Manual Review | 0.00/0.00/1.00 | ✓ | 0.132 | Strong Match | Manual Review Required |
| CLM-001307 | Manual Review | Manual Review | 0.13/0.02/0.86 | Manual Review | 0.00/0.00/1.00 | ✓ | 0.144 | Strong Match | Manual Review Required |
| CLM-001374 | Manual Review | Manual Review | 0.05/0.01/0.95 | Manual Review | 0.00/0.00/1.00 | ✓ | 0.054 | Strong Match | Manual Review Required |
| CLM-001357 | Manual Review | Valid | 0.56/0.03/0.41 | Manual Review | 0.00/0.00/1.00 | ✗ | 0.440 | Model Disagreement | Manual Review Required |
| CLM-001479 | Manual Review | Manual Review | 0.01/0.00/0.99 | Manual Review | 0.00/0.00/1.00 | ✓ | 0.013 | Strong Match | Manual Review Required |
| CLM-001477 | Manual Review | Manual Review | 0.21/0.05/0.75 | Manual Review | 0.00/0.00/1.00 | ✓ | 0.253 | Acceptable Match | Manual Review Required |
| CLM-001354 | Manual Review | Manual Review | 0.26/0.02/0.73 | Manual Review | 0.00/0.00/1.00 | ✓ | 0.275 | Acceptable Match | Manual Review Required |
| CLM-001276 | Manual Review | Manual Review | 0.12/0.02/0.86 | Manual Review | 0.00/0.00/1.00 | ✓ | 0.138 | Strong Match | Manual Review Required |
| CLM-001498 | Manual Review | Manual Review | 0.15/0.02/0.83 | Manual Review | 0.00/0.00/1.00 | ✓ | 0.172 | Acceptable Match | Manual Review Required |

## 3. Per-claim details (rules, evidence, disagreements)

### CLM-001300 — actual: Valid Claim

- **Claim Summary Card:** `CLM-001300_v1.png`
- **Python model:** Valid Claim — V/I/R = 0.890/0.059/0.051
- **Teachable Machine:** Valid Claim — V/I/R = 1.000/0.000/0.000
- **Consistency:** Strong Match (top-class confidence difference 0.110)
- **Rule engine:** Valid Claim
- **Missing documents:** none
- **Duplicate indicators:** prior_claims=0
- **Final decision:** **Likely Valid**

### CLM-001455 — actual: Valid Claim

- **Claim Summary Card:** `CLM-001455_v1.png`
- **Python model:** Valid Claim — V/I/R = 0.936/0.021/0.043
- **Teachable Machine:** Valid Claim — V/I/R = 1.000/0.000/0.000
- **Consistency:** Strong Match (top-class confidence difference 0.064)
- **Rule engine:** Valid Claim
- **Missing documents:** none
- **Duplicate indicators:** prior_claims=0
- **Final decision:** **Likely Valid**

### CLM-001486 — actual: Valid Claim

- **Claim Summary Card:** `CLM-001486_v1.png`
- **Python model:** Valid Claim — V/I/R = 0.632/0.106/0.262
- **Teachable Machine:** Valid Claim — V/I/R = 1.000/0.000/0.000
- **Consistency:** Weak Match (top-class confidence difference 0.368)
- **Rule engine:** Valid Claim
- **Missing documents:** none
- **Duplicate indicators:** prior_claims=0
- **Final decision:** **Manual Review Required**

### CLM-001453 — actual: Valid Claim

- **Claim Summary Card:** `CLM-001453_v1.png`
- **Python model:** Valid Claim — V/I/R = 0.772/0.084/0.143
- **Teachable Machine:** Valid Claim — V/I/R = 1.000/0.000/0.000
- **Consistency:** Acceptable Match (top-class confidence difference 0.228)
- **Rule engine:** Valid Claim
- **Missing documents:** none
- **Duplicate indicators:** prior_claims=0
- **Final decision:** **Likely Valid**

### CLM-001417 — actual: Valid Claim

- **Claim Summary Card:** `CLM-001417_v1.png`
- **Python model:** Valid Claim — V/I/R = 0.953/0.023/0.024
- **Teachable Machine:** Valid Claim — V/I/R = 1.000/0.000/0.000
- **Consistency:** Strong Match (top-class confidence difference 0.047)
- **Rule engine:** Valid Claim
- **Missing documents:** none
- **Duplicate indicators:** prior_claims=0
- **Final decision:** **Likely Valid**

### CLM-001494 — actual: Valid Claim

- **Claim Summary Card:** `CLM-001494_v1.png`
- **Python model:** Valid Claim — V/I/R = 0.923/0.035/0.042
- **Teachable Machine:** Valid Claim — V/I/R = 1.000/0.000/0.000
- **Consistency:** Strong Match (top-class confidence difference 0.077)
- **Rule engine:** Valid Claim
- **Missing documents:** none
- **Duplicate indicators:** prior_claims=0
- **Final decision:** **Likely Valid**

### CLM-001313 — actual: Valid Claim

- **Claim Summary Card:** `CLM-001313_v1.png`
- **Python model:** Valid Claim — V/I/R = 0.697/0.103/0.199
- **Teachable Machine:** Valid Claim — V/I/R = 1.000/0.000/0.000
- **Consistency:** Acceptable Match (top-class confidence difference 0.303)
- **Rule engine:** Valid Claim
- **Missing documents:** none
- **Duplicate indicators:** prior_claims=0
- **Final decision:** **Likely Valid**

### CLM-001473 — actual: Valid Claim

- **Claim Summary Card:** `CLM-001473_v1.png`
- **Python model:** Valid Claim — V/I/R = 0.805/0.053/0.141
- **Teachable Machine:** Valid Claim — V/I/R = 1.000/0.000/0.000
- **Consistency:** Acceptable Match (top-class confidence difference 0.195)
- **Rule engine:** Valid Claim
- **Missing documents:** none
- **Duplicate indicators:** prior_claims=0
- **Final decision:** **Likely Valid**

### CLM-001298 — actual: Valid Claim

- **Claim Summary Card:** `CLM-001298_v1.png`
- **Python model:** Valid Claim — V/I/R = 0.734/0.076/0.190
- **Teachable Machine:** Valid Claim — V/I/R = 1.000/0.000/0.000
- **Consistency:** Acceptable Match (top-class confidence difference 0.266)
- **Rule engine:** Valid Claim
- **Missing documents:** none
- **Duplicate indicators:** prior_claims=0
- **Final decision:** **Likely Valid**

### CLM-001310 — actual: Valid Claim

- **Claim Summary Card:** `CLM-001310_v1.png`
- **Python model:** Valid Claim — V/I/R = 0.976/0.019/0.005
- **Teachable Machine:** Valid Claim — V/I/R = 1.000/0.000/0.000
- **Consistency:** Strong Match (top-class confidence difference 0.024)
- **Rule engine:** Valid Claim
- **Missing documents:** none
- **Duplicate indicators:** prior_claims=0
- **Final decision:** **Likely Valid**

### CLM-001363 — actual: Invalid Claim

- **Claim Summary Card:** `CLM-001363_v1.png`
- **Python model:** Invalid Claim — V/I/R = 0.155/0.772/0.073
- **Teachable Machine:** Invalid Claim — V/I/R = 0.000/1.000/0.000
- **Consistency:** Acceptable Match (top-class confidence difference 0.228)
- **Rule engine:** Invalid Claim — hard fails: Fault reported 51 days after occurrence (limit: 30)
- **Missing documents:** none
- **Duplicate indicators:** prior_claims=0
- **Final decision:** **Likely Invalid**

### CLM-001301 — actual: Invalid Claim

- **Claim Summary Card:** `CLM-001301_v1.png`
- **Python model:** Invalid Claim — V/I/R = 0.024/0.955/0.021
- **Teachable Machine:** Invalid Claim — V/I/R = 0.000/1.000/0.000
- **Consistency:** Strong Match (top-class confidence difference 0.045)
- **Rule engine:** Invalid Claim — hard fails: Warranty expired before the fault date
- **Missing documents:** none
- **Duplicate indicators:** prior_claims=0
- **Final decision:** **Likely Invalid**

### CLM-001367 — actual: Invalid Claim

- **Claim Summary Card:** `CLM-001367_v1.png`
- **Python model:** Invalid Claim — V/I/R = 0.001/0.998/0.002
- **Teachable Machine:** Invalid Claim — V/I/R = 0.000/1.000/0.000
- **Consistency:** Strong Match (top-class confidence difference 0.003)
- **Rule engine:** Invalid Claim — hard fails: Fault type 'physical_damage' is excluded by the Home Appliances policy
- **Missing documents:** none
- **Duplicate indicators:** prior_claims=0
- **Final decision:** **Likely Invalid**

### CLM-001439 — actual: Invalid Claim

- **Claim Summary Card:** `CLM-001439_v1.png`
- **Python model:** Invalid Claim — V/I/R = 0.038/0.957/0.004
- **Teachable Machine:** Invalid Claim — V/I/R = 0.000/1.000/0.000
- **Consistency:** Strong Match (top-class confidence difference 0.043)
- **Rule engine:** Invalid Claim — hard fails: Warranty expired before the fault date
- **Missing documents:** none
- **Duplicate indicators:** prior_claims=0
- **Final decision:** **Likely Invalid**

### CLM-001478 — actual: Invalid Claim

- **Claim Summary Card:** `CLM-001478_v1.png`
- **Python model:** Invalid Claim — V/I/R = 0.025/0.948/0.027
- **Teachable Machine:** Invalid Claim — V/I/R = 0.000/1.000/0.000
- **Consistency:** Strong Match (top-class confidence difference 0.052)
- **Rule engine:** Invalid Claim — hard fails: Warranty expired before the fault date
- **Missing documents:** none
- **Duplicate indicators:** prior_claims=0
- **Final decision:** **Likely Invalid**

### CLM-001433 — actual: Invalid Claim

- **Claim Summary Card:** `CLM-001433_v1.png`
- **Python model:** Invalid Claim — V/I/R = 0.026/0.954/0.020
- **Teachable Machine:** Invalid Claim — V/I/R = 0.000/1.000/0.000
- **Consistency:** Strong Match (top-class confidence difference 0.046)
- **Rule engine:** Invalid Claim — hard fails: Warranty expired before the fault date
- **Missing documents:** none
- **Duplicate indicators:** prior_claims=0
- **Final decision:** **Likely Invalid**

### CLM-001284 — actual: Invalid Claim

- **Claim Summary Card:** `CLM-001284_v1.png`
- **Python model:** Invalid Claim — V/I/R = 0.002/0.998/0.000
- **Teachable Machine:** Invalid Claim — V/I/R = 0.000/1.000/0.000
- **Consistency:** Strong Match (top-class confidence difference 0.002)
- **Rule engine:** Invalid Claim — hard fails: Fault type 'physical_damage' is excluded by the Power Tools policy
- **Missing documents:** none
- **Duplicate indicators:** prior_claims=0
- **Final decision:** **Likely Invalid**

### CLM-001402 — actual: Invalid Claim

- **Claim Summary Card:** `CLM-001402_v1.png`
- **Python model:** Invalid Claim — V/I/R = 0.033/0.933/0.034
- **Teachable Machine:** Invalid Claim — V/I/R = 0.000/1.000/0.000
- **Consistency:** Strong Match (top-class confidence difference 0.067)
- **Rule engine:** Invalid Claim — hard fails: Warranty expired before the fault date
- **Missing documents:** none
- **Duplicate indicators:** prior_claims=0
- **Final decision:** **Likely Invalid**

### CLM-001385 — actual: Invalid Claim

- **Claim Summary Card:** `CLM-001385_v1.png`
- **Python model:** Invalid Claim — V/I/R = 0.006/0.993/0.002
- **Teachable Machine:** Invalid Claim — V/I/R = 0.000/1.000/0.000
- **Consistency:** Strong Match (top-class confidence difference 0.007)
- **Rule engine:** Invalid Claim — hard fails: Fault type 'unauthorized_modification' is excluded by the Electronics policy
- **Missing documents:** none
- **Duplicate indicators:** prior_claims=0
- **Final decision:** **Likely Invalid**

### CLM-001293 — actual: Invalid Claim

- **Claim Summary Card:** `CLM-001293_v1.png`
- **Python model:** Invalid Claim — V/I/R = 0.041/0.905/0.054
- **Teachable Machine:** Invalid Claim — V/I/R = 0.000/1.000/0.000
- **Consistency:** Strong Match (top-class confidence difference 0.095)
- **Rule engine:** Invalid Claim — hard fails: Warranty expired before the fault date
- **Missing documents:** none
- **Duplicate indicators:** prior_claims=0
- **Final decision:** **Likely Invalid**

### CLM-001369 — actual: Manual Review

- **Claim Summary Card:** `CLM-001369_v1.png`
- **Python model:** Manual Review — V/I/R = 0.082/0.007/0.911
- **Teachable Machine:** Manual Review — V/I/R = 0.000/0.000/1.000
- **Consistency:** Strong Match (top-class confidence difference 0.089)
- **Rule engine:** Manual Review — review flags: Serial number does not match purchase records
- **Missing documents:** none
- **Duplicate indicators:** prior_claims=0
- **Final decision:** **Manual Review Required**

### CLM-001273 — actual: Manual Review

- **Claim Summary Card:** `CLM-001273_v1.png`
- **Python model:** Manual Review — V/I/R = 0.124/0.009/0.868
- **Teachable Machine:** Manual Review — V/I/R = 0.000/0.000/1.000
- **Consistency:** Strong Match (top-class confidence difference 0.132)
- **Rule engine:** Manual Review — review flags: Serial number does not match purchase records
- **Missing documents:** none
- **Duplicate indicators:** prior_claims=0
- **Final decision:** **Manual Review Required**

### CLM-001307 — actual: Manual Review

- **Claim Summary Card:** `CLM-001307_v1.png`
- **Python model:** Manual Review — V/I/R = 0.126/0.018/0.856
- **Teachable Machine:** Manual Review — V/I/R = 0.000/0.000/1.000
- **Consistency:** Strong Match (top-class confidence difference 0.144)
- **Rule engine:** Manual Review — review flags: Possible duplicate claim detected
- **Missing documents:** none
- **Duplicate indicators:** prior_claims=1
- **Final decision:** **Manual Review Required**

### CLM-001374 — actual: Manual Review

- **Claim Summary Card:** `CLM-001374_v1.png`
- **Python model:** Manual Review — V/I/R = 0.049/0.005/0.946
- **Teachable Machine:** Manual Review — V/I/R = 0.000/0.000/1.000
- **Consistency:** Strong Match (top-class confidence difference 0.054)
- **Rule engine:** Manual Review — review flags: Missing mandatory documents: receipt
- **Missing documents:** receipt
- **Duplicate indicators:** prior_claims=0
- **Final decision:** **Manual Review Required**

### CLM-001357 — actual: Manual Review

- **Claim Summary Card:** `CLM-001357_v1.png`
- **Python model:** Valid Claim — V/I/R = 0.560/0.029/0.411
- **Teachable Machine:** Manual Review — V/I/R = 0.000/0.000/1.000
- **Consistency:** Model Disagreement (top-class confidence difference 0.440)
- **Rule engine:** Manual Review — contradictions: Fault date is after claim submission date
- **Missing documents:** none
- **Duplicate indicators:** prior_claims=0
- **Final decision:** **Manual Review Required**

**Explanation of disagreement:** the Python model classified the structured claim data as 'Valid Claim' while the Teachable Machine model classified the visual Claim Summary Card as 'Manual Review'. Per fusion policy, disagreeing claims are never auto-decided - they are routed to manual review with the full evidence chain.

### CLM-001479 — actual: Manual Review

- **Claim Summary Card:** `CLM-001479_v1.png`
- **Python model:** Manual Review — V/I/R = 0.011/0.002/0.987
- **Teachable Machine:** Manual Review — V/I/R = 0.000/0.000/1.000
- **Consistency:** Strong Match (top-class confidence difference 0.013)
- **Rule engine:** Manual Review — review flags: Missing mandatory documents: receipt, warranty_card
- **Missing documents:** receipt, warranty_card
- **Duplicate indicators:** prior_claims=0
- **Final decision:** **Manual Review Required**

### CLM-001477 — actual: Manual Review

- **Claim Summary Card:** `CLM-001477_v1.png`
- **Python model:** Manual Review — V/I/R = 0.207/0.046/0.747
- **Teachable Machine:** Manual Review — V/I/R = 0.000/0.000/1.000
- **Consistency:** Acceptable Match (top-class confidence difference 0.253)
- **Rule engine:** Manual Review — review flags: Fault within early-life window - possible dead-on-arrival
- **Missing documents:** none
- **Duplicate indicators:** prior_claims=0
- **Final decision:** **Manual Review Required**

### CLM-001354 — actual: Manual Review

- **Claim Summary Card:** `CLM-001354_v1.png`
- **Python model:** Manual Review — V/I/R = 0.259/0.015/0.725
- **Teachable Machine:** Manual Review — V/I/R = 0.000/0.000/1.000
- **Consistency:** Acceptable Match (top-class confidence difference 0.275)
- **Rule engine:** Manual Review — review flags: Fault within early-life window - possible dead-on-arrival
- **Missing documents:** none
- **Duplicate indicators:** prior_claims=0
- **Final decision:** **Manual Review Required**

### CLM-001276 — actual: Manual Review

- **Claim Summary Card:** `CLM-001276_v1.png`
- **Python model:** Manual Review — V/I/R = 0.119/0.019/0.862
- **Teachable Machine:** Manual Review — V/I/R = 0.000/0.000/1.000
- **Consistency:** Strong Match (top-class confidence difference 0.138)
- **Rule engine:** Manual Review — review flags: Serial number does not match purchase records
- **Missing documents:** none
- **Duplicate indicators:** prior_claims=0
- **Final decision:** **Manual Review Required**

### CLM-001498 — actual: Manual Review

- **Claim Summary Card:** `CLM-001498_v1.png`
- **Python model:** Manual Review — V/I/R = 0.154/0.018/0.828
- **Teachable Machine:** Manual Review — V/I/R = 0.000/0.000/1.000
- **Consistency:** Acceptable Match (top-class confidence difference 0.172)
- **Rule engine:** Manual Review — review flags: Excessive repair history - replacement decision needed
- **Missing documents:** none
- **Duplicate indicators:** prior_claims=0
- **Final decision:** **Manual Review Required**

## 4. Methodology

- Claims sampled from the untouched test split (225 claims, never trained on in CSV or image form)
- Each claim evaluated by the full production stack: rule engine → Python model → Claim Summary Card → Teachable Machine → comparison → fusion decision
- Live duplicate detection (invoice/serial/doc-hash) is application-runtime behaviour and is not applicable to offline dataset claims; the prior-claim indicator from the dataset is reported instead
- Reproducible: fixed sampling seed (2026)

## 5. Conclusion

Both models exceed the 85% SRS accuracy requirement on this sample (96.7% Python, 100.0% Teachable Machine). The fusion engine combined their outputs with rule validation to produce 9 likely-valid, 10 likely-invalid, and 11 manual-review decisions, with every uncertain case routed to human review as designed.

- 'Fusion decision consistent' means: the final decision matched the actual class, OR the claim was conservatively routed to Manual Review (never an incorrect auto-decision)