"""
Simulation framework for testing MPX without hardware.

This module provides:
- Virtual input devices that generate synthetic events
- Simulated compositor environment
- Scenario runner for automated testing
- Visual ASCII representation of cursor positions
"""

import time
import random
import threading
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Dict, Any, Tuple
from enum import Enum, auto
import logging

from ..core import (
    SeatManager,
    InputDevice,
    DeviceType,
    DeviceCapability,
    Position,
    DisplayBounds,
    GrabMode,
    Event,
    EventType,
)

logger = logging.getLogger(__name__)


class SimulationEventType(Enum):
    """Types of simulation events."""
    DEVICE_CONNECTED = auto()
    DEVICE_DISCONNECTED = auto()
    POINTER_MOVE = auto()
    POINTER_BUTTON = auto()
    KEYBOARD_KEY = auto()
    GRAB_REQUEST = auto()
    GRAB_RELEASE = auto()
    WINDOW_FOCUS = auto()


@dataclass
class SimulationEvent:
    """An event in the simulation."""
    event_type: SimulationEventType
    device_id: str = ""
    timestamp: float = field(default_factory=time.time)
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VirtualDevice:
    """
    A virtual input device for simulation.

    Can be programmed to generate sequences of events.
    """
    id: str
    name: str
    device_type: DeviceType
    capabilities: set = field(default_factory=set)

    # Current state
    is_connected: bool = True
    position: Position = field(default_factory=Position)
    buttons_pressed: set = field(default_factory=set)
    keys_pressed: set = field(default_factory=set)

    def to_input_device(self) -> InputDevice:
        """Convert to core InputDevice."""
        return InputDevice(
            id=self.id,
            name=self.name,
            device_type=self.device_type,
            capabilities=self.capabilities,
            is_available=self.is_connected,
        )


@dataclass
class VirtualWindow:
    """A virtual window in the simulation."""
    id: str
    title: str
    x: int
    y: int
    width: int
    height: int
    has_focus: bool = False
    has_pointer_grab: bool = False
    grab_mode: Optional[GrabMode] = None

    def contains(self, pos: Position) -> bool:
        """Check if position is within window."""
        return (self.x <= pos.x < self.x + self.width and
                self.y <= pos.y < self.y + self.height)


