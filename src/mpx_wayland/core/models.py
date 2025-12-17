"""
Core data models for Wayland Multi-Pointer (MPX) support.

These models represent the fundamental concepts:
- InputDevice: Physical input devices (mice, keyboards)
- Seat: A logical grouping of input devices (pointer + keyboard pair)
- Cursor: Visual representation of a pointer position
- Grab: Exclusive input capture by an application
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Set
import uuid
from datetime import datetime


class DeviceType(Enum):
    """Type of input device."""
    POINTER = auto()      # Mouse, trackpad, etc.
    KEYBOARD = auto()     # Physical keyboard
    TOUCH = auto()        # Touchscreen
    TABLET = auto()       # Graphics tablet
    UNKNOWN = auto()


class DeviceCapability(Enum):
    """Capabilities a device can have."""
    POINTER = auto()
    KEYBOARD = auto()
    TOUCH = auto()
    TABLET_TOOL = auto()
    TABLET_PAD = auto()
    GESTURE = auto()
    SWITCH = auto()


class GrabMode(Enum):
    """Type of pointer/keyboard grab."""
    NONE = auto()         # No grab active
    POINTER_LOCK = auto() # Pointer locked to position (mouselook)
    POINTER_CONFINE = auto() # Pointer confined to region
    KEYBOARD = auto()     # Keyboard grab


class SeatState(Enum):
    """State of a seat."""
    ACTIVE = auto()       # Seat is active and routing input
    INACTIVE = auto()     # Seat exists but not routing
    SUSPENDED = auto()    # Temporarily suspended


@dataclass
class Position:
    """2D position for cursor."""
    x: float = 0.0
    y: float = 0.0

    def move(self, dx: float, dy: float) -> 'Position':
        """Return new position moved by delta."""
        return Position(self.x + dx, self.y + dy)

    def clamp(self, min_x: float, min_y: float, max_x: float, max_y: float) -> 'Position':
        """Return position clamped to bounds."""
        return Position(
            max(min_x, min(max_x, self.x)),
            max(min_y, min(max_y, self.y))
        )


@dataclass
class InputDevice:
    """
    Represents a physical input device.

    Mirrors libinput device representation. Each physical device
    (mouse, keyboard) gets one InputDevice instance.
    """
    id: str                                    # Unique identifier (e.g., from libinput)
    name: str                                  # Human-readable name
    device_type: DeviceType                    # Primary type
    capabilities: Set[DeviceCapability] = field(default_factory=set)
    vendor_id: int = 0                         # USB vendor ID
    product_id: int = 0                        # USB product ID
    sysfs_path: str = ""                       # /sys path for device
    seat_id: Optional[str] = None              # Currently assigned seat
    is_available: bool = True                  # Device is plugged in and working

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if not isinstance(other, InputDevice):
            return False
        return self.id == other.id

    @property
    def is_assigned(self) -> bool:
        """Check if device is assigned to a seat."""
        return self.seat_id is not None

    def has_capability(self, cap: DeviceCapability) -> bool:
        """Check if device has a specific capability."""
        return cap in self.capabilities


@dataclass
class Cursor:
    """
    Visual cursor state for a seat.

    Tracks position, visibility, and cursor image.
    """
    position: Position = field(default_factory=Position)
    visible: bool = True
    cursor_theme: str = "default"
    cursor_name: str = "left_ptr"
    hotspot_x: int = 0
    hotspot_y: int = 0

    def move_to(self, x: float, y: float) -> None:
        """Move cursor to absolute position."""
        self.position = Position(x, y)

    def move_by(self, dx: float, dy: float) -> None:
        """Move cursor by relative amount."""
        self.position = self.position.move(dx, dy)


@dataclass
class Grab:
    """
    Represents an active input grab.

    When an application grabs input, only that app receives
    events for the grabbed device type.
    """
    mode: GrabMode
    client_id: str                             # ID of grabbing client/window
    surface_id: Optional[str] = None           # Specific surface if applicable
    started_at: datetime = field(default_factory=datetime.now)

    @property
    def is_active(self) -> bool:
        return self.mode != GrabMode.NONE


@dataclass
class FocusState:
    """Tracks what surface/window has focus for a seat."""
    pointer_focus: Optional[str] = None        # Surface ID under pointer
    keyboard_focus: Optional[str] = None       # Surface ID with keyboard focus


@dataclass
class Seat:
    """
    Represents a logical seat (wl_seat equivalent).

    A seat is a group of input devices that together form
    one user's interaction point. Typically one pointer +
    one keyboard, but can have multiple of each.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""                             # Human-readable name (e.g., "seat0", "aux")
    state: SeatState = SeatState.ACTIVE
    cursor: Cursor = field(default_factory=Cursor)
    focus: FocusState = field(default_factory=FocusState)
    pointer_grab: Optional[Grab] = None
    keyboard_grab: Optional[Grab] = None

    # Device IDs assigned to this seat
    pointer_devices: Set[str] = field(default_factory=set)
    keyboard_devices: Set[str] = field(default_factory=set)

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if not isinstance(other, Seat):
            return False
        return self.id == other.id

    @property
    def has_pointer(self) -> bool:
        """Check if seat has at least one pointer device."""
        return len(self.pointer_devices) > 0

    @property
    def has_keyboard(self) -> bool:
        """Check if seat has at least one keyboard device."""
        return len(self.keyboard_devices) > 0

    @property
    def is_complete(self) -> bool:
        """Check if seat has both pointer and keyboard."""
        return self.has_pointer and self.has_keyboard

    @property
    def is_pointer_grabbed(self) -> bool:
        """Check if pointer is currently grabbed."""
        return self.pointer_grab is not None and self.pointer_grab.is_active

    @property
    def is_keyboard_grabbed(self) -> bool:
        """Check if keyboard is currently grabbed."""
        return self.keyboard_grab is not None and self.keyboard_grab.is_active

    def add_pointer_device(self, device_id: str) -> None:
        """Add a pointer device to this seat."""
        self.pointer_devices.add(device_id)

    def add_keyboard_device(self, device_id: str) -> None:
        """Add a keyboard device to this seat."""
        self.keyboard_devices.add(device_id)

    def remove_pointer_device(self, device_id: str) -> None:
        """Remove a pointer device from this seat."""
        self.pointer_devices.discard(device_id)

    def remove_keyboard_device(self, device_id: str) -> None:
        """Remove a keyboard device from this seat."""
        self.keyboard_devices.discard(device_id)

    def set_pointer_grab(self, client_id: str, mode: GrabMode,
                         surface_id: Optional[str] = None) -> Grab:
        """Set pointer grab for this seat."""
        self.pointer_grab = Grab(
            mode=mode,
            client_id=client_id,
            surface_id=surface_id
        )
        return self.pointer_grab

    def release_pointer_grab(self) -> None:
        """Release any active pointer grab."""
        self.pointer_grab = None

    def set_keyboard_grab(self, client_id: str,
                          surface_id: Optional[str] = None) -> Grab:
        """Set keyboard grab for this seat."""
        self.keyboard_grab = Grab(
            mode=GrabMode.KEYBOARD,
            client_id=client_id,
            surface_id=surface_id
        )
        return self.keyboard_grab

    def release_keyboard_grab(self) -> None:
        """Release any active keyboard grab."""
        self.keyboard_grab = None


@dataclass
class DisplayBounds:
    """Represents the bounds of a display/output."""
    x: int = 0
    y: int = 0
    width: int = 1920
    height: int = 1080
    name: str = "default"

    def contains(self, pos: Position) -> bool:
        """Check if position is within display bounds."""
        return (self.x <= pos.x < self.x + self.width and
                self.y <= pos.y < self.y + self.height)
