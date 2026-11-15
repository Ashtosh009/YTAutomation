"""Pluggable still-image providers for the explainer render mode.

Providers are tried in the order given by IMAGE_PROVIDERS:
  kit           pre-made images from assets/kit/manifest.json (preferred when a tag matches)
  gemini_image  Gemini image model, only if a probe call succeeds on this key
  pollinations  free key-less public endpoint (best effort: retries, rate limits, watermark crop)
  procedural    code-drawn gradient/silhouette scene; never fails

Every returned image is RGB at CANVAS_SIZE (output size plus overscan for camera moves).
Results are cached in assets/cache/images/ keyed by a hash of the full prompt.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import math
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from core.config import (
    CACHE_DIR,
    GEMINI_API_KEY,
    GEMINI_IMAGE_MODEL,
    IMAGE_PROVIDERS,
    IMAGE_TIME_BUDGET_S,
    KIT_DIR,
    VIDEO_HEIGHT,
    VIDEO_WIDTH,
)

OVERSCAN = 1.10
CANVAS_SIZE = (int(round(VIDEO_WIDTH * OVERSCAN)), int(round(VIDEO_HEIGHT * OVERSCAN)))  # (1188, 2112)

STYLE_PREFIX = (
    "painterly semi-3D illustration, saturated complementary palette, wide-angle perspective, "
    "strong leading lines, atmospheric depth, cinematic lighting, vertical 9:16 composition"
)
STYLE_SUFFIX = "no people, no faces, no text, no letters, no logos, no watermark"

IMAGE_CACHE = CACHE_DIR / "images"
IMAGE_CACHE.mkdir(parents=True, exist_ok=True)
PROVIDER_VERSION = "v1"


class ProviderUnavailable(Exception):
    """Provider cannot serve requests for the rest of this run (quota, billing, outage)."""


@dataclass
class ImageResult:
    image: Image.Image
    provider: str
    cached: bool = False
    prompt: str = ""
    notes: str = ""


@dataclass
class ProviderStats:
    calls: int = 0
    successes: int = 0
    failures: int = 0
    rate_limited: int = 0
    seconds: float = 0.0
    disabled_reason: str = ""


def full_prompt(shot_prompt: str, palette: Optional[List[str]] = None) -> str:
    palette_txt = ""
    if palette:
        palette_txt = f", dominant colors {', '.join(palette[:3])}"
    shot = re.sub(r"\s+", " ", shot_prompt or "").strip().rstrip(".")
    return f"{STYLE_PREFIX}{palette_txt}. {shot}. {STYLE_SUFFIX}"


def fit_canvas(img: Image.Image, crop_bottom_frac: float = 0.0) -> Image.Image:
    """Center-crop to the canvas aspect ratio and resize to CANVAS_SIZE, sharpening upscales."""
    img = img.convert("RGB")
    w, h = img.size
    if crop_bottom_frac > 0:
        h = int(h * (1.0 - crop_bottom_frac))
        img = img.crop((0, 0, w, h))
    target_ar = CANVAS_SIZE[0] / CANVAS_SIZE[1]
    if w / h > target_ar:
        nw = int(h * target_ar)
        x0 = (w - nw) // 2
        img = img.crop((x0, 0, x0 + nw, h))
    else:
        nh = int(w / target_ar)
        y0 = (h - nh) // 2
        img = img.crop((0, y0, w, y0 + nh))
    upscale = CANVAS_SIZE[0] / img.size[0]
    img = img.resize(CANVAS_SIZE, Image.LANCZOS)
    if upscale > 1.3:
        img = img.filter(ImageFilter.UnsharpMask(radius=2.2, percent=70, threshold=2))
    return img


def is_blank(img: Image.Image) -> bool:
    arr = np.asarray(img.convert("L").resize((108, 192)), dtype=np.float32)
    return float(arr.std()) < 6.0


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------
class BaseProvider:
    name = "base"

    def __init__(self):
        self.stats = ProviderStats()
        self.enabled = True

    def disable(self, reason: str):
        if self.enabled:
            print(f"[Images] Provider '{self.name}' disabled for this run: {reason}")
        self.enabled = False
        self.stats.disabled_reason = reason

    def generate(self, prompt: str, seed: int, shot: Dict) -> Image.Image:
        raise NotImplementedError


class KitProvider(BaseProvider):
    """assets/kit/manifest.json: [{"file": "ship_deck.png", "tags": ["ship", "deck", "ocean"]}, ...]"""

    name = "kit"

    def __init__(self):
        super().__init__()
        self.items: List[Dict] = []
        manifest = KIT_DIR / "manifest.json"
        if manifest.exists():
            try:
                self.items = json.loads(manifest.read_text()).get("images", [])
            except Exception as e:
                print(f"[Images] Could not read kit manifest: {e}")
        if not self.items:
            self.enabled = False
            self.stats.disabled_reason = "no assets/kit/manifest.json entries"

    def generate(self, prompt: str, seed: int, shot: Dict) -> Image.Image:
        words = set(re.findall(r"[a-z]+", (shot.get("shot_prompt") or "").lower()))
        best, best_score = None, 0
        for item in self.items:
            score = len(words & {t.lower() for t in item.get("tags", [])})
            if score > best_score:
                best, best_score = item, score
        if not best or best_score < 2:
            raise LookupError("no kit image matches")
        return Image.open(KIT_DIR / best["file"])


class GeminiImageProvider(BaseProvider):
    name = "gemini_image"
    FATAL_STATUSES = {"RESOURCE_EXHAUSTED", "PERMISSION_DENIED", "FAILED_PRECONDITION", "NOT_FOUND"}

    def __init__(self):
        super().__init__()
        self.probed = False
        if not GEMINI_API_KEY:
            self.enabled = False
            self.stats.disabled_reason = "GEMINI_API_KEY not set"

    def _call(self, prompt: str, timeout: int = 120) -> Image.Image:
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "9:16"}},
        }
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_IMAGE_MODEL}:generateContent",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY},
        )
        try:
            data = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
        except urllib.error.HTTPError as e:
            status = ""
            try:
                status = json.loads(e.read()).get("error", {}).get("status", "")
            except Exception:
                pass
            if e.code in (429, 403, 404) or status in self.FATAL_STATUSES:
                self.stats.rate_limited += int(e.code == 429)
                raise ProviderUnavailable(f"HTTP {e.code} {status} (quota/billing; not free on this key)")
            raise
        for part in data["candidates"][0]["content"]["parts"]:
            if "inlineData" in part:
                return Image.open(io.BytesIO(base64.b64decode(part["inlineData"]["data"])))
        raise RuntimeError("Gemini returned no image part")

    def generate(self, prompt: str, seed: int, shot: Dict) -> Image.Image:
        if not self.probed:
            self.probed = True  # the first real call doubles as the probe
        return self._call(prompt)


class PollinationsProvider(BaseProvider):
    """Free, key-less, best effort. Returns ~576x1024 with a bottom-right watermark that we crop off."""

    name = "pollinations"
    URL = "https://image.pollinations.ai/prompt/{prompt}?width=1080&height=1920&nologo=true&seed={seed}"
    MAX_ATTEMPTS = 5
    MAX_CONSECUTIVE_FAILURES = 3

    def __init__(self):
        super().__init__()
        self.consecutive_failures = 0

    MIN_INTERVAL_S = 9.0  # anonymous tier answers 402/429 to back-to-back requests

    def generate(self, prompt: str, seed: int, shot: Dict) -> Image.Image:
        url = self.URL.format(prompt=urllib.parse.quote(prompt[:900]), seed=seed)
        last = None
        for attempt in range(self.MAX_ATTEMPTS):
            wait = getattr(self, "_last_call", 0.0) + self.MIN_INTERVAL_S - time.time()
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.time()
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "ytanimation-pipeline/1.0"})
                with urllib.request.urlopen(req, timeout=90) as r:
                    if not (r.headers.get("Content-Type") or "").startswith("image/"):
                        raise RuntimeError(f"non-image response {r.headers.get('Content-Type')}")
                    img = Image.open(io.BytesIO(r.read()))
                    img.load()
                self.consecutive_failures = 0
                return img
            except urllib.error.HTTPError as e:
                last = e
                if e.code in (402, 429, 503):
                    self.stats.rate_limited += 1
                    time.sleep(min(4 * (attempt + 1), 12))
                    continue
                break
            except Exception as e:  # timeouts, resets
                last = e
                time.sleep(2)
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
            raise ProviderUnavailable(f"{self.consecutive_failures} consecutive failures (last: {last})")
        raise RuntimeError(f"pollinations failed after {self.MAX_ATTEMPTS} attempts: {last}")


class ProceduralProvider(BaseProvider):
    """Code-drawn painterly scene from prompt keywords and the episode palette. Never fails."""

    name = "procedural"

    def generate(self, prompt: str, seed: int, shot: Dict) -> Image.Image:
        return draw_procedural_scene(shot.get("shot_prompt") or prompt, shot.get("_palette") or [], seed)


# ---------------------------------------------------------------------------
# Procedural scene painter
# ---------------------------------------------------------------------------
def _hex(c: str, default: Tuple[int, int, int]) -> Tuple[int, int, int]:
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", (c or "").strip())
    if not m:
        return default
    v = m.group(1)
    return (int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16))


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def draw_procedural_scene(text: str, palette: List[str], seed: int) -> Image.Image:
    rnd = random.Random(seed)
    W, H = CANVAS_SIZE
    t = (text or "").lower()
    c1 = _hex(palette[0] if len(palette) > 0 else "", (32, 64, 120))   # sky / cool
    c2 = _hex(palette[1] if len(palette) > 1 else "", (232, 128, 56))  # warm accent
    c3 = _hex(palette[2] if len(palette) > 2 else "", (18, 28, 48))    # deep shadow
    night = any(k in t for k in ("night", "star", "space", "dark", "signal", "telescope", "radio", "galaxy"))
    sky_top = _mix(c3, (5, 8, 20), 0.5) if night else _mix(c1, (255, 255, 255), 0.15)
    sky_bot = _mix(c1, c2, 0.35) if not night else _mix(c1, c3, 0.4)

    # Sky gradient
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    sky = (np.array(sky_top, np.float32) * (1 - y) + np.array(sky_bot, np.float32) * y)
    arr = np.repeat(sky, W, axis=1)
    img = Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGB")
    d = ImageDraw.Draw(img, "RGBA")

    horizon = int(H * rnd.uniform(0.56, 0.64))
    if night:
        for _ in range(420):
            x, yy = rnd.randrange(W), rnd.randrange(int(horizon * 0.95))
            r = rnd.choice([1, 1, 2, 2, 3])
            d.ellipse([x - r, yy - r, x + r, yy + r], fill=(255, 255, 240, rnd.randint(120, 255)))
    else:
        sx, sy = int(W * rnd.uniform(0.2, 0.8)), int(horizon * rnd.uniform(0.35, 0.6))
        for rr, a in ((320, 30), (200, 60), (110, 200)):
            d.ellipse([sx - rr, sy - rr, sx + rr, sy + rr], fill=c2 + (a,))
        for _ in range(7):  # soft clouds
            cx, cy, cw = rnd.randrange(W), rnd.randrange(int(horizon * 0.8)), rnd.randint(220, 520)
            d.ellipse([cx - cw, cy - cw // 5, cx + cw, cy + cw // 5], fill=(255, 255, 255, 46))

    water = any(k in t for k in ("ocean", "sea", "ship", "boat", "wave", "harbor", "harbour", "island", "lighthouse", "coast", "atlantic"))
    ground_col = _mix(c3, c1, 0.25) if water else _mix(c3, c2, 0.35)
    # Ground / sea with perspective bands
    for i in range(40):
        y0 = horizon + int((H - horizon) * (i / 40) ** 1.6)
        y1 = horizon + int((H - horizon) * ((i + 1) / 40) ** 1.6) + 1
        shade = _mix(_mix(ground_col, sky_bot, 0.45), ground_col, i / 40)
        d.rectangle([0, y0, W, y1], fill=shade + (255,))
        if water and i % 3 == 0:
            for _ in range(6):
                wx, ww = rnd.randrange(W), rnd.randint(40, 160) * (1 + i // 8)
                d.line([wx, y0, wx + ww, y0], fill=(255, 255, 255, 50), width=2 + i // 10)
    # Distant hills / cliffs
    if not water or "island" in t or "lighthouse" in t or "coast" in t:
        pts = [(0, horizon)]
        x = 0
        while x < W:
            x += rnd.randint(60, 160)
            pts.append((x, horizon - rnd.randint(40, 260 if "cliff" in t or "island" in t else 140)))
        pts += [(W, horizon), (W, horizon + 6), (0, horizon + 6)]
        d.polygon(pts, fill=_mix(c3, sky_bot, 0.35) + (255,))

    sil = _mix(c3, (0, 0, 0), 0.4) + (255,)
    cx = int(W * rnd.uniform(0.38, 0.62))
    if any(k in t for k in ("ship", "boat", "brigantine", "vessel", "schooner")):
        hull_w, base = int(W * 0.46), horizon + 40
        d.polygon([(cx - hull_w // 2, base - 70), (cx + hull_w // 2, base - 70), (cx + hull_w // 2 - 70, base + 20), (cx - hull_w // 2 + 60, base + 20)], fill=sil)
        for mx, mh in ((cx - hull_w // 5, 640), (cx + hull_w // 6, 560)):
            d.line([mx, base - 70, mx, base - 70 - mh], fill=sil, width=12)
            for k in range(3):
                sy0 = base - 120 - mh + 110 + k * (mh // 3)
                sw = 170 - k * 18
                d.polygon([(mx - sw, sy0), (mx + sw, sy0 + 12), (mx + sw - 18, sy0 + mh // 3 - 30), (mx - sw + 12, sy0 + mh // 3 - 40)],
                          fill=_mix(sky_bot, (255, 255, 255), 0.55) + (235,))
    if "lighthouse" in t:
        lx, base = int(W * 0.66), horizon - 120
        d.polygon([(lx - 70, base), (lx + 70, base), (lx + 42, base - 620), (lx - 42, base - 620)], fill=(235, 235, 228, 255))
        for k in range(4):
            yy = base - 80 - k * 150
            d.rectangle([lx - 66 + k * 7, yy - 40, lx + 66 - k * 7, yy], fill=c2 + (255,))
        d.rectangle([lx - 52, base - 700, lx + 52, base - 620], fill=(250, 230, 150, 255))
        d.polygon([(lx, base - 660), (0, base - 900), (0, base - 520)], fill=(255, 240, 180, 60))
    if any(k in t for k in ("telescope", "radio", "antenna", "dish", "observatory")):
        dx, base = int(W * 0.5), horizon + 80
        # Truss legs, then an upward-opening bowl (lower half of an ellipse) tilted to the sky
        d.polygon([(dx - 150, base), (dx + 150, base), (dx + 40, base - 330), (dx - 40, base - 330)], fill=sil)
        dish_col = _mix(sil[:3], (210, 210, 220), 0.55) + (255,)
        d.chord([dx - 360, base - 720, dx + 360, base - 300], 0, 180, fill=dish_col)
        d.ellipse([dx - 360, base - 560, dx + 360, base - 460], fill=_mix(dish_col[:3], (0, 0, 0), 0.35) + (255,))
        d.line([dx, base - 510, dx, base - 820], fill=sil, width=10)
        d.ellipse([dx - 26, base - 846, dx + 26, base - 794], fill=sil)
    if any(k in t for k in ("room", "office", "cabin", "desk", "interior", "lab")):
        d.rectangle([0, 0, W, int(H * 0.58)], fill=_mix(c3, c1, 0.4) + (190,))
        d.rectangle([int(W * 0.15), int(H * 0.14), int(W * 0.55), int(H * 0.36)], fill=_mix(sky_top, c2, 0.3) + (255,))
        d.rectangle([0, int(H * 0.62), W, int(H * 0.66)], fill=_mix(c3, c2, 0.5) + (255,))

    # Atmosphere: haze near horizon, vignette, painterly blur + noise
    haze = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hd = ImageDraw.Draw(haze)
    for i in range(30):
        a = int(70 * (1 - i / 30))
        hd.rectangle([0, horizon - 90 + i * 4, W, horizon - 86 + i * 4], fill=_mix(sky_bot, (255, 255, 255), 0.4) + (a,))
    img = Image.alpha_composite(img.convert("RGBA"), haze.filter(ImageFilter.GaussianBlur(18))).convert("RGB")
    img = img.filter(ImageFilter.GaussianBlur(1.2))
    noise = np.random.default_rng(seed).normal(0, 6, (H, W, 1)).astype(np.float32)
    out = np.asarray(img, np.float32) + noise
    return Image.fromarray(out.clip(0, 255).astype(np.uint8), "RGB")


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------
PROVIDER_CLASSES = {
    "kit": KitProvider,
    "gemini_image": GeminiImageProvider,
    "pollinations": PollinationsProvider,
    "procedural": ProceduralProvider,
}


class ImageManager:
    """One instance per video: tracks provider health, budget and stats."""

    def __init__(self, order: Optional[List[str]] = None, time_budget_s: float = IMAGE_TIME_BUDGET_S):
        order = order or IMAGE_PROVIDERS
        self.providers: List[BaseProvider] = [PROVIDER_CLASSES[n]() for n in order if n in PROVIDER_CLASSES]
        if not any(isinstance(p, ProceduralProvider) for p in self.providers):
            self.providers.append(ProceduralProvider())
        self.deadline = time.time() + time_budget_s
        self.log: List[Dict] = []

    def _cache_path(self, prompt: str, seed: int):
        key = hashlib.sha256(f"{PROVIDER_VERSION}|{prompt}|{seed}".encode()).hexdigest()[:24]
        return IMAGE_CACHE / f"{key}.png", IMAGE_CACHE / f"{key}.json"

    def get(self, shot: Dict, palette: List[str], seed: int) -> ImageResult:
        prompt = full_prompt(shot.get("shot_prompt", ""), palette)
        png, meta = self._cache_path(prompt, seed)
        if png.exists() and meta.exists():
            info = json.loads(meta.read_text())
            res = ImageResult(Image.open(png).convert("RGB"), info.get("provider", "?"), True, prompt)
            self.log.append({"provider": res.provider, "cached": True})
            return res
        shot = dict(shot, _palette=palette)
        for p in self.providers:
            if not p.enabled:
                continue
            remote = p.name in ("gemini_image", "pollinations")
            if remote and time.time() > self.deadline:
                p.disable("per-video image time budget exhausted")
                continue
            t0 = time.time()
            p.stats.calls += 1
            try:
                raw = p.generate(prompt, seed, shot)
                img = fit_canvas(raw, crop_bottom_frac=0.05 if p.name == "pollinations" else 0.0)
                if is_blank(img):
                    raise RuntimeError("blank image")
                p.stats.successes += 1
                p.stats.seconds += time.time() - t0
                # Only cache remote/kit results; procedural is cheap and palette-dependent.
                if p.name != "procedural":
                    img.save(png)
                    meta.write_text(json.dumps({"provider": p.name, "prompt": prompt}))
                self.log.append({"provider": p.name, "cached": False, "seconds": round(time.time() - t0, 1)})
                return ImageResult(img, p.name, False, prompt)
            except ProviderUnavailable as e:
                p.stats.failures += 1
                p.stats.seconds += time.time() - t0
                p.disable(str(e))
            except LookupError:
                p.stats.calls -= 1  # kit miss is not a failure
            except Exception as e:
                p.stats.failures += 1
                p.stats.seconds += time.time() - t0
                print(f"[Images] {p.name} failed for shot ({str(e)[:120]}); trying next provider")
        raise RuntimeError("all image providers failed")  # unreachable: procedural never fails

    def summary(self) -> Dict:
        return {p.name: {**p.stats.__dict__, "enabled": p.enabled} for p in self.providers}
