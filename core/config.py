import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# LLM
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

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

# Output & Assets directory
OUTPUT_DIR = BASE_DIR / "output"
ASSETS_DIR = BASE_DIR / "assets"
DATA_DIR = BASE_DIR / "data"

for directory in [OUTPUT_DIR, ASSETS_DIR, DATA_DIR]:
    directory.mkdir(parents=True, exist_ok=True)
