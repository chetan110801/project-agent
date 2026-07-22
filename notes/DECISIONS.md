# Decision log

One entry per decision that shaped the project. Newest first.
Format: date · decision · why · what was rejected.

---

## 2026-07-22 (morning) — Phase A done: first live run; the harness is built against a mock so it never waits on quota

**Decision:** The agent harness is developed against an **offline mock environment**
(`harness/mock_game.py`) that returns the SDK's own `FrameData` objects, with the real API
used only for ground-truth runs. Our loop takes an `Environment` protocol rather than
subclassing the SDK's `Agent`, because the SDK's loop is welded to its HTTP transport —
every test of it would cost a network call and a slice of the free tier, which in practice
means the tests don't get written. Result: 35 tests, running in 0.4 s, no key required.

**Phase A is complete.** The `ls20` game was played end to end by the SDK's random
baseline; the 81-frame recording is committed in `runs/` and analysed by
`scripts/analyze_run.py` into `artifacts/run-report.json`. Score 0, state `NOT_FINISHED`,
80 actions — the expected baseline result.

**Findings from that run (all measured, all in the artifact):**

- **The baseline wasted 47.5% of its budget.** `available_actions` was `[1, 2, 3, 4]` in
  every frame; the SDK's random agent picks from all eight. 38 of 80 actions were buttons
  that don't exist, and those are exactly the 38 transitions that changed nothing. Our
  loop's illegal-action guard recovers that for one line of code and no model.
- **Three of our pre-data assumptions were wrong**, each silent, none caught by a test:
  cell values reach 12 (so packed *decimal* rendering is ambiguous — cells are now one hex
  character); the background of `ls20` is colour 4 covering 64% of the screen, not 0 (the
  object encoder was describing the floor as the biggest object — background is now
  inferred); and one frame carried **six** grids, an animation for a single action (so
  `frame[0]` would show a stale mid-animation picture — we take the last).
- **Encoding costs on a real frame:** hex-packed grid 1,471 tokens; the same grid as spaced
  decimals 8,191 (**5.6× for identical information**); objects 468; diff 22. On a
  hand-built checkerboard the object encoding *inverts* to 20.9× the raw grid, so it
  carries a truncation cap. Counts are `tiktoken/o200k_base` — for comparing encodings
  only, never as a budget for another vendor's model.
- **My synthetic pre-run measurement of the object encoding said 14×; the real frame says
  3×.** The code was fine; the invented test input was flattering. Recorded because it is
  the commonest way an honest number misleads.
- **Two Windows papercuts, both costing a session's start:** `Set-Content -Encoding utf8`
  writes a UTF-8 BOM, so `.env` produced a variable literally named `﻿ARC_API_KEY` and
  the API returned 401 (the same BOM bug hit `.gitignore` on 2026-07-21). And the SDK's CLI
  shuts down with `os.kill(os.getpid(), SIGINT)`, which on Windows kills the process before
  the scorecard is printed — exit code 2, no output, despite a fully successful run. Both
  are written into `notes/howto/01`.

**Why:** Phase A's stated goal was to prove the pipeline before adding cleverness. It did
that and more — the run cost nothing, scored nothing, and destroyed three wrong assumptions
that every test would have kept passing.

**Rejected:** subclassing the SDK's `Agent` and using its loop (untestable offline, and the
loop is the interview artifact — see study note 05); waiting for real frames before writing
any encoder (the mock made the loop and its guards testable immediately, and the guards
turned out to be what the run needed); using the SDK CLI as the runner (the Windows
shutdown bug plus no control over context is exactly what our own runner is for).

**Also decided:** study notes quote numbers only from `artifacts/`, and every token count
in this repo travels with the name of the tokeniser that produced it. Study note 06
(context engineering) is written; note 07 (evals) waits for the eval suite to exist.

---

## 2026-07-22 — Study notes become a structured course for a zero-knowledge reader; step-by-step walkthroughs are mandatory

**Decision:** Three new hard rules, written into `CLAUDE.md` (§6A, §6B) so every future
session and model obeys them:

