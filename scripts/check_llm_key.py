"""Prove a free LLM key works, and measure what a real game frame costs in ITS tokens.

    py scripts/check_llm_key.py

Written 2026-07-22 for `notes/howto/02-get-a-free-llm-api-key.md`.

**Verified state.** The no-key path and the frame-loading path were run in this session
and behave as documented. The three steps that require a live key — model list, one
generated reply, and Gemini's own token count — are **untested until a key exists**; they
are written against `google-genai` 2.8.0 as installed on this laptop (`client.models.list`,
`client.models.generate_content`, `client.models.count_tokens`, all confirmed present by
introspection). Delete this paragraph after a real key runs it end to end.

Why the token count matters more than the "hello" reply: every token figure in this repo so
far carries the caveat that it came from `tiktoken/o200k_base`, an *OpenAI* tokeniser, and
is therefore only valid for comparing our own encodings against each other
(`artifacts/run-report.json`). A model's real bill is counted by its own tokeniser. This
script asks Gemini to count a real `ls20` frame, so the budget numbers in study note 06
can finally be stated in the units the model actually charges in.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.env_file import read_env_key  # noqa: E402
from harness.frames import render_grid, render_objects  # noqa: E402
from harness.tokens import measure  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MODEL = "gemini-2.5-flash"


def mask(key: str) -> str:
    """Never print a key. Enough characters to tell two keys apart, and no more."""
    return f"{key[:4]}…{key[-4:]} ({len(key)} chars)" if len(key) > 12 else "(short key)"


def newest_frame() -> list[list[int]] | None:
    """The last settled grid from the newest committed recording, or None."""
    runs = sorted((ROOT / "runs").glob("*.recording.jsonl"))
    if not runs:
        return None
    for line in reversed(runs[-1].read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        data = json.loads(line).get("data")
        if isinstance(data, dict) and data.get("frame"):
            return data["frame"][-1]
    return None


def main() -> int:
    key = read_env_key("GEMINI_API_KEY", "GOOGLE_API_KEY", required=False)
    if not key:
        print("no GEMINI_API_KEY or GOOGLE_API_KEY found.")
        print("Follow notes/howto/02-get-a-free-llm-api-key.md, then run this again.")
        return 1
    print(f"key found      : {mask(key)}")

    try:
        from google import genai
    except ImportError:
        print("google-genai is not installed. Run:  py -m pip install -U google-genai")
        return 1

    client = genai.Client(api_key=key)

    # 1. Can we see the free models?
    try:
        names = [m.name for m in client.models.list()]
    except Exception as exc:
        print(f"FAILED to list models: {type(exc).__name__}: {exc}")
        print("A 400/403 here almost always means the key is wrong or not yet active.")
        return 1
    flash = [n for n in names if "flash" in n.lower()]
    print(f"models visible : {len(names)} ({len(flash)} with 'flash' in the name)")

    # 2. One tiny round trip — proves the key can actually generate, not just read.
    t0 = time.perf_counter()
    try:
        reply = client.models.generate_content(
            model=MODEL, contents="Reply with exactly the word: ready"
        )
    except Exception as exc:
        print(f"FAILED to generate: {type(exc).__name__}: {exc}")
        return 1
    ms = (time.perf_counter() - t0) * 1000
    print(f"round trip     : {ms:.0f} ms, model said {(reply.text or '').strip()!r}")

    # 3. What a real frame costs, in the model's OWN tokens.
    grid = newest_frame()
    if grid is None:
        print("no recording in runs/ — skipping the frame measurement")
        return 0

    print(f"\n{'encoding':<28}{'chars':>8}{'tiktoken':>10}{'gemini':>9}")
    print("-" * 55)
    for label, text in (
        ("raw grid, hex packed", render_grid(grid)),
        ("objects", render_objects(grid)),
    ):
        local = measure(label, text)
        try:
            n = client.models.count_tokens(model=MODEL, contents=text).total_tokens
        except Exception as exc:
            n = f"err: {type(exc).__name__}"
        print(f"{label:<28}{local.chars:>8,}{str(local.tokens):>10}{str(n):>9}")

    print(
        "\nThe 'gemini' column is the one that maps to a real bill and a real context "
        "window; the tiktoken column only ever compared our encodings with each other."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
