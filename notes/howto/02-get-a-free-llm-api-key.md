# How-to 02 — Free LLM API key (Google AI Studio)

*Checked 2026-07-22 against Google's own docs (links at the bottom). ~6 minutes. Free, no
card. Needs a Google account.*

**Why:** the agent can play but can't think — its "decide" step is still a coin flip, which
completed 0 of 7 levels of `ls20` even with 400 actions. This key puts a model in that slot.

::: warn
**Two rules.**
1. The key is a password — `.env` only, never chat or GitHub.
2. **On the free tier Google may use your prompts to improve their products** (their
   pricing page says so outright). Game grids are harmless. Never send anything private,
   personal, or work-confidential through a free-tier key.
:::

---

## Get the key

1. Go to **https://aistudio.google.com/apikey** and sign in.
2. Accept the terms. If it mentions a **Google Cloud project**, accept the default — one is
   created for you, it costs nothing.
3. Click **Create API key** → **copy it**. It starts with `AIza`. This is the only time the
   full key is shown.

## Put it in the project

4. Open PowerShell and go to the folder:

```powershell
cd "C:\Users\cheta\OneDrive\project-agent"
```

5. Append the key — replace `PASTE_YOUR_KEY_HERE`, keep the quotes:

```powershell
Add-Content -Path .env -Value 'GEMINI_API_KEY=PASTE_YOUR_KEY_HERE' -Encoding utf8
```

::: warn
**`Add-Content`, not `Set-Content`.** Your `.env` already holds the ARC key.
`Set-Content` replaces the whole file and it would be gone.
:::

6. Check — you should now see **two** lines:

```powershell
Get-Content .env
```

```text
ARC_API_KEY=…
GEMINI_API_KEY=AIza…
```

## Prove it works

7. Run the checker (it masks the key, so its output is safe to share):

```powershell
py scripts/check_llm_key.py
```

Expect roughly:

```text
key found      : AIza…7Xk2 (39 chars)
models visible : 47 (12 with 'flash' in the name)
round trip     : 812 ms, model said 'ready'

encoding                       chars  tiktoken   gemini
raw grid, hex packed           4,159      1471     ....
objects                        1,083       468     ....
```

The last two lines are the point: what one real `ls20` screen costs in **Gemini's own
tokens**. Every token number in this project so far came from an OpenAI counter, which only
ever compared our encodings with each other.

## Get your rate limits — I can't look these up for you

8. Open **https://aistudio.google.com/rate-limit**, find the **Gemini 2.5 Flash** row, and
   note three numbers: **RPM** (requests/minute), **TPM** (tokens/minute), **RPD**
   (requests/day).

Google no longer publishes these — they're per-account, so any number I wrote here would be
invented. They decide real things: how fast the agent can play, whether it can afford to
think twice per move, how many eval runs fit in a day.

## Report back

9. Paste me the step 7 output **and** the three numbers from step 8. Never the key.

---

## If it doesn't work

| What you see | Fix |
|---|---|
| `no GEMINI_API_KEY or GOOGLE_API_KEY found` | Wrong folder, or step 5 didn't run. Check `Get-Content .env` |
| `google-genai is not installed` | `py -m pip install -U google-genai` (it was already installed on 2026-07-22) |
| `FAILED to list models` — 400 or 403 | Key wrong, or brand new. Re-copy it; wait a minute; retry |
| `429` or "quota" | Free-tier limit hit. Wait — it resets. See step 8 |
| Only `GEMINI_API_KEY` in `.env` | You overwrote the file. Re-add the ARC key: How-to 01, rotate section |

---

**Sources checked 2026-07-22:**
[api-key](https://ai.google.dev/gemini-api/docs/api-key) (creation flow, default project,
and that the SDK reads both `GEMINI_API_KEY` and `GOOGLE_API_KEY` — the latter wins if both
are set) ·
[pricing](https://ai.google.dev/gemini-api/docs/pricing) (Flash models free of charge;
free-tier data **is** used to improve Google's products) ·
[rate-limits](https://ai.google.dev/gemini-api/docs/rate-limits) (limits are per-project and
must be read from AI Studio — hence step 8).
