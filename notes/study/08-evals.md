# Study 08 — Evals: making the comparison a habit instead of an event

*Written 2026-07-22, the day the eval suite was built. Every number here comes from a file
in this repo you can regenerate: `artifacts/evals/*.json` (built by `scripts/run_evals.py`),
`artifacts/model-bakeoff.json` (by `scripts/model_bakeoff.py`), and the four run reports in
`artifacts/` (rebuilt by `scripts/analyze_run.py` from the recordings in `runs/`). The code
was run: 89 tests pass offline, and every arm below was played against the live server.*

> **You are here:** rung 8. Part 2, the engineering.
> **Assumes you read:** [07](07-baselines-and-controlled-experiments.md) (baselines and one
> controlled experiment). One line so you're not stranded: a *baseline* is a deliberately
> simple version — ours presses buttons at random — whose only job is to be the number you
> compare against, and we found that the game's **score** stays at zero no matter what we
> do, so it cannot tell us whether a change helped.
> **After this you can:** say what an eval suite is and why every serious AI team has one,
> explain the dev/held-out split and why touching held-out data is the one unforgivable
> mistake, describe how you choose a metric when the obvious one is broken, and — the parts
> that actually land in an interview — tell the story of a metric you designed, ran, and
> found was measuring nothing, and of an experiment you ran, disproved, and reverted.

---

## The question this note answers

Note 07 gave you one comparison: two runs, side by side, one number that moved.

That was an **event**. You set it up by hand, you ran it, you read it, you wrote it down.

Now imagine you want to try twenty ideas. Different prompts, different ways of describing
the screen, different models, more memory, less memory. Doing note 07's dance twenty times
by hand means you will do it carefully three times, sloppily five times, and then stop.

::: key
An **eval** (short for *evaluation*) is a fixed, repeatable test of how well a system does
a job. An **eval suite** is a set of them run together with one command, producing a table
of numbers that any change can be judged against.
:::

The word "fixed" is carrying the weight. If the test changes when the system changes, the
numbers are not comparable, and you have measured nothing.

::: example
Think of a school exam. If every student sits the same paper, the marks rank the students.
If each student gets a paper written specially for them, the marks rank nothing at all —
even though every student still gets a number out of a hundred.
:::

---

## Part 1 — What goes in the suite

### Why more than one game

Our agent plays ARC-AGI-3 games. We could judge every change on `ls20`, the game we have
played since day one.

We should not, and one measurement from today shows exactly why. Here is how many buttons
each of our four test games offers the agent (from `available_actions`, the list the server
sends with every frame — see note 04):

| game | buttons the agent may press |
|---|---|
| `ar25-0c556536` | 7 |
| `ls20-9607627b` | 4 |
| `sb26-7fbdac44` | 3 |
| `tn36-ef4dde99` | **1** |

These are not four flavours of the same problem. `tn36` is a game where the only legal move
is a mouse click, so the agent's whole decision is *where* to click. `ls20` is a game with
four buttons and no clicking at all. A prompt tuned until it shines on `ls20` may be useless
on `tn36`, and if `ls20` is your only test, you will never find out.

::: key
**Overfitting** (making something good at your test rather than good at the job) is the
permanent risk. More than one test case is the cheapest defence there is.
:::

### The dev set and the held-out set

Now a harder idea, and the one interviewers press on.

You are going to run these games over and over, tweaking as you go. After twenty rounds,
you have not just improved your agent — you have *learned the games*. You have seen which
ones are easy, which prompt wording happens to work on which puzzle. Your suite has stopped
being a test and become a training exercise.

::: key
So the games are split in two.

- The **dev set** (development set) is what you iterate on. Run it as often as you like.
- The **held-out set** is games you do not touch while developing. You run them once,
  at the end, to report a number.

The held-out number is the honest one, because nothing you did was shaped by it.
:::

::: warn
Tuning on held-out data — even once, even a little — is the one mistake that invalidates
everything. Every number you then report is a number you already optimised for, and you
have no way to know how much. This project's rules call it "the one unforgivable sin", and
that is not hyperbole (exaggeration): it is the failure that makes published results wrong.
:::

Our split, from `harness/evals.py`:

- 25 games exist on the server.
- **4 are the dev set**, **6 are held out**, 15 are reserve (we cannot afford to run them;
  see note on budget below).
