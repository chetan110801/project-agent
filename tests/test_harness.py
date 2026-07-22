"""Tests for the offline harness. Standard-library `unittest` — no extra install.

Run:  py -m unittest discover -s tests -v
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from arc_agi_3._structs import GameAction, GameState  # noqa: E402

from harness.actions import Action  # noqa: E402
from harness import evals  # noqa: E402
from harness.frames import (  # noqa: E402
    diff_grids,
    find_blobs,
    grid_fingerprint,
    grid_shape,
    main_grid,
    render_diff,
    render_grid,
    render_history,
    render_objects,
)
from harness.budget import LIMITS, BudgetExhausted, Limits, RateLimiter  # noqa: E402
from harness.llm import ScriptedClient  # noqa: E402
from harness.loop import run_episode  # noqa: E402
from harness.mock_game import AGENT, MockGame, WIN_SCORE  # noqa: E402
from harness.policies import (  # noqa: E402
    LLMPolicy,
    RandomPolicy,
    legal_actions,
    parse_action,
)
from harness.tokens import measure  # noqa: E402
from harness.trace import Tracer  # noqa: E402
from scripts.analyze_run import load as load_recording  # noqa: E402
from scripts.run_agent import RecordingEnv, resolve_game  # noqa: E402
from scripts.run_evals import main as run_evals_main  # noqa: E402
from scripts import compare_evals  # noqa: E402


class TestAction(unittest.TestCase):
    def test_simple_action_takes_no_coordinates(self):
        with self.assertRaises(ValueError):
            Action(GameAction.ACTION1, x=1, y=1)

    def test_complex_action_requires_coordinates(self):
        with self.assertRaises(ValueError):
            Action(GameAction.ACTION6)

    def test_coordinates_are_capped_at_63(self):
        Action(GameAction.ACTION6, x=63, y=0)  # ok
        with self.assertRaises(ValueError):
            Action(GameAction.ACTION6, x=64, y=0)
        with self.assertRaises(ValueError):
            Action(GameAction.ACTION6, x=0, y=-1)

    def test_label_and_payload(self):
        a = Action(GameAction.ACTION6, x=12, y=40)
        self.assertEqual(a.label(), "ACTION6(x=12,y=40)")
        self.assertEqual(a.payload(), {"x": 12, "y": 40})
        self.assertEqual(Action(GameAction.ACTION1).payload(), {})

    def test_action_is_immutable(self):
        """The whole reason this type exists: no shared mutable state."""
        a = Action(GameAction.ACTION6, x=1, y=2)
        with self.assertRaises(Exception):
            a.x = 5  # type: ignore[misc]


class TestFrames(unittest.TestCase):
    def setUp(self):
        self.grid = [
            [0, 0, 0, 0],
            [0, 4, 4, 0],
            [0, 4, 4, 0],
            [0, 0, 0, 3],
        ]

    def test_grid_shape(self):
        self.assertEqual(grid_shape(self.grid), (4, 4))
        self.assertEqual(grid_shape([]), (0, 0))
        with self.assertRaises(ValueError):
            grid_shape([[0, 0], [0]])

    def test_render_grid_packed_is_smaller_than_spaced(self):
        packed = render_grid(self.grid)
        spaced = render_grid(self.grid, sep=" ", cell="dec")
        self.assertEqual(packed.splitlines()[1], "0440")
        self.assertEqual(spaced.splitlines()[1], "0 4 4 0")
        self.assertLess(len(packed), len(spaced))

    def test_hex_keeps_one_character_per_cell_above_nine(self):
        """Real frames reach 12, so this is the case that matters."""
        self.assertEqual(render_grid([[10, 12], [15, 0]]), "ac\nf0")

    def test_packed_decimal_refuses_ambiguous_values(self):
        with self.assertRaises(ValueError):
            render_grid([[10, 0], [0, 0]], cell="dec")

    def test_hex_refuses_values_it_cannot_represent(self):
        with self.assertRaises(ValueError):
            render_grid([[16, 0], [0, 0]])

    def test_find_blobs(self):
        blobs = find_blobs(self.grid)
        self.assertEqual(len(blobs), 2)
        big = blobs[0]
        self.assertEqual((big.value, big.cells), (4, 4))
        self.assertTrue(big.is_rect)
        self.assertEqual((big.top, big.left, big.bottom, big.right), (1, 1, 2, 2))
        self.assertEqual(blobs[1].cells, 1)

    def test_find_blobs_does_not_merge_different_colours(self):
        blobs = find_blobs([[4, 3], [0, 0]])
        self.assertEqual(len(blobs), 2)

    def test_render_objects_is_much_smaller_than_the_raw_grid(self):
        big = [[0] * 64 for _ in range(64)]
        for r in range(10, 13):
            for c in range(10, 13):
                big[r][c] = 4
        self.assertLess(len(render_objects(big)), len(render_grid(big)) / 10)

    def test_render_objects_truncates_instead_of_exploding(self):
        noisy = [[(r + c) % 2 * 5 for c in range(20)] for r in range(20)]
        out = render_objects(noisy, max_blobs=5)
        self.assertIn("truncated", out)

    def test_diff_detects_nothing_changed(self):
        self.assertTrue(diff_grids(self.grid, self.grid).is_empty)
        self.assertEqual(render_diff(self.grid, self.grid), "nothing changed")

    def test_diff_lists_changed_cells(self):
        after = [row[:] for row in self.grid]
        after[0][0] = 7
        d = diff_grids(self.grid, after)
        self.assertEqual(d.count, 1)
        self.assertEqual(d.changed[0], (0, 0, 0, 7))
        self.assertIn("(r0, c0) 0->7", render_diff(self.grid, after))

    def test_diff_handles_shape_change(self):
        d = diff_grids(self.grid, [[0]])
        self.assertFalse(d.same_shape)
        self.assertEqual(render_diff(self.grid, [[0]]), "grid shape changed")

    def test_diff_summarises_when_too_many_cells_changed(self):
        after = [[9] * 4 for _ in range(4)]
        self.assertIn("too many to list", render_diff(self.grid, after, max_cells=3))


class TestTokens(unittest.TestCase):
    def test_measure_reports_exact_characters(self):
        r = measure("x", "abc\ndef")
        self.assertEqual(r.chars, 7)
        self.assertEqual(r.lines, 2)

    def test_token_count_always_names_its_tokenizer(self):
        r = measure("x", "hello world")
        # tokens and tokenizer are present together, or absent together — never a
        # number without provenance.
        self.assertEqual(r.tokens is None, r.tokenizer is None)
        if r.tokens is not None:
            self.assertGreater(r.tokens, 0)
            self.assertTrue(r.tokenizer.startswith("tiktoken/"))


class TestMockGame(unittest.TestCase):
    def test_reset_puts_the_game_in_play(self):
        g = MockGame()
        f = g.reset()
        self.assertIs(f.state, GameState.NOT_FINISHED)
        self.assertEqual(f.score, 0)
        self.assertEqual(grid_shape(main_grid(f)), (16, 16))
        self.assertEqual(main_grid(f)[0][0], AGENT)

    def test_movement_changes_the_grid(self):
        g = MockGame()
        before = main_grid(g.reset())
        after = main_grid(g.step(Action(GameAction.ACTION4)))  # right
        self.assertEqual(diff_grids(before, after).count, 2)  # left cell, arrived cell

    def test_dead_actions_change_nothing(self):
        g = MockGame()
        before = main_grid(g.reset())
        for dead in (GameAction.ACTION5, GameAction.ACTION7):
            after = main_grid(g.step(Action(dead)))
            self.assertTrue(diff_grids(before, after).is_empty, dead.name)

    def test_paint_changes_the_screen_but_not_the_score(self):
        g = MockGame()
        before = g.reset()
        after = g.step(Action(GameAction.ACTION6, x=7, y=7))
        self.assertGreater(diff_grids(main_grid(before), main_grid(after)).count, 0)
        self.assertEqual(after.score, before.score)

    def test_edges_clip_instead_of_wrapping(self):
        g = MockGame()
        g.reset()
        for _ in range(5):
            g.step(Action(GameAction.ACTION1))  # up, from row 0
        self.assertEqual(g.agent, (0, 0))

    def test_reaching_the_target_scores(self):
        g = MockGame()
        g.reset()
        for _ in range(2):
            g.step(Action(GameAction.ACTION2))  # down to row 2
        for _ in range(5):
            f = g.step(Action(GameAction.ACTION4))  # right to col 5
        self.assertEqual(f.score, 1)

    def test_deterministic(self):
        seq = [Action(GameAction.ACTION4)] * 3 + [Action(GameAction.ACTION2)] * 2
        runs = []
        for _ in range(2):
            g = MockGame()
            g.reset()
            for a in seq:
                f = g.step(a)
            runs.append((f.score, main_grid(f)))
        self.assertEqual(runs[0], runs[1])


class _Beeline:
    """Test-only policy that cheats: it can see the game's internals and walks to the
    target. Used to prove the loop can reach a WIN, not to prove anything about agents."""

    name = "beeline"

    def __init__(self, game: MockGame) -> None:
        self.game = game

    def choose(self, frames, latest) -> Action:
        target = self.game.target
        if target is None:
            return Action(GameAction.ACTION5)
        (ar, ac), (tr, tc) = self.game.agent, target
        if ar < tr:
            return Action(GameAction.ACTION2)
        if ar > tr:
            return Action(GameAction.ACTION1)
        if ac < tc:
            return Action(GameAction.ACTION4)
        return Action(GameAction.ACTION3)


class _AlwaysDead:
    name = "always-dead"

    def choose(self, frames, latest) -> Action:
        return Action(GameAction.ACTION5)


class _Illegal:
    name = "illegal"

    def choose(self, frames, latest) -> Action:
        return Action(GameAction.ACTION6, x=1, y=1)


class TestLoop(unittest.TestCase):
    def test_random_baseline_runs_to_the_action_cap(self):
        g = MockGame()
        r = run_episode(g, RandomPolicy(seed=1), max_actions=30)
        self.assertEqual(r.actions_taken, 30)
        self.assertEqual(r.stopped_because, "max_actions")
        self.assertEqual(r.rejected_actions, 0)

    def test_random_baseline_is_reproducible_from_its_seed(self):
        a = run_episode(MockGame(), RandomPolicy(seed=7), max_actions=40)
        b = run_episode(MockGame(), RandomPolicy(seed=7), max_actions=40)
        self.assertEqual([s.action for s in a.steps], [s.action for s in b.steps])
        self.assertEqual(a.final_score, b.final_score)

    def test_loop_stops_on_a_win(self):
        g = MockGame()
        r = run_episode(g, _Beeline(g), max_actions=80)
        self.assertEqual(r.final_state, GameState.WIN.value)
        self.assertEqual(r.final_score, WIN_SCORE)
        self.assertEqual(r.stopped_because, "win")
        self.assertLess(r.actions_taken, 80)

    def test_stuck_detection_stops_a_flailing_agent(self):
        r = run_episode(MockGame(), _AlwaysDead(), max_actions=80, stuck_limit=5)
        self.assertEqual(r.stopped_because, "stuck")
        self.assertEqual(r.actions_taken, 5)
        self.assertEqual(r.dead_action_rate, 1.0)

    def test_illegal_actions_are_rejected_not_sent(self):
        g = MockGame(available=[GameAction.RESET, GameAction.ACTION1])
        r = run_episode(g, _Illegal(), max_actions=4)
        self.assertEqual(r.rejected_actions, 4)
        self.assertTrue(all(not s.accepted for s in r.steps))
        self.assertTrue(all(s.action == "RESET" for s in r.steps))

    def test_dead_action_rate_is_counted(self):
        g = MockGame()
        r = run_episode(g, _AlwaysDead(), max_actions=10)
        self.assertEqual(r.no_change_actions, 10)


class TestTracer(unittest.TestCase):
    def test_trace_is_written_and_reads_back(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "run.jsonl"
            g = MockGame()
            with Tracer(path, run_id="test-run") as t:
                r = run_episode(g, RandomPolicy(seed=3), max_actions=12, tracer=t)
            records = Tracer.read(path)
            kinds = [rec["kind"] for rec in records]
            self.assertEqual(kinds[0], "episode_start")
            self.assertEqual(kinds[-1], "episode_end")
            self.assertEqual(kinds.count("step"), r.actions_taken)
            self.assertTrue(all(rec["run_id"] == "test-run" for rec in records))
            self.assertIn("latency_ms", records[1])

    def test_bad_lines_are_skipped_not_fatal(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "broken.jsonl"
            path.write_text('{"kind": "ok"}\nnot json\n\n{"kind": "ok2"}\n', encoding="utf-8")
            self.assertEqual([r["kind"] for r in Tracer.read(path)], ["ok", "ok2"])


class TestLegalActions(unittest.TestCase):
    def test_reset_is_legal_even_when_the_frame_omits_it(self):
        """Real frames advertise `[1, 2, 3, 4]` and never list RESET, but RESET is what
        the loop falls back to — so without this it would reject its own fallback."""
        g = MockGame(available=[GameAction.ACTION1])
        frame = g.reset()
        self.assertNotIn(GameAction.RESET, frame.available_actions)
        self.assertIn(GameAction.RESET, legal_actions(frame))

    def test_empty_available_actions_falls_back_to_all_eight(self):
        g = MockGame(available=[])
        self.assertEqual(len(legal_actions(g.reset())), len(list(GameAction)))


class _FakeGameList:
    """Stands in for ArcEnv in resolve_game — only list_games is consulted."""

    def __init__(self, games: list[str]) -> None:
        self._games = games

    def list_games(self) -> list[str]:
        return self._games


class TestResolveGame(unittest.TestCase):
    GAMES = ["ls20-9607627b", "lp85-305b61c3", "ls21-aaaaaaaa"]

    def test_prefix_resolves_to_the_versioned_id(self):
        self.assertEqual(resolve_game(_FakeGameList(self.GAMES), "ls20"), "ls20-9607627b")

    def test_exact_id_passes_through(self):
        self.assertEqual(
            resolve_game(_FakeGameList(self.GAMES), "ls20-9607627b"), "ls20-9607627b"
        )

    def test_ambiguous_and_unknown_prefixes_raise(self):
        with self.assertRaises(Exception):
            resolve_game(_FakeGameList(self.GAMES), "ls")  # matches ls20 and ls21
        with self.assertRaises(Exception):
            resolve_game(_FakeGameList(self.GAMES), "zz99")


class TestRecordingEnv(unittest.TestCase):
    def test_recording_round_trips_through_the_analyser(self):
        """The point of matching the SDK's format: one analyser reads both our runs and
        the SDK baseline, so a before/after comparison can't be an artefact of two
        different readers."""
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "x.recording.jsonl"
            env = RecordingEnv(MockGame(), path)
            result = run_episode(env, RandomPolicy(seed=2), max_actions=9)
            env.record_scorecard({"mock01": {"total_plays": 1, "actions": [9]}})
            env.close()

            frames, scorecard = load_recording(path)
            self.assertEqual(len(frames), result.actions_taken + 1)  # +1 for the reset
            self.assertEqual(scorecard, {"mock01": {"total_plays": 1, "actions": [9]}})
            self.assertTrue(all("action_input" in f for f in frames))

    def test_frames_survive_a_crash_mid_episode(self):
        class _Exploding(MockGame):
            def step(self, action):  # type: ignore[override]
                if self.steps >= 3:
                    raise RuntimeError("network died")
                return super().step(action)

        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "y.recording.jsonl"
            env = RecordingEnv(_Exploding(), path)
            with self.assertRaises(RuntimeError):
                run_episode(env, RandomPolicy(seed=4), max_actions=20)
            env.close()
            frames, _ = load_recording(path)
            self.assertEqual(len(frames), 4)  # reset + 3 steps, flushed as they happened

    def test_a_gz_path_compresses_on_close_and_still_reads_back(self):
        with tempfile.TemporaryDirectory() as d:
            asked = Path(d) / "z.recording.jsonl.gz"
            env = RecordingEnv(MockGame(), asked)
            self.assertEqual(env.path.suffix, ".jsonl")  # plain while playing
            run_episode(env, RandomPolicy(seed=2), max_actions=6)
            env.close()

            self.assertTrue(asked.exists())
            self.assertFalse((Path(d) / "z.recording.jsonl").exists())
            self.assertEqual(env.path, asked)
            frames, _ = load_recording(asked)
            self.assertEqual(len(frames), 7)

    def test_a_recording_is_readable_mid_run_which_is_why_it_is_not_gzipped_live(self):
        """The measured reason compression waits for close: a half-written gzip stream
        raises EOFError, and surviving a crash is what the format was chosen for."""
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "w.recording.jsonl.gz"
            env = RecordingEnv(MockGame(), path)
            run_episode(env, RandomPolicy(seed=2), max_actions=5)
            frames, _ = load_recording(env.path)  # NOT closed yet
            self.assertEqual(len(frames), 6)
            env.close()


class TestParseAction(unittest.TestCase):
    def test_plain_replies(self):
        self.assertEqual(parse_action("ACTION3").kind, GameAction.ACTION3)
        self.assertEqual(parse_action("action3\nbecause it moves left").kind, GameAction.ACTION3)

    def test_models_wrap_things_in_junk_and_we_cope(self):
        for text in (
            "```\nACTION2\n```",
            "Action: ACTION2 — moving down",
            "I'll press ACTION 2 now.",
            "**ACTION2**",
        ):
            with self.subTest(text=text):
                self.assertEqual(parse_action(text).kind, GameAction.ACTION2)

    def test_complex_action_coordinates(self):
        for text in ("ACTION6 x=12 y=40", "ACTION6 x: 12, y: 40", "ACTION6 (12, 40)"):
            with self.subTest(text=text):
                a = parse_action(text)
                self.assertEqual((a.kind, a.x, a.y), (GameAction.ACTION6, 12, 40))

    def test_out_of_range_coordinates_are_rejected_not_clamped(self):
        """A clamp would turn a wrong answer into a plausible one and hide it from evals."""
        self.assertIsNone(parse_action("ACTION6 x=99 y=99"))

    def test_nonsense_returns_none(self):
        for text in ("", "I refuse", "ACTION9", "ACTION6 with no coordinates"):
            with self.subTest(text=text):
                self.assertIsNone(parse_action(text))


class TestLLMPolicy(unittest.TestCase):
    def test_a_good_reply_becomes_that_action(self):
        client = ScriptedClient(["ACTION1\nmoving up"])
        policy = LLMPolicy(client)
        g = MockGame()
        frame = g.reset()
        action = policy.choose([frame], frame)
        self.assertEqual(action.kind, GameAction.ACTION1)
        self.assertEqual(policy.parse_failures, 0)

    def test_the_prompt_carries_screen_feedback_and_legal_options(self):
        client = ScriptedClient(["ACTION1"])
        g = MockGame(available=[GameAction.ACTION1, GameAction.ACTION2])
        frame = g.reset()
        prompt = LLMPolicy(client).build_prompt([frame], frame)
        self.assertIn("grid 16x16", prompt)          # the encoded screen
        self.assertIn("first frame", prompt)          # feedback slot filled
        self.assertIn("ACTION1, ACTION2", prompt)     # only the legal buttons
        self.assertNotIn("ACTION5", prompt)

    def test_unparseable_replies_fall_back_and_are_counted(self):
        policy = LLMPolicy(ScriptedClient(["I'd rather not."]))
        r = run_episode(MockGame(), policy, max_actions=5)
        self.assertEqual(policy.parse_failures, 5)
        self.assertEqual(r.actions_taken, 5)          # the episode still ran
        self.assertEqual(r.rejected_actions, 0)       # the fallback is always legal

    def test_client_errors_do_not_end_the_episode(self):
        policy = LLMPolicy(ScriptedClient([RuntimeError("429 quota")]))
        r = run_episode(MockGame(), policy, max_actions=4)
        self.assertEqual(policy.client_errors, 4)
        self.assertEqual(r.actions_taken, 4)
        self.assertIn("client error", r.steps[0].reasoning)

    def test_an_illegal_choice_is_still_stopped_by_the_loop(self):
        """Prompt says which buttons are legal; the guard guarantees it."""
        g = MockGame(available=[GameAction.RESET, GameAction.ACTION1])
        policy = LLMPolicy(ScriptedClient(["ACTION4"]))
        r = run_episode(g, policy, max_actions=3)
        self.assertEqual(r.rejected_actions, 3)


class TestHistoryEncoding(unittest.TestCase):
    """The context change Phase C's first experiment is about."""

    def _frames(self, moves):
        g = MockGame()
        frames = [g.reset()]
        for kind in moves:
            frames.append(g.step(Action(kind)))
        return frames

    def test_first_move_says_so_rather_than_showing_an_empty_list(self):
        self.assertIn("first move", render_history(self._frames([])))

    def test_each_line_names_the_action_and_its_effect(self):
        frames = self._frames([GameAction.ACTION1, GameAction.ACTION2])
        text = render_history(frames, window=8)
        self.assertEqual(len(text.splitlines()), 2)
        self.assertIn("ACTION1", text)
        self.assertIn("ACTION2", text)
        self.assertIn("cells changed", text)

    def test_the_window_caps_how_much_past_is_shown(self):
        frames = self._frames([GameAction.ACTION1] * 20)
        self.assertEqual(len(render_history(frames, window=5).splitlines()), 5)

    def test_a_dead_action_repeated_looks_identical_every_line(self):
        """The whole point: forty identical lines is what 'stuck' looks like in text."""
        frames = self._frames([GameAction.ACTION5] * 6)  # not available in the mock
        lines = render_history(frames, window=6).splitlines()
        self.assertEqual(len(set(line.split(":", 1)[1] for line in lines)), 1)
        self.assertIn("screen unchanged", lines[0])

    def test_history_is_absent_from_the_prompt_by_default(self):
        """Phase B's prompt must be reproducible byte for byte, or the A/B is not one."""
        g = MockGame()
        frame = g.reset()
        plain = LLMPolicy(ScriptedClient(["ACTION1"]))
        self.assertNotIn("recent actions", plain.build_prompt([frame], frame))

    def test_history_appears_when_asked_for(self):
        g = MockGame()
        frames = [g.reset()]
        frames.append(g.step(Action(GameAction.ACTION1)))
        policy = LLMPolicy(ScriptedClient(["ACTION1"]), history=4)
        prompt = policy.build_prompt(frames, frames[-1])
        self.assertIn("recent actions", prompt)
        self.assertIn("ACTION1 ->", prompt)

    def test_history_reports_what_was_sent_not_what_was_asked_for(self):
        """The loop rewrites illegal choices to RESET; the agent must see the RESET."""
        g = MockGame(available=[GameAction.RESET, GameAction.ACTION1])
        policy = LLMPolicy(ScriptedClient(["ACTION4"]), history=4)
        run_episode(g, policy, max_actions=3)
        last_prompt = policy.client.prompts[-1]
        self.assertIn("RESET ->", last_prompt)
        self.assertNotIn("ACTION4 ->", last_prompt)


