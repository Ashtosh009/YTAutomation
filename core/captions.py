import os
from typing import List, Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont

class CaptionsDrawer:
    def __init__(self, font_size: int = 74):
        self.font_size = font_size
        self.font = self._load_font()

    def _load_font(self):
        # Try finding a bold system font or fallback to PIL default
        candidate_fonts = [
            "/System/Library/Fonts/Supplemental/Impact.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/Library/Fonts/Arial Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
        ]
        for f in candidate_fonts:
            if os.path.exists(f):
                try:
                    return ImageFont.truetype(f, self.font_size)
                except Exception:
                    pass
        return ImageFont.load_default()

    def draw_karaoke_captions(self, img: Image.Image, words_chunk: List[str], active_idx: int, y_pos: int = 1380):
        """Draws high-impact Shorts-style captions with word highlight and outline."""
        draw = ImageDraw.Draw(img)
        w, h = img.size

        text_line = " ".join(words_chunk).upper()
        # Calculate total text width for centering
        bbox = draw.textbbox((0, 0), text_line, font=self.font)
        text_width = bbox[2] - bbox[0]
        start_x = (w - text_width) / 2

        cur_x = start_x
        space_bbox = draw.textbbox((0, 0), " ", font=self.font)
        space_width = space_bbox[2] - space_bbox[0]

        for i, word in enumerate(words_chunk):
            word_upper = word.upper()
            word_bbox = draw.textbbox((0, 0), word_upper, font=self.font)
            word_w = word_bbox[2] - word_bbox[0]

            # Highlight color: Vibrant Yellow for active word, White for others
            fill_color = (255, 235, 20) if i == active_idx else (255, 255, 255)
            stroke_color = (0, 0, 0)
            stroke_width = 8

            # Draw thick outline + text
            draw.text(
                (cur_x, y_pos),
                word_upper,
                font=self.font,
                fill=fill_color,
                stroke_width=stroke_width,
                stroke_fill=stroke_color
            )

            cur_x += word_w + space_width

captions_drawer = CaptionsDrawer()
