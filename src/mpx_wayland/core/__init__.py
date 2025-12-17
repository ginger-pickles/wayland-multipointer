"""
Core module for Wayland Multi-Pointer (MPX) support.

This module provides the fundamental building blocks:
- Data models for seats, devices, cursors, and grabs
- SeatManager for coordinating multiple seats
"""

from .models import (
    DeviceType,
    DeviceCapability,
    GrabMode,
    SeatState,
    Position,
    InputDevice,
    Cursor,
    Grab,
    FocusState,
    Seat,
    DisplayBounds,
)

from .seat_manager import (
    SeatManager,
    Event,
    EventType,
    EventCallback,
    SeatManagerError,
    SeatNotFoundError,
    DeviceNotFoundError,
    DeviceAlreadyAssignedError,
)

__all__ = [
    # Models
    "DeviceType",
    "DeviceCapability",
    "GrabMode",
    "SeatState",
    "Position",
    "InputDevice",
    "Cursor",
    "Grab",
    "FocusState",
    "Seat",
    "DisplayBounds",
    # Seat Manager
    "SeatManager",
    "Event",
    "EventType",
    "EventCallback",
    "SeatManagerError",
    "SeatNotFoundError",
    "DeviceNotFoundError",
    "DeviceAlreadyAssignedError",
]
