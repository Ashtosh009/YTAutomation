"""Evidence inserts rendered in code with real, legible text (>= 60 px).

Kinds: newspaper, logbook, map, calendar, telegram, sticky_note, photo_frame.
evidence_prop fields (all optional except kind):
  masthead, headline, date, subhead, title, lines[], labels[], month, day, year, text, caption
Returns an RGB canvas-size image plus a report of the text actually drawn.
"""
from __future__ import annotations

import math
import random
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from core.config import FONTS_DIR
from core.images import CANVAS_SIZE, _hex, _mix, draw_procedural_scene

MIN_PX = 60
INK = (28, 24, 22)
SERIF_BOLD = FONTS_DIR / "AbrilFatface-Regular.ttf"
TYPEWRITER = FONTS_DIR / "CourierPrime-Bold.ttf"
SANS = FONTS_DIR / "Poppins-ExtraBold.ttf"
PROP_KINDS = ("newspaper", "logbook", "map", "calendar", "telegram", "sticky_note", "photo_frame")


@lru_cache(maxsize=64)
def font(path, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)


def wrap(text: str, fnt: ImageFont.FreeTypeFont, max_w: int) -> List[str]:
    words, lines, cur = (text or "").split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if fnt.getlength(trial) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


class TextBlock:
    """Fits text into a box: largest size in [min_size, max_size] that fits max_lines."""

    def __init__(self, report: Dict):
        self.report = report

    def draw(self, d: ImageDraw.ImageDraw, text: str, path, box: Tuple[int, int, int, int], max_size: int,
             max_lines: int = 3, fill=INK, align: str = "center", min_size: int = MIN_PX, spacing: float = 1.12) -> int:
        if not text:
            return box[1]
        x0, y0, x1, y1 = box
        size = max_size
        while True:
            f = font(path, size)
            lines = wrap(text, f, x1 - x0)
            line_h = int(size * spacing)
            if (len(lines) <= max_lines and line_h * len(lines) <= (y1 - y0)) or size <= min_size:
                break
            size -= 4
        if len(lines) > max_lines:  # still too long at the minimum size: keep whole words, mark as truncated
            lines = lines[:max_lines]
            lines[-1] = lines[-1].rstrip(".,;:") + "…"
            self.report.setdefault("truncated", []).append(text)
        y = y0
        for ln in lines:
            w = f.getlength(ln)
            x = x0 if align == "left" else x0 + (x1 - x0 - w) / 2
            d.text((x, y), ln, font=f, fill=fill)
            y += line_h
        self.report.setdefault("texts", []).append(" ".join(lines))
        self.report["min_font_px"] = min(self.report.get("min_font_px", 10 ** 6), size)
        return y


