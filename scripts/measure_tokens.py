"""Measure every encoding of a real frame under BOTH tokenisers, and write the artifact.

    py scripts/measure_tokens.py [--model gemini-3.5-flash-lite]

Writes `artifacts/tokens-by-tokeniser.json`. Needs a Gemini key (see `notes/howto/02`);
without one it still reports characters and tiktoken counts and says the Gemini column is
missing rather than guessing it.

Why this script exists. Every token figure this project published before 2026-07-22 came
from `tiktoken/o200k_base` — an *OpenAI* tokeniser — carrying the caveat that it was only
valid for comparing our own encodings with each other. That caveat turned out to be doing
real work: on the first real measurement, Gemini's own counter charged **2.8× more** for the
same grid, because it does not pack runs of hex digits the way o200k_base does. A ratio
between encodings is not portable across tokenisers, and this file is the evidence.

One request per encoding, `count_tokens` only — no generation, so it costs a handful of
requests against the daily quota and no output tokens at all.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness.env_file import read_env_key  # noqa: E402
from harness.frames import render_diff, render_grid, render_objects  # noqa: E402
from harness.tokens import measure  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
DEFAULT_MODEL = "gemini-3.5-flash-lite"


def frames_from_recording() -> tuple[str, list[list[int]], list[list[int]]]:
    """(recording name, previous grid, current grid) from the middle of one run.

    The recording is the **last by filename**, not the newest by clock, and the frame is the
    middle one — both chosen for being deterministic. Re-running this script must produce
    the same numbers the notes quote, and "whatever I recorded most recently" would not.
    The chosen file is printed and stored in the artifact.
    """
    runs = sorted((ROOT / "runs").glob("*.recording.jsonl"))
    if not runs:
        raise SystemExit("no recordings in runs/ — play a game first")
    path = runs[-1]
    grids = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        data = json.loads(line).get("data")
        if isinstance(data, dict) and data.get("frame"):
            grids.append(data["frame"][-1])  # the settled grid; see harness.frames
    if len(grids) < 2:
        raise SystemExit(f"{path.name} has fewer than two frames")
    mid = len(grids) // 2
    return path.name, grids[mid - 1], grids[mid]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args(argv)

    name, prev, cur = frames_from_recording()

    # The adversarial grid, imported rather than rebuilt so both scripts measure the same
    # thing: a checkerboard is 2,048 one-cell objects, the case where "compression" inverts.
    from measure_encodings import busy_grid  # noqa: E402

    checker = busy_grid()

    encodings = {
        "real frame / raw grid, hex packed": render_grid(cur),
        "real frame / raw grid, decimal space-separated": render_grid(cur, sep=" ", cell="dec"),
        "real frame / objects (cap 40)": render_objects(cur),
        "real frame / diff vs previous frame": render_diff(prev, cur),
        "synthetic checkerboard / raw grid, hex packed": render_grid(checker),
        "synthetic checkerboard / objects (uncapped)": render_objects(checker, max_blobs=10_000),
        "synthetic checkerboard / objects (cap 40)": render_objects(checker),
    }

    counter = None
    key = read_env_key("GEMINI_API_KEY", "GOOGLE_API_KEY", required=False)
    if key:
        try:
            from google import genai

            client = genai.Client(api_key=key)

            def counter(text: str) -> int | str:  # noqa: F811
                try:
                    return client.models.count_tokens(
                        model=args.model, contents=text
                    ).total_tokens
                except Exception as exc:
                    return f"err: {type(exc).__name__}"
        except ImportError:
            print("google-genai not installed; skipping the Gemini column")

    rows = []
    for label, text in encodings.items():
        local = measure(label, text)
        row = local.as_dict()
        row["gemini_tokens"] = counter(text) if counter else None
        row["gemini_model"] = args.model if counter else None
        row["chars_per_gemini_token"] = (
            round(local.chars / row["gemini_tokens"], 3)
            if isinstance(row["gemini_tokens"], int) and row["gemini_tokens"]
            else None
        )
        rows.append(row)

    # Ratios are taken against the hex-packed grid *of the same family* — comparing a
    # synthetic checkerboard against a real frame would be a ratio between two different
    # pictures, which measures nothing.
    for family, base_label in (
        ("real frame /", "real frame / raw grid, hex packed"),
        ("synthetic checkerboard /", "synthetic checkerboard / raw grid, hex packed"),
    ):
        base = next(r for r in rows if r["label"] == base_label)
        for row in rows:
            if not row["label"].startswith(family):
                continue
            row["x_vs_hex_packed_tiktoken"] = (
                round(row["tokens"] / base["tokens"], 3)
                if base["tokens"] and row["tokens"]
                else None
            )
            row["x_vs_hex_packed_gemini"] = (
                round(row["gemini_tokens"] / base["gemini_tokens"], 3)
                if isinstance(base["gemini_tokens"], int)
                and isinstance(row["gemini_tokens"], int)
                and base["gemini_tokens"]
                else None
            )

    report = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_recording": name,
        "gemini_model": args.model if counter else None,
        "note": (
            "Two tokenisers, same strings. tiktoken/o200k_base is OpenAI's and is only "
            "valid for comparing our encodings with each other; the Gemini column is the "
            "one that maps to a real context window and a real bill for the model we call."
        ),
        "encodings": rows,
    }
    ARTIFACTS.mkdir(exist_ok=True)
    out = ARTIFACTS / "tokens-by-tokeniser.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    width = max(len(r["label"]) for r in rows)
    print(f"frame from     : {name}")
    print(f"gemini model   : {args.model if counter else '(no key — column skipped)'}\n")
    head = f"{'encoding'.ljust(width)}  {'chars':>7} {'tiktoken':>9} {'gemini':>8} {'x tik':>7} {'x gem':>7}"
    print(head)
    print("-" * len(head))
    for r in rows:
        print(
            f"{r['label'].ljust(width)}  {r['chars']:>7,} {str(r['tokens']):>9} "
            f"{str(r['gemini_tokens']):>8} {str(r['x_vs_hex_packed_tiktoken']):>7} "
            f"{str(r['x_vs_hex_packed_gemini']):>7}"
        )
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
