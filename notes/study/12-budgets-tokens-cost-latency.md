# Study 12 — Budgets: tokens, cost, and time

*Written 2026-07-23. Every number here comes from a file in this repo you can regenerate:
`harness/budget.py` (the measured rate limits), `artifacts/llm-budget.json` (from
`scripts/budget_report.py`), and `artifacts/llm-ourloop-80.json` (from an
`scripts/run_agent.py` run). The one live number — how much of today's quota is left — was
re-measured this session with `harness.budget.budget_check` and is a moving target by
design, which is the whole point of this note.*

> **You are here:** rung 12 of the ladder. It sits in Part 2 (the engineering), but it does
> **not** stand on notes 10 (traces) or 11 (memory) — those are still to be written and this
> note does not need them. You can read it now, straight after note 09.
> **Assumes you read:** [03](03-what-an-llm-really-is.md) (tokens and the context window),
> [06](06-context-engineering.md) (encodings — the different ways we turn a game screen into
> text), [08](08-evals.md) (the eval suite — a fixed set of games we replay to judge a
> change), and [09](09-exploration-and-the-signal-that-cannot-exist.md) (where you met the
> quota wall as the thing that killed an experiment). One-line gists of each are carried
> below so you are never stranded.
> **After this you can:** name the three budgets an AI engineer actually spends; say what a
> rate limit is and explain which limit "binds"; tell the story of the quota wall and the
> one-line bug behind it; and — the part that wins an interview — explain why the *fastest
> model on paper* was the wrong model to pick.

---

## Where we are, in one breath

Our agent plays a puzzle game by calling a language model once per turn: it sends the
screen as text, the model answers with a button, we press it, repeat. Notes 06–09 were
about making that loop *smart* — what to show the model, how to know a change helped, why
it got stuck. This note is about making it *affordable*, because every one of those calls
costs something, and the something is not money.

::: key
A **budget** here is any limited resource you have to spend carefully. Most people hear
"budget" and think money. In LLM engineering there are **three** budgets, and on a free
tier the money one is the *least* interesting:

1. **Tokens** — how much text each call carries (note 03: a **token** is a chunk of text,
   roughly a short word or a few characters, and the model's **context window** is the
   maximum number of tokens it can read at once).
2. **Requests** — how *many* calls you are allowed to make, per minute and per day.
3. **Time** — how long the whole run takes on the clock.

An engineer who can only talk about one of these has a blind spot. This note walks all
three, in the order they bit us.
:::

---

## Part 1 — The rate limit, and the three numbers that make it up

You cannot call a free API as fast as you like. The provider caps you. That cap is called
a **rate limit** (*a ceiling on how often you may call*), and it is not one number — it is
three, and they are enforced at the same time:

::: key
- **RPM — requests per minute.** How many calls you may make in any 60 seconds.
- **TPM — tokens per minute.** How many tokens of *input* you may send in any 60 seconds.
- **RPD — requests per day.** How many calls total in a rolling day.
:::

These are not published numbers we can look up — Google stopped printing free-tier limits
and points each user at their own dashboard. So they were **read off Chetan's dashboard on
2026-07-22** and written into the code as data, with the date attached, because they go
stale (`harness/budget.py`). Here are the two that matter to us:

| model | RPM | TPM | RPD |
|---|---:|---:|---:|
| **gemini-3.5-flash-lite** (what we use) | 15 | 250,000 | 500 |
| **gemma-4-31b-it** (an open model) | 30 | 16,000 | 14,400 |

Read those two rows side by side, because they are opposites. Gemma lets you make **twice
as many requests per minute** and **twenty-eight times as many per day** — but only
**one-fifteenth the tokens per minute**. One model is generous with *requests* and stingy
with *tokens*; the other is the reverse. That trade is the whole story of the next two parts.

---

## Part 2 — "Which limit binds": the idea that makes budgets an engineering problem

Three limits apply at once, but at any moment **only one of them actually stops you**. That
one has a name.

::: key
The **binding constraint** (*binds* = is the one that actually stops you first) is whichever
limit you hit soonest. The other two have slack — room to spare — so improving them changes
nothing. Find the binding one before you optimise anything, or you will speed up a queue
that was never the hold-up.
:::

