"""Learn mode: the short "what is this?" blurb each view carries, plus safe reading of a
study note so the app can open the full write-up in a modal. Using the app then teaches
the project — the reason Learn mode exists (spec notes/07, decision 2026-07-29).

Every blurb is a plain-language gist of the note it links to; the note itself is the
source of truth, one click away.
"""

from __future__ import annotations

from . import repo

# view id -> {blurb, notes:[{title, file}]}. `file` is a repo-relative path served raw.
LEARN: dict[str, dict] = {
    "home": {
        "blurb": (
            "This project is an LLM agent that plays ARC-AGI-3 — games with no instructions "
            "and no stated goal. The point is not the score; it is the engineering harness "
            "around the agent, and one honestly-reported result: it never beats the game."
        ),
        "notes": [
            {"title": "01 — What we are building", "file": "notes/study/01-what-we-are-building.md"},
            {"title": "13 — The interview story", "file": "notes/study/13-the-interview-story.md"},
        ],
    },
    "replay": {
        "blurb": (
            "One recorded game, replayed move by move. Each move is one turn of the agent "
            "loop: observe the screen, decide an action (with a stated reason), act, get a "
            "new screen and score. Watch the screen keep changing while the score stays at "
            "zero — that is the wall, made visible."
        ),
        "notes": [
            {"title": "05 — The agent loop", "file": "notes/study/05-the-agent-loop.md"},
            {"title": "06 — Context engineering", "file": "notes/study/06-context-engineering.md"},
            {"title": "09 — Exploration & the signal that cannot exist",
             "file": "notes/study/09-exploration-and-the-signal-that-cannot-exist.md"},
        ],
    },
    "evals": {
        "blurb": (
            "Evals are the regression suite for the agent: a fixed set of games, run on "
            "every change, scored on metrics tagged steering / outcome / cost. A change is "
            "only kept if the before/after numbers justify it — never on vibes. Held-out "
            "games are touched only for reported results, never for tuning."
        ),
        "notes": [
            {"title": "07 — Baselines & controlled experiments",
             "file": "notes/study/07-baselines-and-controlled-experiments.md"},
            {"title": "08 — Evals", "file": "notes/study/08-evals.md"},
        ],
    },
    "taxonomy": {
        "blurb": (
            "The failure taxonomy sorts every recorded action into one of six buckets, by "
            "priority. The headline: ~88% of the agent's moves are active-but-no-progress — "
            "legal, non-repeating, screen-changing work that gets nowhere — and 0% make "
            "progress. That single table is the wall, counted."
        ),
        "notes": [
            {"title": "10 — Traces & the failure taxonomy",
             "file": "notes/study/10-traces-and-the-failure-taxonomy.md"},
        ],
    },
    "traces": {
        "blurb": (
            "A trace is one append-only JSONL record per decision — the receipts. It stores "
            "what the agent saw, the action it chose, the model's own reason, whether the "
            "action was legal, cells changed, score and latency. The evals and the taxonomy "
            "are both computed from exactly these files, so 'why did it do that?' has an answer."
        ),
        "notes": [
            {"title": "10 — Traces & the failure taxonomy",
             "file": "notes/study/10-traces-and-the-failure-taxonomy.md"},
        ],
    },
    "budgets": {
        "blurb": (
            "Three budgets you actually spend on a free tier: tokens per call, requests per "
            "day (the 500/day LLM cap this project keeps hitting), and latency. The bakeoff "
            "showed the fastest model on paper was the wrong one — it timed out on real "
            "prompts. A pre-flight check refuses an arm that would die half-run."
        ),
        "notes": [
            {"title": "12 — Budgets: tokens, cost, latency",
             "file": "notes/study/12-budgets-tokens-cost-latency.md"},
        ],
    },
    "live": {
        "blurb": (
            "The live modes talk to the real ARC-AGI-3 game server through the same harness "
            "the offline runs used. 'You play' needs only an ARC key (no LLM quota burned). "
            "'Watch the agent' needs an LLM key too and carries real free-tier 429 risk — it "
            "degrades the same way the harness does, rather than crashing."
        ),
        "notes": [
            {"title": "04 — ARC-AGI-3, the game", "file": "notes/study/04-arc-agi-3-the-game.md"},
            {"title": "05 — The agent loop", "file": "notes/study/05-the-agent-loop.md"},
        ],
    },
}


def learn_index() -> dict:
    return LEARN


def get_note_markdown(rel_path: str) -> str | None:
    """Serve a note's raw markdown, refusing anything outside notes/."""
    if ".." in rel_path or rel_path.startswith(("/", "\\")):
        return None
    path = (repo.ROOT / rel_path).resolve()
    try:
        path.relative_to(repo.NOTES.resolve())
    except ValueError:
        return None
    if not path.exists() or path.suffix != ".md":
        return None
    return path.read_text(encoding="utf-8")


__all__ = ["learn_index", "get_note_markdown", "LEARN"]
