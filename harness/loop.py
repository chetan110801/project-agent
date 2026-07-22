"""Our agent loop: observe -> decide -> act -> record, with the guards that matter.

The SDK ships a loop. We do not use it, for the reasons in study note 05 — and for one
more that only shows up in code: the SDK's loop is welded to its HTTP transport, so every
test of the loop would need a network call and a quota. Ours takes an `Environment`
protocol, which the mock game satisfies offline, so the loop is testable in milliseconds.

Three guards are built in, because all three are failure modes we know about in advance:

1. **Hard action cap.** A confused agent otherwise runs forever burning quota. Non-optional.
2. **Illegal-action rejection.** The decide step will eventually return something illegal
   (an LLM certainly will). The loop refuses it, records the refusal, and falls back —
   it never sends it.
3. **Stuck detection.** Counting consecutive actions that changed nothing is what makes a
   dead action *visible* rather than repeated twenty times.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from arc_agi_3._structs import FrameData, GameAction, GameState

from .actions import Action
from .frames import diff_grids, main_grid
from .policies import Policy, legal_actions
from .trace import Tracer


@runtime_checkable
class Environment(Protocol):
    """A thing an agent can act in. Implemented by the mock game, and (Phase A) by the
    real ARC-AGI-3 API adapter."""

    game_id: str

    def reset(self) -> FrameData:
        """Start (or restart) the game and return the first frame."""
        ...

    def step(self, action: Action) -> FrameData:
        """Apply one action and return the resulting frame."""
        ...


@dataclass
class StepRecord:
    """One turn of the loop, as it will appear in the trace."""

    index: int
    action: str
    accepted: bool
    state: str
    score: int
    score_delta: int
    cells_changed: int
    latency_ms: float
    note: str = ""
    # Why the policy chose this. Empty for a coin flip; for an LLM it is the model's own
    # words, which is the only thing that makes a trace answer "why did it do that?"
    # rather than just "what did it do?".
    reasoning: str = ""


@dataclass
class EpisodeResult:
    """One game played, start to finish."""

    game_id: str
    policy: str
    actions_taken: int
    final_score: int
    final_state: str
    stopped_because: str
    no_change_actions: int
    rejected_actions: int
    wall_seconds: float
    steps: list[StepRecord] = field(default_factory=list)

    @property
    def dead_action_rate(self) -> float:
        """Share of actions that changed nothing on screen. High = flailing."""
        return self.no_change_actions / self.actions_taken if self.actions_taken else 0.0

    def summary(self) -> str:
        return (
            f"{self.game_id} [{self.policy}] score={self.final_score} "
            f"state={self.final_state} actions={self.actions_taken} "
            f"dead={self.dead_action_rate:.0%} stopped={self.stopped_because}"
        )


def _cells_changed(before: FrameData, after: FrameData) -> int:
    """-1 when the grids are not comparable (shape change, or an empty frame)."""
    try:
        return diff_grids(main_grid(before), main_grid(after)).count
    except ValueError:
        return -1


def run_episode(
    env: Environment,
    policy: Policy,
    max_actions: int = 80,
    tracer: Tracer | None = None,
    stuck_limit: int | None = None,
) -> EpisodeResult:
    """Play one game.

    `max_actions` mirrors the SDK default of 80 — the number the real server's scorecard
    is used to seeing, so our offline numbers stay comparable to real ones.
    `stuck_limit`: stop after this many consecutive no-change actions (None = never).
    """
    started = time.perf_counter()
    frame = env.reset()
    frames: list[FrameData] = [frame]
    steps: list[StepRecord] = []
    no_change = rejected = consecutive_no_change = 0
    stopped = "max_actions"

    if tracer:
        tracer.write(
            "episode_start",
            game_id=env.game_id,
            policy=policy.name,
            max_actions=max_actions,
            state=frame.state.value,
            score=frame.score,
        )

    for i in range(max_actions):
        if frame.state is GameState.WIN:
            stopped = "win"
            break

        action = policy.choose(frames, frame)
        reasoning = str(action.reasoning or "")

        # Guard 2: never send an action the frame says is not available.
        allowed = legal_actions(frame)
        accepted = action.kind in allowed
        note = ""
        if not accepted:
            rejected += 1
            note = f"illegal action {action.label()}; fell back to RESET"
            action = Action(GameAction.RESET, reasoning=note)

        t0 = time.perf_counter()
        nxt = env.step(action)
        latency_ms = (time.perf_counter() - t0) * 1000

        changed = _cells_changed(frame, nxt)
        delta = nxt.score - frame.score
        if changed == 0 and delta == 0:
            no_change += 1
            consecutive_no_change += 1
        else:
            consecutive_no_change = 0

        rec = StepRecord(
            index=i,
            action=action.label(),
            accepted=accepted,
            state=nxt.state.value,
            score=nxt.score,
            score_delta=delta,
            cells_changed=changed,
            latency_ms=round(latency_ms, 3),
            note=note,
            reasoning=reasoning,
        )
        steps.append(rec)
        if tracer:
            tracer.write("step", **rec.__dict__)

        frames.append(nxt)
        frame = nxt

        # Guard 3: stop flailing.
        if stuck_limit is not None and consecutive_no_change >= stuck_limit:
            stopped = "stuck"
            break
    else:
        stopped = "max_actions"

    if frame.state is GameState.WIN:
        stopped = "win"

    result = EpisodeResult(
        game_id=env.game_id,
        policy=policy.name,
        actions_taken=len(steps),
        final_score=frame.score,
        final_state=frame.state.value,
        stopped_because=stopped,
        no_change_actions=no_change,
        rejected_actions=rejected,
        wall_seconds=round(time.perf_counter() - started, 4),
        steps=steps,
    )
    if tracer:
        tracer.write(
            "episode_end",
            **{k: v for k, v in result.__dict__.items() if k != "steps"},
            dead_action_rate=round(result.dead_action_rate, 4),
        )
    return result


__all__ = ["Environment", "EpisodeResult", "StepRecord", "run_episode"]
