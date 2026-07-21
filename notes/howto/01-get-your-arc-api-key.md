# How-to 01 — Get your ARC-AGI-3 API key (step by step)

*Written 2026-07-22. The sign-up flow below was checked against the official ARC Prize
documentation ([docs.arcprize.org/api-keys](https://docs.arcprize.org/api-keys)) on
2026-07-22. The commands were written against the `arc-agi-3` SDK v0.0.1 installed on
your laptop, and the exact file it reads was confirmed by reading the SDK's source.*

> **Time needed:** about 5 minutes.
> **You need:** a web browser, and a Google **or** GitHub account.
> **Cost:** free. No card, no payment, no trial.

---

## Why you're doing this

Right now our code can't talk to a real game. The ARC Prize servers refuse anyone without
a key — they need to know who's asking so they can attach scores to an account.

Until this key exists, **nothing else in the project can move**: no game, no scorecard, no
numbers, and this project doesn't write notes about numbers it hasn't measured. This is
the one blocking task, and it's yours because it needs your identity, not the code's.

::: warn
**The one safety rule.** An API key is a password. Anyone who has it can use your quota
and act as you. So:
- Never paste it into a chat, an email, a screenshot, or a file that goes to GitHub.
- It goes in exactly one place: a file called `.env` in the project folder, which is
  already listed in `.gitignore` so Git will never upload it.
- If you ever think it leaked, delete the key on the website and make a new one. That's
  all it takes — old key dead, new key works.

**Including me:** don't paste the key into our chat. Step 6 tells you what to send
instead.
:::

---

## Step 1 — Open the ARC Prize platform

1. Open your web browser.
2. Go to: **https://arcprize.org/platform**

You should land on the ARC Prize platform page with a way to log in.

**If you see a page that isn't a login or dashboard:** try **https://three.arcprize.org**
instead — that's the ARC-AGI-3 host, and it links to the same account system. Either
route ends up in the same place.

---

## Step 2 — Log in with Google or GitHub

There is **no email-and-password sign-up.** You log in with an account you already have.

1. Click **Log in** (or **Sign in** / **Sign up** — the wording may vary; they all go to
   the same place).
2. Choose either:
   - **Google** — pick your Google account and approve, or
   - **GitHub** — approve access when GitHub asks.
3. You'll be returned to the ARC Prize platform, now logged in.

**Which should you pick?** Either is fine. Use GitHub if you'd rather keep this tied to
the same identity as your `chetan110801` repo; Google if that's simply fewer clicks.
Whichever you pick, **remember it** — you'll need the same one to log back in later.

::: warn
**If nothing happens when you click Google or GitHub:** it's almost always a blocked
pop-up. Look for a small icon at the right-hand end of your browser's address bar saying
a pop-up was blocked, click it, and choose to allow pop-ups for this site. Then click the
login button again.
:::

---

## Step 3 — Create the API key

1. Look at the **top-right corner** of the page. There will be your **user profile** —
   your name, your avatar picture, or a small circle icon.
2. **Click it.** A menu opens.
3. In that menu, find and click **API Keys**.
4. On the API Keys page, click the button to **create a new key**. (Labels vary a little —
   look for *Create*, *New key*, *Generate*, or a **+** button.)
5. If it asks you to name the key, type: `project-agent` — the name is only a label to
   help you recognise it later; it changes nothing.
6. **The key now appears on screen.** It will be a long string of letters and numbers.

::: warn
**Copy it now.** Many key systems show the full key exactly once and only a masked
version afterwards. Click the copy button next to it (or select the text and press
`Ctrl+C`) **before you navigate away**.

If you lose it, don't panic — you delete that key and create another. Nothing breaks.
:::

Paste it somewhere safe for the next 60 seconds — Notepad is fine. **Don't save that
Notepad file**; you'll paste the key into its proper home in Step 4 and then close
Notepad without saving.

---

## Step 4 — Put the key in your project

The key must live in a file called `.env` inside the project folder.

Windows File Explorer makes filenames that start with a dot awkward to create, so we'll
use PowerShell. This is copy-paste — you don't need to understand it.

**4a. Open PowerShell in the right folder.**

1. Press the **Windows key**, type `powershell`, and press **Enter**. A dark blue window
   opens.
2. Copy this line, paste it into that window (right-click pastes in PowerShell), and press
   **Enter**:

```powershell
cd "C:\Users\cheta\OneDrive\project-agent"
```

The prompt at the left of the window should now end with `project-agent>`. That means
you're in the right folder — this matters, because the tool looks for `.env` **in the
folder you're standing in**, and nowhere else.

**4b. Create the `.env` file with your key in it.**

Copy the line below, but **replace `PASTE_YOUR_KEY_HERE` with the actual key you
copied** — keep the quotes, delete the placeholder text between them:

```powershell
Set-Content -Path .env -Value 'ARC_API_KEY=PASTE_YOUR_KEY_HERE' -Encoding utf8
```

Press **Enter**. Nothing visible happens. That's correct — this command is silent when it
works.

**4c. Check it worked.**

Paste this and press **Enter**:

```powershell
Get-Content .env
```

You should see one line:

```
ARC_API_KEY=abc123...whatever-your-key-is
```

::: warn
**If you see `ARC_API_KEY=PASTE_YOUR_KEY_HERE`** — you pasted the command without
swapping in your real key. Just run the 4b command again with the key in place; it
overwrites the file.

**If you see an error about the path not existing** — the folder path in step 4a was
wrong. Check the spelling, and confirm the folder exists by running `ls` in PowerShell.

**If you see nothing at all** — the file wasn't created. Make sure you pressed Enter on
the 4b command and that no error text appeared.
:::

---

## Step 5 — Run a real game

This is the payoff. Still in the same PowerShell window, in the same folder, paste:

```powershell
arc-agi-3 --agent=random --game=ls20
```

Press **Enter**.

**What should happen:** lines start scrolling — the tool connects, starts the game, and
plays it with the random agent (the deliberately dumb baseline from
[Study 05](../study/05-the-agent-loop.md)). Each line shows an action, a count, and a
score. It'll run up to 80 actions and then stop.

At the end it prints a **scorecard** — a block of JSON with the score and action counts —
and a **web link** where you can view the same result in your browser.

::: note
**Expect the score to be zero or near zero, and that is the correct outcome.** The random
agent presses buttons at random; it isn't supposed to win. What we're proving here is
that the *pipeline* works: your key is accepted, a real game ran, and a scorecard came
back. That's the entire goal of this step. The score becomes meaningful in the next phase,
as the baseline everything else is compared against.
:::

### If it doesn't work

| What you see | What it means | What to do |
|---|---|---|
| `401` or `Unauthorized` or `Invalid API key` | The key isn't reaching the tool | Re-run `Get-Content .env` and check the line reads `ARC_API_KEY=` followed by your real key — no spaces around the `=`, no quotes around the key |
| `arc-agi-3 : The term ... is not recognized` | The tool isn't on your command path | Run it this way instead: `py -m arc_agi_3._cli --agent=random --game=ls20` |
| `404` or `game not found` | The game id `ls20` isn't available on your account | Run `arc-agi-3 --agent=random` with no `--game` — it plays whatever games your key can reach |
| Connection / timeout errors | Network or server issue | Check you're online, wait a minute, try again |
| It runs but you're not sure it worked | — | That's fine — send me the output (Step 6) and I'll read it |

---

## Step 6 — Tell me it's done

Come back to our chat and send me **either**:

- the last ~20 lines of output (select them in PowerShell, press `Ctrl+C` to copy, paste
  into chat), **or**
- the scorecard link it printed, **or**
- simply: *"key is in, ls20 ran, score was 0"*

::: warn
**Do not paste the key itself.** I don't need it and shouldn't have it — the code reads it
from `.env` on your machine at run time. If a key ever does end up in our chat by
accident, say so and delete it on the website; making a fresh one takes ten seconds.
:::

Once you confirm, I can start Phase A properly: record that run as a committed artifact,
count the tokens in a real frame (which replaces the estimate in
[Study 03](../study/03-what-an-llm-really-is.md) with a measured number), and begin
building the loop.

---

## What just happened, in one line

You created an identity with ARC Prize, generated a secret that proves you're you, stored
it in the one file Git is configured to ignore, and used it to play a real game
end-to-end. That last part — a full round trip through the real system with the simplest
possible agent — is exactly how you should start every integration: **prove the pipeline
before you add the cleverness**, so that when something breaks later you already know the
plumbing was fine.

---

**Sources checked 2026-07-22:**
- [docs.arcprize.org/api-keys](https://docs.arcprize.org/api-keys) — sign-up flow, Google/GitHub login, profile → API Keys, the `ARC_API_KEY` variable name
- The installed `arc-agi-3` SDK v0.0.1 source — confirms it reads `.env` from the current
  working directory and sends the key as the `X-API-Key` header
