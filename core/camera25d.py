"""Depth-driven 2.5D camera: turns one still + depth map into a moving shot.

Each output pixel samples the canvas at
    src = canvas_center + lens(dst - out_center) / (zoom * (1 + depth_zoom * Zw(d))) + shift + parallax * P(d)
so near pixels (d -> 1) zoom and slide more than far ones, which reads as a camera
moving through the scene. Disoccluded edges are filled by edge-extension
(BORDER_REFLECT_101 plus the backward warp stretching rather than tearing).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, Tuple

import cv2
import numpy as np

CAMERA_MOVES = ("dolly_in", "dolly_out", "pan_left", "pan_right", "crane_up", "whip", "static_punch", "fly_through", "orbit")


def smoothstep(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def ease_out(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 3


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


@dataclass
class CamParams:
    zoom: float = 1.0        # global zoom (>= 1 keeps the frame inside the overscanned canvas)
    depth_zoom: float = 0.0  # extra zoom applied in proportion to nearness (dolly feel)
    sx: float = 0.0          # uniform pan in canvas px (+ = camera moves right)
    sy: float = 0.0
    px: float = 0.0          # depth-weighted parallax shift in px
    py: float = 0.0


def camera_params(move: str, t: float) -> CamParams:
    """Camera path for a shot. t in [0, 1] over the shot's duration."""
    e = smoothstep(t)
    if move == "dolly_in":
        return CamParams(zoom=1.0 + 0.05 * e, depth_zoom=0.18 * e, py=-24 * e)
    if move == "dolly_out":
        return CamParams(zoom=1.05 - 0.05 * e, depth_zoom=0.18 * (1 - e), py=-24 * (1 - e))
    if move == "pan_left":
        return CamParams(zoom=1.10, sx=lerp(32, -32, e), px=lerp(52, -52, e))
    if move == "pan_right":
        return CamParams(zoom=1.10, sx=lerp(-32, 32, e), px=lerp(-52, 52, e))
    if move == "crane_up":
        return CamParams(zoom=1.10, sy=lerp(40, -40, e), py=lerp(60, -60, e), depth_zoom=0.04 * e)
    if move == "whip":
        k = ease_out(min(t * 2.2, 1.0))  # arrives fast from the whip, then settles
        return CamParams(zoom=1.10, sx=lerp(-60, 18, k) + 10 * e, px=lerp(-40, 20, k))
    if move == "static_punch":
        k = smoothstep((t - 0.42) / 0.12)
        return CamParams(zoom=1.02 + 0.12 * k, depth_zoom=0.04 * k + 0.01 * e)
    if move == "fly_through":
        return CamParams(zoom=1.0 + 0.16 * e, depth_zoom=0.30 * e, py=-30 * e)
    if move == "orbit":
        s = math.sin(math.pi * (e - 0.5))
        return CamParams(zoom=1.08 + 0.03 * e, sx=30 * s, px=-70 * s, depth_zoom=0.05)
    if move == "push_flat":  # evidence inserts: slow push on a flat prop
        return CamParams(zoom=1.0 + 0.07 * e)
    return CamParams(zoom=1.04 + 0.02 * e)


