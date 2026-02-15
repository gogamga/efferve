"""Tests for presence history logging and device naming."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session

import efferve.registry.store as store_module
from efferve.registry.models import Device, PresenceEvent, PresenceLog
from efferve.registry.store import (
    detect_presence_changes,
    get_presence_history,
    log_presence_change,
    set_display_name,
)


@pytest.fixture(autouse=True)
def reset_previously_present():
    """Reset the _previously_present set before each test."""
    store_module._previously_present = set()
    yield
    store_module._previously_present = set()


def test_set_display_name(session: Session):
    session.add(Device(mac_address="AA:CC:F3:1A:41:68"))
    session.commit()

    result = set_display_name(session, "AA:CC:F3:1A:41:68", "My Phone")
    assert result is not None
    assert result.display_name == "My Phone"


def test_set_display_name_not_found(session: Session):
    assert set_display_name(session, "00:11:27:3D:53:69", "Ghost") is None


def test_log_presence_change(session: Session):
    session.add(Device(mac_address="AA:CC:F3:1A:41:68"))
    session.commit()

    log = log_presence_change(session, "AA:CC:F3:1A:41:68", PresenceEvent.arrive)
    assert log.id is not None
    assert log.mac_address == "AA:CC:F3:1A:41:68"
    assert log.event_type == PresenceEvent.arrive


def test_get_presence_history(session: Session):
    session.add(Device(mac_address="AA:CC:F3:1A:41:68"))
    session.commit()

    log_presence_change(session, "AA:CC:F3:1A:41:68", PresenceEvent.arrive)
    log_presence_change(session, "AA:CC:F3:1A:41:68", PresenceEvent.depart)

    history = get_presence_history(session)
    assert len(history) == 2
    # Ordered by timestamp desc — depart (newer) first
    assert history[0].event_type == PresenceEvent.depart
    assert history[1].event_type == PresenceEvent.arrive


def test_get_presence_history_filtered(session: Session):
    session.add(Device(mac_address="AA:CC:F3:1A:41:6A"))
    session.add(Device(mac_address="AA:CC:F3:1A:41:6B"))
    session.commit()

    log_presence_change(session, "AA:CC:F3:1A:41:6A", PresenceEvent.arrive)
    log_presence_change(session, "AA:CC:F3:1A:41:6B", PresenceEvent.arrive)

    history = get_presence_history(session, mac_address="AA:CC:F3:1A:41:6A")
    assert len(history) == 1
    assert history[0].mac_address == "AA:CC:F3:1A:41:6A"


def test_detect_presence_changes_arrival(session: Session):
    now = datetime.now(UTC).replace(tzinfo=None)
    session.add(Device(mac_address="AA:CC:F3:1A:41:68", last_seen=now))
    session.commit()

    changes = detect_presence_changes(session)
    assert len(changes) == 1
    mac, event_type = changes[0]
    assert mac == "AA:CC:F3:1A:41:68"
    assert event_type == "arrive"


def test_detect_presence_changes_departure(session: Session):
    store_module._previously_present = {"AA:CC:F3:1A:41:68"}

    old_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1)
    session.add(Device(mac_address="AA:CC:F3:1A:41:68", last_seen=old_time))
    session.commit()

    changes = detect_presence_changes(session)
    assert len(changes) == 1
    mac, event_type = changes[0]
    assert mac == "AA:CC:F3:1A:41:68"
    assert event_type == "depart"


def test_detect_presence_changes_no_change(session: Session):
    now = datetime.now(UTC).replace(tzinfo=None)
    session.add(Device(mac_address="AA:CC:F3:1A:41:68", last_seen=now))
    session.commit()

    # First call detects arrival
    detect_presence_changes(session)
    # Second call with same state — no changes
    changes = detect_presence_changes(session)
    assert len(changes) == 0
