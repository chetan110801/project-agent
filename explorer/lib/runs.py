"""Reading recorded games: the list of every run, and one run's full replay.

The heavy lifting — decoding a `runs/*.recording.jsonl.gz` into per-move frames, actions,
the model's own reasoning, score and cells-changed — already exists and is trusted in
`build_demo.py`. We import it rather than re-implement it (spec notes/07: "reuse; don't
reinvent"). This module adds only the thin layer the app needs on top: listing runs,
deriving game/role/arm from the filename, and finding where a run visibly got stuck.
"""

from __future__ import annotations

import gzip
import json
from functools import lru_cache
from pathlib import Path

from . import repo

# Reuse the proven building blocks from the repo-root demo builder.
import build_demo  # noqa: E402  (import after repo.py put ROOT on sys.path)

PALETTE = build_demo.PALETTE
load_run = build_demo.load_run  # (path) -> {steps, final_score, n_moves, pct_changed, actions_used}

REC_SUFFIX = ".recording.jsonl.gz"


# --- naming: turn a filename into human-facing facts -------------------------------------

def run_id_from_path(path: Path) -> str:
    """The stable id of a run = its recording filename minus the suffix."""
    return path.name[: -len(REC_SUFFIX)] if path.name.endswith(REC_SUFFIX) else path.stem


def _classify(run_id: str) -> dict:
    """Derive game / role / arm / policy from the recording filename, e.g.
    `ls20-9607627b.eval-dev-llm-h0.llm-gemini-3.5-flash-lite-objects-h0.30.<uuid>`.
    Filenames are dot-separated: game . [arm] . policy . max_actions . [attempt] . uuid
    """
    parts = run_id.split(".")
    game_id = parts[0]
    tokens = set(parts)
    if "random" in tokens or any(p == "random" for p in parts):
        role = "random"
    elif any("llm" in p for p in parts):
        role = "llm"
    else:
        role = "other"
    arm = next((p for p in parts if p.startswith("eval-")), None)
    # the policy token: the one naming the model, or the literal 'random'
    policy = next((p for p in parts if "llm-" in p or p == "random"), None)
    return {"game_id": game_id, "role": role, "arm": arm, "policy": policy}


def trace_path_for(run_id: str) -> Path:
    """Recording and trace share a stem: `<id>.recording.jsonl.gz` / `<id>.trace.jsonl`."""
    return repo.RUNS / f"{run_id}.trace.jsonl"


def _recording_path(run_id: str) -> Path | None:
    """Resolve a run id to its recording file, guarding against path escapes."""
    if "/" in run_id or "\\" in run_id or ".." in run_id:
        return None
    path = repo.RUNS / f"{run_id}{REC_SUFFIX}"
    try:
        path.resolve().relative_to(repo.RUNS.resolve())
    except ValueError:
        return None
    return path if path.exists() else None


# --- light scan: enough to list a run without decoding every cell ------------------------

def _read_frames(path: Path) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        records = [json.loads(line) for line in fh if line.strip()]
    return [r for r in records if "frame" in r.get("data", {})]


def _action_labels(frames: list[dict]) -> list[str]:
    labels = []
    for i, rec in enumerate(frames):
        if i == 0:
            labels.append("START")
            continue
        ai = rec["data"].get("action_input") or {}
        act_id = ai.get("id", 0)
        labels.append(f"ACTION{act_id}" if act_id else "RESET")
    return labels


def longest_streak(labels: list[str]) -> dict | None:
    """Longest run of the same real move (RESET/START excluded). This is the visible
    'stuck' — perseveration — and is what the replay's 'jump to where it got stuck'
    control targets. None if nothing repeats 3+ times."""
    best = None
    i = 0
    n = len(labels)
    while i < n:
        if labels[i] in ("START", "RESET"):
            i += 1
            continue
        j = i
        while j + 1 < n and labels[j + 1] == labels[i]:
            j += 1
        length = j - i + 1
        if length >= 3 and (best is None or length > best["length"]):
            best = {"start_index": i, "length": length, "action": labels[i]}
        i = j + 1
    return best


@lru_cache(maxsize=256)
def _summary_cached(path_str: str, mtime: float) -> dict:
    path = Path(path_str)
    frames = _read_frames(path)
    labels = _action_labels(frames)
    move_idx = [k for k, lbl in enumerate(labels) if lbl not in ("START", "RESET")]
    final_score = frames[-1]["data"].get("score", 0) if frames else 0
    final_state = frames[-1]["data"].get("state", "") if frames else ""
    run_id = run_id_from_path(path)
    info = _classify(run_id)
    return {
        "id": run_id,
        **info,
        "frames": len(frames),
        "n_moves": len(move_idx),
        "final_score": final_score,
        "final_state": final_state,
        "has_trace": trace_path_for(run_id).exists(),
        "stuck": longest_streak(labels),
    }


def run_summary(path: Path) -> dict:
    return _summary_cached(str(path), path.stat().st_mtime)


def list_runs() -> list[dict]:
    """Every recorded game as a light summary, newest first, grouped-friendly by game."""
    out = []
    for path in repo.RUNS.glob(f"*{REC_SUFFIX}"):
        try:
            out.append(run_summary(path))
        except Exception as exc:  # a single corrupt recording must not break the list
            out.append({"id": run_id_from_path(path), "error": str(exc),
                        **_classify(run_id_from_path(path))})
    out.sort(key=lambda r: (r.get("game_id", ""), r.get("role", ""), r.get("id", "")))
    return out


# --- full replay: the payload the player animates ----------------------------------------

@lru_cache(maxsize=64)
def _replay_cached(path_str: str, mtime: float) -> dict:
    path = Path(path_str)
    run_id = run_id_from_path(path)
    data = load_run(path)  # {steps, final_score, n_moves, pct_changed, actions_used}
    labels = [s["action"] for s in data["steps"]]
    return {
        "id": run_id,
        **_classify(run_id),
        "has_trace": trace_path_for(run_id).exists(),
        "stuck": longest_streak(labels),
        **data,
    }


def get_replay(run_id: str) -> dict | None:
    path = _recording_path(run_id)
    if path is None:
        return None
    return _replay_cached(str(path), path.stat().st_mtime)


# --- one run's trace (the raw decision receipts) -----------------------------------------

def get_trace(run_id: str) -> list[dict] | None:
    if "/" in run_id or "\\" in run_id or ".." in run_id:
        return None
    path = trace_path_for(run_id)
    try:
        path.resolve().relative_to(repo.RUNS.resolve())
    except ValueError:
        return None
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


__all__ = [
    "PALETTE", "list_runs", "get_replay", "get_trace",
    "run_id_from_path", "longest_streak",
]
