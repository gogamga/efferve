"""Mock sniffer for development and testing.

Produces fake BeaconEvents on a timer with a mix of realistic
device behaviors: stable residents, intermittent visitors, and
randomized-MAC passersby.
"""

import asyncio
import logging
import random
from collections.abc import Callable
from datetime import UTC, datetime

from efferve.sniffer.base import BaseSniffer, BeaconEvent

logger = logging.getLogger(__name__)

# Stable devices (real OUI prefixes)
_RESIDENT_DEVICES = [
    ("AA:BB:CC:11:22:33", "Home-iPhone", -42),
    ("AA:BB:CC:44:55:66", "Living-Room-TV", -35),
    ("AA:BB:CC:77:88:99", "Work-Laptop", -50),
]

_VISITOR_DEVICES = [
    ("DD:EE:FF:11:22:33", "Guest-Phone", -60),
    ("DD:EE:FF:44:55:66", "Neighbor-Tablet", -72),
]

# Locally administered MACs (randomized — bit 1 of first octet set)
_RANDOM_MACS = [
    "FA:12:34:56:78:9A",
    "F2:AB:CD:EF:01:23",
    "FE:99:88:77:66:55",
]


class MockSniffer(BaseSniffer):
    """Generates fake WiFi presence events for development."""

    def __init__(self, poll_interval: int = 5) -> None:
        self.poll_interval = poll_interval
        self._callbacks: list[Callable[[BeaconEvent], None]] = []
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._tick = 0

    async def start(self) -> None:
        logger.info("Starting mock sniffer (interval=%ds)", self.poll_interval)
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        logger.info("Stopping mock sniffer")
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def on_event(self, callback: Callable[[BeaconEvent], None]) -> None:
        self._callbacks.append(callback)

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                now = datetime.now(UTC)
                events = self._generate_events(now)
                for event in events:
                    for cb in self._callbacks:
                        cb(event)
                self._tick += 1
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Mock sniffer error")

            await asyncio.sleep(self.poll_interval)

    def _generate_events(self, now: datetime) -> list[BeaconEvent]:
        events: list[BeaconEvent] = []

        # Residents: always present with slight signal variation
        for mac, _name, base_rssi in _RESIDENT_DEVICES:
            jitter = random.randint(-5, 5)
            events.append(
                BeaconEvent(
                    mac_address=mac,
                    signal_strength=base_rssi + jitter,
                    ssid="HomeNetwork",
                    timestamp=now,
                    source="mock",
                )
            )

        # Visitors: appear intermittently (roughly 40% of ticks)
        for mac, _name, base_rssi in _VISITOR_DEVICES:
            if random.random() < 0.4:
                jitter = random.randint(-8, 8)
                events.append(
                    BeaconEvent(
                        mac_address=mac,
                        signal_strength=base_rssi + jitter,
                        ssid="HomeNetwork",
                        timestamp=now,
                        source="mock",
                    )
                )

        # Random MACs: occasional passersby with weak signal
        if random.random() < 0.3:
            mac = random.choice(_RANDOM_MACS)
            events.append(
                BeaconEvent(
                    mac_address=mac,
                    signal_strength=random.randint(-90, -75),
                    ssid=None,
                    timestamp=now,
                    source="mock",
                )
            )

        return events
