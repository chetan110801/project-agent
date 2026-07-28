"""Read every committed trace and sort the agent's actions into named failure buckets.

    py scripts/failure_taxonomy.py [--out NAME] [--force]

A **failure taxonomy** is a sorted catalogue of the distinct ways the agent wastes a turn,
with counts, built from real traces (study note 02). It exists because "the agent is bad"
is not actionable and "63% of its actions produce fresh activity with no progress, 12% do
nothing at all, 8% repeat a dead button" is — each named bucket becomes a fix and an eval
case.

The rule this obeys (study notes 08 and 09): *a classifier invented from a story about a
failure is a guess until it is run against the failure.* So it reads the **committed**
traces — including the 80-action stuck run where the agent pressed one button 41 times in a
row — and the summary singles that run out, so the buckets can be checked against a failure
we already understand.

Source of truth is the trace, not the recording. Every field used here — `accepted`,
`cells_changed`, `score_delta`, `screen_hash`, `action` — is written by `harness/loop.py`
into the same `StepRecord` the agent acted on, so the taxonomy and the eval suite cannot
drift apart. The quarantined runs (`runs/aborted-*`, `runs/quota-wall-*`) live in
subdirectories and are excluded, exactly as every other aggregate excludes them.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.trace import Tracer  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
RUNS = ROOT / "runs"

# Perseveration = repeating one action beyond what chance ever does. Study note 09 measured
# that random play's longest identical streak is 3, and that it exceeds three-in-a-row on
# under 2% of its moves — so the *fourth* identical action in a row is the first repetition
# count chance essentially never produces. The threshold is that measured ceiling, not taste.
PERSEVERATION_STREAK = 4

# Priority order. Each action lands in the FIRST bucket it qualifies for, so the shares
# partition the actions and sum to 100%. Most-specific waste first, the catch-all last.
BUCKETS = [
    "illegal_action",      # asked for a button the frame said was unavailable (loop rejected it)
    "dead_action",         # legal, but the screen was byte-identical afterwards
    "revisit",             # legal and changed, but landed on a screen already seen this episode
    "perseveration",       # legal and changed and new, but the 4th+ identical action in a row
    "active_no_progress",  # legal, changed, new screen, not repetitive — and STILL no score. The wall.
    "progress",            # the score went up. The bucket that has stayed empty.
]

BUCKET_BLURB = {
    "illegal_action": "asked for an unavailable button (loop rejected it, forced RESET)",
    "dead_action": "legal, but changed nothing on screen",
    "revisit": "returned to a screen already seen this episode",
    "perseveration": f"repeated one action beyond chance (>={PERSEVERATION_STREAK} in a row)",
    "active_no_progress": "real, new activity on a fresh screen — and no progress",
    "progress": "the score moved",
}

FNAME = re.compile(r"^(?P<game>[^.]+)\.(?P<arm>[^.]+)\.")


def parse_name(path: Path) -> tuple[str, str, int | None]:
    """(arm label, attempt, max_actions) parsed from the run filename.

    Eval runs are `<game>.eval-...-<arm>.<policy>.<n>.[aK.]<guid>` and standalone runs are
    `<game>.<policy>.<n>.<guid>`. The arm we want is the short `eval-dev-llm-h0` for eval
    runs; for standalone runs there is no eval label, so we join the policy segments up to
    the action count — which reassembles a clean `llm-gemini-3.5-flash-lite-objects` instead
    of truncating at the dot inside the version number ("3.5" splits, producing "llm-gemini-3").
    """
    segs = path.name.split(".")
    attempt = next((s for s in segs if re.fullmatch(r"a\d+", s)), "")
    max_actions = next((int(s) for s in segs[1:] if s.isdigit()), None)
    if len(segs) > 1 and segs[1].startswith(("eval-", "random")):
        arm = segs[1]
    else:  # standalone: rejoin the policy label up to the action-count segment
        label: list[str] = []
        for s in segs[1:]:
            if s.isdigit():
                break
            label.append(s)
        arm = ".".join(label) if label else (segs[1] if len(segs) > 1 else path.stem)
    return arm, attempt, max_actions


def policy_family(policy: str) -> str:
    """'llm' or 'random' — the two families we compare. LLM names look like
    'llm:gemini-3.5-flash-lite:objects:h0'; the baseline is 'random...'."""
    return "random" if "random" in policy.lower() else "llm"


def classify_episode(steps: list[dict]):
    """Yield (bucket, step) for each step in order. Episode-local memory: the screens seen so
    far and the current run of identical actions."""
    seen: set[str] = set()
    prev_label: str | None = None
    streak = 0
    for s in steps:
        label = s.get("action", "")
        streak = streak + 1 if label == prev_label else 1
        prev_label = label

        accepted = bool(s.get("accepted", True))
        changed = s.get("cells_changed", 0)
        delta = s.get("score_delta", 0) or 0
        h = s.get("screen_hash") or ""

        if not accepted:
            bucket = "illegal_action"
        elif delta > 0:
            bucket = "progress"
        elif changed == 0:
            bucket = "dead_action"
        elif h and h in seen:
            bucket = "revisit"
        elif streak >= PERSEVERATION_STREAK:
            bucket = "perseveration"
        else:
            bucket = "active_no_progress"

        if h:
            seen.add(h)
        yield bucket, s


def episode_counts(steps: list[dict]) -> tuple[Counter, int]:
    """Bucket counts and the longest identical-action streak for one episode."""
    c: Counter = Counter()
    prev_label = None
    streak = longest = 0
    for bucket, s in classify_episode(steps):
        c[bucket] += 1
        label = s.get("action", "")
        streak = streak + 1 if label == prev_label else 1
        longest = max(longest, streak)
        prev_label = label
    return c, longest


def shares(counter: Counter) -> dict:
    """{bucket: {count, share}} in BUCKETS order, plus the total. Pooled, never averaged —
    a 30-action arm and a 6-action arm contribute their raw counts (study note 08)."""
    total = sum(counter.values())
    rows = {
        b: {"count": counter.get(b, 0),
            "share": round(counter.get(b, 0) / total, 4) if total else 0.0}
        for b in BUCKETS
    }
    return {"actions": total, "buckets": rows}


def load_episodes() -> list[tuple[dict, list[dict]]]:
    """(meta, steps) for every top-level trace in runs/. Subdirectories are quarantined."""
    out = []
    for path in sorted(RUNS.glob("*.trace.jsonl")):
        records = Tracer.read(path)
        start = next((r for r in records if r.get("kind") == "episode_start"), {})
        steps = [r for r in records if r.get("kind") == "step"]
        if not steps:
            continue
        arm, attempt, max_actions = parse_name(path)
        policy = start.get("policy", "?")
        out.append((
            {
                "file": path.name,
                "game_id": start.get("game_id", path.name.split(".")[0]),
                "policy": policy,
                "family": policy_family(policy),
                "arm": arm,
                "attempt": attempt,
                "max_actions": max_actions,
                "actions": len(steps),
            },
            steps,
        ))
    return out


def group(episodes, key) -> dict:
    """Pool bucket counts over episodes grouped by key(meta) -> label."""
    buckets_by: dict[str, Counter] = {}
    eps_by: Counter = Counter()
    for meta, steps in episodes:
        label = key(meta)
        buckets_by.setdefault(label, Counter())
        c, _ = episode_counts(steps)
        buckets_by[label].update(c)
        eps_by[label] += 1
    return {
        label: {"episodes": eps_by[label], **shares(c)}
        for label, c in sorted(buckets_by.items())
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", default="failure-taxonomy", help="artifacts/<NAME>.json")
    ap.add_argument("--force", action="store_true", help="overwrite (there is only one source set)")
    args = ap.parse_args(argv)

    episodes = load_episodes()
    if not episodes:
        print("no traces in runs/ — nothing to classify")
        return 1

    llm = [e for e in episodes if e[0]["family"] == "llm"]
    rnd = [e for e in episodes if e[0]["family"] == "random"]
    llm_eval = [e for e in llm if e[0]["arm"].startswith("eval-")]

    # The current default configuration is guards-on / no-hypothesis / no-progress: that is
    # arm r3, and p0 attempt 1 (its control prompt is byte-identical). This is "the agent as
    # it stands", so it is the headline the note leans on.
    default_now = [e for e in llm if e[0]["arm"] in ("eval-dev-llm-r3",)]

    # The validation case: the 80-action ls20 run where the agent pressed one button 41 times.
    # Found, not assumed — the single llm episode with the longest identical streak.
    stuck = max(llm, key=lambda e: episode_counts(e[1])[1])
    stuck_counts, stuck_longest = episode_counts(stuck[1])

    report = {
        "generated_from": "runs/*.trace.jsonl (top-level only; aborted-* and quota-wall-* quarantined)",
        "perseveration_streak_threshold": PERSEVERATION_STREAK,
        "bucket_order": BUCKETS,
        "bucket_meaning": BUCKET_BLURB,
        "episodes_read": len(episodes),
        "actions_classified": sum(m["actions"] for m, _ in episodes),
        "headline_llm_default_now": {
            "arm": "eval-dev-llm-r3 (guards on, no hypothesis, no progress = current default)",
            **({"episodes": len(default_now), **shares(sum((episode_counts(s)[0] for _, s in default_now), Counter()))}
               if default_now else {"note": "arm not found"}),
        },
        "by_family": {
            "llm_all": {"episodes": len(llm), **shares(sum((episode_counts(s)[0] for _, s in llm), Counter()))},
            "llm_eval_arms": {"episodes": len(llm_eval), **shares(sum((episode_counts(s)[0] for _, s in llm_eval), Counter()))},
            "random_all": {"episodes": len(rnd), **shares(sum((episode_counts(s)[0] for _, s in rnd), Counter()))},
        },
        "llm_by_arm": group(llm, lambda m: m["arm"]),
        "llm_by_game": group(llm_eval, lambda m: m["game_id"]),
        "random_by_game": group(rnd, lambda m: m["game_id"]),
        "validation_stuck_run": {
            "file": stuck[0]["file"],
            "policy": stuck[0]["policy"],
            "actions": stuck[0]["actions"],
            "longest_identical_streak": stuck_longest,
            **shares(stuck_counts),
            "note": (
                "the classifier is run against a failure we already understand: this is the "
                "run study notes 05/08/09 describe (one button 41 times). perseveration should "
                "dominate — if it did not, the bucket would be wrong."
            ),
        },
    }

    # The source set is the committed traces and the classification is deterministic, so a
    # re-run reproduces the file byte-for-byte; overwriting is always safe (unlike
    # analyze_run.py, which can be pointed at a different recording). --force is accepted for
    # symmetry with the other scripts but changes nothing here.
    out = ARTIFACTS / f"{args.out}.json"
    ARTIFACTS.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    # ---- printed summary ------------------------------------------------- #
    def line(label: str, block: dict) -> None:
        b = block["buckets"]
        cells = "  ".join(f"{name.split('_')[0][:6]:>6} {b[name]['share']:>5.0%}" for name in BUCKETS)
        print(f"{label:<34} n={block['actions']:>4}  {cells}")

    print(f"episodes read : {report['episodes_read']}  "
          f"actions classified : {report['actions_classified']}")
    print(f"perseveration = >={PERSEVERATION_STREAK} identical in a row "
          f"(random's ceiling is 3, note 09)\n")
    print(f"{'':<34} {'':>6}  " + "  ".join(f"{n.split('_')[0][:6]:>6} {'':>5}" for n in BUCKETS))
    line("LLM - current default (r3)", report["headline_llm_default_now"])
    line("LLM - all eval arms pooled", report["by_family"]["llm_eval_arms"])
    line("random - baseline (all)", report["by_family"]["random_all"])
    print()
    print("LLM by arm:")
    for arm, block in report["llm_by_arm"].items():
        line(f"  {arm}", block)
    print()
    print("LLM by game (eval arms):")
    for g, block in report["llm_by_game"].items():
        line(f"  {g}", block)
    print()
    v = report["validation_stuck_run"]
    print(f"validation - stuck run ({v['actions']} actions, longest streak {v['longest_identical_streak']}):")
    line(f"  {v['file'][:32]}", v)
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
