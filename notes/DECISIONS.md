# Decision log

One entry per decision that shaped the project. Newest first.
Format: date · decision · why · what was rejected.

---

## 2026-07-23 (later) — Experiment 3, PRE-REGISTERED before the run: make the theory explicit and falsifiable

*This half of the entry was written and committed **before** the arm was run. The results
section below it was appended afterwards. That order is the point: the last two experiments
each produced a number that could be read as a win if you chose the reading afterwards, and
the cheapest defence against choosing is to write the reading down first.*

**The question.** The diagnosis left standing this morning is **premature commitment**: the
agent picks one theory of the goal and never tests another. Memory did not fix it
(experiment 1, reverted). A progress signal cannot exist (refuted offline). The repetition
guard stopped the *symptom* — 26 identical actions in a row became 3 — and the score stayed
0. So: does making the theory **explicit and falsifiable** change how the agent explores?

**The change (one variable).** `hypothesis: None -> True`, arm `dev-llm-y1` against
`dev-llm-r3`. Everything else identical — dev suite, seed 0, 30 actions, `repeat_limit 3`,
`gemini-3.5-flash-lite`, objects encoder. The agent is asked for three lines: a GOAL (its
theory of what the game wants), the ACTION, and a PREDICT of how much of the screen that
action will change (NONE / FEW / MANY). The harness carries the theory forward, **checks the
prediction against the frame that comes back**, and when the prediction fails says so in its
own voice and demands a different theory. The model never grades itself — experiment 1
established that a model given facts to interpret interprets them in its own favour.

**The FEW/MANY boundary is measured, not chosen** (`scripts/change_sizes.py` →
`artifacts/change-sizes.json`): across every committed recording these screens change
**bimodally** — about two cells, or dozens, with almost nothing in between. Every boundary
from 3 to 20 reclassifies under 1% of actions in every arm, so the number cannot be tuned to
produce a result. It is set at 5.

**What would count as the intervention working** (steering, decided in advance):
`top_action_share_excess` down and `distinct_targets` up — the same two metrics the
repetition guard moved — *with* `hypothesis_changes` well above zero, which is what says the
mechanism actually ran rather than the prompt being ignored.

**What would count as it backfiring.** A written theory carried forward may *entrench*
commitment instead of breaking it: excess up, distinct targets down, `hypothesis_changes`
near zero while predictions keep failing. This is a real possibility, not a formality —
carrying the agent's own words forward is exactly what experiment 1 did with its actions,
and that made things worse.

**What would count as no result at all.** `hypothesis_stated_rate` low (the model ignores
the format), or `predictions_checked` near zero. Either means the arm measured our prompt's
obedience, not the agent's play.

**The noise floor is known in advance and constrains what may be claimed.** A single seed;
this morning a metric moved 17 points in a game where the intervention never fired. So no
difference of that size in one game will be called a result, and any claim has to point at
the games where the mechanism actually fired.

**Cost expected:** roughly +5-8% input tokens for the extra block, and the same 120 calls.

---

## 2026-07-23 — The progress signal cannot exist. Four candidates, all refuted offline; a repetition guard shipped instead

**Decision:** `harness/progress.py` and `scripts/progress_signals.py` exist as a **recorded
negative result** — nothing in them is in the agent's prompt. The change that shipped is the
**repetition guard** in `harness/policies.py` (`LLMPolicy(repeat_limit=…)`), kept on the
numbers below. 109 tests, all offline.

### The idea that died, and how cheaply

Yesterday's entry ends: *"the next experiment is not more memory — it is a progress signal."*
Four candidates were written (`harness/progress.py`), and — obeying the rule Lie 1 produced —
all four were run over the committed recordings **before** any went near a model
(`scripts/progress_signals.py` → `artifacts/progress-signals.json`). All four failed. The one
I believed in failed **backwards**.

Churn ratio = net change ÷ total change over a look-back window; low is supposed to mean the
work undoes itself. Holding the game constant at `ls20`, mean over every recording we have:

| look-back window | 5 | 10 | 20 | 30 | 40 | 60 |
|---|---:|---:|---:|---:|---:|---:|
| random play | 0.359 | 0.233 | 0.158 | 0.131 | **0.116** | 0.114 |
| the stuck LLM run | 0.681 | 0.538 | 0.334 | 0.194 | **0.136** | 0.122 |

**At every window the stuck agent scores better than a coin flip**, and inside its own
41-action streak it reads 0.650 against 0.336 outside it. Novelty is worse still: the stuck
run reached a new screen on **100%** of actions against random's 80.6%.

**Why, from the recording, action by action.** The two-cell event during the streak is not a
marker sliding — it is a **bar being extended by two fresh cells per press**. Nothing is
undone, nothing is revisited, and net change equals total change. By every local measure the
stuck agent was doing **perfect accumulating work**. It was extending the wrong thing.

**So the signal is not hard to build, it is impossible.** Progress is defined against a goal;
with the goal unknown and the score frozen at 0, no statistic over the screen separates
progress from busywork — only activity from stillness. Both previous diagnoses are now
retired: *"it cannot see its own repetition"* (refuted by the h8 experiment) and *"it needs a
progress signal"* (refuted here). The fault is **premature commitment**: one hypothesis about
the goal, never tested against another.

### What shipped instead — the repetition guard

After `repeat_limit` identical actions in a row, that exact action is refused: named as
blocked in the prompt, removed from the offered options, and enforced in code if the model
returns it anyway. Two things make it engineering rather than a hunch:

- **The threshold is read off the baseline** (`repeat_cap_firing_rates` in the artifact). A
  random player exceeds three-in-a-row on **0-2%** of its moves; the LLM exceeds it on **30%,
  57% and 77%** of the three dev games where a guard can fire. The rule is therefore *you may
  repeat an action as often as chance would*, and it provably cannot punish normal play.
- **It bans the full label, coordinates included**, so clicking four squares is exploring and
  clicking one square four times is not — and it can never leave zero options, which is why
  `tn36-ef4dde99` (one legal action) is untouched.

### The experiment (`comparison-dev-llm-h0-vs-dev-llm-r3.json`, one variable, 4 games × 30)

