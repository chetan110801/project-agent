# Study 02 — The words you need, in the order you need them

*Written 2026-07-22. This is the dictionary for the whole course — but sorted so you can
read it top to bottom like a story, because each word is built from the ones above it.
Don't memorise it. Read it once now, and come back when a later note uses a word you've
gone fuzzy on.*

> **You are here:** rung 2 of the ladder.
> **Assumes you read:** [Study 00](00-how-to-use-these-notes.md),
> [Study 01](01-what-we-are-building.md).
> **After this you can:** hear any sentence in an AI-engineering interview and know what
> every word in it means.

---

## How to read this note

Seven groups, in dependency order — each group uses only words defined above it. Every
entry is the same three lines:

- **The word** — one plain sentence saying what it is.
- *Picture:* something concrete, so it isn't just a definition.
- *Why it matters here:* where it shows up in our project.

::: warn
Do not try to hold all of this in your head today. The job of this note is that
**nothing in notes 03–11 is ever a surprise word.** You'll re-meet each of these in
context, which is where they actually stick.
:::

---

## Group A — What a "model" is

**Model.** A big pile of numbers that turns an input into an output. That's it. Nothing
is "understood" or "stored as facts" inside it — there are just numbers that were
adjusted until the outputs came out useful.
*Picture:* a spice mix tuned over thousands of attempts until the dish tastes right. The
mix doesn't "know" the recipe; it just produces the taste.
*Why it matters:* when someone asks "does the model know X?", the honest answer is
always about behaviour, never about knowledge.

**Parameters (also called weights).** The individual numbers inside the model. Modern
language models have billions of them. "A 7B model" means seven billion parameters.
*Picture:* the knobs on a mixing desk. Billions of knobs, each set to a specific value.
*Why it matters:* parameter count is the rough size dial — bigger usually means smarter,
slower and more expensive. Our project never trains any, but you'll be asked about them.

**Training.** The process of adjusting those numbers by showing the model huge amounts of
data and nudging the knobs whenever it gets something wrong. It's expensive, slow, and
needs specialised hardware.
*Picture:* thousands of practice rounds with a coach correcting you after each one.
*Why it matters:* **we do zero training in this project** — deliberately. Training needs
GPUs we don't have. Everything we do happens at the *next* word.

**Inference.** Actually *using* a trained model — you give it an input, it gives you an
output. Cheap and fast compared to training.
*Picture:* training is learning to cook; inference is cooking one meal.
*Why it matters:* this whole project is inference. Every mention of "calling the model"
means one inference.

**LLM (Large Language Model).** A model trained on an enormous amount of text, whose one
skill is: given some text, produce the text that plausibly comes next. ChatGPT, Claude
and Gemini are products built on LLMs.
*Picture:* the world's most well-read autocomplete.
*Why it matters:* the "decide what to press next" step of our agent is an LLM call.
Everything else in the project is scaffolding around that one act.

**Frontier model.** Informal term for the most capable models available at a given
moment. It's a moving label — today's frontier model is next year's baseline.
*Why it matters:* "the best frontier model scores ~7.8% on ARC-AGI-3" (checked
2026-07-21) is how we describe how hard our benchmark is.

::: key
Everything in Group A collapses to one sentence worth remembering: **a language model is
a fixed function from text to text.** It doesn't learn while you use it, it doesn't
remember your last conversation, and it has no state of its own. Every appearance of
memory or learning in an agent is something *we* built around it. Internalise that and
half of agent engineering becomes obvious.
:::

---

## Group B — Talking to a model

**Token.** The unit a model reads and writes. Not quite a word — it's a chunk of
characters. Common words are one token; rare words split into several.
*Picture:* `"unbelievable"` might arrive as `un` + `believ` + `able` — three tokens.
*Why it matters:* you are billed per token, limited per token, and slowed per token.
Tokens are the currency of this entire field. Note 03 is largely about them.

**Tokenisation.** The step that chops your text into tokens before the model sees it.
*Why it matters:* it's why models are oddly bad at counting letters in a word — they
never see the letters, only the chunks.

**Context window.** The hard maximum number of tokens a model can look at in one call —
your input and its output together. Go over it and something must be dropped.
*Picture:* a desk of a fixed size. Everything the model can consider has to physically
fit on that desk at once. Anything else may as well not exist.
*Why it matters:* this is *the* constraint that shapes agent design. Our agent plays
hundreds of turns; the full history will never fit; so every turn we must choose what
goes on the desk. That choosing has a name — see Group C, *context engineering*.

**Prompt.** The text you send the model.
*Why it matters:* in an agent, the prompt isn't hand-written once — it's *assembled by
code*, freshly, every single turn.

