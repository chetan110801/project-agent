# Study note 3 — The project, take two: an agent you can trust, on ARC-AGI-3

*Written 2026-07-21, evening — the day the project pivoted. Supersedes the plan in
note 01; the DECISIONS.md evening entry records why. Plain language, as always.*

---

## What we are building, in one paragraph

An **LLM-driven agent that plays ARC-AGI-3 games** — worlds with no instructions, no
stated goal, where the agent must figure out the rules by acting — wrapped in the
**engineering harness that makes an agent trustworthy**: a hand-built loop, an eval
suite that runs on every change, traces of every decision, reliability guards, and a
token/cost budget it must live inside. The score matters less than the harness: the
interview artifact is *"here is how I measure, debug, and improve an agent — and every
claim, you can re-run."* Free tiers only; no GPU training anywhere.

---

## Why this covers what interviews actually ask (checked 2026-07-21)

2026 AI-engineering interviews concentrate on five areas. Each maps to a layer of this
one project — that mapping *is* the design:

| What interviews probe | Where it lives in this project |
|---|---|
| **LLM fundamentals** — tokens, tokenization, context windows, sampling/temperature | Study notes wired to real code: we count every token the agent spends, watch truncation break it, and tune sampling for planning vs. acting |
| **Context engineering** — what goes in the window, compression, prompt structure | The heart of the loop: each step decides what the model sees — observations, memory summaries, hypotheses. Measured, not vibed: context changes go through the eval suite |
| **Agent design & failure modes** — loops, tools, memory, stuck states | The agent loop built from first principles (observe → hypothesize → plan → act → reflect), plus a failure taxonomy from real traces, bucketed and counted |
| **Evals** — golden sets, LLM-as-judge, regression gates | A fixed suite of games + per-game metrics (score, actions-to-first-progress, tokens spent). Every change ships with before/after numbers; regressions block the merge |
| **Production ops** — tracing, cost/latency budgets, caching, model routing | Every LLM call traced (inputs, outputs, tokens, cost, latency). Per-game token budget. Cheap-model-first routing with escalation; caching of repeated world-queries |
| **Retrieval/embeddings** (the honest RAG angle) | The agent's long-term memory: embedding-based retrieval over its *own past experience* — same concepts as RAG (chunking, similarity search, retrieval quality) without building a tutorial doc-bot |

Sources: 2026 interview guides and real-interview compilations (UPenn career services,
Interview Coder, KORE1, 100+-interview Medium compilation), cross-checked against the
`youtube-data/` research in this repo (evals + observability + failure modes dominate).

---

## The phases — each one showable on its own

| Phase | What gets built | Showable when |
|---|---|---|
| **A — First contact** | ARC-AGI-3 SDK running locally, API key, a scripted random agent, scorecard retrieved | A game plays end-to-end from our code |
| **B — The loop** | Hand-built agent loop with an LLM planner; free-tier model bake-off (Gemini Flash / Groq / local) chosen *by measurement* | The agent makes non-random progress on ≥1 game |
| **C — Evals** | Fixed eval suite of games; metrics: score, actions-to-progress, tokens/game; one-command run; results table auto-written | Any change can be judged in numbers within minutes |
| **D — Traces & failure taxonomy** | Every decision logged (context in, action out, tokens, latency, cost); failures bucketed by mode; evals added for each bucket | We can answer "*why* did it do that?" for any action, with receipts |
| **E — Memory & retrieval** | Short-term (in-context) + long-term (embedding retrieval over past episodes); measured effect on the suite | Before/after numbers showing memory helps (or doesn't — also a result) |
| **F — Budget engineering** | Per-game token/cost budget, caching, cheap-first model routing; cost-vs-score curve | The agent's cost per game is a dial, and we show the curve |
| **G — Publish** | Public leaderboard entry; README that tells the story; study notes complete | A stranger can re-run the suite and get our numbers |

Phase order is dependency order: you can't do context engineering (B) honestly without
evals (C) — so C comes *immediately* after the first working loop, before any tuning.
Timeline: flexible, as always. A–C is the minimum showable core.

---

## Rules carried over from note 01 (unchanged, re-aimed)

- **Held-out games:** the eval suite is split — a dev set we iterate on and a held-out
  set we touch rarely. Never tune on what we report.
- **One-command reruns:** `make eval` (or equivalent) reproduces every number in the
  README.
- **Written records:** every experiment — including failed prompt ideas — gets its
  page: question, change, numbers, what we believe now.
- **Study notes teach timeless things:** tokens and context windows, the agent loop,
  evaluation design, exploration under unknown rules, budgets as constraints. Vendor
  tools appear only as implementations of those ideas.

## What this project deliberately is not

Not a RAG doc-bot, not a framework showcase, not a prize bid (the Kaggle no-internet
track would forbid LLM APIs; it stays optional for later), and not GPU research — the
TRM reproduction is parked in `trm-reproduction/` for project-asi.

---

## Next step

Phase A: install the `arc-agi-3` SDK, register the free API key (three.arcprize.org),
run a scripted agent on one public game, pull the scorecard. First study note after
that: **tokens, context windows, and why they are the physics of this whole project.**
