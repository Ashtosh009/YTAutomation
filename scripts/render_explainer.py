#!/usr/bin/env python3
"""Render explainer videos locally (no DB, no Storage upload) and print a summary.

  python scripts/render_explainer.py --topic "The Wow! Signal"
  python scripts/render_explainer.py --script output/explainer/script_wow_signal.json
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.cast import get_cast  # noqa: E402
from core.config import OUTPUT_DIR  # noqa: E402
from core.explainer import explainer_renderer  # noqa: E402
from core.llm import generate_explainer_script  # noqa: E402
from core.quality_check import QualityGateError  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", action="append", default=[])
    ap.add_argument("--script", action="append", default=[])
    args = ap.parse_args()
    jobs = [("script", s) for s in args.script] + [("topic", t) for t in args.topic]
    results = []
    for kind, value in jobs:
        t0 = time.time()
        if kind == "topic":
            script = generate_explainer_script(value, get_cast().names())
        else:
            script = json.loads(Path(value).read_text())
        name = Path(value).stem.replace("script_", "") if kind == "script" else value[:30]
        out = OUTPUT_DIR / "explainer" / f"{name.replace(' ', '_')}.mp4"
        status = "PASS"
        try:
            explainer_renderer.render_short(script, str(out))
        except QualityGateError:
            status = "FAIL"
        explainer_renderer.generate_thumbnail(script, str(out), str(out.with_suffix(".jpg")))
        r = explainer_renderer.last_report
        prov = {k: {x: v[x] for x in ("successes", "failures", "rate_limited")} | {"seconds": round(v["seconds"]), "disabled": v["disabled_reason"]}
                for k, v in r["image_providers"].items()} if sys.version_info >= (3, 9) else r["image_providers"]
        res = {"name": name, "gate": status, "total_s": round(time.time() - t0), "timings": r["timings_s"],
               "summary": r["summary"], "video": r["video"], "providers": prov,
               "shot_providers": [s["provider"] for s in r["shots"]], "failures": r["failures"], "warnings": r["warnings"],
               "workdir": str(explainer_renderer.last_workdir), "mp4": str(out)}
        results.append(res)
        print("RESULT " + json.dumps(res, ensure_ascii=False))
    return 0 if all(r["gate"] == "PASS" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
