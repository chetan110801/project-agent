# Study 07 — Baselines: how you know a change helped

*Written 2026-07-22, the day the agent first played real games through our own code. Every
number here comes from a file in this repo that you can regenerate:
`artifacts/comparison.json` (built by `scripts/compare_runs.py` from the three recordings
committed in `runs/`) and `artifacts/ourloop-random-400.json`. The code was run: 42 tests
pass, and three real games were played.*

> **You are here:** rung 7. Part 2, the engineering.
> **Assumes you read:** [05](05-the-agent-loop.md) (the loop and its guards) and
> [06](06-context-engineering.md) (what we feed the model). One line so you're not
> stranded: our loop refuses to send an action the game says isn't available, and the
> stock baseline didn't.
> **After this you can:** say what a baseline is and why a result without one means
> nothing, describe a controlled experiment you ran with its real numbers, explain the
> difference between an improvement you *measured* and one that's true *by construction*,
> and — the part interviewers actually listen for — report a fix that worked and still
> didn't win.

---

## The question this note answers

You change something. The agent scores 3 instead of 2. Did your change help?

You cannot tell. Maybe the game was easier that day. Maybe the model happened to guess
well. Maybe your change did nothing and something else moved.

::: key
A **baseline** is a deliberately simple version of the thing, run under the same
conditions, whose only job is to be the number you compare against. Without one, "our
agent scored 3" is not a result. It's a sentence.
:::

This is not an AI idea. It is the **control group** (the group that gets no treatment, so
you can see what the treatment actually did) from a drug trial, under a different name.

---

## Our baseline, and why it's a coin flip

Ours is `RandomPolicy` — it presses a button at random. It is *meant* to be bad.

Two design choices in it are worth more than they look:

**1. It is seeded.** A *seed* (starting number for the random generator) means the same
seed always produces the same sequence of "random" choices.

::: warn
An unseeded baseline gives a different number every run. Then "we beat the baseline"
can never be proved wrong — and a claim that can't be wrong isn't worth making. The
official SDK's random agent seeds itself from the clock. Ours takes the seed as an
argument.
:::

**2. It only picks from the actions the game says are available.** Hold that thought; it's
the whole experiment.

---

## The experiment

The setup, in one line: **same game, same kind of policy, same action budget — one
difference.**

| | run 1 | run 2 |
|---|---|---|
| who played | the SDK's stock random agent | our loop, random policy |
| game | `ls20` | `ls20` |
| action budget | 80 | 80 |
| the difference | picks from all 8 buttons | picks only from the available ones |

Everything else is held still. That is what **controlled** (all else kept equal) means: if
the numbers differ, there is only one thing they can differ *because of*.

### The result

| | SDK baseline | our loop |
|---|---|---|
| actions that weren't available | **38 of 80 (47.5%)** | **0 of 80 (0%)** |
| actions that changed nothing | 38 of 80 (47.5%) | 0 of 80 (0%) |
| **final score** | **0** | **0** |

Nearly half the baseline's budget went on buttons that did not exist. Every one of those
38 actions changed nothing on screen — the wasted actions and the dead actions are the
same 38 actions. Our loop recovers all of it.

And the score is still zero.

---

## Two kinds of "it improved", and why the difference matters

::: key
The 47.5% → 0% is **true by construction**, not measured from a sample. The filter *cannot*
emit an unavailable action; there is no world in which it emits one and no run that could
come out differently. The measurement only confirms the code does what it says.
:::

Compare that to the score. Score is a *measured* quantity, it varies from run to run, and we
have exactly **one run each** — what statisticians write as *n = 1*, a sample of one. From
one run you can honestly say "still zero" and nothing more. You cannot say the guard didn't
help the score; you can only say it didn't visibly.

Being able to tell these two apart in your own results is most of what **rigour** (being
strict about what your evidence actually supports) means in practice.

::: warn
**An honest weakness in this experiment.** The two runs used different streams of random
numbers, so they didn't send the same actions — only the same *kind* of agent. That
difference is a **confound** (a second thing that changed, so you can't be sure which one
caused the result). Here it doesn't damage the 47.5% claim, because that effect is built
into the code rather than observed in a sample. But if I were comparing two things whose
effect was statistical — two prompts, say — this design would be too weak, and I would need
many runs with matched seeds on both sides.
:::

---

## The follow-up: was the budget the real problem?

A fair objection: 80 actions is just too few. Maybe the agent never had a chance.

So we asked the game. When you close a scorecard, the server sends back a breakdown per
level — including how many actions a **reference solution** (someone who knows how to play,
solving it properly) needs for each one. This was hiding in plain sight: the official
library's data model doesn't declare those fields, so it quietly returns them as empty, and
nobody using it would ever see them.

```text
ls20 has 7 levels
reference actions per level : [22, 123, 73, 84, 96, 192, 186]   (776 in total)
our 80-action run           : [80,  0,  0,  0,  0,   0,   0]    levels completed: 0
```

