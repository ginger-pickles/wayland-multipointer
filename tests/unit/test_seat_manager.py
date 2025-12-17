"""
Unit tests for SeatManager.
"""

import unittest
from src.mpx_wayland.core import (
    SeatManager,
    InputDevice,
    DeviceType,
    DeviceCapability,
    GrabMode,
    SeatState,
    DisplayBounds,
    Event,
    EventType,
    SeatNotFoundError,
    DeviceNotFoundError,
    DeviceAlreadyAssignedError,
)


class TestSeatManagerBasic(unittest.TestCase):
    """Basic tests for SeatManager."""

    def test_initialization(self):
        """Test manager creates default seat."""
        manager = SeatManager()
        self.assertEqual(len(manager.seats), 1)
        self.assertEqual(manager.default_seat.name, "seat0")

    def test_custom_default_seat_name(self):
        """Test custom default seat name."""
        manager = SeatManager(default_seat_name="primary")
        self.assertEqual(manager.default_seat.name, "primary")

    def test_create_seat(self):
        """Test creating additional seats."""
        manager = SeatManager()
        seat_id = manager.create_seat("aux")

        self.assertEqual(len(manager.seats), 2)
        seat = manager.get_seat(seat_id)
        self.assertEqual(seat.name, "aux")

    def test_destroy_seat(self):
        """Test destroying a seat."""
        manager = SeatManager()
        aux_id = manager.create_seat("aux")
        self.assertEqual(len(manager.seats), 2)

        manager.destroy_seat(aux_id)
        self.assertEqual(len(manager.seats), 1)

    def test_cannot_destroy_default_seat(self):
        """Test that default seat cannot be destroyed."""
        manager = SeatManager()
        with self.assertRaises(Exception):
            manager.destroy_seat(manager.default_seat.id)

    def test_get_seat_not_found(self):
        """Test getting non-existent seat raises error."""
        manager = SeatManager()
        with self.assertRaises(SeatNotFoundError):
            manager.get_seat("nonexistent-id")

    def test_get_seat_by_name(self):
        """Test finding seat by name."""
        manager = SeatManager()
        manager.create_seat("aux")

        seat = manager.get_seat_by_name("aux")
        self.assertIsNotNone(seat)
        self.assertEqual(seat.name, "aux")

        missing = manager.get_seat_by_name("nonexistent")
        self.assertIsNone(missing)


class TestSeatManagerDevices(unittest.TestCase):
    """Tests for device management in SeatManager."""

    def setUp(self):
        """Set up test fixtures."""
        self.manager = SeatManager()
        self.mouse = InputDevice(
            id="mouse1",
            name="Test Mouse",
            device_type=DeviceType.POINTER,
            capabilities={DeviceCapability.POINTER},
        )
        self.keyboard = InputDevice(
            id="keyboard1",
            name="Test Keyboard",
            device_type=DeviceType.KEYBOARD,
            capabilities={DeviceCapability.KEYBOARD},
        )

    def test_register_device(self):
        """Test registering a device."""
        self.manager.register_device(self.mouse)
        self.assertEqual(len(self.manager.devices), 1)
        self.assertIn(self.mouse, self.manager.devices)

    def test_unregister_device(self):
        """Test unregistering a device."""
        self.manager.register_device(self.mouse)
        self.manager.unregister_device("mouse1")
        self.assertEqual(len(self.manager.devices), 0)

    def test_unregister_nonexistent_device(self):
        """Test unregistering non-existent device raises error."""
        with self.assertRaises(DeviceNotFoundError):
            self.manager.unregister_device("nonexistent")

    def test_assign_device(self):
        """Test assigning device to seat."""
        self.manager.register_device(self.mouse)
        self.manager.assign_device("mouse1", self.manager.default_seat.id)

        device = self.manager.get_device("mouse1")
        self.assertEqual(device.seat_id, self.manager.default_seat.id)
        self.assertIn("mouse1", self.manager.default_seat.pointer_devices)

    def test_assign_keyboard_device(self):
        """Test assigning keyboard device to seat."""
        self.manager.register_device(self.keyboard)
        self.manager.assign_device("keyboard1", self.manager.default_seat.id)

        self.assertIn("keyboard1", self.manager.default_seat.keyboard_devices)

    def test_assign_already_assigned_device(self):
        """Test assigning already-assigned device raises error."""
        self.manager.register_device(self.mouse)
        self.manager.assign_device("mouse1", self.manager.default_seat.id)

        with self.assertRaises(DeviceAlreadyAssignedError):
            self.manager.assign_device("mouse1", self.manager.default_seat.id)

    def test_assign_device_force(self):
        """Test force reassigning device."""
        self.manager.register_device(self.mouse)
        aux_id = self.manager.create_seat("aux")

        self.manager.assign_device("mouse1", self.manager.default_seat.id)
        self.manager.assign_device("mouse1", aux_id, force=True)

        device = self.manager.get_device("mouse1")
        self.assertEqual(device.seat_id, aux_id)

    def test_unassign_device(self):
        """Test unassigning device from seat."""
        self.manager.register_device(self.mouse)
        self.manager.assign_device("mouse1", self.manager.default_seat.id)
        self.manager.unassign_device("mouse1")

        device = self.manager.get_device("mouse1")
        self.assertIsNone(device.seat_id)
        self.assertNotIn("mouse1", self.manager.default_seat.pointer_devices)

    def test_auto_assign_device(self):
        """Test auto-assigning device to default seat."""
        self.manager.register_device(self.mouse)
        seat_id = self.manager.auto_assign_device("mouse1")

        self.assertEqual(seat_id, self.manager.default_seat.id)
        device = self.manager.get_device("mouse1")
        self.assertEqual(device.seat_id, self.manager.default_seat.id)

    def test_unassigned_devices(self):
        """Test listing unassigned devices."""
        self.manager.register_device(self.mouse)
        self.manager.register_device(self.keyboard)

        self.assertEqual(len(self.manager.unassigned_devices), 2)

        self.manager.assign_device("mouse1", self.manager.default_seat.id)
        self.assertEqual(len(self.manager.unassigned_devices), 1)


