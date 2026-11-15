"""Audio for the explainer mode.

- One continuous edge-tts narration with word timings, aligned back to the script
  tokens (so captions keep punctuation) and to scene boundaries.
- Pauses longer than MAX_GAP are shortened so narration never goes quiet > 0.4 s.
- Synthesized music bed (no licensing), whoosh/hit/riser/pop effects.
- ffmpeg mix: music ducked under the voice (sidechain), loudnorm -14 LUFS, stereo 44.1 kHz.
"""
from __future__ import annotations

import math
import re
import subprocess
import wave
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

SR = 44100
MAX_GAP = 0.30      # longer pauses get shortened ...
KEEP_GAP = 0.22     # ... to this length
LEAD_IN = 0.06


def _norm(w: str) -> str:
    return re.sub(r"[^\w']", "", w.lower()).replace("'", "")


def decode_to_mono(ffmpeg_bin: str, path: str) -> np.ndarray:
    res = subprocess.run([ffmpeg_bin, "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        raise RuntimeError(f"[Audio] decode failed: {res.stderr.decode()[-400:]}")
    return np.frombuffer(res.stdout, np.float32).copy()


def write_wav(path: str, data: np.ndarray):
    data = np.atleast_2d(data.T).T if data.ndim == 1 else data
    pcm = (np.clip(data, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(pcm.shape[1] if pcm.ndim == 2 else 1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


# ---------------------------------------------------------------------------
# Narration
# ---------------------------------------------------------------------------
def align_words(scene_texts: List[str], timings: List[Dict]) -> Tuple[List[Dict], List[int]]:
    """Map TTS word timings back to script tokens. Returns caption words (with punctuation,
    scene index) and the first-word index of each scene."""
    tokens: List[Tuple[str, int]] = []
    for si, text in enumerate(scene_texts):
        for tok in text.split():
            if _norm(tok):
                tokens.append((tok, si))
    words: List[Dict] = []
    j = 0
    for t in timings:
        nw = _norm(t["word"])
        if not nw:
            continue
        match = None
        for k in range(j, min(j + 4, len(tokens))):
            nt = _norm(tokens[k][0])
            if nt == nw or nt.replace("-", "") == nw:
                match = k
                break
        if match is not None:
            tok, si = tokens[match]
            j = match + 1
            words.append({"word": tok, "start": t["start"], "end": t["end"], "scene": si})
        else:  # partial (e.g. hyphen split) or TTS normalisation: keep the spoken word
            si = tokens[min(j, len(tokens) - 1)][1] if tokens else 0
            words.append({"word": t["word"], "start": t["start"], "end": t["end"], "scene": si})
    starts = []
    for si in range(len(scene_texts)):
        idx = next((i for i, w in enumerate(words) if w["scene"] == si), None)
        starts.append(idx if idx is not None else -1)
    return words, starts


def compress_gaps(audio: np.ndarray, words: List[Dict]) -> Tuple[np.ndarray, List[Dict], List[float]]:
    """Shorten pauses between words; shift timings accordingly. Returns new audio, words, removed gaps."""
    cuts: List[Tuple[int, int]] = []
    if words and words[0]["start"] > LEAD_IN:
        cuts.append((0, int((words[0]["start"] - LEAD_IN) * SR)))
    for a, b in zip(words, words[1:]):
        gap = b["start"] - a["end"]
        if gap > MAX_GAP:
            remove = gap - KEEP_GAP
            mid = a["end"] + KEEP_GAP / 2
            cuts.append((int(mid * SR), int((mid + remove) * SR)))
    if not cuts:
        return audio, words, []
    keep, prev = [], 0
    fade = int(0.006 * SR)
    for s, e in cuts:
        seg = audio[prev:s].copy()
        if len(seg) > 2 * fade:
            seg[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
            if prev:
                seg[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)
        keep.append(seg)
        prev = e
    keep.append(audio[prev:])
    out = np.concatenate(keep)

    def shift(t: float) -> float:
        removed = sum((e - s) / SR for s, e in cuts if e / SR <= t + 1e-6)
        return max(0.0, t - removed)

    new_words = [dict(w, start=shift(w["start"]), end=shift(w["end"])) for w in words]
    return out, new_words, [round((e - s) / SR, 3) for s, e in cuts]


def envelope(audio: np.ndarray, fps: int, n_frames: int) -> np.ndarray:
    hop = SR / fps
    env = np.zeros(n_frames, np.float32)
    for i in range(n_frames):
        seg = audio[int(i * hop): int((i + 1) * hop)]
        env[i] = float(np.sqrt(np.mean(seg ** 2))) if len(seg) else 0.0
    peak = np.percentile(env, 95) if env.any() else 1.0
    return np.clip(env / (peak + 1e-6), 0, 1)


# ---------------------------------------------------------------------------
# Music bed + SFX (synthesized)
# ---------------------------------------------------------------------------
def _midi(n: int) -> float:
    return 440.0 * 2 ** ((n - 69) / 12)


def music_bed(duration: float, seed: int = 0, mood: str = "mystery") -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(duration * SR)
    t = np.arange(n, dtype=np.float32) / SR
    out = np.zeros((n, 2), np.float32)
    # Minor progression (Am - F - Dm - E), 4 s per chord, soft pad voicing
    prog = [(57, 60, 64), (53, 57, 60), (50, 53, 57), (52, 56, 59)]
    chord_len = 4.0
    for ci in range(int(math.ceil(duration / chord_len))):
        s0 = int(ci * chord_len * SR)
        s1 = min(n, int((ci + 1) * chord_len * SR + 0.6 * SR))
        if s0 >= n:
            break
        tt = t[s0:s1] - t[s0]
        env = np.minimum(1, tt / 0.8) * np.exp(-np.maximum(0, tt - chord_len) * 4)
        for k, note in enumerate(prog[ci % len(prog)]):
            f = _midi(note)
            for ch, det in ((0, -0.6), (1, 0.6)):
                ph = rng.uniform(0, 2 * np.pi)
                w = np.sin(2 * np.pi * (f + det) * tt + ph) + 0.25 * np.sin(4 * np.pi * (f + det) * tt + ph)
                out[s0:s1, ch] += (0.07 / (1 + 0.3 * k)) * env * w
        # Sub bass root
        out[s0:s1, :] += (0.08 * env * np.sin(2 * np.pi * _midi(prog[ci % len(prog)][0] - 24) * tt))[:, None]
    # Soft pulse (heartbeat-like) and airy ticks for momentum
    beat = 60 / 92
    for b in np.arange(0, duration, beat):
        s = int(b * SR)
        L = int(0.18 * SR)
        if s + L >= n:
            break
        tt = np.arange(L) / SR
        kick = np.sin(2 * np.pi * (60 - 25 * tt / 0.18) * tt) * np.exp(-tt * 22) * 0.18
        out[s:s + L] += kick[:, None]
        hs = s + int(beat / 2 * SR)
        if hs + 800 < n:
            hh = rng.normal(0, 1, 800) * np.exp(-np.arange(800) / 120) * 0.025
            out[hs:hs + 800, 0] += hh
            out[hs:hs + 800, 1] += hh * 0.8
    fade = int(0.15 * SR)
    out[:fade] *= np.linspace(0, 1, fade)[:, None]
    out[-int(0.6 * SR):] *= np.linspace(1, 0, int(0.6 * SR))[:, None]
    return out / (np.abs(out).max() + 1e-6) * 0.5


def _noise_band(n: int, rng, lo_smooth: int, hi_smooth: int) -> np.ndarray:
    x = rng.normal(0, 1, n).astype(np.float32)
    a = np.convolve(x, np.ones(lo_smooth) / lo_smooth, mode="same")
    b = np.convolve(x, np.ones(hi_smooth) / hi_smooth, mode="same")
    return a - b


def sfx(kind: str, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    if kind == "whoosh":
        L = int(0.42 * SR)
        tt = np.arange(L) / SR
        x = _noise_band(L, rng, 3, 40)
        env = np.sin(np.pi * np.clip(tt / 0.42, 0, 1)) ** 2
        pan = np.linspace(-1, 1, L)
        return np.stack([x * env * (1 - pan) / 2, x * env * (1 + pan) / 2], 1) * 1.4
    if kind == "hit":
        L = int(0.9 * SR)
        tt = np.arange(L) / SR
        boom = np.sin(2 * np.pi * (110 * np.exp(-tt * 3) + 38) * tt) * np.exp(-tt * 4.5)
        crack = _noise_band(L, rng, 2, 18) * np.exp(-tt * 30) * 0.8
        x = 0.9 * boom + crack
        return np.stack([x, x], 1)
    if kind == "riser":
        L = int(1.0 * SR)
        tt = np.arange(L) / SR
        x = _noise_band(L, rng, 2, 25) * (tt / 1.0) ** 2 * 0.7 + 0.25 * np.sin(2 * np.pi * (200 + 500 * tt) * tt) * tt
        return np.stack([x, x], 1)
    if kind == "pop":
        L = int(0.12 * SR)
        tt = np.arange(L) / SR
        x = np.sin(2 * np.pi * (900 - 400 * tt / 0.12) * tt) * np.exp(-tt * 40) * 0.6
        return np.stack([x, x], 1)
    if kind == "paper":
        L = int(0.3 * SR)
        tt = np.arange(L) / SR
        x = _noise_band(L, rng, 1, 6) * np.exp(-tt * 10) * 0.5
        return np.stack([x, x * 0.9], 1)
    return np.zeros((1, 2), np.float32)


def sfx_track(duration: float, events: List[Tuple[float, str]]) -> np.ndarray:
    n = int(duration * SR)
    out = np.zeros((n, 2), np.float32)
    gains = {"whoosh": 0.35, "hit": 0.5, "riser": 0.22, "pop": 0.3, "paper": 0.3}
    for i, (t0, kind) in enumerate(events):
        clip = sfx(kind, seed=i) * gains.get(kind, 0.3)
        s = int(max(0.0, t0) * SR)
        e = min(n, s + len(clip))
        if s < n:
            out[s:e] += clip[: e - s]
    return out


def duck_gain(narration: np.ndarray, n: int, depth_db: float = 10.0, attack: float = 0.015, release: float = 0.35) -> np.ndarray:
    """Music gain that dips under the voice. Envelope on 10 ms blocks, attack/release smoothing."""
    block = int(0.01 * SR)
    nb = int(math.ceil(n / block))
    x = np.zeros(nb * block, np.float32)
    x[:min(n, len(narration))] = narration[:n]
    rms = np.sqrt(np.mean(x.reshape(nb, block) ** 2, axis=1) + 1e-12)
    level_db = 20 * np.log10(rms)
    target = np.clip((level_db + 42) / 18, 0, 1)  # 0 below -42 dBFS, 1 above -24 dBFS
    a_up, a_dn = math.exp(-0.01 / attack), math.exp(-0.01 / release)
    sm = np.empty_like(target)
    cur = 0.0
    for i, v in enumerate(target):
        coef = a_up if v > cur else a_dn
        cur = coef * cur + (1 - coef) * v
        sm[i] = cur
    gain_blocks = 10 ** (-depth_db * sm / 20)
    return np.interp(np.arange(n), np.arange(nb) * block + block / 2, gain_blocks).astype(np.float32)


def mix(ffmpeg_bin: str, narration_wav: str, music_wav: str, sfx_wav: str, out_wav: str, target_lufs: float = -14.0):
    """Mix in numpy (deterministic), then one static gain to target loudness + true-peak limiter.

    ffmpeg's sidechaincompress/amix/loudnorm graph zeroed the last ~1 s of the music bed
    (measured -80..-180 dB tails), so ducking and summing are done here instead.
    """
    def read(path):
        with wave.open(path) as w:
            ch = w.getnchannels()
            x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        x = x.reshape(-1, ch)
        return np.repeat(x, 2, axis=1) if ch == 1 else x

    nar, mus, fx = read(narration_wav), read(music_wav), read(sfx_wav)
    n = max(len(nar), len(mus), len(fx))
    pad = lambda a: np.pad(a, ((0, n - len(a)), (0, 0)))
    nar, mus, fx = pad(nar), pad(mus), pad(fx)
    g = duck_gain(nar[:, 0], n)[:, None]
    out = nar + mus * 0.55 * g + fx
    raw = str(Path(out_wav).with_suffix(".raw.wav"))
    write_wav(raw, np.clip(out, -1, 1) * 0.5)  # headroom; static gain below restores level

    res = subprocess.run([ffmpeg_bin, "-hide_banner", "-nostats", "-i", raw, "-af", "ebur128", "-f", "null", "-"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    found = re.findall(r"I:\s+(-?[\d.]+) LUFS", res.stderr)
    if not found:
        raise RuntimeError("[Audio] could not measure loudness of the raw mix")
    gain_db = target_lufs - float(found[-1])
    res = subprocess.run([ffmpeg_bin, "-y", "-v", "error", "-i", raw, "-af",
                          f"volume={gain_db:.2f}dB,alimiter=limit=0.76:attack=5:release=50:level=disabled",
                          "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le", out_wav],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        raise RuntimeError(f"[Audio] mix failed: {res.stderr.decode()[-600:]}")
    Path(raw).unlink(missing_ok=True)


def measure(ffmpeg_bin: str, wav: str, silence_db: float = -45.0, silence_d: float = 0.4) -> Dict:
    """Integrated loudness (ebur128) and silences longer than silence_d."""
    res = subprocess.run([ffmpeg_bin, "-hide_banner", "-nostats", "-i", wav, "-af",
                          f"silencedetect=noise={silence_db}dB:d={silence_d},ebur128=peak=true", "-f", "null", "-"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    err = res.stderr
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", err)]
    durs = [float(x) for x in re.findall(r"silence_duration: ([\d.]+)", err)]
    lufs = re.findall(r"I:\s+(-?[\d.]+) LUFS", err)
    peak = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", err)
    return {"integrated_lufs": float(lufs[-1]) if lufs else None,
            "true_peak_dbfs": float(peak[-1]) if peak else None,
            "silences": [{"start": round(s, 2), "duration": round(d, 2)} for s, d in zip(starts, durs)]}
