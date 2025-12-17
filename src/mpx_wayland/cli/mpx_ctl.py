#!/usr/bin/env python3
"""
mpx-ctl: Command-line tool for managing Wayland Multi-Pointer seats and devices.

Similar to xinput for X11 MPX, this tool allows:
- Creating/destroying seats
- Listing devices and their assignments
- Assigning devices to seats
- Querying system status
"""

import argparse
import sys
import json
from typing import Optional

from ..core import (
    SeatManager,
    InputDevice,
    DeviceType,
    DeviceCapability,
    SeatState,
    DisplayBounds,
)
from ..config import (
    ConfigManager,
    SeatConfig,
    DeviceMapping,
    get_device_identifier,
)


class MPXController:
    """
    High-level controller for MPX operations.

    Bridges between CLI commands and the core seat manager.
    """

    def __init__(self, config_dir: Optional[str] = None):
        """Initialize controller with optional config directory override."""
        from pathlib import Path

        config_path = Path(config_dir) if config_dir else None
        self.config_manager = ConfigManager(config_path)
        self.seat_manager = SeatManager()

        # Load configuration
        self._load_config()

    def _load_config(self) -> None:
        """Load seats from configuration."""
        config = self.config_manager.load_config()

        # Create configured seats (skip seat0 as it's created by default)
        for seat_config in config.seats:
            if seat_config.name != "seat0" and seat_config.enabled:
                try:
                    self.seat_manager.create_seat(seat_config.name)
                except Exception:
                    pass  # Seat might already exist

    def list_seats(self) -> list:
        """List all seats and their status."""
        return self.seat_manager.get_status()["seats"]

    def list_devices(self) -> list:
        """List all devices and their assignments."""
        return self.seat_manager.get_status()["devices"]

    def create_seat(self, name: str, save: bool = True) -> str:
        """
        Create a new seat.

        Args:
            name: Name for the new seat
            save: Whether to save to configuration

        Returns:
            ID of created seat
        """
        seat_id = self.seat_manager.create_seat(name)

        if save:
            try:
                self.config_manager.add_seat(SeatConfig(name=name))
            except Exception:
                pass  # Config might already have this seat

        return seat_id

    def destroy_seat(self, name: str, save: bool = True) -> None:
        """
        Destroy a seat.

        Args:
            name: Name of seat to destroy
            save: Whether to update configuration
        """
        seat = self.seat_manager.get_seat_by_name(name)
        if not seat:
            raise ValueError(f"Seat '{name}' not found")

        self.seat_manager.destroy_seat(seat.id)

        if save:
            try:
                self.config_manager.remove_seat(name)
            except Exception:
                pass

    def register_device(self, device_id: str, name: str,
                        device_type: str = "pointer",
                        vendor_id: int = 0,
                        product_id: int = 0) -> None:
        """
        Register a new device.

        Args:
            device_id: Unique device identifier
            name: Human-readable device name
            device_type: "pointer", "keyboard", or "both"
            vendor_id: USB vendor ID
            product_id: USB product ID
        """
        capabilities = set()
        if device_type in ("pointer", "both"):
            capabilities.add(DeviceCapability.POINTER)
            dtype = DeviceType.POINTER
        if device_type in ("keyboard", "both"):
            capabilities.add(DeviceCapability.KEYBOARD)
            dtype = DeviceType.KEYBOARD
        if device_type == "both":
            dtype = DeviceType.UNKNOWN

        device = InputDevice(
            id=device_id,
            name=name,
            device_type=dtype,
            capabilities=capabilities,
            vendor_id=vendor_id,
            product_id=product_id,
        )

        self.seat_manager.register_device(device)

    def assign_device(self, device_id: str, seat_name: str,
                      save: bool = True) -> None:
        """
        Assign a device to a seat.

        Args:
            device_id: Device identifier
            seat_name: Name of target seat
            save: Whether to save mapping to configuration
        """
        seat = self.seat_manager.get_seat_by_name(seat_name)
        if not seat:
            raise ValueError(f"Seat '{seat_name}' not found")

        self.seat_manager.assign_device(device_id, seat.id, force=True)

        if save:
            device = self.seat_manager.get_device(device_id)
            mapping = DeviceMapping(
                device_id=device_id,
                seat_name=seat_name,
                device_name=device.name,
            )
            self.config_manager.add_device_mapping(mapping)

    def unassign_device(self, device_id: str, save: bool = True) -> None:
        """
        Unassign a device from its current seat.

        Args:
            device_id: Device identifier
            save: Whether to update configuration
        """
        self.seat_manager.unassign_device(device_id)

        if save:
            self.config_manager.remove_device_mapping(device_id)

    def get_status(self) -> dict:
        """Get full system status."""
        return self.seat_manager.get_status()

    def get_config(self) -> dict:
        """Get current configuration."""
        config = self.config_manager.load_config()
        return {
            "global": {
                "auto_assign_new_devices": config.global_config.auto_assign_new_devices,
                "default_seat": config.global_config.default_seat,
                "verbose": config.global_config.verbose,
            },
            "seats": [
                {
                    "name": s.name,
                    "enabled": s.enabled,
                    "cursor_theme": s.cursor_theme,
                    "cursor_size": s.cursor_size,
                }
                for s in config.seats
            ],
            "device_mappings": [
                {
                    "device_id": m.device_id,
                    "seat_name": m.seat_name,
                    "device_name": m.device_name,
                }
                for m in self.config_manager.get_all_mappings()
            ],
        }