| metric | h0 | r3 | |
|---|---:|---:|---|
| illegal-action rate | 0.83% | 0% | better |
| **longest repeat streak** | **26** | **3** | better |
| **favourite-action excess** | **+36.9%** | **+17.7%** | better |
| distinct actions | 2.5 | 3.25 | better |
| distinct targets | 10.75 | 12.25 | better |
| no-change rate | 9.2% | **11.7%** | worse |
| revisit rate | 7.5% | **10.0%** | worse |
| level1_ratio | 1.215 | 1.226 | worse |
| *outcome:* score / levels | 0 / 0 | 0 / 0 | — |
| *cost:* input tokens | 103,162 | 104,376 | +1.2% |
| **guard overrules needed** | — | **0 of 120** | — |

**Decision: kept**, with the trade stated. Justification for the three regressions, as
CLAUDE.md §5 requires: **both rate regressions come from one game.** `sb26` moved 0.300 →
0.433 dead and 0.267 → 0.400 revisit; `ls20` and `ar25` held or improved. That is the trade we
bought on purpose — stop an agent repeating its favourite button and some of the alternatives
it tries do nothing. Paying 2.5 points of dead actions to stop spending 26 consecutive turns
on one button is the intended direction, at +1.2% tokens.

**The headline is not the win.** Score 0 → 0, levels 0 → 0. The guard did exactly what it was
built to do and **the agent is no better at the game.** Reported that way everywhere.

### Three more things the measurement said

1. **The model obeyed the prompt every single time: `repeat_blocks` = 0 of 120.** The code
   never had to overrule it — it wrote *"Since ACTION1 is blocked, trying ACTION2"* and
   *"ACTION2 was blocked after 3 consecutive uses, so I must switch to ACTION1"* in its own
   reasoning. The enforcement path stays anyway: a prompt is a request, a guard is a
   guarantee, and one obedient run is not a property of the model. `aggregate()` reports this
   zero as `0` and not as `-`, deliberately — a measured zero is the finding.
2. **A free noise estimate, from the game where the change was inactive.** On `tn36` the guard
   fired **0 times in both arms** (measured: 27 distinct click targets in 30 actions, never
   three identical in a row), so its prompt was unchanged — and its unparseable replies still
   moved **9 → 14 of 30**. The whole aggregate `usable_reply_rate` regression (0.90 → 0.85) is
   that one game. **A metric that moves in a game where the intervention never fired is
   noise**, and this is the first quantified sense of how much of a single-seed A/B is noise.
3. **`level1_ratio` is saturated and is not a steering metric.** At a 30-action budget every
   episode in both arms spent all 30 actions in level 1 (h0: 29/30/30/30, r3: 30/30/30/30), so
   the ratio is ~30 ÷ reference — a number set by the action cap, not by play. It can only
   move by completing level 1, which makes it an outcome metric wearing a steering label. It
   stays in the table with this note against it rather than being quietly dropped.

**Also decided / recorded:**

- **`--repeat-limit` now defaults to 3** in `run_evals.py` and `run_agent.py`, because that is
  what "kept" means. Reproducing any arm from before today requires `--repeat-limit 0`; every
  artifact records its own config, so the instruction is in the file.
- **A provenance correction to yesterday's entry.** It quoted *"Extending the green bar…"* as
  something the model said during the **h8** run. Checked against the traces: that line appears
  only in the **h0** arm, and *"Continuing the sequence to progress the puzzle mechanics"* in
  h0 and the 80-action stuck run. Neither is from h8. The diagnosis survives; the attribution
  was wrong, and it made the history block look like the cause of a theory the model states
  with no history at all. Corrected in place, above.
- **Study note 09 is exploration**, and the ladder shifted: traces → 10, memory → 11,
  budgets → 12, interview story → 13.
- **A number in study note 08 was wrong and is fixed:** it said an arm is "320 model calls"
  and that "the token-per-minute limit binds before the request limit". Measured from
  `dev-llm-h0.json`: an arm is **120 calls**, running at **13.8 calls/min against a 15 RPM
  ceiling** while using **11.8K tokens/min against a 250K ceiling**. RPM binds, as
  `DECISIONS` already said; the note contradicted it.

**Rejected:** shipping any of the four progress signals (measured backwards or blind);
deleting `harness/progress.py` after the negative result (the evidence is the result, and the
tests pin the growing-bar case so nobody rebuilds it from the same story a third time);
banning by button rather than by full action label (would forbid exploring a click game);
firing the guard on single-option games (repetition there is forced, not chosen); calling the
`usable_reply_rate` drop a regression (it is one game in which the change never fired).

---

## 2026-07-22 (late) — Phase C: the eval suite, and three separate ways measurement lied

**Decision:** `harness/evals.py` + `scripts/run_evals.py` + `scripts/compare_evals.py` are
the eval apparatus. Every number is tagged **steering** / **outcome** / **cost**; a change
is kept or reverted on steering rows only, outcome rows carry no better/worse verdict at
all, and cost sits in the same table so a steering win bought by tripling the bill is
visible as a trade. 90 tests, all offline. Study note 08 written.

**The suite's first act was to reject the change it was built to test** (below), and to
catch three separate ways the measurement itself was lying. That is the return on
CLAUDE.md §5's "evals gate all tuning": every one of these would have been invisible from
inside a tuning loop.

**The split, and one confession in it.** 25 games exist; the suite is **4 dev / 6 held-out /
15 reserve**, made by shuffling the sorted id list with the published seed `20260722`.
`ls20` is **pinned** to dev, because every baseline number in this repo was measured on it —
putting it in the held-out set would let us report a game we had already studied. The
runner **refuses** `--suite heldout` without `--report` and stamps `heldout_touched` into
the artifact when used. Reserve is not spare capacity; it is the games the free tier cannot
afford (see below).

### Lie 1 — a metric built from a story about a failure was blind to that failure

Phase B's stuck LLM run (`ACTION3` 57 of 80 times, 41 consecutively) was diagnosed as
oscillation between two screens, so Phase C added a **screen fingerprint** and a
**revisit rate**. Run against the recording that motivated it: **0%. All 80 screens
distinct.**

