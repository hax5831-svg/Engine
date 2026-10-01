"""Configuration parameters for the AeroEngine 10-cylinder aircraft piston engine."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class EngineState(Enum):
    OFF = "OFF"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"


class Stroke(Enum):
    INTAKE = "INTAKE"
    COMPRESSION = "COMPRESSION"
    POWER = "POWER"
    EXHAUST = "EXHAUST"


@dataclass
class EngineConfig:
    # Cylinder and crankshaft mechanics
    num_cylinders: int = 10
    crank_radius_mm: float = 70.0       # r = 70mm (140mm stroke)
    rod_length_mm: float = 210.0        # L = 210mm (L/r = 3.0)
    bore_mm: float = 130.0              # 130mm bore
    compression_ratio: float = 8.5      # Typical supercharged/aircraft avgas engine

    # Firing order (1-indexed cylinder IDs)
    # Standard even-firing 10-cylinder order (72° interval)
    firing_order: List[int] = field(default_factory=lambda: [1, 6, 5, 10, 2, 7, 3, 8, 4, 9])

    # RPM and Throttle limits
    starter_rpm: float = 350.0
    idle_rpm: float = 800.0
    cruise_rpm: float = 2200.0
    max_rpm: float = 2800.0
    redline_rpm: float = 3000.0

    # Dynamic rates
    rpm_accel_rate: float = 1200.0      # RPM per second acceleration rate
    rpm_decel_rate: float = 900.0       # RPM per second deceleration rate
    starter_crank_time: float = 1.8     # seconds to crank before catching

    # Thermodynamic and fluid properties
    ambient_temp_c: float = 20.0
    target_operating_temp_c: float = 165.0
    max_safe_temp_c: float = 230.0
    warmup_rate_deg_per_sec: float = 12.0
    cooldown_rate_deg_per_sec: float = 3.5

    # Oil pressure (bar)
    idle_oil_pressure_bar: float = 2.2
    max_oil_pressure_bar: float = 5.5

    # Fuel flow (L/h)
    idle_fuel_flow_lph: float = 14.0
    max_fuel_flow_lph: float = 68.0

    # Valve timing (relative to cylinder 0-720° cycle)
    # Intake: 0° - 180°
    # Compression: 180° - 360°
    # Power: 360° - 540°
    # Exhaust: 540° - 720°
    spark_advance_deg: float = 22.0     # Fires at 360° - 22° = 338°
    spark_duration_deg: float = 30.0    # Spark visible for 30°

    @property
    def displacement_cc(self) -> float:
        """Total engine displacement in cubic centimeters."""
        import math
        single_cyl = math.pi * ((self.bore_mm / 20.0) ** 2) * (2 * self.crank_radius_mm / 10.0)
        return single_cyl * self.num_cylinders

    @property
    def displacement_liters(self) -> float:
        """Total displacement in liters."""
        return self.displacement_cc / 1000.0


DEFAULT_CONFIG = EngineConfig()
