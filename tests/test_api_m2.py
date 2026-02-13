"""API endpoint tests for M2: persona, alerts, device management."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlmodel import Session

from efferve.alerts.models import AlertRule, TriggerType
from efferve.persona.models import Person, PersonDevice
from efferve.registry.models import Device, PresenceEvent, PresenceLog


def test_patch_device_name(client: TestClient, session: Session):
    session.add(Device(mac_address="AA:BB:CC:DD:EE:FF"))
    session.commit()

    resp = client.patch("/api/devices/AA:BB:CC:DD:EE:FF", json={"display_name": "My Phone"})
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "My Phone"


def test_patch_device_not_found(client: TestClient):
    resp = client.patch("/api/devices/00:00:00:00:00:00", json={"display_name": "Ghost"})
    assert resp.status_code == 404


def test_create_person_api(client: TestClient):
    resp = client.post("/api/persons", json={"name": "Alice"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "Alice"
    assert "id" in resp.json()


def test_list_persons_api(client: TestClient):
    client.post("/api/persons", json={"name": "Alice"})
    client.post("/api/persons", json={"name": "Bob"})

    resp = client.get("/api/persons")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_person_detail_api(client: TestClient):
    create_resp = client.post("/api/persons", json={"name": "Alice"})
    person_id = create_resp.json()["id"]

    resp = client.get(f"/api/persons/{person_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["person"]["name"] == "Alice"
    assert "devices" in data


def test_get_person_detail_not_found(client: TestClient):
    assert client.get("/api/persons/99999").status_code == 404


def test_delete_person_api(client: TestClient):
    create_resp = client.post("/api/persons", json={"name": "Alice"})
    person_id = create_resp.json()["id"]

    resp = client.delete(f"/api/persons/{person_id}")
    assert resp.status_code == 200
    assert client.get(f"/api/persons/{person_id}").status_code == 404


def test_delete_person_not_found(client: TestClient):
    assert client.delete("/api/persons/99999").status_code == 404


def test_assign_device_api(client: TestClient, session: Session):
    create_resp = client.post("/api/persons", json={"name": "Alice"})
    person_id = create_resp.json()["id"]
    session.add(Device(mac_address="AA:BB:CC:DD:EE:FF"))
    session.commit()

    resp = client.post(
        f"/api/persons/{person_id}/devices",
        json={"mac_address": "AA:BB:CC:DD:EE:FF"},
    )
    assert resp.status_code == 200
    assert resp.json()["mac_address"] == "AA:BB:CC:DD:EE:FF"


def test_assign_device_invalid_api(client: TestClient):
    create_resp = client.post("/api/persons", json={"name": "Alice"})
    person_id = create_resp.json()["id"]

    resp = client.post(
        f"/api/persons/{person_id}/devices",
        json={"mac_address": "00:00:00:00:00:00"},
    )
    assert resp.status_code == 400


def test_persons_presence_api(client: TestClient, session: Session):
    resp = client.get("/api/persons/presence")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_create_alert_api(client: TestClient):
    resp = client.post(
        "/api/alerts",
        json={
            "name": "Test Alert",
            "webhook_url": "https://example.com/hook",
            "trigger_type": "arrive",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Alert"
    assert data["trigger_type"] == "arrive"


def test_list_alerts_api(client: TestClient):
    client.post("/api/alerts", json={"name": "A1", "webhook_url": "https://example.com/1"})
    client.post("/api/alerts", json={"name": "A2", "webhook_url": "https://example.com/2"})

    resp = client.get("/api/alerts")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_update_alert_api(client: TestClient):
    create_resp = client.post(
        "/api/alerts",
        json={"name": "Old", "webhook_url": "https://example.com/hook"},
    )
    rule_id = create_resp.json()["id"]

    resp = client.patch(f"/api/alerts/{rule_id}", json={"name": "New"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New"


def test_update_alert_not_found(client: TestClient):
    assert client.patch("/api/alerts/99999", json={"name": "X"}).status_code == 404


def test_delete_alert_api(client: TestClient):
    create_resp = client.post(
        "/api/alerts",
        json={"name": "Delete me", "webhook_url": "https://example.com/hook"},
    )
    rule_id = create_resp.json()["id"]

    assert client.delete(f"/api/alerts/{rule_id}").status_code == 200


def test_delete_alert_not_found(client: TestClient):
    assert client.delete("/api/alerts/99999").status_code == 404


def test_presence_history_api(client: TestClient, session: Session):
    session.add(Device(mac_address="AA:BB:CC:DD:EE:FF"))
    session.commit()

    now = datetime.now(UTC).replace(tzinfo=None)
    session.add(PresenceLog(
        mac_address="AA:BB:CC:DD:EE:FF",
        event_type=PresenceEvent.arrive,
        timestamp=now,
    ))
    session.commit()

    resp = client.get("/api/presence/history")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["mac_address"] == "AA:BB:CC:DD:EE:FF"


def test_presence_history_api_filtered(client: TestClient, session: Session):
    session.add(Device(mac_address="AA:BB:CC:DD:EE:01"))
    session.add(Device(mac_address="AA:BB:CC:DD:EE:02"))
    session.commit()

    now = datetime.now(UTC).replace(tzinfo=None)
    session.add(PresenceLog(mac_address="AA:BB:CC:DD:EE:01", event_type=PresenceEvent.arrive, timestamp=now))
    session.add(PresenceLog(mac_address="AA:BB:CC:DD:EE:02", event_type=PresenceEvent.arrive, timestamp=now))
    session.commit()

    resp = client.get("/api/presence/history", params={"mac": "AA:BB:CC:DD:EE:01"})
    assert resp.status_code == 200
    data = resp.json()
    assert all(e["mac_address"] == "AA:BB:CC:DD:EE:01" for e in data)