Read the second row: all 80 of our actions were spent on level 1, and it was never
finished. Level 1 takes **22 actions** done properly. So we ran it again with **400** —
eighteen times what level 1 needs.

**Result: 0 of 7 levels completed. Score 0.** (`artifacts/ourloop-random-400.json`.)

That settles it. The budget was never the blocker. The *policy* is. Random play stays alive
in this game for a surprisingly steady stretch — it died at actions 129, 260 and 392, so it
survived 129, 131 and 132 actions between deaths — and our loop noticed each `GAME_OVER`
and reset and carried on. It stays alive; it just never solves anything, because `ls20`
needs directed play, not luck.

::: key
This is the most valuable thing the session produced, and it is a negative result: **the
metric we planned to steer by is dead.** Score is 0 for the baseline and 0 for the improved
version, at 80 actions and at 400. A number that cannot move cannot tell you whether your
next change was good.
:::

---

## What a dead metric forces you to do

If score won't move, you need signals that will — measurements that respond *before* the
agent starts winning. We already have four, all recomputed from the recordings:

- **actions that weren't available** — did the agent obey the rules? (47.5% → 0%)
- **actions that changed nothing** — is it flailing (doing a lot, achieving nothing)?
- **`GAME_OVER` count** — is it dying, and does it recover?
- **actions spent inside level 1** vs the reference 22 — is it *getting closer* to a solve?

That last one is the real target for the next phase. "Levels completed" is what we're
judged on; "how far into level 1 did you get" is what we can *steer* by.

::: note
**This is why measurement design comes before tuning.** If we'd started tweaking prompts
now, every experiment would have returned "score 0 → score 0" and we'd have learned nothing
from any of them, slowly.
:::

---

## One rule that makes any of this trustworthy

Both runs are measured by **the same script** (`scripts/analyze_run.py`), reading recordings
written in the **same format**, and the comparison table is generated by a script
(`scripts/compare_runs.py`) rather than typed by hand.

That sounds like unnecessary care. It isn't:

::: warn
If run A is scored by one piece of code and run B by another, then part of the difference
you measured is a difference between your two **measuring instruments** (the tools doing the
measuring), and you cannot tell which part is which.

And this session made a cruder version of the same mistake, for real: analysing a throwaway
test run silently overwrote the committed baseline report that three of these notes quote
from. It was restored from Git within the minute, but nothing had warned me — so the
analyser now refuses to overwrite a report that was made from a different recording. A
number's provenance (where it came from) is worthless if the file holding it can be replaced
by a stray command.
:::

---

## Say it in an interview

> "The first thing I built after the loop was a baseline, and the first real result was a
> controlled comparison against it. Same game, same random policy, same 80-action budget —
> the only difference was that my loop filters actions against the availability list the
> server sends in every frame. The stock baseline wasted 38 of its 80 actions on buttons
> that didn't exist, which is 47.5% of the budget, and those were exactly the 38 actions
> that changed nothing on screen. My version wastes zero. The score stayed at zero for
> both, and I report that just as loudly, because a fix that removes waste isn't the same
> as a fix that wins."

**"How do you know the improvement is real?"**
> "There are two different claims there and I'd separate them. The 47.5% to 0% is true by
> construction — the policy cannot select an action outside the available set, so it isn't
> an estimate, the run just confirms the code does what it claims. The score is a measured
> quantity and I have one run each, so all I'm entitled to say is 'still zero'. I'd need
> many runs with matched seeds before claiming anything statistical, and my baseline is
> seeded precisely so those runs are reproducible."

**"So the guard was pointless?"**
> "No — it bought back 47% of the budget, and budget is the scarce resource. But I tested
> whether budget was the *binding* constraint and it wasn't. The scorecard exposes a
> per-level reference: seven levels, and level one is solvable in 22 actions. I gave the
> random policy 400 — eighteen times that — and it still completed zero levels. So the
> ceiling is the decision-making, not the budget. That's the result that told me where to
> spend the next week."

**"What did that change about your plan?"**
> "It killed my planned metric before I built anything on it. Score is zero on both sides
> at every budget I tried, so it can't tell me whether tomorrow's change helped. I switched
> to denser signals that move earlier — illegal-action rate, no-change rate, deaths, and
> actions spent inside level one against that 22-action reference. Designing the
> measurement before doing the tuning is the whole reason I found this now instead of after
> a week of prompt tweaks that all read 'zero to zero'."

**"Anything surprise you in the data?"**
> "The vendor's own SDK was dropping it. The per-level reference counts come back when you
> close a scorecard, but their response model doesn't declare those fields, so validating
> the response through it returns an object with the interesting parts silently empty — and
> a computed score of zero that isn't the server's zero. I keep the raw JSON and validate
> what I need myself. Trusting a client library's schema to be a complete description of
> its own API is a good way to never see the number that matters."

---

**Next:** note 08 — evals: turning these one-off comparisons into a suite that runs on every
change, with a dev set you tune on and a held-out set you don't. It gets written when the
suite exists, because a note about an unbuilt thing is guesswork.
