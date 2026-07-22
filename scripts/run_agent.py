"""Play one ARC-AGI-3 game with OUR loop, and leave receipts.

    py scripts/run_agent.py --game ls20                  # live, random baseline
    py scripts/run_agent.py --game ls20 --mock           # offline dry run, no key, no quota
    py scripts/run_agent.py --game ls20 --max-actions 80 --seed 0

This is the runner the SDK's CLI would have been, except that (a) the SDK's CLI shuts down
with `os.kill(os.getpid(), SIGINT)`, which on Windows kills the process before the
scorecard is printed, and (b) it drives the SDK's loop, not ours — and our loop is the
artifact this project is about (guards, traces, budgets).

What it does, in order:

    1. resolve the game id (`ls20` -> `ls20-9607627b`; the suffix is a version hash)
    2. open a scorecard          (the server groups plays under it)
    3. run `harness.loop.run_episode` with a tracer
    4. close the scorecard       (this is what makes the run appear on the site)
    5. write three files:
         runs/<game>.<policy>.<n>.<guid>.recording.jsonl   frames, SDK Recorder format
         runs/<game>.<policy>.<n>.<guid>.trace.jsonl       one line per decision
         artifacts/<name>.json                             the summary you cite

The recording deliberately mirrors the SDK's own format — `{"timestamp", "data"}` per
line, `FrameData` dumps, scorecard last (`arc_agi_3/_recorder.py`, `_agent.py:150-156`).
That is not politeness: it means `scripts/analyze_run.py` reads our run and the SDK
baseline with the *same* code, so the before/after comparison cannot be an artefact of
two different analysers.

Steps 2 and 4 run under try/finally: a crash mid-game still closes the scorecard and still
flushes the recording, because a run that cost quota and left nothing behind is a run that
has to be paid for twice.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from arc_agi_3._structs import FrameData  # noqa: E402

from harness.actions import Action  # noqa: E402
from harness.arc_env import ArcApiError, ArcEnv  # noqa: E402
from harness.loop import EpisodeResult, run_episode  # noqa: E402
from harness.mock_game import MockGame  # noqa: E402
from harness.policies import LLMPolicy, RandomPolicy  # noqa: E402
from harness.trace import Tracer  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
ARTIFACTS = ROOT / "artifacts"

def _llm_policy(args):
    from harness.frames import main_grid, render_grid, render_objects
    from harness.llm import GeminiClient

    encoders = {
        "objects": lambda frame: render_objects(main_grid(frame)),
        "grid": lambda frame: render_grid(main_grid(frame)),
    }
    client = GeminiClient(model=args.model)
    return LLMPolicy(
        client,
        encoder=encoders[args.encoder],
        name=f"llm:{args.model}:{args.encoder}",
        fallback_seed=args.seed,
        history=args.history,
        repeat_limit=args.repeat_limit,
    )


POLICIES = {
    "random": lambda args: RandomPolicy(seed=args.seed),
    "llm": _llm_policy,
}


class RecordingEnv:
    """Wraps an environment and writes every frame to a `.recording.jsonl`.

    A wrapper rather than a hook inside the loop: the loop's job is to decide and act, and
    a loop that also knows about file formats is a loop that is harder to test. Anything
    the environment returns gets recorded, including frames from a run that later crashes.
    """

    def __init__(self, inner: Any, path: Path) -> None:
        self.inner = inner
        self.game_id = inner.game_id
        # Ask for `.jsonl.gz` and you get a compressed file *at the end*; the live write is
        # always plain. Recordings compress 126x (measured: a 400-action run, 5.8 MB ->
        # 46 KB), which matters when every experiment writes one per game per arm — but a
        # gzip stream cannot be read back until it is closed, and surviving a crash
        # mid-episode is the whole reason the format is JSONL. So: plain while playing,
        # compressed once the episode is over and there is nothing left to lose.
        self.compress = path.suffix == ".gz"
        self.path = path.with_suffix("") if self.compress else path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("a", encoding="utf-8")
        self.frames = 0

    def _record(self, data: dict[str, Any]) -> dict[str, Any]:
        event = {"timestamp": datetime.now(timezone.utc).isoformat(), "data": data}
        self._fh.write(json.dumps(event) + "\n")
        self._fh.flush()  # survive a crash on action 57
        return event

    def _log_frame(self, frame: FrameData) -> FrameData:
        self._record(json.loads(frame.model_dump_json()))
        self.frames += 1
        return frame

    def reset(self) -> FrameData:
        return self._log_frame(self.inner.reset())

    def step(self, action: Action) -> FrameData:
        return self._log_frame(self.inner.step(action))

    def record_scorecard(self, card: dict[str, Any] | None) -> None:
        """The trailing record, same as the SDK writes: the game's card, not the envelope."""
        if card is not None:
            self._record(card)

    def close(self) -> None:
        """Close the file and, if asked for, compress it.

        A failure to compress must never destroy the recording — the plain file is only
        removed once the compressed one exists and is non-empty.
        """
        if not self._fh.closed:
            self._fh.close()
        if not self.compress or not self.path.exists():
            return
        gz = self.path.with_suffix(self.path.suffix + ".gz")
        with self.path.open("rb") as src, gzip.open(gz, "wb", compresslevel=9) as dst:
            shutil.copyfileobj(src, dst)
        if gz.stat().st_size > 0:
            self.path.unlink()
            self.path = gz


