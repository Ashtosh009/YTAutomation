"""Monocular depth for 2.5D parallax.

Uses Depth Anything V2 Small (quantized ONNX, CPU) when available; otherwise a
simple gradient/luminance depth map. Output: float32 HxW in [0, 1], 1 = nearest.
Results are cached in assets/cache/depth/ keyed by image hash.
"""
from __future__ import annotations

import hashlib
import os
import urllib.request
from typing import Optional

import cv2
import numpy as np
from PIL import Image

from core.config import CACHE_DIR, DEPTH_MODEL_URL

MODEL_PATH = CACHE_DIR / "models" / "depth_anything_v2_small_q.onnx"
DEPTH_CACHE = CACHE_DIR / "depth"
DEPTH_CACHE.mkdir(parents=True, exist_ok=True)
INFER_SIZE = (392, 700)  # (w, h), multiples of 14, ~9:16
_MEAN = np.array([0.485, 0.456, 0.406], np.float32)
_STD = np.array([0.229, 0.224, 0.225], np.float32)


class DepthEstimator:
    def __init__(self):
        self.session = None
        self.backend = "gradient"
        self.error = ""
        try:
            if not MODEL_PATH.exists():
                MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
                tmp = str(MODEL_PATH) + ".part"
                print("[Depth] Downloading Depth Anything V2 Small (ONNX, ~27 MB)...")
                urllib.request.urlretrieve(DEPTH_MODEL_URL, tmp)
                os.replace(tmp, MODEL_PATH)
            import onnxruntime as ort

            opts = ort.SessionOptions()
            opts.log_severity_level = 3
            self.session = ort.InferenceSession(str(MODEL_PATH), opts, providers=["CPUExecutionProvider"])
            self.backend = "depth_anything_v2_small"
        except Exception as e:
            self.error = f"{type(e).__name__}: {e}"
            print(f"[Depth] Model unavailable ({self.error[:160]}); using gradient depth fallback.")

    def estimate(self, img: Image.Image, flat: bool = False) -> np.ndarray:
        w, h = img.size
        if flat:
            return np.full((h, w), 0.5, np.float32)
        key = hashlib.sha256(np.asarray(img.resize((64, 114))).tobytes() + self.backend.encode()).hexdigest()[:24]
        cache = DEPTH_CACHE / f"{key}_{w}x{h}.npy"
        if cache.exists():
            return np.load(cache)
        if self.session is not None:
            try:
                depth = self._model_depth(img)
            except Exception as e:
                print(f"[Depth] inference failed ({e}); gradient fallback for this image")
                depth = gradient_depth(img)
        else:
            depth = gradient_depth(img)
        depth = cv2.resize(depth, (w, h), interpolation=cv2.INTER_CUBIC)
        # Smooth edges so the per-pixel warp stretches instead of tearing at depth boundaries
        depth = cv2.GaussianBlur(depth, (0, 0), sigmaX=6)
        depth = np.clip(depth, 0, 1).astype(np.float32)
        np.save(cache, depth)
        return depth

    def _model_depth(self, img: Image.Image) -> np.ndarray:
        x = np.asarray(img.convert("RGB").resize(INFER_SIZE, Image.BICUBIC), np.float32) / 255.0
        x = ((x - _MEAN) / _STD).transpose(2, 0, 1)[None].astype(np.float32)
        d = self.session.run(None, {"pixel_values": x})[0][0]
        lo, hi = np.percentile(d, 2), np.percentile(d, 98)
        return np.clip((d - lo) / (hi - lo + 1e-6), 0, 1).astype(np.float32)


def gradient_depth(img: Image.Image) -> np.ndarray:
    """Fallback: bottom of frame is near, top is far, nudged by local contrast."""
    small = np.asarray(img.convert("L").resize(INFER_SIZE), np.float32) / 255.0
    h = small.shape[0]
    vert = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None] ** 1.4
    detail = cv2.GaussianBlur(np.abs(cv2.Laplacian(small, cv2.CV_32F)), (0, 0), 9)
    detail = detail / (detail.max() + 1e-6)
    return np.clip(0.8 * vert + 0.2 * detail, 0, 1).astype(np.float32)


_estimator: Optional[DepthEstimator] = None


def get_estimator() -> DepthEstimator:
    global _estimator
    if _estimator is None:
        _estimator = DepthEstimator()
    return _estimator
