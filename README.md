# project-agent — an LLM agent for ARC-AGI-3, judged by its engineering harness

An LLM-driven agent that plays **[ARC-AGI-3](https://arcprize.org)** — games with no
instructions and no stated goal, where the agent has to work out the rules by acting — wrapped
in the **engineering harness that makes an agent trustworthy**: a hand-built agent loop, an
evaluation suite that runs on every change, a trace of every decision, reliability guards, and a
token/cost budget it must live inside.

**The score matters less than the harness.** The deliverable is not "I beat a benchmark" — it is
*"here is how I measure, debug, and improve an agent, and every claim I make, you can re-run."*
Built on **free tiers only** (no paid APIs, no GPU training) on a Windows laptop.

> **New to the project? Read the course.** Every component below has a plain-language write-up in
> [`notes/study/`](notes/study/) — a 14-note course read in order, or browse the whole thing as a
> single offline page by opening [`index.html`](index.html).

---

## The headline — reported honestly

The most important thing this project demonstrates is **rigour about a negative result**, so it
leads with one:

- **The agent does not beat the game.** On the outcome that counts it scores the same as a random
  baseline: zero. That is the finding — established thoroughly and reported as loudly as a win
  would be, not buried.
- **A failure taxonomy, built from the agent's own traces, says *why* in one number:** **88% of
  its actions are legal, non-repeating, screen-changing work that makes no progress; 0% make
  progress.** It is not stuck in a loop and not flailing — it does *purposeful-looking work toward
  a goal it never identified.*
- **Four controlled, pre-registered experiments** — the agent's memory of its own actions, a
  repetition guard, a falsifiable theory of the goal, and an after-the-fact progress signal — each
  **changed the agent's behaviour and moved the score not at all.** That locates the wall exactly:
  nothing in the loop turns feedback into a better-chosen next action, because the games state no
  goal and only the server's end-of-game scorecard ever knows it.
- **Every number here is re-runnable from this repo.** **154 tests, all offline, all passing.**

The value is in *how thoroughly* that is established and *what it locates* — which is exactly the
kind of thing an interviewer is probing for.

---

## What's in the repo — the engineering

| Layer | What it is | Where |
|---|---|---|
| **Agent loop** | observe → decide → act → record, built from first principles (not the SDK's), with three guards: hard action cap, illegal-action rejection, stuck detection | [`harness/loop.py`](harness/loop.py) |
| **Policies** | the "decide" step, isolated so it can be swapped and compared — a seeded random baseline and an LLM policy | [`harness/policies.py`](harness/policies.py) |
| **Context engineering** | three ways to turn a game screen into text the model can read (verbatim grid, objects, diff), measured against each other | [`harness/frames.py`](harness/frames.py) |
| **Evals** | a fixed dev / held-out / reserve game split, per-game metrics tagged **steering / outcome / cost**, and a runner that refuses to touch held-out data without `--report` | [`harness/evals.py`](harness/evals.py), [`scripts/run_evals.py`](scripts/run_evals.py) |
| **Traces** | one append-only JSONL record per decision — including the model's own stated reason — so "why did it do that?" has an answer | [`harness/trace.py`](harness/trace.py) |
| **Failure taxonomy** | every recorded action sorted into one of six priority buckets; the wall as a counted table | [`scripts/failure_taxonomy.py`](scripts/failure_taxonomy.py) |
| **Budgets** | the three budgets you actually spend on a free tier — tokens, requests/day, latency — with a pre-flight quota check that refuses an arm that would die half-run | [`harness/budget.py`](harness/budget.py) |
| **The course** | a 14-note plain-language explanation of all of the above, compiled into one offline reader | [`notes/study/`](notes/study/), [`build_site.py`](build_site.py) → `index.html` |

---

## How it maps to what AI-engineering interviews ask

This mapping *is* the design — each thing interviews probe lives in a layer of this one project:

| Interview topic | Where it lives here |
|---|---|
| **LLM fundamentals** — tokens, tokenization, context windows | Every token the agent spends is counted; a tokeniser correction ([note 06](notes/study/06-context-engineering.md)) overturned a headline claim and shows *a token ratio is a property of the tokeniser, not the data* |
| **Context engineering** — what goes in the window, compression | The heart of the loop: each step decides what the model sees; encoding changes go through the eval suite, never vibes |
| **Agent design & failure modes** — loops, memory, stuck states | The loop from first principles, five named failure modes, and a failure taxonomy counted from real traces |
| **Evals** — golden sets, regression gates | A fixed suite; every change ships with before/after numbers; held-out data is guarded by code, not good intentions |
| **Memory & retrieval** — short/long-term, embeddings, RAG | Two built memory mechanisms, and the honest reason this project uses **no** RAG ([note 11](notes/study/11-memory-and-retrieval.md)) — knowing when *not* to reach for it |
| **Production ops** — tracing, cost/latency budgets | Every call traced; a per-day request budget; the fastest model on paper was the wrong one, and the notes show why |

---

## Run it

Requires **Python 3.11+** on Windows (PowerShell) or any POSIX shell.

```bash
# 1. install the runtime dependencies: reader (markdown), LLM client, game SDK
py -m pip install markdown google-genai arc-agi-3

# 2. run the whole test suite — offline, no keys, ~1 second
py -m unittest discover -s tests

# 3. build the notes into one browsable page, then open index.html
py build_site.py

# 4. (optional) play a game. Needs a free ARC key in .env — see notes/howto/01.
py scripts/run_agent.py --policy random          # the seeded baseline
py scripts/run_agent.py --policy llm --model gemini-3.5-flash-lite

# 5. (optional) run one eval configuration and compare two of them
py scripts/run_evals.py --arm smoke --mock        # offline rehearsal, no quota
py scripts/compare_evals.py dev-llm-p0 dev-llm-p1 --attempt 2
```

Keys live in an untracked `.env` (see [`.env.example`](.env.example)); the two how-to notes in
[`notes/howto/`](notes/howto/) are click-by-click walkthroughs for getting them.

---

## Honest status, and what's next

The teaching course is **complete** (notes 00–13). The engineering is built and tested. The
central result — the wall — is documented from four angles.

The genuine next direction, **learning across attempts** (credit assignment / novelty-driven
exploration), is fully *designed* in [note 04](notes/04-learning-across-attempts-design.md) and
deliberately **deferred**: it is the highest quota/run risk, and the design pass showed it is
blocked by the same reward-sparsity wall (with the score at zero on every attempt, there is no
success to learn from). Designing it, and explaining exactly why it is hard, is itself part of
the story.

Every decision that shaped the project — with dates, rejected alternatives, and evidence — is in
[`notes/DECISIONS.md`](notes/DECISIONS.md).

---

## Repo layout

```
harness/     the agent: loop, policies, encoders, evals, traces, budgets, guards
scripts/     runnable entry points: run_agent, run_evals, compare_evals, failure_taxonomy, ...
tests/       154 offline tests (test_harness.py)
artifacts/   every result the notes cite, as JSON you can re-generate
notes/       study/ (the course) · howto/ (walkthroughs) · DECISIONS.md · design notes
runs/        recorded game traces (gzipped JSONL)
index.html   the whole course as one offline reading app (built by build_site.py)
```

*Built by Chetan J with Claude Code. The course is written for a data scientist learning this
stack from scratch; if a note ever uses a term it didn't define, that's a bug — it gets rewritten,
not patched in chat.*