The recording says why: during the 41-action streak, 37 presses moved a **two-cell marker
along rows 61–62 by exactly one column each** — 42, 43, 44 … 54, then a 138-cell event,
then restarting at column 16. Every screen genuinely was new. So `no_change_rate` *and*
`revisit_rate` both read healthy through the entire failure.

Kept anyway, with its limits in the docstring, because re-analysing all four committed
recordings showed it measures something real:

| metric | SDK random | our random | our random 400 | **our LLM** |
|---|---:|---:|---:|---:|
| illegal-action rate | 47.5% | 0% | 0% | 0% |
| no-change rate | 47.5% | 0% | 0.25% | 0% |
| **revisit rate** | **46%** | **0%** | 6% | **0%** |
| longest repeat streak | 2 | 4 | 6 | **41** |
| favourite-action share | 20% | 27% | 25% | **70%** |

Revisit rate separates the SDK baseline (46%, its illegal actions bounced it back) from our
loop (0%). It is just not a measure of *stuckness*. The two that are: streak and
favourite-action share. **A metric invented from a story is a guess until it is run against
the failure** — and the recording being on disk is why that cost an hour, not a week.

### Lie 2 — the metric that did catch it was not comparable across games

The random baseline on `tn36-ef4dde99` scored a **99% favourite-action share and a
61-action identical streak** — worse than the stuck LLM, from a coin flip. Measured cause:
**`tn36` offers exactly one legal action in all 81 frames.** Across the dev set:
`ar25` offers 7, `ls20` 4, `sb26` 3, `tn36` 1.

Fix: **`top_action_share_excess` = observed share − 1/n_options**, reported instead of the
raw share (the raw share is kept but carries no direction). `tn36` random reads **−1%**;
`ls20` LLM reads **+62%**. Also added **`distinct_targets`** (full action labels, coordinates
included), because on a click-only game `distinct_actions` is 1 however widely the agent
clicks. `StepRecord` now records `legal_options` so the denominator is in the trace.

### Lie 3 — the model chosen on published quota does not serve real requests

Phase B chose `gemma-4-31b-it` as the eval model on arithmetic alone: **14,400 requests/day
vs Flash-Lite's 500**, i.e. 180 games/day vs 6. Recorded as provisional, pending a bake-off.

The first arm on it **hung on move 1 of game 1 for 25 minutes at zero CPU.** Two faults:

1. **`google-genai`'s `generate_content` has no default timeout,** so an unanswered request
   stalls forever and looks exactly like a slow one. Fixed: `timeout_seconds=90` via
   `types.HttpOptions(timeout=ms)` — **milliseconds**, verified against the installed 2.8.0,
   not guessed. A timeout is now a failed `Completion`: one lost turn, not a lost run.
2. With the timeout in, the real fault surfaced. `scripts/model_bakeoff.py` sends every
   candidate the agent's **real** 1,464-character prompt (`artifacts/model-bakeoff.json`):

| model | answered | median | usable action | requests/day |
|---|---:|---:|---:|---:|
| `gemma-4-31b-it` | **0 of 3** — 504 DEADLINE_EXCEEDED | — | 0 | 14,400 |
| `gemma-4-26b-a4b-it` | **0 of 3** — read timeout | — | 0 | 14,400 |
| `gemini-3.5-flash-lite` | 3 of 3 | 828 ms | 3 | 500 |
| `gemini-3.1-flash-lite` | 3 of 3 | 761 ms | 3 | 500 |

Both Gemma models answer `"Reply with exactly the word: ready"` in ~3 s. **A rate limit is
a promise about requests you may make, not requests that will be served**, and a smoke test
with a toy prompt cannot tell the difference. This supersedes the Phase B entry's
"Phase C's eval suite therefore runs on Gemma-4 with the object encoding".

**Consequence, stated because it shapes every number that follows:** the eval model is
`gemini-3.5-flash-lite` and the suite lives inside **500 requests/day**. One arm = 4 games ×
**30 actions** = 120 calls; an A/B = 240. The 80-action episodes in `runs/` predate this.
Episode length is set by a free-tier cap, not by what the metric would prefer.

### The first experiment — REVERTED, and the reason is the finding

**Question:** the Phase B stuck loop was diagnosed as "the agent cannot see its own
repetition". Does putting its last 8 actions in the context fix it?

**Where we stood first** (4 dev games × 30 actions; *not* an experiment — four settings
differ — but the reference every other number is read against):

| metric | random | LLM |
|---|---:|---:|
| no-change rate | 20% | **9.2%** |
| revisit rate | 18.3% | **7.5%** |
| **favourite-action excess** | **+4.4%** | **+36.9%** |
| longest streak (games with a choice) | **3** | **26** |
| level-1 ratio | 1.23 | 1.22 |
| wall-clock per arm | 65 s | 522 s |

The LLM's actions land better than random — half the dead actions, a third the revisits —
while being **8× more repetitive than chance** and making **exactly as much level-1 progress
as random** for 8× the wall clock.

**The experiment** (one variable, `history: 0 -> 8`;
`artifacts/evals/comparison-dev-llm-h0-vs-dev-llm-h8.json`):

| metric | h0 | h8 | |
|---|---:|---:|---|
| illegal-action rate | 0.8% | 0% | better |
| no-change rate | 9.2% | **17.5%** | worse |
| revisit rate | 7.5% | **23.3%** | worse |
| favourite-action excess | +36.9% | **+46.9%** | worse |
| longest repeat streak | 26 | **30** (whole episode) | worse |
| distinct actions | 2.5 | **1.75** | worse |
| distinct targets | 10.75 | **4.75** | worse |
| level-1 ratio | 1.215 | 1.226 | worse |
| *outcome:* score | 0 | 0 | — |
| *cost:* input tokens | 103,162 | **117,824** | +14.2% |
| *cost:* usable replies | 90% | 97.5% | better |

**Decision: reverted.** `history` stays in the code defaulting to 0. Worse on 7 of 10
steering metrics for +14% tokens does not get kept on the strength of the hypothesis that
produced it. (The offline prediction of +14% token cost matched the live +14.2% — the one
thing that went exactly to plan.)

**Why it backfired, which is worth more than the change would have been.** After eight
identical presses the history block reads:

```
  -8: ACTION3 -> 2 cells changed
  ...  (eight identical lines)
```

