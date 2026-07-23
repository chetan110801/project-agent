"""Policies: the 'decide' step of the loop, isolated so it can be swapped and compared.

The loop does not care what is inside a policy — a coin flip, an LLM call, a search. That
separation is the whole point: the harness (loop, traces, evals, budgets) stays fixed
while the decide step changes, so any score difference is attributable to the policy and
not to the plumbing around it.

`RandomPolicy` is the baseline. It is meant to be bad. Its job is to make later numbers
mean something.
"""

from __future__ import annotations

import random
import re
from typing import Protocol, runtime_checkable

from arc_agi_3._structs import FrameData, GameAction, GameState

from .actions import GRID_MAX, Action
from .hypothesis import REPLY_FORMAT as HYPOTHESIS_REPLY_FORMAT
from .hypothesis import (
    Hypothesis,
    judge,
    parse_hypothesis,
    render_block,
    same_goal,
    strip_hypothesis_lines,
)
from .llm import Completion
from .progress_signal import AttemptSummary, render_progress_block


@runtime_checkable
class Policy(Protocol):
    """Anything that can pick the next action from the history."""

    name: str

    def choose(self, frames: list[FrameData], latest: FrameData) -> Action:
        """Return the next action. Must be legal for `latest`."""
        ...


def legal_actions(latest: FrameData) -> list[GameAction]:
    """What the agent may press right now.

    The server sends `available_actions` per frame. When it is empty we fall back to all
    eight — but that fallback is a guess, so it is one line and easy to find, rather than
    scattered `or ALL` defaults across the codebase.

    RESET is always included. Real frames leave it out of `available_actions` (the live
    `ls20` run advertised `[1, 2, 3, 4]` in all 81 frames, measured — see
    `artifacts/run-report.json`), yet RESET is what you send when the game is over, and the
    SDK sends it regardless of that list. Without this line the loop would flag its own
    fallback as an illegal action and report a rejection that never happened.
    """
    allowed = list(latest.available_actions) or list(GameAction)
    if GameAction.RESET not in allowed:
        allowed.insert(0, GameAction.RESET)
    return allowed


class RandomPolicy:
    """Presses buttons at random. Seeded, so a run is reproducible.

    Seeding matters more than it looks: an unseeded baseline gives a different number
    every time, and then 'we beat the baseline' is unfalsifiable. The SDK's own Random
    agent seeds from the clock; ours takes the seed as an argument.
    """

    def __init__(self, seed: int = 0, name: str = "random") -> None:
        self.name = name
        self.seed = seed
        self._rng = random.Random(seed)

    def choose(self, frames: list[FrameData], latest: FrameData) -> Action:
        if latest.state in (GameState.NOT_PLAYED, GameState.GAME_OVER):
            return Action(GameAction.RESET, reasoning="game not in play — reset")

        options = [a for a in legal_actions(latest) if a is not GameAction.RESET]
        if not options:
            return Action(GameAction.RESET, reasoning="no non-reset action available")

        kind = self._rng.choice(options)
        if kind.is_complex():
            return Action(
                kind,
                x=self._rng.randint(0, GRID_MAX),
                y=self._rng.randint(0, GRID_MAX),
                reasoning="random baseline",
            )
        return Action(kind, reasoning="random baseline")


# --------------------------------------------------------------------------- #
# The repetition guard
# --------------------------------------------------------------------------- #
# How many times in a row the agent may repeat one action before the harness refuses it.
# Chosen by measurement, not by taste. Across every committed recording, a *random* player
# exceeds three identical actions in a row on 0-2% of its moves (and 0% on the 30-action
# arms), while the LLM exceeds it on 30-77%. So the cap is set at exactly what chance
# produces: **you may repeat an action as often as a coin flip would.** A guard that also
# fires on random play would be punishing normal play; this one is calibrated so it cannot.
REPEAT_LIMIT = 3


def played_labels(frames: list[FrameData]) -> list[str]:
    """The action labels actually sent to the server, oldest first.

    Read from `action_input` rather than from the policy's own memory for the same reason
    `render_history` does: the loop may override what the policy asked for (an illegal
    action becomes RESET), and the guard has to count what the *game* saw.
    """
    labels = []
    for f in frames[1:]:
        if f.action_input is None:
            continue
        label = f.action_input.id.name
        data = f.action_input.data or {}
        if "x" in data and "y" in data:
            label += f"(x={data['x']},y={data['y']})"
        labels.append(label)
    return labels


