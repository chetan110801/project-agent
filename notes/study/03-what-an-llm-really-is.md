# Study 03 — What an LLM really is: tokens and the context window

*Written 2026-07-22. The most important note in the early ladder. Everything later —
context engineering, memory, budgets, why the agent breaks — is downstream of what's
here.*

> **You are here:** rung 3 of the ladder.
> **Assumes you read:** [Study 00](00-how-to-use-these-notes.md),
> [01](01-what-we-are-building.md), [02](02-the-words-you-need.md).
> **After this you can:** explain what a token is, what a context window is, why it is
> the hard constraint on every agent, and how cost, speed and quality all trace back to
> it.

---

## Start with what the model actually does

Strip away everything and a large language model does exactly one thing:

::: key
**Given a sequence of text, produce the text that most plausibly comes next.**
That's it. One function, from text to text. There is no memory, no goal, no plan, and
nothing that survives between calls.
:::

Everything that feels like more — a chatbot remembering your name, an agent pursuing a
goal across a hundred turns — is *engineering built around* that single function. When
ChatGPT "remembers" what you said earlier, no memory was involved: the whole
conversation was re-sent, from the top, on every single message.

Sit with that, because it explains almost everything that follows:

- The model has **no memory**, so *we* have to carry state (the situation as it stands)
  forward ourselves.
- The model has **no goal**, so *we* have to restate the goal every turn.
- The model has **no idea what happened last turn** unless we tell it again.

**Our agent's job is 90% deciding what to re-tell the model each turn.** That is not a
detail of the implementation. That is the work.

---

## Tokens: the atoms

The model doesn't read letters, and it doesn't read words. It reads **tokens** — chunks
of characters, somewhere between a letter and a word.

Roughly, for ordinary English:

| Text | Roughly how many tokens |
|---|---|
| A common short word (`the`, `cat`, `run`) | 1 |
| A longer or rarer word (`unbelievable`) | 2–4 |
| A page of prose (~500 words) | ~650–750 |
| A number like `0 0 3 0 0` | 5–10 |

::: warn
Every "roughly" above is a rule of thumb, not a measurement. Different models chop text
differently, so the same sentence is a different number of tokens on different models.
**When a number matters, you count it with the provider's token-counting endpoint — you
never estimate.** (There's a well-known trap here: people reach for OpenAI's `tiktoken`
library to count tokens for any model. It's the wrong tokeniser for anything but
OpenAI's models, and undercounts Claude's tokens by roughly 15–20% on ordinary text,
worse on code. Using the wrong counter silently corrupts every budget built on it.)
:::

### Why tokens instead of words

Two reasons, and knowing them is a genuine interview differentiator.

**Vocabulary size.** English has millions of word forms; a model can't have a slot for
each. Tokens give a fixed vocabulary (typically ~50k–200k chunks) that can spell
*anything* — including words invented after training, names, typos, other languages, and
code — by combining pieces.

**Nothing is unrepresentable.** A word the model has never seen still arrives as a
sequence of familiar chunks, so the model can do *something* sensible with it.

### The famous consequence

Ask a model how many letter *r*'s are in "strawberry" and it has historically struggled.
Not because it's stupid — **because it never saw the letters.** It saw two or three
chunks. Asking it to count letters is like asking you to count the brush strokes in a
printed photograph of a painting: the information was thrown away before you got there.

That's the shape of most "why is the AI dumb at this simple thing?" questions. Usually
the answer is: *the information you're asking about isn't in the representation it
receives.* It's a great thing to be able to explain calmly in an interview, because it
shows you understand the machine rather than just its outputs.

---

## The context window: the desk

Here's the constraint that shapes everything.

::: key
The **context window** is the maximum number of tokens the model can consider in one
call — your input *and* its output, counted together. Cross it and something must be
dropped. There is no "just a bit more".
:::

Picture a desk of fixed size. Everything the model can take into account has to fit on
that desk at once. Anything not on the desk does not exist as far as that call is
concerned — not "less important", **nonexistent**.

### How big is the desk? (checked 2026-07-22)

Real numbers, from Anthropic's current model reference:

| Model | Context window | Max output |
|---|---|---|
| Claude Opus 4.8 | 1,000,000 tokens | 128,000 |
| Claude Sonnet 5 | 1,000,000 tokens | 128,000 |
| Claude Haiku 4.5 | 200,000 tokens | 64,000 |

A million tokens is a big desk — roughly a few thousand pages of prose. Two things stop
that from making the problem go away:

**1. The free models we can actually use are smaller.** This project runs on free tiers
only. The models available to us for free have smaller windows than the flagship
figures above, and we'll record the exact numbers when we pick our model in Phase B —
measured, not remembered.

