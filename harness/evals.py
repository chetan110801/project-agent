"""The eval suite: how a change to this agent is judged.

Phase C exists because of a measurement made in Phase B: **score cannot referee anything
here.** A random policy given 400 actions on `ls20` — eighteen times the 22 actions the
server's own reference solution needs for level 1 — completed zero levels and scored zero
(`artifacts/ourloop-random-400.json`). The improved loop also scored zero. A metric that
reads 0 before and 0 after is not a metric; it is a constant, and tuning against it is
tuning against noise.

So this module splits every number into three kinds, and the split is the point:

* **STEERING** — dense signals that move long before the agent starts winning. These are
  what a change is judged on. Illegal actions, dead actions, revisited screens, repetition,
  and how deep into level 1 the agent gets against the server's own reference.
* **OUTCOME** — score, levels completed, final state. Reported always, steered on never.
  The day one of these moves is the day the project has a result; until then they are
  context, and optimising them directly means optimising a constant.
* **COST** — wall time, model calls, tokens, time asleep on the rate limit. A change that
  improves steering metrics by tripling the bill is a trade, not a win, and the trade has
  to be visible in the same table.

The failure this suite was built to catch, and what actually catches it — measured, not
assumed, by re-analysing the four committed recordings with the metrics below
(`scripts/analyze_run.py`, all four re-run 2026-07-22):

| metric                | SDK random | our random | our random 400 | **our LLM** |
|-----------------------|-----------:|-----------:|---------------:|------------:|
| illegal-action rate   |      47.5% |         0% |             0% |          0% |
| no-change rate        |      47.5% |         0% |          0.25% |          0% |
| revisit rate          |        46% |         0% |             6% |      **0%** |
| longest repeat streak |          2 |          4 |              6 |      **41** |
| favourite-action share|        20% |        27% |            25% |      **70%** |

**Two of these metrics are blind to the failure and one of them is the one this module was
first written to add.** `revisit_rate` reads 0% on the run that pressed one button 41 times:
all 80 screens were distinct. Digging into why (see study note 08) shows a two-cell marker
at rows 61-62 stepping one column per press — 42, 43, 44 … 54 — so every screen really was
new, the loop's `cells_changed` was never 0, and both "nothing changed" and "we have been
here before" stayed silent through the entire failure.

The lesson is kept rather than tidied away, because it is the honest version of what evals
are for: **a metric invented from a story about a failure is a guess until it is run against
the failure.** `revisit_rate` survives — it is the metric that separates the SDK baseline's
46% from our loop's 0% — but it is not the one that sees a stuck agent. The two that do are
`longest_repeat_streak` and `top_action_share`, by a factor of ten and of three.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from typing import Any

# --------------------------------------------------------------------------- #
# The games, and the split we are allowed to iterate on
# --------------------------------------------------------------------------- #
# Read from GET /api/games on 2026-07-22. Frozen here rather than fetched at import time
# on purpose: an eval suite whose membership depends on what the server felt like listing
# this morning is an eval suite whose numbers cannot be compared across weeks.
# `scripts/run_evals.py --check-games` re-reads the live list and reports any drift.
GAMES_SOURCE = "GET https://three.arcprize.org/api/games, read 2026-07-22"
GAMES: tuple[str, ...] = (
    "ar25-0c556536",
    "bp35-0a0ad940",
    "cd82-fb555c5d",
    "cn04-2fe56bfb",
    "dc22-fdcac232",
    "ft09-0d8bbf25",
    "g50t-5849a774",
    "ka59-38d34dbb",
    "lf52-271a04aa",
    "lp85-305b61c3",
    "ls20-9607627b",
    "m0r0-492f87ba",
    "r11l-495a7899",
    "re86-8af5384d",
    "s5i5-18d95033",
    "sb26-7fbdac44",
    "sc25-635fd71a",
    "sk48-d8078629",
    "sp80-589a99af",
    "su15-1944f8ab",
    "tn36-ef4dde99",
    "tr87-cd924810",
    "tu93-0768757b",
    "vc33-5430563c",
    "wa30-ee6fef47",
)

# `ls20` is pinned to the dev set, and that is a confession rather than a choice: every
# baseline number in this repository was measured on it, so it is already contaminated by
# our own looking. Putting it in the held-out set would let us report a game we had
# already studied and call it held out.
PINNED_DEV: tuple[str, ...] = ("ls20-9607627b",)

DEV_SIZE = 4
HELDOUT_SIZE = 6
# Any fixed seed would do; the requirement is that it is fixed, published, and was chosen
# before the numbers were seen. Today's date, picked in advance of the first suite run.
SPLIT_SEED = 20260722


def split(
    games: tuple[str, ...] = GAMES,
    dev_size: int = DEV_SIZE,
    heldout_size: int = HELDOUT_SIZE,
    seed: int = SPLIT_SEED,
) -> dict[str, list[str]]:
    """Deterministic dev / held-out / reserve split.

    Sorted first, so the server's response order cannot change the split; then shuffled
    with a published seed, so the membership is arbitrary rather than chosen. Reproduce it
    with the same three numbers and you get the same three lists.

    The reserve is not spare capacity — it is the games we can afford to leave untouched.
    A suite is limited by the free tier, not by how many games exist (`harness/budget.py`),
    and pretending otherwise would mean a suite we cannot actually run.
    """
    pool = sorted(set(games) - set(PINNED_DEV))
    random.Random(seed).shuffle(pool)
    dev = list(PINNED_DEV) + pool[: max(0, dev_size - len(PINNED_DEV))]
    rest = pool[max(0, dev_size - len(PINNED_DEV)) :]
    return {"dev": dev, "heldout": rest[:heldout_size], "reserve": rest[heldout_size:]}


SUITES = split()


class HeldOutViolation(RuntimeError):
    """Someone tried to iterate on the reported set. Rule 5 of CLAUDE.md, in code."""


# --------------------------------------------------------------------------- #
# One game's numbers
# --------------------------------------------------------------------------- #
STEERING = (
    "illegal_action_rate",
    "no_change_rate",
    "revisit_rate",
    "top_action_share_excess",
    "top_action_share",
    "longest_repeat_streak",
    "distinct_actions",
    "distinct_targets",
    "game_overs",
    "level1_ratio",
    # How often the repetition guard overruled the model. Listed here so it prints in the
    # comparison, and in neither direction set below so it prints without a verdict: it is
    # the *size* of an intervention, not a measure of how well the agent played. A change
    # whose intervention rate is invisible is a change of unknown magnitude.
    "repeat_blocks",
    # The same treatment for the theory-of-the-game arm: how often the agent changed its
    # stated theory, and how often the prediction it attached to that theory survived
    # contact with the game. Both are the size and the bite of the intervention. Neither
    # gets a direction — a high hit rate can mean a sharp theory or a safe one, and we do
    # not know which without reading the traces (`harness/hypothesis.py`).
    "hypothesis_changes",
    "prediction_hit_rate",
)
OUTCOME = ("final_score", "levels_completed", "final_state", "level1_completed")
COST = (
    "wall_seconds",
    "llm_calls",
    "llm_input_tokens",
    "seconds_waited",
    "llm_retries",
    "usable_reply_rate",
    # Format compliance, next to the other reply-quality number and for the same reason: a
    # prompt that asks for three lines and gets two has not been obeyed, and that is a cost
    # of the change rather than a property of the agent's play.
    "hypothesis_stated_rate",
)

# Which way is good. Anything not listed is reported without a verdict, because inventing
# a direction for a metric we do not understand yet is how a dashboard starts lying.
LOWER_IS_BETTER = {
    "illegal_action_rate",
    "no_change_rate",
    "revisit_rate",
    "top_action_share_excess",
    "longest_repeat_streak",
    "game_overs",
    "level1_ratio",
    "wall_seconds",
    "llm_calls",
    "llm_input_tokens",
    "seconds_waited",
}
HIGHER_IS_BETTER = {
    "distinct_actions",
    "distinct_targets",
    "final_score",
    "levels_completed",
    "usable_reply_rate",
}


@dataclass
class Metrics:
    """One episode, measured. Counts are stored; rates are derived.

    Counts rather than rates, because the aggregate over a suite has to be **pooled**
    (total illegal ÷ total actions) and not an average of per-game percentages. Averaging
    percentages over games of unequal length quietly weights a game that died after 12
    actions the same as one that ran the full 80.
    """

    game_id: str
    policy: str
    actions: int
    illegal_actions: int
    no_change_actions: int
    unique_screens: int
    top_action_count: int
    longest_repeat_streak: int
    distinct_actions: int
    game_overs: int
    resets: int
    final_score: int
    final_state: str
    wall_seconds: float
    # Which attempt at this game produced these numbers, 1-based. 1 for every arm that plays
    # each game once (all of them before the progress-signal experiment), so old artifacts
    # read back as attempt 1. The progress signal only acts from attempt 2 on, so the
    # comparison that judges it slices to a single attempt — see `scripts/compare_evals.py
    # --attempt`.
    attempt: int = 1
    # The typical number of buttons the game offered. The denominator that makes every
    # repetition number readable — see `top_action_share_excess`.
    median_legal_options: int = 1
    # Distinct full action labels, coordinates included. On a click-only game like
    # `tn36-ef4dde99` every action is `ACTION6`, so `distinct_actions` is 1 no matter how
    # widely the agent clicks, and only this number tells exploring from stabbing.
    distinct_targets: int = 0
    actions_to_first_score: int | None = None
    # From the server's own scorecard close, never from us: `level_actions[0]` against
    # `level_baseline_actions[0]`. See `from_scorecard`.
    level1_actions: int | None = None
    level1_reference: int | None = None
    level1_completed: bool | None = None
    levels_completed: int | None = None
    level_count: int | None = None
    llm_calls: int | None = None
    llm_input_tokens: int | None = None
    parse_failures: int | None = None
    client_errors: int | None = None
    seconds_waited: float | None = None
    # 429s that were retried and then succeeded. Not failures — but not free either, and
    # invisible in every other number, so they are counted rather than shrugged off.
    llm_retries: int | None = None
    # Times the repetition guard refused the model's choice (`harness/policies.py`).
    repeat_blocks: int | None = None
    # The theory-of-the-game arm (`harness/hypothesis.py`). All None when it was off, so an
    # arm from before it existed reports "-" rather than a zero it never measured.
    hypotheses_stated: int | None = None
    hypothesis_changes: int | None = None
    predictions_checked: int | None = None
    predictions_wrong: int | None = None
    error: str | None = None

    # -- derived ----------------------------------------------------------- #
    def _rate(self, n: int) -> float:
        return n / self.actions if self.actions else 0.0

    @property
    def illegal_action_rate(self) -> float:
        """Share of decisions the loop had to refuse. The Phase B guard drove this to 0."""
        return self._rate(self.illegal_actions)

    @property
    def no_change_rate(self) -> float:
        """Share of actions after which the screen was byte-identical."""
        return self._rate(self.no_change_actions)

    @property
    def revisit_rate(self) -> float:
        """Share of actions landing on a screen already seen this episode.

        Measured 2026-07-22: 46% for the SDK baseline (its illegal actions bounced it back
        to the same screen), 0% for our loop. So it does measure something real.

        It does **not** measure stuckness, which is what it was added for: the LLM run that
        pressed one button 41 times scored 0% here, because a marker on the bottom row
        advanced one column per press and made every screen technically new. Kept, with its
        limits stated, rather than quietly dropped.
        """
        return 1.0 - self._rate(self.unique_screens)

    @property
    def top_action_share(self) -> float:
        """How hard the agent leant on its favourite button. Random on 4 options ≈ 0.25.

        With `longest_repeat_streak`, the pair that actually caught the stuck LLM: 70% and
        41 against 20-27% and 2-6 for every random arm — but only because those numbers all
        came from `ls20`. Across games it is not comparable; use the excess below.
        """
        return self._rate(self.top_action_count)

    @property
    def top_action_share_excess(self) -> float:
        """`top_action_share` minus what a uniform random chooser would score on this game.

        The number that survives being compared across games, and it exists because the
        raw share does not. Measured on 2026-07-22, our random baseline scored a 99%
        favourite-action share and a 61-action identical streak on `tn36-ef4dde99` — which
        looks like the worst stuck-loop in the project until you see that the game offers
        exactly one legal action in all 81 frames. Its excess is 0: perfectly normal play.

        Positive means more repetitive than chance. Zero means indistinguishable from a
        coin flip. Negative means it spread out more evenly than random, which is possible
        and is not automatically good.
        """
        return self.top_action_share - (1 / max(1, self.median_legal_options))

    @property
    def level1_ratio(self) -> float | None:
        """Actions spent in level 1 ÷ the server's reference solution for level 1.

        1.0 means the agent matched the reference. Below 1 with `level1_completed` false
        means it simply has not spent the actions yet, so the number is only meaningful
        alongside that flag — which is why they are reported together and never averaged
        into one figure.
        """
        if not self.level1_reference:
            return None
        return (self.level1_actions or 0) / self.level1_reference

    @property
    def usable_reply_rate(self) -> float | None:
        """Share of model calls that produced an action we could actually send."""
        if not self.llm_calls:
            return None
        bad = (self.parse_failures or 0) + (self.client_errors or 0)
        return (self.llm_calls - bad) / self.llm_calls

    @property
    def prediction_hit_rate(self) -> float | None:
        """Share of checkable predictions that matched what the screen actually did.

        The denominator is `predictions_checked`, not the number of actions: a turn where
        the agent stated no prediction is not a turn it got wrong. Counting silence as a
        miss would let the metric improve by making the model less talkative.
        """
        if not self.predictions_checked:
            return None
        return (self.predictions_checked - (self.predictions_wrong or 0)) / self.predictions_checked

    @property
    def hypothesis_stated_rate(self) -> float | None:
        """Share of model calls that came back with the theory line the prompt asked for."""
        if not self.llm_calls or self.hypotheses_stated is None:
            return None
        return self.hypotheses_stated / self.llm_calls

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for name in (
            "illegal_action_rate",
            "no_change_rate",
            "revisit_rate",
            "top_action_share",
            "top_action_share_excess",
            "level1_ratio",
            "usable_reply_rate",
            "prediction_hit_rate",
            "hypothesis_stated_rate",
        ):
            v = getattr(self, name)
            d[name] = round(v, 4) if isinstance(v, float) else v
        return d


def measure(result: Any, llm: dict[str, Any] | None = None) -> Metrics:
    """Turn an `EpisodeResult` into `Metrics`.

    Takes the result rather than the recording so it works identically for a mock run and
    a live one — the same reason `scripts/analyze_run.py` reads our runs and the SDK's
    baseline with one reader.
    """
    steps = list(result.steps)
    kinds = [s.action.split("(")[0] for s in steps]

    counts: dict[str, int] = {}
    for k in kinds:
        counts[k] = counts.get(k, 0) + 1

    options = sorted(getattr(s, "legal_options", 0) for s in steps)
    median_options = options[len(options) // 2] if options else 1

    streak = best = 0
    previous = None
    for k in kinds:
        streak = streak + 1 if k == previous else 1
        best = max(best, streak)
        previous = k

    # Screens the loop hashed. Steps recorded before `screen_hash` existed have "", which
    # would collapse to one "unique" screen and read as a 99% revisit rate — so an episode
    # without hashes reports its screen count as the action count (revisit_rate 0) and the
    # metric is simply absent rather than fabricated.
    hashes = [s.screen_hash for s in steps if getattr(s, "screen_hash", "")]
    unique = len(set(hashes)) if hashes else len(steps)

    first_score = next((i + 1 for i, s in enumerate(steps) if s.score_delta > 0), None)

    return Metrics(
        game_id=result.game_id,
        policy=result.policy,
        actions=result.actions_taken,
        illegal_actions=result.rejected_actions,
        no_change_actions=result.no_change_actions,
        unique_screens=unique,
        top_action_count=max(counts.values(), default=0),
        longest_repeat_streak=best,
        distinct_actions=len(counts),
        game_overs=sum(1 for s in steps if s.state == "GAME_OVER"),
        resets=sum(1 for k in kinds if k == "RESET"),
        final_score=result.final_score,
        final_state=result.final_state,
        wall_seconds=result.wall_seconds,
        median_legal_options=median_options,
        distinct_targets=len({s.action for s in steps}),
        actions_to_first_score=first_score,
        llm_calls=(llm or {}).get("calls"),
        llm_input_tokens=(llm or {}).get("input_tokens"),
        parse_failures=(llm or {}).get("parse_failures"),
        client_errors=(llm or {}).get("client_errors"),
        seconds_waited=(llm or {}).get("seconds_waited"),
        llm_retries=(llm or {}).get("retries"),
        repeat_blocks=(llm or {}).get("repeat_blocks"),
        hypotheses_stated=(llm or {}).get("hypotheses_stated"),
        hypothesis_changes=(llm or {}).get("hypothesis_changes"),
        predictions_checked=(llm or {}).get("predictions_checked"),
        predictions_wrong=(llm or {}).get("predictions_wrong"),
    )


def from_scorecard(metrics: Metrics, closed: dict[str, Any] | None) -> Metrics:
    """Fill in the level fields from the server's scorecard-close response.

    The level data is the server's, not ours, and it is the only place the *reference*
    solution length appears — `level_baseline_actions`, measured on 2026-07-22 for `ls20`
    as `[22, 123, 73, 84, 96, 192, 186]`. The SDK's `Scorecard` model drops this entire
    structure (see `harness/arc_env.close_scorecard`), which is why we read raw JSON.

    Multiple `runs` appear when a game is played more than once under one card; we sum
    their per-level action counts, because our loop resets and continues within an episode.
    """
    if not closed:
        return metrics
    envs = [e for e in closed.get("environments", []) if e.get("id") == metrics.game_id]
    if not envs:
        return metrics
    env = envs[0]
    runs = env.get("runs") or []

    per_level: list[int] = []
    reference: list[int] = []
    for run in runs:
        for i, n in enumerate(run.get("level_actions") or []):
            while len(per_level) <= i:
                per_level.append(0)
            per_level[i] += n
        reference = run.get("level_baseline_actions") or reference

    metrics.level1_actions = per_level[0] if per_level else None
    metrics.level1_reference = reference[0] if reference else None
    metrics.levels_completed = env.get("levels_completed")
    metrics.level_count = env.get("level_count")
    metrics.level1_completed = bool((metrics.levels_completed or 0) >= 1)
    return metrics


def _pooled_rate(hits: int, total: int, measured: bool = True) -> float | None:
    """A rate over the whole suite, or None when there is nothing to divide by.

    None and 0.0 are different answers and the difference matters: None means the arm never
    measured this, 0.0 means it measured it and the answer was none. A zero denominator has
    to come back as None, or an arm that stated no predictions at all would report a perfect
    (or a catastrophic) hit rate out of thin air.
    """
    if not measured or total <= 0:
        return None
    return round(hits / total, 4)


# --------------------------------------------------------------------------- #
# A whole arm of the experiment
# --------------------------------------------------------------------------- #
@dataclass
class Arm:
    """One configuration, run over one suite. The unit a change is judged in."""

    name: str
    suite: str
    games: list[str] = field(default_factory=list)
    episodes: list[Metrics] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)

    def aggregate(self) -> dict[str, Any]:
        """Pooled over episodes. Rates are totals ÷ totals, never means of percentages."""
        eps = [e for e in self.episodes if e.error is None]
        actions = sum(e.actions for e in eps)

        def pooled(attr: str) -> float:
            return sum(getattr(e, attr) for e in eps) / actions if actions else 0.0

        ratios = [e.level1_ratio for e in eps if e.level1_ratio is not None]
        usable = [e.usable_reply_rate for e in eps if e.usable_reply_rate is not None]
        return {
            "episodes": len(eps),
            "failed_episodes": len(self.episodes) - len(eps),
            "actions": actions,
            # steering
            "illegal_action_rate": round(pooled("illegal_actions"), 4),
            "no_change_rate": round(pooled("no_change_actions"), 4),
            "revisit_rate": round(1.0 - pooled("unique_screens"), 4) if actions else 0.0,
            "top_action_share": round(pooled("top_action_count"), 4),
            # Averaged over episodes rather than pooled, because each game has its own
            # random-play baseline to subtract; pooling would compare a click-only game's
            # counts against a seven-button game's denominator.
            "top_action_share_excess": round(
                sum(e.top_action_share_excess for e in eps) / len(eps), 4
            ) if eps else 0.0,
            # Max over episodes, but only those where the agent had a choice. Same
            # confound as `top_action_share`, one level up: `tn36-ef4dde99` offers one
            # action, so its streak is always the full episode length and a plain max over
            # games reports 30 for every arm including a random one. A metric that reads
            # the same for every arm cannot referee anything.
            "longest_repeat_streak": max(
                (e.longest_repeat_streak for e in eps if e.median_legal_options > 1),
                default=0,
            ),
            "distinct_actions": round(
                sum(e.distinct_actions for e in eps) / len(eps), 2
            ) if eps else 0,
            "distinct_targets": round(
                sum(e.distinct_targets for e in eps) / len(eps), 2
            ) if eps else 0,
            "game_overs": sum(e.game_overs for e in eps),
            "level1_ratio": round(sum(ratios) / len(ratios), 4) if ratios else None,
            # Summed, not pooled: it is a count of interventions, and the arms it is
            # compared across run the same number of actions.
            #
            # Deliberately NOT `or None` the way the cost fields below are. A measured zero
            # here is the finding — it means the model obeyed the ban in the prompt every
            # single time and the code never had to overrule it — and collapsing that to
            # "not measured" would hide the most interesting number in the experiment.
            "repeat_blocks": (
                sum(e.repeat_blocks or 0 for e in eps)
                if any(e.repeat_blocks is not None for e in eps)
                else None
            ),
            # Same convention as `repeat_blocks`: a measured zero is a finding and prints as
            # 0, while None means the arm never had the feature at all. Rates are pooled
            # over the suite (totals over totals), never averaged over games.
            "hypothesis_changes": (
                sum(e.hypothesis_changes or 0 for e in eps)
                if any(e.hypothesis_changes is not None for e in eps)
                else None
            ),
            "prediction_hit_rate": _pooled_rate(
                sum(
                    (e.predictions_checked or 0) - (e.predictions_wrong or 0)
                    for e in eps
                ),
                sum(e.predictions_checked or 0 for e in eps),
            ),
            "hypothesis_stated_rate": _pooled_rate(
                sum(e.hypotheses_stated or 0 for e in eps),
                sum(e.llm_calls or 0 for e in eps),
                measured=any(e.hypotheses_stated is not None for e in eps),
            ),
            # outcome — reported, never steered on
            "final_score": sum(e.final_score for e in eps),
            "levels_completed": sum(e.levels_completed or 0 for e in eps),
            "wins": sum(1 for e in eps if e.final_state == "WIN"),
            # cost
            "wall_seconds": round(sum(e.wall_seconds for e in eps), 1),
            "llm_calls": sum(e.llm_calls or 0 for e in eps) or None,
            "llm_input_tokens": sum(e.llm_input_tokens or 0 for e in eps) or None,
            "seconds_waited": round(sum(e.seconds_waited or 0 for e in eps), 1) or None,
            "llm_retries": sum(e.llm_retries or 0 for e in eps) or None,
            "usable_reply_rate": round(sum(usable) / len(usable), 4) if usable else None,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm": self.name,
            "suite": self.suite,
            "games": self.games,
            "config": self.config,
            "aggregate": self.aggregate(),
            "episodes": [e.to_dict() for e in self.episodes],
        }


def direction(name: str, before: Any, after: Any) -> str:
    """'better' / 'worse' / 'same' / '' — empty when we have not claimed a direction."""
    if before is None or after is None or isinstance(before, str) or isinstance(after, str):
        return ""
    if after == before:
        return "same"
    improved = after < before if name in LOWER_IS_BETTER else after > before
    if name not in LOWER_IS_BETTER and name not in HIGHER_IS_BETTER:
        return ""
    return "better" if improved else "worse"


def compare(before: Arm, after: Arm) -> list[dict[str, Any]]:
    """Row per metric, tagged with which of the three kinds it is.

    The `kind` column is not decoration. It is the rule from CLAUDE.md §5 made visible: a
    change is kept or reverted on the *steering* rows, and the *outcome* rows are there so
    that a steering win which quietly destroys the score cannot hide.
    """
    a, b = before.aggregate(), after.aggregate()
    rows = []
    for kind, names in (("steering", STEERING), ("outcome", OUTCOME), ("cost", COST)):
        for name in names:
            if name not in a and name not in b:
                continue
            rows.append(
                {
                    "metric": name,
                    "kind": kind,
                    "before": a.get(name),
                    "after": b.get(name),
                    "direction": (
                        direction(name, a.get(name), b.get(name)) if kind != "outcome" else ""
                    ),
                }
            )
    return rows


__all__ = [
    "Arm",
    "COST",
    "GAMES",
    "GAMES_SOURCE",
    "HeldOutViolation",
    "HIGHER_IS_BETTER",
    "LOWER_IS_BETTER",
    "Metrics",
    "OUTCOME",
    "PINNED_DEV",
    "SPLIT_SEED",
    "STEERING",
    "SUITES",
    "compare",
    "direction",
    "from_scorecard",
    "measure",
    "split",
]
