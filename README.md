# wayland-multipointer (MPX for Wayland)

A system to provide multiple independent pointer/keyboard pairs on Wayland, analogous to X11's MPX (Multi-Pointer X).

## Overview

This project provides the core logic and simulation framework for implementing multi-pointer support on Wayland. The primary use case is enabling one pointer to be captured by a fullscreen game while another remains free for other displays/applications.

```
Current Wayland:                     With MPX:
┌──────────────────────────┐        ┌──────────────────────────┐
│ Single pointer ──▶ Game  │        │ Pointer A ──▶ Game       │
│              grabs it    │        │ Pointer B ──▶ Other apps │
│ Entire system loses      │        │                          │
│ pointer control          │        │ Both visible, both work! │
└──────────────────────────┘        └──────────────────────────┘
```

## Features

- **Multiple independent seats** - Each seat has its own cursor position and focus
- **Device-to-seat routing** - Physical input devices can be assigned to specific seats
- **Grab isolation** - Pointer grabs are scoped to individual seats
- **Configuration persistence** - Settings survive reboots
- **Simulation framework** - Full testing without hardware/compositor
- **CLI tool** - Manage seats and devices from the command line

## Project Structure

```
src/mpx_wayland/
├── core/           # Core data models and seat management
│   ├── models.py   # Seat, Device, Cursor, Grab data classes
│   └── seat_manager.py  # Central coordinator
├── config/         # Configuration file management
│   └── config.py   # JSON-based config persistence
├── cli/            # Command-line interface
│   └── mpx_ctl.py  # mpx-ctl tool
└── simulation/     # Testing framework
    └── simulator.py # Virtual compositor and devices

tests/
├── unit/           # Unit tests for each component
└── integration/    # End-to-end scenario tests
```

## Installation

```bash
# Clone the repository
git clone https://github.com/your-org/wayland-multipointer.git
cd wayland-multipointer

# Install in development mode
pip install -e .

# Or just run directly
python -m mpx_wayland.cli.mpx_ctl --help
```

## Quick Start

### Using the CLI

```bash
# List all seats
mpx-ctl list-seats

# Create a new seat
mpx-ctl create-seat aux

# List devices
mpx-ctl list-devices

# Assign a device to a seat
mpx-ctl assign mouse1 aux

# View system status
mpx-ctl status
```

### Programmatic Usage

```python
from mpx_wayland.core import (
    SeatManager,
    InputDevice,
    DeviceType,
    DeviceCapability,
    GrabMode,
)

# Create seat manager (default seat "seat0" is created automatically)
manager = SeatManager()

# Create a second seat
aux_id = manager.create_seat("aux")

# Register a device
mouse = InputDevice(
    id="usb-mouse-001",
    name="Gaming Mouse",
    device_type=DeviceType.POINTER,
    capabilities={DeviceCapability.POINTER}
)
manager.register_device(mouse)

# Assign device to aux seat
manager.assign_device("usb-mouse-001", aux_id)

# Route pointer motion (returns seat ID that received the event)
seat_id = manager.route_pointer_motion("usb-mouse-001", dx=10, dy=5)

# Request pointer grab (e.g., for a game)
manager.request_pointer_grab(
    manager.default_seat.id,
    client_id="game-window",
    mode=GrabMode.POINTER_LOCK
)

# Check grab status - other seat is still free!
print(manager.default_seat.is_pointer_grabbed)  # True
aux_seat = manager.get_seat(aux_id)
print(aux_seat.is_pointer_grabbed)  # False
```

### Running the Simulation

