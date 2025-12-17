"""
Integration tests using the simulation framework.

These tests verify the complete multi-pointer behavior using
the simulated compositor environment.
"""

import unittest
from src.mpx_wayland.simulation import (
    SimulatedCompositor,
    VirtualDevice,
    ScenarioRunner,
    create_test_devices,
    scenario_basic_dual_pointer,
    scenario_grab_isolation,
    scenario_device_hotplug,
)
from src.mpx_wayland.core import (
    DeviceType,
    DeviceCapability,
    GrabMode,
)


class TestSimulatedCompositor(unittest.TestCase):
    """Tests for SimulatedCompositor."""

    def setUp(self):
        """Create compositor for each test."""
        self.compositor = SimulatedCompositor(width=1920, height=1080)

    def test_compositor_initialization(self):
        """Test compositor initializes correctly."""
        self.assertEqual(self.compositor.display.width, 1920)
        self.assertEqual(self.compositor.display.height, 1080)
        self.assertEqual(len(self.compositor.seat_manager.seats), 1)

    def test_connect_device(self):
        """Test connecting a virtual device."""
        device = VirtualDevice(
            id="test_mouse",
            name="Test Mouse",
            device_type=DeviceType.POINTER,
            capabilities={DeviceCapability.POINTER},
        )
        self.compositor.connect_device(device, "seat0")

        self.assertIn("test_mouse", self.compositor.devices)
        self.assertTrue(self.compositor.devices["test_mouse"].is_connected)

    def test_disconnect_device(self):
        """Test disconnecting a virtual device."""
        device = VirtualDevice(
            id="test_mouse",
            name="Test Mouse",
            device_type=DeviceType.POINTER,
            capabilities={DeviceCapability.POINTER},
        )
        self.compositor.connect_device(device, "seat0")
        self.compositor.disconnect_device("test_mouse")

        self.assertFalse(self.compositor.devices["test_mouse"].is_connected)

    def test_create_window(self):
        """Test creating virtual windows."""
        window = self.compositor.create_window(
            "win1", "Test Window", 100, 100, 800, 600
        )
        self.assertIn("win1", self.compositor.windows)
        self.assertEqual(window.title, "Test Window")

    def test_window_position_check(self):
        """Test window position containment."""
        self.compositor.create_window("win1", "Window", 100, 100, 800, 600)
        window = self.compositor.windows["win1"]

        from src.mpx_wayland.core import Position
        self.assertTrue(window.contains(Position(500, 400)))  # Inside
        self.assertFalse(window.contains(Position(50, 50)))   # Outside


class TestDualPointerScenario(unittest.TestCase):
    """Tests for dual pointer scenarios."""

    def setUp(self):
        """Create compositor with two seats."""
        self.compositor = SimulatedCompositor()
        self.compositor.seat_manager.create_seat("aux")

    def test_two_seats_exist(self):
        """Test that two seats exist after setup."""
        seats = self.compositor.seat_manager.seats
        self.assertEqual(len(seats), 2)

    def test_independent_cursors(self):
        """Test that two cursors can exist at different positions."""
        # Create and connect devices
        mouse1 = VirtualDevice(
            id="mouse1", name="Mouse 1",
            device_type=DeviceType.POINTER,
            capabilities={DeviceCapability.POINTER}
        )
        mouse2 = VirtualDevice(
            id="mouse2", name="Mouse 2",
            device_type=DeviceType.POINTER,
            capabilities={DeviceCapability.POINTER}
        )

        self.compositor.connect_device(mouse1, "seat0")
        self.compositor.connect_device(mouse2, "aux")

        # Move to different positions
        self.compositor.move_pointer("mouse1", absolute=(100, 100))
        self.compositor.move_pointer("mouse2", absolute=(900, 500))

        # Verify positions
        seat0 = self.compositor.seat_manager.get_seat_by_name("seat0")
        aux = self.compositor.seat_manager.get_seat_by_name("aux")

        self.assertEqual((seat0.cursor.position.x, seat0.cursor.position.y), (100, 100))
        self.assertEqual((aux.cursor.position.x, aux.cursor.position.y), (900, 500))

    def test_pointer_motion_routing(self):
        """Test that pointer motion routes to correct seat."""
        mouse1 = VirtualDevice(
            id="mouse1", name="Mouse 1",
            device_type=DeviceType.POINTER,
            capabilities={DeviceCapability.POINTER}
        )
        mouse2 = VirtualDevice(
            id="mouse2", name="Mouse 2",
            device_type=DeviceType.POINTER,
            capabilities={DeviceCapability.POINTER}
        )

        self.compositor.connect_device(mouse1, "seat0")
        self.compositor.connect_device(mouse2, "aux")

        # Move mouse1 multiple times
        self.compositor.move_pointer("mouse1", dx=50, dy=50)
        self.compositor.move_pointer("mouse1", dx=50, dy=50)

        seat0 = self.compositor.seat_manager.get_seat_by_name("seat0")
        aux = self.compositor.seat_manager.get_seat_by_name("aux")

        # seat0 should have moved, aux should be at 0,0
        self.assertEqual(seat0.cursor.position.x, 100)
        self.assertEqual(aux.cursor.position.x, 0)


