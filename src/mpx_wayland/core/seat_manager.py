"""
Seat Manager - Core logic for managing multiple seats and device routing.

This is the heart of the MPX implementation. It manages:
- Creating and destroying seats
- Assigning/unassigning devices to seats
- Routing input events to appropriate seats
- Managing grab state per seat
"""

from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum, auto
import logging

from .models import (
    Seat, InputDevice, DeviceType, DeviceCapability,
    Position, GrabMode, SeatState, DisplayBounds
)

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of events that can be emitted."""
    SEAT_CREATED = auto()
    SEAT_DESTROYED = auto()
    SEAT_STATE_CHANGED = auto()
    DEVICE_ADDED = auto()
    DEVICE_REMOVED = auto()
    DEVICE_ASSIGNED = auto()
    DEVICE_UNASSIGNED = auto()
    POINTER_MOTION = auto()
    POINTER_BUTTON = auto()
    POINTER_AXIS = auto()
    KEYBOARD_KEY = auto()
    GRAB_STARTED = auto()
    GRAB_ENDED = auto()
    FOCUS_CHANGED = auto()


@dataclass
class Event:
    """Event emitted by the seat manager."""
    event_type: EventType
    seat_id: Optional[str] = None
    device_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)


EventCallback = Callable[[Event], None]


class SeatManagerError(Exception):
    """Base exception for seat manager errors."""
    pass


class SeatNotFoundError(SeatManagerError):
    """Raised when a seat is not found."""
    pass


class DeviceNotFoundError(SeatManagerError):
    """Raised when a device is not found."""
    pass


class DeviceAlreadyAssignedError(SeatManagerError):
    """Raised when trying to assign an already-assigned device."""
    pass


class SeatManager:
    """
    Manages multiple seats and their device assignments.

    This class is the central coordinator for the multi-pointer system.
    It tracks all seats, devices, and handles routing of input events.
    """

    def __init__(self, default_seat_name: str = "seat0"):
        """
        Initialize the seat manager.

        Args:
            default_seat_name: Name for the default/primary seat
        """
        self._seats: Dict[str, Seat] = {}
        self._devices: Dict[str, InputDevice] = {}
        self._event_listeners: List[EventCallback] = []
        self._display_bounds: DisplayBounds = DisplayBounds()

        # Create the default seat
        self._default_seat_id: str = self.create_seat(default_seat_name)

    @property
    def default_seat(self) -> Seat:
        """Get the default seat."""
        return self._seats[self._default_seat_id]

    @property
    def seats(self) -> List[Seat]:
        """Get all seats."""
        return list(self._seats.values())

    @property
    def devices(self) -> List[InputDevice]:
        """Get all registered devices."""
        return list(self._devices.values())

    @property
    def unassigned_devices(self) -> List[InputDevice]:
        """Get devices not assigned to any seat."""
        return [d for d in self._devices.values() if not d.is_assigned]

    def set_display_bounds(self, bounds: DisplayBounds) -> None:
        """Set the display bounds for cursor confinement."""
        self._display_bounds = bounds

    def add_event_listener(self, callback: EventCallback) -> None:
        """Add an event listener."""
        self._event_listeners.append(callback)

    def remove_event_listener(self, callback: EventCallback) -> None:
        """Remove an event listener."""
        if callback in self._event_listeners:
            self._event_listeners.remove(callback)

    def _emit_event(self, event: Event) -> None:
        """Emit an event to all listeners."""
        for listener in self._event_listeners:
            try:
                listener(event)
            except Exception as e:
                logger.error(f"Event listener error: {e}")

    # === Seat Management ===

    def create_seat(self, name: str) -> str:
        """
        Create a new seat.

        Args:
            name: Human-readable name for the seat

        Returns:
            The ID of the created seat
        """
        seat = Seat(name=name)
        self._seats[seat.id] = seat

        logger.info(f"Created seat '{name}' with ID {seat.id}")
        self._emit_event(Event(
            event_type=EventType.SEAT_CREATED,
            seat_id=seat.id,
            data={"name": name}
        ))

        return seat.id

    def destroy_seat(self, seat_id: str) -> None:
        """
        Destroy a seat.

        Devices assigned to this seat become unassigned.

        Args:
            seat_id: ID of seat to destroy

        Raises:
            SeatNotFoundError: If seat doesn't exist
            SeatManagerError: If trying to destroy the default seat
        """
        if seat_id not in self._seats:
            raise SeatNotFoundError(f"Seat {seat_id} not found")

        if seat_id == self._default_seat_id:
            raise SeatManagerError("Cannot destroy the default seat")

        seat = self._seats[seat_id]

        # Unassign all devices from this seat
        for device_id in list(seat.pointer_devices) + list(seat.keyboard_devices):
            if device_id in self._devices:
                self._devices[device_id].seat_id = None

        del self._seats[seat_id]

        logger.info(f"Destroyed seat '{seat.name}' ({seat_id})")
        self._emit_event(Event(
            event_type=EventType.SEAT_DESTROYED,
            seat_id=seat_id,
            data={"name": seat.name}
        ))

    def get_seat(self, seat_id: str) -> Seat:
        """
        Get a seat by ID.

        Args:
            seat_id: ID of seat to get

        Returns:
            The requested seat

        Raises:
            SeatNotFoundError: If seat doesn't exist
        """
        if seat_id not in self._seats:
            raise SeatNotFoundError(f"Seat {seat_id} not found")
        return self._seats[seat_id]

    def get_seat_by_name(self, name: str) -> Optional[Seat]:
        """
        Get a seat by name.

        Args:
            name: Name of seat to find

        Returns:
            The seat if found, None otherwise
        """
        for seat in self._seats.values():
            if seat.name == name:
                return seat
        return None

    def set_seat_state(self, seat_id: str, state: SeatState) -> None:
        """
        Set the state of a seat.

        Args:
            seat_id: ID of seat to modify
            state: New state for the seat
        """
        seat = self.get_seat(seat_id)
        old_state = seat.state
        seat.state = state

        logger.info(f"Seat '{seat.name}' state changed: {old_state} -> {state}")
        self._emit_event(Event(
            event_type=EventType.SEAT_STATE_CHANGED,
            seat_id=seat_id,
            data={"old_state": old_state, "new_state": state}
        ))

    # === Device Management ===

    def register_device(self, device: InputDevice) -> None:
        """
        Register a new input device.

        Args:
            device: The device to register
        """
        self._devices[device.id] = device

        logger.info(f"Registered device '{device.name}' ({device.id})")
        self._emit_event(Event(
            event_type=EventType.DEVICE_ADDED,
            device_id=device.id,
            data={"name": device.name, "type": device.device_type}
        ))

    def unregister_device(self, device_id: str) -> None:
        """
        Unregister a device.

        If assigned to a seat, it will be unassigned first.

        Args:
            device_id: ID of device to unregister

        Raises:
            DeviceNotFoundError: If device doesn't exist
        """
        if device_id not in self._devices:
            raise DeviceNotFoundError(f"Device {device_id} not found")

        device = self._devices[device_id]

        # Unassign from seat if assigned
        if device.seat_id:
            self.unassign_device(device_id)

        del self._devices[device_id]

        logger.info(f"Unregistered device '{device.name}' ({device_id})")
        self._emit_event(Event(
            event_type=EventType.DEVICE_REMOVED,
            device_id=device_id,
            data={"name": device.name}
        ))

    def get_device(self, device_id: str) -> InputDevice:
        """
        Get a device by ID.

        Args:
            device_id: ID of device to get

        Returns:
            The requested device

        Raises:
            DeviceNotFoundError: If device doesn't exist
        """
        if device_id not in self._devices:
            raise DeviceNotFoundError(f"Device {device_id} not found")
        return self._devices[device_id]

    def assign_device(self, device_id: str, seat_id: str,
                      force: bool = False) -> None:
        """
        Assign a device to a seat.

        Args:
            device_id: ID of device to assign
            seat_id: ID of seat to assign to
            force: If True, reassign even if already assigned

        Raises:
            DeviceNotFoundError: If device doesn't exist
            SeatNotFoundError: If seat doesn't exist
            DeviceAlreadyAssignedError: If device is assigned and force=False
        """
        device = self.get_device(device_id)
        seat = self.get_seat(seat_id)

        if device.seat_id and not force:
            raise DeviceAlreadyAssignedError(
                f"Device {device_id} already assigned to seat {device.seat_id}")

        # Unassign from current seat if any
        if device.seat_id:
            self.unassign_device(device_id)

        # Assign to new seat
        device.seat_id = seat_id

        if device.has_capability(DeviceCapability.POINTER):
            seat.add_pointer_device(device_id)
        if device.has_capability(DeviceCapability.KEYBOARD):
            seat.add_keyboard_device(device_id)

        logger.info(f"Assigned device '{device.name}' to seat '{seat.name}'")
        self._emit_event(Event(
            event_type=EventType.DEVICE_ASSIGNED,
            seat_id=seat_id,
            device_id=device_id,
            data={"device_name": device.name, "seat_name": seat.name}
        ))

    def unassign_device(self, device_id: str) -> None:
        """
        Unassign a device from its current seat.

        Args:
            device_id: ID of device to unassign

        Raises:
            DeviceNotFoundError: If device doesn't exist
        """
        device = self.get_device(device_id)

        if not device.seat_id:
            return  # Already unassigned

        seat_id = device.seat_id
        seat = self._seats.get(seat_id)

        if seat:
            seat.remove_pointer_device(device_id)
            seat.remove_keyboard_device(device_id)

        device.seat_id = None

        logger.info(f"Unassigned device '{device.name}' from seat")
        self._emit_event(Event(
            event_type=EventType.DEVICE_UNASSIGNED,
            seat_id=seat_id,
            device_id=device_id,
            data={"device_name": device.name}
        ))

    def auto_assign_device(self, device_id: str) -> str:
        """
        Automatically assign a device to the default seat.

        This is the default behavior when a new device is plugged in.

        Args:
            device_id: ID of device to assign

        Returns:
            ID of the seat the device was assigned to
        """
        self.assign_device(device_id, self._default_seat_id)
        return self._default_seat_id

    # === Input Event Routing ===

    def route_pointer_motion(self, device_id: str, dx: float, dy: float) -> Optional[str]:
        """
        Route a pointer motion event to the appropriate seat.

        Args:
            device_id: ID of device generating the motion
            dx: X delta
            dy: Y delta

        Returns:
            ID of seat that received the event, or None if not routed
        """
        device = self._devices.get(device_id)
        if not device or not device.seat_id:
            return None

        seat = self._seats.get(device.seat_id)
        if not seat or seat.state != SeatState.ACTIVE:
            return None

        # Update cursor position
        seat.cursor.move_by(dx, dy)

        # Clamp to display bounds
        seat.cursor.position = seat.cursor.position.clamp(
            self._display_bounds.x,
            self._display_bounds.y,
            self._display_bounds.x + self._display_bounds.width - 1,
            self._display_bounds.y + self._display_bounds.height - 1
        )

        self._emit_event(Event(
            event_type=EventType.POINTER_MOTION,
            seat_id=seat.id,
            device_id=device_id,
            data={
                "dx": dx, "dy": dy,
                "x": seat.cursor.position.x,
                "y": seat.cursor.position.y
            }
        ))

        return seat.id

    def route_pointer_button(self, device_id: str, button: int,
                             pressed: bool) -> Optional[str]:
        """
        Route a pointer button event to the appropriate seat.

        Args:
            device_id: ID of device generating the event
            button: Button code
            pressed: True if pressed, False if released

        Returns:
            ID of seat that received the event, or None if not routed
        """
        device = self._devices.get(device_id)
        if not device or not device.seat_id:
            return None

        seat = self._seats.get(device.seat_id)
        if not seat or seat.state != SeatState.ACTIVE:
            return None

        self._emit_event(Event(
            event_type=EventType.POINTER_BUTTON,
            seat_id=seat.id,
            device_id=device_id,
            data={"button": button, "pressed": pressed}
        ))

        return seat.id

    def route_keyboard_key(self, device_id: str, key: int,
                           pressed: bool) -> Optional[str]:
        """
        Route a keyboard key event to the appropriate seat.

        Args:
            device_id: ID of device generating the event
            key: Key code
            pressed: True if pressed, False if released

        Returns:
            ID of seat that received the event, or None if not routed
        """
        device = self._devices.get(device_id)
        if not device or not device.seat_id:
            return None

        seat = self._seats.get(device.seat_id)
        if not seat or seat.state != SeatState.ACTIVE:
            return None

        self._emit_event(Event(
            event_type=EventType.KEYBOARD_KEY,
            seat_id=seat.id,
            device_id=device_id,
            data={"key": key, "pressed": pressed}
        ))

        return seat.id

    # === Grab Management ===

    def request_pointer_grab(self, seat_id: str, client_id: str,
                             mode: GrabMode,
                             surface_id: Optional[str] = None) -> bool:
        """
        Request a pointer grab for a seat.

        This is called when an application (like a game) wants exclusive
        pointer input.

        Args:
            seat_id: ID of seat to grab
            client_id: ID of requesting client
            mode: Type of grab (lock, confine)
            surface_id: Optional surface to confine to

        Returns:
            True if grab was granted, False otherwise
        """
        seat = self.get_seat(seat_id)

        if seat.is_pointer_grabbed:
            logger.warning(f"Seat '{seat.name}' pointer already grabbed")
            return False

        seat.set_pointer_grab(client_id, mode, surface_id)

        logger.info(f"Pointer grab granted for seat '{seat.name}' to {client_id}")
        self._emit_event(Event(
            event_type=EventType.GRAB_STARTED,
            seat_id=seat_id,
            data={"type": "pointer", "mode": mode, "client_id": client_id}
        ))

        return True

    def release_pointer_grab(self, seat_id: str) -> None:
        """
        Release a pointer grab on a seat.

        Args:
            seat_id: ID of seat to release grab on
        """
        seat = self.get_seat(seat_id)

        if not seat.is_pointer_grabbed:
            return

        seat.release_pointer_grab()

        logger.info(f"Pointer grab released for seat '{seat.name}'")
        self._emit_event(Event(
            event_type=EventType.GRAB_ENDED,
            seat_id=seat_id,
            data={"type": "pointer"}
        ))

    def get_active_grabs(self) -> Dict[str, GrabMode]:
        """
        Get all seats with active pointer grabs.

        Returns:
            Dict mapping seat_id to grab mode
        """
        grabs = {}
        for seat in self._seats.values():
            if seat.is_pointer_grabbed:
                grabs[seat.id] = seat.pointer_grab.mode
        return grabs

    # === State Queries ===

    def get_seat_for_device(self, device_id: str) -> Optional[Seat]:
        """Get the seat a device is assigned to."""
        device = self._devices.get(device_id)
        if not device or not device.seat_id:
            return None
        return self._seats.get(device.seat_id)

    def get_status(self) -> Dict[str, Any]:
        """
        Get complete status of the seat manager.

        Returns:
            Dict with all seats, devices, and their states
        """
        return {
            "seats": [
                {
                    "id": s.id,
                    "name": s.name,
                    "state": s.state.name,
                    "cursor_position": {
                        "x": s.cursor.position.x,
                        "y": s.cursor.position.y
                    },
                    "pointer_devices": list(s.pointer_devices),
                    "keyboard_devices": list(s.keyboard_devices),
                    "pointer_grabbed": s.is_pointer_grabbed,
                    "keyboard_grabbed": s.is_keyboard_grabbed,
                }
                for s in self._seats.values()
            ],
            "devices": [
                {
                    "id": d.id,
                    "name": d.name,
                    "type": d.device_type.name,
                    "capabilities": [c.name for c in d.capabilities],
                    "seat_id": d.seat_id,
                    "available": d.is_available,
                }
                for d in self._devices.values()
            ],
            "default_seat_id": self._default_seat_id,
        }
