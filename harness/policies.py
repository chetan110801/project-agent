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
from typing import Protocol, runtime_checkable

from arc_agi_3._structs import FrameData, GameAction, GameState

from .actions import GRID_MAX, Action


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
    """
    return list(latest.available_actions) or list(GameAction)


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


__all__ = ["Policy", "RandomPolicy", "legal_actions"]
