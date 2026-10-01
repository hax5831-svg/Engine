"""Crankshaft kinematics and geometry for the AeroEngine simulator."""

import math
from typing import List
from aero_engine.config import EngineConfig, DEFAULT_CONFIG


def calculate_piston_position(crank_angle_rad: float, r: float, l: float) -> float:
    """
    Calculate absolute piston position from crank axis using crank-slider equation:
    x = r * cos(theta) + sqrt(L^2 - r^2 * sin^2(theta))

    Args:
        crank_angle_rad: Crankshaft angle in radians.
        r: Crank radius (half of stroke length).
        l: Connecting rod length.

    Returns:
        Distance from crankshaft center to piston wrist pin in mm.
    """
    sin_theta = math.sin(crank_angle_rad)
    cos_theta = math.cos(crank_angle_rad)
    inner = l * l - (r * sin_theta) ** 2
    # Ensure numerical stability
    inner = max(0.0, inner)
    return r * cos_theta + math.sqrt(inner)


def calculate_normalized_piston_height(crank_angle_deg: float, r: float, l: float) -> float:
    """
    Returns normalized piston height in range [0.0, 1.0], where:
    1.0 = Top Dead Center (TDC)
    0.0 = Bottom Dead Center (BDC)
    """
    rad = math.radians(crank_angle_deg % 360.0)
    x = calculate_piston_position(rad, r, l)
    min_x = l - r  # BDC
    max_x = l + r  # TDC
    stroke = 2.0 * r
    if stroke <= 0.0:
        return 0.0
    h = (x - min_x) / stroke
    return max(0.0, min(1.0, h))


def calculate_connecting_rod_angle(crank_angle_deg: float, r: float, l: float) -> float:
    """
    Calculate the connecting rod angle beta in radians relative to cylinder axis.
    sin(beta) = (r / L) * sin(theta)
    """
    rad = math.radians(crank_angle_deg % 360.0)
    val = (r / l) * math.sin(rad)
    val = max(-1.0, min(1.0, val))
    return math.asin(val)


class Crankshaft:
    """
    Models the rotating crankshaft assembly for a 10-cylinder engine over a 720° 4-stroke cycle.
    """

    def __init__(self, config: EngineConfig = DEFAULT_CONFIG):
        self.config = config
        self.angle_deg: float = 0.0  # Master crank angle in [0.0, 720.0)
        self.rpm: float = 0.0
        self.angular_velocity_deg_s: float = 0.0
        self.total_rotations: float = 0.0

    @property
    def r(self) -> float:
        return self.config.crank_radius_mm

    @property
    def l(self) -> float:
        return self.config.rod_length_mm

    def set_rpm(self, rpm: float) -> None:
        """Set RPM and update angular velocity (deg/sec)."""
        self.rpm = max(0.0, rpm)
        # 1 RPM = 360 degrees / 60 seconds = 6.0 deg/s
        self.angular_velocity_deg_s = self.rpm * 6.0

    def advance(self, dt: float) -> float:
        """
        Advance crankshaft angle by elapsed time dt (seconds).
        Returns the delta angle in degrees.
        """
        if dt <= 0.0 or self.rpm <= 0.0:
            return 0.0

        delta_deg = self.angular_velocity_deg_s * dt
        self.total_rotations += delta_deg / 360.0
        self.angle_deg = (self.angle_deg + delta_deg) % 720.0
        return delta_deg

    def get_cylinder_phase(self, firing_order_index: int) -> float:
        """
        Calculate local 720° cycle phase angle for a cylinder given its firing order index (0 to 9).
        The firing interval for 10 cylinders is 720° / 10 = 72°.
        When master crank angle reaches firing_offset + 360°, this cylinder is at TDC Power stroke.
        """
        cyl_interval = 720.0 / self.config.num_cylinders
        offset = firing_order_index * cyl_interval
        # Cylinder phase in [0.0, 720.0)
        # Offset is subtracted so that cylinders reach 360° (power stroke) sequentially
        return (self.angle_deg - offset) % 720.0

    def reset(self) -> None:
        """Reset crankshaft to zero position and zero RPM."""
        self.angle_deg = 0.0
        self.rpm = 0.0
        self.angular_velocity_deg_s = 0.0
        self.total_rotations = 0.0