class SimulatedCompositor:
    """
    Simulated Wayland compositor environment.

    Provides a virtual display with windows that can be
    interacted with using virtual devices.
    """

    def __init__(self, width: int = 1920, height: int = 1080):
        """
        Initialize the simulated compositor.

        Args:
            width: Display width in pixels
            height: Display height in pixels
        """
        self.display = DisplayBounds(width=width, height=height)
        self.seat_manager = SeatManager()
        self.seat_manager.set_display_bounds(self.display)

        self.windows: Dict[str, VirtualWindow] = {}
        self.devices: Dict[str, VirtualDevice] = {}

        self.event_log: List[SimulationEvent] = []
        self._event_callbacks: List[Callable[[SimulationEvent], None]] = []

    def add_event_callback(self, callback: Callable[[SimulationEvent], None]) -> None:
        """Add a callback for simulation events."""
        self._event_callbacks.append(callback)

    def _emit_event(self, event: SimulationEvent) -> None:
        """Record and emit a simulation event."""
        self.event_log.append(event)
        for callback in self._event_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Event callback error: {e}")

    # === Device Management ===

    def connect_device(self, device: VirtualDevice, seat_name: str = "seat0") -> None:
        """
        Connect a virtual device.

        Args:
            device: The virtual device to connect
            seat_name: Seat to assign device to
        """
        self.devices[device.id] = device
        device.is_connected = True

        # Register with seat manager
        self.seat_manager.register_device(device.to_input_device())

        # Assign to seat
        seat = self.seat_manager.get_seat_by_name(seat_name)
        if seat:
            self.seat_manager.assign_device(device.id, seat.id)

        self._emit_event(SimulationEvent(
            event_type=SimulationEventType.DEVICE_CONNECTED,
            device_id=device.id,
            data={"seat": seat_name}
        ))

        logger.info(f"Connected device '{device.name}' to seat '{seat_name}'")

    def disconnect_device(self, device_id: str) -> None:
        """
        Disconnect a virtual device.

        Args:
            device_id: ID of device to disconnect
        """
        if device_id in self.devices:
            device = self.devices[device_id]
            device.is_connected = False

            self.seat_manager.unregister_device(device_id)

            self._emit_event(SimulationEvent(
                event_type=SimulationEventType.DEVICE_DISCONNECTED,
                device_id=device_id,
            ))

            logger.info(f"Disconnected device '{device.name}'")

    # === Window Management ===

    def create_window(self, window_id: str, title: str,
                      x: int, y: int, width: int, height: int) -> VirtualWindow:
        """
        Create a virtual window.

        Args:
            window_id: Unique window identifier
            title: Window title
            x, y: Window position
            width, height: Window dimensions

        Returns:
            The created window
        """
        window = VirtualWindow(
            id=window_id,
            title=title,
            x=x, y=y,
            width=width, height=height,
        )
        self.windows[window_id] = window
        logger.info(f"Created window '{title}' at ({x}, {y})")
        return window

    def destroy_window(self, window_id: str) -> None:
        """Destroy a virtual window."""
        if window_id in self.windows:
            window = self.windows.pop(window_id)
            logger.info(f"Destroyed window '{window.title}'")

    def get_window_at(self, pos: Position) -> Optional[VirtualWindow]:
        """Get the window at a given position (topmost)."""
        # Reverse order = topmost window first
        for window in reversed(list(self.windows.values())):
            if window.contains(pos):
                return window
        return None

    # === Input Simulation ===

    def move_pointer(self, device_id: str, dx: float = 0, dy: float = 0,
                     absolute: Optional[Tuple[float, float]] = None) -> Optional[str]:
        """
        Simulate pointer movement.

        Args:
            device_id: Device generating the movement
            dx, dy: Relative movement (if absolute is None)
            absolute: Absolute position to move to

        Returns:
            ID of seat that received the event
        """
        if device_id not in self.devices:
            return None

        device = self.devices[device_id]

        if absolute:
            # Calculate delta from current position
            dx = absolute[0] - device.position.x
            dy = absolute[1] - device.position.y
            device.position = Position(absolute[0], absolute[1])
        else:
            device.position = device.position.move(dx, dy)

        seat_id = self.seat_manager.route_pointer_motion(device_id, dx, dy)

        self._emit_event(SimulationEvent(
            event_type=SimulationEventType.POINTER_MOVE,
            device_id=device_id,
            data={"dx": dx, "dy": dy, "seat_id": seat_id}
        ))

        return seat_id

    def click_button(self, device_id: str, button: int = 1,
                     pressed: bool = True) -> Optional[str]:
        """
        Simulate a button click.

        Args:
            device_id: Device generating the click
            button: Button number (1=left, 2=middle, 3=right)
            pressed: True for press, False for release

        Returns:
            ID of seat that received the event
        """
        if device_id not in self.devices:
            return None

        device = self.devices[device_id]

        if pressed:
            device.buttons_pressed.add(button)
        else:
            device.buttons_pressed.discard(button)

        seat_id = self.seat_manager.route_pointer_button(device_id, button, pressed)

        self._emit_event(SimulationEvent(
            event_type=SimulationEventType.POINTER_BUTTON,
            device_id=device_id,
            data={"button": button, "pressed": pressed, "seat_id": seat_id}
        ))

        return seat_id

    def press_key(self, device_id: str, key: int,
                  pressed: bool = True) -> Optional[str]:
        """
        Simulate a key press.

        Args:
            device_id: Device generating the keypress
            key: Key code
            pressed: True for press, False for release

        Returns:
            ID of seat that received the event
        """
        if device_id not in self.devices:
            return None

        device = self.devices[device_id]

        if pressed:
            device.keys_pressed.add(key)
        else:
            device.keys_pressed.discard(key)

        seat_id = self.seat_manager.route_keyboard_key(device_id, key, pressed)

        self._emit_event(SimulationEvent(
            event_type=SimulationEventType.KEYBOARD_KEY,
            device_id=device_id,
            data={"key": key, "pressed": pressed, "seat_id": seat_id}
        ))

        return seat_id

    # === Grab Simulation ===

    def request_grab(self, window_id: str, seat_id: str,
                     mode: GrabMode = GrabMode.POINTER_LOCK) -> bool:
        """
        Simulate a window requesting pointer grab.

        Args:
            window_id: Window requesting the grab
            seat_id: Seat to grab
            mode: Type of grab

        Returns:
            True if grab was granted
        """
        if window_id not in self.windows:
            return False

        window = self.windows[window_id]
        result = self.seat_manager.request_pointer_grab(seat_id, window_id, mode)

        if result:
            window.has_pointer_grab = True
            window.grab_mode = mode

        self._emit_event(SimulationEvent(
            event_type=SimulationEventType.GRAB_REQUEST,
            data={
                "window_id": window_id,
                "seat_id": seat_id,
                "mode": mode.name,
                "granted": result,
            }
        ))

        return result

    def release_grab(self, window_id: str, seat_id: str) -> None:
        """
        Simulate releasing a pointer grab.

        Args:
            window_id: Window releasing the grab
            seat_id: Seat to release
        """
        if window_id in self.windows:
            window = self.windows[window_id]
            window.has_pointer_grab = False
            window.grab_mode = None

        self.seat_manager.release_pointer_grab(seat_id)

        self._emit_event(SimulationEvent(
            event_type=SimulationEventType.GRAB_RELEASE,
            data={"window_id": window_id, "seat_id": seat_id}
        ))

    # === Visualization ===

    def render_ascii(self, width: int = 80, height: int = 24) -> str:
        """
        Render the current state as ASCII art.

        Args:
            width: ASCII output width
            height: ASCII output height

        Returns:
            ASCII representation of the display
        """
        # Scale factors
        scale_x = width / self.display.width
        scale_y = height / self.display.height

        # Create empty grid
        grid = [[' ' for _ in range(width)] for _ in range(height)]

        # Draw border
        for x in range(width):
            grid[0][x] = '-'
            grid[height-1][x] = '-'
        for y in range(height):
            grid[y][0] = '|'
            grid[y][width-1] = '|'
        grid[0][0] = grid[0][width-1] = grid[height-1][0] = grid[height-1][width-1] = '+'

        # Draw windows
        for window in self.windows.values():
            wx1 = int(window.x * scale_x)
            wy1 = int(window.y * scale_y)
            wx2 = int((window.x + window.width) * scale_x)
            wy2 = int((window.y + window.height) * scale_y)

            # Clamp to grid
            wx1 = max(1, min(width-2, wx1))
            wy1 = max(1, min(height-2, wy1))
            wx2 = max(1, min(width-2, wx2))
            wy2 = max(1, min(height-2, wy2))

            # Draw window border
            char = '#' if window.has_pointer_grab else '.'
            for x in range(wx1, wx2):
                if 0 < wy1 < height-1:
                    grid[wy1][x] = char
                if 0 < wy2-1 < height-1:
                    grid[wy2-1][x] = char
            for y in range(wy1, wy2):
                if 0 < wx1 < width-1:
                    grid[y][wx1] = char
                if 0 < wx2-1 < width-1:
                    grid[y][wx2-1] = char

            # Draw window title (truncated)
            title = window.title[:wx2-wx1-2]
            for i, c in enumerate(title):
                if wx1 + 1 + i < wx2 and wy1 + 1 < height - 1:
                    grid[wy1 + 1][wx1 + 1 + i] = c

        # Draw cursors for each seat
        cursor_chars = ['@', '*', 'X', 'O', '+']
        for i, seat in enumerate(self.seat_manager.seats):
            cursor_char = cursor_chars[i % len(cursor_chars)]
            cx = int(seat.cursor.position.x * scale_x)
            cy = int(seat.cursor.position.y * scale_y)

            # Clamp to grid
            cx = max(1, min(width-2, cx))
            cy = max(1, min(height-2, cy))

            grid[cy][cx] = cursor_char

        # Convert to string
        lines = [''.join(row) for row in grid]

        # Add legend
        legend = "Cursors: "
        for i, seat in enumerate(self.seat_manager.seats):
            cursor_char = cursor_chars[i % len(cursor_chars)]
            grabbed = "[GRABBED]" if seat.is_pointer_grabbed else ""
            legend += f"{cursor_char}={seat.name}{grabbed} "

        lines.append(legend)

        return '\n'.join(lines)

    def get_state_summary(self) -> str:
        """Get a text summary of the current state."""
        lines = ["=== Simulation State ===", ""]

        lines.append("Seats:")
        for seat in self.seat_manager.seats:
            grabbed = " [POINTER GRABBED]" if seat.is_pointer_grabbed else ""
            lines.append(f"  {seat.name}: cursor at "
                        f"({seat.cursor.position.x:.0f}, {seat.cursor.position.y:.0f})"
                        f"{grabbed}")

        lines.append("")
        lines.append("Devices:")
        for device in self.devices.values():
            seat = self.seat_manager.get_seat_for_device(device.id)
            seat_name = seat.name if seat else "(unassigned)"
            status = "connected" if device.is_connected else "disconnected"
            lines.append(f"  {device.name}: {status}, assigned to {seat_name}")

        lines.append("")
        lines.append("Windows:")
        for window in self.windows.values():
            grab = f" [GRAB: {window.grab_mode.name}]" if window.has_pointer_grab else ""
            lines.append(f"  {window.title}: ({window.x}, {window.y}) "
                        f"{window.width}x{window.height}{grab}")

        return '\n'.join(lines)