class TestGrabIsolation(unittest.TestCase):
    """Tests for grab isolation between seats."""

    def setUp(self):
        """Set up compositor with two seats and a game window."""
        self.compositor = SimulatedCompositor()
        self.compositor.seat_manager.create_seat("aux")

        # Connect devices
        mouse1 = VirtualDevice(
            id="mouse1", name="Mouse 1",
            device_type=DeviceType.POINTER,
            capabilities={DeviceCapability.POINTER}
        )
        mouse2 = VirtualDevice(
            id="mouse2", name="Mouse 2",
            device_type=DeviceType.POINTER,
            capabilities={DeviceCapability.POINTER}
        )
        self.compositor.connect_device(mouse1, "seat0")
        self.compositor.connect_device(mouse2, "aux")

        # Create game window
        self.compositor.create_window("game", "Fullscreen Game", 0, 0, 1920, 1080)

    def test_grab_one_seat(self):
        """Test grabbing one seat's pointer."""
        seat0 = self.compositor.seat_manager.get_seat_by_name("seat0")
        result = self.compositor.request_grab("game", seat0.id, GrabMode.POINTER_LOCK)

        self.assertTrue(result)
        self.assertTrue(seat0.is_pointer_grabbed)

    def test_grab_does_not_affect_other_seat(self):
        """Test that grabbing one seat doesn't affect the other."""
        seat0 = self.compositor.seat_manager.get_seat_by_name("seat0")
        aux = self.compositor.seat_manager.get_seat_by_name("aux")

        self.compositor.request_grab("game", seat0.id, GrabMode.POINTER_LOCK)

        self.assertTrue(seat0.is_pointer_grabbed)
        self.assertFalse(aux.is_pointer_grabbed)

    def test_other_pointer_can_move_during_grab(self):
        """Test that the other pointer can still move when one is grabbed."""
        seat0 = self.compositor.seat_manager.get_seat_by_name("seat0")
        aux = self.compositor.seat_manager.get_seat_by_name("aux")

        # Grab seat0
        self.compositor.request_grab("game", seat0.id, GrabMode.POINTER_LOCK)

        # Move aux pointer
        self.compositor.move_pointer("mouse2", absolute=(500, 300))

        self.assertEqual(aux.cursor.position.x, 500)
        self.assertEqual(aux.cursor.position.y, 300)

    def test_release_grab(self):
        """Test releasing a grab."""
        seat0 = self.compositor.seat_manager.get_seat_by_name("seat0")
        self.compositor.request_grab("game", seat0.id, GrabMode.POINTER_LOCK)
        self.compositor.release_grab("game", seat0.id)

        self.assertFalse(seat0.is_pointer_grabbed)


class TestScenarioRunner(unittest.TestCase):
    """Tests for the scenario runner."""

    def test_run_basic_dual_pointer_scenario(self):
        """Run the basic dual pointer scenario."""
        compositor = SimulatedCompositor()
        runner = ScenarioRunner(compositor)

        steps = scenario_basic_dual_pointer(compositor)
        result = runner.run_scenario(
            "basic_dual_pointer",
            steps,
            "Test independent dual pointer movement"
        )

        self.assertTrue(result)

    def test_run_grab_isolation_scenario(self):
        """Run the grab isolation scenario."""
        compositor = SimulatedCompositor()
        runner = ScenarioRunner(compositor)

        steps = scenario_grab_isolation(compositor)
        result = runner.run_scenario(
            "grab_isolation",
            steps,
            "Test that grab on one seat doesn't affect others"
        )

        self.assertTrue(result)

    def test_run_device_hotplug_scenario(self):
        """Run the device hotplug scenario."""
        compositor = SimulatedCompositor()
        runner = ScenarioRunner(compositor)

        steps = scenario_device_hotplug(compositor)
        result = runner.run_scenario(
            "device_hotplug",
            steps,
            "Test device connect/disconnect"
        )

        self.assertTrue(result)

    def test_scenario_report(self):
        """Test generating scenario report."""
        compositor = SimulatedCompositor()
        runner = ScenarioRunner(compositor)

        runner.run_scenario("test1", [lambda c: True], "First test")
        runner.run_scenario("test2", [lambda c: False], "Second test (fails)")

        report = runner.get_report()

        self.assertIn("test1", report)
        self.assertIn("test2", report)
        self.assertIn("PASS", report)
        self.assertIn("FAIL", report)


