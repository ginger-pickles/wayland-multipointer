"""
Configuration module for Wayland Multi-Pointer.

Provides persistent configuration management for seats and device mappings.
"""

from .config import (
    Config,
    GlobalConfig,
    SeatConfig,
    DeviceMapping,
    DeviceMapConfig,
    ConfigManager,
    ConfigError,
    load_config,
    get_device_identifier,
    CONFIG_DIR,
    CONFIG_FILE,
    DEVICE_MAP_FILE,
)

__all__ = [
    "Config",
    "GlobalConfig",
    "SeatConfig",
    "DeviceMapping",
    "DeviceMapConfig",
    "ConfigManager",
    "ConfigError",
    "load_config",
    "get_device_identifier",
    "CONFIG_DIR",
    "CONFIG_FILE",
    "DEVICE_MAP_FILE",
]
