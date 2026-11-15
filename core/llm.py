import os
import json
import re
from typing import Dict, Any, List
import urllib.request
import urllib.error
from core.config import GEMINI_API_KEY, GEMINI_MODEL

GEMINI_TIMEOUT = 90  # seconds per attempt
GEMINI_ATTEMPTS = 2

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
    return gemini_json(SYSTEM_PROMPT + "\n" + prompt, temperature=0.7, required_keys=("title", "scenes"))


def gemini_json(prompt: str, temperature: float = 0.7, required_keys=()) -> Dict[str, Any]:
    """Calls Gemini in JSON mode with retries. Raises after GEMINI_ATTEMPTS failures.

    With an API key configured, a Gemini failure must fail the run rather than
    silently publishing a generic fallback template.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("[LLM] GEMINI_API_KEY is not set")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"},
    }
    last_err: Exception = RuntimeError("no attempts made")
    for attempt in range(1, GEMINI_ATTEMPTS + 1):
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY}
            )
            with urllib.request.urlopen(req, timeout=GEMINI_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            # Clean markdown JSON wraps if present
            cleaned_json = re.sub(r"^```json\s*", "", raw_text.strip())
            cleaned_json = re.sub(r"```$", "", cleaned_json.strip())
            result = json.loads(cleaned_json)
            missing = [k for k in required_keys if not result.get(k)]
            if missing:
                raise ValueError(f"Gemini JSON missing {missing} (keys: {sorted(result)})")
            return result
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:300]
            last_err = RuntimeError(f"HTTP {e.code} from {GEMINI_MODEL}: {body}")
        except Exception as e:
            last_err = e
        print(f"[LLM] Gemini attempt {attempt}/{GEMINI_ATTEMPTS} failed ({GEMINI_MODEL}): {last_err}")
    raise RuntimeError(f"[LLM] Gemini call failed after {GEMINI_ATTEMPTS} attempts: {last_err}") from last_err

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


# ===========================================================================
# Explainer mode: fact-grounded, three-pass script (facts -> script -> validator)
# ===========================================================================
EXPLAINER_CAMERAS = ["dolly_in", "dolly_out", "pan_left", "pan_right", "crane_up", "whip", "static_punch", "fly_through", "orbit"]
EXPLAINER_POSES = ["idle", "talking", "shocked", "angry", "thinking", "pointing", "smug", "scared"]
EXPLAINER_PROPS = ["newspaper", "logbook", "map", "calendar", "telegram", "sticky_note", "photo_frame"]
EXPLAINER_BEATS = ["reveal", "twist", "shock", "tension", "humor"]
EXPLAINER_SFX = ["none", "whoosh", "hit", "riser", "pop", "paper"]

FACTS_PROMPT = """You are a careful historical researcher preparing notes for a short explainer video.
Topic: "{topic}"

List only facts that are well documented by reliable sources. Be conservative: if you are not sure
something is documented, mark it "disputed" or "unknown" instead of "established". Popular stories
that are false, embellished or fictional (e.g. from later novels, hoaxes, retellings) go in "myths".

Return JSON:
{{
  "subject": "short name of the subject",
  "facts": [{{"id": "F1", "claim": "one specific documented fact (who/what/when/where/numbers)", "status": "established|disputed|unknown"}}],
  "theories": [{{"id": "T1", "claim": "an explanation people have proposed", "status": "theory"}}],
  "myths": ["popular claim that is false or unsupported"],
  "real_people": ["names of real people involved"]
}}
Give 10-16 facts, 2-5 theories, 0-5 myths."""

SCRIPT_PROMPT = """You write vertical-video explainers for the channel "No Brain Stickman": original mysteries and
"what really happened" stories, told by a small cast of cartoon stick characters.