Which limit binds depends on **how big your prompt is** — and note 06 was entirely about
controlling that. Recall its result: the same game screen can be sent as a raw grid of
digits (**~4,130 tokens**) or as a compact list of objects (**~573 tokens**), a ~7× difference,
`artifacts/tokens-by-tokeniser.json`. Now watch what that difference does on each model.

`scripts/budget_report.py` computes this exactly (`artifacts/llm-budget.json`), assuming
80 calls per game:

| model + encoding | tokens/call | binding limit | minutes per 80-action game |
|---|---:|---|---:|
| gemma-4, **objects** (573 tok) | 573 | **TPM** | **2.9** |
| gemma-4, **raw grid** (4,130 tok) | 4,130 | **TPM** | **20.6** |
| flash-lite, **objects** (573 tok) | 573 | **RPM** | **5.3** |
| flash-lite, **raw grid** (4,130 tok) | 4,130 | **RPM** | **5.3** |

Look at the last column, top two rows against the bottom two.

::: key
On **Gemma, tokens bind** — so shrinking the prompt from 4,130 to 573 tokens makes each game
**7× faster** (20.6 → 2.9 minutes). On **Flash-Lite, requests bind** — so the *identical*
shrink changes the speed by **nothing** (5.3 → 5.3 minutes): you are capped at 15 requests a
minute no matter how small each request is.
:::

This is the sentence to say out loud in an interview:

::: example
**You cannot choose your model and your prompt size independently.** The value of a
prompt-shrinking optimisation is not a property of the optimisation — it depends on which
limit binds on the model you chose. The exact same context-engineering win is worth *7× the
throughput* on one model and *zero* on another. The optimisation and the model selection are
one decision, not two.
:::

(*Throughput* = how much work you get done per unit time. It is the flip side of the
per-game minutes: fewer minutes per game, more games per hour.)

---

## Part 3 — The trap: the fastest model on paper could not play the game

Read that Gemma row again. **180 games a day** (its 14,400 daily requests ÷ 80 calls a
game), against Flash-Lite's **6.25**. On the arithmetic, Gemma wins by nearly 29×. Phase B
of this project actually picked Gemma as the model for exactly that reason.

It was the wrong choice, and finding out why is the most important lesson in this note.

::: warn
**Measured 2026-07-22** (`artifacts/model-bakeoff.json`): both Gemma models answer a toy
"say ready" prompt in about 3 seconds — and answer a **real** 1,464-character game prompt
**0 times out of 3**. The server returns `504 DEADLINE_EXCEEDED` (*it took too long, giving
up*), then the connection times out. The 180-games-a-day throughput is real arithmetic on a
model that cannot serve a single real turn.
:::

::: key
**A rate limit is a promise about requests you are *allowed* to make — not about requests
that will be *answered*.** A dashboard can tell you the first thing. It cannot tell you the
second. Neither can a smoke test (*a quick check that the basic thing works*) with a toy
prompt — only the real prompt, at real size, can.
:::

So the model is `gemini-3.5-flash-lite`, at **6.25 games a day**, chosen because it is the
one free model that actually answers a real game prompt (`artifacts/model-bakeoff.json`).
And that scarcity is not a footnote — it reshaped the experiments themselves:

::: example
Six games a day is why the eval runs in note 09 play **30 actions per game, not 80.** The
80-action runs live in `runs/` from before the quota mattered; once the day's requests
became the binding budget, shorter episodes were the only way to fit four games and an A/B
comparison inside one day (`scripts/run_evals.py`). The budget did not just cost us speed —
it set the *length of the experiment*. Constraints like this are not excuses to apologise
for; they are part of the engineering story, and you say them plainly.
:::

---

## Part 4 — The quota wall: a per-day limit and a per-process counter

You met this in note 09 as *the wall that stopped an experiment half-way*. Here we look at
it as a budget-engineering problem, because the bug behind it is one every engineer meets
eventually and it is a clean one to be able to tell.

The daily limit is **500 requests (RPD)**. On 2026-07-22, four eval arms were run on one
day, 120 calls each. Four times 120 is 480; add the day's earlier runs and the day was
already over 500. The fourth arm died **19 actions into its second game**, its next turns
coming back `429 RESOURCE_EXHAUSTED` (*quota used up*), which the harness turns into a random
fallback that looks like play in the trace but is not.

