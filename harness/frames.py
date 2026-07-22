"""Turning a frame into something a language model can read.

A frame from the SDK is `list[list[list[int]]]` — a list of 2-D integer grids
(`arc_agi_3/_structs.py`, `FrameData.frame`). Coordinates are capped at 0-63, so a grid
is at most 64x64 = 4096 cells.

The model cannot see a grid. It sees text. *Which* text is the single highest-leverage
decision in this project, so the encodings live here, side by side, measurable against
each other:

    render_grid     — every cell, verbatim. Lossless, biggest.
    render_objects  — connected blocks of one colour, described. Lossy, ~100x smaller.
    render_diff     — what changed since the previous frame. Tiny, useless alone.

Nothing here picks a winner. Phase C's eval suite does that with numbers.
"""

from __future__ import annotations

import hashlib
from collections import deque
from dataclasses import dataclass, field

from arc_agi_3._structs import FrameData

Grid = list[list[int]]

BACKGROUND = 0  # the value we treat as "empty"; see caveat in main_grid()


# --------------------------------------------------------------------------- #
# Getting at the grid
# --------------------------------------------------------------------------- #
def grids(frame: FrameData) -> list[Grid]:
    """All 2-D grids carried by a frame (the SDK sends a list of them)."""
    return list(frame.frame)


def main_grid(frame: FrameData) -> Grid:
    """The grid we treat as 'the screen'.

    VERIFIED on real data (ls20 run, 2026-07-22, `runs/`): 80 of 81 frames carried exactly
    one 64x64 grid, and one frame carried **six** — an animation the server played out in
    response to a single action. So a frame is not always one screen, and code that assumed
    `frame[0]` would be showing the model a stale mid-animation picture.

    We take the **last** grid: the state the world settled into after the action. Every
    intermediate grid is discarded, which is a real (if small) information loss and is
    recorded here rather than hidden.
    """
    gs = grids(frame)
    if not gs:
        raise ValueError("frame carries no grid (FrameData.is_empty() is True)")
    return gs[-1]


def grid_fingerprint(grid: Grid) -> str:
    """A stable 16-character fingerprint of a screen.

    `hashlib`, not Python's `hash()`: the built-in is salted per process, so the same
    screen would fingerprint differently in two runs and nothing could be compared across
    processes — which is exactly what a trace file on disk is for.

    Lives here rather than in the loop so that the live loop and the offline recording
    analyser use one function. Two implementations that "should agree" is how a comparison
    silently becomes an artefact of its two readers.
    """
    payload = ";".join(",".join(str(v) for v in row) for row in grid)
    return hashlib.blake2b(payload.encode("utf-8"), digest_size=8).hexdigest()


def grid_shape(grid: Grid) -> tuple[int, int]:
    """(rows, cols). Raises on a ragged grid rather than producing nonsense later."""
    rows = len(grid)
    if rows == 0:
        return (0, 0)
    widths = {len(r) for r in grid}
    if len(widths) != 1:
        raise ValueError(f"ragged grid: row widths {sorted(widths)}")
    return (rows, widths.pop())


# --------------------------------------------------------------------------- #
# Encoding 1 — every cell, verbatim
# --------------------------------------------------------------------------- #
HEX_DIGITS = "0123456789abcdef"


def render_grid(grid: Grid, sep: str = "", cell: str = "hex") -> str:
    """The whole grid, one row per line.

    `cell="hex"` writes each value as a single hex character (0-f), so a cell is always
    exactly one character and no separator is needed. This is not a stylistic choice:
    real ARC-AGI-3 frames contain values above 9 (measured — the ls20 run reached 12), so
    packed *decimal* is ambiguous and is rejected below rather than silently producing a
    grid the model reads wrongly.

    `cell="dec"` with `sep=" "` is the readable form. It costs several times more tokens
    for identical information — see `artifacts/` and study note 06.
    """
    rows, _ = grid_shape(grid)
    if rows == 0:
        return ""
    if cell == "hex":
        if any(v < 0 or v > 15 for row in grid for v in row):
            raise ValueError("hex rendering covers values 0-15 only")
        return "\n".join(sep.join(HEX_DIGITS[v] for v in row) for row in grid)
    if cell != "dec":
        raise ValueError(f"unknown cell mode {cell!r}; use 'hex' or 'dec'")
    if sep == "" and any(v > 9 or v < 0 for row in grid for v in row):
        raise ValueError(
            "packed decimal is ambiguous for values above 9; use cell='hex' or sep=' '"
        )
    return "\n".join(sep.join(str(v) for v in row) for row in grid)


