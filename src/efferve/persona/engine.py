"""Persona engine: CRUD operations for persons and device assignments."""

import logging
from typing import Any

from sqlmodel import Session, select

from efferve.persona.models import Person, PersonDevice
from efferve.registry.models import Device
from efferve.registry.store import get_present_devices, normalize_mac

logger = logging.getLogger(__name__)


def create_person(session: Session, name: str) -> Person:
    """Create a new person."""
    person = Person(name=name)
    session.add(person)
    session.commit()
    session.refresh(person)
    logger.info("Created person: %s (id=%s)", name, person.id)
    return person


def get_person(session: Session, person_id: int) -> Person | None:
    """Get a person by ID."""
    return session.get(Person, person_id)


def list_persons(session: Session) -> list[Person]:
    """List all persons."""
    stmt = select(Person).order_by(Person.name)
    return list(session.exec(stmt).all())


def delete_person(session: Session, person_id: int) -> bool:
    """Delete a person and their device links.

    Returns True if the person was deleted, False if not found.
    """
    person = session.get(Person, person_id)
    if person is None:
        return False

    # Delete device links first
    stmt = select(PersonDevice).where(PersonDevice.person_id == person_id)
    links = session.exec(stmt).all()
    for link in links:
        session.delete(link)

    session.delete(person)
    session.commit()
    logger.info("Deleted person: %s (id=%s)", person.name, person_id)
    return True


def assign_device(session: Session, person_id: int, mac_address: str) -> PersonDevice:
    """Link a device to a person.

    Raises:
        ValueError: If device doesn't exist or is already assigned to another person.
    """
    mac = normalize_mac(mac_address)

    # Check device exists
    device = session.get(Device, mac)
    if device is None:
        raise ValueError(f"Device {mac} does not exist")

    # Check if already assigned to someone else
    existing_link = session.exec(
        select(PersonDevice).where(PersonDevice.mac_address == mac)
    ).first()
    if existing_link is not None and existing_link.person_id != person_id:
        other_person = session.get(Person, existing_link.person_id)
        other_name = other_person.name if other_person else f"person #{existing_link.person_id}"
        raise ValueError(f"Device {mac} is already assigned to {other_name}")

    # Check if already assigned to this person (idempotent)
    link = session.get(PersonDevice, (person_id, mac))
    if link is not None:
        logger.debug("Device %s already assigned to person %s", mac, person_id)
        return link

    # Create link
    link = PersonDevice(person_id=person_id, mac_address=mac)
    session.add(link)
    session.commit()
    session.refresh(link)
    logger.info("Assigned device %s to person %s", mac, person_id)
    return link


def unassign_device(session: Session, person_id: int, mac_address: str) -> bool:
    """Remove a device link from a person.

    Returns True if the link was removed, False if it didn't exist.
    """
    mac = normalize_mac(mac_address)
    link = session.get(PersonDevice, (person_id, mac))
    if link is None:
        return False

    session.delete(link)
    session.commit()
    logger.info("Unassigned device %s from person %s", mac, person_id)
    return True


def get_person_devices(session: Session, person_id: int) -> list[Device]:
    """Get all Device objects for a person."""
    stmt = (
        select(Device)
        .join(PersonDevice, Device.mac_address == PersonDevice.mac_address)  # type: ignore[arg-type]
        .where(PersonDevice.person_id == person_id)
        .order_by(Device.last_seen.desc())  # type: ignore[attr-defined]
    )
    return list(session.exec(stmt).all())


def get_person_for_device(session: Session, mac_address: str) -> Person | None:
    """Reverse lookup: which person owns this device?"""
    mac = normalize_mac(mac_address)
    link = session.exec(select(PersonDevice).where(PersonDevice.mac_address == mac)).first()
    if link is None:
        return None
    return session.get(Person, link.person_id)


def get_present_persons(session: Session, grace_seconds: int = 180) -> list[dict[str, Any]]:
    """Return list of dicts with person presence information.

    Each dict contains:
        - person: Person object
        - present_devices: list[Device] (devices currently present)
        - is_present: bool (True if any device is present)

    A person is considered present if ANY of their assigned devices is present.
    """
    all_persons = list_persons(session)
    present_devices = get_present_devices(session, grace_seconds)
    present_macs = {d.mac_address for d in present_devices}

    result = []
    for person in all_persons:
        if person.id is None:
            continue
        person_devices = get_person_devices(session, person.id)
        present_person_devices = [d for d in person_devices if d.mac_address in present_macs]
        is_present = len(present_person_devices) > 0

        result.append(
            {
                "person": person,
                "present_devices": present_person_devices,
                "is_present": is_present,
            }
        )

    return result
