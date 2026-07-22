"""What the free tier actually allows, and a limiter that keeps us inside it.

Two things live here:

* `LIMITS` — the measured free-tier rate limits, per model. Not from documentation:
  Google stopped publishing free-tier numbers and points you at your own dashboard, so
  these were read off Chetan's `aistudio.google.com/rate-limit` page on **2026-07-22** and
  are specific to that account. They are data, and they go stale; re-read them rather than
  trusting this table forever.
* `RateLimiter` — enforces them client-side by waiting.

Why enforce them ourselves rather than catching 429s and retrying: a 429 in the middle of a
game costs a turn and pollutes the trace with a failure that isn't the agent's. Waiting
4 seconds is boring and correct. The limiter also makes the *cost* of a design visible —
if a run spends most of its wall-clock asleep, the loop is asking the model too often, and
that shows up as a number instead of a feeling.

Definitions, since the dashboard's abbreviations are not obvious:
    RPM — requests per minute
    TPM — **input** tokens per minute (the dashboard chart is labelled "peak input tokens")
    RPD — requests per day
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass

SOURCE = "aistudio.google.com/rate-limit, free tier, read 2026-07-22"


@dataclass(frozen=True)
class Limits:
    """One model's free-tier allowance."""

    model: str
    rpm: int
    tpm: int
    rpd: int

    def actions_per_day(self, calls_per_action: int = 1) -> float:
        """How many game actions a day's quota buys, at N model calls per action."""
        return self.rpd / calls_per_action

    def seconds_per_call(self) -> float:
        """Minimum spacing the RPM limit implies."""
        return 60.0 / self.rpm if self.rpm else 0.0

    def binding_limit(self, tokens_per_call: int) -> str:
        """Which ceiling we hit first at this prompt size: 'RPM' or 'TPM'."""
        if not tokens_per_call:
            return "RPM"
        calls_allowed_by_tokens = self.tpm / tokens_per_call
        return "TPM" if calls_allowed_by_tokens < self.rpm else "RPM"


# Text-out models only; image/audio/embedding rows are irrelevant to this project.
LIMITS: dict[str, Limits] = {
    m.model: m
    for m in [
        # The Flash-Lite tier is the interesting one: same 250K TPM as its bigger
        # siblings, three times the RPM, and twenty-five times the daily requests.
        Limits("gemini-3.5-flash-lite", rpm=15, tpm=250_000, rpd=500),
        Limits("gemini-3.1-flash-lite", rpm=15, tpm=250_000, rpd=500),
        Limits("gemini-2.5-flash-lite", rpm=10, tpm=250_000, rpd=20),
        Limits("gemini-3.6-flash", rpm=5, tpm=250_000, rpd=20),
        Limits("gemini-3.5-flash", rpm=5, tpm=250_000, rpd=20),
        Limits("gemini-3-flash-preview", rpm=5, tpm=250_000, rpd=20),
        Limits("gemini-2.5-flash", rpm=5, tpm=250_000, rpd=20),
        # The open Gemma models trade the token budget for the request budget: 16K TPM
        # instead of 250K, but 14,400 requests a day instead of 500 — 180 games a day
        # against 6, which is why Phase B picked one of them as the eval model.
        #
        # DO NOT USE THEM. **MEASURED 2026-07-22** (`artifacts/model-bakeoff.json`): both
        # answer a "say ready" prompt in ~3 s and answer a real 1,464-character game prompt
        # **0 times out of 3** — `504 DEADLINE_EXCEEDED` from the server, then read timeouts.
        # The limits below are real and the throughput they imply is fiction.
        #
        # The lesson is worth more than the models: **a rate limit is a promise about
        # requests you may make, not about requests that will be served.** A dashboard
        # cannot tell you the second thing, and a smoke test with a toy prompt cannot
        # either. Only the real prompt can.
        Limits("gemma-4-31b-it", rpm=30, tpm=16_000, rpd=14_400),
        Limits("gemma-4-26b-a4b-it", rpm=30, tpm=16_000, rpd=14_400),
    ]
}


class BudgetExhausted(RuntimeError):
    """The daily request allowance is gone. Not retryable today."""


# Pace at 80% of the stated limit, not 100%.
#
# MEASURED 2026-07-22: a limiter pacing at exactly the dashboard's 15 RPM still collected
# `429 RESOURCE_EXHAUSTED` on 3 of 80 calls. Our window and the server's do not start at the
# same instant, our clock is not its clock, and requests already in flight still count — so
# "exactly at the limit" is, from the server's side, sometimes just over it. Headroom is
# cheaper than a lost turn: at 15 RPM this costs 3 seconds a minute and removes a failure
# mode that otherwise lands in the middle of a game.
HEADROOM = 0.8


class RateLimiter:
    """Blocks until the next call is allowed. Thread-safe, though we are single-threaded.

    Tracks a rolling 60-second window for RPM and TPM, and a simple counter for RPD. The
    day counter is per-process: it protects a run, not a whole day across restarts, and
    saying so is more useful than pretending otherwise.
    """

    def __init__(
        self,
        limits: Limits,
        sleep=time.sleep,
        clock=time.monotonic,
        headroom: float = HEADROOM,
    ) -> None:
        self.limits = limits
        self.headroom = headroom
        self._rpm = max(1, int(limits.rpm * headroom))
        self._tpm = max(1, int(limits.tpm * headroom))
        self._sleep = sleep
        self._clock = clock
        self._calls: deque[float] = deque()
        self._tokens: deque[tuple[float, int]] = deque()
        self._day_calls = 0
        self._waited = 0.0
        self._lock = threading.Lock()

    @property
    def calls_made(self) -> int:
        return self._day_calls

    @property
    def seconds_waited(self) -> float:
        """Total time spent asleep. A budget cost that would otherwise be invisible."""
        return round(self._waited, 3)

    def _prune(self, now: float) -> None:
        while self._calls and now - self._calls[0] >= 60:
            self._calls.popleft()
        while self._tokens and now - self._tokens[0][0] >= 60:
            self._tokens.popleft()

    def acquire(self, tokens: int = 0) -> float:
        """Wait until a call of `tokens` input tokens is allowed. Returns seconds waited."""
        with self._lock:
            if self._day_calls >= self.limits.rpd:
                raise BudgetExhausted(
                    f"{self.limits.model}: {self._day_calls} requests used, "
                    f"daily limit is {self.limits.rpd} ({SOURCE})"
                )
            waited = 0.0
            while True:
                now = self._clock()
                self._prune(now)
                wait_for = 0.0
                if len(self._calls) >= self._rpm:
                    wait_for = max(wait_for, 60 - (now - self._calls[0]))
                used = sum(n for _, n in self._tokens)
                if tokens and used + tokens > self._tpm and self._tokens:
                    wait_for = max(wait_for, 60 - (now - self._tokens[0][0]))
                if wait_for <= 0:
                    break
                self._sleep(wait_for)
                waited += wait_for

            now = self._clock()
            self._calls.append(now)
            if tokens:
                self._tokens.append((now, tokens))
            self._day_calls += 1
            self._waited += waited
            return waited


__all__ = ["LIMITS", "SOURCE", "BudgetExhausted", "Limits", "RateLimiter"]
