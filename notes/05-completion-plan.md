# Design note 5 — The completion plan: consolidate the project for interviews

*Written 2026-07-28, revised the same day after Chetan clarified the goal — "I just wanna
present the complete project in the interviews" — and chose **Consolidate & present** over
building the far-side agent. This note is the plan he asked for: how the existing project
becomes a finished, presentable interview artifact across a session or two. The dated
`DECISIONS.md` entry of this date records the choice and supersedes the short-lived "far-side
build" plan.*

> **STATUS: PLAN — approved to execute.** The far-side agent build (notes 04 §5) is
> **deferred, not deleted** — its design is kept as presentable record. What remains is
> consolidation: one teaching note, a presentation surface, and a consistency pass.

---

## 0. What "complete the project" honestly means

This matters more than any milestone below, so it comes first.

**The project's success was never "beat the game."** Note 03 (the spec) says it in one line:
*"The score matters less than the harness: the interview artifact is 'here is how I measure,
debug, and improve an agent — and every claim, you can re-run.'"* Against the real goal —
**Chetan presenting a finished project in interviews** — the project is nearly there already.

So "complete" here means **all of this, finished and re-runnable**:

- every engineering layer built (loop, traces, evals, guards, budgets — **done**);
- every planned experiment run and written up honestly (four **done**, the wall documented);
- every teaching rung on the ladder written (00–10, 12, 13 **done**; **note 11 remains**);
- a **presentation surface** so an interviewer — and Chetan — can see the whole thing at a
  glance (README + interview-prep pack);
- the wall (note 09/10) presented as the genuine finding it is, not hidden.

**What I can promise:** all of the above gets finished, every number traces to a run artifact
or cited source (CLAUDE.md §3), and the result reads end-to-end as one honest story.

**What this plan deliberately does NOT do:** build the far-side agent (learning across
attempts / novelty exploration). That is deferred because it is the highest quota/run risk,
spans multiple sessions, most likely returns null, and — the decisive point — **note 04 already
lets Chetan speak to those approaches without building them.** A documented, well-explained
wall is a stronger interview artifact than a half-built agent.

---

## 1. Where the project stands (the ledger, so the remainder is scoped)

| Layer | State |
|---|---|
| Harness: loop, illegal/stuck guards, JSONL traces, recordings | **done** |
| Encoders + the token-cost correction (note 06) | **done** |
| Eval suite: dev/held-out/reserve split, steering/outcome/cost metrics, budget gate | **done** |
| Four experiments (history, repetition guard, falsifiable theory, after-the-fact progress) | **done, all null on score** |
| Failure taxonomy (note 10): 88% active-no-progress, 0% progress | **done** |
| Far-side design pass (notes 04, 05) — the approaches, assessed | **done** (design only) |
| Course notes 00–10, 12, 13 + the reader site | **done** |
| **Study note 11 (memory & retrieval)** | **to write** (Milestone 1) |
| **Presentation surface (README + interview-prep pack)** | **to write** (Milestone 2) |
| **Final consistency pass** | **to do** (Milestone 3) |
| Far-side agent *build* | **deferred** (design kept; see notes 04 §5) |

The remaining work is the three "to write / to do" rows. Everything above them is finished.

---

## 2. The plan, in milestones

Each milestone **ends committed and pushed**, with the memory `NEXT STEP` line updated, so any
later session (any model) resumes cleanly. No live game runs, no quota — this is all writing
and consistency work.

### Milestone 1 — Study note 11 (memory & retrieval) — *the keystone*
*Completes the teaching ladder. Writable NOW, and not guesswork — the agent already has the
memory mechanisms the note teaches:*

- **Short-term memory** = the history window (Experiment 1): the agent's own recent actions in
  the prompt. Built, run, and reverted (it made repetition worse — a real, honest case).
- **Long-term / cross-attempt memory** = the progress signal (Experiment 4): attempt K's
  outcome carried into attempt K+1's prompt. Built, run, null.
- **Retrieval / embeddings / RAG** = taught as the concept, then the honest scoping: why this
  project's tiny, discrete, non-document experience did **not** need embedding-based retrieval —
  and when it *would*. Knowing when **not** to reach for RAG is itself the interview point.

Obeys §6A: ladder header (You-are-here / Assumes / After), no forward references, every term
glossed at first use, a `Say it in an interview` section, and the four recheck passes (flow /
jargon / closure / truth). It corrects note 10's footer ("note 11 waits until the agent has
cross-attempt memory") — it didn't, once the progress signal is counted as the long-term
memory it is.

### Milestone 2 — Presentation surface
*So the project can actually be shown.*

- **A top-level `README.md`** — project at a glance: the one-paragraph pitch, what was built,
  the headline results (including the wall as the finding), the tech, and how to re-run. This is
  the first thing an interviewer sees on GitHub, and the repo currently has no reader-facing one.
- **An interview-prep pack** — the likely questions and Chetan's answers, the STAR-style project
  pitch, and a tour of the artifacts, aggregating the `Say it in an interview` sections from
  across the course into one place he can rehearse from.

### Milestone 3 — Final consistency pass
- Mark note 00's ladder **11 ✅** and fix its reading order.
- Fix note 10's footer (11 written, not owed).
- Refresh the capstone (note 13) to fold in note 11 and state the final status.
- Rebuild the site (`py build_site.py`); a closing `DECISIONS.md` summary.
- The whole project reads end-to-end; every claim re-runnable.

---

## 3. Decision gates — where I pause for Chetan

Very few, because none of this spends quota or touches the live game:

- **After Milestone 1** — I show Chetan note 11 so he can confirm it reads clearly and he can
  say it out loud (the whole point of the course).
- **Milestone 2's interview pack** — I confirm the framing/emphasis matches how he wants to
  pitch it.

Everything else — the writing, consistency edits, site rebuild — I complete without pausing.

---

## 4. Risks, and how the plan already handles them

| Risk | How the plan handles it |
|---|---|
| **Note 11 drifting into guesswork** | It is grounded only in mechanisms already built and run (history, progress signal); the one unbuilt piece (RAG) is taught as concept + an honest "why we didn't need it," never as a thing that exists. |
| **Inconsistency after adding a rung** | Milestone 3 is a dedicated consistency pass (ladder, footers, capstone, site) — the same discipline that caught the 2026-07-23 renumbering debt. |
| **Session discontinuity** | Every milestone ends committed + pushed with `NEXT STEP` updated; the plan lives in-repo so no session re-plans. |

---

## 5. What this session did

Wrote the far-side design pass (note 04) and this plan; recorded the goal clarification and the
consolidation choice in `DECISIONS.md`; and began Milestone 1 — study note 11. Remaining
milestones (presentation surface, consistency pass) follow in the next session or two.

---

*Builds on [note 03 — the harness spec](03-agent-harness-spec.md) and [note 04 — the far-side
design](04-learning-across-attempts-design.md); completes the ladder begun in
[study note 00](study/00-how-to-use-these-notes.md).*
