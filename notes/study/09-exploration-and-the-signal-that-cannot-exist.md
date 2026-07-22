# Study 09 — Exploration: why the agent got stuck, and the signal that cannot exist

*Written 2026-07-23. Every number here comes from a file in this repo you can regenerate:
`artifacts/progress-signals.json` (built by `scripts/progress_signals.py` from the
recordings in `runs/`) and `artifacts/evals/*.json` (built by `scripts/run_evals.py`).
The code was run: 109 tests pass offline, and the experiment below was played against the
live server.*

> **You are here:** rung 9. Part 2, the engineering.
> **Assumes you read:** [08](08-evals.md) (evals). One line so you are not stranded: an
> **eval suite** is a fixed set of games plus a fixed set of measurements, run with one
> command, so any change to the agent can be judged in numbers instead of opinions — and
> ours splits those numbers into *steering* (dense signals we tune on), *outcome* (the
> score, which never moves) and *cost*.
> **After this you can:** explain what *exploration* means and why it is the hard part of
> any agent working in a world it was not told the rules of; describe how you diagnose
> (work out the cause of) an agent failure from recordings instead of guessing; and — the
> part that lands in an interview — explain a measurement that proved an idea was
> impossible, not merely bad, and what you built instead.

---

## Where we left off

Our agent plays a puzzle game it has never been told the rules of. It sees a screen, picks
one of a few buttons, sees the new screen, picks again.

It has one glaring (very obvious) fault, measured twice:

::: key
Given 80 turns, the agent pressed **the same button 41 times in a row**. It wrote a fresh
sentence of justification (reason) each time. Random button-pressing repeats itself at most
**3** times in a row.
:::

Note 08 covered the first attempt to fix that: show the agent its own last eight actions,
so it can *see* the repetition. It was A/B tested — one change, measured before and after —
and it made things **worse** on 7 of 10 steering metrics. We reverted it.

The reason it failed was the useful part. Eight lines saying *"ACTION3 → 2 cells changed"*
read to us as *you are stuck*. They read to the model as *this action reliably works*.

So we wrote down what we thought we had learned:

> Memory of your actions is not feedback about your progress. We supplied the first and
> expected the second. **The next experiment is a progress signal.**

This note is about what happened when we tried to build that progress signal. The short
version: **it cannot be built**, and finding that out cost a few seconds of computing time
instead of a week.

---

## Part 1 — What a "progress signal" would even be

A **signal** here just means: a short piece of text we put into the agent's prompt
(the instructions it reads before choosing) that tells it something it cannot see for
itself.

The agent already gets three:

| What it sees | Example |
|---|---|
| the screen | *"grid 64x64, background 4, 37 objects: colour 9: filled rect 2x1 at rows 61-62…"* |
| its last action | *"ACTION3"* |
| what changed | *"2 cells changed: (r61, c42) 4→9; (r62, c42) 4→9"* |

Look at that last row and you can see the hole. It says **something happened**. It does not
say **whether that was any good**.

::: key
A **progress signal** would be a line in the prompt that says: *the last few things you did
added up to something* — or did not. Not "the screen changed". "You are getting somewhere."
:::

Normally you get this for free, from the **score** — the game's own number saying how well
you are doing. Ours is stuck at 0 and has never moved, in any run, at any length. Note 07
measured that: 400 random actions, eighteen times what the game's own reference solution
needs for level 1, and the score was still 0.

So the score cannot supply it. The question of this note is: **can we compute a progress
signal ourselves, out of the screens alone?**

---

## Part 2 — The rule we made ourselves obey first

In note 08 there is a story worth repeating in one sentence, because this whole note is
built on top of it.

::: warn
We once invented a measurement from a *story* about a failure — "the agent is bouncing
between the same two screens" — shipped it, and only afterwards ran it against the
recording of that very failure. It read **0%**. It had been blind to the thing it was
invented for.
:::

That produced a house rule, and this session is the rule being obeyed:

::: key
**A signal invented from a story about a failure is a guess until it is run against the
failure.** Test it on the recordings you already have, *before* it goes anywhere near a
model.
:::

That is only possible because of a decision made much earlier: **every run is recorded to
disk** — every screen, every action, every result, kept in the repository. The stuck run
from the day the agent first got stuck is still there. So a new idea can be tested against a
real failure that already happened, for free, in seconds, with no risk and no quota spent.

::: example
This is worth saying out loud in an interview: *"I could test my next four ideas against a
failure from a week ago, because I had recorded it."* Recording runs is boring
infrastructure. It is also what turns "I think this would help" into "I checked".
:::

---

## Part 3 — Four candidate signals, in plain words

