# Design note 4 — Learning across attempts: the far side of the wall

*Written 2026-07-28. This is a **design pass for approval**, not a build. It commits no
code and runs nothing live. Its job: say precisely what "the agent learns across attempts"
could mean, be honest about the odds given four failed experiments, recommend the
cheapest-first path, and pre-register the first experiment — so that if Chetan approves a
direction, the build is a fill-in and the discipline (§2, §5) is already in place.*

> **STATUS: DESIGN — NOT APPROVED FOR BUILD.** Per CLAUDE.md §2 this is a *new direction*.
> It needs its own dated `DECISIONS.md` entry (this pass writes one recording the design)
> **and** Chetan's explicit "build option X" before any code. Nothing here is a decision
> yet; §8 is the decision I need from him.

---

## 0. What this is, in plain words

The teaching course (notes 00–10, 12, 13) is finished. Along the way the agent hit a
**wall**: it plays every game busily and legally and **never once moves the score**. The
failure taxonomy (note 10) put a number on it — **88% of its actions are "active but no
progress," 0% are progress.** Four experiments tried to get it past the wall by *telling
it more* (its own history, a falsifiable theory, an after-the-fact progress report). All
four changed its behaviour; **none moved the score.**

The one direction left is different in kind: let the agent **play the same game several
times and carry something it learned from one attempt into the next.** That is what
"learning across attempts" means. This note designs it — and, just as importantly, is
honest that the four prior failures set a *low prior* on any version of it working, and
that "the wall is the finding" is itself a legitimate, strong place to stop.

---

## 1. The wall, precisely (so a fix has a target)

Carried from notes 09 and 10, in one paragraph so a design has something concrete to
attack:

- **Progress is undefined without a goal.** These games state no goal (note 04).
- **Nothing *inside* an episode knows the goal.** Every screen-derived "am I getting
  warmer?" signal we tried read *backwards* on the recorded failure — a meaningless marker
  sliding one cell a turn looked like steady progress (`artifacts/progress-signals.json`,
  the impossibility result).
- **Exactly one thing knows the goal: the server's scorecard**, closed at the end of a
  play — it reports levels cleared and a reference solution's length. But it arrives only
  at the end, and Exp 4 fed it into the *next* attempt's prompt and **it did not steer**
  (null on every pre-registered "works" metric; score stayed 0→0).
- **The taxonomy names the target exactly.** A real fix has to move actions **out of
  `active_no_progress` (88%) and into `progress` (0%)** — and `progress` means the score
  moved, which across every committed run it never has.

That last line is the whole problem stated as a target. Keep it in view for the rest of
this note.

---

## 2. The one hard fact every design hits: there is no success to learn from

This is the crux of the entire design pass, so it comes before the options.

**Learning "which actions led to success" needs at least one success.** Credit assignment,
reward models, an action-value table — all of them learn a mapping from *what I did* to
*how well it went*. Our agent's "how well it went" is **0 on every attempt of every dev
game** (final_score 0, levels_cleared 0, note 10). A learner fed an all-zero outcome learns
nothing: `0 = f(anything)` has no gradient, no signal, no preferred action. So:

> **Any design that learns from the outcome is blocked until the agent produces a first
> non-zero outcome — which is the very thing we are trying to make it do.** This is the
> reward-sparsity wall, and "learn across attempts" does not dissolve it; it just moves it
> up one level (now we lack a success to learn *across attempts* from).

There are only two ways around a sparse-reward wall, and every serious design below is one
of them:

- **(a) Manufacture the first success by coverage** — explore the game's states
  *systematically* (novelty-seeking) until you stumble into a level clear, then bootstrap
  from that first non-zero reward.
- **(b) Learn something goal-agnostic** — a model of *what each action does* (not what is
  good), and hope a better-informed agent gets further on its own.

If neither of those produces a first success, the far-side work characterises the wall more
sharply but does not break it. That has to be said out loud (§4 honesty), and it shapes the
recommendation.