class TestScreenFingerprint(unittest.TestCase):
    def test_the_same_grid_fingerprints_the_same(self):
        grid = [[1, 2], [3, 4]]
        self.assertEqual(grid_fingerprint(grid), grid_fingerprint([[1, 2], [3, 4]]))

    def test_one_changed_cell_changes_the_fingerprint(self):
        self.assertNotEqual(grid_fingerprint([[1, 2]]), grid_fingerprint([[1, 3]]))

    def test_rows_cannot_be_confused_with_each_other(self):
        """A naive 'flatten and join' makes [[1],[2,3]] and [[1,2],[3]] identical."""
        self.assertNotEqual(grid_fingerprint([[1], [2, 3]]), grid_fingerprint([[1, 2], [3]]))

    def test_the_loop_records_a_fingerprint_for_every_step(self):
        r = run_episode(MockGame(), RandomPolicy(seed=3), max_actions=6)
        self.assertTrue(all(len(s.screen_hash) == 16 for s in r.steps))


class TestEvalMetrics(unittest.TestCase):
    def test_a_dead_agent_scores_the_worst_on_every_steering_metric(self):
        r = run_episode(MockGame(), _AlwaysDead(), max_actions=10)
        m = evals.measure(r)
        self.assertEqual(m.no_change_rate, 1.0)
        self.assertEqual(m.top_action_share, 1.0)
        self.assertEqual(m.longest_repeat_streak, 10)
        self.assertEqual(m.distinct_actions, 1)
        self.assertEqual(m.revisit_rate, 0.9)  # ten actions, one screen

    def test_a_random_agent_spreads_across_actions(self):
        r = run_episode(MockGame(), RandomPolicy(seed=5), max_actions=40)
        m = evals.measure(r)
        self.assertGreater(m.distinct_actions, 1)
        self.assertLess(m.top_action_share, 0.6)
        self.assertLess(m.longest_repeat_streak, 10)

    def test_a_game_with_one_legal_action_is_not_reported_as_a_stuck_agent(self):
        """The confound found on 2026-07-22: `tn36-ef4dde99` offers exactly one action.

        A random policy there necessarily repeats it every turn, scoring a 100% favourite
        share and a full-length streak. The raw share cannot tell that from a stuck agent;
        the excess can, and reads 0.
        """
        g = MockGame(available=[GameAction.RESET, GameAction.ACTION1])
        m = evals.measure(run_episode(g, RandomPolicy(seed=4), max_actions=20))
        self.assertEqual(m.median_legal_options, 1)
        self.assertEqual(m.top_action_share, 1.0)
        self.assertEqual(m.top_action_share_excess, 0.0)

    def test_the_same_share_on_a_wide_game_is_flagged_as_excess(self):
        r = run_episode(MockGame(), _AlwaysDead(), max_actions=20)  # 7 options, one used
        m = evals.measure(r)
        self.assertEqual(m.median_legal_options, 7)
        self.assertEqual(m.top_action_share, 1.0)
        self.assertAlmostEqual(m.top_action_share_excess, 1 - 1 / 7)

    def test_distinct_targets_separates_clicking_around_from_clicking_once(self):
        """On a click-only game every action is ACTION6, so kinds cannot measure spread."""
        g = MockGame(available=[GameAction.RESET, GameAction.ACTION6])
        m = evals.measure(run_episode(g, RandomPolicy(seed=11), max_actions=20))
        self.assertEqual(m.distinct_actions, 1)       # one kind
        self.assertGreater(m.distinct_targets, 10)    # many coordinates

    def test_illegal_actions_show_up_as_a_rate(self):
        g = MockGame(available=[GameAction.RESET, GameAction.ACTION1])
        m = evals.measure(run_episode(g, _Illegal(), max_actions=4))
        self.assertEqual(m.illegal_action_rate, 1.0)

    def test_actions_to_first_score_is_none_when_nothing_scores(self):
        m = evals.measure(run_episode(MockGame(), _AlwaysDead(), max_actions=5))
        self.assertIsNone(m.actions_to_first_score)

    def test_level_numbers_come_from_the_servers_scorecard_not_from_us(self):
        """The exact shape measured from a real close on 2026-07-22."""
        m = evals.measure(run_episode(MockGame(), RandomPolicy(seed=0), max_actions=5))
        m.game_id = "ls20-9607627b"
        closed = {
            "environments": [
                {
                    "id": "ls20-9607627b",
                    "level_count": 7,
                    "levels_completed": 0,
                    "runs": [
                        {
                            "level_actions": [400, 0, 0, 0, 0, 0, 0],
                            "level_baseline_actions": [22, 123, 73, 84, 96, 192, 186],
                        }
                    ],
                }
            ]
        }
        out = evals.from_scorecard(m, closed)
        self.assertEqual(out.level1_actions, 400)
        self.assertEqual(out.level1_reference, 22)
        self.assertAlmostEqual(out.level1_ratio, 400 / 22)
        self.assertFalse(out.level1_completed)
        self.assertEqual(out.level_count, 7)

    def test_a_scorecard_for_another_game_is_ignored(self):
        m = evals.measure(run_episode(MockGame(), RandomPolicy(seed=0), max_actions=3))
        out = evals.from_scorecard(m, {"environments": [{"id": "somethingelse", "runs": []}]})
        self.assertIsNone(out.level1_actions)

    def test_no_scorecard_leaves_the_level_fields_empty_rather_than_zero(self):
        m = evals.measure(run_episode(MockGame(), RandomPolicy(seed=0), max_actions=3))
        self.assertIsNone(evals.from_scorecard(m, None).level1_ratio)


