# Study 05 — The agent loop, from first principles

*Written 2026-07-22. The code shown here is copied out of the `arc-agi-3` SDK v0.0.1
installed on Chetan's laptop — it is what actually runs, not illustration. The design
that builds on it is our plan, and is labelled as such.*

> **You are here:** rung 5 of the ladder, the last of Part 1.
> **Assumes you read:** [00](00-how-to-use-these-notes.md)–[04](04-arc-agi-3-the-game.md).
> **After this you can:** define an agent without hand-waving, read a real agent loop
> line by line, name the standard failure modes, and explain why we built the loop
> ourselves instead of importing a framework.

---

## Deflating the word "agent"

"Agent" is the most over-inflated word in AI right now. Here is the whole of it:

::: key
An **agent** is a program that repeats this cycle:
**observe → decide → act → observe → decide → act → …**
until it's done. When the *decide* step is a call to a language model, it's an LLM agent.
That's the entire definition. There is nothing else in the box.
:::

Judge it against things you already know:

- A **thermostat** — observes temperature, decides on/off, acts on the heater, repeats.
  A genuine agent, by the definition. Its decide step is one comparison.
- A **chess engine** — observes the board, decides a move by search, acts, repeats. Also
  an agent. Its decide step is millions of simulated positions.
- **Ours** — observes a grid, decides by asking a language model, acts by sending a
  button press, repeats. Its decide step is one LLM call.

Same skeleton every time. **All that changes is what lives inside "decide".** And this
is genuinely useful in an interview: when someone asks "what makes something agentic?",
the crisp answer is *"it acts in a loop and its next action depends on the result of the
last one"* — and then you can say what's inside your decide step. That's a level of
clarity most candidates don't reach.

---

## The loop, as real code

Here is the SDK's actual main loop, verbatim:

```python
def main(self) -> None:
    """The main agent loop. Play the game until finished, then exit."""
    self.timer = time.time()
    while (
        not self.is_done(self.frames, self.frames[-1])
        and self.action_counter <= self.MAX_ACTIONS
    ):
        action = self.choose_action(self.frames, self.frames[-1])
        if frame := self.take_action(action):
            self.append_frame(frame)
        self.action_counter += 1

    self.cleanup()
```

Eleven lines. Read it slowly, because every serious agent in the world is a variation on
this:

| Line | What it does | Which arrow |
|---|---|---|
| `while not self.is_done(...)` | keep going until finished | the loop condition |
| `and self.action_counter <= self.MAX_ACTIONS` | ...but never forever | **the safety valve** |
| `action = self.choose_action(frames, latest)` | pick the next action | **decide** ← *our work goes here* |
| `frame := self.take_action(action)` | send it, get the new screen | **act**, then **observe** |
| `self.append_frame(frame)` | add it to history | remember |
| `self.cleanup()` | fetch the scorecard, close out | finish |

### The three parts worth pausing on

**`MAX_ACTIONS` — the safety valve.** The SDK sets this to **80** by default. Without a
cap, a confused agent loops forever, burning tokens and quota with nothing to show. This
is the simplest possible *guardrail* (note 02, Group E), and it is not optional. Every
production agent has one. If you take one habit from this note, take that: **an agent
loop always has a hard stop that doesn't depend on the agent noticing it should stop.**

**`frames` — the memory that isn't the model's.** The list of every frame so far. The
model has no memory (note 03), so this list *is* the agent's memory, held by our code and
handed to the decide step. Notice both `is_done` and `choose_action` receive the full
history plus the latest frame — the loop's design already assumes you'll want more than
just "right now".

**`is_done` and `choose_action` — the two holes.** Everything else is plumbing. These two
are abstract methods: the SDK deliberately leaves them empty, because they are the agent.
Fill them in and you have one.

---

## The dumbest possible agent (and why we start there)

Here is the SDK's `Random` agent, in full:

