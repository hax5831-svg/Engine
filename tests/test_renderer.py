"""Unit tests for TerminalRenderer methods, mock drawing, and dashboard formatting."""

import unittest
from aero_engine.config import EngineConfig, EngineState, Stroke
from aero_engine.engine import Engine
from aero_engine.simulation import Simulation
from aero_engine.renderer import TerminalRenderer


class MockCursesWindow:
    def __init__(self, max_y=30, max_x=100):
        self.max_y = max_y
        self.max_x = max_x
        self.buffer = {}
        self.refreshed = False

    def getmaxyx(self):
        return self.max_y, self.max_x

    def nodelay(self, flag):
        pass

    def keypad(self, flag):
        pass

    def erase(self):
        self.buffer.clear()

    def noutrefresh(self):
        self.refreshed = True

    def addstr(self, y, x, text, attr=0):
        for idx, ch in enumerate(text):
            if 0 <= y < self.max_y and 0 <= (x + idx) < self.max_x:
                self.buffer[(y, x + idx)] = (ch, attr)

    def inch(self, y, x):
        ch, _ = self.buffer.get((y, x), (' ', 0))
        return ord(ch)

    def get_text_at(self, y, x, length):
        return "".join(self.buffer.get((y, x + i), (" ", 0))[0] for i in range(length))


class TestRenderer(unittest.TestCase):
    def setUp(self):
        self.mock_win = MockCursesWindow(max_y=35, max_x=100)
        self.renderer = TerminalRenderer(self.mock_win, use_color=False)
        self.sim = Simulation()

    def test_renderer_initialization(self):
        self.assertEqual(self.renderer.use_color, False)
        self.assertFalse(self.renderer.show_diagnostics)
        self.assertFalse(self.renderer.show_cycle_chart)

    def test_render_normal_terminal(self):
        # Render initial OFF state
        self.renderer.render(self.sim)
        self.assertTrue(self.mock_win.refreshed)

        # Check header rendered
        found_header = any("AERO-10" in self.mock_win.get_text_at(y, 0, 100) for y in range(5))
        self.assertTrue(found_header)

        # Check cylinder labels #01 to #10 rendered
        found_cyl1 = any("#01" in self.mock_win.get_text_at(y, 0, 100) for y in range(35))
        found_cyl10 = any("#10" in self.mock_win.get_text_at(y, 0, 100) for y in range(35))
        self.assertTrue(found_cyl1)
        self.assertTrue(found_cyl10)

    def test_render_running_with_combustion(self):
        self.sim.time_scale = 1.0
        self.sim.engine.start()
        for _ in range(30):
            self.sim.update(0.1)

        self.assertEqual(self.sim.engine.state, EngineState.RUNNING)
        self.renderer.render(self.sim)
        self.assertTrue(self.mock_win.refreshed)

    def test_pause_and_speed_controls(self):
        self.sim.time_scale = 0.08
        self.sim.toggle_pause()
        self.assertTrue(self.sim.is_paused)
        self.sim.speed_up()
        self.assertGreater(self.sim.time_scale, 0.08)
        self.sim.slow_down()
        self.sim.toggle_pause()
        self.assertFalse(self.sim.is_paused)

    def test_render_diagnostics_overlay(self):
        self.renderer.show_diagnostics = True
        self.renderer.render(self.sim)
        found_diag = any("DIAGNOSTICS" in self.mock_win.get_text_at(y, 0, 100) for y in range(35))
        self.assertTrue(found_diag)

    def test_render_cycle_chart_overlay(self):
        self.renderer.show_cycle_chart = True
        self.renderer.render(self.sim)
        found_chart = any("SYNCHRONIZATION" in self.mock_win.get_text_at(y, 0, 100) for y in range(35))
        self.assertTrue(found_chart)

    def test_render_compact_fallback_small_terminal(self):
        small_win = MockCursesWindow(max_y=20, max_x=60)
        renderer = TerminalRenderer(small_win, use_color=False)
        renderer.render(self.sim)
        found_fallback = any("Compact Mode" in small_win.get_text_at(y, 0, 60) for y in range(20))
        self.assertTrue(found_fallback)

    def test_particle_effects_simulation(self):
        self.sim.engine.start()
        for _ in range(40):
            self.sim.update(0.05)
        # Should have stepped simulation and possibly spawned exhaust particles
        self.renderer.render(self.sim)
        self.assertGreaterEqual(self.sim.frame_count, 40)

    def test_particles_do_not_corrupt_text(self):
        self.sim.time_scale = 1.0
        self.sim.engine.start()
        self.sim.engine.actual_rpm = 2500.0
        self.sim.engine.state = EngineState.RUNNING
        self.sim.engine.set_throttle(0.8)

        # Run multiple frames with heavy particle spawning
        for _ in range(30):
            self.sim.update(0.05)
            self.renderer.render(self.sim)

            # Dashboard text on row 2 must never have dots or missing letters
            row2_text = self.mock_win.get_text_at(2, 0, 100)
            self.assertIn("THROTTLE", row2_text)
            self.assertIn("STATE", row2_text)
            self.assertIn("RPM", row2_text)
            self.assertNotIn("THRO.TLE", row2_text)


if __name__ == "__main__":
    unittest.main()
