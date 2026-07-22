"""Reading a secret from the environment or a `.env` file, once, correctly.

This is four lines of logic and it lives in its own module because getting it slightly
wrong has already cost this project two sessions. Windows PowerShell 5.1's
`Set-Content -Encoding utf8` writes a **byte-order mark** — three invisible bytes at the
start of the file. A `.env` written that way defines a variable literally named
`﻿ARC_API_KEY`, so the lookup for `ARC_API_KEY` misses, the request goes out with no
key, and the server answers 401. The failure looks exactly like a wrong key, which is why
it was diagnosed twice.

`encoding="utf-8-sig"` strips that mark. Every key this project reads goes through here,
so the fix cannot be forgotten in the next adapter.
"""

from __future__ import annotations

import os
from pathlib import Path


class MissingKey(RuntimeError):
    """No key anywhere. Carries the names we looked for, so the message is actionable."""


def read_env_key(
    *names: str,
    explicit: str | None = None,
    env_path: str | Path = ".env",
    required: bool = True,
) -> str | None:
    """First of `names` found in: the explicit argument, the environment, then `.env`.

    Several names because vendors disagree with themselves — Google's own SDK reads both
    `GEMINI_API_KEY` and `GOOGLE_API_KEY` (verified in its docs, 2026-07-22).
    """
    if explicit:
        return explicit
    for name in names:
        value = os.getenv(name)
        if value:
            return value

    path = Path(env_path)
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            line = raw.lstrip("﻿").strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key.strip() in names:
                return value.strip().strip('"').strip("'")

    if required:
        wanted = " or ".join(names)
        raise MissingKey(
            f"no {wanted} found — set the environment variable, or put "
            f"'{names[0]}=<key>' in a .env file in this folder"
        )
    return None


__all__ = ["MissingKey", "read_env_key"]