Here is the part worth remembering, because the code had a rate-limiter whose entire job was
to prevent this, and it did not:

::: key
The limiter counted requests **correctly** the whole time — but its day-counter was
**per-process** (*per program run*). Each of the four arms was a fresh program that started
its count at zero and believed it had the full 500. The limiter was measuring the right
number in the **wrong scope**: it protected a single run, when the limit is across every run
of the day.
:::

The fix is unglamorous plumbing, and that is the point — this is what separates a harness
from a script:

1. **Every request appends one line to a file** that outlives the program
   (`artifacts/llm-usage.jsonl`, via `record_call` in `harness/budget.py`). Failed requests
   are logged too — a 429 is a request the server received and refused, and pretending
   refusals are free is exactly the assumption that produces the surprise.
2. **Every run reads that file before it starts** and refuses to begin an arm that will not
   fit in what is left of the day (the `budget_check` / "REFUSING TO START" gate in
   `scripts/run_evals.py`).

::: example
Why refuse up front instead of just stopping when the quota runs out? Because an arm that
dies half-way is not a cheap failure. It **spends the quota anyway** *and* leaves a results
table full of random fallbacks that read like real play in every downstream number. Better
to not start than to produce a run you then have to remember not to trust.
:::

One more detail, and it is a small lesson in humility about clocks:

::: key
The day-counter counts the **trailing 24 hours**, not "today" — because *we do not know when
this provider's daily window resets*, and guessing would be a number from nowhere. A rolling
24-hour window can only ever **over-**state what the server thinks we have used, never
under-state it, so the error lands on the safe side: it can make us wait when we needn't
have, but it can never walk us into the wall.
:::

This is not abstract today. Re-measured this session (2026-07-23, 08:59 UTC): **413 of 500
used, 87 left**, and all 413 were made in a burst yesterday afternoon. So tonight's
experiment cannot start until enough of that burst ages out of the trailing-24h window —
the gate computed that as roughly 15:19 UTC. The budget is not a story from last week; it is
the reason a run is waiting right now.

---

## Part 5 — Headroom: why we pace at 80% of the limit, not 100%

A natural instinct is to pace exactly at the stated limit — 15 requests a minute, so one
every 4 seconds. We tried it.

::: warn
**Measured 2026-07-22:** a limiter pacing at *exactly* 15 RPM still collected
`429 RESOURCE_EXHAUSTED` on **3 of 80 calls**. Our 60-second window and the server's do not
start at the same instant, our clock is not its clock, and requests already in flight still
count against the window — so "exactly at the limit", seen from the server's side, is
sometimes just over it.
:::

The fix is one constant: `HEADROOM = 0.8` in `harness/budget.py`. We pace at 80% of every
limit — 12 effective RPM instead of 15.

::: key
**Headroom** (*deliberate margin below a ceiling*) is cheaper than the failure it prevents.
At 15 RPM, 80% headroom costs about 3 extra seconds a minute of waiting. In exchange it
removes a failure that otherwise lands in the *middle of a game* and corrupts that turn.
Three boring seconds beats one lost turn. You leave margin on any limit you do not perfectly
control — and you never perfectly control someone else's server.
:::

---

## Part 6 — The third budget: time, and where it actually goes

Money costs nothing on a free tier, and we have now costed the request budget. The last
budget is the clock — the **latency** (*how long one call takes*) of the whole run — and it
holds a surprise that is worth measuring rather than guessing.

Here is one real 80-action run of our LLM agent, every number straight from
`artifacts/llm-ourloop-80.json`:

| | value |
|---|---:|
| total wall-clock time | **308.9 s** |
| of which, asleep waiting on the rate limiter | **189.0 s** (61%) |
| median time for one model reply | **0.57 s** |
| the same 80 actions, random button-pressing | **38.2 s** |

Read the second row against the third. The model itself answers in a little over half a
second. Yet the run took five minutes, and **61% of that was the agent sitting idle, waiting
for permission to make its next call.**

