# Study note 2 — Phase 0: checking the ground before building on it

*Written 2026-07-21, from live sources checked today. Phase 0's whole job is to catch
the facts that moved between "when we planned" and "when we build." Two did.*

---

## The verdict in one paragraph

The plan survives, with one forced change: **a full-scale ARC-AGI-1 reproduction is
arithmetically impossible on free Kaggle GPUs** (the paper used ~288 H100-hours; that is
roughly two *years* of Kaggle quota). The fix is not to abandon reproduction but to
reorder it: reproduce TRM **on Sudoku-Extreme first** (the paper's cheapest headline
result, ~18 GPU-hours on a datacenter card — feasible in 1–2 weeks of quota), run the
recursion-depth ablation there, and then do a **reduced-scale** ARC-AGI-1 run, reported
honestly as reduced-scale. The ablation — the part of Step 1 that is genuinely ours —
is untouched; it just runs on a task we can afford. Step 2 (ARC-AGI-3 agent) is
confirmed and the Sept 30 milestone is real, but the leaderboard has moved a lot since
our numbers were written down.

---

## Fact by fact

### 1. The TRM paper — ✅ confirmed unchanged

[arXiv 2510.04871](https://arxiv.org/abs/2510.04871), "Less is More: Recursive
Reasoning with Tiny Networks," Alexia Jolicoeur-Martineau (Samsung SAIL Montréal).
45% on ARC-AGI-1, 8% on ARC-AGI-2, ~7M parameters, ~87% on Sudoku-Extreme. Still v1,
no revisions.

### 2. The TRM code — ⚠️ available, but the repo is now frozen

[SamsungSAILMontreal/TinyRecursiveModels](https://github.com/SamsungSAILMontreal/TinyRecursiveModels)
is MIT-licensed and public, but was **archived (made read-only) on 2026-04-01**.
Cloning and modifying is fine; upstream fixes, answered issues, or updates will never
come. Consequence: we fork it into our own repo early so our reproduction can't be
orphaned by a deletion.

### 3. Training cost — 🚨 the fact that changes the plan

From the repo's own README:

| Task | Paper's hardware | Paper's runtime | ≈ on Kaggle (T4×2) |
|---|---|---|---|
| Sudoku-Extreme | 1× L40S | ~18 h | ~45–60 h → **1–2 weeks of quota** |
| Maze-Hard | 4× L40S | <24 h | several weeks |
| ARC-AGI-1 | 4× H100 | ~3 days (~288 H100-h) | **thousands of hours → ~2 years** |

Kaggle gives ~30 GPU-hours/week (T4×2 or P100, 12-hour session cap — so training must
checkpoint and resume). An H100 is roughly 10–15× a T4 for this kind of training; the
conversion above is approximate but the conclusion is not close: full-scale ARC training
is out by two orders of magnitude. **This is why Phase 0 exists.** The original plan's
"confirm the published ARC score" was written before this arithmetic was done.

### 4. ARC-AGI-1 data — ✅ confirmed, free

Public on GitHub ([fchollet/ARC-AGI](https://github.com/fchollet/ARC-AGI)) and mirrored
as Kaggle competition data. TRM's dataset builder expects the Kaggle layout
(`kaggle/combined/arc-agi`). No access barrier.

### 5. Kaggle quota — ✅ confirmed as remembered

~30 GPU-hours/week, NVIDIA T4×2 or P100 (16 GB), sessions up to 12 h, background
execution supported. Free.

### 6. ARC Prize 2026 / ARC-AGI-3 — ✅ confirmed, with corrected numbers

Per [arcprize.org/competitions/2026/arc-agi-3](https://arcprize.org/competitions/2026/arc-agi-3):

- Total pool **$850K**: Grand Prize $700K (first agent to score 100% — carries over if
  unclaimed), Top Score awards $75K, Milestone prizes $75K.
- **Milestone #2 closes 2026-09-30**: 1st $25K / 2nd $10K / 3rd $2.5K, open-source
  required. (Our old note said "$75K milestone" — that's the whole milestone *category*
  across both deadlines; Milestone #1, June 30, has already passed.)
- Submissions via Kaggle. All prize-eligible code open-sourced. **No internet access
  during evaluation** — so no calling GPT/Claude APIs from inside the agent.

### 7. ARC-AGI-3 state of play — ⚠️ moved a lot since our numbers

What we had written down (frontier best 0.37%, best agent ~12.6%) is now stale:

- Frontier best is now **GPT-5.6 Sol at ~7.8%** (up ~20× in months).
- The ~12.58% figure was a preview-phase RL + graph-search agent.
- A July 2026 paper, OPINE-World ([arXiv 2607.01531](https://arxiv.org/pdf/2607.01531)),
  claims **78.4% on the public eval set** with programmatic world-modeling +
  ontology-guided exploration. (Public eval ≠ the competition's private eval, and
  paper claims deserve skepticism until reproduced — but the direction is clear.)
- Humans: still 100%.

Two honest consequences. First, study note 1's line "best frontier model scores under
1%" is now false and the interview pitch must not use it. Second, the bar for "a
leaderboard-worthy agent" is rising monthly — our Step 2 goal stays *getting on the
public leaderboard with an open, explainable agent*, not prize money.

---

## The revised Step 1 (decision recorded in DECISIONS.md)

1. **Reproduce cheap, at full scale:** TRM on Sudoku-Extreme, target ≈87%. This is a
   real reproduction of a headline paper number, affordable on Kaggle.
2. **Run the ablation where we can afford statistics:** recursion depth 16 → 8 → 4
   (→ 2), identical budget per depth, on Sudoku-Extreme. This curve is still
   unpublished — the contribution survives intact.
3. **Touch ARC honestly:** one reduced-scale ARC-AGI-1 run (reduced augmentation /
   shorter schedule), reported as "X% at 1/Nth of the paper's compute," never presented
   as a full reproduction.

The timeless lesson this note exists to teach: **check the arithmetic of a plan against
its budget before writing code.** One README table invalidated a phase; ten minutes of
verification saved weeks. That is what Phase 0 is *for*.

---

## Sources checked (2026-07-21)

- https://arxiv.org/abs/2510.04871
- https://github.com/SamsungSAILMontreal/TinyRecursiveModels (+ raw README)
- https://github.com/fchollet/ARC-AGI
- https://arcprize.org/arc-agi/3 and https://arcprize.org/competitions/2026/arc-agi-3
- Kaggle docs / community posts on GPU quota
- ARC-AGI-3 leaderboard trackers (llm-stats.com, benchlm.ai) + arXiv 2607.01531
