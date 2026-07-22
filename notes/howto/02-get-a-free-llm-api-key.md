# How-to 02 — Get a free LLM API key (step by step)

*Written 2026-07-22. Every claim below was checked against Google's own documentation on
that day (links at the bottom) or tested on your laptop in that session. Where Google no
longer publishes a number, this note says so and tells you where to read it yourself
instead of guessing one for you.*

> **Time needed:** about 6 minutes.
> **You need:** a web browser and a Google account.
> **Cost:** free. No card, no trial, no payment step.

---

## Why you're doing this

The agent can now *play* — it opens a game, sends actions, records everything, closes the
scorecard. What it can't do is **think**. The "decide" step is still a coin flip, and a
coin flip completed **0 of 7 levels** of `ls20` even when we gave it 400 actions, which is
18× the 22 actions the reference solution needs for level 1 (measured this session,
`artifacts/comparison.json`).

To put a model in that slot we need a key from a company that will answer our requests.
This project spends nothing, ever, so it has to be a **free tier** — a level of service a
vendor gives away, capped at some number of requests.

Google's AI Studio is the first candidate because its Flash models are free of charge with
no card. It is **a candidate, not a decision**: which model we actually use gets settled
later by measurement, not by whoever we signed up with first.

::: warn
**Two safety rules, both different from last time.**

1. **An API key is a password.** Never paste it into chat (including to me), email, a
   screenshot, or any file that goes to GitHub. It goes in one place: `.env`, which
   `.gitignore` already blocks.
2. **On the free tier, Google says your prompts may be used to improve their products.**
   Their pricing page states this outright: free tier = "used to improve our products:
   Yes", paid tier = "No". For us that means Google may see pictures of ARC puzzle grids,
   which is harmless. But it means you must **never** send anything private, personal, or
   work-confidential through a free-tier key. That is a real rule, not a formality.
:::

---

## Step 1 — Open Google AI Studio's key page

1. Open your browser.
2. Go to: **https://aistudio.google.com/apikey**
3. Sign in with your Google account if it asks.

You should land on a page titled **API keys**.

**If you land on the AI Studio home page instead:** look for **Dashboard** in the left
menu, then **API keys**. Same place, one extra click.

---

## Step 2 — Accept the terms (a project is made for you)

The first time, Google shows its terms of service.

1. Read the summary, tick the box, and continue.
2. You may see a mention of a **Google Cloud project**. Every Gemini key belongs to one.
   **You do not have to create it** — new users get a default project automatically. If a
   dropdown appears asking you to pick a project, pick whatever is already listed.

::: note
**What is a "project"?** Just Google's folder for grouping usage and limits. It exists so
Google can count your requests. It costs nothing and needs no setup from you.
:::

---

## Step 3 — Create the key and copy it

1. Click **Create API key**.
2. If it asks which project, accept the default.
3. The key appears — a long string starting with `AIza`.
4. **Click the copy button** next to it. The key is now on your clipboard.

Leave the browser tab open; you'll come back to it in Step 6.

::: warn
**This is the only time the full key is shown.** After you leave the page it's masked. If
you lose it, don't panic — delete that key and create another. Old key dead, new key
works, nothing else breaks.
:::

---

## Step 4 — Add the key to your project file — **append, don't overwrite**

Your `.env` file **already contains your ARC key**. If you use the `Set-Content` command
from How-to 01, it will **replace** the file and your ARC key will be gone, and the game
runs will start failing with 401 for a reason that looks nothing like this step.

So we use `Add-Content`, which adds a line to the end instead.

**4a. Open PowerShell in the project folder.**

1. Press the **Windows key**, type `powershell`, press **Enter**.
2. Paste this and press **Enter**:

```powershell
cd "C:\Users\cheta\OneDrive\project-agent"
```

The prompt should now end with `project-agent>`.

**4b. Append the key.**

Copy the line below and **replace `PASTE_YOUR_KEY_HERE` with the key you copied** — keep
the quotes:

```powershell
Add-Content -Path .env -Value 'GEMINI_API_KEY=PASTE_YOUR_KEY_HERE' -Encoding utf8
```

Press **Enter**. Nothing visible happens. That is correct.

::: note
**Why `Add-Content` and not `Set-Content`?** `Set-Content` replaces the whole file;
`Add-Content` appends one line. Tested on this laptop on 2026-07-22: appending this way
does **not** insert the invisible byte-order mark that broke the ARC key twice — that mark
is only written when the file is first created.
:::

**4c. Check it worked.**

```powershell
Get-Content .env
```

You should now see **two** lines:

```
ARC_API_KEY=...your arc key...
GEMINI_API_KEY=AIza...your new key...
```

