"""
Simulation module for testing Wayland Multi-Pointer without hardware.

Provides virtual devices, simulated compositor, and test scenarios.
"""

from .simulator import (
    SimulatedCompositor,
    VirtualDevice,
    VirtualWindow,
    SimulationEvent,
    SimulationEventType,
    ScenarioRunner,
    create_test_devices,
    scenario_basic_dual_pointer,
    scenario_grab_isolation,
    scenario_device_hotplug,
)

__all__ = [
    "SimulatedCompositor",
    "VirtualDevice",
    "VirtualWindow",
    "SimulationEvent",
    "SimulationEventType",
    "ScenarioRunner",
    "create_test_devices",
    "scenario_basic_dual_pointer",
    "scenario_grab_isolation",
    "scenario_device_hotplug",
]
