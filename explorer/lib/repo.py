"""Where the repo is, and one-time wiring so we can reuse code that lives at its root.

The Explorer never copies data. Every path here points at a file the harness or a script
already produced; the app opens it read-only on request.
"""

from __future__ import annotations

import sys
from pathlib import Path

# explorer/lib/repo.py -> explorer/lib -> explorer -> <repo root>
ROOT = Path(__file__).resolve().parents[2]

RUNS = ROOT / "runs"
ARTIFACTS = ROOT / "artifacts"
EVALS = ARTIFACTS / "evals"
NOTES = ROOT / "notes"
STUDY = NOTES / "study"

# Put the repo root on the import path so we can reuse the proven rendering logic in
# build_demo.py (palette, reason-cleaning, per-run replay) instead of reinventing it.
# build_demo guards its work behind `if __name__ == "__main__"`, so importing it is inert.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

__all__ = ["ROOT", "RUNS", "ARTIFACTS", "EVALS", "NOTES", "STUDY"]