class TestSeatManagerInputRouting(unittest.TestCase):
    """Tests for input event routing."""

    def setUp(self):
        """Set up test fixtures."""
        self.manager = SeatManager()
        self.manager.set_display_bounds(DisplayBounds(width=1920, height=1080))

        self.mouse1 = InputDevice(
            id="mouse1",
            name="Mouse 1",
            device_type=DeviceType.POINTER,
            capabilities={DeviceCapability.POINTER},
        )
        self.mouse2 = InputDevice(
            id="mouse2",
            name="Mouse 2",
            device_type=DeviceType.POINTER,
            capabilities={DeviceCapability.POINTER},
        )

        # Create second seat
        self.aux_id = self.manager.create_seat("aux")

        # Register and assign devices
        self.manager.register_device(self.mouse1)
        self.manager.register_device(self.mouse2)
        self.manager.assign_device("mouse1", self.manager.default_seat.id)
        self.manager.assign_device("mouse2", self.aux_id)

    def test_route_pointer_motion(self):
        """Test routing pointer motion to correct seat."""
        # Move mouse1 - should affect seat0
        seat_id = self.manager.route_pointer_motion("mouse1", 100, 50)
        self.assertEqual(seat_id, self.manager.default_seat.id)
        self.assertEqual(self.manager.default_seat.cursor.position.x, 100)
        self.assertEqual(self.manager.default_seat.cursor.position.y, 50)

        # Move mouse2 - should affect aux seat
        aux_seat = self.manager.get_seat(self.aux_id)
        seat_id = self.manager.route_pointer_motion("mouse2", 200, 100)
        self.assertEqual(seat_id, self.aux_id)
        self.assertEqual(aux_seat.cursor.position.x, 200)
        self.assertEqual(aux_seat.cursor.position.y, 100)

    def test_pointer_motion_independence(self):
        """Test that pointer movements are independent."""
        # Move both pointers
        self.manager.route_pointer_motion("mouse1", 100, 100)
        self.manager.route_pointer_motion("mouse2", 500, 500)

        # Verify positions
        seat0_pos = self.manager.default_seat.cursor.position
        aux_pos = self.manager.get_seat(self.aux_id).cursor.position

        self.assertEqual((seat0_pos.x, seat0_pos.y), (100, 100))
        self.assertEqual((aux_pos.x, aux_pos.y), (500, 500))

        # Move one pointer, verify other unchanged
        self.manager.route_pointer_motion("mouse1", 50, 0)
        seat0_pos = self.manager.default_seat.cursor.position
        aux_pos = self.manager.get_seat(self.aux_id).cursor.position

        self.assertEqual((seat0_pos.x, seat0_pos.y), (150, 100))
        self.assertEqual((aux_pos.x, aux_pos.y), (500, 500))  # Unchanged

    def test_pointer_motion_clamped(self):
        """Test that pointer stays within display bounds."""
        self.manager.route_pointer_motion("mouse1", 5000, 5000)
        pos = self.manager.default_seat.cursor.position
        self.assertEqual(pos.x, 1919)  # width - 1
        self.assertEqual(pos.y, 1079)  # height - 1

    def test_route_unassigned_device(self):
        """Test routing from unassigned device returns None."""
        self.manager.unassign_device("mouse1")
        result = self.manager.route_pointer_motion("mouse1", 100, 100)
        self.assertIsNone(result)

    def test_route_pointer_button(self):
        """Test routing button events."""
        seat_id = self.manager.route_pointer_button("mouse1", 1, True)
        self.assertEqual(seat_id, self.manager.default_seat.id)

    def test_route_keyboard_key(self):
        """Test routing keyboard events."""
        keyboard = InputDevice(
            id="keyboard1",
            name="Keyboard 1",
            device_type=DeviceType.KEYBOARD,
            capabilities={DeviceCapability.KEYBOARD},
        )
        self.manager.register_device(keyboard)
        self.manager.assign_device("keyboard1", self.manager.default_seat.id)

        seat_id = self.manager.route_keyboard_key("keyboard1", 30, True)  # 'a' key
        self.assertEqual(seat_id, self.manager.default_seat.id)