::: key
On a free tier, your run's wall-clock time is dominated not by how fast the *model* thinks,
but by how often you are *allowed to ask it*. The LLM agent took **8× longer** than random
play (309 s vs 38 s) — and almost none of that gap is the model being slow. It is the rate
limiter, doing its job.
:::

This is why the limiter's waiting is not hidden — it is measured and reported
(`seconds_waited_on_rate_limit`). A run that spends most of its clock asleep is telling you
something real: the loop is asking the model too often for the budget it has. That is a
number you can act on — call the model on fewer turns, or accept fewer games a day — instead
of a vague feeling that "the run is slow."

---

## Part 7 — Putting the three budgets in one picture

::: key
- **Tokens** decide how much each call *carries* — and, on a token-bound model, how fast you
  go. Note 06 was how we control them.
- **Requests** decide how *many* calls you get — per minute (your speed) and per day (whether
  the experiment fits at all). This is the budget that bit hardest, because it is the one
  that binds on our model.
- **Time** is mostly a *consequence* of the request budget on a free tier — you spend it
  asleep, waiting for the next request to be allowed.

And sitting above all three: **a limit is a promise about what you may attempt, never about
what will succeed.** The model that could do the most requests could not answer one real
prompt. Always cost against the model that actually works, not the one that looks best on the
dashboard.
:::

---

## Say it in an interview

**"You were on a free tier — how did you manage cost?"**
> "On a free tier the scarce budget isn't money, it's requests. My model allowed 500 a day
> and 15 a minute, so I treated those like a bank balance. Every call writes one line to a
> usage log that outlives the process, and every run reads it back and refuses to start if it
> won't fit in what's left of the day. That refusal exists because I once ran four experiments
> in a day, each a fresh process that thought it had the full 500, and the fourth died
> half-way through with quota-exceeded errors — the limiter was counting correctly but
> per-process, when the limit is per-day. I was measuring the right number in the wrong
> scope."

**Follow-up: "Why refuse up front instead of just stopping when you run out?"**
> "Because an arm that dies half-way isn't a free failure — it spends the quota *and* leaves a
> results table full of random fallbacks that read like real play. A corrupted run you have to
> remember not to trust is worse than a run that never started. So the check is a pre-flight
> gate, not a mid-flight catch."

**Follow-up: "You mentioned prompt size — did shrinking it help?"**
> "It depends entirely on which limit binds, and that's the bit I'd want to get across. The
> same screen was ~4,100 tokens as a raw grid or ~570 as an object list, a 7× cut. On an
> open model where tokens-per-minute was the binding limit, that made each game 7× faster. On
> the model I actually used, requests-per-minute bound and tokens had slack — so the identical
> 7× shrink changed my throughput by *zero*, because I was still capped at 15 requests a
> minute. The value of an optimisation isn't a property of the optimisation; it's a property
> of the constraint that binds. You have to find that first."

**Follow-up: "How did you choose the model, then?"**
> "Badly at first — I picked the one with the highest throughput on paper, an open model that
> allowed 180 games a day against my eventual model's 6. Then I actually sent it a real game
> prompt and it failed three times out of three with server timeouts, while answering a toy
> prompt fine. So the lesson I'd hand anyone: a rate limit is a promise about requests you're
> *allowed* to make, not requests that get *answered*, and a dashboard or a toy smoke-test
> can't tell the difference — only the real prompt at real size can. I cost everything against
> the model that actually works."

**Follow-up: "Where did the time actually go in a run?"**
> "I measured it, and it surprised me. A full LLM run took about five minutes; the model's
> median reply was half a second; and 61% of the wall-clock was the agent asleep, waiting on
> the rate limiter for permission to make its next call. So on a free tier, latency isn't
> about how fast the model thinks — it's about how often you're allowed to ask. That's why I
> report the seconds spent waiting as a first-class number: if a run is mostly asleep, my loop
> is asking too often for the budget it has, and that's an actionable fact, not a vibe."

---

**Next:** note 13 — the interview story: the whole project compressed into a three-minute
answer, with the hard follow-ups. It gets written once the current experiment arc closes,
because a capstone about an unfinished investigation would have to guess its own ending.
Notes 10 (traces) and 11 (memory and retrieval) are still owed too — traces waits for the
failure taxonomy to organise it around, and memory waits until the agent actually has one.
