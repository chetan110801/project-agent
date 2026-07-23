"""The one progress signal that can exist: after-the-fact, from something that knows the goal.

Three earlier attempts to tell the agent whether it was getting anywhere all failed, and
each failure narrowed the problem:

* **Memory of its own actions** (reverted 2026-07-22): eight lines of "ACTION3 -> 2 cells"
  read as *this button works*, not *you are stuck*.
* **A screen-derived progress signal** (refuted 2026-07-23 before a single model call): on the
  recorded failure every candidate read *better* than random, because the stuck agent was
  extending a bar two cells a turn — perfect accumulating work on the wrong thing
  (`artifacts/progress-signals.json`).
* **A falsifiable theory of the goal** (`harness/hypothesis.py`, 2026-07-23): broke premature
  commitment — 14 theories in 30 turns instead of 1 in 41 — and still did not help, because
  nothing in the loop knows the goal, so the agent falsified its way back into the same wrong
  theory ("grow the tower higher").

Every one of those signals was sourced from *inside* the episode — the screen, the agent's own
words — and the lesson they share is that **progress is undefined without a goal, and nothing
inside the episode knows the goal.** Exactly one thing in this whole system does: the server's
scorecard, closed at the end of a play, which reports how many levels were actually cleared
and — measured for `ls20` on 2026-07-22 — how many actions a reference solution needs per
level (`[22, 123, 73, 84, 96, 192, 186]`; see `harness/evals.from_scorecard`).

That number cannot help the play it came from; it arrives only at the end. So this signal is
**after the fact**: the summary of one attempt is carried into the *opening context of the
next attempt at the same game*. "On your last attempt you used 30 actions and did not clear
even level 1; a reference player clears level 1 in 22." It is the only progress signal that
can exist, because it is the only one sourced from something that knows the goal.

The wording is the harness's own voice, flat and unencouraging, for the reason attempt 1
established: a fact left for the model to interpret gets interpreted in its favour, so the
harness delivers a verdict the model cannot argue with — the number came from the game, not
from the agent's reading of the screen.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AttemptSummary:
    """What the last completed attempt at a game is worth telling the next one.

    Two sources that agree by construction: `actions_spent` is what the episode actually spent
    (`EpisodeResult.actions_taken`), and the level numbers are the server's, read out of the
    scorecard-close response — the only place the *reference* solution length appears at all.
    A missing reference (`None`) is normal: `level_baseline_actions` was measured for `ls20`
    and is not guaranteed for every game, so the block simply omits the sentence it would fill.
    """

    actions_spent: int
    levels_cleared: int = 0
    level_count: int | None = None
    level1_reference: int | None = None

    @property
    def is_empty(self) -> bool:
        """No attempt worth reporting — nothing was actually played."""
        return self.actions_spent <= 0


def summary_from_scorecard(
    closed: dict[str, Any] | None, game_id: str, actions_spent: int
) -> AttemptSummary | None:
    """Build a summary of the attempt just finished, or None when the server said nothing.

    Reads the same response, the same fields, as `harness.evals.from_scorecard`, and on
    purpose: the number the metric records and the number the next prompt is told must come
    from one place, or they can drift and the drift is invisible until they disagree in a
    report. Returns None rather than a zero-filled summary when there is no scorecard (a mock
    run) or the game is absent from it — None means "say nothing", which is not the same claim
    as "you cleared zero levels".
    """
    if not closed:
        return None
    envs = [e for e in closed.get("environments", []) if e.get("id") == game_id]
    if not envs:
        return None
    env = envs[0]

    reference: list[int] = []
    for run in env.get("runs") or []:
        ref = run.get("level_baseline_actions")
        if ref:
            reference = ref  # last non-empty wins, matching from_scorecard

    return AttemptSummary(
        actions_spent=actions_spent,
        levels_cleared=env.get("levels_completed") or 0,
        level_count=env.get("level_count"),
        level1_reference=reference[0] if reference else None,
    )


def render_progress_block(summary: AttemptSummary | None) -> str:
    """The lines the agent reads at the top of a fresh attempt. "" when there is nothing to say.

    Returns the empty string for a missing or empty summary, which is what keeps the first
    attempt's prompt — and every prompt of an arm that does not use this signal — the Phase B
    control prompt byte for byte. There is a golden test for exactly that.

    Two shapes, and the wording of each is the intervention:

    * **did not clear level 1** — the common case for this agent. Stated as a verdict, with
      the reference length next to it so the failure has a scale: 30 actions and not past a
      level a reference clears in 22.
    * **cleared at least one level** — reported flatly, no praise, for the reason the
      hypothesis block gives no praise: this agent reads any encouragement as proof it is
      winning.
    """
    if summary is None or summary.is_empty:
        return ""

    if summary.level_count:
        cleared = f"cleared {summary.levels_cleared} of {summary.level_count} levels"
    else:
        cleared = f"cleared {summary.levels_cleared} levels"

    lines = [
        f"On your last attempt at this game you used {summary.actions_spent} actions and "
        f"{cleared}."
    ]
    if summary.levels_cleared == 0:
        first = "You did not clear even level 1."
        if summary.level1_reference:
            first += f" A reference player clears level 1 in {summary.level1_reference} actions."
        first += " What you did last time did not work; do something different."
        lines.append(first)
    elif summary.level1_reference:
        lines.append(
            f"For scale, a reference player clears level 1 in {summary.level1_reference} actions."
        )
    return "\n".join(lines) + "\n\n"


__all__ = [
    "AttemptSummary",
    "render_progress_block",
    "summary_from_scorecard",
]
