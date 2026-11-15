"""Recurring cast: bean-head characters distinguished by costume and color.

Sprites come from assets/cast/<slug>/<pose>.png when present; otherwise they are
drawn in code (round white head, dot eyes, simple mouth, thin dark legs, costume
coat and hat). Drawing is 2x supersampled for clean edges and cached per
(character, pose, mouth, blink, size, effect phase).
"""
from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw

from core.config import CAST_DIR

POSES = ("idle", "talking", "shocked", "angry", "thinking", "pointing", "smug", "scared")
INK = (24, 22, 30, 255)
SS = 2  # supersampling factor


def _rgb(h: str, default=(200, 200, 200)) -> Tuple[int, int, int]:
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", (h or "").strip())
    if not m:
        return default
    v = m.group(1)
    return (int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16))


class Cast:
    def __init__(self, path=CAST_DIR / "cast.json"):
        data = json.loads(path.read_text())
        self.characters: Dict[str, Dict] = {c["name"].lower(): c for c in data["characters"]}
        self.main = data["characters"][0]["name"]

    def resolve(self, name: str) -> Dict:
        key = (name or "").lower().strip()
        if key in self.characters:
            return self.characters[key]
        for k, c in self.characters.items():  # loose match ("inspector" -> "Chief Inspector")
            if key and (key in k or k.split()[-1] in key):
                return c
        return self.characters[self.main.lower()]

    def names(self) -> List[str]:
        return [c["name"] for c in self.characters.values()]

    def sprite(self, name: str, pose: str, mouth_open: bool, blink: bool, R: int, phase: int = 0) -> np.ndarray:
        c = self.resolve(name)
        pose = pose if pose in POSES else "idle"
        return _sprite_cached(c["slug"], json.dumps(c, sort_keys=True), pose, mouth_open, blink, R, phase % 6)


@lru_cache(maxsize=600)
def _sprite_cached(slug: str, cjson: str, pose: str, mouth_open: bool, blink: bool, R: int, phase: int) -> np.ndarray:
    png = CAST_DIR / slug / f"{pose}.png"
    if png.exists():
        img = Image.open(png).convert("RGBA")
        target_h = int(R * 6.6)
        img = img.resize((max(1, int(img.width * target_h / img.height)), target_h), Image.LANCZOS)
        return np.asarray(img)
    return np.asarray(draw_bean(json.loads(cjson), pose, mouth_open, blink, R, phase))


