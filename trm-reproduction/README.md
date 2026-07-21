# TRM reproduction on free Kaggle GPUs — ⏸ DEFERRED (2026-07-21)

> **Status: deferred to project-asi's research track** (see
> [notes/DECISIONS.md](../notes/DECISIONS.md), evening entry). project-agent pivoted to
> the LLM-driven ARC-AGI-3 agent + engineering harness. Everything below — the Phase 0
> feasibility findings and the pre-registered ablation design — is kept intact for
> when this work resumes. Nothing here is abandoned; it's parked.

Step 1 of this project: reproduce the Tiny Recursion Model (TRM,
[arXiv 2510.04871](https://arxiv.org/abs/2510.04871)) and run the unpublished
recursion-depth ablation. Scope was set by the Phase 0 feasibility check
([notes/02-phase0-verification.md](../notes/02-phase0-verification.md)):
**Sudoku-Extreme at full scale, ARC-AGI-1 at reduced scale.**

## Upstream code

Official repo: [SamsungSAILMontreal/TinyRecursiveModels](https://github.com/SamsungSAILMontreal/TinyRecursiveModels)
— MIT license, **archived 2026-04-01 (read-only)**.

First action of Phase 1: fork it (Chetan's GitHub account) so the code we depend on
cannot disappear, then clone the fork inside Kaggle notebooks.

## Plan of record

| Run | Task | Scale | Purpose | Est. Kaggle cost |
|---|---|---|---|---|
| 0 | Sudoku-Extreme | smoke (minutes) | pipeline works end-to-end on T4 | <1 h |
| 1 | Sudoku-Extreme | full (paper config) | reproduce ≈87% exact-accuracy | ~45–60 h (2 wks quota) |
| 2 | Sudoku-Extreme | ablation ×3–4 depths | the missing depth-vs-accuracy curve | budget set after run 1 |
| 3 | ARC-AGI-1 | reduced | connect the story to ARC, honestly labeled | 1 week of quota, fixed cap |

Experiment design for run 2 lives in [ablation-plan.md](ablation-plan.md).

## Kaggle constraints that shape everything

- ~30 GPU-hours/week (T4×2 or P100, 16 GB), sessions capped at 12 h
  → **training must checkpoint and resume across sessions**. Verifying/patching
  checkpoint-resume in the upstream trainer is the first engineering task of Phase 1.
- No persistent disk between sessions → checkpoints saved to a Kaggle Dataset each
  session, reloaded at the start of the next.
- Paper used `torchrun` multi-GPU; T4×2 supports 2-process DDP, P100 is single-GPU.

## Files

- [ablation-plan.md](ablation-plan.md) — the experiment: question, knob, protocol,
  what would falsify it.
- [kaggle/bootstrap.sh](kaggle/bootstrap.sh) — draft setup script for a Kaggle
  notebook cell (clone, install, build Sudoku data). Untested until first Kaggle run;
  expect to adjust.

## Rigor rules (from note 01, unchanged)

Reproduction target stated before running (87% Sudoku). Never tune on the scored
split. Every claim traces to a run artifact (config + seed + checkpoint + log).
Negative results get written up with the same care.
