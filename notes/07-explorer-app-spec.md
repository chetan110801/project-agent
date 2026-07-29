# notes/07 — Explorer app spec (the local, offline project dashboard)

**Status: BUILT 2026-07-29 (new session), to this spec.** The app lives in `explorer/`;
run it with `py explorer/app.py`. Offline core (six views + Learn/Demo toggle) and both
gated live modes (you-play, watch-agent) are done and verified offline; see the
2026-07-29 "built" entry in `notes/DECISIONS.md` for exactly what was verified and the one
thing left to the user (real-server live play, which needs the still-unrotated ARC key).
The brief below is kept as the record of what was asked for. Decided 2026-07-29.

---

## Why this exists (one paragraph)

The project is real and tested, but you can only *read about* it (the course) or *run it
in a terminal* (the scripts). Chetan asked for a **local full-stack app that shows the
whole project working end-to-end**, both to demo it and to **understand it in depth by
exploring it**. A single-file replay (`demo.html`, built 2026-07-29 as the proof of
concept) showed the idea works; this app is the full version.

## Governance (read before building — CLAUDE.md §2)

This app is a **scope addition**, agreed by Chetan in-session on 2026-07-29 and recorded
in `notes/DECISIONS.md`. It is a **presentation / understanding layer that sits on top of
the harness**. It does **not** supersede the locked identity of the project: *the harness
is the deliverable that gets judged; the app is a viewer on top of it.* Keep them cleanly
separated (see "Separation contract").

## Locked decisions (from the 2026-07-29 session — do not re-litigate)

1. **Offline core + optional live modes.** The **default experience is fully offline** —
   reads existing files in `runs/` and `artifacts/`, no keys, no network, and cannot fail
   in an interview. On top of that, **optional real-time modes** (added at Chetan's
   request 2026-07-29) let him *play and watch the game end-to-end live*. These need API
   keys + network and are **clearly gated and labelled**, so the always-works offline core
   is never at their mercy. See "Live modes (optional)".
2. **Learn ↔ Demo toggle.** One switch in the header:
   - **Learn mode** — each view carries a short "what is this?" overlay linking to the
     matching study note / concept, so *using the app teaches the project*.
   - **Demo mode** — overlays off; clean and minimal for showing an interviewer.
3. **Separate folder `explorer/`.** All app code lives there. Chetan will not read it and
   does not need to understand it — so it must be *reliable and one-command to run*, not
   clever.
4. **Free + local + Windows.** Must start with essentially one command on Chetan's
   Windows laptop. No paid infra, no cloud, no account.

## What it shows (the views) — each tagged with its study note for Learn mode

| View | What it shows | Data source | Learn-mode links to |
|---|---|---|---|
| **Home / overview** | The project at a glance: the headline (the wall), the four experiments, jump-links to each view | `README.md` facts, `artifacts/` | notes/13 (story), 01 |
| **Game replay** | Pick any recorded game; step/play through it; screen + action + the model's own reasoning + score + cells-changed; **side-by-side compare** (LLM vs random on the same game); a "jump to where it got stuck" control | `runs/*.recording.jsonl.gz` | notes/05 (loop), 06 (context), 09 (exploration) |
| **Evals** | The dev / held-out / reserve split; arm-vs-arm comparison; per-game metrics tagged steering / outcome / cost; before/after for a change | `artifacts/evals/`, `artifacts/comparison.json` | notes/07 (baselines), 08 (evals) |
| **Failure taxonomy** | The six buckets as a chart; the **88% active-but-no-progress / 0% progress** headline; validated against the stuck run | `artifacts/failure-taxonomy.json` | notes/10 (traces & taxonomy) |
| **Traces** | Browse one run's raw decision records (the receipts) — the same JSONL the eval + taxonomy read | `runs/*.trace.jsonl` | notes/10 |
| **Budgets** | Tokens / requests-per-day / latency; the model bakeoff (fastest ≠ best); the daily-quota usage log | `artifacts/*budget*.json`, `artifacts/llm-usage.jsonl`, `model-bakeoff.json` | notes/12 (budgets) |

The **grid-render + 16-colour palette + reason-cleaning logic** already exist in
`build_demo.py` — reuse them; don't reinvent.

## Live modes (optional) — "play and check end-to-end in real time"

Added 2026-07-29. These are **opt-in**, behind a clear button, and **never block the
offline core**. Both talk to the **real ARC-AGI-3 game server** (`arcprize.org`) through
the existing `arc-agi-3` SDK / `harness` code — the app *calls* the harness, it does not
reimplement or change it.

