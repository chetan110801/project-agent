# Study 11 — Memory and retrieval: giving an agent a past, honestly

*Written 2026-07-28. Every mechanism here is one already built and run in this repo — the
history window (`harness/frames.render_history`, Experiment 1 in note 08) and the progress
signal (`harness/progress_signal.py`, Experiment 4 in note 09). The one thing this note does
**not** build — embedding-based retrieval — it teaches as a concept and then explains, plainly,
why this project did not need it. That honesty is the point of the note, not a gap in it.*

> **You are here:** rung 11 — the last engineering rung before the capstone.
> **Assumes you read:** [00](00-how-to-use-these-notes.md)–[10](10-traces-and-the-failure-taxonomy.md).
> Three one-line gists so you are never stranded: (1) each call to the model is **stateless**
> — it starts fresh and remembers nothing from the last call (note 05); (2) the **context
> window** is the fixed amount of text the model can see at once — miss the limit and the
> oldest text falls off (note 03); (3) the **scorecard** is the end-of-game report from the
> server, the one thing in the system that knows the goal (note 04).
> **After this you can:** say what "memory" really is for an agent, tell short-term from
> long-term memory using this project's own two cases, explain embeddings and RAG in one
> breath — and, the senior move, say **when not to reach for them.**

---

## Where we are

We have an agent that plays, a suite that judges it, traces that explain it, and a wall we can
put a number on (88% busy, 0% progress). This note is about the thing everyone means when they
say *"just give the agent a memory"* — and about doing it without fooling yourself.

Start with the fact that makes agent memory a real engineering problem at all:

::: key
**A language model has no memory of its own.** Every call is **stateless** (*starts fresh,
keeps nothing from the previous call*). It does not remember your last question, its own last
answer, or that it has been playing this game for forty turns. Whatever the agent must "know"
from one turn to the next, **you put back into the prompt yourself.**

So for an agent, *memory is not a brain. It is a discipline* — a set of choices about **what
you re-insert into the context on every call**, and how you phrase it. That single idea is the
whole of this note.
:::

Because you are choosing what to re-insert, the useful way to sort memory is **by how far back
it reaches** — what happened moments ago in this same game, versus what happened in a whole
earlier game. This project built one of each, so the two kinds are not abstract here; they are
two experiments you can re-run.

---

## Part 1 — Short-term memory: what just happened (the history window)

::: key
**Short-term memory** is what happened **recently, inside the game you are playing now** — the
last few turns. For our agent it is the **history window**: the agent's own last N actions and
what each one changed on screen, pasted into the prompt (`harness/frames.render_history`).
:::

Why we built it, in one line you already have: the agent pressed one button 41 times in a row
because it was being asked a question *with no memory in it*, and forty times is only visibly
absurd if you can see the other thirty-nine (note 05).

And it **backfired** — [note 08 Part 6](08-evals.md) has the experiment and the numbers: eight
past actions in the prompt, worse on most steering metrics (*the numbers that track whether its
play improved*), reverted. What belongs in *this* note is the reason, because it is a fact about
memory rather than about that one experiment:

::: warn
Eight lines of `ACTION3 -> 2 cells changed` read to me as *"you are stuck, stop."* **The model
read them as *"this action reliably works — keep going."*** The memory was perfectly accurate.
It just pointed the wrong way.
:::

::: key
**Memory is only as useful as the conclusion it lets the model draw.** A record of *what you
did* ("ACTION3 changed two cells") is not the same as feedback about *whether it helped*, and
if the model can read your memory as encouragement, it will. So the design question is never
just "should the agent remember?" — it is **what should it remember, and how should that be
phrased so the right conclusion is the easy one?** Getting that wrong makes memory an
accelerant for the failure, not a cure.
:::

---

## Part 2 — Long-term memory: what happened last time (the progress signal)

::: key
**Long-term memory** reaches back **across whole games** — what happened on a *previous
attempt*, carried into a new one. For our agent it is the **progress signal**
(`harness/progress_signal.py`, note 09): when a game is played twice, attempt one's
**scorecard** result is written into the opening prompt of attempt two.
:::