# --------------------------------------------------------------------------- #
# Encoding 2 — objects
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Blob:
    """One connected block of same-valued cells (4-connectivity)."""

    value: int
    cells: int
    top: int
    left: int
    bottom: int
    right: int

    @property
    def height(self) -> int:
        return self.bottom - self.top + 1

    @property
    def width(self) -> int:
        return self.right - self.left + 1

    @property
    def is_rect(self) -> bool:
        return self.cells == self.height * self.width

    def describe(self) -> str:
        if self.cells == 1:
            return f"colour {self.value}: 1 cell at (r{self.top}, c{self.left})"
        shape = "filled rect" if self.is_rect else "blob"
        return (
            f"colour {self.value}: {shape} {self.height}x{self.width} "
            f"at rows {self.top}-{self.bottom}, cols {self.left}-{self.right} "
            f"({self.cells} cells)"
        )


def infer_background(grid: Grid) -> int:
    """The most common value — our best guess at "empty".

    Needed because the obvious assumption is wrong: in the real `ls20` frames measured on
    2026-07-22, colour **4** covers 2,609 of 4,096 cells and colour 0 appears three times.
    Hard-coding 0 as background made the encoder emit the *floor* as a 2,509-cell object,
    which is both the largest line in the output and pure noise.
    """
    counts: dict[int, int] = {}
    for row in grid:
        for v in row:
            counts[v] = counts.get(v, 0) + 1
    return max(counts.items(), key=lambda kv: (kv[1], -kv[0]))[0] if counts else BACKGROUND


def find_blobs(grid: Grid, background: int | None = BACKGROUND) -> list[Blob]:
    """Connected components of non-background cells, 4-connected, same value.

    `background=None` infers it from the grid (see `infer_background`).

    Flood fill with an explicit queue — no recursion, because a 64x64 field of one colour
    is 4096 deep and would blow the interpreter's stack.
    """
    if background is None:
        background = infer_background(grid)
    rows, cols = grid_shape(grid)
    seen = [[False] * cols for _ in range(rows)]
    blobs: list[Blob] = []
    for r in range(rows):
        for c in range(cols):
            if seen[r][c] or grid[r][c] == background:
                continue
            value = grid[r][c]
            q = deque([(r, c)])
            seen[r][c] = True
            cells = 0
            top = bottom = r
            left = right = c
            while q:
                cr, cc = q.popleft()
                cells += 1
                top, bottom = min(top, cr), max(bottom, cr)
                left, right = min(left, cc), max(right, cc)
                for nr, nc in ((cr - 1, cc), (cr + 1, cc), (cr, cc - 1), (cr, cc + 1)):
                    if 0 <= nr < rows and 0 <= nc < cols and not seen[nr][nc]:
                        if grid[nr][nc] == value:
                            seen[nr][nc] = True
                            q.append((nr, nc))
            blobs.append(Blob(value, cells, top, left, bottom, right))
    blobs.sort(key=lambda b: (-b.cells, b.value, b.top, b.left))
    return blobs


def render_objects(grid: Grid, background: int | None = None, max_blobs: int = 40) -> str:
    """The grid as a list of objects. Lossy on purpose: exact pixels are dropped.

    `background` defaults to **inferred**, not 0 — see `infer_background` for the real
    frame that forced that default.

    `max_blobs` is a guardrail, not a preference: a noisy grid can contain hundreds of
    single-cell blobs, at which case this encoding is *larger* than the raw grid and the
    compression argument inverts. We truncate and say so, rather than silently blowing
    the budget.
    """
    if background is None:
        background = infer_background(grid)
    rows, cols = grid_shape(grid)
    blobs = find_blobs(grid, background)
    head = f"grid {rows}x{cols}, background {background}, {len(blobs)} objects"
    if not blobs:
        return head + "\n(empty)"
    shown = blobs[:max_blobs]
    lines = [head] + [b.describe() for b in shown]
    if len(blobs) > max_blobs:
        lines.append(f"... and {len(blobs) - max_blobs} more objects (truncated)")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Encoding 3 — what changed
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class FrameDiff:
    """Cell-level change between two grids of the same shape."""

    changed: list[tuple[int, int, int, int]] = field(default_factory=list)  # r, c, old, new
    same_shape: bool = True

    @property
    def count(self) -> int:
        return len(self.changed)

    @property
    def is_empty(self) -> bool:
        return self.same_shape and not self.changed


