# Study 10 — Traces, and the failure taxonomy: answering "why did it do that?"

*Written 2026-07-28. Every number here comes from a file in this repo you can regenerate:
`artifacts/failure-taxonomy.json` (built by `scripts/failure_taxonomy.py` from the committed
traces in `runs/`). The code was run: 154 tests pass offline, four of them new and named after
this note. The trace format quoted is `harness/trace.py` and `harness/loop.py`, read straight
from the files.*

> **You are here:** rung 10. Part 2, the engineering.
> **Assumes you read:** [00](00-how-to-use-these-notes.md)–[09](09-exploration-and-the-signal-that-cannot-exist.md).
> One line so you are not stranded: across four experiments the agent's behaviour changed four
> times and its **score never moved** — it is stuck at 0, and note 09 named the wall (nothing in
> the loop can turn feedback into a better-chosen next action).
> **After this you can:** say what a *trace* is and what *observability* means; read the record
> of a single decision the agent made; and — the part that lands in an interview — present a
> **failure taxonomy**, a counted catalogue of how the agent wastes its turns, and use it to say
> the wall as a single number instead of a story.

---

## Where we are

Nine notes in, we have an agent that plays, an eval suite that judges it, and a wall we can
describe in words: it acts with purpose toward a goal it never worked out. This note is about
the machinery that let us *see* all of that — and then turns "the agent is bad" into a table
with counts.

Two words first, because the whole note hangs on them.

::: key
A **trace** is the complete record of one operation — what went in, what came out, how long it
took, what it cost. For one turn of our agent: the exact action it chose, whether that action
was legal, what changed on screen, the score, how long the call took, and **the model's own
stated reason** for the choice.

**Observability** is the property of a system you can inspect from the outside well enough to
explain its behaviour. Traces are the mechanism; observability is the goal. "Why did it do
that?" gets an *answer* instead of a guess only if the answer was written down at the time.
:::

---

## Part 1 — One decision, as a receipt

Our loop writes one line per decision to a file, in a format called **JSONL** (*one JSON object
per line*). The format is not an accident (`harness/trace.py`):

::: key
JSONL is **append-only and survives a crash.** A run that dies on action 57 still leaves 56
readable records; a single big JSON array would leave one unparseable file. Every decision goes
through the same writer, so the eval suite and the failure taxonomy read *the exact record the
agent acted on* — they cannot quietly drift from what really happened.
:::

Here is what one turn records (`StepRecord` in `harness/loop.py`), in plain terms:

| Field | What it answers |
|---|---|
| `action` | *what* it did — e.g. `ACTION3` or `ACTION6(x=12,y=40)` |
| `accepted` | was that action legal in this frame? (if not, the loop rejected it and forced RESET) |
| `cells_changed` | how much of the screen changed afterwards (`0` = nothing; `-1` = not comparable) |
| `score_delta` | did the score move? (it never has) |
| `screen_hash` | a fingerprint of the resulting screen — *have we been here before?* |
| `legal_options` | how many buttons were legal when it chose (so "pressed one button 99%" is readable) |
| `latency_ms` | how long the model took |
| `reasoning` | **why** — the model's own words for the choice |

That last field is the one that turns a log into an explanation. Without it a trace says *what*
the agent did; with it, the trace answers *why*. Two real lines pulled from our recordings make
the point — the agent, mid-failure, explaining itself:

> *"Extending the green bar at the bottom right to connect the elements."*
> *"Continuing the sequence to progress the puzzle mechanics."*

The "green bar" is the two-cell marker from note 06 that slides one column per press and means
nothing. We only *know* the agent had adopted a wrong theory of the goal — rather than merely
mashing a button — because the reasoning was on the receipt. That is observability doing its
job: the failure is legible, not guessed.

::: note
This is also why the ARC-AGI-3 API itself carries a 16 KB `reasoning` blob on every action
(note 04): the people who built the benchmark expected serious agents to explain themselves.
We fill it, and we keep our own copy in the trace.
:::

---

## Part 2 — From one trace to a taxonomy

One trace explains one decision. But an experiment produces thousands: the committed traces hold
**2,071 classified actions across 46 episodes**. Nobody reads 2,071 actions by hand and comes
back with a fair summary. You need to *count*.

::: key
A **failure taxonomy** (*a sorted catalogue of the distinct ways a thing fails, with counts*)
is what converts "the agent is bad" into the counted sentence Part 4 arrives at — "88% of its
actions are purposeful activity that makes no progress, 12% do nothing at all, and repetition is
gone." Note 02 called it "the single most impressive thing a junior can bring to an interview,"
and this is why: each named bucket becomes a fix to try and an eval case to guard it.
:::

`scripts/failure_taxonomy.py` reads every committed trace and drops each action into exactly
**one** bucket — the first one it qualifies for, so the shares partition the actions and sum to
100%. Most-specific waste first, the catch-all last:

| Bucket | The action was… |
|---|---|
| `illegal_action` | not a legal button — the loop rejected it and forced a RESET |
| `dead_action` | legal, but the screen was byte-identical afterwards (it did nothing) |
| `revisit` | legal and it changed something, but landed on a screen already seen this game |
| `perseveration` | legal, changed, new screen — but the **4th-or-later identical action in a row** |
| `active_no_progress` | legal, changed, a fresh screen, not repetitive — **and still no score** |
| `progress` | the score went up |

::: note
**Two thresholds set by measurement, not taste.** *Perseveration* starts at the **4th** identical
action because note 09 measured that random play's longest streak is 3 and it exceeds
three-in-a-row on under 2% of moves — so the fourth is the first repetition chance essentially
never produces. And `revisit` uses the `screen_hash` fingerprint, whose known limit (note 08)
is why it is *not* the whole story: a marker sliding one column makes a screen technically new,
so a stuck agent can revisit nothing while going nowhere. That failure lives in the catch-all,
by design.
:::

---

## Part 3 — The rule: run the classifier against a failure you already understand

Note 08 has a scar this note refuses to reopen: a metric invented from a *story* about a failure
("the agent is bouncing between two screens") read **0%** on the very recording of that failure,
because the story was wrong. The house rule that came out of it:

::: key
**A classifier of failures is a guess until it is run against a real failure.** So the taxonomy
is pointed at the recording we understand best: the 80-action run where the agent pressed one
button **41 times in a row** (notes 05, 08, 09). If `perseveration` did not dominate there, the
bucket would be wrong.
:::

It does. On that run — found automatically as the episode with the longest identical streak, not
hand-picked — the taxonomy reads:

| the stuck run (80 actions, longest streak 41) | share |
|---|---:|
| perseveration | **60%** |
| active_no_progress | 40% |
| everything else (illegal / dead / revisit / progress) | 0% |

The classifier sees exactly the failure the notes have described for a week. That is the whole
of its licence to be trusted on runs we have *not* stared at.

---

## Part 4 — What the taxonomy says about the agent as it stands

Now the payoff. Here is the current default agent — guards on, no hypothesis prompt, no progress
signal (arm `eval-dev-llm-r3`), the configuration every default settled on — across the four dev
games, 30 actions each:

| the current agent (120 actions) | share |
|---|---:|
| `active_no_progress` | **88%** |
| `dead_action` | 12% |
| `illegal_action` / `revisit` / `perseveration` | 0% |
| **`progress`** | **0%** |

::: key
**This is the wall from note 09, as a single number.** Nearly nine in ten of the agent's actions
are *legal, non-repetitive, screen-changing activity that moves the score not at all.* Not
flailing, not stuck in a loop, not pressing dead buttons — **purposeful-looking work toward a
goal it never identified.** The taxonomy does not just confirm the wall; it says how much of the
agent's behaviour *is* the wall.
:::

And it shows the earlier fixes working, in one table. Watch perseveration move as the guards go
in (each arm is one configuration, 30 actions × 4 games unless noted):

| arm | what changed | perseveration | active_no_progress | dead |
|---|---|---:|---:|---:|
| `h0` | guards off (baseline LLM) | **41%** | 50% | 8% |
| `h8` | + its own 8-action history | **53%** | 22% | 18% |
| `r3` | + repetition guard (current default) | **0%** | 88% | 12% |
| `y1` | + falsifiable-theory prompt | 0% | 87% | 12% |
| `p1` | + after-the-fact progress signal | 0% | 72% | **20%** |

Read it top to bottom and it is the whole story of notes 08–09 in one column:

- **History made repetition worse** (41% → 53%): the eight-line history read to the model as
  "this action reliably works," exactly as note 08 found.
- **The repetition guard did what it was built to do** (53% → 0%). But look where those actions
  *went* — into `active_no_progress` (22% → 88%). The guard did not make the agent play better;
  it **relocated** the wasted motion from "same button" to "different buttons, same nowhere."
- **The progress signal raised dead actions** (12% → 20%): told to "do something different," the
  agent pressed a wider set of buttons, and more of them did nothing — note 09's "adverse on
  wasted-motion," now visible as a bucket shifting.

::: warn
The `progress` column is **0% in every row**, including the baseline random agent (`active` 89%,
`dead` 8%, `perseveration` 1%). Every intervention rearranged *how* the agent wastes turns; none
moved a single action into `progress`. If you only showed the shrinking perseveration column you
would be telling the flattering half of a true story — the same mistake note 09 warns against.
:::

Per game, the buckets also expose how different the four games are (which is why note 08 insists
on more than one): `sb26` is **45% dead** (its alternatives frequently do nothing), `tn36` is the
one-button click game so it is **89% active / 0% dead**, and `ls20` shows **5% illegal** on the
progress arm — the one place the guard-plus-signal combination pushed the model into asking for
buttons that were not there.

---