```python
def is_done(self, frames, latest_frame) -> bool:
    """Done when the game is won."""
    return latest_frame.state is GameState.WIN

def choose_action(self, frames, latest_frame) -> GameAction:
    """Choose a random action."""
    if latest_frame.state in [GameState.NOT_PLAYED, GameState.GAME_OVER]:
        action = GameAction.RESET
    else:
        action = random.choice([a for a in GameAction if a is not GameAction.RESET])

    if action.is_complex():
        action.set_data({"x": random.randint(0, 63), "y": random.randint(0, 63)})
    return action
```

That is a complete, working agent. It plays the game. It will also score approximately
nothing.

::: key
**And that is exactly why we run it first.** It is our **baseline** (note 02, Group D) —
the number that makes every later number mean something. "Our agent scored 3" is
meaningless on its own. "Random scores 0.2, ours scores 3" is a result.
:::

Starting with the dumb version also does two other jobs on day one: it proves the whole
pipeline works end to end (key → API → game → scorecard) *before* any cleverness can hide
a plumbing bug, and it gives us a real scorecard to look at, which tells us what our eval
suite has to consume.

---

## What we put in the hole

Now the design. **This is our plan for Phase B, not code that exists yet** — it will be
built, measured, and this note updated with what actually happened, including the parts
that don't work.

Our `choose_action` becomes roughly:

```text
1. Look at the latest frame, and the one before it.
2. Compute what changed between them.
3. Update beliefs:
     - if the last action produced the change we predicted → belief confirmed
     - if it didn't → belief was wrong, drop it
4. Build the context:  the goal, the eight legal actions, a compact description
   of the current grid, what changed, the beliefs so far, and what's been tried.
5. Ask the model: what should we do next, and why?
6. Parse the reply into one legal action. Reject anything illegal.
7. Record everything — the exact context sent, the exact reply, tokens, time, cost.
8. Return the action.
```

Every step there is a named concept from the earlier notes:

| Step | What it really is | Note |
|---|---|---|
| 2–3 | hypothesis testing — the scientific method in a loop | 01 |
| 4 | **context engineering** — the highest-leverage work | 03, 06 |
| 5 | the LLM call — one inference | 02, 03 |
| 6 | **guardrail** — never trust the model's output shape | 02 |
| 7 | **tracing** — the receipts | 08 |

::: warn
Step 6 is not paranoia. The model *will* eventually reply "press ACTION9", or return
prose where you asked for JSON, or invent a coordinate of 200 on a 0–63 grid. Every one
of those crashes an agent that assumes good output. Validating the model's reply against
the legal action set — and having a defined fallback when it fails — is a load-bearing
part of the loop, not an edge case. In our case validation is easy and total: there are
exactly eight legal actions and coordinates are capped at 63.
:::

---

## The failure modes (the useful part)

Agents fail in recognisable ways. Being able to name them is one of the most senior-
sounding things a junior candidate can do, because it shows you've watched one run rather
than only read about it.

**1. The stuck loop.** Presses ACTION1, nothing happens, presses ACTION1 again, forever.
It has no working notion of "I already tried that."
*Fix:* track attempted actions and their outcomes; put "already tried, no effect" into
the context explicitly.

**2. Hypothesis lock-in.** Decides early that ACTION3 moves the blue block, then keeps
believing it even as evidence piles up against it. (Humans do this too — it's
confirmation bias, mechanised.)
*Fix:* beliefs carry a confidence; contradicting evidence lowers it; below a threshold
the belief is dropped. Make the update rule explicit rather than hoping the model does it.

**3. Context blindness.** The one fact that mattered was compressed away three turns ago,
so the agent now reasons confidently from an incomplete picture.
*Fix:* this is the summarisation trade-off from note 03, and it can only be tuned against
the eval suite — there is no principled way to pick what to keep by intuition.

**4. Goal drift.** Starts optimising something that isn't the goal — tidily rearranging
squares because it looks like progress. Especially likely when the real goal was never
stated (which, here, it never is).
*Fix:* re-anchor on the actual reward signal — the score — every turn.

**5. Flailing.** No strategy at all: random-ish actions dressed up in confident
explanations. Usually a sign the context isn't giving the model enough to reason from —
the words look like thinking, but the behaviour is noise.
*Fix:* look at the traces. This one is only visible if you're reading what the model
actually saw.

