import math
import random
from typing import Dict, Any, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont
from core.config import VIDEO_WIDTH, VIDEO_HEIGHT

class StickFigureRenderer:
    def __init__(self, width: int = VIDEO_WIDTH, height: int = VIDEO_HEIGHT):
        self.width = width
        self.height = height
        self.line_width = 12

    def draw_background(self, draw: ImageDraw.ImageDraw, bg_type: str, time_offset: float = 0.0):
        """Draws clean, colorful 9:16 background setting."""
        w, h = self.width, self.height

        if bg_type == "bedroom":
            # Cozy modern bedroom
            draw.rectangle([0, 0, w, h * 0.75], fill=(245, 240, 235))  # Warm wall
            draw.rectangle([0, h * 0.75, w, h], fill=(210, 180, 140))  # Wooden floor
            draw.line([(0, h * 0.75), (w, h * 0.75)], fill=(120, 90, 60), width=8)

            # Window with sky & sun/stars
            draw.rectangle([w * 0.65, h * 0.15, w * 0.90, h * 0.35], fill=(173, 216, 230), outline=(80, 80, 80), width=8)
            draw.line([(w * 0.775, h * 0.15), (w * 0.775, h * 0.35)], fill=(80, 80, 80), width=6)
            draw.line([(w * 0.65, h * 0.25), (w * 0.90, h * 0.25)], fill=(80, 80, 80), width=6)
            draw.ellipse([w * 0.78, h * 0.17, w * 0.86, h * 0.23], fill=(255, 220, 50)) # Sun

            # Minimalist wall poster
            draw.rectangle([w * 0.1, h * 0.18, w * 0.32, h * 0.34], fill=(255, 255, 255), outline=(50, 50, 50), width=6)
            draw.rectangle([w * 0.13, h * 0.21, w * 0.29, h * 0.31], fill=(255, 100, 100))

        elif bg_type == "office":
            # Cool corporate tech office
            draw.rectangle([0, 0, w, h * 0.75], fill=(230, 238, 245))  # Pale blue/grey wall
            draw.rectangle([0, h * 0.75, w, h], fill=(160, 165, 175))  # Carpet
            draw.line([(0, h * 0.75), (w, h * 0.75)], fill=(90, 95, 105), width=8)

            # Whiteboard with funny chart
            draw.rectangle([w * 0.15, h * 0.15, w * 0.85, h * 0.38], fill=(255, 255, 255), outline=(120, 120, 120), width=10)
            # Upward zigzag red line
            draw.line([
                (w * 0.25, h * 0.32),
                (w * 0.40, h * 0.28),
                (w * 0.55, h * 0.30),
                (w * 0.75, h * 0.19)
            ], fill=(230, 40, 40), width=8)

        elif bg_type == "classroom":
            # Classroom with chalkboard
            draw.rectangle([0, 0, w, h * 0.75], fill=(240, 235, 220))
            draw.rectangle([0, h * 0.75, w, h], fill=(180, 140, 100))
            draw.line([(0, h * 0.75), (w, h * 0.75)], fill=(100, 70, 40), width=8)

            # Blackboard
            draw.rectangle([w * 0.1, h * 0.15, w * 0.9, h * 0.40], fill=(40, 60, 50), outline=(140, 90, 40), width=12)

        else:
            # High-energy vibrant gradient / modern studio void
            for y in range(0, h, 16):
                ratio = y / h
                r = int(245 - 30 * ratio)
                g = int(240 - 20 * ratio)
                b = int(255 - 40 * ratio)
                draw.rectangle([0, y, w, y + 16], fill=(r, g, b))
            # Floor shadow platform
            draw.ellipse([w * 0.2, h * 0.78, w * 0.8, h * 0.85], fill=(210, 210, 225))

    def draw_face(self, draw: ImageDraw.ImageDraw, cx: float, cy: float, expression: str, mouth_open: bool = False):
        """Draws expressive cartoon stick-man face."""
        black = (20, 20, 20)
        lw = 8

        if expression == "shocked":
            # Huge wide eyes, tiny pupils
            draw.ellipse([cx - 45, cy - 35, cx - 15, cy + 5], fill=(255, 255, 255), outline=black, width=6)
            draw.ellipse([cx + 15, cy - 35, cx + 45, cy + 5], fill=(255, 255, 255), outline=black, width=6)
            draw.ellipse([cx - 33, cy - 18, cx - 27, cy - 12], fill=black)
            draw.ellipse([cx + 27, cy - 18, cx + 33, cy - 12], fill=black)
            # Big open O mouth
            draw.ellipse([cx - 20, cy + 18, cx + 20, cy + 58], fill=(230, 60, 60), outline=black, width=6)
            # Sweat drop
            draw.ellipse([cx + 55, cy - 40, cx + 70, cy - 20], fill=(80, 180, 255))

        elif expression == "smug":
            # Slanted cool eyes
            draw.line([(cx - 45, cy - 20), (cx - 15, cy - 15)], fill=black, width=lw)
            draw.line([(cx + 15, cy - 15), (cx + 45, cy - 20)], fill=black, width=lw)
            draw.ellipse([cx - 32, cy - 10, cx - 22, cy], fill=black)
            draw.ellipse([cx + 22, cy - 10, cx + 32, cy], fill=black)
            # Smirk curve
            draw.arc([cx - 10, cy + 10, cx + 35, cy + 40], start=10, end=170, fill=black, width=lw)

        elif expression == "laughing":
            # Curved ^^ happy eyes
            draw.arc([cx - 45, cy - 30, cx - 15, cy - 5], start=180, end=360, fill=black, width=lw)
            draw.arc([cx + 15, cy - 30, cx + 45, cy - 5], start=180, end=360, fill=black, width=lw)
            # Wide laughing mouth with tongue
            draw.chord([cx - 35, cy + 10, cx + 35, cy + 50], start=0, end=180, fill=(240, 70, 70), outline=black, width=6)

        elif expression == "angry":
            # Angled aggressive eyebrows
            draw.line([(cx - 45, cy - 30), (cx - 15, cy - 15)], fill=black, width=lw)
            draw.line([(cx + 15, cy - 15), (cx + 45, cy - 30)], fill=black, width=lw)
            draw.ellipse([cx - 35, cy - 10, cx - 25, cy], fill=black)
            draw.ellipse([cx + 25, cy - 10, cx + 35, cy], fill=black)
            # Gritted teeth rectangle mouth
            draw.rectangle([cx - 30, cy + 20, cx + 30, cy + 38], fill=(255, 255, 255), outline=black, width=6)
            draw.line([(cx, cy + 20), (cx, cy + 38)], fill=black, width=4)

        elif expression == "crying":
            # Screaming tears
            draw.line([(cx - 45, cy - 20), (cx - 15, cy - 20)], fill=black, width=lw)
            draw.line([(cx + 15, cy - 20), (cx + 45, cy - 20)], fill=black, width=lw)
            # Waterfall blue tears
            draw.rectangle([cx - 40, cy - 15, cx - 20, cy + 60], fill=(100, 190, 255))
            draw.rectangle([cx + 20, cy - 15, cx + 40, cy + 60], fill=(100, 190, 255))
            # Wavy sad mouth
            draw.arc([cx - 30, cy + 25, cx + 30, cy + 55], start=180, end=360, fill=black, width=lw)

        elif expression == "derp":
            # One eye up, one eye down
            draw.ellipse([cx - 40, cy - 35, cx - 15, cy - 10], fill=(255, 255, 255), outline=black, width=6)
            draw.ellipse([cx - 30, cy - 30, cx - 22, cy - 22], fill=black)
            draw.ellipse([cx + 15, cy - 20, cx + 40, cy + 5], fill=(255, 255, 255), outline=black, width=6)
            draw.ellipse([cx + 25, cy - 5, cx + 33, cy + 3], fill=black)
            # Silly tongue
            draw.ellipse([cx - 10, cy + 25, cx + 15, cy + 50], fill=(255, 120, 140))

        else: # Neutral
            draw.ellipse([cx - 35, cy - 20, cx - 23, cy - 8], fill=black)
            draw.ellipse([cx + 23, cy - 20, cx + 35, cy - 8], fill=black)
            if mouth_open:
                draw.ellipse([cx - 15, cy + 15, cx + 15, cy + 35], fill=black)
            else:
                draw.line([(cx - 20, cy + 22), (cx + 20, cy + 22)], fill=black, width=lw)

    def draw_character(self, draw: ImageDraw.ImageDraw, cx: float, cy: float, expression: str, action: str, prop: str = "none", bounce_y: float = 0.0, mouth_open: bool = False):
        """Renders the stick figure character with dynamic poses, limbs and props."""
        black = (20, 20, 20)
        lw = self.line_width

        head_radius = 85
        head_cy = cy - 260 + bounce_y
        neck_y = head_cy + head_radius
        pelvis_y = neck_y + 260
        feet_y = pelvis_y + 260

        # --- 1. Torso ---
        draw.line([(cx, neck_y), (cx, pelvis_y)], fill=black, width=lw)

        # --- 2. Legs ---
        if action == "running":
            # Running split
            draw.line([(cx, pelvis_y), (cx - 90, pelvis_y + 120), (cx - 140, feet_y - 30)], fill=black, width=lw)
            draw.line([(cx, pelvis_y), (cx + 80, pelvis_y + 110), (cx + 130, feet_y)], fill=black, width=lw)
        else:
            # Standing/slight natural bend
            draw.line([(cx, pelvis_y), (cx - 60, feet_y)], fill=black, width=lw)
            draw.line([(cx, pelvis_y), (cx + 60, feet_y)], fill=black, width=lw)

        # --- 3. Arms & Poses ---
        shoulder_y = neck_y + 35
        if action == "screaming":
            # Hands up beside head / flailing
            draw.line([(cx, shoulder_y), (cx - 110, shoulder_y - 80), (cx - 90, head_cy)], fill=black, width=lw)
            draw.line([(cx, shoulder_y), (cx + 110, shoulder_y - 80), (cx + 90, head_cy)], fill=black, width=lw)
        elif action == "facepalm":
            # Left arm down, right arm touching forehead
            draw.line([(cx, shoulder_y), (cx - 70, shoulder_y + 130)], fill=black, width=lw)
            draw.line([(cx, shoulder_y), (cx + 60, shoulder_y + 40), (cx + 10, head_cy + 10)], fill=black, width=lw)
        elif action == "shrugging":
            # Both hands raised up in shrug ¯\_(ツ)_/¯
            draw.line([(cx, shoulder_y), (cx - 90, shoulder_y + 20), (cx - 140, shoulder_y - 70)], fill=black, width=lw)
            draw.line([(cx, shoulder_y), (cx + 90, shoulder_y + 20), (cx + 140, shoulder_y - 70)], fill=black, width=lw)
        elif action == "explaining":
            # Both hands gesturing forward
            draw.line([(cx, shoulder_y), (cx - 100, shoulder_y + 70), (cx - 150, shoulder_y + 30)], fill=black, width=lw)
            draw.line([(cx, shoulder_y), (cx + 100, shoulder_y + 70), (cx + 150, shoulder_y + 30)], fill=black, width=lw)
        else: # Talking
            draw.line([(cx, shoulder_y), (cx - 70, shoulder_y + 120)], fill=black, width=lw)
            draw.line([(cx, shoulder_y), (cx + 80, shoulder_y + 60), (cx + 120, shoulder_y - 20)], fill=black, width=lw)

        # --- 4. Head ---
        # White filled circle with black outline
        draw.ellipse([cx - head_radius, head_cy - head_radius, cx + head_radius, head_cy + head_radius],
                     fill=(255, 255, 255), outline=black, width=lw)

        # Facial Expression
        self.draw_face(draw, cx, head_cy, expression, mouth_open)

        # --- 5. Props ---
        if prop == "phone":
            px = cx + 130
            py = shoulder_y - 40
            draw.rectangle([px - 20, py - 35, px + 20, py + 35], fill=(30, 30, 30), outline=black, width=4)
            draw.rectangle([px - 16, py - 30, px + 16, py + 25], fill=(135, 206, 250)) # Screen glow
        elif prop == "coffee":
            px = cx + 130
            py = shoulder_y + 20
            draw.rectangle([px - 25, py - 30, px + 25, py + 30], fill=(230, 230, 230), outline=black, width=5)
            draw.arc([px + 15, py - 20, px + 40, py + 15], start=270, end=90, fill=black, width=5) # Handle
        elif prop == "laptop":
            px = cx
            py = pelvis_y + 20
            draw.line([(px - 70, py), (px + 70, py)], fill=(70, 70, 70), width=10) # Base
            draw.line([(px - 40, py), (px - 50, py - 70)], fill=(120, 120, 120), width=8) # Screen
        elif prop == "question_mark":
            # Big yellow question mark floating above head
            qx = cx + 80
            qy = head_cy - 120
            draw.arc([qx - 25, qy - 40, qx + 25, qy], start=180, end=360, fill=(255, 180, 0), width=12)
            draw.line([(qx + 25, qy - 20), (qx, qy + 15)], fill=(255, 180, 0), width=12)
            draw.ellipse([qx - 6, qy + 35, qx + 6, qy + 47], fill=(255, 180, 0))
        elif prop == "exclamation":
            ex = cx + 80
            ey = head_cy - 120
            draw.line([(ex, ey - 50), (ex, ey + 15)], fill=(255, 50, 50), width=14)
            draw.ellipse([ex - 7, ey + 30, ex + 7, ey + 44], fill=(255, 50, 50))

    def render_frame(self, scene_data: Dict[str, Any], progress: float, word_highlight: Optional[str] = None) -> Image.Image:
        """Renders a single 1080x1920 video frame."""
        img = Image.new("RGB", (self.width, self.height), (255, 255, 255))
        draw = ImageDraw.Draw(img)

        bg = scene_data.get("background", "minimal_gradient")
        expression = scene_data.get("expression", "neutral")
        action = scene_data.get("action", "talking")
        prop = scene_data.get("prop", "none")
        camera_effect = scene_data.get("camera_effect", "static")

        # Subtle procedural speech bounce (sin wave)
        bounce_y = math.sin(progress * math.pi * 8) * 12
        mouth_open = (int(progress * 14) % 2 == 0)

        # Camera Shake Effect on dramatic moments
        shake_x = 0
        shake_y = 0
        if camera_effect == "shake":
            shake_x = random.randint(-15, 15)
            shake_y = random.randint(-10, 10)

        self.draw_background(draw, bg, time_offset=progress)
        self.draw_character(
            draw,
            cx=self.width * 0.5 + shake_x,
            cy=self.height * 0.55 + shake_y,
            expression=expression,
            action=action,
            prop=prop,
            bounce_y=bounce_y,
            mouth_open=mouth_open
        )

        return img

renderer_engine = StickFigureRenderer()
