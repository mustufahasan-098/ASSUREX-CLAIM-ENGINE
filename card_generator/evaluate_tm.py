"""AssureX Claim Engine - Teachable Machine evaluation script (Step 2).

Evaluates the exported TFLite model on the validation and test Claim Summary
Cards (which were NEVER used for TM training) and reports accuracy,
per-class recall and the confusion matrix against the 85% SRS requirement.

Prerequisites:
  1. Train the model at https://teachablemachine.withgoogle.com using ONLY
     the images in data/cards/train/
  2. Export as TensorFlow Lite, unzip, and place the files at:
        model/tm/model.tflite
        model/tm/labels.txt

Run from the project root:
    python -m card_generator.evaluate_tm
"""
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image

from src.tm_inference import TMModel

ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = ROOT / "model" / "tm" / "model.tflite"
LABELS_PATH = ROOT / "model" / "tm" / "labels.txt"
CARDS = ROOT / "data" / "cards"
CLASS_ORDER = ["Valid Claim", "Invalid Claim", "Manual Review"]


def collect(split):
    items = []
    for cls_dir in sorted((CARDS / split).iterdir()):
        if cls_dir.is_dir():
            for f in sorted(cls_dir.iterdir()):
                if f.suffix.lower() in (".png", ".jpg", ".jpeg"):
                    items.append((f, cls_dir.name))
    return items


def evaluate(model, items):
    matrix = defaultdict(Counter)
    correct = 0
    for path, actual in items:
        with Image.open(path) as im:
            probs = model.predict(im)
        pred = max(probs, key=probs.get)
        matrix[actual][pred] += 1
        if pred == actual:
            correct += 1
    return correct / len(items), matrix


def print_matrix(split, acc, matrix):
    print(f"\n{split.upper()} SET - confusion matrix (rows: actual, cols: predicted)")
    print(f"{'':>14}" + "".join(f"{c[:13]:>15}" for c in CLASS_ORDER))
    for a in CLASS_ORDER:
        print(f"{a[:14]:>14}" + "".join(f"{matrix[a].get(p, 0):>15}"
                                        for p in CLASS_ORDER))
    verdict = "PASS (>= 85% required)" if acc >= 0.85 \
        else "FAIL (< 85%) - retrain/re-export"
    print(f"Accuracy: {acc:.1%}  ->  {verdict}")
    for a in CLASS_ORDER:
        total = sum(matrix[a].values())
        if total:
            print(f"  recall {a}: {matrix[a].get(a, 0) / total:.1%}")


def main():
    if not MODEL_PATH.exists() or not LABELS_PATH.exists():
        raise SystemExit("model/tm/model.tflite or labels.txt not found.\n"
                         "Train the Teachable Machine model first, export as "
                         "TensorFlow Lite, then copy model.tflite and labels.txt "
                         "into model/tm/.")
    model = TMModel(MODEL_PATH, LABELS_PATH)
    print(f"Labels loaded: {model.labels}")

    # calibrate input normalisation on labelled TRAIN cards (never val/test)
    train = collect("train")
    sample = random.Random(42).sample(train, min(40, len(train)))
    opened = []
    for p, lbl in sample:
        with Image.open(p) as im:
            opened.append((im.copy(), lbl))
    mode, correct, n = model.calibrate(opened)
    print(f"Input normalisation calibrated: '{mode}' "
          f"({correct}/{n} train cards matched)")

    report = {"calibration_mode": mode, "calibration_accuracy": correct / n}
    for split in ("val", "test"):
        items = collect(split)
        acc, matrix = evaluate(model, items)
        print_matrix(split, acc, matrix)
        report[split] = {
            "accuracy": acc,
            "confusion_matrix": {a: {p: matrix[a].get(p, 0) for p in CLASS_ORDER}
                                 for a in CLASS_ORDER},
        }

    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    (out / "tm_evaluation.json").write_text(json.dumps(report, indent=2))
    print("\nReport saved to reports/tm_evaluation.json")
    print("\nSTEP 2B COMPLETE [OK]")


if __name__ == "__main__":
    main()