::: warn
**If you only see `GEMINI_API_KEY`** — you overwrote the file. Not a disaster: go back to
How-to 01 Step 3, copy your ARC key again, and add it back with
`Add-Content -Path .env -Value 'ARC_API_KEY=...' -Encoding utf8`.

**If you see `PASTE_YOUR_KEY_HERE`** — you pasted the command without swapping in the real
key. Open `.env` in Notepad (`notepad .env`), fix that line, save.
:::

---

## Step 5 — Prove the key works

Still in the same window:

```powershell
py scripts/check_llm_key.py
```

**What you should see** (roughly — the numbers will differ):

```text
key found      : AIza…7Xk2 (39 chars)
models visible : 47 (12 with 'flash' in the name)
round trip     : 812 ms, model said 'ready'

encoding                       chars  tiktoken   gemini
-------------------------------------------------------
raw grid, hex packed           4,159      1471     ....
objects                        1,083       468     ....
```

The last two lines are the point of the whole exercise: they say what one real screen of
`ls20` costs in **Gemini's own tokens**. Until now every token number in this project came
from an OpenAI counter, which was only ever good for comparing our encodings with each
other — not for predicting a real bill or a real context limit.

::: note
**The key never appears on screen.** The script masks it — first four characters, last
four, and the length. That's enough to tell two keys apart and useless to a thief.
:::

### If it doesn't work

| What you see | What it means | What to do |
|---|---|---|
| `no GEMINI_API_KEY or GOOGLE_API_KEY found` | The script can't see the key | You're in the wrong folder, or Step 4 didn't write the line. Run `Get-Content .env` and check |
| `google-genai is not installed` | Library missing | Run `py -m pip install -U google-genai` (it was already installed on 2026-07-22, so this is unlikely) |
| `FAILED to list models` with 400 or 403 | Key wrong, or not active yet | Re-copy the key; if it's fresh, wait a minute and retry |
| `429` or "quota" | You hit the free-tier limit | Wait — free limits reset. See Step 6 |
| Anything else | — | Copy the whole output to me (it contains no key) |

---

## Step 6 — Read your actual limits and send them to me

This is a real step, not paperwork. Google's public documentation **no longer prints the
free-tier request limits** — it tells you to look them up for your own project, because
they differ per account. So I cannot write the number here honestly, and I won't invent
one.

1. Go back to your browser.
2. Open: **https://aistudio.google.com/rate-limit**
3. Find the row for **Gemini 2.5 Flash** (or whichever Flash model is listed as free).
4. Note the three numbers: **RPM** (requests per minute), **TPM** (tokens per minute),
   **RPD** (requests per day).

Send me those three numbers. They decide real design choices: how many game steps we can
afford per minute, whether the agent can afford to think twice per move, and how many
evaluation runs fit in a day. Guessing them would mean designing the budget around a
number nobody checked.

---

## Step 7 — Tell me it's done

Come back to chat and send:

- the output of `py scripts/check_llm_key.py` (safe — it never prints the key), **and**
- the three limit numbers from Step 6.

::: warn
**Do not paste the key itself.** I don't need it and shouldn't have it — the code reads it
from `.env` on your machine at run time.
:::

---

## What just happened, in one line

You gave the agent a brain it doesn't pay for, wrote the secret into the one file Git
ignores, and — the part that matters — refused to accept a rate limit from memory when the
real one was two clicks away. **A number you looked up beats a number someone told you**,
and that habit is the whole difference between an engineer and someone repeating a blog
post.

---

**Sources checked 2026-07-22:**
- [ai.google.dev/gemini-api/docs/api-key](https://ai.google.dev/gemini-api/docs/api-key) —
  key creation at `aistudio.google.com/apikey`, the automatic default Cloud project, and
  the two variable names the SDK reads (`GEMINI_API_KEY`, `GOOGLE_API_KEY`; if both are
  set, `GOOGLE_API_KEY` wins)
- [ai.google.dev/gemini-api/docs/pricing](https://ai.google.dev/gemini-api/docs/pricing) —
  Flash and Flash-Lite models are "Free of charge" on the free tier, and free-tier data
  **is** used to improve Google's products
- [ai.google.dev/gemini-api/docs/rate-limits](https://ai.google.dev/gemini-api/docs/rate-limits)
  — confirms the limits are per-project and must be read from AI Studio, which is why
  Step 6 exists
- Tested on this laptop: `google-genai` 2.8.0 already installed; `Add-Content` verified not
  to insert a byte-order mark when appending; `scripts/check_llm_key.py` verified to fail
  cleanly with no key present