def blocked_label(frames: list[FrameData], limit: int) -> str | None:
    """The action the agent has just played `limit` times in a row, or None.

    Compares **full labels**, coordinates included, so that on a click game clicking the
    same square four times is caught while clicking four different squares is not. On a
    game whose only action is a click, banning one square still leaves 4,095 — which is why
    this can be safe to enforce even where `available_actions` has a single entry.
    """
    if limit <= 0:
        return None
    labels = played_labels(frames)
    if len(labels) < limit:
        return None
    tail = labels[-limit:]
    return tail[0] if len(set(tail)) == 1 else None


PROMPT = """{progress}You are playing a puzzle video game. You see the screen as a grid of colours.

{screen}

Your last action: {last_action}
What that changed: {feedback}
{hypothesis}{history}{ban}
Buttons you may press right now: {options}

{reply_format}"""

# The Phase B reply format, frozen. Every arm before 2026-07-23 ran with exactly this tail,
# so it stays a separate constant rather than an f-string with a switch in it: the control
# arm of every future experiment has to be reproducible byte for byte, and the cheapest way
# to guarantee that is for its text to be somewhere nobody edits by accident.
REPLY_FORMAT = """Reply with ONE line and nothing else, in this exact form:
ACTION<n>
or, for a click:
ACTION6 x=<0-63> y=<0-63>

Then, on a second line, at most 15 words explaining why."""