class ScenarioRunner:
    """
    Runs predefined test scenarios.

    Useful for automated testing of multi-pointer behavior.
    """

    def __init__(self, compositor: SimulatedCompositor):
        """Initialize with a compositor instance."""
        self.compositor = compositor
        self.results: List[Dict[str, Any]] = []

    def run_scenario(self, name: str,
                     steps: List[Callable[['SimulatedCompositor'], bool]],
                     description: str = "") -> bool:
        """
        Run a test scenario.

        Args:
            name: Scenario name
            steps: List of step functions that return True on success
            description: Human-readable description

        Returns:
            True if all steps passed
        """
        logger.info(f"Running scenario: {name}")

        result = {
            "name": name,
            "description": description,
            "steps_passed": 0,
            "steps_total": len(steps),
            "passed": False,
            "errors": [],
        }

        for i, step in enumerate(steps):
            try:
                if step(self.compositor):
                    result["steps_passed"] += 1
                else:
                    result["errors"].append(f"Step {i+1} returned False")
                    break
            except Exception as e:
                result["errors"].append(f"Step {i+1} raised: {e}")
                break

        result["passed"] = result["steps_passed"] == result["steps_total"]
        self.results.append(result)

        status = "PASSED" if result["passed"] else "FAILED"
        logger.info(f"Scenario '{name}': {status}")

        return result["passed"]

    def get_report(self) -> str:
        """Get a summary report of all scenarios."""
        lines = ["=== Scenario Report ===", ""]

        passed = sum(1 for r in self.results if r["passed"])
        total = len(self.results)

        lines.append(f"Total: {passed}/{total} passed")
        lines.append("")

        for result in self.results:
            status = "PASS" if result["passed"] else "FAIL"
            lines.append(f"[{status}] {result['name']}")
            if result["description"]:
                lines.append(f"       {result['description']}")
            lines.append(f"       Steps: {result['steps_passed']}/{result['steps_total']}")
            if result["errors"]:
                for error in result["errors"]:
                    lines.append(f"       Error: {error}")
            lines.append("")

        return '\n'.join(lines)


