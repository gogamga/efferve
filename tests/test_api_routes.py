"""Tests for API endpoints."""

from datetime import UTC, datetime

from sqlmodel import Session

from efferve.database import get_session
from efferve.main import app
from efferve.registry.models import Device, DeviceClassification


def _seed_devices(client) -> None:
    """Insert test devices via the overridden session."""
    session_gen = app.dependency_overrides[get_session]()
    session = next(session_gen)
    now = datetime.now(UTC)
    session.add(
        Device(
            mac_address="08:11:4E:4E:64:7A",
            classification=DeviceClassification.resident,
            first_seen=now,
            last_seen=now,
            signal_strength=-42,
        )
    )
    session.add(
        Device(
            mac_address="08:11:4E:5F:75:8B",
            classification=DeviceClassification.passerby,
            first_seen=now,
            last_seen=now,
            signal_strength=-80,
        )
    )
    session.commit()
    session.close()


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestDeviceEndpoints:
    def test_list_devices_empty(self, client):
        resp = client.get("/api/devices")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_devices_populated(self, client):
        _seed_devices(client)
        resp = client.get("/api/devices")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_list_devices_filtered(self, client):
        _seed_devices(client)
        resp = client.get("/api/devices?classification=resident")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["mac_address"] == "08:11:4E:4E:64:7A"

    def test_device_detail_found(self, client):
        _seed_devices(client)
        resp = client.get("/api/devices/08:11:4E:4E:64:7A")
        assert resp.status_code == 200
        assert resp.json()["mac_address"] == "08:11:4E:4E:64:7A"

    def test_device_detail_not_found(self, client):
        resp = client.get("/api/devices/FF:10:26:3C:52:68")
        assert resp.status_code == 404

    def test_presence_summary(self, client):
        _seed_devices(client)
        resp = client.get("/api/presence")
        assert resp.status_code == 200
        data = resp.json()
        assert "present_count" in data
        assert "grace_seconds" in data
        assert "devices" in data
        assert isinstance(data["devices"], list)
