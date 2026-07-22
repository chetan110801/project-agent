"""Calling a model, behind an interface small enough to fake.

The whole provider surface this project needs is one function:

    complete(prompt: str) -> Completion

`GeminiClient` implements it against `google-genai`, with the free-tier rate limits
enforced client-side (`harness/budget.py`) rather than discovered as 429s mid-game.
`ScriptedClient` implements it from a list, so every test of the policy and the loop runs
offline, instantly, and for free — the same reason `mock_game.py` exists.

Keeping the surface this small is a deliberate bet: swapping providers for the Phase B
bake-off should be a new twenty-line class, not a refactor of the loop.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from .budget import LIMITS, Limits, RateLimiter


@dataclass
class Completion:
    """One model response, with the numbers a budget report needs."""

    text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: float = 0.0
    waited_ms: float = 0.0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


@runtime_checkable
class LLMClient(Protocol):
    name: str

    def complete(self, prompt: str) -> Completion: ...


class ScriptedClient:
    """Returns canned replies in order. The offline stand-in for a real model.

    `replies` may contain strings or Exceptions; an Exception is *returned* as a failed
    Completion rather than raised, because that is what a real provider outage looks like
    to the policy and the policy has to keep playing through it.
    """

    def __init__(self, replies: list[Any], name: str = "scripted") -> None:
        self.name = name
        self.replies = list(replies)
        self.prompts: list[str] = []
        self.calls = 0

    def complete(self, prompt: str) -> Completion:
        self.prompts.append(prompt)
        reply = self.replies[self.calls % len(self.replies)] if self.replies else ""
        self.calls += 1
        if isinstance(reply, Exception):
            return Completion(text="", model=self.name, error=str(reply))
        return Completion(
            text=str(reply),
            model=self.name,
            input_tokens=len(prompt) // 4,  # a stand-in, never reported as a measurement
            output_tokens=len(str(reply)) // 4,
        )


@dataclass
class GeminiClient:
    """google-genai, rate-limited to the free tier.

    Errors are captured, not raised: a rate-limit or a transient 500 must cost one turn of
    the game, not the whole run. The loop's guards then handle a missing decision the same
    way they handle a nonsensical one.
    """

    model: str = "gemini-3.5-flash-lite"
    api_key: str | None = None
    limits: Limits | None = None
    temperature: float = 0.0  # deterministic-ish: an eval needs runs to be comparable
    retry_seconds: float = 5.0
    _client: Any = field(default=None, repr=False)
    _limiter: RateLimiter = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.name = self.model
        self.retries = 0
        limits = self.limits or LIMITS.get(self.model)
        if limits is None:
            raise KeyError(
                f"no measured rate limits for {self.model!r} — add them to harness/budget.py "
                f"from aistudio.google.com/rate-limit rather than guessing"
            )
        self.limits = limits
        self._limiter = RateLimiter(limits)
        if self._client is None:
            from google import genai

            from .env_file import read_env_key

            self._client = genai.Client(
                api_key=self.api_key or read_env_key("GEMINI_API_KEY", "GOOGLE_API_KEY")
            )

    @property
    def calls_made(self) -> int:
        return self._limiter.calls_made

    @property
    def seconds_waited(self) -> float:
        return self._limiter.seconds_waited

    def complete(self, prompt: str) -> Completion:
        # Charge the limiter with a character-based estimate: asking the API to count
        # tokens first would double our request count against the very limit we're
        # respecting. 4 chars/token is wrong for these grids (measured: Gemini bills them
        # at ~1 token/char), so we use the conservative 1.
        estimate = len(prompt)
        try:
            waited = self._limiter.acquire(tokens=estimate)
        except Exception as exc:
            return Completion(text="", model=self.model, error=f"{type(exc).__name__}: {exc}")

        from google.genai import types

        t0 = time.perf_counter()
        resp = None
        last_error = ""
        # One retry, only for 429. Client-side pacing at 80% of the stated limit still let
        # 3 of 80 calls through as RESOURCE_EXHAUSTED on 2026-07-22, and a lost turn is a
        # hole in an episode we paid quota for. Retrying anything else would hide real bugs.
        for attempt in range(2):
            try:
                resp = self._client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=self.temperature),
                )
                break
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {str(exc)[:200]}"
                if attempt == 0 and "429" in str(exc):
                    self.retries += 1
                    backoff = self.retry_seconds
                    time.sleep(backoff)
                    waited += backoff
                    continue
                break

        if resp is None:
            return Completion(
                text="",
                model=self.model,
                latency_ms=round((time.perf_counter() - t0) * 1000, 2),
                waited_ms=round(waited * 1000, 2),
                error=last_error,
            )

        usage = getattr(resp, "usage_metadata", None)
        return Completion(
            text=resp.text or "",
            model=self.model,
            input_tokens=getattr(usage, "prompt_token_count", None),
            output_tokens=getattr(usage, "candidates_token_count", None),
            latency_ms=round((time.perf_counter() - t0) * 1000, 2),
            waited_ms=round(waited * 1000, 2),
        )


__all__ = ["Completion", "GeminiClient", "LLMClient", "ScriptedClient"]