```python
from mpx_wayland.simulation import (
    SimulatedCompositor,
    VirtualDevice,
    ScenarioRunner,
    scenario_grab_isolation,
)
from mpx_wayland.core import DeviceType, DeviceCapability, GrabMode

# Create simulated compositor
compositor = SimulatedCompositor(width=1920, height=1080)
compositor.seat_manager.create_seat("aux")

# Connect virtual devices
mouse1 = VirtualDevice(
    id="mouse1", name="Gaming Mouse",
    device_type=DeviceType.POINTER,
    capabilities={DeviceCapability.POINTER}
)
compositor.connect_device(mouse1, "seat0")

# Create virtual windows
compositor.create_window("game", "UT99", 0, 0, 1920, 1080)

# Simulate game grabbing pointer
seat0 = compositor.seat_manager.get_seat_by_name("seat0")
compositor.request_grab("game", seat0.id, GrabMode.POINTER_LOCK)

# Visualize current state
print(compositor.render_ascii(80, 24))
print(compositor.get_state_summary())
```

## Running Tests

```bash
# Run all tests
python -m unittest discover -s tests -v

# Run specific test file
python -m unittest tests.unit.test_seat_manager -v

# Run the full test suite with demo
python run_tests.py
```

## Architecture

### Core Concepts

1. **Seat** (`wl_seat` equivalent) - A logical grouping of input devices. Each seat has:
   - Cursor position and state
   - Focus tracking (pointer and keyboard)
   - Grab state (independent per seat!)
   - Assigned devices

2. **InputDevice** - Represents a physical input device (mouse, keyboard). Has:
   - Unique identifier (e.g., from libinput)
   - Capabilities (pointer, keyboard, touch, etc.)
   - Current seat assignment

3. **SeatManager** - Central coordinator that:
   - Creates/destroys seats
   - Routes input events to appropriate seats
   - Manages device assignments
   - Handles grab requests (scoped to seats)

4. **Grab** - Exclusive input capture by an application:
   - `POINTER_LOCK` - Pointer locked to position (mouselook)
   - `POINTER_CONFINE` - Pointer confined to region
   - Grabs on one seat do NOT affect other seats

### Event Flow

```
Physical Device (libinput)
       │
       ▼
   SeatManager
       │
       ├──► Route to assigned seat
       │
       ▼
   Seat (cursor update, grab check)
       │
       ▼
   Application (via Wayland protocol)
```

## Configuration

Configuration is stored in `~/.config/mpx-wayland/`:

```json
// config.json
{
  "version": 1,
  "global_config": {
    "auto_assign_new_devices": true,
    "default_seat": "seat0"
  },
  "seats": [
    {"name": "seat0", "enabled": true, "cursor_size": 24},
    {"name": "aux", "enabled": true, "cursor_size": 24}
  ]
}

// devices.json
{
  "version": 1,
  "mappings": [
    {"device_id": "046d:c332", "seat_name": "aux", "device_name": "Gaming Mouse"}
  ]
}
```

## Integration with Compositors

This library provides the core logic. To actually implement MPX on Wayland, you would need to integrate with a compositor:

### KWin (KDE)
- Create a KWin plugin that uses this library
- Hook into `seat_interface.cpp` for multi-seat support
- Modify cursor rendering for multiple cursors

### wlroots (Sway, etc.)
- wlroots already has good seat abstraction
- Create a wlroots-based compositor or plugin
- Use this library for device routing logic

### XWayland
- XWayland needs seat-scoped pointer grab support
- Each X screen could map to a different seat

## Future Work

- [ ] Actual compositor integration (KWin plugin or wlroots-based)
- [ ] libinput integration for real device detection
- [ ] DBus IPC for runtime seat management
- [ ] GUI configuration tool (KDE System Settings module)
- [ ] XWayland multi-seat support

## License

MIT License - See LICENSE file for details.

## Related Projects

- [X11 MPX](https://www.x.org/wiki/Development/Documentation/MPX/) - Multi-Pointer X for X11
- [libinput](https://gitlab.freedesktop.org/libinput/libinput) - Input device handling
- [wlroots](https://gitlab.freedesktop.org/wlroots/wlroots) - Modular Wayland compositor library
- [KWin](https://invent.kde.org/plasma/kwin) - KDE's Wayland compositor
