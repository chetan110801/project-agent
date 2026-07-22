"""Prove a free LLM key works, and measure what a real game frame costs in ITS tokens.

    py scripts/check_llm_key.py

Written 2026-07-22 for `notes/howto/02-get-a-free-llm-api-key.md`.

**Verified end to end on 2026-07-22** against a real key: model probe, generation, and
token counting all ran.

Why the token count matters more than the "hello" reply: every token figure in this repo
before that day came from `tiktoken/o200k_base`, an *OpenAI* tokeniser, carrying the caveat
that it was only good for comparing our own encodings against each other. The caveat earned
its keep — Gemini's own counter charged **2.8× more** for the same grid, which turned study
note 06's headline "5.6×" into "2.0×". See `scripts/measure_tokens.py` for the full
two-tokeniser table; this script is only a smoke test.
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

# Tried in order; the first that actually answers wins.
#
# This is a list and not a constant because `models.list()` cannot be trusted to say what
# you may call. Measured 2026-07-22 on this key: the API listed `gemini-2.5-flash` with
# `generateContent` among its supported actions, and calling it returned
# `404 ... no longer available to new users`. A model being listed means it exists, not
# that your account may use it. The only reliable check is a request.
#
# Order: cheapest-and-current first. Flash-Lite is the right default for an agent that
# makes one call per game action; the `-latest` aliases are the fallback because they keep
# working across retirements — at the cost of not being pinned, which matters for evals and
# not for a smoke test.
CANDIDATES = [
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
]


def _short(exc: Exception) -> str:
    """One line of an API error — the status and reason, not the whole JSON blob."""
    text = str(exc).replace("\n", " ")
    return text[:90] + "…" if len(text) > 90 else text


def mask(key: str) -> str:
    """Never print a key. Enough characters to tell two keys apart, and no more."""
    return f"{key[:4]}…{key[-4:]} ({len(key)} chars)" if len(key) > 12 else "(short key)"


def sample_frame() -> list[list[int]] | None:
    """One settled grid from a committed recording, or None if there are none.

    This is a smoke test, so it just grabs the final frame of the last recording by
    filename. For the numbers the study notes quote, use `scripts/measure_tokens.py`, which
    pins both the recording and the frame so the figures reproduce.
    """
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
    wanted = sys.argv[1:2] or CANDIDATES
    model = None
    for candidate in wanted:
        t0 = time.perf_counter()
        try:
            reply = client.models.generate_content(
                model=candidate, contents="Reply with exactly the word: ready"
            )
        except Exception as exc:
            print(f"  {candidate:26} unavailable ({_short(exc)})")
            continue
        ms = (time.perf_counter() - t0) * 1000
        model = candidate
        print(f"model          : {model}")
        print(f"round trip     : {ms:.0f} ms, model said {(reply.text or '').strip()!r}")
        break

    if model is None:
        print("\nno candidate model answered. Pass one explicitly:")
        print(f"  py scripts/check_llm_key.py <model-name>")
        print(f"  (flash models this key can see: {', '.join(f.split('/')[-1] for f in flash[:6])} …)")
        return 1

    # 3. What a real frame costs, in the model's OWN tokens.
    grid = sample_frame()
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
            n = client.models.count_tokens(model=model, contents=text).total_tokens
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
