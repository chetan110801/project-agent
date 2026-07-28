# Study 13 — The interview story: the whole project as one answer

*Written 2026-07-27, the day the four-experiment steering arc closed. This note invents no
new fact. Every number in it is carried from an earlier note, and each of those traces to a
file in this repo you can regenerate — the artifacts are named where the number first
appeared (notes 06–09 and 12). The one thing this note adds is the **order**: it puts the
whole project into a single line you can say out loud.*

> **You are here:** rung 13 — the capstone (*the stone that finishes an arch and holds the
> rest in place*). The last written rung of the course.
> **Assumes you read:** the whole ladder — [00](00-how-to-use-these-notes.md) through
> [09](09-exploration-and-the-signal-that-cannot-exist.md), and
> [12](12-budgets-tokens-cost-latency.md). This note leans on all of them and re-teaches
> none of them in full; it carries a one-line gist of each thing as it needs it, so you are
> never stranded, but the depth lives in the earlier notes.
> **After this you can:** tell the entire project as one continuous story — the problem, the
> machine, the one lever you hold, how you know anything, the four experiments and the wall
> they found, and the budget you actually spend — in three minutes, and hold your ground on
> the hard follow-ups.

---

## What this note is for

Every other note teaches one thing and ends by pointing at the next. This one does the
opposite: it stands at the top of the finished ladder and looks back down the whole flight
at once.

Because the real test is not "explain tokens" or "explain evals" in isolation. It is the
opening question of almost every interview:

> *"So — walk me through this project."*

That question rewards a **spine** (one connected line of reasoning), not a pile of facts.
This note is the spine — the whole ladder of detail behind you, arranged so each part hands
to the next without a gap.

::: key
There is one sentence the whole project hangs from, and if you remember nothing else,
remember this one: **the score is not the point — the harness is the point.** ("Harness" =
all the supporting machinery built around a thing to make it measurable, debuggable and
trustworthy — the test rig around an engine, not the engine.) The agent that plays the game
is one component. Knowing whether that component works, why it did what it did, and what it
costs — that is the project, and that is the job you are interviewing for.
:::

---

## Movement 1 — The problem worth attacking

**The game.** ARC-AGI-3 is a benchmark (*a standard test everyone measures against*) of
small video-games with **no instructions**: no stated goal, no documented controls, no worked
examples. The agent gets a **64 × 64 grid** of coloured cells — 4,096 numbers — and exactly
**eight** actions: six plain button presses, one click carrying an (x, y) coordinate, and a
reset (note 04, read straight from the installed SDK). Nothing tells you what any button
does. Working that out *is* the game.

**Why it is worth building on.** It isolates the one thing today's models are weakest at.
A language model is spectacular at things that resemble text it has seen; ARC games are built
so resemblance never helps, because every game has fresh rules. What is left is the measured
skill — *learn a brand-new rule, on the spot, from a handful of observations*. Humans score
100%. The best frontier model (*the most capable models available at a given moment*) was
around **7.8%** when I last checked, on 2026-07-21 (note 04).

::: example
Say the difficulty as a number and it lands: a gap from 7.8% to 100% is not a rounding
error, it is the open problem. And it invites exactly the questions I prepared for — how do
you evaluate it, why does it get stuck, what does it cost — instead of "so, which vector
database?", which is what a document-chatbot portfolio invites. **Difficulty is the raw
material the story is made from** (note 01).
:::

**One design decision to defend up front**, because interviewers poke at it: there was
$850K of prize money and I did not chase it. The prize track runs on Kaggle with the
internet switched off, and no internet means no calling a model over the network — so a
prize-eligible agent cannot be LLM-driven at all. I targeted the public leaderboard, where
LLMs are the normal approach, because it teaches the stack interviews actually probe. That
is a decision with a reason, recorded on 2026-07-21, not an excuse (notes 01, 04).

---

## Movement 2 — The machine you are driving

Before any cleverness, you have to know what a language model actually *is*, because every
later problem is downstream of it (note 03).

