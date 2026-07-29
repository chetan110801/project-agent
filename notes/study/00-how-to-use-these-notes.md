# Study 00 — Start here: how to use these notes

*Written 2026-07-22. This is the front door. Read this one first, then read the rest in
number order. Nothing here assumes you know anything about AI, agents, or LLMs.*

> **You are here:** the beginning.
> **Assumes you read:** nothing.
> **After this you can:** say what this course is, how it is ordered, and where to
> start when you have 20 free minutes.

---

## Why these notes exist

You are building a portfolio project to get an AI-engineering job. Claude writes the
code. **You own the understanding.** In an interview nobody will ask you to type code
on the spot — they will ask you to *explain*: what you built, why you built it that
way, how you know it works, what broke, and what you would do differently.

So the code and the notes are two halves of one thing. The code is the proof. These
notes are the words.

::: key
These notes are a **course**, not a reference pile. They are meant to be read
**in number order**, once each, top to bottom. Each note is written assuming you have
read the ones before it — and assuming you have read *nothing else*.
:::

---

## The one rule that shapes everything here

Every note follows the same shape, because you told me the thing that kills learning
is a jump — a moment where a word or an idea shows up that was never explained, and you
quietly fall off (lose the thread) and stop understanding the rest.

So there is a hard rule now, written into this project's `CLAUDE.md` so every future
session obeys it:

> **No forward references.** A note may only use a word that an earlier note already
> explained, or that this note explains right there on the spot.

That is why the early notes look "too basic". They are supposed to. The basics are the
floor everything else stands on, and if the floor has a hole, the rest collapses.

---

## How each note is built

Every study note has the same five parts, always in the same place:

| Part | What it does |
|---|---|
| **You are here** | Where this note sits in the ladder |
| **Assumes you read** | Which earlier notes it stands on |
| **After this you can** | The exact thing you'll be able to *say* when you finish |
| The body | The teaching — plain words, one idea at a time, with real examples |
| **Say it in an interview** | Lines you can actually speak out loud, plus the follow-up questions an interviewer would ask and how to answer them |

Two more habits you'll see throughout:

- **Hard words get a short meaning in brackets right after them** — like *ambiguous
  (can be read in more than one way)*. Once per note, at first appearance. If a word
  ever appears bare and you don't know it, that is a bug in the note. Tell me and I
  fix it.
- **Every abstract idea gets something concrete** — a picture, a number, a real case —
  so you feel what it is *for*, not just what it means.

---

## The ladder — what you will read, in order

Every note below is now **✅ written**. Each was written as we built the thing it describes —
a note about a part we hadn't built yet would be guesswork, and this project does not do
guesswork.

### Part 1 — The ground (read these first)

| # | Note | What it gives you |
|---|---|---|
| 00 | **How to use these notes** ✅ | you are reading it |
| 01 | **What we are building, in plain English** ✅ | the whole project in words your non-technical friend would follow |
| 02 | **The words you need, in the order you need them** ✅ | every technical term in this project, defined, in dependency order |
| 03 | **What an LLM really is** ✅ | tokens, context window, prompt — the *physics* of everything we build |
| 04 | **ARC-AGI-3: the game our agent has to play** ✅ | the benchmark, the grid, the 8 actions, the scorecard |
| 05 | **The agent loop** ✅ | what an "agent" actually is, from first principles, with real code |

### Part 2 — The engineering (written as we build each one)

| # | Note | What it will give you |
|---|---|---|
| 06 | **Context engineering** ✅ | choosing what the model gets to see each step, and why that is the job |
| 07 | **Baselines** ✅ | how you *know* a change helped, instead of believing it did — with the run where the fix worked and the score still didn't move |
| 08 | **Evals** ✅ | turning one-off comparisons into a suite that runs on every change — and the metric I built, ran, and found was measuring nothing |
| 09 | **Exploration** ✅ | why the agent got stuck, and the progress signal I proved could not exist before I built it |
| 10 | **Traces and the failure taxonomy** ✅ | answering "why did it do that?" with receipts — and the counted catalogue of how the agent wastes its turns |
| 11 | **Memory and retrieval** ✅ | short-term vs long-term memory, embeddings, the honest version of RAG — and when *not* to reach for it |
| 12 | **Budgets: tokens, cost, latency** ✅ | the three budgets you actually spend on a free tier, and why the fastest model on paper was the wrong one |
| 13 | **The interview story** ✅ | the whole project as a 3-minute answer, with the hard follow-ups |