Topic: "{topic}"
Use ONLY these research notes. Every factual statement must come from an "established" fact. Anything
"disputed", "unknown" or from "theories" MUST be phrased as uncertain ("one theory says...", "nobody knows...").
Never state a myth as fact. Never invent names, numbers, dates, quotes or details that are not in the notes.
NOTES:
{facts}

STRUCTURE (45-55 seconds, {min_words}-{max_words} words total, about 2.7 words per second):
hook (a striking true question or claim in the very first line) -> setup/history -> conflict and escalation ->
the clue or twist -> resolution (what is actually known) -> closing question to the viewer.

SCENES: {min_scenes}-{max_scenes} scenes, each narration 5-10 words (2-3 seconds spoken). A new shot every 2-3 seconds.
Each scene object:
{{
  "narration": "spoken line",
  "fact_ids": ["F1"],
  "shot_prompt": "ENVIRONMENT-ONLY painterly scene: place, objects, weather, light, time of day, camera angle. NO people, NO faces, NO text, NO letters, NO logos, NO real brands",
  "camera": one of {cameras},
  "characters": [{{"name": one of {cast}, "pose": one of {poses}, "position": "left|center|right"}}],
  "evidence_prop": null OR {{"kind": one of {props}, ...fields}},
  "emotion_beat": null OR one of {beats},
  "sfx": one of {sfx},
  "palette_note": "short color/lighting note",
  "punch_text": null OR one big word or number to flash on screen (max 2 in the whole video)
}}
evidence_prop fields by kind (ALL text must be taken from the notes, short and exact):
  newspaper: masthead (generic paper name, not a real newspaper), date, headline (<= 7 words), subhead (<= 9 words)
  logbook: title, date, lines (1-3 lines, <= 8 words each)
  map: title (place/region), labels (2 short place names)
  calendar: month, day, year
  telegram: date, lines (1-3 short lines)
  sticky_note: text (<= 6 words, usually the open question)
  photo_frame: caption (<= 5 words), scene (what the old photo shows, no people)

RULES:
- 4 to 6 scenes have an evidence_prop; never two in a row. Evidence scenes have no characters.
- Use at least 5 different camera moves; use "whip" 2-4 times for fast changes of place.
- Characters appear in at least half of the non-evidence scenes, 0-2 per scene. They are fictional cartoon
  narrators reacting to the story, never depictions of the real people. "Mystery Stickman" is the main character
  and appears most; "Doubtful Dan" doubts theories; "Chief Inspector" gives the official account;
  "Professor Knot" explains science.
- Use emotion_beat "reveal" or "twist" for the key clue (1-3 times total).

Return JSON with keys:
  "title" (under 60 chars, 1 emoji, honest curiosity hook), "description" (2 sentences + "#Shorts #mystery #history #animation"),
  "tags" (8-10), "palette" (3 hex colors: cool sky, warm complementary accent, deep shadow),
  "emphasis_words" (3-6 key words/names/numbers from the narration), "scenes" (list)."""

VALIDATOR_PROMPT = """You are a strict fact-checker. Compare each scene's narration and evidence text with the research notes.
Flag a scene if it states something as fact that is not an "established" fact in the notes, invents a specific
(name, number, date, quote, detail), presents a theory or myth as certain, or contradicts the notes.
Phrasing such as "one theory says", "some believe", "nobody knows" is acceptable for theories.

NOTES:
{facts}

SCENES:
{scenes}

Return JSON:
{{"flags": [{{"scene": <index>, "text": "the problematic words", "problem": "why",
   "fix_narration": "a corrected narration of similar length (5-10 words) that is supported by the notes",
   "fix_prop": null or a corrected evidence_prop object}}],
  "verdict": "pass" or "fail"}}
