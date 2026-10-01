"""Individual cylinder physics and stroke tracking for the AeroEngine simulator."""

import math
from typing import Tuple
from aero_engine.config import EngineConfig, Stroke, DEFAULT_CONFIG
from aero_engine.crankshaft import (
    calculate_piston_position,
    calculate_normalized_piston_height,
    calculate_connecting_rod_angle,
)


class Cylinder:
    """
    Represents an individual cylinder in a 4-stroke 10-cylinder engine.
    Tracks kinematics, valve states, ignition, combustion, and exhaust.
    """

    def __init__(self, cylinder_id: int, firing_order_index: int, config: EngineConfig = DEFAULT_CONFIG):
        self.cylinder_id = cylinder_id
        self.firing_order_index = firing_order_index
        self.config = config

        # Dynamic cycle state
        self.crank_phase: float = 0.0          # Local angle in [0.0, 720.0)
        self.mechanical_angle: float = 0.0      # Mechanical angle in [0.0, 360.0)
        self.piston_position_mm: float = 0.0    # Distance from crank center
        self.normalized_height: float = 0.0     # 0.0 (BDC) to 1.0 (TDC)
        self.rod_angle_rad: float = 0.0         # Connecting rod angle (rad)
        self.current_stroke: Stroke = Stroke.INTAKE
        self.stroke_progress: float = 0.0       # Progress in current stroke [0.0, 1.0]

        # Valve states
        self.intake_valve_open: bool = False
        self.intake_valve_lift: float = 0.0     # 0.0 (closed) to 1.0 (full open)
        self.exhaust_valve_open: bool = False
        self.exhaust_valve_lift: float = 0.0    # 0.0 (closed) to 1.0 (full open)

        # Combustion & Ignition states
        self.ignition_state: bool = False       # Spark plug firing
        self.combustion_state: bool = False     # Fuel burning in power stroke
        self.combustion_intensity: float = 0.0  # 0.0 to 1.0
        self.exhaust_state: bool = False        # Exhaust gas venting
        self.exhaust_intensity: float = 0.0     # 0.0 to 1.0

        # Thermodynamics
        self.pressure_bar: float = 1.0

        # Initialize to starting phase
        self.update(0.0, is_engine_firing=False)

    def update(self, crank_phase: float, is_engine_firing: bool = True) -> None:
        """
        Update the cylinder state based on the local crank phase [0.0, 720.0).

        Args:
            crank_phase: Local cycle angle in degrees [0.0, 720.0).
            is_engine_firing: True if fuel/ignition is active.
        """
        self.crank_phase = crank_phase % 720.0
        self.mechanical_angle = self.crank_phase % 360.0

        r = self.config.crank_radius_mm
        l = self.config.rod_length_mm

        # Kinematics
        self.piston_position_mm = calculate_piston_position(
            math.radians(self.mechanical_angle), r, l
        )
        self.normalized_height = calculate_normalized_piston_height(
            self.mechanical_angle, r, l
        )
        self.rod_angle_rad = calculate_connecting_rod_angle(
            self.mechanical_angle, r, l
        )

        # 4-Stroke cycle determination
        # 0° - 180°: Intake
        # 180° - 360°: Compression
        # 360° - 540°: Power (Combustion)
        # 540° - 720°: Exhaust
        phase = self.crank_phase

        if 0.0 <= phase < 180.0:
            self.current_stroke = Stroke.INTAKE
            self.stroke_progress = phase / 180.0
            self.intake_valve_open = True
            # Valve lift follows smooth half-sine lobe
            self.intake_valve_lift = math.sin(math.radians(phase))
            self.exhaust_valve_open = False
            self.exhaust_valve_lift = 0.0
            self.combustion_state = False
            self.combustion_intensity = 0.0
            self.exhaust_state = False
            self.exhaust_intensity = 0.0
            self.pressure_bar = 1.0

        elif 180.0 <= phase < 360.0:
            self.current_stroke = Stroke.COMPRESSION
            self.stroke_progress = (phase - 180.0) / 180.0
            self.intake_valve_open = False
            self.intake_valve_lift = 0.0
            self.exhaust_valve_open = False
            self.exhaust_valve_lift = 0.0
            self.combustion_state = False
            self.combustion_intensity = 0.0
            self.exhaust_state = False
            self.exhaust_intensity = 0.0

            # Polytropic compression pressure curve
            comp_ratio = self.config.compression_ratio
            effective_cr = 1.0 + (comp_ratio - 1.0) * self.normalized_height
            self.pressure_bar = 1.0 * (effective_cr ** 1.35)

        elif 360.0 <= phase < 540.0:
            self.current_stroke = Stroke.POWER
            self.stroke_progress = (phase - 360.0) / 180.0
            self.intake_valve_open = False
            self.intake_valve_lift = 0.0
            self.exhaust_valve_open = False
            self.exhaust_valve_lift = 0.0

            if is_engine_firing:
                self.combustion_state = True
                # Intensity drops exponentially from peak after TDC
                decay = math.exp(-3.0 * self.stroke_progress)
                self.combustion_intensity = max(0.05, decay)
                peak_p = 55.0
                self.pressure_bar = max(3.0, peak_p * (1.0 - 0.85 * self.stroke_progress))
            else:
                self.combustion_state = False
                self.combustion_intensity = 0.0
                self.pressure_bar = 2.0

            self.exhaust_state = False
            self.exhaust_intensity = 0.0

        else:  # 540.0 <= phase < 720.0
            self.current_stroke = Stroke.EXHAUST
            self.stroke_progress = (phase - 540.0) / 180.0
            self.intake_valve_open = False
            self.intake_valve_lift = 0.0
            self.exhaust_valve_open = True
            # Valve lift follows smooth half-sine lobe
            self.exhaust_valve_lift = math.sin(math.radians(phase - 540.0))
            self.combustion_state = False
            self.combustion_intensity = 0.0

            if is_engine_firing:
                self.exhaust_state = True
                # Highest ejection at beginning of exhaust blowdown
                self.exhaust_intensity = math.sin(math.radians(phase - 540.0))
            else:
                self.exhaust_state = False
                self.exhaust_intensity = 0.0

            self.pressure_bar = 1.3

        # Ignition spark window
        # Fires slightly before TDC (e.g., 360° - advance) through early expansion
        spark_start = (360.0 - self.config.spark_advance_deg) % 720.0
        spark_end = (spark_start + self.config.spark_duration_deg) % 720.0
        if is_engine_firing:
            if spark_start <= spark_end:
                self.ignition_state = spark_start <= self.crank_phase <= spark_end
            else:
                # Wrap-around if spark crosses 720° (not typical for 338°-368°, but robust)
                self.ignition_state = self.crank_phase >= spark_start or self.crank_phase <= spark_end
        else:
            self.ignition_state = False

    @property
    def stroke_name(self) -> str:
        return self.current_stroke.value

    def get_status_summary(self) -> str:
        """Short formatted status, e.g. '01 POWER'."""
        return f"{self.cylinder_id:02d} {self.current_stroke.value}"
