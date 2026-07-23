"""Did the falsification loop actually do anything? Read back out of the traces.

    py scripts/hypothesis_report.py --arm dev-llm-y1

Writes `artifacts/hypothesis-report.json` and prints the table.

The eval suite answers *did the numbers move*. This answers the question underneath it:
**when the harness told the agent its prediction was wrong, did the agent change its mind?**
That is the mechanism the whole arm rests on, and it is not visible in any aggregate —
`hypothesis_changes` counts changes of theory but not what preceded them, so an agent that
reworded its theory at random would score the same as one that revised after being refuted.

The conditional is the finding either way:

* changes far more often after a **wrong** prediction than after one that **held** — the
  falsification is doing the work it was built to do.
* changes at the same rate either way — the agent is churning theories, and the verdict is
  decoration. That would be a negative result about the intervention, not about the agent.

Everything here is read from `runs/*.trace.jsonl`, which records the model's own reply and
the cells its action changed. No model is called and no quota is spent.

One limit, stated rather than hidden: the trace's `cells_changed` is the loop's count, and a
screen that changed *shape* is recorded by the loop as a number this script cannot
distinguish from a normal one. The policy treats a shape change as *unknown* and never grades
a prediction on it, so a run containing one would make this report's counts drift from the
policy's own. Measured across every recording on disk: it has never happened.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.hypothesis import judge, parse_hypothesis, same_goal  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
ARTIFACTS = ROOT / "artifacts"


def steps_of(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [r for r in rows if r.get("kind") == "step"]


def walk(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Replay the policy's own bookkeeping over one episode's trace.

    Deliberately mirrors `LLMPolicy._record_theory`, including the rule that a reply with no
    GOAL line leaves the previous theory standing. If this drifts from the policy the two
    will disagree about the same run, so the numbers it produces are checked against the
    arm's artifact in `main`.
    """
    out = []
    goal: str | None = None
    for s in steps:
        stated = parse_hypothesis(s.get("reasoning", ""))
        changed = bool(stated.goal and goal and not same_goal(goal, stated.goal))
        goal = stated.goal or goal
        verdict = judge(stated.prediction, s.get("cells_changed"))
        out.append(
            {
                "index": s["index"],
                "action": s["action"],
                "goal": goal,
                "goal_stated": bool(stated.goal),
                "goal_changed": changed,
                "prediction": stated.prediction,
                "cells_changed": s.get("cells_changed"),
                "verdict": None if verdict.correct is None else ("held" if verdict.correct else "wrong"),
            }
        )
    return out


def episode_report(path: Path) -> dict[str, Any]:
    rows = walk(steps_of(path))
    # The theory stated on turn t is judged by what turn t's action did; the *response* to
    # that judgement is whatever the agent says on turn t+1. So the conditional is read one
    # step forward, and turns with no verdict are excluded rather than counted as "held".
    after: dict[str, dict[str, int]] = {"wrong": {"n": 0, "changed": 0}, "held": {"n": 0, "changed": 0}}
    for now, nxt in zip(rows, rows[1:]):
        if now["verdict"] in after:
            after[now["verdict"]]["n"] += 1
            after[now["verdict"]]["changed"] += bool(nxt["goal_changed"])

    theories: list[str] = []
    for r in rows:
        if r["goal_stated"] and (not theories or not same_goal(theories[-1], r["goal"])):
            theories.append(r["goal"])
    return {
        "trace": path.name,
        "game": path.name.split(".", 1)[0],
        "actions": len(rows),
        "goals_stated": sum(r["goal_stated"] for r in rows),
        "goal_changes": sum(r["goal_changed"] for r in rows),
        "predictions": sum(r["prediction"] is not None for r in rows),
        "checked": sum(r["verdict"] is not None for r in rows),
        "wrong": sum(r["verdict"] == "wrong" for r in rows),
        "prediction_mix": {
            b: sum(r["prediction"] == b for r in rows) for b in ("NONE", "FEW", "MANY")
        },
        "changed_after": {
            k: {**v, "rate": round(v["changed"] / v["n"], 4) if v["n"] else None}
            for k, v in after.items()
        },
        "distinct_theories": len(theories),
        "theories": theories,
        "steps": rows,
    }


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Read the falsification loop back out of traces.")
    p.add_argument("--arm", default="dev-llm-y1", help="arm name as used by run_evals.py")
    args = p.parse_args(argv)

    traces = sorted(RUNS.glob(f"*.eval-{args.arm}.*.trace.jsonl"))
    if not traces:
        raise SystemExit(f"no traces for arm {args.arm!r} in {RUNS}")
    episodes = [episode_report(t) for t in traces]

    totals = {k: sum(e[k] for e in episodes) for k in ("actions", "goals_stated", "goal_changes", "predictions", "checked", "wrong")}
    pooled = {
        k: {
            "n": sum(e["changed_after"][k]["n"] for e in episodes),
            "changed": sum(e["changed_after"][k]["changed"] for e in episodes),
        }
        for k in ("wrong", "held")
    }
    for v in pooled.values():
        v["rate"] = round(v["changed"] / v["n"], 4) if v["n"] else None

    payload = {
        "arm": args.arm,
        "generated_from": [t.name for t in traces],
        "totals": totals,
        "prediction_mix": {
            b: sum(e["prediction_mix"][b] for e in episodes) for b in ("NONE", "FEW", "MANY")
        },
        "changed_theory_after": pooled,
        "episodes": episodes,
    }
    ARTIFACTS.mkdir(exist_ok=True)
    out = ARTIFACTS / f"hypothesis-report-{args.arm}.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"arm: {args.arm}  ({len(episodes)} games, {totals['actions']} actions)\n")
    print(f"{'game':18} {'stated':>7} {'changes':>8} {'checked':>8} {'wrong':>6} {'theories':>9} {'chg|wrong':>10} {'chg|held':>9}")
    for e in episodes:
        w = e["changed_after"]["wrong"]["rate"]
        h = e["changed_after"]["held"]["rate"]
        print(
            f"{e['game']:18} {e['goals_stated']:>7} {e['goal_changes']:>8} {e['checked']:>8} "
            f"{e['wrong']:>6} {e['distinct_theories']:>9} "
            f"{'-' if w is None else format(w, '.0%'):>10} {'-' if h is None else format(h, '.0%'):>9}"
        )
    print(
        f"\npooled: theory changed after a WRONG prediction "
        f"{pooled['wrong']['changed']}/{pooled['wrong']['n']}"
        f" ({'-' if pooled['wrong']['rate'] is None else format(pooled['wrong']['rate'], '.0%')}), "
        f"after one that HELD {pooled['held']['changed']}/{pooled['held']['n']}"
        f" ({'-' if pooled['held']['rate'] is None else format(pooled['held']['rate'], '.0%')})"
    )
    print(f"predictions offered: {payload['prediction_mix']}")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
