"""How much of the screen actually moves per action, measured over the recordings we have.

    py scripts/change_sizes.py

Writes `artifacts/change-sizes.json`.

**Why this exists.** The next experiment asks the agent to make a *falsifiable prediction*
before it acts: how much of the screen its action will change — nothing, a little, or a lot.
For that to be a test rather than a formality, the boundary between "a little" and "a lot"
has to be a number the world actually produces. Pick it too high and every prediction is
FEW and always right; too low and every prediction is MANY and always right. Either way the
agent is never told it was wrong, which is the one thing the prompt is for.

So the boundary is read off the recordings, the same way the repetition guard's threshold
was read off random play (`harness/policies.py`). What the recordings say (below) is better
than a percentile: **these screens change bimodally.** An action moves either a couple of
cells or dozens — almost nothing lands in between. That is why the boundary is safe: every
value from 3 to 20 splits the data identically, so the number is not a knob anyone can tune
a result with.

Games are held apart as well as pooled. Pooling arms that played different games is the
confound that made the raw favourite-action share unusable across games (`harness/evals.py`);
the `by_game` block is the version of this table that is allowed to be compared.

Nothing here calls a model or costs quota. The recordings were paid for when they happened.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.frames import diff_grids  # noqa: E402
from harness.hypothesis import FEW_MANY_BOUNDARY  # noqa: E402
from scripts.progress_signals import load_frames, screen  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
ARTIFACTS = ROOT / "artifacts"

# Candidate boundaries to report, so the choice is visible next to its alternatives.
CANDIDATES = (2, 3, 5, 8, 10, 20)


def change_sizes(path: Path) -> list[int]:
    """Cells changed by each action in one recording. Shape changes are dropped, not zeroed.

    A grid that changes shape is not "0 cells changed" and not "everything changed" — it is
    a different question, and counting it either way would bias the very percentile this
    script exists to compute. Measured: this never happened in the recordings on disk.
    """
    frames = load_frames(path)
    sizes = []
    for a, b in zip(frames, frames[1:]):
        d = diff_grids(screen(a), screen(b))
        if d.same_shape:
            sizes.append(d.count)
    return sizes


def percentile(values: list[int], q: float) -> float:
    """Nearest-rank percentile. Small samples make interpolation a fiction."""
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round(q * len(ordered)) - 1))
    return float(ordered[idx])


def summarise(sizes: list[int]) -> dict[str, Any]:
    if not sizes:
        return {}
    return {
        "actions": len(sizes),
        "dead_share": round(sum(1 for s in sizes if s == 0) / len(sizes), 4),
        "median": percentile(sizes, 0.5),
        "p75": percentile(sizes, 0.75),
        "p90": percentile(sizes, 0.90),
        "p99": percentile(sizes, 0.99),
        "max": max(sizes),
        "mean": round(statistics.fmean(sizes), 2),
        "share_above": {
            str(c): round(sum(1 for s in sizes if s > c) / len(sizes), 4) for c in CANDIDATES
        },
    }


def game_of(name: str) -> str:
    return name.split(".", 1)[0]


def arm_of(name: str) -> str:
    """Which experimental arm a recording belongs to, read off its own filename.

    `scripts/run_evals.py` stems every file `<game>.eval-<arm>.<policy>...`, so the arm is
    recorded by the run itself and does not have to be guessed from substrings. Guessing is
    how `dev-llm-r3` and an ad-hoc Phase B run ended up pooled into one group called "LLM"
    the first time this table was printed — two different prompts averaged into one row.
    """
    if ".eval-" in name:
        return name.split(".eval-", 1)[1].split(".", 1)[0]
    if "9669d0d5" in name:
        return "llm-80-THE-STUCK-RUN"
    return "adhoc-random" if ".random." in name else "adhoc-llm"


def stable_band(by_group: dict[str, list[int]]) -> list[int]:
    """Every candidate boundary that splits the data the same way as the one below it.

    The claim "the boundary does not matter" is checked rather than asserted: a candidate
    joins the band when moving to it reclassifies under 1% of actions in every group.
    """
    band = []
    for lo, hi in zip(CANDIDATES, CANDIDATES[1:]):
        moved = max(
            (
                sum(1 for s in sizes if lo < s <= hi) / len(sizes)
                for sizes in by_group.values()
                if sizes
            ),
            default=1.0,
        )
        if moved < 0.01:
            band += [lo, hi]
    return sorted(set(band))


def main() -> int:
    by_group: dict[str, list[int]] = {}
    by_game: dict[str, dict[str, list[int]]] = {}
    per_run = []
    for path in sorted(RUNS.glob("*.recording.jsonl*")):
        sizes = change_sizes(path)
        if not sizes:
            continue
        group = arm_of(path.name)
        by_group.setdefault(group, []).extend(sizes)
        by_game.setdefault(game_of(path.name), {}).setdefault(group, []).extend(sizes)
        per_run.append({"recording": path.name, "group": group, **summarise(sizes)})

    groups = {name: summarise(sizes) for name, sizes in sorted(by_group.items())}
    band = stable_band(by_group)

    payload = {
        "generated_from": "recordings committed in runs/",
        "rule": (
            "NONE = 0 cells; FEW = 1..B; MANY = above B. B is any value in the stable band "
            "below — inside it, moving the boundary reclassifies under 1% of actions in "
            "every group, because these screens change bimodally (about 2 cells, or dozens)."
        ),
        "stable_band": band,
        "few_many_boundary": FEW_MANY_BOUNDARY,
        "boundary_is_inside_the_band": FEW_MANY_BOUNDARY in band,
        "groups": groups,
        "by_game": {
            game: {name: summarise(sizes) for name, sizes in sorted(arms.items())}
            for game, arms in sorted(by_game.items())
        },
        "runs": per_run,
    }
    ARTIFACTS.mkdir(exist_ok=True)
    out = ARTIFACTS / "change-sizes.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"{'group':28} {'actions':>8} {'dead':>7} {'med':>5} {'p75':>5} {'p90':>5} {'p99':>6} {'max':>6}")
    for name, s in groups.items():
        print(
            f"{name:28} {s['actions']:>8} {s['dead_share']:>7.0%} {s['median']:>5.0f} "
            f"{s['p75']:>5.0f} {s['p90']:>5.0f} {s['p99']:>6.0f} {s['max']:>6}"
        )
    print("\nshare of actions changing MORE than N cells:")
    print(f"{'group':28} " + " ".join(f"{c:>7}" for c in CANDIDATES))
    for name, s in groups.items():
        print(f"{name:28} " + " ".join(f"{s['share_above'][str(c)]:>7.1%}" for c in CANDIDATES))
    print(f"\nboundary from the rule above: FEW = 1..{payload['few_many_boundary']}, "
          f"MANY = {(payload['few_many_boundary'] or 0) + 1}+")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