---

## 3. The four candidate designs, assessed honestly

Each is judged on: what signal it learns from, whether it needs the goal, where it plugs
into code that already exists, build size, free-tier quota cost, and — the column that
matters — its honest odds against the wall in §2.

| # | Design | Learns from | Needs goal? | Escape hatch (§2) | Build | Honest odds |
|---|---|---|---|---|---|---|
| **A** | Cross-attempt **credit assignment on the score** | levels cleared per attempt | yes | neither | small | **~0 — blocked**: no success to assign credit to |
| **B** | A goal-agnostic **action/effect model** | what each action does to the screen | no | (b) | medium | low–moderate |
| **C** | **Count-based novelty exploration** across attempts | how often each (state, action) was tried | no | **(a)** | large | the only path to a *first* success; uncertain |
| **D** | Cheap probe: a **plain-language memory of prior attempts** | what was tried across attempts | no | weak (b) | small | low, but cheapest to test |

### A — Credit assignment on the score. *Reject as the primary path.*
The textbook "learn across attempts": figure out which actions in a losing attempt cost you
the level. It is blocked by §2 before it starts — with every attempt scoring 0, there is no
win and no loss to compare, so credit assignment has nothing to bite on. It becomes
available *only after* something else produces a first level clear. Kept on the shelf for
after C, not built now.

### B — A goal-agnostic action/effect model.
Learn, across attempts, a compact statement of what each action *does*: e.g. "ACTION3 moves
the marker one column right — same effect in all 5 attempts, and it never cleared a level."
This is stronger than Exp 1's within-episode history because it is *aggregated over
attempts* and can carry the damning part ("...and it never cleared a level in 5 tries").
Plugs straight into the progress-signal path (§6). **The honest doubt:** Exp 1 and Exp 3
already showed the LLM reads "what an action does" as *"this action works,"* and narrated a
meaningless marker as achievement. A cross-attempt effect model might read differently
because it can say "the same nothing, every time" — or it might get read favourably again.
Medium build, cheap to run.

### C — Count-based novelty exploration across attempts. *The only design that can produce a first success.*
Keep a store, persisted across all attempts at a game, of how many times each
`(state-feature, action)` pair has been tried. Bias the agent toward the **least-tried**
options — classic sparse-reward exploration (pseudo-counts / novelty bonuses). It needs no
goal: novelty is intrinsic. It is the one design with a *mechanism* for escape hatch (a) —
methodically covering unexplored states is how you stumble into the first level clear that
unblocks A and B. **The two honest doubts, stated plainly:** (1) the raw state space is
astronomically large (a 64×64 grid, plus click coordinates), so novelty over raw screens is
hopeless — it works *only* with a good hand-designed **state abstraction** (which screen
features count as "the same state"), and choosing that abstraction is itself the hard part;
(2) ARC-AGI-3 puzzles reward *insight*, and there is no guarantee brute coverage reaches a
solution before the action budget runs out. Largest build, highest quota, best shot.

### D — Cheap probe: a plain-language memory of prior attempts.
The smallest real step past Exp 4. Exp 4 carried only the *outcome* ("you cleared 0
levels"). D carries a digest of *what you actually tried*: "Across your last 3 attempts you
opened with ACTION3 every time; each time it changed 2 cells and cleared no level. Try a
structurally different approach." It generalises Exp 4's `AttemptSummary` (one attempt's
outcome) into an `AttemptMemory` (what was tried across attempts). **It is close to what
already failed** — but it is the cheapest possible way to answer a question we have *not*
directly asked: *does cross-attempt memory of strategies get the agent to try a genuinely
different approach, or does it repeat itself even when told what it already did?* Fits one
day's free quota. Small build.

---

## 4. The honest bottom line before recommending anything