I read that as *"you are stuck"*. The model read it as *"this action reliably works"*. The
agent had a theory that extending the bottom-row bar *is* the goal, and the history handed it
eight supporting observations per turn.

> **CORRECTED 2026-07-23.** This paragraph originally quoted *"Extending the green bar at the
> bottom right to connect the elements"* and *"Continuing the sequence to progress the puzzle
> mechanics"* as things the model said **during the h8 run**. Checked against the traces: the
> first appears only in `runs/ls20-…eval-dev-llm-h0.…trace.jsonl` — the **h0** arm — and the
> second in the h0 arm and the 80-action stuck run. Neither is from h8. The quotes are real
> and the diagnosis survives; the attribution was wrong, and it made the history block look
> like the *cause* of a theory the model states without any history at all. Provenance is a
> claim like any other (CLAUDE.md §3).

**Memory of your actions is not feedback about your progress.** We supplied the first and
expected the second, and with score frozen at zero there is nothing in the prompt that could
supply the second. **So the next experiment is not more memory — it is a progress signal**,
and that is a harder problem than a prompt tweak. Knowing which of the two we have is the
return on building the suite before doing the tuning.

**Also decided / recorded:**

- **Aggregate `longest_repeat_streak` excludes single-option games**, for the Lie 2 reason
  one level up: `tn36`'s forced streak is the full episode, so a plain max over games
  reported 30 for *every* arm including random. After the fix random reads **3** and the LLM
  **26** — an 8.7× separation that a broken aggregate had flattened to 1.0×.
- **`compare_evals.py` recomputes aggregates from the stored per-episode metrics** rather
  than trusting the `aggregate` block in the file. The per-episode numbers are data; the
  roll-up is a definition, and definitions get corrected — recomputing means both sides of
  an old comparison move together instead of silently comparing yesterday's definition
  against today's.
- **Recordings are gzipped on close, not while writing.** They compress **126×** (a
  400-action run: 5.8 MB → 46 KB; `runs/` overall 29 MB → 692 KB, 42×), which matters when
  every experiment writes one per game per arm. But measured: a gzip stream **cannot be read
  back until closed** (`EOFError: Compressed file ended before the end-of-stream marker`),
  and mid-run readability is exactly why the format is JSONL — a run that dies on action 57
  must leave 56 readable records. So: plain while playing, compressed at `RecordingEnv.close`,
  and the plain file is deleted only after the compressed one exists and is non-empty. All
  four committed reports were regenerated from the compressed files and reproduce
  identically.
- **Rates are pooled, never averaged over games.** A 90-action disaster and a clean
  10-action game average to 50% and pool to 90%. There is a test named after it.
- **`compare_evals.py` prints what changed in the config before printing any result**, and
  labels the table `NOT AN EXPERIMENT` when more than one variable moved.
