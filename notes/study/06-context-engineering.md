# Study 06 — Context engineering: choosing what the model gets to see

*Written 2026-07-22, the day the agent first played a real game. Every number here was
measured on this laptop that day. The real-frame numbers come from
`scripts/analyze_run.py` reading the recording committed in `runs/`; the worst-case
numbers come from `scripts/measure_encodings.py`, which builds its grid by hand and says
so. Results are saved in `artifacts/`. The code is `harness/` and it was run: 35 tests
pass.*

> **You are here:** rung 6, the first note of Part 2 — the engineering.
> **Assumes you read:** [00](00-how-to-use-these-notes.md)–[05](05-the-agent-loop.md),
> especially [03](03-what-an-llm-really-is.md) (tokens, the context window, the four ways
> out) and [05](05-the-agent-loop.md) (the loop, and the hole called *decide*).
> **After this you can:** say what context engineering actually is, show four real
> encodings of the same screen with their measured costs, explain why format alone
> multiplied one bill by 5.6×, name the case where compression makes things *worse*, and
> tell the story of the three assumptions that real data destroyed.

---

## Where we are

Note 05 left the loop with a hole in it:

```text
observe → DECIDE → act → observe → DECIDE → act → …
                ↑
        this is where the model call goes
```

Before that call can happen, something has to turn the game's **grid of numbers** into
**text**, because text is the only thing a model can read (note 03). There is no default
and no obvious choice. We choose — every turn.

::: key
**Context engineering** is deciding what text goes into the model's context window on
each turn, and what doesn't. In an agent it isn't one job among many. It *is* the job:
the model is fixed, the loop is eleven lines, and the only real lever we hold is what the
model gets to look at.
:::

Note 03 named the four moves — **compress, drop, summarise, retrieve**. This note does
the first one for real, and measures what it costs instead of guessing.

---

## The thing we have to write down

One frame is a grid of numbers, at most 64 × 64 = 4,096 cells (note 04). Here is a tiny
4 × 4 version so you can see all of it at once — think of a screen with a 2 × 2 blue block
and a single red dot:

```text
0 0 0 0
0 4 4 0
0 4 4 0
0 0 0 3
```

We built three ways to write that down. They live side by side in `harness/frames.py` on
purpose — so they can be compared rather than argued about.

### Encoding 1 — the raw grid (`render_grid`)

Every cell, exactly as it is. *Encoding* just means "a way of writing something down".

```text
0000
0440
0440
0003
```

**Lossless** — nothing is thrown away. Also the biggest, and the format details turn out
to matter enormously.

### Encoding 2 — the objects (`render_objects`)

Instead of pixels, describe the *things*. The code finds connected blocks of same-valued
cells — a standard flood fill: start at a cell, spread outward to touching cells with the
same value, and you've found one blob — then describes each:

```text
grid 4x4, background 0, 2 objects
colour 4: filled rect 2x2 at rows 1-2, cols 1-2 (4 cells)
colour 3: 1 cell at (r3, c1)
```

**Lossy** — some information is thrown away, here the exact layout of anything that isn't
a neat rectangle. Much smaller.

### Encoding 3 — the change (`render_diff`)

Don't describe the screen. Describe what changed since last turn:

```text
2 cells changed: (r1, c1) 4->0; (r1, c2) 0->4
```

or, when the last action did nothing at all:

```text
nothing changed
```

Useless alone — you can't reason about a game from a list of changes with no picture of
the board. Extremely valuable *next to* one of the others.

---

## The measurements, on real frames

This table is one real 64 × 64 frame from the `ls20` game, taken from the committed
recording of the first live run:

| Encoding | Characters | Tokens | Size vs packed |
|---|---:|---:|---:|
| raw grid, hex-packed (`0440`) | 4,159 | 1,471 | 1.00× |
| raw grid, decimal, space-separated (`0 4 4 0`) | 8,243 | 8,191 | **5.57×** |
| objects | 1,085 | 468 | 0.32× |
| diff vs the previous frame | 66 | **22** | 0.015× |

And one grid that no real frame produced, built by hand to break the object encoding — a
checkerboard, every other cell filled, i.e. 2,048 separate one-cell objects:

