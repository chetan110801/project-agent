# Decision log

One entry per decision that shaped the project. Newest first.
Format: date · decision · why · what was rejected.

---

## 2026-07-22 (night) — Phase B part 2: an LLM plays a real game, and it is worse than a coin flip

**Decision:** `harness/llm.py` (provider behind a one-method interface + client-side rate
limiting) and `harness/policies.py::LLMPolicy` are the decide step. `scripts/run_agent.py
--policy llm` runs it. 57 tests, all offline — `ScriptedClient` fakes the model the same way
`mock_game.py` fakes the environment, so policy and parser tests cost nothing and need no key.

**The free tier, measured** (Chetan's dashboard, 2026-07-22, in `harness/budget.py`):

| model | RPM | TPM | RPD |
|---|---:|---:|---:|
| gemini-3.5-flash-lite / 3.1-flash-lite | 15 | 250K | **500** |
| gemini-2.5-flash-lite | 10 | 250K | 20 |
| gemini-2.5/3/3.5/3.6-flash | 5 | 250K | 20 |
| gemma-4-31b-it / 26b-a4b-it | 30 | **16K** | **14,400** |

**What that buys** (`scripts/budget_report.py` → `artifacts/llm-budget.json`, at one model
call per action and 80 actions per game):

- **gemma-4-31b + object encoding: 180 games/day, 2.9 min/game.**
- gemini-3.5-flash-lite: **6.25 games/day**, 5.3 min/game.
- every other Flash: **0.25 games/day** — one game every four days. Unusable for evals.
- On Gemma, **TPM binds**, so the encoding choice is worth **7×** in throughput (2.9 vs 20.6
  min/game). On Flash-Lite, **RPM binds**, so encoding changes throughput by **nothing**. The
  same compression decision is worth 7× on one model and 0× on the other — which is why the
  encoding and the model cannot be chosen separately.

**Phase C's eval suite therefore runs on Gemma-4 with the object encoding** (180 games/day
makes a suite possible at all), with Flash-Lite as a scarce, better-model arm. Not final —
it becomes final when the bake-off has quality numbers, not just throughput ones.

**The first LLM run, reported as it happened** (80 actions, `gemini-3.5-flash-lite`, objects;
`artifacts/comparison.json`):

| | SDK random | our loop, random | our loop, **LLM** |
|---|---|---|---|
| actions not available | 38 (47.5%) | 0 | **0** |
| actions that changed nothing | 38 (47.5%) | 0 | **0** |
| final score | 0 | 0 | **0** |
| most-repeated action | 20% | 27% | **70%** |
| longest identical streak | — | — | **41 actions** |

**The model is no better than random on score and markedly worse on exploration.** It chose
`ACTION3` for 57 of 80 actions and repeated one action 41 times in a row, narrating fresh
justifications each turn ("repeating it continues the progress"). Every reply parsed — 0
unparseable in 105 live calls — so this is not a formatting failure. It is the stuck-loop
failure mode from study note 05, arriving exactly where that note predicted, and the
`nothing changed` feedback did not prevent it because the screen *was* changing by 2 cells
per press while going nowhere.

That is the finding: **"the screen changed" is not the same signal as "you made progress",
and the current prompt only carries the first.** Phase C's first real experiment is a
context change that gives the model its own recent action history, so it can see that it has
pressed the same button forty times.

**Also decided / recorded:**

- **Client-side pacing at exactly the stated limit is not enough.** Measured: a limiter
  running at the dashboard's 15 RPM still collected `429 RESOURCE_EXHAUSTED` on **3 of 80**
  calls. Fixed with `HEADROOM = 0.8` plus a single 429-only retry; a 25-action re-run came
  back **0 errors in 25 calls**. Retrying only 429 is deliberate — retrying everything would
  hide real bugs.
