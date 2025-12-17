"""
Unit tests for core data models.
"""

import unittest
from src.mpx_wayland.core.models import (
    Position,
    InputDevice,
    DeviceType,
    DeviceCapability,
    Cursor,
    Grab,
    GrabMode,
    Seat,
    SeatState,
    DisplayBounds,
)


class TestPosition(unittest.TestCase):
    """Tests for Position class."""

    def test_default_position(self):
        """Test default position is (0, 0)."""
        pos = Position()
        self.assertEqual(pos.x, 0.0)
        self.assertEqual(pos.y, 0.0)

    def test_position_with_values(self):
        """Test position with specific values."""
        pos = Position(100.5, 200.5)
        self.assertEqual(pos.x, 100.5)
        self.assertEqual(pos.y, 200.5)

    def test_move(self):
        """Test relative movement."""
        pos = Position(100, 100)
        new_pos = pos.move(50, -25)
        self.assertEqual(new_pos.x, 150)
        self.assertEqual(new_pos.y, 75)
        # Original should be unchanged
        self.assertEqual(pos.x, 100)

    def test_clamp(self):
        """Test position clamping to bounds."""
        pos = Position(150, 250)
        clamped = pos.clamp(0, 0, 100, 200)
        self.assertEqual(clamped.x, 100)
        self.assertEqual(clamped.y, 200)

    def test_clamp_negative(self):
        """Test clamping handles negative overshoot."""
        pos = Position(-50, -100)
        clamped = pos.clamp(0, 0, 1920, 1080)
        self.assertEqual(clamped.x, 0)
        self.assertEqual(clamped.y, 0)


class TestInputDevice(unittest.TestCase):
    """Tests for InputDevice class."""

    def test_create_device(self):
        """Test basic device creation."""
        device = InputDevice(
            id="mouse1",
            name="Test Mouse",
            device_type=DeviceType.POINTER,
        )
        self.assertEqual(device.id, "mouse1")
        self.assertEqual(device.name, "Test Mouse")
        self.assertEqual(device.device_type, DeviceType.POINTER)
        self.assertTrue(device.is_available)
        self.assertFalse(device.is_assigned)

    def test_device_capabilities(self):
        """Test device capability checking."""
        device = InputDevice(
            id="combo1",
            name="Combo Device",
            device_type=DeviceType.UNKNOWN,
            capabilities={DeviceCapability.POINTER, DeviceCapability.KEYBOARD},
        )
        self.assertTrue(device.has_capability(DeviceCapability.POINTER))
        self.assertTrue(device.has_capability(DeviceCapability.KEYBOARD))
        self.assertFalse(device.has_capability(DeviceCapability.TOUCH))

    def test_device_assignment_tracking(self):
        """Test device assignment state."""
        device = InputDevice(
            id="mouse1",
            name="Test Mouse",
            device_type=DeviceType.POINTER,
        )
        self.assertFalse(device.is_assigned)
        device.seat_id = "seat-123"
        self.assertTrue(device.is_assigned)

    def test_device_equality(self):
        """Test device equality based on ID."""
        device1 = InputDevice(id="mouse1", name="Mouse 1", device_type=DeviceType.POINTER)
        device2 = InputDevice(id="mouse1", name="Different Name", device_type=DeviceType.POINTER)
        device3 = InputDevice(id="mouse2", name="Mouse 1", device_type=DeviceType.POINTER)

        self.assertEqual(device1, device2)  # Same ID
        self.assertNotEqual(device1, device3)  # Different ID


class TestCursor(unittest.TestCase):
    """Tests for Cursor class."""

    def test_default_cursor(self):
        """Test default cursor state."""
        cursor = Cursor()
        self.assertEqual(cursor.position.x, 0)
        self.assertEqual(cursor.position.y, 0)
        self.assertTrue(cursor.visible)
        self.assertEqual(cursor.cursor_name, "left_ptr")

    def test_move_to(self):
        """Test absolute cursor movement."""
        cursor = Cursor()
        cursor.move_to(500, 300)
        self.assertEqual(cursor.position.x, 500)
        self.assertEqual(cursor.position.y, 300)

    def test_move_by(self):
        """Test relative cursor movement."""
        cursor = Cursor()
        cursor.move_to(100, 100)
        cursor.move_by(50, -25)
        self.assertEqual(cursor.position.x, 150)
        self.assertEqual(cursor.position.y, 75)