| Encoding (worst case, synthetic) | Characters | Tokens | Size vs packed |
|---|---:|---:|---:|
| raw grid, hex-packed | 4,159 | 1,471 | 1.00× |
| objects, uncapped | 62,886 | **30,735** | **20.9×** |
| objects, with our cap | 1,266 | 626 | 0.43× |

::: warn
**Where these numbers come from, exactly.** The first table is measured on a real frame
from a real game. The second is deliberately synthetic — real recordings happen to contain
no adversarial (worst-case, chosen to break it) frame, and that is luck rather than
safety, so the worst case is constructed by hand.

The token counts use `tiktoken`'s `o200k_base` — **an OpenAI tokeniser.** As note 03
warned, that is the wrong counter for a Claude or Gemini budget. It is used here for one
legitimate job: comparing encodings against each other under one consistent ruler. Every
token number in this repo travels with the name of the tokeniser that produced it. The
character counts are exact and depend on no vendor at all.
:::

---

## Finding 1 — format costs tokens even when it carries no information

Same 4,096 cells, same information, written two ways: **1,471 tokens versus 8,191.**
Putting a space between the numbers multiplied the cost by **5.6×** and told the model
nothing new.

Why? Tokens are chunks, not characters (note 03). Checked directly with the tokeniser:

```text
'00000000'         → 3 tokens:  ['000', '000', '00']
'0 0 0 0 0 0 0 0'  → 15 tokens: ['0',' ','0',' ','0',' ','0',' ','0',' ','0',' ','0',' ','0']
```

The tokeniser packs runs of digits three-to-a-token for free. Put a separator between them
and every character becomes its own token; the compression you were getting for nothing is
destroyed by the space you added "for readability".

::: key
**Prompt format is a cost decision, not a style decision.** Pretty-printing data for a
model can multiply your token bill several-fold for zero information gained, and it never
shows up as an error — just as a bill. You find it in ten minutes by encoding the same
content two ways and counting.
:::

---

## Finding 2 — the object view saves ~3×, and my first estimate was 4× too optimistic

On the real frame: 1,471 tokens → 468. Roughly a **3× saving**, at the cost of exact
pixel detail.

Worth telling honestly, because it is the more useful lesson: **before the real frames
arrived I measured this same encoder on a grid I invented, and got a 14× saving.** My
made-up screen had a few tidy shapes on a big empty field. Real game screens are busier,
so there is far more to describe and the compression is a third as good.

::: key
Nothing was wrong with the code. The *test input* was flattering, and a flattering input
produces a number that is real, reproducible, and misleading. This is the commonest way
benchmarks lie, and it is worth being able to describe: my synthetic 14× would have been a
completely honest number to put in a README, and it would have been wrong by 4×.
:::

And even the 3× is only the *cost* side. Whether the discarded detail mattered — whether
the agent still plays as well — is a question about behaviour, and behaviour is measured
by the eval suite in note 07. **Cost is knowable today; benefit is not.**

---

## Finding 3 — compression can invert, and the worst case is the one that bites

The checkerboard row is the one I'd put on a slide. On that grid the object description is
**21× larger than the pixels it replaced.** The compression scheme became a decompression
scheme.

That is the shape of a real outage:

1. You measure your clever encoding on a few normal screens. It looks like a win.
2. You ship it. It works, for a while.
3. The game reaches a busy, cluttered state — exactly the interesting part — and the
   encoder silently emits thirty thousand tokens instead of five hundred.
4. The request blows the context window or the rate limit, and the agent dies **at the
   hardest moment of the game**, which is the one you least wanted to lose.

So `render_objects` carries a guardrail (notes 02 and 05): a cap that truncates the list
and *says in the output that it truncated*. With the cap, that checkerboard costs 626
tokens instead of 30,735.

::: key
Truncating loses information — but **loudly and boundedly**, at a place we chose, instead
of silently and without limit. That is the entire difference between a guardrail and a
bug. And it only surfaced because we deliberately fed the encoder its worst input instead
of three friendly ones.
:::

---

## Finding 4 — "nothing changed" costs 2 tokens and kills the commonest failure mode

