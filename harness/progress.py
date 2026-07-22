"""Progress signals: telling the agent whether its work is *accumulating* or *churning*.

This module exists because of a measured failure and a measured non-fix.

**The failure** (Phase B, `artifacts/run-report-llm-80.json`): the model pressed `ACTION3`
57 times out of 80, 41 of them consecutively, narrating a fresh justification each turn. It
was not being stupid. Each press really did change the screen — a two-cell marker on rows
61-62 stepped one column along, 42, 43, 44 ... — so every signal the prompt carried said
*something happened*. Nothing in the prompt could say *and it got you nowhere*.

**The non-fix** (Phase C experiment 1, reverted): we gave it its own last eight actions.
Eight lines reading `ACTION3 -> 2 cells changed` were read by the model as *this action
reliably works*, and it got **worse** on 7 of 10 steering metrics for +14% tokens. The
lesson, written into `notes/DECISIONS.md`: **memory of your actions is not feedback about
your progress.** So this module does not tell the agent what it did. It measures what its
actions *added up to*, and states a verdict the model does not have to infer.

The four candidates below were written before any of them was believed, and
`scripts/progress_signals.py` runs all four over the committed recordings — including the
one where the agent got stuck — before any of them is put in a prompt. That ordering is the
whole point: `revisit_rate` was invented from a story about this exact failure and reads
**0%** on it (`harness/evals.py`). A signal is a guess until it is run against the failure.

**Nothing in this module is in the agent's prompt, and that is the result.** All four
candidates were measured against the recordings before any of them was shown to a model
(`scripts/progress_signals.py` -> `artifacts/progress-signals.json`), and all four failed.
The best of them failed *backwards*.

Holding the game constant at `ls20`, mean churn ratio — net change divided by total change,
so low means "the work undoes itself" — at every window we swept:

| window (actions) | 5 | 10 | 20 | 30 | 40 | 60 |
|---|---:|---:|---:|---:|---:|---:|
| random play | 0.359 | 0.233 | 0.158 | 0.131 | **0.116** | 0.114 |
| the stuck LLM run | 0.681 | 0.538 | 0.334 | 0.194 | **0.136** | 0.122 |

**The stuck agent looks healthier than a coin flip at every window**, and inside its own
41-action streak it scores 0.650 against 0.336 outside it — the opposite of the prediction.
Novelty agrees: the stuck run reached a new screen on **100%** of its actions against random
play's 80.6%.

The recordings say why, and it is worth more than the signal would have been. The agent was
not oscillating. It had found a bar it could extend by two cells per press, and it extended
it — monotonically, forty times, each press adding two cells that stayed added. By every
local measure of "is my work accumulating", it was doing perfect work. It was simply
extending the wrong thing, and *no statistic computed from the screen can know that*,
because knowing it requires knowing the goal — which is precisely what an ARC-AGI-3 agent
is not told and what a frozen score cannot supply.

So the Phase B diagnosis ("the agent cannot see its own repetition") and the Phase C
diagnosis ("it needs a progress signal") are both wrong, and the recordings refuted both
for the price of a few seconds of CPU. The real failure is **premature commitment**: the
agent formed one hypothesis about the goal and never tested another. That is answered by
`harness/policies.py`'s repetition guard, not by more feedback.

Kept, rather than deleted, for three reasons: the negative result is evidence and evidence
lives in the repo; `scripts/progress_signals.py` imports it, so the claim above is
re-runnable; and the tests pin the growing-bar case that defeated it, so nobody rebuilds
this idea from the same story a third time.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any

from .frames import Grid, diff_grids, grid_shape

# Where "going in circles" would have been declared, had the signal worked. It does not:
# measured on `ls20`, random play sits at 0.116-0.359 and the stuck run at 0.136-0.681, so
# any threshold that catches the failure catches ordinary play first. The constant is kept
# so `going_in_circles` has a definition and the tests can pin the behaviour; no agent
# decision depends on it.
CHURN_STUCK_BELOW = 0.5

# The window the signals look back over. 10 is the shortest window in which the stuck run
# is unambiguous (a 41-action streak) and short enough that a genuinely new phase of the
# game clears it within a few actions. Costed in tokens: the rendered block is one or two
# lines, roughly 40 tokens, against the 104 that eight history lines cost.
DEFAULT_WINDOW = 10


@dataclass(frozen=True)
class Progress:
    """What the last `window` actions added up to. All four candidates, always computed.

    Computing every candidate on every call — not just the one we ship — costs nothing
    offline and means the trace can be re-read later for the signals we did *not* use.
    """

    window: int
    # -- candidate 1: novelty of the screen (the one already known to be blind) --------
    new_screens: int
    # -- candidate 2: has the composition of the screen changed at all? ---------------
    colours_changed: int
    # -- candidate 3: how much of the board has the agent touched lately? -------------
    activity_cells: int
    activity_box: tuple[int, int, int, int] | None  # top, left, bottom, right
    activity_box_share: float
    # -- candidate 4: net effect against work done ------------------------------------
    cumulative_changes: int
    net_changes: int

    @property
    def new_screen_rate(self) -> float:
        return self.new_screens / self.window if self.window else 0.0

    @property
    def churn_ratio(self) -> float | None:
        """`net_changes / cumulative_changes`. None when nothing changed at all.

        1.0 means every cell the agent touched stayed touched — work accumulated.
        0.1 means it moved ten cells for every one that ended up different — it is
        walking a marker back and forth, or in a circle.

        None is deliberately not 0.0: "you changed nothing" is a different situation from
        "you changed a lot and it added up to nothing", and `no_change_rate` already
        covers the first. Collapsing them would make the metric read the same for a dead
        button and a treadmill.
        """
        if not self.cumulative_changes:
            return None
        return self.net_changes / self.cumulative_changes

    @property
    def going_in_circles(self) -> bool:
        r = self.churn_ratio
        return r is not None and r < CHURN_STUCK_BELOW

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["churn_ratio"] = None if self.churn_ratio is None else round(self.churn_ratio, 4)
        d["new_screen_rate"] = round(self.new_screen_rate, 4)
        d["going_in_circles"] = self.going_in_circles
        return d


def _colour_counts(grid: Grid) -> Counter:
    return Counter(v for row in grid for v in row)


def measure_progress(
    grids: list[Grid],
    seen_before: set[str] | None = None,
    hashes: list[str] | None = None,
    window: int = DEFAULT_WINDOW,
) -> Progress | None:
    """Measure the last `window` transitions in `grids` (oldest first, newest last).

    Returns None when there is not yet a full transition to measure, so a caller can say
    "too early to tell" rather than print a confident 0.

    `hashes` are the fingerprints of the same grids (`frames.grid_fingerprint`), passed in
    rather than recomputed because the loop already has them. When absent, the novelty
    candidate is simply not measured — it is reported as 0 new screens, and the offline
    analyser always passes them.

    Grids of differing shape inside the window end the measurement: a shape change means
    the screen was replaced, and diffing across it would produce a meaningless count. We
    measure only the tail that shares the newest shape, which is the honest answer to
    "what have you done *lately*".
    """
    if len(grids) < 2:
        return None

    tail = grids[-(window + 1) :]
    shape = grid_shape(tail[-1])
    # Walk back from the newest until the shape changes; keep only the comparable tail.
    keep = 1
    for g in reversed(tail[:-1]):
        if grid_shape(g) != shape:
            break
        keep += 1
    tail = tail[-keep:]
    if len(tail) < 2:
        return None

    steps = len(tail) - 1
    cumulative = 0
    touched: list[tuple[int, int]] = []
    for before, after in zip(tail, tail[1:]):
        d = diff_grids(before, after)
        cumulative += d.count
        touched.extend((r, c) for r, c, _, _ in d.changed)

    net = diff_grids(tail[0], tail[-1]).count

    before_counts, after_counts = _colour_counts(tail[0]), _colour_counts(tail[-1])
    colours_changed = sum(
        1
        for v in set(before_counts) | set(after_counts)
        if before_counts.get(v, 0) != after_counts.get(v, 0)
    )

    box = None
    share = 0.0
    if touched:
        rows_, cols_ = zip(*touched)
        box = (min(rows_), min(cols_), max(rows_), max(cols_))
        area = (box[2] - box[0] + 1) * (box[3] - box[1] + 1)
        share = area / max(1, shape[0] * shape[1])

    new_screens = 0
    if hashes:
        seen = set(seen_before or ())
        window_hashes = hashes[-steps:]
        earlier = set(hashes[:-steps]) if len(hashes) > steps else set()
        seen |= earlier
        for h in window_hashes:
            if h not in seen:
                new_screens += 1
            seen.add(h)

    return Progress(
        window=steps,
        new_screens=new_screens,
        colours_changed=colours_changed,
        activity_cells=len(set(touched)),
        activity_box=box,
        activity_box_share=round(share, 6),
        cumulative_changes=cumulative,
        net_changes=net,
    )


def render_progress(p: Progress | None) -> str:
    """The wording the model *would* have seen. Never called by the policy — see above.

    Kept because it is what the experiment would have shipped, and a negative result you
    cannot read is a negative result nobody can check. It was written with the lesson of
    experiment 1 built in — the harness states the verdict rather than handing over facts
    for the model to interpret favourably — which is the one part of this idea that
    survived, and it survived into the repetition guard instead.
    """
    if p is None:
        return "too early to tell"
    if p.cumulative_changes == 0:
        return (
            f"in your last {p.window} actions NOTHING on the screen changed at all. "
            "What you are doing has no effect — try a different action or a different spot."
        )
    net_words = (
        f"the screen is now {p.net_changes} cells different from where it was "
        f"{p.window} actions ago"
    )
    if p.going_in_circles:
        return (
            f"you changed {p.cumulative_changes} cells over your last {p.window} actions, "
            f"but {net_words}. You are going in circles: the work is undoing itself. "
            "Try a different action, or the same action somewhere else."
        )
    return (
        f"you changed {p.cumulative_changes} cells over your last {p.window} actions and "
        f"{net_words}. Your changes are adding up."
    )


__all__ = [
    "CHURN_STUCK_BELOW",
    "DEFAULT_WINDOW",
    "Progress",
    "measure_progress",
    "render_progress",
]
