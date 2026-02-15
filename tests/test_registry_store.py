"""Tests for device store operations."""

from datetime import UTC, datetime, timedelta

from efferve.registry.models import Device, DeviceClassification
from efferve.registry.store import (
    classify_device,
    get_all_devices,
    get_device,
    get_present_devices,
    normalize_mac,
    upsert_device,
)
from efferve.sniffer.base import BeaconEvent


class TestNormalizeMac:
    def test_already_normalized(self):
        assert normalize_mac("AA:CC:F3:1A:41:68") == "AA:CC:F3:1A:41:68"

    def test_lowercase(self):
        assert normalize_mac("aa:cc:f3:1a:41:68") == "AA:CC:F3:1A:41:68"

    def test_dash_separated(self):
        assert normalize_mac("aa-bb-cc-dd-ee-ff") == "AA:CC:F3:1A:41:68"

    def test_bare_hex(self):
        assert normalize_mac("aabbccddeeff") == "AA:CC:F3:1A:41:68"


class TestUpsertDevice:
    def test_creates_new_device(self, session):
        event = BeaconEvent(
            mac_address="08:11:4E:E7:0E:35",
            signal_strength=-45,
            ssid="TestNet",
            timestamp=datetime.now(UTC),
            source="mock",
        )
        device = upsert_device(session, event)
        assert device.mac_address == "08:11:4E:E7:0E:35"
        assert device.signal_strength == -45
        assert device.ssid == "TestNet"
        assert device.visit_count == 1

    def test_updates_existing_device(self, session):
        now = datetime.now(UTC)
        event1 = BeaconEvent(
            mac_address="08:11:4E:E7:0E:35",
            signal_strength=-45,
            ssid="TestNet",
            timestamp=now,
            source="mock",
        )
        upsert_device(session, event1)

        event2 = BeaconEvent(
            mac_address="08:11:4E:E7:0E:35",
            signal_strength=-50,
            ssid="TestNet",
            timestamp=now + timedelta(seconds=10),
            source="mock",
        )
        device = upsert_device(session, event2)
        assert device.signal_strength == -50
        assert device.visit_count == 1  # no gap, same visit

    def test_visit_count_increments_after_gap(self, session):
        now = datetime.now(UTC)
        event1 = BeaconEvent(
            mac_address="08:11:4E:E7:0E:35",
            signal_strength=-45,
            ssid="TestNet",
            timestamp=now,
            source="mock",
        )
        upsert_device(session, event1)

        event2 = BeaconEvent(
            mac_address="08:11:4E:E7:0E:35",
            signal_strength=-45,
            ssid="TestNet",
            timestamp=now + timedelta(minutes=31),
            source="mock",
        )
        device = upsert_device(session, event2)
        assert device.visit_count == 2

    def test_zero_signal_not_overwritten(self, session):
        """OPNsense uses 0 as sentinel — should not overwrite real signal."""
        now = datetime.now(UTC)
        event1 = BeaconEvent(
            mac_address="08:11:4E:E7:0E:35",
            signal_strength=-45,
            ssid="TestNet",
            timestamp=now,
            source="ruckus",
        )
        upsert_device(session, event1)

        event2 = BeaconEvent(
            mac_address="08:11:4E:E7:0E:35",
            signal_strength=0,
            ssid=None,
            timestamp=now + timedelta(seconds=5),
            source="opnsense",
        )
        device = upsert_device(session, event2)
        assert device.signal_strength == -45  # preserved from ruckus


class TestClassifyDevice:
    def test_randomized_mac_is_passerby(self):
        device = Device(
            mac_address="FA:23:5B:93:CB:03",
            is_randomized_mac=True,
            visit_count=10,
            first_seen=datetime.now(UTC) - timedelta(days=30),
            last_seen=datetime.now(UTC),
        )
        assert classify_device(device) == DeviceClassification.passerby

    def test_resident(self):
        device = Device(
            mac_address="08:11:4E:E7:0E:35",
            is_randomized_mac=False,
            visit_count=5,
            first_seen=datetime.now(UTC) - timedelta(days=5),
            last_seen=datetime.now(UTC),
        )
        assert classify_device(device) == DeviceClassification.resident

    def test_frequent(self):
        device = Device(
            mac_address="08:11:4E:E7:0E:35",
            is_randomized_mac=False,
            visit_count=3,
            first_seen=datetime.now(UTC) - timedelta(days=1),
            last_seen=datetime.now(UTC),
        )
        assert classify_device(device) == DeviceClassification.frequent

    def test_single_weak_signal_is_passerby(self):
        device = Device(
            mac_address="08:11:4E:E7:0E:35",
            is_randomized_mac=False,
            visit_count=1,
            signal_strength=-80,
            first_seen=datetime.now(UTC),
            last_seen=datetime.now(UTC),
        )
        assert classify_device(device) == DeviceClassification.passerby

    def test_single_strong_signal_is_unknown(self):
        device = Device(
            mac_address="08:11:4E:E7:0E:35",
            is_randomized_mac=False,
            visit_count=1,
            signal_strength=-40,
            first_seen=datetime.now(UTC),
            last_seen=datetime.now(UTC),
        )
        assert classify_device(device) == DeviceClassification.unknown


class TestPresenceQueries:
    def test_get_present_devices(self, session):
        now = datetime.now(UTC)

        # Present device
        session.add(Device(mac_address="08:11:4E:4E:64:7A", last_seen=now, first_seen=now))
        # Stale device — beyond grace period
        session.add(
            Device(
                mac_address="08:11:4E:5F:75:8B",
                last_seen=now - timedelta(seconds=300),
                first_seen=now - timedelta(days=1),
            )
        )
        session.commit()

        present = get_present_devices(session, grace_seconds=180)
        macs = [d.mac_address for d in present]
        assert "08:11:4E:4E:64:7A" in macs
        assert "08:11:4E:5F:75:8B" not in macs

    def test_get_all_devices_unfiltered(self, session):
        now = datetime.now(UTC)
        session.add(
            Device(
                mac_address="08:11:4E:4E:64:7A",
                classification=DeviceClassification.resident,
                first_seen=now,
                last_seen=now,
            )
        )
        session.add(
            Device(
                mac_address="08:11:4E:5F:75:8B",
                classification=DeviceClassification.passerby,
                first_seen=now,
                last_seen=now,
            )
        )
        session.commit()
        assert len(get_all_devices(session)) == 2

    def test_get_all_devices_filtered(self, session):
        now = datetime.now(UTC)
        session.add(
            Device(
                mac_address="08:11:4E:4E:64:7A",
                classification=DeviceClassification.resident,
                first_seen=now,
                last_seen=now,
            )
        )
        session.add(
            Device(
                mac_address="08:11:4E:5F:75:8B",
                classification=DeviceClassification.passerby,
                first_seen=now,
                last_seen=now,
            )
        )
        session.commit()
        result = get_all_devices(session, classification=DeviceClassification.resident)
        assert len(result) == 1
        assert result[0].mac_address == "08:11:4E:4E:64:7A"

    def test_get_device_found(self, session):
        now = datetime.now(UTC)
        session.add(Device(mac_address="08:11:4E:4E:64:7A", first_seen=now, last_seen=now))
        session.commit()
        assert get_device(session, "08:11:4E:4E:64:7A") is not None

    def test_get_device_not_found(self, session):
        assert get_device(session, "FF:10:26:3C:52:68") is None
