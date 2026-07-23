"""Run one configuration over the eval suite and write the numbers it will be judged on.

    py scripts/run_evals.py --arm random --policy random
    py scripts/run_evals.py --arm llm-nohistory --policy llm --model gemma-4-31b-it
    py scripts/run_evals.py --arm llm-history8 --policy llm --model gemma-4-31b-it --history 8
    py scripts/run_evals.py --arm smoke --mock            # offline, no key, no quota
    py scripts/run_evals.py --suite heldout --report      # see the guard below

Writes `artifacts/evals/<arm>.json`: per-game metrics, the pooled aggregate, and the exact
configuration that produced them. `scripts/compare_evals.py` turns two of those into a
before/after table.

**One arm = one variable.** The whole apparatus is worthless if two things change between
runs, so the config block is written into the artifact and `compare_evals.py` prints the
difference between the two configs at the top of the table. If that difference is more than
one line, the comparison is not an experiment.

**The held-out guard.** `--suite heldout` refuses to run without `--report`, and stamps
`"heldout_touched"` into the artifact when it does. CLAUDE.md §5 says the held-out games
are for reported results and never for iteration; a rule enforced only by good intentions
is a rule that gets broken at 1 a.m. two weeks from now.

**Incremental writing.** The artifact is rewritten after every game. A four-game LLM arm
takes roughly twenty minutes of wall clock, most of it asleep on the free-tier rate limit,
and a crash on game four should not cost games one to three.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import evals  # noqa: E402
from harness.arc_env import ArcEnv  # noqa: E402
from harness.budget import budget_check  # noqa: E402
from harness.evals import Arm, HeldOutViolation, Metrics  # noqa: E402
from harness.loop import run_episode  # noqa: E402
from harness.mock_game import MockGame  # noqa: E402
from harness.policies import LLMPolicy, RandomPolicy  # noqa: E402
from harness.progress_signal import summary_from_scorecard  # noqa: E402
from harness.trace import Tracer  # noqa: E402
from scripts.run_agent import RecordingEnv  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
EVAL_DIR = ROOT / "artifacts" / "evals"


def build_policy(args, seed: int, progress=None):
    if args.policy == "random":
        return RandomPolicy(seed=seed)

    from harness.frames import main_grid, render_grid, render_objects
    from harness.llm import GeminiClient, ScriptedClient

    encoders = {
        "objects": lambda frame: render_objects(main_grid(frame)),
        "grid": lambda frame: render_grid(main_grid(frame)),
    }
    # `--mock --policy llm` is the offline rehearsal of an LLM arm: it exercises the prompt
    # builder, the parser and the whole artifact path without a key. It proves the plumbing
    # and nothing about play, so the artifact records `mock: true` and the numbers must
    # never be quoted.
    # The canned reply follows the format the arm actually asks for, so a mock run of the
    # theory arm rehearses the theory path too instead of silently exercising the
    # no-theory-stated branch for every action.
    rehearsal = (
        "GOAL: rehearsal, not a theory\nACTION1\nPREDICT: FEW"
        if args.hypothesis
        else "ACTION1\nrehearsal"
    )
    client = (
        ScriptedClient([rehearsal], name="scripted")
        if args.mock
        else GeminiClient(model=args.model)
    )
    return LLMPolicy(
        client,
        encoder=encoders[args.encoder],
        name=(
            f"llm:{args.model}:{args.encoder}:h{args.history}:r{args.repeat_limit}"
            f":y{int(args.hypothesis)}:p{int(progress is not None)}"
        ),
        fallback_seed=seed,
        history=args.history,
        repeat_limit=args.repeat_limit,
        hypothesis=args.hypothesis,
        progress=progress,
    )


def llm_stats(policy) -> dict[str, Any] | None:
    if not isinstance(policy, LLMPolicy):
        return None
    return {
        "calls": policy.calls,
        "input_tokens": policy.input_tokens,
        "parse_failures": policy.parse_failures,
        "client_errors": policy.client_errors,
        "seconds_waited": getattr(policy.client, "seconds_waited", 0.0),
        "retries": getattr(policy.client, "retries", 0),
        "requests_used_today": getattr(policy.client, "calls_made", None),
        "repeat_blocks": policy.repeat_blocks,
        # None rather than 0 when the arm never asked for a theory, so an old arm and an
        # arm whose agent stayed silent do not report the same number.
        **(
            {
                "hypotheses_stated": policy.hypotheses_stated,
                "hypothesis_changes": policy.hypothesis_changes,
                "predictions_checked": policy.predictions_checked,
                "predictions_wrong": policy.predictions_wrong,
            }
            if policy.hypothesis
            else {}
        ),
    }


def play(args, game: str, seed: int) -> list[Metrics]:
    """One game, played `args.attempts` times. Returns one `Metrics` per attempt.

    Each attempt is a fresh scorecard, a fresh recording and a fresh trace, so its numbers
    stand alone. When `--progress` is on, the scorecard-close summary of attempt K is carried
    into attempt K+1's opening prompt (`harness/progress_signal.py`) — the after-the-fact
    signal is the only progress signal that can exist, because the scorecard is the only thing
    in this system that knows the goal. Without `--progress`, or with `--attempts 1`, this is
    the single play it has always been and nothing is carried anywhere.

    Never raises past the caller's report; a broken attempt is caught in `main` and recorded
    as an ERROR episode so the arm keeps its shape.
    """
    out: list[Metrics] = []
    prior = None  # AttemptSummary | None — the previous attempt at THIS game
    for attempt in range(1, args.attempts + 1):
        # The signal is only handed to the policy when the arm asked for it AND there is a
        # previous attempt to summarise. Attempt 1 of a progress arm is therefore the control
        # prompt byte for byte, which is what makes the attempt-2 comparison a clean A/B.
        carried = prior if (args.progress and prior is not None) else None
        policy = build_policy(args, seed, progress=carried)
        safe = re.sub(r"[^A-Za-z0-9._-]+", "-", f"{args.arm}.{policy.name}")
        inner: Any = MockGame() if args.mock else ArcEnv(game, tags=args.tag)
        game_id = inner.game_id if args.mock else game
        run_id = str(uuid.uuid4())
        stem = f"{game_id}.eval-{safe}.{args.max_actions}.a{attempt}.{run_id}"
        env = RecordingEnv(inner, RUNS / f"{stem}.recording.jsonl.gz")
        closed = None
        try:
            if not args.mock:
                inner.open_scorecard()
            with Tracer(RUNS / f"{stem}.trace.jsonl", run_id=run_id) as tracer:
                result = run_episode(
                    env, policy, max_actions=args.max_actions, tracer=tracer
                )
        finally:
            if not args.mock:
                try:
                    env.record_scorecard(inner.card(game))
                except Exception as exc:
                    print(f"    warning: could not read scorecard: {exc}")
                try:
                    closed = inner.close_scorecard()
                except Exception as exc:
                    print(f"    warning: could not close scorecard: {exc}")
                inner.close()
            env.close()

        metrics = evals.from_scorecard(evals.measure(result, llm_stats(policy)), closed)
        metrics.attempt = attempt
        out.append(metrics)

        # What the next attempt at this game gets to open with. Built from the same scorecard
        # fields the metric reads, so the number in the prompt and the number in the report
        # can never disagree. `actions_spent` is what the episode actually spent, not a
        # scorecard total, so it is right even on the games whose card omits the level data.
        prior = summary_from_scorecard(closed, game, metrics.actions)
    return out


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Run the eval suite for one configuration.")
    p.add_argument("--arm", required=True, help="name of this configuration (the artifact name)")
    p.add_argument("--suite", default="dev", choices=["dev", "heldout", "reserve"])
    p.add_argument("--games", default=None, help="comma-separated ids, overriding --suite")
    p.add_argument("--policy", default="random", choices=["random", "llm"])
    # Flash-Lite, not Gemma, despite Gemma having 23x the daily request budget: Gemma does
    # not serve a real game prompt at all (`artifacts/model-bakeoff.json`). 500 requests a
    # day is what an arm has to fit inside, and that is why episodes here are shorter than
    # the 80-action runs in `runs/` — a constraint, stated, not a preference.
    p.add_argument("--model", default="gemini-3.5-flash-lite")
    p.add_argument("--encoder", default="objects", choices=["objects", "grid"])
    p.add_argument("--history", type=int, default=0, help="past actions shown to the model")
    # 3 because the experiment on 2026-07-23 kept it: streak 26 -> 3 and favourite-action
    # excess +36.9% -> +17.7% for +1.2% tokens. Every arm run before that date needs
    # `--repeat-limit 0` to reproduce, and each artifact records the config that made it.
    p.add_argument(
        "--repeat-limit",
        type=int,
        default=3,
        help="block an action after this many identical plays in a row (0 = off)",
    )
    # Off by default while it is the change under test. The default moves only if the
    # numbers say it should, and then the move is recorded in notes/DECISIONS.md.
    p.add_argument(
        "--hypothesis",
        action="store_true",
        help="make the agent state a theory of the goal and a checkable prediction",
    )
    # How many times each game is attempted. 1 is the historical behaviour (each game played
    # once) and every earlier arm ran that way. The progress signal needs at least 2, because
    # it feeds attempt K's result into attempt K+1's opening prompt.
    p.add_argument("--attempts", type=int, default=1, help="times each game is replayed")
    # Off by default, like every other addition. Carries the previous attempt's scorecard-close
    # summary into the next attempt's opening prompt (`harness/progress_signal.py`). No effect
    # with --attempts 1, and none on a random policy.
    p.add_argument(
        "--progress",
        action="store_true",
        help="feed the previous attempt's scorecard summary into the next attempt's prompt",
    )
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--max-actions", type=int, default=80)
    p.add_argument("--mock", action="store_true", help="offline: no key, no quota, no meaning")
    p.add_argument("--report", action="store_true", help="required to touch the held-out set")
    p.add_argument(
        "--force-budget",
        action="store_true",
        help="run even when the arm does not fit in the remaining daily quota",
    )
    p.add_argument("--tag", action="append", default=["project-agent", "eval"])
    p.add_argument("--check-games", action="store_true", help="compare the frozen list to live")
    args = p.parse_args(argv)

    if args.check_games:
        return check_games()

    if args.suite == "heldout" and not args.report:
        raise HeldOutViolation(
            "the held-out suite is for reported results only (CLAUDE.md §5). "
            "Pass --report if this run IS the report; use --suite dev to iterate."
        )

    if args.attempts < 1:
        raise SystemExit("--attempts must be at least 1")
    if args.progress and args.attempts < 2:
        print(
            "NOTE: --progress has no effect with --attempts 1. The signal is the previous\n"
            "      attempt's result, and attempt 1 has no previous attempt. Use --attempts 2+.\n"
        )
    if args.progress and args.policy != "llm":
        print("NOTE: --progress is ignored by a random policy (it reads no prompt).\n")

    games = (
        [g.strip() for g in args.games.split(",") if g.strip()]
        if args.games
        else list(evals.SUITES[args.suite])
    )
    if args.mock:
        games = games[:2]  # the mock is one game repeated; two proves aggregation works

    arm = Arm(
        name=args.arm,
        suite=args.suite if not args.games else "custom",
        games=games,
        config={
            "policy": args.policy,
            "model": args.model if args.policy == "llm" else None,
            "encoder": args.encoder if args.policy == "llm" else None,
            "history": args.history if args.policy == "llm" else None,
            "repeat_limit": args.repeat_limit if args.policy == "llm" else None,
            "hypothesis": bool(args.hypothesis) if args.policy == "llm" else None,
            "progress": bool(args.progress) if args.policy == "llm" else None,
            "attempts": args.attempts,
            "seed": args.seed,
            "max_actions": args.max_actions,
            "mock": bool(args.mock),
        },
    )

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    out = EVAL_DIR / f"{args.arm}.json"
    print(f"arm     : {arm.name}")
    print(f"suite   : {arm.suite} - {len(games)} games")
    print(f"config  : {arm.config}")
    if args.mock:
        print("MOCK    : offline rehearsal. These numbers prove plumbing, not play.")
    if args.policy == "llm" and not args.mock:
        budget = budget_check(args.model, planned=len(games) * args.attempts * args.max_actions)
        print(
            f"budget  : {budget['used_last_24h']} calls in the last 24h, "
            f"{budget['remaining']} left of {budget['daily_limit']}/day; "
            f"this arm needs about {budget['planned']}"
        )
        if not budget["fits"] and not args.force_budget:
            raise SystemExit(
                "\nREFUSING TO START: this arm does not fit in the remaining daily quota.\n"
                "An arm that dies half way is not a cheap failure — it spends the quota and\n"
                "produces episodes whose actions were random fallbacks, which look like play\n"
                "in every table that reads them. Wait for the window to roll, run fewer games\n"
                "with --games, or pass --force-budget if you mean to spend what is left.\n"
                "(This check exists because on 2026-07-22 the fourth arm of the day died 19\n"
                "actions into its second game; see notes/DECISIONS.md.)"
            )
    print()

    for i, game in enumerate(games, 1):
        print(f"[{i}/{len(games)}] {game} ...", flush=True)
        try:
            episodes = play(args, game, args.seed)
        except Exception:
            traceback.print_exc()
            episodes = [
                Metrics(
                    game_id=game,
                    policy=args.policy,
                    actions=0,
                    illegal_actions=0,
                    no_change_actions=0,
                    unique_screens=0,
                    top_action_count=0,
                    longest_repeat_streak=0,
                    distinct_actions=0,
                    game_overs=0,
                    resets=0,
                    final_score=0,
                    final_state="ERROR",
                    wall_seconds=0.0,
                    error=traceback.format_exc(limit=1).strip().splitlines()[-1][:200],
                )
            ]
        for m in episodes:
            arm.episodes.append(m)
            tag = f" attempt {m.attempt}/{args.attempts}" if args.attempts > 1 else ""
            print(
                f"       {tag} score={m.final_score} state={m.final_state} "
                f"illegal={m.illegal_action_rate:.0%} dead={m.no_change_rate:.0%} "
                f"revisit={m.revisit_rate:.0%} "
                f"top={m.top_action_share:.0%} (excess {m.top_action_share_excess:+.0%} "
                f"of {m.median_legal_options} options) "
                f"streak={m.longest_repeat_streak} lvl1={m.level1_actions}/{m.level1_reference}",
                flush=True,
            )
            write(out, arm, args)

    print()
    print(json.dumps(arm.aggregate(), indent=2))
    print(f"\nwrote {out}")
    return 0


def write(out: Path, arm: Arm, args) -> None:
    payload = arm.to_dict()
    payload["generated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload["split"] = {
        "seed": evals.SPLIT_SEED,
        "pinned_dev": list(evals.PINNED_DEV),
        "games_source": evals.GAMES_SOURCE,
    }
    if args.suite == "heldout":
        payload["heldout_touched"] = True
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def check_games() -> int:
    """Has the server's game list drifted from the frozen one the split was built on?"""
    live = set(ArcEnv("").list_games())
    frozen = set(evals.GAMES)
    gone, new = sorted(frozen - live), sorted(live - frozen)
    print(f"frozen : {len(frozen)} games ({evals.GAMES_SOURCE})")
    print(f"live   : {len(live)} games")
    for g in gone:
        print(f"  GONE  {g}{'  [IN A SUITE]' if _in_suite(g) else ''}")
    for g in new:
        print(f"  NEW   {g}")
    if not gone and not new:
        print("  no drift — the split still describes the server")
    return 1 if gone else 0


def _in_suite(game: str) -> bool:
    return any(game in members for key, members in evals.SUITES.items() if key != "reserve")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
