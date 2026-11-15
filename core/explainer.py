"""Cinematic explainer renderer (RENDER_MODE=explainer).

Pipeline per video:
  narration (one TTS take, gaps shortened) -> shot plan from word timings (a shot every 2-3 s)
  -> stills (kit / gemini_image / pollinations / procedural) and evidence props -> depth maps
  -> per-frame 2.5D camera + cast + transitions + single-word captions -> ffmpeg (H.264 + AAC)
  -> quality gate report, contact sheet, preview GIF.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw

from core import audio_mix
from core.camera25d import (Camera25D, CamParams, alpha_over, camera_params, flash, motion_blur_h,
                            speed_lines, zoom_blur)
from core.captions_word import SAFE_BOTTOM, SAFE_TOP, WordCaptioner, load_font, punch_text_tile
from core.cast import get_cast
from core.config import CAPTION_STYLE, FPS, MAX_IMAGES_PER_VIDEO, OUTPUT_DIR, VIDEO_HEIGHT, VIDEO_WIDTH
from core.depth import get_estimator
from core.images import CANVAS_SIZE, ImageManager, is_blank
from core.props_text import render_prop
from core.quality_check import enforce, evaluate
from core.renderer import get_ffmpeg_binary
from core.tts import tts

SPLIT_OVER = 3.6        # scenes longer than this become two shots
WHIP_T = 0.12           # each side of a whip pan
ZOOM_T = 0.16
FLASH_T = 0.18
SPEED_T = 0.30
ALT_MOVES = {"dolly_in": "pan_right", "dolly_out": "pan_left", "pan_left": "dolly_in", "pan_right": "crane_up",
             "crane_up": "dolly_out", "whip": "dolly_in", "static_punch": "orbit", "fly_through": "pan_left",
             "orbit": "dolly_in", "push_flat": "push_flat"}


@dataclass
class Shot:
    index: int
    scene: int
    start: float
    end: float
    camera: str
    kind: str                     # image | prop
    plate_key: str
    sub: int = 0                  # 0 = first shot of scene, 1 = cut-in
    transition_in: str = "cut"    # cut | whip | zoom | flash | speed
    characters: List[Dict] = field(default_factory=list)
    provider: str = ""

    @property
    def duration(self) -> float:
        return self.end - self.start


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40] or "video"


class ExplainerRenderer:
    def __init__(self, width: int = VIDEO_WIDTH, height: int = VIDEO_HEIGHT, fps: int = FPS):
        self.W, self.H, self.fps = width, height, fps
        self.ffmpeg = get_ffmpeg_binary()
        self.last_report: Optional[Dict] = None
        self.last_workdir: Optional[Path] = None
        self._thumb_frame: Optional[np.ndarray] = None

    # ------------------------------------------------------------------ public API
    def render_short(self, script: Dict, output_path: str) -> str:
        t_start = time.time()
        topic = script.get("title", "video")
        work = OUTPUT_DIR / "explainer" / f"{_slug(topic)}_{time.strftime('%Y%m%d_%H%M%S')}"
        work.mkdir(parents=True, exist_ok=True)
        self.last_workdir = work
        seed = int(hashlib.sha256(topic.encode()).hexdigest()[:8], 16)
        scenes = script["scenes"]
        palette = script.get("palette") or []
        timings_log: Dict[str, float] = {}

        # 1) Narration ------------------------------------------------------
        t0 = time.time()
        texts = [s["narration"] for s in scenes]
        mp3 = str(work / "narration_raw.mp3")
        raw_timings = tts.synthesize(" ".join(texts), mp3)
        if not raw_timings:
            raise RuntimeError("[Explainer] TTS returned no word timings")
        audio = audio_mix.decode_to_mono(self.ffmpeg, mp3)
        words, _ = audio_mix.align_words(texts, raw_timings)
        audio, words, gaps_removed = audio_mix.compress_gaps(audio, words)
        speech_end = len(audio) / audio_mix.SR
        total = speech_end + 0.45
        # Pad with an inaudible noise floor (-80 dB), not digital zero: ffmpeg's sidechaincompress
        # mutes the music bed when its sidechain is exactly 0 (measured: mix fell to -180 dB).
        pad = np.random.default_rng(seed).normal(0, 1e-4, int((total - speech_end) * audio_mix.SR) + 1).astype(np.float32)
        audio = np.concatenate([audio, pad])
        audio[np.abs(audio) < 1e-6] = 1e-4
        n_frames = int(total * self.fps)
        total = n_frames / self.fps
        timings_log["narration"] = time.time() - t0
        print(f"[Explainer] Narration {speech_end:.1f}s, {len(words)} words, {len(gaps_removed)} pause(s) shortened")

        # 2) Shot plan ------------------------------------------------------
        shots = self._plan_shots(scenes, words, total)

        # 3) Plates (images, props) + depth ---------------------------------
        t0 = time.time()
        images = ImageManager()
        cam = Camera25D(self.W, self.H, grain_sigma=3.0, seed=seed % 1000)
        estimator = get_estimator()
        plates: Dict[str, Dict] = {}
        plate_info: Dict[str, Dict] = {}
        props_report: List[Dict] = []
        generated = 0
        reused = 0
        for sc_i, sc in enumerate(scenes):
            key = f"s{sc_i}"
            if sc.get("evidence_prop"):
                img, rep = render_prop(sc["evidence_prop"], palette, seed + sc_i)
                rep["scene"] = sc_i
                props_report.append(rep)
                plate_info[key] = {"provider": "props", "blank": False}
                depth = estimator.estimate(img, flat=True)
                plates[key] = cam.prepare(np.asarray(img), depth)
                continue
            painted = [k for k, v in plate_info.items() if v["provider"].split(" ")[0] in ("kit", "gemini_image", "pollinations")]
            remote_alive = any(p.enabled for p in images.providers if p.name in ("kit", "gemini_image", "pollinations"))
            # Budget reached, or remote providers gone: reuse painted plates rather than mixing in
            # procedural art (which clashes with the painted look) once we have enough variety.
            if generated >= MAX_IMAGES_PER_VIDEO or (not remote_alive and len(painted) >= 4):
                src = self._best_reuse(sc, scenes, plate_info)
                plates[key] = plates[src]
                plate_info[key] = {"provider": f"reuse:{plate_info[src]['provider']}", "blank": plate_info[src]["blank"], "reuse_of": src}
                reused += 1
                continue
            res = images.get(sc, palette, seed + sc_i)
            generated += 1
            img = self._grade(res.image)
            depth = estimator.estimate(img)
            plates[key] = cam.prepare(np.asarray(img), depth)
            plate_info[key] = {"provider": res.provider + (" (cache)" if res.cached else ""), "blank": is_blank(img)}
            print(f"[Explainer] Plate {sc_i + 1}/{len(scenes)}: {plate_info[key]['provider']}")
        for s in shots:
            s.provider = plate_info[s.plate_key]["provider"]
        timings_log["images_depth"] = time.time() - t0

        # 4) Sound design + mix --------------------------------------------
        t0 = time.time()
        events = self._sfx_events(shots, scenes)
        nar_wav, mus_wav, sfx_wav, mix_wav = (str(work / n) for n in ("narration.wav", "music.wav", "sfx.wav", "mix.wav"))
        audio_mix.write_wav(nar_wav, audio)
        audio_mix.write_wav(mus_wav, audio_mix.music_bed(total + 0.1, seed % 1000))
        audio_mix.write_wav(sfx_wav, audio_mix.sfx_track(total + 0.1, events))
        audio_mix.mix(self.ffmpeg, nar_wav, mus_wav, sfx_wav, mix_wav)
        env = audio_mix.envelope(audio, self.fps, n_frames)
        timings_log["audio"] = time.time() - t0

        # 5) Frames -> ffmpeg ------------------------------------------------
        t0 = time.time()
        metrics = self._render_frames(shots, scenes, plates, cam, words, env, script, mix_wav, output_path, n_frames, work, seed)
        timings_log["frames_encode"] = time.time() - t0

        # 6) Quality gate ----------------------------------------------------
        audio_m = audio_mix.measure(self.ffmpeg, mix_wav)
        metrics.update({
            "duration_s": total, "width": self.W, "height": self.H, "safe_top": SAFE_TOP, "safe_bottom": SAFE_BOTTOM,
            "audio": audio_m, "fact_flags": script.get("fact_flags", []), "props": props_report,
            "narration_gaps_removed": gaps_removed, "image_providers": images.summary(),
            "reused_images": reused, "words": len(words), "render_seconds": round(time.time() - t_start, 1),
        })
        report = evaluate(metrics)
        report["timings_s"] = {k: round(v, 1) for k, v in timings_log.items()}
        report["shots"] = [{"index": s.index, "scene": s.scene, "start": round(s.start, 2), "duration": round(s.duration, 2),
                            "camera": s.camera, "kind": s.kind, "transition_in": s.transition_in, "provider": s.provider,
                            "characters": [c["name"] + ":" + c["pose"] for c in s.characters]} for s in shots]
        report["image_providers"] = images.summary()
        report["images_generated"] = generated
        report["props"] = props_report
        report["video"] = self._probe(output_path)
        report["contact_sheet"] = str(work / "contact_sheet.png")
        report["preview_gif"] = str(work / "preview.gif")
        self.last_report = report
        enforce(report, work / "quality_report.json")
        return output_path

    def generate_thumbnail(self, script: Dict, video_path: str, output_thumbnail_path: str) -> str:
        Path(output_thumbnail_path).parent.mkdir(parents=True, exist_ok=True)
        if self._thumb_frame is not None:
            Image.fromarray(self._thumb_frame).save(output_thumbnail_path, "JPEG", quality=90)
        else:
            subprocess.run([self.ffmpeg, "-y", "-v", "error", "-ss", "1", "-i", video_path, "-frames:v", "1", output_thumbnail_path])
        return output_thumbnail_path

    # ------------------------------------------------------------------ planning
    def _plan_shots(self, scenes: List[Dict], words: List[Dict], total: float) -> List[Shot]:
        starts = []
        for i in range(len(scenes)):
            w = next((w for w in words if w["scene"] == i), None)
            starts.append(w["start"] if w else None)
        # Fill scenes that got no aligned words by interpolation
        known = [(i, s) for i, s in enumerate(starts) if s is not None]
        for i in range(len(starts)):
            if starts[i] is None:
                prev = max((k for k in known if k[0] < i), default=(0, 0.0), key=lambda k: k[0])
                nxt = min((k for k in known if k[0] > i), default=(len(starts), total), key=lambda k: k[0])
                starts[i] = prev[1] + (nxt[1] - prev[1]) * (i - prev[0]) / max(1, nxt[0] - prev[0])
        starts[0] = 0.0
        bounds = [max(0.0, s - 0.08) if i else 0.0 for i, s in enumerate(starts)] + [total]
        shots: List[Shot] = []
        for i, sc in enumerate(scenes):
            a, b = bounds[i], bounds[i + 1]
            if b - a < 0.05:
                continue
            is_prop = bool(sc.get("evidence_prop"))
            camera = "push_flat" if is_prop else sc.get("camera", "dolly_in")
            pieces = [(a, b)]
            if b - a > SPLIT_OVER:
                mid = a + (b - a) / 2
                pieces = [(a, mid), (mid, b)]
            for j, (pa, pb) in enumerate(pieces):
                cam = camera if j == 0 else ALT_MOVES.get(camera, "dolly_in")
                shots.append(Shot(len(shots), i, pa, pb, cam, "prop" if is_prop else "image", f"s{i}", j,
                                  characters=[] if is_prop else list(sc.get("characters") or [])))
        # Transitions
        for k in range(1, len(shots)):
            prev, cur = shots[k - 1], shots[k]
            sc = scenes[cur.scene]
            if cur.sub == 1:
                cur.transition_in = "cut"
            elif sc.get("emotion_beat") in ("reveal", "twist", "shock"):
                cur.transition_in = "flash"
            elif cur.camera == "whip":
                cur.transition_in = "whip"
            elif cur.kind == "prop":
                cur.transition_in = "zoom"
            elif prev.kind == "prop":
                cur.transition_in = "whip"
            else:
                cur.transition_in = ("cut", "speed", "cut", "whip")[k % 4]
        return shots

    def _best_reuse(self, sc: Dict, scenes: List[Dict], info: Dict[str, Dict]) -> str:
        words = set(re.findall(r"[a-z]{4,}", sc.get("shot_prompt", "").lower()))
        best, score = None, -1
        painted_only = any(m["provider"].split(" ")[0] not in ("procedural", "props") and "reuse_of" not in m for m in info.values())
        used = {m.get("reuse_of") for m in info.values()}
        for key, meta in info.items():
            if meta["provider"] == "props" or "reuse_of" in meta:
                continue
            if painted_only and meta["provider"].startswith("procedural"):
                continue
            other = set(re.findall(r"[a-z]{4,}", scenes[int(key[1:])].get("shot_prompt", "").lower()))
            s = len(words & other) - (2 if key in used else 0)
            if s > score:
                best, score = key, s
        return best

    def _grade(self, img: Image.Image) -> Image.Image:
        """Push toward the saturated painterly look: +saturation, gentle contrast."""
        hsv = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2HSV).astype(np.float32)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.18, 0, 255)
        out = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB).astype(np.float32)
        out = np.clip((out - 128) * 1.06 + 128, 0, 255)
        return Image.fromarray(out.astype(np.uint8))

    def _sfx_events(self, shots: List[Shot], scenes: List[Dict]) -> List[Tuple[float, str]]:
        ev: List[Tuple[float, str]] = []
        for s in shots:
            if s.index == 0:
                continue
            if s.transition_in == "whip":
                ev.append((s.start - 0.22, "whoosh"))
            elif s.transition_in == "flash":
                if s.start > 1.2:
                    ev.append((s.start - 1.0, "riser"))
                ev.append((s.start - 0.02, "hit"))
            elif s.transition_in == "zoom":
                ev.append((s.start - 0.15, "whoosh"))
                ev.append((s.start + 0.05, "paper"))
            elif s.transition_in == "speed":
                ev.append((s.start - 0.05, "whoosh"))
        for s in shots:
            sc = scenes[s.scene]
            if s.sub == 0 and sc.get("punch_text"):
                ev.append((s.start + 0.15, "pop"))
            if s.sub == 0 and sc.get("sfx") in ("hit", "riser", "pop", "paper", "whoosh"):
                if all(abs(t - s.start) > 0.35 for t, _ in ev):
                    ev.append((s.start, sc["sfx"]))
        return sorted(ev)

    # ------------------------------------------------------------------ rendering
    def _char_layout(self, shot: Shot) -> List[Dict]:
        chars = shot.characters
        if not chars:
            return []
        close = len(chars) == 1 and shot.camera in ("dolly_in", "static_punch", "orbit")
        R = 150 if close else (100 if len(chars) == 1 else 84)
        # Keep the head (centre at feet - 4.6R, radius ~1R plus hat) fully above the caption line at 70% H,
        # so single-word captions land on the body/legs, never on the face.
        caption_top = self.H * 0.70 - 80
        feet_y = caption_top - 1.35 * R + 4.6 * R
        xs = {"left": 0.27, "center": 0.5, "right": 0.73}
        out = []
        used = set()
        for i, c in enumerate(chars):
            pos = c.get("position", "center")
            if len(chars) == 2 and pos in used:
                pos = "right" if pos != "right" else "left"
            used.add(pos)
            fx = xs[pos] if len(chars) > 1 or not close else 0.5
            # canvas-space anchor (output coords at neutral camera mapped into the canvas)
            ax = (CANVAS_SIZE[0] - 1) / 2 + (fx * self.W - (self.W - 1) / 2)
            ay = (CANVAS_SIZE[1] - 1) / 2 + (feet_y - (self.H - 1) / 2)
            out.append({**c, "position": pos, "R": R, "ax": ax, "ay": ay, "depth": 0.85, "speaker": i == 0,
                        "mirror": pos == "right", "bob_phase": (hash(c["name"]) % 100) / 100})
        return out

    def _render_frames(self, shots, scenes, plates, cam: Camera25D, words, env, script, mix_wav, output_path,
                       n_frames, work: Path, seed: int) -> Dict:
        cast = get_cast()
        captioner = WordCaptioner(self.W, self.H, style=CAPTION_STYLE)
        emphasis = script.get("emphasis_words", [])
        lines_overlay = speed_lines(self.W, self.H, seed)
        layouts = {s.index: self._char_layout(s) for s in shots}
        rng = random.Random(seed)

        cmd = [self.ffmpeg, "-y", "-v", "error", "-f", "rawvideo", "-vcodec", "rawvideo", "-s", f"{self.W}x{self.H}",
               "-pix_fmt", "rgb24", "-r", str(self.fps), "-i", "-", "-i", mix_wav,
               # Grain is incompressible: cap the bitrate (CRF 20 uncapped gave ~33 Mbps / 228 MB per video)
               "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
               "-maxrate", "6M", "-bufsize", "12M", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", "-shortest", "-movflags", "+faststart", output_path]
        log = open(work / "ffmpeg.log", "w")
        pipe = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log)

        # Preview GIF windows: first whip boundary and the longest dolly-type shot
        whip = next((s for s in shots if s.transition_in == "whip"), None)
        dolly = max((s for s in shots if s.camera in ("dolly_in", "dolly_out", "fly_through")), key=lambda s: s.duration, default=None)
        gif_windows = []
        if whip:
            gif_windows.append((whip.start - 1.5, whip.start + 1.5))
        if dolly:
            c = (dolly.start + dolly.end) / 2
            gif_windows.append((c - 1.5, c + 1.5))
        gif_frames: List[Image.Image] = []
        contact: Dict[int, np.ndarray] = {}

        prev_small = None
        static_run = static_max = 0
        static_at = 0.0
        shot_i = 0
        word_i = -1
        shake_until, shake_amp = -1.0, 0.0
        for f in range(n_frames):
            t = f / self.fps
            while shot_i < len(shots) - 1 and t >= shots[shot_i + 1].start:
                shot_i += 1
                if shots[shot_i].transition_in == "flash":
                    shake_until, shake_amp = t + 0.35, 22.0
            s = shots[shot_i]
            u = (t - s.start) / max(s.duration, 1e-3)
            p = camera_params(s.camera, u)
            if s.sub == 1 and s.kind == "prop":  # insert close-up on the text area of the prop
                p = CamParams(p.zoom * 1.5, 0.0, p.sx, p.sy - 170, 0.0, 0.0)
            elif s.sub == 1:  # cut-in: tighter framing, offset
                p = CamParams(p.zoom * 1.15, p.depth_zoom, p.sx + 26, p.sy - 30, p.px, p.py)

            blur_k, zblur, fl, sl = 0, 0.0, 0.0, 0.0
            nxt = shots[shot_i + 1] if shot_i + 1 < len(shots) else None
            tin = t - s.start
            tout = s.end - t
            if nxt and nxt.transition_in == "whip" and tout < WHIP_T:
                k = 1 - tout / WHIP_T
                p.sx += (k ** 2) * self.W * 0.9
                blur_k = int(10 + 90 * k)
            if s.transition_in == "whip" and tin < WHIP_T:
                k = 1 - tin / WHIP_T
                p.sx -= (k ** 2) * self.W * 0.9
                blur_k = max(blur_k, int(10 + 90 * k))
            if nxt and nxt.transition_in == "zoom" and tout < ZOOM_T:
                k = 1 - tout / ZOOM_T
                p.zoom *= 1 + 0.7 * k * k
                zblur = 0.25 * k
            if s.transition_in == "zoom" and tin < ZOOM_T:
                k = 1 - tin / ZOOM_T
                p.zoom *= 1 + 0.25 * k
                zblur = max(zblur, 0.2 * k)
            if s.transition_in == "flash" and tin < FLASH_T:
                fl = 1 - tin / FLASH_T
            if s.transition_in == "speed" and tin < SPEED_T:
                sl = 1 - tin / SPEED_T
            shake = (0.0, 0.0)
            if t < shake_until:
                a = shake_amp * (shake_until - t) / 0.35
                shake = (rng.uniform(-a, a), rng.uniform(-a, a))

            plate = plates[s.plate_key]
            frame = cam.render(plate, p, shake)

            # Characters
            for c in layouts[s.index]:
                ox, oy, z = cam.project_point(plate, p, c["ax"] + shake[0] * 0, c["ay"], c["depth"])
                R = max(24, int(round(c["R"] * z / 3) * 3))
                speaking = c["speaker"] and env[f] > 0.32
                mouth = speaking and (f // 3) % 2 == 0
                blink = ((t + c["bob_phase"] * 3) % 3.1) < 0.12
                spr = cast.sprite(c["name"], c["pose"], mouth, blink, R, (f // 4) % 6)
                if c["mirror"]:
                    spr = spr[:, ::-1]
                if s.sub == 0 and scenes[s.scene].get("emotion_beat") in ("reveal", "twist", "shock") and tin < 0.3:
                    q = math.sin(math.pi * tin / 0.3)
                    spr = cv2.resize(spr, (max(1, int(spr.shape[1] * (1 - 0.08 * q))), max(1, int(spr.shape[0] * (1 + 0.14 * q)))))
                bob = math.sin(2 * math.pi * (t * 1.5 + c["bob_phase"])) * 0.04 * R
                jitter = math.sin(t * 70) * 3 if c["pose"] == "scared" else 0
                h, w = spr.shape[:2]
                alpha_over(frame, spr, int(ox - w / 2 + jitter), int(oy - h + bob))

            if blur_k:
                frame = motion_blur_h(frame, blur_k)
            if zblur:
                frame = zoom_blur(frame, zblur)

            # Static-frame detector (before grain/captions, which always change)
            small = cv2.cvtColor(cv2.resize(frame, (54, 96), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2GRAY).astype(np.float32)
            if prev_small is not None and float(np.mean(np.abs(small - prev_small))) < 0.08:
                static_run += 1
                if static_run > static_max:
                    static_max, static_at = static_run, t
            else:
                static_run = 0
            prev_small = small

            frame = cam.post(frame, f)
            if fl:
                frame = flash(frame, fl * 0.9)
            if sl:
                alpha_over(frame, lines_overlay, 0, 0, opacity=sl)

            sc = scenes[s.scene]
            if sc.get("punch_text") and s.sub == 0 and 0.12 <= tin <= 1.15:
                pt = punch_text_tile(sc["punch_text"])
                k = tin - 0.12
                sc_ = 0.6 + 0.55 * min(k / 0.12, 1) - 0.15 * min(max((k - 0.12) / 0.1, 0), 1)
                fade = 1.0 if tin < 0.95 else max(0.0, 1 - (tin - 0.95) / 0.2)
                pt = cv2.resize(pt, (max(1, int(pt.shape[1] * sc_)), max(1, int(pt.shape[0] * sc_))))
                if pt.shape[1] > self.W * 0.9:
                    r_ = self.W * 0.9 / pt.shape[1]
                    pt = cv2.resize(pt, (int(pt.shape[1] * r_), int(pt.shape[0] * r_)))
                alpha_over(frame, pt, (self.W - pt.shape[1]) // 2, max(SAFE_TOP + 20, int(self.H * 0.27) - pt.shape[0] // 2), opacity=fade)

            if self._thumb_frame is None and s.index >= 1 and layouts[s.index] and abs(u - 0.5) < 0.02:
                self._thumb_frame = frame.copy()

            while word_i + 1 < len(words) and t >= words[word_i + 1]["start"]:
                word_i += 1
            if word_i >= 0 and t <= words[word_i]["end"] + 0.6:
                captioner.draw(frame, words, word_i, t, emphasis)

            if s.index not in contact and u >= 0.5:
                contact[s.index] = cv2.resize(frame, (216, 384), interpolation=cv2.INTER_AREA)
            if f % 3 == 0 and any(a <= t < b for a, b in gif_windows):
                gif_frames.append(Image.fromarray(cv2.resize(frame, (270, 480), interpolation=cv2.INTER_AREA)))

            try:
                pipe.stdin.write(frame.tobytes())
            except BrokenPipeError:
                break
        pipe.stdin.close()
        rc = pipe.wait()
        log.close()
        if rc != 0 or not os.path.exists(output_path):
            raise RuntimeError(f"[Explainer] FFmpeg encode failed (exit {rc}): {(work / 'ffmpeg.log').read_text()[-800:]}")

        self._contact_sheet(shots, contact, work / "contact_sheet.png")
        if gif_frames:
            gif_frames[0].save(work / "preview.gif", save_all=True, append_images=gif_frames[1:], duration=100, loop=0, optimize=True)
        return {
            "shots": [{"index": s.index, "duration": s.duration, "camera": s.camera, "kind": s.kind,
                       "blank": False if s.kind == "prop" else None} for s in shots],
            "static_max_run_s": static_max / self.fps, "static_max_run_at": static_at,
            "caption_bboxes": captioner.bboxes,
        }

    def _contact_sheet(self, shots: List[Shot], tiles: Dict[int, np.ndarray], path: Path):
        cols = 6
        tw, th, lh = 216, 384, 58
        rows = math.ceil(len(shots) / cols)
        sheet = Image.new("RGB", (cols * tw + (cols + 1) * 8, rows * (th + lh) + (rows + 1) * 8), (18, 18, 24))
        d = ImageDraw.Draw(sheet)
        f = load_font(17)
        for i, s in enumerate(shots):
            x, y = 8 + (i % cols) * (tw + 8), 8 + (i // cols) * (th + lh + 8)
            if s.index in tiles:
                sheet.paste(Image.fromarray(tiles[s.index]), (x, y))
            d.text((x + 2, y + th + 3), f"#{s.index} {s.duration:.1f}s {s.camera}", font=f, fill=(240, 240, 240))
            d.text((x + 2, y + th + 25), f"{s.transition_in} | {s.provider[:18]}", font=f, fill=(170, 200, 255))
        sheet.save(path)

    def _probe(self, path: str) -> Dict:
        res = subprocess.run([self.ffmpeg, "-hide_banner", "-i", path], stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)
        info = {}
        m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", res.stderr)
        if m:
            info["duration_s"] = round(int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)), 2)
        v = re.search(r"Video: (\w+).*?, (\w+)\(?.*?, (\d+)x(\d+)", res.stderr)
        if v:
            info.update({"video_codec": v.group(1), "pix_fmt": v.group(2), "size": f"{v.group(3)}x{v.group(4)}"})
        a = re.search(r"Audio: (\w+).*?, (\d+) Hz, (\w+)", res.stderr)
        if a:
            info.update({"audio_codec": a.group(1), "sample_rate": int(a.group(2)), "channels": a.group(3)})
        info["size_bytes"] = os.path.getsize(path)
        return info


explainer_renderer = ExplainerRenderer()