class TestEvalAggregation(unittest.TestCase):
    def _arm(self, name, *results):
        return evals.Arm(
            name=name,
            suite="dev",
            games=[r.game_id for r in results],
            episodes=[evals.measure(r) for r in results],
        )

    def test_rates_are_pooled_not_averaged_over_games(self):
        """Two games of unequal length must not count equally in a rate."""
        g = MockGame(available=[GameAction.RESET, GameAction.ACTION1])
        long_illegal = run_episode(g, _Illegal(), max_actions=90)   # 90 of 90 illegal
        short_clean = run_episode(MockGame(), RandomPolicy(seed=1), max_actions=10)  # 0 of 10
        arm = self._arm("mixed", long_illegal, short_clean)
        agg = arm.aggregate()
        self.assertEqual(agg["actions"], 100)
        # Pooled is 90/100. The mean of the two per-game rates would be (1.0 + 0.0)/2 = 0.5,
        # which would let a ten-action game cancel out a ninety-action disaster.
        self.assertAlmostEqual(agg["illegal_action_rate"], 0.9, places=4)
        per_game = [e.illegal_action_rate for e in arm.episodes]
        self.assertAlmostEqual(sum(per_game) / len(per_game), 0.5, places=4)

    def test_a_failed_episode_is_counted_but_does_not_pollute_the_rates(self):
        ok = evals.measure(run_episode(MockGame(), RandomPolicy(seed=2), max_actions=10))
        broken = evals.Metrics(
            game_id="x", policy="p", actions=0, illegal_actions=0, no_change_actions=0,
            unique_screens=0, top_action_count=0, longest_repeat_streak=0,
            distinct_actions=0, game_overs=0, resets=0, final_score=0,
            final_state="ERROR", wall_seconds=0.0, error="boom",
        )
        arm = evals.Arm(name="a", suite="dev", games=["x"], episodes=[ok, broken])
        agg = arm.aggregate()
        self.assertEqual(agg["episodes"], 1)
        self.assertEqual(agg["failed_episodes"], 1)
        self.assertEqual(agg["actions"], 10)

    def test_compare_labels_each_metric_with_its_kind(self):
        a = self._arm("before", run_episode(MockGame(), _AlwaysDead(), max_actions=10))
        b = self._arm("after", run_episode(MockGame(), RandomPolicy(seed=1), max_actions=10))
        rows = {r["metric"]: r for r in evals.compare(a, b)}
        self.assertEqual(rows["no_change_rate"]["kind"], "steering")
        self.assertEqual(rows["final_score"]["kind"], "outcome")
        self.assertEqual(rows["wall_seconds"]["kind"], "cost")

    def test_outcome_metrics_never_carry_a_verdict(self):
        """Score is reported, never steered on — so it gets no better/worse arrow."""
        a = self._arm("before", run_episode(MockGame(), _AlwaysDead(), max_actions=10))
        b = self._arm("after", run_episode(MockGame(), RandomPolicy(seed=1), max_actions=10))
        for row in evals.compare(a, b):
            if row["kind"] == "outcome":
                self.assertEqual(row["direction"], "")

    def test_a_forced_streak_on_a_one_action_game_is_left_out_of_the_aggregate(self):
        """Otherwise every arm, random included, reports the full episode length."""
        forced = MockGame(available=[GameAction.RESET, GameAction.ACTION1])
        wide = MockGame()
        arm = self._arm(
            "mixed",
            run_episode(forced, RandomPolicy(seed=1), max_actions=25),  # streak 25, no choice
            run_episode(wide, RandomPolicy(seed=1), max_actions=25),    # a real streak
        )
        self.assertEqual(arm.episodes[0].longest_repeat_streak, 25)
        self.assertLess(arm.aggregate()["longest_repeat_streak"], 25)

    def test_direction_knows_which_way_is_good(self):
        self.assertEqual(evals.direction("no_change_rate", 0.9, 0.1), "better")
        self.assertEqual(evals.direction("no_change_rate", 0.1, 0.9), "worse")
        self.assertEqual(evals.direction("distinct_actions", 1, 4), "better")
        self.assertEqual(evals.direction("final_state", "A", "B"), "")
        self.assertEqual(evals.direction("resets", 1, 2), "")  # no direction claimed


