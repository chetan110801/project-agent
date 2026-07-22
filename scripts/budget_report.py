"""What the free tier buys, in games — the number that decides how evals are designed.

    py scripts/budget_report.py

Writes `artifacts/llm-budget.json` and prints the table. No API calls: it combines the
measured rate limits in `harness/budget.py` with the measured prompt sizes in
`artifacts/tokens-by-tokeniser.json`, both of which have their own provenance.

The question it answers is the one that decides Phase C's design: *at one model call per
game action, how many 80-action games fit in a day, and how long does one take?* An eval
suite that needs more runs per day than the quota allows isn't an eval suite, it's a wish.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.budget import LIMITS, SOURCE  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
ACTIONS_PER_GAME = 80  # the SDK default, and what every run so far used


def prompt_sizes() -> dict[str, int]:
    """Measured Gemini token counts per encoding, from the committed artifact."""
    path = ARTIFACTS / "tokens-by-tokeniser.json"
    if not path.exists():
        raise SystemExit("run scripts/measure_tokens.py first")
    data = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for row in data["encodings"]:
        if row["label"].startswith("real frame /") and isinstance(row["gemini_tokens"], int):
            out[row["label"].removeprefix("real frame / ")] = row["gemini_tokens"]
    return out


def main() -> int:
    sizes = prompt_sizes()
    # The two encodings a real policy would choose between (note 06).
    candidates = {
        k: v for k, v in sizes.items() if k in ("raw grid, hex packed", "objects (cap 40)")
    }

    rows = []
    for name, lim in LIMITS.items():
        for enc, tokens in candidates.items():
            # Prompt = the frame plus instructions; the instruction block is not written
            # yet, so this is the frame alone and is therefore a LOWER bound on cost.
            per_min_by_tokens = lim.tpm / tokens
            calls_per_min = min(lim.rpm, per_min_by_tokens)
            minutes_per_game = ACTIONS_PER_GAME / calls_per_min
            rows.append(
                {
                    "model": name,
                    "encoding": enc,
                    "prompt_tokens_per_call": tokens,
                    "rpm": lim.rpm,
                    "tpm": lim.tpm,
                    "rpd": lim.rpd,
                    "binding_limit": lim.binding_limit(tokens),
                    "effective_calls_per_min": round(calls_per_min, 2),
                    "minutes_per_80_action_game": round(minutes_per_game, 1),
                    "games_per_day": round(lim.rpd / ACTIONS_PER_GAME, 2),
                }
            )

    rows.sort(key=lambda r: (-r["games_per_day"], r["minutes_per_80_action_game"]))

    report = {
        "limits_source": SOURCE,
        "token_source": "artifacts/tokens-by-tokeniser.json (gemini-3.5-flash-lite counter)",
        "assumptions": {
            "actions_per_game": ACTIONS_PER_GAME,
            "model_calls_per_action": 1,
            "prompt": (
                "the encoded frame only — no instruction block, no history, no output "
                "tokens. Every figure here is therefore a BEST case."
            ),
        },
        "rows": rows,
    }
    ARTIFACTS.mkdir(exist_ok=True)
    out = ARTIFACTS / "llm-budget.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    w = max(len(r["model"]) for r in rows)
    head = (
        f"{'model'.ljust(w)}  {'encoding':<21} {'tok':>6} {'binds':>6} "
        f"{'calls/min':>10} {'min/game':>9} {'games/day':>10}"
    )
    print(f"at 1 model call per action, {ACTIONS_PER_GAME} actions per game\n")
    print(head)
    print("-" * len(head))
    for r in rows:
        print(
            f"{r['model'].ljust(w)}  {r['encoding']:<21} {r['prompt_tokens_per_call']:>6,} "
            f"{r['binding_limit']:>6} {r['effective_calls_per_min']:>10} "
            f"{r['minutes_per_80_action_game']:>9} {r['games_per_day']:>10}"
        )
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