class Camera25D:
    def __init__(self, out_w: int, out_h: int, lens_k: float = 0.035, grain_sigma: float = 5.0, seed: int = 0):
        self.W, self.H = out_w, out_h
        xs = np.arange(out_w, dtype=np.float32) - (out_w - 1) / 2
        ys = np.arange(out_h, dtype=np.float32) - (out_h - 1) / 2
        X, Y = np.meshgrid(xs, ys)
        r2 = (X / (out_w / 2)) ** 2 + (Y / (out_h / 2)) ** 2
        lens = (1.0 + lens_k * r2 / 2).astype(np.float32)  # slight barrel distortion
        self.XL = (X * lens).astype(np.float32)
        self.YL = (Y * lens).astype(np.float32)
        # Film grain: a few precomputed tiles, applied with saturating add/subtract (fast)
        rng = np.random.default_rng(seed)
        self.grain = []
        for _ in range(6):
            g = rng.normal(0, grain_sigma, (out_h, out_w, 1)).astype(np.float32)
            g3 = np.repeat(g, 3, axis=2)
            self.grain.append((np.clip(g3, 0, 255).astype(np.uint8), np.clip(-g3, 0, 255).astype(np.uint8)))
        # Vignette
        vig = 1.0 - 0.28 * np.clip(r2 / 2, 0, 1) ** 1.3
        self.vignette = np.repeat((vig * 255).astype(np.uint8)[:, :, None], 3, axis=2)

    def prepare(self, img: np.ndarray, depth: np.ndarray) -> Dict:
        """Precompute per-plate arrays. img: HcxWcx3 uint8 RGB canvas; depth: HcxWc float32."""
        hc, wc = depth.shape
        y0, x0 = (hc - self.H) // 2, (wc - self.W) // 2
        d = depth[y0:y0 + self.H, x0:x0 + self.W]
        return {
            "img": np.ascontiguousarray(img),
            "cx": (wc - 1) / 2,
            "cy": (hc - 1) / 2,
            "Zw": (0.3 + 0.7 * d).astype(np.float32),
            "P": (0.15 + 0.85 * d).astype(np.float32),
        }

    def project_point(self, plate: Dict, p: CamParams, x: float, y: float, d: float) -> Tuple[float, float, float]:
        """Where a canvas-space point at depth d lands in the output, and its scale (for sprites)."""
        z = p.zoom * (1 + p.depth_zoom * (0.3 + 0.7 * d))
        par = 0.15 + 0.85 * d
        ox = (x - plate["cx"] - p.sx - p.px * par) * z + (self.W - 1) / 2
        oy = (y - plate["cy"] - p.sy - p.py * par) * z + (self.H - 1) / 2
        return ox, oy, z

    def render(self, plate: Dict, p: CamParams, shake: Tuple[float, float] = (0.0, 0.0)) -> np.ndarray:
        inv = 1.0 / (p.zoom * (1.0 + p.depth_zoom * plate["Zw"])) if p.depth_zoom else np.float32(1.0 / p.zoom)
        sx, sy = p.sx + shake[0], p.sy + shake[1]
        if p.px or p.py:
            map_x = plate["cx"] + sx + self.XL * inv + p.px * plate["P"]
            map_y = plate["cy"] + sy + self.YL * inv + p.py * plate["P"]
        else:
            map_x = plate["cx"] + sx + self.XL * inv
            map_y = plate["cy"] + sy + self.YL * inv
        return cv2.remap(plate["img"], map_x.astype(np.float32), map_y.astype(np.float32),
                         interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)

    def post(self, frame: np.ndarray, frame_idx: int) -> np.ndarray:
        frame = cv2.multiply(frame, self.vignette, scale=1 / 255.0)
        pos, neg = self.grain[frame_idx % len(self.grain)]
        frame = cv2.add(frame, pos)
        return cv2.subtract(frame, neg)


# ---------------------------------------------------------------------------
# Transitions (operate on rendered frames)
# ---------------------------------------------------------------------------
def motion_blur_h(frame: np.ndarray, k: int) -> np.ndarray:
    k = int(k)
    if k < 3:
        return frame
    return cv2.blur(frame, (k, 1))


def zoom_blur(frame: np.ndarray, amount: float) -> np.ndarray:
    """Cheap radial zoom blur: average of a few progressively scaled copies."""
    if amount < 0.01:
        return frame
    h, w = frame.shape[:2]
    acc = frame.astype(np.float32)
    n = 4
    for i in range(1, n + 1):
        s = 1 + amount * i / n
        M = np.float32([[s, 0, (1 - s) * w / 2], [0, s, (1 - s) * h / 2]])
        acc += cv2.warpAffine(frame, M, (w, h), borderMode=cv2.BORDER_REFLECT_101)
    return (acc / (n + 1)).astype(np.uint8)


def flash(frame: np.ndarray, alpha: float) -> np.ndarray:
    if alpha <= 0.01:
        return frame
    return cv2.addWeighted(frame, 1 - alpha, np.full_like(frame, 255), alpha, 0)


def speed_lines(w: int, h: int, seed: int = 0, n: int = 70) -> np.ndarray:
    """RGBA overlay of radial speed lines (precompute once)."""
    rng = np.random.default_rng(seed)
    over = np.zeros((h, w, 4), np.uint8)
    cx, cy = w / 2, h * 0.45
    for _ in range(n):
        a = rng.uniform(0, 2 * math.pi)
        r0 = rng.uniform(0.38, 0.55) * h
        r1 = r0 + rng.uniform(0.25, 0.6) * h
        p0 = (int(cx + math.cos(a) * r0), int(cy + math.sin(a) * r0))
        p1 = (int(cx + math.cos(a) * r1), int(cy + math.sin(a) * r1))
        cv2.line(over, p0, p1, (255, 255, 255, 210), int(rng.integers(3, 9)), cv2.LINE_AA)
    return over


def alpha_over(frame: np.ndarray, rgba: np.ndarray, x: int, y: int, opacity: float = 1.0) -> Tuple[int, int, int, int]:
    """Alpha-composite an RGBA sprite onto frame at top-left (x, y), clipped. Returns drawn bbox."""
    H, W = frame.shape[:2]
    h, w = rgba.shape[:2]
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x0 >= x1 or y0 >= y1:
        return (0, 0, 0, 0)
    src = rgba[y0 - y:y1 - y, x0 - x:x1 - x]
    a = src[:, :, 3:4].astype(np.float32) * (opacity / 255.0)
    roi = frame[y0:y1, x0:x1].astype(np.float32)
    frame[y0:y1, x0:x1] = (roi * (1 - a) + src[:, :, :3].astype(np.float32) * a).astype(np.uint8)
    return (x0, y0, x1, y1)