Note 05's failure mode number one was the stuck loop: press ACTION1, nothing happens,
press ACTION1 again, forever, because nothing in the context says the last press did
nothing.

Diffing the previous frame against the current one and saying `nothing changed` costs
**two tokens**. Two. It is free.

Generalise it, because this travels well past this project: **the highest-value thing you
can put in an agent's context is usually not more description of the world — it's feedback
about the agent's own last action.** Cheap to produce, tiny to send, and it addresses the
failure mode that wastes the most turns.

---

## Finding 5 — the baseline threw away 47% of its budget, and no model was needed to fix it

This is the one that surprised me most, and it came out of the very first live run.

The `ls20` game tells you, in every single frame, which buttons exist. Across all 81
frames the answer never changed: **`available_actions` was `[1, 2, 3, 4]`** — four buttons,
not eight.

The SDK's `Random` agent ignores that field and picks from all eight. Measured over the
run:

- **38 of its 80 actions** were buttons the server had already said were unavailable.
- **38 of the 80 transitions changed nothing on screen** — and they are the *same 38*.

::: key
**47.5% of the action budget was spent pressing buttons that do not exist.** Not a subtle
bug, not a model quality problem: a field in the response that the agent didn't read. The
fix costs one line — filter the choice by `available_actions` — and it is worth up to
double the effective budget before any cleverness, any prompt, any model.
:::

Our loop (`harness/loop.py`) refuses to send an action that isn't in the current frame's
`available_actions`, records the refusal in the trace, and falls back. That guard existed
before this run for a different reason — a language model will eventually invent
`ACTION9`. It turns out the *dumb* baseline needed it just as badly.

There's a general lesson worth stealing: **look at what the environment is already telling
you before adding intelligence to guess it.** Half the budget was recoverable by reading a
field that was in every response all along.

---

## What real data broke: three assumptions, in one run

Everything above the fold in this note existed the morning of the run, written against
grids I invented. Then 81 real frames arrived and broke three things. This is the honest
value of getting to real data early, so it's written down rather than quietly patched:

| I assumed | Reality (measured) | What it would have caused |
|---|---|---|
| Cell values are single digits 0-9 | Values reach **12** in `ls20` | The packed encoding was *ambiguous*: `12` reads as `1,2`. The model would have seen a subtly wrong grid, with nothing to notice. Now cells are written as one hex character (`0`-`f`). |
| Background is colour 0 | Colour **4** covers 2,609 of 4,096 cells; colour 0 appears **3 times** | The object encoder described the *floor* as one 2,509-cell object — its biggest, most prominent line was pure noise. Background is now inferred as the most common value. |
| A frame is one grid | 80 frames had one grid; **one frame had six** — an animation returned for a single action | Code taking `frame[0]` would show the model a stale mid-animation picture. We take the last grid: the state the world settled into. |

None of the three was carelessness — each was the reasonable guess. All three were wrong,
all three were caught within minutes of the first real run, and none would have thrown an
error. They would have quietly degraded the agent while every test still passed.

::: key
This is the argument for the cheapest possible end-to-end run *first* (note 05's random
baseline). It scored zero, as expected — and it paid for itself three times over in
assumptions destroyed before they could be built on.
:::

---

## What we built, and what we deliberately have not decided

Built and tested today — `py -m unittest discover -s tests`, 35 tests, all passing:

| File | What it does |
|---|---|
| `harness/frames.py` | the encodings, blob finding, background inference, diffing |
| `harness/actions.py` | an immutable action record (see the footnote) |
| `harness/policies.py` | the *decide* step, isolated and swappable; a seeded random baseline |
| `harness/loop.py` | our loop: hard action cap, illegal-action rejection, stuck detection |
| `harness/trace.py` | one JSON object per line, per decision — the receipts (note 08) |
| `harness/tokens.py` | sizes; never a token count without naming the tokeniser |
| `harness/mock_game.py` | a fake game that runs offline, so all of the above is testable with no key and no quota |
| `scripts/analyze_run.py` | turns a real recording into the numbers this note quotes |

**Not decided: which encoding the agent will actually use.** Deliberately. Picking now
means picking on taste; the eval suite that can settle it doesn't exist yet. The encodings
sit side by side, measured, waiting for note 07 to choose with numbers.

