# Aborted run — 2026-07-23 sleep-kill (NOT play)

These four files are the remnants of the **first** launch of the Experiment 4 control arm
(`dev-llm-p0`), on 2026-07-23 ~21:51 UTC. The process was killed by the OS when the laptop
slept mid-run, after 40 clean model calls, during `ls20` attempt 2 — note that the `a2`
recording is a plain `.jsonl`, never gzipped, because the process died before `close()`.

They are quarantined here so no report that globs `runs/` for `dev-llm-p0` traces mistakes a
partial, never-finished run for real play (the arm's `artifacts/evals/dev-llm-p0.json` was
never written — a hard OS kill leaves no ERROR episode). The experiment was re-run clean on
2026-07-27; that run is the record. See `notes/DECISIONS.md` (Experiment 4 RESULTS) for the
narrative. Kept, not deleted, as evidence of the incident.
