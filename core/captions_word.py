"""Captions for the explainer mode.

single_word:      one word at a time, lowercase (punctuation kept), heavy rounded sans,
                  white fill + thick dark outline + soft shadow, centered at 70% of height,
                  quick scale pop (90% -> 105% -> 100%) on each word. Emphasis words are yellow.
highlight_phrase: three-word chunk with the spoken word highlighted (legacy look), same position.
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from core.camera25d import alpha_over
from core.config import FONTS_DIR

FONT_CANDIDATES = [
    str(FONTS_DIR / "Poppins-ExtraBold.ttf"),
    "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
WHITE = (255, 255, 255)
YELLOW = (255, 214, 10)
OUTLINE = (16, 16, 26)
SAFE_TOP, SAFE_BOTTOM = 200, 320
CENTER_Y_FRAC = 0.70
MAX_TEXT_W_FRAC = 0.86


@lru_cache(maxsize=16)
def load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def norm_token(w: str) -> str:
    return re.sub(r"[^\w']", "", w.lower())


@lru_cache(maxsize=512)
def render_text_tile(text: str, size: int, color: Tuple[int, int, int], stroke: int) -> np.ndarray:
    """RGBA tile with outline and drop shadow, trimmed to content."""
    font = load_font(size)
    l, t, r, b = font.getbbox(text, stroke_width=stroke)
    pad = stroke + 24
    w, h = r - l + 2 * pad, b - t + 2 * pad
    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text((pad - l, pad - t + 10), text, font=font, fill=(0, 0, 0, 150), stroke_width=stroke, stroke_fill=(0, 0, 0, 150))
    shadow = shadow.filter(ImageFilter.GaussianBlur(7))
    fg = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(fg).text((pad - l, pad - t), text, font=font, fill=color + (255,), stroke_width=stroke, stroke_fill=OUTLINE + (255,))
    out = Image.alpha_composite(shadow, fg)
    bbox = out.getbbox() or (0, 0, w, h)
    return np.asarray(out.crop(bbox))


def pop_scale(dt: float) -> float:
    """0.90 -> 1.05 over 70 ms, back to 1.00 by 140 ms."""
    if dt < 0.07:
        return 0.90 + 0.15 * (dt / 0.07)
    if dt < 0.14:
        return 1.05 - 0.05 * ((dt - 0.07) / 0.07)
    return 1.0


class WordCaptioner:
    def __init__(self, width: int, height: int, style: str = "single_word", base_size: int = 112):
        self.W, self.H = width, height
        self.style = style
        self.base_size = base_size
        self.cy = int(height * CENTER_Y_FRAC)
        self.bboxes: List[Tuple[int, int, int, int]] = []  # for the quality gate

    def is_emphasis(self, word: str, emphasis: Sequence[str], sentence_start: bool) -> bool:
        tok = norm_token(word)
        if any(ch.isdigit() for ch in tok):
            return True
        if tok and tok in {norm_token(e) for e in emphasis}:
            return True
        return bool(word[:1].isupper() and not sentence_start and len(tok) > 2)

    def _fit_size(self, text: str) -> int:
        size = self.base_size
        while size > 56:
            font = load_font(size)
            l, _, r, _ = font.getbbox(text, stroke_width=max(8, size // 9))
            if r - l <= self.W * MAX_TEXT_W_FRAC:
                return size
            size -= 6
        return size

    def draw(self, frame: np.ndarray, words: List[Dict], idx: int, now: float, emphasis: Sequence[str]) -> Optional[Tuple[int, int, int, int]]:
        if idx < 0 or idx >= len(words):
            return None
        w = words[idx]
        sentence_start = idx == 0 or bool(re.search(r"[.!?]$", words[idx - 1]["word"]))
        if self.style == "highlight_phrase":
            return self._draw_phrase(frame, words, idx, emphasis)
        text = w["word"].lower()
        color = YELLOW if self.is_emphasis(w["word"], emphasis, sentence_start) else WHITE
        size = self._fit_size(text)
        tile = render_text_tile(text, size, color, max(8, size // 9))
        s = pop_scale(now - w["start"])
        if abs(s - 1.0) > 0.005:
            tile = cv2.resize(tile, (max(1, int(tile.shape[1] * s)), max(1, int(tile.shape[0] * s))), interpolation=cv2.INTER_LINEAR)
        th, tw = tile.shape[:2]
        x, y = (self.W - tw) // 2, self.cy - th // 2
        y = min(max(y, SAFE_TOP), self.H - SAFE_BOTTOM - th)
        bbox = alpha_over(frame, tile, x, y)
        self.bboxes.append(bbox)
        return bbox

    def _draw_phrase(self, frame: np.ndarray, words: List[Dict], idx: int, emphasis: Sequence[str]):
        start = (idx // 3) * 3
        chunk = words[start:start + 3]
        size = self._fit_size(" ".join(c["word"] for c in chunk).lower())
        tiles = [render_text_tile(c["word"].lower(), size, YELLOW if start + i == idx else WHITE, max(8, size // 9)) for i, c in enumerate(chunk)]
        gap = size // 4
        total = sum(t.shape[1] for t in tiles) + gap * (len(tiles) - 1)
        x = (self.W - total) // 2
        th = max(t.shape[0] for t in tiles)
        y = min(max(self.cy - th // 2, SAFE_TOP), self.H - SAFE_BOTTOM - th)
        x0 = x
        for t in tiles:
            alpha_over(frame, t, x, y + (th - t.shape[0]) // 2)
            x += t.shape[1] + gap
        bbox = (max(x0, 0), y, min(x, self.W), y + th)
        self.bboxes.append(bbox)
        return bbox


def punch_text_tile(text: str, size: int = 230) -> np.ndarray:
    return render_text_tile(text.upper(), size, YELLOW, max(12, size // 10))