**System prompt.** A special instruction block placed before everything else, setting the
model's role and rules for the whole conversation.
*Picture:* the briefing you give a new hire on day one, versus the individual tasks you
give them after.
*Why it matters:* the agent's standing rules — "you are playing an unknown game, here
are the eight legal actions, always reply in this format" — live here.

**Completion (or response, or generation).** What the model sends back.

**Temperature.** A dial from roughly 0 to 1+ controlling randomness. Near 0, the model
picks the most likely next token every time — repeatable, predictable, boring. Higher,
it takes chances — varied, creative, less reliable.
*Picture:* 0 is a person who always orders their usual; 1 is a person who tries the
weird thing on the menu.
*Why it matters:* a real design decision for us. Deciding *which action to take* wants
low temperature (be consistent). *Generating candidate theories about the game* may want
higher (be varied). Both are testable choices, and note 07's eval suite is how we test
them instead of guessing.

**Sampling.** The general name for how the model picks each next token from its ranked
options. Temperature is one sampling control.

**Hallucination.** When a model states something false with complete confidence. Not a
bug to be patched — a direct consequence of what a model *is* (Group A: a function
producing plausible next text, with no fact-checker inside).
*Why it matters:* our agent will hallucinate rules the game doesn't have. The defence
isn't hoping — it's the loop: any theory gets *tested* against the real game, and gets
dropped when the game disagrees.

**API (Application Programming Interface).** A way for one program to ask another program
for something over the internet. You send a structured request; you get a structured
answer.
*Picture:* a restaurant's ordering window. You don't enter the kitchen; you pass a
written order in and food comes out.
*Why it matters:* we use two APIs — one to play the game, one to call the language model.

**API key.** A long secret string that identifies you to an API, like a password for
programs.
*Why it matters:* it must never be committed to the repository. Ours lives in an
untracked `.env` file. Leaked keys get abused and billed. This is the *first* thing a
security-conscious interviewer checks in a portfolio repo.

**SDK (Software Development Kit).** A ready-made code library that wraps an API so you
write `agent.take_action(...)` instead of hand-building web requests.
*Why it matters:* ARC Prize ships an official Python SDK (`arc-agi-3`) — installed and
verified on your laptop. We use it for the plumbing and write our own agent on top.

**Latency.** How long a call takes to come back, usually in milliseconds or seconds.
*Why it matters:* our agent makes one model call per turn and a game runs many turns —
so latency multiplies. It's a first-class number in our traces, not an afterthought.

**Rate limit.** A cap on how many calls you may make per minute or per day.
*Why it matters:* free tiers are generous on price and strict on rate. Handling
"slow down, you've hit the limit" gracefully is a reliability feature we have to build.

**Free tier.** The amount of a paid service you can use for nothing.
*Why it matters:* a hard project constraint — no paid APIs, ever. It's also a genuine
engineering story: staying useful inside a tight budget.

---

## Group C — Building something with a model

**Agent.** A program that repeatedly looks at a situation, decides an action, performs it,
observes the result, and goes again — pursuing a goal without a human in the loop each
step. When the deciding is done by an LLM, it's an LLM agent.
*Picture:* a thermostat is the simplest possible agent — observe temperature, decide,
act, repeat. Swap the thermostat's rule for a language model and you have ours.
*Why it matters:* it's the noun in your job title. Being able to define it plainly, with
no hype, is a real interview advantage.

**Agent loop.** The cycle itself: **observe → decide → act → observe…** Everything else in
agent engineering is a question about one of those four arrows.
*Why it matters:* note 05 builds ours from scratch, with real code.

**Observation.** What the agent perceives at one moment. Ours: a 64×64 grid of numbers,
plus the score and game state.

**Action.** One thing the agent can do. Ours: exactly eight — RESET, six simple button
presses, and one click at a coordinate.

**State.** Everything true about the world right now. In our game the state is what the
grid shows; the agent's *belief* about the state is a separate, often wrong, thing.
*Why it matters:* the gap between real state and believed state is where nearly every
agent failure lives.

**Episode.** One complete run from start to finish — here, one play of one game.

**Tool use (function calling).** Letting a model trigger real code — search the web, run
a query, press a button — rather than only emitting text.
*Picture:* the difference between an advisor who tells you what to do and one who's been
given the keys.
*Why it matters:* our agent's eight game actions are its tools. It's the same concept
interviewers mean by "function calling", in its simplest possible form.

