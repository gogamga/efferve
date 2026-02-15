"""Device model and classification enum."""

import enum
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class DeviceClassification(enum.StrEnum):
    resident = "resident"
    frequent = "frequent"
    passerby = "passerby"
    unknown = "unknown"


class Device(SQLModel, table=True):
    mac_address: str = Field(primary_key=True)
    display_name: str | None = None
    hostname: str | None = None
    vendor: str | None = None
    first_seen: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_seen: datetime = Field(default_factory=lambda: datetime.now(UTC))
    signal_strength: int = -100  # latest dBm
    visit_count: int = 1
    classification: DeviceClassification = DeviceClassification.unknown
    is_randomized_mac: bool = False
    ap_name: str | None = None
    ssid: str | None = None


class PresenceEvent(enum.StrEnum):
    arrive = "arrive"
    depart = "depart"


class PresenceLog(SQLModel, table=True):
    """Time-series log of device presence changes."""

    id: int | None = Field(default=None, primary_key=True)
    mac_address: str = Field(index=True, foreign_key="device.mac_address")
    event_type: PresenceEvent
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
