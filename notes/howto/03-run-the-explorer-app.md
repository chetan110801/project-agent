# How-to 03 — Run the Explorer app (see the whole project in your browser)

*Written and checked 2026-07-29 on this laptop, against the real app. ~2 minutes to start,
~15 minutes for the tour. **No API key. No internet. Nothing to install.***

**Why you are doing this.** Everything this project built — the recorded games, the evals,
the failure taxonomy, the traces, the budgets — currently lives in files. The Explorer app
puts all of it on one screen so you can *see* it, and so you can show it to an interviewer
by sharing your screen instead of scrolling through JSON. It is also the fastest way to
understand your own project: every view has a **Learn** switch that explains, in plain
words, what you are looking at.

::: note
The app is a **viewer** (something that only looks at things). It reads files the project
already wrote and never changes them. You cannot break the project by clicking around in it.
:::

---

## Start it

1. Open **PowerShell**: press the **Windows key**, type `powershell`, press **Enter**.
   A dark window opens with a blinking cursor.

2. Go to the project folder — type this and press **Enter**:

```powershell
cd "C:\Users\cheta\OneDrive\project-agent"
```

The line in front of your cursor (the *prompt*) should now end with `project-agent>`.

3. Start the app — type this and press **Enter**:

```powershell
py explorer/app.py
```

4. **What you should see.** In PowerShell, exactly this box:

```text
====================================================================
  project-agent — Explorer (offline)
  serving http://localhost:8000/
  offline core: no API key, no network. Ctrl-C to stop.
====================================================================
```

Then your **browser opens by itself** at `http://localhost:8000`, showing a dark page (a light
one if your system is set to light mode) with **project-agent · Explorer** at the top left, a
row of seven tabs — **Home, Replay, Evals, Taxonomy, Traces, Budgets, Live** — and a
**Demo / Learn** switch at the top right.

::: warn
**Leave the PowerShell window open.** It *is* the app — closing it stops the site, and the
browser page will then fail to load. It is normal for that window to keep printing lines
like `127.0.0.1 - "GET /api/runs HTTP/1.1" 200 -`. That is the page asking for data; it
means things are working.
:::

---

## The 15-minute tour (do this once, in order)

5. **Home.** Read the headline at the top. It says the honest result — the agent never beats
   the game — and lists the four experiments. This is the same sentence you open with in an
   interview.

6. **Replay.** This is the best part. Two dropdowns at the top:
   - **Run** — pick any recorded game. It starts on an LLM run that visibly gets stuck.
   - **Compare with (same game)** — pick the *random* run of the same game to get two screens
     side by side.

   Then press **▶ Play**. You are watching one turn of the agent loop (look at the screen →
   decide → act → look again) at a time: the 64×64 screen (the game's picture, 64 squares
   across and 64 down), the action it chose, **the model's own reason for choosing it**, and
   the score. Use **❚❚ Pause**, and the **Speed** control to slow it down.

   Now press **⤷ Jump to where it got stuck**. It jumps to the longest run of the same action
   repeated over and over. **Watch the screen keep changing while the score stays 0.** That is
   the wall this whole project is about, and now you have seen it rather than read about it.

7. **Evals.** Every experiment arm (one setup being tested) and its numbers. Each measurement
   is tagged *steering* (did the change do what it was meant to do?), *outcome* (did the score
   move?) or *cost* (what did it spend?), and the before/after comparisons sit underneath. The
   story to notice: steering numbers move, outcome numbers don't.

8. **Taxonomy.** The bar chart of the six failure buckets — **88% active-but-no-progress,
   0% progress**. The wall as a number, counted from the traces.

9. **Traces.** The raw decision records behind everything else — one line per decision, with
   the reasoning. This is your answer to *"how do you know why it did that?"*

10. **Budgets.** Tokens (the pieces of text a model is billed and limited by), requests per day,
    latency (how long each call takes), and the model bakeoff (a head-to-head comparison) — the
    run where the fastest model on paper turned out to be unusable.

11. **Now flip the switch.** Top right, slide **Demo → Learn**. Every view grows a plain-language
    explainer and links to the matching study note; clicking one opens the note right there in
    the app. Flip it back to **Demo** when you show someone — Demo is the clean version.

---

## Stop it

12. Click the **PowerShell** window, hold **Ctrl** and press **C**.

You should see:

```text
  stopped.
```

The browser tab will now fail to load if you refresh it. That is correct — the app is off.
To start again, repeat step 3.

---

## The **Live** tab — read this before you touch it

The seventh tab plays **real games over the internet**. Everything above needs nothing; this
needs keys, and one of its two modes spends your rationed (strictly limited) free quota — the
number of requests the free plan lets you make in a day.

| Button | What it does | What it costs |
|---|---|---|
| **▶ No-key demo (mock)** | A fake local game, clearly labelled as not the real server | Nothing. Safe to click any time |
| **▶ Real game** (under *You play*) | You play a real ARC-AGI-3 game yourself, in the browser | Needs `ARC_API_KEY`. No LLM quota — it's you clicking, not the model |
| **▶ Start watching** (under *Watch the agent play*) | A real agent plays a real game, streamed live | Needs an ARC key **and** an LLM key, and **spends the 500-requests-per-day free tier**. The action budget is capped low on purpose |

::: warn
**Before using either real mode, rotate the ARC key.** The old key was once printed into a
transcript, so it must be replaced — the steps are in
[how-to 01, "Rotating a key"](01-get-your-arc-api-key.md). Until then, use **▶ No-key demo
(mock)**, which works with no keys at all.
:::

If a key is missing, its button is **disabled** and a **📘 How to get an ARC key** button
appears instead. Nothing crashes; that is by design. If the agent hits the daily limit
mid-run, you'll see an amber **"fell back"** step rather than an error: with no model answer
available the agent plays a **random** action and keeps going, exactly as the real harness
(the project's own agent code) does.

---

## If it doesn't work

| What you see | What to do |
|---|---|
| `py : The term 'py' is not recognized` | Type `python explorer/app.py` instead |
| `can't open file ... app.py: No such file or directory` | You're in the wrong folder. Redo step 2, then `dir` — you should see `explorer`, `harness`, `notes` |
| Two PowerShell windows are both running the app, and the page looks wrong or stale | On Windows a second copy **can quietly take the same port 8000 without any error** — so you cannot tell which one is answering. Press **Ctrl + C** in *every* window, then start one |
| `OSError: [WinError 10048] ... normally permitted` | Some *other* program is holding port 8000 (a port is the numbered door the app listens at). Use `py explorer/app.py --port 8001` and go to `http://localhost:8001` |
| The browser doesn't open by itself | Open it yourself and type `localhost:8000` in the address bar |
| The page is stuck on **Loading…** | Press **Ctrl + F5** (a hard refresh). If it stays, tell me — and check the PowerShell window for a red error block |
| A Windows Firewall pop-up | Not expected — the app only listens on your own machine (`127.0.0.1`). If one appears, **Cancel** is safe; the app still works |
| You want it to just run without typing | Double-click **`explorer\run.bat`** in File Explorer. Same thing |

**Want to prove the app itself is healthy?** With the server stopped, run:

```powershell
py explorer/smoke_test.py
```

The last line should read:

```text
All checks passed. The offline core reads real repo data with no key and no network.
```

---

## Tell me it's done

Paste back the last line PowerShell printed, plus one sentence: which run you replayed and
whether the score ever moved. (Nothing in that output contains a key.)

---

*Details of how the app is built: [`explorer/README.md`](../../explorer/README.md).
Why it exists: [`notes/07-explorer-app-spec.md`](../07-explorer-app-spec.md).*
