# Study 01 — What we are building, in plain English

*Written 2026-07-22. No jargon in this note that isn't explained on the spot. If you
read only one note before an interview, read this one — then note 11 when it exists.*

> **You are here:** rung 1 of the ladder.
> **Assumes you read:** [Study 00](00-how-to-use-these-notes.md).
> **After this you can:** explain the whole project to someone in two minutes, say why
> we chose it, and name the six things it is meant to prove about you.

---

## The two-sentence version

We are building a **computer program that plays puzzle-games it has never seen, with
no instructions, by figuring out the rules through trial and error** — and it does the
figuring-out by asking an AI language model (the same kind of AI as ChatGPT) what to
try next.

The program is only half the project. The other half — the half that actually gets you
hired — is all the **engineering around it**: the machinery that measures whether it's
getting better, records why it did what it did, catches it when it breaks, and keeps it
inside a cost budget.

::: key
The score is not the point. **The harness is the point.** ("Harness" = all the
supporting machinery built around a thing to make it measurable, debuggable and
trustworthy — like the test rig around an engine, not the engine.) A stranger should be
able to open our repository, run one command, and reproduce every number we claim.
:::

---

## Part 1 — The game

There is a competition called **ARC-AGI-3**. It is run by the ARC Prize Foundation, and
it exists to test one specific thing that today's AI is bad at.

Here is the setup. You are dropped into a small video-game. Nobody tells you:

- what the goal is,
- what the buttons do,
- what the shapes on screen mean,
- or even whether you're winning.

You get a grid of coloured squares on screen, and eight buttons. That's it. You press a
button, the screen changes, and from that change you have to *infer* (work out from
evidence) what just happened. Press more buttons, watch more changes, slowly build a
theory of the world — "ah, button 3 moves the blue block right" — then use that theory
to reach a goal you also had to figure out for yourself.

**Humans do this easily.** Drop a person into an unfamiliar game and they'll be poking
around productively within a minute, because they bring a lifetime of intuition
(instant understanding without reasoning it out) about objects, goals, cause and effect.
Measured on these games, humans score 100%.

**AI is dramatically worse at it.** As of our last check on 2026-07-21, the best
frontier model [the most advanced publicly available AI models] scored around 7.8% on
this benchmark. That number was near-zero a few months earlier, so it's climbing fast —
but the gap to 100% is still enormous.

::: note
Why such a gap? Because the AI's usual advantage is gone. A language model is
extraordinary at things it has seen written down somewhere before. ARC games are
deliberately built so that memory doesn't help — every game has fresh rules. What's
left is the thing being measured: **can you learn a brand-new rule from scratch, on the
spot, from a handful of observations?** That skill has a name in this field —
*fluid intelligence* — and it's the closest thing we have to a measurable stand-in for
general intelligence.
:::

### What the screen actually is

Concretely, and verified from the official toolkit installed on your laptop today: the
game sends back a **frame** — a 64×64 grid where each square holds a number, and each
number means a colour. Think of it as a very low-resolution picture, described as a
table of numbers instead of pixels.

The agent can send back exactly **eight** things: a RESET (start over), six plain
button-presses, and one "click at position (x, y)" — where x and y are each between 0
and 63, i.e. anywhere on the grid.

That's the entire conversation with the world: *numbers in, one button out, repeat.*

---

## Part 2 — The player

Our program plays those games. And the way it decides what to press is by asking a
**large language model** — an AI trained on enormous amounts of text, the technology
behind ChatGPT, Claude and Gemini. (Note 03 opens this up properly. For now: a thing
you send text to, and it sends text back.)

Roughly, each turn goes like this:

1. Look at the current grid.
2. Turn it into text the model can read, along with a summary of what we've learned so
   far and what we've already tried.
3. Ask the model: *given all this, what should we press next, and why?*
4. Press it.
5. See what changed. Update what we believe about the world.
6. Repeat.