# === Pre-built scenarios ===

def create_test_devices() -> List[VirtualDevice]:
    """Create a standard set of test devices."""
    return [
        VirtualDevice(
            id="mouse1",
            name="Virtual Mouse 1",
            device_type=DeviceType.POINTER,
            capabilities={DeviceCapability.POINTER},
        ),
        VirtualDevice(
            id="mouse2",
            name="Virtual Mouse 2",
            device_type=DeviceType.POINTER,
            capabilities={DeviceCapability.POINTER},
        ),
        VirtualDevice(
            id="keyboard1",
            name="Virtual Keyboard 1",
            device_type=DeviceType.KEYBOARD,
            capabilities={DeviceCapability.KEYBOARD},
        ),
        VirtualDevice(
            id="keyboard2",
            name="Virtual Keyboard 2",
            device_type=DeviceType.KEYBOARD,
            capabilities={DeviceCapability.KEYBOARD},
        ),
    ]


def scenario_basic_dual_pointer(compositor: SimulatedCompositor) -> List[Callable]:
    """
    Basic dual-pointer scenario.

    Tests that two pointers can move independently.
    """
    def step1_setup(comp: SimulatedCompositor) -> bool:
        """Set up two seats with mice."""
        comp.seat_manager.create_seat("aux")

        devices = create_test_devices()
        comp.connect_device(devices[0], "seat0")  # mouse1 -> seat0
        comp.connect_device(devices[1], "aux")    # mouse2 -> aux

        return len(comp.seat_manager.seats) == 2

    def step2_move_independently(comp: SimulatedCompositor) -> bool:
        """Move both pointers to different positions."""
        comp.move_pointer("mouse1", absolute=(100, 100))
        comp.move_pointer("mouse2", absolute=(500, 500))

        seats = comp.seat_manager.seats
        pos1 = seats[0].cursor.position
        pos2 = seats[1].cursor.position

        return (pos1.x == 100 and pos1.y == 100 and
                pos2.x == 500 and pos2.y == 500)

    def step3_verify_independence(comp: SimulatedCompositor) -> bool:
        """Verify moving one doesn't affect the other."""
        comp.move_pointer("mouse1", dx=50, dy=0)

        seats = comp.seat_manager.seats
        pos1 = seats[0].cursor.position
        pos2 = seats[1].cursor.position

        return (pos1.x == 150 and pos2.x == 500)  # mouse2 unchanged

    return [step1_setup, step2_move_independently, step3_verify_independence]


