import os
import json
import re
from typing import Dict, Any, List
import urllib.request
import urllib.error
from core.config import GEMINI_API_KEY

SYSTEM_PROMPT = """
You are a viral YouTube Shorts writer and animator director specializing in comedic stick figure storytime animations.
Channel style: Relatable, hilarious, high-energy storytelling similar to Jaiden Animations, TheOdd1sOut, or Casually Explained, but concise for 30-45 second Shorts.
Always structure your output strictly as valid JSON matching the requested schema.
"""

SCRIPT_SCHEMA_PROMPT = """
Generate an engaging 30-45 second stick figure comedy Short on the topic: "{topic}".

Guidelines:
1. First 2 seconds MUST have a strong hook (no "Hey guys", jump straight into the awkward/funny situation).
2. Total words: 75 to 110 words maximum (fast, conversational pacing).
3. 4 to 6 distinct scenes.
4. Each scene should specify:
   - "text": Spoken narration or dialogue for this scene.
   - "expression": One of ["neutral", "smug", "shocked", "laughing", "angry", "crying", "derp"]
   - "action": One of ["talking", "explaining", "shrugging", "running", "facepalm", "screaming"]
   - "background": One of ["bedroom", "office", "classroom", "living_room", "park", "minimal_gradient"]
   - "prop": One of ["none", "phone", "coffee", "laptop", "money", "question_mark", "exclamation"]
   - "camera_effect": One of ["static", "zoom_in", "shake"]
5. Metadata:
   - "title": Clickable, curious, under 50 characters, includes 1 emoji.
   - "description": 2-sentence summary + #Shorts #animation #comedy #storytime
   - "tags": 8-10 relevant tags.

Return ONLY raw JSON with keys:
{
  "title": "...",
  "description": "...",
  "tags": ["..."],
  "scenes": [
    {
      "text": "...",
      "expression": "...",
      "action": "...",
      "background": "...",
      "prop": "...",
      "camera_effect": "..."
    }
  ]
}
"""

def generate_script_with_gemini(topic: str) -> Dict[str, Any]:
    """Generates structured script JSON using Gemini API or offline fallback."""
    if not GEMINI_API_KEY:
        print("[LLM] GEMINI_API_KEY not found. Using high-quality default template.")
        return get_fallback_script(topic)

    prompt = SCRIPT_SCHEMA_PROMPT.replace("{topic}", topic)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={GEMINI_API_KEY}"
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": SYSTEM_PROMPT + "\n" + prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "responseMimeType": "application/json"
        }
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            # Clean markdown JSON wraps if present
            cleaned_json = re.sub(r"^```json\s*", "", raw_text.strip())
            cleaned_json = re.sub(r"```$", "", cleaned_json.strip())
            return json.loads(cleaned_json)
    except Exception as e:
        print(f"[LLM] Error calling Gemini API: {e}. Falling back to template.")
        return get_fallback_script(topic)

def get_fallback_script(topic: str) -> Dict[str, Any]:
    """Provides an instant high-retention fallback script for testing without API keys."""
    return {
        "title": f"Why {topic.capitalize()} Always Goes Wrong! 💀",
        "description": f"The painful truth about {topic}. Can anyone else relate? #Shorts #animation #comedy #storytime",
        "tags": ["shorts", "animation", "stickfigure", "comedy", "funny", "storytime", topic.lower()],
        "scenes": [
            {
                "text": f"Nobody ever warns you about what happens when you try {topic}.",
                "expression": "shocked",
                "action": "screaming",
                "background": "bedroom",
                "prop": "question_mark",
                "camera_effect": "shake"
            },
            {
                "text": "At first, you think you have everything completely under control.",
                "expression": "smug",
                "action": "explaining",
                "background": "living_room",
                "prop": "coffee",
                "camera_effect": "static"
            },
            {
                "text": "Then two minutes later, reality hits you right in the face.",
                "expression": "derp",
                "action": "facepalm",
                "background": "office",
                "prop": "laptop",
                "camera_effect": "zoom_in"
            },
            {
                "text": "You check your phone, and suddenly your whole plan is in flames.",
                "expression": "crying",
                "action": "talking",
                "background": "bedroom",
                "prop": "phone",
                "camera_effect": "shake"
            },
            {
                "text": "Moral of the story: pretend you knew what you were doing all along.",
                "expression": "laughing",
                "action": "shrugging",
                "background": "minimal_gradient",
                "prop": "none",
                "camera_effect": "static"
            }
        ]
    }