- **Rate limits are enforced, not discovered.** A 429 mid-game costs a turn and puts a
  failure in the trace that isn't the agent's. The limiter also makes the cost visible: the
  80-action LLM run took **309 s wall, 189 s of it asleep** on the rate limit, against 38 s
  for the same game with a random policy.
- **Coordinates out of range are rejected, never clamped** (`parse_action`). Clamping would
  turn a wrong answer into a plausible one, which is precisely what an eval must be able to
  see.
- **The prompt states the legal actions and the loop still guards them.** A prompt is a
  request; a guard is a guarantee. Both.
- `StepRecord` now carries `reasoning`, so a trace answers *why* and not only *what*. A test
  written against a field that didn't exist is what surfaced the gap.
- Windows rejects `:` in filenames, so run names are sanitised — `llm:model:encoder` produced
  an `Errno 22` that named the path but not the reason.

**Rejected:** raising on client errors (an agent that dies on a 429 measures nothing);
letting the policy parse strictly (measures our prompt's obedience, not the model's play);
choosing the model by reputation rather than by the throughput table plus a quality bake-off.

---

## 2026-07-22 (evening) — CORRECTION: study note 06's headline number was a fact about the wrong tokeniser

**What happened:** Chetan's Gemini key arrived. `scripts/measure_tokens.py` re-measured the
exact strings note 06 was built on, using `count_tokens` on `gemini-3.5-flash-lite` — the
model we actually call — alongside the offline `tiktoken/o200k_base`. They disagree by up to
2.8×, and the note's headline claim did not survive
(`artifacts/tokens-by-tokeniser.json`):

| encoding (real `ls20` frame) | chars | tiktoken | Gemini | ×  tik | × gem |
|---|---:|---:|---:|---:|---:|
| raw grid, hex packed | 4,159 | 1,471 | 4,130 | 1.00 | 1.00 |
| raw grid, decimal spaced | 8,243 | 8,191 | 8,244 | **5.57** | **2.00** |
| objects (cap 40) | 1,085 | 468 | 573 | 0.32 | **0.14** |
| diff vs previous | 66 | 22 | 28 | 0.015 | 0.007 |

**Gemini charges these grids at ~1 token per character** (4,130 tokens for 4,159 chars). It
does not pack digit runs the way `o200k_base` does, so the hex trick buys only what it buys
in characters and the celebrated "5.6× for identical information" is **2.00× on the model we
use** — which is just the character ratio, 8,243 ÷ 4,159 = 1.98.

**Every conclusion held in direction; only magnitudes moved.** Spacing still costs double.
The object encoding is still a win — a *bigger* one, 7.2× rather than 3× — because there is
more fat to cut when the raw grid is billed by the character. The checkerboard still
inverts (8.7× instead of 20.9×), so the truncation cap still earns its place.

**Decision:** note 06 now carries **both tokeniser columns** in both tables, and states as
its central lesson that *a ratio between encodings is a property of a tokeniser, not of your
data*. The interview answers were rewritten around the correction rather than around the
retired number — it is the strongest story in the note.

**Why this is a win, not an embarrassment:** the rule from Phase A that every token number
travels with the name of the tokeniser that produced it is exactly what made this a
correction instead of a wrong claim defended in an interview. A number labelled "OpenAI's
counter, used only to compare encodings" was honest when written and is still honest now.

**Also decided / recorded:**

- **`models.list()` is not an availability check.** Measured: the API listed
  `gemini-2.5-flash` with `generateContent` among its supported actions, and calling it
  returned `404 … no longer available to new users`. `scripts/check_llm_key.py` now probes an
  ordered candidate list and reports the first model that actually answers.
- **First working model: `gemini-3.5-flash-lite`** (~964 ms round trip). Flash-Lite is the
  right default for one call per game action; the `-latest` aliases are the fallback because
  they survive retirements — at the cost of not being pinned, which matters for evals and
  not for smoke tests. **This is not the model decision**; that is still made by measurement.
