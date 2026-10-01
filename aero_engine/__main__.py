"""Main entry point for the AeroEngine 10-cylinder aircraft engine simulator."""

import argparse
import curses
import sys
import time
from aero_engine.config import EngineConfig, DEFAULT_CONFIG, EngineState
from aero_engine.simulation import Simulation
from aero_engine.renderer import TerminalRenderer


def parse_args():
    parser = argparse.ArgumentParser(
        prog="aero-engine",
        description="AeroEngine: 10-cylinder aircraft piston engine simulator rendered in terminal curses.",
    )
    parser.add_argument(
        "--rpm",
        type=float,
        default=None,
        help="Initial target RPM (e.g. 1800)",
    )
    parser.add_argument(
        "--throttle",
        type=float,
        default=None,
        help="Initial throttle percent 0-100 or ratio 0.0-1.0 (e.g. 60 or 0.6)",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=0.08,
        help="Visual animation speed multiplier (default: 0.08 for clear slow-motion observation; 1.0 for real-time)",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colors and use monochrome rendering",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Run in debug mode with diagnostic panel active on launch",
    )
    return parser.parse_args()


def run_app(stdscr, args):
    """Main curses simulation and rendering loop."""
    config = EngineConfig()
    sim = Simulation(config, initial_time_scale=args.speed)
    renderer = TerminalRenderer(stdscr, use_color=not args.no_color)

    if args.debug:
        renderer.show_diagnostics = True

    # Process CLI initial values
    if args.throttle is not None:
        throt = args.throttle / 100.0 if args.throttle > 1.0 else args.throttle
        sim.engine.set_throttle(throt)

    if args.rpm is not None:
        sim.engine.start()
        # Fast-crank starter into running
        sim.engine.actual_rpm = max(config.idle_rpm, args.rpm)
        sim.engine.state = EngineState.RUNNING
        sim.engine.set_target_rpm(args.rpm)

    target_fps = 25.0
    frame_duration = 1.0 / target_fps
    last_time = time.perf_counter()

    while True:
        current_time = time.perf_counter()
        dt = current_time - last_time
        last_time = current_time

        # Clamp dt to prevent simulation explosion during pause or terminal resize
        dt = min(0.1, dt)

        # 1. Handle keyboard inputs
        try:
            key = stdscr.getch()
        except curses.error:
            key = -1

        if key != -1:
            if key in (ord('q'), ord('Q'), 27):  # 'q', 'Q', or ESC
                break
            elif key == ord(' '):  # SPACE
                if sim.engine.state == EngineState.OFF:
                    sim.engine.start()
                elif sim.engine.state == EngineState.RUNNING:
                    sim.engine.stop()
            elif key in (ord('s'), ord('S')):
                sim.engine.stop()
            elif key in (ord('r'), ord('R')):
                sim.engine.reset()
                sim.clear_particles()
            elif key in (ord('p'), ord('P')):
                sim.toggle_pause()
            elif key in (ord('-'), ord('['), ord('_')):
                sim.slow_down()
            elif key in (ord('+'), ord('='), ord(']')):
                sim.speed_up()
            elif key in (ord('.'), ord('>')):
                if sim.is_paused:
                    sim.step_single_frame()
            elif key in (ord('d'), ord('D')):
                renderer.show_diagnostics = not renderer.show_diagnostics
                if renderer.show_diagnostics:
                    renderer.show_cycle_chart = False
            elif key in (ord('f'), ord('F')):
                renderer.show_cycle_chart = not renderer.show_cycle_chart
                if renderer.show_cycle_chart:
                    renderer.show_diagnostics = False
            elif key == curses.KEY_UP:
                sim.engine.adjust_rpm(50.0)
            elif key == curses.KEY_DOWN:
                sim.engine.adjust_rpm(-50.0)
            elif key == curses.KEY_RIGHT:
                sim.engine.adjust_throttle(0.05)
            elif key == curses.KEY_LEFT:
                sim.engine.adjust_throttle(-0.05)
            elif key == curses.KEY_RESIZE:
                curses.resizeterm(*stdscr.getmaxyx())

        # 2. Advance physics and simulation
        sim.update(dt)

        # 3. Render frame to terminal
        renderer.render(sim)

        # 4. Regulate frame rate
        elapsed = time.perf_counter() - current_time
        sleep_time = frame_duration - elapsed
        if sleep_time > 0.001:
            time.sleep(sleep_time)


def main():
    args = parse_args()
    try:
        curses.wrapper(lambda stdscr: run_app(stdscr, args))
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"\n[AeroEngine Error]: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