That cycle — **look, decide, act, learn** — is called an **agent loop**, and a program
built around one is called an **agent**. That is the whole meaning of the word. It is
not a mystical thing; it is a loop with a language model inside the "decide" step.
(Note 05 builds it properly, with real code.)

::: example
Make it concrete. Turn 1, our agent presses ACTION3 at random. The grid changes: a
blue square that was at row 10 is now at row 11. Turn 2, the model is told exactly
that, and it now has a hypothesis (a proposed explanation, not yet proven): *"ACTION3
probably moves the blue thing down."* Turn 3, it tests the hypothesis by pressing
ACTION3 again and checking whether the blue square moves down once more. If it does,
that belief gets stronger and goes into memory. If it doesn't, the belief was wrong and
gets thrown out.

That is not fancy AI. That is the scientific method, running in a loop, with a language
model proposing the hypotheses.
:::

### One important thing we are deliberately *not* doing

The competition has a prize track, run on the Kaggle platform, and in that track your
program is judged **with the internet switched off**. No internet means no calling an
AI model over the network — so prize-eligible agents can't use language models at all.

We checked this and made a deliberate choice, recorded in the project's decision log on
2026-07-21: **we are not chasing the prize.** We target the public leaderboard, where
internet is allowed and language models are the normal approach.

Why that's the right call for you: the prize track would have taught you how to write
clever search code. The public track teaches you the stack that job interviews actually
probe — language models, prompts, context, evaluation, tracing, cost control. You are
building a portfolio, not entering a lottery.

::: warn
This is worth rehearsing, because it's exactly the kind of thing an interviewer pokes
at: *"there was prize money and you skipped it?"* The answer is a design decision with
a reason, not an excuse. Say it as one: **"the prize track forbids internet access at
evaluation time, which forbids LLM APIs. I optimised for learning the LLM engineering
stack, not for lottery odds against funded teams."**
:::

---

## Part 3 — The harness (this is the actual project)

Anyone can write a loop that calls a language model. That takes an afternoon. What
separates a hobby script from engineering is everything wrapped around it — and that
wrapping is what we're really building.

Six pieces, and each one maps to a thing interviews ask about:

**1. The loop, built by hand.** We write the observe → decide → act cycle ourselves
instead of importing a framework that hides it. You cannot explain in an interview what
you never wrote. → note 05.

**2. Context engineering.** The model can only see what we put in front of it, and
there is a hard limit on how much that can be (note 03 explains why). Every turn we
choose: which parts of the grid, how much history, which past lessons, in what order.
That choosing *is* the job. It's the difference between an agent that works and one
that flails. → note 06.

**3. Evals.** Short for *evaluations*. A fixed set of games, a fixed set of measurements
— score, how many actions until first real progress, how many tokens spent — that we
re-run after every single change. So "did that prompt tweak help?" is answered with a
number instead of a feeling. This is the single most important discipline in the whole
project, and the one most beginner projects don't have. → note 07.

**4. Traces.** Every decision the agent makes gets written down: exactly what the model
was shown, exactly what it replied, how long it took, how much it cost. When the agent
does something stupid, we can open the record and see *why*, instead of guessing. →
note 08.

**5. Memory and retrieval.** The agent plays hundreds of turns. It can't hold all of
that in front of the model at once. So it needs a way to store what it learned and pull
back the relevant bits later — which is the same set of ideas behind "RAG", the
retrieval technique interviewers love asking about, except here it's over the agent's
own experience rather than a folder of PDFs. → note 09.

**6. Budget engineering.** Every call to a model costs money and time. We give the agent
a spending limit per game, cache (save and re-use) repeated work, and try a cheap model
first before escalating to an expensive one. Then we show the curve: how score changes
as budget changes. → note 10.

::: key
Read those six again and notice: **only #1 is about the agent.** The other five are
about *knowing whether the agent works*. That ratio is the thesis of this project, and
it is what an experienced engineer will recognise instantly as the real work.
:::

