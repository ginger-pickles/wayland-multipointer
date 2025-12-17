"""
Unit tests for configuration management.
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from src.mpx_wayland.config import (
    Config,
    GlobalConfig,
    SeatConfig,
    DeviceMapping,
    DeviceMapConfig,
    ConfigManager,
    ConfigError,
    get_device_identifier,
)


class TestConfigDataClasses(unittest.TestCase):
    """Tests for configuration data classes."""

    def test_global_config_defaults(self):
        """Test GlobalConfig default values."""
        config = GlobalConfig()
        self.assertTrue(config.auto_assign_new_devices)
        self.assertEqual(config.default_seat, "seat0")
        self.assertFalse(config.verbose)

    def test_seat_config_defaults(self):
        """Test SeatConfig default values."""
        config = SeatConfig(name="test")
        self.assertEqual(config.name, "test")
        self.assertTrue(config.enabled)
        self.assertEqual(config.cursor_theme, "default")
        self.assertEqual(config.cursor_size, 24)
        self.assertEqual(config.pointer_devices, [])

    def test_config_creates_default_seat(self):
        """Test Config creates default seat if none provided."""
        config = Config()
        self.assertEqual(len(config.seats), 1)
        self.assertEqual(config.seats[0].name, "seat0")

    def test_device_mapping(self):
        """Test DeviceMapping creation."""
        mapping = DeviceMapping(
            device_id="1234:5678",
            seat_name="aux",
            device_name="Gaming Mouse",
        )
        self.assertEqual(mapping.device_id, "1234:5678")
        self.assertEqual(mapping.seat_name, "aux")


class TestConfigManager(unittest.TestCase):
    """Tests for ConfigManager."""

    def setUp(self):
        """Create temporary config directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = Path(self.temp_dir)
        self.manager = ConfigManager(self.config_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)

    def test_load_default_config(self):
        """Test loading config when file doesn't exist."""
        config = self.manager.load_config()
        self.assertIsInstance(config, Config)
        self.assertEqual(len(config.seats), 1)

    def test_save_and_load_config(self):
        """Test saving and loading config."""
        config = Config(
            global_config=GlobalConfig(default_seat="custom"),
            seats=[
                SeatConfig(name="seat0"),
                SeatConfig(name="aux", cursor_size=32),
            ],
        )
        self.manager.save_config(config)

        # Create new manager to force reload
        manager2 = ConfigManager(self.config_dir)
        loaded = manager2.load_config()

        self.assertEqual(loaded.global_config.default_seat, "custom")
        self.assertEqual(len(loaded.seats), 2)
        self.assertEqual(loaded.seats[1].name, "aux")
        self.assertEqual(loaded.seats[1].cursor_size, 32)

    def test_add_seat(self):
        """Test adding a new seat configuration."""
        self.manager.load_config()
        self.manager.add_seat(SeatConfig(name="gaming"))

        config = self.manager.load_config()
        seat_names = [s.name for s in config.seats]
        self.assertIn("gaming", seat_names)

    def test_add_duplicate_seat(self):
        """Test adding duplicate seat raises error."""
        self.manager.load_config()
        self.manager.add_seat(SeatConfig(name="aux"))

        with self.assertRaises(ConfigError):
            self.manager.add_seat(SeatConfig(name="aux"))

    def test_remove_seat(self):
        """Test removing a seat configuration."""
        config = Config(seats=[
            SeatConfig(name="seat0"),
            SeatConfig(name="aux"),
        ])
        self.manager.save_config(config)

        self.manager.remove_seat("aux")

        config = self.manager.load_config()
        seat_names = [s.name for s in config.seats]
        self.assertNotIn("aux", seat_names)

    def test_cannot_remove_default_seat(self):
        """Test that default seat cannot be removed."""
        self.manager.load_config()
        with self.assertRaises(ConfigError):
            self.manager.remove_seat("seat0")

    def test_update_seat(self):
        """Test updating seat configuration."""
        self.manager.load_config()
        self.manager.update_seat("seat0", cursor_size=48)

        config = self.manager.load_config()
        self.assertEqual(config.seats[0].cursor_size, 48)

    def test_update_nonexistent_seat(self):
        """Test updating non-existent seat raises error."""
        self.manager.load_config()
        with self.assertRaises(ConfigError):
            self.manager.update_seat("nonexistent", cursor_size=48)