def cmd_list_seats(args, controller: MPXController) -> int:
    """Handle 'list-seats' command."""
    seats = controller.list_seats()

    if args.json:
        print(json.dumps(seats, indent=2))
    else:
        print("Seats:")
        for seat in seats:
            grabbed = ""
            if seat["pointer_grabbed"]:
                grabbed = " [POINTER GRABBED]"
            if seat["keyboard_grabbed"]:
                grabbed += " [KEYBOARD GRABBED]"

            print(f"  {seat['name']} ({seat['id'][:8]}...)")
            print(f"    State: {seat['state']}{grabbed}")
            print(f"    Cursor: ({seat['cursor_position']['x']:.0f}, "
                  f"{seat['cursor_position']['y']:.0f})")
            print(f"    Pointers: {len(seat['pointer_devices'])} devices")
            print(f"    Keyboards: {len(seat['keyboard_devices'])} devices")
            print()

    return 0


def cmd_list_devices(args, controller: MPXController) -> int:
    """Handle 'list-devices' command."""
    devices = controller.list_devices()

    if args.json:
        print(json.dumps(devices, indent=2))
    else:
        print("Devices:")
        for device in devices:
            seat_info = f"-> {device['seat_id'][:8]}..." if device['seat_id'] else "(unassigned)"
            status = "" if device['available'] else " [UNAVAILABLE]"
            caps = ", ".join(device['capabilities'])

            print(f"  {device['name']}")
            print(f"    ID: {device['id']}")
            print(f"    Type: {device['type']} ({caps})")
            print(f"    Assignment: {seat_info}{status}")
            print()

    return 0


def cmd_create_seat(args, controller: MPXController) -> int:
    """Handle 'create-seat' command."""
    try:
        seat_id = controller.create_seat(args.name)
        print(f"Created seat '{args.name}' with ID {seat_id}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_destroy_seat(args, controller: MPXController) -> int:
    """Handle 'destroy-seat' command."""
    try:
        controller.destroy_seat(args.name)
        print(f"Destroyed seat '{args.name}'")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_assign(args, controller: MPXController) -> int:
    """Handle 'assign' command."""
    try:
        controller.assign_device(args.device, args.seat)
        print(f"Assigned device '{args.device}' to seat '{args.seat}'")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_unassign(args, controller: MPXController) -> int:
    """Handle 'unassign' command."""
    try:
        controller.unassign_device(args.device)
        print(f"Unassigned device '{args.device}'")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_status(args, controller: MPXController) -> int:
    """Handle 'status' command."""
    status = controller.get_status()

    if args.json:
        print(json.dumps(status, indent=2))
    else:
        print("MPX Status")
        print("=" * 40)
        print(f"Default seat: {status['default_seat_id'][:8]}...")
        print(f"Total seats: {len(status['seats'])}")
        print(f"Total devices: {len(status['devices'])}")

        assigned = sum(1 for d in status['devices'] if d['seat_id'])
        print(f"Assigned devices: {assigned}")
        print(f"Unassigned devices: {len(status['devices']) - assigned}")

    return 0


def cmd_config(args, controller: MPXController) -> int:
    """Handle 'config' command."""
    config = controller.get_config()

    if args.json:
        print(json.dumps(config, indent=2))
    else:
        print("Configuration")
        print("=" * 40)
        print("\nGlobal settings:")
        for key, value in config['global'].items():
            print(f"  {key}: {value}")

        print("\nConfigured seats:")
        for seat in config['seats']:
            print(f"  {seat['name']}: enabled={seat['enabled']}, "
                  f"cursor_size={seat['cursor_size']}")

        print("\nDevice mappings:")
        if config['device_mappings']:
            for mapping in config['device_mappings']:
                print(f"  {mapping['device_id']} -> {mapping['seat_name']}"
                      f" ({mapping['device_name']})")
        else:
            print("  (none)")

    return 0


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="mpx-ctl",
        description="Wayland Multi-Pointer control utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  mpx-ctl list-seats              List all seats
  mpx-ctl list-devices            List all input devices
  mpx-ctl create-seat aux         Create a new seat named 'aux'
  mpx-ctl assign mouse1 aux       Assign device 'mouse1' to seat 'aux'
  mpx-ctl status                  Show system status

Similar to xinput for X11 Multi-Pointer X (MPX).
""",
    )

    parser.add_argument(
        "--config-dir",
        help="Override configuration directory",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # list-seats
    subparsers.add_parser("list-seats", help="List all seats")

    # list-devices
    subparsers.add_parser("list-devices", help="List all input devices")

    # create-seat
    p = subparsers.add_parser("create-seat", help="Create a new seat")
    p.add_argument("name", help="Name for the new seat")

    # destroy-seat
    p = subparsers.add_parser("destroy-seat", help="Destroy a seat")
    p.add_argument("name", help="Name of seat to destroy")

    # assign
    p = subparsers.add_parser("assign", help="Assign device to seat")
    p.add_argument("device", help="Device ID to assign")
    p.add_argument("seat", help="Seat name to assign to")

    # unassign
    p = subparsers.add_parser("unassign", help="Unassign device from seat")
    p.add_argument("device", help="Device ID to unassign")

    # status
    subparsers.add_parser("status", help="Show system status")

    # config
    subparsers.add_parser("config", help="Show configuration")

    return parser


def main(argv: Optional[list] = None) -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    controller = MPXController(args.config_dir)

    commands = {
        "list-seats": cmd_list_seats,
        "list-devices": cmd_list_devices,
        "create-seat": cmd_create_seat,
        "destroy-seat": cmd_destroy_seat,
        "assign": cmd_assign,
        "unassign": cmd_unassign,
        "status": cmd_status,
        "config": cmd_config,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args, controller)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