1. **Study notes are a course, not a pile.** They live in `notes/study/`, are numbered,
   and are read in order. Every note declares *You are here* / *Assumes you read* /
   *After this you can*, defines every term at first use, **makes no forward references**,
   gives overview before detail, anchors abstract ideas in something concrete, and ends
   with **Say it in an interview**. Non-basic English gets a short inline gloss.
2. **Anything Chetan must do himself gets a numbered, click-by-click walkthrough** in
   `notes/howto/` — exact clicks, exact commands, exact expected output, what can go
   wrong, and how to report back. Never a one-line instruction.
3. **Rechecks are separate single-focus passes** (flow / jargon / closure / truth), not
   one combined skim.

Written this session: `notes/study/00`–`05` (how to use the notes; the project in plain
English; the vocabulary in dependency order; tokens & context windows; ARC-AGI-3 and its
exact interface; the agent loop) and `notes/howto/01-get-your-arc-api-key.md`.
Notes 06–11 (context engineering, evals, traces, memory, budgets, the interview story)
are listed in the ladder and get written **as each component is built** — a note about an
unbuilt component would be guesswork.

**Why:** Chetan stated plainly that he has **zero** technical knowledge of this stack and
cannot learn from notes that assume any. He also cannot act on instructions like "get an
API key" without a walkthrough. Both were previously implicit-at-best; interview fluency
is the project's whole purpose, so failing at them fails the project regardless of how
good the agent gets.

**Rejected:** writing all of notes 06–11 now (would violate the no-unverified-claims rule
— they'd describe components that don't exist); keeping the course inside `notes/`
alongside the project record (mixes teaching with history and breaks the reading order).

**Also decided (reader/site):** `build_site.py` now groups documents into *Learn from
zero* → *Do this — step by step* → *Project record* → *Project* → *Deferred: TRM*, which
is the reading order, and renders `::: key/example/warn/note` callout boxes. Reader-shell
fixes for iPhone: the menu and home buttons moved into one fixed flex row so they can
never overlap at any inset or font size; corner buttons stay faintly visible on touch
devices (which have no hover, so they were invisible forever after the load hint faded);
phone padding cut from 3.4rem/4.5rem to 3.05rem/1.6rem so text fills the screen
vertically; and the JS viewport-height override now only runs where CSS `dvh` is
unsupported — a stale `innerHeight` in an in-app browser (e.g. opening the file from the
OneDrive app) is the most likely cause of the dead band Chetan saw at the bottom.
**Untested on the actual iPhone** — needs his confirmation.

---

## 2026-07-21 (evening) — PIVOT: the project is an LLM-driven ARC-AGI-3 agent judged by its engineering harness; TRM deferred to project-asi

**Decision:** project-agent is re-centered on one build: an **LLM-driven agent for
ARC-AGI-3**, where the interview-facing deliverable is the **engineering harness**
around it — the agent loop built from first principles, context engineering, an eval
suite run on every change, tracing/observability, reliability guards, and free-tier
cost/latency engineering. Target: the public leaderboard (internet allowed); the Kaggle
prize track (no internet → no LLM APIs) is optional later, not the goal. The
TRM/Sudoku reproduction + ablation is **deferred to project-asi** — the Phase 0
verification and the pre-registered ablation plan are kept in this repo
(`trm-reproduction/`, marked deferred) so nothing is lost.

**Why:** Chetan's requirement, stated plainly: the portfolio must showcase *current*
AI-engineering / agentic-engineering practice (loops, evals, reliability, efficiency)
because that's what interviews probe, and he needs to learn it ("I don't know shit
about it"). The morning plan had a real gap the pivot fixes: prize-eligible ARC-AGI-3
agents can't call LLM APIs (no internet at eval), so building for the prize would have
taught loop fundamentals but not the LLM-engineering stack. Off-Kaggle, LLM-driven
agents are the expected pattern (the official SDK ships OpenAI/LangGraph integrations).
The substrate keeps the AGI-path spine that motivation depends on; the harness carries
the interview story. No GPU training anywhere — laptop + free API tiers only.