**2. Filling the window is not free, and not even always good.** More tokens means more
money, more waiting, and — counter-intuitively — often *worse* answers, because the
thing that mattered is buried in noise. "It fits" and "it helps" are different
questions, and only the eval suite (note 07) can tell them apart.

---

## Making it concrete: our agent's actual problem

Now the arithmetic that makes this real, using our game.

One ARC-AGI-3 frame is a **64 × 64 grid** = **4,096 cells**, each holding a number for a
colour. (Verified from the official SDK installed on your laptop: coordinates are capped
at 0–63, and a frame is a list of 2D integer grids.)

Write that grid out as text — digits with spaces and line breaks — and you're looking at
**several thousand tokens for a single screenshot of a single moment.**

::: warn
**Updated 2026-07-22 — now measured on a real frame.** That "several thousand" started as
arithmetic. It has been counted, on an actual 64 × 64 frame from the `ls20` game, recorded
in this repo (`runs/`, analysed by `scripts/analyze_run.py`, results in
`artifacts/run-report.json`):

| The same real frame, written as… | Tokens |
|---|---:|
| one character per cell, no separators | **1,471** |
| decimal numbers with spaces between them | **8,191** |
| a description of the objects in it | **468** |
| just what changed since the previous frame | **22** |

Same screen. Same information in the first two rows. **5.6× the cost.** That gap is the
subject of [note 06](06-context-engineering.md).

Still owed, and not rounded up: these counts come from `tiktoken`'s `o200k_base` — an
**OpenAI** tokeniser — so they compare formats against each other honestly but are *not* a
budget for another vendor's model (see the tokeniser trap above). The budget number gets
counted with the provider's own endpoint once we pick the model in Phase B.
:::

Now watch the problem appear:

| Turn | If we send every frame so far | Result |
|---|---|---|
| 1 | 1 frame | fine |
| 10 | 10 frames | getting heavy |
| 50 | 50 frames | probably over the window |
| 200 | 200 frames | far over, and expensive |

And a game can run many turns. So we hit the wall — not eventually, but early.

### The four ways out (this is the whole field in miniature)

Every technique in agent engineering is one of these four moves:

**1. Send less of each thing.** Don't send the raw grid — send a *description*. "A 3×3
blue square at (10,10); a red dot at (40,22); everything else empty." Thousands of
tokens become dozens. Cheap, fast — and lossy (some information is thrown away), so if
the discarded detail mattered, the agent goes blind. Measurable trade-off.

**2. Send fewer things.** Only the current frame and the previous one, not all 200. Most
of the history is genuinely irrelevant; the risk is that occasionally it isn't.

**3. Summarise the old stuff.** Replace 50 old turns with a paragraph: *"Tried ACTION1
and ACTION2 — no visible effect. ACTION3 moves the blue block down. Goal appears to be
reaching the green tile."* Fifty frames become fifty tokens. This is the highest-value
move in agent engineering, and the one with the sharpest failure mode: summarise away
the one detail that mattered and the agent is confidently wrong.

**4. Store it outside and fetch what's relevant.** Keep everything in a store, and each
turn retrieve just the pieces relevant to right now. This is **retrieval** — the same
machinery as RAG (note 02, Group F), applied to the agent's own past. Note 09.

::: key
These four moves — compress, drop, summarise, retrieve — **are** context engineering.
When an interviewer asks "how do you handle long contexts?", this is the answer, and
you now have a concrete grid-of-numbers example to hang it on.
:::

---

## The three costs of a token

Every token you put in the window costs you three separate things. Agent engineering is
the practice of trading them against each other on purpose.

### 1. Money

Models are priced per million tokens, and **output is always more expensive than input**
— typically ~5× — because generating is more work than reading. Current published rates
(checked 2026-07-22):

| Model | Input / 1M tokens | Output / 1M tokens |
|---|---|---|
| Claude Opus 4.8 | $5.00 | $25.00 |
| Claude Sonnet 5 | $3.00 | $15.00 |
| Claude Haiku 4.5 | $1.00 | $5.00 |

Work an example. Say our agent sends 5,000 tokens of context and gets 200 tokens back,
each turn, and plays 100 turns:

- Input: 5,000 × 100 = 500,000 tokens
- Output: 200 × 100 = 20,000 tokens

On the cheapest model above, that's about **$0.60 for one game**. Sounds like nothing —
until you run a 20-game eval suite after every change, several times a day. That's
where "just send everything" quietly turns into real money.

::: note
We pay $0 — free tiers only, by project rule. But free tiers are metered in the same
currency: tokens per minute and per day. So the arithmetic is identical, just with
*quota* where the dollars go. And knowing the real prices is what lets you answer
"what would this cost in production?" — a question interviewers genuinely ask.
:::

