"""The receipts: one JSON object per line, per decision.

A trace answers "why did it do that?" after the fact. The format is JSONL (one JSON
object per line) for one reason: it is append-only and survives a crash. A run that dies
on action 57 still leaves 56 readable records; a single JSON array would leave an
unparseable file.

Nothing here is clever. The discipline is that *every* decision goes through it, so the
eval suite and the failure taxonomy read the same source of truth the agent acted on.
"""

from __future__ import annotations

import gzip
import io
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def open_jsonl(path: str | Path, mode: str = "r") -> io.TextIOBase:
    """Open a `.jsonl` or a `.jsonl.gz`, transparently, as text.

    Recordings are enormous and almost entirely repetition — a 400-action run is a 5.8 MB
    file of 64x64 grids that mostly resemble each other. Measured on that exact file:
    **gzip takes it to 46 KB, a factor of 126.** Since every experiment from Phase C on
    produces one recording per game per arm, uncompressed recordings would add ~15 MB per
    experiment to a repository whose entire point is that the evidence is committed
    alongside the claims.

    Both extensions are readable forever, so recordings written before this existed keep
    working and no analysis has to be re-run to prove that nothing changed.

    ::warning:: **A gzip file being appended to cannot be read back until it is closed.**
    Measured: `Tracer.read` on a half-written `.jsonl` returns every record so far; on a
    half-written `.jsonl.gz` it raises `EOFError: Compressed file ended before the
    end-of-stream marker was reached`, because `flush()` does not emit a complete gzip
    member. Mid-run readability is precisely the property JSONL was chosen for — a run that
    dies on action 57 must still leave 56 readable records — so anything written *live*
    stays plain, and compression happens when the file is closed (`RecordingEnv.close`).
    """
    path = Path(path)
    if path.suffix == ".gz":
        return gzip.open(path, mode + "t", encoding="utf-8", newline="")
    return path.open(mode, encoding="utf-8")


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
        self._fh = open_jsonl(self.path, "a")
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
        with open_jsonl(path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out


__all__ = ["Tracer", "open_jsonl"]
