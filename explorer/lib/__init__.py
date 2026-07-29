"""Explorer app internals. Everything the local dashboard needs to read the repo.

This package is a *viewer* on top of the harness. It reads the files the harness and
scripts already wrote (runs/, artifacts/) and never edits harness/, scripts/ or tests/.
See notes/07-explorer-app-spec.md and the 2026-07-29 DECISIONS entry.
"""