def diff_grids(before: Grid, after: Grid) -> FrameDiff:
    """Which cells differ. Different shapes are reported, not crashed on."""
    if grid_shape(before) != grid_shape(after):
        return FrameDiff(changed=[], same_shape=False)
    rows, cols = grid_shape(after)
    changed = [
        (r, c, before[r][c], after[r][c])
        for r in range(rows)
        for c in range(cols)
        if before[r][c] != after[r][c]
    ]
    return FrameDiff(changed=changed)


def render_diff(before: Grid, after: Grid, max_cells: int = 20) -> str:
    """The change, in words.

    'nothing changed' is the single most useful line the agent can be told — it is how a
    dead action becomes visible instead of being repeated for twenty turns (the stuck-loop
    failure mode).
    """
    d = diff_grids(before, after)
    if not d.same_shape:
        return "grid shape changed"
    if d.is_empty:
        return "nothing changed"
    if d.count <= max_cells:
        cells = "; ".join(f"(r{r}, c{c}) {old}->{new}" for r, c, old, new in d.changed)
        return f"{d.count} cells changed: {cells}"
    rs = [r for r, _, _, _ in d.changed]
    cs = [c for _, c, _, _ in d.changed]
    return (
        f"{d.count} cells changed, within rows {min(rs)}-{max(rs)}, "
        f"cols {min(cs)}-{max(cs)} (too many to list)"
    )


# --------------------------------------------------------------------------- #
# Encoding 4 — what the agent itself has been doing
# --------------------------------------------------------------------------- #
def render_history(frames: list[FrameData], window: int = 8) -> str:
    """The agent's own last `window` actions and what each one did.

    Everything above encodes the *world*. This encodes the *agent*, and it exists because
    of a measured failure: on 2026-07-22 the first LLM run pressed `ACTION3` for 41
    consecutive turns, writing a fresh justification each turn ("repeating it continues the
    progress"). It was not stuck in any sense the loop could see — 37 of those 41 presses
    moved a two-cell marker one column along the bottom row, so `cells_changed` was never 0,
    the `nothing changed` feedback never fired, and the score never moved either.

    The model was not being stupid. It was being asked a question with no memory in it: it
    saw one screen, one last action, and one diff, and from that position pressing the
    button again is a perfectly reasonable answer. Forty times in a row is only visibly
    absurd if you can see the other thirty-nine.

    Derived from the frames, deliberately, and not from the policy's own bookkeeping: the
    loop is allowed to override a policy's choice (illegal actions become RESET), so what
    the policy *asked for* and what was *actually sent* can differ. `action_input` is what
    the server received, which is what the agent needs to reason about.
    """
    if len(frames) < 2:
        return "none yet — this is the first move"
    lines = []
    start = max(1, len(frames) - window)
    for i in range(start, len(frames)):
        prev, cur = frames[i - 1], frames[i]
        label = "?"
        if cur.action_input is not None:
            label = cur.action_input.id.name
            data = cur.action_input.data or {}
            if "x" in data and "y" in data:
                label += f"(x={data['x']}, y={data['y']})"
        try:
            n = diff_grids(main_grid(prev), main_grid(cur)).count
            effect = "screen unchanged" if n == 0 else f"{n} cells changed"
        except ValueError:
            effect = "screen replaced"
        delta = cur.score - prev.score
        if delta:
            effect += f", SCORE +{delta}"
        lines.append(f"  {i - len(frames)}: {label} -> {effect}")
    return "\n".join(lines)


__all__ = [
    "BACKGROUND",
    "HEX_DIGITS",
    "Blob",
    "infer_background",
    "FrameDiff",
    "Grid",
    "diff_grids",
    "find_blobs",
    "grid_fingerprint",
    "grid_shape",
    "grids",
    "main_grid",
    "render_diff",
    "render_grid",
    "render_history",
    "render_objects",
]