**Caching is the biggest lever here.** If the front part of your prompt is *byte-for-byte
identical* between calls, the provider can cache it: a cache read costs roughly a tenth
of a normal input token, while writing the cache costs about 1.25×. So repeated context
pays off from the second call onward. The catch — and this is the part people get wrong —
**caching is a prefix match: one changed byte anywhere near the front invalidates
everything after it.** Put a timestamp at the top of your system prompt and you've
silently destroyed your cache and never see an error. This is why an agent's stable
instructions go first and the volatile per-turn stuff goes last. (Note 10.)

### 2. Time

More tokens means a longer wait. Our agent makes one call per turn and a game is many
turns, so latency multiplies: two seconds per call across 100 turns is over three
minutes for one game — and an eval suite is many games. Speed isn't a nicety here; it
determines how many experiments you can run in a day, which determines how fast you
learn.

### 3. Attention

The subtle one. A model given 100,000 tokens does not attend to all of them equally.
Bury the critical fact in the middle of a huge context and the model may effectively
miss it — the well-documented "lost in the middle" effect.

::: key
**More context is not monotonically better** (it doesn't keep improving as you add
more). Beyond a point, adding context makes performance *worse*. This is exactly why
context changes have to go through the eval suite instead of being judged by intuition
— "I gave it more information, so it should be smarter" is the intuition, and it is
frequently false.
:::

---

## Two more dials worth knowing

**Temperature — how random the model is.** Near 0, it always picks its top choice:
repeatable and predictable. Higher, it takes chances: varied and creative, less
reliable. For us: *deciding the next action* wants low (be consistent, be debuggable);
*brainstorming theories about the game* may want higher (explore more possibilities).
Which is better is an empirical question, and note 07 is how we answer it.

::: note
Worth knowing for interviews: on the newest models this dial is disappearing. Anthropic's
current top models **reject `temperature` outright** — you steer behaviour with the
prompt and an "effort" setting instead. If someone asks about temperature, the strong
answer is: "conceptually it's the randomness dial, but on current frontier models it's
been removed in favour of prompt-level control and thinking-effort settings" (checked
2026-07-22).
:::

**Thinking / reasoning effort.** Recent models can spend extra tokens "thinking" before
answering — visible as a real cost you pay for a real quality gain. It's the same
trade-off as everything else in this note: tokens for quality. For an agent making
hundreds of calls, whether to pay for thinking on *every* action or only on hard ones is
a design decision — and, again, one the eval suite settles.

---

## What to hold onto

1. A model is a fixed function from text to text — no memory, no goal, no state.
2. It reads tokens, not words, which is why it's odd about letters and why everything is
   billed and limited in tokens.
3. The context window is a hard ceiling on what it can consider at once.
4. Our agent generates far more information than the window holds, so every turn is a
   *choice* about what goes in — and that choosing is the job.
5. Every token costs money, time, and attention. Attention is the one people forget, and
   the reason "more context" is not automatically better.

---

## Say it in an interview

**"Explain tokens and context windows."**
> "A token is the unit the model actually reads — a chunk of characters between a letter
> and a word. It's the unit of billing, of rate limits, and of the context window, which
> is the hard cap on how much the model can consider in a single call, input and output
> together. In an agent it's *the* binding constraint, because history grows every turn
> and the window doesn't."

**"So how did you handle it?"**
> "There are only four moves, and I used three. Compress: I never send the raw 64×64
> grid, I send a structured description of the objects in it. Drop: only the last couple
> of frames go in verbatim. Summarise: older turns collapse into a running set of beliefs
> about the game's rules. The fourth is retrieval over stored history, which I added
> later for cross-episode memory. Every one of those changed the score, and I have
> before-and-after eval numbers for each."

**"Isn't a million-token context window enough that this doesn't matter?"**
> "It removes the hard failure, not the problem. Three things still bite: cost and
> latency scale with tokens, so a big window is a big bill on every one of hundreds of
> calls; attention degrades with length, so burying the key fact in the middle measurably
> hurts accuracy; and the free tiers I was restricted to have much smaller windows
> anyway. I treated the window as a budget to spend well, not a limit to fill."

**"How do you count tokens?"**
> "With the provider's own token-counting endpoint, on the model I'm actually calling —
> never with an estimator and never with another vendor's tokeniser. `tiktoken` is
> OpenAI's; using it for a Claude budget undercounts by roughly 15–20% on prose and worse
> on code, and the error is silent, so every budget built on it is quietly wrong."

**"What would you do to cut cost?"**
> "In order of impact: prompt caching first, because agents re-send a near-identical
> prefix every turn — but that needs the prompt laid out stable-first, volatile-last,
> since caching is a prefix match and one changed byte at the front invalidates
> everything after it. Then cheap-model-first routing, escalating only when the cheap
> model's answer fails a check. Then context compression, measured against the eval suite
> so I know what the saving cost me in score."

---

**Next:** [Study 04 — ARC-AGI-3: the game our agent has to play](04-arc-agi-3-the-game.md)
