"""Engine assembly, state machine, and telemetry for the AeroEngine simulator."""

import math
from typing import List, Dict, Optional
from aero_engine.config import EngineConfig, EngineState, Stroke, DEFAULT_CONFIG
from aero_engine.crankshaft import Crankshaft
from aero_engine.cylinder import Cylinder


class Engine:
    """
    Simulates a 10-cylinder 4-stroke aircraft engine.
    Maintains crankshaft, cylinders, state machine, throttle, and thermodynamic metrics.
    """

    def __init__(self, config: EngineConfig = DEFAULT_CONFIG):
        self.config = config
        self.state: EngineState = EngineState.OFF
        self.crankshaft = Crankshaft(config)

        # Control inputs
        self.throttle: float = 0.0          # 0.0 (0%) to 1.0 (100%)
        self.target_rpm: float = 0.0
        self.actual_rpm: float = 0.0

        # State machine timers
        self._starting_timer: float = 0.0
        self._has_fired: bool = False

        # Telemetry
        self.engine_temp_c: float = self.config.ambient_temp_c
        self.oil_pressure_bar: float = 0.0
        self.fuel_flow_lph: float = 0.0

        # Cylinders initialized according to firing order
        self.cylinders: List[Cylinder] = []
        self.cylinders_by_id: Dict[int, Cylinder] = {}
        self._init_cylinders()

    def _init_cylinders(self) -> None:
        """Create cylinder instances and map them according to the configured firing order."""
        self.cylinders.clear()
        self.cylinders_by_id.clear()

        # Build map: cylinder_id -> firing_order_index
        # Example firing order: [1, 6, 5, 10, 2, 7, 3, 8, 4, 9]
        order_index_by_cyl_id = {}
        for idx, cyl_id in enumerate(self.config.firing_order):
            order_index_by_cyl_id[cyl_id] = idx

        # Create 10 cylinders sorted by cylinder ID 1..10
        for cyl_id in range(1, self.config.num_cylinders + 1):
            firing_idx = order_index_by_cyl_id.get(cyl_id, cyl_id - 1)
            cyl = Cylinder(cyl_id, firing_idx, self.config)
            self.cylinders.append(cyl)
            self.cylinders_by_id[cyl_id] = cyl

    def set_firing_order(self, new_order: List[int]) -> None:
        """Update firing order and re-index cylinders."""
        if len(new_order) != self.config.num_cylinders:
            raise ValueError(f"Firing order must have {self.config.num_cylinders} cylinders.")
        self.config.firing_order = list(new_order)
        self._init_cylinders()
        self._update_cylinders()

    def start(self) -> None:
        """Initiate the engine start sequence."""
        if self.state in (EngineState.OFF, EngineState.STOPPING):
            self.state = EngineState.STARTING
            self._starting_timer = 0.0
            self._has_fired = False

    def stop(self) -> None:
        """Cut ignition and fuel to stop the engine."""
        if self.state in (EngineState.RUNNING, EngineState.STARTING):
            self.state = EngineState.STOPPING

    def reset(self) -> None:
        """Instant reset of engine state to initial conditions."""
        self.state = EngineState.OFF
        self.crankshaft.reset()
        self.actual_rpm = 0.0
        self.target_rpm = 0.0
        self.throttle = 0.0
        self._starting_timer = 0.0
        self._has_fired = False
        self.engine_temp_c = self.config.ambient_temp_c
        self.oil_pressure_bar = 0.0
        self.fuel_flow_lph = 0.0
        self._update_cylinders()

    def set_throttle(self, value: float) -> None:
        """Set throttle position clamped between 0.0 and 1.0."""
        self.throttle = max(0.0, min(1.0, value))
        self._recalculate_target_rpm()

    def adjust_throttle(self, delta: float) -> None:
        """Increment or decrement throttle position."""
        self.set_throttle(self.throttle + delta)

    def set_target_rpm(self, rpm: float) -> None:
        """Set target RPM directly, updating throttle accordingly."""
        rpm = max(self.config.idle_rpm, min(self.config.max_rpm, rpm))
        span = self.config.max_rpm - self.config.idle_rpm
        if span > 0:
            self.throttle = (rpm - self.config.idle_rpm) / span
        self.target_rpm = rpm

    def adjust_rpm(self, delta_rpm: float) -> None:
        """Increment or decrement target RPM."""
        if self.state == EngineState.RUNNING:
            current_target = self.target_rpm if self.target_rpm > 0 else self.actual_rpm
            self.set_target_rpm(current_target + delta_rpm)

    def _recalculate_target_rpm(self) -> None:
        """Calculate target RPM based on current throttle and state."""
        if self.state == EngineState.RUNNING:
            span = self.config.max_rpm - self.config.idle_rpm
            self.target_rpm = self.config.idle_rpm + self.throttle * span
        elif self.state == EngineState.STARTING:
            if not self._has_fired:
                self.target_rpm = self.config.starter_rpm
            else:
                self.target_rpm = self.config.idle_rpm
        else:
            self.target_rpm = 0.0

    def step(self, dt: float) -> None:
        """Advance the engine simulation by dt seconds."""
        if dt <= 0.0:
            return

        # 1. State machine transitions & RPM dynamics
        self._update_rpm_and_state(dt)

        # 2. Advance crankshaft rotation
        self.crankshaft.set_rpm(self.actual_rpm)
        self.crankshaft.advance(dt)

        # 3. Synchronize cylinders
        self._update_cylinders()

        # 4. Update thermal and fluid dynamics
        self._update_telemetry(dt)

    def _update_rpm_and_state(self, dt: float) -> None:
        """Handle state transitions and smooth RPM inertia."""
        if self.state == EngineState.OFF:
            self.target_rpm = 0.0
            self.actual_rpm = 0.0

        elif self.state == EngineState.STARTING:
            self._starting_timer += dt
            if self._starting_timer < self.config.starter_crank_time:
                # Cranking up to starter RPM
                self.target_rpm = self.config.starter_rpm
                accel = self.config.rpm_accel_rate * 0.6
                if self.actual_rpm < self.target_rpm:
                    self.actual_rpm = min(self.target_rpm, self.actual_rpm + accel * dt)
            else:
                # Engine catches fire!
                self._has_fired = True
                self._recalculate_target_rpm()
                accel = self.config.rpm_accel_rate
                self.actual_rpm += accel * dt
                if self.actual_rpm >= self.config.idle_rpm * 0.95:
                    self.state = EngineState.RUNNING

        elif self.state == EngineState.RUNNING:
            self._recalculate_target_rpm()
            diff = self.target_rpm - self.actual_rpm
            if diff > 0:
                step = self.config.rpm_accel_rate * dt
                self.actual_rpm = min(self.target_rpm, self.actual_rpm + step)
            elif diff < 0:
                step = self.config.rpm_decel_rate * dt
                self.actual_rpm = max(self.target_rpm, self.actual_rpm - step)

        elif self.state == EngineState.STOPPING:
            self.target_rpm = 0.0
            decel = self.config.rpm_decel_rate * 1.2
            self.actual_rpm = max(0.0, self.actual_rpm - decel * dt)
            if self.actual_rpm <= 5.0:
                self.actual_rpm = 0.0
                self.state = EngineState.OFF

    def _update_cylinders(self) -> None:
        """Update each cylinder based on its firing offset and the crankshaft angle."""
        is_firing = (self.state == EngineState.RUNNING) or (
            self.state == EngineState.STARTING and self._has_fired
        )

        for cyl in self.cylinders:
            phase = self.crankshaft.get_cylinder_phase(cyl.firing_order_index)
            cyl.update(phase, is_engine_firing=is_firing)

    def _update_telemetry(self, dt: float) -> None:
        """Compute live temperature, oil pressure, and fuel flow."""
        # 1. Engine Temperature
        if self.actual_rpm > 100.0:
            load_factor = (self.actual_rpm / self.config.max_rpm) * 0.6 + self.throttle * 0.4
            target_temp = self.config.ambient_temp_c + (
                self.config.target_operating_temp_c - self.config.ambient_temp_c
            ) * load_factor
            if self.engine_temp_c < target_temp:
                self.engine_temp_c += self.config.warmup_rate_deg_per_sec * dt * load_factor
            else:
                self.engine_temp_c -= self.config.cooldown_rate_deg_per_sec * dt * 0.3
        else:
            # Cool down towards ambient
            if self.engine_temp_c > self.config.ambient_temp_c:
                cooldown = self.config.cooldown_rate_deg_per_sec * dt
                self.engine_temp_c = max(self.config.ambient_temp_c, self.engine_temp_c - cooldown)

        # 2. Oil Pressure
        # Mechanical oil pump driven by crankshaft
        if self.actual_rpm <= 10.0:
            self.oil_pressure_bar = 0.0
        else:
            rpm_ratio = min(1.0, self.actual_rpm / self.config.max_rpm)
            # Pressure relief valve profile
            p_span = self.config.max_oil_pressure_bar - self.config.idle_oil_pressure_bar
            self.oil_pressure_bar = self.config.idle_oil_pressure_bar * min(1.0, self.actual_rpm / self.config.idle_rpm) + (
                p_span * (rpm_ratio ** 0.7)
            )

        # 3. Fuel Flow (L/h)
        if self.state in (EngineState.RUNNING, EngineState.STARTING) and self.actual_rpm > 50.0:
            f_span = self.config.max_fuel_flow_lph - self.config.idle_fuel_flow_lph
            norm_rpm = (self.actual_rpm - self.config.idle_rpm) / (self.config.max_rpm - self.config.idle_rpm)
            norm_rpm = max(0.0, min(1.0, norm_rpm))
            self.fuel_flow_lph = self.config.idle_fuel_flow_lph + (norm_rpm * 0.6 + self.throttle * 0.4) * f_span
        else:
            self.fuel_flow_lph = 0.0

    @property
    def crank_angle(self) -> float:
        """Current master crank angle [0.0, 720.0)."""
        return self.crankshaft.angle_deg

    def get_active_combustion_count(self) -> int:
        """Number of cylinders currently in combustion/power stroke."""
        return sum(1 for c in self.cylinders if c.combustion_state)

    def get_active_spark_count(self) -> int:
        """Number of cylinders currently sparking."""
        return sum(1 for c in self.cylinders if c.ignition_state)