class LLMPolicy:
    """The decide step, done by a language model.

    Everything interesting is in what the model is shown, not in this class — see study
    note 06. The parts of the prompt are the encoded screen, the feedback about the agent's
    own last action, an optional window of its own recent actions (`history`, off by
    default so the Phase B prompt is reproducible byte for byte), an optional repetition
    ban (`repeat_limit`, likewise off by default), an optional theory-of-the-game block
    (`hypothesis`, also off by default — `harness/hypothesis.py`), and the list of buttons
    that are legal *right now*.

    With both options off, `build_prompt` produces the Phase B prompt byte for byte. That
    is deliberate and there is a test for it: an A/B whose control arm has quietly drifted
    is not an A/B.

    That last part is belt-and-braces with the loop's guard: telling the model the legal
    set makes a good answer likelier, and the guard makes a bad one harmless. Both, because
    a prompt is a request and a guard is a guarantee.

    Failures are counted, never raised. A refused, empty, or unparseable reply falls back to
    a legal action so the episode continues and the trace records why — an agent that dies
    on a 429 measures nothing.
    """

    def __init__(
        self,
        client,
        encoder=None,
        name: str | None = None,
        fallback_seed: int = 0,
        history: int = 0,
        repeat_limit: int = 0,
        hypothesis: bool = False,
        progress: AttemptSummary | None = None,
    ) -> None:
        from .frames import main_grid, render_objects

        self.client = client
        self.encode = encoder or (lambda frame: render_objects(main_grid(frame)))
        self.name = name or f"llm:{getattr(client, 'name', 'unknown')}"
        # How many of the agent's own past actions to put in the prompt. 0 reproduces the
        # Phase B prompt exactly, which is what makes this an A/B and not a rewrite.
        self.history = history
        # After this many identical actions in a row, the repeated action is refused. 0 is
        # off, and off is the setting every earlier arm ran under.
        self.repeat_limit = repeat_limit
        # Ask the agent to state a theory of the goal and a checkable prediction, and hold
        # it to both (`harness/hypothesis.py`). Off by default, like every other addition.
        self.hypothesis = hypothesis
        # A summary of the previous attempt at THIS game, from the server's scorecard close
        # (`harness/progress_signal.py`). None for a first attempt and for every arm that
        # does not carry it — in which case the prompt is the Phase B control byte for byte.
        # It is a whole-episode fact, so it is shown on every turn of the attempt, not just
        # the first: our loop makes stateless calls, and a fact shown once is forgotten by
        # turn two.
        self.progress = progress
        self._fallback = RandomPolicy(seed=fallback_seed, name="fallback")
        self.calls = 0
        self.parse_failures = 0
        self.client_errors = 0
        self.input_tokens = 0
        # How often the guard actually had to overrule the model. Reported, because a guard
        # whose firing rate is invisible is a change whose size is unknown.
        self.repeat_blocks = 0
        # The theory the agent stated last turn, and the bookkeeping that makes the
        # intervention's size visible. `hypothesis_changes` over-counts rewordings on
        # purpose — see `hypothesis.same_goal`.
        self.theory = Hypothesis()
        self.hypotheses_stated = 0
        self.hypothesis_changes = 0
        self.predictions_checked = 0
        self.predictions_wrong = 0
        self.last: Completion | None = None

    def cells_changed(self, frames: list[FrameData]) -> int | None:
        """How many cells the agent's last action moved, or None if that is not a number.

        None covers both ends of the episode's edge cases — the first frame, and a screen
        that changed shape — and the caller must treat it as *unknown*, never as zero. A
        shape change scored as "0 cells changed" would mark a prediction of NONE correct on
        the one turn the world was doing the most.
        """
        from .frames import diff_grids, main_grid

        if len(frames) < 2:
            return None
        try:
            d = diff_grids(main_grid(frames[-2]), main_grid(frames[-1]))
        except ValueError:
            return None
        return d.count if d.same_shape else None

    def build_prompt(self, frames: list[FrameData], latest: FrameData) -> str:
        from .frames import main_grid, render_diff, render_history

        options = [a.name for a in legal_actions(latest) if a is not GameAction.RESET]
        last_action = latest.action_input.id.name if latest.action_input else "none yet"
        feedback = "this is the first frame"
        if len(frames) >= 2:
            try:
                feedback = render_diff(main_grid(frames[-2]), main_grid(latest))
            except ValueError:
                feedback = "the screen changed shape"

        # The theory block, and the reply format that goes with it. Both empty in the
        # control arm, so `build_prompt` there is the Phase B prompt byte for byte — there
        # is a golden test for exactly that string.
        hypothesis = ""
        reply_format = REPLY_FORMAT
        if self.hypothesis:
            hypothesis = render_block(self.theory, judge(self.theory.prediction, self.cells_changed(frames)))
            reply_format = HYPOTHESIS_REPLY_FORMAT

        history = ""
        if self.history:
            history = (
                "\nYour recent actions, oldest first:\n"
                + render_history(frames, self.history)
                + "\n"
            )

        # The ban is stated as a rule already in force, not as advice. Experiment 1 showed
        # that facts the model is left to interpret get interpreted favourably: eight lines
        # of "ACTION3 -> 2 cells changed" were read as proof the action worked. So the
        # harness does the judging and reports a decision.
        ban = ""
        banned = blocked_label(frames, self.repeat_limit)
        if banned:
            simple = banned if "(" not in banned else banned.split("(")[0]
            if simple in options and len(options) > 1:
                options = [o for o in options if o != simple]
            ban = (
                f"\nRULE: you have played {banned} {self.repeat_limit} times in a row. "
                f"It is BLOCKED this turn. Pick something else.\n"
            )

        return PROMPT.format(
            progress=render_progress_block(self.progress),
            screen=self.encode(latest),
            last_action=last_action,
            feedback=feedback,
            hypothesis=hypothesis,
            history=history,
            ban=ban,
            options=", ".join(options) or "none",
            reply_format=reply_format,
        )

    def choose(self, frames: list[FrameData], latest: FrameData) -> Action:
        if latest.state in (GameState.NOT_PLAYED, GameState.GAME_OVER):
            return Action(GameAction.RESET, reasoning="game not in play — reset")

        # Grade last turn's prediction before the prompt is built, so the counters and the
        # sentence the agent reads are the same ruling and cannot drift apart.
        if self.hypothesis:
            verdict = judge(self.theory.prediction, self.cells_changed(frames))
            if verdict.checked:
                self.predictions_checked += 1
                self.predictions_wrong += not verdict.correct

        prompt = self.build_prompt(frames, latest)
        completion = self.client.complete(prompt)
        self.last = completion
        self.calls += 1
        self.input_tokens += completion.input_tokens or 0

        if not completion.ok:
            self.client_errors += 1
            # The turn the agent never got to answer. Its previous prediction must be
            # dropped rather than carried: the harness is about to play a random fallback
            # action, and grading "MANY cells will change" against the result of an action
            # the agent did not choose is a verdict about the wrong thing. The *goal*
            # stands — an outage is not a retraction. MEASURED: this happened on 2 of 30
            # turns in the first live run of this arm before it was fixed.
            self.theory = Hypothesis(goal=self.theory.goal)
            return self._fall_back(frames, latest, f"client error: {completion.error}")

        text = completion.text
        if self.hypothesis:
            self._record_theory(text)
            # The action is parsed from the reply with the theory lines removed: a goal
            # reading "keep pressing ACTION3" must not be mistaken for a decision.
            text = strip_hypothesis_lines(text)

        action = parse_action(text)
        if action is None:
            self.parse_failures += 1
            # Same reasoning as the client-error branch above: a prediction is a claim about
            # the action the agent named, and when we could not read that action the harness
            # plays a random one instead. Nothing about that turn is the agent's to be
            # judged on, except the theory, which stands.
            self.theory = Hypothesis(goal=self.theory.goal)
            # The WHOLE reply, not its first line. The first-line version of this message
            # recorded 14 unparseable replies on `tn36` as the single word "ACTION6" and
            # left no way to find out what the rest of them said — a diagnostic that
            # deletes the evidence. Newlines are escaped so a trace line stays one line.
            raw = " / ".join(completion.text.strip().splitlines())[:300]
            return self._fall_back(frames, latest, f"unparseable reply: {raw!r}")

        # A prompt is a request; a guard is a guarantee — the same pairing as the legal
        # action list. The model is told the action is blocked and is still capable of
        # returning it, so the block is also enforced here.
        banned = blocked_label(frames, self.repeat_limit)
        if banned and action.label() == banned:
            self.repeat_blocks += 1
            return self._escape(frames, latest, banned)

        return Action(action.kind, action.x, action.y, reasoning=completion.text.strip()[:300])

    def _record_theory(self, text: str) -> None:
        """Store what the agent just claimed, and count whether it changed its mind.

        A reply that states no theory leaves the previous one standing rather than clearing
        it. Silence is not a retraction, and clearing on silence would make the prompt
        forget a commitment the agent never withdrew — turning a missing line into an escape
        hatch from the only rule this arm adds.
        """
        stated = parse_hypothesis(text)
        if stated.goal:
            self.hypotheses_stated += 1
            if self.theory.goal and not same_goal(self.theory.goal, stated.goal):
                self.hypothesis_changes += 1
        self.theory = Hypothesis(
            goal=stated.goal or self.theory.goal,
            prediction=stated.prediction,
        )

    def _escape(self, frames, latest, banned: str) -> Action:
        """Any legal action that is not the banned one.

        Bounded retries rather than a `while True`: on a game whose only action is a click,
        a random square could in principle repeat the banned one, and an unbounded loop in
        the decide step is a hang in the middle of a live run.
        """
        for _ in range(8):
            candidate = self._fallback.choose(frames, latest)
            if candidate.label() != banned:
                return Action(
                    candidate.kind,
                    candidate.x,
                    candidate.y,
                    reasoning=f"repetition guard: {banned} blocked after "
                    f"{self.repeat_limit} in a row — forced variety",
                )
        return Action(GameAction.RESET, reasoning=f"repetition guard: {banned} blocked, reset")

    def _fall_back(self, frames, latest, why: str) -> Action:
        action = self._fallback.choose(frames, latest)
        return Action(action.kind, action.x, action.y, reasoning=f"{why} — fell back")