class TestDeviceMapping(unittest.TestCase):
    """Tests for device mapping management."""

    def setUp(self):
        """Create temporary config directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = Path(self.temp_dir)
        self.manager = ConfigManager(self.config_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)

    def test_load_empty_device_map(self):
        """Test loading device map when file doesn't exist."""
        device_map = self.manager.load_device_map()
        self.assertIsInstance(device_map, DeviceMapConfig)
        self.assertEqual(len(device_map.mappings), 0)

    def test_add_device_mapping(self):
        """Test adding a device mapping."""
        mapping = DeviceMapping(
            device_id="1234:5678",
            seat_name="aux",
            device_name="Gaming Mouse",
        )
        self.manager.add_device_mapping(mapping)

        mappings = self.manager.get_all_mappings()
        self.assertEqual(len(mappings), 1)
        self.assertEqual(mappings[0].device_id, "1234:5678")

    def test_update_existing_mapping(self):
        """Test updating existing device mapping."""
        mapping1 = DeviceMapping(
            device_id="1234:5678",
            seat_name="seat0",
            device_name="Mouse",
        )
        self.manager.add_device_mapping(mapping1)

        mapping2 = DeviceMapping(
            device_id="1234:5678",
            seat_name="aux",
            device_name="Mouse Updated",
        )
        self.manager.add_device_mapping(mapping2)

        mappings = self.manager.get_all_mappings()
        self.assertEqual(len(mappings), 1)  # Still only one mapping
        self.assertEqual(mappings[0].seat_name, "aux")

    def test_remove_device_mapping(self):
        """Test removing a device mapping."""
        mapping = DeviceMapping(
            device_id="1234:5678",
            seat_name="aux",
        )
        self.manager.add_device_mapping(mapping)
        self.manager.remove_device_mapping("1234:5678")

        mappings = self.manager.get_all_mappings()
        self.assertEqual(len(mappings), 0)

    def test_get_seat_for_device(self):
        """Test looking up seat for device."""
        mapping = DeviceMapping(
            device_id="1234:5678",
            seat_name="gaming",
        )
        self.manager.add_device_mapping(mapping)

        seat = self.manager.get_seat_for_device("1234:5678")
        self.assertEqual(seat, "gaming")

        seat = self.manager.get_seat_for_device("unknown")
        self.assertIsNone(seat)

    def test_get_seat_by_vendor_product(self):
        """Test looking up seat by vendor:product."""
        mapping = DeviceMapping(
            device_id="046d:c332",  # Logitech gaming mouse format
            seat_name="gaming",
        )
        self.manager.add_device_mapping(mapping)

        # Match by vendor_product parameter
        seat = self.manager.get_seat_for_device(
            "some/sysfs/path",
            vendor_product="046d:c332"
        )
        self.assertEqual(seat, "gaming")


class TestDeviceIdentifier(unittest.TestCase):
    """Tests for device identifier generation."""

    def test_get_device_identifier(self):
        """Test creating device identifier from IDs."""
        identifier = get_device_identifier(0x046d, 0xc332)
        self.assertEqual(identifier, "046d:c332")

    def test_zero_padding(self):
        """Test identifier is zero-padded correctly."""
        identifier = get_device_identifier(0x1, 0x2)
        self.assertEqual(identifier, "0001:0002")


class TestDefaultConfig(unittest.TestCase):
    """Tests for default configuration creation."""

    def test_create_default_config(self):
        """Test creating default config with two seats."""
        config = ConfigManager.create_default_config()

        self.assertEqual(len(config.seats), 2)
        seat_names = [s.name for s in config.seats]
        self.assertIn("seat0", seat_names)
        self.assertIn("aux", seat_names)


if __name__ == "__main__":
    unittest.main()