::: key
**A large language model is a fixed function from text to text.** Given a sequence of text,
it produces the text that most plausibly comes next. That is the whole of it. **No memory,
no goal, no state** — nothing survives between calls. When a chatbot seems to "remember", the
whole conversation was re-sent from the top on every message.
:::

Three consequences fall straight out, and they shape everything:

- It has no memory, so **we** carry the situation forward.
- It has no goal, so **we** restate the goal every turn.
- It reads **tokens** (*chunks of characters, between a letter and a word*), not words —
  which is why it is billed, limited, and rate-capped in tokens, and why the **context
  window** (*the hard cap on how many tokens it can consider in one call*) is the binding
  constraint on the whole design. History grows every turn; the window does not.

**The agent, deflated.** An **agent** is just a program that repeats *observe → decide → act*
until it is done; when the decide step is a model call, it is an LLM agent (note 05). A
thermostat fits the definition. Ours observes the grid, decides by asking the model, acts by
sending a button. I wrote the eleven-line loop by hand instead of importing a framework, for
one reason that survives every follow-up: **you cannot explain in an interview what you never
wrote**, and a framework hides exactly the parts — context assembly, retry policy, what
happens on a malformed reply — that the interview is about.

::: key
The loop always carries one thing that does not depend on the agent noticing anything: a
**hard action cap** (the SDK's is 80). A confused agent loops forever, burning quota with
nothing to show. *A guardrail is a guarantee; a prompt is only a request* — a phrase that
earns its place four more times before this note ends.
:::

---

## Movement 3 — The only lever you actually hold

The model is fixed. The loop is eleven lines. So the whole of the engineering leverage is in
one place: **what text the model gets to see each turn.** That is **context engineering**, and
it is the job, not a job (note 06).

The model cannot see a grid — only text. Someone has to turn 4,096 numbers into words, every
turn, and there is no default. So I wrote three encodings (*ways of writing the screen down*)
side by side and **measured** them instead of arguing: the raw grid, an object-level
description ("a 2×2 block of colour 4 at (1,1); a single cell of colour 3"), and a diff
against the previous frame ("2 cells changed").

Two results from that measurement are worth carrying whole, because they are the strongest
things in the note.

::: key
**The token-cost correction — the single most useful thing I can tell an interviewer.** My
best early finding was that writing the grid with spaces instead of packed cost **5.6× the
tokens for identical information**, with a clean mechanism: OpenAI's tokeniser (*the part that
chops text into tokens before the model reads it*) packs digit runs three-to-a-token, and a
separator defeats it. Then I re-measured the *same two strings*
with the tokeniser of the model I actually call (Gemini), and the ratio was **2.0×**, because
Gemini bills those grids at almost exactly one token per character — there is no packing to
defeat. **Both measurements are correct. Only one is a fact about my system.** Every direction
held — spacing still costs double, the object view is still a win — but the magnitude moved by
up to 2.8×. So the rule I would take anywhere: *a ratio between prompt encodings is a property
of a tokeniser, not of your data. If you cannot name the tokeniser, you do not have a number.*
(`artifacts/tokens-by-tokeniser.json`.)
:::

::: key
**47% of the budget was recovered by reading a field, before any model was involved.** The
game advertises which buttons are legal in every frame. The stock baseline ignored that and
picked from all eight — so **38 of its 80 actions** were buttons that did not exist, and those
were exactly the 38 that changed nothing on screen. My loop filters against that list. *Look
at what the environment already tells you before adding intelligence to guess it.*
(`artifacts/comparison.json`.)
:::

The object view compresses a real frame ~7× in the units that bill me — but on a
checkerboard (2,048 one-cell objects) the "compressed" form is **8.7× larger** than the raw
grid, so it carries a cap that truncates loudly and says it truncated. *A compression scheme
must be measured on its worst input, because it meets that input exactly when the game gets
complicated — the moment you least want it to fail.* And the cheapest valuable thing in the
whole context turned out not to be more description of the world but feedback about the
agent's own last move: "nothing changed" costs two tokens and kills the commonest failure
mode (note 06).

---

## Movement 4 — How you know anything at all

Here is where a hobby script and an engineering project part ways. You change something; the
agent scores 3 instead of 2. **Did your change help?** You cannot tell — not without a
baseline and a repeatable measurement (notes 07, 08).

