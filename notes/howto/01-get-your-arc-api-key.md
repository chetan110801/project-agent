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

## Step 3 — Find your API key (it already exists)

*Corrected 2026-07-22 after Chetan actually did this: the platform creates a key for you
automatically on first login. There is usually nothing to create.*

1. Look at the **top-right corner** of the page. There will be your **user profile** —
   your name, your avatar picture, or a small circle icon.
2. **Click it.** You land on your profile page (the address bar reads
   `arcprize.org/user`).
3. Scroll down to the box headed **API Keys**.
4. **You should already see one row there** — a masked key like `6e•••7851`, a **GAMES**
   column saying `public`, and the date it was created. That is your key. It was made for
   you when you logged in.
5. **Click the small copy icon** (the clipboard button immediately to the right of the
   masked key). That copies the **full** key to your clipboard — the screen only ever
   shows the masked short form, so the copy button is the only way to get it.

::: note
**Why is it masked?** So that a screenshot, a screen-share, or someone glancing at your
laptop doesn't leak it. The first and last few characters are shown only so you can tell
two keys apart. Nothing is wrong.
:::

**If the API Keys box is empty:** click **Create Key** (leave the `public` checkbox
ticked — `public` means the key can play the public games, which is exactly what we
want). The new row appears immediately; then do step 5 above.

**Don't delete the key** (the bin icon on the right) unless you mean to. If you ever do
delete it by accident, or think it leaked, just click **Create Key** for a new one — old
key dead, new key works, nothing else breaks.

The key is now on your clipboard. Go straight to Step 4 — you'll paste it there. You do
not need to save it anywhere else.

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

**What actually happens on Windows** (observed 2026-07-22, this exact machine):

```text
API endpoint: https://three.arcprize.org/api/games
2026-07-22 10:11:21,180 | INFO | Game list: ['ls20-9607627b']
```

…and then the window comes back to a prompt, seemingly having done nothing. **It worked.**
Look in the project folder and you'll find a new file named something like
`ls20-9607627b.random.80.<long-id>.recording.jsonl`, about 1 MB. That file is the whole
game: 81 frames plus the scorecard.

::: warn
**This is a bug in the tool, on Windows, and it is not your fault.** When the agent
finishes, the tool shuts itself down by sending itself the "Ctrl-C" signal. On Linux and
Mac that runs a tidy-up step that prints the scorecard and a web link. On Windows the same
signal simply kills the process, so the run ends abruptly with exit code 2 and the
scorecard is never printed — even though the game was played and fully recorded.

Nothing is lost: the scorecard is the last line of the recording file, and
`py scripts/analyze_run.py` reads it out. It is also one of the reasons this project runs
the agent from its own code rather than through this tool.
:::

::: note
**Expect the score to be zero, and that is the correct outcome.** The random agent presses
buttons at random; it isn't supposed to win. What this proves is that the *pipeline* works:
key accepted, real game played, frames recorded. The score becomes meaningful in the next
phase, as the baseline everything else is compared against.
:::

### If it doesn't work

| What you see | What it means | What to do |
|---|---|---|
| `401` or `unauthorized`, and `Game list: []` | The key isn't reaching the tool | Almost always the `.env` file. It must contain the line `ARC_API_KEY=` **followed by** the key, and it must have no invisible byte-order mark at the start — which `Set-Content -Encoding utf8` adds on Windows PowerShell 5.1. Tell me and I'll rewrite the file for you; it's a two-second fix and it has bitten this project twice. |
| Exit code 2, no scorecard printed | The Windows shutdown bug above | Nothing to do — check for the `.recording.jsonl` file; if it's there, the run succeeded |
| `arc-agi-3 : The term ... is not recognized` | The tool isn't on your command path | Run it this way instead: `py -m arc_agi_3._cli --agent=random --game=ls20` |
| `The specified game ... does not exist` | The game id filter matched nothing | Run `arc-agi-3 --agent=random` with no `--game` — it plays whatever games your key can reach |
| Connection / timeout errors | Network or server issue | Check you're online, wait a minute, try again |
| It runs but you're not sure it worked | — | Send me the output (Step 6) and I'll read it |

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