def paper_texture(w: int, h: int, base=(242, 234, 214), seed: int = 0, age: float = 0.5) -> Image.Image:
    rng = np.random.default_rng(seed)
    arr = np.ones((h, w, 3), np.float32) * np.array(base, np.float32)
    arr += rng.normal(0, 5, (h, w, 1))
    fibers = np.asarray(Image.fromarray(rng.integers(0, 255, (h // 6, w // 6), dtype=np.uint8)).resize((w, h), Image.BICUBIC), np.float32)
    arr += (fibers[:, :, None] - 128) * 0.05
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    edge = np.minimum.reduce([xx, yy, w - xx, h - yy]) / (0.18 * min(w, h))
    arr *= (1 - age * 0.22 * np.clip(1 - edge, 0, 1) ** 2)[:, :, None]
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGB")


def desk_background(palette: List[str], seed: int) -> Image.Image:
    W, H = CANVAS_SIZE
    c1 = _hex(palette[0] if palette else "", (40, 60, 90))
    c3 = _hex(palette[2] if len(palette) > 2 else "", (20, 22, 30))
    base = np.array(_mix(c3, c1, 0.35), np.float32)
    rng = np.random.default_rng(seed)
    streaks = np.asarray(Image.fromarray(rng.integers(0, 255, (H // 40, 8), dtype=np.uint8)).resize((W, H), Image.BICUBIC), np.float32)
    arr = base + (streaks[:, :, None] - 128) * 0.12 + rng.normal(0, 4, (H, W, 1))
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H * 0.45) / H) ** 2)
    arr *= (1.15 - 0.9 * r)[:, :, None]
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGB")


def place_on_desk(bg: Image.Image, paper: Image.Image, angle: float, center_y: float = 0.45) -> Image.Image:
    W, H = bg.size
    rot = paper.convert("RGBA").rotate(angle, resample=Image.BICUBIC, expand=True)
    shadow = Image.new("RGBA", rot.size, (0, 0, 0, 0))
    shadow.putalpha(rot.getchannel("A").point(lambda a: int(a * 0.55)))
    shadow = shadow.filter(ImageFilter.GaussianBlur(22))
    x, y = (W - rot.width) // 2, int(H * center_y - rot.height / 2)
    out = bg.convert("RGBA")
    out.alpha_composite(shadow, (x + 26, y + 34))
    out.alpha_composite(rot, (x, y))
    return out.convert("RGB")


def render_prop(prop: Dict, palette: List[str], seed: int = 0) -> Tuple[Image.Image, Dict]:
    kind = (prop.get("kind") or "newspaper").lower().strip()
    if kind not in PROP_KINDS:
        kind = "newspaper"
    rnd = random.Random(seed)
    report: Dict = {"kind": kind}
    tb = TextBlock(report)
    accent = _hex(palette[1] if len(palette) > 1 else "", (200, 60, 50))
    angle = rnd.uniform(-3.5, 3.5)
    bg = desk_background(palette, seed)

    if kind == "newspaper":
        pw, ph = 980, 1340
        p = paper_texture(pw, ph, (236, 230, 212), seed, 0.7)
        d = ImageDraw.Draw(p)
        y = tb.draw(d, prop.get("masthead") or "THE MORNING HERALD", SERIF_BOLD, (50, 40, pw - 50, 170), 108, 1)
        d.line([(50, y + 6), (pw - 50, y + 6)], fill=INK, width=6)
        y = tb.draw(d, prop.get("date") or "", TYPEWRITER, (50, y + 20, pw - 50, y + 110), 62, 1)
        d.line([(50, y + 8), (pw - 50, y + 8)], fill=INK, width=3)
        y = tb.draw(d, (prop.get("headline") or "").upper(), SERIF_BOLD, (50, y + 30, pw - 50, y + 560), 150, 3)
        y = tb.draw(d, prop.get("subhead") or "", TYPEWRITER, (60, y + 26, pw - 60, y + 300), 64, 3)
        for col in range(2):  # body copy as grey bars
            cx0 = 60 + col * (pw - 120) // 2 + (20 if col else 0)
            for k in range(max(0, (ph - 80 - y) // 34)):
                lw = (pw - 160) // 2 - (rnd.randint(0, 90) if k % 5 == 4 else 0)
                d.rectangle([cx0, y + 40 + k * 34, cx0 + lw, y + 54 + k * 34], fill=(150, 145, 135))
        img = place_on_desk(bg, p, angle)

    elif kind == "logbook":
        pw, ph = 960, 1300
        p = paper_texture(pw, ph, (238, 228, 196), seed, 0.8)
        d = ImageDraw.Draw(p)
        for k in range(14):
            d.line([(40, 300 + k * 72), (pw - 40, 300 + k * 72)], fill=(140, 170, 205), width=2)
        d.line([(130, 0), (130, ph)], fill=(200, 80, 80), width=3)
        y = tb.draw(d, prop.get("title") or "SHIP'S LOG", SERIF_BOLD, (150, 50, pw - 50, 170), 96, 1, align="left")
        y = tb.draw(d, prop.get("date") or "", TYPEWRITER, (150, y + 20, pw - 50, y + 110), 66, 1, fill=(120, 40, 30), align="left")
        for line in (prop.get("lines") or [prop.get("text", "")])[:4]:
            y = tb.draw(d, line, TYPEWRITER, (150, y + 24, pw - 50, y + 230), 64, 3, align="left")
        img = place_on_desk(bg, p, angle)

    elif kind == "map":
        pw, ph = 1000, 1240
        p = paper_texture(pw, ph, (232, 222, 192), seed, 0.9)
        d = ImageDraw.Draw(p, "RGBA")
        d.rectangle([40, 180, pw - 40, ph - 40], fill=(150, 190, 205, 255), outline=INK, width=4)
        for _ in range(3):
            cx, cy, rr = rnd.randint(150, pw - 150), rnd.randint(330, ph - 200), rnd.randint(90, 190)
            pts = [(cx + rr * (0.7 + 0.3 * rnd.random()) * math.cos(a), cy + rr * (0.7 + 0.3 * rnd.random()) * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 18)]
            d.polygon(pts, fill=(205, 190, 140, 255), outline=(120, 100, 70, 255))
        a, b = (rnd.randint(140, 360), rnd.randint(ph - 360, ph - 180)), (rnd.randint(pw - 360, pw - 140), rnd.randint(320, 520))
        for k in range(18):
            t0, t1 = k / 18, (k + 0.55) / 18
            def pt(t):
                return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t - math.sin(math.pi * t) * 160)
            d.line([pt(t0), pt(t1)], fill=accent + (255,), width=10)
        for s in (-1, 1):
            d.line([(b[0] - 34, b[1] - 34 * s), (b[0] + 34, b[1] + 34 * s)], fill=(190, 30, 30, 255), width=14)
        y = tb.draw(d, prop.get("title") or "", SERIF_BOLD, (50, 40, pw - 50, 170), 96, 1)
        labels = (prop.get("labels") or [])[:2]
        for (lx, ly), text in zip((a, b), labels):
            f = font(TYPEWRITER, 62)
            w = int(f.getlength(text)) + 30
            x0 = int(min(max(lx - w / 2, 50), pw - 50 - w))
            y0 = int(ly + 40 if ly < ph - 260 else ly - 130)
            d.rounded_rectangle([x0, y0, x0 + w, y0 + 86], radius=12, fill=(255, 255, 255, 235), outline=INK, width=3)
            tb.draw(d, text, TYPEWRITER, (x0 + 15, y0 + 8, x0 + w - 15, y0 + 84), 62, 1)
        img = place_on_desk(bg, p, angle)

    elif kind == "calendar":
        pw, ph = 860, 1080
        p = paper_texture(pw, ph, (248, 246, 240), seed, 0.3)
        d = ImageDraw.Draw(p)
        d.rectangle([0, 0, pw, 270], fill=accent)
        tb.draw(d, (prop.get("month") or "").upper(), SERIF_BOLD, (40, 50, pw - 40, 230), 140, 1, fill=(255, 255, 255))
        tb.draw(d, str(prop.get("day") or ""), SERIF_BOLD, (40, 300, pw - 40, 820), 420, 1)
        tb.draw(d, str(prop.get("year") or ""), TYPEWRITER, (40, 850, pw - 40, 1000), 110, 1, fill=(90, 90, 90))
        for k in range(2):
            d.ellipse([pw // 3 * (k + 1) - 22, -22, pw // 3 * (k + 1) + 22, 22], fill=(60, 60, 60))
        img = place_on_desk(bg, p, angle)

    elif kind == "telegram":
        pw, ph = 1000, 1100
        p = paper_texture(pw, ph, (240, 226, 170), seed, 0.6)
        d = ImageDraw.Draw(p)
        d.rectangle([30, 30, pw - 30, ph - 30], outline=(120, 90, 40), width=5)
        y = tb.draw(d, prop.get("title") or "TELEGRAM", SERIF_BOLD, (60, 60, pw - 60, 200), 120, 1, fill=(110, 60, 20))
        y = tb.draw(d, prop.get("date") or "", TYPEWRITER, (60, y + 10, pw - 60, y + 100), 62, 1)
        d.line([(60, y + 14), (pw - 60, y + 14)], fill=(120, 90, 40), width=3)
        for line in (prop.get("lines") or [prop.get("text", "")])[:4]:
            y = tb.draw(d, line.upper(), TYPEWRITER, (70, y + 30, pw - 70, y + 260), 66, 3, align="left")
        img = place_on_desk(bg, p, angle)

    elif kind == "sticky_note":
        pw = ph = 820
        p = paper_texture(pw, ph, (255, 226, 92), seed, 0.25)
        d = ImageDraw.Draw(p)
        tb.draw(d, prop.get("text") or prop.get("headline") or "", SANS, (70, 120, pw - 70, ph - 80), 120, 4)
        img = place_on_desk(bg, p, angle * 2, center_y=0.42)

    else:  # photo_frame
        pw, ph = 900, 1180
        p = Image.new("RGB", (pw, ph), (248, 246, 240))
        scene = draw_procedural_scene(prop.get("scene") or prop.get("caption") or "", palette, seed).resize((pw - 100, int((pw - 100) * 1.1)))
        scene = Image.fromarray((np.asarray(scene.convert("L").convert("RGB"), np.float32) * np.array([1.05, 0.95, 0.8])).clip(0, 255).astype(np.uint8))
        p.paste(scene, (50, 50))
        d = ImageDraw.Draw(p)
        tb.draw(d, prop.get("caption") or "", TYPEWRITER, (50, 50 + scene.height + 20, pw - 50, ph - 30), 70, 2)
        img = place_on_desk(bg, p, angle)

    report.setdefault("min_font_px", MIN_PX)
    report["legible"] = report["min_font_px"] >= MIN_PX and not report.get("truncated")
    return img, report