**Rejected:** (a) same harness on a business-shaped benchmark (τ-bench-style) — closer
to product-company day jobs but crowded territory and loses the AGI spine; (b) keeping
the TRM-first plan — the LLM/agentic stack would arrive too late or not at all;
(c) dropping TRM entirely — the ablation idea stays parked, it costs nothing to keep.

**Supersedes:** the morning entries below insofar as they made TRM Step 1. The rigor
constraint (reproducible claims, held-out evals, written records, timeless study notes)
carries over unchanged — it now applies to agent evals instead of training runs.

---

## 2026-07-21 — Step 1 reordered: Sudoku-first reproduction; ARC at reduced scale only

**Decision:** Phase 0 verification (see `notes/02-phase0-verification.md`) found the
paper's ARC-AGI-1 training run cost ~288 H100-hours — roughly two years of Kaggle's
free 30 GPU-h/week. Step 1 therefore becomes: (a) full-scale TRM reproduction on
**Sudoku-Extreme** (~18 datacenter-GPU-hours, feasible in 1–2 weeks of quota, target
≈87%), (b) the recursion-depth ablation (16→8→4→2, equal budget per depth) on
Sudoku-Extreme, (c) one **reduced-scale** ARC-AGI-1 run reported honestly as
reduced-scale. The ablation contribution is unchanged; only the task it runs on moved.

**Why:** Forced by arithmetic, not preference. The alternative — burning weeks of quota
to reach a fraction of one ARC run — produces nothing showable.

**Rejected:** Renting cloud GPUs (violates zero-budget constraint); skipping
reproduction and doing only the ablation (no calibration that our training pipeline is
correct); Maze-Hard as the cheap task (several weeks of quota vs Sudoku's 1–2).

**Also recorded:** TRM's official repo was archived 2026-04-01 (read-only) — we fork it
so the reproduction can't be orphaned. ARC-AGI-3 leaderboard moved (frontier ~7.8%,
a paper claims 78.4% on public eval); the "frontier under 1%" line is retired from the
pitch.

---

## 2026-07-21 — Where "agentic engineering" lives in this project

**Decision:** Interview-facing agentic topics (the agent loop, memory, exploration
policy, evaluation of agents) are covered by **Step 2 itself** — the ARC-AGI-3 agent is
an observe→decide→act loop with memory and hypothesis-testing, built from first
principles rather than a framework. A study note on "the agent loop, timelessly" is
added to the standing list. Framework-specific tooling (LangGraph et al.) stays out of
study notes per the timeless-concepts constraint; RAG/function-calling interview
questions are covered by ResearchPath (resume project #2), not this project.

---

## 2026-07-21 — The project is an AGI-direction research piece, not an app

**Decision:** Build (1) a reproduction of the Tiny Recursion Model on ARC-AGI-1 plus an
unpublished recursion-depth ablation, then (2) a purpose-built agent for ARC-AGI-3
targeting the 30 Sept 2026 open-source milestone. Timeline flexible; each step showable
on its own.

**Why:** Chetan's long-term goal is AGI/ASI work; the portfolio must be a step on that
path or motivation dies. project-asi's own forward plan (`LEARNING/THE_PLAN.md`,
2026-07-21) identified the efficiency frontier as the one part of AGI research open to a
zero-budget individual, with these exact two moves as Phases 2–3. The portfolio project
and the AGI path now share one spine.

**Rejected:** study-materials generator, job-application copilot, GitHub issue triage,
customer-support agent, SRE/log copilot — all "generic software" apps; Chetan is
explicitly not interested in learning replaceable app-stack practices.

**Constraint recorded:** study notes teach *timeless* concepts (generalization,
test-time compute, ablations, exploration, the research loop) — never tooling for its
own sake. Claude writes the code; Chetan owns the understanding.

---

## 2026-07-21 — (earlier) Reliability-as-thesis, reframed

**Decision:** The original thesis — "anyone can vibe-code an app; the trust system
around it is the differentiator" — survives, reframed for research: reproduction
targets, held-out tests, one-command reruns, written experiment records.

**Why:** It is the same discipline interviewers probe in applied-science loops
(how do you know your result is real?), and it is timeless scientific method rather
than a tooling stack.
