"""Curses-based terminal renderer for the AeroEngine 10-cylinder simulator."""

import curses
import math
from typing import Optional, List
from aero_engine.config import EngineConfig, EngineState, Stroke, DEFAULT_CONFIG
from aero_engine.engine import Engine
from aero_engine.simulation import Simulation, Particle


class TerminalRenderer:
    """
    Renders high-fps, flicker-free terminal animation of the 10-cylinder aircraft engine.
    """

    # Color pair IDs
    CP_DEFAULT = 0
    CP_CYAN = 1       # Intake / Air / Telemetry
    CP_YELLOW = 2     # Compression / Fuel
    CP_RED = 3        # Combustion / Flame / Redline
    CP_MAGENTA = 4    # Exhaust gas
    CP_GREEN = 5      # Running / Valves open
    CP_WHITE = 6      # Mechanical parts / Crankshaft / Piston
    CP_FLASH = 7      # Ignition flash highlight
    CP_BAR_FILL = 8   # Dashboard bars

    def __init__(self, stdscr, use_color: bool = True):
        self.stdscr = stdscr
        try:
            has_colors = curses.has_colors()
        except curses.error:
            has_colors = False
        self.use_color = use_color and has_colors
        self.show_diagnostics: bool = False
        self.show_cycle_chart: bool = False

        self._init_curses()

    def _init_curses(self) -> None:
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        try:
            self.stdscr.nodelay(True)
            self.stdscr.keypad(True)
        except (curses.error, AttributeError):
            pass
        try:
            curses.noecho()
            curses.cbreak()
        except curses.error:
            pass

        if self.use_color:
            try:
                curses.start_color()
                curses.use_default_colors()
                curses.init_pair(self.CP_CYAN, curses.COLOR_CYAN, -1)
                curses.init_pair(self.CP_YELLOW, curses.COLOR_YELLOW, -1)
                curses.init_pair(self.CP_RED, curses.COLOR_RED, -1)
                curses.init_pair(self.CP_MAGENTA, curses.COLOR_MAGENTA, -1)
                curses.init_pair(self.CP_GREEN, curses.COLOR_GREEN, -1)
                curses.init_pair(self.CP_WHITE, curses.COLOR_WHITE, -1)
                curses.init_pair(self.CP_FLASH, curses.COLOR_YELLOW, -1)
                curses.init_pair(self.CP_BAR_FILL, curses.COLOR_GREEN, -1)
            except curses.error:
                self.use_color = False

    def color(self, pair_id: int, bold: bool = False) -> int:
        if not self.use_color:
            return curses.A_BOLD if bold else curses.A_NORMAL
        attr = curses.color_pair(pair_id)
        if bold:
            attr |= curses.A_BOLD
        return attr

    def safe_addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        """Safely write string to window without crashing on terminal edge."""
        max_y, max_x = self.stdscr.getmaxyx()
        if 0 <= y < max_y and 0 <= x < max_x:
            # Clip string so it doesn't wrap past screen width
            space = max_x - x
            if space > 0:
                clipped = text[:space]
                try:
                    self.stdscr.addstr(y, x, clipped, attr)
                except curses.error:
                    pass

    def render(self, sim: Simulation) -> None:
        """Render complete engine frame."""
        self.stdscr.erase()
        max_y, max_x = self.stdscr.getmaxyx()

        # Check for minimum terminal size
        if max_y < 24 or max_x < 78:
            self._render_compact_fallback(sim, max_y, max_x)
            self.stdscr.noutrefresh()
            try:
                curses.doupdate()
            except curses.error:
                pass
            return

        engine = sim.engine

        # 1. Top Header Banner
        self._render_header(0, 0, max_x)

        # 2. Main Telemetry Dashboard
        dash_bottom = self._render_dashboard(engine, sim, 1, 0, max_x)

        # 3. 10-Cylinder Mechanical Visualizer
        cyl_bottom = self._render_cylinders(engine, sim, dash_bottom + 1, 0, max_x)

        # 4. Crankshaft End-View & Cylinder Status Table
        table_top = cyl_bottom + 1
        table_bottom = self._render_crank_and_table(engine, table_top, 0, max_x)

        # 5. Exhaust Particles (Strictly bounded between dashboard and table, cannot overwrite text)
        self._render_particles(sim, min_y=dash_bottom, max_y_allowed=table_top)

        # 6. Overlays (Diagnostics or Cycle Chart)
        if self.show_diagnostics:
            self._render_diagnostics_overlay(engine, max_y, max_x)
        elif self.show_cycle_chart:
            self._render_cycle_chart_overlay(engine, max_y, max_x)

        # 7. Bottom Navigation & Controls Help Bar
        self._render_footer(max_y - 1, max_x)

        self.stdscr.noutrefresh()
        try:
            curses.doupdate()
        except curses.error:
            pass

    def _render_header(self, y: int, x: int, width: int) -> None:
        title = " ◆ AERO-10 AIRCRAFT PISTON ENGINE SIMULATOR ◆ "
        bar = "═" * max(0, (width - len(title)) // 2)
        full_line = f"{bar}{title}{bar}"[:width]
        self.safe_addstr(max(0, y), max(0, x), full_line, self.color(self.CP_CYAN, bold=True))

    def _render_dashboard(self, engine: Engine, sim: Simulation, y: int, x: int, width: int) -> int:
        """Render live gauges and telemetry."""
        cfg = engine.config
        state_color = {
            EngineState.OFF: self.color(self.CP_WHITE),
            EngineState.STARTING: self.color(self.CP_YELLOW, bold=True),
            EngineState.RUNNING: self.color(self.CP_GREEN, bold=True),
            EngineState.STOPPING: self.color(self.CP_RED, bold=True),
        }.get(engine.state, self.color(self.CP_WHITE))

        # Box border
        self.safe_addstr(y, x, "┌" + "─" * (width - 2) + "┐", self.color(self.CP_WHITE))

        # Row 1: State, RPM, Throttle, Crank Angle
        rpm_ratio = min(1.0, engine.actual_rpm / cfg.redline_rpm)
        rpm_bar = self._make_bar(rpm_ratio, 12)
        throt_bar = self._make_bar(engine.throttle, 10)

        r1_part1 = f" STATE: "
        r1_part2 = f"[{engine.state.value:^8}]"
        r1_part3 = f"  RPM: {int(engine.actual_rpm):4d} [{rpm_bar}]"
        r1_part4 = f"  THROTTLE: {int(engine.throttle * 100):3d}% [{throt_bar}]"
        r1_part5 = f"  CRANK: {int(engine.crank_angle):03d}°"

        self.safe_addstr(y + 1, x, "│", self.color(self.CP_WHITE))
        col = x + 2
        self.safe_addstr(y + 1, col, r1_part1, self.color(self.CP_WHITE, bold=True))
        col += len(r1_part1)
        self.safe_addstr(y + 1, col, r1_part2, state_color)
        col += len(r1_part2)
        self.safe_addstr(y + 1, col, r1_part3, self.color(self.CP_CYAN, bold=True))
        col += len(r1_part3)
        self.safe_addstr(y + 1, col, r1_part4, self.color(self.CP_YELLOW, bold=True))
        col += len(r1_part4)
        self.safe_addstr(y + 1, col, r1_part5, self.color(self.CP_WHITE, bold=True))
        self.safe_addstr(y + 1, x + width - 1, "│", self.color(self.CP_WHITE))

        # Row 2: Engine Temp, Oil Pressure, Fuel Flow, Combustion, Speed, FPS
        temp_col = self.CP_GREEN if engine.engine_temp_c < 190.0 else self.CP_RED
        oil_col = self.CP_GREEN if engine.oil_pressure_bar > 1.8 else (self.CP_YELLOW if engine.actual_rpm > 50 else self.CP_WHITE)
        speed_str = "PAUSED" if sim.is_paused else f"{sim.time_scale:.2f}x"

        r2_text = (
            f"  TEMP: {engine.engine_temp_c:5.1f}°C"
            f"   OIL: {engine.oil_pressure_bar:4.1f} bar"
            f"   FUEL: {engine.fuel_flow_lph:4.1f} L/h"
            f"   FIRING: {engine.get_active_combustion_count()}/10"
            f"   SPEED: {speed_str:>6}"
            f"   FPS: {int(sim.fps):2d}"
        )
        self.safe_addstr(y + 2, x, "│", self.color(self.CP_WHITE))
        self.safe_addstr(y + 2, x + 2, r2_text, self.color(self.CP_WHITE))
        self.safe_addstr(y + 2, x + width - 1, "│", self.color(self.CP_WHITE))

        self.safe_addstr(y + 3, x, "└" + "─" * (width - 2) + "┘", self.color(self.CP_WHITE))
        return y + 3

    def _make_bar(self, ratio: float, length: int) -> str:
        ratio = max(0.0, min(1.0, ratio))
        filled = int(round(ratio * length))
        return "█" * filled + "░" * (length - filled)

    def _render_cylinders(self, engine: Engine, sim: Simulation, y: int, x: int, width: int) -> int:
        """
        Renders all 10 cylinders with cylinder head, spark plug, valves,
        combustion flame, moving piston, connecting rod, and crankshaft journal.
        """
        num_cyls = 10
        cyl_w = 7   # Width of each cylinder
        spacing = 1
        total_engine_w = num_cyls * cyl_w + (num_cyls - 1) * spacing
        start_x = max(1, x + (width - total_engine_w) // 2)

        bore_height = 5  # Height of cylinder bore travel

        # Row 0: Cylinder Header & Numbers (#01 .. #10)
        # Row 1: Intake & Exhaust Valves: [I] [E]
        # Row 2: Cylinder Head & Spark Plug: ┌──*──┐
        # Rows 3..7: Cylinder walls and Piston: │     │
        # Row 8: Crankcase bed / journal: └──O──┘

        for i, cyl in enumerate(engine.cylinders):
            cx = start_x + i * (cyl_w + spacing)

            # Spawn exhaust particle if exhaust valve is open and engine firing
            if cyl.exhaust_state and cyl.exhaust_intensity > 0.2:
                sim.spawn_exhaust_particle(cx + 4, y + 1, cyl.exhaust_intensity)

            # 1. Cylinder Number & Firing order indicator
            is_active_firing = cyl.combustion_state
            header_attr = self.color(self.CP_RED, bold=True) if is_active_firing else self.color(self.CP_WHITE, bold=True)
            self.safe_addstr(y, cx, f" #{cyl.cylinder_id:02d} ", header_attr)

            # 2. Valves row: I E
            i_attr = self.color(self.CP_GREEN, bold=True) if cyl.intake_valve_open else self.color(self.CP_WHITE)
            e_attr = self.color(self.CP_MAGENTA, bold=True) if cyl.exhaust_valve_open else self.color(self.CP_WHITE)
            i_char = "▲" if cyl.intake_valve_open else "·"
            e_char = "▲" if cyl.exhaust_valve_open else "·"
            self.safe_addstr(y + 1, cx, f" {i_char}I E{e_char} ", self.color(self.CP_WHITE))
            self.safe_addstr(y + 1, cx + 1, i_char, i_attr)
            self.safe_addstr(y + 1, cx + 2, "I", i_attr)
            self.safe_addstr(y + 1, cx + 4, "E", e_attr)
            self.safe_addstr(y + 1, cx + 5, e_char, e_attr)

            # 3. Cylinder Head with Spark Plug
            spark_attr = self.color(self.CP_FLASH, bold=True) if cyl.ignition_state else self.color(self.CP_YELLOW)
            spark_char = "⚡" if (cyl.ignition_state and self.use_color) else ("*" if cyl.ignition_state else "-")
            self.safe_addstr(y + 2, cx, "┌──", self.color(self.CP_WHITE))
            self.safe_addstr(y + 2, cx + 3, spark_char, spark_attr)
            self.safe_addstr(y + 2, cx + 4, "──┐", self.color(self.CP_WHITE))

            # 4. Piston Travel Bore (height = bore_height)
            # normalized_height: 1.0 = TDC (top, row 0), 0.0 = BDC (bottom, row bore_height-1)
            piston_travel_idx = int(round((1.0 - cyl.normalized_height) * (bore_height - 2)))
            piston_travel_idx = max(0, min(bore_height - 2, piston_travel_idx))

            for row in range(bore_height):
                by = y + 3 + row
                if row < piston_travel_idx:
                    # Space above piston: Combustion flame or intake air
                    if cyl.combustion_state:
                        flame_chars = " *#* " if cyl.combustion_intensity > 0.5 else "  *  "
                        self.safe_addstr(by, cx, f"│{flame_chars}│", self.color(self.CP_RED, bold=True))
                    elif cyl.current_stroke == Stroke.INTAKE:
                        self.safe_addstr(by, cx, "│ · · │", self.color(self.CP_CYAN))
                    elif cyl.current_stroke == Stroke.COMPRESSION:
                        self.safe_addstr(by, cx, "│ ≈≈≈ │", self.color(self.CP_YELLOW))
                    elif cyl.current_stroke == Stroke.EXHAUST:
                        self.safe_addstr(by, cx, "│ o.o │", self.color(self.CP_MAGENTA))
                    else:
                        self.safe_addstr(by, cx, "│     │", self.color(self.CP_WHITE))

                elif row == piston_travel_idx:
                    # Piston Crown
                    piston_str = "│[===]│"
                    p_attr = self.color(self.CP_WHITE, bold=True)
                    if cyl.combustion_state:
                        p_attr = self.color(self.CP_RED, bold=True)
                    self.safe_addstr(by, cx, piston_str, p_attr)

                elif row == piston_travel_idx + 1:
                    # Connecting Rod top
                    rod_tilt = cyl.rod_angle_rad
                    rod_char = "/" if rod_tilt < -0.1 else ("\\" if rod_tilt > 0.1 else "│")
                    self.safe_addstr(by, cx, f"│  {rod_char}  │", self.color(self.CP_WHITE))

                else:
                    # Lower crankcase void
                    self.safe_addstr(by, cx, "│     │", self.color(self.CP_WHITE))

            # 5. Crankcase Bottom and Crankpin Journal
            crank_y = y + 3 + bore_height
            crank_pin_offset = int(round(math.sin(math.radians(cyl.mechanical_angle))))
            # Offset -1, 0, +1
            pin_chars = {
                -1: "└(O)──┘",
                 0: "└──(O)┘",
                 1: "└───(O)",
            }.get(crank_pin_offset, "└──(O)┘")
            self.safe_addstr(crank_y, cx, pin_chars, self.color(self.CP_WHITE, bold=True))

        return y + 3 + bore_height

    def _render_crank_and_table(self, engine: Engine, y: int, x: int, width: int) -> int:
        """
        Renders the rotating Crankshaft End-View disc alongside the 10-cylinder telemetry table.
        """
        # 1. Crankshaft Rotating Disc (6x6 characters)
        # Crank angle mod 360
        angle = engine.crank_angle % 360.0
        rad = math.radians(angle)
        # Vector on 5x5 grid
        arm_x = int(round(2.0 * math.cos(rad)))
        arm_y = int(round(-1.2 * math.sin(rad)))  # Curses Y is inverted

        disc = [
            "  CRANK-SHAFT ",
            "   .─────.    ",
            "  /   │   \\   ",
            " │────*────│  ",
            "  \\   │   /   ",
            "   '─────'    ",
        ]
        disc_w = 14
        for row_idx, line in enumerate(disc):
            self.safe_addstr(y + row_idx, x + 2, line, self.color(self.CP_CYAN))

        # Draw rotating crank arm throw on top of center '*' at (y+3, x+2+6)
        center_y = y + 3
        center_x = x + 8
        target_y = center_y + arm_y
        target_x = center_x + arm_x
        self.safe_addstr(target_y, target_x, "●", self.color(self.CP_WHITE, bold=True))
        self.safe_addstr(y + 6, x + 2, f"  θ={int(angle):03d}° / 720°", self.color(self.CP_WHITE, bold=True))

        # 2. Cylinder Status Table
        table_x = x + disc_w + 3
        table_w = width - table_x - 1

        # Table header: CYL ID
        cyl_hdr = "CYL : " + "  ".join(f"#{c.cylinder_id:02d}" for c in engine.cylinders)
        self.safe_addstr(y, table_x, cyl_hdr[:table_w], self.color(self.CP_WHITE, bold=True))

        # Stroke Row
        self.safe_addstr(y + 1, table_x, "STRK: ", self.color(self.CP_WHITE, bold=True))
        c_offset = table_x + 6
        for c in engine.cylinders:
            stroke_code = {
                Stroke.INTAKE: ("INTK", self.CP_CYAN),
                Stroke.COMPRESSION: ("COMP", self.CP_YELLOW),
                Stroke.POWER: ("POWR", self.CP_RED),
                Stroke.EXHAUST: ("EXHT", self.CP_MAGENTA),
            }[c.current_stroke]
            txt, cp = stroke_code
            self.safe_addstr(y + 1, c_offset, txt, self.color(cp, bold=True))
            c_offset += len(txt) + 1

        # Phase / Angle Row
        phase_str = "PHAS: " + " ".join(f"{int(c.crank_phase):03d}°" for c in engine.cylinders)
        self.safe_addstr(y + 2, table_x, phase_str[:table_w], self.color(self.CP_CYAN))

        # Pressure Row (bar)
        press_str = "PRES: " + " ".join(f"{int(c.pressure_bar):02d}b " for c in engine.cylinders)
        self.safe_addstr(y + 3, table_x, press_str[:table_w], self.color(self.CP_YELLOW))

        # Firing Order Row
        order_str = "FIRE: " + "  ".join(f" {c.firing_order_index + 1} " for c in engine.cylinders)
        self.safe_addstr(y + 4, table_x, order_str[:table_w], self.color(self.CP_GREEN))

        return y + 6

    def _render_particles(self, sim: Simulation, min_y: int, max_y_allowed: int) -> None:
        """Render active exhaust particles drifting in terminal without overwriting text."""
        max_y, max_x = self.stdscr.getmaxyx()
        for p in sim.particles:
            px = int(round(p.x))
            py = int(round(p.y))
            # Strictly confine particles away from header, dashboard, and tables
            if py <= min_y or py >= max_y_allowed:
                continue
            if 0 <= py < max_y and 0 <= px < max_x:
                # Never overwrite existing text, borders, or numbers
                try:
                    if hasattr(self.stdscr, "inch"):
                        ch = self.stdscr.inch(py, px) & curses.A_CHARTEXT
                        if ch not in (ord(' '), 0):
                            continue
                except (curses.error, TypeError):
                    pass
                color_id = self.CP_MAGENTA if p.age < 0.4 else self.CP_WHITE
                self.safe_addstr(py, px, p.char, self.color(color_id))

    def _render_diagnostics_overlay(self, engine: Engine, max_y: int, max_x: int) -> None:
        """Overlay modal displaying comprehensive thermodynamic and mechanical diagnostics."""
        w = min(68, max_x - 4)
        h = 16
        start_y = max(1, (max_y - h) // 2)
        start_x = max(1, (max_x - w) // 2)

        cfg = engine.config
        lines = [
            "┌" + "─" * (w - 2) + "┐",
            f"│{' AERO-10 DETAILED ENGINE DIAGNOSTICS ':^{w-2}}│",
            "├" + "─" * (w - 2) + "┤",
            f"│  Configuration: 10-Cylinder 4-Stroke Aero Piston Engine{' ' * (w - 61)}│",
            f"│  Bore x Stroke: {cfg.bore_mm:.0f}mm x {2*cfg.crank_radius_mm:.0f}mm  |  Rod Length: {cfg.rod_length_mm:.0f}mm{' ' * (w - 58)}│",
            f"│  Displacement:  {cfg.displacement_liters:.2f} Liters ({cfg.displacement_cc:.0f} cc){' ' * (w - 47)}│",
            f"│  Compression:   {cfg.compression_ratio:.1f}:1  |  Crank-Slider L/r: {cfg.rod_length_mm / cfg.crank_radius_mm:.2f}{' ' * (w - 53)}│",
            f"│  Firing Order:  {'-'.join(str(x) for x in cfg.firing_order)}{' ' * (w - 38)}│",
            f"│  Firing Delta:  72.0° between cylinders (720° / 10){' ' * (w - 55)}│",
            f"│  Spark Timing:  {cfg.spark_advance_deg:.1f}° BTDC (Window: 338° - 368°){' ' * (w - 58)}│",
            f"│  Operating RPM: Idle {cfg.idle_rpm:.0f} / Cruise {cfg.cruise_rpm:.0f} / Max {cfg.max_rpm:.0f}{' ' * (w - 57)}│",
            f"│  Oil Pressure:  {engine.oil_pressure_bar:.2f} bar (Normal: 2.0 - 5.5 bar){' ' * (w - 55)}│",
            f"│  Fuel Flow:     {engine.fuel_flow_lph:.1f} L/h  |  Temp: {engine.engine_temp_c:.1f}°C{' ' * (w - 49)}│",
            "├" + "─" * (w - 2) + "┤",
            f"│{' Press [D] to close diagnostics ':^{w-2}}│",
            "└" + "─" * (w - 2) + "┘",
        ]

        for i, line in enumerate(lines):
            self.safe_addstr(start_y + i, start_x, line, self.color(self.CP_CYAN, bold=True))

    def _render_cycle_chart_overlay(self, engine: Engine, max_y: int, max_x: int) -> None:
        """Overlay showing the 720° 4-stroke cycle status bar for all 10 cylinders."""
        w = min(74, max_x - 4)
        h = 16
        start_y = max(1, (max_y - h) // 2)
        start_x = max(1, (max_x - w) // 2)

        self.safe_addstr(start_y, start_x, "┌" + "─" * (w - 2) + "┐", self.color(self.CP_YELLOW, bold=True))
        self.safe_addstr(start_y + 1, start_x, f"│{' 720° FOUR-STROKE CYCLE SYNCHRONIZATION CHART ':^{w-2}}│", self.color(self.CP_YELLOW, bold=True))
        self.safe_addstr(start_y + 2, start_x, "├" + "─" * (w - 2) + "┤", self.color(self.CP_YELLOW))

        # Draw 720° ruler: 0° .. 180° .. 360° .. 540° .. 720°
        ruler = "│ CYL  [0°:INTK][180°:COMP][360°:POWR][540°:EXHT] CRANK PHASE "
        self.safe_addstr(start_y + 3, start_x, ruler[:w-1] + "│", self.color(self.CP_WHITE, bold=True))

        for idx, cyl in enumerate(engine.cylinders):
            cy = start_y + 4 + idx
            bar_len = 36
            # Mark current phase position in 720° cycle
            marker_pos = int((cyl.crank_phase / 720.0) * bar_len)
            marker_pos = max(0, min(bar_len - 1, marker_pos))

            bar_chars = list("░" * 9 + "▒" * 9 + "█" * 9 + "▓" * 9)
            bar_chars[marker_pos] = "●"
            bar_str = "".join(bar_chars)

            line = f"│ #{cyl.cylinder_id:02d}   [{bar_str}]  {int(cyl.crank_phase):03d}° {cyl.current_stroke.value[:4]} "
            self.safe_addstr(cy, start_x, line[:w-1] + "│", self.color(self.CP_WHITE))

        self.safe_addstr(start_y + 14, start_x, "├" + "─" * (w - 2) + "┤", self.color(self.CP_YELLOW))
        self.safe_addstr(start_y + 15, start_x, f"│{' Press [F] to close cycle chart ':^{w-2}}│", self.color(self.CP_YELLOW, bold=True))

    def _render_footer(self, y: int, width: int) -> None:
        """Render controls help footer."""
        msg = " [↑/↓] RPM  [←/→] Throttle  [-/+] Speed  [P] Pause  [SPACE] Start/Stop  [D] Diag  [F] Firing  [Q] Quit "
        bar = "═" * max(0, (width - len(msg)) // 2)
        full = f"{bar}{msg}{bar}"[:width]
        self.safe_addstr(y, 0, full, self.color(self.CP_WHITE, bold=True))

    def _render_compact_fallback(self, sim: Simulation, max_y: int, max_x: int) -> None:
        """Fallback display when terminal is smaller than 78x24."""
        engine = sim.engine
        lines = [
            "AERO-10 ENGINE SIMULATOR (Compact Mode)",
            f"Terminal too small: {max_x}x{max_y} (Require 78x24)",
            f"State: {engine.state.value} | RPM: {int(engine.actual_rpm)}",
            f"Throttle: {int(engine.throttle * 100)}% | Crank: {int(engine.crank_angle)}°",
            f"Temp: {engine.engine_temp_c:.1f}°C | Oil: {engine.oil_pressure_bar:.1f} bar",
            "",
            "CYLINDER STATUS:",
        ]
        for c in engine.cylinders[:5]:
            lines.append(f" #{c.cylinder_id:02d}: {c.current_stroke.value} (p={int(c.crank_phase)}°)")
        lines.append("Controls: [SPACE] Start, [S] Stop, [↑/↓] RPM, [Q] Quit")

        for idx, line in enumerate(lines):
            if idx < max_y:
                self.safe_addstr(idx, 0, line[:max_x], self.color(self.CP_CYAN))
