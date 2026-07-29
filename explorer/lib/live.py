"""Live modes — play and watch a real game, through the existing harness. The app *calls*
harness code (ArcEnv, LLMPolicy, run_episode); it never edits or forks it, so what you
watch is the actual agent, not a demo mock (separation contract, notes/07).

Three things live here:
  - key_status(): which keys exist, so the UI can gate the buttons (no key value crosses).
  - you-play: start / act / close a game the human drives. Works against the real server
    (ARC key only — no LLM quota) or against the offline MockGame (no key at all).
  - watch-agent: run a real LLM agent and stream observe→decide→act→score. Survives a
    free-tier 429 the same way the harness does — the LLMPolicy catches it and falls back,
    so the stream shows an amber "fell back" step instead of crashing.

The offline core imports none of this; a missing or dead key can only disable a button.
"""

from __future__ import annotations

import threading
import time
import uuid

from arc_agi_3._structs import GameAction, GameState

from harness.actions import Action
from harness.env_file import read_env_key
from harness.frames import diff_grids, main_grid
from harness.loop import run_episode
from harness.mock_game import MockGame
from harness.policies import LLMPolicy, legal_actions

import build_demo  # reuse the palette + reason-cleaning the demo already proved

PALETTE = build_demo.PALETTE


# --- the key gate -------------------------------------------------------------------------

def key_status() -> dict:
    arc = read_env_key("ARC_API_KEY", required=False)
    llm = read_env_key("GEMINI_API_KEY", "GOOGLE_API_KEY", required=False)
    return {
        "arc": bool(arc),
        "llm": bool(llm),
        "you_play_enabled": bool(arc),
        "watch_agent_enabled": bool(arc and llm),
        "howto": {
            "arc": "notes/howto/01-get-your-arc-api-key.md",
            "llm": "notes/howto/02-get-a-free-llm-api-key.md",
        },
    }


# --- shared frame encoding (same scheme as the offline replay) ---------------------------

def _encode_frame(frame) -> dict:
    grid = main_grid(frame)
    h = len(grid)
    w = len(grid[0]) if h else 0
    hexstr = "".join(format(min(max(v, 0), 15), "x") for row in grid for v in row)
    return {"grid": hexstr, "w": w, "h": h}


def _legal(frame) -> list[dict]:
    return [{"name": a.name, "complex": a.is_complex()}
            for a in legal_actions(frame) if a is not GameAction.RESET]


