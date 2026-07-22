"""Test four candidate progress signals against recordings we already have.

    py scripts/progress_signals.py [--window 10]

Writes `artifacts/progress-signals.json` and prints the table that decides which signal
(if any) goes into the prompt.

**Why this script exists at all.** Phase C added `revisit_rate` because of a story about a
stuck agent, and then measured it on the recording of that very agent: **0%**. The metric
was blind to the failure it was invented for. So no signal proposed here is put in front of
the model until it has been run over the runs on disk — which cost nothing, because they
were recorded when they happened.

**What "works" means here.** A useful signal must do two things, and both are checked:

1. **Fire on the failure.** The 80-action LLM run (`...9669d0d5...`) pressed one button 41
   times in a row and went nowhere. A signal that reads healthy there is useless.
2. **Stay quiet otherwise.** A signal that also screams during ordinary random play is not
   a signal, it is a constant, and putting a constant in every prompt is paying tokens to
   train the model to ignore a line.

The second is the one that is easy to forget, so the random arms are in the table too, and
the separation ratio between them is the number the decision is made on.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.frames import grid_fingerprint  # noqa: E402
from harness.progress import measure_progress  # noqa: E402
from harness.trace import open_jsonl  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
ARTIFACTS = ROOT / "artifacts"

# The run every candidate has to catch: Phase B's stuck LLM episode. Named explicitly
# rather than found by a heuristic, so the test cannot quietly stop pointing at the failure.
STUCK_RUN = "ls20-9607627b.llm-gemini-3.5-flash-lite-objects.80.9669d0d5"
# A same-action streak this long is our label for "stuck" *within* an episode. It is a
# label, not a signal: it uses the action sequence, which is exactly what experiment 1
# showed the model cannot judge for itself.
STREAK_LABEL = 10
# The window is the only free parameter in the churn idea, so it gets swept rather than
# picked. A negative result at one window is not a negative result.
SWEEP_WINDOWS = (5, 10, 20, 30, 40, 60)
# Candidate caps for the repetition guard. The one we shipped is read off the random arms.
REPEAT_CAPS = (2, 3, 4, 5, 8)


def load_frames(path: Path) -> list[dict]:
    with open_jsonl(path) as fh:
        records = [json.loads(line) for line in fh if line.strip()]
    return [
        r["data"]
        for r in records
        if isinstance(r.get("data"), dict) and "frame" in r["data"]
    ]


def screen(frame: dict) -> list[list[int]]:
    return frame["frame"][-1]


def streak_labels(frames: list[dict], min_len: int = STREAK_LABEL) -> list[bool]:
    """True for each action that sits inside a run of >= `min_len` identical actions."""
    kinds = [f["action_input"]["id"] for f in frames[1:]]
    labels = [False] * len(kinds)
    i = 0
    while i < len(kinds):
        j = i
        while j + 1 < len(kinds) and kinds[j + 1] == kinds[i]:
            j += 1
        if j - i + 1 >= min_len:
            for k in range(i, j + 1):
                labels[k] = True
        i = j + 1
    return labels


def analyse(path: Path, window: int) -> dict[str, Any]:
    frames = load_frames(path)
    if len(frames) < window + 2:
        return {}
    grids = [screen(f) for f in frames]
    hashes = [grid_fingerprint(g) for g in grids]
    labels = streak_labels(frames)

    rows = []
    for t in range(1, len(grids)):
        p = measure_progress(grids[: t + 1], hashes=hashes[: t + 1], window=window)
        if p is None:
            continue
        rows.append(
            {
                "action": t,
                "in_streak": labels[t - 1],
                "new_screen_rate": p.new_screen_rate,
                "colours_changed": p.colours_changed,
                "activity_box_share": p.activity_box_share,
                "churn_ratio": p.churn_ratio,
                "cumulative_changes": p.cumulative_changes,
                "net_changes": p.net_changes,
            }
        )

    def mean(key: str, rs: list[dict]) -> float | None:
        vals = [r[key] for r in rs if r[key] is not None]
        return round(statistics.fmean(vals), 4) if vals else None

    inside = [r for r in rows if r["in_streak"]]
    outside = [r for r in rows if not r["in_streak"]]
    keys = ("new_screen_rate", "colours_changed", "activity_box_share", "churn_ratio")
    return {
        "recording": path.name,
        "game": frames[0]["game_id"],
        "actions": len(frames) - 1,
        "measured_steps": len(rows),
        "steps_in_long_streak": len(inside),
        "overall": {k: mean(k, rows) for k in keys},
        "inside_streak": {k: mean(k, inside) for k in keys} if inside else None,
        "outside_streak": {k: mean(k, outside) for k in keys} if outside else None,
        "churn_below_half": round(
            sum(1 for r in rows if r["churn_ratio"] is not None and r["churn_ratio"] < 0.5)
            / max(1, sum(1 for r in rows if r["churn_ratio"] is not None)),
            4,
        ),
        "per_step": rows,
    }


def churn_over_window(grids: list[list[list[int]]], window: int) -> float | None:
    """Mean churn ratio over an episode at one window size.

    Separate from `analyse` because the window is the one free parameter in the whole idea,
    and "we tried one window" is not an answer to "does this signal exist". A sweep is the
    difference between a negative result and an untested one.
    """
    from harness.frames import diff_grids

    vals = []
    for t in range(1, len(grids)):
        lo = max(0, t - window)
        if t - lo < 2:
            continue
        cumulative = sum(diff_grids(grids[i], grids[i + 1]).count for i in range(lo, t))
        if cumulative:
            vals.append(diff_grids(grids[lo], grids[t]).count / cumulative)
    return round(statistics.fmean(vals), 4) if vals else None


def repeat_cap_firing(frames: list[dict], caps: tuple[int, ...]) -> dict[str, float]:
    """Share of actions that a repeat-cap of each size would have refused.

    This is what sets the repetition guard's threshold in `harness/policies.py`. The rule we
    want is "you may repeat an action as often as chance would", so the cap has to be read
    off the *random* arms: whichever value a random player almost never trips is the value
    that cannot punish ordinary play.

    Games offering a single action are excluded from the count, because there repetition is
    forced rather than chosen — the same confound that made the raw favourite-action share
    unusable across games (`harness/evals.py`).
    """
    labels = []
    for f in frames[1:]:
        label = str(f["action_input"]["id"])
        data = f["action_input"].get("data") or {}
        if "x" in data and "y" in data:
            label += f"({data['x']},{data['y']})"
        labels.append((label, len(f["available_actions"])))

    out = {}
    for cap in caps:
        fired = run = 0
        previous = None
        for label, options in labels:
            run = run + 1 if label == previous else 1
            previous = label
            if run > cap and options > 1:
                fired += 1
        out[str(cap)] = round(fired / len(labels), 4) if labels else 0.0
    return out


def label_of(name: str) -> str:
    if "9669d0d5" in name:
        return "LLM 80 (THE STUCK RUN)"
    if ".random." in name:
        return "random"
    if "llm-h8" in name:
        return "LLM h8 (reverted arm)"
    if "llm-h0" in name:
        return "LLM h0 (current prompt)"
    if "llm-" in name or ".llm" in name:
        return "LLM"
    return "other"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--window", type=int, default=10)
    ap.add_argument("--out", default="progress-signals")
    args = ap.parse_args(argv)

    paths = sorted(RUNS.glob("*.recording.jsonl*"))
    if not paths:
        print("no recordings in runs/")
        return 1

    results = []
    for p in paths:
        try:
            r = analyse(p, args.window)
        except Exception as exc:  # a broken recording must not stop the sweep
            print(f"  skipped {p.name}: {exc}")
            continue
        if r:
            r["arm"] = label_of(p.name)
            results.append(r)

    # -- the decision table ------------------------------------------------- #
    stuck = [r for r in results if "STUCK" in r["arm"]]
    randoms = [r for r in results if r["arm"] == "random"]

    def group_mean(group: list[dict], key: str) -> float | None:
        vals = [r["overall"][key] for r in group if r["overall"].get(key) is not None]
        return round(statistics.fmean(vals), 4) if vals else None

    keys = ("new_screen_rate", "colours_changed", "activity_box_share", "churn_ratio")
    verdict = {}
    for k in keys:
        s, rnd = group_mean(stuck, k), group_mean(randoms, k)
        ratio = None
        if s is not None and rnd not in (None, 0):
            ratio = round(rnd / s, 3) if s else None
        verdict[k] = {"stuck_run": s, "random_runs": rnd, "random_over_stuck": ratio}

    # -- the window sweep --------------------------------------------------- #
    # `ls20` alone as well as everything, because the arms are not spread evenly over the
    # games and a mean across games compares different worlds. Holding the game constant is
    # the only version of this table that means anything.
    sweep: dict[str, dict[str, Any]] = {}
    for windows_label, only_ls20 in (("all_games", False), ("ls20_only", True)):
        by_arm: dict[str, list[list[float | None]]] = {}
        for p in paths:
            if only_ls20 and not p.name.startswith("ls20"):
                continue
            try:
                grids = [screen(f) for f in load_frames(p)]
            except Exception:
                continue
            if len(grids) < 3:
                continue
            by_arm.setdefault(label_of(p.name), []).append(
                [churn_over_window(grids, w) for w in SWEEP_WINDOWS]
            )
        sweep[windows_label] = {
            arm: {
                str(w): (
                    round(statistics.fmean(vals), 4)
                    if (vals := [r[i] for r in rows if r[i] is not None])
                    else None
                )
                for i, w in enumerate(SWEEP_WINDOWS)
            }
            for arm, rows in by_arm.items()
        }

    # -- what threshold the repetition guard should use ---------------------- #
    firing: dict[str, dict[str, Any]] = {}
    for p in paths:
        try:
            frames = load_frames(p)
        except Exception:
            continue
        if len(frames) < 3:
            continue
        firing[p.name] = {
            "arm": label_of(p.name),
            "game": frames[0]["game_id"],
            "actions": len(frames) - 1,
            "min_available_actions": min(len(f["available_actions"]) for f in frames[1:]),
            "would_fire": repeat_cap_firing(frames, REPEAT_CAPS),
        }

    payload = {
        "generated_from": "recordings committed in runs/",
        "window": args.window,
        "streak_label_min_length": STREAK_LABEL,
        "stuck_run": STUCK_RUN,
        "verdict": verdict,
        "churn_by_window": sweep,
        "sweep_windows": list(SWEEP_WINDOWS),
        "repeat_cap_firing_rates": firing,
        "repeat_caps": list(REPEAT_CAPS),
        "runs": [{k: v for k, v in r.items() if k != "per_step"} for r in results],
        "stuck_run_per_step": next(
            (r["per_step"] for r in results if "STUCK" in r["arm"]), []
        ),
    }
    ARTIFACTS.mkdir(exist_ok=True)
    out = ARTIFACTS / f"{args.out}.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    # -- print -------------------------------------------------------------- #
    print(f"window = {args.window} actions;  {len(results)} recordings\n")
    head = f"{'run':52} {'arm':22} {'new':>6} {'col':>6} {'box':>7} {'churn':>7}"
    print(head)
    print("-" * len(head))
    for r in sorted(results, key=lambda r: (r["arm"], r["recording"])):
        o = r["overall"]
        print(
            f"{r['recording'][:52]:52} {r['arm'][:22]:22} "
            f"{fmt(o['new_screen_rate'])} {fmt(o['colours_changed'])} "
            f"{fmt(o['activity_box_share'], 7)} {fmt(o['churn_ratio'], 7)}"
        )

    print("\nSEPARATION — does the signal tell the stuck run from random play?")
    print(f"{'signal':22} {'stuck run':>10} {'random':>10} {'random/stuck':>13}")
    print("-" * 58)
    for k, v in verdict.items():
        print(
            f"{k:22} {fmt(v['stuck_run'], 10)} {fmt(v['random_runs'], 10)} "
            f"{fmt(v['random_over_stuck'], 13)}"
        )

    for label, table in sweep.items():
        print(f"\nCHURN RATIO BY WINDOW — {label} (lower = work undoes itself)")
        print(f"{'arm':24}" + "".join(f"{w:>8}" for w in SWEEP_WINDOWS))
        print("-" * (24 + 8 * len(SWEEP_WINDOWS)))
        for arm in sorted(table):
            print(
                f"{arm[:24]:24}"
                + "".join(fmt(table[arm][str(w)], 8) for w in SWEEP_WINDOWS)
            )

    print("\nREPEAT-CAP FIRING RATE — share of actions each cap would refuse")
    print("(the guard's threshold is read off the random rows: it must not punish chance)")
    print(f"{'arm':24} {'game':16}" + "".join(f"{'>'+str(c):>8}" for c in REPEAT_CAPS))
    print("-" * (41 + 8 * len(REPEAT_CAPS)))
    for name in sorted(firing, key=lambda n: (firing[n]["arm"], firing[n]["game"])):
        f = firing[name]
        note = "  (1 option — cannot fire)" if f["min_available_actions"] <= 1 else ""
        print(
            f"{f['arm'][:24]:24} {f['game'][:16]:16}"
            + "".join(f"{f['would_fire'][str(c)]:>8.0%}" for c in REPEAT_CAPS)
            + note
        )

    inside = [r for r in results if r.get("inside_streak")]
    if inside:
        print("\nWITHIN an episode — inside a >=10 identical-action streak vs outside:")
        for r in inside:
            i, o = r["inside_streak"], r["outside_streak"] or {}
            print(
                f"  {r['recording'][:44]:44} churn inside={fmt(i['churn_ratio'])} "
                f"outside={fmt(o.get('churn_ratio'))} "
                f"(n={r['steps_in_long_streak']}/{r['measured_steps']})"
            )

    print(f"\nwrote {out}")
    return 0


def fmt(v: Any, width: int = 6) -> str:
    if v is None:
        return "-".rjust(width)
    return f"{v:>{width}.3f}" if isinstance(v, float) else f"{v:>{width}}"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
