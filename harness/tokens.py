"""Measuring how big a piece of context is.

Two different numbers, and conflating them is a real mistake:

* **characters** — an exact, tokeniser-independent fact about a string. Ratios between
  encodings computed in characters are honest.
* **tokens** — what is actually billed and what the context window is measured in, and it
  is *model-specific*. There is no such thing as "the" token count of a string.

So `measure()` reports characters always, and tokens only when it can name the tokeniser
it used. It never estimates. If no tokeniser is installed, `tokens` is None — a missing
number, which is honest, rather than a made-up one, which is not.

The tokeniser available offline is OpenAI's `tiktoken`. It is the WRONG counter for a
Claude or Gemini budget (see study note 03). It is used here only for cross-encoding
comparison — the ratio between two encodings under one consistent tokeniser — and the
name of the encoding travels with every number so nobody can mistake it for a budget.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

DEFAULT_ENCODING = "o200k_base"


@dataclass(frozen=True)
class SizeReport:
    """How big one piece of context is, with the provenance of every number."""

    label: str
    chars: int
    lines: int
    tokens: int | None
    tokenizer: str | None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def count_tokens(text: str, encoding: str = DEFAULT_ENCODING) -> tuple[int | None, str | None]:
    """(count, tokenizer name) — or (None, None) if no tokeniser is installed."""
    try:
        import tiktoken
    except ImportError:
        return (None, None)
    try:
        enc = tiktoken.get_encoding(encoding)
    except Exception:  # unknown encoding name, or no cached BPE file offline
        return (None, None)
    return (len(enc.encode(text)), f"tiktoken/{encoding}")


def measure(label: str, text: str, encoding: str = DEFAULT_ENCODING) -> SizeReport:
    """Size of one candidate context block."""
    tokens, tokenizer = count_tokens(text, encoding)
    return SizeReport(
        label=label,
        chars=len(text),
        lines=text.count("\n") + 1 if text else 0,
        tokens=tokens,
        tokenizer=tokenizer,
    )


__all__ = ["DEFAULT_ENCODING", "SizeReport", "count_tokens", "measure"]
