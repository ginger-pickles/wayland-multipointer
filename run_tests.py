#!/usr/bin/env python3
"""
Test runner and demonstration script for MPX Wayland.

This script runs all tests and provides a demonstration of the
multi-pointer functionality using the simulation framework.
"""

import sys
import os
import unittest
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))


def run_unit_tests() -> bool:
    """Run all unit tests."""
    print("=" * 60)
    print("Running Unit Tests")
    print("=" * 60)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Load tests from test directories
    suite.addTests(loader.discover('tests/unit', pattern='test_*.py'))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


def run_integration_tests() -> bool:
    """Run all integration tests."""
    print("\n" + "=" * 60)
    print("Running Integration Tests")
    print("=" * 60)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.discover('tests/integration', pattern='test_*.py'))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


def run_demo():
    """Run interactive demonstration."""
    print("\n" + "=" * 60)
    print("MPX Wayland Demonstration")
    print("=" * 60)

    from src.mpx_wayland.simulation import (
        SimulatedCompositor,
        VirtualDevice,
        ScenarioRunner,
        scenario_basic_dual_pointer,
        scenario_grab_isolation,
    )
    from src.mpx_wayland.core import DeviceType, DeviceCapability, GrabMode

    # Create simulated environment
    print("\n[1] Creating simulated compositor (1920x1080)")
    compositor = SimulatedCompositor(width=1920, height=1080)
    compositor.seat_manager.create_seat("aux")
    print(f"    Created {len(compositor.seat_manager.seats)} seats: seat0, aux")

    # Connect virtual devices
    print("\n[2] Connecting virtual devices")
    mouse1 = VirtualDevice(
        id="gaming_mouse",
        name="Logitech G502",
        device_type=DeviceType.POINTER,
        capabilities={DeviceCapability.POINTER}
    )
    mouse2 = VirtualDevice(
        id="trackball",
        name="Kensington SlimBlade",
        device_type=DeviceType.POINTER,
        capabilities={DeviceCapability.POINTER}
    )
    keyboard1 = VirtualDevice(
        id="gaming_kb",
        name="Corsair K70",
        device_type=DeviceType.KEYBOARD,
        capabilities={DeviceCapability.KEYBOARD}
    )
    keyboard2 = VirtualDevice(
        id="wireless_kb",
        name="Logitech K380",
        device_type=DeviceType.KEYBOARD,
        capabilities={DeviceCapability.KEYBOARD}
    )

    compositor.connect_device(mouse1, "seat0")
    compositor.connect_device(keyboard1, "seat0")
    compositor.connect_device(mouse2, "aux")
    compositor.connect_device(keyboard2, "aux")

    print("    seat0: Logitech G502 + Corsair K70")
    print("    aux:   Kensington SlimBlade + Logitech K380")

    # Create windows
    print("\n[3] Creating virtual windows")
    compositor.create_window("game", "Unreal Tournament 99", 0, 0, 1920, 1080)
    compositor.create_window("browser", "Firefox", 1920, 0, 800, 600)
    compositor.create_window("terminal", "Konsole", 1920, 620, 800, 400)
    print("    - UT99 (fullscreen game on primary display)")
    print("    - Firefox browser")
    print("    - Konsole terminal")

    # Move cursors
    print("\n[4] Moving cursors to different positions")
    compositor.move_pointer("gaming_mouse", absolute=(960, 540))
    compositor.move_pointer("trackball", absolute=(1919, 300))

    seat0 = compositor.seat_manager.get_seat_by_name("seat0")
    aux = compositor.seat_manager.get_seat_by_name("aux")

    print(f"    seat0 cursor: ({seat0.cursor.position.x:.0f}, {seat0.cursor.position.y:.0f})")
    print(f"    aux cursor:   ({aux.cursor.position.x:.0f}, {aux.cursor.position.y:.0f})")

    # Simulate game grabbing pointer
    print("\n[5] Game requests pointer lock (mouselook mode)")
    result = compositor.request_grab("game", seat0.id, GrabMode.POINTER_LOCK)
    print(f"    Grab granted: {result}")
    print(f"    seat0 grabbed: {seat0.is_pointer_grabbed}")
    print(f"    aux grabbed:   {aux.is_pointer_grabbed}")

    # Show that aux can still move
    print("\n[6] Moving aux pointer while game has grab")
    compositor.move_pointer("trackball", absolute=(1919, 700))
    print(f"    aux cursor moved to: ({aux.cursor.position.x:.0f}, {aux.cursor.position.y:.0f})")
    print(f"    seat0 still grabbed: {seat0.is_pointer_grabbed}")

    # Click with aux
    print("\n[7] Clicking with aux pointer (Firefox)")
    compositor.click_button("trackball", 1, True)
    compositor.click_button("trackball", 1, False)
    print("    Click routed to aux seat - Firefox could receive this!")

    # Type with aux keyboard
    print("\n[8] Typing on aux keyboard")
    for key in [30, 31, 32]:  # a, s, d
        compositor.press_key("wireless_kb", key, True)
        compositor.press_key("wireless_kb", key, False)
    print("    Keystrokes routed to aux seat - Firefox could receive input!")

    # Show visual representation
    print("\n[9] ASCII visualization of current state:")
    print(compositor.render_ascii(70, 18))

    # Release grab
    print("\n[10] Game releases pointer grab (alt-tabbed or minimized)")
    compositor.release_grab("game", seat0.id)
    print(f"    seat0 grabbed: {seat0.is_pointer_grabbed}")

    # Run pre-built scenarios
    print("\n" + "=" * 60)
    print("Running Pre-built Test Scenarios")
    print("=" * 60)

    compositor2 = SimulatedCompositor()
    runner = ScenarioRunner(compositor2)

    runner.run_scenario(
        "dual_pointer_independence",
        scenario_basic_dual_pointer(compositor2),
        "Verify two pointers move independently"
    )

    compositor3 = SimulatedCompositor()
    runner2 = ScenarioRunner(compositor3)
    runner2.run_scenario(
        "grab_isolation",
        scenario_grab_isolation(compositor3),
        "Verify grab on one seat doesn't affect others"
    )

    print("\n" + runner.get_report())
    print(runner2.get_report())

    # Show final state
    print("\n" + "=" * 60)
    print("Final State Summary")
    print("=" * 60)
    print(compositor.get_state_summary())

    return True


def main():
    """Main entry point."""
    print("MPX Wayland - Multi-Pointer Support for Wayland")
    print("=" * 60)

    success = True

    # Run unit tests
    if not run_unit_tests():
        success = False

    # Run integration tests
    if not run_integration_tests():
        success = False

    # Run demonstration
    try:
        run_demo()
    except Exception as e:
        print(f"Demo failed: {e}")
        import traceback
        traceback.print_exc()
        success = False

    print("\n" + "=" * 60)
    if success:
        print("ALL TESTS PASSED!")
    else:
        print("SOME TESTS FAILED!")
    print("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