class TestCompareEvals(unittest.TestCase):
    """End to end over the two files an experiment is actually judged from."""

    def _write_arm(self, name: str, policy, history: int, actions: int) -> None:
        arm = evals.Arm(
            name=name,
            suite="dev",
            games=["mock01"],
            episodes=[evals.measure(run_episode(MockGame(), policy, max_actions=actions))],
            config={"policy": "llm", "history": history, "seed": 0, "mock": True},
        )
        (compare_evals.EVAL_DIR / f"{name}.json").write_text(
            json.dumps(arm.to_dict(), indent=2), encoding="utf-8"
        )

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._saved = compare_evals.EVAL_DIR
        compare_evals.EVAL_DIR = Path(self._tmp.name)
        # The comparer prints a table; a test run should not.
        self._stdout = contextlib.redirect_stdout(io.StringIO())
        self._stdout.__enter__()

    def tearDown(self):
        self._stdout.__exit__(None, None, None)
        compare_evals.EVAL_DIR = self._saved
        self._tmp.cleanup()

    def test_the_artifact_stores_canonical_directions_not_display_text(self):
        """The bug this caught: the file said "WORSE" while every reader expects "worse"."""
        self._write_arm("before", RandomPolicy(seed=1), 0, 20)
        self._write_arm("after", _AlwaysDead(), 8, 20)
        compare_evals.main(["before", "after"])

        out = json.loads(
            (compare_evals.EVAL_DIR / "comparison-before-vs-after.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertTrue(out["single_variable"])
        self.assertEqual(out["config_changed"], ["history: 0 -> 8"])
        directions = {r["direction"] for r in out["rows"]}
        self.assertTrue(directions <= {"better", "worse", "same", ""}, directions)
        # A policy that repeats one dead action must be worse on repetition.
        worse = {r["metric"] for r in out["rows"] if r["direction"] == "worse"}
        self.assertIn("top_action_share_excess", worse)

    def test_outcome_rows_never_carry_a_verdict_in_the_file_either(self):
        self._write_arm("a", RandomPolicy(seed=1), 0, 20)
        self._write_arm("b", RandomPolicy(seed=2), 8, 20)
        compare_evals.main(["a", "b"])
        out = json.loads(
            (compare_evals.EVAL_DIR / "comparison-a-vs-b.json").read_text(encoding="utf-8")
        )
        for row in out["rows"]:
            if row["kind"] == "outcome":
                self.assertEqual(row["direction"], "")


class TestSuiteSplit(unittest.TestCase):
    def test_the_three_suites_are_disjoint_and_cover_every_game(self):
        s = evals.SUITES
        allg = s["dev"] + s["heldout"] + s["reserve"]
        self.assertEqual(len(allg), len(set(allg)))
        self.assertEqual(set(allg), set(evals.GAMES))

    def test_the_split_is_reproducible_from_the_published_seed(self):
        self.assertEqual(evals.split(), evals.split())
        self.assertNotEqual(evals.split(seed=1)["dev"], evals.split(seed=2)["dev"])

    def test_the_contaminated_game_is_in_dev_and_not_in_heldout(self):
        """Every baseline in this repo was measured on ls20; it cannot be 'held out'."""
        for game in evals.PINNED_DEV:
            self.assertIn(game, evals.SUITES["dev"])
            self.assertNotIn(game, evals.SUITES["heldout"])

    def test_the_heldout_suite_refuses_to_run_without_report(self):
        with self.assertRaises(evals.HeldOutViolation):
            run_evals_main(["--arm", "sneaky", "--suite", "heldout"])


class TestRateLimiter(unittest.TestCase):
    def _limiter(self, limits, headroom: float = 1.0):
        self.slept: list[float] = []
        self.now = [0.0]

        def sleep(s):
            self.slept.append(s)
            self.now[0] += s

        return RateLimiter(
            limits, sleep=sleep, clock=lambda: self.now[0], headroom=headroom
        )

    def test_rpm_makes_the_caller_wait(self):
        lim = self._limiter(Limits("t", rpm=3, tpm=10_000, rpd=100))
        for _ in range(3):
            lim.acquire(tokens=10)
        self.assertEqual(self.slept, [])
        lim.acquire(tokens=10)          # the fourth call in a minute
        self.assertEqual(len(self.slept), 1)
        self.assertAlmostEqual(self.slept[0], 60.0)

    def test_tpm_binds_before_rpm_on_big_prompts(self):
        lim = self._limiter(Limits("t", rpm=100, tpm=1_000, rpd=100))
        lim.acquire(tokens=600)
        lim.acquire(tokens=600)         # 1,200 > 1,000 in the same minute
        self.assertEqual(len(self.slept), 1)

    def test_daily_limit_raises_rather_than_sleeping_until_tomorrow(self):
        lim = self._limiter(Limits("t", rpm=100, tpm=10_000, rpd=2))
        lim.acquire()
        lim.acquire()
        with self.assertRaises(BudgetExhausted):
            lim.acquire()

    def test_headroom_paces_below_the_stated_limit(self):
        """Pacing at exactly the limit still produced 429s on 3 of 80 real calls."""
        lim = self._limiter(Limits("t", rpm=10, tpm=10_000, rpd=100), headroom=0.8)
        for _ in range(8):
            lim.acquire()
        self.assertEqual(self.slept, [])
        lim.acquire()  # the 9th call, though the stated limit is 10
        self.assertEqual(len(self.slept), 1)

    def test_measured_limits_are_present_for_the_model_we_use(self):
        self.assertIn("gemini-3.5-flash-lite", LIMITS)
        self.assertEqual(LIMITS["gemini-3.5-flash-lite"].rpd, 500)


if __name__ == "__main__":
    unittest.main(verbosity=2)
