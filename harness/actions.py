"""An immutable action record, and the reason it exists.

The SDK models actions as `GameAction`, an `Enum` — but each member *stores the payload
for the current call on itself*:

    class GameAction(Enum):
        RESET = (0, SimpleAction)
        ...
        def set_data(self, data): self.action_data = self.action_type(**data); ...

Enum members are singletons, so `GameAction.ACTION6.set_data(...)` mutates process-global
state. Two agents in one process (or one agent building a batch of candidate actions
before choosing) will silently clobber each other's coordinates. Verified by reading
`arc_agi_3/_structs.py` (v0.0.1), lines 147-189.

So the harness passes around this frozen record instead, and only touches the enum at the
boundary where a request is actually sent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from arc_agi_3._structs import ComplexAction, GameAction

GRID_MAX = 63  # coordinates are capped at 0-63 by the SDK's ComplexAction schema


@dataclass(frozen=True)
class Action:
    """One action the agent wants to take.

    `kind` is the SDK enum member used purely as an identity (which button).
    `x`/`y` are required for complex actions (ACTION6) and must be None otherwise.
    `reasoning` is the opaque blob the server stores and echoes back; it is where the
    model's justification goes, so a trace can be read next to the score it produced.
    """

    kind: GameAction
    x: int | None = None
    y: int | None = None
    reasoning: Any = None

    def __post_init__(self) -> None:
        if self.kind.is_complex():
            if self.x is None or self.y is None:
                raise ValueError(f"{self.kind.name} needs x and y")
            if not (0 <= self.x <= GRID_MAX and 0 <= self.y <= GRID_MAX):
                raise ValueError(
                    f"{self.kind.name} coordinates out of range: ({self.x}, {self.y})"
                )
        elif self.x is not None or self.y is not None:
            raise ValueError(f"{self.kind.name} is a simple action and takes no coordinates")

    @property
    def name(self) -> str:
        return self.kind.name

    def label(self) -> str:
        """Short human/trace label, e.g. 'ACTION6(x=12,y=40)'."""
        if self.kind.is_complex():
            return f"{self.kind.name}(x={self.x},y={self.y})"
        return self.kind.name

    def payload(self) -> dict[str, Any]:
        """The data dict the SDK's request builder expects."""
        if self.kind.is_complex():
            return ComplexAction(x=self.x or 0, y=self.y or 0).model_dump(exclude={"game_id"})
        return {}


__all__ = ["Action", "GRID_MAX"]