- The split is made by shuffling the sorted list with a **published seed** (`20260722`),
  so anyone can reproduce it and nobody can accuse us of hand-picking easy games.

And one honest exception, written into the code:

::: warn
`ls20` is **pinned to the dev set** — not chosen, pinned. Every baseline number in this
project was measured on it, so we have already studied it. Putting it in the held-out set
would let us report a game we had been staring at for two days and call it "held out". That
is a confession in the code, not a design.
:::

We also enforce the rule mechanically. `scripts/run_evals.py --suite heldout` **refuses to
run** unless you also pass `--report`, and stamps `heldout_touched: true` into the artifact
when you do.

::: key
A rule that lives only in someone's good intentions is a rule that gets broken at 1 a.m. by
a tired person who is *sure* it's fine just this once. Put the rule in the code.
:::

---

## Part 2 — What you measure, when the obvious thing is broken

### Score is dead, and that is the interesting part

The obvious metric is the game's score. Note 07 explains why we cannot use it: score was 0
for the stock baseline, 0 for our improved loop, 0 at 80 actions and 0 at 400 actions —
eighteen times the number the game's own reference solution needs for level one.

::: key
A metric that reads 0 before your change and 0 after it is not a metric. It is a constant.
You can tune against it forever and learn nothing, because every experiment "succeeds"
equally at doing nothing.
:::

So we need signals that move **before** the agent starts winning. And the moment you start
inventing metrics, you need a rule about what they are *for*.

### Three kinds of number

Every number in our suite is tagged as one of three kinds, and the tag decides what it is
allowed to do:

::: key
- **Steering** — dense signals that move early. **A change is kept or reverted on these.**
- **Outcome** — score, levels completed. **Reported always, steered on never.** The day one
  of these moves is the day the project has a result.
- **Cost** — wall-clock time, model calls, tokens, time asleep on the rate limit. A change
  that improves steering by tripling the bill is a *trade*, not a win.
:::

Why bother separating them formally? Because of a specific trap: it is easy to make the
steering numbers beautiful in a way that quietly destroys the real goal. Force the agent to
press a different button every turn and "repetition" drops to zero — and the agent gets
worse. Keeping outcome in the same table, with no better/worse arrow next to it, is what
makes that visible instead of celebrated.

Our comparison tool prints them in exactly these three blocks, and refuses to put a
better/worse verdict on an outcome row at all.

### The steering metrics, and what each one catches

| metric | plain meaning |
|---|---|
| illegal-action rate | how often the agent asked for a button that doesn't exist |
| no-change rate | how often the screen was byte-identical after the action |
| revisit rate | how often it landed on a screen it had already seen |
| favourite-action **excess** | how much more repetitive it is than a coin flip would be |
| longest repeat streak | the longest run of pressing the same thing |
| distinct targets | how many *different* actions (click positions included) it tried |
| level-1 ratio | actions spent on level one ÷ the server's own reference for level one |

That last one deserves a note. When you close a scorecard, the ARC-AGI-3 server tells you
how many actions a reference solution needs for each level — for `ls20`, `[22, 123, 73, 84,
96, 192, 186]`. So "the agent spent 29 actions and did not finish level one, which a
reference solution does in 22" is a **densely informative** statement even though the score
is still zero. It is progress measured in someone else's units, and it works on every game
because the server publishes those reference counts for all of them.

---

## Part 3 — Two ways my metrics were wrong, which is the real lesson

This is the part to remember, because it is the part that is true of every measurement job
you will ever do.

### Mistake 1: I built a metric from a story, and the story was wrong

Yesterday's LLM run failed in a memorable way: it pressed `ACTION3` for 57 of its 80
actions, 41 of them in a row, writing a fresh justification each time. The loop's
"nothing changed" alarm never fired, because the screen *was* changing.

So I reasoned: the agent must be oscillating (swinging back and forth) between two screens.
Screen A, screen B, screen A, screen B. Cells change every turn, nothing progresses. The
fix seemed obvious — **fingerprint each screen and count how many you have seen before.**
That is the "revisit rate" above. I wrote it, tested it, and pointed it at the failing run.

**It read 0%.** All 80 screens were different. Every single one.

