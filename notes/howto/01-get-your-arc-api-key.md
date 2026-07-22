# How-to 01 — ARC-AGI-3 API key

*Checked 2026-07-22 against [docs.arcprize.org/api-keys](https://docs.arcprize.org/api-keys)
and the installed `arc-agi-3` SDK v0.0.1. ~5 minutes. Free, no card. Needs a Google or
GitHub account.*

::: warn
The key is a password. It goes in `.env` (gitignored) and nowhere else — not chat, not
screenshots, not GitHub. Leaked? Delete it on the site and create a new one.
:::

---

## Get the key

1. Go to **https://arcprize.org/platform** and log in with **Google or GitHub**.
   *(Nothing happens on click → allow pop-ups for the site.)*
2. Click your **profile, top right** → you land on `arcprize.org/user`.
3. Scroll to **API Keys**. **A key is already there** — the platform makes one on first
   login. If the box is empty, click **Create Key** (leave `public` ticked).
4. Click the **copy icon** next to the masked key. The screen only ever shows the masked
   form, so the copy button is the only way to get the full key.

## Put it in the project

5. Open PowerShell (**Windows key** → `powershell` → Enter) and go to the folder:

```powershell
cd "C:\Users\cheta\OneDrive\project-agent"
```

6. Write the key in — replace `PASTE_YOUR_KEY_HERE`, keep the quotes:

```powershell
Add-Content -Path .env -Value 'ARC_API_KEY=PASTE_YOUR_KEY_HERE' -Encoding utf8
```

::: warn
**`Add-Content`, not `Set-Content`.** `Set-Content` replaces the whole file and deletes
every other key in it.
:::

7. Check it:

```powershell
Get-Content .env
```

Expect a line reading `ARC_API_KEY=` followed by your key.

## Prove it works

8. Play one real game through our runner:

```powershell
py scripts/run_agent.py --game ls20 --max-actions 80
```

Expect roughly:

```text
game    : ls20-9607627b
scorecard: 841609df-…  https://three.arcprize.org/scorecards/841609df-…
ls20-9607627b [random] score=0 state=NOT_FINISHED actions=80 dead=0% stopped=max_actions
rejected  : 0 illegal actions (never sent)
```

**Score 0 is correct.** The random policy isn't meant to win; this proves the pipeline.

## Report back

9. Paste me the output above (it contains no key). Never paste the key itself.

---

## Rotating a key (if it leaks)

1. `arcprize.org/user` → **API Keys** → bin icon on the old key → **Create Key** → copy.
2. Update `.env`: open it (`notepad .env`), replace the value on the `ARC_API_KEY=` line,
   save.
3. **Also check the Windows environment variable** — on this machine `ARC_API_KEY` is set
   there too, and it wins over `.env`:

```powershell
[Environment]::SetEnvironmentVariable('ARC_API_KEY','NEW_KEY_HERE','User')
```

Then **close and reopen PowerShell** (env vars only load at start) and rerun step 8.

---

## If it doesn't work

| What you see | Fix |
|---|---|
| `401` / `unauthorized` | The `.env` line is wrong, or has an invisible byte-order mark at the start — `Set-Content -Encoding utf8` adds one on PowerShell 5.1, and it produces a variable named `﻿ARC_API_KEY` that nothing matches. Tell me; it's a two-second fix and it has bitten this project twice |
| `no ARC_API_KEY found` | Wrong folder, or step 6 didn't run. Check with `Get-Content .env` |
| `no game id starts with 'ls20'` | Game ids carry a version suffix that changes. Run `py scripts/run_agent.py --list` to see what exists |
| Connection / timeout | Check you're online, wait a minute, retry |

::: note
**Using the vendor CLI (`arc-agi-3 --agent=random --game=ls20`) instead?** It works but
exits with code 2 and prints no scorecard on Windows — it shuts down with a Ctrl-C signal
to itself, which Windows treats as a kill. The recording file still gets written. This is
one reason we run the agent from our own code.
:::
