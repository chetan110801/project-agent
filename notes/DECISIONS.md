# Decision log

One entry per decision that shaped the project. Newest first.
Format: date · decision · why · what was rejected.

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
