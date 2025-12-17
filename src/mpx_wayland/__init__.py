"""
Wayland Multi-Pointer (MPX) Support Library.

This package provides multi-pointer functionality analogous to X11's MPX,
allowing multiple independent pointer/keyboard pairs on Wayland.

Modules:
- core: Data models and seat management
- config: Configuration file handling
- cli: Command-line interface
- simulation: Testing framework without hardware

Example usage:
    from mpx_wayland.core import SeatManager, InputDevice, DeviceType, DeviceCapability

    # Create seat manager
    manager = SeatManager()

    # Create a second seat
    aux_seat_id = manager.create_seat("aux")

    # Register and assign devices
    mouse = InputDevice(
        id="mouse1",
        name="Gaming Mouse",
        device_type=DeviceType.POINTER,
        capabilities={DeviceCapability.POINTER}
    )
    manager.register_device(mouse)
    manager.assign_device("mouse1", aux_seat_id)
"""

__version__ = "0.1.0"
__author__ = "Wayland MPX Project"

# Convenience imports
from .core import (
    SeatManager,
    Seat,
    InputDevice,
    DeviceType,
    DeviceCapability,
    GrabMode,
    Position,
    DisplayBounds,
)

__all__ = [
    "__version__",
    "SeatManager",
    "Seat",
    "InputDevice",
    "DeviceType",
    "DeviceCapability",
    "GrabMode",
    "Position",
    "DisplayBounds",
]