## Part 5 — What a trace-based taxonomy honestly cannot see

A good taxonomy is as clear about its blind spots as its buckets. Map note 05's five named
failure modes onto what this one measures:

| Failure mode (note 05) | Does the taxonomy catch it? |
|---|---|
| **Stuck loop** | Yes — `perseveration`, mechanically, from the action labels. |
| **Flailing** | Yes — `dead_action`, from `cells_changed == 0`. |
| **Hypothesis lock-in / goal drift** | **Only its shadow.** These are *why* `active_no_progress` is 88%, but the bucket cannot tell "coherent work toward a wrong theory" from "genuine exploration" — that needs the `reasoning` text, which note 09 read qualitatively (the bar/tower delusion). |
| **Context blindness** | **No.** Whether the one fact that mattered was compressed away three turns ago is invisible in a single trace. |

::: key
The mechanical buckets are rigorous *because* they come from fields the game and the loop
recorded, not from reading intentions. The price is that the biggest bucket, `active_no_progress`,
is a catch-all: it proves the agent is busy and getting nowhere, but not *which* wrong idea it is
chasing. Saying that plainly is the difference between a taxonomy and a horoscope.
:::

---

## What to hold onto

1. A trace is the receipt for one decision, `reasoning` field included — it is what makes "why
   did it do that?" answerable. Observability is the goal; the trace is the mechanism.
2. The format is append-only JSONL so a crash still leaves readable records, and every decision
   goes through it, so no two tools disagree about what happened.
3. A failure taxonomy counts the ways the agent wastes turns, in buckets that partition its
   actions. Ours is built from the committed traces and validated against a failure we already
   understood (the 41-in-a-row run reads 60% perseveration).
4. The headline: the current agent spends **88% of its actions on purposeful activity that makes
   no progress, and 0% on progress** — the wall of note 09, quantified.
5. The taxonomy also shows the earlier fixes as bucket shifts (perseveration 53% → 0% under the
   guard, relocated into `active_no_progress`) — and is honest that its biggest bucket cannot,
   by itself, name *which* wrong theory the agent is chasing.

---

## Say it in an interview

**"How do you debug an agent?"**
> "I trace every decision. One line per turn, append-only JSONL so a crash still leaves readable
> records, and it carries not just what the agent did but the model's own stated reason for
> doing it. That reasoning field is what let me tell the difference between 'the agent is mashing
> a button' and 'the agent has adopted a wrong theory of the goal and is pursuing it
> competently' — it literally wrote 'extending the green bar to connect the elements' about a
> marker that meant nothing. From the score alone that just looks like failure; from the trace
> it's a diagnosis."

**"You mentioned a failure taxonomy — what was in it?"** *(the strong answer)*
> "I sorted every action in every committed trace — about two thousand of them — into one of six
> buckets by priority: illegal, dead, revisit, perseveration, active-but-no-progress, and
> progress, so the shares partition the actions. For the current agent it's 88%
> active-but-no-progress, 12% dead, and zero everything else including zero progress. That single
> number *is* my project's central finding: the agent isn't stuck or flailing, it spends almost
> all its actions on purposeful, non-repetitive, screen-changing work toward a goal it never
> identified. The taxonomy turned 'it doesn't work' into a number I can point at."

**"How do you know the taxonomy itself is right?"**
> "I ran it against a failure I already understood before trusting it on anything else — the run
> where the agent pressed one button 41 times in a row. Perseveration should dominate there, and
> it does, 60%. That's a rule I made after an earlier metric I'd invented from a story about a
> failure read zero percent on the recording of that exact failure. A classifier of failures is
> a guess until you run it against a real one."

**"Did the taxonomy tell you anything the eval numbers didn't?"**
> "Yes — it showed my fixes *relocating* waste rather than removing it. My repetition guard took
> perseveration from 53% to zero, which looks like a win, but the taxonomy shows those actions
> just moved into the active-but-no-progress bucket, which went from 22% to 88%. Same nowhere,
> different buttons. Seeing waste move between buckets instead of leaving is exactly the kind of
> thing a single headline metric hides."

**"What can't it tell you?"**
> "Which wrong idea the agent is chasing. The big catch-all bucket proves it's busy and getting
> nowhere, but distinguishing 'coherent work toward a wrong theory' from 'genuine exploration'
> needs the reasoning text, not the mechanical fields — I read that qualitatively. And context
> blindness, where a compression step dropped the fact that mattered, isn't visible in a single
> trace at all. I'd rather state those blind spots than pretend six buckets explain everything."

---

**Next:** [note 11 — memory and retrieval](11-memory-and-retrieval.md): short-term versus
long-term memory, embeddings, and the honest version of RAG, applied to the agent's own
experience — grounded in the two memory mechanisms this project already built and ran, and
honest about the principled reason it uses no RAG at all. For the whole project as one story,
see [note 13 — the interview story](13-the-interview-story.md).
