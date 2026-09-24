"""Teachable Machine (TensorFlow Lite) inference for Claim Summary Cards.

Loads the exported TM image-classification model and returns class
probabilities. Runs fully locally - no network calls, no external AI APIs
(SRS 1.10.15).

Preprocessing contract (verified experimentally - see dev log):
  Teachable Machine CENTER-CROPS every training image to a square, then
  resizes to 224x224. Inference must do exactly the same. Earlier versions
  squished full-aspect images to 224x224, showing the model distorted
  images it had never trained on. A 6-recipe experiment (3 normalisations
  x crop/squish) on a 30-image control model scored mobilenet+center-crop
  30/30, all other recipes <= 14/30.

Input normalisation is auto-calibrated against labelled training cards,
because TM's export normalisation can vary with export settings.
"""
from pathlib import Path

import numpy as np


class TMModel:
    INPUT_SIZE = 224

    def __init__(self, model_path, labels_path):
        interp_cls = self._interpreter_cls()
        self.interp = interp_cls(model_path=str(model_path))
        self.interp.allocate_tensors()
        self.input_details = self.interp.get_input_details()[0]
        self.output_details = self.interp.get_output_details()[0]
        raw = [l.strip() for l in
               Path(labels_path).read_text(encoding="utf-8").splitlines()
               if l.strip()]
        # Teachable Machine exports labels with an index prefix,
        # e.g. "0 Valid Claim". Strip it so labels match the dataset
        # class names exactly.
        self.labels = [l.split(" ", 1)[1] if l[0].isdigit() and " " in l else l
                       for l in raw]
        self.mode = "mobilenet"   # (pixel / 127.5) - 1, TM's documented scheme

    @staticmethod
    def _interpreter_cls():
        try:
            from ai_edge_litert.interpreter import Interpreter
            return Interpreter
        except ImportError:
            pass
        try:
            import tensorflow as tf
            return tf.lite.Interpreter
        except ImportError:
            raise RuntimeError("No TFLite runtime found. Install with: "
                               "pip install tensorflow  (or pip install ai-edge-litert)")

    def _prepare(self, pil_image):
        img = pil_image.convert("RGB")
        # Teachable Machine center-crops training images to a square before
        # resizing to 224x224. Inference must do exactly the same, or the
        # model is shown distorted images it never trained on.
        w, h = img.size
        s = min(w, h)
        left, top = (w - s) // 2, (h - s) // 2
        img = img.crop((left, top, left + s, top + s)).resize(
            (self.INPUT_SIZE, self.INPUT_SIZE))
        arr = np.asarray(img, dtype=np.float32)
        if self.mode == "mobilenet":
            arr = arr / 127.5 - 1.0
        elif self.mode == "unit":
            arr = arr / 255.0
        # "raw" keeps 0-255 unchanged
        dt = self.input_details["dtype"]
        if dt in (np.float32, np.float16):
            return arr.reshape(1, self.INPUT_SIZE, self.INPUT_SIZE, 3).astype(dt)
        # quantized input: use the model's own quantisation parameters
        scale, zero = self.input_details.get("quantization") or (1.0, 0)
        q = arr / scale + zero if scale else arr
        info = np.iinfo(dt)
        q = np.clip(q, info.min, info.max)
        return q.reshape(1, self.INPUT_SIZE, self.INPUT_SIZE, 3).astype(dt)

    def predict(self, pil_image):
        """Return {class_label: probability} for one card image."""
        self.interp.set_tensor(self.input_details["index"], self._prepare(pil_image))
        self.interp.invoke()
        out = np.asarray(
            self.interp.get_tensor(self.output_details["index"])).flatten()
        # guard: a labels file that doesn't match the model (stale export or
        # failed copy) produces silent garbage - fail loudly instead
        if len(self.labels) != len(out):
            raise RuntimeError(
                f"labels.txt has {len(self.labels)} classes but the model outputs "
                f"{len(out)} - the model and labels file do not match (stale "
                f"export or failed copy).")
        if out.min() < 0 or abs(out.sum() - 1.0) > 0.05:   # not probabilities yet
            out = np.exp(out - out.max())
            out = out / out.sum()
        return {label: float(p) for label, p in zip(self.labels, out)}

    def calibrate(self, samples):
        """samples: list of (PIL image, expected label). Tries each input
        normalisation mode and keeps the one matching the most known labels."""
        best_mode, best = self.mode, -1
        for mode in ("mobilenet", "unit", "raw"):
            self.mode = mode
            correct = 0
            for img, expected in samples:
                probs = self.predict(img)
                if max(probs, key=probs.get) == expected:
                    correct += 1
            if correct > best:
                best, best_mode = correct, mode
        self.mode = best_mode
        return best_mode, best, len(samples)