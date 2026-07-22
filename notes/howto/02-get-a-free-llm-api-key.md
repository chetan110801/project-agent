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

Real output from 2026-07-22:

```text
key found      : AQ.A…Ygqg (53 chars)
models visible : 56 (25 with 'flash' in the name)
model          : gemini-3.5-flash-lite
round trip     : 964 ms, model said 'ready'

encoding                       chars  tiktoken   gemini
raw grid, hex packed           4,159      1473     4152
objects                        1,083       468      571
```

The checker tries several models and reports the first that answers — a model being
*listed* by the API does not mean your account may call it. Pass one explicitly if you
want: `py scripts/check_llm_key.py gemini-3.6-flash`.

Those last two lines are the point: what one real `ls20` screen costs in **Gemini's own
tokens**. They already overturned a headline number in study note 06 — for the full
two-tokeniser table, run `py scripts/measure_tokens.py`.

## Get your rate limits — I can't look these up for you

8. Open **https://aistudio.google.com/rate-limit**, click **See more** to expand the model
   list, find the row for the model the checker picked in step 7 (currently
   **`gemini-3.5-flash-lite`**), and note three numbers: **RPM** (requests/minute), **TPM**
   (tokens/minute), **RPD** (requests/day).

   The dashboard shows them as `used / limit` — the limit is the number after the slash.

Google no longer publishes these — they're per-account and per-model, so any number I wrote
here would be invented. They decide real things: the `gemini-2.5-flash` row shows **20 RPD**,
and if Flash-Lite is similar then **one 80-action game cannot make one model call per
action** and the whole loop design changes.

## Report back

9. Paste me the step 7 output **and** the three numbers from step 8. Never the key.

---

## If it doesn't work

| What you see | Fix |
|---|---|
| `no GEMINI_API_KEY or GOOGLE_API_KEY found` | Wrong folder, or step 5 didn't run. Check `Get-Content .env` |
| `google-genai is not installed` | `py -m pip install -U google-genai` (it was already installed on 2026-07-22) |
| `FAILED to list models` — 400 or 403 | Key wrong, or brand new. Re-copy it; wait a minute; retry |
| every candidate prints `unavailable` | Models get retired for new accounts. Run `py scripts/check_llm_key.py <name>` with one from the printed flash list |
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