**Context engineering.** Deciding what goes into the context window on each call — which
observations, how much history, which remembered lessons, in what order, and what gets
compressed or dropped.
*Picture:* briefing a colleague who has 30 seconds and no memory of yesterday. What do
you tell them, and in what order?
*Why it matters:* it is the highest-leverage work in the whole project, and note 06's
entire subject.

**Framework.** A pre-built library that gives you an agent loop for free (LangGraph,
smolagents and similar).
*Why it matters:* **we deliberately don't use one for the core loop.** A framework hides
exactly the parts an interview asks you to explain. Knowing they exist and why you chose
not to use them is a stronger answer than having used one.

---

## Group D — Knowing whether it works

**Benchmark.** A standard test set everyone measures against, so numbers can be compared
across people.
*Why it matters:* ARC-AGI-3 is ours. We didn't invent the test — which means our number
means something to a stranger.

**Metric.** One specific number you measure. Ours: score per game, actions until first
progress, tokens spent per game, cost per game, latency per call.
*Why it matters:* "it got better" is a feeling. A metric is a claim.

**Baseline.** The simple, dumb version you compare everything against. Ours is a random
agent — it presses buttons at random.
*Picture:* before claiming your diet works, you need to know what happens if you do
nothing.
*Why it matters:* without a baseline, a number is meaningless. "Score 3" means nothing
until you know random scores 1.

**Eval (evaluation).** A repeatable measurement of your system on a fixed set of cases
with fixed metrics. Run it before a change and after, and the difference tells you
whether the change helped.
*Picture:* a blood test. Same test, same conditions, so the before/after comparison is
real.
*Why it matters:* this is the single most-probed skill in 2026 AI-engineering interviews,
and note 07's subject. Our project rule: **no prompt, model or loop change is kept
without before/after eval numbers.**

**Dev set and held-out set.** Split your test cases in two. You tune against the *dev*
set as much as you like. You touch the *held-out* set only to report final results.
*Picture:* practice papers versus the actual exam. Study the exam paper in advance and
your score stops meaning anything.
*Why it matters:* tuning on the data you report is the cardinal sin of ML, and this
project's decision log calls it exactly that. Getting this right in a portfolio project
signals seniority faster than almost anything else.

**Regression.** When a change makes something that used to work stop working.
*Why it matters:* our rule is that a regression either gets reverted or gets a written
justification. Nothing silently rots.

**Ablation.** Deliberately removing one piece to measure how much it was contributing.
*Picture:* to find out whether the salt matters, cook it once without salt.
*Why it matters:* it's how you prove a component earns its place. "Memory helps" is a
claim; "the suite scores 22% with memory and 14% without, same seeds" is evidence.

**Reproducibility.** A stranger can re-run your work and get your numbers.
*Why it matters:* it's the project's whole thesis. One command re-runs the suite; every
number in the README traces to a committed run artifact.

**Artifact.** A file produced by an actual run — a results table, a log, a scorecard —
committed to the repo as evidence.
*Why it matters:* project rule: **every number in a note traces to an artifact or a cited
source checked that day.** Nothing comes from memory.

---

## Group E — Running it for real

**Trace.** The complete record of one operation: what went in, what came out, how long it
took, what it cost. For an LLM call: the exact prompt, the exact reply, token counts,
latency, price.
*Picture:* a flight recorder. After a crash you don't guess — you read the box.
*Why it matters:* it's how "why did it do that?" gets an answer instead of a theory.
Note 08.

**Observability.** The general property of a system you can inspect from the outside well
enough to explain its behaviour. Traces and logs are how you get it.
*Why it matters:* the word interviewers use. Traces are the mechanism; observability is
the goal.

**Failure taxonomy.** A sorted catalogue of the distinct ways your system fails, with
counts, built by reading real traces.
*Picture:* a doctor doesn't treat "feeling unwell" — they name the illness first.
*Why it matters:* it converts "the agent is bad" into "31% of failures are repeating a
known-dead action, 22% are misreading the grid" — and each named bucket becomes a fix
and an eval case. This is the single most impressive thing a junior can bring to an
interview.

**Token budget.** A hard cap on tokens spent per game or per run, enforced in code.
*Why it matters:* it makes cost a *design parameter* instead of a monthly surprise, and
it gives us the cost-versus-score curve in note 10.

**Caching.** Saving the result of expensive work so an identical request is answered from
storage instead of being recomputed.
*Why it matters:* agents repeat themselves constantly. Caching is often the largest single
cost saving available, for almost no complexity.

**Model routing.** Sending easy requests to a cheap, fast model and only escalating hard
ones to an expensive model.
*Picture:* triage in an emergency room.
*Why it matters:* one of the highest-value production patterns in the field, and easy to
demonstrate honestly with an eval suite behind it.