It reads, in the harness's own flat voice:

> *On your last attempt at this game you used 30 actions and cleared 0 of 7 levels. You did not
> clear even level 1. A reference player clears level 1 in 22 actions. What you did last time
> did not work; do something different.*

This is genuine cross-attempt memory, and it carries the one fact nothing *inside* a game can
know: the real goal, from the only thing that measures it. We checked, three ways, that the
agent actually received and read it (note 09). And the result, across all four dev games:

::: key
**It changed the agent's behaviour and moved the score not at all** — 0 levels before, 0
after. Long-term memory delivered the single most authoritative fact available, in plain words,
provably read, and the wall did not move. Because **knowing that you failed is not the same as
knowing what would have worked.** This is the same wall as notes 09 and 10, seen from the
memory side: the agent is not short of memory; it is short of a way to turn memory into a
better-chosen next action.
:::

So be precise about what this project's agent has. **It is not memoryless.** It has short-term
memory (Part 1) and long-term, cross-attempt memory (Part 2). Both were built, both ran. What
it lacks is not recall — it is the machinery that would use recall to choose differently.

---

## Part 3 — When memory gets big: retrieval, embeddings, and RAG

Notice a quiet assumption in Parts 1 and 2: both memories were **small enough to paste in
whole.** Eight lines. One summary sentence. You never had to *choose which* memories to show,
because they all fit.

That assumption breaks the moment memory gets large — a 500-page manual, or thousands of past
games. The context window is finite (note 03): you **cannot** paste it all, and even if you
could, burying the two relevant lines in a thousand irrelevant ones makes the model *worse*.
When memory is too big to include, you must **fetch only the slice that is relevant right
now.** That fetching is called **retrieval**, and here is the machinery it runs on.

::: key
An **embedding** is a **list of numbers** (*a "vector"*) that captures the **meaning** of a
piece of text, arranged so that **texts with similar meaning get similar numbers** — they sit
close together. A model turns text into this vector. "How do I reset my password" and "I forgot
my login" contain almost no shared words, yet their embeddings land near each other, because
their *meaning* is near. Comparing by meaning rather than by exact words is called **semantic**
(*by meaning*) search.
:::

With embeddings, retrieval is mechanical: turn the **current situation** into an embedding, and
fetch the stored memories whose embeddings are **nearest** to it. That gives you the handful of
past items most relevant to now, out of a store too big to read in full.

::: key
**RAG** — *Retrieval-Augmented Generation* — is the whole pattern in three steps: **retrieve**
the relevant slice of a big store (by embedding-nearness), paste it **into the prompt**, then
let the model **generate** its answer using it. RAG is how you give a model access to far more
knowledge than fits in its context window at once — a company's docs, a user's history, an
agent's thousands of past experiences — without trying to cram all of it into every call.
:::

---

## Part 4 — The honest part: why this project has no RAG

Everything in Part 3 is real, standard, and worth being able to explain. And this project
**does not use any of it.** Saying why — clearly, without apology — is a stronger answer than
bolting on a vector store to look current.

::: key
**RAG earns its place when two things are true at once: the memory is too big to fit in the
context, *and* you need only a relevant slice of it.** Neither is true here. Our agent's whole
memory is **tiny and discrete** — a handful of attempts, about eight kinds of action. It *all*
fits in the prompt. There is nothing to "retrieve," because there is nothing you would leave
out. Adding embeddings and a vector store would be pure complexity for **zero** payoff.
:::

There is a deeper reason, and it is the one that ties this note back to the whole project:

::: warn
**The bottleneck here was never recall.** The agent never lost a fact it needed — every fact it
could use was already in the prompt. The wall (notes 09, 10) is that *nothing in the loop turns
feedback into a better action.* RAG fetches relevant **past text**; it does not manufacture a
**goal signal**. So even a perfect memory-retrieval system would leave the score at zero. Fixing
a recall problem you do not have is the most expensive way to not fix the problem you do have.
:::