Note 12 was written **out of build-order** on purpose: it stands only on notes you have already
read (03, 06, 08, 09) and needs nothing from 10 or 11, so it was ready while those waited for
the parts they describe to be built. **The whole ladder is now written** — note 11 (memory) was
the last, once the agent's own two memory mechanisms (the history window and the progress
signal) gave it real, built cases to teach from instead of guesswork.

Alongside the course there are two other kinds of file in this repo, and it helps to
know what they are so you don't confuse them with teaching:

- **Project record** (`notes/01`, `02`, `03`, and `DECISIONS.md`) — the log of what we
  decided and why, written as we went. Useful later; not a course.
- **How-to walkthroughs** (`notes/howto/`) — click-by-click instructions for the things
  *you* have to do yourself, like getting an API key.

---

## Seeing it, not just reading it — the Explorer app

There is a small app in this repo that shows the whole project on one screen in your
browser. It needs no key, no internet, and nothing installed — one command starts it:

```powershell
py explorer/app.py
```

The click-by-click version is [how-to 03](../howto/03-run-the-explorer-app.md). Start it
once *before* you begin the course, so the things these notes talk about are pictures in
your head and not just words. Then, as you climb the ladder, open the tab that matches the
note you just finished:

| After you read | Open this tab | And you will see |
|---|---|---|
| 01, 13 | **Home** | the project's headline result, in one sentence |
| 04, 05, 06, 09 | **Replay** | a real recorded game replayed move by move — the screen, the action, and the model's own reason for it. The **⤷ Jump to where it got stuck** button takes you straight to the part this project is about |
| 07, 08 | **Evals** | the actual before/after numbers behind every claim in those notes |
| 10 | **Taxonomy** and **Traces** | the counted failure buckets, and the raw records they were counted from |
| 12 | **Budgets** | the tokens, the daily request limits, and the model comparison |

The app has a **Demo / Learn** switch in the top-right corner. Set it to **Learn** and every
view grows a plain-language explainer plus a link that opens the matching study note inside
the app. So the course and the app point at each other: the notes give you the words, the
app gives you the thing the words are about.

::: note
The app also has a **Live** tab that plays real games over the internet. Leave it alone
until you have read note 04 — and read the warnings in how-to 03 first, because one of its
two modes spends the daily free quota this project runs on.
:::

---

## How to actually read this

1. **In order.** 00 → 01 → 02 → 03 → 04 → 05 → 06 → 07 → 08 → 09 → 10 → 11 → 12 → 13.
   Don't skip ahead; the ladder only works as a ladder.
2. **One note per sitting.** Each is a 10–20 minute read. Finishing one and stopping
   beats skimming three.
3. **Read the "Say it in an interview" section out loud.** Silently reading a sentence
   and *saying* it are different skills, and only one of them is the one being tested.
4. **When something doesn't land, say so.** "Note 03, the part about the context
   window, didn't click" is the most useful sentence you can send me. The note gets
   rewritten, not patched with an explanation in chat that you'll lose.

::: warn
The one thing that will not work: reading these notes once, nodding, and assuming it
stuck. Understanding you can't *speak* isn't understanding yet — it's recognition
(you know it when you see it). The "Say it in an interview" sections exist to turn one
into the other.
:::

---

## Say it in an interview

You will not be asked about your study notes. But you will be asked *"how did you
learn this?"*, and this is a genuinely good answer:

> "I came from data science, so the whole LLM and agent stack was new to me. I built
> the project and a written course alongside it — every component I built, I wrote a
> plain-language note explaining what it is and why it's there, in an order where
> nothing is used before it's defined. It forced me to notice when I was cargo-culting
> [copying a pattern without understanding it] rather than understanding. The notes are
> in the repo."

**Follow-up an interviewer might ask:** *"Isn't that just documentation?"*
> "Documentation describes what the code does. This explains why the design is what it
> is — the decisions, the alternatives I rejected, and the evidence. There's a separate
> decision log with dates for exactly that reason."

---

**Next:** [Study 01 — What we are building, in plain English](01-what-we-are-building.md)
