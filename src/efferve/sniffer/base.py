"""Base interface for WiFi sniffers."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime


@dataclass
class BeaconEvent:
    """A single observed WiFi device event."""

    mac_address: str
    signal_strength: int  # dBm (negative, e.g. -45)
    ssid: str | None  # SSID from probe request, if available
    timestamp: datetime
    source: str  # "monitor" or "router_api"


class BaseSniffer(ABC):
    """Abstract base for all WiFi capture backends."""

    @abstractmethod
    async def start(self) -> None:
        """Start capturing WiFi events."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop capturing."""

    @abstractmethod
    def on_event(self, callback: Callable[[BeaconEvent], None]) -> None:
        """Register a callback for new beacon events."""
