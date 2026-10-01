# AeroEngine

A visually impressive **10-cylinder aircraft piston engine simulator** rendered entirely in the terminal with standard Python `curses`.

It features real mechanical kinematics, thermodynamic telemetry, and dynamic terminal visual effects including moving pistons, angular connecting rods, a rotating crankshaft, intake/exhaust valve lifts, spark ignition flashes, combustion flames, and drifting exhaust smoke particles.

---

## Kinematics & Simulation Model

- **10 Cylinders & 720° Four-Stroke Cycle**:
  - `INTAKE` (0° – 180°): Piston travels from TDC to BDC, intake valve open.
  - `COMPRESSION` (180° – 360°): Piston travels BDC to TDC, polytropic pressure rise.
  - `POWER` (360° – 540°): Spark ignition near TDC (338°–368°), explosive expansion flame.
  - `EXHAUST` (540° – 720°): Piston travels BDC to TDC, exhaust valve open, smoke ejected.
- **Exact Crank-Slider Geometry**:
  $$\text{x}(\theta) = r \cos(\theta) + \sqrt{L^2 - r^2 \sin^2(\theta)}$$
  Where $r = 70.0\,\text{mm}$ (crank radius, $140\,\text{mm}$ stroke) and $L = 210.0\,\text{mm}$ (connecting rod length).
- **Connecting Rod Angle**:
  $$\beta = \arcsin\left(\frac{r}{L} \sin(\theta)\right)$$
- **Even-Interval Firing Order**:
  - Configurable 10-cylinder firing sequence (default: `1-6-5-10-2-7-3-8-4-9`).
  - Cylinder interval: $\frac{720^\circ}{10} = 72^\circ$.
- **Thermodynamics & Telemetry**:
  - Dynamic RPM inertia (smooth starter crank ramp, acceleration, and deceleration).
  - Cylinder Head Temperature (°C) with load heating and ambient cooling.
  - Crankcase Oil Pressure (bar) with relief valve curve.
  - AvGas Fuel Flow (L/h).
  - Subtle RPM-dependent terminal vibration and exhaust particle system.

---

## Interactive Controls

| Key | Action |
|:---|:---|
| <kbd>SPACE</kbd> | Start / Stop engine (cranks starter motor, ramps to idle) |
| <kbd>↑</kbd> / <kbd>↓</kbd> | Increase / decrease target RPM |
| <kbd>←</kbd> / <kbd>→</kbd> | Decrease / increase throttle position |
| <kbd>-</kbd> or <kbd>[</kbd> | **Slow down** visual simulation speed (ultra slow-mo) |
| <kbd>+</kbd> or <kbd>]</kbd> | **Speed up** visual simulation speed |
| <kbd>P</kbd> | **Pause** / Resume simulation freeze-frame |
| <kbd>.</kbd> or <kbd>></kbd> | **Step single frame** forward (when paused) |
| <kbd>S</kbd> | Stop engine (cuts ignition and fuel, decelerates to 0) |
| <kbd>R</kbd> | Reset engine to initial cold state |
| <kbd>D</kbd> | Toggle detailed diagnostics overlay |
| <kbd>F</kbd> | Toggle 720° cycle synchronization chart overlay |
| <kbd>Q</kbd> / <kbd>ESC</kbd> | Quit application and restore terminal |

---

## Installation & Running

### Requirements
- Python 3.9+ (Zero external dependencies, uses standard library `curses`)
- Standard terminal emulator (minimum 80 columns x 24 rows recommended)

### Run with Python module
```bash
python3 -m aero_engine
```

### Run with CLI executable
```bash
./aero-engine
```

### Optional Arguments
```bash
# Start at 2200 cruise RPM
python3 -m aero_engine --rpm 2200

# Set visual animation speed (default 0.08 for clear slow-mo; 1.0 for real-time)
python3 -m aero_engine --speed 0.05

# Start with 70% throttle
python3 -m aero_engine --throttle 70

# Run in monochrome mode
python3 -m aero_engine --no-color

# Launch directly with diagnostics overlay open
python3 -m aero_engine --debug
```

---

## Project Structure

```
Engine/
├── aero_engine/
│   ├── __init__.py      # Package metadata
│   ├── __main__.py      # CLI parsing, main event loop, curses wrapper
│   ├── config.py        # Physical dimensions, timings, thresholds
│   ├── crankshaft.py    # Kinematic equations, angular progression
│   ├── cylinder.py      # Independent cylinder stroke & valve model
│   ├── engine.py        # State machine, RPM dynamics, telemetry
│   ├── renderer.py      # Flicker-free curses renderer & overlays
│   └── simulation.py    # Particle physics & vibration model
├── tests/
│   ├── test_crankshaft.py
│   ├── test_cylinder.py
│   ├── test_engine.py
│   └── test_renderer.py
├── aero-engine          # Executable launcher script
├── pyproject.toml       # Project packaging metadata
├── README.md            # Documentation
└── .gitignore
```

---

## Running Tests

Run the complete unit test suite:
```bash
python3 -m unittest discover -s tests -v
```
