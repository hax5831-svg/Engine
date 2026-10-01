"""Unit tests for Crankshaft kinematics, angles, and RPM conversion."""

import math
import unittest
from aero_engine.config import EngineConfig
from aero_engine.crankshaft import (
    calculate_piston_position,
    calculate_normalized_piston_height,
    calculate_connecting_rod_angle,
    Crankshaft,
)


class TestCrankshaft(unittest.TestCase):
    def test_crank_slider_piston_position(self):
        r = 70.0
        l = 210.0

        # Top Dead Center (TDC) at 0 deg (or 360 deg)
        x_tdc = calculate_piston_position(0.0, r, l)
        self.assertAlmostEqual(x_tdc, r + l, places=4)  # 280.0 mm
        self.assertAlmostEqual(calculate_normalized_piston_height(0.0, r, l), 1.0, places=4)

        # Bottom Dead Center (BDC) at 180 deg (pi radians)
        x_bdc = calculate_piston_position(math.pi, r, l)
        self.assertAlmostEqual(x_bdc, l - r, places=4)  # 140.0 mm
        self.assertAlmostEqual(calculate_normalized_piston_height(180.0, r, l), 0.0, places=4)

        # 90 degrees
        x_90 = calculate_piston_position(math.pi / 2.0, r, l)
        expected_90 = math.sqrt(l * l - r * r)
        self.assertAlmostEqual(x_90, expected_90, places=4)

        # Piston height is always within [0.0, 1.0]
        for angle in range(0, 720, 15):
            h = calculate_normalized_piston_height(float(angle), r, l)
            self.assertTrue(0.0 <= h <= 1.0)

    def test_connecting_rod_angle(self):
        r = 70.0
        l = 210.0

        # At TDC and BDC, rod angle is 0
        self.assertAlmostEqual(calculate_connecting_rod_angle(0.0, r, l), 0.0, places=4)
        self.assertAlmostEqual(calculate_connecting_rod_angle(180.0, r, l), 0.0, places=4)
        self.assertAlmostEqual(calculate_connecting_rod_angle(360.0, r, l), 0.0, places=4)

        # At 90 deg, sin(beta) = r / l = 70 / 210 = 1/3
        beta_90 = calculate_connecting_rod_angle(90.0, r, l)
        expected_beta = math.asin(1.0 / 3.0)
        self.assertAlmostEqual(beta_90, expected_beta, places=4)

        # At 270 deg, sin(beta) = -1/3
        beta_270 = calculate_connecting_rod_angle(270.0, r, l)
        self.assertAlmostEqual(beta_270, -expected_beta, places=4)

    def test_rpm_to_angular_velocity(self):
        config = EngineConfig()
        crank = Crankshaft(config)

        # 60 RPM = 1 rev/sec = 360 deg/sec
        crank.set_rpm(60.0)
        self.assertAlmostEqual(crank.angular_velocity_deg_s, 360.0, places=4)

        # 1200 RPM = 20 rev/sec = 7200 deg/sec
        crank.set_rpm(1200.0)
        self.assertAlmostEqual(crank.angular_velocity_deg_s, 7200.0, places=4)

    def test_crank_angle_progression(self):
        config = EngineConfig()
        crank = Crankshaft(config)
        crank.set_rpm(600.0)  # 3600 deg/s

        # Advance 0.1 seconds -> 360 degrees
        delta = crank.advance(0.1)
        self.assertAlmostEqual(delta, 360.0, places=4)
        self.assertAlmostEqual(crank.angle_deg, 360.0, places=4)
        self.assertAlmostEqual(crank.total_rotations, 1.0, places=4)

        # Advance another 0.15 seconds -> 540 degrees -> total 900 deg -> wrapped to 180 deg
        delta2 = crank.advance(0.15)
        self.assertAlmostEqual(delta2, 540.0, places=4)
        self.assertAlmostEqual(crank.angle_deg, 180.0, places=4)
        self.assertAlmostEqual(crank.total_rotations, 2.5, places=4)

    def test_crank_reset(self):
        crank = Crankshaft()
        crank.set_rpm(1000.0)
        crank.advance(1.0)
        self.assertGreater(crank.angle_deg, 0)
        crank.reset()
        self.assertEqual(crank.angle_deg, 0.0)
        self.assertEqual(crank.rpm, 0.0)
        self.assertEqual(crank.angular_velocity_deg_s, 0.0)
        self.assertEqual(crank.total_rotations, 0.0)


if __name__ == "__main__":
    unittest.main()
