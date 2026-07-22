"""The receipts: one JSON object per line, per decision.

A trace answers "why did it do that?" after the fact. The format is JSONL (one JSON
object per line) for one reason: it is append-only and survives a crash. A run that dies
on action 57 still leaves 56 readable records; a single JSON array would leave an
unparseable file.

Nothing here is clever. The discipline is that *every* decision goes through it, so the
eval suite and the failure taxonomy read the same source of truth the agent acted on.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _plain(obj: Any) -> Any:
    """Best-effort conversion to something json can write."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _plain(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {str(k): _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


class Tracer:
    """Append-only JSONL writer. Use as a context manager, or call close()."""

    def __init__(self, path: str | Path, run_id: str | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self._fh = self.path.open("a", encoding="utf-8")
        self.count = 0

    def write(self, kind: str, **fields: Any) -> None:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "run_id": self.run_id,
            "kind": kind,
            **{k: _plain(v) for k, v in fields.items()},
        }
        self._fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._fh.flush()  # a crash must not cost us the last records
        self.count += 1

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.close()

    def __enter__(self) -> Tracer:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    @staticmethod
    def read(path: str | Path) -> list[dict[str, Any]]:
        """Read a trace back. Bad lines are skipped, not fatal."""
        out: list[dict[str, Any]] = []
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out


__all__ = ["Tracer"]