Four different ways to answer *"is this agent getting anywhere?"* from screens alone. Each
one looks back over the last **N** actions (we swept several values of N — more on that
below).

**1. Novelty — "have I seen this screen before?"**
Count how many of the last N screens were brand new. An agent going round in circles should
keep landing on screens it has already been to.

**2. Composition — "has the make-up of the screen changed?"**
Count how many cells of each colour there are. If a marker just slides around, the counts
stay the same even though the picture differs.

**3. Activity area — "am I only ever touching one small corner?"**
Draw the smallest box that contains every cell that changed in the last N actions, and
measure how much of the screen that box covers. A stuck agent should be poking at a tiny
region.

**4. Churn ratio — "is my work adding up?"** *(the one I believed in)*
Two numbers. **Total change**: add up every cell that changed on every one of the last N
turns. **Net change**: compare the screen now against the screen N turns ago and count how
many cells differ.

::: key
**Churn** (*churn* = movement that produces nothing) is `net ÷ total`.
If you paint 20 fresh cells over 10 turns and all 20 are still painted, net = total = 20,
and the ratio is **1.0** — your work accumulated (built up).
If you flip the same two cells back and forth 10 times, total = 20 but net = 0, and the
ratio is **0.0** — you are on a treadmill.
:::

I was confident about number 4. It is general, it is cheap, and it says exactly the thing
the prompt was missing. Then we ran it.

---

## Part 4 — The result: all four failed, and the best one failed backwards

Here is the churn ratio measured on every recording we have of the game `ls20`, at six
different look-back windows. Lower is supposed to mean *worse* — work undoing itself.

| look-back window (actions) | 5 | 10 | 20 | 30 | 40 | 60 |
|---|---:|---:|---:|---:|---:|---:|
| **random button-pressing** | 0.359 | 0.233 | 0.158 | 0.131 | **0.116** | 0.114 |
| **the stuck agent** | 0.681 | 0.538 | 0.334 | 0.194 | **0.136** | 0.122 |

Read the two rows again. **At every single window, the stuck agent scores higher — better —
than random button-pressing.**

It gets worse. Inside the stuck agent's own 41-action streak, churn reads **0.650**; outside
it, **0.336**. By this measurement the agent was doing its *best* work exactly while it was
failing.

The other three failed too. Novelty was the most embarrassing: the stuck agent reached a
brand-new screen on **100%** of its actions, against random play's 80.6%. By that measure
the stuck agent was the better explorer.

::: warn
Four candidate signals, four failures, and the most promising one pointed the **wrong way**.
Had I skipped the offline check and gone straight to the prompt, I would have shipped a line
that congratulates the agent precisely when it is stuck.
:::

---

## Part 5 — Why. The bit that changes how you think about agents

The recordings say exactly what happened, action by action. During the long streak, each
press changed **2 cells**, and those 2 cells were *new every time*.

The agent had found a bar on the screen it could make longer. Each press added two cells to
the end of it. Nothing was undone. Nothing was revisited. It was, by any local measurement
you care to name, doing **perfect, accumulating work**.

We know it was pursuing the bar deliberately, because the agent writes down its reason for
every action and we keep them. (That file is called a **trace** — a line-by-line record of
what the agent did and why. Note 10 is about traces; for now it is just "the receipts".)
From the 80-action run:

> *"Continuing the sequence to progress the puzzle mechanics."*

And from a later run under the current prompt, where the theory is stated outright:

> *"Extending the green bar at the bottom right to connect the elements."*

The bar meant nothing. It was not the goal. It filled up, wrapped around, and started again.

::: warn
Note that second quote is from a **different run** than the stuck one, under a different
prompt. The agent invents the same wrong theory about the bar in more than one
configuration. It is not a one-off; it is what this model does on this game.
:::

::: key
The agent was not stuck in a loop. It had **guessed the goal wrong** and was pursuing its
wrong guess competently. There is no arrangement of pixels that tells you the difference,
because *"is this the goal?"* is not a property of the screen.
:::

And that is why this signal cannot exist:

::: key
**Progress is measured against a goal. If you do not know the goal, no statistic computed
from the screen can tell progress from busywork** — it can only tell activity from
stillness. The score is the one thing that knows the goal, and ours is frozen at zero.
:::

Both of our previous diagnoses were wrong, and the recordings said so:

| Diagnosis | What we believed | What the data said |
|---|---|---|
| first guess | "it cannot see its own repetition" | showing it made things worse |
| second guess | "it needs a progress signal" | every candidate is blind or backwards |

The real fault has a name.

::: key
**Premature commitment** (*premature* = too early): the agent formed one theory about what
the game wants, acted on it, and never tested another. Its theory was never contradicted,
because nothing in the game ever contradicts anything — it just does not reward you.
:::

