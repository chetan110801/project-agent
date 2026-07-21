# Decision log

One entry per decision that shaped the project. Newest first.
Format: date · decision · why · what was rejected.

---

## 2026-07-21 — Step 1 reordered: Sudoku-first reproduction; ARC at reduced scale only

**Decision:** Phase 0 verification (see `notes/02-phase0-verification.md`) found the
paper's ARC-AGI-1 training run cost ~288 H100-hours — roughly two years of Kaggle's
free 30 GPU-h/week. Step 1 therefore becomes: (a) full-scale TRM reproduction on
**Sudoku-Extreme** (~18 datacenter-GPU-hours, feasible in 1–2 weeks of quota, target
≈87%), (b) the recursion-depth ablation (16→8→4→2, equal budget per depth) on
Sudoku-Extreme, (c) one **reduced-scale** ARC-AGI-1 run reported honestly as
reduced-scale. The ablation contribution is unchanged; only the task it runs on moved.

**Why:** Forced by arithmetic, not preference. The alternative — burning weeks of quota
to reach a fraction of one ARC run — produces nothing showable.

**Rejected:** Renting cloud GPUs (violates zero-budget constraint); skipping
reproduction and doing only the ablation (no calibration that our training pipeline is
correct); Maze-Hard as the cheap task (several weeks of quota vs Sudoku's 1–2).

**Also recorded:** TRM's official repo was archived 2026-04-01 (read-only) — we fork it
so the reproduction can't be orphaned. ARC-AGI-3 leaderboard moved (frontier ~7.8%,
a paper claims 78.4% on public eval); the "frontier under 1%" line is retired from the
pitch.

---

## 2026-07-21 — Where "agentic engineering" lives in this project

**Decision:** Interview-facing agentic topics (the agent loop, memory, exploration
policy, evaluation of agents) are covered by **Step 2 itself** — the ARC-AGI-3 agent is
an observe→decide→act loop with memory and hypothesis-testing, built from first
principles rather than a framework. A study note on "the agent loop, timelessly" is
added to the standing list. Framework-specific tooling (LangGraph et al.) stays out of
study notes per the timeless-concepts constraint; RAG/function-calling interview
questions are covered by ResearchPath (resume project #2), not this project.

---

## 2026-07-21 — The project is an AGI-direction research piece, not an app

**Decision:** Build (1) a reproduction of the Tiny Recursion Model on ARC-AGI-1 plus an
unpublished recursion-depth ablation, then (2) a purpose-built agent for ARC-AGI-3
targeting the 30 Sept 2026 open-source milestone. Timeline flexible; each step showable
on its own.

**Why:** Chetan's long-term goal is AGI/ASI work; the portfolio must be a step on that
path or motivation dies. project-asi's own forward plan (`LEARNING/THE_PLAN.md`,
2026-07-21) identified the efficiency frontier as the one part of AGI research open to a
zero-budget individual, with these exact two moves as Phases 2–3. The portfolio project
and the AGI path now share one spine.

**Rejected:** study-materials generator, job-application copilot, GitHub issue triage,
customer-support agent, SRE/log copilot — all "generic software" apps; Chetan is
explicitly not interested in learning replaceable app-stack practices.

**Constraint recorded:** study notes teach *timeless* concepts (generalization,
test-time compute, ablations, exploration, the research loop) — never tooling for its
own sake. Claude writes the code; Chetan owns the understanding.

---

## 2026-07-21 — (earlier) Reliability-as-thesis, reframed

**Decision:** The original thesis — "anyone can vibe-code an app; the trust system
around it is the differentiator" — survives, reframed for research: reproduction
targets, held-out tests, one-command reruns, written experiment records.

**Why:** It is the same discipline interviewers probe in applied-science loops
(how do you know your result is real?), and it is timeless scientific method rather
than a tooling stack.
