"""Tests for persona engine: CRUD, device assignment, presence rollup."""

from datetime import UTC, datetime

from sqlmodel import Session

import pytest

from efferve.persona.engine import (
    assign_device,
    create_person,
    delete_person,
    get_person,
    get_person_devices,
    get_person_for_device,
    get_present_persons,
    list_persons,
    unassign_device,
)
from efferve.persona.models import Person, PersonDevice
from efferve.registry.models import Device


def test_create_person(session: Session):
    person = create_person(session, name="Alice")
    assert person.id is not None
    assert person.name == "Alice"


def test_list_persons(session: Session):
    create_person(session, name="Charlie")
    create_person(session, name="Alice")
    create_person(session, name="Bob")
    persons = list_persons(session)
    names = [p.name for p in persons]
    assert names == ["Alice", "Bob", "Charlie"]


def test_get_person(session: Session):
    person = create_person(session, name="Alice")
    fetched = get_person(session, person.id)
    assert fetched is not None
    assert fetched.name == "Alice"


def test_get_person_invalid_id(session: Session):
    assert get_person(session, 99999) is None


def test_delete_person(session: Session):
    person = create_person(session, name="Alice")
    device = Device(mac_address="AA:CC:F3:1A:41:68")
    session.add(device)
    session.commit()
    assign_device(session, person.id, "AA:CC:F3:1A:41:68")

    assert delete_person(session, person.id) is True
    assert get_person(session, person.id) is None
    assert get_person_devices(session, person.id) == []


def test_delete_person_invalid_id(session: Session):
    assert delete_person(session, 99999) is False


def test_assign_device(session: Session):
    person = create_person(session, name="Alice")
    device = Device(mac_address="AA:CC:F3:1A:41:68")
    session.add(device)
    session.commit()

    link = assign_device(session, person.id, "AA:CC:F3:1A:41:68")
    assert link.person_id == person.id
    assert link.mac_address == "AA:CC:F3:1A:41:68"


def test_assign_device_not_found(session: Session):
    person = create_person(session, name="Alice")
    with pytest.raises(ValueError, match="does not exist"):
        assign_device(session, person.id, "00:11:27:3D:53:69")


def test_assign_device_already_assigned(session: Session):
    p1 = create_person(session, name="Alice")
    p2 = create_person(session, name="Bob")
    device = Device(mac_address="AA:CC:F3:1A:41:68")
    session.add(device)
    session.commit()

    assign_device(session, p1.id, "AA:CC:F3:1A:41:68")
    with pytest.raises(ValueError, match="already assigned"):
        assign_device(session, p2.id, "AA:CC:F3:1A:41:68")


def test_assign_device_idempotent(session: Session):
    person = create_person(session, name="Alice")
    device = Device(mac_address="AA:CC:F3:1A:41:68")
    session.add(device)
    session.commit()

    link1 = assign_device(session, person.id, "AA:CC:F3:1A:41:68")
    link2 = assign_device(session, person.id, "AA:CC:F3:1A:41:68")
    assert link1.person_id == link2.person_id
    assert link1.mac_address == link2.mac_address


def test_unassign_device(session: Session):
    person = create_person(session, name="Alice")
    device = Device(mac_address="AA:CC:F3:1A:41:68")
    session.add(device)
    session.commit()
    assign_device(session, person.id, "AA:CC:F3:1A:41:68")

    assert unassign_device(session, person.id, "AA:CC:F3:1A:41:68") is True


def test_unassign_device_nonexistent(session: Session):
    assert unassign_device(session, 99999, "00:11:27:3D:53:69") is False


def test_get_person_devices(session: Session):
    person = create_person(session, name="Alice")
    for mac in ("AA:CC:F3:1A:41:6A", "AA:CC:F3:1A:41:6B"):
        session.add(Device(mac_address=mac))
    session.commit()

    assign_device(session, person.id, "AA:CC:F3:1A:41:6A")
    assign_device(session, person.id, "AA:CC:F3:1A:41:6B")

    devices = get_person_devices(session, person.id)
    macs = {d.mac_address for d in devices}
    assert macs == {"AA:CC:F3:1A:41:6A", "AA:CC:F3:1A:41:6B"}


def test_get_person_for_device(session: Session):
    person = create_person(session, name="Alice")
    session.add(Device(mac_address="AA:CC:F3:1A:41:68"))
    session.commit()
    assign_device(session, person.id, "AA:CC:F3:1A:41:68")

    found = get_person_for_device(session, "AA:CC:F3:1A:41:68")
    assert found is not None
    assert found.name == "Alice"


def test_get_person_for_device_none(session: Session):
    session.add(Device(mac_address="AA:CC:F3:1A:41:68"))
    session.commit()
    assert get_person_for_device(session, "AA:CC:F3:1A:41:68") is None


def test_get_present_persons(session: Session):
    person = create_person(session, name="Alice")
    now = datetime.now(UTC).replace(tzinfo=None)
    session.add(Device(mac_address="AA:CC:F3:1A:41:68", last_seen=now))
    session.commit()
    assign_device(session, person.id, "AA:CC:F3:1A:41:68")

    result = get_present_persons(session)
    assert len(result) == 1
    assert result[0]["person"].name == "Alice"
    assert result[0]["is_present"] is True
    assert len(result[0]["present_devices"]) == 1