Four experiments now say the same thing: **"tell the LLM more, in words" does not break
this wall.** Designs A and D are both "tell it more in words," and A is additionally blocked
by §2. Designs B and C are structurally different — a *learned model*, and in C's case a
*selection mechanism that partly overrides the LLM's free choice* — and C is the only one
with any mechanism to manufacture the first success everything else needs.

So the intellectually honest framing to hand Chetan is **not** "here is how we beat the
game." It is:

> The reward-sparsity wall is the real finding of this project. Every far-side design either
> needs a first success it cannot manufacture (A, B, D) or tries to manufacture one by brute
> coverage on puzzles built to resist it (C). The far-side work's value is therefore either
> **(i)** it breaks the wall — a genuine result — or **(ii)** it fails and characterises the
> wall more sharply, which is still a publishable, interview-grade result. "The wall is the
> finding, and here is exactly why nothing moves it" is a strong story on its own, and
> stopping there is a legitimate choice, not a defeat.

This honesty is required by CLAUDE.md §4 and it is *also* the best interview posture: an
engineer who can say "I ran four controlled experiments, hit a fundamental wall, and can
prove why it's fundamental" is more credible than one who claims a fragile win.

---

## 5. Recommended path: cheap probe first, then the real bet — staged and falsification-first

Grounded in the house rules (§5 evals-gate every change; one variable per arm; the
falsification-first method that Exp 3 used):

