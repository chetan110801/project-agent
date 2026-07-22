"""The real ARC-AGI-3 API, behind the same `Environment` protocol as the mock game.

VERIFIED against the live server on 2026-07-22: two full 80- and 400-action games of
`ls20` were played through this file end to end, scorecards opened and closed
(`artifacts/ourloop-random-run.json`, `artifacts/ourloop-random-400.json`). The endpoints
below are no longer read-from-source guesses; they are observed. One of them turned out
*not* to match the SDK's schema — see `close_scorecard`.

This is the piece that lets our loop (`harness/loop.py`) play a real game without
inheriting from the SDK's `Agent`. We keep the SDK's *data types* — `FrameData` validates
every response, so the server's contract is enforced by the vendor's own schema — and
replace only its transport and its loop.

The protocol, read out of the SDK source (`_agent.py`, `_swarm.py`, v0.0.1) and then
confirmed request by request against the live server on 2026-07-22:

    GET  /api/games                        -> [{"game_id": ...}, ...]
    POST /api/scorecard/open   {tags}      -> {"card_id": ...}
    POST /api/cmd/RESET        {game_id, card_id[, guid]}  -> FrameData
    POST /api/cmd/ACTION1..7   {game_id, guid[, x, y][, reasoning]} -> FrameData
    GET  /api/scorecard/{card_id}/{game_id}                -> Scorecard
    POST /api/scorecard/close  {card_id}                   -> Scorecard

Auth is the `X-API-Key` header. The key is read from the environment, or from a `.env`
file in the current directory — never passed on a command line, where it would land in
shell history.
"""

from __future__ import annotations

from typing import Any

import requests
from arc_agi_3._structs import FrameData, GameAction

from .actions import Action
from .env_file import MissingKey, read_env_key

DEFAULT_ROOT = "https://three.arcprize.org"
TIMEOUT = 30


class ArcApiError(RuntimeError):
    """The server refused something. Carries the status and body so a trace can show why."""


def load_api_key(explicit: str | None = None) -> str:
    """ARC_API_KEY from the argument, the environment, or ./.env — in that order.

    The reading itself lives in `harness/env_file.py`, along with the Windows byte-order-mark
    trap that made this project's first live run return 401 twice.
    """
    try:
        key = read_env_key("ARC_API_KEY", explicit=explicit)
    except MissingKey as exc:
        raise ArcApiError(str(exc)) from exc
    assert key is not None  # required=True guarantees this
    return key


class ArcEnv:
    """One game, played over the real API. Satisfies `harness.loop.Environment`."""

    def __init__(
        self,
        game_id: str,
        api_key: str | None = None,
        root_url: str = DEFAULT_ROOT,
        card_id: str | None = None,
        tags: list[str] | None = None,
    ) -> None:
        self.game_id = game_id
        self.root_url = root_url.rstrip("/")
        self.tags = tags or []
        self.guid: str = ""
        self.card_id = card_id
        self._owns_card = card_id is None
        self._session = requests.Session()
        self._session.headers.update(
            {"X-API-Key": load_api_key(api_key), "Accept": "application/json"}
        )

    # -- plumbing ---------------------------------------------------------- #
    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        r = self._session.post(f"{self.root_url}{path}", json=payload, timeout=TIMEOUT)
        if not r.ok:
            raise ArcApiError(f"POST {path} -> {r.status_code}: {r.text[:300]}")
        data = r.json()
        if isinstance(data, dict) and "error" in data:
            raise ArcApiError(f"POST {path} -> {data['error']}")
        return data

    def _get(self, path: str) -> Any:
        r = self._session.get(f"{self.root_url}{path}", timeout=TIMEOUT)
        if not r.ok:
            raise ArcApiError(f"GET {path} -> {r.status_code}: {r.text[:300]}")
        return r.json()

    # -- scorecard --------------------------------------------------------- #
    def list_games(self) -> list[str]:
        return [g["game_id"] for g in self._get("/api/games")]

    def open_scorecard(self) -> str:
        """A scorecard groups plays together; the server attaches scores to it."""
        if self.card_id is None:
            self.card_id = str(self._post("/api/scorecard/open", {"tags": self.tags})["card_id"])
        return self.card_id

    def close_scorecard(self) -> dict[str, Any] | None:
        """Close the card and return the server's raw JSON.

        Raw, not `Scorecard`, and that is a measured decision: on 2026-07-22 this endpoint
        answered with

            {"card_id", "environments", "score", "tags", "tags_scores", "total_actions",
             "total_environments", "total_environments_completed", "total_levels",
             "total_levels_completed"}

        The SDK's `Scorecard` model has none of those except `card_id` and `tags`; every
        field has a default, so `model_validate` succeeds and silently hands back an object
        whose `cards` is `{}` and whose `score` is a computed 0. Validating here would
        throw away the only numbers the run is judged on. The vendor's schema does not
        cover the vendor's endpoint, so we keep the JSON and say why.
        """
        if not (self.card_id and self._owns_card):
            return None
        data = self._post("/api/scorecard/close", {"card_id": self.card_id})
        self.card_id = None
        return data

    def scorecard(self) -> dict[str, Any]:
        """The open card's per-game state. **Only works before `close_scorecard`** —
        afterwards the id is gone and this returns 404 (measured 2026-07-22)."""
        if not self.card_id:
            raise ArcApiError("no scorecard is open")
        return self._get(f"/api/scorecard/{self.card_id}/{self.game_id}")

    def card(self, game_id: str | None = None) -> dict[str, Any] | None:
        """This game's card: plays, states, action counts, scores. Fetch before closing.

        Shape (measured): the GET returns `{"cards": {game_id: {...}}, "played", "won",
        "total_actions", "levels_completed"}`. This is the record the SDK's own recorder
        writes as the trailing line of a recording, so ours matches file for file.
        """
        data = self.scorecard()
        return (data.get("cards") or {}).get(game_id or self.game_id)

    @property
    def scorecard_url(self) -> str | None:
        return f"{self.root_url}/scorecards/{self.card_id}" if self.card_id else None

    # -- Environment protocol ---------------------------------------------- #
    def reset(self) -> FrameData:
        self.open_scorecard()
        payload: dict[str, Any] = {"game_id": self.game_id, "card_id": self.card_id}
        if self.guid:
            payload["guid"] = self.guid
        return self._frame(self._post("/api/cmd/RESET", payload))

    def step(self, action: Action) -> FrameData:
        if action.kind is GameAction.RESET:
            return self.reset()
        payload: dict[str, Any] = {"game_id": self.game_id, **action.payload()}
        if self.guid:
            payload["guid"] = self.guid
        if action.reasoning is not None:
            payload["reasoning"] = action.reasoning
        return self._frame(self._post(f"/api/cmd/{action.kind.name}", payload))

    def _frame(self, data: dict[str, Any]) -> FrameData:
        frame = FrameData.model_validate(data)
        if frame.guid:
            self.guid = frame.guid
        return frame

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> ArcEnv:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


__all__ = ["ArcApiError", "ArcEnv", "DEFAULT_ROOT", "load_api_key"]