- Measurement scripts pin the recording (last by filename) and the frame (the middle one)
  deliberately, so the figures the notes quote reproduce. "Whatever I recorded most
  recently" would not.

**Open, and blocking budget design:** Chetan's dashboard shows free-tier limits *per model*,
and the row he sent is for the retired `gemini-2.5-flash`: **5 RPM / 250K TPM / 20 RPD**. If
the limit for `gemini-3.5-flash-lite` is of that order, **20 requests per day cannot support
an 80-action game**, and the loop must batch decisions, cache, or use a smaller number of
model calls per episode. The real row is needed before Phase C's budget is designed.

---

## 2026-07-22 (afternoon) — OVERRIDE: how-to walkthroughs are step lists, not essays

**Decision:** Chetan's instruction in-session, verbatim: *"make those howto notes much
thinner ans sharper and crisp, just the steps"*. `notes/howto/` is now **numbered steps,
exact commands, expected output, and a troubleshooting table** — nothing else. Cut: the
"why you're doing this" essays, the closing reflections, the multi-paragraph warning boxes,
the long source lists. 01 went from 263 lines to 106, 02 from 252 to 116.

**This overrides the reading of CLAUDE.md §6B** that produced the long form. §6B still
binds on substance — exact clicks, exact commands, exact expected output, what can go
wrong, and how to report back are all still mandatory. What it no longer licenses is prose
around them.

**Kept deliberately, in one line each, because losing them costs real damage:** use
`Add-Content` and never `Set-Content` (it replaces `.env` and deletes the other key);
free-tier Gemini prompts may be used by Google for product improvement; never paste a key
into chat; and step 8 of how-to 02, where he reads his own rate limits, because Google
doesn't publish them and a number invented here would be a lie with a citation-shaped hole.

**Also:** `scripts/run_agent.py --list` added, so "which games exist?" is a flag rather
than an error message with the answer buried in it.

---

## 2026-07-22 (afternoon) — Phase B part 1: our loop plays real games; the guard recovers 47.5% of the budget and changes nothing about the score

**Decision:** `scripts/run_agent.py` is the project's runner, and `harness/arc_env.py` is no
longer a draft — three real games of `ls20` were played end to end through our own transport
and our own loop (80, 80 and 400 actions), scorecards opened and closed. The SDK's CLI and
`Agent` are now used for nothing.

**The controlled experiment, which was the point of the phase.** Same game, same random
policy, same 80-action budget; the single difference is that our loop filters candidate
actions against the `available_actions` list the server sends in every frame:

| | SDK baseline | our loop |
|---|---|---|
| actions not in `available_actions` | 38 of 80 (**47.5%**) | **0 of 80** |
| actions that changed nothing | 38 of 80 (47.5%) | 0 of 80 |
| final score | 0 | 0 |

Generated by `scripts/compare_runs.py` into `artifacts/comparison.json`, from the
recordings in `runs/`, all read by one analyser.

*Which recording is which* (there are two 80-action runs of ours and they look alike):
`…e37062d0…` is the SDK baseline from Phase A; `…0036eedd…` is our loop's **first** live
run, kept because it is the one that exposed the scorecard bug — it closed the card before
reading it and came back empty; `…18fef424…` is the same run repeated after the fix and is
the one the comparison uses; `…74fbdcbe…` is the 400-action calibration.

**Reported honestly:** the score did not move, and the 47.5% → 0% is **true by construction**
(the policy cannot emit an unavailable action) rather than an estimate from a sample. With
n = 1 per arm, "still zero" is the only claim the score supports.

**The finding that actually redirects the project.** Closing a scorecard returns a per-level
breakdown that the SDK's `Scorecard` model does not declare and therefore silently drops:
`ls20` has **7 levels** with reference solutions of `[22, 123, 73, 84, 96, 192, 186]` actions
(776 total). Level 1 needs 22. We re-ran with **400** actions — 18× that — and completed
**0 levels** (`artifacts/ourloop-random-400.json`). The random policy also hit `GAME_OVER`
three times and our loop reset and continued each time.

