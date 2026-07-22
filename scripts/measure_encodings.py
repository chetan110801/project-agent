"""How big is one frame, under each way of writing it down?

    py scripts/measure_encodings.py

Writes `artifacts/encoding-sizes.json` (the numbers) and prints a table.

WHAT IS MEASURED: synthetic 64x64 grids built here in this file. For numbers on REAL
frames, use `scripts/analyze_run.py`, which reads a committed recording — that is the
script the study notes quote. This one survives for a different job: it constructs the
*adversarial* grid (a checkerboard, 2,048 one-cell objects) that shows the object encoding
inverting and becoming larger than the pixels it replaced. Real recordings happen to
contain no such frame; that is luck, not safety, so the worst case is built by hand.

CHARACTERS are exact and tokeniser-independent. TOKENS are counted with OpenAI's
`tiktoken` (o200k_base) and are only valid for cross-encoding comparison — they are the
wrong counter for a Claude or Gemini budget (study note 03). The tokeniser name is
written next to every token number so it can never be mistaken for a budget.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.frames import Grid, render_diff, render_grid, render_objects  # noqa: E402
from harness.tokens import measure  # noqa: E402

SIZE = 64
ARTIFACTS = Path(__file__).resolve().parents[1] / "artifacts"


def sparse_grid() -> Grid:
    """A typical-looking game screen: a few solid shapes on an empty field."""
    g = [[0] * SIZE for _ in range(SIZE)]
    for r in range(10, 13):  # a 3x3 block
        for c in range(10, 13):
            g[r][c] = 4
    for r in range(30, 40):  # a 10x4 bar
        for c in range(20, 24):
            g[r][c] = 2
    for r in range(50, 52):  # a 2x2 block
        for c in range(58, 60):
            g[r][c] = 6
    g[5][60] = 3  # a lone dot
    return g


def busy_grid() -> Grid:
    """The adversarial case: a checkerboard, i.e. 2048 one-cell objects.

    This exists to stop the object encoding being sold as a free win. On a grid like this
    it is *larger* than the raw pixels, and any agent design that assumed otherwise would
    blow its context budget on exactly the frames that matter most.
    """
    return [[5 if (r + c) % 2 else 0 for c in range(SIZE)] for r in range(SIZE)]


def moved(grid: Grid) -> Grid:
    """The same screen, one object shifted by one cell — a normal turn's change."""
    g = [row[:] for row in grid]
    for r in range(10, 13):
        for c in range(10, 13):
            g[r][c] = 0
    for r in range(10, 13):
        for c in range(11, 14):
            g[r][c] = 4
    return g


def main() -> int:
    sparse = sparse_grid()
    busy = busy_grid()
    after = moved(sparse)

    reports = [
        measure("sparse / raw grid, hex packed", render_grid(sparse)),
        measure("sparse / raw grid, decimal space-separated", render_grid(sparse, sep=" ", cell="dec")),
        measure("sparse / objects", render_objects(sparse)),
        measure("sparse / diff after one move", render_diff(sparse, after)),
        measure("sparse / diff after a dead action", render_diff(sparse, sparse)),
        measure("busy / raw grid, hex packed", render_grid(busy)),
        measure("busy / objects (truncated at 40)", render_objects(busy)),
        measure("busy / objects (untruncated)", render_objects(busy, max_blobs=10_000)),
    ]

    baseline = reports[0].chars
    rows = []
    for r in reports:
        d = r.as_dict()
        d["chars_vs_packed_raw"] = round(r.chars / baseline, 4)
        rows.append(d)

    out = {
        "generated": date.today().isoformat(),
        "what": "size of one 64x64 frame under each encoding in harness/frames.py",
        "caveat": (
            "SYNTHETIC grids built by scripts/measure_encodings.py, not real ARC-AGI-3 "
            "frames. Character counts are exact; token counts are tiktoken/o200k_base "
            "(an OpenAI tokeniser) and are valid for comparing encodings only, never as "
            "a budget for another vendor's model."
        ),
        "grid_size": [SIZE, SIZE],
        "encodings": rows,
    }
    ARTIFACTS.mkdir(exist_ok=True)
    path = ARTIFACTS / "encoding-sizes.json"
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    width = max(len(r.label) for r in reports)
    print(f"{'encoding'.ljust(width)}  {'chars':>7}  {'tokens':>7}  {'x raw':>7}")
    print("-" * (width + 27))
    for r, row in zip(reports, rows):
        tok = "n/a" if r.tokens is None else f"{r.tokens:,}"
        print(f"{r.label.ljust(width)}  {r.chars:>7,}  {tok:>7}  {row['chars_vs_packed_raw']:>7.3f}")
    print(f"\ntokeniser: {reports[0].tokenizer or 'none installed'}")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