---

## Why this project and not something easier

You could have built a chatbot over your documents. Most portfolios do. Three reasons
we didn't, recorded in the decision log:

**It doesn't blend in.** Reviewers see the same document-chatbot dozens of times. An
agent that plays unknown games is remembered — and, more usefully, it *invites the
questions you've prepared for*, instead of "so, which vector database?"

**It has a real, honest, hard problem.** A chatbot over your own PDFs works on the first
try, so there's nothing to measure and nothing to say. On ARC, your first agent will
score zero, and everything interesting — the evals, the failure analysis, the fixes —
comes from climbing off zero. **Difficulty is the raw material the story is made from.**

**It points where you want to go.** Your long-term interest is general intelligence, and
this benchmark exists to measure exactly the gap between what today's models can do and
what general intelligence would need. The portfolio piece and the direction you actually
care about are the same object.

And one honest constraint on top: **free tiers only, no GPU training, must run on a
Windows laptop.** No paid APIs, no rented servers. That's not a limitation we're
apologising for — it's part of the engineering story. Building something that works
inside a hard budget is a skill; it's why note 10 exists.

---

## Where we actually are today (2026-07-22)

Honest status, no rounding up:

- **Done:** the plan, the decision log, the project rules, this course, and the
  official ARC toolkit installed and confirmed working on your laptop.
- **Blocked on you:** we need a free API key from the ARC Prize site before the agent
  can talk to a real game. That is a 5-minute job and there's a click-by-click
  walkthrough waiting for you: [How-to 01 — Get your ARC-AGI-3 API key](../howto/01-get-your-arc-api-key.md).
- **Not started:** everything from the first real game onward — the loop, the evals,
  all of it.

::: warn
That "blocked on you" line is real. Nothing else in the project can move until the key
exists, because we can't run a game, and without a game there are no numbers, and this
project doesn't write notes about numbers it hasn't measured.
:::

---

## Say it in an interview

The two-minute version, out loud:

> "I built an LLM-driven agent for ARC-AGI-3 — a benchmark of small games where the
> agent gets no instructions, no stated goal, and has to work out the rules by acting
> and observing. Humans score 100% on it; the best frontier models were around 7.8%
> when I checked in July 2026, so it isolates exactly the thing models are weakest at:
> learning a brand-new rule on the spot.
>
> The agent itself is an observe–decide–act loop with an LLM in the decide step, built
> from scratch rather than with a framework, so I understand every part of it. But the
> real project is the harness around it: an eval suite that runs on every change so no
> improvement is claimed without before-and-after numbers on a fixed set of games; full
> tracing of every model call, with inputs, outputs, tokens, latency and cost, so I can
> answer 'why did it do that?' with evidence; a failure taxonomy [a sorted catalogue of
> the ways it breaks] built from real traces; and a per-game token budget with
> cheap-model-first routing.
>
> I ran it all on free tiers on a laptop, which forced the cost engineering to be real
> rather than decorative."

**Follow-up: "What was the hardest part?"**
> "Deciding what the model sees each turn. A 64×64 grid plus full history doesn't fit in
> a context window, so every turn is a choice about what to include and what to
> summarise away. It's also the change most likely to break things silently — which is
> why the eval suite came before any tuning, not after."

**Follow-up: "How do you know your agent is actually better and not just lucky?"**
> "Fixed eval set, same games every run, and the games I report on are held out from the
> ones I tune on. Every change ships with before-and-after numbers, and regressions
> either get reverted or get a written justification. It's in the repo — the run
> artifacts and the decision log are both committed."

**Follow-up: "Why ARC and not something practical?"**
> "Because it's honestly hard. A retrieval chatbot works on the first attempt, so there's
> nothing to measure and nothing to learn from. Here my first agent scored zero, and
> every technique I can talk about came from climbing off zero with evidence."

---

**Next:** [Study 02 — The words you need, in the order you need them](02-the-words-you-need.md)