So: **the action budget was never the binding constraint, and score is a dead metric at this
stage** — 0 for the baseline, 0 for the improved version, at 80 and at 400 actions. A metric
that cannot move cannot referee the next change. Phase C's eval suite is therefore built on
denser signals that respond before the agent starts winning: illegal-action rate, no-change
rate, `GAME_OVER` count, and **actions spent inside level 1 measured against the 22-action
reference**. Score and levels-completed remain the reported outcome, never the steering
signal.

**Why:** Phase B's stated first job was one before/after number through our own loop. It
produced that, and the calibration run that followed cost ~3 minutes and invalidated the
metric the whole eval design was about to assume. Finding it now costs one afternoon;
finding it after a week of prompt tuning would have cost the week, since every experiment
would have read "0 → 0".

**Also decided / recorded:**

- **`close_scorecard` returns raw JSON, not the SDK's `Scorecard`.** Measured: the endpoint
  answers with `card_id, environments, score, tags, tags_scores, total_actions,
  total_environments, total_environments_completed, total_levels, total_levels_completed`.
  The SDK's model declares almost none of those, and because every field has a default,
  `model_validate` *succeeds* and returns an object with an empty `cards` and a computed
  `score` of 0 that is not the server's. Validating through a vendor schema that doesn't
  cover the vendor's own endpoint destroys exactly the numbers the run is judged on.
- **The per-game card must be fetched before closing.** After `close`, `GET
  /api/scorecard/{card_id}/{game_id}` returns 404 — the id is retired. Measured.
- **RESET is always legal**, even though real frames never list it in `available_actions`
  (81 of 81 frames advertised `[1, 2, 3, 4]`). Without this the loop flags its own fallback
  as an illegal action.
- **Recordings are written in the SDK's own `{"timestamp", "data"}` format** by a
  `RecordingEnv` wrapper, so one analyser reads our runs and the SDK baseline and the
  comparison cannot be an artefact of two different readers.
- **`analyze_run.py` now refuses to overwrite a report generated from a different
  recording.** It made the mistake first: analysing a throwaway mock run silently replaced
  the committed baseline report that three study notes quote from.
- **Rate limits verified from source, not memory:** the ARC-AGI-3 API allows 600 requests
  per minute and is free during the research preview, with no daily cap
  ([docs.arcprize.org/rate_limits](https://docs.arcprize.org/rate_limits), checked
  2026-07-22). Our runs use roughly 2 req/s, so quota is not a design constraint for game
  play — it was for the LLM, which is a separate budget.
- **Free LLM tier chosen as the first candidate: Google AI Studio (Gemini Flash).** Verified
  from Google's pricing page the same day: Flash and Flash-Lite models are free of charge on
  the free tier, and free-tier data **is** used to improve Google's products. Google no
  longer publishes the free-tier RPM/TPM/RPD in its docs — they are per-project and must be
  read from `aistudio.google.com/rate-limit`, so `notes/howto/02` asks Chetan for his own
  numbers rather than inventing one. This is a *candidate*; the model gets chosen by
  measurement.
- **Key reading is centralised** in `harness/env_file.py` so the Windows byte-order-mark trap
  is fixed once for every future adapter rather than re-discovered per vendor.
- Study note 07 is **baselines and controlled experiments** (written from these runs); evals
  shift to note 08 and are written when the suite exists. Tests: 42 passing, 0.2 s, no key.

**Rejected:** using the SDK's `Scorecard` model for the close response (drops the level data);
recording in a bespoke format (would have made the before/after incomparable); tuning
anything before the metric question was settled; taking Gemini's free-tier limits from a
search result rather than the account dashboard.

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
**Confirmed working on his iPhone 2026-07-22:** text fills the screen top to bottom and
the menu and home buttons are separate and visible. This item is closed.

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
