"""Which free models can actually answer a real game prompt? Ask them.

    py scripts/model_bakeoff.py

Writes `artifacts/model-bakeoff.json`.

Why this exists, and it is not a happy story. The Phase B budget analysis picked
`gemma-4-31b-it` as the eval model on arithmetic alone — 14,400 requests a day against
Flash-Lite's 500, which is 180 games a day against 6. That decision was recorded as
provisional, "pending a quality bake-off", and it was right to be.

Then Phase C tried to run an eval arm on it and the arm hung on the first real prompt.
Gemma answers `"Reply with exactly the word: ready"` in 3.1 seconds and answers a
1,556-character game prompt with `504 DEADLINE_EXCEEDED`, then stops answering at all.

**A rate limit is a promise about requests you are allowed to make, not about requests
that will be served.** This script measures the second thing, because the first thing is
what the dashboard tells you and it turned out not to be the binding constraint.

Each candidate gets the *same* real prompt, built by the real policy from a committed
recording — not a "hello". The whole failure lived in the gap between those two.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from arc_agi_3._structs import FrameData  # noqa: E402

from harness.budget import LIMITS  # noqa: E402
from harness.frames import main_grid, render_objects  # noqa: E402
from harness.llm import GeminiClient, ScriptedClient  # noqa: E402
from harness.policies import LLMPolicy, parse_action  # noqa: E402
from harness.trace import open_jsonl  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"

# Every text model with measured free-tier limits, cheapest-quota-first. The Gemma pair
# leads because if they work they are 23x the daily budget of anything else.
CANDIDATES = [
    "gemma-4-31b-it",
    "gemma-4-26b-a4b-it",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
]

# Long enough that a slow-but-working model is not mistaken for a broken one, short enough
# that four dead models cost two minutes rather than the afternoon Phase C nearly lost.
TIMEOUT_S = 30.0
CALLS_PER_MODEL = 3


def real_prompt() -> str:
    """The prompt the agent actually sends, built from a committed real frame."""
    runs = sorted((ROOT / "runs").glob("ls20*.recording.jsonl*"))
    if not runs:
        raise SystemExit("no ls20 recording in runs/ to build a real prompt from")
    frames: list[FrameData] = []
    with open_jsonl(runs[-1]) as fh:
        for line in fh:
            data = json.loads(line).get("data")
            if isinstance(data, dict) and data.get("frame"):
                frames.append(FrameData.model_validate(data))
    policy = LLMPolicy(ScriptedClient(["x"]), encoder=lambda f: render_objects(main_grid(f)))
    return policy.build_prompt(frames[:20], frames[19])


def main() -> int:
    prompt = real_prompt()
    print(f"prompt: {len(prompt):,} characters, built from a real ls20 frame")
    print(f"asking each model {CALLS_PER_MODEL}x with a {TIMEOUT_S:.0f}s timeout\n")
    print(f"{'model':<24}{'ok':>4}{'median ms':>11}{'usable':>8}  notes")
    print("-" * 78)

    results = []
    for name in CANDIDATES:
        client = GeminiClient(model=name, timeout_seconds=TIMEOUT_S)
        latencies: list[float] = []
        errors: list[str] = []
        parsed = 0
        for _ in range(CALLS_PER_MODEL):
            t0 = time.perf_counter()
            completion = client.complete(prompt)
            if completion.ok:
                latencies.append((time.perf_counter() - t0) * 1000)
                if parse_action(completion.text) is not None:
                    parsed += 1
            else:
                errors.append(completion.error or "?")
        limits = LIMITS[name]
        median = sorted(latencies)[len(latencies) // 2] if latencies else None
        row = {
            "model": name,
            "calls": CALLS_PER_MODEL,
            "answered": len(latencies),
            "usable_actions": parsed,
            "median_ms": round(median) if median else None,
            "errors": errors[:3],
            "rpd": limits.rpd,
            "rpm": limits.rpm,
            # What the quota is worth *if the model answers*. Kept next to `answered` on
            # purpose: this number was the whole basis of the Phase B model choice.
            "games_per_day_at_80_actions": round(limits.rpd / 80, 2),
        }
        results.append(row)
        note = errors[0][:36] if errors else "ok"
        print(
            f"{name:<24}{len(latencies):>2}/{CALLS_PER_MODEL:<2}"
            f"{(str(row['median_ms']) if median else '-'):>11}"
            f"{parsed:>5}/{CALLS_PER_MODEL:<2}  {note}"
        )

    working = [r for r in results if r["answered"] == r["calls"]]
    out = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "prompt_chars": len(prompt),
        "prompt_source": "real ls20 frame, objects encoding, the agent's own prompt builder",
        "timeout_seconds": TIMEOUT_S,
        "calls_per_model": CALLS_PER_MODEL,
        "results": results,
        "conclusion": (
            "models that answered every call: "
            + (", ".join(r["model"] for r in working) or "none")
        ),
    }
    ARTIFACTS.mkdir(exist_ok=True)
    path = ARTIFACTS / "model-bakeoff.json"
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"\n{out['conclusion']}")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
