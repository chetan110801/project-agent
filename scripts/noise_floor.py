"""Measure how much an A/B difference moves when **nothing changes at all**.

    py scripts/noise_floor.py [--out NAME] [--min-replicates 2]

Every verdict in this project is a difference between two arms run once each. Such a
difference is only evidence if it is bigger than the difference two *identical* arms
would have produced. That quantity is the **noise floor** (the spread you get from
re-running the same configuration), and until this script existed the project quoted a
single anecdote for it: on `tn36` the repetition guard never fired, so its prompt was
unchanged, and its unparseable replies still moved 9 -> 14 of 30 (study note 09). One
metric, one game, one pair — generalised to every metric in every table.

**This script gets the real thing for free, from runs already on disk.** Four eval runs
per game turn out to be the *same effective configuration*, so the only thing separating
them is the language model's own sampling:

* `dev-llm-r3` — the guards-on control;
* `dev-llm-p0` attempt 1 and attempt 2 — the progress arm's control, `progress=False`
  in both attempts;
* `dev-llm-p1` attempt 1 — the progress signal only speaks from attempt 2 on, so
  attempt 1 carries no progress block.

That identity is not a guess. `render_progress_block(None)` returns `""` and
`hypothesis=False` leaves the theory block empty, which keeps the prompt the Phase B
control prompt byte for byte — both have golden tests, and `scripts/failure_taxonomy.py`
already leans on the same fact. This script re-derives the grouping from the stored
configs anyway (`fingerprint`), so it cannot quietly pool two configurations that only
look alike.

**What comes out, and why it is stronger than a range.** With four runs of each of four
games there are many ways to deal those 16 episodes into two four-game arms that share no
episode at all — 12 ordered choices per game, so 12^4 = 20,736 pairs. Both arms in every
one of those pairs are the *same configuration*, so every difference between them is
noise by construction. Enumerating all of them exhaustively (not sampling) gives the
**null distribution** (*the differences a change-free experiment produces*) of each
metric. Its 95th percentile is the honest answer to "how big must a difference be before
it is not just sampling?" — `null_p95` below. Each arm's aggregate is computed by
`Arm.aggregate()` itself, so the band belongs to the very numbers the tables report and
cannot drift from them.

The last section applies that test to every comparison already in `artifacts/evals/`,
which is the point: this re-audits past verdicts instead of only advising future ones.

**Three honest limits, stated in the output as well as here.**

1. The null is built from 16 real episodes, so it inherits their luck. Four draws per game
   can miss the tails: a band is a lower bound on the spread, and more runs can only widen
   it. A difference inside the band is decisively not evidence; a difference just outside
   it is suggestive, not proven.
2. Both sides of a real A/B are single runs, so clearing `null_p95` means "larger than 95%
   of change-free differences", not a p-value from a test with replicated arms.
3. The null is measured on one configuration (LLM, `objects`, no history, `repeat_limit
   3`, 30 actions, the four dev games) and applied only to comparisons between two LLM
   arms. A random-policy baseline is a different generator with its own variance, so the
   random-vs-LLM comparison is listed as out of scope rather than silently judged.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.evals import COST, OUTCOME, STEERING, Arm, Metrics  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
EVAL_DIR = ARTIFACTS / "evals"

_METRIC_FIELDS = set(Metrics.__dataclass_fields__)

# The settings that reach the agent. Anything outside this set may differ between two runs
# without making them different configurations — `attempts` schedules how many replays
# happen and does not change any single one of them, and `mock` is off in every real run.
# Absent keys take the default the harness itself uses, which is how an arm recorded before
# a flag existed still matches one recorded after (r3 predates --hypothesis/--progress).
CONFIG_DEFAULTS = {
    "policy": None,
    "model": None,
    "encoder": None,
    "history": 0,
    "max_actions": None,
    "seed": 0,
    "repeat_limit": None,
    "hypothesis": False,
}

# Metrics that are counts of an intervention rather than measures of play. They are 0 or
# None across a control group by construction, so a band of 0 for them says nothing about
# noise and would be misread as "this metric is perfectly stable".
NOT_PLAY = ("repeat_blocks", "hypothesis_changes", "prediction_hit_rate",
            "hypothesis_stated_rate")

METRIC_KINDS = [("steering", STEERING), ("outcome", OUTCOME), ("cost", COST)]


def is_rate(metric: str) -> bool:
    """True for the metrics measured as a proportion of actions.

    Needed because "the widest band" is only a meaningful phrase within one unit. A band of
    2.0 on `distinct_targets` (a count of screen positions) is not wider or narrower than a
    band of 0.09 on `no_change_rate` (a share of turns) — comparing them would produce a
    confident headline about nothing. The rate metrics all live on 0..1, so a percentage-point
    band is comparable across them and only across them.
    """
    return metric.endswith(("_rate", "_share", "_excess"))


def fingerprint(config: dict[str, Any], attempt: int) -> tuple:
    """The configuration as the agent experiences it on **this** attempt.

    `progress` is the one flag whose effect depends on the attempt: the signal is the
    previous attempt's scorecard summary, so an arm with `progress=True` still runs the
    untouched control prompt on attempt 1. Folding the attempt in here is what makes
    `dev-llm-p1` attempt 1 a replicate of `dev-llm-r3` instead of a different arm.
    """
    base = tuple(sorted(
        (key, config.get(key, default)) for key, default in CONFIG_DEFAULTS.items()
    ))
    progress_active = bool(config.get("progress")) and attempt >= 2
    return base + (("progress_active", progress_active),)


def describe(fp: tuple) -> str:
    """One readable line for a fingerprint, for the report and the printed table."""
    d = dict(fp)
    bits = [str(d.get("policy")), str(d.get("model")), str(d.get("encoder")),
            f"h{d.get('history')}", f"{d.get('max_actions')}a", f"seed{d.get('seed')}"]
    if d.get("repeat_limit"):
        bits.append(f"r{d['repeat_limit']}")
    if d.get("hypothesis"):
        bits.append("hypothesis")
    if d.get("progress_active"):
        bits.append("progress")
    return " ".join(b for b in bits if b and b != "None")


def load_arms() -> list[dict[str, Any]]:
    """Every arm file in artifacts/evals/, raw. Comparison files are not arms."""
    out = []
    for path in sorted(EVAL_DIR.glob("*.json")):
        if path.name.startswith("comparison-"):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if "episodes" in data and "config" in data:
            data["_file"] = path.name
            out.append(data)
    return out


def replicate_runs(arms: list[dict[str, Any]]) -> dict[tuple, list[dict[str, Any]]]:
    """Group every (arm, attempt) slice by effective configuration.

    One slice = one full pass over the suite under one configuration, which is the unit a
    change is judged in, so it is the unit whose spread we need.
    """
    groups: dict[tuple, list[dict[str, Any]]] = {}
    for data in arms:
        by_attempt: dict[int, list[dict]] = {}
        for ep in data["episodes"]:
            by_attempt.setdefault(int(ep.get("attempt", 1)), []).append(ep)
        for attempt, eps in sorted(by_attempt.items()):
            fp = fingerprint(data["config"], attempt)
            groups.setdefault(fp, []).append({
                "arm": data["arm"],
                "attempt": attempt,
                "label": f"{data['arm']}"
                         + (f" attempt {attempt}" if len(by_attempt) > 1 else ""),
                "suite": data["suite"],
                "episodes": eps,
            })
    return groups


def aggregate_of(run: dict[str, Any], games: list[str]) -> dict[str, Any]:
    """One replicate's aggregate over `games`, computed by the eval suite's own code.

    Restricted to the shared game list and reusing `Arm.aggregate()` rather than
    re-deriving it: a noise band built by a second, private definition of the same metrics
    would not be a band for the numbers anyone actually reports.
    """
    eps = [ep for ep in run["episodes"] if ep.get("game_id") in games]
    arm = Arm(
        name=run["label"],
        suite=run["suite"],
        games=games,
        episodes=[Metrics(**{k: v for k, v in ep.items() if k in _METRIC_FIELDS})
                  for ep in eps],
    )
    return arm.aggregate()


def _numeric(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def null_distribution(
    runs: list[dict[str, Any]], games: list[str], suite: str
) -> tuple[dict[str, Any], int]:
    """The differences a change-free A/B produces, by exhaustive enumeration.

    Deal the replicates into two arms that share **no episode**: for each game pick run `i`
    for the left arm and run `j != i` for the right. Every such pair is one complete
    experiment in which the treatment is nothing at all, so the spread of its differences is
    exactly the noise an A/B on this suite carries.

    Two design points that matter more than the arithmetic:

    * **Disjoint, not merely different.** Letting both arms reuse one episode would make
      their difference artificially small on that game and flatter the null, which would in
      turn flatter every verdict judged against it.
    * **Exhaustive, not sampled.** 20,736 pairs is small enough to enumerate, so the
      percentiles are properties of the data rather than of a random seed — which is the
      same standard the eval suite holds its own baseline to.

    Returns the per-metric summary and the number of pairs enumerated.
    """
    import itertools

    # Episodes indexed [game][replicate]. A game a run never played drops the whole game,
    # because an arm missing a game is not comparable to one that has it.
    by_game: list[list[dict]] = []
    for game in games:
        col = []
        for run in runs:
            ep = next((e for e in run["episodes"] if e.get("game_id") == game), None)
            if ep is not None:
                col.append(ep)
        by_game.append(col)

    def agg(choice: tuple[int, ...]) -> dict[str, Any]:
        arm = Arm(
            name="null",
            suite=suite,
            games=games,
            episodes=[
                Metrics(**{k: v for k, v in by_game[g][idx].items() if k in _METRIC_FIELDS})
                for g, idx in enumerate(choice)
            ],
        )
        return arm.aggregate()

    # One aggregate per distinct deal (4^4 = 256 here), computed once and reused across the
    # pairs that contain it — 41,472 aggregate() calls collapse to 256.
    cache: dict[tuple[int, ...], dict[str, Any]] = {}
    for choice in itertools.product(*[range(len(col)) for col in by_game]):
        cache[choice] = agg(choice)

    diffs: dict[str, list[float]] = {}
    pairs = 0
    ordered = [
        [(i, j) for i in range(len(col)) for j in range(len(col)) if i != j]
        for col in by_game
    ]
    for combo in itertools.product(*ordered):
        left = tuple(i for i, _ in combo)
        right = tuple(j for _, j in combo)
        a, b = cache[left], cache[right]
        pairs += 1
        for kind, names in METRIC_KINDS:
            for metric in names:
                if metric in NOT_PLAY:
                    continue
                x, y = a.get(metric), b.get(metric)
                if _numeric(x) and _numeric(y):
                    diffs.setdefault(metric, []).append(abs(x - y))

    kind_of = {m: kind for kind, names in METRIC_KINDS for m in names}
    out: dict[str, Any] = {}
    for metric, vals in diffs.items():
        vals.sort()
        out[metric] = {
            "kind": kind_of[metric],
            "null_p50": round(vals[len(vals) // 2], 4),
            "null_p95": round(vals[min(len(vals) - 1, int(0.95 * len(vals)))], 4),
            "null_max": round(vals[-1], 4),
            "null_mean": round(statistics.fmean(vals), 4),
            # A metric no change-free pair ever moved. Consistent with a stable metric, but
            # 16 episodes cannot prove a band below their own resolution — so it is reported
            # as "never moved here", never as "cannot move".
            "never_moved": vals[-1] == 0,
        }
    return out, pairs


def band(values: list[Any]) -> dict[str, Any] | None:
    """min / max / band / mean / sd over one metric's replicate values.

    None when fewer than two runs measured the metric numerically — a band over one number
    is zero, and reporting that as stability is the exact error this file exists to stop.
    """
    nums = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if len(nums) < 2:
        return None
    return {
        "n": len(nums),
        "values": nums,
        "min": round(min(nums), 4),
        "max": round(max(nums), 4),
        "band": round(max(nums) - min(nums), 4),
        "mean": round(statistics.fmean(nums), 4),
        "sd": round(statistics.stdev(nums), 4),
    }


def per_game_bands(runs: list[dict[str, Any]], games: list[str]) -> dict[str, Any]:
    """Per game, per metric, the spread across identical runs of that single game.

    The suite aggregate hides this: four games pooled can look steady while one game swings
    end to end. Every "one game moved N points" claim in the notes is an episode-level
    statement, so it needs an episode-level band to be judged against.
    """
    out: dict[str, Any] = {}
    for game in games:
        rows = {}
        for kind, names in METRIC_KINDS:
            for metric in names:
                if metric in NOT_PLAY:
                    continue
                vals = []
                for run in runs:
                    ep = next((e for e in run["episodes"] if e.get("game_id") == game), None)
                    if ep is not None:
                        vals.append(ep.get(metric))
                b = band(vals)
                if b:
                    rows[metric] = {"kind": kind, **b}
        out[game] = rows
    return out


def audit_comparisons(null: dict[str, Any]) -> list[dict[str, Any]]:
    """Re-judge every stored comparison against the enumerated null.

    A row is `inside_noise` when the two arms differ by no more than 95% of change-free
    pairs did. That is not "the change did nothing" — it is "this experiment could not have
    told the difference", which is a statement about the measurement and the only one a
    single run per arm supports. Rows that clear it are labelled `exceeds_null_max` when
    they are larger than *every* change-free difference, which is the strongest thing this
    design can say.
    """
    out = []
    for path in sorted(EVAL_DIR.glob("comparison-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        llm_only = "random" not in f"{data['before']} {data['after']}"
        rows = []
        for row in data["rows"]:
            n = null.get(row["metric"])
            before, after = row.get("before"), row.get("after")
            if not n or not (_numeric(before) and _numeric(after)):
                continue
            diff = round(abs(after - before), 4)
            rows.append({
                "metric": row["metric"],
                "kind": row["kind"],
                "before": before,
                "after": after,
                "abs_diff": diff,
                "null_p95": n["null_p95"],
                "null_max": n["null_max"],
                "inside_noise": diff <= n["null_p95"],
                "exceeds_null_max": diff > n["null_max"],
                "direction_claimed": row.get("direction", ""),
            })
        inside = [r for r in rows if r["inside_noise"]]
        out.append({
            "comparison": path.name,
            "before": data["before"],
            "after": data["after"],
            "single_variable": data.get("single_variable"),
            "in_scope": llm_only,
            "scope_note": (
                "both arms are LLM arms of the measured configuration family"
                if llm_only else
                "OUT OF SCOPE: a random-policy arm is a different generator with its own "
                "variance; the null measured here does not apply to it"
            ),
            "rows_judged": len(rows),
            "rows_inside_noise": len(inside),
            "survivors": [
                {"metric": r["metric"], "kind": r["kind"], "before": r["before"],
                 "after": r["after"], "abs_diff": r["abs_diff"],
                 "null_p95": r["null_p95"], "exceeds_null_max": r["exceeds_null_max"],
                 "direction_claimed": r["direction_claimed"]}
                for r in rows if not r["inside_noise"]
            ],
            "rows": rows,
        })
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", default="noise-floor", help="artifacts/<NAME>.json")
    ap.add_argument("--min-replicates", type=int, default=2,
                    help="smallest group size worth reporting a band for")
    args = ap.parse_args(argv)

    arms = load_arms()
    if not arms:
        print(f"no arm files in {EVAL_DIR} — nothing to measure")
        return 1

    groups = replicate_runs(arms)
    usable = {fp: runs for fp, runs in groups.items() if len(runs) >= args.min_replicates}
    if not usable:
        print("no configuration was run more than once — no noise floor can be measured")
        return 1

    # The headline group is simply the largest one — found, not hard-coded, so adding
    # replicates later moves the headline without an edit here.
    reports = []
    for fp, runs in sorted(usable.items(), key=lambda kv: -len(kv[1])):
        shared = sorted(
            set.intersection(*[{ep.get("game_id") for ep in r["episodes"]} for r in runs])
        )
        if not shared:
            continue
        aggs = {r["label"]: aggregate_of(r, shared) for r in runs}
        bands: dict[str, Any] = {}
        for kind, names in METRIC_KINDS:
            for metric in names:
                if metric in NOT_PLAY:
                    continue
                b = band([a.get(metric) for a in aggs.values()])
                if b:
                    bands[metric] = {"kind": kind, **b}
        null, pairs = null_distribution(runs, shared, runs[0]["suite"])
        reports.append({
            "config": describe(fp),
            "config_fields": dict(fp),
            "replicates": len(runs),
            "runs": [r["label"] for r in runs],
            "games": shared,
            "aggregates": aggs,
            "observed_bands": bands,
            "null_pairs_enumerated": pairs,
            "null": null,
            "per_game_bands": per_game_bands(runs, shared),
        })

    head = reports[0]
    report = {
        "generated_from": "artifacts/evals/*.json (arm files); no new runs, no quota spent",
        "what_this_is": (
            "the differences a change-free A/B produces on this suite, by exhaustive "
            "enumeration of every way of dealing runs of ONE configuration into two arms "
            "that share no episode. an A/B difference no larger than null_p95 is not "
            "evidence."
        ),
        "limits": [
            f"the null is built from {head['replicates']} runs of each of "
            f"{len(head['games'])} games, so it inherits their luck: more runs can only "
            "widen it. a difference inside the band is decisively not evidence; one just "
            "outside is suggestive, not proven",
            "both sides of a real A/B are single runs, so clearing null_p95 means 'larger "
            "than 95% of change-free differences', not a p-value from a replicated test",
            "the null is measured on one configuration and applied only to comparisons "
            "between two LLM arms; a random-policy arm is a different generator",
            "intervention counts (repeat_blocks, hypothesis_*) are excluded: they are 0 or "
            "absent across a control group by construction, so their spread is not noise",
        ],
        "headline": {
            "config": head["config"],
            "replicates": head["replicates"],
            "runs": head["runs"],
            "games": head["games"],
            "pairs_enumerated": head["null_pairs_enumerated"],
            "steering_p95": {
                m: n["null_p95"] for m, n in sorted(head["null"].items())
                if n["kind"] == "steering"
            },
            # Compared within one unit only (see `is_rate`): the widest change-free swing in
            # any share-of-actions metric, which is the number a blanket "N-point noise
            # floor" claim is really about.
            "widest_rate_p95": max(
                (
                    {"metric": m, "null_p95": n["null_p95"], "null_max": n["null_max"]}
                    for m, n in head["null"].items() if is_rate(m)
                ),
                key=lambda r: r["null_p95"], default=None,
            ),
            "never_moved_metrics": sorted(
                m for m, n in head["null"].items() if n["never_moved"]
            ),
            # The suite aggregate hides how badly one game can swing, and a per-game claim
            # has to be judged against a per-game band. Rate metrics only, same reason.
            "noisiest_single_game_rate": max(
                (
                    {"game": g, "metric": m, "band": b["band"],
                     "values": b["values"], "kind": b["kind"]}
                    for g, rows in head["per_game_bands"].items()
                    for m, b in rows.items() if is_rate(m)
                ),
                key=lambda r: r["band"], default=None,
            ),
        },
        "groups": reports,
        "comparison_audit": audit_comparisons(head["null"]),
    }

    out = ARTIFACTS / f"{args.out}.json"
    ARTIFACTS.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    # ---- printed summary -------------------------------------------------- #
    print(f"replicate groups found (>= {args.min_replicates} runs of one configuration): "
          f"{len(reports)}")
    for g in reports:
        print(f"\n  {g['config']}")
        print(f"  {g['replicates']} identical runs over {len(g['games'])} games: "
              f"{', '.join(g['runs'])}")
    print(f"\nHEADLINE GROUP - {head['config']}")
    print(f"{head['null_pairs_enumerated']} change-free arm pairs enumerated "
          f"(no episode shared between the two arms of a pair)\n")
    print(f"{'metric':<26}{'kind':<10}{'obs.range':>11}{'null p50':>10}"
          f"{'null p95':>10}{'null max':>10}")
    for metric, n in sorted(
        head["null"].items(), key=lambda kv: (kv[1]["kind"], -kv[1]["null_p95"])
    ):
        obs = head["observed_bands"].get(metric, {}).get("band", "-")
        print(f"{metric:<26}{n['kind']:<10}{obs:>11}{n['null_p50']:>10}"
              f"{n['null_p95']:>10}{n['null_max']:>10}")

    print("\nWidest single-game swings under an unchanged configuration:")
    worst = []
    for game, rows in head["per_game_bands"].items():
        for metric, b in rows.items():
            if b["kind"] != "outcome" and b["band"]:
                worst.append((b["band"], game, metric, b["min"], b["max"]))
    for bandv, game, metric, lo, hi in sorted(worst, reverse=True)[:8]:
        print(f"  {game:<16}{metric:<26}{lo} -> {hi}   band {bandv}")

    print("\nEvery stored comparison, re-judged against the null:")
    for c in report["comparison_audit"]:
        scope = "" if c["in_scope"] else "  [OUT OF SCOPE - random arm]"
        print(f"\n  {c['before']} -> {c['after']}{scope}")
        print(f"    {c['rows_inside_noise']}/{c['rows_judged']} rows inside noise")
        for s in c["survivors"]:
            tag = "beyond every change-free pair" if s["exceeds_null_max"] else "> p95"
            print(f"      SURVIVES  {s['metric']:<24}{s['before']} -> {s['after']}"
                  f"   |d|={s['abs_diff']} vs p95 {s['null_p95']}  ({tag}, "
                  f"{s['direction_claimed'] or 'no direction claimed'})")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
