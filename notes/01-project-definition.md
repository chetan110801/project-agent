# Study note 1 — What this project is, and why it exists

*Written 2026-07-21. Plain language on purpose: if you can't say it simply, you don't understand it yet.*

---

## The decision (locked 2026-07-21)

This project is **not an app**. It is the first real research work of your AGI/ASI path
(project-asi), packaged so it also works as a portfolio piece for data-science and
applied-science interviews.

Two steps, in order:

1. **Reproduce a tiny reasoning model and run an experiment its authors never published.**
   The Tiny Recursion Model (TRM) has only 7 million parameters — thousands of times
   smaller than models like Gemini — yet it beats much larger models on a famous
   reasoning test called ARC-AGI-1. We rebuild it on free Kaggle GPUs, confirm the
   published score, then measure something the paper skipped: **what happens to accuracy
   as you cut the model's "thinking depth" from 16 steps to 8 to 4?** That curve doesn't
   exist publicly. Producing it is a small but genuine contribution.

2. **Build an agent for ARC-AGI-3.** This is the newest version of the benchmark: an AI
   is dropped into a small game world with *no instructions, no rules, no stated goal* —
   it has to figure everything out by trying things, like a child with a new toy. Humans
   solve 100% of these. The best frontier model scores under 1%. Hand-built agents score
   ~13× better than the frontier model. We build one and put it on the public Kaggle
   leaderboard (open-source milestone deadline: 30 September 2026).

Timeline: flexible. Step 1 is roughly two weeks of work; it can stretch or shrink.
Each step is complete and showable on its own.

---

## Why this, in one story

There are two ways to get better scores on a hard reasoning test:
**spend more money** (bigger models, more compute per question) or **have better ideas**.

In 2026 the field split along exactly that line. On ARC-AGI-2 — a puzzle test built so
that memorizing the internet doesn't help — the leaderboard that allows ~$10,000 per run
is now above the average human score. The leaderboard that caps cost at cents per task
sits around 24%. Same test, 3.5× apart. The ARC Prize Foundation's own words: the
accuracy gap is now bottlenecked by *engineering*; the efficiency gap is still
bottlenecked by *science and ideas*.

You have no compute budget. So the money-bound side of the field is closed to you — and
the ideas-bound side is wide open, **because on that side, spending more money is against
the rules**. A 7M-parameter model that trains on a free GPU beating giants is the
existence proof that small players can still do real work there.

That is why this project is on the *efficiency frontier* and not another LLM app:
it is the one part of the AGI problem where your situation is not a handicap.

---

## The timeless ideas you'll actually learn (and be interviewed on)

These are the things that will still matter in ten years, whatever happens to today's
tools. Each gets its own study note as we hit it.

1. **Generalization vs. memorization.** Why ARC puzzles are designed so that having seen
   the whole internet doesn't help, and why that's the honest definition of learning.
   This is *the* core concept of machine learning, and most candidates can't explain it.
2. **Test-time compute — thinking longer instead of being bigger.** TRM loops over its
   own draft answer up to 16 times. The same idea, at giant scale, is what "reasoning
   models" like o3 do. One principle, two extremes.
3. **The ablation — how scientists find out *why* something works.** Change one thing
   (recursion depth), hold everything else fixed, plot the curve. This is the daily bread
   of applied-science roles, and our Step 1 is one honest ablation done end-to-end.
4. **What a benchmark can and cannot tell you.** Two leaderboards, same test, opposite
   conclusions — a live lesson in reading evaluation numbers critically.
5. **Exploration — learning with no instructions.** Step 2's agent must act to find out
   what the world even is. Explore-vs-exploit is a forever-concept (it predates AI).
6. **The research loop.** Question → ground it → shrink it until it runs → run it →
   write what happened → update your beliefs. This is how research works at any scale,
   from 30 GPU-hours to 30,000.

**What we deliberately do NOT make a study topic:** CI pipelines, observability vendors,
web frameworks. Claude builds that plumbing where useful; it is not what you're here to
learn. The *idea* behind it — "results must be reproducible and checked automatically,
because wishful thinking is the default failure mode of research" — is timeless, and
that idea is the only part that goes in your notes.

---

## How we'll know it's real (rigor, stated timelessly)

- **A reproduction target:** the paper's published number. If we can't get close, we say
  so and investigate — that is a result too.
- **A held-out test:** we never tune on the data we score on. (This single sentence
  kills half of all bad data science.)
- **One-command reruns:** anyone — including an interviewer — can re-run the evaluation
  and get our number. Every claim in the write-up traces to a run.
- **A written record:** every experiment ends in a short page — question, setup, result,
  what we now believe that we didn't before. Negative results get written up with the
  same care.

---

## The plan (phases, not dates)

| Phase | What happens | Done when |
|---|---|---|
| **0 — Verify the ground** | Re-check today's facts before relying on them: TRM code availability, ARC-AGI-1 data, Kaggle quota, ARC Prize 2026 rules and the Sept 30 milestone | A short note listing each fact as confirmed / changed |
| **1 — Reproduce** | TRM training on ARC-AGI-1, free Kaggle GPUs | Our score is in the paper's ballpark, from a clean rerun |
| **2 — The missing curve** | The recursion-depth ablation (16 → 8 → 4), same setup otherwise | A plot + write-up: does thinking-depth substitute for size gracefully, or fall off a cliff? |
| **3 — Publish piece #1** | GitHub repo (Chetan creates it), README that tells the story, study notes complete | A stranger can understand and re-run it |
| **4 — The agent** | ARC-AGI-3 agent: explore, remember, form and test hypotheses about the world's rules | On the public leaderboard; aiming at the 30 Sept open-source milestone |

---

## Facts that must be re-verified before Phase 1 (they are dated 2026-07-21)

- TRM: arXiv 2510.04871, 45% on ARC-AGI-1 / 8% on ARC-AGI-2 at 7M parameters.
- Kaggle free quota: 30 GPU-hours/week, T4/P100.
- ARC Prize 2026: ARC-AGI-3 track, $75K open-source milestone, deadline 2026-09-30,
  submissions via Kaggle, code must be open-sourced.
- ARC-AGI-3 state of play: best frontier model 0.37%, best purpose-built agent ~12.6%.

*(Numbers move. The reasoning above is built to survive them changing; the numbers are not.)*

---

## The interview pitch (draft — will improve as results arrive)

> "A 7-million-parameter model beats reasoning models a thousand times its size on
> ARC-AGI-1, by recursing on its own answer instead of being big. I reproduced it
> end-to-end on free GPUs, then published the ablation the paper didn't: the
> accuracy-vs-thinking-depth curve. Then I used what that taught me to build an agent
> for ARC-AGI-3 — the benchmark where humans score 100% and frontier models under 1% —
> and put it on the public leaderboard. Every number I just said, you can re-run."
