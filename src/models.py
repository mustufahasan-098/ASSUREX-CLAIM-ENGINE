"""Loads both AI models + policies + settings once per process (memoized) -
keeps every prediction far below the SRS 5-second budget. Also captures
model versions for per-claim version tracking (SRS req xlviii)."""
import json
from pathlib import Path

import joblib
import yaml

from .rules import load_policies
from .tm_inference import TMModel

ROOT = Path(__file__).resolve().parent.parent
_MEMO = {}


def load_all():
    if "all" in _MEMO:
        return _MEMO["all"]
    settings = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text())
    py_model = joblib.load(ROOT / "model" / "python" / "model.joblib")
    le = joblib.load(ROOT / "model" / "python" / "label_encoder.joblib")
    meta = json.loads(
        (ROOT / "model" / "python" / "model_metadata.json").read_text())
    tm = TMModel(ROOT / "model" / "tm" / "model.tflite",
                 ROOT / "model" / "tm" / "labels.txt")
    tm.mode = "mobilenet"   # verified by the 6-recipe preprocessing experiment
    _MEMO["all"] = {
        "settings": settings,
        "policies": load_policies(),
        "py_model": py_model, "le": le, "py_meta": meta,
        "tm": tm, "tm_version": settings["tm_model_version"],
    }
    return _MEMO["all"]