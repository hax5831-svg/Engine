"""Unit tests for individual cylinder stroke phases, valve timings, and ignition."""

import unittest
from aero_engine.config import EngineConfig, Stroke
from aero_engine.cylinder import Cylinder


class TestCylinder(unittest.TestCase):
    def test_four_stroke_phases(self):
        config = EngineConfig()
        cyl = Cylinder(cylinder_id=1, firing_order_index=0, config=config)

        # 1. Intake Stroke: [0, 180)
        cyl.update(90.0, is_engine_firing=True)
        self.assertEqual(cyl.current_stroke, Stroke.INTAKE)
        self.assertTrue(cyl.intake_valve_open)
        self.assertGreater(cyl.intake_valve_lift, 0.9)  # sin(90°) = 1.0
        self.assertFalse(cyl.exhaust_valve_open)
        self.assertFalse(cyl.combustion_state)

        # 2. Compression Stroke: [180, 360)
        cyl.update(270.0, is_engine_firing=True)
        self.assertEqual(cyl.current_stroke, Stroke.COMPRESSION)
        self.assertFalse(cyl.intake_valve_open)
        self.assertFalse(cyl.exhaust_valve_open)
        self.assertFalse(cyl.combustion_state)
        self.assertGreater(cyl.pressure_bar, 1.0)  # Compressing

        # 3. Power Stroke: [360, 540)
        cyl.update(400.0, is_engine_firing=True)
        self.assertEqual(cyl.current_stroke, Stroke.POWER)
        self.assertFalse(cyl.intake_valve_open)
        self.assertFalse(cyl.exhaust_valve_open)
        self.assertTrue(cyl.combustion_state)
        self.assertGreater(cyl.combustion_intensity, 0.0)

        # 4. Exhaust Stroke: [540, 720)
        cyl.update(630.0, is_engine_firing=True)
        self.assertEqual(cyl.current_stroke, Stroke.EXHAUST)
        self.assertFalse(cyl.intake_valve_open)
        self.assertTrue(cyl.exhaust_valve_open)
        self.assertGreater(cyl.exhaust_valve_lift, 0.9)  # sin(90°) = 1.0
        self.assertFalse(cyl.combustion_state)

    def test_spark_ignition_window(self):
        config = EngineConfig(spark_advance_deg=22.0, spark_duration_deg=30.0)
        cyl = Cylinder(cylinder_id=1, firing_order_index=0, config=config)

        # Spark starts at 360 - 22 = 338°, ends at 368°
        cyl.update(330.0, is_engine_firing=True)
        self.assertFalse(cyl.ignition_state)

        cyl.update(345.0, is_engine_firing=True)
        self.assertTrue(cyl.ignition_state)

        cyl.update(360.0, is_engine_firing=True)
        self.assertTrue(cyl.ignition_state)

        cyl.update(375.0, is_engine_firing=True)
        self.assertFalse(cyl.ignition_state)

        # When engine is not firing, spark is always False
        cyl.update(345.0, is_engine_firing=False)
        self.assertFalse(cyl.ignition_state)

    def test_cylinder_piston_height_bounds(self):
        cyl = Cylinder(cylinder_id=1, firing_order_index=0)
        for angle in range(0, 720, 10):
            cyl.update(float(angle), is_engine_firing=True)
            self.assertTrue(0.0 <= cyl.normalized_height <= 1.0)
            min_pos = cyl.config.rod_length_mm - cyl.config.crank_radius_mm
            max_pos = cyl.config.rod_length_mm + cyl.config.crank_radius_mm
            self.assertGreaterEqual(cyl.piston_position_mm, min_pos - 1e-4)
            self.assertLessEqual(cyl.piston_position_mm, max_pos + 1e-4)


if __name__ == "__main__":
    unittest.main()