---

## Part 6 — Exploration, and the fix that follows from the real diagnosis

This is one of the oldest problems in the subject, and it has a standard name.

::: key
**Exploration** = trying things you are unsure about, to learn what they do.
**Exploitation** = repeating the thing you currently believe is best.
Every agent must trade one off against the other. Too much exploitation and you spend forty
turns extending a meaningless bar. Too much exploration and you never finish anything.
:::

Our numbers say precisely which side we are on. Measured over the four games of the dev set,
30 actions each:

| | random | our LLM agent |
|---|---:|---:|
| repetition above chance | +4.4 points | **+36.9 points** |
| longest identical streak | 3 | **26** |
| progress into level 1 | 1.23 | 1.22 |

Read the last row first, because it is the humbling one: **the LLM makes exactly as much
progress as random button-pressing**, at eight times the wall-clock (real elapsed time) cost.
And it does it while being roughly **eight times more repetitive than chance**.

So the fix is not more feedback. It is to stop the agent committing so hard.

::: key
**The repetition guard.** After the agent plays the same action a set number of times in a
row, the harness *refuses* that action for one turn. The prompt tells the model it is
blocked, the model picks something else, and if it insists anyway the code overrules it.
:::

Two details make it engineering rather than a hunch.

**The threshold came from the baseline, not from taste.** How many repeats should we allow?
We counted, across every recording we have: a *random* player exceeds three-in-a-row on
**0–2%** of its moves. On the three dev games where a guard can fire at all, our LLM exceeds
it on **30%, 57% and 77%**. So the cap is set at three:

> **You may repeat an action as often as a coin flip would.**

That is a rule with a reason attached. A guard tuned tighter would start punishing ordinary
play; this one provably cannot, because chance almost never triggers it.

**It bans the exact action, not the button.** On games where the action is *click at a
square*, clicking four different squares is exploring and clicking the same square four
times is the failure. So the guard compares the full action including its coordinates.

**And it can never leave the agent with nothing to press.** One of our four dev games offers
exactly **one** legal button, so there repetition is forced, not chosen — the guard is
written so it cannot fire when the ban would leave no alternative. There is a test named
after that game.

::: example
There is a phrase from note 05 that keeps earning its place: **a prompt is a request; a
guard is a guarantee.** We tell the model the action is blocked *and* we enforce it in code.
The first makes a good answer likelier. The second makes a bad answer harmless.
:::

---

## Part 7 — What happened when we ran it

One arm of the eval suite: 4 dev games, 30 actions each, 120 model calls, against the
identical setup with the guard switched off. One variable moved.

| what we measured | guard off | guard on | |
|---|---:|---:|---|
| longest identical streak | 26 | **3** | better |
| repetition above chance | +36.9 pts | **+17.7 pts** | better |
| different actions tried | 2.5 | 3.25 | better |
| different targets tried | 10.75 | 12.25 | better |
| actions that changed nothing | 9.2% | 11.7% | worse |
| screens revisited | 7.5% | 10.0% | worse |
| **score** | **0** | **0** | — |
| tokens spent | 103,162 | 104,376 | +1.2% |

**We kept it**, and the reason for keeping it despite two red rows is worth learning as a
pattern: both red rows come from **one game out of four**. On that game the agent, denied its
favourite button, tried alternatives that did nothing. That is the trade we bought on
purpose — paying 2.5 points of dead actions to stop losing 26 turns in a row to one button —
and the eval suite makes it a *visible* trade instead of a hidden one.

::: warn
**The headline is not the win.** The score is still 0, and level progress did not move. The
guard did exactly what it was designed to do and **the agent is no better at the game.** If
you only report the green rows you have learned nothing except how to write a good-looking
table.
:::

Two smaller things fell out of the run, and both are the kind of detail interviewers dig for.

**The model obeyed every single time.** The guard has two halves — a sentence in the prompt
saying the action is blocked, and code that overrules the model if it does it anyway. The
code fired **0 times out of 120**. The agent complied with the sentence, and said so:
*"ACTION2 was blocked after 3 consecutive uses, so I must switch to ACTION1."* We kept the
enforcement half anyway. One obedient run is not a guarantee, and the difference between a
request and a guarantee is the whole reason we write guards.

**One game gave us a free measurement of noise.** On the fourth game the guard never fired at
all, in either arm — the agent clicked 27 different squares in 30 moves, so it never repeated
itself three times. Its prompt was therefore unchanged between the two runs. And its count of
replies we could not read still moved from **9 to 14 out of 30**.