**Guardrail.** A check that stops the system doing something forbidden or nonsensical —
validating the model's output, capping retries, refusing an illegal action.
*Why it matters:* the model *will* eventually reply "press ACTION9". Our code must reject
that rather than crash.

---

## Group F — Memory and retrieval

**Embedding.** A piece of text converted into a list of numbers, arranged so that texts
with similar meaning get similar lists.
*Picture:* a map where every sentence is a dot, and sentences about the same thing land
near each other — regardless of the exact words used.
*Why it matters:* it's how a computer measures "similar in meaning" rather than "shares
keywords".

**Vector.** The list of numbers itself. An embedding *is* a vector.

**Similarity search.** Given one vector, find the stored vectors nearest to it — i.e.
find the most related pieces of text.

**Vector store (vector database).** Storage built to do similarity search fast over many
vectors.

**Retrieval.** Fetching the most relevant stored items and putting them into the prompt,
so the model can use information it was never trained on.

**RAG (Retrieval-Augmented Generation).** The pattern of: retrieve relevant text →
paste it into the prompt → let the model answer using it. The standard way to make a
model answer about *your* documents.
*Picture:* an open-book exam. The model isn't smarter; it just has the right page open.
*Why it matters:* interviews ask about RAG constantly. **Our project does the same
mechanics, but over the agent's own past experience instead of a document folder** — so
you can discuss chunking, retrieval quality and relevance from something you actually
built, without shipping the same doc-chatbot everyone else has. Note 09.

**Chunking.** Splitting long text into pieces small enough to embed and retrieve
usefully. Chunk too big and you retrieve noise; too small and you lose the context that
made it meaningful.

---

## Group G — The plumbing you'll be touching

**Repository (repo).** A project folder tracked by Git, with full history of every change.
Ours: `github.com/chetan110801/project-agent`.

**Commit.** One saved snapshot of changes, with a message explaining them.

**Push.** Uploading your commits to GitHub so they exist somewhere other than your laptop.
*Why it matters:* project rule — a session that changed things but pushed nothing is an
unfinished session.

**Branch.** A parallel line of work. Ours is `main`.

**Environment variable.** A setting stored outside your code, in the operating system or a
file, that your code reads at runtime.
*Why it matters:* it's how secrets stay out of source code. Our API key is the
environment variable `ARC_API_KEY`.

**`.env` file.** A plain text file holding environment variables for one project, listed
in `.gitignore` so Git never uploads it.
*Why it matters:* this is the specific mechanism that keeps your key off GitHub.

**`.gitignore`.** A list of files Git must never track. `.env` is in ours.

**CLI (Command-Line Interface).** A program you run by typing a command instead of
clicking. You'll run these in PowerShell.

**JSON.** A plain-text format for structured data — the standard shape of API requests
and replies.

**Markdown.** The simple text format these notes are written in. `#` makes a heading,
`**bold**` makes bold. Our `build_site.py` turns all of them into the single `index.html`
you read on your phone.

---

## Say it in an interview

You won't be asked to recite definitions — but you *will* be judged on whether you use
these words precisely. Three that separate people who understand from people who
repeat:

**"Context window" used correctly.**
> "The context window is a hard token limit per call, covering the prompt and the
> response together. In an agent it's the binding constraint, because history grows every
> turn and the window doesn't. So each turn you're making an explicit choice about what
> to include and what to compress away — that's the actual engineering."

**"Eval" used correctly.**
> "An eval is a repeatable measurement on a fixed set of cases with fixed metrics, so a
> change can be judged in numbers. Mine splits into a dev set I iterate on and a held-out
> set I only touch for reported results. Every change ships with before-and-after
> numbers."

**"RAG" used correctly — and honestly.**
> "RAG is retrieve-then-generate: embed your source material, find the chunks nearest the
> query, put them in the prompt. I didn't build a document chatbot — I applied the same
> mechanics to the agent's own episode history, so it can recall what it learned in
> earlier games. Same concerns: chunking strategy, retrieval quality, and whether
> retrieval actually helps, which I measured with an ablation."

**Follow-up: "What's the difference between fine-tuning and prompting?"**
> "Fine-tuning changes the model's weights by training on your data — expensive, needs
> hardware, and you own a new model afterwards. Prompting changes only what's in the
> context window at call time — free, instant, and reversible. I did zero training in
> this project by design; all the behaviour comes from the loop and the context, which is
> also what makes every result reproducible on a laptop."

---

**Next:** [Study 03 — What an LLM really is: tokens and the context window](03-what-an-llm-really-is.md)