def scenario_grab_isolation(compositor: SimulatedCompositor) -> List[Callable]:
    """
    Grab isolation scenario.

    Tests that grabbing one pointer doesn't affect the other.
    """
    def step1_setup(comp: SimulatedCompositor) -> bool:
        """Set up two seats and a game window."""
        comp.seat_manager.create_seat("aux")

        devices = create_test_devices()
        comp.connect_device(devices[0], "seat0")
        comp.connect_device(devices[1], "aux")

        comp.create_window("game", "Fullscreen Game", 0, 0, 1920, 1080)

        return True

    def step2_grab_seat0(comp: SimulatedCompositor) -> bool:
        """Game grabs seat0's pointer."""
        seat0 = comp.seat_manager.get_seat_by_name("seat0")
        result = comp.request_grab("game", seat0.id, GrabMode.POINTER_LOCK)
        return result and seat0.is_pointer_grabbed

    def step3_aux_still_free(comp: SimulatedCompositor) -> bool:
        """Verify aux seat pointer is still free."""
        aux = comp.seat_manager.get_seat_by_name("aux")
        return not aux.is_pointer_grabbed

    def step4_aux_can_move(comp: SimulatedCompositor) -> bool:
        """Verify aux pointer can still move freely."""
        comp.move_pointer("mouse2", absolute=(960, 540))
        aux = comp.seat_manager.get_seat_by_name("aux")
        return aux.cursor.position.x == 960 and aux.cursor.position.y == 540

    return [step1_setup, step2_grab_seat0, step3_aux_still_free, step4_aux_can_move]


def scenario_device_hotplug(compositor: SimulatedCompositor) -> List[Callable]:
    """
    Device hot-plug scenario.

    Tests connecting and disconnecting devices at runtime.
    """
    def step1_initial_device(comp: SimulatedCompositor) -> bool:
        """Connect initial device."""
        device = VirtualDevice(
            id="mouse_hotplug",
            name="Hotplug Mouse",
            device_type=DeviceType.POINTER,
            capabilities={DeviceCapability.POINTER},
        )
        comp.connect_device(device, "seat0")
        return "mouse_hotplug" in comp.devices

    def step2_disconnect(comp: SimulatedCompositor) -> bool:
        """Disconnect the device."""
        comp.disconnect_device("mouse_hotplug")
        return not comp.devices.get("mouse_hotplug", VirtualDevice("", "", DeviceType.UNKNOWN)).is_connected

    def step3_reconnect(comp: SimulatedCompositor) -> bool:
        """Reconnect the device."""
        device = VirtualDevice(
            id="mouse_hotplug",
            name="Hotplug Mouse",
            device_type=DeviceType.POINTER,
            capabilities={DeviceCapability.POINTER},
        )
        comp.connect_device(device, "seat0")
        return comp.devices["mouse_hotplug"].is_connected

    return [step1_initial_device, step2_disconnect, step3_reconnect]