def _resolve_game(env, wanted: str) -> str:
    games = env.list_games()
    if wanted in games:
        return wanted
    matches = [g for g in games if g.startswith(wanted)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ValueError(f"no game id starts with {wanted!r}; server offers: {games}")
    raise ValueError(f"{wanted!r} is ambiguous: {matches}")


# --- you-play: human-driven sessions -----------------------------------------------------

_SESSIONS: dict[str, "_Session"] = {}
_LOCK = threading.Lock()


class _Session:
    def __init__(self, env, mock: bool, game_id: str, url: str | None) -> None:
        self.env = env
        self.mock = mock
        self.game_id = game_id
        self.scorecard_url = url
        self.last = None
        self.created = time.time()


def start_play(game: str = "ls20", mock: bool = False) -> dict:
    if mock:
        env = MockGame()
        game_id, url = env.game_id, None
    else:
        from harness.arc_env import ArcEnv
        env = ArcEnv(game, tags=["project-agent", "explorer", "you-play"])
        game_id = _resolve_game(env, game)
        env.game_id = game_id
        env.open_scorecard()
        url = env.scorecard_url
    frame = env.reset()
    sid = uuid.uuid4().hex
    s = _Session(env, mock, game_id, url)
    s.last = frame
    with _LOCK:
        _SESSIONS[sid] = s
    return {
        "session_id": sid, "game_id": game_id, "mock": mock, "scorecard_url": url,
        "palette": PALETTE, "frame": _encode_frame(frame), "score": frame.score,
        "state": frame.state.value, "legal": _legal(frame),
        "done": frame.state is GameState.WIN,
    }


def play_action(session_id: str, action_name: str, x=None, y=None) -> dict:
    with _LOCK:
        s = _SESSIONS.get(session_id)
    if s is None:
        raise KeyError("no such session (it may have ended) — start a new game")
    prev = s.last
    try:
        kind = GameAction[action_name]
    except KeyError:
        raise ValueError(f"unknown action {action_name!r}")
    if kind not in set(legal_actions(prev)):
        raise ValueError(f"{action_name} is not available on this frame")
    if kind.is_complex():
        if x is None or y is None:
            raise ValueError("this action is a click — send x and y")
        act = Action(kind, x=int(x), y=int(y), reasoning="you (human)")
    else:
        act = Action(kind, reasoning="you (human)")
    frame = s.env.step(act)
    s.last = frame
    try:
        changed = diff_grids(main_grid(prev), main_grid(frame)).count
    except ValueError:
        changed = -1
    return {
        "frame": _encode_frame(frame), "score": frame.score,
        "dscore": frame.score - prev.score, "changed": changed,
        "state": frame.state.value, "legal": _legal(frame),
        "done": frame.state is GameState.WIN, "action": act.label(),
    }


def close_play(session_id: str) -> dict:
    with _LOCK:
        s = _SESSIONS.pop(session_id, None)
    if s is None:
        return {"ok": False, "note": "no such session"}
    out: dict = {"ok": True, "mock": s.mock}
    if not s.mock:
        card = None
        try:
            card = s.env.card(s.game_id)
        except Exception:
            pass
        try:
            closed = s.env.close_scorecard()
            out["scorecard"] = closed or card
        except Exception as exc:
            out["scorecard"] = card
            out["note"] = f"could not close scorecard: {exc}"
    if hasattr(s.env, "close"):
        try:
            s.env.close()
        except Exception:
            pass
    return out


# --- watch-agent: stream a real LLM run --------------------------------------------------

class _StreamingEnv:
    """Delegates to the real env, remembering the latest frame so the tracer can attach the
    screen to each step event. Emits the opening frame itself."""

    def __init__(self, inner, emit) -> None:
        self.inner = inner
        self.game_id = inner.game_id
        self.emit = emit
        self.last = None

    def reset(self):
        f = self.inner.reset()
        self.last = f
        self.emit({"type": "start", "frame": _encode_frame(f), "score": f.score,
                   "state": f.state.value, "legal": _legal(f)})
        return f

    def step(self, action):
        f = self.inner.step(action)
        self.last = f
        return f


class _StreamTracer:
    """Satisfies the tracer duck-type run_episode uses (.write). Turns each step record into
    a streamed event, merging in the current screen and cleaning the model's reasoning."""

    def __init__(self, env, emit) -> None:
        self.env = env
        self.emit = emit

    def write(self, kind: str, **fields) -> None:
        if kind != "step":
            return
        reason, err = build_demo.clean_reason(fields.get("reasoning", ""), fields.get("action", ""))
        f = self.env.last
        self.emit({
            "type": "step", "index": fields.get("index"), "action": fields.get("action"),
            "accepted": fields.get("accepted"), "score": fields.get("score"),
            "dscore": fields.get("score_delta"), "changed": fields.get("cells_changed"),
            "state": fields.get("state"), "legal_options": fields.get("legal_options"),
            "reason": reason, "err": err, "note": fields.get("note", ""),
            "frame": _encode_frame(f) if f is not None else None,
        })


def watch_stream(game: str, max_actions: int, emit) -> None:
    """Run one real agent game, calling emit(event) as each thing happens. Blocking — the
    caller (the SSE handler) runs this in its own request thread. Always attempts to close
    the scorecard, even on error or client disconnect."""
    from harness.arc_env import ArcApiError, ArcEnv
    from harness.frames import render_objects
    from harness.llm import GeminiClient

    env = None
    url = None
    try:
        env = ArcEnv(game, tags=["project-agent", "explorer", "watch-agent"])
        game_id = _resolve_game(env, game)
        env.game_id = game_id
        env.open_scorecard()
        url = env.scorecard_url
        emit({"type": "info", "game_id": game_id, "scorecard_url": url,
              "max_actions": max_actions, "palette": PALETTE})

        client = GeminiClient(model="gemini-3.5-flash-lite")
        policy = LLMPolicy(
            client,
            encoder=lambda f: render_objects(main_grid(f)),
            name="llm:gemini-3.5-flash-lite:objects",
            repeat_limit=3,
        )
        stream_env = _StreamingEnv(env, emit)
        tracer = _StreamTracer(stream_env, emit)
        result = run_episode(stream_env, policy, max_actions=max_actions, tracer=tracer)

        card = None
        try:
            card = env.card(game_id)
        except Exception:
            pass
        try:
            closed = env.close_scorecard()
        except Exception:
            closed = None
        emit({"type": "end", "final_score": result.final_score,
              "final_state": result.final_state, "stopped_because": result.stopped_because,
              "actions": result.actions_taken, "llm_calls": policy.calls,
              "client_errors": policy.client_errors, "parse_failures": policy.parse_failures,
              "scorecard": closed or card, "scorecard_url": url})
    except ArcApiError as exc:
        emit({"type": "error", "message": f"ARC server: {exc}"})
    except Exception as exc:
        emit({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
    finally:
        if env is not None:
            try:
                if getattr(env, "card_id", None):
                    env.close_scorecard()
            except Exception:
                pass
            try:
                env.close()
            except Exception:
                pass


__all__ = ["key_status", "start_play", "play_action", "close_play", "watch_stream", "PALETTE"]
