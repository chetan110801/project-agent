# Study 04 — ARC-AGI-3: the game our agent has to play

*Written 2026-07-22. Every technical detail here was read out of the official
`arc-agi-3` SDK version 0.0.1, installed and confirmed on Chetan's laptop on
2026-07-21 — not from memory. Facts about the competition come from note 02's
verification pass on 2026-07-21.*

> **You are here:** rung 4 of the ladder.
> **Assumes you read:** [00](00-how-to-use-these-notes.md),
> [01](01-what-we-are-building.md), [02](02-the-words-you-need.md),
> [03](03-what-an-llm-really-is.md).
> **After this you can:** describe the benchmark, the exact interface our agent talks to,
> what "score" means, and why this is hard for AI but easy for people.

---

## What ARC is trying to measure

Most AI benchmarks measure **knowledge or skill** — can you answer these medical exam
questions, can you write this function, can you summarise this document. Models are
extremely good at those now, and there's a nagging doubt about why: a model trained on a
large fraction of the internet has, in some form, seen an enormous amount of the material
those tests draw on.

ARC was built to sidestep that doubt entirely. Its target is:

::: key
**Can you learn a rule you have never seen before, from a handful of examples, right
now?**
That skill has a name — *fluid intelligence* — and it is the part of human thinking most
obviously missing from systems that mainly recall and recombine.
:::

Every ARC puzzle uses rules invented for that puzzle. Having seen a billion other puzzles
doesn't tell you this one's rule. You have to work it out, on the spot, from what's in
front of you. That's the whole design.

### ARC-AGI-1, 2, 3 — three generations

| Version | Shape of the task | What it added |
|---|---|---|
| **ARC-AGI-1** | Static puzzles: a few input→output grid pairs, infer the transformation, apply it to a new input | The original test of "learn the rule from examples" |
| **ARC-AGI-2** | Same shape, harder rules | Raised the difficulty ceiling |
| **ARC-AGI-3** | **Interactive games** — no examples at all; you must *act* to find out anything | Added exploration: you have to *gather* your own evidence |

That last jump is the important one and the reason we're here.

In ARC-AGI-1 you're given the evidence and must find the pattern — a pure reasoning
problem. In ARC-AGI-3 **nobody gives you evidence.** You get a screen and eight buttons.
Want to know what button 3 does? Press it and watch. You have to *design your own
experiments*, which means the agent has to reason about what it doesn't yet know — and
that is a strictly harder, and much more agent-shaped, problem.

::: example
Concretely, the difference between:

*"Here are three examples of a transformation; apply it to a fourth grid."* — a hard
puzzle, but everything you need is on the page.

versus

*"Here is a screen. There are eight buttons. Go."* — you don't know the goal, the
controls, what the shapes mean, or whether you're winning. Every fact has to be bought
with an action.
:::

---

## The state of play (checked 2026-07-21)

| Who | Score on ARC-AGI-3 |
|---|---|
| Humans | 100% |
| Best frontier model (GPT-5.6 Sol) | ~7.8% |

Two honest notes on that gap, both mattering for how you talk about it:

**It's moving fast.** That ~7.8% was near zero a few months earlier. Any specific number
here goes stale quickly — which is exactly why this project's rules require re-verifying
leaderboard figures before quoting them. *Never* recite a benchmark number in an
interview without saying when you checked it.

**Published claims run ahead of the competition scores.** A July 2026 paper (OPINE-World,
arXiv 2607.01531) claims 78.4% on the *public* evaluation set. Public eval and the
competition's private eval are different things, and a paper claim isn't a reproduced
result — but the direction is clear, and pretending otherwise would be exactly the kind
of stale-fact error this project exists to avoid.

### The competition, and the choice we made

ARC Prize 2026 puts up an **$850K** pool: a $700K grand prize for the first agent to
score 100%, plus top-score and milestone awards. Milestone #2 closes **2026-09-30**, and
prize entries must be open-sourced.

The catch, and the reason for one of this project's core decisions: **prize submissions
run on Kaggle with no internet access during evaluation.** No internet means no calling a
language model over the network — so prize-eligible agents cannot use LLMs at all.

We are targeting the **public leaderboard**, not the prize. Recorded in the decision log
on 2026-07-21, with the reasoning: the prize track teaches clever search programming;
the public track teaches the LLM engineering stack that AI-engineering interviews
actually probe. You're building a portfolio, not buying a lottery ticket.

---

## The interface: exactly what our agent sees and does

This is the part worth knowing precisely, because it's what our code touches. All of it
is read from the installed SDK.

### What comes back: a frame

Every action returns a **`FrameData`** object. Its fields:

| Field | Type | What it is |
|---|---|---|
| `game_id` | text | which game |
| `frame` | list of 2D integer grids | **the screen** — cells hold numbers meaning colours |
| `state` | one of four values | `NOT_PLAYED`, `NOT_FINISHED`, `WIN`, `GAME_OVER` |
| `score` | integer, 0–254 | how well we're doing |
| `available_actions` | list | which actions are legal right now |
| `action_input` | object | the action that produced this frame |
| `guid` | text | id for this particular play |

The grid is **64 × 64** — we know this for certain because click coordinates are
validated to the range 0–63 — which is **4,096 cells per frame**. That number is the
whole reason note 03's context-window discussion isn't theoretical for us.

### What we can do: exactly eight actions

Read straight out of the SDK's action definitions:

| Action | Number | Kind | Notes |
|---|---|---|---|
| `RESET` | 0 | simple | start or restart the game |
| `ACTION1`–`ACTION5` | 1–5 | simple | plain button presses; no parameters |
| `ACTION6` | 6 | **complex** | a click: carries `x` and `y`, each 0–63 |
| `ACTION7` | 7 | simple | plain button press |

::: key
**Nothing tells you what any of them do.** ACTION1 might move something up in one game,
change a colour in another, and do nothing at all in a third. Working that out *is* the
game. Note the asymmetry too: the six simple actions give you 6 choices, but ACTION6 —
the click — gives you 64 × 64 = **4,096** distinct choices. The action space is
overwhelmingly clicks, which makes "where should I click?" the single hardest decision
the agent makes.
:::

### One nice detail: the API stores your reasoning

Each action can carry a `reasoning` field — an arbitrary blob of your own data, up to
16 KB, which the server stores and hands back verbatim. It has no effect on the game.

It exists purely so you can record **why** the agent chose each action, attached to the
action itself. That is a tracing feature (note 02, Group E) built into the benchmark —
and a small sign that the people who designed this expected serious agents to care about
explaining themselves. We will use it.

### How you're scored: the scorecard

After playing, you fetch a **scorecard**. Per game it records: every score across
repeated plays, every end state, how many actions each play took, how many resets. Across
all games it computes: games won, games played, total actions, and total score.

Two things to notice, because they shape our eval design in note 07:

**Score is not the only signal.** *Actions taken* is recorded too — so "won in 40 actions"
and "won in 400 actions" are distinguishable outcomes. Efficiency is measurable, not just
success.

**Games can be replayed.** Scores are kept as a list per game and the headline is the
*best* run. So "how consistent is it?" is answerable from the same data — and consistency
is often the more interesting number, since one lucky run proves very little.

---

## Why this is hard for a language model

Worth having a crisp answer to, because it's the natural interview follow-up.

**1. Its main strength is switched off.** A language model is spectacular at things
resembling text it has seen. ARC games are built so that resemblance doesn't help. The
advantage is deliberately removed and only the measured skill is left.

**2. Grids-as-text are an awkward fit.** The model reads a wall of numbers. A human
*sees* a blue square move down and left. Recovering that spatial intuition from a text
table is genuinely hard — and how we render the grid into text is one of our biggest
design levers (note 06).

**3. Exploration is not a language skill.** Working out that ACTION1 and ACTION2 are
untested and therefore worth testing is scientific reasoning under uncertainty, not
next-word prediction. It has to be built into the loop, deliberately.

**4. The context problem from note 03, in full force.** 4,096 numbers per frame, hundreds
of frames per game. It cannot all be shown. Something must always be thrown away, and
throwing away the wrong thing loses the game.

**5. Cause and effect over gaps.** Press a button now, see the consequence three turns
later. Linking the two requires holding a hypothesis across turns — which, since the
model has no memory (note 03), means *we* have to carry it.

::: warn
Notice something about that list: **items 3, 4 and 5 aren't limitations of the model —
they're work the harness has to do.** Which is the entire thesis of this project. The
model is one component; the engineering around it decides whether the thing works.
:::

---

## Say it in an interview

**"What is ARC-AGI-3?"**
> "It's a benchmark of small interactive games with no instructions — no stated goal, no
> documented controls, no examples. The agent gets a 64×64 grid of coloured cells and
> exactly eight actions: six plain button presses, one click with x,y coordinates, and a
> reset. It has to work out the rules by acting and observing. Every game has fresh
> rules, so memorisation doesn't transfer — it targets learning a new rule on the spot,
> which is where models are weakest. Humans score 100%; the best frontier model was
> around 7.8% when I checked in July 2026."

**"Why is that harder than ARC-AGI-1?"**
> "ARC-AGI-1 gives you the examples — it's a pure inference problem. ARC-AGI-3 gives you
> nothing. You have to *generate* your own evidence by acting, which means reasoning
> about what you don't yet know and designing experiments to find out. That's an
> exploration problem on top of a reasoning problem, and it's what makes it an agent
> benchmark rather than a reasoning benchmark."

**"What was the hardest engineering problem it created?"**
> "The observation is 4,096 numbers, and a game runs hundreds of turns — so full history
> never fits in a context window. Every turn is an explicit decision about what the model
> sees: which frames verbatim, what gets compressed into a description, what collapses
> into a running summary of beliefs about the rules. And the click action alone has 4,096
> possible targets, so narrowing 'where to click' is its own problem — random clicking
> effectively never hits anything."

**"There was prize money. Why didn't you enter?"**
> "The prize track evaluates on Kaggle with no internet access, which rules out calling
> an LLM API — so a prize-eligible agent can't be LLM-driven at all. I optimised for
> learning the LLM engineering stack over lottery odds against funded teams, and I wrote
> the decision down with the reasoning at the time. The public leaderboard allows
> internet, which is where LLM agents actually compete."

**"How do you know your agent is improving?"**
> "The scorecard gives more than a score — it records actions taken per play and keeps
> every play separately, so I can measure efficiency and consistency, not just success.
> My eval metrics are score, actions-to-first-progress, and tokens spent per game, run
> across a fixed set of games before and after every change."

---

**Next:** [Study 05 — The agent loop, from first principles](05-the-agent-loop.md)