A **baseline** is a deliberately dumb version run under the same conditions, whose only job
is to be the number you compare against. Ours presses buttons at random, and it is *seeded*
(*fixed starting number, so the "random" sequence repeats*) — because an unseeded baseline
gives a different number every run, and "we beat the baseline" then becomes a claim that can
never be proven wrong (note 07).

And the first thing the baseline told me was the most important negative result in the
project:

::: key
**The obvious metric is dead.** Score was 0 for the stock baseline, 0 for my improved loop, 0
at 80 actions and 0 at 400 — eighteen times what the game's own reference solution needs for
level 1 (`ls20`'s reference is `[22, 123, 73, 84, 96, 192, 186]`, from the scorecard). A
number that reads 0 before your change and 0 after it is not a metric, it is a constant. You
can tune against it forever and learn nothing. (`artifacts/ourloop-random-400.json`.)
:::

So the eval suite (*a fixed set of games plus fixed measurements, run with one command*) had
to be built around denser signals that move *before* the agent starts winning, and around
three disciplines that are the actual content of the note (note 08):

- **Every number is tagged steering / outcome / cost.** A change is kept or reverted on
  **steering** numbers (repetition, dead actions, how far into level 1 it got); **outcome**
  (the score) is reported in the same table but *never steered on*, so a change that games the
  steering metrics and wrecks the real goal cannot hide; **cost** (tokens, time) sits alongside
  so a win bought by tripling the bill shows as the trade it is.
- **Dev set you tune on, held-out set you do not touch.** 4 dev / 6 held-out / 15 reserve of
  25 games, split by a *published* seed so nobody can accuse me of hand-picking easy games,
  with `ls20` pinned to dev in code because every baseline was measured on it — a confession
  in the code, not a design. Tuning on held-out data is the one unforgivable mistake, and the
  runner *refuses* to touch the held-out set without an explicit report flag.
- **One arm, one variable.** An **arm** is one run of the whole suite in one configuration;
  the comparison tool prints what changed between two arms *before* any result, and stamps
  **NOT AN EXPERIMENT** when more than one setting moved.

::: warn
Building the measurement before doing the tuning is not process for its own sake. If I had
started tweaking prompts against a dead score, every experiment would have read "0 → 0" and I
would have learned nothing, slowly, for a week. **Designing the measurement first is what let
me find the dead metric in an afternoon instead of after that week** (note 07).
:::

---

## Movement 5 — The investigation, and the wall it found

This is the heart of the story, and it is a *negative* result told as one arc: **four
experiments, four changes in the agent's behaviour, and the score never moved once** — which,
put together, does not read as four failures. It reads as a wall, located precisely (notes 08,
09).

::: key
**Experiment 1 — give the agent its own memory.** Diagnosis: it pressed one button 41 times
in a row (random repeats at most 3), so it must not be able to *see* its own repetition. Fix:
put its last 8 actions in the prompt. A/B'd on one variable — it got **worse on 7 of 10
steering metrics for +14% tokens**, and I reverted it. The reason is the lesson: eight lines
reading "ACTION3 → 2 cells changed" I read as *you are stuck*; the model read as *this action
reliably works*. **Memory of your actions is not feedback about your progress.** I supplied
the first and expected the second (note 08; `artifacts/evals/`).
:::

::: key
**The hinge — the progress signal that cannot exist.** "The next thing is a progress signal"
was the obvious follow-up. Before building it I tested four candidate versions *offline*
against the recording of the failure I already had on disk — and all four failed, the one I
believed in **backwards**: by a churn measure (*does my work add up, or undo itself?*) the
stuck agent scored *better* than random at every look-back window, because it had found a bar
it could extend two cells a press, so its
work was accumulating perfectly. It was extending the *wrong thing*. **Progress is defined
against a goal; if you do not know the goal, no statistic over the screen can tell progress
from busywork — only activity from stillness.** The real fault was never "can't see
repetition"; it was **premature commitment** — one theory of the goal, never tested against
another (note 09; `artifacts/progress-signals.json`).
:::

That re-diagnosis produced **Experiment 2, the repetition guard** — after N identical actions
the harness refuses that exact action, N set from the baseline (random exceeds 3-in-a-row on
under 2% of moves; the LLM on 30–77%), so the rule is "you may repeat as often as a coin
flip would" and provably cannot punish normal play. It worked on what it was built for —
longest streak **26 → 3**, repetition-above-chance halved — for +1.2% tokens, and I kept it.
**And the score stayed 0.** The guard is the *harness compensating for the agent*, not the
agent getting better, and I report it in exactly those words (note 09).

::: key
**Experiment 3 — make the theory falsifiable.** If the fault is committing to one theory,
force the agent to state its theory and, alongside each action, a **prediction the frame can
settle** (how many cells will change — the boundary read off the recordings, not chosen, so
it is not a knob I could turn to manufacture a result). The harness grades the prediction
against reality and, when wrong, demands a different theory. The mechanism **fired hard**:
the agent revised its theory **94% of the time right after being told it was wrong**, versus
44% after a prediction that held — refutation genuinely moved it. And it **did not steer**:
repetition-above-chance was byte-for-byte identical between arms, score 0, +9.4% tokens. You
can break premature commitment, provably — and the agent still just generates a longer stream
of plausible-but-wrong guesses, because nothing in the loop knows the goal (note 09;
`artifacts/hypothesis-report-dev-llm-y1.json`).
:::

::: key
**Experiment 4 — the one signal that is allowed to exist.** Exactly one thing in the system
knows the goal: the server's end-of-game scorecard, which reports how many levels you cleared
and how many actions a reference solution needs per level. It is useless to the game it came
from — it arrives at the end — so I carried it into the *next attempt at the same game*: *"Last
time you used 30 actions and cleared 0 of 7 levels. A reference clears level 1 in 22. Do
something different."* I checked two things before reading the result: the reference number
came back for **all four** dev games (22, 18, 32, 32 — a pre-registered worry resolved), and
the agent **read it back** (its first reasoning on one retry: *"do something different this
time to clear level 1"*). And it **still did not help** — the "works" pattern moved the right
way by less than the noise, while the number that cleared the noise was the agent taking *more
dead actions*. Score 0 (note 09; `artifacts/evals/dev-llm-p1.json`).
:::

Put the four together and they stop being disappointing and start being a *result*:

::: key
**The wall, named exactly.** Memory of actions, a repetition guard, a falsifiable theory, and
the one true after-the-fact goal signal — each changed *what* the agent does; none changed
*whether* it succeeds. **Knowing you failed is not knowing what would work.** The agent has no
mechanism to turn feedback, however truthful, into a *better-chosen* next action. That needs
either **credit assignment** (*working out which past action deserves the blame or credit for
an outcome*) or a **learned model of what each action does** — and a fresh, stateless prompt
every turn, remembering nothing across attempts, has neither. The arc closes not on a fix but
on a wall, and the next idea worth trying is on the far side of it: **learning across
attempts**, not one more sentence telling the agent it is not there yet.
:::

---

## Movement 6 — The budget you actually spend

The last movement is the one that made all of it real: this ran on **free tiers only**, on a
Windows laptop, by project rule — and that constraint is part of the engineering story, not an
apology for it (note 12).

On a free tier the scarce budget is not money; it is **requests** and **time**. There are
three limits at once — requests per minute, tokens per minute, requests per day — and only one
**binds** (*is the one that actually stops you first*) at any moment. Which one binds decides
whether an optimisation is worth anything:

::: example
The same screen is ~4,130 tokens as a raw grid or ~573 as objects — a 7× cut. On an open
model where tokens-per-minute bound, that made each game **7× faster**. On the model I
actually use, requests-per-minute bound and tokens had slack, so the *identical* 7× shrink
changed my throughput by **zero**. **You cannot choose your model and your prompt size
independently** — the value of a context-engineering win is a property of the constraint that
binds, not of the win (note 12).
:::

And the trap worth the whole note: I first picked the model with the most throughput on paper
— 180 games a day against the eventual model's 6 — and it answered a real game prompt **0 out
of 3 times** (504 timeouts) while answering a toy prompt fine. **A rate limit is a promise
about requests you may make, not requests that will be served**, and only the real prompt at
real size tells you the difference. That scarcity then reshaped the experiments themselves:
six games a day is why the eval episodes are 30 actions long, not 80. *Constraints propagate —
cost limit → episode length → what the metric can detect* — and being able to trace that out
loud is worth more than pretending four games is statistically comfortable (notes 08, 12).

---

## The thread running under all six movements

Step back and one theme runs through every movement above: **my own measurements lied to me
repeatedly, and the discipline is what caught them.** This is the most senior thing in the
whole story, because it is not about ARC at all — it is about how you know anything.

| The measurement that lied | How it was caught |
|---|---|
| "Spacing costs 5.6×" — true, about the wrong tokeniser | every token number carries the name of its tokeniser (note 06) |
| A revisit metric invented from a failure read **0%** on that very failure | run a new metric against the recorded failure before shipping it (note 08) |
| A repetition metric flagged the *random* baseline as the worst stuck-loop | subtract what chance scores on each game — `excess`, not raw share (note 08) |
| The model with 29× the paper throughput served **0 of 3** real prompts | cost against the model that answers a real prompt, not a toy one (note 12) |
| A per-**process** quota counter walked four runs past a per-**day** cap | persist usage across runs; refuse to start an arm that won't fit (note 12) |
| A comparison cried "NOT AN EXPERIMENT" over settings that never moved | normalise absent later-added config keys to their defaults before diffing (note 09) |

::: key
None of these was a modelling failure. Every one was a *measurement* telling a confident
falsehood, and every one was caught by the same habit: **refuse to accept a number that
contradicts what the run plainly did, and keep the recordings so you can check.** Recording
every run is boring infrastructure. It is also what turned "I think this would help" into "I
checked", and every mystery on this project into a lookup.
:::

---

## Where it stands today (2026-07-27)

Honest status, no rounding up:

- **Done and solid:** the hand-built loop; the encoders and their measured costs; the eval
  suite with the steering/outcome/cost split and the dev/held-out discipline; the budget
  machinery; and the four-experiment arc, now closed on a named wall.
- **The result is a negative one, reported as loudly as a win would be:** the agent is no
  better at the game than random on the outcome that counts. The value is in *how thoroughly
  that is established* and *what it locates*.
- **Still owed on the course:** note 11 (memory and retrieval) waits until the agent actually
  has cross-attempt memory — which is the far-side work. (Note 10, traces and the failure
  taxonomy, is now written: it says the wall as a number — 88% of the current agent's actions
  are active-but-no-progress.)
- **The next project direction** is on the far side of the wall — *learning across attempts*
  (credit assignment or an action-model). It is a genuinely new direction, so it gets its own
  dated decision and explicit agreement before any build, not a quiet drift into it.

::: warn
Do not let the closed arc read as "the project failed". The project's thesis was never "score
high on ARC" — it was "build the harness that tells you the truth about an agent". That
harness exists, it works, and its sharpest demonstration is that it took four plausible ideas,
proved each one changed behaviour without moving the goal, and told me *exactly* what is
missing. That is the harness doing its job.
:::

---

## Say it in an interview

This is the whole reason the note exists. First the three-minute walk-through, said as one
line; then the follow-ups that actually get asked.

**"Walk me through your project."**
> "I built an LLM-driven agent for ARC-AGI-3 — a benchmark of small games with no
> instructions, no stated goal, no examples. The agent gets a 64×64 grid and eight actions
> and has to work out the rules by acting. Humans score 100%; the best frontier model was
> around 8% when I checked, so it isolates the thing models are weakest at.
>
> But the agent is one component. The project is the harness around it, and that's where the
> engineering is. The loop is eleven lines I wrote by hand so I could explain every part.
> The one real lever is context — the model only sees what I choose to show it — so I wrote
> and *measured* several encodings of the screen; the headline there is a correction I'd
> stand behind, that a token ratio between two encodings is a fact about a tokeniser, not
> about your data, which is why I never quote one without naming the counter.
>
> Then the discipline: I built an eval suite before I did any tuning, because I measured the
> game's score and it was a dead constant — zero at every budget I tried. So I steer on
> denser signals, tag every number as steering, outcome or cost so a change can't game the
> metrics and quietly wreck the goal, and split the games into a dev set I tune on and a
> held-out set I don't touch.
>
> With that in place I ran four experiments to get the agent off zero — its own action
> history, a repetition guard, a falsifiable-theory prompt, and finally the server's own
> end-of-game verdict fed into the next attempt. Every one changed the agent's behaviour.
> Not one moved the score. Together they locate the wall precisely: the agent can't turn
> feedback, however truthful, into a *better-chosen* next action, because a stateless prompt
> has no credit assignment and no learned model of what its actions do. And all of it ran on
> free tiers, which made the cost engineering real rather than decorative — the model with
> the best throughput on paper couldn't serve a single real prompt, and finding that out is
> its own lesson."

**"What are you proudest of?"**
> "That the negative result is airtight. Anyone can report a win. I ran four reasonable fixes,
> A/B'd each on one variable against a seeded baseline, and showed each one changed behaviour
> and none moved the goal — and I can tell you *why* each failed, not just that it did. The
> arc doesn't end on a shrug; it ends on a named missing ingredient. Getting to a negative
> result you can defend is harder than getting to a positive one you can't."

**"What's the single most useful thing you learned?"**
> "That my own measurements lied to me repeatedly, and a habit caught them every time. A
> metric I invented from a story about a failure read zero percent on that exact failure. A
> token ratio I loved was about the wrong model. A repetition metric called the *random*
> baseline the worst offender. Each was a confident falsehood from a measuring instrument,
> and each was caught the same way — refuse a number that contradicts what the run plainly
> did, and keep every recording so you can check in seconds instead of guessing for a week."

**"So the agent doesn't work — why should I be impressed?"**
> "Because the project was never 'score high on ARC' — it was 'build the harness that tells
> the truth about an agent'. On that, it works: it took four plausible ideas and told me
> exactly what each one does and doesn't buy, and it told me precisely what's missing. That's
> the skill I'd bring to your team — not a model that happens to win, but the machinery that
> tells you *whether* it wins, *why* it did what it did, and what it costs."

**"What would you do next?"**
> "Everything so far steers the agent *within* one attempt. The wall says that's not enough —
> you can't turn 'that didn't work' into a better next move without learning across attempts.
> So the next direction is credit assignment or a learned action-model: some memory of what
> actions actually accomplished, carried between plays and used to *choose*, not just to
> narrate. It's a new direction, so I'd scope it and write the decision down before building —
> which is how every other turn in this project was made."

**"If you had a budget, where would it go first?"**
> "More games and multiple seeds per game, in that order. Everything I report is a single
> seed on four games, bounded by 500 requests a day. More games attacks overfitting to the
> handful I've stared at; more seeds attacks noise — and I can put a number on that noise,
> because one game where my change never fired still swung 17 points. I'd rather say that
> plainly than pretend four games is comfortable."

**"How is this different from documentation?"**
> "Documentation says what the code does. This whole project says *why the design is what it
> is* — the decisions, the alternatives I rejected, and the evidence for each — and it's all
> committed: a dated decision log, run artifacts every number traces back to, and a
> plain-language course I wrote alongside the build so I could explain every part of it
> without hand-waving. If you open the repo and run one command, you get my numbers."

---

## End of the course

That is the ladder, top to bottom, as one line. If you can say Movement 5 and the thread
under it in your own words — four changes, no score movement, a wall named, and a habit that
caught every lie a measurement told — you can carry this whole project into any room.

One rung remains to be written, and it waits on purpose: **note 11 (memory and retrieval)**,
until the agent has the cross-attempt memory that the far side of the wall requires. (Note 10,
traces and the failure taxonomy, was written 2026-07-28.) When that work exists, the course
grows one more rung to explain it — because a note about an unbuilt thing is guesswork, and this
project does not publish guesswork.

**Back to the start:** [Study 00 — how to use these notes](00-how-to-use-these-notes.md).
