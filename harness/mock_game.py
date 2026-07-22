"""A fake ARC-AGI-3 game that runs offline, so the harness can be tested without quota.

Why this exists: every test of the loop, the guards, the traces and (later) the eval
runner would otherwise need a live API key, a network round trip, and a slice of a free
tier. That makes tests slow, flaky and rationed — so in practice they don't get written.
A deterministic local environment makes the whole harness testable in milliseconds.

What it is NOT: a model of a real ARC-AGI-3 game. Real games are unknown by design —
that is the benchmark's entire point. This one has rules we invented, and no number
produced against it is a claim about real performance. It exists to exercise machinery.

What it IS faithful about: the *contract*. It returns the SDK's own `FrameData` objects,
with the same fields, the same action set, the same 0-63 coordinate cap, and the same
`available_actions` mechanism, so code written against it is written against the real
interface.

The rules (deliberately simple, deliberately including dead actions):
  * a 16x16 grid; agent block = 4, target = 3, painted cell = 8, background = 0
  * ACTION1/2/3/4 move the agent up/down/left/right by one cell (clipped at the edges)
  * ACTION5 and ACTION7 do nothing at all — the dead actions a good agent must notice
  * ACTION6(x, y) paints a cell: the screen changes but the score never does — the
    "something happened, but it was useless" case that fools a change-seeking agent
  * stepping onto the target scores +1 and moves the target on
  * 3 points wins
"""

from __future__ import annotations

from arc_agi_3._structs import ActionInput, FrameData, GameAction, GameState

from .actions import Action
from .frames import Grid

SIZE = 16
BACKGROUND = 0
TARGET = 3
AGENT = 4
PAINT = 8
WIN_SCORE = 3

# Where the target sits at score 0, 1, 2. Fixed, not random: a test that depends on a
# random seed is a test that argues with you later.
TARGET_PATH = [(2, 5), (9, 12), (13, 3)]

MOVES = {
    GameAction.ACTION1: (-1, 0),  # up
    GameAction.ACTION2: (1, 0),  # down
    GameAction.ACTION3: (0, -1),  # left
    GameAction.ACTION4: (0, 1),  # right
}

AVAILABLE = [
    GameAction.RESET,
    GameAction.ACTION1,
    GameAction.ACTION2,
    GameAction.ACTION3,
    GameAction.ACTION4,
    GameAction.ACTION5,
    GameAction.ACTION6,
    GameAction.ACTION7,
]


class MockGame:
    """A deterministic offline environment satisfying `harness.loop.Environment`."""

    game_id = "mock01"

    def __init__(
        self,
        size: int = SIZE,
        start: tuple[int, int] = (0, 0),
        available: list[GameAction] | None = None,
    ) -> None:
        if size < 4:
            raise ValueError("size must be at least 4")
        self.size = size
        self.start = start
        # Real games advertise different action sets per frame; being able to restrict
        # them here is how the loop's illegal-action guard gets tested.
        self.available = list(available) if available is not None else list(AVAILABLE)
        self.painted: set[tuple[int, int]] = set()
        self.agent = start
        self.score = 0
        self.state = GameState.NOT_PLAYED
        self.steps = 0

    # -- internals --------------------------------------------------------- #
    @property
    def target(self) -> tuple[int, int] | None:
        if self.score >= len(TARGET_PATH):
            return None
        r, c = TARGET_PATH[self.score]
        return (min(r, self.size - 1), min(c, self.size - 1))

    def _grid(self) -> Grid:
        grid = [[BACKGROUND] * self.size for _ in range(self.size)]
        for r, c in self.painted:
            grid[r][c] = PAINT
        t = self.target
        if t is not None:
            grid[t[0]][t[1]] = TARGET
        grid[self.agent[0]][self.agent[1]] = AGENT
        return grid

    def _frame(self, action: Action | None = None) -> FrameData:
        action_input = ActionInput(
            id=action.kind if action else GameAction.RESET,
            data=action.payload() if action else {},
            reasoning=action.reasoning if action else None,
        )
        return FrameData(
            game_id=self.game_id,
            frame=[self._grid()],
            state=self.state,
            score=self.score,
            action_input=action_input,
            guid="mock-guid",
            full_reset=action is None,
            available_actions=list(self.available),
        )

    # -- Environment protocol ---------------------------------------------- #
    def reset(self) -> FrameData:
        self.agent = self.start
        self.painted = set()
        self.score = 0
        self.steps = 0
        self.state = GameState.NOT_FINISHED
        return self._frame(None)

    def step(self, action: Action) -> FrameData:
        if action.kind is GameAction.RESET:
            return self.reset()

        self.steps += 1
        if self.state is GameState.NOT_PLAYED:
            # Acting before a reset is legal on the real API too; it just does nothing.
            return self._frame(action)

        if action.kind in MOVES:
            dr, dc = MOVES[action.kind]
            r = min(max(self.agent[0] + dr, 0), self.size - 1)
            c = min(max(self.agent[1] + dc, 0), self.size - 1)
            self.agent = (r, c)
            if self.agent == self.target:
                self.score += 1
                if self.score >= WIN_SCORE:
                    self.state = GameState.WIN
        elif action.kind is GameAction.ACTION6:
            # x is the column, y is the row — same convention as the SDK's grid coords.
            r, c = int(action.y or 0), int(action.x or 0)
            if r < self.size and c < self.size and (r, c) != self.agent:
                self.painted.add((r, c))
        # ACTION5 / ACTION7: nothing. On purpose.

        return self._frame(action)


__all__ = ["AGENT", "BACKGROUND", "MockGame", "PAINT", "SIZE", "TARGET", "WIN_SCORE"]