def draw_bean(c: Dict, pose: str, mouth_open: bool, blink: bool, R: int, phase: int = 0) -> Image.Image:
    """Feet at bottom-center of the returned RGBA image. Overall height ~6.6R."""
    r = R * SS
    W, H = int(r * 5.2), int(r * 7.4)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, fy = W // 2, H - int(r * 0.15)
    lw = max(3, int(r * 0.13))
    coat, coat_dark = _rgb(c.get("coat")), _rgb(c.get("coat_dark"), (90, 90, 90))
    hip_y, sh_y = fy - 2.0 * r, fy - 3.65 * r
    head_cy = fy - 4.6 * r
    angry = pose == "angry"

    # Legs
    spread = 0.42 if pose in ("scared", "shocked") else 0.32
    for s in (-1, 1):
        d.line([(cx + s * 0.15 * r, hip_y), (cx + s * spread * r, fy - 0.05 * r)], fill=INK, width=lw)
        d.ellipse([cx + s * spread * r - 0.22 * r, fy - 0.16 * r, cx + s * spread * r + 0.22 * r, fy + 0.06 * r], fill=INK)

    # Arms (drawn before coat so they emerge from the shoulders)
    def arm(pts):
        d.line(pts, fill=INK, width=lw, joint="curve")
        hx, hy = pts[-1]
        d.ellipse([hx - 0.13 * r, hy - 0.13 * r, hx + 0.13 * r, hy + 0.13 * r], fill=INK)

    L, Rr = (cx - 0.5 * r, sh_y + 0.25 * r), (cx + 0.5 * r, sh_y + 0.25 * r)
    wave = math.sin(phase / 6 * 2 * math.pi)
    if pose == "shocked":
        arm([L, (cx - 1.2 * r, sh_y - 0.4 * r), (cx - 1.0 * r, head_cy - 0.2 * r)])
        arm([Rr, (cx + 1.2 * r, sh_y - 0.4 * r), (cx + 1.0 * r, head_cy - 0.2 * r)])
    elif pose == "scared":
        arm([L, (cx - 0.95 * r, sh_y + 0.2 * r), (cx - 0.45 * r, sh_y - 0.55 * r)])
        arm([Rr, (cx + 0.95 * r, sh_y + 0.2 * r), (cx + 0.45 * r, sh_y - 0.55 * r)])
    elif pose == "angry":
        arm([L, (cx - 1.0 * r, sh_y + 0.75 * r), (cx - 0.75 * r, sh_y + 1.45 * r)])
        arm([Rr, (cx + 1.0 * r, sh_y + 0.75 * r), (cx + 0.75 * r, sh_y + 1.45 * r)])
    elif pose == "thinking":
        arm([L, (cx - 0.95 * r, sh_y + 0.9 * r), (cx - 0.7 * r, sh_y + 1.6 * r)])
        arm([Rr, (cx + 0.95 * r, sh_y + 0.6 * r), (cx + 0.35 * r, head_cy + 0.75 * r)])
    elif pose == "pointing":
        arm([L, (cx - 0.95 * r, sh_y + 0.9 * r), (cx - 0.7 * r, sh_y + 1.6 * r)])
        arm([Rr, (cx + 1.25 * r, sh_y + 0.05 * r), (cx + 2.15 * r, sh_y - 0.25 * r)])
        d.line([(cx + 2.15 * r, sh_y - 0.25 * r), (cx + 2.45 * r, sh_y - 0.33 * r)], fill=INK, width=max(2, lw // 2))
    elif pose == "talking":
        arm([L, (cx - 0.95 * r, sh_y + 0.9 * r), (cx - 0.7 * r, sh_y + 1.6 * r)])
        arm([Rr, (cx + 1.05 * r, sh_y + 0.55 * r), (cx + 1.45 * r, sh_y - (0.15 + 0.15 * wave) * r)])
    else:  # idle, smug (smug arms crossed are drawn over the coat below)
        if pose != "smug":
            arm([L, (cx - 0.85 * r, sh_y + 0.95 * r), (cx - 0.75 * r, sh_y + 1.7 * r)])
            arm([Rr, (cx + 0.85 * r, sh_y + 0.95 * r), (cx + 0.75 * r, sh_y + 1.7 * r)])

    # Coat (rounded trapezoid) + shading + buttons
    coat_poly = [(cx - 0.6 * r, sh_y), (cx + 0.6 * r, sh_y), (cx + 0.88 * r, hip_y + 0.1 * r), (cx - 0.88 * r, hip_y + 0.1 * r)]
    d.polygon(coat_poly, fill=coat + (255,), outline=INK, width=max(2, lw // 2))
    # Opaque shade (ImageDraw replaces RGBA pixels rather than blending, so no partial alpha here)
    shade = tuple(int(coat[i] * 0.62 + coat_dark[i] * 0.38) for i in range(3))
    d.polygon([(cx + 0.12 * r, sh_y + 2), (cx + 0.58 * r, sh_y + 2), (cx + 0.85 * r, hip_y + 0.08 * r), (cx + 0.27 * r, hip_y + 0.08 * r)], fill=shade + (255,))
    d.line([(cx, sh_y + 0.15 * r), (cx, hip_y + 0.05 * r)], fill=coat_dark + (255,), width=max(2, lw // 3))
    for k in range(3):
        by = sh_y + (0.45 + 0.42 * k) * r
        d.ellipse([cx - 0.07 * r, by - 0.07 * r, cx + 0.07 * r, by + 0.07 * r], fill=INK)
    acc = c.get("accessory")
    if acc == "scarf":
        sc = _rgb(c.get("accessory_color"), (240, 190, 70))
        d.rounded_rectangle([cx - 0.62 * r, sh_y - 0.18 * r, cx + 0.62 * r, sh_y + 0.18 * r], radius=int(0.15 * r), fill=sc + (255,), outline=INK, width=max(2, lw // 3))
        d.polygon([(cx + 0.2 * r, sh_y + 0.1 * r), (cx + 0.5 * r, sh_y + 0.1 * r), (cx + 0.42 * r, sh_y + 1.0 * r), (cx + 0.22 * r, sh_y + 0.95 * r)], fill=sc + (255,), outline=INK)
    if acc == "badge":
        bc = _rgb(c.get("accessory_color"), (240, 190, 70))
        bx, by = cx - 0.35 * r, sh_y + 0.5 * r
        pts = [(bx + 0.2 * r * math.cos(a) * (1 if i % 2 == 0 else 0.45), by + 0.2 * r * math.sin(a) * (1 if i % 2 == 0 else 0.45))
               for i, a in enumerate(np.linspace(-math.pi / 2, 1.5 * math.pi, 11)[:-1])]
        d.polygon(pts, fill=bc + (255,), outline=INK)
    if pose == "smug":
        d.line([(cx - 0.75 * r, sh_y + 0.55 * r), (cx + 0.55 * r, sh_y + 0.85 * r)], fill=INK, width=lw)
        d.line([(cx + 0.75 * r, sh_y + 0.55 * r), (cx - 0.55 * r, sh_y + 0.85 * r)], fill=INK, width=lw)

    # Head (bean: slightly wider than tall)
    face = (255, 255, 255)
    if angry:
        face = (236, 120, 160)  # flushed purple-pink
    d.ellipse([cx - 1.0 * r, head_cy - 0.92 * r, cx + 1.0 * r, head_cy + 0.92 * r], fill=face + (255,), outline=INK, width=lw)

    # Face
    ex, ey, er = 0.36 * r, head_cy - 0.1 * r, 0.1 * r
    if pose in ("shocked", "scared") and not blink:
        for s in (-1, 1):
            d.ellipse([cx + s * ex - 0.24 * r, ey - 0.26 * r, cx + s * ex + 0.24 * r, ey + 0.22 * r], fill=(255, 255, 255, 255), outline=INK, width=max(2, lw // 2))
            d.ellipse([cx + s * ex - 0.07 * r, ey - 0.07 * r, cx + s * ex + 0.07 * r, ey + 0.07 * r], fill=INK)
    elif blink:
        for s in (-1, 1):
            d.line([(cx + s * ex - er, ey), (cx + s * ex + er, ey)], fill=INK, width=max(2, lw // 2))
    elif pose == "smug":
        for s in (-1, 1):
            d.chord([cx + s * ex - er * 1.3, ey - er, cx + s * ex + er * 1.3, ey + er * 1.2], 0, 180, fill=INK)
    elif pose == "thinking":
        for s in (-1, 1):
            d.ellipse([cx + s * ex - er + 0.05 * r, ey - er - 0.08 * r, cx + s * ex + er + 0.05 * r, ey + er - 0.08 * r], fill=INK)
    else:
        for s in (-1, 1):
            d.ellipse([cx + s * ex - er, ey - er, cx + s * ex + er, ey + er], fill=INK)
    # Brows
    if angry:
        for s in (-1, 1):
            d.line([(cx + s * (ex + 0.22 * r), ey - 0.32 * r), (cx + s * (ex - 0.2 * r), ey - 0.16 * r)], fill=INK, width=lw)
    elif pose in ("thinking", "smug"):
        d.line([(cx + ex - 0.2 * r, ey - 0.34 * r), (cx + ex + 0.2 * r, ey - 0.42 * r)], fill=INK, width=max(2, lw * 2 // 3))
    elif pose == "scared":
        for s in (-1, 1):
            d.line([(cx + s * (ex - 0.2 * r), ey - 0.4 * r), (cx + s * (ex + 0.2 * r), ey - 0.3 * r)], fill=INK, width=max(2, lw * 2 // 3))

    # Accessory over eyes
    if acc == "pixel_sunglasses" and pose in c.get("accessory_poses", []) and not blink:
        px = 0.09 * r
        for s in (-1, 1):
            gx = cx + s * ex
            d.rectangle([gx - 3 * px, ey - 1.6 * px, gx + 3 * px, ey + 1.6 * px], fill=INK)
            d.rectangle([gx - 2 * px, ey - 0.8 * px, gx - 1 * px, ey], fill=(255, 255, 255, 230))
        d.rectangle([cx - ex + 3 * px, ey - 1.0 * px, cx + ex - 3 * px, ey], fill=INK)
    if acc == "round_glasses":
        for s in (-1, 1):
            d.ellipse([cx + s * ex - 0.2 * r, ey - 0.2 * r, cx + s * ex + 0.2 * r, ey + 0.2 * r], outline=INK, width=max(2, lw // 2))
        d.line([(cx - ex + 0.2 * r, ey), (cx + ex - 0.2 * r, ey)], fill=INK, width=max(2, lw // 3))

    # Mouth
    my = head_cy + 0.38 * r
    if mouth_open or pose in ("shocked",):
        h = 0.26 * r if pose != "shocked" else 0.34 * r
        d.ellipse([cx - 0.2 * r, my - h / 2, cx + 0.2 * r, my + h / 2 + 0.06 * r], fill=(70, 20, 30, 255), outline=INK, width=max(2, lw // 3))
        d.ellipse([cx - 0.11 * r, my + 0.02 * r, cx + 0.11 * r, my + h / 2 + 0.03 * r], fill=(230, 90, 100, 255))
    elif angry:
        d.rounded_rectangle([cx - 0.3 * r, my - 0.08 * r, cx + 0.3 * r, my + 0.1 * r], radius=int(0.04 * r), fill=(255, 255, 255, 255), outline=INK, width=max(2, lw // 3))
        d.line([(cx - 0.3 * r, my + 0.01 * r), (cx + 0.3 * r, my + 0.01 * r)], fill=INK, width=max(1, lw // 4))
    elif pose == "smug":
        d.arc([cx - 0.05 * r, my - 0.2 * r, cx + 0.38 * r, my + 0.12 * r], 20, 160, fill=INK, width=max(2, lw * 2 // 3))
    elif pose == "scared":
        pts = [(cx - 0.28 * r + i * 0.08 * r, my + (0.05 * r if i % 2 else -0.05 * r)) for i in range(8)]
        d.line(pts, fill=INK, width=max(2, lw // 2))
    elif pose == "thinking":
        d.line([(cx - 0.12 * r, my + 0.02 * r), (cx + 0.16 * r, my - 0.03 * r)], fill=INK, width=max(2, lw * 2 // 3))
    else:
        d.arc([cx - 0.24 * r, my - 0.18 * r, cx + 0.24 * r, my + 0.1 * r], 25, 155, fill=INK, width=max(2, lw * 2 // 3))

    # Hats / hair
    hat, hc = c.get("hat", "none"), _rgb(c.get("hat_color"), (60, 50, 40))
    top = head_cy - 0.92 * r
    if hat == "fedora":
        d.polygon([(cx - 0.62 * r, top + 0.25 * r), (cx + 0.62 * r, top + 0.25 * r), (cx + 0.5 * r, top - 0.65 * r), (cx, top - 0.5 * r), (cx - 0.5 * r, top - 0.65 * r)], fill=hc + (255,), outline=INK, width=max(2, lw // 2))
        d.rectangle([cx - 0.6 * r, top + 0.02 * r, cx + 0.6 * r, top + 0.2 * r], fill=_rgb(c.get("hat_band"), (20, 20, 20)) + (255,))
        d.ellipse([cx - 1.3 * r, top + 0.12 * r, cx + 1.3 * r, top + 0.42 * r], fill=hc + (255,), outline=INK, width=max(2, lw // 2))
    elif hat == "beanie":
        d.chord([cx - 0.95 * r, top - 0.55 * r, cx + 0.95 * r, top + 0.85 * r], 180, 360, fill=hc + (255,), outline=INK, width=max(2, lw // 2))
        d.rounded_rectangle([cx - 0.98 * r, top + 0.05 * r, cx + 0.98 * r, top + 0.32 * r], radius=int(0.1 * r), fill=tuple(int(v * 0.8) for v in hc) + (255,), outline=INK, width=max(2, lw // 2))
        d.ellipse([cx - 0.2 * r, top - 0.72 * r, cx + 0.2 * r, top - 0.32 * r], fill=(250, 250, 250, 255), outline=INK, width=max(2, lw // 3))
    elif hat == "peaked_cap":
        d.rounded_rectangle([cx - 0.85 * r, top - 0.45 * r, cx + 0.85 * r, top + 0.2 * r], radius=int(0.15 * r), fill=hc + (255,), outline=INK, width=max(2, lw // 2))
        d.rectangle([cx - 0.85 * r, top + 0.02 * r, cx + 0.85 * r, top + 0.2 * r], fill=_rgb(c.get("hat_band"), (20, 20, 20)) + (255,))
        d.chord([cx - 0.95 * r, top + 0.05 * r, cx + 0.95 * r, top + 0.55 * r], 0, 180, fill=(20, 20, 24, 255))
        d.ellipse([cx - 0.1 * r, top - 0.25 * r, cx + 0.1 * r, top - 0.05 * r], fill=(240, 190, 70, 255))
    else:
        hair = _rgb(c.get("hair_color"), (230, 230, 230))
        for s in (-1, 1):
            d.ellipse([cx + s * 0.95 * r - 0.28 * r, head_cy - 0.45 * r, cx + s * 0.95 * r + 0.28 * r, head_cy + 0.1 * r], fill=hair + (255,), outline=INK, width=max(2, lw // 3))

    # Emotion effects (animated by phase)
    ph = phase / 6.0
    if pose == "angry":
        for k, s in enumerate((-1, 1)):
            rise = ((ph + k * 0.5) % 1.0)
            sx, sy = cx + s * 1.1 * r, top - rise * 0.9 * r
            rr = (0.22 + 0.25 * rise) * r
            d.ellipse([sx - rr, sy - rr, sx + rr, sy + rr], fill=(245, 245, 245, int(230 * (1 - rise))), outline=(120, 120, 130, int(200 * (1 - rise))), width=max(2, lw // 3))
    if pose in ("shocked", "scared"):
        drop = (ph % 1.0)
        dx, dy = cx + 1.05 * r, head_cy - 0.5 * r + drop * 0.6 * r
        d.polygon([(dx, dy - 0.25 * r), (dx - 0.13 * r, dy + 0.05 * r), (dx + 0.13 * r, dy + 0.05 * r)], fill=(110, 190, 255, 255))
        d.ellipse([dx - 0.13 * r, dy - 0.07 * r, dx + 0.13 * r, dy + 0.18 * r], fill=(110, 190, 255, 255))
    if pose == "smug":
        for k, (sx, sy) in enumerate(((cx + 1.25 * r, top + 0.1 * r), (cx - 1.2 * r, top + 0.5 * r))):
            a = 0.5 + 0.5 * math.sin(2 * math.pi * (ph + k * 0.5))
            sr = (0.12 + 0.12 * a) * r
            d.polygon([(sx, sy - sr * 2), (sx + sr * 0.5, sy), (sx, sy + sr * 2), (sx - sr * 0.5, sy)], fill=(255, 230, 90, 255))
            d.polygon([(sx - sr * 2, sy), (sx, sy - sr * 0.5), (sx + sr * 2, sy), (sx, sy + sr * 0.5)], fill=(255, 230, 90, 255))
    if pose == "thinking":
        bob = math.sin(2 * math.pi * ph) * 0.08 * r
        qx, qy = cx + 1.25 * r, top - 0.2 * r + bob
        d.arc([qx - 0.25 * r, qy - 0.5 * r, qx + 0.25 * r, qy], 180, 410, fill=(255, 190, 40, 255), width=max(3, lw))
        d.line([(qx + 0.05 * r, qy - 0.05 * r), (qx, qy + 0.2 * r)], fill=(255, 190, 40, 255), width=max(3, lw))
        d.ellipse([qx - 0.07 * r, qy + 0.3 * r, qx + 0.07 * r, qy + 0.44 * r], fill=(255, 190, 40, 255))

    return img.resize((W // SS, H // SS), Image.LANCZOS)


_cast: Optional[Cast] = None


def get_cast() -> Cast:
    global _cast
    if _cast is None:
        _cast = Cast()
    return _cast
