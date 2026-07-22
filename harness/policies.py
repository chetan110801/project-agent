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
from .llm import Completion


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


PROMPT = """You are playing a puzzle video game. You see the screen as a grid of colours.

{screen}

Your last action: {last_action}
What that changed: {feedback}

Buttons you may press right now: {options}

Reply with ONE line and nothing else, in this exact form:
ACTION<n>
or, for a click:
ACTION6 x=<0-63> y=<0-63>

Then, on a second line, at most 15 words explaining why."""


class LLMPolicy:
    """The decide step, done by a language model.

    Everything interesting is in what the model is shown, not in this class — see study
    note 06. The three parts of the prompt are the encoded screen, the feedback about the
    agent's own last action, and the list of buttons that are legal *right now*.

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
    ) -> None:
        from .frames import main_grid, render_objects

        self.client = client
        self.encode = encoder or (lambda frame: render_objects(main_grid(frame)))
        self.name = name or f"llm:{getattr(client, 'name', 'unknown')}"
        self._fallback = RandomPolicy(seed=fallback_seed, name="fallback")
        self.calls = 0
        self.parse_failures = 0
        self.client_errors = 0
        self.last: Completion | None = None

    def build_prompt(self, frames: list[FrameData], latest: FrameData) -> str:
        from .frames import main_grid, render_diff

        options = [a.name for a in legal_actions(latest) if a is not GameAction.RESET]
        last_action = latest.action_input.id.name if latest.action_input else "none yet"
        feedback = "this is the first frame"
        if len(frames) >= 2:
            try:
                feedback = render_diff(main_grid(frames[-2]), main_grid(latest))
            except ValueError:
                feedback = "the screen changed shape"
        return PROMPT.format(
            screen=self.encode(latest),
            last_action=last_action,
            feedback=feedback,
            options=", ".join(options) or "none",
        )

    def choose(self, frames: list[FrameData], latest: FrameData) -> Action:
        if latest.state in (GameState.NOT_PLAYED, GameState.GAME_OVER):
            return Action(GameAction.RESET, reasoning="game not in play — reset")

        prompt = self.build_prompt(frames, latest)
        completion = self.client.complete(prompt)
        self.last = completion
        self.calls += 1

        if not completion.ok:
            self.client_errors += 1
            return self._fall_back(frames, latest, f"client error: {completion.error}")

        action = parse_action(completion.text)
        if action is None:
            self.parse_failures += 1
            first = completion.text.strip().splitlines()[:1]
            return self._fall_back(frames, latest, f"unparseable reply: {first!r:.120}")

        return Action(action.kind, action.x, action.y, reasoning=completion.text.strip()[:300])

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