class TestEventLogging(unittest.TestCase):
    """Tests for event logging in simulation."""

    def test_events_recorded(self):
        """Test that events are recorded during simulation."""
        compositor = SimulatedCompositor()

        device = VirtualDevice(
            id="mouse1", name="Mouse",
            device_type=DeviceType.POINTER,
            capabilities={DeviceCapability.POINTER}
        )
        compositor.connect_device(device, "seat0")
        compositor.move_pointer("mouse1", dx=100, dy=50)
        compositor.click_button("mouse1", 1, True)

        # Should have recorded events
        self.assertGreater(len(compositor.event_log), 0)

    def test_event_callback(self):
        """Test that event callbacks are called."""
        compositor = SimulatedCompositor()
        events = []
        compositor.add_event_callback(events.append)

        device = VirtualDevice(
            id="mouse1", name="Mouse",
            device_type=DeviceType.POINTER,
            capabilities={DeviceCapability.POINTER}
        )
        compositor.connect_device(device, "seat0")

        self.assertGreater(len(events), 0)


class TestAsciiVisualization(unittest.TestCase):
    """Tests for ASCII visualization."""

    def test_render_ascii(self):
        """Test ASCII rendering produces output."""
        compositor = SimulatedCompositor()
        compositor.seat_manager.create_seat("aux")

        # Connect devices and move them
        mouse1 = VirtualDevice(
            id="mouse1", name="Mouse 1",
            device_type=DeviceType.POINTER,
            capabilities={DeviceCapability.POINTER}
        )
        mouse2 = VirtualDevice(
            id="mouse2", name="Mouse 2",
            device_type=DeviceType.POINTER,
            capabilities={DeviceCapability.POINTER}
        )
        compositor.connect_device(mouse1, "seat0")
        compositor.connect_device(mouse2, "aux")

        compositor.move_pointer("mouse1", absolute=(500, 300))
        compositor.move_pointer("mouse2", absolute=(1400, 700))

        # Create a window
        compositor.create_window("win1", "Window", 100, 100, 400, 300)

        output = compositor.render_ascii(80, 24)

        self.assertIsInstance(output, str)
        self.assertIn("Cursors:", output)  # Legend should be present
        self.assertGreater(len(output.split('\n')), 20)

    def test_state_summary(self):
        """Test state summary output."""
        compositor = SimulatedCompositor()
        compositor.seat_manager.create_seat("aux")

        device = VirtualDevice(
            id="mouse1", name="Mouse 1",
            device_type=DeviceType.POINTER,
            capabilities={DeviceCapability.POINTER}
        )
        compositor.connect_device(device, "seat0")

        summary = compositor.get_state_summary()

        self.assertIn("Seats:", summary)
        self.assertIn("Devices:", summary)
        self.assertIn("seat0", summary)
        self.assertIn("aux", summary)


class TestFullWorkflow(unittest.TestCase):
    """Full workflow integration tests."""

    def test_game_with_secondary_pointer(self):
        """
        Test the primary use case: game on one pointer, other apps on another.

        Scenario:
        1. Two seats set up (seat0 for game, aux for other apps)
        2. Game window requests pointer grab on seat0
        3. User can still use aux pointer for other windows
        """
        compositor = SimulatedCompositor()
        compositor.seat_manager.create_seat("aux")

        # Set up devices
        game_mouse = VirtualDevice(
            id="gaming_mouse", name="Gaming Mouse",
            device_type=DeviceType.POINTER,
            capabilities={DeviceCapability.POINTER}
        )
        desktop_mouse = VirtualDevice(
            id="desktop_mouse", name="Desktop Mouse",
            device_type=DeviceType.POINTER,
            capabilities={DeviceCapability.POINTER}
        )
        compositor.connect_device(game_mouse, "seat0")
        compositor.connect_device(desktop_mouse, "aux")

        # Create windows
        compositor.create_window("game", "UT99", 0, 0, 1920, 1080)
        compositor.create_window("browser", "Firefox", 1920, 100, 800, 600)

        # Game grabs seat0 pointer
        seat0 = compositor.seat_manager.get_seat_by_name("seat0")
        aux = compositor.seat_manager.get_seat_by_name("aux")

        grab_result = compositor.request_grab("game", seat0.id, GrabMode.POINTER_LOCK)
        self.assertTrue(grab_result)
        self.assertTrue(seat0.is_pointer_grabbed)

        # Desktop mouse can still move freely
        compositor.move_pointer("desktop_mouse", absolute=(2200, 300))
        self.assertEqual(aux.cursor.position.x, 1919)  # Clamped to display
        self.assertEqual(aux.cursor.position.y, 300)

        # Can click in the aux seat
        click_result = compositor.click_button("desktop_mouse", 1, True)
        self.assertEqual(click_result, aux.id)

        # Game still has grab
        self.assertTrue(seat0.is_pointer_grabbed)

        # Release grab (e.g., game minimized)
        compositor.release_grab("game", seat0.id)
        self.assertFalse(seat0.is_pointer_grabbed)


if __name__ == "__main__":
    unittest.main()
