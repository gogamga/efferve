"""Alert rule models."""

import enum
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class TriggerType(enum.StrEnum):
    arrive = "arrive"
    depart = "depart"
    both = "both"


class AlertRule(SQLModel, table=True):
    """A rule that fires a webhook when presence changes."""

    id: int | None = Field(default=None, primary_key=True)
    name: str
    trigger_type: TriggerType = TriggerType.both
    person_id: int | None = Field(default=None, foreign_key="person.id")  # None = any person/device
    mac_address: str | None = None  # None = any device. If person_id set, this is ignored.
    webhook_url: str  # Where to POST
    enabled: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
