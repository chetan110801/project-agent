"""Read a real ARC-AGI-3 recording and turn it into facts we can cite.

    py scripts/analyze_run.py [path/to/*.recording.jsonl] [--out NAME] [--agent LABEL]

Defaults to the newest recording in `runs/`. Writes `artifacts/<NAME>.json` (default
`run-report`) and prints a summary.

It refuses to overwrite a report that was generated from a *different* recording unless
you pass `--force`. That guard exists because the mistake has already been made once, in
the session that added it: analysing a throwaway mock run silently replaced the committed
baseline report that three study notes quote. A number's provenance is worthless if the
file holding it can be swapped by a stray command.

Every number the study notes quote about *real* frames comes from here, so this script is
the provenance for them: rerun it and you get the same numbers, because the recording is
committed alongside it.

A recording is JSONL written by the SDK's Recorder: one object per line, `{"timestamp",
"data"}`, where `data` is a `FrameData` dump for each action and the final line is the
scorecard.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.frames import (  # noqa: E402
    diff_grids,
    grid_fingerprint,
    grid_shape,
    render_diff,
    render_grid,
    render_objects,
)
from harness.tokens import measure  # noqa: E402
from harness.trace import open_jsonl  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"


def load(path: Path) -> tuple[list[dict], dict | None]:
    """(frames, scorecard). The scorecard is the trailing record, if present."""
    with open_jsonl(path) as fh:
        records = [json.loads(line) for line in fh if line.strip()]
    frames = [r["data"] for r in records if isinstance(r.get("data"), dict) and "frame" in r["data"]]
    tail = records[-1]["data"] if records and isinstance(records[-1].get("data"), dict) else None
    scorecard = tail if tail is not None and "frame" not in tail else None
    return frames, scorecard


def screen(frame: dict) -> list[list[int]]:
    """The settled grid — the last one, see harness.frames.main_grid."""
    return frame["frame"][-1]




def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", nargs="?", help="a *.recording.jsonl (default: newest in runs/)")
    ap.add_argument("--out", default="run-report", help="artifacts/<NAME>.json")
    ap.add_argument(
        "--agent",
        default="unlabelled — pass --agent",
        help="who played, e.g. 'sdk random baseline' or 'our loop (random policy)'",
    )
    ap.add_argument("--force", action="store_true", help="overwrite a report from another recording")
    args = ap.parse_args(argv)

    if args.path:
        path = Path(args.path)
    else:
        candidates = sorted((ROOT / "runs").glob("*.recording.jsonl"))
        if not candidates:
            print("no recordings in runs/ — run the agent first")
            return 1
        path = candidates[-1]

    out = ARTIFACTS / f"{args.out}.json"
    if out.exists() and not args.force:
        try:
            existing = json.loads(out.read_text(encoding="utf-8")).get("recording")
        except (json.JSONDecodeError, OSError):
            existing = None
        if existing and existing != path.name:
            print(f"refusing to overwrite {out.name}: it was made from {existing}")
            print(f"pass --out <other-name> to write elsewhere, or --force to replace it")
            return 2

    frames, scorecard = load(path)
    if not frames:
        print(f"{path} contains no frames")
        return 1

    # -- shape of the world ------------------------------------------------ #
    grids_per_frame = Counter(len(f["frame"]) for f in frames)
    shapes = Counter(grid_shape(screen(f)) for f in frames)
    values = Counter(v for f in frames for g in f["frame"] for row in g for v in row)
    avail = Counter(tuple(f["available_actions"]) for f in frames)
    available_set = set(frames[0]["available_actions"])

    # -- what the agent did ------------------------------------------------ #
    sent = Counter(f["action_input"]["id"] for f in frames)
    illegal = [f for f in frames if f["action_input"]["id"] not in available_set | {0}]
    states = Counter(f["state"] for f in frames)

    # How long the agent stays alive between deaths. Frame 0 is the reset, so a GAME_OVER
    # at frame i is the outcome of action i. The gaps are what "it survived N actions"
    # means — a number worth having in the artifact rather than recounted by hand later.
    game_over_at = [i for i, f in enumerate(frames) if f["state"] == "GAME_OVER"]
    survived = [b - a for a, b in zip([0] + game_over_at, game_over_at)]

    # -- was it going anywhere? -------------------------------------------- #
    # Added in Phase C, and pointed at recordings that already existed. `dead` below counts
    # screens that did not change at all; these count screens the agent had *already seen*,
    # which is the failure `dead` is blind to — two cells flipping back and forth forever
    # is a changed screen every turn and no progress at all. Computing it from the
    # committed recordings means the metric can be checked against a failure we already
    # have on disk instead of one we hope to reproduce.
    hashes = [grid_fingerprint(screen(f)) for f in frames[1:]]
    kinds = [f["action_input"]["id"] for f in frames[1:]]
    streak = longest_streak = 0
    previous = None
    for k in kinds:
        streak = streak + 1 if k == previous else 1
        longest_streak = max(longest_streak, streak)
        previous = k

    dead = changed = 0
    dead_and_illegal = 0
    for before, after in zip(frames, frames[1:]):
        n = diff_grids(screen(before), screen(after)).count
        if n == 0:
            dead += 1
            if after["action_input"]["id"] not in available_set | {0}:
                dead_and_illegal += 1
        else:
            changed += 1

    # -- what one real frame costs ----------------------------------------- #
    mid = frames[len(frames) // 2]
    prev = frames[len(frames) // 2 - 1]
    g_mid, g_prev = screen(mid), screen(prev)
    encodings = [
        measure("real frame / raw grid, hex packed", render_grid(g_mid)),
        measure("real frame / raw grid, decimal space-separated", render_grid(g_mid, sep=" ", cell="dec")),
        measure("real frame / objects (cap 40)", render_objects(g_mid)),
        measure("real frame / objects (uncapped)", render_objects(g_mid, max_blobs=10_000)),
        measure("real frame / diff vs previous", render_diff(g_prev, g_mid)),
    ]
    baseline = encodings[0].chars
    enc_rows = []
    for e in encodings:
        d = e.as_dict()
        d["chars_vs_hex_packed"] = round(e.chars / baseline, 4)
        enc_rows.append(d)

    report = {
        "recording": path.name,
        "game_id": frames[0]["game_id"],
        "agent": args.agent,
        "frames": len(frames),
        "actions": len(frames) - 1,
        "final_state": frames[-1]["state"],
        "final_score": frames[-1]["score"],
        "scores_seen": sorted({f["score"] for f in frames}),
        "scorecard": scorecard,
        "grids_per_frame": {str(k): v for k, v in sorted(grids_per_frame.items())},
        "grid_shapes": {f"{r}x{c}": n for (r, c), n in shapes.items()},
        "cell_values_seen": sorted(values),
        "cell_value_max": max(values),
        "available_actions_sets": {str(list(k)): v for k, v in avail.items()},
        "actions_sent_histogram": {str(k): v for k, v in sorted(sent.items())},
        "states_histogram": dict(sorted(states.items())),
        "game_over_frames": states.get("GAME_OVER", 0),
        "game_over_at_action": game_over_at,
        "actions_survived_between_deaths": survived,
        "resets_sent": sent.get(0, 0),
        "actions_not_available": len(illegal),
        "transitions": len(frames) - 1,
        "transitions_no_change": dead,
        "transitions_changed": changed,
        "no_change_and_unavailable": dead_and_illegal,
        "unique_screens": len(set(hashes)),
        "revisit_rate": round(1 - len(set(hashes)) / len(hashes), 4) if hashes else None,
        "longest_repeat_streak": longest_streak,
        "top_action_share": round(max(sent.values()) / sum(sent.values()), 4) if sent else None,
        "encodings_on_one_real_frame": enc_rows,
        "tokeniser_note": (
            "token counts are tiktoken/o200k_base (an OpenAI tokeniser): valid for "
            "comparing encodings with each other, NOT a budget for another vendor's model"
        ),
    }

    ARTIFACTS.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"recording      : {path.name}")
    print(f"game           : {report['game_id']}")
    print(f"frames/actions : {report['frames']} / {report['actions']}")
    print(f"final          : state={report['final_state']} score={report['final_score']}")
    print(f"grids per frame: {report['grids_per_frame']}")
    print(f"cell values    : {report['cell_values_seen']}")
    print(f"available      : {report['available_actions_sets']}")
    print(f"actions sent   : {report['actions_sent_histogram']}")
    print(
        f"wasted actions : {report['actions_not_available']} of {report['actions']} were "
        f"not in available_actions"
    )
    print(
        f"dead actions   : {report['transitions_no_change']} of {report['transitions']} "
        f"changed nothing ({report['no_change_and_unavailable']} of those were unavailable)"
    )
    print(
        f"screens        : {report['unique_screens']} distinct of {report['actions']} "
        f"(revisit rate {report['revisit_rate']:.0%})"
    )
    print(
        f"repetition     : longest identical-action streak {report['longest_repeat_streak']}, "
        f"favourite action {report['top_action_share']:.0%} of all actions"
    )
    print()
    width = max(len(r["label"]) for r in enc_rows)
    print(f"{'encoding'.ljust(width)}  {'chars':>7}  {'tokens':>7}  {'x hex':>7}")
    print("-" * (width + 27))
    for r in enc_rows:
        tok = "n/a" if r["tokens"] is None else f"{r['tokens']:,}"
        print(f"{r['label'].ljust(width)}  {r['chars']:>7,}  {tok:>7}  {r['chars_vs_hex_packed']:>7.3f}")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