::: note
**A footnote worth having in your pocket.** Reading the SDK source turned up a genuine
trap: its `GameAction` is a Python `Enum`, and each member stores the payload for the
current call *on itself* (`action.set_data({"x": 12, "y": 40})`). Enum members are
singletons — one shared object per name for the whole program — so that write is global.
Two agents in one process, or one agent preparing several candidate actions before
choosing, would silently overwrite each other's coordinates. Our harness passes an
immutable record around and only touches the enum where a request is actually sent.
"I read the library's source and designed around a shared-mutable-state trap in it" is a
specific, checkable thing to bring to an interview.
:::

---

## What to hold onto

1. The model can't see a grid — only text. Someone chooses that text. That choice is
   context engineering, and it's the job.
2. Format is a cost: identical information, spaced out for readability, cost **5.6×** more
   tokens.
3. Compression is a trade, not a free win: ~3× smaller on a real frame, at the price of
   detail — and **21× bigger** on the worst case, so it needs a guardrail.
4. Feedback about the agent's own last action is the cheapest valuable context there is:
   "nothing changed" costs 2 tokens and kills the commonest failure mode.
5. Read what the environment already tells you before adding intelligence: **47% of the
   baseline's budget went on buttons that didn't exist.**
6. Get to real data as early as possible. One 80-action run that scored zero destroyed
   three wrong assumptions that no test would have caught.

---

## Say it in an interview

**"What do you mean by context engineering?"**
> "Deciding, every turn, what text the model actually sees — and what it doesn't. My
> environment sends a 64×64 grid of integers, and a model can't see a grid, only text. So I
> wrote several encodings of the same screen — raw pixels, an object-level description, and
> a diff against the previous frame — and measured each instead of picking by taste. It's
> the highest-leverage thing in the system, because the model is fixed and the loop is
> eleven lines; the context is what I control."

**"Give me a concrete result."**
> "Two. First, writing the grid with separators instead of packed cost 5.6× the tokens for
> identical information — 8,191 versus 1,471 — because the tokeniser packs digit runs three
> to a token and a separator defeats that. Formatting a prompt 'for readability' can
> multiply your bill several-fold and it never surfaces as an error. Second, and bigger:
> the environment advertises which actions are legal in every frame, and the stock baseline
> ignored it — 38 of its 80 actions were buttons that didn't exist, and those were exactly
> the 38 that changed nothing. Reading a field that was in every response was worth 47% of
> the action budget, before any model was involved."

**"Did compression work?"**
> "About 3× on a real frame, and it's lossy. But the number I'd actually report is the
> failure case: on a checkerboard — 2,048 one-cell objects — the 'compressed' form was 21×
> *larger* than the raw grid. So the encoder caps its output and states that it truncated.
> A compression scheme has to be measured on its adversarial input, because it'll meet that
> input exactly when the state gets complicated, which is when you least want it to fail."

**"Tell me about something you got wrong."**
> "I built the encoders before I had real data, against grids I made up, and the first real
> run broke three assumptions in eighty actions. Cell values went above 9, so my packed
> decimal encoding was ambiguous — `12` reads as `1,2` — and the model would have seen a
> subtly wrong grid with no error anywhere. Background wasn't colour 0, it was colour 4
> covering 64% of the screen, so my object encoder was describing the floor as the biggest
> object on screen. And one frame came back with six grids instead of one — an animation —
> so taking the first grid would have shown a stale picture. All three failed silently with
> every test passing. It's why I now spend the first run on the dumbest possible agent
> end-to-end: it scored zero and paid for itself three times over."

**"How are you counting tokens?"**
> "Characters where I can, since those are exact and vendor-independent, and tokens with
> the tokeniser named next to every number. Those counts are OpenAI's `o200k_base`, which
> is the wrong counter for a Claude or Gemini bill — I used it only to compare encodings
> under one consistent ruler. A real budget gets counted with the provider's own endpoint
> on the model I'm actually calling."

---

**Next:** note 07 — evals: how you know a change helped instead of believing it did. It
gets written when the eval suite exists, because the entire point of that note is that
claims arrive with numbers.
