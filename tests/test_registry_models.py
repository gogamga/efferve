"""Tests for Device model and DeviceClassification enum."""

from datetime import UTC, datetime

from efferve.registry.models import Device, DeviceClassification
from efferve.registry.store import is_locally_administered


class TestDeviceClassification:
    def test_enum_values(self):
        assert DeviceClassification.resident == "resident"
        assert DeviceClassification.frequent == "frequent"
        assert DeviceClassification.passerby == "passerby"
        assert DeviceClassification.unknown == "unknown"

    def test_all_members(self):
        assert set(DeviceClassification.__members__) == {
            "resident",
            "frequent",
            "passerby",
            "unknown",
        }


class TestDeviceModel:
    def test_instantiation_defaults(self):
        device = Device(mac_address="AA:CC:F3:1A:41:68")
        assert device.mac_address == "AA:CC:F3:1A:41:68"
        assert device.display_name is None
        assert device.hostname is None
        assert device.vendor is None
        assert device.signal_strength == -100
        assert device.visit_count == 1
        assert device.classification == DeviceClassification.unknown
        assert device.is_randomized_mac is False

    def test_instantiation_with_values(self):
        now = datetime.now(UTC)
        device = Device(
            mac_address="11:33:5A:81:A8:CF",
            display_name="My Phone",
            hostname="iphone",
            vendor="Apple",
            first_seen=now,
            last_seen=now,
            signal_strength=-42,
            visit_count=5,
            classification=DeviceClassification.resident,
            is_randomized_mac=False,
            ap_name="Living Room",
            ssid="HomeNet",
        )
        assert device.display_name == "My Phone"
        assert device.signal_strength == -42
        assert device.classification == DeviceClassification.resident
        assert device.ap_name == "Living Room"


class TestLocallyAdministered:
    def test_real_mac_not_locally_administered(self):
        # First octet 0x00 — bit 1 is 0
        assert is_locally_administered("00:22:49:70:97:BE") is False

    def test_locally_administered_mac(self):
        # First octet 0xFA — bit 1 is 1 (randomized)
        assert is_locally_administered("FA:23:5B:93:CB:03") is True

    def test_another_locally_administered(self):
        # First octet 0xF2 — bit 1 is 1
        assert is_locally_administered("F2:BC:F4:2C:54:8C") is True

    def test_real_oui_mac(self):
        # First octet 0xAA — bit 1 is 1 (AA = 10101010, bit1 set)
        assert is_locally_administered("AA:CC:F3:1A:41:68") is True

    def test_globally_unique_mac(self):
        # First octet 0x08 — bit 1 is 0
        assert is_locally_administered("08:11:4E:E7:0E:35") is False