Return an empty flags list if everything is supported."""


def _validator_scenes(scenes: List[Dict[str, Any]]) -> str:
    rows = []
    for i, s in enumerate(scenes):
        prop = s.get("evidence_prop")
        rows.append({"scene": i, "narration": s.get("narration", ""), "evidence_prop": prop or None})
    return json.dumps(rows, ensure_ascii=False, indent=1)


def _ensure_cast(scenes: List[Dict[str, Any]], cast_names: List[str]) -> None:
    """Guarantee characters in at least half of the non-evidence scenes (the model sometimes omits them).
    Picks who reacts from cues in the narration; the main character fills the rest."""
    main = cast_names[0]
    by_role = {
        "skeptic": next((n for n in cast_names if "dan" in n.lower()), main),
        "authority": next((n for n in cast_names if "inspector" in n.lower()), main),
        "expert": next((n for n in cast_names if "professor" in n.lower()), main),
    }
    open_scenes = [s for s in scenes if not s["evidence_prop"]]
    have = sum(1 for s in open_scenes if s["characters"])
    need = (len(open_scenes) + 1) // 2 - have
    if need <= 0:
        return
    positions = ["left", "right", "center"]
    for i, s in enumerate(open_scenes):
        if need <= 0:
            break
        if s["characters"]:
            continue
        text = s["narration"].lower()
        beat = s.get("emotion_beat")
        if re.search(r"\btheor|some (say|think|believe)|another\b", text):
            who, pose = by_role["skeptic"], "smug" if "another" in text else "thinking"
        elif re.search(r"official|investigat|inquiry|report|superintendent|police|authorit", text):
            who, pose = by_role["authority"], "pointing"
        elif re.search(r"\d|frequency|signal|science|measure|wave|storm|scientist", text):
            who, pose = by_role["expert"], "talking"
        else:
            who, pose = main, "talking"
        if beat in ("reveal", "twist", "shock"):
            pose = "shocked"
        elif text.rstrip().endswith("?"):
            who, pose = main, "thinking"
        elif re.search(r"never|vanish|missing|disappear", text):
            pose = "scared"
        s["characters"] = [{"name": who, "pose": pose, "position": positions[i % 3]}]
        need -= 1


def normalize_explainer_script(script: Dict[str, Any], cast_names: List[str]) -> Dict[str, Any]:
    """Clamp enums, fill defaults, and enforce structural rules the renderer relies on."""
    lower_cast = {n.lower(): n for n in cast_names}
    scenes = []
    for s in script.get("scenes", []):
        narration = re.sub(r"\s+", " ", str(s.get("narration") or s.get("text") or "")).strip()
        if not narration:
            continue
        cam = s.get("camera") if s.get("camera") in EXPLAINER_CAMERAS else "dolly_in"
        chars = []
        for c in (s.get("characters") or [])[:2]:
            name = lower_cast.get(str(c.get("name", "")).lower())
            if not name:
                name = next((v for k, v in lower_cast.items() if str(c.get("name", "")).lower() in k), cast_names[0])
            pose = c.get("pose") if c.get("pose") in EXPLAINER_POSES else "talking"
            pos = c.get("position") if c.get("position") in ("left", "center", "right") else "center"
            chars.append({"name": name, "pose": pose, "position": pos})
        prop = s.get("evidence_prop")
        if isinstance(prop, dict) and prop.get("kind") in EXPLAINER_PROPS:
            chars = []
        else:
            prop = None
        scenes.append({
            "narration": narration,
            "fact_ids": s.get("fact_ids") or [],
            "shot_prompt": str(s.get("shot_prompt") or narration),
            "camera": cam,
            "characters": chars,
            "evidence_prop": prop,
            "emotion_beat": s.get("emotion_beat") if s.get("emotion_beat") in EXPLAINER_BEATS else None,
            "sfx": s.get("sfx") if s.get("sfx") in EXPLAINER_SFX else "none",
            "palette_note": str(s.get("palette_note") or ""),
            "punch_text": (str(s["punch_text"]).strip()[:12] or None) if s.get("punch_text") else None,
        })
    _ensure_cast(scenes, cast_names)
    # At most 2 punch texts
    seen = 0
    for s in scenes:
        if s["punch_text"]:
            seen += 1
            if seen > 2:
                s["punch_text"] = None
    palette = [p for p in (script.get("palette") or []) if re.fullmatch(r"#[0-9a-fA-F]{6}", str(p))][:3]
    if len(palette) < 3:
        palette = ["#2E6FA8", "#F08A3C", "#14213D"]
    script["scenes"] = scenes
    script["palette"] = palette
    script["emphasis_words"] = [str(w) for w in (script.get("emphasis_words") or [])][:8]
    script["tags"] = [str(t) for t in (script.get("tags") or ["shorts", "mystery", "history", "animation"])][:12]
    script["word_count"] = sum(len(s["narration"].split()) for s in scenes)
    script["render_mode"] = "explainer"
    return script


def generate_explainer_script(topic: str, cast_names: List[str], min_words: int = 120, max_words: int = 145) -> Dict[str, Any]:
    """Three passes: verified facts -> script from facts -> validator (with one auto-fix round)."""
    print("[LLM] Pass 1/3: gathering documented facts...")
    facts = gemini_json(FACTS_PROMPT.format(topic=topic), temperature=0.2, required_keys=("facts",))
    facts_txt = json.dumps({k: facts.get(k) for k in ("subject", "facts", "theories", "myths")}, ensure_ascii=False, indent=1)

    print("[LLM] Pass 2/3: writing the script from the facts...")
    prompt = SCRIPT_PROMPT.format(
        topic=topic, facts=facts_txt, min_words=min_words, max_words=max_words, min_scenes=16, max_scenes=20,
        cameras=json.dumps(EXPLAINER_CAMERAS), cast=json.dumps(cast_names), poses=json.dumps(EXPLAINER_POSES),
        props=json.dumps(EXPLAINER_PROPS), beats=json.dumps(EXPLAINER_BEATS), sfx=json.dumps(EXPLAINER_SFX))
    script = normalize_explainer_script(gemini_json(prompt, temperature=0.6, required_keys=("title", "scenes")), cast_names)
    if not (min_words - 15 <= script["word_count"] <= max_words + 15):
        print(f"[LLM] Script has {script['word_count']} words (target {min_words}-{max_words}); regenerating once...")
        script = normalize_explainer_script(gemini_json(
            prompt + f"\n\nIMPORTANT: your previous draft had {script['word_count']} words. Total narration MUST be {min_words}-{max_words} words.",
            temperature=0.6, required_keys=("title", "scenes")), cast_names)

    print("[LLM] Pass 3/3: validating every line against the facts...")
    history = []
    flags: List[Dict[str, Any]] = []
    for round_ in range(2):
        verdict = gemini_json(VALIDATOR_PROMPT.format(facts=facts_txt, scenes=_validator_scenes(script["scenes"])), temperature=0.0)
        flags = [f for f in (verdict.get("flags") or []) if isinstance(f, dict) and isinstance(f.get("scene"), int)
                 and 0 <= f["scene"] < len(script["scenes"])]
        history.append({"round": round_ + 1, "flags": flags})
        if not flags or round_ == 1:
            break
        for f in flags:
            s = script["scenes"][f["scene"]]
            if f.get("fix_narration"):
                s["narration"] = str(f["fix_narration"]).strip()
            if isinstance(f.get("fix_prop"), dict) and f["fix_prop"].get("kind") in EXPLAINER_PROPS:
                s["evidence_prop"] = f["fix_prop"]
        print(f"[LLM] Validator flagged {len(flags)} line(s); applied fixes, re-checking...")
        script = normalize_explainer_script(script, cast_names)
    script["facts"] = facts
    script["fact_check"] = history
    script["fact_flags"] = flags
    print(f"[LLM] Script ready: {len(script['scenes'])} scenes, {script['word_count']} words, {len(flags)} unresolved fact flag(s).")
    return script
