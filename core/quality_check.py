"""Quality gate for explainer renders. Produces a readable report; fails the run on hard problems."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, List

from core.config import QUALITY_GATE


class QualityGateError(RuntimeError):
    pass


def evaluate(m: Dict) -> Dict:
    """m: metrics collected by the explainer renderer."""
    fails: List[str] = []
    warns: List[str] = []
    dur = m["duration_s"]
    shots = m["shots"]
    n = len(shots)
    avg = sum(s["duration"] for s in shots) / max(n, 1)

    if not (1.2 <= avg <= 4.0):
        fails.append(f"Average shot length {avg:.2f}s is outside 1.2-4.0s.")
    need = math.floor(15 * dur / 50)
    if n < need:
        fails.append(f"Only {n} distinct shots for {dur:.1f}s (need >= {need}, i.e. 15 per 50 s).")
    if m["static_max_run_s"] > 2.5:
        fails.append(f"A static frame was held for {m['static_max_run_s']:.2f}s (max 2.5s) around t={m['static_max_run_at']:.1f}s.")
    H, top, bottom = m["height"], m["safe_top"], m["safe_bottom"]
    bad_caps = [b for b in m["caption_bboxes"] if b[1] < top or b[3] > H - bottom or b[0] < 0 or b[2] > m["width"]]
    if bad_caps:
        fails.append(f"{len(bad_caps)} caption frames overlap the safe margins (top {top}px / bottom {bottom}px) or are clipped.")
    tail = dur - 0.6
    silences = [s for s in m["audio"].get("silences", []) if s["duration"] > 0.4 and s["start"] < tail]
    if silences:
        fails.append(f"{len(silences)} silence(s) longer than 0.4s in the final mix: {silences[:3]}")
    moves = sorted({s["camera"] for s in shots if s["kind"] == "image"})
    if len(moves) < 3:
        fails.append(f"Only {len(moves)} camera-move types used ({moves}); need >= 3.")
    blank = [s["index"] for s in shots if s.get("blank")]
    if blank:
        fails.append(f"Blank/failed image frames in shots {blank}.")
    if m.get("fact_flags"):
        fails.append(f"{len(m['fact_flags'])} fact-validator flag(s) remain: " +
                     "; ".join(f"scene {f.get('scene')}: {f.get('problem', '')[:90]}" for f in m["fact_flags"][:3]))
    illegible = [p for p in m.get("props", []) if not p.get("legible")]
    if illegible:
        fails.append(f"{len(illegible)} evidence prop(s) not legible (font < 60px or text truncated).")

    if not (40 <= dur <= 62):
        warns.append(f"Duration {dur:.1f}s is outside the 40-60s target.")
    lufs = m["audio"].get("integrated_lufs")
    if lufs is not None and abs(lufs + 14) > 1.5:
        warns.append(f"Integrated loudness {lufs:.1f} LUFS (target -14).")
    if m.get("narration_gaps_removed"):
        warns.append(f"Shortened {len(m['narration_gaps_removed'])} narration pause(s) to keep speech continuous.")
    rl = sum(p.get("rate_limited", 0) for p in m.get("image_providers", {}).values())
    if rl:
        warns.append(f"Image provider rate-limit responses: {rl}.")
    if m.get("reused_images"):
        warns.append(f"{m['reused_images']} shot(s) reused an earlier image (MAX_IMAGES_PER_VIDEO budget).")

    return {
        "passed": not fails,
        "failures": fails,
        "warnings": warns,
        "summary": {
            "duration_s": round(dur, 2), "shots": n, "avg_shot_s": round(avg, 2),
            "camera_moves": moves, "static_max_run_s": round(m["static_max_run_s"], 2),
            "integrated_lufs": lufs, "true_peak_dbfs": m["audio"].get("true_peak_dbfs"),
            "words": m.get("words"), "render_seconds": m.get("render_seconds"),
        },
    }


def enforce(report: Dict, report_path: Path):
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    lines = [f"[Quality] {'PASS' if report['passed'] else 'FAIL'} -> {report_path}"]
    lines += [f"  FAIL: {f}" for f in report["failures"]] + [f"  warn: {w}" for w in report["warnings"]]
    print("\n".join(lines))
    if not report["passed"] and QUALITY_GATE == "enforce":
        raise QualityGateError("Quality gate failed:\n" + "\n".join(report["failures"]))
