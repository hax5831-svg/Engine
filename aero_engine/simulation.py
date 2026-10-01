"""Simulation runner, particle effects, and vibration model for AeroEngine."""

import math
import random
import time
from dataclasses import dataclass
from typing import List, Tuple
from aero_engine.config import EngineConfig, DEFAULT_CONFIG, EngineState, Stroke
from aero_engine.engine import Engine


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    char: str
    age: float
    lifetime: float
    color_pair: int = 0


class Simulation:
    """
    Coordinates engine simulation with dynamic visual particle effects,
    vibration, and timing.
    """

    SPEED_PRESETS = [0.01, 0.02, 0.05, 0.08, 0.15, 0.3, 0.5, 1.0]

    def __init__(self, config: EngineConfig = DEFAULT_CONFIG, initial_time_scale: float = 0.08):
        self.config = config
        self.engine = Engine(config)
        self.particles: List[Particle] = []
        self.time_scale: float = initial_time_scale
        self.is_paused: bool = False
        self.simulated_time: float = 0.0
        self.last_real_time: float = time.time()
        self.fps: float = 0.0
        self.frame_count: int = 0
        self._fps_timer: float = time.time()
        self._fps_frame_count: int = 0

        # Vibration model
        self.vibration_offset_x: int = 0
        self.vibration_offset_y: int = 0
        self._vibe_phase: float = 0.0

    def toggle_pause(self) -> None:
        """Toggle pause state."""
        self.is_paused = not self.is_paused

    def step_single_frame(self, dt: float = 0.025) -> None:
        """Step exactly one frame forward while paused."""
        effective_scale = self.time_scale if self.time_scale > 0 else 0.05
        scaled_dt = dt * effective_scale
        self.simulated_time += scaled_dt
        self.engine.step(scaled_dt)
        self._update_particles(scaled_dt)

    def speed_up(self) -> None:
        """Increase simulation visual speed."""
        for preset in self.SPEED_PRESETS:
            if preset > self.time_scale + 0.005:
                self.time_scale = preset
                return
        self.time_scale = min(2.0, self.time_scale * 1.5)

    def slow_down(self) -> None:
        """Decrease simulation visual speed."""
        for preset in reversed(self.SPEED_PRESETS):
            if preset < self.time_scale - 0.005:
                self.time_scale = preset
                return
        self.time_scale = max(0.005, self.time_scale / 1.5)

    def update(self, dt: float) -> None:
        """Advance the simulation by dt seconds."""
        if self.is_paused:
            self.vibration_offset_x = 0
            self.vibration_offset_y = 0
            return

        scaled_dt = dt * self.time_scale
        self.simulated_time += scaled_dt

        # Advance engine physics
        self.engine.step(scaled_dt)

        # Update FPS
        self.frame_count += 1
        self._fps_frame_count += 1
        now = time.time()
        if now - self._fps_timer >= 1.0:
            self.fps = self._fps_frame_count / (now - self._fps_timer)
            self._fps_frame_count = 0
            self._fps_timer = now

        # Update vibration
        self._update_vibration(scaled_dt)

        # Update & spawn particles
        self._update_particles(scaled_dt)

    def _update_vibration(self, dt: float) -> None:
        """Calculate subtle terminal vibration based on RPM and firing pulses."""
        rpm = self.engine.actual_rpm
        if rpm > 100.0:
            # Frequency scales with RPM
            freq = (rpm / 60.0) * (self.config.num_cylinders / 2.0)
            self._vibe_phase += freq * 2.0 * math.pi * dt
            # Subtle jitter amplitude (mostly 0, occasional +/- 1 at high RPM)
            intensity = min(1.0, rpm / self.config.max_rpm)
            if random.random() < 0.25 * intensity:
                self.vibration_offset_x = random.choice([-1, 0, 1])
                self.vibration_offset_y = random.choice([0, 0, 0, 1 if random.random() < 0.2 else 0])
            else:
                self.vibration_offset_x = 0
                self.vibration_offset_y = 0
        else:
            self.vibration_offset_x = 0
            self.vibration_offset_y = 0

    def spawn_exhaust_particle(self, origin_x: float, origin_y: float, intensity: float) -> None:
        """Spawn an exhaust particle drifting from cylinder exhaust port."""
        if len(self.particles) > 60:
            return  # Cap particle count for performance

        smoke_chars = ["·", "°", "o", "~", "*"]
        char = random.choice(smoke_chars[: max(1, int(intensity * len(smoke_chars)))])
        # Drift rearward/rightward along exhaust manifold with slight dispersion
        vx = random.uniform(0.5, 2.0)
        vy = random.uniform(-0.1, 0.3)
        lifetime = random.uniform(0.3, 0.8)
        p = Particle(
            x=origin_x,
            y=origin_y,
            vx=vx,
            vy=vy,
            char=char,
            age=0.0,
            lifetime=lifetime,
        )
        self.particles.append(p)

    def _update_particles(self, dt: float) -> None:
        """Update positions and ages of active particles."""
        alive: List[Particle] = []
        for p in self.particles:
            p.age += dt
            if p.age < p.lifetime:
                p.x += p.vx * dt * 10.0
                p.y += p.vy * dt * 8.0
                # Fade character over time
                if p.age / p.lifetime > 0.7:
                    p.char = "."
                elif p.age / p.lifetime > 0.4:
                    p.char = "o" if p.char not in (".", "~") else p.char
                alive.append(p)
        self.particles = alive

    def clear_particles(self) -> None:
        self.particles.clear()