class TestSeatManagerGrabs(unittest.TestCase):
    """Tests for grab management."""

    def setUp(self):
        """Set up test fixtures."""
        self.manager = SeatManager()
        self.aux_id = self.manager.create_seat("aux")

    def test_request_pointer_grab(self):
        """Test requesting pointer grab."""
        result = self.manager.request_pointer_grab(
            self.manager.default_seat.id,
            "game-window",
            GrabMode.POINTER_LOCK
        )
        self.assertTrue(result)
        self.assertTrue(self.manager.default_seat.is_pointer_grabbed)

    def test_grab_isolation(self):
        """Test that grabbing one seat doesn't affect others."""
        # Grab seat0
        self.manager.request_pointer_grab(
            self.manager.default_seat.id,
            "game-window",
            GrabMode.POINTER_LOCK
        )

        # Verify aux seat is not grabbed
        aux_seat = self.manager.get_seat(self.aux_id)
        self.assertFalse(aux_seat.is_pointer_grabbed)

    def test_double_grab_denied(self):
        """Test that double grab on same seat is denied."""
        self.manager.request_pointer_grab(
            self.manager.default_seat.id,
            "game-window",
            GrabMode.POINTER_LOCK
        )
        result = self.manager.request_pointer_grab(
            self.manager.default_seat.id,
            "another-window",
            GrabMode.POINTER_LOCK
        )
        self.assertFalse(result)

    def test_release_pointer_grab(self):
        """Test releasing pointer grab."""
        self.manager.request_pointer_grab(
            self.manager.default_seat.id,
            "game-window",
            GrabMode.POINTER_LOCK
        )
        self.manager.release_pointer_grab(self.manager.default_seat.id)
        self.assertFalse(self.manager.default_seat.is_pointer_grabbed)

    def test_get_active_grabs(self):
        """Test getting all active grabs."""
        # Initially no grabs
        grabs = self.manager.get_active_grabs()
        self.assertEqual(len(grabs), 0)

        # Add grab
        self.manager.request_pointer_grab(
            self.manager.default_seat.id,
            "game-window",
            GrabMode.POINTER_LOCK
        )
        grabs = self.manager.get_active_grabs()
        self.assertEqual(len(grabs), 1)
        self.assertIn(self.manager.default_seat.id, grabs)


class TestSeatManagerEvents(unittest.TestCase):
    """Tests for event emission."""

    def setUp(self):
        """Set up test fixtures."""
        self.manager = SeatManager()
        self.events = []
        self.manager.add_event_listener(self.events.append)

    def test_seat_created_event(self):
        """Test event emitted when seat created."""
        self.manager.create_seat("aux")
        event = self.events[-1]
        self.assertEqual(event.event_type, EventType.SEAT_CREATED)
        self.assertEqual(event.data["name"], "aux")

    def test_device_added_event(self):
        """Test event emitted when device registered."""
        device = InputDevice(
            id="mouse1",
            name="Test Mouse",
            device_type=DeviceType.POINTER,
        )
        self.manager.register_device(device)
        event = self.events[-1]
        self.assertEqual(event.event_type, EventType.DEVICE_ADDED)
        self.assertEqual(event.device_id, "mouse1")

    def test_device_assigned_event(self):
        """Test event emitted when device assigned."""
        device = InputDevice(
            id="mouse1",
            name="Test Mouse",
            device_type=DeviceType.POINTER,
            capabilities={DeviceCapability.POINTER},
        )
        self.manager.register_device(device)
        self.manager.assign_device("mouse1", self.manager.default_seat.id)

        event = self.events[-1]
        self.assertEqual(event.event_type, EventType.DEVICE_ASSIGNED)
        self.assertEqual(event.device_id, "mouse1")

    def test_remove_event_listener(self):
        """Test removing event listener."""
        # First record how many events we have
        initial_count = len(self.events)
        # Remove the listener
        self.manager.remove_event_listener(self.events.append)
        # Create a new seat - this should NOT add to events
        self.manager.create_seat("aux")
        # Should not have recorded the new event
        self.assertEqual(len(self.events), initial_count)


class TestSeatManagerStatus(unittest.TestCase):
    """Tests for status reporting."""

    def test_get_status(self):
        """Test getting complete status."""
        manager = SeatManager()
        manager.create_seat("aux")

        mouse = InputDevice(
            id="mouse1",
            name="Test Mouse",
            device_type=DeviceType.POINTER,
            capabilities={DeviceCapability.POINTER},
        )
        manager.register_device(mouse)
        manager.assign_device("mouse1", manager.default_seat.id)

        status = manager.get_status()

        self.assertEqual(len(status["seats"]), 2)
        self.assertEqual(len(status["devices"]), 1)
        self.assertIn("default_seat_id", status)


if __name__ == "__main__":
    unittest.main()
