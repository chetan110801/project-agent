# Interview-prep pack — rehearse the whole project out loud

*Written 2026-07-28. This is a **rehearsal cockpit**, not teaching. It complements the capstone
[study note 13](study/13-the-interview-story.md) (which is the full narrative) with the three
things you drill before an interview: **the pitch at three lengths**, a **topic-indexed Q&A
bank** you can practise from, and the **traps** to avoid plus the **artifacts** to show. Every
answer here is a tightened version of a line already in the course, so it is true and yours to
say. Read the answers **out loud** — silently reading and speaking are different skills, and only
one is being tested.*

> **The one-sentence spine of everything below:** *"I built the harness that tells the truth
> about an agent — it took four plausible fixes, told me exactly what each does and doesn't buy,
> and named precisely what's missing."* When a question drifts, come back to this.

---

## 1. The pitch, at three lengths

**15 seconds (the hallway version):**
> "I built an LLM agent for ARC-AGI-3 — games with no instructions, where the agent works out
> the rules by acting. But the real project is the *engineering harness* around it: a hand-built
> loop, an eval suite, traces, and cost budgets. The agent doesn't beat the game — and proving
> *why*, rigorously, is the point."

**60 seconds (the "tell me about a project" version):**
> "ARC-AGI-3 is a benchmark of small games with no stated goal — humans get 100%, the best
> frontier model was around 8% when I checked, so it isolates what models are weakest at. My
> agent gets a grid and eight buttons and has to figure out the rules by acting.
>
> The agent is one component; the project is the harness. I hand-wrote the loop so I could
> explain every line, measured different ways of showing the screen to the model, and — this is
> the discipline part — built an eval suite *before* any tuning, because I measured the score and
> it was a dead constant: zero at every budget. So I steer on denser signals and split the games
> into a dev set and a held-out set I never touch.
>
> Then I ran four experiments to get it off zero. Every one changed the agent's behaviour; none
> moved the score. Together they name the wall exactly: the agent can't turn feedback into a
> *better-chosen* next action. And it all ran on free tiers, so the cost engineering was real."

