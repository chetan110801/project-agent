"""Before and after, for one change, in one table.

    py scripts/compare_evals.py llm-nohistory llm-history8

Each argument names an `artifacts/evals/<arm>.json` written by `scripts/run_evals.py`.
Prints the table and writes `artifacts/evals/comparison-<before>-vs-<after>.json`.

Three things this does that a hand-typed table cannot:

1. **It states what actually differed between the two arms** before showing any number.
   If more than one setting changed, the header says so — and a comparison across two
   changed variables cannot attribute anything, so it is labelled `NOT AN EXPERIMENT`.
2. **It separates steering metrics from outcome metrics.** The decision to keep or revert
   is made on the steering block. The outcome block is there so a steering win that
   destroys the score cannot be quietly banked (CLAUDE.md §5).
3. **It refuses to call a difference an improvement when the suites are not the same
   games.** Different games are different difficulty; the numbers are not comparable and
   saying so is the whole job.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.evals import COST, OUTCOME, STEERING, Arm, Metrics, direction  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "artifacts" / "evals"

ARROW = {"better": "better", "worse": "WORSE", "same": "same", "": ""}


_METRIC_FIELDS = set(Metrics.__dataclass_fields__)


def load(name: str, attempt: int | None = None) -> dict[str, Any]:
    """Read an arm, and **recompute its aggregate from its per-episode metrics.**

    The stored `aggregate` block is advisory. The per-episode numbers are the data; how
    they roll up is a definition, and definitions get corrected. When one is — as
    `longest_repeat_streak` was, once it turned out a plain max over games reports the
    one-button game's forced streak for every arm — recomputing here means both sides of
    every old comparison move together. Trusting the stored block would silently compare
    an arm measured under yesterday's definition against one measured under today's, which
    is the exact class of error this whole module exists to prevent.

    `attempt` slices to one replay of each game before aggregating. The progress signal only
    acts from attempt 2 on, so judging it means comparing attempt 2 of the treatment against
    attempt 2 of the control — a plain aggregate would dilute that with attempt 1, which is
    identical in both arms by construction. Episodes with no `attempt` field read as 1, so an
    old single-play arm is untouched by `--attempt 1`.
    """
    path = EVAL_DIR / f"{name.removesuffix('.json')}.json"
    if not path.exists():
        raise SystemExit(f"no such arm: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    episodes = data["episodes"]
    if attempt is not None:
        episodes = [ep for ep in episodes if ep.get("attempt", 1) == attempt]
    arm = Arm(
        name=data["arm"],
        suite=data["suite"],
        games=data["games"],
        episodes=[
            Metrics(**{k: v for k, v in ep.items() if k in _METRIC_FIELDS})
            for ep in episodes
        ],
        config=data["config"],
    )
    data["aggregate"] = arm.aggregate()
    return data


def config_diff(a: dict, b: dict) -> list[str]:
    keys = sorted(set(a["config"]) | set(b["config"]))
    return [
        f"{k}: {a['config'].get(k)!r} -> {b['config'].get(k)!r}"
        for k in keys
        if a["config"].get(k) != b["config"].get(k)
    ]


def fmt(v: Any) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.4g}"
    return str(v)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Compare two eval arms in one table.")
    ap.add_argument("before", help="artifacts/evals/<before>.json")
    ap.add_argument("after", help="artifacts/evals/<after>.json")
    ap.add_argument(
        "--attempt",
        type=int,
        default=None,
        help="compare only this attempt index (for multi-attempt / --progress arms)",
    )
    args = ap.parse_args(argv)
    before, after = load(args.before, args.attempt), load(args.after, args.attempt)

    changed = config_diff(before, after)
    same_games = before["games"] == after["games"]

    if args.attempt is not None:
        print(f"attempt : {args.attempt} only (episodes sliced to this replay of each game)")
    print(f"before : {args.before}  ({before['aggregate']['episodes']} games)")
    print(f"after  : {args.after}  ({after['aggregate']['episodes']} games)")
    print()
    if not changed:
        print("what changed: NOTHING in the config — this is a re-run, not an experiment.")
    else:
        print("what changed:")
        for line in changed:
            print(f"  {line}")
        if len(changed) > 1:
            print("  ^ NOT AN EXPERIMENT: more than one variable moved, so no difference")
            print("    below can be attributed to any single one of them.")
    if not same_games:
        print("\nWARNING: the two arms ran different games. The numbers are not comparable.")
    if before["config"].get("mock") or after["config"].get("mock"):
        print("\nWARNING: a mock arm is in this table. It proves plumbing, not play.")
    print()

    a, b = before["aggregate"], after["aggregate"]
    rows: list[tuple[str, str, str, str, str]] = []
    for kind, names in (("steering", STEERING), ("outcome", OUTCOME), ("cost", COST)):
        for name in names:
            if name not in a and name not in b:
                continue
            d = "" if kind == "outcome" else direction(name, a.get(name), b.get(name))
            if not same_games:
                d = ""
            # The canonical value is stored; ARROW is applied only when printing. Writing
            # the shouty display string into the artifact would make the file agree with
            # the terminal and disagree with every program that reads it.
            rows.append((kind, name, fmt(a.get(name)), fmt(b.get(name)), d))

    w = max(len(r[1]) for r in rows)
    kind_now = ""
    for kind, name, x, y, d in rows:
        if kind != kind_now:
            kind_now = kind
            title = {
                "steering": "STEERING - the change is judged on these",
                "outcome": "OUTCOME - reported, never steered on",
                "cost": "COST - what the change was paid for with",
            }[kind]
            print(f"\n{title}")
            print("-" * (w + 34))
        print(f"  {name:{w}}  {x:>12}  {y:>12}   {ARROW[d]}")

    suffix = f"-attempt{args.attempt}" if args.attempt is not None else ""
    out = EVAL_DIR / f"comparison-{args.before}-vs-{args.after}{suffix}.json"
    out.write_text(
        json.dumps(
            {
                "before": args.before,
                "after": args.after,
                "attempt": args.attempt,
                "config_changed": changed,
                "single_variable": len(changed) == 1,
                "same_games": same_games,
                "games": before["games"],
                "rows": [
                    {
                        "kind": kind,
                        "metric": name,
                        "before": a.get(name),
                        "after": b.get(name),
                        "direction": d,
                    }
                    for kind, name, _, _, d in rows
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