def parse_action(text: str) -> Action | None:
    """Pull an action out of a model reply, or None.

    Deliberately forgiving about everything except the action itself: models add
    markdown fences, prose, and 'Action:' prefixes no matter what the prompt says, and
    refusing those would measure our prompt's obedience rather than the model's play.
    Coordinates out of range are rejected rather than clamped — a clamp would silently
    turn a wrong answer into a plausible one, which is exactly what the eval must see.
    """
    if not text:
        return None
    match = re.search(r"\bACTION\s*([1-7])\b", text, re.IGNORECASE)
    if not match:
        return None
    kind = GameAction.from_id(int(match.group(1)))
    if not kind.is_complex():
        return Action(kind)

    tail = text[match.end() :]
    x = re.search(r"\bx\s*[=:]?\s*(\d{1,2})\b", tail, re.IGNORECASE)
    y = re.search(r"\by\s*[=:]?\s*(\d{1,2})\b", tail, re.IGNORECASE)
    if not (x and y):
        pair = re.search(r"\(?\s*(\d{1,2})\s*[, ]\s*(\d{1,2})\s*\)?", tail)
        if not pair:
            return None
        xv, yv = int(pair.group(1)), int(pair.group(2))
    else:
        xv, yv = int(x.group(1)), int(y.group(1))
    if not (0 <= xv <= GRID_MAX and 0 <= yv <= GRID_MAX):
        return None
    return Action(kind, x=xv, y=yv)


__all__ = ["LLMPolicy", "Policy", "RandomPolicy", "legal_actions", "parse_action"]
