"""Tests for the offline harness. Standard-library `unittest` — no extra install.

Run:  py -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from arc_agi_3._structs import GameAction, GameState  # noqa: E402

from harness.actions import Action  # noqa: E402
from harness.frames import (  # noqa: E402
    diff_grids,
    find_blobs,
    grid_shape,
    main_grid,
    render_diff,
    render_grid,
    render_objects,
)
from harness.loop import run_episode  # noqa: E402
from harness.mock_game import AGENT, MockGame, WIN_SCORE  # noqa: E402
from harness.policies import RandomPolicy, legal_actions  # noqa: E402
from harness.tokens import measure  # noqa: E402
from harness.trace import Tracer  # noqa: E402
from scripts.analyze_run import load as load_recording  # noqa: E402
from scripts.run_agent import RecordingEnv, resolve_game  # noqa: E402


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
