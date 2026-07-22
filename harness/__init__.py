"""project-agent harness — our own agent machinery around ARC-AGI-3.

Deliberately *not* a subclass of the SDK's `Agent`. The SDK owns the wire protocol
(HTTP, auth, frame validation); this package owns everything the interview story is
about: the loop, what gets shown to the model, traces, budgets, evals.

Everything here runs offline against `harness.mock_game`, so the loop can be built and
tested without an API key or quota. The only piece that needs the network is the real
environment adapter (Phase A, blocked on the key).

Data types are the SDK's own pydantic models (`FrameData`, `GameAction`, `GameState`) so
our code is written against the real contract, not a guess at it.
"""

from __future__ import annotations

from .actions import Action
from .frames import (
    FrameDiff,
    diff_grids,
    grid_shape,
    main_grid,
    render_diff,
    render_grid,
    render_objects,
)
from .loop import EpisodeResult, StepRecord, run_episode
from .policies import Policy, RandomPolicy
from .tokens import SizeReport, measure
from .trace import Tracer

__all__ = [
    "Action",
    "EpisodeResult",
    "FrameDiff",
    "Policy",
    "RandomPolicy",
    "SizeReport",
    "StepRecord",
    "Tracer",
    "diff_grids",
    "grid_shape",
    "main_grid",
    "measure",
    "render_diff",
    "render_grid",
    "render_objects",
    "run_episode",
]
