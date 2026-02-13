"""Person models for device-to-person mapping."""

from datetime import UTC, datetime

from sqlmodel import Field, Relationship, SQLModel


class PersonDevice(SQLModel, table=True):
    """Link table: maps devices to a person."""

    person_id: int = Field(foreign_key="person.id", primary_key=True)
    mac_address: str = Field(foreign_key="device.mac_address", primary_key=True)


class Person(SQLModel, table=True):
    """A person who owns one or more devices."""

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Relationships
    device_links: list[PersonDevice] = Relationship()