def resolve_game(env: ArcEnv, wanted: str) -> str:
    """`ls20` -> `ls20-9607627b`. Exact ids pass through.

    Game ids carry a version suffix, so hard-coding one silently plays a stale game (or a
    404) after the platform updates. We ask the server what exists and prefix-match.
    """
    games = env.list_games()
    if wanted in games:
        return wanted
    matches = [g for g in games if g.startswith(wanted)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ArcApiError(f"no game id starts with {wanted!r}; server offers: {games}")
    raise ArcApiError(f"{wanted!r} is ambiguous: {matches}")


def summarise(result: EpisodeResult, extra: dict[str, Any]) -> dict[str, Any]:
    steps = result.steps
    latencies = sorted(s.latency_ms for s in steps)
    return {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "game_id": result.game_id,
        "agent": f"our loop ({result.policy} policy)",
        "policy": result.policy,
        "actions": result.actions_taken,
        "final_score": result.final_score,
        "final_state": result.final_state,
        "stopped_because": result.stopped_because,
        "actions_not_available": result.rejected_actions,
        "transitions_no_change": result.no_change_actions,
        "dead_action_rate": round(result.dead_action_rate, 4),
        "wall_seconds": result.wall_seconds,
        "latency_ms_median": latencies[len(latencies) // 2] if latencies else None,
        "latency_ms_max": latencies[-1] if latencies else None,
        "actions_sent_histogram": _histogram(steps),
        **extra,
    }


def _histogram(steps: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for s in steps:
        key = s.action.split("(")[0]
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Play one ARC-AGI-3 game with our loop.")
    p.add_argument("--game", default="ls20", help="game id or prefix (default: ls20)")
    p.add_argument("--policy", default="random", choices=sorted(POLICIES))
    p.add_argument("--seed", type=int, default=0, help="policy seed (reproducibility)")
    p.add_argument("--max-actions", type=int, default=80, help="hard cap (default: 80)")
    p.add_argument(
        "--stuck-limit",
        type=int,
        default=None,
        help="stop after N consecutive no-change actions (default: never)",
    )
    p.add_argument("--mock", action="store_true", help="offline mock game: no key, no quota")
    p.add_argument("--list", action="store_true", help="print the game ids and exit")
    p.add_argument("--model", default="gemini-3.5-flash-lite", help="for --policy llm")
    p.add_argument(
        "--encoder",
        default="objects",
        choices=["objects", "grid"],
        help="how the screen is written for the model (study note 06)",
    )
    p.add_argument("--history", type=int, default=0, help="past actions shown (0 = none)")
    p.add_argument(
        "--repeat-limit",
        type=int,
        default=3,
        help="block an action after this many identical plays in a row (0 = off)",
    )
    p.add_argument("--tag", action="append", default=[], help="scorecard tag (repeatable)")
    p.add_argument("--out", default=None, help="artifacts/<name>.json (default: derived)")
    args = p.parse_args(argv)

    if args.list:
        # Ids carry a version suffix that changes when the platform updates a game, so the
        # list is asked for rather than remembered.
        for game in ArcEnv("").list_games():
            print(game)
        return 0

    policy = POLICIES[args.policy](args)
    run_id = str(uuid.uuid4())

    inner: Any
    if args.mock:
        inner = MockGame()
        game_id = inner.game_id
    else:
        inner = ArcEnv(args.game, tags=args.tag or ["project-agent", "our-loop"])
        game_id = resolve_game(inner, args.game)
        inner.game_id = game_id

    # Policy names carry colons (`llm:gemini-3.5-flash-lite:objects`) and Windows rejects
    # those in filenames — with an Errno 22 that names the path but not the reason.
    safe_policy = re.sub(r"[^A-Za-z0-9._-]+", "-", policy.name)
    stem = f"{game_id}.{safe_policy}.{args.max_actions}.{run_id}"
    env = RecordingEnv(inner, RUNS / f"{stem}.recording.jsonl.gz")
    trace_path = RUNS / f"{stem}.trace.jsonl"

    print(f"game    : {game_id}{'  (MOCK — offline, proves nothing about real play)' if args.mock else ''}")
    print(f"policy  : {policy.name} (seed {args.seed})")
    print(f"cap     : {args.max_actions} actions")

    card: dict[str, Any] | None = None
    closed: dict[str, Any] | None = None
    scorecard_url: str | None = None
    result: EpisodeResult | None = None
    try:
        if not args.mock:
            card_id = inner.open_scorecard()
            scorecard_url = inner.scorecard_url
            print(f"scorecard: {card_id}  {scorecard_url}")
        with Tracer(trace_path, run_id=run_id) as tracer:
            result = run_episode(
                env,
                policy,
                max_actions=args.max_actions,
                tracer=tracer,
                stuck_limit=args.stuck_limit,
            )
    finally:
        if not args.mock:
            # Order matters: the per-game card must be fetched BEFORE the close, because
            # closing retires the card_id and the GET then 404s (measured 2026-07-22).
            try:
                card = inner.card(game_id)
                env.record_scorecard(card)
            except Exception as exc:
                print(f"warning: could not read scorecard: {exc}")
            try:
                closed = inner.close_scorecard()
            except Exception as exc:  # closing must never mask the real error
                print(f"warning: could not close scorecard: {exc}")
            inner.close()
        env.close()

    assert result is not None
    print()
    print(result.summary())
    print(f"rejected  : {result.rejected_actions} illegal actions (never sent)")
    print(f"dead      : {result.no_change_actions} of {result.actions_taken} changed nothing")

    llm: dict[str, Any] = {}
    if isinstance(policy, LLMPolicy):
        client = policy.client
        llm = {
            "model": getattr(client, "model", getattr(client, "name", "?")),
            "encoder": args.encoder,
            "calls": policy.calls,
            "parse_failures": policy.parse_failures,
            "client_errors": policy.client_errors,
            "requests_used": getattr(client, "calls_made", None),
            "seconds_waited_on_rate_limit": getattr(client, "seconds_waited", None),
            "daily_request_limit": getattr(getattr(client, "limits", None), "rpd", None),
        }
        usable = policy.calls - policy.parse_failures - policy.client_errors
        llm["usable_reply_rate"] = round(usable / policy.calls, 4) if policy.calls else None
        print(
            f"llm       : {llm['calls']} calls, {llm['parse_failures']} unparseable, "
            f"{llm['client_errors']} errors "
            f"({llm['usable_reply_rate']:.0%} usable)" if policy.calls else "llm: no calls"
        )
        print(
            f"budget    : {llm['requests_used']}/{llm['daily_request_limit']} requests today, "
            f"{llm['seconds_waited_on_rate_limit']:.0f}s asleep on the rate limit"
        )

    report = summarise(
        result,
        {
            "run_id": run_id,
            "recording": env.path.name,
            "trace": trace_path.name,
            "mock": bool(args.mock),
            "seed": args.seed,
            "max_actions": args.max_actions,
            "stuck_limit": args.stuck_limit,
            "scorecard_url": scorecard_url,
            "scorecard_card": card,
            "scorecard_closed": closed,
            "llm": llm or None,
        },
    )
    ARTIFACTS.mkdir(exist_ok=True)
    name = args.out or ("mock-run" if args.mock else f"{args.policy}-ourloop")
    out = ARTIFACTS / f"{name}.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"\nrecording : {env.path}")
    print(f"trace     : {trace_path}")
    print(f"summary   : {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