Being honest about *when it would* apply is part of the same answer. If the agent banked
hundreds of games' worth of experience and you wanted it to *"recall the most similar situation
you've seen before and what worked there,"* **that is exactly RAG over experience** — and that
is precisely the far-side work designed in [note 04](../04-learning-across-attempts-design.md)
and deliberately deferred. The concept is not wrong for this project; it is simply **not yet
earned**, and reaching for it early is the classic mistake:

::: note
"Add a vector database" the instant anyone says "memory" is **cargo-culting** (*copying a
pattern without understanding whether it fits*). Knowing **when not to** reach for RAG — because
the data fits in the window, or because recall was never the problem — is as much a part of
knowing the tool as being able to wire it up.
:::

---

## What to hold onto

1. A model is **stateless**; "memory" for an agent is a **discipline of what you re-insert into
   the prompt each call**, not a brain the model carries.
2. **Short-term memory** (this game) and **long-term memory** (across games) are both built here
   — the history window and the progress signal — so the agent is *not* memoryless.
3. Memory can point the **wrong way**: eight honest lines of "ACTION3 changed 2 cells" read to
   the model as *"this works,"* and the history experiment was reverted. *What* you remember and
   *how* you phrase it is the design.
4. **Embeddings** turn text into meaning-vectors so similar meanings sit close; **retrieval**
   fetches the nearest ones; **RAG** pastes that slice into the prompt before generating. That
   is how you use a memory too big for the window.
5. This project uses **none of it, on purpose**: the memory is tiny enough to include whole, and
   the wall is a missing goal signal, not missing recall. Knowing **when not to** use RAG is the
   part that reads as senior.

---

## Say it in an interview

**"How does your agent handle memory?"**
> "The model is stateless — every call forgets the last — so 'memory' is really a discipline
> about what I re-insert into the prompt each turn. I built two kinds: short-term, the agent's
> own recent actions within a game, and long-term, a summary of the previous *attempt* at the
> same game carried into the next one's prompt. So it has both a within-game and an
> across-game memory."

**"Short-term versus long-term — give me the concrete difference."**
> "Short-term was an 8-action history window — what I did in the last few turns of *this* game.
> Long-term was the previous attempt's scorecard result — 'last time you used 30 actions and
> cleared zero levels' — from a whole earlier game. One reaches back turns, the other reaches
> back games."

**"Do you use embeddings or RAG? Why not?"** *(the strong answer)*
> "No, deliberately. RAG earns its place when your memory is too big to fit in the context and
> you need to fetch just the relevant slice. My agent's entire memory is a handful of attempts
> and about eight action types — it all fits in the prompt, so there's nothing to retrieve.
> And more importantly, my bottleneck was never recall: the agent never lost a fact it needed.
> Its problem was that nothing in the loop turns feedback into a better action, and RAG fetches
> past text — it doesn't manufacture a goal. Adding a vector store would've been complexity for
> zero payoff. Knowing when *not* to reach for RAG mattered more here than knowing how to build
> it."

**"What actually is an embedding?"**
> "A list of numbers that captures the meaning of some text, arranged so that texts with similar
> meaning get similar numbers. 'Reset my password' and 'I forgot my login' share no words but
> land close together, because they mean the same thing. That's what lets you search by meaning
> instead of by exact words."

**"If you *did* want long-term memory over hundreds of games, how would you do it?"**
> "Then RAG would finally be earned. I'd store each past situation with its embedding and what
> action worked, and on a new situation retrieve the most similar past ones to inform the next
> move. That's exactly the far-side design I wrote up and deferred — it only makes sense once
> the experience store is too big to just include, which mine isn't yet."

**"You said the long-term memory didn't help — why keep it?"**
> "Because the null result is the finding. It was the one signal sourced from the thing that
> actually knows the goal, delivered in plain words and provably read, and the score still
> didn't move. That's what pins the wall down: the agent isn't short of memory, it's short of a
> way to turn memory into a better choice. Deleting the experiment would delete the evidence."

---

**Next:** [Study 12 — Budgets: tokens, cost, latency](12-budgets-tokens-cost-latency.md) — the
three budgets you actually spend on a free tier, and why the fastest model on paper was the
wrong one. Then [Study 13 — the interview story](13-the-interview-story.md) ties the whole
project into one answer.
