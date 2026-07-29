"""Reading the artifacts the scripts wrote: evals, comparisons, the failure taxonomy,
and the three budgets. Every number the app shows comes straight from one of these files
(CLAUDE.md rule 3: no number invented in the app), so the Explorer can only ever repeat
what the harness already measured.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import repo


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_under(base: Path, name: str) -> Path | None:
    """Resolve `name` inside `base`, refusing anything that escapes it."""
    if "/" in name or "\\" in name or ".." in name:
        return None
    path = base / f"{name}.json"
    try:
        path.resolve().relative_to(base.resolve())
    except ValueError:
        return None
    return path if path.exists() else None


# --- evals + comparisons -----------------------------------------------------------------

def list_evals() -> dict:
    """Split artifacts/evals/*.json into single-arm results and before/after comparisons."""
    arms, comparisons = [], []
    if not repo.EVALS.exists():
        return {"arms": arms, "comparisons": comparisons}
    for path in sorted(repo.EVALS.glob("*.json")):
        name = path.stem
        try:
            doc = _read_json(path)
        except Exception:
            continue
        if name.startswith("comparison-"):
            comparisons.append({
                "name": name,
                "before": doc.get("before"),
                "after": doc.get("after"),
                "config_changed": doc.get("config_changed", []),
                "single_variable": doc.get("single_variable"),
            })
        else:
            agg = doc.get("aggregate", {})
            cfg = doc.get("config", {})
            arms.append({
                "arm": doc.get("arm", name),
                "suite": doc.get("suite"),
                "games": doc.get("games", []),
                "policy": cfg.get("policy"),
                "model": cfg.get("model"),
                "final_score": agg.get("final_score"),
                "episodes": agg.get("episodes"),
                "actions": agg.get("actions"),
                "wins": agg.get("wins"),
                "level1_ratio": agg.get("level1_ratio"),
            })
    return {"arms": arms, "comparisons": comparisons}


def get_eval(arm: str) -> dict | None:
    path = _safe_under(repo.EVALS, arm)
    return _read_json(path) if path else None


def get_comparison(name: str) -> dict | None:
    path = _safe_under(repo.EVALS, name)
    return _read_json(path) if path else None


# --- failure taxonomy --------------------------------------------------------------------

def get_taxonomy() -> dict | None:
    path = repo.ARTIFACTS / "failure-taxonomy.json"
    return _read_json(path) if path.exists() else None


# --- budgets: tokens, requests/day, latency, the model bakeoff, the usage log ------------

def _usage_summary() -> dict | None:
    """Summarise artifacts/llm-usage.jsonl (the cross-process daily-quota counter).
    It is gitignored per-machine state, so it may be absent — that's fine."""
    path = repo.ARTIFACTS / "llm-usage.jsonl"
    if not path.exists():
        return None
    total = ok = fail = 0
    by_day: dict[str, int] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            total += 1
            if rec.get("ok"):
                ok += 1
            else:
                fail += 1
            day = (rec.get("ts") or "")[:10]
            if day:
                by_day[day] = by_day.get(day, 0) + 1
    return {
        "total": total, "ok": ok, "fail": fail,
        "daily_limit": 500,  # free-tier gemini-3.5-flash-lite RPD (harness/budget.py)
        "by_day": [{"day": d, "calls": c} for d, c in sorted(by_day.items())],
    }


def get_budgets() -> dict:
    out: dict = {}
    for key, fname in (
        ("llm_budget", "llm-budget.json"),
        ("model_bakeoff", "model-bakeoff.json"),
        ("change_sizes", "change-sizes.json"),
        ("encoding_sizes", "encoding-sizes.json"),
        ("tokens_by_tokeniser", "tokens-by-tokeniser.json"),
    ):
        path = repo.ARTIFACTS / fname
        if path.exists():
            try:
                out[key] = _read_json(path)
            except Exception:
                pass
    out["usage"] = _usage_summary()
    return out


# --- home / overview: counts computed live + the taxonomy headline read from its file ----

def get_overview() -> dict:
    from . import runs as runs_lib

    runs = runs_lib.list_runs()
    games = sorted({r.get("game_id") for r in runs if r.get("game_id")})
    evals = list_evals()
    tax = get_taxonomy() or {}
    headline = tax.get("headline_llm_default_now", {})
    buckets = headline.get("buckets", {})

    def share(name: str):
        return buckets.get(name, {}).get("share")

    return {
        "title": "project-agent — an LLM agent for ARC-AGI-3, judged by its harness",
        "headline": {
            "one_liner": (
                "The agent does not beat the game — on the outcome that counts it scores "
                "the same as a random baseline: zero. This project's value is how "
                "thoroughly that negative result is established and what it locates."
            ),
            # numbers below are read live from failure-taxonomy.json, not typed here
            "active_no_progress_share": share("active_no_progress"),
            "progress_share": share("progress"),
            "taxonomy_arm": headline.get("arm"),
            "taxonomy_episodes": headline.get("episodes"),
            "taxonomy_actions": headline.get("actions"),
        },
        "counts": {
            "recorded_runs": len(runs),
            "games": len(games),
            "game_ids": games,
            "eval_arms": len(evals["arms"]),
            "comparisons": len(evals["comparisons"]),
            "runs_with_trace": sum(1 for r in runs if r.get("has_trace")),
        },
        "experiments": [
            {"n": 1, "name": "Memory of its own actions (history window)",
             "result": "Changed behaviour; score unchanged.", "note": "notes/study/06"},
            {"n": 2, "name": "Repetition guard (stuck detection)",
             "result": "Removed perseveration; score unchanged.", "note": "notes/study/09"},
            {"n": 3, "name": "A falsifiable theory of the goal (hypothesis)",
             "result": "Testable goal in the prompt; score unchanged.", "note": "notes/study/09"},
            {"n": 4, "name": "An after-the-fact progress signal (server scorecard)",
             "result": "The one real signal, provably read; score unchanged.", "note": "notes/study/10"},
        ],
    }


__all__ = [
    "list_evals", "get_eval", "get_comparison", "get_taxonomy",
    "get_budgets", "get_overview",
]
