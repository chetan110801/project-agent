# The recursion-depth ablation — experiment design

*Drafted 2026-07-21, before any run. Written down now so we can't quietly move the
goalposts later — that's what a pre-registration is for.*

## Question

TRM improves its answer by looping: draft an answer, reconsider, redraft — up to 16
supervised improvement steps at training time. The paper reports results at one depth.
**How does accuracy change as that depth is cut: 16 → 8 → 4 → 2?**

Two live hypotheses, and the curve decides:

- **Graceful:** accuracy declines smoothly — thinking depth substitutes for size, and
  you can trade it for compute at inference.
- **Cliff:** accuracy holds then collapses below a critical depth — recursion isn't
  "more of the same," some minimum number of passes does qualitative work.

Either answer is publishable as a small honest result. The curve does not currently
exist in public.

## The knob (to pin down exactly in Phase 1, against the repo config)

TRM has three nested loop counts: `H_cycles` and `L_cycles` (reasoning passes inside
one improvement step) and the **max number of supervised improvement steps** (the
paper's "up to 16," ACT/halting-controlled). The headline ablation varies the
improvement-step cap: **16 / 8 / 4 / 2**. `H_cycles=3, L_cycles=4` and everything else
stays at the paper's Sudoku config. Exact config-key names get confirmed from the
forked repo before run 0 — this file then records them.

## Protocol

- Task: Sudoku-Extreme, paper's dataset build (`--subsample-size 1000 --num-aug 1000`).
- **Equal budget per depth**: identical optimizer steps, batch size, schedule, and data
  for every arm. If quota forces a shorter budget than the paper's full run, *all* arms
  shrink identically and the write-up says so — the curve's *shape* is the claim, not
  the absolute numbers.
- One seed per arm first (4 runs); repeat seeds only if the quota allows and the
  curve's shape is ambiguous.
- Metric: exact-accuracy on the held-out test split, evaluated once per arm at the end.
  No peeking at test during training; model selection (if any) on the validation split
  only.
- Every arm logs: config, seed, git commit of the fork, wall-clock GPU hours,
  final checkpoint.

## What would break the result (named in advance)

- **Confound:** deeper recursion = more compute per optimizer step. Equal *steps* is
  not equal *FLOPs*. We report both step-matched and (if affordable) a FLOP-matched
  spot-check at one depth; the write-up discusses the difference rather than hiding it.
- **Halting interaction:** ACT may learn to stop early anyway, making depth caps
  non-binding. We log the *realized* average depth per arm; if 16 and 8 realize the
  same depth, the top of the curve is a null result about the cap, not about depth.
- **Single-seed noise:** flagged in the write-up if we can't afford repeats.

## Deliverable

One plot (accuracy vs. depth, with realized-depth annotations), one page of prose:
question, setup, curve, what we now believe that we didn't before.
