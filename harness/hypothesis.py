"""The agent's theory of the game — written down, carried forward, and tested.

This is the third attempt at the same problem, and the first two are the reason it looks
like this.

* **Attempt 1 (memory).** Show the agent its own last eight actions. Reverted: eight lines
  reading "ACTION3 -> 2 cells changed" were read as *this button works*, not *you are
  stuck* (`notes/DECISIONS.md`, 2026-07-22).
* **Attempt 2 (a progress signal).** Compute, from the screen alone, whether the agent is
  getting anywhere. Refuted before it cost a single model call: on the recorded failure
  every candidate read *better* than random play, because the stuck agent was extending a
  bar by two fresh cells a turn — perfect accumulating work, on the wrong thing
  (`artifacts/progress-signals.json`).

The lesson from attempt 2 is that **progress is undefined without a goal**, and the goal is
exactly what nobody in this loop knows. So this module stops trying to compute progress from
outside and asks the agent for the missing half: *what do you think the goal is, and what
would show you were wrong?*

The engineering, rather than the wish, is in three parts:

1. The theory is **stated in words and carried forward** by the harness, so it is a
   commitment across turns instead of a fresh improvisation each turn.
2. The prediction attached to it is **machine-checkable**: how much of the screen the next
   action will change — nothing, a little, a lot. The harness checks it against the frame
   that comes back. The model never grades itself, because a model that grades itself
   reports success (see attempt 1).
3. When the check fails, the harness says so **in its own voice and demands a different
   theory**. A fact left for the model to interpret gets interpreted favourably; a verdict
   does not.

The FEW/MANY boundary is measured, not chosen — see `scripts/change_sizes.py` and
`artifacts/change-sizes.json`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# NONE / FEW / MANY, the vocabulary the agent must predict in. Three buckets rather than a
# number because a number invites a lucky guess to count as a hit, and because the
# recordings say the world only really produces three cases.
NONE, FEW, MANY = "NONE", "FEW", "MANY"
BUCKETS = (NONE, FEW, MANY)

# MEASURED, not picked: across every committed recording, an action changes either about two
# cells or about fifty — the middle is empty. Every boundary from 3 to 20 reclassifies under
# 1% of actions in every arm (`artifacts/change-sizes.json`, `stable_band`), so this number
# is not a knob a result can be tuned with. 5 is the middle of that band.
FEW_MANY_BOUNDARY = 5

# How much of a stated theory is carried into the next prompt. A model that answers with an
# essay must not be able to grow the context without limit — the budget is the free tier's,
# not the model's (`harness/budget.py`).
GOAL_MAX_CHARS = 120

_GOAL_RE = re.compile(r"^\W*GOAL\b\W*(.*)$", re.IGNORECASE | re.MULTILINE)
_PREDICT_RE = re.compile(r"^\W*PREDICT\b\W*(.*)$", re.IGNORECASE | re.MULTILINE)
_LINE_RE = re.compile(r"^\W*(?:GOAL|PREDICT)\b.*$", re.IGNORECASE | re.MULTILINE)


def bucket_of(cells_changed: int) -> str:
    """Which bucket an observed change falls in."""
    if cells_changed <= 0:
        return NONE
    return FEW if cells_changed <= FEW_MANY_BOUNDARY else MANY


@dataclass(frozen=True)
class Hypothesis:
    """What the agent said last turn. `goal` is prose; `prediction` is one of BUCKETS."""

    goal: str | None = None
    prediction: str | None = None

    @property
    def is_empty(self) -> bool:
        return not self.goal and not self.prediction


def parse_hypothesis(text: str) -> Hypothesis:
    """Pull the theory and the prediction out of a reply. Missing parts come back as None.

    Forgiving in the same way and for the same reason as `parse_action`: models add bullets,
    bold markers and colons whatever the prompt says, and refusing those would measure our
    prompt's obedience rather than the model's play. A reply with no GOAL line is not an
    error — it is a turn where the agent declined to commit, and that is a thing we count.
    """
    if not text:
        return Hypothesis()

    goal = None
    m = _GOAL_RE.search(text)
    if m:
        goal = re.sub(r"\s+", " ", m.group(1)).strip(" *_`\"'").strip() or None
        if goal:
            goal = goal[:GOAL_MAX_CHARS]

    prediction = None
    p = _PREDICT_RE.search(text)
    if p:
        found = re.search(r"\b(NONE|FEW|MANY)\b", p.group(1), re.IGNORECASE)
        if found:
            prediction = found.group(1).upper()
    return Hypothesis(goal=goal, prediction=prediction)


def strip_hypothesis_lines(text: str) -> str:
    """Remove the GOAL/PREDICT lines before the action is parsed.

    Without this, a perfectly good reply whose theory reads "keep pressing ACTION3 to grow
    the bar" would be parsed as a decision to press ACTION3, because `parse_action` takes
    the first match anywhere in the text. Stripping here rather than teaching `parse_action`
    about theories keeps the control arm's parser byte-identical to Phase B's.
    """
    return _LINE_RE.sub("", text or "")


@dataclass(frozen=True)
class Verdict:
    """The harness's ruling on last turn's prediction."""

    expected: str | None = None
    actual: str | None = None
    cells: int | None = None
    # None means there was nothing to check (first move, no prediction, shape change).
    correct: bool | None = None

    @property
    def checked(self) -> bool:
        return self.correct is not None


def judge(prediction: str | None, cells_changed: int | None) -> Verdict:
    """Compare a prediction against what the screen actually did."""
    if prediction not in BUCKETS or cells_changed is None:
        actual = bucket_of(cells_changed) if cells_changed is not None else None
        return Verdict(expected=prediction, actual=actual, cells=cells_changed)
    actual = bucket_of(cells_changed)
    return Verdict(
        expected=prediction, actual=actual, cells=cells_changed, correct=actual == prediction
    )


def render_block(previous: Hypothesis, verdict: Verdict) -> str:
    """The lines the agent reads about its own last theory. The harness's voice, not its own.

    Three cases, and the wording of each is the whole intervention:

    * **no theory yet** — asked for, plainly.
    * **prediction held** — stated flatly, with no praise. "Your theory survived a test" is
      not the same as "your theory is right", and the agent has already shown it will read
      any encouragement as proof it is winning.
    * **prediction failed** — the harness declares it wrong and *requires a different
      theory*. This is the only place in the prompt where the agent is told it is mistaken
      about something it cannot argue with, because the number came from the game.
    """
    if previous.is_empty:
        return "\nYou have not stated a theory of this game yet.\n"

    lines = [""]
    if previous.goal:
        lines.append(f'Your theory of this game, from last turn: "{previous.goal}"')
    if verdict.correct is None:
        if previous.prediction:
            lines.append(
                f"You predicted {previous.prediction}, but that prediction could not be "
                f"checked this turn."
            )
    elif verdict.correct:
        lines.append(
            f"You predicted {verdict.expected} and the screen changed {verdict.cells} "
            f"cells ({verdict.actual}). Your prediction held — that is one test passed, "
            f"not a solved game."
        )
    else:
        lines.append(
            f"You predicted {verdict.expected} but the screen changed {verdict.cells} "
            f"cells ({verdict.actual}). YOUR PREDICTION WAS WRONG."
        )
        lines.append(
            "RULE: the theory above just failed a test you set yourself. State a "
            "DIFFERENT theory this turn — not a reworded version of the same one."
        )
    lines.append("")
    return "\n".join(lines)


REPLY_FORMAT = f"""Reply with exactly three lines and nothing else:
GOAL: <under 12 words — what you think this game wants you to do>
ACTION<n>   (for a click: ACTION6 x=<0-63> y=<0-63>)
PREDICT: NONE or FEW or MANY — how much of the screen that action will change
NONE means no cell changes at all. FEW means 1 to {FEW_MANY_BOUNDARY} cells. \
MANY means more than {FEW_MANY_BOUNDARY}."""


def same_goal(a: str | None, b: str | None) -> bool:
    """Whether two stated goals are the same claim, ignoring wording noise.

    Deliberately shallow — case, punctuation and spacing only. Judging whether two English
    sentences mean the same thing needs a model call per turn, and a metric that costs
    quota to compute is a metric that will not be computed. So this over-counts changes: a
    reworded identical theory reads as a change here. That direction of error is stated
    wherever the number is reported, and it is the safe one — it cannot manufacture the
    result that the agent stuck to one theory.
    """
    if a is None or b is None:
        return a == b
    norm = lambda s: re.sub(r"[^a-z0-9 ]+", "", s.lower()).strip()  # noqa: E731
    return norm(a) == norm(b)


__all__ = [
    "BUCKETS",
    "FEW",
    "FEW_MANY_BOUNDARY",
    "GOAL_MAX_CHARS",
    "Hypothesis",
    "MANY",
    "NONE",
    "REPLY_FORMAT",
    "Verdict",
    "bucket_of",
    "judge",
    "parse_hypothesis",
    "render_block",
    "same_goal",
    "strip_hypothesis_lines",
]
