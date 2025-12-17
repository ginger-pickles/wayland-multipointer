"""
Configuration management for Wayland Multi-Pointer.

Handles:
- Loading/saving configuration from YAML files
- Default configuration paths
- Runtime configuration updates
- Device-to-seat persistent mappings
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


# Default configuration paths
XDG_CONFIG_HOME = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
CONFIG_DIR = Path(XDG_CONFIG_HOME) / "mpx-wayland"
CONFIG_FILE = CONFIG_DIR / "config.json"
DEVICE_MAP_FILE = CONFIG_DIR / "devices.json"


@dataclass
class SeatConfig:
    """Configuration for a single seat."""
    name: str
    enabled: bool = True
    cursor_theme: str = "default"
    cursor_size: int = 24
    # Device assignments by identifier (vendor:product or sysfs path)
    pointer_devices: List[str] = field(default_factory=list)
    keyboard_devices: List[str] = field(default_factory=list)


@dataclass
class GlobalConfig:
    """Global configuration options."""
    # Whether to auto-assign new devices to default seat
    auto_assign_new_devices: bool = True
    # Default seat for new devices
    default_seat: str = "seat0"
    # Enable verbose logging
    verbose: bool = False
    # Log file path (empty = stderr only)
    log_file: str = ""
    # Socket path for IPC (empty = default)
    socket_path: str = ""


@dataclass
class Config:
    """Complete MPX configuration."""
    version: int = 1
    global_config: GlobalConfig = field(default_factory=GlobalConfig)
    seats: List[SeatConfig] = field(default_factory=list)

    def __post_init__(self):
        # Ensure at least the default seat exists
        if not self.seats:
            self.seats = [SeatConfig(name="seat0")]


@dataclass
class DeviceMapping:
    """Persistent device-to-seat mapping."""
    # Maps device identifier to seat name
    # Identifier can be "vendor:product" or sysfs path
    device_id: str
    seat_name: str
    device_name: str = ""  # Human-readable name for reference
    priority: int = 0  # Higher priority = preferred matching


@dataclass
class DeviceMapConfig:
    """Complete device mapping configuration."""
    version: int = 1
    mappings: List[DeviceMapping] = field(default_factory=list)


class ConfigError(Exception):
    """Configuration-related error."""
    pass


class ConfigManager:
    """
    Manages MPX configuration files.

    Handles loading, saving, and modifying configuration.
    Supports runtime updates that persist to disk.
    """

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize the config manager.

        Args:
            config_dir: Override default config directory
        """
        self.config_dir = config_dir or CONFIG_DIR
        self.config_file = self.config_dir / "config.json"
        self.device_map_file = self.config_dir / "devices.json"

        self._config: Optional[Config] = None
        self._device_map: Optional[DeviceMapConfig] = None

    def ensure_config_dir(self) -> None:
        """Create config directory if it doesn't exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def load_config(self) -> Config:
        """
        Load configuration from file.

        Creates default config if file doesn't exist.

        Returns:
            Loaded or default configuration
        """
        if self._config is not None:
            return self._config

        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    data = json.load(f)
                self._config = self._parse_config(data)
                logger.info(f"Loaded config from {self.config_file}")
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.error(f"Error loading config: {e}")
                logger.info("Using default configuration")
                self._config = Config()
        else:
            logger.info("Config file not found, using defaults")
            self._config = Config()

        return self._config

    def _parse_config(self, data: Dict[str, Any]) -> Config:
        """Parse config dict into Config object."""
        global_data = data.get("global_config", {})
        global_config = GlobalConfig(
            auto_assign_new_devices=global_data.get("auto_assign_new_devices", True),
            default_seat=global_data.get("default_seat", "seat0"),
            verbose=global_data.get("verbose", False),
            log_file=global_data.get("log_file", ""),
            socket_path=global_data.get("socket_path", ""),
        )

        seats = []
        for seat_data in data.get("seats", []):
            seats.append(SeatConfig(
                name=seat_data.get("name", "seat0"),
                enabled=seat_data.get("enabled", True),
                cursor_theme=seat_data.get("cursor_theme", "default"),
                cursor_size=seat_data.get("cursor_size", 24),
                pointer_devices=seat_data.get("pointer_devices", []),
                keyboard_devices=seat_data.get("keyboard_devices", []),
            ))

        return Config(
            version=data.get("version", 1),
            global_config=global_config,
            seats=seats,
        )

    def save_config(self, config: Optional[Config] = None) -> None:
        """
        Save configuration to file.

        Args:
            config: Config to save (uses current if None)
        """
        if config is not None:
            self._config = config

        if self._config is None:
            raise ConfigError("No configuration to save")

        self.ensure_config_dir()

        data = {
            "version": self._config.version,
            "global_config": asdict(self._config.global_config),
            "seats": [asdict(s) for s in self._config.seats],
        }

        with open(self.config_file, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved config to {self.config_file}")

    def load_device_map(self) -> DeviceMapConfig:
        """
        Load device mapping from file.

        Returns:
            Loaded or empty device mapping
        """
        if self._device_map is not None:
            return self._device_map

        if self.device_map_file.exists():
            try:
                with open(self.device_map_file, "r") as f:
                    data = json.load(f)
                self._device_map = self._parse_device_map(data)
                logger.info(f"Loaded device map from {self.device_map_file}")
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.error(f"Error loading device map: {e}")
                self._device_map = DeviceMapConfig()
        else:
            self._device_map = DeviceMapConfig()

        return self._device_map

    def _parse_device_map(self, data: Dict[str, Any]) -> DeviceMapConfig:
        """Parse device map dict into DeviceMapConfig object."""
        mappings = []
        for m in data.get("mappings", []):
            mappings.append(DeviceMapping(
                device_id=m.get("device_id", ""),
                seat_name=m.get("seat_name", "seat0"),
                device_name=m.get("device_name", ""),
                priority=m.get("priority", 0),
            ))

        return DeviceMapConfig(
            version=data.get("version", 1),
            mappings=mappings,
        )

    def save_device_map(self, device_map: Optional[DeviceMapConfig] = None) -> None:
        """
        Save device mapping to file.

        Args:
            device_map: Device map to save (uses current if None)
        """
        if device_map is not None:
            self._device_map = device_map

        if self._device_map is None:
            raise ConfigError("No device map to save")

        self.ensure_config_dir()

        data = {
            "version": self._device_map.version,
            "mappings": [asdict(m) for m in self._device_map.mappings],
        }

        with open(self.device_map_file, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved device map to {self.device_map_file}")

    # === Configuration Modification ===

    def get_seat_config(self, seat_name: str) -> Optional[SeatConfig]:
        """Get configuration for a specific seat."""
        config = self.load_config()
        for seat in config.seats:
            if seat.name == seat_name:
                return seat
        return None

    def add_seat(self, seat_config: SeatConfig) -> None:
        """
        Add a new seat configuration.

        Args:
            seat_config: Configuration for the new seat

        Raises:
            ConfigError: If seat with same name exists
        """
        config = self.load_config()

        for seat in config.seats:
            if seat.name == seat_config.name:
                raise ConfigError(f"Seat '{seat_config.name}' already exists")

        config.seats.append(seat_config)
        self.save_config(config)

    def remove_seat(self, seat_name: str) -> None:
        """
        Remove a seat configuration.

        Args:
            seat_name: Name of seat to remove

        Raises:
            ConfigError: If seat is the default or doesn't exist
        """
        config = self.load_config()

        if seat_name == config.global_config.default_seat:
            raise ConfigError("Cannot remove the default seat")

        original_count = len(config.seats)
        config.seats = [s for s in config.seats if s.name != seat_name]

        if len(config.seats) == original_count:
            raise ConfigError(f"Seat '{seat_name}' not found")

        self.save_config(config)

    def update_seat(self, seat_name: str, **kwargs) -> None:
        """
        Update a seat configuration.

        Args:
            seat_name: Name of seat to update
            **kwargs: Fields to update

        Raises:
            ConfigError: If seat doesn't exist
        """
        config = self.load_config()

        for seat in config.seats:
            if seat.name == seat_name:
                for key, value in kwargs.items():
                    if hasattr(seat, key):
                        setattr(seat, key, value)
                self.save_config(config)
                return

        raise ConfigError(f"Seat '{seat_name}' not found")

    def add_device_mapping(self, mapping: DeviceMapping) -> None:
        """
        Add a device-to-seat mapping.

        If mapping for device already exists, it's updated.

        Args:
            mapping: The device mapping to add
        """
        device_map = self.load_device_map()

        # Remove existing mapping for this device
        device_map.mappings = [
            m for m in device_map.mappings if m.device_id != mapping.device_id
        ]

        device_map.mappings.append(mapping)
        self.save_device_map(device_map)

    def remove_device_mapping(self, device_id: str) -> None:
        """
        Remove a device mapping.

        Args:
            device_id: ID of device to remove mapping for
        """
        device_map = self.load_device_map()
        device_map.mappings = [
            m for m in device_map.mappings if m.device_id != device_id
        ]
        self.save_device_map(device_map)

    def get_seat_for_device(self, device_id: str,
                            vendor_product: Optional[str] = None) -> Optional[str]:
        """
        Get the configured seat for a device.

        Tries to match by device_id first, then by vendor:product.

        Args:
            device_id: Device identifier (e.g., sysfs path)
            vendor_product: Optional "vendor:product" string

        Returns:
            Seat name if found, None otherwise
        """
        device_map = self.load_device_map()

        # Try exact match first
        for mapping in sorted(device_map.mappings, key=lambda m: -m.priority):
            if mapping.device_id == device_id:
                return mapping.seat_name

        # Try vendor:product match
        if vendor_product:
            for mapping in sorted(device_map.mappings, key=lambda m: -m.priority):
                if mapping.device_id == vendor_product:
                    return mapping.seat_name

        return None

    def get_all_mappings(self) -> List[DeviceMapping]:
        """Get all device mappings."""
        device_map = self.load_device_map()
        return device_map.mappings.copy()

    # === Default Configuration ===

    @staticmethod
    def create_default_config() -> Config:
        """Create a default configuration with two seats."""
        return Config(
            version=1,
            global_config=GlobalConfig(),
            seats=[
                SeatConfig(name="seat0"),
                SeatConfig(name="aux"),
            ]
        )

    def reset_to_defaults(self) -> None:
        """Reset configuration to defaults."""
        self._config = self.create_default_config()
        self._device_map = DeviceMapConfig()
        self.save_config()
        self.save_device_map()


def load_config(config_dir: Optional[Path] = None) -> Config:
    """
    Convenience function to load configuration.

    Args:
        config_dir: Override default config directory

    Returns:
        Loaded configuration
    """
    manager = ConfigManager(config_dir)
    return manager.load_config()


def get_device_identifier(vendor_id: int, product_id: int) -> str:
    """
    Create a device identifier from vendor/product IDs.

    Args:
        vendor_id: USB vendor ID
        product_id: USB product ID

    Returns:
        Identifier string in format "VVVV:PPPP"
    """
    return f"{vendor_id:04x}:{product_id:04x}"
