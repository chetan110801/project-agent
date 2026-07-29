# Explorer — the local, offline dashboard for project-agent

A small full-stack app that lets you **see the whole project working end-to-end**: browse
and replay every recorded game, read the evals, the failure taxonomy, the traces and the
budgets — all from files already in the repo, with **no API key and no network**. On top of
that, two optional, gated **live** modes let you play a real game yourself or watch a real
agent play.

This app is a **viewer on top of the harness**, not part of it. It only ever *reads* the
repo (`runs/`, `artifacts/`, `notes/`) and *calls* the harness (for live play); it never
edits `harness/`, `scripts/`, or `tests/`. The harness stays the deliverable; this is how
you look at it. (Design: [`../notes/07-explorer-app-spec.md`](../notes/07-explorer-app-spec.md).)

## Run it (one command)

```powershell
py explorer/app.py
```

That serves <http://localhost:8000> and opens your browser. No install step — it uses only
the Python standard library. (`explorer\run.bat` does the same by double-click.)

```powershell
py explorer/app.py --port 8001 --no-browser   # options
py explorer/smoke_test.py                       # its own offline self-check
```

## What you get

| Tab | Shows |
|---|---|
| **Home** | The honest headline (the wall), the four experiments, jump-links |
| **Replay** | Any recorded game, move by move: screen + action + the model's own reason + score. Side-by-side compare (LLM vs random on the same game) and a "jump to where it got stuck" control |
| **Evals** | Every arm's metrics tagged steering / outcome / cost, and the before/after comparisons |
| **Taxonomy** | The six failure buckets as a chart — 88% active-but-no-progress, 0% progress |
| **Traces** | One run's raw decision records — the receipts the evals and taxonomy read |
| **Budgets** | Tokens · requests/day · latency, and the model bakeoff (fastest ≠ usable) |
| **Live** | *Optional.* Play a real game (ARC key), or a no-key mock; or watch a real agent play (ARC + LLM keys). Gated: no key → the button is disabled, never broken |

Flip the **Learn ↔ Demo** switch (top-right): **Learn** adds a plain-language explainer and
the matching study note to every view; **Demo** is clean for showing someone.

## Live modes — the honest caveats

- **You play** needs only an `ARC_API_KEY` in `.env` (no LLM quota). A **no-key mock** works
  anywhere and is clearly labelled as not-the-real-server.
- **Watch the agent** needs an LLM key too and spends real free-tier quota (500 requests/day);
  the action budget is capped low on purpose. A `429` mid-run degrades to an amber
  "fell back" step — the same way the harness does — it does not crash.
- Keys are read from the untracked `.env`; only *whether* a key exists is ever sent to the
  page, never its value. Rotate the ARC key before relying on live play (see the project's
  security note).

## How it's built

- **Backend:** `explorer/app.py` — Python's stdlib `http.server`. Read-only JSON API + static
  files. Chosen over FastAPI so there is **nothing to install** — the reliability call for a
  laptop the owner won't maintain. Data readers in `explorer/lib/`.
- **Frontend:** `explorer/static/` — plain ES-module JavaScript, **no build step, no Node**.
- Rendering (16-colour palette, grid decode, reason-cleaning) is reused from the repo's
  `build_demo.py`, not reinvented.