::: key
A metric that moves in a game where your change never fired is **noise**, not an effect. That
one number is the first honest sense of how much of a single run's difference is just the
model rolling different dice — and it is why "5 metrics improved" is a weaker claim than it
looks when each game is played only once.
:::

One last thing to be honest about: this guard is not the agent getting smarter. It is the
*harness* compensating for the agent. That is the project's thesis rather than a confession —
the engineering around the model is the part you control — but it should be said in those
words, not dressed up.

---

## Say it in an interview

**"Tell me about a time you disproved your own idea."**
> "My agent kept pressing one button forty times in a row. I was sure the fix was a progress
> signal — a line in the prompt saying 'your last ten actions added up to nothing'. Before
> writing it I tested four candidate versions of it against the recordings of the failure I
> already had on disk. All four failed, and the one I believed in failed backwards: the stuck
> agent scored *better* than random button-pressing at every look-back window I tried, and
> inside its own stuck streak it scored better than outside it. The recordings showed why —
> the agent had found a bar it could extend by two cells a press, so its work was
> accumulating perfectly. It was just extending the wrong thing. That is when it clicked
> that progress is defined against a goal, and if you do not know the goal, no statistic
> over the screen can separate progress from busywork. The whole check cost a few seconds of
> CPU because I had recorded every run."

**Follow-up: "So what did you build instead?"**
> "I re-diagnosed it. The agent was not stuck in a loop — it was committing to one theory of
> the goal and never testing another, which is an exploration failure, not a feedback
> failure. So I put a repetition guard in the harness: after N identical actions in a row,
> that exact action is blocked for a turn — stated in the prompt and enforced in code. I set
> N from the baseline rather than by taste: a random player exceeds three-in-a-row on under
> two percent of its moves and my LLM on thirty to seventy-seven percent, so the rule is
> 'you may repeat as often as a coin flip would', and it provably cannot punish normal play."

**Follow-up: "Did it work?"**
> "On what it was built to fix, yes and by a lot: the longest identical streak went from 26
> to 3 and repetition-above-chance halved, from plus 37 points to plus 18, for one percent
> more tokens. On whether the agent plays better — no. Score stayed at zero, level progress
> didn't move. I kept it, because two of the three metrics that got worse came from a single
> game where the agent, denied its favourite button, tried things that did nothing, and
> that's the trade I meant to make. But I report it as 'the guard works and the agent is not
> better yet', because the alternative is a table full of green rows that means nothing."

**Follow-up: "How do you know that improvement isn't noise?"**
> "Partly I don't, and I can put a number on my uncertainty. One of the four games never
> triggered the guard at all — the agent clicked 27 different squares in 30 moves, so it never
> repeated three times, which means its prompt was identical in both arms. Its count of
> unreadable replies still moved from 9 to 14 out of 30. So a game where my change was
> provably inactive still swung by 17 points, which tells me single-seed differences of that
> size are within noise. The streak going from 26 to 3 is far outside it and is anyway true
> by construction. If I had more free quota I'd spend it on multiple seeds per game before
> anything else."

**Follow-up: "Isn't that just hard-coding around a weak model?"**
> "Yes, and I would say so plainly. It is the harness compensating for the agent, not the
> agent improving. I would rather have a measured guard than an unmeasured belief that a
> better prompt fixes it. It is the same pattern as the illegal-action guard earlier in the
> project, which recovered 47.5% of the action budget for one line of code — the model asks,
> the harness guarantees."

**Follow-up: "How would you get a real progress signal?"**
> "It has to come from something that knows the goal, so it cannot come from the screen. The
> options I would rank are: the server's per-level action counts, which we only get when the
> scorecard closes, so it is an after-the-fact signal, not an in-prompt one; getting the
> agent to state a hypothesis and what would disprove it, so a wrong theory is falsifiable
> instead of self-confirming; or a novelty-seeking objective, which rewards reaching states
> unlike anything seen before and does not need a goal at all. I would try the second next,
> because it attacks the diagnosis directly and costs only prompt tokens."

**Follow-up: "What if you'd shipped the progress signal without checking?"**
> "I would have shipped a line that congratulates the agent exactly when it is stuck, and
> then spent a week tuning the wording of a sentence that was pointing the wrong way. That is
> the second time on this project a measurement I invented from a story about a failure
> turned out to be blind to that failure. The first time I found out afterwards. This time I
> found out before it reached a model, which is the only real difference between the two,
> and it is entirely down to keeping the recordings."

---

**Next:** note 10 — traces: how you answer "*why* did it do that?" for any single action the
agent ever took, with receipts. It gets written when the failure taxonomy exists, because a
note about an unbuilt thing is guesswork.
