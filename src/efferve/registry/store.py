"""Device CRUD operations, classification, and presence queries."""

import logging
from datetime import UTC, datetime, timedelta

from mac_vendor_lookup import MacLookup, VendorNotFoundError
from sqlmodel import Session, select

from efferve.registry.models import Device, DeviceClassification
from efferve.sniffer.base import BeaconEvent

logger = logging.getLogger(__name__)

_mac_lookup = MacLookup()

# Gap threshold: a new "visit" is counted when the device reappears
# after being absent for at least this long.
_VISIT_GAP_SECONDS = 30 * 60  # 30 minutes


def normalize_mac(mac: str) -> str:
    """Normalize a MAC address to uppercase colon-separated format."""
    cleaned = mac.upper().replace("-", ":").replace(".", "")
    # Handle bare hex (e.g. "AABBCCDDEEFF")
    if ":" not in cleaned and len(cleaned) == 12:
        cleaned = ":".join(cleaned[i : i + 2] for i in range(0, 12, 2))
    return cleaned


def is_locally_administered(mac: str) -> bool:
    """Check if a MAC is locally administered (randomized).

    Bit 1 of the first octet is the U/L bit. If set, the address
    is locally administered — typically a randomized MAC.
    """
    first_octet = int(normalize_mac(mac).split(":")[0], 16)
    return bool(first_octet & 0x02)


def lookup_vendor(mac: str) -> str | None:
    """Look up the device manufacturer from OUI database."""
    try:
        return _mac_lookup.lookup(normalize_mac(mac))
    except VendorNotFoundError:
        return None
    except Exception:
        logger.debug("Vendor lookup failed for %s", mac, exc_info=True)
        return None


def upsert_device(session: Session, event: BeaconEvent) -> Device:
    """Create or update a Device from a BeaconEvent."""
    mac = normalize_mac(event.mac_address)
    device = session.get(Device, mac)

    if device is None:
        device = Device(
            mac_address=mac,
            first_seen=event.timestamp,
            last_seen=event.timestamp,
            signal_strength=event.signal_strength,
            visit_count=1,
            is_randomized_mac=is_locally_administered(mac),
            vendor=lookup_vendor(mac),
            ssid=event.ssid,
        )
        session.add(device)
    else:
        # Count a new visit if gap exceeds threshold
        # SQLite stores naive datetimes; normalize both for comparison
        last_seen = device.last_seen
        last = last_seen.replace(tzinfo=UTC) if last_seen.tzinfo is None else last_seen
        gap = (event.timestamp - last).total_seconds()
        if gap > _VISIT_GAP_SECONDS:
            device.visit_count += 1

        device.last_seen = event.timestamp
        if event.signal_strength != 0:  # 0 is sentinel for "no RF data"
            device.signal_strength = event.signal_strength
        if event.ssid:
            device.ssid = event.ssid

    session.commit()
    session.refresh(device)
    return device


def classify_device(device: Device) -> DeviceClassification:
    """Determine classification based on visit patterns."""
    if device.is_randomized_mac:
        return DeviceClassification.passerby

    age_days = (device.last_seen - device.first_seen).total_seconds() / 86400

    if device.visit_count >= 5 and age_days >= 3:
        return DeviceClassification.resident
    if device.visit_count >= 3:
        return DeviceClassification.frequent
    if device.visit_count == 1 and device.signal_strength < -75:
        return DeviceClassification.passerby

    return DeviceClassification.unknown


def reclassify_device(session: Session, device: Device) -> Device:
    """Re-evaluate and update a device's classification."""
    device.classification = classify_device(device)
    session.commit()
    session.refresh(device)
    return device


def get_all_devices(
    session: Session,
    classification: DeviceClassification | None = None,
) -> list[Device]:
    """Get all devices, optionally filtered by classification."""
    stmt = select(Device)
    if classification is not None:
        stmt = stmt.where(Device.classification == classification)
    stmt = stmt.order_by(Device.last_seen.desc())  # type: ignore[union-attr]
    return list(session.exec(stmt).all())


def get_device(session: Session, mac: str) -> Device | None:
    """Get a single device by MAC address."""
    return session.get(Device, normalize_mac(mac))


def get_present_devices(session: Session, grace_seconds: int = 180) -> list[Device]:
    """Get devices seen within the grace period (currently present)."""
    # Use naive UTC for SQLite compatibility (SQLite strips tzinfo)
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=grace_seconds)
    stmt = (
        select(Device)
        .where(Device.last_seen >= cutoff)  # type: ignore[arg-type]
        .order_by(Device.last_seen.desc())  # type: ignore[union-attr]
    )
    return list(session.exec(stmt).all())
