"""DRAFT — UNTESTED. Written 2026-07-22, never executed against the live API.

Nothing in this file has made a single real request yet: the session ended before it could
be run. The URL paths, payload shapes and header were read out of the SDK source, not
observed, so treat every one of them as a claim to be checked. First job next session:
run it (`scripts/run_agent.py` does not exist yet either) and delete this banner only
after a real game has been played through it end to end.

The real ARC-AGI-3 API, behind the same `Environment` protocol as the mock game.

This is the piece that lets our loop (`harness/loop.py`) play a real game without
inheriting from the SDK's `Agent`. We keep the SDK's *data types* — `FrameData` validates
every response, so the server's contract is enforced by the vendor's own schema — and
replace only its transport and its loop.

The protocol, read out of the SDK source (`_agent.py`, `_swarm.py`, v0.0.1) and confirmed
against a live run on 2026-07-22:

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

import os
from pathlib import Path
from typing import Any

import requests
from arc_agi_3._structs import FrameData, GameAction, Scorecard

from .actions import Action

DEFAULT_ROOT = "https://three.arcprize.org"
TIMEOUT = 30


class ArcApiError(RuntimeError):
    """The server refused something. Carries the status and body so a trace can show why."""


def load_api_key(explicit: str | None = None) -> str:
    """ARC_API_KEY from the argument, the environment, or ./.env — in that order.

    We parse `.env` ourselves rather than depending on python-dotenv, and we strip a
    leading byte-order mark. That is not defensive programming for its own sake: Windows
    PowerShell 5.1's `Set-Content -Encoding utf8` writes a BOM, which turns the first line
    into a variable literally named `﻿ARC_API_KEY`, and the resulting 401 looks
    exactly like a wrong key. It cost this project two sessions; it is handled here once.
    """
    if explicit:
        return explicit
    key = os.getenv("ARC_API_KEY")
    if key:
        return key
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            line = line.lstrip("﻿").strip()
            if line.startswith("ARC_API_KEY"):
                _, _, value = line.partition("=")
                return value.strip().strip('"').strip("'")
    raise ArcApiError(
        "no ARC_API_KEY found — set the environment variable, or put "
        "'ARC_API_KEY=<key>' in a .env file in this folder"
    )


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

    def close_scorecard(self) -> Scorecard | None:
        if not (self.card_id and self._owns_card):
            return None
        data = self._post("/api/scorecard/close", {"card_id": self.card_id})
        card = Scorecard.model_validate(data)
        self.card_id = None
        return card

    def scorecard(self) -> Scorecard:
        if not self.card_id:
            raise ArcApiError("no scorecard is open")
        return Scorecard.model_validate(
            self._get(f"/api/scorecard/{self.card_id}/{self.game_id}")
        )

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
