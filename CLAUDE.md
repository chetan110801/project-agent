# CLAUDE.md — binding rules for every Claude session in this project

These rules apply to ANY Claude model working here (Opus, Fable, or later models).
They exist because sessions and models change but quality must not. Treat every rule
as hard unless Chetan explicitly overrides it in-session — and if he does, record the
override in `notes/DECISIONS.md`.

## 1. Session protocol

- **Start:** read auto-memory `MEMORY.md`, then `notes/DECISIONS.md` (newest entries
  first), then the newest `notes/NN-*.md`. "continue" from Chetan means: resume from
  the NEXT STEP line in memory. Do not re-plan work that is already planned.
- **End:** persist every decision made this session to auto-memory (update the NEXT
  STEP line), commit with a descriptive message, and push to `origin main`.
  A session that changed things but pushed nothing is an unfinished session.

## 2. Decision discipline — no silent drift

- `notes/DECISIONS.md` is binding. Do not re-litigate or quietly deviate from a locked
  decision. Changing one requires: Chetan's explicit agreement in-session + a new dated
  entry (decision / why / rejected alternatives / what it supersedes).
- Current scope (2026-07-21 evening entry): **LLM-driven ARC-AGI-3 agent judged by its
  engineering harness** — spec in `notes/03-agent-harness-spec.md`. Not an app, not a
  tutorial RAG project, no GPU training. TRM work is deferred, not deletable.

## 3. Recheck everything you produce (the rule this file exists for)

Before ending any turn that produced content, do an explicit self-review pass:

- **Code:** state plainly whether it was run. Untested code is labeled
  `DRAFT — untested` in the file itself, not just in chat. Never claim "works" without
  having executed it in this session.
- **Numbers and facts:** every number in a note traces to either (a) a run artifact in
  this repo or (b) a cited live source checked this session. Facts older than ~a month
  in a fast-moving area (leaderboards, prices, quotas, APIs) get re-verified with web
  search before being relied on. No number may be produced from model memory alone.
- **Consistency:** new content must not contradict `DECISIONS.md` or earlier notes.
  If it does, either fix the new content or record a decision — never leave both
  versions standing.
- **Claims about what exists** (files, configs, API flags, library functions): verify
  against the actual file/repo/docs before writing them down. Do not guess interfaces.

## 4. Honesty of reporting

- Failures, regressions, and negative results are reported plainly and written up with
  the same care as wins. Never round "partially works" up to "works".
- Reduced-scale or shortcut results are labeled as such everywhere they appear.
- If a session hits a wall, write down the wall (what was tried, what failed) before
  stopping — the next session must not rediscover it.

## 5. Evals gate all tuning (from Phase C onward)

- Once the eval suite exists: **no prompt, context, model, or loop change is kept
  without before/after eval numbers** on the dev set. Regressions revert or get a
  written justification.
- The held-out game set is touched only for reported results, never for iteration.
  Tuning on held-out data is the one unforgivable sin of this project.
- Every experiment gets a record: question, change, numbers, conclusion.

## 6. Chetan must be able to explain everything

- Chetan's goal is interview fluency; he is learning this stack from scratch. Every
  non-trivial artifact gets a plain-language explanation (what it is, why it exists,
  how to explain it in an interview). If it can't be said simply, flag it — that's a
  sign it isn't understood yet.
- Study notes in `notes/` teach **timeless concepts** (tokens/context windows, the
  agent loop, evaluation design, exploration, budgets); tools and vendors appear only
  as implementations of those concepts.

## 6A. The study-notes standard — HARD RULE (set 2026-07-22 at Chetan's instruction)

Chetan's exact framing: *"I don't have any idea of what the project is about… zero
technical knowledge of the technical terms… you need to make me understand through
those study notes… a flow, incremental learning… first the basics and the overview,
then detail later, building on the earlier files."* This binds every session and every
model. Violating it is a defect on the level of a wrong number.

**Who the reader is.** A working data scientist (~2.5 years) who is a **complete
beginner in LLMs, agents, and this whole stack**. English is not his first language;
his working vocabulary is everyday Indian English. He must be able to *say these
things out loud in an interview*, not merely recognise them.

**The ladder (non-negotiable shape).** Study notes are a **course**, not a pile.
They live in `notes/study/`, numbered, and are read in order:

1. Every note declares, at the top: **You are here**, **Assumes you read** (which
   earlier notes), and **After this you can** (what he'll be able to say).
2. **No forward references.** A note may only use terms already defined in an earlier
   note or defined on the spot. If you need a term early, teach it early — never write
   "we'll explain later" and move on.
3. **Overview before detail.** The first notes give the whole picture in plain words;
   depth arrives only after the map exists.
4. **Every term is defined at first use**, in one plain sentence, before it is used to
   explain anything else.
5. **Gloss non-basic English inline** — a short `(…)` meaning of ≈2–5 words, once per
   note, at first appearance. Over-glossing is not a defect; under-glossing is. Leave
   bare only everyday high-frequency words.
6. **Concrete before abstract.** Every hard idea gets a worked picture or a real case
   showing what it is *for*. A definition with no cash value is a defect.
7. **Every note ends with `Say it in an interview`** — 3–6 lines he can actually speak,
   plus the follow-up questions an interviewer would ask and how to answer them.
8. **Closure.** No idea may be left half-open. If a note leans on an earlier one, carry
   a one-line gist so he is never stranded.

**Recheck passes (separate reads, one question each — not one combined skim):**
(1) *flow* — does it read as one continuous line with no jump where he falls off?
(2) *jargon* — is every technical term defined before use, and every non-basic word
glossed? (3) *closure* — does every idea land and finish? (4) *truth* — does every
claim survive rule 3 above (run artifact or checked source)?

**When the project changes, the course changes with it.** A session that adds a
capability but leaves the ladder unable to explain it is unfinished.

## 6B. Anything Chetan must do himself gets a step-by-step — HARD RULE (2026-07-22)

Chetan cannot be handed a task like "get an API key" or "install X" as a one-liner.
Any action outside what Claude does in-session gets a **numbered, click-by-click
walkthrough**, written before he is asked to do it:

- Numbered steps, one action each, in the order he performs them.
- Say **exactly what to click / type**, what the screen should look like, and where he
  is (browser? PowerShell? which folder?).
- Give the **exact command text** to paste, and the **exact expected output**, so he
  can tell success from failure.
- List what can go wrong and what to do about it (**If you see X, do Y**).
- Say **why** he is doing it — one line — so it isn't a ritual.
- End with **how he tells Claude it's done** (what to paste back).

These walkthroughs live in `notes/howto/` so they survive the chat window.

## 7. Hard constraints

- **Free tiers only.** No paid APIs, no paid infra, no "small" spend. If a free tier
  is insufficient, that constraint becomes part of the engineering story — say so.
- Windows machine, PowerShell primary; code must run on Chetan's laptop.
- Secrets (API keys) never committed. Use env vars / untracked `.env`; keep
  `.gitignore` current before any commit that could touch them.
- Repo: `github.com/chetan110801/project-agent`, branch `main`.