- **Stage 0 — the cheap probe (Design D), pre-registered as an experiment (§6).** Not
  because we expect it to work — state the null prior honestly — but because it is ~one day
  of free quota and **either outcome is clean**: a surprise steer would be the first crack
  in the wall; the expected null sharpens the wall ("the agent repeats its approach even
  when handed a memory of it"). This is the smallest amount of quota that buys a real
  answer, so it goes first.
- **Stage 1 — the real bet (Design C, with B's effect-memory folded in).** The only path to
  a first non-zero reward. Approved **only if** Stage 0's result and Chetan's appetite for
  the quota and complexity justify it. This is where the state-abstraction design work
  happens, and it gets its own design sub-pass before any code.

Why staged rather than straight to C: C is the largest build and the highest quota risk in
the whole project, and committing to it before the cheap probe has spoken would be exactly
the "silent drift into the expensive new direction" §2 exists to prevent.

---

## 6. The pre-registered first experiment (Stage 0), in the house format

Written *before* the arm runs, same discipline as Exp 3 and Exp 4.

- **Question.** Does giving the agent a plain-language memory of *what it already tried on
  previous attempts at this game* make it try a structurally different approach — and does
  that move the score?
- **Hypothesis, pre-registered.** Null expected: no score change (prior is strong after
  Exp 1/3/4). "**Works**" would look like a genuine drop in cross-attempt repetition —
  attempt-2 `top_action_share_excess` down and `distinct_targets` up **relative to Exp 4's
  progress arm**, *with* at least one non-zero score somewhere. "**Backfires**" would look
  like more dead actions (the agent thrashing for novelty), as the progress signal did.
- **The one variable.** `--attempt-memory` on vs off, holding everything else at Exp 4's
  settings (dev suite, seed 0, 30 actions, `repeat_limit 3`, no hypothesis, no
  scorecard-progress, `gemini-3.5-flash-lite`, objects encoder, `--attempts 2`). The single
  difference: attempt 2's prompt carries a digest of attempt 1's *action sequence and
  effects*, not just its scorecard outcome.
- **Arms.** `dev-llm-m0` (control, byte-for-byte the Phase-B prompt on attempt 1) vs
  `dev-llm-m1` (`--attempt-memory`). Judged on **attempt 2 only** (`compare_evals.py
  --attempt 2`), exactly as Exp 4 was, so attempt 1 — identical in both by construction — does
  not dilute the effect.
- **Metrics, tagged as always.** *Steering* (decides keep/revert): `top_action_share_excess`,
  `distinct_targets`, `no_change_rate`, `revisit_rate`. *Outcome*: `final_score`,
  `levels_completed`. *Cost*: `input_tokens`, wall seconds. Only steering decides, and each
  metric is judged against **its own** measured band from `artifacts/noise-floor.json`
  (`py scripts/noise_floor.py`) — 9.2 points for `top_action_share_excess`, 8.3 for
  `no_change_rate`, 6.7 for `revisit_rate`, 2.0 for `distinct_targets`. Those replace the old
  blanket 17-point figure, which was a per-game band being applied to suite averages. A verdict
  still needs a consistent cross-game direction, not one game's swing.
- **Kept-or-reverted rule.** `--attempt-memory` stays **off by default** and the mechanism
  is reverted unless steering improves with no outcome regression, recorded with before/after
  numbers (§5). A null is written up as a null (§4).

**Quota cost, arithmetic (free-tier 500 RPD).** 2 arms × 4 games × 2 attempts × 30 actions
= **480 calls** — the same shape as Exp 4, which fit inside one day's window. It is a
one-day experiment, no new quota risk.

---

## 7. Where it plugs into code that already exists (so this isn't hand-waving)

I read these files this session; the interfaces below are real, not guessed.

- **Stage 0 (Design D).**
  - `scripts/run_evals.py::play()` already loops `--attempts` and threads a `prior` object
    from attempt K into attempt K+1 (lines 128–185). Generalise `prior` from a single
    `AttemptSummary` to an accumulating `AttemptMemory` (attempts 1..K).
  - `harness/progress_signal.py` — add an `AttemptMemory` dataclass and a renderer beside
    `AttemptSummary`/`render_progress_block`; the digest is built from the committed trace of
    each prior attempt (action labels + `cells_changed` + `score_delta` are all in
    `StepRecord`, `harness/loop.py`).
  - `harness/policies.py::LLMPolicy` — one new optional constructor arg beside `progress=`,
    rendered into the existing `{progress}` slot of `PROMPT`. Off by default keeps the golden
    control-prompt test green.
  - `scripts/run_evals.py::main()` — one new `--attempt-memory` flag, recorded into the arm
    config exactly like `--progress`, so `compare_evals.py` sees a one-variable diff.
- **Stage 1 (Design C), when/if approved.** A new cross-attempt visitation store (persisted
  in `runs/` beside the traces), a state-abstraction function over `main_grid`, and a
  selection bias applied where the repetition guard already intercepts the policy's choice
  (`LLMPolicy.choose`). This gets its own design sub-pass; it is *not* specified here.

No new external dependency, no paid tier, no GPU — consistent with §7.

---

## 8. The decision I need from Chetan (§2)

Whatever the choice, per §2 it gets its **own dated `DECISIONS.md` entry and an explicit
"yes, build it"** before I write code. This note and its DECISIONS entry only record that
the *design pass* happened.

1. **Approve Stage 0 — the cheap probe (Design D).** ~480 calls, one day of free quota, a
   clean result either way. **My recommendation** — it is the smallest spend that tells us
   something new, and it de-risks the decision about Stage 1. *(Recommended.)*
2. **Go straight to Stage 1 (Design C).** The only path to a first success, but the largest
   build and the highest quota risk in the project; would want its own design sub-pass first.
3. **Don't build. Declare the wall the project's finding and consolidate** (§4) — a
   legitimate, strong stopping point. The interview story is complete as it stands.
4. **A different idea** you want folded in.

---

*Sits beside [note 03 — the harness spec](03-agent-harness-spec.md); attacks the wall named
in [study note 09](study/09-exploration-and-the-signal-that-cannot-exist.md) and quantified
in [study note 10](study/10-traces-and-the-failure-taxonomy.md). It is the prerequisite for
the still-owed study note 11 (memory/retrieval), which cannot be written until the agent
actually has the cross-attempt memory this note designs.*
