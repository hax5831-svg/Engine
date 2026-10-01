"""Unit tests for Engine assembly, firing order, synchronization, and state transitions."""

import unittest
from aero_engine.config import EngineConfig, EngineState, Stroke
from aero_engine.engine import Engine


class TestEngine(unittest.TestCase):
    def test_cylinder_count_and_mapping(self):
        engine = Engine()
        self.assertEqual(len(engine.cylinders), 10)
        self.assertEqual(len(engine.cylinders_by_id), 10)
        for cyl_id in range(1, 11):
            self.assertIn(cyl_id, engine.cylinders_by_id)
            self.assertEqual(engine.cylinders_by_id[cyl_id].cylinder_id, cyl_id)

    def test_firing_order_synchronization(self):
        config = EngineConfig(firing_order=[1, 6, 5, 10, 2, 7, 3, 8, 4, 9])
        engine = Engine(config)

        # Cylinder interval is 720 / 10 = 72°
        # At crank angle = 360°, Cylinder 1 (index 0) should be at phase 360° (Power stroke start)
        engine.crankshaft.angle_deg = 360.0
        engine._update_cylinders()

        cyl1 = engine.cylinders_by_id[1]
        self.assertAlmostEqual(cyl1.crank_phase, 360.0, places=4)
        self.assertEqual(cyl1.current_stroke, Stroke.POWER)

        # 72 degrees later (crank angle = 432°), Cylinder 6 (index 1 in firing order) reaches 360°
        engine.crankshaft.angle_deg = 432.0
        engine._update_cylinders()

        cyl6 = engine.cylinders_by_id[6]
        self.assertAlmostEqual(cyl6.crank_phase, 360.0, places=4)
        self.assertEqual(cyl6.current_stroke, Stroke.POWER)

        # Another 72 degrees later (crank angle = 504°), Cylinder 5 (index 2 in firing order) reaches 360°
        engine.crankshaft.angle_deg = 504.0
        engine._update_cylinders()

        cyl5 = engine.cylinders_by_id[5]
        self.assertAlmostEqual(cyl5.crank_phase, 360.0, places=4)
        self.assertEqual(cyl5.current_stroke, Stroke.POWER)

    def test_custom_firing_order(self):
        engine = Engine()
        new_order = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        engine.set_firing_order(new_order)
        self.assertEqual(engine.config.firing_order, new_order)

        # Cylinder 2 should have firing index 1 (offset 72°)
        cyl2 = engine.cylinders_by_id[2]
        self.assertEqual(cyl2.firing_order_index, 1)

        # Invalid length raises ValueError
        with self.assertRaises(ValueError):
            engine.set_firing_order([1, 2, 3])

    def test_engine_state_transitions(self):
        config = EngineConfig(starter_crank_time=0.5, rpm_accel_rate=2000.0, idle_rpm=800.0)
        engine = Engine(config)

        # Initial state
        self.assertEqual(engine.state, EngineState.OFF)
        self.assertEqual(engine.actual_rpm, 0.0)

        # Start engine
        engine.start()
        self.assertEqual(engine.state, EngineState.STARTING)

        # Step through starter crank
        engine.step(0.2)
        self.assertEqual(engine.state, EngineState.STARTING)
        self.assertGreater(engine.actual_rpm, 0.0)

        # Step past starter time until engine catches and reaches idle
        for _ in range(25):
            engine.step(0.1)

        self.assertEqual(engine.state, EngineState.RUNNING)
        self.assertAlmostEqual(engine.actual_rpm, config.idle_rpm, delta=30.0)

        # Adjust throttle to 50%
        engine.set_throttle(0.5)
        expected_rpm = config.idle_rpm + 0.5 * (config.max_rpm - config.idle_rpm)
        for _ in range(35):
            engine.step(0.1)
        self.assertAlmostEqual(engine.actual_rpm, expected_rpm, delta=30.0)

        # Stop engine
        engine.stop()
        self.assertEqual(engine.state, EngineState.STOPPING)

        # Step until RPM reaches 0 and transitions to OFF
        for _ in range(50):
            engine.step(0.1)
        self.assertEqual(engine.state, EngineState.OFF)
        self.assertEqual(engine.actual_rpm, 0.0)

    def test_engine_reset(self):
        engine = Engine()
        engine.start()
        for _ in range(10):
            engine.step(0.1)
        engine.reset()
        self.assertEqual(engine.state, EngineState.OFF)
        self.assertEqual(engine.actual_rpm, 0.0)
        self.assertEqual(engine.crankshaft.angle_deg, 0.0)
        self.assertEqual(engine.throttle, 0.0)
        self.assertEqual(engine.engine_temp_c, engine.config.ambient_temp_c)

    def test_engine_telemetry_progression(self):
        engine = Engine()
        engine.start()
        # Run for 5 simulated seconds
        for _ in range(50):
            engine.step(0.1)

        self.assertGreaterEqual(engine.oil_pressure_bar, engine.config.idle_oil_pressure_bar * 0.9)
        self.assertGreaterEqual(engine.fuel_flow_lph, engine.config.idle_fuel_flow_lph * 0.9)
        self.assertGreaterEqual(engine.engine_temp_c, engine.config.ambient_temp_c)


if __name__ == "__main__":
    unittest.main()
