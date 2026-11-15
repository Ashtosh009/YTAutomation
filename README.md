# ⚡ Automated Animated Shorts Channel (Stick-Figure Storytime)

A fully automated, 100% free-tier YouTube Shorts pipeline powered by **GitHub Actions**, **Gemini API**, **Microsoft Edge TTS**, and a custom **Stick Figure Animation Engine**.

---

## 🏗️ Architecture & Stack

| Layer | Free Tool | Role |
|---|---|---|
| **Worker / Runner** | **GitHub Actions** (cron + workflow_dispatch) | Automated video generation & scheduled publishing |
| **Animation Engine** | **Custom Python Vector Engine** (Pillow + FFmpeg) | Generates dynamic 9:16 stick-figure comedy animations |
| **Voice Narration** | **Microsoft Edge TTS** (`edge-tts`) | Natural human-like speech with word boundary timestamps |
| **Captions** | **Karaoke Captions Module** | Active word highlighting with high-contrast outlines |
| **Script & Metadata** | **Google Gemini 1.5 Flash** (Free AI Studio) | High-hook viral comedy scripts, titles, tags, hashtags |
| **Queue & DB** | **Supabase Free Tier** (or local SQLite) | Stores ideas, script storyboards, status, review queue |
| **Control Panel** | **Vercel** (`web/`) | Morning review queue & 1-click GitHub Actions trigger |
| **Publishing** | **YouTube Data API v3** | Scheduled publishing at 09:00, 14:00, 19:00 IST |

---

## 📁 Project Structure

```
YTanimation/
├── .github/
│   └── workflows/
│       └── pipeline.yml       # GitHub Actions worker (cron + manual trigger)
├── core/
│   ├── config.py              # Configuration & path management
│   ├── db.py                  # Supabase & SQLite database client
│   ├── llm.py                 # Gemini script & scene storyboard generator
│   ├── tts.py                 # Edge-TTS engine with word-level boundary detection
│   ├── stick_engine.py        # 1080x1920 stick figure vector animator & scene builder
│   ├── captions.py            # Karaoke-style dynamic animated captions
│   ├── renderer.py            # FFmpeg frame pipe & video composer
│   └── youtube.py             # YouTube Data API v3 OAuth & scheduled uploader
├── web/
│   ├── index.html             # Vercel control panel & morning review dashboard
│   └── api/
│       └── trigger.js         # Vercel serverless function to trigger GitHub Actions
├── data/                      # Local SQLite database (if Supabase not set)
├── output/                    # Rendered 1080x1920 Shorts MP4 files
├── requirements.txt           # Python dependencies
├── supabase_schema.sql        # 1-click database schema for Supabase
├── run_pipeline.py            # CLI entrypoint for test, review, and publishing
└── .env.example               # Environment variables template
```

---

## 🚀 Quickstart: Local Setup & Test

### 1. Create Virtualenv & Install Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment (`.env`)
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Fill in your `GEMINI_API_KEY` from [Google AI Studio](https://aistudio.google.com).

### 3. Generate Your First Stick Figure Short Locally
```bash
# Generate a test short
python run_pipeline.py --mode generate --topic "Trying to wake up at 5 AM"
```
The output video will be generated at `output/short_<id>_<timestamp>.mp4`!

---

## 📋 Morning Review Queue Workflow

1. **Automatic Batch Generation**:
   GitHub Actions runs early morning and produces 3 finished Shorts in your review queue (`ready_for_review`).
2. **Reviewing**:
   - Open your Vercel dashboard or run:
     ```bash
     python run_pipeline.py --mode review
     ```
   - Watch the preview, edit the title/description if desired.
3. **Approval**:
   - Click **Approve** in the Vercel panel or run:
     ```bash
     python run_pipeline.py --approve <video_id>
     ```
4. **Scheduled Upload**:
   - The worker automatically publishes your approved videos to YouTube at your 3 daily slots:
     - Slot 1: **09:00 IST**
     - Slot 2: **14:00 IST**
     - Slot 3: **19:00 IST**

---

## 🔑 YouTube API Setup (One-Time)

1. Go to [Google Cloud Console](https://console.cloud.google.com).
2. Create a project and enable **YouTube Data API v3**.
3. Under **APIs & Services > OAuth consent screen**, set user type to **External** and add your Gmail as a **Test User**.
4. Under **Credentials**, click **Create Credentials > OAuth client ID > Desktop app**.
5. Download the JSON and save it as `client_secret.json` in this project directory.
6. Run the one-time local authentication:
   ```bash
   python -c "from core.youtube import youtube_uploader; youtube_uploader.get_authenticated_service()"
   ```
   A browser window will open. Sign in and grant permission. This will generate `token.json`.
7. For GitHub Actions: Convert `token.json` to base64:
   ```bash
   base64 -i token.json
   ```
   Add the output string as a GitHub Secret named `YOUTUBE_TOKEN_BASE64`.

---

## 🤖 GitHub Actions Configuration

In your GitHub repository, navigate to **Settings > Secrets and variables > Actions** and add the following repository secrets:

- `GEMINI_API_KEY`: Your Google AI Studio API key.
- `YOUTUBE_TOKEN_BASE64`: The base64-encoded `token.json`.
- `SUPABASE_URL`: (Optional) Your Supabase project URL.
- `SUPABASE_KEY`: (Optional) Your Supabase anon/service role key.

You can trigger a test batch run directly under **Actions > Automated Shorts Pipeline > Run workflow**.