- **The history window was sized by measurement, not taste:** 8 past actions costs **+14%**
  input tokens on a real frame (747 → 851, Gemini's own tokeniser); 16 costs +28%.
- **Near-miss worth recording:** a bulk `gzip runs/*.recording.jsonl` was run while a live
  arm was writing into that directory. Windows' file locking refused to touch the open file
  and the run survived. That was luck, not design — bulk file operations over a directory a
  live run is writing to are unsafe.

**Rejected:** using score as the steering metric (measured constant); raw
`top_action_share` as a cross-game metric (confounded by how many buttons a game offers);
keeping Gemma for its quota (quota it cannot serve is not quota); gzipping the live
recording (trades crash-survival for disk, and disk was never the scarce thing during a
run); a bigger dev suite (500 requests/day is the ceiling, and saying so beats pretending
4 games is statistically comfortable).

---

## 2026-07-22 (night) — Phase B part 2: an LLM plays a real game, and it is worse than a coin flip

**Decision:** `harness/llm.py` (provider behind a one-method interface + client-side rate
limiting) and `harness/policies.py::LLMPolicy` are the decide step. `scripts/run_agent.py
--policy llm` runs it. 57 tests, all offline — `ScriptedClient` fakes the model the same way
`mock_game.py` fakes the environment, so policy and parser tests cost nothing and need no key.

**The free tier, measured** (Chetan's dashboard, 2026-07-22, in `harness/budget.py`):

| model | RPM | TPM | RPD |
|---|---:|---:|---:|
| gemini-3.5-flash-lite / 3.1-flash-lite | 15 | 250K | **500** |
| gemini-2.5-flash-lite | 10 | 250K | 20 |
| gemini-2.5/3/3.5/3.6-flash | 5 | 250K | 20 |
| gemma-4-31b-it / 26b-a4b-it | 30 | **16K** | **14,400** |

**What that buys** (`scripts/budget_report.py` → `artifacts/llm-budget.json`, at one model
call per action and 80 actions per game):

- **gemma-4-31b + object encoding: 180 games/day, 2.9 min/game.**
- gemini-3.5-flash-lite: **6.25 games/day**, 5.3 min/game.
- every other Flash: **0.25 games/day** — one game every four days. Unusable for evals.
- On Gemma, **TPM binds**, so the encoding choice is worth **7×** in throughput (2.9 vs 20.6
  min/game). On Flash-Lite, **RPM binds**, so encoding changes throughput by **nothing**. The
  same compression decision is worth 7× on one model and 0× on the other — which is why the
  encoding and the model cannot be chosen separately.

**Phase C's eval suite therefore runs on Gemma-4 with the object encoding** (180 games/day
makes a suite possible at all), with Flash-Lite as a scarce, better-model arm. Not final —
it becomes final when the bake-off has quality numbers, not just throughput ones.

**The first LLM run, reported as it happened** (80 actions, `gemini-3.5-flash-lite`, objects;
`artifacts/comparison.json`):

| | SDK random | our loop, random | our loop, **LLM** |
|---|---|---|---|
| actions not available | 38 (47.5%) | 0 | **0** |
| actions that changed nothing | 38 (47.5%) | 0 | **0** |
| final score | 0 | 0 | **0** |
| most-repeated action | 20% | 27% | **70%** |
| longest identical streak | — | — | **41 actions** |

**The model is no better than random on score and markedly worse on exploration.** It chose
`ACTION3` for 57 of 80 actions and repeated one action 41 times in a row, narrating fresh
justifications each turn ("repeating it continues the progress"). Every reply parsed — 0
unparseable in 105 live calls — so this is not a formatting failure. It is the stuck-loop
failure mode from study note 05, arriving exactly where that note predicted, and the
`nothing changed` feedback did not prevent it because the screen *was* changing by 2 cells
per press while going nowhere.

That is the finding: **"the screen changed" is not the same signal as "you made progress",
and the current prompt only carries the first.** Phase C's first real experiment is a
context change that gives the model its own recent action history, so it can see that it has
pressed the same button forty times.

**Also decided / recorded:**

- **Client-side pacing at exactly the stated limit is not enough.** Measured: a limiter
  running at the dashboard's 15 RPM still collected `429 RESOURCE_EXHAUSTED` on **3 of 80**
  calls. Fixed with `HEADROOM = 0.8` plus a single 429-only retry; a 25-action re-run came
  back **0 errors in 25 calls**. Retrying only 429 is deliberate — retrying everything would
  hide real bugs.
- **Rate limits are enforced, not discovered.** A 429 mid-game costs a turn and puts a
  failure in the trace that isn't the agent's. The limiter also makes the cost visible: the
  80-action LLM run took **309 s wall, 189 s of it asleep** on the rate limit, against 38 s
  for the same game with a random policy.
- **Coordinates out of range are rejected, never clamped** (`parse_action`). Clamping would
  turn a wrong answer into a plausible one, which is precisely what an eval must be able to
  see.
- **The prompt states the legal actions and the loop still guards them.** A prompt is a
  request; a guard is a guarantee. Both.
- `StepRecord` now carries `reasoning`, so a trace answers *why* and not only *what*. A test
  written against a field that didn't exist is what surfaced the gap.
- Windows rejects `:` in filenames, so run names are sanitised — `llm:model:encoder` produced
  an `Errno 22` that named the path but not the reason.

**Rejected:** raising on client errors (an agent that dies on a 429 measures nothing);
letting the policy parse strictly (measures our prompt's obedience, not the model's play);
choosing the model by reputation rather than by the throughput table plus a quality bake-off.

---

## 2026-07-22 (evening) — CORRECTION: study note 06's headline number was a fact about the wrong tokeniser

**What happened:** Chetan's Gemini key arrived. `scripts/measure_tokens.py` re-measured the
exact strings note 06 was built on, using `count_tokens` on `gemini-3.5-flash-lite` — the
model we actually call — alongside the offline `tiktoken/o200k_base`. They disagree by up to
2.8×, and the note's headline claim did not survive
(`artifacts/tokens-by-tokeniser.json`):

| encoding (real `ls20` frame) | chars | tiktoken | Gemini | ×  tik | × gem |
|---|---:|---:|---:|---:|---:|
| raw grid, hex packed | 4,159 | 1,471 | 4,130 | 1.00 | 1.00 |
| raw grid, decimal spaced | 8,243 | 8,191 | 8,244 | **5.57** | **2.00** |
| objects (cap 40) | 1,085 | 468 | 573 | 0.32 | **0.14** |
| diff vs previous | 66 | 22 | 28 | 0.015 | 0.007 |

**Gemini charges these grids at ~1 token per character** (4,130 tokens for 4,159 chars). It
does not pack digit runs the way `o200k_base` does, so the hex trick buys only what it buys
in characters and the celebrated "5.6× for identical information" is **2.00× on the model we
use** — which is just the character ratio, 8,243 ÷ 4,159 = 1.98.

**Every conclusion held in direction; only magnitudes moved.** Spacing still costs double.
The object encoding is still a win — a *bigger* one, 7.2× rather than 3× — because there is
more fat to cut when the raw grid is billed by the character. The checkerboard still
inverts (8.7× instead of 20.9×), so the truncation cap still earns its place.

**Decision:** note 06 now carries **both tokeniser columns** in both tables, and states as
its central lesson that *a ratio between encodings is a property of a tokeniser, not of your
data*. The interview answers were rewritten around the correction rather than around the
retired number — it is the strongest story in the note.

**Why this is a win, not an embarrassment:** the rule from Phase A that every token number
travels with the name of the tokeniser that produced it is exactly what made this a
correction instead of a wrong claim defended in an interview. A number labelled "OpenAI's
counter, used only to compare encodings" was honest when written and is still honest now.

**Also decided / recorded:**

- **`models.list()` is not an availability check.** Measured: the API listed
  `gemini-2.5-flash` with `generateContent` among its supported actions, and calling it
  returned `404 … no longer available to new users`. `scripts/check_llm_key.py` now probes an
  ordered candidate list and reports the first model that actually answers.
- **First working model: `gemini-3.5-flash-lite`** (~964 ms round trip). Flash-Lite is the
  right default for one call per game action; the `-latest` aliases are the fallback because
  they survive retirements — at the cost of not being pinned, which matters for evals and
  not for smoke tests. **This is not the model decision**; that is still made by measurement.
- Measurement scripts pin the recording (last by filename) and the frame (the middle one)
  deliberately, so the figures the notes quote reproduce. "Whatever I recorded most
  recently" would not.

**Open, and blocking budget design:** Chetan's dashboard shows free-tier limits *per model*,
and the row he sent is for the retired `gemini-2.5-flash`: **5 RPM / 250K TPM / 20 RPD**. If
the limit for `gemini-3.5-flash-lite` is of that order, **20 requests per day cannot support
an 80-action game**, and the loop must batch decisions, cache, or use a smaller number of
model calls per episode. The real row is needed before Phase C's budget is designed.

---

## 2026-07-22 (afternoon) — OVERRIDE: how-to walkthroughs are step lists, not essays

**Decision:** Chetan's instruction in-session, verbatim: *"make those howto notes much
thinner ans sharper and crisp, just the steps"*. `notes/howto/` is now **numbered steps,
exact commands, expected output, and a troubleshooting table** — nothing else. Cut: the
"why you're doing this" essays, the closing reflections, the multi-paragraph warning boxes,
the long source lists. 01 went from 263 lines to 106, 02 from 252 to 116.

**This overrides the reading of CLAUDE.md §6B** that produced the long form. §6B still
binds on substance — exact clicks, exact commands, exact expected output, what can go
wrong, and how to report back are all still mandatory. What it no longer licenses is prose
around them.

**Kept deliberately, in one line each, because losing them costs real damage:** use
`Add-Content` and never `Set-Content` (it replaces `.env` and deletes the other key);
free-tier Gemini prompts may be used by Google for product improvement; never paste a key
into chat; and step 8 of how-to 02, where he reads his own rate limits, because Google
doesn't publish them and a number invented here would be a lie with a citation-shaped hole.

**Also:** `scripts/run_agent.py --list` added, so "which games exist?" is a flag rather
than an error message with the answer buried in it.

---

## 2026-07-22 (afternoon) — Phase B part 1: our loop plays real games; the guard recovers 47.5% of the budget and changes nothing about the score

**Decision:** `scripts/run_agent.py` is the project's runner, and `harness/arc_env.py` is no
longer a draft — three real games of `ls20` were played end to end through our own transport
and our own loop (80, 80 and 400 actions), scorecards opened and closed. The SDK's CLI and
`Agent` are now used for nothing.

**The controlled experiment, which was the point of the phase.** Same game, same random
policy, same 80-action budget; the single difference is that our loop filters candidate
actions against the `available_actions` list the server sends in every frame:

| | SDK baseline | our loop |
|---|---|---|
| actions not in `available_actions` | 38 of 80 (**47.5%**) | **0 of 80** |
| actions that changed nothing | 38 of 80 (47.5%) | 0 of 80 |
| final score | 0 | 0 |

Generated by `scripts/compare_runs.py` into `artifacts/comparison.json`, from the
recordings in `runs/`, all read by one analyser.

*Which recording is which* (there are two 80-action runs of ours and they look alike):
`…e37062d0…` is the SDK baseline from Phase A; `…0036eedd…` is our loop's **first** live
run, kept because it is the one that exposed the scorecard bug — it closed the card before
reading it and came back empty; `…18fef424…` is the same run repeated after the fix and is
the one the comparison uses; `…74fbdcbe…` is the 400-action calibration.

**Reported honestly:** the score did not move, and the 47.5% → 0% is **true by construction**
(the policy cannot emit an unavailable action) rather than an estimate from a sample. With
n = 1 per arm, "still zero" is the only claim the score supports.

**The finding that actually redirects the project.** Closing a scorecard returns a per-level
breakdown that the SDK's `Scorecard` model does not declare and therefore silently drops:
`ls20` has **7 levels** with reference solutions of `[22, 123, 73, 84, 96, 192, 186]` actions
(776 total). Level 1 needs 22. We re-ran with **400** actions — 18× that — and completed
**0 levels** (`artifacts/ourloop-random-400.json`). The random policy also hit `GAME_OVER`
three times and our loop reset and continued each time.

So: **the action budget was never the binding constraint, and score is a dead metric at this
stage** — 0 for the baseline, 0 for the improved version, at 80 and at 400 actions. A metric
that cannot move cannot referee the next change. Phase C's eval suite is therefore built on
denser signals that respond before the agent starts winning: illegal-action rate, no-change
rate, `GAME_OVER` count, and **actions spent inside level 1 measured against the 22-action
reference**. Score and levels-completed remain the reported outcome, never the steering
signal.

**Why:** Phase B's stated first job was one before/after number through our own loop. It
produced that, and the calibration run that followed cost ~3 minutes and invalidated the
metric the whole eval design was about to assume. Finding it now costs one afternoon;
finding it after a week of prompt tuning would have cost the week, since every experiment
would have read "0 → 0".

**Also decided / recorded:**

- **`close_scorecard` returns raw JSON, not the SDK's `Scorecard`.** Measured: the endpoint
  answers with `card_id, environments, score, tags, tags_scores, total_actions,
  total_environments, total_environments_completed, total_levels, total_levels_completed`.
  The SDK's model declares almost none of those, and because every field has a default,
  `model_validate` *succeeds* and returns an object with an empty `cards` and a computed
  `score` of 0 that is not the server's. Validating through a vendor schema that doesn't
  cover the vendor's own endpoint destroys exactly the numbers the run is judged on.
- **The per-game card must be fetched before closing.** After `close`, `GET
  /api/scorecard/{card_id}/{game_id}` returns 404 — the id is retired. Measured.
- **RESET is always legal**, even though real frames never list it in `available_actions`
  (81 of 81 frames advertised `[1, 2, 3, 4]`). Without this the loop flags its own fallback
  as an illegal action.
- **Recordings are written in the SDK's own `{"timestamp", "data"}` format** by a
  `RecordingEnv` wrapper, so one analyser reads our runs and the SDK baseline and the
  comparison cannot be an artefact of two different readers.
- **`analyze_run.py` now refuses to overwrite a report generated from a different
  recording.** It made the mistake first: analysing a throwaway mock run silently replaced
  the committed baseline report that three study notes quote from.
- **Rate limits verified from source, not memory:** the ARC-AGI-3 API allows 600 requests
  per minute and is free during the research preview, with no daily cap
  ([docs.arcprize.org/rate_limits](https://docs.arcprize.org/rate_limits), checked
  2026-07-22). Our runs use roughly 2 req/s, so quota is not a design constraint for game
  play — it was for the LLM, which is a separate budget.
- **Free LLM tier chosen as the first candidate: Google AI Studio (Gemini Flash).** Verified
  from Google's pricing page the same day: Flash and Flash-Lite models are free of charge on
  the free tier, and free-tier data **is** used to improve Google's products. Google no
  longer publishes the free-tier RPM/TPM/RPD in its docs — they are per-project and must be
  read from `aistudio.google.com/rate-limit`, so `notes/howto/02` asks Chetan for his own
  numbers rather than inventing one. This is a *candidate*; the model gets chosen by
  measurement.
- **Key reading is centralised** in `harness/env_file.py` so the Windows byte-order-mark trap
  is fixed once for every future adapter rather than re-discovered per vendor.
- Study note 07 is **baselines and controlled experiments** (written from these runs); evals
  shift to note 08 and are written when the suite exists. Tests: 42 passing, 0.2 s, no key.

**Rejected:** using the SDK's `Scorecard` model for the close response (drops the level data);
recording in a bespoke format (would have made the before/after incomparable); tuning
anything before the metric question was settled; taking Gemini's free-tier limits from a
search result rather than the account dashboard.

---

## 2026-07-22 (morning) — Phase A done: first live run; the harness is built against a mock so it never waits on quota

**Decision:** The agent harness is developed against an **offline mock environment**
(`harness/mock_game.py`) that returns the SDK's own `FrameData` objects, with the real API
used only for ground-truth runs. Our loop takes an `Environment` protocol rather than
subclassing the SDK's `Agent`, because the SDK's loop is welded to its HTTP transport —
every test of it would cost a network call and a slice of the free tier, which in practice
means the tests don't get written. Result: 35 tests, running in 0.4 s, no key required.

**Phase A is complete.** The `ls20` game was played end to end by the SDK's random
baseline; the 81-frame recording is committed in `runs/` and analysed by
`scripts/analyze_run.py` into `artifacts/run-report.json`. Score 0, state `NOT_FINISHED`,
80 actions — the expected baseline result.

**Findings from that run (all measured, all in the artifact):**

- **The baseline wasted 47.5% of its budget.** `available_actions` was `[1, 2, 3, 4]` in
  every frame; the SDK's random agent picks from all eight. 38 of 80 actions were buttons
  that don't exist, and those are exactly the 38 transitions that changed nothing. Our
  loop's illegal-action guard recovers that for one line of code and no model.
- **Three of our pre-data assumptions were wrong**, each silent, none caught by a test:
  cell values reach 12 (so packed *decimal* rendering is ambiguous — cells are now one hex
  character); the background of `ls20` is colour 4 covering 64% of the screen, not 0 (the
  object encoder was describing the floor as the biggest object — background is now
  inferred); and one frame carried **six** grids, an animation for a single action (so
  `frame[0]` would show a stale mid-animation picture — we take the last).
- **Encoding costs on a real frame:** hex-packed grid 1,471 tokens; the same grid as spaced
  decimals 8,191 (**5.6× for identical information**); objects 468; diff 22. On a
  hand-built checkerboard the object encoding *inverts* to 20.9× the raw grid, so it
  carries a truncation cap. Counts are `tiktoken/o200k_base` — for comparing encodings
  only, never as a budget for another vendor's model.
- **My synthetic pre-run measurement of the object encoding said 14×; the real frame says
  3×.** The code was fine; the invented test input was flattering. Recorded because it is
  the commonest way an honest number misleads.
- **Two Windows papercuts, both costing a session's start:** `Set-Content -Encoding utf8`
  writes a UTF-8 BOM, so `.env` produced a variable literally named `﻿ARC_API_KEY` and
  the API returned 401 (the same BOM bug hit `.gitignore` on 2026-07-21). And the SDK's CLI
  shuts down with `os.kill(os.getpid(), SIGINT)`, which on Windows kills the process before
  the scorecard is printed — exit code 2, no output, despite a fully successful run. Both
  are written into `notes/howto/01`.

**Why:** Phase A's stated goal was to prove the pipeline before adding cleverness. It did
that and more — the run cost nothing, scored nothing, and destroyed three wrong assumptions
that every test would have kept passing.

**Rejected:** subclassing the SDK's `Agent` and using its loop (untestable offline, and the
loop is the interview artifact — see study note 05); waiting for real frames before writing
any encoder (the mock made the loop and its guards testable immediately, and the guards
turned out to be what the run needed); using the SDK CLI as the runner (the Windows
shutdown bug plus no control over context is exactly what our own runner is for).

**Also decided:** study notes quote numbers only from `artifacts/`, and every token count
in this repo travels with the name of the tokeniser that produced it. Study note 06
(context engineering) is written; note 07 (evals) waits for the eval suite to exist.

---

## 2026-07-22 — Study notes become a structured course for a zero-knowledge reader; step-by-step walkthroughs are mandatory

**Decision:** Three new hard rules, written into `CLAUDE.md` (§6A, §6B) so every future
session and model obeys them:

1. **Study notes are a course, not a pile.** They live in `notes/study/`, are numbered,
   and are read in order. Every note declares *You are here* / *Assumes you read* /
   *After this you can*, defines every term at first use, **makes no forward references**,
   gives overview before detail, anchors abstract ideas in something concrete, and ends
   with **Say it in an interview**. Non-basic English gets a short inline gloss.
2. **Anything Chetan must do himself gets a numbered, click-by-click walkthrough** in
   `notes/howto/` — exact clicks, exact commands, exact expected output, what can go
   wrong, and how to report back. Never a one-line instruction.
3. **Rechecks are separate single-focus passes** (flow / jargon / closure / truth), not
   one combined skim.

Written this session: `notes/study/00`–`05` (how to use the notes; the project in plain
English; the vocabulary in dependency order; tokens & context windows; ARC-AGI-3 and its
exact interface; the agent loop) and `notes/howto/01-get-your-arc-api-key.md`.
Notes 06–11 (context engineering, evals, traces, memory, budgets, the interview story)
are listed in the ladder and get written **as each component is built** — a note about an
unbuilt component would be guesswork.

**Why:** Chetan stated plainly that he has **zero** technical knowledge of this stack and
cannot learn from notes that assume any. He also cannot act on instructions like "get an
API key" without a walkthrough. Both were previously implicit-at-best; interview fluency
is the project's whole purpose, so failing at them fails the project regardless of how
good the agent gets.

**Rejected:** writing all of notes 06–11 now (would violate the no-unverified-claims rule
— they'd describe components that don't exist); keeping the course inside `notes/`
alongside the project record (mixes teaching with history and breaks the reading order).

**Also decided (reader/site):** `build_site.py` now groups documents into *Learn from
zero* → *Do this — step by step* → *Project record* → *Project* → *Deferred: TRM*, which
is the reading order, and renders `::: key/example/warn/note` callout boxes. Reader-shell
fixes for iPhone: the menu and home buttons moved into one fixed flex row so they can
never overlap at any inset or font size; corner buttons stay faintly visible on touch
devices (which have no hover, so they were invisible forever after the load hint faded);
phone padding cut from 3.4rem/4.5rem to 3.05rem/1.6rem so text fills the screen
vertically; and the JS viewport-height override now only runs where CSS `dvh` is
unsupported — a stale `innerHeight` in an in-app browser (e.g. opening the file from the
OneDrive app) is the most likely cause of the dead band Chetan saw at the bottom.
**Confirmed working on his iPhone 2026-07-22:** text fills the screen top to bottom and
the menu and home buttons are separate and visible. This item is closed.

---

## 2026-07-21 (evening) — PIVOT: the project is an LLM-driven ARC-AGI-3 agent judged by its engineering harness; TRM deferred to project-asi

**Decision:** project-agent is re-centered on one build: an **LLM-driven agent for
ARC-AGI-3**, where the interview-facing deliverable is the **engineering harness**
around it — the agent loop built from first principles, context engineering, an eval
suite run on every change, tracing/observability, reliability guards, and free-tier
cost/latency engineering. Target: the public leaderboard (internet allowed); the Kaggle
prize track (no internet → no LLM APIs) is optional later, not the goal. The
TRM/Sudoku reproduction + ablation is **deferred to project-asi** — the Phase 0
verification and the pre-registered ablation plan are kept in this repo
(`trm-reproduction/`, marked deferred) so nothing is lost.

**Why:** Chetan's requirement, stated plainly: the portfolio must showcase *current*
AI-engineering / agentic-engineering practice (loops, evals, reliability, efficiency)
because that's what interviews probe, and he needs to learn it ("I don't know shit
about it"). The morning plan had a real gap the pivot fixes: prize-eligible ARC-AGI-3
agents can't call LLM APIs (no internet at eval), so building for the prize would have
taught loop fundamentals but not the LLM-engineering stack. Off-Kaggle, LLM-driven
agents are the expected pattern (the official SDK ships OpenAI/LangGraph integrations).
The substrate keeps the AGI-path spine that motivation depends on; the harness carries
the interview story. No GPU training anywhere — laptop + free API tiers only.

**Rejected:** (a) same harness on a business-shaped benchmark (τ-bench-style) — closer
to product-company day jobs but crowded territory and loses the AGI spine; (b) keeping
the TRM-first plan — the LLM/agentic stack would arrive too late or not at all;
(c) dropping TRM entirely — the ablation idea stays parked, it costs nothing to keep.

**Supersedes:** the morning entries below insofar as they made TRM Step 1. The rigor
constraint (reproducible claims, held-out evals, written records, timeless study notes)
carries over unchanged — it now applies to agent evals instead of training runs.

---

## 2026-07-21 — Step 1 reordered: Sudoku-first reproduction; ARC at reduced scale only

**Decision:** Phase 0 verification (see `notes/02-phase0-verification.md`) found the
paper's ARC-AGI-1 training run cost ~288 H100-hours — roughly two years of Kaggle's
free 30 GPU-h/week. Step 1 therefore becomes: (a) full-scale TRM reproduction on
**Sudoku-Extreme** (~18 datacenter-GPU-hours, feasible in 1–2 weeks of quota, target
≈87%), (b) the recursion-depth ablation (16→8→4→2, equal budget per depth) on
Sudoku-Extreme, (c) one **reduced-scale** ARC-AGI-1 run reported honestly as
reduced-scale. The ablation contribution is unchanged; only the task it runs on moved.

**Why:** Forced by arithmetic, not preference. The alternative — burning weeks of quota
to reach a fraction of one ARC run — produces nothing showable.

**Rejected:** Renting cloud GPUs (violates zero-budget constraint); skipping
reproduction and doing only the ablation (no calibration that our training pipeline is
correct); Maze-Hard as the cheap task (several weeks of quota vs Sudoku's 1–2).

**Also recorded:** TRM's official repo was archived 2026-04-01 (read-only) — we fork it
so the reproduction can't be orphaned. ARC-AGI-3 leaderboard moved (frontier ~7.8%,
a paper claims 78.4% on public eval); the "frontier under 1%" line is retired from the
pitch.

---

## 2026-07-21 — Where "agentic engineering" lives in this project

**Decision:** Interview-facing agentic topics (the agent loop, memory, exploration
policy, evaluation of agents) are covered by **Step 2 itself** — the ARC-AGI-3 agent is
an observe→decide→act loop with memory and hypothesis-testing, built from first
principles rather than a framework. A study note on "the agent loop, timelessly" is
added to the standing list. Framework-specific tooling (LangGraph et al.) stays out of
study notes per the timeless-concepts constraint; RAG/function-calling interview
questions are covered by ResearchPath (resume project #2), not this project.

---

## 2026-07-21 — The project is an AGI-direction research piece, not an app

**Decision:** Build (1) a reproduction of the Tiny Recursion Model on ARC-AGI-1 plus an
unpublished recursion-depth ablation, then (2) a purpose-built agent for ARC-AGI-3
targeting the 30 Sept 2026 open-source milestone. Timeline flexible; each step showable
on its own.

**Why:** Chetan's long-term goal is AGI/ASI work; the portfolio must be a step on that
path or motivation dies. project-asi's own forward plan (`LEARNING/THE_PLAN.md`,
2026-07-21) identified the efficiency frontier as the one part of AGI research open to a
zero-budget individual, with these exact two moves as Phases 2–3. The portfolio project
and the AGI path now share one spine.

**Rejected:** study-materials generator, job-application copilot, GitHub issue triage,
customer-support agent, SRE/log copilot — all "generic software" apps; Chetan is
explicitly not interested in learning replaceable app-stack practices.

**Constraint recorded:** study notes teach *timeless* concepts (generalization,
test-time compute, ablations, exploration, the research loop) — never tooling for its
own sake. Claude writes the code; Chetan owns the understanding.

---

## 2026-07-21 — (earlier) Reliability-as-thesis, reframed

**Decision:** The original thesis — "anyone can vibe-code an app; the trust system
around it is the differentiator" — survives, reframed for research: reproduction
targets, held-out tests, one-command reruns, written experiment records.

**Why:** It is the same discipline interviewers probe in applied-science loops
(how do you know your result is real?), and it is timeless scientific method rather
than a tooling stack.