class TestGrab(unittest.TestCase):
    """Tests for Grab class."""

    def test_grab_creation(self):
        """Test grab creation."""
        grab = Grab(
            mode=GrabMode.POINTER_LOCK,
            client_id="game-window",
        )
        self.assertEqual(grab.mode, GrabMode.POINTER_LOCK)
        self.assertEqual(grab.client_id, "game-window")
        self.assertTrue(grab.is_active)

    def test_inactive_grab(self):
        """Test NONE grab mode is inactive."""
        grab = Grab(mode=GrabMode.NONE, client_id="test")
        self.assertFalse(grab.is_active)


class TestSeat(unittest.TestCase):
    """Tests for Seat class."""

    def test_seat_creation(self):
        """Test basic seat creation."""
        seat = Seat(name="seat0")
        self.assertEqual(seat.name, "seat0")
        self.assertEqual(seat.state, SeatState.ACTIVE)
        self.assertFalse(seat.has_pointer)
        self.assertFalse(seat.has_keyboard)
        self.assertFalse(seat.is_complete)

    def test_add_pointer_device(self):
        """Test adding pointer device to seat."""
        seat = Seat(name="seat0")
        seat.add_pointer_device("mouse1")
        self.assertTrue(seat.has_pointer)
        self.assertIn("mouse1", seat.pointer_devices)

    def test_add_keyboard_device(self):
        """Test adding keyboard device to seat."""
        seat = Seat(name="seat0")
        seat.add_keyboard_device("keyboard1")
        self.assertTrue(seat.has_keyboard)
        self.assertIn("keyboard1", seat.keyboard_devices)

    def test_complete_seat(self):
        """Test complete seat has both pointer and keyboard."""
        seat = Seat(name="seat0")
        seat.add_pointer_device("mouse1")
        self.assertFalse(seat.is_complete)
        seat.add_keyboard_device("keyboard1")
        self.assertTrue(seat.is_complete)

    def test_remove_device(self):
        """Test removing devices from seat."""
        seat = Seat(name="seat0")
        seat.add_pointer_device("mouse1")
        seat.add_pointer_device("mouse2")
        seat.remove_pointer_device("mouse1")
        self.assertNotIn("mouse1", seat.pointer_devices)
        self.assertIn("mouse2", seat.pointer_devices)

    def test_pointer_grab(self):
        """Test pointer grab management."""
        seat = Seat(name="seat0")
        self.assertFalse(seat.is_pointer_grabbed)

        grab = seat.set_pointer_grab("game", GrabMode.POINTER_LOCK)
        self.assertTrue(seat.is_pointer_grabbed)
        self.assertEqual(grab.client_id, "game")

        seat.release_pointer_grab()
        self.assertFalse(seat.is_pointer_grabbed)

    def test_keyboard_grab(self):
        """Test keyboard grab management."""
        seat = Seat(name="seat0")
        self.assertFalse(seat.is_keyboard_grabbed)

        grab = seat.set_keyboard_grab("terminal")
        self.assertTrue(seat.is_keyboard_grabbed)
        self.assertEqual(grab.client_id, "terminal")

        seat.release_keyboard_grab()
        self.assertFalse(seat.is_keyboard_grabbed)


class TestDisplayBounds(unittest.TestCase):
    """Tests for DisplayBounds class."""

    def test_default_bounds(self):
        """Test default display bounds."""
        bounds = DisplayBounds()
        self.assertEqual(bounds.width, 1920)
        self.assertEqual(bounds.height, 1080)

    def test_contains_position(self):
        """Test position containment check."""
        bounds = DisplayBounds(x=0, y=0, width=1920, height=1080)

        self.assertTrue(bounds.contains(Position(0, 0)))
        self.assertTrue(bounds.contains(Position(960, 540)))
        self.assertTrue(bounds.contains(Position(1919, 1079)))
        self.assertFalse(bounds.contains(Position(1920, 1080)))
        self.assertFalse(bounds.contains(Position(-1, 0)))


if __name__ == "__main__":
    unittest.main()