Digging into the recording showed what was really happening: a two-cell marker on the
bottom row of the screen, at rows 61–62, stepping one column to the right with each press.
Column 42, then 43, 44, 45… up to 54, then a large change, then starting again from column
16. Every screen genuinely was new. The agent was not going back and forth. It was pressing
a button that moved a little bar and did nothing else, forty-one times.

::: warn
A metric invented from a story about a failure is a **guess** until you run it against the
failure. Mine was a good guess, carefully implemented, fully tested — and blind to the exact
problem it was written for.
:::

I kept it anyway, with its limits written into the code, because when I ran it against all
four of our recorded games it turned out to measure something real:

| metric | stock SDK baseline | our loop, random | our loop, **LLM** |
|---|---:|---:|---:|
| illegal-action rate | 47.5% | 0% | 0% |
| no-change rate | 47.5% | 0% | 0% |
| **revisit rate** | **46%** | **0%** | **0%** |
| longest repeat streak | 2 | 4 | **41** |
| favourite-action share | 20% | 27% | **70%** |

Revisit rate cleanly separates the stock baseline (46% — its illegal actions bounced it
back to the same screen every time) from our loop (0%). It is a real measurement of a real
thing. It just is not a measurement of *being stuck*.

The two that caught the stuck agent are the last two rows: **41 versus 2–4**, and **70%
versus 20–27%**. Ten times and three times the baseline. Those are not subtle.

### Mistake 2: the metric that caught it was comparing apples to nothing

Then I ran the random baseline across all four dev games, and it reported this:

> `tn36-ef4dde99` — favourite action **99%** of the time, longest identical streak **61**.

By the numbers above, that is the worst stuck-loop in the entire project — worse than the
LLM's 70% and 41 — produced by a policy that flips a coin and has no opinions at all.

The reason is in the table at the top of this note. **`tn36` offers exactly one legal
action, in all 81 frames.** There is nothing else to press. A 99% favourite-action share
there means "the game has one button", not "the agent is stuck".

::: key
The fix is to subtract what pure chance would score on that specific game:

**excess = (share of the favourite action) − (1 ÷ number of buttons available)**

On `tn36`: 99% − (1 ÷ 1) = **0**. Perfectly normal play.
On `ls20` for the stuck LLM: 70% − (1 ÷ 4) = **+45%**. Genuinely stuck.
:::

Same raw number, opposite meanings, and the difference is a property of the *game*, not of
the agent. This is the general shape of a **confound** (something that varies alongside what
you are measuring and corrupts the comparison), and it is worth internalising: a metric
that is meaningful within one test case is not automatically meaningful across several.

The same problem bites in a second way on `tn36`. Every action there is `ACTION6`, so
"how many different actions did it try?" is always 1, no matter how widely it clicks. That
is why the suite also counts **distinct targets** — different actions *including their
coordinates* — which is the only number that can tell exploring from stabbing at one spot.

---

## Part 4 — Two small rules that keep the arithmetic honest

### Pool the rates; never average the percentages

Suppose game one runs 90 actions and every one is illegal. Game two runs 10 actions and all
are fine.

- **Averaging the per-game rates:** (100% + 0%) ÷ 2 = **50%**.
- **Pooling:** 90 illegal ÷ 100 total = **90%**.

The first lets a ten-action game cancel out a ninety-action disaster. We pool, and there is
a test named after this so nobody quietly changes it back.

### One arm, one variable

A **run of the whole suite with one configuration** is called an **arm** (borrowed from
clinical trials — the treatment arm, the control arm). Every arm writes down its exact
configuration, and the comparison tool prints the *difference between the two configurations*
before it prints any result.

::: warn
If more than one setting changed between two arms, the tool prints **NOT AN EXPERIMENT**,
because no difference in the results can be attributed to any single one of them. The
number would still look perfectly convincing, and it would be worthless.
:::

---

## Part 5 — What a suite costs, and the third thing that went wrong

Evals are not free, and on a free tier the cost shows up as *time* and as a daily cap.

Yesterday's budget work picked the model for this suite by arithmetic. Free tiers publish
three limits: requests per minute, input tokens per minute, and **requests per day**. The
open `gemma-4-31b-it` allows **14,400 requests a day** against Flash-Lite's **500** — which
at one model call per game action is 180 games a day versus 6. It was not close, so Gemma
was chosen, with the decision recorded as provisional "pending a quality bake-off".

