import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# LLM
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# gemini-flash-latest stopped responding (>120s timeouts, 2026-11-15); gemini-3.5-flash answers in ~13s.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

# Database / Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "shorts")
SQLITE_DB_PATH = BASE_DIR / "data" / "pipeline.db"

# Video Configuration
VIDEO_WIDTH = int(os.getenv("VIDEO_WIDTH", "1080"))
VIDEO_HEIGHT = int(os.getenv("VIDEO_HEIGHT", "1920"))
FPS = int(os.getenv("FPS", "30"))

# Voice settings (Edge TTS default voices: en-US-ChristopherNeural, en-US-GuyNeural, en-US-AriaNeural)
DEFAULT_VOICE = os.getenv("DEFAULT_VOICE", "en-US-ChristopherNeural")

# YouTube settings
YOUTUBE_CLIENT_SECRETS_FILE = os.getenv("YOUTUBE_CLIENT_SECRETS_FILE", str(BASE_DIR / "client_secret.json"))
YOUTUBE_TOKEN_FILE = os.getenv("YOUTUBE_TOKEN_FILE", str(BASE_DIR / "token.json"))
YOUTUBE_TOKEN_BASE64 = os.getenv("YOUTUBE_TOKEN_BASE64", "")
# Privacy for uploads with no scheduled publish time: public | unlisted | private.
YOUTUBE_DEFAULT_PRIVACY = os.getenv("YOUTUBE_DEFAULT_PRIVACY", "public")

# Output & Assets directory
OUTPUT_DIR = BASE_DIR / "output"
ASSETS_DIR = BASE_DIR / "assets"
DATA_DIR = BASE_DIR / "data"

CACHE_DIR = ASSETS_DIR / "cache"
FONTS_DIR = ASSETS_DIR / "fonts"
KIT_DIR = ASSETS_DIR / "kit"
CAST_DIR = ASSETS_DIR / "cast"

for directory in [OUTPUT_DIR, ASSETS_DIR, DATA_DIR, CACHE_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Render mode
#   explainer: 2.5D "cinematic explainer" (painted stills + depth parallax camera,
#              recurring cast, evidence inserts, single-word captions)
#   kit:       the original stick-figure renderer (core/stick_engine.py)
# ---------------------------------------------------------------------------
RENDER_MODE = os.getenv("RENDER_MODE", "explainer").strip().lower()
CAPTION_STYLE = os.getenv("CAPTION_STYLE", "single_word").strip().lower()  # single_word | highlight_phrase

# Image providers, tried in order. gemini_image is only used if a probe call succeeds.
IMAGE_PROVIDERS = [p.strip() for p in os.getenv("IMAGE_PROVIDERS", "kit,gemini_image,pollinations,procedural").split(",") if p.strip()]
GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
MAX_IMAGES_PER_VIDEO = int(os.getenv("MAX_IMAGES_PER_VIDEO", "14"))
# Wall-clock budget for remote image generation per video (keeps CI under ~12 min/video).
IMAGE_TIME_BUDGET_S = float(os.getenv("IMAGE_TIME_BUDGET_S", "300"))

# Depth model (Depth Anything V2 Small, quantized ONNX, ~27 MB, CPU)
DEPTH_MODEL_URL = os.getenv(
    "DEPTH_MODEL_URL",
    "https://huggingface.co/onnx-community/depth-anything-v2-small/resolve/main/onnx/model_quantized.onnx",
)

# Quality gate: enforce (fail the run) | warn (report only)
QUALITY_GATE = os.getenv("QUALITY_GATE", "enforce").strip().lower()