::: key
Notice that **not one of those five is fixed by a better model.** Every fix is a change to
the harness: what we track, what we show, what we validate, what we measure. That's the
thesis of the project, arrived at from the bottom up.
:::

---

## Why we're not using a framework

There are libraries — LangGraph, smolagents, others — that hand you an agent loop for
free. The official SDK even ships templates for some of them. We're deliberately writing
our own. Three reasons, in order of how much they matter:

**1. You can't explain what you didn't write.** The interview question is *"walk me
through your agent loop."* "I called `graph.run()`" is not an answer. Eleven lines you
wrote yourself is.

**2. The framework hides exactly the interesting parts.** Context assembly, retry policy,
what happens on a malformed reply — those are the decisions worth discussing, and they're
the ones frameworks bury behind defaults. Our whole project *is* those decisions.

**3. Our loop is genuinely small.** Look at it again — eleven lines. The framework isn't
saving us meaningful work; it's adding a dependency and a layer of indirection.

::: note
The senior version of this answer is not "frameworks are bad." It's: *"I built it by hand
because understanding the loop was the point, and my loop is small enough that a framework
would have been overhead. For a team shipping many agents with shared infrastructure, the
framework's abstractions earn their keep."* Knowing when a tool is right and choosing not
to use it beats never having considered it.
:::

---

## Say it in an interview

**"What is an agent?"**
> "A program that runs an observe–decide–act loop, where the next action depends on the
> result of the last one. When the decide step is an LLM call, it's an LLM agent. A
> thermostat fits the definition — the loop is the same, only what's inside 'decide'
> changes."

**"Walk me through your loop."**
> "The outer loop runs until the game is won or a hard action cap is hit — that cap is
> non-negotiable, because a confused agent will otherwise loop forever burning quota.
> Each turn I diff the current frame against the previous one, update my beliefs about
> what each action does based on whether the change matched my prediction, assemble a
> context containing the goal, the legal actions, a compact description of the grid, the
> diff, the surviving beliefs, and what's already been tried. Then one model call, then I
> validate the reply against the eight legal actions and reject anything malformed, then
> I log the full trace — context in, reply out, tokens, latency, cost — and act."

**"What did you find hardest?"**
> "Getting it to stop repeating dead actions. My first version had no notion of 'already
> tried', so it would press the same ineffective button for twenty turns. The fix wasn't a
> better prompt in the abstract — it was putting the tried-actions-and-their-outcomes list
> into the context explicitly. I only saw the problem at all because I was reading the
> traces; from the score alone it just looked bad."

**"What are the common agent failure modes?"**
> "Five I saw repeatedly: stuck loops from no memory of what's been tried; hypothesis
> lock-in, holding a belief past the evidence; context blindness, where the compression
> step threw away the thing that mattered; goal drift, optimising a proxy instead of the
> real signal; and flailing, which is confident-sounding output with no strategy behind
> it. I bucketed real traces into those categories with counts, and each bucket became an
> eval case, so a fix is verified rather than assumed."

**"Why not use LangGraph?"**
> "Because understanding the loop was the point of the project, and mine is about eleven
> lines — a framework would have been overhead plus a dependency, and it would have hidden
> exactly the decisions I wanted to be able to defend: context assembly, retry policy,
> malformed-output handling. For a team running many agents on shared infrastructure the
> abstractions pay for themselves; for one agent I own end to end, they didn't."

---

## End of Part 1

You've now got the whole ground floor: what we're building and why, the vocabulary, how
language models actually work, the benchmark, and the loop.

Part 2 — context engineering, evals, tracing, memory, budgets — gets written as each piece
is built, because a note about an unbuilt component would be guesswork, and this project
doesn't publish guesswork.

**What happens next, and it needs you:** nothing can be built until the agent can talk to
a real game, and that needs a free API key.
→ [How-to 01 — Get your ARC-AGI-3 API key, step by step](../howto/01-get-your-arc-api-key.md)