Today the first eval arm was launched on it. It stopped on the first move of the first
game and sat there for twenty-five minutes at **zero CPU**.

Two separate faults, and both are worth knowing:

**Fault one: no timeout.** The call to the model had no time limit set, so a request that
never comes back stops the entire suite — forever, silently, looking exactly like a slow
run from the outside.

::: key
Any call that leaves your process — to a model, a database, another service — needs a
**timeout** (a maximum time to wait before giving up). Without one, "it's still running"
and "it will never finish" look identical, and you cannot tell which you have.
:::

The fix is one setting, and it converts an infinite hang into the loss of a single turn:
the failure is captured, the agent falls back to a legal action, the episode continues, and
the trace records what happened. That is the same shape as every other guard in note 05 —
*don't crash, don't hide it, count it.*

**Fault two, the real one: the model does not answer.** With the timeout in place, the
truth came out. Here is the bake-off (`scripts/model_bakeoff.py`, which sends every
candidate the *same real game prompt* built by the agent's own prompt builder):

| model | answered | median | usable action | requests/day |
|---|---:|---:|---:|---:|
| `gemma-4-31b-it` | **0 of 3** | — | 0 of 3 | 14,400 |
| `gemma-4-26b-a4b-it` | **0 of 3** | — | 0 of 3 | 14,400 |
| `gemini-3.5-flash-lite` | 3 of 3 | 828 ms | 3 of 3 | 500 |
| `gemini-3.1-flash-lite` | 3 of 3 | 761 ms | 3 of 3 | 500 |

Gemma answers `"Reply with exactly the word: ready"` in about three seconds. Given a real
1,464-character game prompt it returns `504 DEADLINE_EXCEEDED` and then stops responding
altogether. Its 14,400 daily requests are real and completely worthless.

::: warn
**A rate limit is a promise about requests you are allowed to make, not about requests
that will be served.** The dashboard cannot tell you the second thing. Neither can a smoke
test with a toy prompt — that is exactly what made this invisible for a day. Only the real
prompt, at its real size, tells you anything.
:::

So the eval model is `gemini-3.5-flash-lite`, and the suite has to fit inside **500
requests a day**. One arm is 4 games × 30 actions = 120 calls; an A/B is two arms, 240.

That is where the numbers in this note come from, and it is why episodes here are 30
actions long while the runs in note 07 were 80.

::: key
Notice what just happened to the design: the daily cap of a free API decided how long an
episode is allowed to be. Constraints propagate. In an interview this is a good thing to
be able to trace out loud — cost limit → episode length → what the metric can detect —
because it shows you know your numbers are shaped by something, and which something.
:::

::: note
The history window was sized the same way. Adding the agent's last 8 actions to the prompt
costs **+14%** input tokens (747 → 851 on a real `ls20` frame, counted with the model's own
tokeniser). A window of 16 costs +28%. The window was picked by measuring the price, not by
taste.
:::

---

## Part 6 — The first experiment, and it failed

Everything above is apparatus. Here is what it was built to do, used once.

### First, where we stand: is the LLM better than a coin flip?

Four dev games, 30 actions each, same loop, same guards. This is **not** an experiment —
four settings differ between these two columns, so nothing can be attributed to any one of
them — but it is the reference you need before reading anything else.

| metric | random | LLM |
|---|---:|---:|
| illegal-action rate | 0% | 0.8% |
| no-change rate | 20% | **9.2%** |
| revisit rate | 18.3% | **7.5%** |
| **favourite-action excess** | **+4.4%** | **+36.9%** |
| longest streak (games with a choice) | **3** | **26** |
| distinct targets | 13.5 | 10.75 |
| level-1 ratio | 1.23 | 1.22 |
| wall-clock per arm | 65 s | 522 s |

Read that honestly and it says three things at once. The LLM's actions **land** better —
half as many dead actions, a third as many revisited screens. It is also **eight times more
repetitive than chance** where random is essentially at chance, with a 26-action streak
against random's 3. And it makes **exactly as much progress into level one as random does**,
for eight times the wall-clock.

::: key
"Better on some metrics, worse on others, no better on the goal" is a completely normal
result and you must be able to say it without flinching. The wrong move is to quote the
two rows that flatter you.
:::

### The experiment: give the agent its own recent history

The stuck-loop diagnosis from note 07's follow-up was that the agent cannot see its own
repetition — it gets one screen and one last action per turn, and from there pressing the
same button again is a reasonable answer. Forty times in a row is only absurd if you can
see the other thirty-nine.

So: **one variable.** Add the agent's last 8 actions and what each one did. Nothing else
changes — same model, same encoder, same games, same seed, same 30 actions.

| metric | history 0 | history 8 | |
|---|---:|---:|---|
| illegal-action rate | 0.8% | 0% | better |
| no-change rate | 9.2% | **17.5%** | worse |
| revisit rate | 7.5% | **23.3%** | worse |
| favourite-action excess | +36.9% | **+46.9%** | worse |
| longest repeat streak | 26 | **30** (the whole episode) | worse |
| distinct actions tried | 2.5 | **1.75** | worse |
| distinct targets | 10.75 | **4.75** | worse |
| level-1 ratio | 1.215 | 1.226 | worse |
| — outcome: score | 0 | 0 | — |
| — cost: input tokens | 103,162 | **117,824** | +14.2% |
| — cost: usable replies | 90% | 97.5% | better |

**It made things worse on seven of the ten steering metrics, and cost 14% more tokens to do
it.** The one clear gain — 90% to 97.5% usable replies — is real but small, and it is not
what the change was for.

::: warn
The change is **reverted**. `history` stays in the code, defaulting to 0, because the
result is about *this* history format on *this* model and a different format may behave
differently. But it does not become the default on the strength of a hypothesis that the
numbers just refused.
:::

### Why it backfired, which is the useful part

Look at what the history block actually says after eight presses of the same button:

```
  -8: ACTION3 -> 2 cells changed
  -7: ACTION3 -> 2 cells changed
  ...
  -1: ACTION3 -> 2 cells changed
```

I read that as *"you are stuck, do something else."* The model read it as *"this action
reliably works."* Eight consecutive confirmations that the button does something are
**evidence for pressing it again**, and the model said so in its own words during the run:

> *"Extending the green bar at the bottom right to connect the elements."*
> *"Continuing the sequence to progress the puzzle mechanics."*

The "green bar at the bottom right" is the two-cell marker from Part 3 — the thing that
moves one column per press and means nothing. The agent had built a theory that moving it
*is* the goal, and the history block handed it eight pieces of supporting evidence per turn.

::: key
**Memory of your actions is not the same as feedback about your progress.** I gave the
agent the first and expected the second. The history says *what happened*; it contains no
signal for *whether it helped*, and with score frozen at zero there is nothing in the
prompt that could supply one.
:::

That reframes the next experiment. Adding more memory will not fix this. What is missing is
a **progress signal** — something the agent can read that distinguishes "the screen changed"
from "I am closer to the goal". That is a harder problem than a prompt tweak, and knowing
which of the two you have is worth more than the eight hours it would take to find out by
tweaking.

---

## Say it in an interview

**"Tell me how you evaluate your agent."**
> "The suite is a fixed set of games, split into a dev set I iterate on and a held-out set
> I don't touch, with the split made by a published random seed so it can't be hand-picked.
> Every number is tagged as steering, outcome, or cost. Changes are kept or reverted on the
> steering numbers; outcome — the score — is reported in the same table but never steered
> on, so a change that games the steering metrics and wrecks the score can't hide. One
> command runs an arm and writes a JSON artifact; a second command diffs two arms and
> prints what configuration actually changed between them before it prints any result."

**"Why not just use the score?"**
> "Because I measured it and it's a constant. Zero for the baseline, zero for the improved
> loop, zero at 80 actions and zero at 400 — and 400 is eighteen times what the game's own
> reference solution needs for level one. A metric that reads zero before and after can't
> referee anything. So the steering signals are denser things that move earlier: illegal
> actions, dead actions, repetition above chance, and actions spent inside level one against
> the server's published reference count for that level. Score stays in the report as the
> outcome, because the day it moves is the day I have a result."

**"Tell me about a metric that didn't work."** *(the strongest answer you have)*
> "I built one that was blind to the exact failure I built it for. The agent had pressed one
> button 41 times in a row, and the loop's 'nothing changed' check never fired because the
> screen was changing. I assumed it was oscillating between two states, so I fingerprinted
> every screen and measured how often it revisited one. Ran it against the failing recording
> — zero percent. All eighty screens were distinct. What was actually happening was a
> two-cell marker sliding one column along the bottom row with each press, so every screen
> was technically new while the agent went nowhere. I kept the metric, because it turned out
> to separate the stock baseline at 46% from my loop at 0%, but I wrote its limits into the
> code. The lesson I took is that a metric invented from a story about a failure is a guess
> until you run it against the failure — and I had a recording on disk to run it against,
> which is the only reason I found out in an hour instead of after a week of tuning."

**"Any measurement traps you hit?"**
> "A confound across test cases. My repetition metric flagged the random baseline as the
> worst stuck-loop in the project on one game — 99% of actions were the same one, a
> 61-action identical streak. Then I looked at that game's available-actions list: it offers
> exactly one legal action in every frame. The agent had no alternative. So I subtract the
> uniform-random expectation for each game — the observed share minus one over the number of
> legal buttons — and that reads zero on the one-button game and plus 45 points on the
> genuinely stuck one. Same raw number, opposite meanings, and the difference belongs to the
> game rather than the agent."

**"How do you stop yourself from cheating on the held-out set?"**
> "I don't rely on discipline for it. The runner refuses to execute against the held-out
> suite unless you pass an explicit `--report` flag, and it stamps a `heldout_touched` field
> into the artifact when you do, so the file itself records that the set was used. The
> contaminated game is handled the same way — `ls20` is pinned into the dev set in code with
> a comment saying why, because every baseline in the project was measured on it and calling
> it held-out would be a lie."

**"Tell me about an experiment that didn't work."** *(the other strong answer)*
> "My agent was pressing the same button dozens of times in a row. My hypothesis was that it
> couldn't see its own repetition — each turn it gets one screen and one last action, and
> from that position pressing again is reasonable. So I added its last eight actions to the
> prompt and A/B'd it: one variable, same model, same games, same seed. It got worse on
> seven of ten steering metrics — the repetition-above-chance measure went from plus 37 to
> plus 47 points, the number of distinct things it tried more than halved, and it cost 14%
> more tokens. I reverted it. What I got out of it was the reason: the history block shows
> eight lines saying 'this action changed two cells', and I read that as 'you're stuck' while
> the model read it as 'this action reliably works'. It's eight pieces of evidence *for*
> pressing the button again. Memory of your actions isn't feedback about your progress — I
> gave it the first and expected the second. So the next thing I build isn't more memory,
> it's a progress signal, and I'd rather learn that from one measured experiment than from a
> week of prompt tweaking."

**"Tell me about a time your infrastructure choice was wrong."**
> "I picked the model for my eval suite on published rate limits. One model allowed 14,400
> requests a day against the alternative's 500 — 180 games a day versus six — so it wasn't a
> close call. Then the first eval arm hung on the first move and sat at zero CPU for
> twenty-five minutes. Two bugs: I hadn't set a timeout on the model call, so an
> unanswered request stalls forever and looks identical to a slow one. And once the timeout
> was in, the real problem showed: that model answers a two-word test prompt in three
> seconds and answers my actual 1,500-character game prompt zero times out of three — 504
> from the server, then nothing. Its daily quota is real and worthless. What I took from it
> is that a rate limit is a promise about requests you may *make*, not requests that will be
> *served*, and the only way to learn the difference is to send the real payload. I wrote
> the bake-off as a script that sends every candidate the agent's actual prompt, so the next
> model decision is thirty seconds of measurement instead of a day of reading dashboards."

**"Isn't four games too small?"**
> "Yes, and I'd say so rather than defend it. It's bounded by the free tier: one arm is 320
> model calls, the token-per-minute limit binds before the request limit, so an arm spends
> most of its wall-clock asleep on the rate limiter. Four games is the largest suite I can
> run twice in an evening, which is what an A/B needs. If I had budget, the first thing I'd
> spend it on is more games and multiple seeds per game, in that order — more games attacks
> overfitting, more seeds attacks noise, and right now overfitting is the bigger risk."

---

**Next:** note 09 — traces: how you answer "*why* did it do that?" for any single action the
agent ever took, with receipts. It gets written when the failure taxonomy exists, because a
note about an unbuilt thing is guesswork.