**3 minutes:** use the walk-through in [note 13's "Say it in an interview"](study/13-the-interview-story.md#say-it-in-an-interview)
— it is written as one spoken line, followed by the hard follow-ups. Practise from there.

---

## 2. The Q&A drill bank, by topic

Each answer is drill-length (say it in one breath or two). The **★** marks your strongest
answers — lead with these when you get the chance.

### Framing — "so it doesn't work, why should I care?"
- **"So the agent doesn't work — why should I be impressed?" ★**
  > "The project was never 'score high on ARC' — it was 'build the harness that tells the truth
  > about an agent.' On that it works: it took four plausible ideas and told me exactly what each
  > does and doesn't buy, and what's missing. That's the skill I'd bring — not a model that
  > happens to win, but the machinery that tells you whether it wins, why it did what it did, and
  > what it costs."
- **"What are you proudest of?" ★**
  > "That the negative result is airtight. Anyone can report a win. I A/B'd four fixes on one
  > variable against a seeded baseline, showed each changed behaviour and none moved the goal, and
  > I can tell you *why* each failed. A negative result you can defend is harder than a positive
  > one you can't."

### LLM fundamentals & context engineering
- **"What do you mean by context engineering?"**
  > "Deciding, every turn, what text the model actually sees. The environment sends a 64×64 grid
  > of integers and the model can only read text, so I wrote several encodings — raw pixels, an
  > object description, a diff — and measured each instead of picking by taste. It's the highest-
  > leverage thing in the system: the model is fixed, the loop is eleven lines; the context is
  > what I control."
- **"Give me a concrete result." ★**
  > "Reading the 'legal actions' field the server sends every frame was worth 47% of the action
  > budget — the stock baseline spent 38 of 80 actions on buttons that didn't exist, and those
  > were exactly the 38 that changed nothing. And writing the grid with separators instead of
  > packed doubled the tokens for identical information."
- **"How are you counting tokens?"**
  > "Characters where I can, since they're exact and vendor-independent, and tokens with the
  > tokeniser *named next to every number*. My headline correction is that a token ratio between
  > two encodings is a fact about the tokeniser, not about your data — I re-measured against the
  > provider's own counter and the famous '5.6× cost' became 2× on the model I actually call."
- **"Did compression work?"**
  > "7× on a real frame, and it's lossy — but the number I'd report is the failure case: on a
  > checkerboard, 2,048 one-cell objects, the 'compressed' form was *larger* than raw — 21× under
  > OpenAI's tokeniser, 8.7× under the Gemini counter I actually bill against. So the encoder caps
  > its output and says it truncated. A compression scheme has to be measured on its adversarial
  > input, because it meets that input exactly when the state gets complicated."

### Agent design & failure modes
- **"How do you debug an agent?" ★**
  > "I trace every decision — one append-only JSONL line per turn, carrying not just what the
  > agent did but the model's own stated reason. That reasoning field let me tell 'the agent is
  > mashing a button' apart from 'the agent adopted a wrong theory of the goal and is pursuing it
  > competently' — it literally wrote 'extending the green bar to connect the elements' about a
  > marker that meant nothing. From the score that's just failure; from the trace it's a
  > diagnosis."
- **"You mentioned a failure taxonomy — what was in it?" ★**
  > "I sorted every action in every trace — about two thousand — into six priority buckets:
  > illegal, dead, revisit, perseveration, active-but-no-progress, and progress. For the current
  > agent it's 88% active-but-no-progress, 12% dead, zero everything else including zero progress.
  > That single number *is* the finding: the agent isn't stuck or flailing, it does purposeful,
  > non-repetitive work toward a goal it never identified."
- **"How do you know the taxonomy itself is right?"**
  > "I ran it against a failure I already understood before trusting it elsewhere — the run where
  > the agent pressed one button 41 times. Perseveration should dominate there, and it does, 60%.
  > That's a rule I made after an earlier metric I'd invented from a *story* about a failure read
  > zero percent on the recording of that exact failure."
- **"How does your agent handle memory?"**
  > "The model is stateless, so 'memory' is a discipline about what I re-insert into the prompt
  > each turn. I built two kinds: short-term — the agent's recent actions within a game — and
  > long-term — the previous *attempt's* result carried into the next attempt's prompt. So it has
  > both a within-game and an across-game memory."

### Evals & controlled experiments
- **"Tell me how you evaluate your agent." ★**
  > "A fixed set of games, split into a dev set I iterate on and a held-out set I don't touch, by
  > a *published seed* so the split can't be hand-picked. Every number is tagged steering, outcome,
  > or cost — I keep or revert on steering, and the score stays in the same table but I never steer
  > on it, so a change that games the metrics and wrecks the goal can't hide. One command runs an
  > arm; a second diffs two arms and prints what config actually changed before any result."
- **"Why not just use the score?"**
  > "Because I measured it and it's a constant — zero at 80 actions and zero at 400, which is
  > eighteen times what the game's own reference needs for level one. A metric that reads zero
  > before and after can't referee anything. So I steer on denser signals that move earlier, and
  > the score stays as the outcome, because the day it moves is the day I have a result."
- **"Tell me about a metric that didn't work." ★**
  > "I built one blind to the exact failure I built it for. The agent pressed one button 41 times;
  > I assumed it was oscillating between two screens, so I fingerprinted screens and measured
  > revisits. Ran it against the failing recording — zero percent, all 80 screens distinct,
  > because a two-cell marker slid one column per press. A metric invented from a story about a
  > failure is a guess until you run it against the failure — and I had the recording to run it
  > against, so I found out in an hour, not a week."
- **"How do you stop yourself cheating on the held-out set?"**
  > "I don't rely on discipline. The runner refuses to execute against held-out unless you pass an
  > explicit `--report` flag, and it stamps `heldout_touched` into the artifact when you do, so the
  > file records that the set was used."

### The wall & exploration (the core result)
- **"Tell me about a time you disproved your own idea." ★**
  > "I was sure the fix was a progress signal — a line saying 'your last ten actions added up to
  > nothing.' Before writing it I tested four versions against recordings I already had. All four
  > failed, and the one I believed failed *backwards*: the stuck agent scored better than random
  > at every window, because it had found a bar it could extend two cells a press — perfect
  > accumulating work on the wrong thing. That's when it clicked: progress is defined against a
  > goal, and if you don't know the goal, no statistic over the screen separates progress from
  > busywork."
- **"You ran four experiments — what did they add up to?" ★**
  > "History, a repetition guard, a falsifiable-theory prompt, and the server's own end-of-game
  > verdict fed into the next attempt. Every one changed the agent's behaviour; not one moved the
  > score. Together they locate the wall: a stateless prompt has no credit assignment and no
  > learned model of what its actions do, so it can't turn feedback — however truthful — into a
  > *better-chosen* next action."
- **"Isn't the repetition guard just hard-coding around a weak model?"**
  > "Yes, and I'd say so plainly — it's the harness compensating for the agent, not the agent
  > improving. But I'd rather have a *measured* guard than an unmeasured belief that a better
  > prompt fixes it. Same pattern as the illegal-action guard: the model asks, the harness
  > guarantees."
- **"How do you know an improvement isn't noise?" ★**
  > "I measured the noise instead of guessing it. Repeat runs cost 120 model calls each against a
  > 500-a-day free cap, so I couldn't buy them — but I found four already on disk. My last
  > experiment played each game twice, and its signal is a summary of the *previous* play, so the
  > first play of the treated arm ran the plain prompt. With that plus the control arm's two plays
  > and an earlier arm on the same settings, I had four runs of one setup on each of four games.
  > I split those 16 episodes into two four-game arms that share no episode — 20,736 ways to do it,
  > all of them worked out — and every one is an A/B where the change is nothing, so every
  > difference is noise. The size only 5% exceed is my band: 9.2 points for repetition, 8.3 for
  > dead actions, 0.8 for illegal actions. The lesson was that there's no single noise floor, and
  > my old 17-point figure was a *per-game* number I'd been using on four-game averages — two to
  > three times too loose. A streak going from 26 to 3 beats all 20,736, so that one was never in
  > doubt. More seeds is still the first thing I'd buy: more runs can only widen the band."
- **"Did measuring the noise change anything you'd already concluded?" ★**
  > "Two things, and I'd rather volunteer them. I'd written that my repetition guard cost 2.5 points
  > of dead actions as a deliberate trade — that metric's band is 8.3 points, so the cost was inside
  > noise and I'd told a tidy story I had no evidence for. And I'd called the progress-signal
  > experiment a null; four of its metrics are worse than *every one* of the 20,736 change-free
  > differences — on one game the agent demanded unavailable buttons ten times in thirty moves. So
  > it was a measurable degradation, not a null. The wins were unaffected."

### Memory & retrieval
- **"Do you use embeddings or RAG? Why not?" ★**
  > "No, deliberately. RAG earns its place when your memory is too big for the context and you need
  > only a slice. My agent's whole memory is a handful of attempts and eight action types — it all
  > fits in the prompt, so there's nothing to retrieve. And my bottleneck was never recall: the
  > agent never lost a fact it needed. Its problem is that nothing turns feedback into a better
  > action, and RAG fetches past text — it doesn't manufacture a goal. Knowing when *not* to reach
  > for RAG mattered more here than knowing how to build it."
- **"What actually is an embedding?"**
  > "A list of numbers that captures the meaning of text, arranged so similar meanings get similar
  > numbers. 'Reset my password' and 'I forgot my login' share no words but land close together —
  > that's what lets you search by meaning instead of exact words."

### Budgets & production ops
- **"You were on a free tier — how did you manage cost?" ★**
  > "The scarce budget wasn't money, it was requests — 500 a day, 15 a minute. Every call writes
  > one line to a usage log that outlives the process, and every run reads it back and refuses to
  > start if it won't fit in what's left of the day. That refusal exists because I once ran four
  > experiments in a day, each a fresh process that thought it had the full 500, and the fourth
  > died half-way — I was measuring the right number in the wrong scope."
- **"Did shrinking the prompt help?"**
  > "It depends which limit binds. The same screen was 4,100 tokens raw or 570 as objects, a 7×
  > cut. On an open model where tokens-per-minute bound, that made each game 7× faster. On the
  > model I actually used, requests-per-minute bound and tokens had slack — so the identical shrink
  > changed throughput by *zero*. The value of an optimisation is a property of the constraint that
  > binds, not of the optimisation."
- **"How did you choose the model?"**
  > "Badly at first — I picked the highest throughput on paper, 180 games a day against my eventual
  > model's 6. Then I sent it a real game prompt and it failed three times out of three with
  > timeouts, while answering a toy prompt fine. A rate limit is a promise about requests you're
  > *allowed* to make, not ones that get *answered* — only the real prompt at real size tells you
  > the difference."
- **"Where did the time go in a run?"**
  > "I measured it: a full run was about five minutes, the model's median reply half a second, and
  > 61% of the wall-clock was the agent *asleep* waiting on the rate limiter. On a free tier,
  > latency isn't how fast the model thinks — it's how often you're allowed to ask."

### Meta — learning & process
- **"What's the single most useful thing you learned?" ★**
  > "That my own measurements lied to me repeatedly, and one habit caught them every time. A metric
  > read zero on the exact failure it was built for; a token ratio I loved was about the wrong
  > model; a repetition metric called the *random* baseline the worst offender. Each was a confident
  > falsehood from a measuring instrument, and each was caught by refusing a number that contradicts
  > what the run plainly did — and keeping every recording so I could check in seconds."
- **"How is this different from documentation?"**
  > "Documentation says what the code does. This says *why the design is what it is* — the
  > decisions, the alternatives I rejected, the evidence — and it's all committed: a dated decision
  > log, run artifacts every number traces to, and a plain-language course I wrote alongside the
  > build. Open the repo, run one command, and you get my numbers."
- **"How did you learn this stack?"**
  > "I came from data science, so the LLM and agent stack was new. I built the project and a written
  > course alongside it — every component got a plain-language note, in an order where nothing is
  > used before it's defined. It forced me to notice when I was cargo-culting rather than
  > understanding."
- **"What would you do next?" ★**
  > "Everything so far steers the agent *within* one attempt, and the wall says that's not enough —
  > you can't turn 'that didn't work' into a better move without learning *across* attempts. So the
  > next direction is credit assignment or a learned action-model: memory of what actions actually
  > accomplished, used to *choose*, not just narrate. It's a new direction, so I'd scope it and
  > write the decision down before building — which is how every turn in this project was made."

---

## 3. Traps to avoid

- **Never say "it works" or "it beats random."** It doesn't, on the outcome. Say "the *harness*
  works; the agent is not better yet." Rounding a negative up to a positive is the one thing that
  breaks trust — and the honesty is your strongest card, so don't throw it away.
- **Don't quote a token number without naming the tokeniser.** That's the project's own headline
  correction; contradicting it in the room would be self-inflicted.
- **Don't over-claim the statistics.** Every arm is one run on four games. Say so — then say you
  measured the noise band anyway, per metric, from 16 replicate episodes you already had
  (`artifacts/noise-floor.json`). Volunteering the limitation *and* the measurement reads as
  strength. Don't call the band a p-value; it isn't one.
- **Don't call the guards "the agent improving."** They're the harness compensating — "the model
  asks, the harness guarantees." Naming that distinction is the point.
- **Don't get pulled into defending the score.** When someone presses "but it's zero," pivot to
  *what the zero locates* — the wall, named exactly. The zero is the evidence, not the failure.
- **If you don't know, say so and say how you'd find out.** The whole project is "measure it, don't
  guess" — live that in the room.

---

## 4. Artifacts to show (screen-share checklist)

If you can share a screen, this is the tour, in order:

1. **[`README.md`](../README.md)** — the honest headline in 30 seconds.
2. **The Explorer app** (`py explorer/app.py` → `localhost:8000`, offline, no keys) — the
   strongest thing to show. **Home** for the headline, then **Replay** → *⤷ Jump to where it got
   stuck*: the screen keeps changing while the score stays 0, which is the whole project in one
   picture. Then **Evals** and **Taxonomy** for the numbers. Keep the toggle on **Demo**. Start it
   *before* the call and leave it running; don't touch the **Live** tab in an interview — it spends
   real quota and depends on the network. Walkthrough: [how-to 03](howto/03-run-the-explorer-app.md).
3. **`index.html`** (build with `py build_site.py`) — the 14-note course as one page; open note 13.
4. **[`notes/DECISIONS.md`](DECISIONS.md)** — dated decisions with rejected alternatives. This is
   the "why," and it's what separates a project from a tutorial.
5. **A trace** in `runs/` — one JSONL line per decision, reasoning field included → "this is how I
   answer *why did it do that.*"
6. **[`artifacts/failure-taxonomy.json`](../artifacts/failure-taxonomy.json)** — the 88% / 0%
   table, the wall as a number.
7. **`py -m unittest discover -s tests`** — 163 tests pass in about a second, live.

---

*Full narrative: [note 13 — the interview story](study/13-the-interview-story.md). The whole
project's design record: [DECISIONS.md](DECISIONS.md).*