| Mode | What it does | Needs | Free-tier risk |
|---|---|---|---|
| **You play** | Chetan drives a real game live through the UI — click an action, the real server returns the next frame + score. Feels the exact task the agent faces. | ARC key only (`.env`), network | **Low** — no LLM calls, so the 500/day LLM quota is untouched; ARC limit is 600 RPM |
| **Watch the agent play** | Triggers a real agent run (`harness/loop.py` + an LLM policy) and streams observe→decide→act→score as it happens. | ARC **+** LLM keys, network | **Real** — the free LLM is 500 requests/day and *has* hit `429` mid-run; must degrade gracefully, not crash |

Rules for the live modes:
- **Gate them clearly.** If no key is present in `.env`, the buttons are visibly disabled
  with a one-line "add your key (see `notes/howto/`)" hint — never a crash or a blank page.
- **Watch-the-agent must survive a `429`** the same way the harness does: show the amber
  "model call failed — free-tier quota; fell back" state (the `demo.html` pattern), keep
  the partial run, don't lose the frames already streamed.
- **Reuse, don't fork.** Live runs go through the existing loop/policies/SDK so what you
  watch is the *actual* agent, not a demo mock. The app depends on `harness/`; `harness/`
  must not gain any dependency on the app.
- **Key dependency / security.** The live modes read the ARC (and, for agent-play, LLM)
  keys from the untracked `.env`. Note the still-open action item to **rotate the leaked
  `ARC_API_KEY`** (memory `security-key-rotation`) before relying on live play — a live
  demo is exactly where a dead/blocked key would embarrass.

## Recommended architecture (minimal-friction; the builder may refine but keep the spirit)

- **Backend:** Python **FastAPI** + `uvicorn` — matches the repo's Python stack, free,
  serves both JSON endpoints (list runs, get a run's frames/trace, get eval/taxonomy/
  budget JSON) and the static frontend. Reads the repo files directly; copies nothing.
- **Frontend:** **no-build** (vanilla JS modules, or Preact + htm vendored as a local
  file) so **Node/npm is not required** — this is the reliability call for a Windows
  laptop the owner won't maintain. A framework with a build step is allowed only if a
  single documented command still starts everything.
- **Start:** `py explorer/app.py` (or a `run.bat`) → serves on `http://localhost:8000`
  and opens the browser. One step.
- Endpoints read files lazily; large recordings are streamed/decompressed on request, not
  all baked into one page (that was the single-file demo's limitation).
- **Live modes** stream in real time via **SSE or WebSocket** (frame → decision → score
  as each step happens). Keys come from the untracked `.env` (never hard-coded, never
  committed — CLAUDE.md §7). If `.env` has no key, the live buttons are disabled, not
  broken.

## Explicitly OUT of scope

Auth/login · a database · deployment/hosting or any cloud · paid infra of any kind · any
*change* to `harness/`, `scripts/`, or `tests/` (the app may **call** them, never edit
them). Note: live agent/human play is **in** scope now (see "Live modes") but stays
optional, gated, and free-tier only.

## Separation contract (so the harness stays the clean deliverable)

- All app code under `explorer/`. Nothing else in the repo changes to accommodate it.
- The **154-test harness suite does not cover the app** and is not expected to. The app
  may have its own light smoke check inside `explorer/`.
- `README.md` gets **one line** pointing at the app as an optional way to explore — the
  harness remains the headline.
- If the app ever needs a harness change to work, that's a signal the boundary is wrong —
  stop and reconsider, don't bend the harness.

## Handoff checklist for the new session

1. Read this spec + the newest `notes/DECISIONS.md` entry (2026-07-29) + `MEMORY.md`.
2. Confirm the locked product choices still hold (offline **core** + optional gated live
   modes; learn+demo toggle).
3. Scaffold `explorer/` (backend + no-build frontend), reusing `build_demo.py` logic.
4. Build the six offline views; wire the Learn/Demo toggle. **Ship and verify the offline
   core first** — it must be complete and reliable before any live code is added.
5. Then add the two live modes (you-play, watch-agent) behind clear gates, streaming via
   SSE/WebSocket, degrading gracefully with no key and on a `429`.
6. Verify: starts with one command; every offline view loads from real repo data with no
   network; live buttons disable cleanly when `.env` has no key; a real you-play round
   works against the game server.
7. Add the one-line pointer to `README.md`; record a short "built" entry in DECISIONS;
   update memory; commit + push.
