"""AssureX Claim Engine - Python classification model training (Step 3).

Trains and compares THREE algorithms (SRS minimum), following proper ML
methodology:
  1. LogisticRegression  (linear baseline)
  2. RandomForest        (bagged trees)
  3. XGBoost             (gradient boosting)

Procedure:
  - loads the stratified splits from Step 1 (train/val/test)
  - builds engineered features via src.preprocessing (shared with live app)
  - 5-fold stratified cross-validation on the training set
  - selects the best model on the VALIDATION set (test stays untouched)
  - final evaluation on the TEST set: accuracy, precision, recall, F1,
    confusion matrix, class-wise report, feature importances
  - saves the pipeline + label encoder + metadata for the live app

Run from the project root:
    python -m src.train_model
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
import sklearn
import xgboost
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix, f1_score)
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, OneHotEncoder, StandardScaler

from .preprocessing import (BOOLEAN_FEATURES, CATEGORICAL_FEATURES,
                            NUMERIC_FEATURES, build_feature_frame)
from .rules import load_policies

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MODEL_DIR = ROOT / "model" / "python"
REPORTS = ROOT / "reports"
RANDOM_STATE = 42
MODEL_VERSION = "PY-1.0"


def load_split(name):
    return pd.read_csv(DATA / f"{name}_claims.csv")


def make_pipeline(estimator):
    """Preprocessing + classifier. Everything is inside ONE pipeline so the
    saved model file is self-contained: imputer, scaler, encoder, classifier."""
    preprocess = ColumnTransformer(
        transformers=[
            ("num", Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ]), NUMERIC_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
            ("bool", "passthrough", BOOLEAN_FEATURES),
        ],
        remainder="drop",
    )
    return Pipeline([("preprocess", preprocess), ("clf", estimator)])


def main():
    policies = load_policies()
    train, val, test = load_split("train"), load_split("val"), load_split("test")
    print(f"Loaded splits: train={len(train)}  val={len(val)}  test={len(test)}")

    le = LabelEncoder()
    y_train = le.fit_transform(train["label"])
    y_val = le.transform(val["label"])
    y_test = le.transform(test["label"])
    print(f"Label order: {list(le.classes_)}")

    X_train = build_feature_frame(train.to_dict("records"), policies)
    X_val = build_feature_frame(val.to_dict("records"), policies)
    X_test = build_feature_frame(test.to_dict("records"), policies)

    estimators = {
        "LogisticRegression": LogisticRegression(max_iter=3000,
                                                 random_state=RANDOM_STATE),
        "RandomForest": RandomForestClassifier(n_estimators=400, min_samples_leaf=2,
                                               random_state=RANDOM_STATE, n_jobs=-1),
        "XGBoost": xgboost.XGBClassifier(n_estimators=300, max_depth=6,
                                         learning_rate=0.1, subsample=0.9,
                                         colsample_bytree=0.9,
                                         eval_metric="mlogloss",
                                         random_state=RANDOM_STATE),
    }

    print("\n--- 5-fold cross-validation on TRAIN + validation evaluation ---")
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    fitted, results = {}, []
    for name, est in estimators.items():
        pipe = make_pipeline(est)
        cv = cross_val_score(pipe, X_train, y_train, cv=skf,
                             scoring="accuracy", n_jobs=-1)
        pipe.fit(X_train, y_train)
        fitted[name] = pipe
        val_pred = pipe.predict(X_val)
        r = {"algorithm": name,
             "cv_accuracy_mean": round(float(cv.mean()), 4),
             "cv_accuracy_std": round(float(cv.std()), 4),
             "val_accuracy": round(float(accuracy_score(y_val, val_pred)), 4),
             "val_f1_macro": round(float(f1_score(y_val, val_pred, average="macro")), 4)}
        results.append(r)
        print(f"{name:18s} CV acc {r['cv_accuracy_mean']:.4f} +/- {r['cv_accuracy_std']:.4f}"
              f"   VAL acc {r['val_accuracy']:.4f}  f1 {r['val_f1_macro']:.4f}")

    best = max(results, key=lambda r: (r["val_accuracy"], r["val_f1_macro"]))
    best_name = best["algorithm"]
    print(f"\nSelected model: {best_name} (best validation performance)")

    final = fitted[best_name]
    test_pred = final.predict(X_test)
    test_proba = final.predict_proba(X_test)
    test_acc = accuracy_score(y_test, test_pred)
    test_f1 = f1_score(y_test, test_pred, average="macro")
    cm = confusion_matrix(y_test, test_pred)

    lines = []
    lines.append("ASSUREX - PYTHON CLASSIFICATION MODEL REPORT")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"Model version: {MODEL_VERSION}  |  Selected: {best_name}")
    lines.append(f"sklearn {sklearn.__version__}  |  xgboost {xgboost.__version__}")
    lines.append("")
    lines.append("--- ALGORITHM COMPARISON (CV on train, selection on val) ---")
    lines.append(f"{'Algorithm':18s}{'CV mean':>10s}{'CV std':>10s}"
                 f"{'Val acc':>10s}{'Val F1':>10s}")
    for r in results:
        lines.append(f"{r['algorithm']:18s}{r['cv_accuracy_mean']:>10.4f}"
                     f"{r['cv_accuracy_std']:>10.4f}{r['val_accuracy']:>10.4f}"
                     f"{r['val_f1_macro']:>10.4f}")
    lines.append("")
    lines.append("--- FINAL TEST SET EVALUATION (never used for training/selection) ---")
    lines.append(f"Accuracy: {test_acc:.4f}   F1 (macro): {test_f1:.4f}")
    lines.append(f"SRS requirement: >= 0.85 -> "
                 + ("PASS" if test_acc >= 0.85 else "FAIL"))
    lines.append("")
    lines.append("Class-wise report:")
    lines.append(classification_report(y_test, test_pred,
                                       target_names=le.classes_, digits=4))
    lines.append("Confusion matrix (rows = actual, cols = predicted):")
    lines.append(f"{'':>15}" + "".join(f"{c[:14]:>15}" for c in le.classes_))
    for i, cls in enumerate(le.classes_):
        lines.append(f"{cls[:15]:>15}" + "".join(f"{cm[i, j]:>15}"
                                                 for j in range(len(le.classes_))))

     
    clf = final.named_steps["clf"]
    if hasattr(clf, "feature_importances_"):
        names = final.named_steps["preprocess"].get_feature_names_out()
        imp = sorted(zip(names, clf.feature_importances_),
                     key=lambda t: -t[1])[:15]
        lines.append("")
        lines.append("Top 15 feature importances:")
        for n, v in imp:
            lines.append(f"  {n:40s} {v:.4f}")

     
    lines.append("")
    lines.append("Sample test predictions (first 5):")
    for i in range(5):
        probs = ", ".join(f"{c}={p:.3f}" for c, p in zip(le.classes_, test_proba[i]))
        lines.append(f"  {test['claim_id'].iloc[i]}  actual={le.classes_[y_test[i]]}"
                     f"  pred={le.classes_[test_pred[i]]}  [{probs}]")

    report_text = "\n".join(lines)
    print("\n" + report_text)

     
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    joblib.dump(final, MODEL_DIR / "model.joblib")
    joblib.dump(le, MODEL_DIR / "label_encoder.joblib")
    (MODEL_DIR / "model_metadata.json").write_text(json.dumps({
        "model_version": MODEL_VERSION,
        "algorithm": best_name,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "class_order": list(le.classes_),
        "training_rows": len(train),
        "validation_rows": len(val),
        "test_rows": len(test),
        "cv_results": results,
        "test_accuracy": round(float(test_acc), 4),
        "test_f1_macro": round(float(test_f1), 4),
        "numeric_features": NUMERIC_FEATURES,
        "boolean_features": BOOLEAN_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "excluded_columns": ["claim_id", "user_id", "serial_number",
                             "invoice_number", "raw dates (replaced by derived features)"],
    }, indent=2))
    (REPORTS / "python_model_report.txt").write_text(report_text)

    print(f"\nSaved: model/python/model.joblib, label_encoder.joblib, model_metadata.json")
    print(f"Saved: reports/python_model_report.txt")
    print("\nSTEP 3 COMPLETE [OK]")


if __name__ == "__main__":
    main()